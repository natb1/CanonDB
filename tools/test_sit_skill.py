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
#: the parts of the skill, read on demand, in the order the skill's text runs
PARTS = os.path.join(ROOT, "skills", "sit", "parts")
PART_ORDER = ["arrangement", "brief", "serves", "ground-rules", "page", "bells", "open-lines",
              "predictions", "board", "opening", "round", "batch-point", "ai-line",
              "attenuation", "departures"]
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


def read(path):
    """A file's text; the sitting's skill read as its core and then its parts,
    in the order the skill's text runs."""
    if os.path.realpath(path) != os.path.realpath(SKILL):
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    texts = []
    for each in [SKILL] + [os.path.join(PARTS, name + ".md") for name in PART_ORDER]:
        with open(each, encoding="utf-8") as fh:
            texts.append(fh.read())
    return "\n".join(texts)


def flat(path):
    return " ".join(read(path).split())


def spans(path):
    """Every code span of a file, in its order, its code blocks left out."""
    text = re.sub(r"```.*?```", "", read(path), flags=re.S)
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


def _code(path, heading):
    """The first JSON code block of a file after ``heading``."""
    text = read(path)
    return re.search(r"```json\n(.*?)```", text[text.index(heading):], re.S).group(1)


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

    def test_the_skill_states_no_goal_of_its_own(self):
        serves = self.skill[self.skill.index("## What the sitting serves"):
                            self.skill.index("## Ground rules")]
        for words in ("This skill states no goal of its own.",
                      "The sitting serves that portion of the principal's rule of life that can "
                      "be delegated to the AI, as the notebook states it.",
                      "The AI's graph is built by a line that arrives at the principle by which "
                      "the delegated actions are carried out",
                      "This skill is meant to be a projection of the AI's graph: each of its rules "
                      "following from an answer there, and citing it.",
                      "Most of it was built straight from the principal's words, as a stopgap, "
                      "before the AI's graph held answers that cover it.",
                      "A part of it is rebuilt when the AI's graph comes to cover that part and "
                      "would build it differently",
                      "How the AI's graph realizes the user's is not fixed here.",
                      "Each is an observation and never a verdict",
                      "or to a stated reason why none is owed",
                      "A count is read, and never driven."):
            self.assertIn(words, serves)
        self.assertNotIn("## The goal", self.skill)
        self.assertNotIn("is a reconciliation of the AI's graph", self.skill)
        self.assertNotIn("weighted by the share each principle carries", self.skill)
        self.assertNotIn("the goal says", self.skill)

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
                "Tradition readings are recorded as the round goes, without waiting for "
                "approval",
                "as a note opening with the word *pending* that calls it a lead, never marked "
                "verified, stating the party's position and never the answer it was given "
                "after, the question or its case, through the recorder",
                "a review that states or changes a principle carries no tradition, and a review "
                "of mechanism is followed, after its answer, by tradition for and against that "
                "answer",
                "which is the speaker's reading of the principal's word that the readings given "
                "after two reviews of mechanism were good, and no rule the principal dictated",
                "ends with the stamp of the record of predictions",
                "sealed the same way as a question, and the principal's choice is graded against "
                "the sealed one",
                "once it is graded, a failed prediction is recorded and an agreeing one counted",
                "what was built is reported in the action context",
                "5. **The principal may always override the action ranked first**",
                "An override is an observation of a gap, never a verdict",
                "the page keeps showing the deferred action beside the revised one",
                "it is carried in every whole-document `set` of `ordo/current` until it is done "
                "or the principal drops it",
                "6. **The next action is one of four kinds: question, office, work, review.**",
                "a review is put exactly as a question is",
                "a review of mechanism carries the speaker's recommendation, in "
                "`next.recommendation`, its own field and never in the case, and a review that "
                "states or changes a principle, a grant or a row stating a principle among them, "
                "is put with no recommendation, as a question is, and the page shows none",
                "a prediction is sealed before every review as well, by the speaker itself",
                "the file says who predicted",
                "There are no checklists.",
                "7. **Bells.** An unresolved office of the principal's shows first unless the "
                "principal has set it aside or an action put before the bell rang is still "
                "pending; items run by the session never hold the card.",
                "until each of the principal's is done, overruled or marked not due, or the "
                "principal sets the office aside; only then does the speaker's own next action "
                "show",
                "an item may be taken up",
                "among a bell's unresolved items the page shows a taken one first, else the first "
                "open one",
                "A `work` action has no mark: it stays `next` in `ordo/current` until the speaker "
                "changes it on the principal's word.",
                "The page always shows the next bell",
                "always in the context panel, on one timeline",
                "An office item marked `by: \"session\"` is the speaker's, not the principal's",
                "puts any question it raises on the page as an action, and writes its mark; the "
                "principal never reports it",
                "a transient action divergence",
                "the speaker writes `office_deferred` only at the principal's word",
                "an observation of a gap, as **Observations** says, and never a verdict",
                "clears it when the principal takes the office up again",
                "A measured value the principal reports with an item is kept as a plain field in "
                "the day's marks document beside the marks.",
                "The page writes nothing",
                "an overruled office item is an observation like any other override",
                "8. **Every time the speaker stamps is read from the clock, never typed**",
                "9. **The speaker, at the full tier, writes no code, page or tooling itself.**",
                "the judge is never the tier judged",
                "10. **Every ask of the principal is an action on the page, in order.**",
                "The speaker never leaves an ask only in the session's text",
                # round three, S7
                "Every explanation, every answer to a question of the principal's, and every "
                "report of what was done goes in the page's action context, `context`, as its "
                "`heading` and `paragraphs`, or in `context.log`.",
                # the session's printed text is a log of operations
                "Anything that needs the principal's attention is on the page: an action, a "
                "result the principal should know, an error, a helper's finding, a thing owed by "
                "the principal; where the page is in use, what is only in the session's text has "
                "not been presented.",
                "What the speaker prints in the session never repeats what the page presents: "
                "the session's printed text is a log of operations, each in the fewest words "
                "that identify it, for example a version written, a job launched, a helper's "
                "verdict in a word, a refusal, a pull request's number and state, a wait or a "
                "stop, with no explanation, no summary of the page and no restating of a "
                "question or a recommendation.",
                "Every write of the page is logged, by the version written; where the write puts "
                "on the page something that needs the principal's attention other than the "
                "action itself, an error, a refusal, a helper's finding or a thing owed, the log "
                "line says in a word that the page holds one, a pointer and not a summary.",
                "Where the page is not in use or cannot be relied on, the session says so and "
                "says the thing itself: where the page could not be written, where the sitting "
                "runs without one, and at every stop before the page's store is read at the "
                "opening, the stops of **Before anything** among them.",
                "Once the page is written again, what was said only in the session is written "
                "to the page as well, since the page is its record.",
                "Context above a question of principle still carries no recommendation (rule 1).",
                # round three, B1, S5, S6
                "The page counts it only where `since` is at or after the moment the named bell "
                "rang in the current Rule day, and the speaker removes it in its first write "
                "after a later bell has rung or the Rule's day has turned.",
                "the speaker itself runs it, with its own tools, when the timing is right",
                "It is the one act not put to the principal: the Rule, written at the "
                "principal's word, is the grant.",
                "An office set aside, or left unresolved, when a later bell rings does not "
                "vanish: the page shows only the latest bell's office on the card, and the "
                "speaker lists those items in the action context as still due from the earlier "
                "bell until the principal says done, overruled or not due for each.",
                # round three, S8: sentences no test held
                "This session does not read the sealed file until the answer is in.",
                "while it stands the page shows the speaker's next action with the office under "
                "it, still due",
                "carries it in every whole-document `set` of `ordo/current`, and clears it",
                "it never holds back the speaker's own next action",
                "`office_deferred`'s `since`, `ordo/agenda`'s `fetched`, `context.at` and "
                "each `at` of `context.log`, and a line's `opened_at` and `touched_at`"):
            self.assertIn(words, round_)
        self.assertNotIn("a helper it starts", self.skill)
        self.assertNotIn("runs itself, or by a helper", self.skill)
        self.assertNotIn("a later bell ends it", self.skill)
        self.assertNotIn("Put the question, with the four parts of the step", self.skill)
        self.assertNotIn("Tradition readings go to the notebook only with the principal's "
                         "approval", self.skill)
        self.assertNotIn("a review of mechanism included", self.skill)
        self.assertNotIn("sealed the same way as a review", self.skill)
        self.assertNotIn("collection `predictions`", self.skill)
        self.assertNotIn("reports what they hand back in the action context", self.skill)
        self.assertNotIn("marks it as given", self.skill)
        with open(SKILL, encoding="utf-8") as fh:
            core = " ".join(fh.read().split())
        self.assertNotIn("one or two lines saying the page changed", round_)
        self.assertNotIn("one or two lines saying the page changed", core)
        for words in ("Anything that needs the principal's attention is presented here, in the "
                      "next action, the action context or its log, and the session's printed "
                      "text, a log of operations only, never repeats it (rule 10).",
                      "where the write still cannot be made, the session says so and says the "
                      "thing itself, since the page cannot carry it (rule 10)"):
            self.assertIn(words, flat(os.path.join(PARTS, "page.md")))
        self.assertIn("The session's printed text is a log of operations in the fewest words "
                      "that identify each, never repeating what the page presents; every write "
                      "of the page is logged by its version, and says in a word where it holds "
                      "an error, a refusal, a helper's finding or a thing owed. Where the page "
                      "could not be written, where the sitting runs without one, and at every "
                      "stop before the page's store is read at the opening, the session says so "
                      "and says the thing itself.", core)
        self.assertIn("where the page is in use, what is only in the session's text has not "
                      "been presented", core)
        self.assertNotIn("one or two lines saying the page changed",
                         flat(os.path.join(PARTS, "page.md")))
        departures = flat(os.path.join(PARTS, "departures.md"))
        self.assertIn("The session's printed text is a log of operations in the fewest words "
                      "that identify each, every write of the page logged by its version, where "
                      "before it was one or two lines saying the page changed.", departures)
        attenuation = flat(os.path.join(PARTS, "attenuation.md"))
        for words in ("**The session's printed text is held by reading.** Nothing checks what "
                      "the speaker prints in the session",
                      "a second voice, said as such on the page, in the action context.",
                      "the speaker says so to the principal on the page, in the action context",
                      "a kind that keeps failing is said to the principal on the page, in the "
                      "action context."):
            self.assertIn(words, attenuation)

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

    def test_round_three_reports_go_on_the_page(self):
        """S7: the brief, the close and a failed link are on the page."""
        for words in ("**2 — The brief.** The brief is a report, written on the page, in the "
                      "action context (rule 10), and not in the session's text.",
                      "Run `status` again and say on the page, in the action context, what "
                      "stands open",
                      "tells the principal on the page, in the action context, which link failed "
                      "and why in a sentence"):
            self.assertIn(words, self.skill)
        self.assertIn("An office item the Rule gives the session to run is run by the speaker "
                      "itself and is not put to the principal", self.skill)
        self.assertIn("save an office item the Rule gives the session to run", self.skill)
        self.assertIn("The session's shell stays in the project", self.skill)

    def test_round_three_the_turn_s_paragraph(self):
        """B1, S6, S8, S9: the turn's paragraph says what rule 7 says."""
        turn = self.skill[self.skill.index("At each turn the speaker reads and writes (rule 7)"):
                          self.skill.index("## Procedure")]
        for words in ("While the latest bell has an item of the principal's unresolved, the page "
                      "is putting the office and not `next`",
                      "or the principal sets the office aside, except while an action put "
                      "before the bell rang is still pending",
                      "the pending action is resolved after the bell, then the very next item is "
                      "the office item; items run by the session never hold the card",
                      "the speaker reads the clock and writes `taken`",
                      "the speaker lists each in the action context as still due from that bell "
                      "until the principal says done, overruled or not due for it, and lets none "
                      "lapse without that word",
                      "the speaker writes `office_deferred`, only at the principal's word",
                      "it removes it too in its first write after a later bell has rung or the "
                      "Rule's day has turned"):
            self.assertIn(words, turn)
        self.assertNotIn("lets them lapse", self.skill)

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


