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
#: a board that holds no job
EMPTY = board.Board(None, {}, {}, [])
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
                             "beyond doubt"),
                            ([dict(self.launches[0], at="2030-01-02T02:59:00Z")],
                             "while it stood on the board"),
                            ([dict(self.launches[0], ended="2030-01-02T03:10:01Z")],
                             "beyond doubt")):
            with self.subTest(rows=rows):
                with self.assertRaisesRegex(lead.Refused, words):
                    self.record(launches=rows)

    def test_a_job_done_by_another_claimant_is_refused(self):
        self.finish()
        path = os.path.join(self.store.export, "jobs", JOB + ".json")
        with open(path) as fh:
            doc = json.load(fh)
        doc["claimed_by"] = "s2"
        with open(path, "w") as fh:
            json.dump(doc, fh)
        with self.assertRaisesRegex(lead.Refused, "not done by the coordinator"):
            self.record()

    # -- B2: a launch tied to its helper by its own call, not by the order of starts

    def test_a_launch_that_never_started_lends_no_row_to_a_later_job(self):
        # h0 was launched for an earlier job and never started; the reader of
        # this job's start was given to h0, the oldest unstarted row of the
        # kind, and its own row h1 stayed bare; the call's return names it
        self.finish()
        stale = {"id": "h0", "kind": "principal:question-reader",
                 "description": "s1-b0-1-lead", "at": "2030-01-02T02:00:00Z",
                 "agent_id": "a1", "started": "2030-01-02T03:01:01Z",
                 "ended": "2030-01-02T03:09:00Z"}
        bare = {"id": "h1", "kind": "principal:question-reader", "description": JOB,
                "at": "2030-01-02T03:01:00Z", "returned": "2030-01-02T03:09:01Z",
                "returned_agent": "a1"}
        got = self.record(launches=[stale, bare])
        self.assertEqual((got["helper"]["agent_id"], got["helper"]["started"]),
                         ("a1", "2030-01-02T03:01:01Z"))
        # with no return to name the helper, the bare row attests nothing
        with self.assertRaisesRegex(lead.Refused, "a new lead job is added"):
            self.record(launches=[stale, {k: v for k, v in bare.items()
                                          if not k.startswith("returned")}])

    def test_two_launches_at_once_whose_starts_crossed(self):
        # B's reader b started first and was given A's row; A's reader a then
        # B's row; each call's return names its own helper
        self.finish()
        a_row = {"id": "h1", "kind": "principal:question-reader", "description": "s1-b1-2-lead",
                 "at": "2030-01-02T03:01:00Z", "agent_id": "b", "started": "2030-01-02T03:01:05Z",
                 "ended": "2030-01-02T03:05:00Z", "returned_agent": "a"}
        b_row = {"id": "h2", "kind": "principal:question-reader", "description": JOB,
                 "at": "2030-01-02T03:01:02Z", "agent_id": "a", "started": "2030-01-02T03:01:06Z",
                 "ended": "2030-01-02T03:06:00Z", "returned_agent": "b"}
        got = self.record(launches=[a_row, b_row])
        self.assertEqual((got["helper"]["agent_id"], got["helper"]["ended"]),
                         ("b", "2030-01-02T03:05:00Z"))
        # without the returns the crossing cannot be read, and nothing is attested
        plain = [{k: v for k, v in r.items() if k != "returned_agent"} for r in (a_row, b_row)]
        with self.assertRaisesRegex(lead.Refused, "beyond doubt"):
            self.record(launches=plain)

    def test_a_returned_helper_that_ended_after_the_mark_of_done_is_refused(self):
        self.finish()
        rows = [dict(self.launches[0], returned_agent="a2"),
                {"id": "h2", "kind": "principal:question-reader", "description": "",
                 "at": "2030-01-02T03:01:00Z", "agent_id": "a2",
                 "started": "2030-01-02T03:01:01Z", "ended": "2030-01-02T03:11:00Z"}]
        with self.assertRaises(lead.Refused):
            self.record(launches=rows)

    def test_a_helper_started_before_its_launch_is_refused(self):
        self.finish()
        rows = [dict(self.launches[0], started="2030-01-02T03:00:59Z")]
        with self.assertRaisesRegex(lead.Refused, "beyond doubt"):
            self.record(launches=rows)
        rows = [dict(self.launches[0], returned_agent="a1", agent_id="a1",
                     started="2030-01-02T03:00:59Z")]
        with self.assertRaisesRegex(lead.Refused, "beyond doubt"):
            self.record(launches=rows)

    def test_a_launch_that_never_started_is_closed_by_failing_its_job(self):
        # no return names the helper; the dead launch h0 of job s1-b0-1 took
        # this reader's start, and stands open until its job is failed
        dead = "s1-b0-1-lead"
        self.add(jid=dead)
        stale = {"id": "h0", "kind": "principal:question-reader", "description": dead,
                 "at": "2030-01-02T03:00:10Z", "agent_id": "a1",
                 "started": "2030-01-02T03:01:01Z", "ended": "2030-01-02T03:09:00Z"}
        bare = {"id": "h1", "kind": "principal:question-reader", "description": JOB,
                "at": "2030-01-02T03:01:00Z"}
        self.store.send(board.claim(self.store.load(), dead, "coordinator",
                                    "2030-01-02T03:00:05Z"))
        self.finish()
        with self.assertRaisesRegex(lead.Refused, "closed by failing its job"):
            self.record(launches=[stale, bare])
        self.store.send(board.fail(self.store.load(), dead, "coordinator", "refused",
                                   "2030-01-02T03:00:20Z"))
        got = self.record(launches=[stale, bare])
        self.assertEqual(got["helper"]["agent_id"], "a1")
        # a closed row that fits for two launches at once attests neither
        other = dict(stale, id="h2", agent_id="a2")
        with self.assertRaises(lead.Refused):
            self.record(launches=[stale, other, bare])

    # -- B1 and the bound on readings

    def test_a_led_record_is_final_and_one_text_is_read_once(self):
        self.finish()
        out = os.path.join(self.n, "lead.json")
        lead.write(out, lead.led(self.question, CLOCK))
        with self.assertRaisesRegex(lead.Refused, "final for that number"):
            self.record()
        lead.write(out, {"tool": "lead.py record", "sha256": self.qsha(),
                         "verdict": "does not lead"})
        with self.assertRaisesRegex(lead.Refused, "read already"):
            self.record()
        with self.assertRaisesRegex(lead.Refused, "read already"):
            lead.job(self.question, "s1-b1-3-lead", "doc1", self.store.load())

    def test_a_job_prints_the_jobs_file_of_one_reading(self):
        # the text is on the board already, in the job setUp added
        with self.assertRaisesRegex(lead.Refused, "on the board already, in the lead job"):
            lead.job(self.question, "s1-b2-4-lead", "doc1", self.store.load())
        got = lead.job(self.question, "s1-b2-4-lead", "doc1", EMPTY)
        self.assertEqual(got, [{"id": "s1-b2-4-lead", "sitting": "s1", "batch": "b2",
                                "row": "4", "kind": "lead", "tier": "full", "waits_on": [],
                                "inputs": {"notebook": "doc1",
                                           "question": os.path.abspath(self.question),
                                           "question_fingerprint": self.qsha()}}])
        self.assertEqual(board.given_problems(got[0], "job"), [])
        for jid in ("s1-b2-4-seal", "nope"):
            with self.assertRaises(lead.Refused):
                lead.job(self.question, jid, "doc1", EMPTY)
        with self.assertRaisesRegex(lead.Refused, "question.md on a line"):
            lead.job(self.reply, "s1-b2-4-lead", "doc1", EMPTY)

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

    def test_a_refusal_leaves_the_record_that_stood(self):
        # B1: a withholding is never removed by a refused record
        done = self.run_tool("led", "--question", self.question, "-o", self.out)
        self.assertEqual(done.returncode, 0, done.stderr)
        with open(self.out, "rb") as fh:
            before = fh.read()
        for job in ("nope", JOB):
            done = self.run_tool("record", "--question", self.question, "--board",
                                 self.store.export, "--versions", self.store.versions_path,
                                 "--job", job, "-o", self.out)
            self.assertEqual(done.returncode, 1)
            self.assertIn("REFUSED:", done.stderr)
            with open(self.out, "rb") as fh:
                self.assertEqual(fh.read(), before)
        self.finish()
        done = self.recorded()
        self.assertEqual(done.returncode, 1)
        self.assertIn("final for that number", done.stderr)
        with open(self.out, "rb") as fh:
            self.assertEqual(fh.read(), before)
        self.assertEqual([n for n in os.listdir(self.n) if n.endswith(".tmp")], [])

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
        with open(os.path.join(self.line, str(n), "question.md"), "rb") as fh:
            qsha = sha(fh.read())
        with open(os.path.join(self.line, str(n), "lead.json"), "w") as fh:
            json.dump({"tool": "lead.py record", "verdict": verdict, "sha256": qsha}, fh)

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

    def test_a_question_put_on_a_reading_whose_record_is_gone_is_not_carried(self):
        manifest = os.path.join(self.line, "1", "draws", "manifest.json")
        with open(manifest) as fh:
            doc = json.load(fh)
        doc["origin"] = {"approval_sha256": "0" * 64, "lead_sha256": "1" * 64,
                         "read": "2030-01-02T03:00:00Z"}
        with open(manifest, "w") as fh:
            json.dump(doc, fh)
        with self.assertRaisesRegex(self.packet.Refused, "whose record is gone"):
            self.packet.line(self.line)
        self.reading(1, "does not lead")
        self.assertEqual(len(self.packet.line(self.line)[0]), 2)


