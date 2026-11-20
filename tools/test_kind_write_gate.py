"""The kinds' write gate: the coordinator writes its own scratch, the
interviewer nothing the gates and the project's setup stand on, every other
kind no file, and every other turn keeps what the harness gives it. Run as a
process, as the harness runs it."""

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
GATE = os.path.join(ROOT, "hooks", "kind-write-gate.py")
HOOKS = os.path.join(ROOT, "hooks", "hooks.json")
TOOLS = os.path.join(ROOT, "tools")

NO_WRITE = ("checker", "clean-reader", "fetcher", "grader", "recorder", "reviewer",
            "comparer", "ai-recorder")
WRITERS = ("Write", "Edit", "MultiEdit", "NotebookEdit")
SESSION = "claude-1000/-home-u-proj/0b7c6f2e-1d2a-4c3b-9e8f-7a6b5c4d3e2f/scratchpad/sit"
JOBS = ".claude/jobs/0f82a3c4/tmp/sit"


class Gate(unittest.TestCase):
    def setUp(self):
        self.project = tempfile.mkdtemp()
        # a session's scratchpad stands under /tmp/claude-*/…/scratchpad
        self.base = tempfile.mkdtemp(prefix="claude-", dir=os.path.realpath("/tmp"))
        self.home = tempfile.mkdtemp()
        for d in (self.project, self.base, self.home):
            self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        self.scratch = os.path.join(self.base, SESSION)
        self.env = {k: v for k, v in os.environ.items()
                    if k not in ("CLAUDE_PROJECT_DIR", "CLAUDE_PLUGIN_ROOT")}
        self.env["HOME"] = self.home

    def run_hook(self, agent, path, tool="Write", cwd=None, raw=None, env=None):
        key = "notebook_path" if tool == "NotebookEdit" else "file_path"
        c = {"cwd": cwd or self.project, "tool_name": tool, "tool_input": {key: path}}
        if agent is not None:
            c["agent_type"] = agent
        data = raw if raw is not None else json.dumps(c).encode()
        done = subprocess.run([sys.executable, "-B", GATE], input=data, capture_output=True,
                              env=env or self.env, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stderr, b"")
        lines = done.stdout.decode().splitlines()
        self.assertEqual(len(lines), 1, lines)
        return json.loads(lines[0])

    def denied(self, agent, path, **kw):
        got = self.run_hook(agent, path, **kw)
        self.assertEqual(got.get("hookSpecificOutput", {}).get("permissionDecision"), "deny",
                         (agent, path))
        return got["hookSpecificOutput"]["permissionDecisionReason"]

    def silent(self, agent, path, **kw):
        self.assertEqual(self.run_hook(agent, path, **kw), {}, (agent, path))


class CoordinatorTest(Gate):
    def test_its_own_files(self):
        m = self.scratch + "/coordinator"
        for path in (m + "/versions.json", m + "/replies/s1-b1-1-seal",
                     m + "/results/s1-b1-1-seal.json",
                     os.path.join(self.base, SESSION, "coordinator", "versions.json"),
                     os.path.join(self.home, JOBS, "coordinator", "replies", "j1")):
            for tool in WRITERS:
                with self.subTest(path=path, tool=tool):
                    self.silent("principal:coordinator", path, tool=tool)

    def test_s1_what_the_gates_stand_on_is_refused(self):
        """The review's S1: the tool the shell gate admits by its path, the
        gates themselves, the notebook's file, and every path not its own."""
        os.makedirs(os.path.join(self.project, ".principal"))
        link = os.path.join(self.scratch, "coordinator", "link")
        os.makedirs(os.path.dirname(link))
        os.symlink(self.project, link)
        for path in (TOOLS + "/board.py", ROOT + "/hooks/kind-bash-gate.py",
                     ROOT + "/hooks/notebook-gate.py", ROOT + "/hooks/kinds.py",
                     self.project + "/.principal/notebook.json",
                     self.project + "/coordinator/x",
                     self.project + "/.claude/agents/checker.md",
                     self.scratch + "/answers/1.md", self.scratch + "/questions/1.md",
                     self.scratch + "/speaker/versions.json", self.scratch + "/coordinator",
                     self.scratch + "/coordinator/../answers/1.md",
                     link + "/.principal/notebook.json",
                     self.home + "/.claude/settings.json",
                     self.home + "/.claude/projects/coordinator/x",
                     self.home + "/.claude/coordinator/x",
                     "coordinator/x", "", "/"):
            with self.subTest(path=path):
                why = self.denied("principal:coordinator", path)
                self.assertIn("a coordinator writes only", why)

    def test_a_call_with_no_path(self):
        for raw in ({"tool_input": {}}, {"tool_input": "x"}, {"tool_input": {"file_path": 7}}):
            c = dict({"cwd": self.project, "tool_name": "Write",
                      "agent_type": "principal:coordinator"}, **raw)
            got = self.run_hook(None, "", raw=json.dumps(c).encode())
            self.assertEqual(got["hookSpecificOutput"]["permissionDecision"], "deny")