class StopgapTest(unittest.TestCase):
    """What the principal said of predictions, tradition, writing as the round
    goes, merging, hinges, the head kept after a compaction and the board's
    keys, each carried by the skill, and each rule it reverses listed."""

    def setUp(self):
        self.raw = read(SKILL)
        self.skill = flat(SKILL)

    def section(self, heading, until):
        return self.skill[self.skill.index(heading):self.skill.index(until)]

    def test_after_a_compaction_is_the_first_section_and_short(self):
        headings = re.findall(r"^## .*$", self.raw, re.M)
        self.assertEqual(headings[0], "## After a compaction")
        start = self.raw.index("## After a compaction")
        body = self.raw[start:self.raw.index("\n## ", start + 3)]
        self.assertLessEqual(len(body.strip().splitlines()), 25)
        # well inside the head a compaction keeps, some 5,000 tokens
        self.assertLess(start + len(body), 5000 * 3)
        flat_body = " ".join(body.split())
        for words in ("`${CLAUDE_PLUGIN_ROOT}/skills/sit/SKILL.md`",
                      "with the Read tool in parts, by `offset` and `limit`, to its last line",
                      "`ordo/current`", "the open documents of `lines`",
                      "`tools/predictions.py stamp $SCRATCH/graph.json --added "
                      "$SCRATCH/predictions --at <time> > $SCRATCH/speaker/stamp.txt`",
                      "the session's scratchpad named in its own instructions, or a job's",
                      "whose answer is not yet in `$SCRATCH/answers/` stands: it is not sealed "
                      "again",
                      "nothing is done from what survives of it"):
            self.assertIn(words, flat_body)
        # the last line it names is the file's last section's opening
        self.assertIn("What this entry point says now that reverses what it said before:",
                      self.raw)

    def test_the_record_of_predictions_is_the_notebook(self):
        rec = self.section("## The record of predictions", "## Procedure")
        for words in ("What is learned about predicting the principal must not be transient",
                      "as a stopgap (**What the sitting serves**)",
                      "There is no store of predictions and no store of lessons beside the "
                      "notebook.",
                      "**A failed prediction is a divergence.**",
                      "names the seal graded by its id, who predicted, the kind of action, the "
                      "grade and the direction, and never the sealed text, the answer or the "
                      "case",
                      "so that two failures in the same words are two notes",
                      "the tab the notebook keeps for how the record predicts the user",
                      "in the line doc's Fidelity rounds section",
                      "which needs no new form",
                      "the speaker puts the making of one to the principal as an action",
                      "**The lessons are record.** A clean reader reads the notebook, and so "
                      "reads these notes and the lessons in them",
                      "It is never handed the stamp or the tally",
                      "**Before every prediction of the speaker's own**",
                      "Only then is its fingerprint taken."):
            self.assertIn(words, rec)
        from hypo import predictions
        for name in predictions.DIRECTIONS + predictions.FAILED:
            self.assertIn("`%s`" % name, rec)
        self.assertIn("**The record of predictions is held by reading.**", self.skill)
        self.assertNotIn("ArtifactData` `list` of `predictions`", self.skill)

    def test_every_lesson_is_the_invented_one_or_a_placeholder(self):
        """B1: the skill gives a lesson only as a placeholder, and the tests use
        one invented lesson, about weather and days."""
        self.assertEqual(re.findall(r'--lesson "([^"]*)"', self.skill), ["<the lesson>"])
        import test_predictions
        self.assertEqual(test_predictions.LESSON,
                         "A rule about days is asked about weather too.")
        with open(os.path.join(HERE, "test_predictions.py"), encoding="utf-8") as fh:
            body = fh.read()
        self.assertEqual(set(re.findall(r'lesson="([^"]*)"', body)),
                         {"a rule about days is asked about  weather too",
                          "Ask about the post as well as the plants."})

    def test_tradition_and_writing_as_the_round_goes(self):
        for words in ("The principal approved the readings of tradition given and asked that "
                      "they be recorded as the round goes.",
                      "A party's graph is expected to follow the structure of the user's and the "
                      "AI's; that change of form is not made here, and is carried as an open "
                      "line",
                      "**Written as the round goes.** The principal has given leave to write to "
                      "the notebook as the round goes.",
                      "once its restatement has been shown in the action context, so that the "
                      "principal may correct it before the job is added",
                      "None is first put as a review of rows.",
                      "Everything else, a sentence, a case, and anything that changes a standing "
                      "answer, still goes through the batch point's reviews.",
                      "Three notes are written at the round without a review of rows"):
            self.assertIn(words, self.skill)

    def test_tradition_on_a_new_fact_is_recorded_before_the_next_action(self):
        rule = self.section("4. **After the answer, in this order on the page.**",
                            "5. **The principal may always override")
        for words in ("Tradition follows an answer whenever the answer brings a new fact, "
                      "whatever the kind of action it answers",
                      "tradition on a newly reported fact is always given",
                      "every reading given, on the page or, where there is none, in the "
                      "session's words, is recorded in the notebook in the same round, before "
                      "the next action is put",
                      "on the `dictate` tab, at the end of its Hinge section, naming its party, "
                      "stating the party's position only, never the answer, the question or its "
                      "case, called a lead and never marked verified",
                      "`tools/tradition.py rows <the dictate tab's file in that fetch's views "
                      "directory> $SCRATCH/tradition/<job id>.json",
                      "The next action is not put while a reading given is unrecorded",
                      "appends to the context, in `context.log`, that the readings were "
                      "recorded",
                      "Where the `record` job fails, or its rows cannot be made",
                      "at the board's limit of attempts, or once a second set of rows drawn for "
                      "the same readings has failed or could not be made, the readings are "
                      "carried as an open note of kind `work`, the action context says that "
                      "they are not recorded, and the next action is then put.",
                      "where that tab has no Hinge section, they go at the end of its last "
                      "section, named by `--section`",
                      "those writes are not held, and what waits is the speaker's own next "
                      "action, the next write of `next`",
                      "a `fetch` job of the `dictate` tab is run first",
                      "--after <the last block of its Hinge section>"):
            self.assertIn(words, rule)
        self.assertIn("neither touches the tradition on a new fact an answer brings, which "
                      "rule 4 gives after an answer of any kind", self.skill)
        self.assertIn("5 to 10 bind every action, and so does rule 4's tradition on a new "
                      "fact and its recording", self.skill)
        build = self.section("9. **The speaker, at the full tier", "10. **Every ask")
        for words in ("The speaker never tells the principal that the process will change "
                      "from now on without starting the mechanism in the same round",
                      "it says that the process has not changed until that pull request is "
                      "merged and the plugin loaded again",
                      "A note in the speaker's own memory is not the mechanism.",
                      "the change is named to the principal as an open note of kind `change`, "
                      "and the process is said not to have changed until that lands"):
            self.assertIn(words, build)
        departs = self.skill[self.skill.rindex("What this entry point says now that "
                                               "reverses"):]
        self.assertIn("Tradition follows every answer that brings a new fact, whatever the "
                      "kind of action", departs)
        self.assertIn("**The card's check and the readings' rows hold shapes, not sense.**",
                      self.skill)
        self.assertIn("checked with `tools/card.py check <that file>`; it is sent only once "
                      "the check prints `ok`", self.skill)

    def test_merging_and_the_reload(self):
        rule = self.section("9. **The speaker, at the full tier", "10. **Every ask")
        for words in ("what was built is reported in the action context; a build that "
                      "changes what the principal decides, a rule of a skill or what the page "
                      "shows among it, is put to the principal as a review and waits for the "
                      "answer; and then the speaker may merge, unless the principal said "
                      "otherwise",
                      "The principal has given leave to merge pull requests unless the "
                      "principal says otherwise",
                      "the pull request's checks pass; the full tier's adversarial review of it "
                      "returns, with no blocker left open",
                      "The first two conditions are mechanism, the speaker's and not the "
                      "principal's words.",
                      "puts the reload of the plugin to the principal as a `work` action on the "
                      "page"):
            self.assertIn(words, rule)
        boot = flat(os.path.join(ROOT, "skills", "bootstrap", "SKILL.md"))
        self.assertIn("**The author merges, or this run at the principal's leave.**", boot)
        self.assertIn("those two conditions are mechanism", boot)
        self.assertNotIn("It never merges", boot)

    def test_hinges_in_the_ai_s_graph(self):
        line = self.section("## The line in the AI's graph", "## Attenuation")
        for words in ("10. **Every presupposition is a hinge.**",
                      "A hinge is justified only by a later answer of the AI's own that it is "
                      "linked to",
                      "`tools/hinges.py unjustified $SCRATCH/graph.json`",
                      "`tools/hinges.py place $SCRATCH/lines/<line> --n <n> --under <id> > "
                      "$SCRATCH/lines/<line>/<n>/place.json`",
                      "It reads the line's directory alone, and nothing of the user's record.",
                      "a new tab of the AI's own record needs no dictation",
                      "`tools/hinges.py rows $SCRATCH/lines/<line>/<n>/place.json --line "
                      "$SCRATCH/lines/<line> --line-name <line> --node <node id> --kind <kind> "
                      "--read <the tab's read> > $SCRATCH/rows/<job id>.json`",
                      "Placing on a new tab is two steps, in this order, and no one command "
                      "prints both"):
            self.assertIn(words, line)
        answerer = flat(os.path.join(ROOT, "clean", "answerer.md"))
        self.assertIn("\"Presupposes:\" stands on a line of its own, and under it, one to a "
                      "line, each line opening with \"- \"", answerer)

    def test_the_board_and_the_page_named_missing(self):
        before = self.section("## Before anything", "## Ground rules")
        for words in ("Publish the plugin's `web/board.html` once as a private artifact",
                      "put its address in `.principal/notebook.json` as `board`",
                      "Publish `web/ordo.html` once as a private artifact, with the db and user "
                      "capabilities and rules that let only its owner read and write, and put "
                      "its address there as `page`",
                      "Then start the sitting again."):
            self.assertIn(words, before)
        self.assertIn("tells the principal to publish `web/ordo.html` once as above",
                      self.skill)

    def test_the_review_card_s_order_is_unchanged(self):
        self.assertIn("The page keeps that order, heading, \"Written\", paragraphs, tradition, "
                      "prediction, notes and the records, whatever the data's.", self.skill)

    def test_each_reversal_is_listed(self):
        reversals = self.skill[self.skill.rindex("What this entry point says now that "
                                                 "reverses"):]
        for words in ("A failed prediction is recorded on the notebook at the round, as a "
                      "divergence",
                      "A review of mechanism is followed by tradition for and against its "
                      "answer, where before a review carried none. This one is the speaker's "
                      "reading of the principal's word",
                      "Readings of tradition are recorded on the parties' tabs at the round, as "
                      "leads never marked verified, by a `record` job, without waiting for "
                      "approval, where before",
                      "A requirement the principal states is recorded on the notebook as a "
                      "*pending* note at the round it is said",
                      "In the open way the speaker may merge",
                      "Every presupposition a question on a line carries in is recorded as a "
                      "hinge"):
            self.assertIn(words, reversals)
        self.assertNotIn("An act is sealed by the speaker", reversals)


class PartsTest(unittest.TestCase):
    """The core a session keeps whole, and every part it names, each opening
    with when it is read."""

    def test_the_core_is_short_and_indexes_every_part(self):
        with open(SKILL, encoding="utf-8") as fh:
            core = fh.read()
        self.assertLessEqual(len(core.splitlines()), 250)
        self.assertEqual(sorted(f[:-3] for f in os.listdir(PARTS) if f.endswith(".md")),
                         sorted(PART_ORDER))
        index = core[core.index("## The parts"):]
        self.assertEqual(re.findall(r"^\| `([\w-]+)\.md` \|", index, re.M), PART_ORDER)
        for name in PART_ORDER:
            with open(os.path.join(PARTS, name + ".md"), encoding="utf-8") as fh:
                self.assertTrue(fh.readline().startswith("Read this part "), name)


