"""The kinds' shell gate: the checker runs its sequence, the coordinator the
board's tools and a few plain programs over its own scratch, the kinds with
no shell run nothing, and every other turn keeps what the harness gives it.
Run as a process, as the harness runs it."""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
GATE = os.path.join(ROOT, "hooks", "kind-bash-gate.py")
HOOKS = os.path.join(ROOT, "hooks", "hooks.json")
TOOLS = os.path.join(ROOT, "tools")

NO_SHELL = ("clean-reader", "fetcher", "grader", "recorder", "reviewer", "comparer",
            "ai-recorder")

#: the two shapes a session's scratch takes, below the root each stands in
SESSION = "claude-1000/-home-u-proj/0b7c6f2e-1d2a-4c3b-9e8f-7a6b5c4d3e2f/scratchpad/sit"
JOBS = ".claude/jobs/0f82a3c4/tmp/sit"


def checker_lines():
    """The checker's lines as agents/checker.md writes them."""
    with open(os.path.join(ROOT, "agents", "checker.md"), encoding="utf-8") as fh:
        body = fh.read()
    return re.findall(r"^\s*`(<tools>/[^`]+)`\s*$", body, re.M)


class Gate(unittest.TestCase):
    def setUp(self):
        self.project = tempfile.mkdtemp()
        # a session's scratchpad stands under /tmp/claude-*/…/scratchpad
        self.base = tempfile.mkdtemp(prefix="claude-", dir=os.path.realpath("/tmp"))
        self.home = tempfile.mkdtemp()
        for d in (self.project, self.base, self.home):
            self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        self.scratch = os.path.join(self.base, SESSION)
        self.mine = self.scratch + "/coordinator"
        self.env = {k: v for k, v in os.environ.items()
                    if k not in ("CLAUDE_PROJECT_DIR", "CLAUDE_PLUGIN_ROOT")}
        self.env["HOME"] = self.home

    def run_hook(self, agent, command, tool="Bash", cwd=None, raw=None, gate=GATE, env=None):
        c = {"cwd": cwd or self.project, "tool_name": tool,
             "tool_input": {"command": command}}
        if agent is not None:
            c["agent_type"] = agent
        data = raw if raw is not None else json.dumps(c).encode()
        done = subprocess.run([sys.executable, "-B", gate], input=data,
                              capture_output=True, env=env or self.env, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stderr, b"")
        lines = done.stdout.decode().splitlines()
        self.assertEqual(len(lines), 1, lines)
        return json.loads(lines[0])

    def denied(self, agent, command, **kw):
        got = self.run_hook(agent, command, **kw)
        self.assertEqual(got.get("hookSpecificOutput", {}).get("permissionDecision"), "deny",
                         (agent, command))
        return got["hookSpecificOutput"]["permissionDecisionReason"]

    def silent(self, agent, command, **kw):
        self.assertEqual(self.run_hook(agent, command, **kw), {}, (agent, command))


