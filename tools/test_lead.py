"""lead.py: the record that a question drafted on the user's side was read, by a helper of the
question-reader kind, for whether it leads the answerer; and packet.py's refusal to carry a
question found to have led."""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from hypo import board, brief, inhand, lead  # noqa: E402

JOB = "s1-b1-1-lead"
ADDED = "2030-01-02T03:00:00Z"
DONE = "2030-01-02T03:10:00Z"
CLOCK = "2030-01-02T03:11:00Z"
SESSION = "sess-1"
REPLY = "verdict: does not lead\nreason: It states the case and the ends to be served.\nstatus: ok\n"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class Store:
    """A board's store, exported as the gate reads it."""

    def __init__(self, directory):
        self.dir = directory
        self.versions_path = os.path.join(directory, "versions.json")
        self.export = os.path.join(directory, "board")
        self.versions = {}
        os.makedirs(self.export)
        self.save()

    def save(self):
        with open(self.versions_path, "w") as fh:
            json.dump(self.versions, fh)

    def send(self, writes):
        for w in writes:
            where = os.path.join(self.export, w["collection"])
            os.makedirs(where, exist_ok=True)
            with open(os.path.join(where, w["doc_id"] + ".json"), "w") as fh:
                json.dump(w["data"], fh)
            key = "%s/%s" % (w["collection"], w["doc_id"])
            self.versions[key] = self.versions.get(key, 0) + 1
        self.save()

    def load(self):
        return board.load(self.export, self.versions_path)


class Base(unittest.TestCase):
    ADDED, CLAIMED, DONE = ADDED, "2030-01-02T03:00:30Z", DONE
    LAUNCHED, STARTED, ENDED = "2030-01-02T03:01:00Z", "2030-01-02T03:01:01Z", \
        "2030-01-02T03:09:00Z"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = tmp.name
        self.n = os.path.join(self.tmp, "lines", "l1", "1")
        os.makedirs(self.n)
        self.question = os.path.join(self.n, "question.md")
        with open(self.question, "w", encoding="utf-8") as fh:
            fh.write("What is a kept record for, and what must it never do?\n")
        self.reply = os.path.join(self.tmp, "coordinator", "replies", JOB)
        os.makedirs(os.path.dirname(self.reply))
        self.write_reply(REPLY)
        self.store = Store(os.path.join(self.tmp, "speaker"))
        self.store.send(board.init(self.store.load(), "doc1"))
        self.add()
        self.launches = [{"id": "h1", "kind": "principal:question-reader", "description": JOB,
                          "at": self.LAUNCHED, "agent_id": "a1", "started": self.STARTED,
                          "ended": self.ENDED}]

    def write_reply(self, text):
        with open(self.reply, "w", encoding="utf-8") as fh:
            fh.write(text)

    def qsha(self):
        with open(self.question, "rb") as fh:
            return sha(fh.read())

    def add(self, kind="lead", inputs=None, jid=JOB):
        sitting, batch, row, _ = jid.split("-")
        given = {"id": jid, "sitting": sitting, "batch": batch, "row": row, "kind": kind,
                 "tier": "full", "inputs": inputs if inputs is not None else
                 {"notebook": "doc1", "question": self.question,
                  "question_fingerprint": self.qsha()}}
        self.store.send(board.add(self.store.load(), [given], self.ADDED))

    def finish(self, jid=JOB, fingerprint=None):
        self.store.send(board.claim(self.store.load(), jid, "coordinator", self.CLAIMED))
        with open(self.reply, "rb") as fh:
            got = sha(fh.read())
        self.store.send(board.done(self.store.load(), jid, "coordinator",
                                   {"reply": self.reply, "fingerprint": fingerprint or got},
                                   self.DONE))

    def record(self, clock=CLOCK, launches=None):
        return lead.record(self.question, self.store.load(), JOB,
                           self.launches if launches is None else launches, "principal", clock)