class LineTest(unittest.TestCase):
    """The line in the AI's graph, and what the sitting's other rules say of
    it: the key sentences."""

    def setUp(self):
        self.skill = flat(SKILL)
        self.line = self.skill[self.skill.index("## The line in the AI's graph"):
                               self.skill.index("## Attenuation")]

    def test_a_clean_turn_is_a_run_of_its_own(self):
        for words in ("Each is put in a clean turn: a run of the harness of its own, started by "
                      "`tools/clean_turn.py`",
                      "A clean turn is never a helper of this session",
                      "the speaker runs `tools/clean_turn.py probe`; where it exits other than 0 "
                      "no line is drawn",
                      "the tool refuses a question of the graph the AI does not answer, or that "
                      "holds no answer past held, a graph on which `only-ai-put` or "
                      "`state-order` fails, a gap in the line"):
            self.assertIn(words, self.line)

    def test_the_nine_rules(self):
        for words in (
                # 1, the order
                "The principal's requirement is recorded on the user's side first",
                "Then the build, whose brief cites the AI's answers by their opening words and "
                "never the principal's requirement. Then the build is checked against the record",
                "Nothing is built straight from the principal's words unless the principal asks "
                "for that explicitly, once",
                # 2, intention
                "Every line opens at the purpose: what the thing is for, and what it must never "
                "do. A question of how stands only beneath an answer of why.",
                "Each answer names the answers it rests on",
                "a back-brief is drawn",
                "A difference of intention is repaired by drawing again higher up, never by "
                "correcting the mechanism.",
                "one of them is a case where the letter of the mechanism and its purpose part",
                # 3, questions
                "Only a question read as `does not lead` becomes its own action on the page, "
                "a `review` whose prompt is the question word for word, its `next.reading` the "
                "path of its `lead.json`, for the principal to approve or revise;",
                "and the question is put to the AI only on that approval.",
                "A revision is written over `question.md`, checked and read again before it "
                "is shown again, and only the text the principal approved is put.",
                "`{\"sha256\": <the fingerprint of the question file as approved>, "
                "\"approved\": <the time, from the clock>}`, and the clean turn refuses any "
                "other text",
                "breaks the notebook's rule for naming the user, saying what it found",
                "A question the AI's own record raises comes verbatim from a drawer turn",
                "Case situations go to the AI's record as questions; verdicts and reasons stay "
                "on the user's side, with the comparing run.",
                # 4, draws
                "All are kept, none is chosen by what it says, and the first kept is the answer "
                "of record (above). Where they part in what they would do, that is the "
                "finding, and the question is drawn higher.",
                # 5, the signal
                "the drawer refuses words that do not open exactly one answer of the packet, "
                "or hold fewer than four words",
                # 5, a divergence
                "The comparing run hands back only the redraw signal",
                "After two redraws of one divergence, the default,",
                "which stands in the AI's record in the principal's words by way of a further "
                "approved question",
                "a further question, a stated position, a build straight from the notebook as a "
                "stopgap, or the principal does it",
                # 6, budget
                "A line spends at most twenty-four clean turns, the default",
                "the turns spent against the budget and the cost the draws recorded",
                # 7, the AI's action
                "as the AI's action, naming the answers it rests on by their opening words, so "
                "that the principal is prompted to review it",
                # 8, four signals
                "Before the speaker treats any constraint as binding it tests four signals and "
                "says which apply: marked stale by a later note; a mechanism standing as a "
                "principle",
                "its price, the divergences recorded on it, beside the share it carries; and "
                "unjustified, no edge to a principle nearer the root",
                # 11, new ideas in the draws
                "reads every kept draw for ideas new to the sitting: every kept draw of a "
                "question, a drawer turn's draw and the back-brief",
                "An idea is new where neither the user's record, the page, a document of "
                "`lines` whatever its state, nor the AI's own record as the packet carried it "
                "already holds it, and it was not already returned in this sitting",
                "what counts as one idea, and whether it is new, is the speaker's reading",
                "a `review`, put with no recommendation, since it states no position of the "
                "notebook's",
                "In a drawer turn's draw, the questions it raises go on by rule 3 and are not "
                "`ai-draw` lines; anything else it says is read as any draw is.",
                "an `ai-draw` line is not put as the next action while its naming is held",
                "A build's brief cites the answers of record as rule 1 gives.",
                "Each such idea opens an open line of origin `ai-draw` (**The open lines**) in "
                "the same round",
                "The speaker makes no judgment of which are worth following, and the principal "
                "drops what is not wanted",
                "citing the line, the question's number, or the drawer turn or the back-brief, "
                "and the draw's index, and saying whether that draw is the answer of record",
                "Where a context already stands for the round, the naming is a record in "
                "`context.log`.",
                "While a question or review of principle is put on the page, or another action "
                "is the next to be put and the idea bears on it, the naming is held and given "
                "after its answer",
                "A held naming, and an owed statement that no new idea was found, are kept in "
                "the work in hand, `tools/inhand.py add $SCRATCH/speaker",
                "For each question, drawer turn or back-brief read, the action context says "
                "that its draws yielded no new idea where they yielded none.",
                "Until the principal has answered the idea's line, the speaker carries no idea "
                "of a draw not of record anywhere, a build's brief among them, and no idea of "
                "any draw in its own drafting of a question or a redraw signal",
                "What `tools/packet.py` carries of the answer of record, and a question a "
                "drawer turn raised, go on as rules 3 and 4 give.",
                "An idea dropped, or closed without being taken up, stays out of the speaker's "
                "drafting of a question or a redraw signal, and, where it comes from a draw not "
                "of record, out of a build's brief, for good, unless the principal states it; a "
                "brief that cites an answer of record holding it cites it as rule 1 gives.",
                "it goes on the tab the idea bears on, and where it bears on none, at the end of "
                "the `dictate` tab's Hinge section, or of its last section where it has none",
                "A line of origin `ai-draw` is never queued to a clean turn unasked.",
                "it enters the AI's record only by rules 1, 3 and 5, in an approved question",
                "the note says it is an idea from the AI's draws and not a position of the "
                "user's",
                "Nothing of this changes which draw is the answer of record, the first kept "
                "(rule 4)."):
            self.assertIn(words, self.line)

    def test_the_action_context_is_appended_to_within_a_round(self):
        for words in ("once it is written for a round, nothing in it is changed until the "
                      "principal answers",
                      "appended to the same context as a record carrying its time, in "
                      "`context.log`, each record `{at, paragraphs}`",
                      "never kept as a separate log beside the context",
                      "After the principal answers, the context is written anew."):
            self.assertIn(words, self.skill)

    def test_every_helper_is_started_with_a_model_named_for_the_job(self):
        self.assertIn("Every helper the speaker starts is started with a model named for the "
                      "job, never left to inherit", self.skill)
        self.assertIn("Lookups and mechanical checks go to the smallest tier that can do them.",
                      self.skill)

    def test_the_table_and_the_turns(self):
        for row in ("| `turn` | `full` | none: the speaker, by `tools/clean_turn.py` |",
                    "| `compare` | `full` | `comparer` |",
                    "| `place` | `mid` | `ai-recorder` |"):
            self.assertIn(row, self.skill)
        self.assertIn("(`state`, `remedy`, `line`) has no helper defined for it", self.skill)
        self.assertIn("No other session puts a question to the AI's record.", self.skill)
        self.assertNotIn("/principal:ask` in a session of the principal's own", self.skill)
        self.assertNotIn("refuses a packet `tools/packet.py` did not write", self.skill)
        self.assertIn("| `compare` | `full` | `comparer` | `notebook`, `index`: the line's index, "
                      "`$SCRATCH/lines/<line>/index` |", self.skill)

    def test_a_line_is_many_questions_deep(self):
        """B2: the packet carries the line's earlier answers, each under its
        question, the first kept draw of each the answer of record."""
        for words in ("`tools/packet.py $SCRATCH/graph.json --under <id> --line "
                      "$SCRATCH/lines/<line> -o $SCRATCH/lines/<line>/<n>/packet.md`",
                      "then the line's own earlier questions and answers, in the order they "
                      "were put, each answer under the question it was given to, marked "
                      "`<<< question >>>` and `<<< answer >>>`",
                      "a question of how reaches the answer of why above it on the line, however "
                      "many questions deep",
                      "the first draw a question's manifest lists as kept is the answer of "
                      "record, the one every later packet carries; the others are the evidence "
                      "of whether that answer is stable",
                      "A drawer turn's packet is cut by the same line as the question it draws "
                      "under",
                      "and `index`, every file of the line by its absolute path, one a line",
                      "The clean turn refuses a question in which a token opens with `@`"):
            self.assertIn(words, self.line)

    def test_the_open_lines_have_one_home(self):
        lines = self.skill[self.skill.index("## The open lines"):self.skill.index("## Procedure")]
        for words in ("Every open line still to be put to the principal is one document of the "
                      "page's database, in the collection `lines`, beside `ordo`, and nothing "
                      "waits anywhere else: not in the speaker's context, not only in the line "
                      "doc, not only as a note in the notebook.",
                      "An item of the line doc's *Opened* section and an open note on a tab each "
                      "name the line's id and point to it",
                      "`ai` for a drawer turn, `ai-draw` for an idea new to the sitting in a kept "
                      "draw (**The line in the AI's graph**, rule 11), which is never queued to a "
                      "clean turn unasked",
                      "`ordo/current.queue` is a projection of the open documents of `lines`, in "
                      "the order of their `rank`, for the page to draw",
                      "the page reads `ordo` alone, and never `lines`",
                      "The speaker starts every sitting, and resumes after its context is "
                      "compacted, by reading `ordo/current` and the open documents of `lines` "
                      "with `ArtifactData`, and trusts them over anything it remembers",
                      "A line is closed only by the principal's answer to it; by the principal's "
                      "own later sentence settling it in terms, the line then closed with that "
                      "sentence quoted in `closed_by` and listed in the action context, so "
                      "that the principal can reopen it; or by the principal dropping it. Never "
                      "because a reader predicts the answer",
                      "No tool reads, orders or sweeps it but `tools/lines.py`, which reads an "
                      "export of it and prints the writes it needs, and nothing else decides how "
                      "a line closes",
                      "where the user has said no such sentence, the line stays open, "
                      "however sure a reading is",
                      "which is a proposal for the user and nothing more"):
            self.assertIn(words, lines)
        for field in ("`id`", "`title`", "`kind`", "`state`", "`ask`", "`why`", "`source`",
                      "`anchors`", "`seal`", "`parent` and `children`", "`answered_by`",
                      "`rank`", "`opened_at` and `touched_at`", "`review_count`", "`origin`"):
            self.assertIn("- " + field, lines)
        for state in ("`open`", "`put`", "`answered`", "`closed`", "`merged`", "`dropped`"):
            self.assertIn(state, lines)
        self.assertIn("`{case, prompt, recommendation}`", lines)
        self.assertIn("`{tab, block, h, words}`", lines)
        example = json.loads(_code(SKILL, "## The open lines"))
        self.assertEqual(set(example), {"id", "title", "kind", "state", "ask", "why", "source",
                                        "anchors", "seal", "parent", "children", "answered_by",
                                        "rank", "opened_at", "touched_at", "review_count",
                                        "origin"})
        self.assertIn("**1 — Read.** Read `ordo/current` and the open documents of `lines` "
                      "first", self.skill)
        self.assertIn("drawn from the open documents of `lines` (**The open lines**), which is "
                      "where each waits", self.skill)

    def test_the_attenuation_says_what_a_tool_holds_and_what_reading_holds(self):
        for words in ("**What holds a clean turn, and what only reading holds.**",
                      "are plain files: each binds a check to an exact text and catches drift, "
                      "and none is a signature, so one written by hand with the right hash "
                      "passes",
                      "**\"None chosen\" is per directory.**",
                      "While the key is unset the guard lets the comparer insert on any tab, and "
                      "its definition alone keeps it off a tab that holds an answer of the AI's.",
                      "**The open lines are held by reading.**",
                      "**The sides of the notebook are held by node, not by block.**",
                      "**The line's rules are held by reading.**",
                      "the reading of every kept draw for ideas new to the sitting, and their "
                      "return to the principal through the session and the page alone",
                      "**An idea from a draw is kept out of the line by reading.**",
                      "nor for good once it is dropped unless the principal states it, or that "
                      "a line of origin `ai-draw` is never queued to a clean turn unasked. What "
                      "counts as one idea, and whether it is new, is the speaker's reading.",
                      "The principal's approval of a question does not show where a phrase of it "
                      "came from"):
            self.assertIn(words, self.skill)