class CheckerTest(Gate):
    def fill(self, line, scratch=None):
        s = scratch or self.scratch
        return (line.replace("<tools>", TOOLS)
                .replace("<views>", s + "/coordinator/views/j1")
                .replace("<list>", s + "/coordinator/lists/j1/doc-p1.json")
                .replace("<work>", s + "/check/j2"))

    def test_the_definition_s_own_lines_pass(self):
        """The three lines of agents/checker.md, its placeholders filled."""
        lines = checker_lines()
        self.assertEqual(len(lines), 3, lines)
        for line in lines:
            self.silent("principal:checker", self.fill(line))

    def test_both_shapes_of_a_session_s_scratch(self):
        """Minor 12: the scratch of a session, under /tmp and under
        ~/.claude/jobs/<id>/tmp, passes the listing and the paths."""
        for scratch in (os.path.join(self.base, SESSION), os.path.join(self.home, JOBS)):
            for line in checker_lines():
                with self.subTest(scratch=scratch, line=line):
                    self.silent("principal:checker", self.fill(line, scratch))

    def test_anything_else_is_refused(self):
        t, w = TOOLS, self.scratch + "/check/j2"
        v = self.scratch + "/coordinator/views/j1"
        lst = self.scratch + "/coordinator/lists/j1/doc-p1.json"
        listing = "$(ls %s/tabs | sed -n 's/\\.md$//p')" % w
        far = "/.." * 14
        for command in (
                "ls %s" % w,
                "curl https://example.invalid",
                "git push",
                "claude -p hello",
                "python3 %s/page.py %s/*.json -o %s/tabs" % (t, v, w),
                "%s/board.py status x --versions y" % t,
                "%s/page.py %s/*.json -o %s/tabs; rm -rf %s" % (t, v, w, w),
                "%s/page.py %s/*.json -o %s/tabs && claude -p hi" % (t, v, w),
                "%s/page.py %s/*.json -o %s/tabs | tee z" % (t, v, w),
                "%s/check.py %s/graph.json > %s/out" % (t, w, w),
                "%s/check.py $(claude -p hi)" % t,
                "%s/check.py `claude -p hi`" % t,
                "%s/check.py \"$(claude -p hi)\"" % t,
                "%s/check.py $HOME/g.json" % t,
                "X=1 %s/check.py %s/graph.json" % (t, w),
                "%s/check.py %s/graph.json\nclaude -p hi" % (t, w),
                "%s/check.py 'unclosed" % t,
                "/tmp/page.py x.json -o y",
                "%s/page.py %s/*.json --scope %s" % (t, v, listing),
                "%s/read.py %s %s/tabs --scope %s %s -o %s/graph.json"
                % (t, lst, w, listing, listing, w),
                "%s/read.py %s %s/tabs -o %s" % (t, lst, w, listing),
                "%s/read.py l t --scope $(ls %s/tabs | sed -n 's/\\.md$//p'; claude)" % (t, w),
                "",
                # B1: an assignment word whose value resolves to a tool
                "X=%s%s/check.py claude -p 'write the notebook'" % (far, t),
                "X=%s%s/board.py bash -c 'id -un; echo joined'" % (far, t),
                # B2: verify.py is no longer in the sequence
                "%s/verify.py %s/graph.json %s/tabs" % (t, w, w),
                # S2: an output anywhere but a check directory outside the project
                "%s/read.py %s %s/tabs -o %s/hooks/kind-bash-gate.py" % (t, lst, w, ROOT),
                "%s/page.py %s/*.json -o %s/.claude/agents" % (t, v, self.project),
                "%s/page.py %s/*.json -o %s/elsewhere/tabs" % (t, v, self.scratch),
                "%s/page.py %s/*.json -o %s/check" % (t, v, self.scratch),
                "%s/page.py %s/*.json -o %s/.claude/projects/check/j2/tabs" % (t, v, self.home),
                "%s/page.py %s/*.json -o %s/check/j2/tabs" % (t, v, self.project),
                "%s/page.py %s/*.json -o %s/check/../../x" % (t, v, self.scratch),
                "%s/page.py %s/*.json -o %s/tabs --outlines %s/outlines" % (t, v, w, w),
                "%s/page.py %s/*.json --out %s/tabs" % (t, v, w),
                "%s/page.py %s/*.json --ou %s/tabs" % (t, v, w),
                "%s/page.py %s/*.json -o%s/tabs" % (t, v, w),
                "%s/page.py %s/*.json --out=%s/tabs" % (t, v, w),
                "%s/page.py %s/*.json -o %s/tabs -o %s/x" % (t, v, w, self.project),
                "%s/page.py %s/*.json" % (t, v),
                "%s/page.py %s/../../*/x.json -o %s/tabs" % (t, v, w),
                "%s/page.py %s/*/x.json -o %s/tabs" % (t, self.scratch + "/coordinator", w),
                "%s/page.py %s/?.json -o %s/tabs" % (t, v, w),
                "%s/page.py %s/canon/*.json -o %s/tabs" % (t, ROOT, w),
                "%s/page.py ~/x.json -o %s/tabs" % (t, w),
                "%s/read.py %s %s/tabs --scope canon -o %s/graph.json" % (t, lst, w, w),
                "%s/read.py %s %s/tabs --scope $(ls %s/other/tabs | sed -n 's/\\.md$//p') "
                "-o %s/graph.json" % (t, lst, w, self.scratch + "/check", w),
                "%s/read.py %s %s/tabs --scope %s -o %s/graph.json --project x"
                % (t, lst, w, listing, w),
                "%s/read.py %s %s/tabs --scope %s --state-enum e -o %s/graph.json"
                % (t, lst, w, listing, w),
                "%s/read.py /etc/passwd %s/tabs --scope %s -o %s/graph.json" % (t, w, listing, w),
                "%s/check.py %s/graph.json --only acyclic" % (t, w),
                "%s/check.py --list" % t,
                "%s/check.py %s/graph.json %s/other.json" % (t, w, w),
                "%s/check.py %s/.principal/notebook.json" % (t, self.project),
                # minor 1: braces
                "%s/check.py %s/{graph,other}.json" % (t, w),
        ):
            with self.subTest(command=command):
                why = self.denied("principal:checker", command)
                self.assertIn("a checker runs only", why)

    def test_a_tool_by_a_relative_path_is_refused(self):
        """B1's fix: a program word is absolute."""
        self.denied("principal:checker", "tools/check.py %s/check/j/graph.json"
                    % self.scratch, cwd=ROOT)
        self.denied("principal:checker", "./check.py %s/check/j/graph.json"
                    % self.scratch, cwd=TOOLS)


