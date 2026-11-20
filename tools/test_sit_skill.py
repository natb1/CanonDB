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


def _code(path, heading):
    """The first JSON code block of a file after ``heading``."""
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
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
                            self.skill.index("## Before anything")]
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
                "principal has set it aside; items run by the session never hold the card.",
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
                "`heading` and `paragraphs`; the session's own text is one or two lines saying "
                "the page changed, and never repeats what the page says; nothing the principal "
                "must decide appears only in the session's text.",
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
                      "or the principal sets the office aside; items run by the session never "
                      "hold the card",
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
        with open(SKILL, encoding="utf-8") as fh:
            self.raw = fh.read()
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
        for words in ("The principal: \"These traditions are good, make sure they are being "
                      "recorded as we go.\"",
                      "A party's graph is expected to follow the structure of the user's and the "
                      "AI's; that change of form is not made here, and is carried as an open "
                      "line",
                      "**Written as the round goes.** The principal: \"You may write to the "
                      "notebook as we go.\"",
                      "once its restatement has been shown in the action context, so that the "
                      "principal may correct it before the job is added",
                      "None is first put as a review of rows.",
                      "Everything else, a sentence, a case, and anything that changes a standing "
                      "answer, still goes through the batch point's reviews.",
                      "Three notes are written at the round without a review of rows"):
            self.assertIn(words, self.skill)

    def test_merging_and_the_reload(self):
        rule = self.section("9. **The speaker, at the full tier", "10. **Every ask")
        for words in ("what was built is reported in the action context; a build that "
                      "changes what the principal decides, a rule of a skill or what the page "
                      "shows among it, is put to the principal as a review and waits for the "
                      "answer; and then the speaker may merge, unless the principal said "
                      "otherwise",
                      "The principal: \"You have permission to merge pull requests unless "
                      "otherwise stated.",
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
                      "a `place` job is added only once the guard admits the `ai-recorder` a "
                      "new tab under the AI's root"):
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
                "Each such question is then its own action on the page, a `review` whose "
                "prompt is the question word for word, for the principal to approve or "
                "revise; it is put to the AI only on that approval.",
                "A revision is written over `question.md` and checked again before it is "
                "shown again, and only the text the principal approved is put.",
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
                "unjustified, no edge to a principle nearer the root"):
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
                      "**The line's rules are held by reading.**"):
            self.assertIn(words, self.skill)


class LineWalk(Walk):
    """The line's commands as the skill writes them: the packet, the leak
    check and a clean turn, the turn dry-run."""

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
        # no control, made in the source or at run time, in any quoting or case
        controls = r"(?:button|input|textarea|select|form|option|dialog|a)"
        self.assertIsNone(re.search(r"<\s*%s\b" % controls, self.page, re.I))
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
            self.assertNotIn(word.lower(), self.page.lower())
        self.assertNotIn("href", self.script)
        made = re.findall(r"\bel\(\s*([\"'`])(\w+)\1", self.script)
        self.assertTrue(made)
        self.assertLessEqual({t for _, t in made}, {"p", "span", "b", "li", "div", "ul"})
        self.assertEqual(re.findall(r"createElement\(\s*(\w+)\s*\)", self.script), ["tag"])

    def test_the_session_s_action_waits_while_an_office_is_unresolved(self):
        nxt = self.body("renderNext")
        self.assertRegex(nxt, r"if\s*\(\s*st\.unres\.length\s*&&\s*!st\.aside\s*\)\s*renderOffice\(st\);\s*"
                              r"else\s*\{\s*renderSession\(\);\s*if\s*\(st\.aside\)\s*renderAside\(st\);\s*\}")
        self.assertEqual(self.script.count("renderSession("), 2)
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
        self.assertIn('if (!st.left.length) box.appendChild(el("p", "quiet", "The office is '
                      'complete."));', panel)
        self.assertIn('!agenda ? "No calendar has been read."', panel)
        self.assertIn("st.left.concat(st.all.filter(function (x) { return x.session && "
                      "!(x.state === \"open\" || x.state === \"taken\"); }))", panel)
        self.assertIn("if (en <= now || s > end) return null;", self.body("upcomingEvents"))
        self.assertIn("if (at > now && at <= end)", self.body("upcomingBells"))
        # the office's items come from the latest rung bell alone, and only bell- keys are read
        self.assertIn("var all = lr.rung ? officeItems(lr.rung.b, rd) : [];", now)
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
            "y", "mo", "d"}
        given = {"context", "next", "queue", "background", "updated",
                 "heading", "paragraphs", "for", "against", "prediction", "notes", "who", "text",
                 "kind", "line", "case", "prompt", "how", "deferred", "reason", "title",
                 "recommendation", "day_start", "days", "bells", "time", "time_by_day", "name", "office", "label",
                 "except_days", "off_from", "off_to", "ask", "by",
                 "office_deferred", "since", "bell",
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
                      "its report of what was done, the brief and the close among them (rule 10)",
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
        for words in ("The page is display only: it has no button and no input, its source holds "
                      "no data, and it writes nothing.",
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
            # the action context appended to before the next answer
            "logged": {"now": cls.NOW, "rule": cls.RULE, "ticks": None,
                       "current": dict(cls.CURRENT, context=cls.LOGGED)},
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


if __name__ == "__main__":
    unittest.main()