class LineWalk(Walk):
    """The line's commands as the skill writes them: the packet, the leak
    check, the reading of whether the question leads and a clean turn, the
    turn dry-run."""

    def read_as_clear(self, n_dir, approved=T):
        """The record lead.py record writes of a reading that the question does
        not lead, written as a plain file, as an approval is; the reading
        made before the approval."""
        with open(os.path.join(n_dir, "question.md"), "rb") as fh:
            digest = hashlib.sha256(fh.read()).hexdigest()
        with open(os.path.join(n_dir, "lead.json"), "w") as fh:
            json.dump({"tool": "lead.py record", "sha256": digest, "verdict": "does not lead",
                       "read": "2030-01-02T03:00:00Z"}, fh)

    def test_a_question_is_read_before_it_is_shown_and_put_only_so(self):
        """Rule 3 walked: the question checked, a `lead` job done by the
        coordinator with the reader's reply, the hooks' record of its launch,
        the skill's `lead.py record` line, the approval after it, the turn."""
        from hypo import board as gate, brief, inhand
        shutil.copy(os.path.join(TOOLS, "fixtures", "valid.json"),
                    os.path.join(self.scratch, "graph.json"))
        n = os.path.join(self.scratch, "lines", "l1", "1")
        os.makedirs(n)
        values = {"<line>": "l1", "<n>": "1", "<id>": "ti-esti"}
        self.sh(line(SKILL, "packet.py"), values)
        with open(os.path.join(n, "question.md"), "w", encoding="utf-8") as fh:
            fh.write("What is the thing for, and what must it never do?\n")
        self.sh(line(SKILL, "public.py", "question"), values)
        with open(os.path.join(n, "question.md"), "rb") as fh:
            digest = hashlib.sha256(fh.read()).hexdigest()
        # the `lead` job as board.md's table gives its inputs, done by the coordinator
        jid = "s2-b1-1-lead"
        reply = os.path.join(self.scratch, "coordinator", "replies", jid)
        os.makedirs(os.path.dirname(reply))
        with open(reply, "w", encoding="utf-8") as fh:
            fh.write("verdict: does not lead\nreason: It states the case and its ends.\n"
                     "status: ok\n")
        with open(reply, "rb") as fh:
            fingerprint = hashlib.sha256(fh.read()).hexdigest()
        here = gate.Board(None, {}, {}, [])
        writes = gate.init(here, "doc:abc")
        self.store.docs, self.store.versions = {}, {}

        def apply(ws):
            for w in ws:
                key = "%s/%s" % (w["collection"], w["doc_id"])
                self.store.docs[key] = w["data"]
                self.store.versions[key] = self.store.versions.get(key, 0) + 1

        def loaded():
            self.export("speaker")
            return gate.load(os.path.join(self.scratch, "speaker", "board"),
                             os.path.join(self.scratch, "speaker", "versions.json"))
        apply(writes)
        os.makedirs(os.path.join(self.scratch, "speaker"), exist_ok=True)
        written = [w for w in lines(SKILL, "lead.py") if "--question" in w or "--line" in w]
        self.assertEqual([w.split()[1] for w in written],
                         ["job", "record", "led", "aside", "carry"])
        self.export("speaker")
        self.sh(written[0], dict(values, **{"<job id>": jid,
                                            "<the notebook's address>": "doc:abc"}))
        with open(os.path.join(self.scratch, "speaker", "jobs.json")) as fh:
            given = json.load(fh)
        self.assertEqual(given[0]["inputs"]["question_fingerprint"], digest)
        apply(gate.add(loaded(), given, "2020-01-02T03:00:00Z"))
        apply(gate.claim(loaded(), jid, "coordinator", "2020-01-02T03:00:30Z"))
        apply(gate.done(loaded(), jid, "coordinator",
                        {"reply": reply, "fingerprint": fingerprint}, "2020-01-02T03:10:00Z"))
        self.export("speaker")
        # the hooks' record of the launch, under the session's id
        os.makedirs(os.path.join(self.project, ".principal"))
        with open(os.path.join(self.project, ".principal", "notebook.json"), "w") as fh:
            json.dump({"notebook": "doc:abc"}, fh)
        self.env["CLAUDE_CODE_SESSION_ID"] = "sess-1"
        where = inhand.session_dir(brief.brief_dir(os.path.realpath(self.project), self.env),
                                   "sess-1")
        os.makedirs(where)
        with open(os.path.join(where, "launches.json"), "w") as fh:
            json.dump([{"id": "h1", "kind": "principal:question-reader", "description": jid,
                        "at": "2020-01-02T03:01:00Z", "agent_id": "a1",
                        "started": "2020-01-02T03:01:01Z", "ended": "2020-01-02T03:09:00Z"}],
                      fh)
        self.sh(written[1], dict(values, **{"<job id>": jid}))
        with open(os.path.join(n, "lead.json"), encoding="utf-8") as fh:
            reading = json.load(fh)
        self.assertEqual((reading["verdict"], reading["sha256"]), ("does not lead", digest))
        # the card that shows it names its reading, and card.py holds the order
        from hypo import card
        shown = {"next": {"kind": "review", "prompt": "What is the thing for, and what must it "
                          "never do?", "reading": os.path.join(n, "lead.json")}, "updated": T}
        self.assertEqual(card.check(shown), [])
        # a second reading of the same text is refused
        self.sh(written[0], dict(values, **{"<job id>": "s2-b1-2-lead",
                                            "<the notebook's address>": "doc:abc"}), code=1)
        # an approval made before the reading is taken once the reading is clear
        with open(os.path.join(n, "approval.json"), "w") as fh:
            json.dump({"sha256": digest, "approved": "2020-01-02T03:00:00Z"}, fh)
        done = self.sh(line(SKILL, "clean_turn.py", "answer") + " --dry-run", values)
        self.assertIn("What is the thing for", done.stdout)
        # found later to have led: the skill's `lead.py led` line, the turn and the card
        # refuse it, and `aside` cuts the line there
        self.sh(written[2], values)
        self.sh(line(SKILL, "clean_turn.py", "answer") + " --dry-run", values, code=15)
        self.assertTrue(card.check(shown))
        done = self.sh(written[3], values)
        self.assertIn("question(s) 1", done.stdout)
        self.assertEqual(os.listdir(os.path.join(self.scratch, "lines", "l1")), ["held"])
        # the index the skill writes leaves out what the line set aside
        with open(os.path.join(self.scratch, "lines", "l1", "requirement"), "w") as fh:
            fh.write("rotation\n")
        self.sh(line(SKILL, "find"), values)
        with open(os.path.join(self.scratch, "lines", "l1", "index")) as fh:
            listed = fh.read().split()
        self.assertEqual([os.path.basename(f) for f in listed], ["requirement"])

    def test_a_question_from_packet_to_dry_run(self):
        shutil.copy(os.path.join(TOOLS, "fixtures", "valid.json"),
                    os.path.join(self.scratch, "graph.json"))
        n = os.path.join(self.scratch, "lines", "l1", "1")
        os.makedirs(n)
        values = {"<line>": "l1", "<n>": "1", "<id>": "ti-esti"}
        self.sh(line(SKILL, "packet.py"), values)
        self.assertTrue(os.path.exists(os.path.join(n, "packet.md.fingerprint.json")))
        with open(os.path.join(n, "question.md"), "w", encoding="utf-8") as fh:
            fh.write("What is the thing for, and what must it never do?\n")
        self.sh(line(SKILL, "public.py", "question"), values)
        with open(os.path.join(n, "question.md"), "rb") as fh:
            digest = hashlib.sha256(fh.read()).hexdigest()
        with open(os.path.join(n, "approval.json"), "w") as fh:
            json.dump({"sha256": digest, "approved": T}, fh)
        self.read_as_clear(n)
        done = self.sh(line(SKILL, "clean_turn.py", "answer") + " --dry-run", values)
        self.assertIn("--system-prompt-file", done.stdout)
        self.assertIn("What is the thing for", done.stdout)
        drawn = os.path.join(self.scratch, "lines", "l1", "drawn-1")
        os.makedirs(drawn)
        self.sh(line(SKILL, "packet.py").replace("/<n>/", "/drawn-<n>/"), values)
        done = self.sh(line(SKILL, "clean_turn.py", "draw") + " --dry-run", values)
        self.assertIn("A relationship that continues", done.stdout)
        done = self.sh(line(SKILL, "clean_turn.py", "probe") + " --dry-run")
        self.assertIn("--tools", done.stdout)

    def test_the_second_question_carries_the_first_s_answer_of_record(self):
        """B2 walked: question 1 drawn (the harness mocked), question 2's
        packet cut by the skill's line holds question 1 and its first kept
        draw, and a redraw signal from that answer reaches the drawer."""
        import shlex
        import clean_turn
        from test_clean_turn import Harness
        shutil.copy(os.path.join(TOOLS, "fixtures", "valid.json"),
                    os.path.join(self.scratch, "graph.json"))
        base = os.path.join(self.scratch, "lines", "l1")

        def put(n, words):
            values = {"<line>": "l1", "<n>": str(n), "<id>": "ti-esti"}
            os.makedirs(os.path.join(base, str(n)))
            self.sh(line(SKILL, "packet.py"), values)
            with open(os.path.join(base, str(n), "question.md"), "w", encoding="utf-8") as fh:
                fh.write(words)
            self.sh(line(SKILL, "public.py", "question"), values)
            with open(os.path.join(base, str(n), "question.md"), "rb") as fh:
                digest = hashlib.sha256(fh.read()).hexdigest()
            with open(os.path.join(base, str(n), "approval.json"), "w") as fh:
                json.dump({"sha256": digest, "approved": T}, fh)
            self.read_as_clear(os.path.join(base, str(n)))
            return values

        values = put(1, "What is the morning for, and what must it never do?\n")
        argv = shlex.split(self.fill(line(SKILL, "clean_turn.py", "answer"), values))[1:]
        h = Harness(answers=("The morning is for the plants, before anything is sent.",
                             "The morning is for the post.", "The morning is for rest."))
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(clean_turn.main(argv, runner=h), 0)
        values = put(2, "How is the morning kept?\n")
        with open(os.path.join(base, "2", "packet.md"), encoding="utf-8") as fh:
            pairs = __import__("packet").parse(fh.read())
        self.assertEqual(pairs[-1], ("What is the morning for, and what must it never do?",
                                     "The morning is for the plants, before anything is sent."))
        self.assertNotIn("The morning is for the post.", str(pairs))
        done = self.sh(line(SKILL, "clean_turn.py", "answer") + " --dry-run", values)
        self.assertIn("The morning is for the plants", done.stdout)
        self.assertTrue(done.stdout.rstrip().endswith("How is the morning kept?"))
        os.makedirs(os.path.join(base, "drawn-1"))
        self.sh(line(SKILL, "packet.py").replace("/<n>/", "/drawn-<n>/"),
                dict(values, **{"<n>": "1"}))
        drawn = line(SKILL, "clean_turn.py", "draw") + ' --from "The morning is for the" --dry-run'
        done = self.sh(drawn, {"<line>": "l1", "<n>": "1"})
        self.assertIn("Draw from the answer that opens: The morning is for the", done.stdout)