class InterviewerTest(Gate):
    def test_its_own_files(self):
        for path in (self.scratch + "/questions/1.md", self.scratch + "/answers/1.md",
                     self.scratch + "/rows/j.json",
                     os.path.join(self.home, JOBS, "sealed", "1.md"),
                     self.project + "/notes.md"):
            with self.subTest(path=path):
                self.silent("principal:interviewer", path)

    def test_what_the_gates_and_the_project_s_setup_stand_on(self):
        sub = os.path.join(self.project, "sub")
        os.makedirs(sub)
        os.makedirs(os.path.join(self.project, ".principal"))
        for path, cwd in ((self.project + "/.principal/notebook.json", None),
                          (self.project + "/.claude/agents/recorder.md", None),
                          (self.project + "/.claude/settings.json", None),
                          (self.project + "/.principal/notebook.json", sub),
                          (ROOT + "/hooks/notebook-gate.py", None),
                          (ROOT + "/agents/recorder.md", None),
                          (self.home + "/.claude/settings.json", None),
                          (self.home + "/.claude/agents/x.md", None),
                          (self.project + "/x/../.principal/notebook.json", None),
                          ("relative.md", None), ("", None)):
            with self.subTest(path=path, cwd=cwd):
                why = self.denied("principal:interviewer", path, cwd=cwd)
                self.assertIn("the interviewer writes no file", why)

    def test_the_project_dir_from_the_environment(self):
        elsewhere = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, elsewhere, ignore_errors=True)
        path = self.project + "/.principal/notebook.json"
        env = dict(self.env, CLAUDE_PROJECT_DIR=self.project)
        self.denied("principal:interviewer", path, cwd=elsewhere, env=env)


