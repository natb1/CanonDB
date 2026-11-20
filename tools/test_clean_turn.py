"""The clean turn: a process of its own, checked before it runs and after.

Every test but one mocks the harness; the live probe runs only where
CLEAN_TURN_LIVE=1 is set."""

import contextlib
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FIXTURE = os.path.join(HERE, "fixtures", "valid.json")
CLEAN = os.path.join(ROOT, "clean")

sys.path.insert(0, HERE)

import clean_turn  # noqa: E402
import packet  # noqa: E402

EMAIL = "someone.else@example.invalid"
QUESTION = "What is a kept record for, before anything is built on it?\n"
#: the AI's earlier answers, each under its question, as packet.py writes them
PAIRS = [("What is the first question?", "An earlier answer of the AI's, on what is kept."),
         ("What is the second question?", "A later one, on what settles it, in series of "
                                          "errands.")]
#: a key the mocked harness leaves out of its `init`
GONE = object()


class Done:
    def __init__(self, returncode, stdout):
        self.returncode, self.stdout, self.stderr = returncode, stdout, ""


class Harness:
    """The harness, mocked: `auth status` gives the account, and each run
    gives its `init` and its result, as stream-json does."""

    def __init__(self, answers=("An answer.",), init=None, returncode=0, email=EMAIL,
                 turns=1, inits=1, during=None):
        self.answers = list(answers)
        self.init = init or {}
        self.returncode = returncode
        self.email = email
        self.turns = turns
        self.inits = inits
        self.during = during
        self.calls = []

    def __call__(self, cmd, **kw):
        if cmd[1:3] == ["auth", "status"]:
            self.calls.append(("auth", cmd, kw))
            return Done(0, json.dumps({"email": self.email}) if self.email else "{}")
        cwd = kw["cwd"]
        system_file = cmd[cmd.index("--system-prompt-file") + 1]
        with open(system_file, encoding="utf-8") as fh:
            system = fh.read()
        self.calls.append(("run", cmd, dict(kw, listing=os.listdir(cwd), system=system)))
        init = {"type": "system", "subtype": "init", "cwd": cwd, "original_cwd": cwd,
                "session_id": "s-1", "tools": [], "mcp_servers": [], "slash_commands": [],
                "skills": [], "additional_directories": [], "output_style": "default",
                "agents": ["Explore"],
                "plugins": [{"name": "x", "path": "builtin", "source": "x@builtin"}],
                "claude_code_version": "9.9.9", "model": "a-model"}
        init.update(self.init)
        for key in [k for k, v in init.items() if v is GONE]:
            del init[key]
        if self.during:
            self.during()
        text = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
        if callable(text):
            text = text(cwd)
        result = {"type": "result", "subtype": "success", "is_error": False,
                  "result": text, "session_id": "s-1", "total_cost_usd": 0.01}
        if self.turns is not GONE:
            result["num_turns"] = self.turns
        return Done(self.returncode, "\n".join(json.dumps(e) for e in
                                                [init] * self.inits + [result]))

    def runs(self):
        return [c for c in self.calls if c[0] == "run"]


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = self.tmp.name
        self.packet = self.path("packet.md")
        packet.write(self.packet, packet.text(PAIRS), FIXTURE, 2)
        self.question = self.path("question.txt")
        with open(self.question, "w", encoding="utf-8") as fh:
            fh.write(QUESTION)
        self.leak = self.path("leak.json")
        done = subprocess.run([sys.executable, os.path.join(HERE, "public.py"), "question",
                               FIXTURE, self.question, "--record", self.leak],
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.approval = self.path("approval.json")
        self.write_json(self.approval, {"sha256": self.sha(self.question),
                                        "approved": "2030-01-02T03:04:05Z"})
        self.out = self.path("q1")

    def path(self, name):
        return os.path.join(self.dir, name)

    @staticmethod
    def sha(path):
        with open(path, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()

    @staticmethod
    def write_json(path, obj):
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(obj, fh)

    def main(self, argv, harness=None):
        harness = harness or Harness()
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = clean_turn.main(argv, runner=harness)
        return code, out.getvalue(), err.getvalue(), harness

    def answer(self, *extra, harness=None, origin=None):
        argv = ["answer", "--packet", self.packet, "--question", self.question,
                "--out", self.out, "--leak", self.leak]
        argv += origin if origin is not None else ["--approval", self.approval]
        return self.main(argv + list(extra), harness)


class AnswerTest(Base):
    def test_three_draws_by_default_each_kept_and_none_chosen(self):
        h = Harness(answers=("First.", "Second.", "Third."))
        code, out, err, _ = self.answer(harness=h)
        self.assertEqual(code, 0, err)
        self.assertEqual(len(h.runs()), 3)
        texts = []
        for i in (1, 2, 3):
            with open(os.path.join(self.out, "draw-%d.json" % i), encoding="utf-8") as fh:
                d = json.load(fh)
            texts.append(d["answer"])
            self.assertEqual(d["tier"], clean_turn.spec("answerer")["tier"])
            self.assertEqual(d["question_sha256"], self.sha(self.question))
            self.assertEqual(d["packet_sha256"], self.sha(self.packet))
            self.assertEqual(d["spec_sha256"], self.sha(os.path.join(CLEAN, "answerer.md")))
            for key in ("cli_version", "session_id", "cost_usd", "flags", "residue"):
                self.assertIn(key, d)
        self.assertEqual(texts, ["First.", "Second.", "Third."])
        with open(os.path.join(self.out, "manifest.json"), encoding="utf-8") as fh:
            manifest = json.load(fh)
        self.assertIsNone(manifest["chosen"])
        self.assertEqual([d["file"] for d in manifest["draws"]],
                         ["draw-1.json", "draw-2.json", "draw-3.json"])
        self.assertEqual(manifest["of_record"], "draw-1.json")
        self.assertNotIn(EMAIL, json.dumps(manifest))

    def test_each_draw_is_its_own_process_in_a_fresh_empty_directory(self):
        h = Harness()
        os.environ["CLAUDE_PROJECT_DIR"] = self.dir
        self.addCleanup(os.environ.pop, "CLAUDE_PROJECT_DIR", None)
        self.answer("--draws", "2", harness=h)
        runs = h.runs()
        self.assertEqual(len({kw["cwd"] for _, _, kw in runs}), 2)
        for _, cmd, kw in runs:
            self.assertEqual(kw["listing"], [])
            self.assertFalse(os.path.exists(kw["cwd"]), "removed after")
            self.assertEqual(kw["env"]["CLAUDE_CODE_DISABLE_AUTO_MEMORY"], "1")
            self.assertEqual(kw["env"]["CLAUDE_CODE_DISABLE_CLAUDE_MDS"], "1")
            self.assertNotIn("CLAUDE_PROJECT_DIR", kw["env"])
            self.assertEqual(kw["env"]["PWD"], kw["cwd"])
            self.assertEqual(kw["system"], clean_turn.spec("answerer")["body"])
            # a fixed line of the tool's opens the prompt, the question stands last
            self.assertTrue(kw["input"].startswith(clean_turn.OPENING + "\n"))
            self.assertTrue(kw["input"].endswith(clean_turn.NOW + "\n" + QUESTION))
            self.assertIn(packet.QUESTION + "\nWhat is the second question?\n" + packet.ANSWER
                          + "\nA later one", kw["input"])
            # the prompt goes on stdin alone: nothing of it is on the command line
            for arg in cmd:
                for words in (QUESTION.strip(), "A later one", "first question"):
                    self.assertNotIn(words, arg)
            for flag in ("-p", "--setting-sources", "--disable-slash-commands",
                         "--strict-mcp-config", "--mcp-config", "--tools", "--model",
                         "--output-format"):
                self.assertIn(flag, cmd)
            self.assertEqual(cmd[cmd.index("--tools") + 1], "")
            self.assertEqual(cmd[cmd.index("--setting-sources") + 1], "")
            self.assertEqual(cmd[cmd.index("--mcp-config") + 1], '{"mcpServers":{}}')

    def test_the_dry_run_prints_and_runs_nothing(self):
        h = Harness()
        code, out, _, _ = self.answer("--dry-run", harness=h)
        self.assertEqual(code, 0)
        self.assertEqual(h.calls, [])
        self.assertIn("--system-prompt-file", out)
        self.assertIn(clean_turn.spec("answerer")["body"].splitlines()[0], out)
        self.assertIn(QUESTION.strip(), out)
        self.assertFalse(os.path.exists(self.out))

    def test_a_packet_not_written_by_packet_py_is_refused(self):
        os.unlink(self.packet + packet.SIDECAR)
        self.assertEqual(self.answer()[0], clean_turn.PACKET)

    def test_a_packet_changed_after_it_was_written_is_refused(self):
        with open(self.packet, "a", encoding="utf-8") as fh:
            fh.write("\n---\n\nA note of the user's.\n")
        self.assertEqual(self.answer()[0], clean_turn.PACKET)

    def test_a_sidecar_of_another_tool_is_refused(self):
        self.write_json(self.packet + packet.SIDECAR,
                        {"tool": "another.py", "sha256": self.sha(self.packet)})
        self.assertEqual(self.answer()[0], clean_turn.PACKET)

    def test_a_leak_record_over_another_text_is_refused(self):
        with open(self.question, "a", encoding="utf-8") as fh:
            fh.write("And one word more.\n")
        self.write_json(self.approval, {"sha256": self.sha(self.question),
                                        "approved": "2030-01-02T03:04:05Z"})
        self.assertEqual(self.answer()[0], clean_turn.LEAK)

    def test_a_leak_record_over_another_graph_is_refused(self):
        with open(self.leak, encoding="utf-8") as fh:
            record = json.load(fh)
        for other in ("0" * 64, None):
            with self.subTest(other=other):
                self.write_json(self.leak, dict(record, graph_sha256=other))
                self.assertEqual(self.answer()[0], clean_turn.LEAK)

    def test_a_leak_record_that_is_no_pass_is_refused(self):
        self.write_json(self.leak, {"tool": "public.py question", "exit": 2,
                                    "sha256": self.sha(self.question)})
        self.assertEqual(self.answer()[0], clean_turn.LEAK)
        os.unlink(self.leak)
        self.assertEqual(self.answer()[0], clean_turn.LEAK)

    def test_an_approval_of_another_text_or_with_no_time_is_refused(self):
        self.write_json(self.approval, {"sha256": "0" * 64, "approved": "2030-01-02T03:04:05Z"})
        self.assertEqual(self.answer()[0], clean_turn.ORIGIN)
        self.write_json(self.approval, {"sha256": self.sha(self.question)})
        self.assertEqual(self.answer()[0], clean_turn.ORIGIN)

    def test_an_origin_must_be_shown(self):
        with self.assertRaises(SystemExit) as raised:
            self.answer(origin=[])
        self.assertEqual(raised.exception.code, 2)

    def drawer_record(self, answer):
        path = self.path("drawn.json")
        self.write_json(path, {"kind": "drawer", "answer": answer,
                               "answer_sha256": hashlib.sha256(answer.encode()).hexdigest()})
        return path

    def test_a_question_drawn_by_the_drawer_needs_no_approval(self):
        line = "%s | from: An earlier answer | clause: earlier | direction: up" % QUESTION.strip()
        drawn = self.drawer_record("Another question? | from: A later | clause: later | "
                                   "direction: down\n" + line + "\n")
        code, _, err, _ = self.answer(origin=["--drawn-from", drawn])
        self.assertEqual(code, 0, err)
        with open(os.path.join(self.out, "manifest.json"), encoding="utf-8") as fh:
            self.assertIn("drawn_from_sha256", json.load(fh)["origin"])

    def test_a_question_not_drawn_is_refused_its_drawn_from(self):
        drawn = self.drawer_record("Another question? | from: A later | clause: later | "
                                   "direction: down\n")
        self.assertEqual(self.answer(origin=["--drawn-from", drawn])[0], clean_turn.ORIGIN)

    def test_a_drawer_record_altered_by_hand_is_refused(self):
        line = "%s | from: An earlier answer | clause: earlier | direction: up" % QUESTION.strip()
        drawn = self.drawer_record(line)
        with open(drawn, encoding="utf-8") as fh:
            d = json.load(fh)
        d["answer"] += "\nAn added question? | from: x | clause: x | direction: up"
        self.write_json(drawn, d)
        self.assertEqual(self.answer(origin=["--drawn-from", drawn])[0], clean_turn.ORIGIN)

    def test_a_run_not_clean_is_not_written(self):
        inits = [{"tools": ["Read"]}, {"mcp_servers": [{"name": "x"}]},
                 {"skills": ["s"]}, {"slash_commands": ["/x"]},
                 {"plugins": [{"name": "y", "path": "/somewhere", "source": "y@builtin"}]},
                 {"plugins": [{"name": "y", "path": "builtin", "source": "y@elsewhere"}]},
                 {"plugins": [{"name": "y", "path": "builtin"}]},
                 {"cwd": "/elsewhere"}, {"original_cwd": "/elsewhere"},
                 {"additional_directories": ["/elsewhere"]}, {"output_style": "custom"},
                 {"agents": None}]
        # a key missing, or null, counts as held
        for key in clean_turn.EMPTY + ("plugins", "cwd", "original_cwd", "output_style"):
            inits += [{key: GONE}, {key: None}]
        for init in inits:
            with self.subTest(init=init):
                out = self.path("q-%d" % len(os.listdir(self.dir)))
                self.out = out
                code, _, _, _ = self.answer(harness=Harness(init=init))
                self.assertEqual(code, clean_turn.UNCLEAN)
                self.assertFalse([n for n in os.listdir(out) if n.startswith("draw-")])
                with open(os.path.join(out, "manifest.json"), encoding="utf-8") as fh:
                    self.assertTrue(all("refused" in d for d in json.load(fh)["draws"]))

    def test_an_answer_that_gives_the_account_away_is_not_written(self):
        for text in ("Write to %s." % EMAIL, "Signed, Someone.Else", "As someone.else says."):
            with self.subTest(text=text):
                self.out = self.path("q-%d" % len(os.listdir(self.dir)))
                h = Harness(answers=("A clean one.", text, "Another clean one."))
                code, _, err, _ = self.answer(harness=h)
                self.assertEqual(code, clean_turn.EXPOSED)
                self.assertEqual(sorted(n for n in os.listdir(self.out) if n.startswith("draw-")),
                                 ["draw-1.json", "draw-3.json"])
                self.assertNotIn(EMAIL, err)
                with open(os.path.join(self.out, "manifest.json"), encoding="utf-8") as fh:
                    self.assertNotIn(EMAIL.split("@")[0], fh.read())

    def test_an_answer_that_names_its_directory_is_not_written(self):
        h = Harness(answers=(lambda cwd: "I stand in %s." % cwd,))
        self.assertEqual(self.answer("--draws", "1", harness=h)[0], clean_turn.EXPOSED)

    def test_a_failed_run_is_refused(self):
        self.assertEqual(self.answer(harness=Harness(returncode=1))[0], clean_turn.RUN)

    def test_every_init_is_read(self):
        self.assertEqual(self.answer(harness=Harness(inits=2))[0], clean_turn.UNCLEAN)

    def test_a_run_that_made_no_model_turn_is_refused_and_not_kept(self):
        # a prompt the harness answered itself: no request, no turn, its own line
        for turns in (0, 2, GONE, None):
            with self.subTest(turns=turns):
                self.out = self.path("q-%d" % len(os.listdir(self.dir)))
                h = Harness(answers=("/compact isn't available in this environment.",),
                            turns=turns)
                code, _, err, _ = self.answer("--draws", "1", harness=h)
                self.assertEqual(code, clean_turn.RUN, err)
                self.assertFalse([n for n in os.listdir(self.out) if n.startswith("draw-")])

    def test_a_run_s_directory_inside_a_repository_is_refused(self):
        repo = self.path("repo")
        os.makedirs(os.path.join(repo, ".git"))
        old, clean_turn.RUNS = clean_turn.RUNS, repo
        self.addCleanup(setattr, clean_turn, "RUNS", old)
        h = Harness()
        self.assertEqual(self.answer("--draws", "1", harness=h)[0], clean_turn.RUN)
        self.assertEqual(h.runs(), [])

    def test_an_account_that_cannot_be_read_is_refused(self):
        self.assertEqual(self.answer(harness=Harness(email=""))[0], clean_turn.ACCOUNT)

    def test_draws_already_there_are_never_overwritten(self):
        os.makedirs(self.out)
        with open(os.path.join(self.out, "draw-1.json"), "w") as fh:
            fh.write("{}")
        self.assertEqual(self.answer()[0], clean_turn.OUT)

    def test_a_claimed_directory_is_refused(self):
        os.makedirs(self.out)
        with open(os.path.join(self.out, "manifest.json"), "w") as fh:
            fh.write('{"state": "running"}')
        h = Harness()
        self.assertEqual(self.answer(harness=h)[0], clean_turn.OUT)
        self.assertEqual(h.runs(), [])

    def test_an_out_that_names_a_file_is_refused(self):
        with open(self.out, "w") as fh:
            fh.write("x")
        self.assertEqual(self.answer()[0], clean_turn.OUT)

    def test_a_draw_written_by_another_run_meanwhile_is_not_overwritten(self):
        # two runs into one directory: the draw is created exclusively, so
        # the second never writes over the first's
        def meanwhile():
            path = os.path.join(self.out, "draw-1.json")
            if not os.path.exists(path):
                with open(path, "w") as fh:
                    fh.write('{"answer": "the other run\'s"}')
        code, _, _, _ = self.answer("--draws", "1", harness=Harness(during=meanwhile))
        self.assertEqual(code, clean_turn.OUT)
        with open(os.path.join(self.out, "draw-1.json")) as fh:
            self.assertIn("the other run", fh.read())

    def test_text_that_is_not_utf8_is_refused(self):
        with open(self.question, "wb") as fh:
            fh.write(b"\xff\xfe?")
        self.assertEqual(self.answer()[0], clean_turn.USAGE)
        with open(self.packet, "wb") as fh:
            fh.write(b"\xff")
        self.write_json(self.packet + packet.SIDECAR,
                        {"tool": "packet.py", "sha256": self.sha(self.packet)})
        self.assertEqual(clean_turn.main(["draw", "--packet", self.packet, "--out", self.out,
                                          "--dry-run"], runner=Harness()), clean_turn.PACKET)

    def test_the_refusal_codes_are_distinct(self):
        codes = (clean_turn.PACKET, clean_turn.LEAK, clean_turn.ORIGIN, clean_turn.UNCLEAN,
                 clean_turn.EXPOSED, clean_turn.RUN, clean_turn.ACCOUNT, clean_turn.SPEC,
                 clean_turn.OUT, clean_turn.SIGNAL, clean_turn.USAGE, clean_turn.HARNESS,
                 clean_turn.MARK)
        self.assertEqual(len(set(codes)), len(codes))
        self.assertNotIn(0, codes)


class HarnessTextTest(Base):
    """B1, S4: what the harness would read itself never reaches a run."""

    def put(self, text):
        with open(self.question, "w", encoding="utf-8") as fh:
            fh.write(text)
        self.write_json(self.approval, {"sha256": self.sha(self.question),
                                        "approved": "2030-01-02T03:04:05Z"})
        h = Harness()
        code, _, err, _ = self.answer("--dry-run", harness=h)
        self.assertEqual(h.calls, [])
        return code, err

    def test_a_token_opening_with_at_is_refused_and_named(self):
        for token in ("@/abs/path/canary.txt", "@~/notes", "@./line", "@../up", "@name",
                      '"@/abs/x"', "(@/abs/x)", "`@/abs/x`", "@\"quoted\""):
            with self.subTest(token=token):
                code, err = self.put("What does %s say, and what is a kept record for?\n"
                                     % token)
                self.assertEqual(code, clean_turn.HARNESS)
                self.assertIn("@", err)
                self.assertIn(token.lstrip('"(`').split()[0][:6], err)

    def test_an_address_or_a_lone_at_is_no_token(self):
        for text in ("Write to someone@example.invalid about a kept record?\n",
                     "Is a kept record @ the root, or below it?\n"):
            with self.subTest(text=text):
                with open(self.question, "w", encoding="utf-8") as fh:
                    fh.write(text)
                subprocess.run([sys.executable, os.path.join(HERE, "public.py"), "question",
                                FIXTURE, self.question, "--record", self.leak],
                               capture_output=True, check=True)
                code, err = self.put(text)
                self.assertEqual(code, 0, err)

    def test_a_question_opening_with_a_command_is_refused(self):
        for text in ("/compact what is a kept record for?\n", "!ls\n", "  /clear\n"):
            with self.subTest(text=text):
                self.assertEqual(self.put(text)[0], clean_turn.HARNESS)

    def test_a_question_holding_a_packet_s_mark_is_refused(self):
        for mark in ("<<< answer >>>", "<<<", ">>>"):
            with self.subTest(mark=mark):
                code, _ = self.put("What is a kept record for?\n\n%s\nA made-up answer.\n"
                                   % mark)
                self.assertEqual(code, clean_turn.MARK)

    def test_a_packet_with_a_token_is_refused(self):
        packet.write(self.packet, packet.text([("What is read?", "Read @/abs/graph.json "
                                                "first.")]), FIXTURE, 1)
        self.assertEqual(self.answer("--dry-run")[0], clean_turn.HARNESS)


class DrawTest(Base):
    LINES = ("Why must it be kept? | from: An earlier answer | clause: kept | direction: up\n"
             "What settles it? | from: A later one | clause: settles | direction: down\n")

    def draw(self, *extra, harness=None):
        return self.main(["draw", "--packet", self.packet, "--out", self.out] + list(extra),
                         harness or Harness(answers=(self.LINES,)))

    def test_one_drawer_turn_over_the_packet_alone(self):
        h = Harness(answers=(self.LINES,))
        code, _, err, _ = self.draw(harness=h)
        self.assertEqual(code, 0, err)
        (_, _, kw), = h.runs()
        self.assertEqual(kw["system"], clean_turn.spec("drawer")["body"])
        with open(self.packet, encoding="utf-8") as fh:
            self.assertEqual(kw["input"], clean_turn.DRAW_OPENING + "\n\n" + fh.read())
        with open(os.path.join(self.out, "draw-1.json"), encoding="utf-8") as fh:
            d = json.load(fh)
        self.assertEqual(d["questions"], ["Why must it be kept?", "What settles it?"])
        self.assertEqual(d["kind"], "drawer")

    def test_only_a_line_in_the_drawer_s_form_is_a_question(self):
        self.assertEqual(clean_turn.drawn_lines(
            " | from: x | clause: y | direction: up\n"
            "Half a line? | from: x\n"
            "Sideways? | from: x | clause: y | direction: sideways\n"
            "Whole? | from: x | clause: y | direction: down\n"), ["Whole?"])

    def test_a_drawn_line_is_a_question_answer_takes(self):
        self.draw()
        with open(self.question, "w", encoding="utf-8") as fh:
            fh.write("What settles it?\n")
        subprocess.run([sys.executable, os.path.join(HERE, "public.py"), "question", FIXTURE,
                        self.question, "--record", self.leak], capture_output=True, check=True)
        drawn = os.path.join(self.out, "draw-1.json")
        self.out = self.path("q2")
        code, _, err, _ = self.answer(origin=["--drawn-from", drawn])
        self.assertEqual(code, 0, err)

    def test_the_redraw_signal_must_open_exactly_one_answer(self):
        for words in ("A sentence of the user's that is long", "  ", "e", "A later one",
                      "series of errands.", "on what settles it, in",
                      "A later one, on what settles it, in series of err",
                      "@/abs/x opens nothing here"):
            with self.subTest(words=words):
                code = self.draw("--from", words)[0]
                self.assertIn(code, (clean_turn.SIGNAL, clean_turn.HARNESS))
                self.assertFalse(os.path.exists(self.out))
        h = Harness(answers=(self.LINES,))
        code, _, err, _ = self.draw("--from", "A later  one, on\nwhat", harness=h)
        self.assertEqual(code, 0, err)
        self.assertTrue(h.runs()[0][2]["input"].startswith(
            clean_turn.DRAW_OPENING + "\n\nDraw from the answer that opens: A later one, on "
            "what\n\n"))

    def test_a_signal_that_opens_two_answers_is_refused(self):
        packet.write(self.packet, packet.text([("Q one?", "A kept record is read first."),
                                               ("Q two?", "A kept record is read last.")]),
                     FIXTURE, 2)
        self.assertEqual(self.draw("--from", "A kept record is", "--dry-run")[0],
                         clean_turn.SIGNAL)
        self.assertEqual(self.draw("--from", "A kept record is read last", "--dry-run")[0], 0)

    def test_a_line_s_answer_may_be_the_signal(self):
        # the packet's answers are the graph's and the line's alike
        self.assertEqual(self.draw("--from", "An earlier answer of the AI's",
                                   "--dry-run")[0], 0)

    def test_draws_already_there_are_never_overwritten(self):
        os.makedirs(self.out)
        with open(os.path.join(self.out, "draw-1.json"), "w") as fh:
            fh.write("{}")
        h = Harness(answers=(self.LINES,))
        self.assertEqual(self.draw(harness=h)[0], clean_turn.OUT)
        self.assertEqual(h.runs(), [])
        with open(os.path.join(self.out, "draw-1.json")) as fh:
            self.assertEqual(fh.read(), "{}")

    def test_an_empty_packet_raises_nothing(self):
        packet.write(self.packet, "", FIXTURE, 0)
        self.assertEqual(self.draw()[0], clean_turn.PACKET)

    def test_the_dry_run(self):
        h = Harness()
        code, out, _, _ = self.draw("--dry-run", harness=h)
        self.assertEqual(code, 0)
        self.assertEqual(h.calls, [])
        self.assertIn("A later one", out)


class ProbeTest(Base):
    def test_clean_is_exit_zero_and_says_what_it_saw(self):
        code, out, _, h = self.main(["probe"])
        self.assertEqual(code, 0)
        facts = json.loads(out)
        self.assertTrue(facts["clean"])
        self.assertEqual(facts["seen"]["tools"], [])
        self.assertEqual(h.runs()[0][2]["system"], clean_turn.spec("probe")["body"])

    def test_anything_beyond_the_stated_residue_fails(self):
        code, out, _, _ = self.main(["probe"], Harness(init={"mcp_servers": [{"name": "m"}]}))
        self.assertEqual(code, clean_turn.UNCLEAN)
        self.assertEqual(json.loads(out)["beyond_the_stated_residue"], ["mcp_servers"])

    def test_the_dry_run(self):
        h = Harness()
        code, out, _, _ = self.main(["probe", "--dry-run"], h)
        self.assertEqual((code, h.calls), (0, []))
        self.assertIn(clean_turn.PROBE_PROMPT, out)


class EnvironmentTest(unittest.TestCase):
    def test_only_the_listed_variables_reach_the_run(self):
        env = clean_turn.environment({"CLAUDE_PROJECT_DIR": "/p", "CLAUDE_PLUGIN_ROOT": "/r",
                                      "CLAUDE_CODE_PLUGIN_DIRS": "/d", "CLAUDECODE": "1",
                                      "CLAUDE_CONFIG_DIR": "/c", "HOME": "/h",
                                      "ANTHROPIC_BASE_URL": "http://127.0.0.1:1",
                                      "ANTHROPIC_DEFAULT_OPUS_MODEL": "x",
                                      "ANTHROPIC_CUSTOM_HEADERS": "x", "NODE_OPTIONS": "x",
                                      "XDG_CONFIG_HOME": "/x", "GIT_DIR": "/g",
                                      "PWD": "/caller", "OLDPWD": "/before", "PATH": "/bin"},
                                     cwd="/tmp/t1")
        self.assertEqual(env, {"CLAUDE_CONFIG_DIR": "/c", "HOME": "/h", "PATH": "/bin",
                               "PWD": "/tmp/t1",
                               "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1",
                               "CLAUDE_CODE_DISABLE_CLAUDE_MDS": "1"})


class SpecTest(unittest.TestCase):
    """The specs: the whole system prompt each, outside agents/, the tier
    named in their frontmatter and nowhere else."""

    NAMES = ("answerer", "drawer", "probe")

    def read(self, name):
        with open(os.path.join(CLEAN, name + ".md"), encoding="utf-8") as fh:
            return fh.read()

    def test_the_fields(self):
        for name in self.NAMES:
            head = self.read(name)[4:].partition("\n---\n")[0]
            self.assertEqual([l.partition(":")[0] for l in head.splitlines()],
                             ["name", "description", "model"], name)
            self.assertIn("outside agents/", head, name)

    def test_no_tier_but_in_the_model_field(self):
        tiers = {clean_turn.spec(n)["tier"] for n in self.NAMES}
        pattern = re.compile(r"\b(%s)\b" % "|".join(sorted(tiers)), re.I)
        for name in self.NAMES:
            text = self.read(name)
            head, _, body = text[4:].partition("\n---\n")
            rest = "\n".join(l for l in head.splitlines() if not l.startswith("model:"))
            self.assertIsNone(pattern.search(rest + body), name)
        with open(os.path.join(HERE, "clean_turn.py"), encoding="utf-8") as fh:
            self.assertIsNone(pattern.search(fh.read()))
        self.assertIsNone(re.search(r"\bclaude-[a-z]+-\d", self.read("answerer")))

    def test_no_spec_is_a_helper(self):
        for name in self.NAMES:
            for where in ("agents", os.path.join(".claude", "agents")):
                self.assertFalse(os.path.exists(os.path.join(ROOT, where, name + ".md")))

    def test_the_answerer_s_rules(self):
        body = " ".join(clean_turn.spec("answerer")["body"].split())
        for words in ("You are answering one question.",
                      "Above it are your own earlier answers, oldest first, each under the "
                      "question it was given to",
                      "\"<<< question >>>\"", "\"<<< answer >>>\"",
                      "\"<<< the question you are asked now >>>\"",
                      "are all you were given. You have no tools.",
                      "Answer in your own words, from your own reasoning.",
                      "say plainly where two things you said conflict and which of them gives "
                      "way",
                      "say first what it is for, and answer the how from that",
                      "Do not guess what the asker wants. What you know of the asker is what "
                      "the question says.",
                      "Give the reason a case would turn on, not only the ruling.",
                      "Your answer is public.",
                      "\"Rests on:\"", "\"Presupposes:\"", "or says \"nothing earlier\"",
                      "Reply with the answer and nothing else."):
            self.assertIn(words, body)

    def test_the_drawer_s_rules(self):
        body = " ".join(clean_turn.spec("drawer")["body"].split())
        for words in ("You are given nothing else. You have no tools.",
                      "each under the question it was given to",
                      "A question goes down, from a clause that would have to be settled "
                      "before it could be acted on; or up, from something an answer took for "
                      "granted.",
                      "draw no more than five",
                      "<question> | from: <the opening words of the answer it is drawn from> | "
                      "clause: <the words of that answer it is drawn from> | direction: up",
                      "Ask nothing the answers do not raise, and add no fact."):
            self.assertIn(words, body)


@unittest.skipUnless(os.environ.get("CLEAN_TURN_LIVE") == "1",
                     "a live run of the harness; set CLEAN_TURN_LIVE=1 to run it")
class LiveTest(unittest.TestCase):
    def test_the_probe_is_clean(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = clean_turn.main(["probe"])
        self.assertEqual(code, 0, out.getvalue())


class _Listener:
    """A stand-in for the service on the loopback interface: it keeps each
    request's path and body and answers every message with a canned
    reply, so that the harness runs whole and no model is asked anything."""

    EVENTS = (
        ("message_start", {"type": "message_start", "message": {
            "id": "m1", "type": "message", "role": "assistant", "model": "m", "content": [],
            "stop_reason": None, "stop_sequence": None,
            "usage": {"input_tokens": 1, "output_tokens": 1}}}),
        ("content_block_start", {"type": "content_block_start", "index": 0,
                                 "content_block": {"type": "text", "text": ""}}),
        ("content_block_delta", {"type": "content_block_delta", "index": 0,
                                 "delta": {"type": "text_delta", "text": "ok"}}),
        ("content_block_stop", {"type": "content_block_stop", "index": 0}),
        ("message_delta", {"type": "message_delta", "usage": {"output_tokens": 1},
                           "delta": {"stop_reason": "end_turn", "stop_sequence": None}}),
        ("message_stop", {"type": "message_stop"}))

    def __init__(self):
        import http.server
        import threading
        seen = self.seen = []
        events = self.EVENTS

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"{}")

            def do_POST(self):
                body = self.rfile.read(int(self.headers.get("content-length") or 0))
                seen.append(body.decode("utf-8", "replace"))
                stream = b'"stream":true' in body.replace(b" ", b"")
                self.send_response(200)
                self.send_header("content-type", "text/event-stream" if stream
                                 else "application/json")
                self.end_headers()
                if stream:
                    for name, data in events:
                        self.wfile.write(("event: %s\ndata: %s\n\n"
                                          % (name, json.dumps(data))).encode())
                else:
                    self.wfile.write(b'{"input_tokens": 1}')

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = "http://127.0.0.1:%d" % self.server.server_address[1]

    def close(self):
        self.server.shutdown()
        self.seen.clear()


@unittest.skipUnless(os.environ.get("CLEAN_TURN_LISTENER") == "1",
                     "runs the real harness against a listener on the loopback interface, "
                     "which receives the harness's sign-in header; set CLEAN_TURN_LISTENER=1")
class HarnessExpansionTest(unittest.TestCase):
    """B1 against the real harness, with no model run: every form of `@`
    the harness expands into a file is one `expands` refuses."""

    def test_every_expanded_form_is_refused(self):
        listener = _Listener()
        self.addCleanup(listener.close)
        where = tempfile.mkdtemp(prefix="c", dir="/tmp")
        self.addCleanup(shutil.rmtree, where, True)
        canary = os.path.join(where, "canary.txt")
        with open(canary, "w") as fh:
            fh.write("CANARY-SEEN\n")
        sp = clean_turn.spec("answerer")
        expanded = []
        for form in ("@%s", '"@%s"', "(@%s)", "x@%s", ".@%s", "-@%s", "[@%s]"):
            token = form % canary
            prompt = "%s\n\nWhat does %s say?\n" % (clean_turn.OPENING, token)
            work = tempfile.mkdtemp(prefix="t", dir="/tmp")
            self.addCleanup(shutil.rmtree, work, True)
            system = os.path.join(work, "..", os.path.basename(work) + ".p")
            with open(system, "w") as fh:
                fh.write(sp["body"])
            self.addCleanup(os.unlink, system)
            env = clean_turn.environment(cwd=work)
            env["ANTHROPIC_BASE_URL"] = listener.url
            subprocess.run([clean_turn.PROGRAM] + clean_turn.flags(system, sp["tier"]),
                           input=prompt, cwd=work, env=env, capture_output=True, text=True,
                           timeout=180)
            if any("CANARY-SEEN" in body for body in listener.seen):
                expanded.append(token)
                with self.assertRaises(clean_turn.Refusal):
                    clean_turn.expands(prompt, "the question")
            listener.seen.clear()
        self.assertIn("@" + canary, expanded, "the harness expanded no form: nothing tested")


class Round5Test(Base):
    """The exclusive claim, an answer no later turn could carry, the
    approval's keys, and the harness's narrower idea of a space."""

    def test_a_second_claim_of_one_directory_is_refused(self):
        clean_turn.claim(self.out, "answerer")
        with self.assertRaises(clean_turn.Refusal) as caught:
            clean_turn.claim(self.out, "answerer")
        self.assertEqual(caught.exception.code, clean_turn.OUT)

    def test_an_answer_holding_a_mark_or_a_token_is_not_kept(self):
        h = Harness(answers=("Use a here-string: cat <<< \"$x\".",
                             "Mark it with @dataclass and list the fields.",
                             "Kept, and of record."))
        code, _, err, _ = self.answer(harness=h)
        self.assertEqual(code, clean_turn.MARK, err)
        with open(os.path.join(self.out, "manifest.json"), encoding="utf-8") as fh:
            manifest = json.load(fh)
        self.assertIn("refused", manifest["draws"][0])
        self.assertIn("@", manifest["draws"][1]["refused"])
        self.assertEqual(manifest["of_record"], "draw-3.json")
        self.assertFalse(os.path.exists(os.path.join(self.out, "draw-1.json")))
        self.assertEqual(clean_turn.judged(
            {"ok": True, "extra": [], "answer": "See @notes.", "cwd": "/tmp/x"}, EMAIL)[0],
            clean_turn.HARNESS)

    def test_an_approval_with_other_keys_is_taken_and_one_without_approved_is_named(self):
        self.write_json(self.approval, {"sha256": self.sha(self.question),
                                        "approved": "2030-01-02T03:04:05Z", "by": "speaker"})
        self.assertEqual(self.answer("--dry-run")[0], 0)
        self.write_json(self.approval, {"sha256": self.sha(self.question),
                                        "approved_at": "2030-01-02T03:04:05Z"})
        code, _, err, _ = self.answer("--dry-run")
        self.assertEqual(code, clean_turn.ORIGIN)
        self.assertIn('"approved"', err)
        self.assertIn("'approved_at'", err)

    def test_at_followed_by_any_space_but_an_ascii_one_is_a_token(self):
        for after in ("\u3000", "\u0085", "\u001c", "\u00a0"):
            with self.subTest(after=repr(after)):
                self.assertTrue(clean_turn.AT.search("Is it @%s/abs/x?" % after))
        for text in ("Is it @ the root?", "Is it @\tthe root?", "Ends @", "a@b.c"):
            with self.subTest(text=text):
                self.assertIsNone(clean_turn.AT.search(text))

    def test_the_account_is_read_in_the_runs_directory(self):
        h = Harness()
        clean_turn.account(h)
        self.assertEqual(h.calls[0][2]["cwd"], clean_turn.RUNS)


class LinePlaceTest(Base):
    """S1: a packet cut for question n of a line is answered only there,
    and only while the line stands as it was cut from."""

    def setUp(self):
        super().setUp()
        self.line = self.path("l1")
        one = os.path.join(self.line, "1")
        os.makedirs(os.path.join(one, "draws"))
        raw = b"What is it for?\n"
        with open(os.path.join(one, "question.md"), "wb") as fh:
            fh.write(raw)
        q = hashlib.sha256(raw).hexdigest()
        for i, text in ((1, "For the morning."), (2, "For the day.")):
            self.write_json(os.path.join(one, "draws", "draw-%d.json" % i),
                            {"kind": "answerer", "answer": text, "question_sha256": q,
                             "answer_sha256": hashlib.sha256(text.encode()).hexdigest()})
        self.manifest = os.path.join(one, "draws", "manifest.json")
        self.write_json(self.manifest, {"kind": "answerer", "question_sha256": q,
                                        "draws": [{"index": 1, "file": "draw-1.json"},
                                                  {"index": 2, "file": "draw-2.json"}]})
        two = os.path.join(self.line, "2")
        os.makedirs(two)
        shutil.copy(self.question, os.path.join(two, "question.md"))
        self.question = os.path.join(two, "question.md")
        self.packet = os.path.join(two, "packet.md")
        self.out = os.path.join(two, "draws")

    def cut(self, *extra):
        done = subprocess.run([sys.executable, os.path.join(HERE, "packet.py"), FIXTURE]
                              + list(extra) + ["-o", self.packet],
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_a_packet_cut_for_its_place_is_taken(self):
        self.cut("--line", self.line)
        code, _, err, _ = self.answer("--draws", "1")
        self.assertEqual(code, 0, err)

    def test_a_packet_cut_without_the_line_is_refused_for_a_question_on_it(self):
        self.cut("--under", "ti-esti")
        code, _, err, h = self.answer("--draws", "1")
        self.assertEqual(code, clean_turn.PACKET)
        self.assertIn("packet.py --line", err)
        self.assertEqual(h.runs(), [])

    def test_a_copied_question_cannot_fill_a_line_s_draws(self):
        """S7 of round 6: the question copied out, a packet cut without the
        line beside it, and --out the line's draws; and a link to the
        line's question."""
        elsewhere = self.path("q")
        os.makedirs(elsewhere)
        line_question = self.question
        self.question = os.path.join(elsewhere, "question.md")
        shutil.copy(line_question, self.question)
        self.packet = os.path.join(elsewhere, "packet.md")
        self.cut("--under", "ti-esti")
        code, _, err, h = self.answer("--draws", "1")
        self.assertEqual(code, clean_turn.PACKET)
        self.assertIn("draws of question 2", err)
        self.assertEqual(h.runs(), [])
        os.remove(self.question)
        os.symlink(line_question, self.question)
        self.out = self.path("elsewhere-draws")
        code, _, err, _ = self.answer("--draws", "1")
        self.assertEqual(code, clean_turn.PACKET)
        self.assertIn("question 2's directory", err)

    def test_an_out_directory_beside_its_place_is_refused(self):
        self.cut("--line", self.line)
        self.out = os.path.dirname(self.out)
        code, _, err, _ = self.answer("--draws", "1")
        self.assertEqual(code, clean_turn.PACKET)
        self.assertIn("the out directory", err)

    def test_a_line_moved_since_the_packet_was_cut_is_refused(self):
        self.cut("--line", self.line)
        with open(self.manifest) as fh:
            d = json.load(fh)
        d["draws"].reverse()
        self.write_json(self.manifest, d)
        code, _, err, _ = self.answer("--draws", "1")
        self.assertEqual(code, clean_turn.PACKET)
        self.assertIn("no longer stands", err)

    def test_a_question_answered_since_is_refused(self):
        self.cut("--line", self.line)
        os.makedirs(self.out)
        self.write_json(os.path.join(self.out, "manifest.json"), {"kind": "answerer"})
        code, _, err, _ = self.answer("--draws", "1")
        self.assertEqual(code, clean_turn.PACKET)
        self.assertIn("answered already", err)


if __name__ == "__main__":
    unittest.main()