class PageTest(unittest.TestCase):
    """The page the round is put on, read as text, and the contract the skill
    gives for its four documents."""

    @classmethod
    def setUpClass(cls):
        with open(PAGE, encoding="utf-8") as fh:
            cls.page = fh.read()
        cls.script = cls.page[cls.page.index("<script>"):cls.page.index("</script>")]
        text = flat(SKILL)
        cls.contract = text[text.index("## The page"):text.index("## Procedure")]

    def test_the_contract_gives_the_pending_action_s_fields(self):
        for words in ("`put_at`, an ISO time with its offset, when this action was put",
                      "restating, rewording or adding to the same pending action",
                      "counted only where it is not earlier than `put_at`",
                      "`resolved_at`, an ISO time", "`asks`, `false` on an action that asks nothing",
                      "a second bell during the hold neither ends it nor drops the first bell's items",
                      "whether a hold lapses when no sitting is open is an open line for the user",
                      "\"After this: the <bell name> office\"",
                      "the very next thing the card shows is the carried office's first item"):
            self.assertIn(words, self.contract)
        skill = flat(SKILL)
        self.assertIn("An action already put and still pending when a bell rings is not "
                      "replaced by the office", skill)
        self.assertIn("An action already put and still pending when a bell rings stays on the "
                      "card", skill)
        self.assertIn("`next.put_at` and `next.resolved_at`, the time in a mark", skill)

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
        self.assertEqual(len(docs), 4)
        for at in docs:
            close = self.script.index(")", at)
            self.assertTrue(self.script[close + 1:].startswith(".onSnapshot("),
                            self.script[at - 7:close + 14])
        # nothing goes out
        # "fetch" as a word: the agenda's field `fetched` is data, not a call
        self.assertIsNone(re.search(r"\bfetch\b", self.script))
        for word in ("XMLHttpRequest", "sendBeacon", "WebSocket", "EventSource",
                     "postMessage", "import(", "window.open", "location", "localStorage",
                     "sessionStorage", "indexedDB", "document.cookie", "eval", "Function("):
            self.assertNotIn(word, self.script)
        # no control, made in the source or at run time, in any quoting or case, but the
        # one button at the foot that goes back to the top (test_page_top), wired once by
        # its property and focusing the main landmark, which alone takes a tabindex
        page = self.page
        for allowed in ('<button type="button" class="top" id="top">', '<main id="main" tabindex="-1">',
                        'if (top) top.onclick = toTop;'):
            self.assertEqual(page.count(allowed), 1, allowed)
            page = page.replace(allowed, "")
        controls = r"(?:button|input|textarea|select|form|option|dialog|a)"
        self.assertIsNone(re.search(r"<\s*%s\b" % controls, page, re.I))
        # one native details element, the waiting list's card, closed in the source and
        # never opened or closed by the script
        self.assertEqual(re.findall(r"<\s*details\b[^>]*>", self.page, re.I),
                         ['<details class="panel wait" id="wait" hidden>'])
        self.assertIsNone(re.search(r"\.open\b|Attribute\(\s*[\"'`]open", self.script))
        self.assertIsNone(re.search(r"[\"'`]\s*(?:details|summary)\s*[\"'`]", self.script,
                                    re.I))
        self.assertIsNone(re.search(r"[\"'`]\s*%s\s*[\"'`]" % controls, self.script, re.I))
        for word in ("onclick", "addEventListener", "contenteditable", "contentEditable",
                     "innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "tabindex"):
            self.assertNotIn(word.lower(), page.lower())
        self.assertNotIn("href", self.script)
        made = re.findall(r"\bel\(\s*([\"'`])(\w+)\1", self.script)
        self.assertTrue(made)
        self.assertLessEqual({t for _, t in made}, {"p", "span", "b", "li", "div", "ul"})
        self.assertEqual(re.findall(r"createElement\(\s*(\w+)\s*\)", self.script), ["tag"])

    def test_the_session_s_action_waits_while_an_office_is_unresolved(self):
        # which of the office and the session's action leads is read by behaviour
        # (PageBehaviourTest: rung, aside, held), not by the shape of renderNext (RN5)
        office = self.body("renderOffice")
        self.assertIn('$("next-prompt").textContent = it.label;', office)
        self.assertNotIn('$("next-prompt").textContent = str(n', office)
        self.assertIn("var it = st.unres[0]", office)
        # a taken item first (S11)
        self.assertRegex(self.body("unresolved"),
                         r'return items\.filter\(function \(it\) \{ return it\.state === "taken"; \}\)'
                         r'\s*\.concat\(items\.filter\(function \(it\) \{ return it\.state === "open"; \}\)\)')
        # an item run by the session never drives the card or the notice
        now = self.body("officeNow")
        self.assertIn("var mine = all.filter(function (it) { return !it.session; }), unres = unresolved(mine);", now)
        self.assertIn('session: o.by === "session"', self.body("officeItems"))

    def test_an_office_set_aside_names_the_rung_bell(self):
        now = self.body("officeNow")
        self.assertIn("var od = current && current.office_deferred,", now)
        self.assertIn('str(od.bell) === str(lr.rung.b.time).replace(":", "")', now)
        self.assertIn("lr.rung && unres.length && od", now)
        aside = self.body("renderAside")
        self.assertIn("st.unres.map(", aside)
        self.assertIn("str(st.aside.reason)", aside)
        self.assertIn('"Its office is set aside for now; "', self.body("renderNotice"))
        self.assertIn("Office set aside, still due", self.page)

    def test_round_three_text_level_checks(self):
        """S8: where node is not installed, the mutations a structural read can catch."""
        now = self.body("officeNow")
        # B1: the aside counts only from the moment the named bell rang this Rule day
        self.assertIn("odAt = od && typeof od === \"object\" ? parseWhen(od.since) : null;", now)
        self.assertIn("lr.rung && unres.length && odAt &&", now)
        self.assertIn("new Date(rd.y, rd.mo, rd.d, 0, lr.rung.m) <= odAt", now)
        # the notice is hidden only when no item of the principal's is unresolved
        self.assertRegex(self.body("renderNotice"),
                         r'if \(!st\.unres\.length\) \{ band\.hidden = true; return; \}')
        self.assertEqual(self.script.count("band.hidden = true"), 1)
        panel = self.body("renderPanel")
        self.assertIn("end = new Date(now.getTime() + 48 * 3600 * 1000)", panel)
        self.assertIn("var isNext = firstBell; firstBell = false;", panel)
        self.assertIn('isNext ? "Next bell" : "Bell"', panel)
        self.assertIn('if (i === 0 && !st.left.length) box.appendChild(el("p", "quiet", "The office is '
                      'complete."));', panel)
        self.assertIn('!agenda ? "No calendar has been read."', panel)
        self.assertIn("st.left.concat(st.all.filter(function (x) { return x.session && "
                      "!(x.state === \"open\" || x.state === \"taken\"); }))", panel)
        self.assertIn("if (en <= now || s > end) return null;", self.body("upcomingEvents"))
        self.assertIn("if (at > now && at <= end)", self.body("upcomingBells"))
        # only bell- keys are read; which bells' items are read is behaviour (RN5)
        self.assertIn("ticks[it.key]", now)
        self.assertEqual(len(re.findall(r"\bticks\[", self.script)), 1)
        self.assertIsNone(re.search(r"Object\.keys\(\s*ticks", self.script))
        # a session item never makes the card
        self.assertIn("if (st.unres.length && !st.aside) renderOffice(st);", self.body("renderNext"))
        self.assertIn("var it = st.unres[0]", self.body("renderOffice"))
        # the recommendation: its own block, never on a question
        sess = self.body("renderSession")
        self.assertIn('kindOf(n.kind) === "question" ? [] : texts(n.recommendation)', sess)
        self.assertIn('$("next-rec").hidden = $("next-rec-label").hidden = !rec.length;', sess)
        self.assertLess(self.page.index('id="next-case"'), self.page.index('id="next-prompt"'))
        self.assertLess(self.page.index('id="next-prompt"'), self.page.index('id="next-rec"'))
        # the action context's appended records, after a divider each, and the first
        # writing's time under the heading
        ctx = self.body("renderContext") if "function renderContext" in self.script else self.script
        self.assertIn('$("ctx-at").textContent = w ? "Written " + w : "";', ctx)
        self.assertIn("arr(c.log).forEach(", ctx)
        self.assertIn('rec.appendChild(el("div", "logsep", label));', ctx)
        self.assertLess(self.page.index('id="ctx-at"'), self.page.index('id="ctx-log"'))
        self.assertIn('$("wait-sum").textContent = "Waiting, in order (" + list.length + ")";',
                      self.script)
        self.assertIn("The helpers' action context", self.page)
        # db is held in no alias: every mention is one of these
        rest = re.sub(r'var db = null;|db = await window\.claude\.use\("db"\);|'
                      r'"db"|!db\b|\bdb\.doc\(', "", self.script)
        self.assertIsNone(re.search(r"\bdb\b", re.sub(r"//[^\n]*", "", rest)))

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
            "getElementById", "getFullYear", "getHours", "getMinutes", "getMonth", "getTime",
            "hidden", "indexOf", "isArray", "join", "keys", "length", "map", "push",
            "removeChild", "replace", "round", "setAttribute", "slice", "some", "sort",
            "stringify", "test", "textContent", "toLowerCase",
            # the store's read
            "claude", "use", "doc", "onSnapshot", "data", "exists", "metadata", "fromCache",
            "code",
            # what the page computes
            "b", "m", "ds", "rd", "md", "mins", "wd", "date", "key", "v", "state", "rung",
            "unres", "applied", "all", "left", "aside", "session", "now", "at", "ev", "allDay",
            "y", "mo", "d", "hold", "carry",
            # the button back to the top (test_page_top)
            "onclick", "focus", "scrollTo", "matchMedia", "matches"}
        given = {"context", "next", "queue", "background", "updated",
                 "heading", "paragraphs", "for", "against", "prediction", "notes", "who", "text",
                 "kind", "line", "case", "prompt", "how", "deferred", "reason", "title",
                 "recommendation", "day_start", "days", "bells", "time", "time_by_day", "name", "office", "label",
                 "except_days", "off_from", "off_to", "ask", "by",
                 "office_deferred", "since", "bell", "put_at", "resolved_at", "asks",
                 "events", "start", "end", "all_day", "fetched", "log"}
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
               # `r` names a record of the context's log inside renderContext
               "rule": set(re.findall(r"\br\.(\w+)", self.script.replace(
                   self.body("renderContext"), ""))),
               "agenda": set(re.findall(r"\b(?:ag|agenda)\.(\w+)", self.script))}
        self.assertEqual(top["current"], {"context", "next", "queue", "background", "updated",
                                          "office_deferred"})
        self.assertEqual(top["rule"], {"day_start", "days", "bells"})
        self.assertEqual(top["agenda"], {"events", "fetched"})
        nested = ("heading", "paragraphs", "for", "against", "prediction", "notes",
                  "predicted", "diverged", "addressed", "who", "text",
                  "kind", "line", "case", "prompt", "how", "deferred", "reason", "title",
                  "recommendation", "time", "time_by_day", "name", "office", "label", "except_days",
                  "off_from", "off_to", "ask", "by", "reason", "since", "bell",
                  "start", "end", "all_day", "at", "log")
        for field in nested:
            self.assertTrue(re.search(r"\.%s\b|\"%s\"" % (field, field), self.script), field)
        for field in sorted(top["current"] | top["rule"] | top["agenda"]) + list(nested):
            self.assertIn("`%s`" % field, self.contract, field)
        for doc in ("`ordo/current`", "`ordo/rule`", "`ordo/ticks-<day>`", "`ordo/agenda`"):
            self.assertIn(doc, self.contract)
        self.assertIn('db.doc("ordo/ticks-" + day)', self.script)
        self.assertIn('db.doc("ordo/agenda")', self.script)

    def test_the_contract_gives_the_panel_the_session_s_items_and_the_set_aside_office(self):
        for words in ("It reads four documents of the collection `ordo` in its store, and the "
                      "speaker writes all four",
                      "on a phone the panel sits under the next action",
                      "\"This bell\"", "\"Next 48 hours\"",
                      "a second card holds only \"Waiting, in order (N)\", the queue (rule 10), as "
                      "a native details element closed by default, which the page never opens or "
                      "closes on a redraw",
                      "as \"Waiting, in order (N)\" in its own card below the context panel, a "
                      "details element closed by default",
                      "`at`, the ISO time the context was first written, shown as a quiet line "
                      "\"Written HH:MM\" under the heading",
                      "each after a divider labelled \"Added HH:MM\", with the date where it is "
                      "not today",
                      "which the speaker writes at each sync, after reading the principal's calendar",
                      "and `by`, `\"session\"` where the item is the session's to run",
                      "the principal never reports it",
                      "\"Office set aside, still due\"",
                      "Once a later bell rings, or every item of the principal's in that bell is "
                      "resolved, the field is ignored, and so it is where `since` does not parse or "
                      "is before that bell rang today, as on a later day; the speaker removes it in "
                      "its first write after a later bell has rung or the Rule's day has turned.",
                      "It is the principal's private data like `ordo/rule`.",
                      "where `ordo/current` does not yet exist, as at the first sitting on a page, "
                      "the speaker first `set`s it with `updated` alone",
                      "A sync is an office item of the Rule's with `by: \"session\"` at which the "
                      "speaker reads the principal's calendar for the next forty-eight hours and "
                      "writes `ordo/agenda`.",
                      "writes no agenda and says so in the action context, and the panel then says "
                      "\"No calendar has been read.\"",
                      "the speaker's explanation, its answer to a question of the principal's, or "
                      "its report of what was done, the brief and the close among them, a result "
                      "the principal should know, an error, a helper's finding and a thing owed by "
                      "the principal included (rule 10)",
                      "`prediction` never holds the prediction of the action now put",
                      "the question put on the page as an action (rule 10)",
                      "`recommendation`, a string or a list of strings, the speaker's "
                      "recommendation, shown under \"Recommendation\" after the prompt and only "
                      "where set: every review of mechanism carries it here, its "
                      "own field and never in the case, and a question, or a review that states or "
                      "changes a principle, never carries one, the page showing none on a "
                      "`question`.",
                      "a weight for example, is kept as a plain field of the same document beside "
                      "the marks, under a key that does not begin with `bell-`"):
            self.assertIn(words, self.contract)
        current = json.loads(re.search(r"\*\*`ordo/current`\*\*.*?```json(.*?)```", self.contract)
                             .group(1))
        self.assertEqual(set(current["office_deferred"]), {"reason", "since", "bell"})
        self.assertRegex(current["office_deferred"]["bell"], r"^\d{4}$")
        agenda = json.loads(re.search(r"\*\*`ordo/agenda`\*\*.*?```json(.*?)```", self.contract)
                            .group(1))
        self.assertEqual(set(agenda), {"events", "fetched"})
        rule = json.loads(re.search(r"\*\*`ordo/rule`\*\*.*?```json(.*?)```", self.contract)
                          .group(1))
        self.assertIn({"label": "Copy out the seed list", "by": "session"}, rule["bells"][0]["office"])

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
        for words in ("The page is display only: it has no input and one button, at its foot, that "
                      "goes back to the top and does nothing else; its source holds no data, and "
                      "it writes nothing.",
                      "and the speaker writes all four, the day's marks included",
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
    if (subs["ordo/agenda"]) subs["ordo/agenda"](snap(sc.agenda));
    // the latest subscription to a day's marks: with a day_start the page subscribes again once the Rule arrives
    const ticks = Object.keys(subs).filter(k => k.startsWith("ordo/ticks-")).pop();
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
                       "office": ["Water the plants", "Feed the goldfish", "Wind the clock",
                                  {"label": "Copy the list", "by": "session"}]},
                      {"time": "21:00", "name": "Evening", "office": ["Cover the seedlings"]}]}
    CURRENT = {"next": {"kind": "question", "prompt": "Is watering still first?",
                        "items": ["CHECKLIST-ITEM"], "recommendation": "REC-ON-A-QUESTION",
                        "deferred": {"prompt": "Write the letter.", "reason": "A passing feeling.",
                                     "kind": "nonsense"}},
               "queue": [{"kind": "review", "title": "Review the rows"}],
               "updated": "2030-01-02T09:00:00Z"}
    NOW = [2030, 0, 2, 9, 0]
    ASIDE = {"reason": "The letter first.", "since": "2030-01-02T08:40:00Z", "bell": "0800"}
    LAST = {"reason": "Later.", "since": "2030-01-02T21:30:00Z", "bell": "2100"}
    KEYS = ("bell-0800-water-the-plants", "bell-0800-feed-the-goldfish",
            "bell-0800-wind-the-clock")
    SESSION_KEY = "bell-0800-copy-the-list"
    #: an invented calendar, read at 08:50 on the day of NOW (the harness runs in UTC)
    AGENDA = {"events": [
        {"start": "2030-01-02T08:30:00Z", "end": "2030-01-02T10:00:00Z", "title": "An example visit"},
        {"start": "2030-01-02T06:00:00Z", "end": "2030-01-02T07:00:00Z", "title": "An example ended"},
        {"start": "2030-01-04T08:30:00Z", "end": "2030-01-04T08:45:00Z", "title": "An example near"},
        {"start": "2030-01-04T10:00:00Z", "end": "2030-01-04T11:00:00Z", "title": "An example far"},
        {"start": "2030-01-03", "end": "2030-01-04", "title": "An example fair", "all_day": True}],
        "fetched": "2030-01-02T08:50:00Z"}
    LOGGED = {"heading": "Your answer, as read", "paragraphs": ["FIRST-WRITING"],
              "at": "2030-01-02T08:55:00Z",
              "log": [{"at": "2030-01-02T08:58:00Z", "paragraphs": ["LOG-ONE"]},
                      {"at": "2030-01-02T08:59:00Z", "paragraphs": []},
                      {"at": "2030-01-01T20:00:00Z", "paragraphs": "LOG-STRING"}]}
    PUT_BEFORE = "2030-01-02T07:50:00Z"
    #: RULE with a noon bell between its two
    RULE3 = {"bells": [RULE["bells"][0], {"time": "12:00", "name": "Noon", "office": ["Fold the post"]},
                       RULE["bells"][1]]}

    @classmethod
    def put(cls, at, **more):
        """CURRENT with its action stamped as put at `at`, and any more fields of `next`."""
        return dict(cls.CURRENT, next=dict(cls.CURRENT["next"], put_at=at, **more))

    REVIEW = {"next": {"kind": "review", "prompt": "Is the new wording right?",
                       "recommendation": ["Keep the shorter wording.", "It reads plainer."]},
              "updated": "2030-01-02T09:00:00Z"}

    @classmethod
    def setUpClass(cls):
        cls.node = shutil.which("node")
        if not cls.node:
            sys.stderr.write("\n*** PageBehaviourTest SKIPPED: node is not installed; run again "
                             "under `nix shell nixpkgs#nodejs` to run the page's behaviour "
                             "tests ***\n")
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
            # the office set aside: naming the rung bell, an earlier bell, and none left
            "aside": {"now": cls.NOW, "current": dict(cls.CURRENT, office_deferred=cls.ASIDE),
                      "rule": cls.RULE, "ticks": {k[2]: "taken " + T, k[0]: D}},
            "aside_earlier": {"now": [2030, 0, 2, 22, 0],
                              "current": dict(cls.CURRENT, office_deferred=cls.ASIDE),
                              "rule": cls.RULE, "ticks": None},
            "aside_none": {"now": cls.NOW, "current": dict(cls.CURRENT, office_deferred=cls.ASIDE),
                           "rule": cls.RULE,
                           "ticks": {k[0]: D, k[1]: "notdue " + D, k[2]: "overruled " + D}},
            # B1: set aside yesterday, the same bell rings again today
            "aside_next_day": {"now": [2030, 0, 3, 9, 0],
                               "current": dict(cls.CURRENT, office_deferred=cls.ASIDE),
                               "rule": cls.RULE, "ticks": None},
            "aside_last_bell": {"now": [2030, 0, 2, 22, 0], "rule": cls.RULE, "ticks": None,
                                "current": dict(cls.CURRENT, office_deferred=cls.LAST)},
            "aside_last_bell_next_day": {"now": [2030, 0, 3, 22, 0], "rule": cls.RULE,
                                         "ticks": None,
                                         "current": dict(cls.CURRENT, office_deferred=cls.LAST)},
            "aside_bad_since": {"now": cls.NOW, "rule": cls.RULE, "ticks": None,
                                "current": dict(cls.CURRENT, office_deferred=dict(
                                    cls.ASIDE, since="this morning"))},
            # S8: the calendar, the office complete, a session item done, a measured value
            "agenda": {"now": cls.NOW, "current": cls.REVIEW, "rule": cls.RULE,
                       "agenda": cls.AGENDA,
                       "ticks": {k[0]: D, k[1]: D, k[2]: D, cls.SESSION_KEY: D,
                                 "water_used": "MEASURED-2-L"}},
            "session_overruled": {"now": cls.NOW, "current": cls.CURRENT, "rule": cls.RULE,
                                  "ticks": {cls.SESSION_KEY: "overruled " + D}},
            # the pending action through a bell: put before it rang, resolved, put after,
            # with the office set aside, a placeholder that asks nothing, an item taken
            "held": {"now": cls.NOW, "rule": cls.RULE, "ticks": None,
                     "current": cls.put(cls.PUT_BEFORE)},
            "held_resolved": {"now": cls.NOW, "rule": cls.RULE, "ticks": None,
                              "current": cls.put(cls.PUT_BEFORE,
                                                 resolved_at="2030-01-02T08:30:00Z")},
            "held_after": {"now": cls.NOW, "rule": cls.RULE, "ticks": None,
                           "current": cls.put("2030-01-02T08:30:00Z")},
            "held_aside": {"now": cls.NOW, "rule": cls.RULE,
                           "ticks": {k[2]: "taken " + T, k[0]: D},
                           "current": dict(cls.put(cls.PUT_BEFORE), office_deferred=cls.ASIDE)},
            "held_placeholder": {"now": cls.NOW, "rule": cls.RULE, "ticks": None,
                                 "current": dict(cls.CURRENT, next={
                                     "kind": "work", "prompt": "A helper is at work.",
                                     "asks": False, "put_at": cls.PUT_BEFORE})},
            "held_taken": {"now": cls.NOW, "rule": cls.RULE, "ticks": {k[1]: "taken " + T},
                           "current": cls.put(cls.PUT_BEFORE)},
            # B2: the same pending action restated keeps its put_at, and still holds
            "held_rewritten": {"now": cls.NOW, "rule": cls.RULE, "ticks": None,
                               "current": dict(cls.put(cls.PUT_BEFORE), next=dict(
                                   cls.put(cls.PUT_BEFORE)["next"],
                                   prompt="Is watering the plants still first, put plainly?",
                                   how="A quiet line added."))},
            # B4: a second bell during the hold; then resolved
            "held_two": {"now": [2030, 0, 2, 12, 20], "rule": cls.RULE3, "ticks": None,
                         "current": cls.put(cls.PUT_BEFORE)},
            "held_two_resolved": {"now": [2030, 0, 2, 12, 20], "rule": cls.RULE3, "ticks": None,
                                  "current": cls.put(cls.PUT_BEFORE,
                                                     resolved_at="2030-01-02T12:10:00Z")},
            "held_two_resolved_noon_done": {"now": [2030, 0, 2, 12, 20], "rule": cls.RULE3,
                                            "ticks": {"bell-1200-fold-the-post": D},
                                            "current": cls.put(cls.PUT_BEFORE,
                                                               resolved_at="2030-01-02T12:10:00Z")},
            # RN2: one carried item taken, then done; the hold resumes
            "held_taken_done": {"now": cls.NOW, "rule": cls.RULE, "ticks": {k[1]: D},
                                "current": cls.put(cls.PUT_BEFORE)},
            "held_two_noon_done": {"now": [2030, 0, 2, 12, 20], "rule": cls.RULE3,
                                   "ticks": {"bell-1200-fold-the-post": D},
                                   "current": cls.put(cls.PUT_BEFORE)},
            # put exactly at the bell, a put_at that does not parse, resolved before it was put
            "held_at_bell": {"now": cls.NOW, "rule": cls.RULE, "ticks": None,
                             "current": cls.put("2030-01-02T08:00:00Z")},
            "held_bad_put": {"now": cls.NOW, "rule": cls.RULE, "ticks": None,
                             "current": cls.put("this morning")},
            "held_res_before": {"now": cls.NOW, "rule": cls.RULE, "ticks": None,
                                "current": cls.put(cls.PUT_BEFORE,
                                                   resolved_at="2030-01-02T07:40:00Z")},
            # B1, as built and left open: an action pending from the day before still holds
            "held_yesterday": {"now": cls.NOW, "rule": cls.RULE, "ticks": None,
                               "current": cls.put("2030-01-01T22:40:00Z")},
            # an action of any kind that asks nothing never holds
            "held_question_asks_nothing": {"now": cls.NOW, "rule": cls.RULE, "ticks": None,
                                           "current": cls.put(cls.PUT_BEFORE, asks=False)},
            # the action context appended to before the next answer
            "logged": {"now": cls.NOW, "rule": cls.RULE, "ticks": None,
                       "current": dict(cls.CURRENT, context=cls.LOGGED)},
        }
        # N6: a zone not UTC, where the bell's local 08:00 is 13:00Z
        zoned = {"held_zoned": {"now": cls.NOW, "rule": cls.RULE, "ticks": None,
                                "current": cls.put("2030-01-02T12:50:00Z")},
                 "after_zoned": {"now": cls.NOW, "rule": cls.RULE, "ticks": None,
                                 "current": cls.put("2030-01-02T13:10:00Z")}}
        cls.res = cls.run_node(scenarios, "UTC")
        cls.res.update(cls.run_node(zoned, "America/New_York"))

    @classmethod
    def run_node(cls, scenarios, tz):
        with tempfile.TemporaryDirectory() as tmp:
            paths = []
            for name, data in (("page.js", cls.script), ("hidden.json", json.dumps(cls.hidden)),
                               ("scenarios.json", json.dumps(scenarios)),
                               ("harness.js", HARNESS)):
                with open(os.path.join(tmp, name), "w", encoding="utf-8") as fh:
                    fh.write(data)
                paths.append(os.path.join(tmp, name))
            done = subprocess.run([cls.node, paths[3]] + paths[:3], capture_output=True,
                                  text=True, timeout=60, env=dict(os.environ, TZ=tz))
        if done.returncode:
            raise AssertionError(done.stderr)
        return json.loads(done.stdout)

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
            self.assertLessEqual(set(out["made"]), {"p", "span", "b", "li", "div", "ul", "#text"},
                                 name)

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
        self.assertIn("Next bell", self.text("quiet", "panel-list"))
        self.assertIn("Morning", self.text("quiet", "panel-list"))
        self.assertEqual(self.text("quiet", "panel-cal"), "No calendar has been read.")
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


    def test_the_waiting_list_is_its_own_card_with_a_count(self):
        for name in ("quiet", "rung"):
            self.assertTrue(self.shown(name, "wait"), name)
            self.assertIn("Review the rows", self.text(name, "wait-list"))
            self.assertEqual(self.text(name, "wait-sum"), "Waiting, in order (1)")

    def test_the_action_context_shows_its_time_and_its_appended_records(self):
        self.assertTrue(self.shown("logged", "ctx-at"))
        self.assertEqual(self.text("logged", "ctx-at"), "Written 08:55")
        log = self.text("logged", "ctx-log")
        self.assertIn("Added 08:58LOG-ONE", log)
        self.assertIn("LOG-STRING", log)
        self.assertIn("2030-01-01", log)
        self.assertEqual(log.count("Added"), 2)
        self.assertLess(log.index("LOG-ONE"), log.index("LOG-STRING"))
        self.assertFalse(self.shown("rung", "ctx-at"))

    def test_an_item_run_by_the_session_is_only_in_the_panel(self):
        self.assertIn("Copy the list · run by the session, open", self.text("rung", "panel-bell"))
        self.assertNotIn("Copy the list", self.text("rung", "office-then"))
        self.assertNotIn("Copy the list", self.text("rung", "bell-msg"))
        # the principal's items resolved: the session's action shows though one of its items is open
        self.assertEqual(self.text("resolved", "next-prompt"), "Is watering still first?")
        self.assertFalse(self.shown("resolved", "bell"))

    def test_an_office_set_aside_shows_the_session_s_action_with_the_office_under_it(self):
        self.assertEqual(self.text("aside", "next-prompt"), "Is watering still first?")
        self.assertEqual(self.text("aside", "next-kind"), "question")
        self.assertFalse(self.shown("aside", "office-after"))
        self.assertTrue(self.shown("aside", "office-aside"))
        self.assertEqual(self.text("aside", "office-aside-items"),
                         "Wind the clock (under way) · Feed the goldfish")
        self.assertEqual(self.text("aside", "office-aside-reason"), "The letter first.")
        self.assertTrue(self.shown("aside", "next-deferred"))
        self.assertTrue(self.shown("aside", "bell"))
        self.assertIn("set aside for now; 2 of 3 office items still due",
                      self.text("aside", "bell-msg"))
        # the panel's "This bell" is unchanged by it
        self.assertIn("Wind the clock · under way", self.text("aside", "panel-bell"))

    def test_an_office_set_aside_lapses_with_a_later_bell_or_an_office_done(self):
        self.assertEqual(self.text("aside_earlier", "next-prompt"), "Cover the seedlings")
        self.assertFalse(self.shown("aside_earlier", "office-aside"))
        self.assertIn("not yet taken up", self.text("aside_earlier", "bell-msg"))
        self.assertEqual(self.text("aside_none", "next-prompt"), "Is watering still first?")
        self.assertFalse(self.shown("aside_none", "office-aside"))
        self.assertFalse(self.shown("aside_none", "bell"))

    def test_round_three_b1_an_aside_holds_only_the_day_it_was_set(self):
        for name in ("aside_next_day", "aside_bad_since"):
            self.assertEqual(self.text(name, "next-prompt"), "Water the plants", name)
            self.assertFalse(self.shown(name, "office-aside"), name)
            self.assertNotIn("set aside", self.text(name, "bell-msg"), name)
        self.assertEqual(self.text("aside_last_bell", "next-prompt"), "Is watering still first?")
        self.assertTrue(self.shown("aside_last_bell", "office-aside"))
        self.assertEqual(self.text("aside_last_bell_next_day", "next-prompt"),
                         "Cover the seedlings")
        self.assertFalse(self.shown("aside_last_bell_next_day", "office-aside"))

    def test_a_pending_action_put_before_the_bell_holds_the_card(self):
        self.assertEqual(self.text("held", "next-prompt"), "Is watering still first?")
        self.assertEqual(self.text("held", "next-kind"), "question")
        self.assertTrue(self.shown("held", "office-next"))
        self.assertEqual(self.text("held", "office-next-label"), "After this: the Morning office")
        self.assertEqual(self.text("held", "office-next-items"),
                         "Water the plants · Feed the goldfish · Wind the clock")
        self.assertEqual(self.text("held", "office-next-meta"), "Morning rang 08:00.")
        self.assertTrue(self.shown("held", "bell"))
        self.assertIn("Morning rang at 08:00. Its office follows this action.",
                      self.text("held", "bell-msg"))
        self.assertFalse(self.shown("held", "office-after"))
        self.assertFalse(self.shown("held", "office-aside"))
        self.assertFalse(self.shown("held", "office-tell"))
        self.assertTrue(self.shown("held", "next-deferred"))
        self.assertIn("Wind the clock", self.text("held", "panel-bell"))

    def test_a_pending_action_resolved_or_put_after_the_bell_gives_way_to_the_office(self):
        for name in ("held_resolved", "held_after", "held_taken", "held_at_bell", "held_bad_put",
                     "held_question_asks_nothing", "after_zoned"):
            self.assertEqual(self.text(name, "next-kind"), "office", name)
            self.assertFalse(self.shown(name, "office-next"), name)
            self.assertTrue(self.shown(name, "office-after"), name)
            self.assertNotIn("follows this action", self.text(name, "bell-msg"), name)
        self.assertEqual(self.text("held_resolved", "next-prompt"), "Water the plants")
        self.assertEqual(self.text("held_after", "next-prompt"), "Water the plants")
        self.assertEqual(self.text("held_taken", "next-prompt"), "Feed the goldfish")
        for name in ("held_at_bell", "held_bad_put", "held_question_asks_nothing", "after_zoned"):
            self.assertEqual(self.text(name, "next-prompt"), "Water the plants", name)

    def test_a_pending_action_restated_resolved_too_early_or_from_yesterday_still_holds(self):
        for name in ("held_rewritten", "held_res_before", "held_yesterday", "held_zoned"):
            self.assertNotEqual(self.text(name, "next-kind"), "office", name)
            self.assertTrue(self.shown(name, "office-next"), name)
            self.assertEqual(self.text(name, "office-next-label"),
                             "After this: the Morning office", name)
        self.assertEqual(self.text("held_rewritten", "next-prompt"),
                         "Is watering the plants still first, put plainly?")

    def test_the_panel_and_the_notice_read_the_carried_bells(self):
        for name in ("held_two", "held_two_resolved_noon_done", "held_two_noon_done"):
            panel = self.text(name, "panel-bell")
            self.assertIn("Morning · rang 08:00", panel, name)
            self.assertIn("Noon · rang 12:00", panel, name)
            self.assertLess(panel.index("Morning"), panel.index("Noon"), name)
            self.assertIn("Water the plants", panel, name)
            self.assertNotIn("The office is complete.", panel, name)
        self.assertIn("Fold the post", self.text("held_two", "panel-bell"))
        self.assertNotIn("Fold the post", self.text("held_two_noon_done", "panel-bell"))
        msg = self.text("held_two_resolved_noon_done", "bell-msg")
        self.assertEqual(msg, "Noon rang at 12:00. 3 of 4 office items left. "
                              "Counted over the Morning and Noon offices.")
        self.assertEqual(self.text("held_two_resolved_noon_done", "next-prompt"), "Water the plants")
        # resolved with nothing left of Noon's: the latest bell alone is not named
        self.assertEqual(self.text("held_two_resolved", "bell-msg"),
                         "Noon rang at 12:00. The office is not yet taken up. "
                         "Counted over the Morning and Noon offices.")
        # a carry of the latest bell alone reads as before
        self.assertEqual(self.text("held_resolved", "bell-msg"),
                         "Morning rang at 08:00. Its office is not yet taken up.")

    def test_a_hold_resumes_once_a_taken_item_is_done(self):
        self.assertEqual(self.text("held_taken_done", "next-prompt"), "Is watering still first?")
        self.assertEqual(self.text("held_taken_done", "office-next-items"),
                         "Water the plants · Wind the clock")

    def test_a_second_bell_during_a_hold_keeps_the_first_bell_s_office(self):
        self.assertEqual(self.text("held_two", "next-prompt"), "Is watering still first?")
        self.assertEqual(self.text("held_two", "office-next-label"),
                         "After this: the Morning and Noon offices")
        self.assertEqual(self.text("held_two", "office-next-items"),
                         "Water the plants · Feed the goldfish · Wind the clock · Fold the post")
        self.assertEqual(self.text("held_two", "office-next-meta"),
                         "Morning rang 08:00 · Noon rang 12:00.")
        self.assertIn("Noon rang at 12:00. The Morning and Noon offices follow this action.",
                      self.text("held_two", "bell-msg"))
        # once resolved, the first bell's office first, the second's after it
        self.assertEqual(self.text("held_two_resolved", "next-prompt"), "Water the plants")
        self.assertEqual(self.text("held_two_resolved", "next-line"), "Morning office, rang 08:00")
        self.assertEqual(self.text("held_two_resolved", "office-then"),
                         "Then: Feed the goldfish · Wind the clock · Fold the post")
        # the later bell's office done, the earlier still follows the pending action
        self.assertEqual(self.text("held_two_noon_done", "office-next-label"),
                         "After this: the Morning office")
        self.assertIn("The Morning office follows this action.",
                      self.text("held_two_noon_done", "bell-msg"))

    def test_a_deferral_is_unchanged_by_a_pending_action(self):
        self.assertEqual(self.text("held_aside", "next-prompt"), "Is watering still first?")
        self.assertTrue(self.shown("held_aside", "office-aside"))
        self.assertFalse(self.shown("held_aside", "office-next"))
        self.assertEqual(self.text("held_aside", "office-aside-items"),
                         "Wind the clock (under way) · Feed the goldfish")
        self.assertIn("set aside for now", self.text("held_aside", "bell-msg"))

    def test_a_placeholder_that_asks_nothing_never_holds_the_card(self):
        self.assertEqual(self.text("held_placeholder", "next-prompt"), "Water the plants")
        self.assertEqual(self.text("held_placeholder", "next-kind"), "office")
        self.assertFalse(self.shown("held_placeholder", "office-next"))
        self.assertEqual(self.text("held_placeholder", "office-after-prompt"),
                         "A helper is at work.")

    def test_round_three_the_calendar_on_the_timeline(self):
        tl = self.text("agenda", "panel-list")
        self.assertIn("until 10:00", tl)
        self.assertIn("An example visit", tl)
        self.assertIn("An example near", tl)
        self.assertIn("All day", tl)
        self.assertIn("An example fair", tl)
        # ended, and beyond the forty-eight hours
        self.assertNotIn("An example ended", tl)
        self.assertNotIn("An example far", tl)
        # four bells in the window, the first alone tagged as the next
        self.assertEqual(tl.count("Next bell"), 1)
        self.assertEqual(tl.count("Bell"), 3)
        self.assertLess(tl.index("Next bell"), tl.index("Tomorrow"))
        # a later bell's office items are never listed
        self.assertNotIn("Cover the seedlings", tl)
        self.assertEqual(self.text("agenda", "panel-cal"), "Calendar read today at 08:50.")

    def test_round_three_the_office_complete_and_the_session_s_items(self):
        bell = self.text("agenda", "panel-bell")
        self.assertIn("The office is complete.", bell)
        self.assertIn("Copy the list · run by the session, done", bell)
        self.assertNotIn("MEASURED-2-L", self.res["agenda"]["all"])
        self.assertNotIn("water", self.res["agenda"]["all"].lower())
        self.assertFalse(self.shown("agenda", "bell"))
        self.assertIn("Copy the list · run by the session, overruled",
                      self.text("session_overruled", "panel-bell"))
        self.assertEqual(self.text("session_overruled", "next-prompt"), "Water the plants")

    def test_round_three_a_recommendation_on_a_review_and_never_on_a_question(self):
        self.assertTrue(self.shown("agenda", "next-rec"))
        self.assertTrue(self.shown("agenda", "next-rec-label"))
        self.assertEqual(self.text("agenda", "next-rec"),
                         "Keep the shorter wording.It reads plainer.")
        for name, out in self.res.items():
            self.assertNotIn("REC-ON-A-QUESTION", out["all"], name)
        self.assertFalse(self.shown("quiet", "next-rec"))