class WhoTest(Gate):
    def test_the_kinds_that_write_no_file(self):
        for kind in NO_WRITE:
            for tool in WRITERS:
                with self.subTest(kind=kind, tool=tool):
                    why = self.denied("principal:" + kind, self.scratch + "/x", tool=tool)
                    self.assertIn("this kind writes no file", why)

    def test_every_other_turn_keeps_what_it_had(self):
        for agent in (None, "", "general-purpose", "fork", "other:coordinator", "reviewer",
                      "coordinator", "interviewer"):
            with self.subTest(agent=agent):
                self.silent(agent, ROOT + "/hooks/kind-bash-gate.py")

    def test_another_tool_is_not_the_gate_s(self):
        self.silent("principal:checker", self.scratch + "/x", tool="Read")

    def test_a_bare_kind_where_the_project_defines_it_as_ours(self):
        os.makedirs(os.path.join(self.project, ".claude", "agents"))
        shutil.copy(os.path.join(ROOT, "agents", "coordinator.md"),
                    os.path.join(self.project, ".claude", "agents", "coordinator.md"))
        self.denied("coordinator", ROOT + "/hooks/kind-bash-gate.py")
        self.silent("coordinator", self.scratch + "/coordinator/x")

    def test_input_that_does_not_parse(self):
        got = self.run_hook(None, "", raw=b'{"agent_type": "principal:coordinator", oops')
        self.assertEqual(got["hookSpecificOutput"]["permissionDecision"], "deny")
        got = self.run_hook(None, "", raw=b'{"agent_type": "reviewer", oops')
        self.assertEqual(got["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertEqual(self.run_hook(None, "", raw=b'{"agent_type": "fork", oops'), {})
        deep = b'{"agent_type": "principal:checker", "x": ' + b"[" * 200000 + b"]" * 200000 + b"}"
        self.assertEqual(self.run_hook(None, "", raw=deep)["hookSpecificOutput"]
                         ["permissionDecision"], "deny")


class Round1cTest(Gate):
    """The third review of the gates, on the write gate."""

    def test_minor_1_a_kind_s_directory_is_one_under_a_scratch_root(self):
        other = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, other, ignore_errors=True)
        h, s = self.home, self.scratch
        for path in ("/tmp/coordinator/x", h + "/coordinator/.zshenv", other + "/coordinator/x",
                     other + "/.git/refs/heads/coordinator/x",
                     h + "/.config/systemd/user/coordinator/x.service",
                     s + "/answers/coordinator/a", self.base + "/coordinator/x"):
            with self.subTest(path=path):
                self.denied("principal:coordinator", path)

    def test_minor_3_the_interviewer_with_no_project_found(self):
        path = self.project + "/.principal/notebook.json"
        os.makedirs(os.path.dirname(path))
        raw = json.dumps({"agent_type": "principal:interviewer", "tool_name": "Write",
                          "tool_input": {"file_path": path}}).encode()
        got = self.run_hook(None, "", raw=raw)
        self.assertEqual(got["hookSpecificOutput"]["permissionDecision"], "deny")
        # a cwd outside the project: no `.principal` or `.claude` directory anywhere
        for path in (self.project + "/.principal/notebook.json",
                     self.project + "/.claude/agents/recorder.md"):
            with self.subTest(path=path):
                self.denied("principal:interviewer", path, cwd="/tmp")
        self.silent("principal:interviewer", self.scratch + "/questions/1.md", cwd="/tmp")

    def test_minor_8_case_is_folded_for_what_is_refused(self):
        os.makedirs(os.path.join(self.project, ".principal"))
        head, tail = os.path.split(self.project)
        swapped = os.path.join(head, tail.swapcase())
        for path in (self.home + "/.CLAUDE/agents/x.md",
                     swapped + "/.Principal/notebook.json",
                     ROOT.upper() + "/hooks/kinds.py"):
            with self.subTest(path=path):
                self.denied("principal:interviewer", path)

    def test_the_interviewer_s_reach_is_said_as_it_is(self):
        with open(GATE, encoding="utf-8") as fh:
            text = fh.read()
        self.assertNotIn("out of its reach", text)
        self.assertIn("shell is not confined", " ".join(text.split()))
        with open(HOOKS, encoding="utf-8") as fh:
            said = json.load(fh)["description"]
        self.assertIn("shell is not confined", said)


class HooksFileTest(unittest.TestCase):
    def test_the_gate_fires_on_every_tool_that_writes_a_file(self):
        with open(HOOKS, encoding="utf-8") as fh:
            entries = json.load(fh)["hooks"]["PreToolUse"]
        found = [e for e in entries if e["hooks"] == [{
            "type": "command",
            "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/kind-write-gate.py\""}]]
        self.assertEqual(len(found), 1)
        matcher = re.compile("^(?:%s)$" % found[0]["matcher"])
        for tool in WRITERS:
            self.assertTrue(matcher.match(tool), tool)
        for tool in ("Read", "Bash", "WriteX"):
            self.assertIsNone(matcher.match(tool), tool)


if __name__ == "__main__":
    unittest.main()