class AssignmentFuzzTest(Gate):
    """B1 and its neighbours: whatever is in front of the tool's path, the
    shell would run something else, and the gate refuses it."""

    def forms(self, tool, args):
        far = "/.." * 14
        path = "%s/%s" % (TOOLS, tool)
        return [
            "X=%s%s bash -c 'id -un'" % (far, path),
            "X=%s%s %s %s" % (far, path, path, args),
            "X=1 %s %s" % (path, args),
            "X=1\t%s %s" % (path, args),
            "\tX=1 %s %s" % (path, args),
            "X+=1 %s %s" % (path, args),
            "_x9=%s %s %s" % (path, path, args),
            "'X'=1 %s %s" % (path, args),
            "\"X=%s%s\" bash" % (far, path),
            "X=%s%s" % (far, path),
            "env X=1 %s %s" % (path, args),
            "env %s %s" % (path, args),
            "command %s %s" % (path, args),
            "exec %s %s" % (path, args),
            "builtin %s %s" % (path, args),
            "nohup %s %s" % (path, args),
            "time %s %s" % (path, args),
            "%s \\\n%s" % (path, args),
            "%s %s\\\n; bash" % (path, args),
            "%s %s\nbash" % (path, args),
            "%s %s\rbash" % (path, args),
            "/nonexistent/..%s %s" % (path, args),
            "%s/../tools/%s %s" % (TOOLS, "x" + tool, args),
            "%s%s %s" % (path, "=", args),
            "'%s=' %s" % (path, args),
            "%s/%s %s" % (self.base, tool, args),
        ]

    def test_the_checker(self):
        w = self.scratch + "/check/j2"
        for command in self.forms("check.py", "%s/graph.json" % w):
            with self.subTest(command=command):
                self.denied("principal:checker", command)

    def test_the_coordinator(self):
        m = self.mine
        args = "next %s/board --versions %s/versions.json" % (m, m)
        for command in self.forms("board.py", args):
            with self.subTest(command=command):
                self.denied("principal:coordinator", command)

    def test_quotes_around_the_program_word_name_the_same_program(self):
        w = self.scratch + "/check/j2"
        self.silent("principal:checker", "'%s/check.py' %s/graph.json" % (TOOLS, w))
        self.silent("principal:checker", "\"%s/check.py\"\t%s/graph.json" % (TOOLS, w))
        self.silent("principal:checker", "%s/../tools/check.py %s/graph.json" % (TOOLS, w))