class BriefLinesTest(unittest.TestCase):
    """The brief's and the work in hand's lines, run as the skill gives them,
    in a project naming a notebook, with the brief's directory under an
    invented home."""

    def setUp(self):
        self.base = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)
        self.project = os.path.join(self.base, "project")
        os.makedirs(os.path.join(self.project, ".principal"))
        with open(os.path.join(self.project, ".principal", "notebook.json"), "w") as fh:
            json.dump({"artifact": "doc:abc", "conventions": "wording"}, fh)
        self.scratch = os.path.join(self.base, "home", ".claude", "jobs", "0f82a3c4", "tmp", "s")
        os.makedirs(os.path.join(self.scratch, "speaker", "lines", "lines"))
        shutil.copyfile(os.path.join(HERE, "fixtures", "brief.json"),
                        os.path.join(self.scratch, "graph.json"))
        with open(os.path.join(self.scratch, "speaker", "lines", "lines", "l1.json"), "w") as fh:
            json.dump({"id": "l1", "title": "Rest a bed", "state": "open", "rank": 1}, fh)
        self.env = {k: v for k, v in os.environ.items()
                    if k not in ("CLAUDE_PROJECT_DIR", "CLAUDE_PLUGIN_ROOT", "CLAUDE_CONFIG_DIR")}
        self.env["HOME"] = os.path.join(self.base, "home")

    def run_line(self, program, *first, values=None, having=None):
        text = line(SKILL, program, *first) if having is None else \
            [s for s in lines(SKILL, program) if having in s][0]
        text = text.replace("$SCRATCH", self.scratch)
        text = TOOLS + text[len("tools"):]
        for key, value in (values or {}).items():
            text = text.replace(key, value)
        self.assertIsNone(UNFILLED.search(text), text)
        done = subprocess.run(["bash", "-c", text], cwd=self.project, capture_output=True,
                              text=True, env=self.env, timeout=60)
        self.assertEqual(done.returncode, 0, (text, done.stderr))
        return done.stdout

    def test_install_where_and_check(self):
        where = self.run_line("brief.py", "install",
                              values={"<the line's questions>": "rotation", "<time>": T})
        where = where.strip().splitlines()[-1]
        self.assertEqual(self.run_line("brief.py", "where").strip(), where)
        with open(os.path.join(where, "standing.md")) as fh:
            standing = fh.read()
        self.assertIn("[lines/l1] Rest a bed", standing)
        self.assertIn("[wording/a1.s1]", standing)
        self.assertEqual(self.run_line("brief.py", "check", values={
            "<the brief's file>": os.path.join(where, "neighbourhood.md")}), "fresh\n")

    def test_the_work_in_hand(self):
        self.assertEqual(self.run_line("inhand.py", "add", values={
            "<what is in hand>": "a coordinator for the seal", "<time>": T}).strip(), "w1")
        self.assertEqual(self.run_line("inhand.py", values={
            "<a time to come back>": "the evening bell", "<time>": T},
            having="--schedule").strip(), "s2")
        said = self.run_line("inhand.py", "list")
        self.assertIn("a coordinator for the seal", said)
        write = json.loads(self.run_line("inhand.py", "export", values={"<time>": T}))
        self.assertEqual((write["collection"], write["doc_id"]), ("ordo", "session"))
        os.makedirs(os.path.join(self.scratch, "speaker", "ordo"))
        with open(os.path.join(self.scratch, "speaker", "ordo", "session.json"), "w") as fh:
            json.dump({"at": T, "in_hand": [], "schedule": ["the morning bell"]}, fh)
        self.assertIn("1 entry", self.run_line("inhand.py", "seed", values={"<time>": T}))
        self.run_line("inhand.py", "done", values={"<entry id>": "w1"})
        self.assertNotIn("a coordinator", self.run_line("inhand.py", "list"))

    def test_the_skill_says_who_receives_a_brief_and_the_order(self):
        skill = flat(SKILL)
        section = skill[skill.index("## The brief and the neighbourhood"):
                        skill.index("## What the sitting serves")]
        for words in ("defaults to nobody", "the clean reader receives nothing",
                      "the AI's own answers alone", "no worktree is made for a brief",
                      "The order today: conventions;",
                      "then the glossary entries in full; then the tradition on the line; then "
                      "by share",
                      "outside every repository", "is a job on the board or recorded by the hooks as it launches",
                      "a helper of no kind, or of a kind the list does not name, nothing",
                      "is an open line for the principal",
                      "never a later sentence without the one before it",
                      "reserved before lineage takes the rest",
                      "kept by the session's id, and never shown to another",
                      "no hook approves a launch", "A read is never checked.", "`ordo/session.schedule`",
                      "goes to the notebook's statement of conventions first"):
            self.assertIn(words, section)


