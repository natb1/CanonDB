"""The sitting as its commands run.

Every line the skill and the coordinator's and the checker's definitions
give is extracted from the files, its placeholders filled, and run by the
shell as written: the coordinator's and the checker's first through the
plugin's shell gate, as those kinds, and only on no opinion. They run
against an invented store (a batch applied all or nothing, each write
pinned), an invented fetcher transcript, and views of the fixture graph. A
placeholder left unfilled fails the test, and the store is exported only
where the skill says to export it. Then the sentences that hold what no
tool decides.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

import test_cli
import test_inplace
import test_views
from hypo import page, render
from support import load
from test_board import read_batch

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
SKILL = os.path.join(ROOT, "skills", "sit", "SKILL.md")
COORDINATOR = os.path.join(ROOT, "agents", "coordinator.md")
CHECKER = os.path.join(ROOT, "agents", "checker.md")
GATE = os.path.join(ROOT, "hooks", "kind-bash-gate.py")
TOOLS = os.path.join(ROOT, "tools")

T = "2030-01-02T03:04:05Z"
LATER = "2030-01-03T03:04:05Z"
DOC = "p1"
#: what is left of a placeholder once a line is filled
UNFILLED = re.compile(r"<[^<>]*>|\[ID\]|\$SCRATCH|(?<![\w./-])(?:READ|ID|N|T)(?![\w./-])")


def flat(path):
    with open(path, encoding="utf-8") as fh:
        return " ".join(fh.read().split())


def spans(path):
    """Every code span of a file, in its order, its code blocks left out."""
    with open(path, encoding="utf-8") as fh:
        text = re.sub(r"```.*?```", "", fh.read(), flags=re.S)
    return re.findall(r"`([^`]+)`", " ".join(text.split()))


def lines(path, program):
    """Every code span of a file that runs ``program`` with words after it,
    in the file's order: a tool by `tools/<name>` or `<tools>/<name>`, a
    plain program by its name."""
    out = []
    for span in spans(path):
        word = span.split(" ", 1)[0]
        if " " in span and (word == program or word in ("tools/" + program,
                                                         "<tools>/" + program)):
            out.append(span)
    return out


def line(path, program, *first):
    """The first line of ``program`` whose words after it open with ``first``."""
    found = [s for s in lines(path, program) if s.split()[1:1 + len(first)] == list(first)]
    if not found:
        raise AssertionError("no line of %s %s in %s" % (program, " ".join(first), path))
    return found[0]


class Store:
    """A board's store: documents with versions, a batch applied all or
    nothing, each pinned write checked, and an export to a party's own
    directory."""

    def __init__(self):
        self.docs, self.versions = {}, {}

    def send(self, batch_path):
        writes = read_batch(batch_path)
        for w in writes:
            key = "%s/%s" % (w["collection"], w["doc_id"])
            if "if_version" in w and self.versions.get(key) != w["if_version"]:
                return "CONFLICT %s" % key
            if "if_version" not in w and key in self.versions:
                return "CONFLICT %s exists" % key
        for w in writes:
            key = "%s/%s" % (w["collection"], w["doc_id"])
            self.docs[key] = w["data"]
            self.versions[key] = self.versions.get(key, 0) + 1
        return "ok"

    def export(self, board, versions):
        shutil.rmtree(board, ignore_errors=True)
        os.makedirs(board)
        for key, doc in self.docs.items():
            coll, doc_id = key.split("/")
            os.makedirs(os.path.join(board, coll), exist_ok=True)
            with open(os.path.join(board, coll, doc_id + ".json"), "w") as fh:
                json.dump(doc, fh)
        with open(versions, "w") as fh:
            json.dump(self.versions, fh)


def labelled(xml, graph):
    """A view whose chips are labelled with the tab names they name, as the
    document labels them."""
    names = {render.chip_key(q.id)[2:]: q.id for q in graph.questions}
    return re.sub(r'label="([^"]*)"',
                  lambda m: 'label="%s"' % names.get(m.group(1), m.group(1)), xml)


class Walk(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)
        self.project = os.path.join(self.base, "project")
        self.home = os.path.join(self.base, "home")
        # a job's scratch, a root the gates recognise
        self.scratch = os.path.join(self.home, ".claude", "jobs", "0f82a3c4", "tmp", "s")
        for d in (self.project, self.scratch):
            os.makedirs(d)
        self.env = {k: v for k, v in os.environ.items()
                    if k not in ("CLAUDE_PROJECT_DIR", "CLAUDE_PLUGIN_ROOT")}
        self.env["HOME"] = self.home
        self.store = Store()
        self.graph = load()

    # -- a line as written -------------------------------------------------

    def fill(self, text, values=None):
        text = text.replace("$SCRATCH", self.scratch).replace("<tools>/", TOOLS + "/")
        if text.startswith("tools/"):
            text = TOOLS + text[len("tools"):]
        for key, value in (values or {}).items():
            text = text.replace(key, value)
        left = UNFILLED.search(text)
        self.assertIsNone(left, "a placeholder left unfilled: %r in %s" % (
            left and left.group(0), text))
        return text

    def gate(self, kind, command):
        call = {"agent_type": "principal:" + kind, "cwd": self.project, "tool_name": "Bash",
                "tool_input": {"command": command}}
        done = subprocess.run([sys.executable, "-B", GATE], input=json.dumps(call).encode(),
                              capture_output=True, env=self.env, timeout=60)
        self.assertEqual(json.loads(done.stdout), {}, (kind, command))

    def sh(self, text, values=None, kind=None, code=0):
        command = self.fill(text, values)
        if kind:
            self.gate(kind, command)
        done = subprocess.run(["bash", "-c", command], cwd=self.project, capture_output=True,
                              text=True, env=self.env, timeout=120)
        if code is not None:
            self.assertEqual(done.returncode, code, (command, done.stdout, done.stderr))
        return done

    def export(self, party):
        self.store.export(os.path.join(self.scratch, party, "board"),
                          os.path.join(self.scratch, party, "versions.json"))

    def send(self, party):
        """The batch sent, and the board exported again, as the skill says
        before the next mode."""
        self.assertEqual(self.store.send(os.path.join(self.scratch, party, "out",
                                                      "batch.json")), "ok")
        self.export(party)

    def job(self, jid):
        return self.store.docs["jobs/" + jid]

    # -- the speaker's lines -----------------------------------------------

    def speak(self, mode, jid=None, time=T, **more):
        values = {"<id>": jid or "", "<time>": time, "<this sitting's id>": "s2",
                  "<the notebook's address>": "doc:abc"}
        values.update(more)
        return self.sh(line(SKILL, "board.py", mode), values)

    def begin(self):
        """Step 1 on a board not yet begun: the export finds none, the
        directory is made and `{}` written as the versions, `init`, sent,
        and exported again."""
        self.export("speaker")
        with open(os.path.join(self.scratch, "speaker", "versions.json")) as fh:
            self.assertEqual(json.load(fh), {})
        self.speak("init")
        self.send("speaker")

    def add(self, jobs):
        path = os.path.join(self.scratch, "jobs-%d.json" % len(self.store.docs))
        with open(path, "w") as fh:
            json.dump(jobs, fh)
        self.speak("add", **{"<file>": path})
        self.send("speaker")

    # -- the coordinator's lines -------------------------------------------

    def coordinate(self, mode, jid=None, reason="helper"):
        values = {"<job id>": jid or "", "<time>": T, "<reason>": reason}
        return self.sh(line(COORDINATOR, "board.py", mode), values, kind="coordinator")

    def claim(self, jid):
        """Steps 1 and 2: export, `next`, `claim`, send, export again, and
        go on only where the job stands claimed by the coordinator."""
        self.export("coordinator")
        self.assertIn(jid, self.coordinate("next").stdout)
        self.coordinate("claim", jid)
        self.send("coordinator")
        self.assertEqual(self.job(jid)["state"], "claimed")
        self.assertEqual(self.job(jid)["claimed_by"], "coordinator")

    def reply(self, jid, text, **result):
        """Step 4: the reply written whole, its fingerprint by the line the
        definition gives, and the result file beside it."""
        mine = os.path.join(self.scratch, "coordinator")
        os.makedirs(os.path.join(mine, "replies"), exist_ok=True)
        os.makedirs(os.path.join(mine, "results"), exist_ok=True)
        path = os.path.join(mine, "replies", jid)
        with open(path, "w") as fh:
            fh.write(text)
        done = self.sh(line(COORDINATOR, "sha256sum"), {"<job id>": jid}, kind="coordinator")
        fingerprint = done.stdout.split()[0]
        with open(path, "rb") as fh:
            self.assertEqual(fingerprint, hashlib.sha256(fh.read()).hexdigest())
        with open(os.path.join(mine, "results", jid + ".json"), "w") as fh:
            json.dump(dict(reply=path, fingerprint=fingerprint, **result), fh)
        return text.rstrip("\n").rsplit("\n", 1)[-1]

    def transcript(self, tabs, broken=False):
        """A fetcher's transcript where the harness keeps one: the document's
        tab list read by its bare id, then a whole view of each tab."""
        where = os.path.join(self.base, "fixture-%d" % len(os.listdir(self.base)))
        os.makedirs(where)
        with open(test_cli.document(where)[0], encoding="utf-8") as fh:
            manifest = json.load(fh)
        out = [test_views.call("c0", {"object": "project", "id": DOC}, {}),
               test_views.result("c0", json.dumps({"verdict": "allow", "rev": 2,
                                                   "data": manifest}))]
        for n, qid in enumerate(tabs, 1):
            xml = labelled(test_inplace.view_of(self.graph, qid)[0], self.graph)
            if broken and qid == tabs[-1]:
                xml = re.sub(r">question: [a-z ]+? ·", ">question: bogus ·", xml, count=1)
            out += test_views.answered("c%d" % n, self.graph.get(qid).body,
                                       {"verdict": "allow", "rev": 6,
                                        "data": {"rev": 6, "xml": xml}},
                                       payload={"kind": "view", "sinceRev": 0})
        path = os.path.join(self.home, ".claude", "projects", "-p", "s2", "subagents",
                            "agent-%d.jsonl" % len(os.listdir(self.base)))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(out) + "\n")
        return path

    def lift(self, jid, transcript):
        """The fetch's lift, by the coordinator's two views.py lines."""
        values = {"<that transcript>": transcript, "<job id>": jid, "<document id>": DOC}
        listed = self.sh(line(COORDINATOR, "views.py", "<that"), values, kind="coordinator")
        self.assertEqual(listed.stdout, "1 saved: doc-%s\n" % DOC)
        doc_line = [s for s in lines(COORDINATOR, "views.py") if "--doc" in s][0]
        return self.sh(doc_line, values, kind="coordinator")

    def fetch(self, jid, tabs, broken=False):
        self.claim(jid)
        saved = self.lift(jid, self.transcript(tabs, broken))
        self.assertEqual(saved.stdout, "%d saved: %s\n" % (len(tabs), " ".join(sorted(tabs))))
        views = os.path.join(self.scratch, "coordinator", "views", jid)
        listed = os.path.join(self.scratch, "coordinator", "lists", jid, "doc-%s.json" % DOC)
        self.assertEqual(self.reply(jid, "read the tabs\nstatus: ok\n", views=views,
                                    list=listed), "status: ok")
        self.coordinate("done", jid)
        self.send("coordinator")
        self.assertEqual(self.job(jid)["state"], "done")
        return views, listed

    def check(self, jid):
        """A check job as the coordinator runs it: the checker's three lines
        from its definition, each through the gate as the checker, run in
        order until one exits other than 0; the status its rule gives."""
        self.claim(jid)
        inputs = self.job(jid)["inputs"]
        values = {"<views>": inputs["views"], "<list>": inputs["list"],
                  "<work>": os.path.join(self.scratch, "check", jid)}
        said, codes = [], []
        for each in lines(CHECKER, "page.py") + lines(CHECKER, "read.py") \
                + lines(CHECKER, "check.py"):
            done = self.sh(each, values, kind="checker", code=None)
            codes.append(done.returncode)
            said.append(done.stdout)
            if done.returncode:
                break
        failed = len(codes) < 3 or any(codes) or any("ERROR" in s for s in said)
        return codes, "status: failed" if failed else "status: ok"


class SpeakerTest(Walk):
    def test_every_board_line_writes_to_the_party_s_own_paths(self):
        for each in lines(SKILL, "board.py"):
            self.assertIn("$SCRATCH/speaker/board", each)
            self.assertIn("--versions $SCRATCH/speaker/versions.json", each)
            if " --out " in each:
                self.assertIn("--out $SCRATCH/speaker/out", each)
        self.assertEqual(len(lines(COORDINATOR, "board.py")), 5)
        for each in lines(COORDINATOR, "board.py") + lines(COORDINATOR, "views.py") \
                + lines(COORDINATOR, "sha256sum"):
            self.assertIn("$SCRATCH/coordinator/", each)

    def test_finding_11_an_empty_board_is_begun_before_status(self):
        text = flat(SKILL)
        self.assertLess(text.index(line(SKILL, "board.py", "init")),
                        text.index(line(SKILL, "board.py", "status")))

    def test_the_speaker_s_own_lines_from_begin_to_close(self):
        """init, status, verify; an earlier sitting's queued chain failed
        superseded; the probe claimed and done with its line doc; a turn
        held with wait and queued again with resume; a quiet claim released."""
        self.begin()
        self.assertEqual(self.speak("verify").returncode, 0)
        self.add([
            {"id": "s1-b2-2-seal", "sitting": "s1", "batch": "b2", "row": "2",
             "kind": "seal", "tier": "full", "inputs": {"question": "/q/questions/2.md"}},
            {"id": "s1-b2-2-grade", "sitting": "s1", "batch": "b2", "row": "2",
             "kind": "grade", "tier": "mid", "waits_on": ["s1-b2-2-seal"]},
            {"id": "s2-open-linedoc-probe", "sitting": "s2", "batch": "open",
             "row": "linedoc", "kind": "probe", "tier": "mid"},
            {"id": "s2-b1-1-turn", "sitting": "s2", "batch": "b1", "row": "1",
             "kind": "turn", "tier": "full", "inputs": {"question": "q7"}},
            {"id": "s2-b1-2-observe", "sitting": "s2", "batch": "b1", "row": "2",
             "kind": "observe", "tier": "mid", "inputs": {"subject": "doc:abc"}},
        ])
        for jid in ("s1-b2-2-grade", "s1-b2-2-seal"):
            self.speak("fail", jid)
            self.send("speaker")
            self.assertEqual(self.job(jid)["reason"], "superseded")
        self.speak("claim", "s2-open-linedoc-probe")
        self.send("speaker")
        result = os.path.join(self.scratch, "speaker", "probe.json")
        with open(result, "w") as fh:
            json.dump({"line_doc": "0123abcd00004000800000000000beef"}, fh)
        self.speak("done", "s2-open-linedoc-probe", **{"<the result file>": result})
        self.send("speaker")
        self.assertEqual(self.job("s2-open-linedoc-probe")["result"]["line_doc"],
                         "0123abcd00004000800000000000beef")
        self.speak("wait", "s2-b1-1-turn")
        self.send("speaker")
        self.assertEqual(self.job("s2-b1-1-turn")["state"], "waiting")
        self.speak("resume", "s2-b1-1-turn")
        self.send("speaker")
        self.assertEqual(self.job("s2-b1-1-turn")["state"], "queued")
        self.speak("claim", "s2-b1-2-observe")
        self.send("speaker")
        self.speak("release", time=LATER, **{"--older-than N": "--older-than 60"})
        self.send("speaker")
        self.assertEqual(self.job("s2-b1-2-observe")["state"], "queued")
        status = self.speak("status")
        self.assertIn("blocked by a failed job: none", status.stdout)
        self.assertEqual(self.speak("verify").returncode, 0)

    def test_a_line_left_unfilled_fails(self):
        with self.assertRaises(AssertionError):
            self.fill(line(SKILL, "board.py", "claim"), {"<time>": T})
        with self.assertRaises(AssertionError):
            self.fill(line(SKILL, "board.py", "release"), {"<time>": T})


class ChainTest(Walk):
    """The chain after a record, by the coordinator's and the checker's own
    lines: the review's B2, a correct scoped page passing its check and a
    broken one failing it, and a failed link queued again by the skill's
    `retry`."""

    def chain(self, broken):
        self.begin()
        fetch, check = "s2-b3-2-fetch", "s2-b3-3-check"
        tabs = os.path.join(self.scratch, "tabs-b3.txt")
        with open(tabs, "w") as fh:
            fh.write("ti-esti\nparty\n")
        self.add([
            {"id": fetch, "sitting": "s2", "batch": "b3", "row": "2", "kind": "fetch",
             "tier": "small", "inputs": {"notebook": "doc:abc", "tabs": tabs}},
            {"id": check, "sitting": "s2", "batch": "b3", "row": "3", "kind": "check",
             "tier": "small", "waits_on": [fetch],
             "inputs": {"views": "%s/coordinator/views/%s" % (self.scratch, fetch),
                        "list": "%s/coordinator/lists/%s/doc-%s.json"
                                % (self.scratch, fetch, DOC)}},
        ])
        self.fetch(fetch, ["party", "ti-esti"], broken=broken)
        return check, self.check(check)

    def test_b2_a_correct_scoped_page_passes_its_check(self):
        check, (codes, status) = self.chain(broken=False)
        self.assertEqual((codes, status), ([0, 0, 0], "status: ok"))
        work = os.path.join(self.scratch, "check", check)
        with open(os.path.join(work, "graph.json")) as fh:
            self.assertEqual(sorted(q["id"] for q in json.load(fh)["questions"]),
                             ["party", "ti-esti"])
        self.assertEqual(self.reply(check, "page.py 0\nread.py 0\ncheck.py 0\n" + status),
                         "status: ok")
        self.coordinate("done", check)
        self.send("coordinator")
        self.assertEqual(self.job(check)["state"], "done")

    def test_b2_a_broken_page_fails_it_and_the_link_is_retried(self):
        check, (codes, status) = self.chain(broken=True)
        self.assertEqual(codes, [0, 0, 1])
        self.assertEqual(status, "status: failed")
        self.reply(check, "check.py 1\n" + status)
        self.coordinate("fail", check)
        self.send("coordinator")
        self.assertEqual((self.job(check)["state"], self.job(check)["reason"]),
                         ("failed", "helper"))
        # the coordinator has reported: the board is exported again before
        # the speaker's next mode, as step 6 says
        self.assertIn("export the board again, as step 1 does, before this session's next "
                      "mode", flat(SKILL))
        self.export("speaker")
        self.speak("retry", check)
        self.send("speaker")
        self.assertEqual(self.job(check)["state"], "queued")


class OpeningTest(Walk):
    """The opening's read over every tab, and a rows file of one note made
    by the skill's own lines."""

    def test_the_opening_and_a_rows_file(self):
        jid = "s2-open-1-fetch"
        every = sorted(q.id for q in self.graph.questions)
        self.lift(jid, self.transcript(every))
        values = {"<job id>": jid, "<document id>": DOC}
        self.sh(line(SKILL, "page.py"), values)
        built = self.sh(line(SKILL, "read.py"), values)
        self.assertIn("%d questions" % len(every), built.stdout)
        self.sh(line(SKILL, "residue.py", "list"))
        self.sh(line(SKILL, "divergence.py", "list"))

        # a note on canon's Thesis, its words printed to a file
        record = "s2-b4-1-record"
        rows = os.path.join(self.scratch, "rows", record)
        os.makedirs(rows)
        read = os.path.join(self.scratch, "coordinator", "views", jid, "canon.json")
        with open(read, encoding="utf-8") as fh:
            blocks = page.blocks(fh.read())
        start = next(i for i, (_, md) in enumerate(blocks) if md == "## Thesis")
        end = next(i for i in range(start + 1, len(blocks)) if blocks[i][1].startswith("## "))
        words = os.path.join(rows, "note.txt")
        with open(words, "w") as fh:
            fh.write("open: w · kind: work · whose: ai · from: f · returns: r\n")
        text = [s for s in spans(SKILL) if s.startswith("--text \"$(cat")][0]
        insert = line(SKILL, "inplace.py", "note", "insert").replace("--text T", text)
        out = os.path.join(rows, "1.json")
        done = self.sh(insert + " > " + out, {"READ": read, "ID": blocks[end - 1][0],
                                               "<that file>": words})
        self.assertIn("on: Thesis", done.stderr)
        values = {"<node id>": self.graph.get("canon").body, "<job id>": record, "<n>": "1",
                  "<every .entry file, named in order>": os.path.join(rows, "1.entry")}
        self.sh(line(SKILL, "jq", "-c"), values)
        self.sh(line(SKILL, "jq", "-s"), values)
        with open(os.path.join(self.scratch, "rows", record + ".json")) as fh:
            made = json.load(fh)
        self.assertEqual(len(made), 1)
        self.assertEqual(made[0]["node"], self.graph.get("canon").body)
        self.assertEqual(made[0]["op_id"], record + "-1")
        self.assertEqual(made[0]["payload"]["ops"][0]["op"], "insert")


