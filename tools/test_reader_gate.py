"""The clean reader's read gate: a file in the sitting's questions directory,
outside the checkout, and nothing else; every other turn keeps what the
harness gives it. Run as a process, as the harness runs it."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
GATE = os.path.join(ROOT, "hooks", "reader-gate.py")
HOOKS = os.path.join(ROOT, "hooks", "hooks.json")


class ReaderGateTest(unittest.TestCase):
    def setUp(self):
        self.checkout = tempfile.mkdtemp()
        # a session's scratchpad stands under /tmp/claude-*/…/scratchpad
        self.base = tempfile.mkdtemp(prefix="claude-", dir=os.path.realpath("/tmp"))
        self.scratch = os.path.join(self.base, "-home-u-proj", "s", "scratchpad", "sit")
        self.addCleanup(shutil.rmtree, self.checkout, ignore_errors=True)
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)
        for sub in ("questions", "answers", "replies", "results", "sealed", "rows",
                    "replies/questions"):
            os.makedirs(os.path.join(self.scratch, sub), exist_ok=True)
        self.home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.home, ignore_errors=True)
        self.env = {k: v for k, v in os.environ.items()
                    if k not in ("CLAUDE_PROJECT_DIR", "CLAUDE_PLUGIN_ROOT")}
        self.env["HOME"] = self.home

    def define(self):
        os.makedirs(os.path.join(self.checkout, ".claude", "agents"), exist_ok=True)
        shutil.copy(os.path.join(ROOT, "agents", "clean-reader.md"),
                    os.path.join(self.checkout, ".claude", "agents", "clean-reader.md"))

    def run_hook(self, agent, path, tool="Read", raw=None, cwd=None, env=None, gate=GATE):
        c = {"cwd": cwd or self.checkout, "tool_name": tool, "tool_input": {"file_path": path}}
        if agent is not None:
            c["agent_type"] = agent
        done = subprocess.run([sys.executable, "-B", gate],
                              input=raw if raw is not None else json.dumps(c).encode(),
                              capture_output=True, timeout=60, env=env or self.env)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stderr, b"")
        return json.loads(done.stdout)

    def decision(self, agent, path, **kw):
        return self.run_hook(agent, path, **kw)["hookSpecificOutput"]["permissionDecision"]

    def test_the_question_it_was_handed(self):
        self.define()
        for agent in ("principal:clean-reader", "clean-reader"):
            self.assertEqual(self.decision(agent, self.scratch + "/questions/3.md"), "allow")

    def test_both_shapes_of_a_session_s_scratch(self):
        """Minor 12: a session's scratchpad under /tmp, and a job's
        ~/.claude/jobs/<id>/tmp; any other place under ~/.claude is refused."""
        for path in (self.scratch + "/claude-1000/-home-u-proj/0b7c6f2e-1d2a-4c3b-9e8f-"
                     "7a6b5c4d3e2f/scratchpad/sit/questions/1.md",
                     self.home + "/.claude/jobs/0f82a3c4/tmp/sit/questions/1.md"):
            self.assertEqual(self.decision("principal:clean-reader", path), "allow", path)
        for path in (self.home + "/.claude/projects/x/questions/1.md",
                     self.home + "/.claude/jobs/0f82a3c4/questions/1.md",
                     ROOT + "/questions/1.md"):
            self.assertEqual(self.decision("principal:clean-reader", path), "deny", path)

    def test_minor_5_a_cwd_inside_the_project(self):
        """The project is found from a cwd below it, by its mark or by
        CLAUDE_PROJECT_DIR, and a question inside it is refused."""
        os.makedirs(os.path.join(self.checkout, ".principal"))
        sub = os.path.join(self.checkout, "sub")
        os.makedirs(os.path.join(self.checkout, "questions"))
        os.makedirs(sub)
        inside = self.checkout + "/questions/1.md"
        self.assertEqual(self.decision("principal:clean-reader", inside, cwd=sub), "deny")
        bare = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, bare, ignore_errors=True)
        os.makedirs(os.path.join(bare, "questions"))
        os.makedirs(os.path.join(bare, "sub"))
        env = dict(self.env, CLAUDE_PROJECT_DIR=bare)
        self.assertEqual(self.decision("principal:clean-reader", bare + "/questions/1.md",
                                       cwd=os.path.join(bare, "sub"), env=env), "deny")
        # outside the project, but under no scratch root: no opinion (round 1c's minor 5)
        self.assertEqual(self.run_hook("principal:clean-reader", bare + "/questions/1.md",
                                       cwd=os.path.join(bare, "sub")), {})

    def test_minor_6_a_bare_name_the_project_does_not_define_as_ours(self):
        for agent in ("clean-reader", "other:clean-reader"):
            self.assertEqual(self.run_hook(agent, self.scratch + "/answers/3.md"), {}, agent)
        self.define()
        self.assertEqual(self.decision("clean-reader", self.scratch + "/answers/3.md"), "deny")

    def test_everything_else_the_sitting_keeps_is_refused(self):
        s = self.scratch
        for path in (s + "/answers/3.md", s + "/replies/s1-b1-r1-seal",
                     s + "/results/s1-b1-r1-seal.json", s + "/sealed/3.md",
                     s + "/rows/s1-b1-r1-record.json", s + "/replies/questions/3.md",
                     # the record of predictions the speaker reads and the reader never
                     s + "/speaker/stamp.txt", s + "/predictions/r1.txt",
                     s + "/graph.json", s + "/lines/l1/1/place.json",
                     s + "/questions/../answers/3.md", s + "/questions",
                     s + "/q/questions.md", os.path.expanduser("~/.claude/projects/x.jsonl"),
                     "/etc/passwd", "questions/3.md", ""):
            with self.subTest(path=path):
                self.assertEqual(self.decision("principal:clean-reader", path), "deny")

    def test_a_questions_directory_inside_the_checkout_admits_nothing(self):
        os.makedirs(os.path.join(self.checkout, "questions"))
        self.assertEqual(self.decision("principal:clean-reader",
                                       self.checkout + "/questions/3.md"), "deny")

    def test_a_link_into_a_forbidden_directory_is_refused(self):
        os.symlink(os.path.join(self.scratch, "answers", "3.md"),
                   os.path.join(self.scratch, "questions", "4.md"))
        self.assertEqual(self.decision("principal:clean-reader",
                                       self.scratch + "/questions/4.md"), "deny")

    def test_another_tool_is_refused_to_the_reader(self):
        self.assertEqual(self.decision("principal:clean-reader",
                                       self.scratch + "/questions/3.md", tool="Grep"), "deny")

    def test_every_other_turn_gets_no_opinion(self):
        for agent in (None, "", "principal:grader", "principal:interviewer", "fork",
                      "principal:comparer"):
            with self.subTest(agent=agent):
                self.assertEqual(self.run_hook(agent, self.scratch + "/answers/3.md"), {})

    def test_input_that_does_not_parse_is_no_opinion(self):
        self.assertEqual(self.run_hook(None, "", raw=b"{oops"), {})
        self.assertEqual(self.run_hook(None, "", raw=b'{"agent_type": "fork", oops'), {})

    def test_minor_4_input_that_does_not_parse_is_refused_to_the_reader(self):
        for raw in (b'{"agent_type": "principal:clean-reader", oops',
                    b'{"agent_type": "clean-reader", "x": "\xff"',
                    b'{"agent_type": "principal:clean-reader", "x": '
                    + b"[" * 200000 + b"]" * 200000 + b"}"):
            got = self.run_hook(None, "", raw=raw)
            self.assertEqual(got["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_minor_7_a_manifest_that_cannot_be_read_fails_closed(self):
        plugin = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, plugin, ignore_errors=True)
        shutil.copytree(os.path.join(ROOT, "hooks"), os.path.join(plugin, "hooks"),
                        ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(os.path.join(ROOT, "agents"), os.path.join(plugin, "agents"))
        gate = os.path.join(plugin, "hooks", "reader-gate.py")
        for agent in ("principal:clean-reader", "x:clean-reader"):
            got = self.run_hook(agent, self.scratch + "/answers/3.md", gate=gate)
            self.assertEqual(got["hookSpecificOutput"]["permissionDecision"], "deny", agent)

    def test_1c_minor_5_outside_a_scratch_root_no_opinion(self):
        other = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, other, ignore_errors=True)
        for path in ("/etc/questions/x", self.home + "/.ssh/questions/id",
                     other + "/questions/x"):
            with self.subTest(path=path):
                self.assertEqual(self.run_hook("principal:clean-reader", path), {})
        for path in (self.scratch + "/coordinator/questions/x.md",
                     self.scratch + "/check/questions/x.md"):
            with self.subTest(path=path):
                self.assertEqual(self.decision("principal:clean-reader", path), "deny")
        self.assertEqual(self.decision("principal:clean-reader",
                                       self.scratch + "/questions/x.md"), "allow")

    def test_the_gate_fires_on_read(self):
        with open(HOOKS, encoding="utf-8") as fh:
            entries = json.load(fh)["hooks"]["PreToolUse"]
        self.assertIn({"matcher": "Read", "hooks": [{
            "type": "command",
            "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/reader-gate.py\""}]}, entries)


class QuestionReaderGateTest(unittest.TestCase):
    """The question reader: a question's `question.md` in a line's directory
    of the sitting's scratch gets no opinion, never an allow; every other read
    is refused."""

    setUp = ReaderGateTest.setUp
    run_hook = ReaderGateTest.run_hook
    decision = ReaderGateTest.decision
    AGENT = "principal:question-reader"

    def test_the_line_s_question_gets_no_opinion_and_never_an_allow(self):
        for path in (self.scratch + "/lines/l1/1/question.md",
                     self.scratch + "/lines/rotation/12/question.md",
                     self.home + "/.claude/jobs/0f82a3c4/tmp/sit/lines/l1/3/question.md"):
            with self.subTest(path=path):
                self.assertEqual(self.run_hook(self.AGENT, path), {})

    def test_everything_else_is_refused(self):
        s = self.scratch
        for path in (s + "/lines/l1/1/packet.md", s + "/lines/l1/1/draws/draw-1.json",
                     s + "/lines/l1/1/lead.json", s + "/lines/l1/1/leak.json",
                     s + "/lines/l1/drawn-1/question.md", s + "/lines/l1/01/question.md",
                     s + "/lines/l1/0/question.md", s + "/lines/l1/index",
                     s + "/lines/question.md", s + "/questions/3.md", s + "/answers/3.md",
                     s + "/replies/lines/l1/1/question.md",
                     s + "/coordinator/lines/l1/1/question.md", s + "/graph.json",
                     s + "/lines/l1/1/../2/packet.md",
                     self.checkout + "/lines/l1/1/question.md",
                     "/etc/lines/l1/1/question.md", self.home + "/.ssh/lines/l1/1/question.md",
                     "lines/l1/1/question.md", ""):
            with self.subTest(path=path):
                self.assertEqual(self.decision(self.AGENT, path), "deny")

    def test_another_tool_is_refused(self):
        self.assertEqual(self.decision(self.AGENT, self.scratch + "/lines/l1/1/question.md",
                                       tool="Grep"), "deny")

    def test_a_link_out_of_a_line_is_refused(self):
        os.makedirs(os.path.join(self.scratch, "lines", "l1", "1"))
        os.symlink(os.path.join(self.scratch, "answers", "3.md"),
                   os.path.join(self.scratch, "lines", "l1", "1", "question.md"))
        self.assertEqual(self.decision(self.AGENT, self.scratch + "/lines/l1/1/question.md"),
                         "deny")

    def test_the_clean_reader_is_not_given_a_line_s_question(self):
        self.assertEqual(self.decision("principal:clean-reader",
                                       self.scratch + "/lines/l1/1/question.md"), "deny")

    def test_input_that_does_not_parse_is_refused_to_it(self):
        got = self.run_hook(None, "", raw=b'{"agent_type": "principal:question-reader", oops')
        self.assertEqual(got["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn("a question reader reads", got["hookSpecificOutput"]
                      ["permissionDecisionReason"])
        got = self.run_hook(self.AGENT, self.scratch + "/answers/3.md")
        self.assertIn("a question reader reads", got["hookSpecificOutput"]
                      ["permissionDecisionReason"])

    def test_no_decision_of_the_gate_is_an_allow_for_it(self):
        with open(GATE, encoding="utf-8") as fh:
            text = fh.read()
        body = text[text.index("    if question_reader(call, env, plugin, own):"):
                    text.index("    if not guarded(call, env, plugin, own):")]
        self.assertNotIn('"allow"', body)


if __name__ == "__main__":
    unittest.main()