class AsideTest(PacketTest):
    """B3: a question led mid-line cuts the line there; it and every later
    question, and the drawer turns that carried them, are set aside together."""

    def setUp(self):
        super().setUp()
        where = os.path.join(self.line, "3")
        os.makedirs(where)
        with open(os.path.join(where, "question.md"), "w") as fh:
            fh.write("Not yet answered?\n")
        for name, carried in (("drawn-1", [{"n": 1}]), ("drawn-2", [{"n": 1}, {"n": 2}])):
            os.makedirs(os.path.join(self.line, name))
            with open(os.path.join(self.line, name, "packet.md"), "w") as fh:
                fh.write("x")
            with open(os.path.join(self.line, name, "packet.md.fingerprint.json"), "w") as fh:
                json.dump({"tool": "packet.py", "line": carried}, fh)
        with open(os.path.join(self.line, "2", "place.json"), "w") as fh:
            fh.write("{}")

    def test_the_led_question_and_all_after_it_are_set_aside_and_the_line_reads_on(self):
        with self.assertRaisesRegex(lead.Refused, "not recorded as leading"):
            lead.aside(self.line, "2")
        self.reading(2, "leads")
        got = lead.aside(self.line, "2")
        self.assertEqual(got["held"], os.path.join(self.line, "held", "1"))
        self.assertEqual((got["questions"], got["drawn"], got["placed"], got["led_drafts"]),
                         ([2, 3], ["drawn-2"], [2], 1))
        self.assertEqual(sorted(os.listdir(os.path.join(self.line, "held", "1"))),
                         ["2", "3", "drawn-2"])
        self.assertTrue(os.path.isdir(os.path.join(self.line, "drawn-1")))
        pairs, _ = self.packet.line(self.line)
        self.assertEqual(len(pairs), 1)
        # a new draft at 2: the bound counts the drafts set aside as leading
        os.makedirs(os.path.join(self.line, "2"))
        for k in (2, 3):
            with open(os.path.join(self.line, "2", "question.md"), "w") as fh:
                fh.write("Draft %d?\n" % k)
            self.assertEqual(lead.job(os.path.join(self.line, "2", "question.md"),
                                      "s1-b1-%d-lead" % k, "doc1", EMPTY)[0]["kind"], "lead")
            self.reading(2, "leads")
            self.assertEqual(lead.aside(self.line, "2")["led_drafts"], k)
            os.makedirs(os.path.join(self.line, "2"))
        with open(os.path.join(self.line, "2", "question.md"), "w") as fh:
            fh.write("Draft 4?\n")
        with self.assertRaisesRegex(lead.Refused, "could not be drafted without leading"):
            lead.job(os.path.join(self.line, "2", "question.md"), "s1-b1-4-lead", "doc1", EMPTY)

    def test_a_text_set_aside_is_not_read_again(self):
        self.reading(2, "leads")
        with open(os.path.join(self.line, "2", "lead.json"), "w") as fh:
            json.dump({"tool": "lead.py led", "verdict": "leads",
                       "sha256": sha(b"How is it kept?\n")}, fh)
        lead.aside(self.line, "2")
        os.makedirs(os.path.join(self.line, "2"))
        with open(os.path.join(self.line, "2", "question.md"), "w") as fh:
            fh.write("How is it kept?\n")
        with self.assertRaisesRegex(lead.Refused, "set aside"):
            lead.job(os.path.join(self.line, "2", "question.md"), "s1-b1-5-lead", "doc1", EMPTY)

    def test_the_command_prints_what_it_set_aside(self):
        self.reading(2, "leads")
        done = subprocess.run([sys.executable, os.path.join(HERE, "lead.py"), "aside",
                               "--line", self.line, "--from", "2"],
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("question(s) 2, 3; drawer turn(s) drawn-2", done.stdout)
        self.assertIn("open note of kind change: question(s) 2", done.stdout)
        self.assertIn("1 of 3 drafts of question 2", done.stdout)


class ReturnTest(unittest.TestCase):
    """The hooks tie a launch to the helper it ran by the Agent call's own return."""

    def test_the_helper_s_id_is_read_from_the_result(self):
        for response, want in (({"agentId": "ab12cd"}, "ab12cd"),
                               ({"agent_id": "ab12cd"}, "ab12cd"),
                               ({"content": [{"type": "text", "text": "done\nagentId: ab12cd "
                                              "(for resuming)"}]}, "ab12cd"),
                               ("agentId: ab12cd", "ab12cd"),
                               ({"content": "nothing"}, None), (None, None)):
            with self.subTest(response=response):
                self.assertEqual(inhand.agent_of(response), want)

    def test_the_newest_launch_of_its_kind_and_description_is_marked_returned(self):
        with tempfile.TemporaryDirectory() as where:
            for at in ("2030-01-02T03:00:00Z", "2030-01-02T03:01:00Z"):
                inhand.launched(where, SESSION, "principal:question-reader", JOB, at)
            inhand.launched(where, SESSION, "principal:question-reader", "s1-b1-2-lead",
                            "2030-01-02T03:02:00Z")
            inhand.returned(where, SESSION, "principal:question-reader", JOB, "x1",
                            "2030-01-02T03:05:00Z")
            rows = inhand.launches(where, SESSION)
            self.assertEqual([r.get("returned_agent") for r in rows], [None, "x1", None])
            inhand.returned(where, SESSION, "principal:question-reader", JOB, None,
                            "2030-01-02T03:06:00Z")
            rows = inhand.launches(where, SESSION)
            self.assertEqual([bool(r.get("returned")) for r in rows], [True, True, False])

    def test_the_hook_records_the_return(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "inhand_log", os.path.join(os.path.dirname(HERE), "hooks", "inhand-log.py"))
        hook = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(hook)
        with tempfile.TemporaryDirectory() as tmp:
            project = os.path.join(tmp, "p")
            os.makedirs(os.path.join(project, ".principal"))
            with open(os.path.join(project, ".principal", "notebook.json"), "w") as fh:
                json.dump({}, fh)
            env = {"CLAUDE_CONFIG_DIR": os.path.join(tmp, "c"), "HOME": tmp}
            base = {"session_id": SESSION, "cwd": project, "tool_name": "Agent",
                    "tool_input": {"subagent_type": "principal:question-reader",
                                   "description": JOB}}
            self.assertTrue(hook.record(dict(base, hook_event_name="PreToolUse"), env))
            self.assertTrue(hook.record(dict(base, hook_event_name="PostToolUse",
                                             tool_response={"agentId": "q9q9"}), env))
            where = brief.brief_dir(os.path.realpath(project), env)
            rows = inhand.launches(where, SESSION)
            self.assertEqual(rows[0]["returned_agent"], "q9q9")
        with open(os.path.join(os.path.dirname(HERE), "hooks", "hooks.json")) as fh:
            post = json.load(fh)["hooks"]["PostToolUse"]
        self.assertIn({"matcher": "Agent|Task", "hooks": [{
            "type": "command", "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/inhand-log.py\"",
            "timeout": 30}]}, post)


class BoardReadingTest(Base):
    """N2: the readings the board holds count, not only the records written."""

    def other_text(self, words):
        with open(self.question, "w", encoding="utf-8") as fh:
            fh.write(words)

    def test_a_second_job_for_a_text_on_the_board_is_refused_until_it_failed(self):
        for _ in range(2):
            with self.assertRaisesRegex(lead.Refused, "on the board already"):
                lead.job(self.question, "s1-b1-5-lead", "doc1", self.store.load())
        self.store.send(board.claim(self.store.load(), JOB, "coordinator", self.CLAIMED))
        self.store.send(board.fail(self.store.load(), JOB, "coordinator", "timeout", self.DONE))
        self.assertEqual(lead.job(self.question, "s1-b1-5-lead", "doc1",
                                  self.store.load())[0]["id"], "s1-b1-5-lead")

    def test_a_reply_that_leads_bars_its_text_though_never_recorded(self):
        self.write_reply("verdict: leads\nreason: Its second sentence states the design.\n"
                         "status: ok\n")
        self.finish()
        with self.assertRaisesRegex(lead.Refused, "on the board already"):
            lead.job(self.question, "s1-b1-5-lead", "doc1", self.store.load())

    def test_a_clear_reply_not_recorded_may_be_read_again(self):
        self.finish()
        lead.job(self.question, "s1-b1-5-lead", "doc1", self.store.load())

    def test_the_drafts_on_the_board_count_toward_the_bound(self):
        for k in (2, 3, 4):
            self.other_text("Draft %d?\n" % k)
            self.add(jid="s1-b1-%d-lead" % k)
        self.other_text("Draft 5?\n")
        with self.assertRaisesRegex(lead.Refused, "could not be drafted without leading"):
            lead.job(self.question, "s1-b1-6-lead", "doc1", self.store.load())

    def test_record_refuses_where_another_job_read_the_text(self):
        self.add(jid="s1-b1-2-lead")
        self.finish()
        with self.assertRaisesRegex(lead.Refused, "s1-b1-2-lead"):
            self.record()


class CarryTest(PacketTest):
    """N1: a question set aside only for standing after a led one, read as not
    leading, is put again in its own words, its reading carried over."""

    def test_the_reading_of_an_innocent_later_question_is_carried_over(self):
        self.reading(1, "leads")
        self.reading(2, "does not lead")
        lead.aside(self.line, "1")
        for n, words in ((1, "A new first question?\n"), (2, "How is it kept?\n")):
            os.makedirs(os.path.join(self.line, str(n)))
            with open(os.path.join(self.line, str(n), "question.md"), "w") as fh:
                fh.write(words)
        # the old question 2, set aside only for standing after 1, is carried
        later = os.path.join(self.line, "2", "question.md")
        with self.assertRaisesRegex(lead.Refused, "carried over"):
            lead.job(later, "s1-b1-7-lead", "doc1", EMPTY)
        got = lead.carry(later)
        self.assertEqual((got["verdict"], got["sha256"]),
                         ("does not lead", sha(b"How is it kept?\n")))
        self.assertTrue(got["carried_from"].endswith(os.path.join("held", "1", "2",
                                                                  "lead.json")))
        lead.write(os.path.join(self.line, "2", "lead.json"), got)
        with self.assertRaises(lead.Refused):
            lead.carry(later)
        with self.assertRaisesRegex(lead.Refused, "read already"):
            lead.job(later, "s1-b1-7-lead", "doc1", EMPTY)
        # the led one is not carried, and is refused in its own words
        first = os.path.join(self.line, "1", "question.md")
        with open(first, "w") as fh:
            fh.write("What is it for?\n")
        with self.assertRaisesRegex(lead.Refused, "no reading set aside"):
            lead.carry(first)
        with self.assertRaisesRegex(lead.Refused, "read as leading and set aside"):
            lead.job(first, "s1-b1-8-lead", "doc1", EMPTY)


if __name__ == "__main__":
    unittest.main()