class RecordTest(Base):
    def test_a_reading_done_and_launched_is_recorded(self):
        self.finish()
        got = self.record()
        self.assertEqual(got["tool"], "lead.py record")
        self.assertEqual(got["sha256"], self.qsha())
        self.assertEqual(got["verdict"], "does not lead")
        self.assertEqual(got["read"], CLOCK)
        self.assertEqual(got["job"], JOB)
        self.assertEqual(got["helper"], {"kind": "principal:question-reader", "agent_id": "a1",
                                         "launched": "2030-01-02T03:01:00Z",
                                         "started": "2030-01-02T03:01:01Z",
                                         "ended": "2030-01-02T03:09:00Z"})

    def test_the_record_holds_no_word_of_the_reason(self):
        self.finish()
        self.assertNotIn("ends to be served", json.dumps(self.record()))

    def test_a_verdict_that_it_leads_is_recorded_as_such(self):
        self.write_reply("verdict: leads\nreason: Its second sentence states the design.\n"
                         "status: ok\n")
        self.finish()
        self.assertEqual(self.record()["verdict"], "leads")

    def test_a_job_not_done_or_of_another_kind_is_refused(self):
        with self.assertRaisesRegex(lead.Refused, "not done by the coordinator"):
            self.record()
        self.add(kind="seal", jid="s1-b1-2-seal")
        with self.assertRaisesRegex(lead.Refused, "of the kind 'seal'"):
            lead.record(self.question, self.store.load(), "s1-b1-2-seal", self.launches,
                        "principal", CLOCK)
        with self.assertRaisesRegex(lead.Refused, "no job"):
            lead.record(self.question, self.store.load(), "s1-b1-9-lead", self.launches,
                        "principal", CLOCK)

    def test_a_reading_of_another_text_is_refused(self):
        self.finish()
        with open(self.question, "a", encoding="utf-8") as fh:
            fh.write("And one clause more.\n")
        with self.assertRaisesRegex(lead.Refused, "read it again"):
            self.record()

    def test_a_reading_of_another_file_is_refused(self):
        other = os.path.join(self.tmp, "lines", "l1", "2")
        os.makedirs(other)
        with open(os.path.join(other, "question.md"), "w") as fh:
            fh.write("What is a kept record for, and what must it never do?\n")
        self.finish()
        with self.assertRaisesRegex(lead.Refused, "another file"):
            lead.record(os.path.join(other, "question.md"), self.store.load(), JOB,
                        self.launches, "principal", CLOCK)

    def test_a_reply_that_does_not_match_its_fingerprint_is_refused(self):
        self.finish()
        self.write_reply(REPLY.replace("does not lead", "leads"))
        with self.assertRaisesRegex(lead.Refused, "fingerprint"):
            self.record()

    def test_a_reply_out_of_its_three_lines_is_refused(self):
        long = "reason: " + "x" * (lead.REASON + 1)
        for text in ("verdict: does not lead\nstatus: ok\n",
                     "verdict: does not lead\nreason: Fine.\nA better wording: ...\nstatus: ok\n",
                     "verdict: maybe\nreason: Fine.\nstatus: ok\n",
                     "verdict: does not lead\nreason: Fine.\nstatus: failed\n",
                     "verdict: does not lead\nreason:  \nstatus: ok\n",
                     "verdict: does not lead\n%s\nstatus: ok\n" % long,
                     "verdict: does not lead\nreason: Fine.\n"):
            with self.subTest(text=text):
                with self.assertRaises(lead.Refused):
                    lead.reply(text)
        self.assertEqual(lead.reply("verdict: leads\nreason: Its list of choices.\nstatus: ok"),
                         ("leads", "Its list of choices."))

    def test_a_reading_the_hooks_did_not_record_is_refused(self):
        self.finish()
        for rows, words in (([], "recorded no launch"),
                            ([dict(self.launches[0], kind="principal:clean-reader")],
                             "recorded no launch"),
                            ([dict(self.launches[0], description="s1-b1-2-lead")],
                             "recorded no launch"),
                            ([{k: v for k, v in self.launches[0].items() if k != "ended"}],
                             "started and ended"),
                            ([dict(self.launches[0], at="2030-01-02T02:59:00Z")],
                             "after the job was added"),
                            ([dict(self.launches[0], ended="2030-01-02T03:10:01Z")],
                             "before it was marked done")):
            with self.subTest(rows=rows):
                with self.assertRaisesRegex(lead.Refused, words):
                    self.record(launches=rows)

    def test_a_clock_earlier_than_the_mark_of_done_is_refused(self):
        self.finish()
        with self.assertRaisesRegex(lead.Refused, "clock"):
            self.record(clock="2030-01-02T03:09:59Z")

    def test_a_board_that_does_not_verify_is_refused(self):
        self.finish()
        os.unlink(self.store.versions_path)
        with self.assertRaisesRegex(lead.Refused, "not sound"):
            self.record()

    def test_led_records_a_question_found_to_have_led(self):
        got = lead.led(self.question, CLOCK)
        self.assertEqual(got, {"tool": "lead.py led", "sha256": self.qsha(),
                               "verdict": "leads", "found": CLOCK})


