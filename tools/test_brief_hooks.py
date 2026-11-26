"""The brief's hooks, run as processes as the harness runs them: the
session's brief at start and after a compaction, a helper's own brief at its
launch by the allow-list, the work in hand into a compaction, and the
convention check on every text as it leaves."""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from support import fixture

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
HOOKS = os.path.join(ROOT, "hooks")
GRAPH = fixture("brief")
T = "2030-01-02T03:04:05Z"
#: the harness keeps at most this much of one hook's output in context
CAP = 10000


def load_hook(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"),
                                                  os.path.join(HOOKS, name))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.project = os.path.join(self.tmp, "project")
        os.makedirs(os.path.join(self.project, ".principal"))
        with open(os.path.join(self.project, ".principal", "notebook.json"), "w") as fh:
            json.dump({"artifact": "x", "conventions": "wording"}, fh)
        self.env = {k: v for k, v in os.environ.items()
                    if k not in ("CLAUDE_PROJECT_DIR", "CLAUDE_PLUGIN_ROOT",
                                 "CLAUDE_CONFIG_DIR")}
        self.env["HOME"] = os.path.join(self.tmp, "home")
        self.graph = os.path.join(self.tmp, "scratch", "graph.json")
        os.makedirs(os.path.dirname(self.graph))
        shutil.copyfile(GRAPH, self.graph)

    def tool(self, name, *args, code=0):
        done = subprocess.run([sys.executable, "-B", os.path.join(HERE, name)] + list(args),
                              cwd=self.project, capture_output=True, text=True, env=self.env,
                              timeout=60)
        self.assertEqual(done.returncode, code, done.stderr)
        return done.stdout

    def install(self, line="rotation"):
        return self.tool("brief.py", "install", self.graph, "--line", line, "--at", T) \
            .strip().splitlines()[-1]

    def hook(self, name, call, *args, cwd=None):
        call = dict(call)
        call.setdefault("cwd", cwd or self.project)
        done = subprocess.run([sys.executable, "-B", os.path.join(HOOKS, name)] + list(args),
                              input=json.dumps(call).encode(), capture_output=True,
                              env=self.env, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        return done.stdout.decode()

    def decision(self, name, call, cwd=None):
        return json.loads(self.hook(name, call, cwd=cwd))


class SessionTest(Base):
    START = {"hook_event_name": "SessionStart", "source": "startup"}

    def parts(self, source="startup"):
        call = dict(self.START, source=source)
        return [self.hook("brief-session.py", call, str(n)) for n in range(1, 5)]

    def test_no_notebook_nothing(self):
        other = os.path.join(self.tmp, "elsewhere")
        os.makedirs(other)
        self.assertEqual(self.hook("brief-session.py", self.START, "1", cwd=other), "")
        self.assertEqual(self.hook("brief-session.py", self.START, "inhand", cwd=other), "")

    def test_no_brief_one_line(self):
        first = self.parts()[0]
        self.assertIn("No brief is installed for this project", first)
        self.assertEqual(len(first.strip().splitlines()), 2)

    def test_the_brief_and_the_neighbourhood_at_each_source(self):
        self.install()
        for source in ("startup", "resume", "compact"):
            parts = self.parts(source)
            whole = "".join(parts)
            for p in parts:
                self.assertLessEqual(len(p), CAP)
            self.assertIn("The brief matches the graph it was made from", parts[0])
            self.assertIn("# Brief: standing (side all)", whole)
            self.assertIn("# Brief: neighbourhood of the line (side all)", whole)
            self.assertIn("[planting/a1.t1.1] raises rotation", whole)
            self.assertEqual(parts[1:], ["", "", ""])

    def test_a_moved_graph_is_said_stale(self):
        self.install()
        with open(self.graph, "a") as fh:
            fh.write("\n")
        self.assertIn("The brief is stale", self.parts()[0])

    def test_a_graph_gone_cannot_be_told_fresh(self):
        self.install()
        os.unlink(self.graph)
        self.assertIn("cannot be told", self.parts()[0])

    def test_a_blind_or_wordless_session_is_given_nothing(self):
        self.install()
        for agent in ("principal:grader", "principal:fetcher"):
            self.assertEqual(self.hook("brief-session.py", dict(self.START, agent_type=agent),
                                       "1"), "")
        self.assertIn("Brief", self.hook("brief-session.py",
                                         dict(self.START, agent_type="principal:interviewer"),
                                         "1"))

    def test_parts_cut_at_line_ends_under_the_cap(self):
        session = load_hook("brief-session.py")
        words = "".join("line %d %s\n" % (n, "x" * 90) for n in range(400))
        parts = session.split(words, session.PART - 120)
        self.assertEqual("".join(parts), words)
        self.assertTrue(all(len(p) <= session.PART - 120 for p in parts))
        self.assertTrue(all(p.endswith("\n") for p in parts))
        self.assertGreaterEqual(session.PARTS * (session.PART - 120), 32000 + 1000)

    def test_the_work_in_hand_after_a_compaction_is_this_session_s(self):
        call = dict(self.START, source="compact", session_id="sess-a")
        said = self.hook("brief-session.py", call, "inhand")
        self.assertIn("Work in hand of session sess-a", said)
        self.assertIn("kept no list of its own", said)
        speaker = os.path.join(self.tmp, "scratch", "speaker")
        self.tool("inhand.py", "add", speaker, "the reviewer of the page", "--at", T,
                  "--session", "sess-a")
        self.tool("inhand.py", "add", speaker, "the evening bell", "--at", T, "--schedule",
                  "--session", "sess-a")
        said = self.hook("brief-session.py", call, "inhand")
        self.assertIn("- w1 (since %s, " % T, said)
        self.assertIn("the reviewer of the page", said)
        self.assertIn("- s2 (since %s, " % T, said)
        other = self.hook("brief-session.py", dict(call, session_id="sess-b"), "inhand")
        self.assertNotIn("the reviewer of the page", other)
        self.assertIn("Work in hand of session sess-b", other)
        self.assertIn("No session's id", self.hook("brief-session.py", dict(self.START),
                                                   "inhand"))


class PreCompactTest(Base):
    def test_the_list_and_its_path_go_into_the_compaction(self):
        call = {"hook_event_name": "PreCompact", "trigger": "auto", "custom_instructions": None,
                "session_id": "sess-a"}
        self.assertIn("kept no list of its own", self.hook("inhand-precompact.py", call))
        speaker = os.path.join(self.tmp, "scratch", "speaker")
        self.tool("inhand.py", "add", speaker, "a fetch of the tabs", "--at", T,
                  "--session", "sess-a")
        said = self.hook("inhand-precompact.py", call)
        self.assertIn(os.path.realpath(os.path.join(speaker, "inhand.json")), said)
        self.assertIn("a fetch of the tabs", said)
        self.assertIn("not an instruction", said)
        self.assertLessEqual(len(said), CAP)

    def test_no_notebook_nothing(self):
        other = os.path.join(self.tmp, "elsewhere")
        os.makedirs(other)
        self.assertEqual(self.hook("inhand-precompact.py", {"trigger": "manual"}, cwd=other), "")

    def test_a_helper_s_compaction_is_given_nothing(self):
        """RB1: inside a helper, or where the input cannot tell, nothing."""
        speaker = os.path.join(self.tmp, "scratch", "speaker")
        self.tool("inhand.py", "add", speaker, "awaiting the reply on the sheet", "--at", T,
                  "--session", "sess-a")
        base = {"hook_event_name": "PreCompact", "trigger": "auto", "session_id": "sess-a"}
        for more in ({"agent_type": "principal:grader", "agent_id": "g1"},
                     {"agent_id": "x1"}, {"agent_type": "principal:comparer", "agent_id": "c1"},
                     {"agent_type": "principal:fetcher"}):
            self.assertEqual(self.hook("inhand-precompact.py", dict(base, **more)), "", more)
            self.assertEqual(self.hook("brief-session.py", dict(base, **more), "inhand"), "",
                             more)
        done = subprocess.run([sys.executable, "-B", os.path.join(HOOKS, "inhand-precompact.py")],
                              input=b"not json", capture_output=True, env=self.env, timeout=60,
                              cwd=self.project)
        self.assertEqual(done.stdout, b"")
        self.assertIn("awaiting the reply", self.hook("inhand-precompact.py", base))


class SubagentTest(Base):
    def start(self, agent, n=1):
        call = {"hook_event_name": "SubagentStart", "agent_id": "a1", "session_id": "sess-a"}
        if agent is not None:
            call["agent_type"] = agent
        return self.decision("brief-subagent.py", call) if n == 1 else \
            json.loads(self.hook("brief-subagent.py", call, str(n)))

    def test_the_allow_list_by_kind_defaults_to_nobody(self):
        self.install()
        expect = {"principal:comparer": "all", "principal:grader": "ai",
                  "principal:reviewer": "ai", "principal:canon-answer": "ai",
                  "PRINCIPAL:Grader": "ai", "grader": "ai", "Comparer": "all",
                  "general-purpose": None, "Explore": None, "Plan": None, "fork": None,
                  "claude-code-guide": None, "other-plugin:grader": None, "": None,
                  None: None, "principal:clean-reader": None, "principal:fetcher": None,
                  "principal:checker": None, "principal:coordinator": None,
                  "principal:recorder": None, "principal:ai-recorder": None,
                  "principal:a-kind-nobody-listed": None}
        for helper, side in expect.items():
            with self.subTest(helper=helper):
                got = self.start(helper)
                if side is None:
                    self.assertEqual(got, {})
                    continue
                out = got["hookSpecificOutput"]
                self.assertEqual(out["hookEventName"], "SubagentStart")
                self.assertNotIn("updatedInput", out)
                self.assertNotIn("permissionDecision", out)
                words = out["additionalContext"]
                self.assertLessEqual(len(words), CAP)
                self.assertIn("# Brief: standing (side %s)" % side, words)
                if side == "ai":
                    self.assertNotIn("one sheet", words)
                    self.assertNotIn("named the user", words)
                    self.assertIn("[planting/a1.h]", words)
                else:
                    self.assertIn("[rotation/a1.s1]", words)

    def test_a_part_past_the_last_gives_nothing(self):
        self.install()
        self.assertEqual(self.start("principal:comparer", 2), {})

    def test_fail_open(self):
        self.assertEqual(self.start("principal:comparer"), {})
        other = os.path.join(self.tmp, "elsewhere")
        os.makedirs(other)
        call = {"hook_event_name": "SubagentStart", "agent_type": "principal:comparer"}
        self.assertEqual(self.decision("brief-subagent.py", call, cwd=other), {})

    def test_no_launch_is_rewritten_or_approved(self):
        with open(os.path.join(HOOKS, "hooks.json"), encoding="utf-8") as fh:
            text = fh.read()
        self.assertNotIn("brief-agent.py", text)
        self.assertFalse(os.path.exists(os.path.join(HOOKS, "brief-agent.py")))
        for name in os.listdir(HOOKS):
            if name.endswith(".py") and name.startswith(("brief", "inhand")):
                with open(os.path.join(HOOKS, name), encoding="utf-8") as fh:
                    code = fh.read()
                self.assertNotIn('"updatedInput"', code, name)
                self.assertNotIn('"allow"', code, name)


class LaunchLogTest(Base):
    """B5: the helpers a session starts, recorded by the hooks alone."""

    def log(self, event, session="sess-a", **more):
        call = {"hook_event_name": event, "session_id": session}
        call.update(more)
        self.assertEqual(self.decision("inhand-log.py", call), {})

    def test_launch_start_stop_by_session(self):
        self.log("PreToolUse", tool_name="Agent",
                 tool_input={"subagent_type": "principal:grader", "description": "grade 2",
                             "prompt": "x"})
        self.log("PreToolUse", tool_name="Agent", tool_input={"description": "build the page",
                                                              "prompt": "y"})
        self.log("SubagentStart", agent_type="principal:grader", agent_id="g1")
        said = self.hook("inhand-precompact.py", {"hook_event_name": "PreCompact",
                                                  "session_id": "sess-a"})
        self.assertIn("principal:grader (launched", said)
        self.assertIn("; started) grade 2", said)
        self.assertIn("general-purpose (launched", said)
        self.assertIn("; not yet started) build the page", said)
        self.log("SubagentStop", agent_type="principal:grader", agent_id="g1")
        said = self.hook("inhand-precompact.py", {"hook_event_name": "PreCompact",
                                                  "session_id": "sess-a"})
        self.assertNotIn("grade 2", said)
        self.assertIn("build the page", said)
        other = self.hook("inhand-precompact.py", {"hook_event_name": "PreCompact",
                                                   "session_id": "sess-b"})
        self.assertNotIn("build the page", other)

    def test_a_resume_updates_its_own_row(self):
        """RB3: a start for an id already recorded takes no other row."""
        launch = lambda d: self.log("PreToolUse", tool_name="Agent",
                                    tool_input={"subagent_type": "principal:grader",
                                                "description": d, "prompt": "x"})
        launch("grade first")
        self.log("SubagentStart", agent_type="principal:grader", agent_id="g1")
        self.log("SubagentStop", agent_type="principal:grader", agent_id="g1")
        launch("grade second")
        self.log("SubagentStart", agent_type="principal:grader", agent_id="g1")
        for _ in range(4):
            self.log("SubagentStart", agent_type="principal:grader", agent_id="g1")
        self.log("SubagentStart", agent_type="principal:grader", agent_id="g2")
        where = os.path.join(self.env["HOME"], ".claude", "principal", "brief")
        [key] = os.listdir(where)
        with open(os.path.join(where, key, "sessions", "sess-a", "launches.json")) as fh:
            rows = json.load(fh)
        self.assertEqual([(r["description"], r.get("agent_id")) for r in rows],
                         [("grade first", "g1"), ("grade second", "g2")])
        self.log("SubagentStop", agent_type="principal:grader", agent_id="g1")
        said = self.hook("inhand-precompact.py", {"hook_event_name": "PreCompact",
                                                  "session_id": "sess-a"})
        self.assertIn("grade second", said)
        self.assertNotIn("grade first", said)

    def test_the_record_is_bounded(self):
        from hypo import inhand
        rows = [{"id": "h%d" % n, "ended": "t" if n % 2 else None} for n in range(500)]
        kept = inhand.trim(rows)
        self.assertLessEqual(len(kept), inhand.KEPT)
        self.assertLessEqual(sum(1 for r in kept if r.get("ended")), inhand.ENDED)
        self.assertEqual(kept[-1]["id"], "h499")

    def test_nothing_outside_a_project_or_without_a_session(self):
        other = os.path.join(self.tmp, "elsewhere")
        os.makedirs(other)
        call = {"hook_event_name": "PreToolUse", "session_id": "s", "tool_name": "Agent",
                "tool_input": {"prompt": "x"}}
        self.assertEqual(self.decision("inhand-log.py", call, cwd=other), {})
        self.log("PreToolUse", session="../escape", tool_name="Agent",
                 tool_input={"prompt": "x"})
        self.assertFalse(os.path.exists(os.path.join(self.env["HOME"], ".claude", "principal",
                                                     "escape")))


class ConventionGateTest(Base):
    def bash(self, command, agent=None):
        call = {"tool_name": "Bash", "tool_input": {"command": command}}
        if agent:
            call["agent_type"] = agent
        return self.decision("convention-gate.py", call)

    def denied(self, got):
        out = got.get("hookSpecificOutput", {})
        return out.get("permissionDecision") == "deny" and out["permissionDecisionReason"]

    def test_a_commit_message_calling_the_user_the_human(self):
        self.install()
        reason = self.denied(self.bash("git commit -m 'Let the human choose the beds'"))
        self.assertIn("[check:user-named]", reason)
        self.assertIn("[wording/a1.s1] The one the record is kept for is named the user.", reason)
        self.assertEqual(self.bash("git commit -m 'Let the user choose the beds'"), {})
        self.assertEqual(self.bash("ls the human"), {})
        for read in ('gh search issues "the human condition"', 'gh pr view 3 --comments',
                     'gh api repos/x/y/issues -q ".[] | select(.title==\'the human\')"',
                     'git log --grep "the human"'):
            self.assertEqual(self.bash(read), {}, read)
        self.assertTrue(self.denied(self.bash("git tag -a v1 -m 'for the human'")))
        self.assertTrue(self.denied(self.bash("git notes add -m 'for the human'")))
        # N3 of the loading review: a merge's own message leaves as a commit's does
        self.assertTrue(self.denied(self.bash("git merge -m 'for the human' beds")))
        self.assertTrue(self.denied(self.bash("git merge --no-ff --message='for the human' beds")))
        self.assertTrue(self.denied(self.bash("git merge '-mfor the human' beds")))
        self.assertEqual(self.bash("git merge the-human-branch"), {})
        # N3 of the small-debts review: bundled flags, and a message file attached or bundled
        self.assertTrue(self.denied(self.bash("git merge --no-ff -nm 'for the human' beds")))
        msg = os.path.join(self.tmp, "msg.txt")
        with open(msg, "w") as fh:
            fh.write("Let the human choose the beds\n")
        for cmd in ("git merge -F %s beds", "git merge -F%s beds", "git merge -nF %s beds",
                    "git commit -F%s"):
            self.assertTrue(self.denied(self.bash(cmd % msg)), cmd)
        # a message file that cannot be read fails open
        self.assertEqual(self.bash("git merge -F%s beds" % os.path.join(self.tmp, "none.txt")), {})
        self.assertEqual(self.bash("git merge -s ours -Xpatience beds"), {})
        self.assertTrue(self.denied(self.bash("cd x && git -C y commit -m 'the human'")))
        self.assertTrue(self.denied(self.bash("gh issue comment 3 -b 'the human'")))
        self.assertTrue(self.denied(self.bash(
            "git commit -F - <<'EOF'\nLet the human choose\nEOF")))

    def test_the_review_s_reads_pass(self):
        """RB2: every read the re-review saw refused now passes."""
        self.install()
        for read in ("gh api graphql -f query='{ search(query: \"the human\") { issueCount } }'",
                     "gh api repos/x/y/issues -f title='the human'",
                     "git merge-base main the-human-branch && echo the human",
                     "git tag -l 'the human*'",
                     "git cat-file commit HEAD | grep -i 'the human'",
                     "git log --grep 'the human' -- tools/commit.py",
                     "echo git commit -m 'the human'"):
            self.assertEqual(self.bash(read), {}, read)

    def test_masked_words_into_a_pull_request(self):
        self.install()
        body = os.path.join(self.tmp, "body.md")
        with open(body, "w") as fh:
            fh.write("Built so that the garden is kept to feed the house.")
        reason = self.denied(self.bash("gh pr create --title Beds --body-file %s" % body))
        self.assertEqual(self.bash("gh pr view --json body"), {})
        self.assertIn("[check:masked]", reason)
        blind = self.denied(self.bash("gh pr create --title Beds --body-file %s" % body,
                                      agent="principal:checker"))
        self.assertIn("[check:masked]", blind)
        self.assertNotIn("feed the house", blind)

    def test_the_store(self):
        self.install()
        got = self.decision("convention-gate.py", {
            "tool_name": "ArtifactData",
            "tool_input": {"action": "set", "collection": "ordo", "doc_id": "current",
                           "data": {"context": {"paragraphs": ["The human is out today."]}}}})
        self.assertTrue(self.denied(got))
        rows = os.path.join(self.tmp, "scratch", "speaker", "out")
        os.makedirs(rows)
        with open(os.path.join(rows, "w.json"), "w") as fh:
            json.dump({"why": "Here \"fallow\" means unweeded."}, fh)
        got = self.decision("convention-gate.py", {
            "tool_name": "ArtifactData",
            "tool_input": {"action": "batch", "writes": [
                {"op": "set", "collection": "lines", "doc_id": "l1",
                 "file_path": os.path.join(rows, "w.json")}]}})
        self.assertIn("[check:definition-in-glossary]", self.denied(got))
        self.assertEqual(self.decision("convention-gate.py", {
            "tool_name": "ArtifactData",
            "tool_input": {"action": "get", "collection": "ordo", "doc_id": "current"}}), {})

    def test_a_write_to_a_tab_out_of_reach(self):
        self.install()
        call = {"tool_name": "mcp__claude_ai_Claude_Docs__update",
                "tool_input": {"container": {"kind": "project", "id": "x"},
                               "ref": {"object": "node", "id": "g-03"},
                               "payload": {"ops": [{"op": "insert", "markdown":
                                                    "A fallow bed is left to rest."}]}}}
        reason = self.denied(self.decision("convention-gate.py", call))
        self.assertIn("[check:reach]", reason)
        self.assertIn("[rotation/≡fallow.s1]", reason)
        call["tool_input"]["ref"]["id"] = "g-04"
        self.assertEqual(self.decision("convention-gate.py", call), {})

    def test_fail_open_without_a_graph_and_outside_a_project(self):
        got = self.bash("git commit -m 'Let the human choose'")
        self.assertNotIn("permissionDecision", got["hookSpecificOutput"])
        self.assertIn("went unchecked", got["hookSpecificOutput"]["additionalContext"])
        other = os.path.join(self.tmp, "elsewhere")
        os.makedirs(other)
        call = {"tool_name": "Bash", "tool_input": {"command": "git commit -m 'the human'"}}
        self.assertEqual(self.decision("convention-gate.py", call, cwd=other), {})


class WiringTest(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(HOOKS, "hooks.json"), encoding="utf-8") as fh:
            self.hooks = json.load(fh)["hooks"]
        with open(os.path.join(HOOKS, "brief-sides.json"), encoding="utf-8") as fh:
            self.sides = json.load(fh)

    def commands(self, event):
        return [h["command"] for e in self.hooks[event] for h in e["hooks"]]

    def test_session_start_runs_every_part_and_the_work_in_hand(self):
        [entry] = self.hooks["SessionStart"]
        self.assertEqual(sorted(entry["matcher"].split("|")),
                         ["clear", "compact", "resume", "startup"])
        session = load_hook("brief-session.py")
        want = ["python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/brief-session.py\" %s" % n
                for n in list(range(1, session.PARTS + 1)) + ["inhand"]]
        self.assertEqual(self.commands("SessionStart"), want)

    def test_pre_compact(self):
        [entry] = self.hooks["PreCompact"]
        self.assertEqual(sorted(entry["matcher"].split("|")), ["auto", "manual"])
        self.assertEqual(self.commands("PreCompact"),
                         ["python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/inhand-precompact.py\""])

    def test_the_launch_log_the_helper_s_brief_and_the_convention_gate(self):
        by = {}
        for e in self.hooks["PreToolUse"]:
            for h in e["hooks"]:
                by[h["command"].rsplit("/", 1)[-1].rstrip('"')] = e["matcher"]
        self.assertEqual(by["inhand-log.py"], "Agent|Task")
        gate = load_hook("convention-gate.py")
        self.assertEqual(sorted(by["convention-gate.py"].split("|")),
                         sorted(gate.CONNECTOR + (gate.STORE, gate.SHELL)))
        [start] = self.hooks["SubagentStart"]
        self.assertNotIn("matcher", start)
        self.assertEqual(self.commands("SubagentStart"),
                         ["python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/brief-subagent.py\" %d" % n
                          for n in range(1, 5)]
                         + ["python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/inhand-log.py\""])
        self.assertEqual(self.commands("SubagentStop"),
                         ["python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/inhand-log.py\""])

    def test_the_allow_list_names_every_kind_and_gives_nobody_else_anything(self):
        kinds = {n[:-3] for n in os.listdir(os.path.join(ROOT, "agents")) if n.endswith(".md")}
        self.assertTrue(kinds <= set(self.sides["kinds"]))
        for wordless in ("fetcher", "checker", "coordinator", "recorder", "ai-recorder"):
            self.assertIsNone(self.sides["kinds"][wordless])
        for blind in ("grader", "reviewer", "canon-answer"):
            self.assertEqual(self.sides["kinds"][blind], "ai")
        self.assertIsNone(self.sides["kinds"]["clean-reader"])
        # the question reader holds the notebook already, and needs no brief of it
        self.assertIsNone(self.sides["kinds"]["question-reader"])
        self.assertIsNone(self.sides["no_kind"])
        briefing = load_hook("briefing.py")
        table = briefing.sides()
        # a kind the plugin defines and the list does not name gets nothing
        self.assertIsNone(briefing.side_for("principal:grader", None, {},
                                            {"no_kind": "all", "kinds": {}},
                                            os.path.join(ROOT, "agents")))
        self.assertEqual(briefing.side_for("general-purpose", None, {},
                                           {"no_kind": None, "kinds": {}}), None)
        self.assertEqual(table["kinds"]["grader"], "ai")

    def test_the_clean_reader_is_one_line_of_configuration(self):
        with open(os.path.join(HOOKS, "brief-sides.json"), encoding="utf-8") as fh:
            lines = [l for l in fh if '"clean-reader"' in l]
        self.assertEqual(len(lines), 1)


if __name__ == "__main__":
    unittest.main()