class CoordinatorTest(Gate):
    def test_what_it_runs(self):
        t, m = TOOLS, self.mine
        transcript = self.home + "/.claude/projects/-p/s1/subagents/agent-a1.jsonl"
        for command in (
                "%s/board.py next %s/board --versions %s/versions.json" % (t, m, m),
                "%s/board.py claim %s/board s1-b1-r1-seal --by coordinator "
                "--versions %s/versions.json --now 2030-01-02T03:04:05Z "
                "--out %s/out" % (t, m, m, m),
                "%s/board.py done %s/board s1-b1-r1-seal --versions %s/versions.json --by "
                "coordinator --result %s/results/s1-b1-r1-seal.json --now "
                "2030-01-02T03:04:05Z --out %s/out" % (t, m, m, m, m),
                "%s/board.py fail %s/board s1-b1-r1-seal --versions %s/versions.json --by "
                "coordinator --reason helper --now 2030-01-02T03:04:05Z --out %s/out"
                % (t, m, m, m),
                "%s/board.py status %s/board --versions %s/versions.json --json" % (t, m, m),
                "%s/views.py %s/t.jsonl %s/lists/j1 --list-only" % (t, m, m),
                "%s/views.py %s %s/lists/j1 --list-only" % (t, transcript, m),
                "%s/views.py %s %s/views/j1 --doc %s/lists/j1/doc-p1.json"
                % (t, transcript, m, m),
                "date -u",
                "date -u +%Y-%m-%dT%H:%M:%SZ",
                "sha256sum %s/replies/j1" % m,
                "mkdir -p %s/board" % m,
                "mkdir -p %s/board %s/out" % (m, m),
                "jq -r '.runnable[0]' %s/next.json" % m,
                "jq '.[] | .id' %s/x.json" % m,
                "jq -c --arg k v '{k: $k}' %s/x.json" % m,
                "jq -rc .state %s/board/jobs/j1.json" % m,
        ):
            with self.subTest(command=command):
                self.silent("principal:coordinator", command)

    def test_both_shapes_of_a_session_s_scratch(self):
        for scratch in (os.path.join(self.base, SESSION), os.path.join(self.home, JOBS)):
            m = scratch + "/coordinator"
            for command in ("%s/board.py next %s/board --versions %s/versions.json"
                            % (TOOLS, m, m),
                            "mkdir -p %s/out" % m,
                            "%s/views.py %s/t.jsonl %s/views/j1 --doc %s/lists/j1/doc-p.json"
                            % (TOOLS, m, m, m)):
                with self.subTest(command=command):
                    self.silent("principal:coordinator", command)

    def test_anything_else_is_refused(self):
        t, s, m, p = TOOLS, self.scratch, self.mine, self.project
        for command in (
                "date", "date -s 2030-01-01", "date -u +%s extra",
                "sha256sum", "sha256sum -c sums",
                "mkdir %s/x" % m, "mkdir -p relative", "mkdir -p %s/../x" % m,
                "mkdir -p %s/sub" % p, "mkdir -p /",
                "cat %s/replies/j1" % m, "rm -rf %s" % s, "claude -p hi", "git status",
                "%s/page.py x -o y" % t,
                "%s/board.py next %s/board --versions %s/versions.json > z" % (t, m, m),
                "jq . x | sh",
                "jq \"$(cat x)\" y",
                "sha256sum %s/r; curl https://example.invalid" % m,
                # minor 1: braces
                "mkdir -p /{tmp/zz,%s/inside}" % p.lstrip("/"),
                "mkdir -p %s/{a,b}" % m,
                # minor 2: jq's environment and files of its own choosing
                "jq -n env", "jq -n '$ENV.HOME'", "jq env %s/x.json" % m,
                "jq '$ENV.HOME' %s/x.json" % m, "jq '.a | env' %s/x.json" % m,
                "jq input_filename %s/x.json" % m, "jq '$__loc__' %s/x.json" % m,
                "jq --rawfile a /etc/passwd . %s/x.json" % m,
                "jq --slurpfile a /etc/passwd . %s/x.json" % m,
                "jq --args . a b", "jq --jsonargs . 1", "jq -f %s/p.jq %s/x.json" % (m, m),
                "jq -L /tmp . %s/x.json" % m, "jq -Rr . /etc/passwd",
                "jq . /etc/passwd", "jq . %s/answers/1.md" % s,
                "jq 'import \"x\" as x; .' %s/x.json" % m, "jq .", "jq -rn 1",
                "jq --null-input 1", "jq . %s/*.json" % m,
                # S1 and minor 3: the board's tool and views.py on the coordinator's own paths
                "%s/board.py next %s/speaker/board --versions %s/versions.json" % (t, s, m),
                "%s/board.py next %s/board --versions %s/speaker/versions.json" % (t, m, s),
                "%s/board.py claim %s/board j1 --by coordinator --versions %s/versions.json "
                "--now 2030-01-02T03:04:05Z --out %s/speaker/out" % (t, m, m, s),
                "%s/board.py claim %s/board j1 --by coordinator --versions %s/versions.json "
                "--now 2030-01-02T03:04:05Z --out %s/.principal" % (t, m, m, p),
                "%s/board.py claim %s/board j1 --by s2 --versions %s/versions.json "
                "--now 2030-01-02T03:04:05Z --out %s/out" % (t, m, m, m),
                "%s/board.py fail %s/board j1 --by coordinator --versions %s/versions.json "
                "--reason superseded --now 2030-01-02T03:04:05Z --ou %s" % (t, m, m, p),
                "%s/board.py fail %s/board j1 --by coordinator --versions %s/versions.json "
                "--reason helper --now 2030-01-02T03:04:05Z --out=%s" % (t, m, m, p),
                "%s/board.py done %s/board j1 --by coordinator --versions %s/versions.json "
                "--result %s/x.json --now 2030-01-02T03:04:05Z" % (t, m, m, s),
                "%s/board.py add %s/board --versions %s/versions.json --jobs %s/j.json "
                "--now 2030-01-02T03:04:05Z" % (t, m, m, m),
                "%s/board.py retry %s/board j1 --versions %s/versions.json --now "
                "2030-01-02T03:04:05Z" % (t, m, m),
                "%s/board.py release %s/board --versions %s/versions.json --older-than 1 "
                "--now 2030-01-02T03:04:05Z" % (t, m, m),
                "%s/board.py next %s/board --versions %s/versions.json -h" % (t, m, m),
                "%s/board.py next %s/board %s/x --versions %s/versions.json" % (t, m, p, m),
                "%s/views.py %s/t.jsonl %s/.principal" % (t, m, p),
                "%s/views.py %s/t.jsonl %s/views/j1" % (t, m, s),
                "%s/views.py %s/t.jsonl %s/views/j1 --doc %s/notebook.json" % (t, m, m, p),
                "%s/views.py %s/t.jsonl %s/views/j1 --names %s/n.tsv" % (t, m, m, s),
                "%s/views.py %s/t.jsonl %s/views/j1 --do %s/x" % (t, m, m, m),
                "%s/views.py /etc/passwd %s/views/j1 --list-only" % (t, m),
                "%s/views.py %s/.claude/projects/x/secret.txt %s/v --list-only"
                % (t, self.home, m),
                "%s/views.py %s/.claude/agents/a.jsonl %s/v --list-only" % (t, self.home, m),
                "%s/views.py %s/t.jsonl %s/.claude/agents/coordinator/v" % (t, m, self.home),
                "%s/views.py %s/t.jsonl %s/hooks/coordinator" % (t, m, ROOT),
                "mkdir -p %s/answers" % s,
                "mkdir -p %s/.claude/coordinator" % self.home,
        ):
            with self.subTest(command=command):
                why = self.denied("principal:coordinator", command)
                self.assertIn("a coordinator runs only", why)


