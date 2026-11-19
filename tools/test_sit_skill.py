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
PAGE = os.path.join(ROOT, "web", "ordo.html")
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

    def test_the_goal_stands_in_its_two_sentences(self):
        self.assertIn("The sitting's goal is to make the distance between what the principal's "
                      "principles ask and what the principal does as small as it can be, "
                      "weighted by the share each principle carries. The goal is only the thing "
                      "being optimized and constrains no mechanism.", self.skill)
        goal = self.skill[self.skill.index("## The goal"):self.skill.index("## Before anything")]
        for words in ("is mechanism, and may change",
                      "a prediction of the principal that fails",
                      "an override or a deferral of the action ranked first",
                      "an action or a sitting not taken up",
                      "Each is an observation and never a verdict",
                      "or to a stated reason why none is owed",
                      "Counts are mechanism and are never part of the goal"):
            self.assertIn(words, goal)

    def test_the_round_s_rules_each_have_their_key_sentence(self):
        round_ = self.skill[self.skill.index("**3 — One action at a time: the round.**"):
                            self.skill.index("**4 — The batch point.**")]
        for words in (
                "1. **One question at a time, put as one concrete case.**",
                "Nothing accompanies it: no recommendation, no tradition on the question being "
                "put, no list of what is sealed, no line telling the principal how to answer.",
                "The tradition on the last answer, already given, stands in the action context "
                "above it (rule 4): it is on that answer, never on the question now put.",
                "The aporia the line is pursuing, with what each possible answer will be tested "
                "against, is sealed by the speaker in a file of its own",
                "Seals exist mechanically and are not listed to the principal.",
                "3. **The question's file holds no answer.**",
                "nothing of the sitting: no answer and no admission of the principal's",
                "restated and never word for word",
                "the prediction is that the principal declines to pick and says what is missing",
                "First the answer as the speaker read it, a restatement and never word for word; "
                "then tradition for and against the answer that was given",
                "what was predicted, where the result diverged, and how or whether that gap is "
                "addressed",
                "unrevised when the next answer comes, it stands",
                "Tradition readings go to the notebook only with the principal's approval.",
                "5. **The principal may always override the action ranked first**",
                "An override is an observation of a gap, never a verdict",
                "the page keeps showing the deferred action beside the revised one",
                "it is carried in every whole-document `set` of `ordo/current` until it is done "
                "or the principal drops it",
                "6. **The next action is one of four kinds: question, office, work, review.**",
                "a review is put exactly as a question is",
                "a review of mechanism may carry the speaker's recommendation, and a review that "
                "states or changes a principle, a grant or a row stating a principle among them, "
                "is put with no recommendation, as a question is",
                "a prediction is sealed before every review as well, by the speaker itself",
                "the file says who predicted",
                "There are no checklists.",
                "7. **Bells.**",
                "only then does the speaker's own next action show",
                "an item may be taken up",
                "among a bell's unresolved items the page shows a taken one first, else the first "
                "open one",
                "A `work` action has no mark: it stays `next` in `ordo/current` until the speaker "
                "changes it on the principal's word.",
                "The page always shows the next bell",
                "The page writes nothing",
                "an overruled office item is an observation like any other override",
                "8. **Every time the speaker stamps is read from the clock, never typed**",
                "9. **The speaker, at the full tier, writes no code, page or tooling itself.**",
                "the judge is never the tier judged",
                "10. **Every ask of the principal is an action on the page, in order.**",
                "The speaker never leaves an ask only in the session's text"):
            self.assertIn(words, round_)
        self.assertNotIn("Put the question, with the four parts of the step", self.skill)
        self.assertNotIn("marks it as given", self.skill)

    def test_round_two_the_count_the_brief_s_ask_and_no_speaker_write(self):
        """Round two: S2, S4, S12."""
        self.assertIn("Only a question of principle is counted", self.skill)
        self.assertIn("An office item, a review and a work action are not counted.", self.skill)
        self.assertNotIn("Every action put is counted as a question", self.skill)
        self.assertIn("put on the page as the sitting's first action, a `review`, like any other",
                      self.skill)
        self.assertIn("The speaker never writes the notebook. Never work around a refusal.",
                      self.skill)
        self.assertNotIn("gives the word for the speaker to send that write itself", self.skill)

    def test_two_ways_to_start_and_what_holds_in_the_open_one(self):
        before = self.skill[self.skill.index("## Before anything"):
                            self.skill.index("## Ground rules")]
        for words in ("**The confined way.**", "**The open way.**",
                      "the gates still bind every helper by its kind",
                      "a helper that is no kind of this plugin is refused any write aimed at the "
                      "notebook",
                      "nothing but this text keeps the speaker itself off the notebook"):
            self.assertIn(words, before)
        self.assertNotIn("stops here, and tells the principal the command of ground rule 1",
                         self.skill)
        self.assertIn("**In the open way this text alone keeps the speaker off the notebook.**",
                      self.skill)
        self.assertIn("**A recorder's write may be refused by a permission check.**", self.skill)
        self.assertIn("Never work around a refusal.", self.skill)

    def test_the_departures_list_the_reversals(self):
        departs = self.skill[self.skill.index("## Where this entry point departs"):]
        for words in ("An ordinary session may run a sitting, the open way",
                      "A question is put alone, where before",
                      "Every ask of the principal is an action on the page"):
            self.assertIn(words, departs)

    def test_the_attenuation_names_what_is_untested_and_left(self):
        for words in ("this is untested", "The guards have a blind spot outside the project",
                      "A reply on disk is the coordinator's copy",
                      "The shell and the files are bound for the helpers, not for the speaker"):
            self.assertIn(words, self.skill)