class SentenceTest(unittest.TestCase):
    """What no tool decides, said where it is decided."""

    def setUp(self):
        self.skill = flat(SKILL)

    def test_the_coordinator_runs_every_review_and_is_the_only_helper_started(self):
        self.assertIn("The coordinator runs every kind the table gives a helper, every "
                      "`review` among them", self.skill)
        self.assertIn("The coordinator is the only helper this session starts", self.skill)
        self.assertNotIn("a reviewer only for a `review` job it claimed itself", self.skill)
        self.assertIn("One coordinator runs at a time", self.skill)

    def test_the_coordinator_confirms_its_claim_before_a_helper_starts(self):
        self.assertIn("After sending a claim, the coordinator exports the board again and "
                      "starts the helper only where the job stands `claimed` by "
                      "`coordinator`; where it does not, it starts nothing for that job and "
                      "moves on.", self.skill)

    def test_questions_stand_where_the_reader_s_gate_opens(self):
        self.assertIn("`$SCRATCH/questions/<n>.md`", self.skill)
        self.assertIn("`$SCRATCH/answers/<n>.md`", self.skill)

    def test_shares_are_listed_over_the_opening_s_graph_only(self):
        self.assertIn("`residue.py list --by-share` is run over this graph, the opening's "
                      "whole-notebook read, and no other", self.skill)
        self.assertNotIn("over a fresh fetch of what the sitting wrote, and say", self.skill)

    def test_the_line_doc_goes_on_the_board_by_its_bare_id(self):
        self.assertIn("its bare id, the trailing id of its address", self.skill)

    def test_the_tabs_file_is_one_name_a_line(self):
        self.assertIn("a file of tab names, one name a line", self.skill)

    def test_the_rows_file_is_one_entry_a_run(self):
        self.assertIn("one entry per run of a tool, in the order the tools were run", self.skill)
        self.assertIn("`--text \"$(cat <that file>)\"`", self.skill)
        self.assertIn("`jq` must be installed", self.skill)

    def test_minor_10_a_failed_job_s_reply_is_read_by_its_path(self):
        self.assertIn("The speaker reads the failed job's reply, the file "
                      "`$SCRATCH/coordinator/replies/<job id>`, since a failed job carries "
                      "no result", self.skill)
        self.assertNotIn("by the `reply` its result names where there is one", self.skill)

    def test_b2_the_check_says_what_it_covers(self):
        self.assertIn("It does not run `tools/verify.py`", self.skill)
        self.assertIn("**The check after a record is scoped.**", self.skill)
        self.assertIn("It does not run `verify.py`", flat(CHECKER))

    def test_minor_12_what_the_scratch_may_be(self):
        self.assertIn("`$SCRATCH` is an absolute path spelled in letters, digits and "
                      "`_ . + -`", self.skill)
        self.assertIn("No directory on it is named `questions`, `answers`, `replies`, "
                      "`results`, `sealed`, `rows`, `check` or `coordinator`", self.skill)

    def test_the_attenuation_names_what_is_untested_and_left(self):
        for words in ("this is untested", "The guards have a blind spot outside the project",
                      "A reply on disk is the coordinator's copy",
                      "The shell and the files are bound for the helpers, not for the speaker"):
            self.assertIn(words, self.skill)


if __name__ == "__main__":
    unittest.main()