class WhoTest(Gate):
    def test_the_kinds_with_no_shell_run_nothing(self):
        for kind in NO_SHELL:
            with self.subTest(kind=kind):
                why = self.denied("principal:" + kind, "date -u")
                self.assertIn("runs nothing in the shell", why)

    def test_the_main_thread_and_the_interviewer_keep_what_they_had(self):
        for agent in (None, "", "principal:interviewer", "interviewer", "general-purpose",
                      "fork", "other:checker"):
            with self.subTest(agent=agent):
                self.silent(agent, "claude -p hi; git push")

    def test_a_bare_name_is_a_kind_only_where_the_project_defines_it_as_ours(self):
        self.silent("checker", "git push")
        self.silent("recorder", "git push")
        os.makedirs(os.path.join(self.project, ".claude", "agents"))
        for kind in ("checker", "recorder"):
            shutil.copy(os.path.join(ROOT, "agents", kind + ".md"),
                        os.path.join(self.project, ".claude", "agents", kind + ".md"))
        self.denied("checker", "git push")
        self.denied("recorder", "git push")
        with open(os.path.join(self.project, ".claude", "agents", "checker.md"), "a") as fh:
            fh.write("\nchanged\n")
        self.silent("checker", "git push")

    def test_another_tool_is_not_the_gate_s(self):
        self.silent("principal:checker", "git push", tool="Read")

    def test_note_1_a_missing_tool_name_is_no_way_round(self):
        for raw in ({"agent_type": "principal:checker", "cwd": self.project,
                     "tool_input": {"command": "curl x"}},
                    {"agent_type": "principal:checker", "cwd": self.project,
                     "tool_name": None, "tool_input": {"command": "curl x"}},
                    {"agent_type": "principal:fetcher", "cwd": self.project,
                     "tool_input": {"command": "id"}}):
            with self.subTest(raw=raw):
                got = self.run_hook(None, "", raw=json.dumps(raw).encode())
                self.assertEqual(got["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_round_3_note_5_a_tool_name_spelled_as_the_shell_is_the_shell(self):
        for tool in ("", "bash", "Bash ", " BASH"):
            with self.subTest(tool=tool):
                self.denied("principal:checker", "curl x", tool=tool)

    def test_input_that_does_not_parse(self):
        got = self.run_hook(None, "", raw=b'{"agent_type": "principal:checker", oops')
        self.assertEqual(got["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertEqual(self.run_hook(None, "", raw=b'{"agent_type": "fork", oops'), {})
        self.assertEqual(self.run_hook(None, "", raw=b"{oops"), {})

    def test_a_manifest_that_cannot_be_read_fails_closed(self):
        """Minor 7: with no readable plugin.json, any name ending in a kind
        is that kind."""
        plugin = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, plugin, ignore_errors=True)
        shutil.copytree(os.path.join(ROOT, "hooks"), os.path.join(plugin, "hooks"),
                        ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(os.path.join(ROOT, "agents"), os.path.join(plugin, "agents"))
        gate = os.path.join(plugin, "hooks", "kind-bash-gate.py")
        for agent in ("principal:checker", "principal:fetcher", "x:checker",
                      "principal:coordinator"):
            with self.subTest(agent=agent):
                self.denied(agent, "curl x", gate=gate)
        self.silent("principal:interviewer", "curl x", gate=gate)
        os.makedirs(os.path.join(plugin, ".claude-plugin"))
        with open(os.path.join(plugin, ".claude-plugin", "plugin.json"), "w") as fh:
            fh.write("{not json")
        self.denied("principal:checker", "curl x", gate=gate)


class Round1cTest(Gate):
    """The third review of the gates, its minors on the shell gate."""

    def test_minor_1_a_kind_s_directory_is_one_under_a_scratch_root(self):
        other = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, other, ignore_errors=True)
        t, m, h, s = TOOLS, self.mine, self.home, self.scratch
        for path in ("/tmp/coordinator/x", h + "/coordinator/.zshenv", other + "/coordinator/x",
                     other + "/.git/refs/heads/coordinator/x",
                     h + "/.config/systemd/user/coordinator/x.service",
                     s + "/answers/coordinator/a", self.base + "/coordinator/x",
                     h + "/.claude/jobs/coordinator/x"):
            for command in ("mkdir -p %s" % path,
                            "%s/board.py next %s/board --versions %s/versions.json --out %s"
                            % (t, m, m, path)):
                with self.subTest(command=command):
                    self.denied("principal:coordinator", command)
        os.makedirs(s + "/check")
        os.symlink("/etc", s + "/check/toetc")
        w = s + "/check/j2"
        lst = m + "/lists/j1/doc-p1.json"
        listing = "$(ls %s/tabs | sed -n 's/\\.md$//p')" % w
        for out in ("/tmp/check/x", h + "/check/x", s + "/check/toetc/check/x",
                    s + "/answers/check/x"):
            with self.subTest(out=out):
                self.denied("principal:checker", "%s/read.py %s %s/tabs --scope %s -o %s"
                            % (t, lst, w, listing, out))
                self.denied("principal:checker", "%s/check.py %s" % (t, out))

    def test_minor_2_sha256sum_over_its_own_files_only(self):
        for path in (self.home + "/.ssh/id_ed25519", "/dev/zero", self.scratch + "/answers/1"):
            with self.subTest(path=path):
                self.denied("principal:coordinator", "sha256sum %s" % path)
        self.silent("principal:coordinator", "sha256sum %s/replies/j1 %s/r2" % (self.mine,
                                                                                 self.mine))

    def test_minor_6_a_view_or_a_tab_named_as_an_option(self):
        t, m, w = TOOLS, self.mine, self.scratch + "/check/j2"
        views = m + "/views/j1"
        os.makedirs(views)
        open(views + "/q1.json", "w").close()
        page = "%s/page.py %s/*.json -o %s/tabs" % (t, views, w)
        self.silent("principal:checker", page)
        open(views + "/-o.json", "w").close()
        self.denied("principal:checker", page)
        lst = m + "/lists/j1/doc-p1.json"
        read = "%s/read.py %s %s/tabs --scope $(ls %s/tabs | sed -n 's/\\.md$//p') -o %s/g.json" \
            % (t, lst, w, w, w)
        os.makedirs(w + "/tabs")
        open(w + "/tabs/q1.md", "w").close()
        self.silent("principal:checker", read)
        open(w + "/tabs/-o.md", "w").close()
        self.denied("principal:checker", read)

    def test_minor_7_the_stand_in_word_typed(self):
        t, m, w = TOOLS, self.mine, self.scratch + "/check/j2"
        lst = m + "/lists/j1/doc-p1.json"
        self.denied("principal:checker", "%s/read.py %s %s/tabs --scope __scope_listing__ -o "
                    "%s/g$(ls %s/tabs | sed -n 's/\\.md$//p')" % (t, lst, w, w, w))
        self.denied("principal:checker", "%s/check.py %s/__scope_listing__" % (t, w))

    def test_minor_10_its_own_directory_itself(self):
        self.silent("principal:coordinator", "mkdir -p %s" % self.mine)
        self.denied("principal:coordinator", "mkdir -p %s/check" % self.scratch)

    def test_minor_11_jq_names_where_it_stands(self):
        for program in ("get_prog_origin", "$JQ_BUILD_CONFIGURATION", '"a"|modulemeta'):
            with self.subTest(program=program):
                self.denied("principal:coordinator", "jq '%s' %s/x.json" % (program, self.mine))

    def test_minor_12_the_transcript_of_this_session_s_project(self):
        env = dict(self.env, CLAUDE_PROJECT_DIR=self.project)
        mine = re.sub(r"[^A-Za-z0-9]", "-", self.project)
        projects = self.home + "/.claude/projects/"
        command = "%s/views.py %s %s/lists/j1 --list-only"
        self.silent("principal:coordinator", command % (
            TOOLS, projects + mine + "/s1/subagents/agent-a1.jsonl", self.mine), env=env)
        for path in (projects + "-other/s1/subagents/agent-a1.jsonl",
                     projects + mine + "x/a.jsonl", projects + "a.jsonl"):
            with self.subTest(path=path):
                self.denied("principal:coordinator", command % (TOOLS, path, self.mine),
                            env=env)
        # where the session's project is not known, any project's, as before
        self.silent("principal:coordinator", command % (
            TOOLS, projects + "-other/s1/subagents/agent-a1.jsonl", self.mine))


class HooksFileTest(unittest.TestCase):
    def test_the_gate_fires_on_bash(self):
        with open(HOOKS, encoding="utf-8") as fh:
            entries = json.load(fh)["hooks"]["PreToolUse"]
        self.assertIn({"matcher": "Bash", "hooks": [{
            "type": "command",
            "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/kind-bash-gate.py\""}]},
            entries)


if __name__ == "__main__":
    unittest.main()