class PageTest(unittest.TestCase):
    """The page the round is put on, read as text, and the contract the skill
    gives for its three documents."""

    @classmethod
    def setUpClass(cls):
        with open(PAGE, encoding="utf-8") as fh:
            cls.page = fh.read()
        cls.script = cls.page[cls.page.index("<script>"):cls.page.index("</script>")]
        text = flat(SKILL)
        cls.contract = text[text.index("## The page"):text.index("## Procedure")]

    def test_it_loads_no_script_from_another_host(self):
        for tag in re.findall(r"<script\b[^>]*>", self.page):
            self.assertNotIn("src=", tag)
        self.assertEqual(self.page.count("<script"), 1)

    def test_it_writes_nothing_and_takes_no_input(self):
        verbs = r"(?:set|update|delete|add|batch|remove|put|write|commit)"
        # a write in any spelling: a call, a subscript in any quoting, a verb held in a string
        self.assertIsNone(re.search(r"\.\s*%s\s*\(" % verbs, self.script))
        self.assertIsNone(re.search(r"\[\s*[\"'`]\s*%s\s*[\"'`]\s*\]" % verbs, self.script))
        self.assertIsNone(re.search(r"[\"'`]%s[\"'`]" % verbs, self.script))
        # the store is read only through db.doc(<path>).onSnapshot(
        self.assertIsNone(re.search(r"\bdb\s*(?:\[|\.\s*(?!doc\())", self.script))
        self.assertIsNone(re.search(r"[=(,:]\s*db\s*[;,)}]", self.script))
        docs = [m.end() for m in re.finditer(r"\bdb\.doc\(", self.script)]
        self.assertEqual(len(docs), 3)
        for at in docs:
            close = self.script.index(")", at)
            self.assertTrue(self.script[close + 1:].startswith(".onSnapshot("),
                            self.script[at - 7:close + 14])
        # nothing goes out
        for word in ("fetch", "XMLHttpRequest", "sendBeacon", "WebSocket", "EventSource",
                     "postMessage", "import(", "window.open", "location", "localStorage",
                     "sessionStorage", "indexedDB", "document.cookie", "eval", "Function("):
            self.assertNotIn(word, self.script)
        # no control, made in the source or at run time, in any quoting or case
        controls = r"(?:button|input|textarea|select|form|option|details|dialog|a)"
        self.assertIsNone(re.search(r"<\s*%s\b" % controls, self.page, re.I))
        self.assertIsNone(re.search(r"[\"'`]\s*%s\s*[\"'`]" % controls, self.script, re.I))
        for word in ("onclick", "addEventListener", "contenteditable", "contentEditable",
                     "innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "tabindex"):
            self.assertNotIn(word.lower(), self.page.lower())
        self.assertNotIn("href", self.script)
        made = re.findall(r"\bel\(\s*([\"'`])(\w+)\1", self.script)
        self.assertTrue(made)
        self.assertLessEqual({t for _, t in made}, {"p", "span", "b", "li", "div"})
        self.assertEqual(re.findall(r"createElement\(\s*(\w+)\s*\)", self.script), ["tag"])

    def test_the_session_s_action_waits_while_an_office_is_unresolved(self):
        nxt = self.body("renderNext")
        self.assertRegex(nxt, r"if\s*\(\s*st\.unres\.length\s*\)\s*renderOffice\(st\);\s*"
                              r"else\s+renderSession\(\);")
        self.assertEqual(self.script.count("renderSession("), 2)
        office = self.body("renderOffice")
        self.assertIn('$("next-prompt").textContent = it.label;', office)
        self.assertNotIn('$("next-prompt").textContent = str(n', office)
        self.assertIn("var it = st.unres[0]", office)
        # a taken item first (S11)
        self.assertRegex(self.body("officeNow"),
                         r'unres: items\.filter\(function \(it\) \{ return it\.state === "taken"; \}\)'
                         r'\s*\.concat\(items\.filter\(function \(it\) \{ return it\.state === "open"; \}\)\)')

    def test_a_deferred_action_stays_shown(self):
        for name in ("renderSession", "renderOffice"):
            self.assertIn("renderDeferred(", self.body(name), name)
        deferred = self.body("renderDeferred")
        self.assertIn('$("next-deferred").hidden = !has;', deferred)
        self.assertIn("var has = !!str(o.prompt);", deferred)
        self.assertEqual(self.script.count('$("next-deferred").hidden'), 1)

    def body(self, name):
        """A function's body in the script, to its closing brace at two spaces."""
        at = self.script.index("function %s(" % name)
        return self.script[at:self.script.index("\n  }\n", at)]

    def test_it_reads_no_field_the_contract_does_not_give(self):
        code = re.sub(r"//[^\n]*", "", self.script)
        code = re.sub(r"/(?:[^/\\\n*]|\\.)(?:[^/\\\n]|\\.)*/[gimsuy]*(?=[.,;)\s])", "/r/", code)
        quoted = set(re.findall(r"\[\s*[\"'`](\w+)[\"'`]\s*\]", code))
        code = re.sub(r'"(?:[^"\\]|\\.)*"', '""', code)
        read = set(re.findall(r"\.\s*([A-Za-z_]\w*)", code)) | quoted
        internal = {
            # the language and the document
            "appendChild", "catch", "className", "concat", "createElement", "createTextNode",
            "every", "exec", "filter", "firstChild", "floor", "forEach", "getDate", "getDay",
            "getElementById", "getFullYear", "getHours", "getMinutes", "getMonth", "hidden",
            "indexOf", "isArray", "join", "keys", "length", "map", "push", "removeChild",
            "replace", "setAttribute", "slice", "some", "sort", "stringify", "test",
            "textContent", "toLowerCase",
            # the store's read
            "claude", "use", "doc", "onSnapshot", "data", "exists", "metadata", "fromCache",
            "code",
            # what the page computes
            "b", "m", "ds", "rd", "md", "mins", "wd", "date", "key", "v", "state", "rung",
            "unres", "applied", "nextItems"}
        given = {"context", "next", "queue", "background", "updated",
                 "heading", "paragraphs", "for", "against", "prediction", "notes", "who", "text",
                 "kind", "line", "case", "prompt", "how", "deferred", "reason", "title",
                 "day_start", "days", "bells", "time", "time_by_day", "name", "office", "label",
                 "except_days", "off_from", "off_to", "ask"}
        self.assertEqual(read - internal, given)
        for field in ("predicted", "diverged", "addressed"):
            self.assertIn('"%s"' % field, self.script)
        self.assertNotIn("items", read - internal)

    def test_it_holds_no_label_of_an_office_item(self):
        rule = json.loads(re.search(r"\*\*`ordo/rule`\*\*.*?```json(.*?)```", self.contract)
                          .group(1))
        labels = [o if isinstance(o, str) else o["label"]
                  for b in rule["bells"] for o in b["office"]]
        self.assertTrue(labels)
        for label in labels:
            self.assertNotIn(label.lower(), self.page.lower())

    def test_the_contract_names_every_field_the_page_reads(self):
        top = {"current": set(re.findall(r"\bcurrent\.(\w+)", self.script)),
               "rule": set(re.findall(r"\br\.(\w+)", self.script))}
        self.assertEqual(top["current"], {"context", "next", "queue", "background", "updated"})
        self.assertEqual(top["rule"], {"day_start", "days", "bells"})
        nested = ("heading", "paragraphs", "for", "against", "prediction", "notes",
                  "predicted", "diverged", "addressed", "who", "text",
                  "kind", "line", "case", "prompt", "how", "deferred", "reason", "title",
                  "time", "time_by_day", "name", "office", "label", "except_days",
                  "off_from", "off_to", "ask")
        for field in nested:
            self.assertTrue(re.search(r"\.%s\b|\"%s\"" % (field, field), self.script), field)
        for field in sorted(top["current"] | top["rule"]) + list(nested):
            self.assertIn("`%s`" % field, self.contract, field)
        for doc in ("`ordo/current`", "`ordo/rule`", "`ordo/ticks-<day>`"):
            self.assertIn(doc, self.contract)
        self.assertIn('db.doc("ordo/ticks-" + day)', self.script)

    def test_the_contract_gives_every_mark_the_page_reads(self):
        for state in ("taken", "overruled", "notdue"):
            self.assertIn("/^%s(\\s|$)/" % state, self.script)
            self.assertIn("`%s <ISO time>`" % state, self.contract)
        self.assertRegex(self.body("markState"),
                         r'return /\^\\d\{4\}-\\d\{2\}-\\d\{2\}T\\S\*\$/\.test\(v\) \? "done" : "open";')
        self.assertIn("any other value being read as open", self.contract)
        self.assertIn('keysFor("bell-"', self.script)
        self.assertIn("`bell-<HHMM>-<slug>`", self.contract)

    def test_the_page_is_named_and_kept_off_the_rule(self):
        self.assertIn("Its address is the `page` key of `.principal/notebook.json`, beside "
                      "`board`.", self.contract)
        self.assertIn("with the `db` and `user` capabilities", self.contract)
        self.assertIn("three sections in a fixed order, the action context, the next action "
                      "and the helpers' action context", self.contract)
        self.assertIn("one small data write to the document `ordo/current`", self.contract)
        self.assertIn("never by republishing", self.contract)
        self.assertIn("never into this repository", self.contract)
        self.assertIn("names no `page`, the sitting runs without one and says so",
                      self.contract)

    def test_round_two_sentences_of_the_contract(self):
        for words in ("The page is display only: it has no button and no input, its source holds "
                      "no data, and it writes nothing.",
                      "and the speaker writes all three, the day's marks included",
                      "Each write sets `updated`, and the clock is read before it is stamped",
                      "the speaker reads `ordo/current` with `ArtifactData` at `as_level` "
                      "`interact` and again at `admin`; where either read returns a document",
                      "the sitting runs without a page and says so",
                      "also while an office is put, under \"After the office\"",
                      "the first such item taken, else the first open one"):
            self.assertIn(words, self.contract)
        # the example's day start is an invented one, and the page's comment the same
        self.assertIn('"day_start": "05:00"', self.contract)
        self.assertIn("with day_start 05:00", self.page)


#: a stubbed document and store, the page's script run against them in node;
#: argv: the script's file, the ids the page's source hides, the scenarios
HARNESS = r"""
const fs = require("fs"), vm = require("vm");
const [script, hiddenIds, scenarios] = process.argv.slice(2).map((a, i) =>
  i === 0 ? fs.readFileSync(a, "utf8") : JSON.parse(fs.readFileSync(a, "utf8")));
function run(sc) {
  const out = { writes: [], net: [], made: [] };
  const els = {};
  function node(tag) {
    const n = { tag, children: [], hidden: false, attrs: {}, className: "", _text: "",
      appendChild(c) { this.children.push(c); return c; },
      removeChild(c) { this.children.splice(this.children.indexOf(c), 1); },
      setAttribute(k, v) { this.attrs[k] = String(v); },
      get firstChild() { return this.children[0] || null; },
      get textContent() { return this._text + this.children.map(c => c.textContent).join(""); },
      set textContent(t) { this._text = String(t); this.children = []; } };
    return n;
  }
  const document = {
    getElementById(id) { if (!els[id]) { els[id] = node("x"); els[id].hidden = hiddenIds.includes(id); } return els[id]; },
    createElement(tag) { out.made.push(String(tag).toLowerCase()); return node(tag); },
    createTextNode(t) { const n = node("#text"); n._text = String(t); return n; },
  };
  const subs = {};
  const db = { doc(path) { return new Proxy({ onSnapshot(cb) { subs[path] = cb; return () => {}; } }, {
      get(t, k) { if (k in t) return t[k]; out.writes.push(path + "." + String(k)); return () => {}; } }); } };
  const RealDate = Date, NOW = new RealDate(sc.now[0], sc.now[1], sc.now[2], sc.now[3], sc.now[4]).getTime();
  class FakeDate extends RealDate {
    constructor(...a) { if (a.length) super(...a); else super(NOW); }
    static now() { return NOW; } }
  const net = name => function () { out.net.push(name); };
  const sandbox = { document, Date: FakeDate, JSON, Math, Object, Array, String, Number, isNaN,
    console, setTimeout: () => 0, clearTimeout: () => {}, setInterval: () => 0, Promise,
    fetch: net("fetch"), XMLHttpRequest: net("XMLHttpRequest"), WebSocket: net("WebSocket"),
    navigator: { sendBeacon: net("sendBeacon") },
    window: { claude: { use: async () => db } } };
  vm.createContext(sandbox);
  vm.runInContext(script, sandbox);
  return new Promise(r => setImmediate(r)).then(() => {
    const snap = d => ({ exists: d != null, data: () => d, metadata: { fromCache: false } });
    subs["ordo/current"](snap(sc.current));
    if (subs["ordo/rule"]) subs["ordo/rule"](snap(sc.rule));
    const ticks = Object.keys(subs).find(k => k.startsWith("ordo/ticks-"));
    if (ticks) subs[ticks](snap(sc.ticks));
    out.ticksDoc = ticks || null;
    out.els = {};
    for (const [id, n] of Object.entries(els)) out.els[id] = { hidden: n.hidden, text: n.textContent };
    out.all = Object.values(els).map(n => n.textContent).join("\n");
    return out;
  });
}
(async () => { const res = {}; for (const [k, sc] of Object.entries(scenarios)) res[k] = await run(sc);
  process.stdout.write(JSON.stringify(res)); })();
"""


class PageBehaviourTest(unittest.TestCase):
    """The page's script run against a stubbed document and store, where node
    is installed; skipped where it is not."""

    #: an invented Rule; the times and labels are no one's
    RULE = {"bells": [{"time": "08:00", "name": "Morning",
                       "office": ["Water the plants", "Feed the goldfish", "Wind the clock"]},
                      {"time": "21:00", "name": "Evening", "office": ["Cover the seedlings"]}]}
    CURRENT = {"next": {"kind": "question", "prompt": "Is watering still first?",
                        "items": ["CHECKLIST-ITEM"],
                        "deferred": {"prompt": "Write the letter.", "reason": "A passing feeling.",
                                     "kind": "nonsense"}},
               "queue": [{"kind": "review", "title": "Review the rows"}],
               "updated": "2030-01-02T09:00:00Z"}
    NOW = [2030, 0, 2, 9, 0]
    KEYS = ("bell-0800-water-the-plants", "bell-0800-feed-the-goldfish",
            "bell-0800-wind-the-clock")

    @classmethod
    def setUpClass(cls):
        cls.node = shutil.which("node")
        if not cls.node:
            raise unittest.SkipTest("node is not installed")
        with open(PAGE, encoding="utf-8") as fh:
            page = fh.read()
        cls.hidden = [m.group(1) for m in re.finditer(r"<[^>]*\bid=\"([^\"]+)\"[^>]*>", page)
                      if re.search(r"\shidden[\s>]", m.group(0))]
        cls.script = page[page.index("<script>") + len("<script>"):page.index("</script>")]
        T, D = "2030-01-02T08:30:00.000Z", "2030-01-02T08:10:00.000Z"
        k = cls.KEYS
        scenarios = {
            "quiet": {"now": [2030, 0, 2, 7, 0], "current": cls.CURRENT, "rule": cls.RULE,
                      "ticks": None},
            "rung": {"now": cls.NOW, "current": cls.CURRENT, "rule": cls.RULE, "ticks": None},
            "taken": {"now": cls.NOW, "current": cls.CURRENT, "rule": cls.RULE,
                      "ticks": {k[2]: "taken " + T}},
            "junk": {"now": cls.NOW, "current": cls.CURRENT, "rule": cls.RULE,
                     "ticks": {k[0]: "done", k[1]: D, k[2]: "overruled " + D}},
            "resolved": {"now": cls.NOW, "current": cls.CURRENT, "rule": cls.RULE,
                         "ticks": {k[0]: D, k[1]: "notdue " + D, k[2]: "overruled " + D}},
            "norule": {"now": cls.NOW, "current": cls.CURRENT, "rule": None, "ticks": None},
        }
        with tempfile.TemporaryDirectory() as tmp:
            paths = []
            for name, data in (("page.js", cls.script), ("hidden.json", json.dumps(cls.hidden)),
                               ("scenarios.json", json.dumps(scenarios)),
                               ("harness.js", HARNESS)):
                with open(os.path.join(tmp, name), "w", encoding="utf-8") as fh:
                    fh.write(data)
                paths.append(os.path.join(tmp, name))
            done = subprocess.run([cls.node, paths[3]] + paths[:3], capture_output=True,
                                  text=True, timeout=60, env=dict(os.environ, TZ="UTC"))
        if done.returncode:
            raise AssertionError(done.stderr)
        cls.res = json.loads(done.stdout)

    # the stub keeps no tree: a block's parts are read by their own ids
    def shown(self, name, id_):
        e = self.res[name]["els"].get(id_)
        return e is not None and not e["hidden"]

    def text(self, name, id_):
        return self.res[name]["els"][id_]["text"]

    def test_it_writes_nothing_sends_nothing_and_makes_no_control(self):
        for name, out in self.res.items():
            self.assertEqual(out["writes"], [], name)
            self.assertEqual(out["net"], [], name)
            self.assertLessEqual(set(out["made"]), {"p", "span", "b", "li", "div", "#text"}, name)

    def test_no_checklist_is_rendered(self):
        for name, out in self.res.items():
            self.assertNotIn("CHECKLIST-ITEM", out["all"], name)

    def test_the_session_s_action_with_no_office_open(self):
        for name in ("quiet", "resolved", "norule"):
            self.assertEqual(self.text(name, "next-prompt"), "Is watering still first?", name)
            self.assertTrue(self.shown(name, "next-deferred"), name)
            self.assertFalse(self.shown(name, "bell"), name)
            self.assertFalse(self.shown(name, "office-after"), name)
        self.assertEqual(self.text("quiet", "next-def-prompt"), "Write the letter.")
        # a deferred kind the page does not know is shown as work
        self.assertIn("work", self.text("quiet", "next-def-meta"))
        self.assertIn("Next bell: Morning at 08:00.", self.text("quiet", "next-bell"))
        self.assertEqual(self.res["rung"]["ticksDoc"], "ordo/ticks-2030-01-02")

    def test_the_office_comes_before_the_session_s_action(self):
        self.assertTrue(self.shown("rung", "bell"))
        self.assertEqual(self.text("rung", "next-prompt"), "Water the plants")
        self.assertEqual(self.text("rung", "next-kind"), "office")
        self.assertNotIn("Is watering still first?", self.text("rung", "next-prompt"))
        self.assertTrue(self.shown("rung", "office-after"))
        self.assertEqual(self.text("rung", "office-after-prompt"), "Is watering still first?")
        # S3: the deferred action stays shown under the office
        self.assertTrue(self.shown("rung", "next-deferred"))
        self.assertEqual(self.text("rung", "next-def-prompt"), "Write the letter.")
        self.assertIn("not yet taken up", self.text("rung", "bell-msg"))

    def test_a_taken_item_is_shown_first(self):
        self.assertEqual(self.text("taken", "next-prompt"), "Wind the clock")
        self.assertTrue(self.shown("taken", "under"))
        self.assertIn("Then: Water the plants · Feed the goldfish",
                      self.text("taken", "office-then"))
        self.assertIn("under way", self.text("taken", "bell-msg"))

    def test_a_mark_that_is_no_time_is_open(self):
        self.assertEqual(self.text("junk", "next-prompt"), "Water the plants")
        self.assertIn("1 of 3 office items left", self.text("junk", "bell-msg"))
        self.assertIn("Done: Feed the goldfish", self.text("junk", "office-resolved"))


if __name__ == "__main__":
    unittest.main()