class CommandTest(Base):
    """lead.py as the skill runs it, the hooks' record found by the session's id, the
    board's times in the past of the clock it reads."""
    ADDED, CLAIMED, DONE = "2020-01-02T03:00:00Z", "2020-01-02T03:00:30Z", "2020-01-02T03:10:00Z"
    LAUNCHED, STARTED, ENDED = "2020-01-02T03:01:00Z", "2020-01-02T03:01:01Z", \
        "2020-01-02T03:09:00Z"

    def setUp(self):
        super().setUp()
        self.project = os.path.join(self.tmp, "project")
        os.makedirs(os.path.join(self.project, ".principal"))
        with open(os.path.join(self.project, ".principal", "notebook.json"), "w") as fh:
            json.dump({"notebook": "doc1"}, fh)
        self.config = os.path.join(self.tmp, "config")
        self.env = dict(os.environ, CLAUDE_CONFIG_DIR=self.config,
                        CLAUDE_CODE_SESSION_ID=SESSION)
        self.env.pop("CLAUDE_PROJECT_DIR", None)
        where = brief.brief_dir(os.path.realpath(self.project), self.env)
        rows = inhand.session_dir(where, SESSION)
        os.makedirs(rows)
        # the launch is in the past of the clock the tool reads
        self.launches = [dict(self.launches[0])]
        with open(os.path.join(rows, "launches.json"), "w") as fh:
            json.dump(self.launches, fh)
        self.out = os.path.join(self.n, "lead.json")

    def run_tool(self, *argv):
        return subprocess.run([sys.executable, os.path.join(HERE, "lead.py")] + list(argv),
                              cwd=self.project, env=self.env, capture_output=True, text=True)

    def recorded(self):
        return self.run_tool("record", "--question", self.question, "--board", self.store.export,
                             "--versions", self.store.versions_path, "--job", JOB,
                             "-o", self.out)

    def test_record_writes_the_record_the_clean_turn_takes(self):
        self.finish()
        done = self.recorded()
        self.assertEqual(done.returncode, 0, done.stderr)
        with open(self.out, encoding="utf-8") as fh:
            got = json.load(fh)
        self.assertEqual((got["tool"], got["verdict"], got["sha256"]),
                         ("lead.py record", "does not lead", self.qsha()))
        self.assertTrue(board.is_time(got["read"]))

    def test_a_verdict_that_it_leads_exits_2_and_is_recorded(self):
        self.write_reply("verdict: leads\nreason: Its second sentence states the design.\n"
                         "status: ok\n")
        self.finish()
        done = self.recorded()
        self.assertEqual(done.returncode, 2, done.stderr)
        with open(self.out, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["verdict"], "leads")

    def test_a_refusal_leaves_no_record_an_earlier_one_included(self):
        with open(self.out, "w") as fh:
            fh.write("{}")
        done = self.recorded()
        self.assertEqual(done.returncode, 1)
        self.assertIn("REFUSED:", done.stderr)
        self.assertFalse(os.path.exists(self.out))

    def test_no_session_s_id_is_refused(self):
        self.finish()
        self.env.pop("CLAUDE_CODE_SESSION_ID")
        done = self.recorded()
        self.assertEqual(done.returncode, 1)
        self.assertIn("session's id", done.stderr)

    def test_led_writes_a_record_that_withholds(self):
        done = self.run_tool("led", "--question", self.question, "-o", self.out)
        self.assertEqual(done.returncode, 0, done.stderr)
        with open(self.out, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["verdict"], "leads")


class PacketTest(unittest.TestCase):
    """packet.py carries no draw of a question found to have led."""

    def setUp(self):
        import packet
        self.packet = packet
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.line = tmp.name
        for n, (q, a) in enumerate((("What is it for?\n", "It is for keeping."),
                                    ("How is it kept?\n", "By hand.")), 1):
            where = os.path.join(self.line, str(n))
            os.makedirs(os.path.join(where, "draws"))
            with open(os.path.join(where, "question.md"), "w", encoding="utf-8") as fh:
                fh.write(q)
            qsha = sha(q.encode("utf-8"))
            with open(os.path.join(where, "draws", "draw-1.json"), "w") as fh:
                json.dump({"kind": "answerer", "answer": a,
                           "answer_sha256": sha(a.encode("utf-8")), "question_sha256": qsha}, fh)
            with open(os.path.join(where, "draws", "manifest.json"), "w") as fh:
                json.dump({"kind": "answerer", "question_sha256": qsha,
                           "draws": [{"index": 1, "file": "draw-1.json"}]}, fh)

    def reading(self, n, verdict):
        with open(os.path.join(self.line, str(n), "lead.json"), "w") as fh:
            json.dump({"tool": "lead.py record", "verdict": verdict}, fh)

    def test_a_line_with_no_reading_is_carried_as_before(self):
        pairs, _ = self.packet.line(self.line)
        self.assertEqual(len(pairs), 2)

    def test_a_reading_that_it_does_not_lead_is_carried(self):
        self.reading(1, "does not lead")
        pairs, _ = self.packet.line(self.line)
        self.assertEqual(len(pairs), 2)

    def test_a_question_found_to_have_led_is_not_carried(self):
        for verdict in ("leads", None, "Does not lead"):
            with self.subTest(verdict=verdict):
                self.reading(2, verdict)
                with self.assertRaisesRegex(self.packet.Refused,
                                            "question 2 of the line was found to lead"):
                    self.packet.line(self.line)

    def test_a_reading_that_cannot_be_read_is_refused(self):
        with open(os.path.join(self.line, "1", "lead.json"), "w") as fh:
            fh.write("not json")
        with self.assertRaises(self.packet.Refused):
            self.packet.line(self.line)


if __name__ == "__main__":
    unittest.main()