class SensitiveRuleTest(unittest.TestCase):
    """Ground rule 9 is held by reading: each place where it binds carries its
    own sentences, and the skill says no tool decides it."""

    def part(self, name):
        return flat(os.path.join(PARTS, name + ".md"))

    def skill(self, name):
        return flat(os.path.join(ROOT, "skills", name, "SKILL.md"))

    def has(self, text, *sentences):
        for words in sentences:
            self.assertIn(words, text)

    def test_the_ground_rule_in_full(self):
        rules = self.part("ground-rules")
        self.has(rules,
                 "9. **What the principal reports of the principal's own life is sensitive, and "
                 "goes nowhere a stranger can read.**",
                 "it notes there, in words, that the fact is sensitive; a form for a mark that "
                 "records carry is not yet defined.",
                 "the notebook, the page and its store, the line doc, the sitting's `$SCRATCH`, "
                 "the brief's directory under the config home (`tools/brief.py where`), "
                 "and a project's own private repository only where a standing rule already "
                 "places such a record there",
                 "Whether a private repository may hold more is the principal's to decide.",
                 "nor a message to another session, a document other than the notebook and the "
                 "line doc, or an artifact other than the page, unless that place is private.",
                 "carries this rule in substance",
                 "an example in it is invented and neutral",
                 "it stops and hands that back to the speaker, without judging whose the fact is.",
                 "is doing its work when it handles such a fact, and does not stop on it.",
                 "A helper that builds cannot know that a fact is the principal's",
                 "the speaker and the full tier's adversarial reviewer each read the pull "
                 "request's whole text",
                 "commit messages, branch, tag and file names, and diff",
                 "no search for strings stands in for it",
                 "no history is rewritten without the principal's word.",
                 "This rule binds a sitting and the publish steps of `/principal:bootstrap` and "
                 "`/principal:dictate`; a session outside those is not reached by it")
        # the hand-back is scoped to a helper whose work leaves (B1 of the second review)
        hand_back = rules.index("carries it no further: it stops and hands that back")
        self.assertIn("A helper whose work leaves for a repository or any published place, and "
                      "that finds in what it handles", rules[hand_back - 200:hand_back])
        # the line doc is among the private places (B2 of the second review)
        self.assertNotIn("recorded only in the notebook, the page and its store, and `$SCRATCH`",
                         rules)

    def test_the_core(self):
        with open(SKILL, encoding="utf-8") as fh:
            core = " ".join(fh.read().split())
        self.has(core, "**Ground rules** 1 to 9 in full",
                 "9. What the principal reports of the principal's own state",
                 "the notebook, the page and its store, the line doc, `$SCRATCH`, the brief's "
                 "directory, and a private "
                 "repository only where a standing rule puts such a record",
                 "a helper of the notebook handles it as its work",
                 "Before a merge the speaker and the full tier's reviewer read the pull "
                 "request's whole text",
                 "The rule binds a sitting and the publish steps of bootstrap and dictate, and no "
                 "session outside those.")

    def test_the_round(self):
        self.has(self.part("round"),
                 "Each brief, the implementing helper's and the adversarial reviewer's, states "
                 "the mechanism wanted and never the occasion",
                 "carries ground rule 9 in substance",
                 "The reviewer reads the pull request for such a fact as well as for its faults.",
                 "comments, commit messages, branch, tag and file names, and diff, as a reader "
                 "looking for the principal, the reviewer having read it so too, and says in "
                 "the action context that it did and what it read (ground rule 9)")

    def test_the_brief_and_attenuation(self):
        self.has(self.part("brief"),
                 "(ground rule 9). The speaker composes such a brief from the rule",
                 "carries the rule itself in substance")
        self.has(self.part("attenuation"),
                 "**Sensitive information is held by reading.** No tool decides ground rule 9.",
                 "A helper that builds cannot know a fact is the principal's",
                 "It binds a sitting and the publish steps of bootstrap and dictate; a session "
                 "outside those is not reached by it.")

    def test_bootstrap_and_dictate(self):
        for name in ("bootstrap", "dictate"):
            self.has(self.skill(name),
                     "an example is invented and neutral",
                     "commit messages, branch, tag and file names, and diff, as a reader looking "
                     "for the principal, and says that it did and what it read",
                     "in for that reading.",
                     "reported to the principal at once, with what its removal would take, and "
                     "no history is rewritten without the principal's word.")
        self.has(self.skill("dictate"), "kept only in the private places ground rule 9 of "
                 "`/principal:sit` names (the notebook, the page and its store, the line doc, "
                 "the sitting's scratch, the brief's directory")
        self.assertNotIn("recorded only in the notebook", self.skill("dictate"))
        self.has(self.skill("bootstrap"), "Before a merge, its own or the author's",
                 "the full tier's adversarial reviewer is briefed with this rule, never the "
                 "occasion, and reads for it too")


class QuestionReadByMeaningTest(unittest.TestCase):
    """Rule 3 of the line: a question drafted on the user's side is read by
    meaning for whether it leads, before it is shown, and the word search is
    gone from its path."""

    @staticmethod
    def part(name):
        return flat(os.path.join(PARTS, name + ".md"))

    def test_rule_3_orders_the_reading_before_the_showing(self):
        text = self.part("ai-line")
        rule = text[text.index("3. **Two kinds of question.**"):text.index("4. **Draws.**")]
        for words in ("Then, before it is shown to the principal, it is read for whether it "
                      "leads the answerer, in a `lead` job",
                      "judges by meaning whether the question hands over an answer, a design or "
                      "a position of the user's record, so that the reply would echo that "
                      "record instead of being the AI's own",
                      "Stating a problem and the ends to be served is not leading; sharing "
                      "words with the record is not leading.",
                      "neither quotes nor paraphrases the notebook, and proposes no rewording",
                      "A question read as `leads` is never shown",
                      "Only a question read as `does not lead` becomes its own action on the "
                      "page",
                      "A revision is written over `question.md`, checked and read again before "
                      "it is shown again",
                      "It does not compare the approval's time with the reading's",
                      "one text is read once",
                      "or by a `lead` job of it the board holds, whatever was recorded of it",
                      "the job is never retried under its id: a new `lead` job, under a new id",
                      "Once three drafts of one question have been read as leading, no draft is "
                      "read again",
                      "saying that the question could not be drafted without leading",
                      "`tools/card.py check` refuses such a card unless that record is of "
                      "exactly the question the prompt shows and says `does not lead`",
                      "looks for no run of the user's words"):
            self.assertIn(words, rule)
        self.assertNotIn("repeats masked words", rule)
        self.assertLess(rule.index("before it is shown to the principal"),
                        rule.index("becomes its own action on the page"))

    def test_rule_4_backs_a_question_out_that_led_all_the_same(self):
        text = self.part("ai-line")
        rule = text[text.index("4. **Draws.**"):text.index("5. **On a divergence.**")]
        self.assertIn("--lead $SCRATCH/lines/<line>/<n>/lead.json", rule)
        for words in ("A question found later to have led all the same, on a later reading or "
                      "at the principal's word, cuts the line there.",
                      "sets aside together the led question and every later question of the "
                      "line, whose packets carried its answer",
                      "moved under the line's `held/`, nothing renumbered by hand and nothing "
                      "deleted",
                      "The line goes on from that number with a newly drafted question",
                      "each is carried as an open note of kind `change`",
                      "carries its earlier reading over, the same text being read once"):
            self.assertIn(words, rule)

    def test_the_board_s_table_and_the_coordinator_s_mapping_name_the_lead_job(self):
        self.assertIn("| `lead` | `full` | `question-reader` | `notebook`, `question`: the "
                      "question's file, `$SCRATCH/lines/<line>/<n>/question.md`, "
                      "`question_fingerprint`: its SHA-256 | `reply`: the verdict and the "
                      "reason, `fingerprint` |", self.part("board"))
        self.assertIn("| `lead` | question-reader | `full` |", flat(COORDINATOR))
        from hypo import board
        self.assertIn("lead", board.KINDS)

    def test_attenuation_says_the_verdict_is_a_reading(self):
        text = self.part("attenuation")
        for words in ("**Whether a question leads is a reading.** No tool decides it",
                      "its verdict is its reading and no more",
                      "What the tools hold is only that a reading was made, once for one text "
                      "as the board and the records hold the readings",
                      "a launch that never started is closed once its job is marked failed",
                      "a card that names no reading passes",
                      "cannot hand one job's run to another",
                      "A refused record leaves the record that stood",
                      "is held by its definition alone",
                      "is untested in a live sitting",
                      "whether it leads the answerer"):
            self.assertIn(words, text)


class WhenToAskForABootstrapTest(unittest.TestCase):
    """Rule 1 of the line: where the speaker itself asks for a bootstrap.
    A rule about meaning is not guarded by matching its words, so this holds
    only what a test can: the rule stands where the parts table and the
    cross-references say, the references resolve, its text has no dash, and
    the manifest lists its files. Its meaning is held by the adversarial
    reader before the merge and by the speaker's reading (attenuation.md)."""

    HEADING = "**When the speaker asks for a bootstrap.**"

    @staticmethod
    def part(name):
        return flat(os.path.join(PARTS, name + ".md"))

    def rule(self):
        text = self.part("ai-line")
        line = text[text.index("## The line in the AI's graph"):]
        return line[line.index("1. **The order.**"):line.index("2. **Intention is carried")]

    def test_the_rule_stands_in_rule_1_of_the_line(self):
        self.assertEqual(self.part("ai-line").count(self.HEADING), 1)
        self.assertIn(self.HEADING, self.rule())

    def test_the_cross_references_resolve(self):
        core = flat(SKILL)
        for text in (self.part("round"), core):
            self.assertIn("the three cases of **The line in the AI's graph**, rule 1,", text)
        self.assertIn("rule 1 of the line", self.part("departures"))
        self.assertIn("rule 1 of the line", self.part("attenuation"))
        self.assertIn("**When the speaker asks for a bootstrap is held by reading.**",
                      self.part("attenuation"))
        # the bold names the rule cites stand where it says
        self.assertIn("**Written as the round goes.**", self.part("round"))
        self.assertIn("**The round** (`round.md`", core)
        self.assertIn("**Attenuation**", core)

    def test_the_part_is_read_when_a_build_is_first_owed(self):
        with open(os.path.join(PARTS, "ai-line.md"), encoding="utf-8") as fh:
            self.assertIn("when a build is first owed", fh.readline())
        row = [r for r in flat(SKILL).split("| `") if r.startswith("ai-line.md` |")]
        self.assertEqual(len(row), 1)
        self.assertIn("when a build is first owed", row[0])

    def test_no_dash_in_the_rule(self):
        for dash in ("\u2014", "\u2013"):
            self.assertNotIn(dash, self.rule())

    def test_the_manifest_lists_the_files(self):
        with open(os.path.join(ROOT, ".principal", "bootstrap.json"), encoding="utf-8") as fh:
            apps = json.load(fh)["applications"]
        entry = [a for a in apps if a["application"] == "the request for a bootstrap"]
        self.assertEqual(len(entry), 1)
        files = entry[0]["files"]
        for f in ("skills/sit/SKILL.md", "skills/sit/parts/ai-line.md",
                  "skills/sit/parts/round.md", "skills/sit/parts/attenuation.md",
                  "skills/sit/parts/departures.md", "tools/test_sit_skill.py"):
            self.assertIn(f, files)
        for f in files:
            self.assertTrue(os.path.exists(os.path.join(ROOT, f)), f)


if __name__ == "__main__":
    unittest.main()
