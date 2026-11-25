"""The AI's presuppositions as hinges: read off an answer one a line, placed
with the question and the answer word for word, each unjustified and named
by the question it came in by; and every unjustified hinge of the AI's graph
listed with the builds that rest on it. Every line here is invented."""

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest

from hypo import hinges, model
from support import fixture, run

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.join(HERE, "..", "skills", "sit", "SKILL.md")
ANSWER = ("The morning is for the plants, before anything is sent.\n\n"
          "Rests on:\n- nothing earlier\n"
          "Presupposes:\n- that the plants need water every morning\n"
          "- that the post can wait an hour.\n")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def answered(line_dir, n, question, answer):
    """A question of a line answered as clean_turn.py leaves one."""
    d = os.path.join(line_dir, str(n))
    os.makedirs(os.path.join(d, "draws"))
    raw = question.encode("utf-8")
    with open(os.path.join(d, "question.md"), "wb") as fh:
        fh.write(raw)
    with open(os.path.join(d, "draws", "draw-1.json"), "w") as fh:
        json.dump({"kind": "answerer", "answer": answer, "model": "a-model",
                   "answer_sha256": sha(answer.encode("utf-8")),
                   "question_sha256": sha(raw)}, fh)
    with open(os.path.join(d, "draws", "manifest.json"), "w") as fh:
        json.dump({"kind": "answerer", "question_sha256": sha(raw), "state": "done",
                   "draws": [{"file": "draw-1.json"}]}, fh)


class ReadTest(unittest.TestCase):
    def test_presuppositions_one_a_line(self):
        self.assertEqual(hinges.presuppositions(ANSWER),
                         ["that the plants need water every morning",
                          "that the post can wait an hour."])
        self.assertEqual(hinges.rests_on(ANSWER), ["nothing earlier"])
        self.assertEqual(hinges.presuppositions("A.\nPresupposes:\n- nothing\n"), [])
        # a blank line between two items does not drop the rest
        self.assertEqual(hinges.presuppositions("A.\nPresupposes:\n- x\n\n- y\n"), ["x", "y"])

    def test_a_draw_made_before_the_rule_gives_them_on_the_label_s_line(self):
        """Run together, they are parted at each `that` a comma or an `and`
        opens; with no such `that`, at the commas and the closing `and`."""
        self.assertEqual(hinges.presuppositions(
            "A.\nPresupposes: that the plants and the seedlings are the user's to tend, that "
            "the can holds two litres, and that the tap is outside.\n"),
            ["that the plants and the seedlings are the user's to tend",
             "that the can holds two litres", "that the tap is outside"])
        self.assertEqual(hinges.presuppositions("A.\nPresupposes: rain, wind and frost.\n"),
                         ["rain", "wind", "frost"])
        self.assertEqual(hinges.presuppositions("A.\nPresupposes: that it rains.\n"),
                         ["that it rains"])

    def test_refusals(self):
        with self.assertRaises(hinges.Refused):
            hinges.presuppositions("An answer with no closing lines.")
        with self.assertRaises(hinges.Refused):
            hinges.presuppositions("A.\nPresupposes: that a\n- that b\n")
        with self.assertRaises(hinges.Refused):
            hinges.presuppositions("A.\nPresupposes:\n- that the post (the letters) waits\n")

    def test_a_placed_hinge_reads_back_unjustified(self):
        placed = hinges.place("What is the morning for?", ANSWER, "l1", 2, "ti-esti")
        self.assertEqual(placed["answer"], ANSWER)
        self.assertEqual(placed["hinge"]["question"],
                         "that the plants need water every morning (unjustified; came in by "
                         "l1/2)\nthat the post can wait an hour (unjustified; came in by l1/2)")
        q = model.Question(id="x", tab="t", body="b", question="q", state="held", kind="case",
                           pressure=0,
                           hinge=model.Hinge(question=" ".join(
                               placed["hinge"]["question"].split())))
        got = hinges.read(q)
        self.assertEqual([(h.words, h.came_in_by, h.justified_by) for h in got],
                         [("that the plants need water every morning", "l1/2", None),
                          ("that the post can wait an hour", "l1/2", None)])
        self.assertEqual(placed["hinge"]["thesis"],
                         "model: not recorded · harness: a clean turn with no tools, over the "
                         "line's packet · canon: the AI's answers of ti-esti and above it, and "
                         "the line l1 before question 2")

    def test_a_placed_node_passes_the_notebook_s_hinge_check(self):
        import json as _json
        from hypo import spec
        placed = hinges.place("What is the morning for?", ANSWER, "l1", 1, "ti-esti")
        with open(fixture("valid"), encoding="utf-8") as fh:
            data = _json.load(fh)
        data["questions"][0]["hinge"].update(placed["hinge"])
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        path = os.path.join(d, "g.json")
        with open(path, "w", encoding="utf-8") as fh:
            _json.dump(data, fh)
        self.assertEqual([f for f in spec.run(model.load(path), only=("hinge-present",))], [])


class PlaceCliTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.line = os.path.join(self.dir, "lines", "l1")
        answered(self.line, 1, "What is the morning for?\n", ANSWER)

    def test_place_prints_the_question_the_answer_and_the_hinges(self):
        done = run("hinges.py", "place", self.line, "--n", "1", "--under", "ti-esti")
        self.assertEqual(done.returncode, 0, done.stderr)
        out = json.loads(done.stdout)
        self.assertEqual(out["question"], "What is the morning for?")
        self.assertEqual(out["answer"], ANSWER.strip())
        self.assertEqual(out["under"], "ti-esti")
        self.assertEqual(out["came_in_by"], "l1/1")
        self.assertEqual([h["justified"] for h in out["hinges"]], [False, False])
        self.assertTrue(out["hinge"]["thesis"].startswith("model: a-model · "))

    def test_the_line_s_name_where_its_directory_is_not_named_for_it(self):
        done = run("hinges.py", "place", self.line, "--n", "1", "--line-name", "line-1")
        self.assertEqual(json.loads(done.stdout)["came_in_by"], "line-1/1")

    def test_a_question_not_answered_and_a_tampered_draw_are_refused(self):
        done = run("hinges.py", "place", self.line, "--n", "2")
        self.assertEqual(done.returncode, 1)
        self.assertIn("no answered question 2", done.stderr)
        with open(os.path.join(self.line, "1", "draws", "draw-1.json")) as fh:
            draw = json.load(fh)
        draw["answer"] = "Another answer."
        with open(os.path.join(self.line, "1", "draws", "draw-1.json"), "w") as fh:
            json.dump(draw, fh)
        done = run("hinges.py", "place", self.line, "--n", "1")
        self.assertEqual(done.returncode, 1)
        self.assertIn("REFUSED", done.stderr)

    def test_a_draw_made_before_the_rule_is_placed(self):
        line = os.path.join(self.dir, "l2")
        answered(line, 1, "Why?\n", "Because.\nPresupposes: that it rains, and that the "
                                    "barrel is full.\n")
        done = run("hinges.py", "place", line, "--n", "1")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual([h["words"] for h in json.loads(done.stdout)["hinges"]],
                         ["that it rains", "that the barrel is full"])
        line = os.path.join(self.dir, "l3")
        answered(line, 1, "Why?\n", "Because, with no closing lines.\n")
        done = run("hinges.py", "place", line, "--n", "1")
        self.assertEqual(done.returncode, 1)
        self.assertIn("no line opening", done.stderr)

    def test_the_skill_s_place_line_runs(self):
        import test_sit_skill as walk
        (each,) = [s for s in walk.lines(SKILL, "hinges.py") if s.split()[1] == "place"]
        command = each.replace("tools/", HERE + "/", 1)
        for key, value in {"$SCRATCH": self.dir, "<line>": "l1", "<n>": "1",
                           "<id>": "ti-esti"}.items():
            command = command.replace(key, value)
        self.assertIsNone(walk.UNFILLED.search(command), command)
        done = subprocess.run(["bash", "-c", command], capture_output=True, text=True,
                              timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        with open(os.path.join(self.line, "1", "place.json")) as fh:
            self.assertEqual(json.load(fh)["came_in_by"], "l1/1")


#: an answer as the answerer gives one that the page holds as it stands: each
#: labelled line a paragraph of its own, the presuppositions a list
HELD = ("The morning is for the plants, before anything is sent.\n\n"
        "Rests on: nothing earlier\n\n"
        "Presupposes:\n\n"
        "- that the plants need water every morning\n"
        "- that the post can wait an hour")
QUESTION = "What is the morning for?"
#: the key ai_root of an invented notebook, and the notebook file holding it
LISTED = [{"node": "n-root", "tab": "t-root"}, {"node": "n-tab", "tab": "t-tab"}]


def as_view(markdown, rev=4):
    """A tab's markdown as the document holds it once inserted, in the view a
    read prints: a block a paragraph, a heading by its marks, a block wholly
    in single stars in italics, and a run of items a list. A line under a
    paragraph's line is joined to it, and one under an item to the item, as
    the document joins a wrapped line; an item under a paragraph's line
    opens a list of its own. No inline mark is read: the texts here hold
    none."""
    from xml.sax.saxutils import escape
    out, ids = [], iter(range(1, 10000))

    def para(words, heading=None, italic=False):
        inner = "<text id='s1.%d'>%s</text>" % (next(ids), escape(words))
        if italic:
            inner = "<italic>%s</italic>" % inner
        return "<paragraph id='s1.%d'%s>%s</paragraph>" % (
            next(ids), " heading='%d'" % heading if heading else "", inner)

    for block in markdown.strip().split("\n\n"):
        head = re.match(r"^(#{1,6}) (.*)$", block)
        if head and "\n" not in block:
            out.append(para(head.group(2), len(head.group(1))))
            continue
        if block.startswith("*") and block.endswith("*") and "\n" not in block:
            out.append(para(block[1:-1], italic=True))
            continue
        lines, items = [], None
        for row in block.split("\n"):
            if row.startswith("- "):
                if items is None:
                    if lines:
                        out.append(para(" ".join(lines)))
                        lines = []
                    items = []
                items.append(row[2:])
            elif items is not None:
                items[-1] += " " + row
            else:
                lines.append(row)
        if lines:
            out.append(para(" ".join(lines)))
        if items is not None:
            out.append("<list kind='bullet'>%s</list>" % "".join(
                "<listItem>%s</listItem>" % para(i) for i in items))
    return "<doc rev='%d' sinceRev='0'>%s</doc>" % (rev, "".join(out))


def tab_after(entry, name="q-one"):
    """The tab a fresh one, its heading alone, holds once the entry's inserts
    have landed at its end, as markdown."""
    return "\n\n".join(["# " + name] + [op["source"]["from"]["content"]
                                         for op in entry["payload"]["ops"]])


class RowsTest(unittest.TestCase):
    """The rows that place an answer of record on its tab: the form the reader
    reads back as the AI's answer, the answer word for word, the operation id
    fixed, the refusals, and the guard."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.line = os.path.join(self.dir, "lines", "l1")
        answered(self.line, 1, QUESTION + "\n", HELD)
        self.notebook = os.path.join(self.dir, "notebook.json")
        with open(self.notebook, "w", encoding="utf-8") as fh:
            json.dump({"artifact": "https://example.invalid/code/artifact/"
                                   "0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0",
                       "ai_root": LISTED}, fh)

    def placed(self, line=None, n=1):
        done = run("hinges.py", "place", line or self.line, "--n", str(n), "--under", "ai-root")
        self.assertEqual(done.returncode, 0, done.stderr)
        path = os.path.join(self.dir, "place.json")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(done.stdout)
        return path

    def loaded(self):
        with open(self.placed(), encoding="utf-8") as fh:
            return json.load(fh)

    def rows(self, place, node="n-tab", kind="definitional"):
        return run("hinges.py", "rows", place, "--node", node, "--kind", kind,
                   "--notebook", self.notebook)

    def entry(self, **kw):
        done = self.rows(self.placed(), **kw)
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout)

    def test_the_entry_is_one_update_of_three_inserts_at_the_tab_s_end(self):
        entry = self.entry()
        self.assertEqual(sorted(entry), ["node", "op_id", "payload"])
        self.assertEqual(entry["node"], "n-tab")
        self.assertEqual(list(entry["payload"]), ["ops"])
        for op in entry["payload"]["ops"]:
            self.assertEqual(op, {"op": "insert", "target": {"kind": "root"}, "side": "end",
                                  "source": {"as": "markdown", "from": {
                                      "kind": "inline",
                                      "content": op["source"]["from"]["content"]}}})
        self.assertEqual(len(entry["payload"]["ops"]), 3)

    def test_the_form_is_the_notebook_s_question_answer_and_hinge(self):
        ops = [op["source"]["from"]["content"] for op in self.entry()["payload"]["ops"]]
        self.assertEqual(ops[0], "*What is the morning for?*\n\n"
                         "question: in thread · definitional · answerer: ai · pressure 0 · "
                         "backlog 0 · load 0\n\n## Thesis\n\n"
                         "### ◆ The morning is for the plants, before anything\n\n"
                         "assent: none · in thread · provenance: thesis hinge")
        self.assertEqual(ops[2], "## Hinge\n\n"
                         "### ⚓ question: what the asking presupposes\n\n"
                         "that the plants need water every morning (unjustified; came in by "
                         "l1/1)\n\n"
                         "that the post can wait an hour (unjustified; came in by l1/1)\n\n"
                         "### ⚓ thesis: what the answer was drawn from\n\n"
                         "model: a-model · harness: a clean turn with no tools, over the "
                         "line's packet · canon: the AI's answers of ai-root and above it, and "
                         "the line l1 before question 1")

    def test_the_answer_is_an_insert_of_its_own_word_for_word(self):
        """What the ai-recorder checks: the text inserted as the answer is the
        draw's answer, neither cut nor joined nor reflowed."""
        ops = self.entry()["payload"]["ops"]
        with open(os.path.join(self.line, "1", "draws", "draw-1.json"), encoding="utf-8") as fh:
            self.assertEqual(ops[1]["source"]["from"]["content"], json.load(fh)["answer"])
        self.assertNotIn(HELD, ops[0]["source"]["from"]["content"])
        self.assertNotIn(HELD, ops[2]["source"]["from"]["content"])

    def test_the_tab_reads_back_as_the_ai_s_answer_under_its_question(self):
        """Rendered into the view a read prints, spelled by page.py, read by
        read.py and carried by packet.py: the AI's answer past held, word
        for word, under its question, with its hinges unjustified."""
        import read as reader
        from hypo import page, spec
        entry = self.entry()
        bodies = {"q-one": page.markdown(as_view(tab_after(entry)))}
        manifest = {"value": {"tabs": {"t-tab": {"name": "q-one", "order": "a0"}}},
                    "files": [{"id": "t-tab", "content": {"id": "n-tab"}}]}
        graph_path = os.path.join(self.dir, "graph.json")
        with open(graph_path, "w", encoding="utf-8") as fh:
            json.dump(reader.assemble(manifest, bodies), fh)
        out = os.path.join(self.dir, "packet.md")
        done = run("packet.py", graph_path, "--whole", "-o", out)
        self.assertEqual(done.returncode, 0, done.stderr)
        import packet
        with open(out, encoding="utf-8") as fh:
            self.assertEqual(packet.parse(fh.read()), [(QUESTION, HELD)])
        graph = model.load(graph_path)
        (q,) = graph.questions
        self.assertEqual((q.answerer, q.state, [t.state for t in q.theses]),
                         ("ai", "in thread", ["in thread"]))
        self.assertTrue(q.claude)
        self.assertEqual([(h.words, h.came_in_by, h.justified_by) for h in hinges.read(q)],
                         [("that the plants need water every morning", "l1/1", None),
                          ("that the post can wait an hour", "l1/1", None)])
        self.assertEqual(q.hinge.thesis.split(" · ")[0], "model: a-model")
        self.assertEqual([f.line() for f in spec.run(graph, only=(
            "text-unwrapped", "text-unquoted", "state-order", "only-ai-put", "hinge-present",
            "provenance-complete", "assent-present", "headline-not-identifier"))], [])

    def test_the_operation_id_is_fixed_by_the_line_the_number_and_the_node(self):
        first, again = self.entry(), self.entry()
        self.assertEqual(first, again)
        self.assertEqual(first["op_id"], hinges.place_op_id("l1", 1, "n-tab"))
        self.assertEqual(self.entry(node="N-TAB")["op_id"], first["op_id"])
        self.assertNotEqual(self.entry(node="n-root")["op_id"], first["op_id"])
        self.assertNotEqual(hinges.place_op_id("l1", 2, "n-tab"), first["op_id"])
        self.assertNotEqual(hinges.place_op_id("l2", 1, "n-tab"), first["op_id"])
        self.assertTrue(first["op_id"].startswith("ai-place-"))

    def test_an_answer_the_page_would_not_give_back_is_refused_unaltered(self):
        """The answerer's closing lines as a draw may give them, one under the
        other, are a line break inside a paragraph: the document joins them,
        so the tab would read back another text, and the rows are refused."""
        line = os.path.join(self.dir, "lines", "l2")
        answered(line, 1, QUESTION + "\n", ANSWER)
        done = self.rows(self.placed(line))
        self.assertEqual(done.returncode, 1)
        self.assertIn("REFUSED: the answer breaks a line inside a paragraph", done.stderr)
        self.assertEqual(done.stdout, "")
        # and this is why: the page would give back another text
        from hypo import page, read
        joined = read.parse_tab(page.markdown(as_view("# q-two\n\n" + ANSWER.strip())))
        self.assertEqual(joined["id"], "q-two")
        self.assertNotIn(ANSWER.strip(), page.markdown(as_view(ANSWER.strip())))

    def test_each_mark_the_form_reserves_is_refused_and_named(self):
        for words, why in (
                ("A.\n\n## B", "opens a block on #"),
                ("A.\n\n> B", "blockquote"),
                ("A.\n\n**Support**", "opens the citations"),
                ("A.\nB.", "breaks a line inside a paragraph"),
                ("A.\n\n\nB.", "more than one blank line"),
                ("A.\n\n  - B", "indented"),
                ("A. ", "space at its ends"),
                ("A <<< B", "packet"),
                ("A <?claude block m_x?> B", "chip"),
                ("A \\ B", "backslash"),
                ("A [B] C", "bracket"),
                ("A _B_ C", "underscore"),
                ("A * B", "star"),
                ("A `B C", "backtick"),
                ("A.\n\n* B", "markers"),
                ("A.\n\n2. B", "markers"),
                ("A.\n\n```\nB\n```", "code fence"),
                ("A.\n\n---", "rule")):
            with self.subTest(words=words):
                why_given = hinges.unheld(words, "the answer")
                self.assertIsNotNone(why_given)
                self.assertIn(why, why_given)
        for words in (HELD, "A **bold** word and an *aside*.", "1. one\n2. two",
                      "snake_case stays", "A `code` span."):
            with self.subTest(words=words):
                self.assertIsNone(hinges.unheld(words, "the answer"))

    def test_the_question_stands_on_one_line_in_italics(self):
        place = self.loaded()
        for question in ("What is *the* morning for?", "What is\nthe morning for?"):
            with self.subTest(question=question):
                with self.assertRaises(hinges.Refused):
                    hinges.rows(dict(place, question=question), "n-tab", "case", ["n-tab"])

    def test_a_place_not_as_place_printed_it_is_refused(self):
        place = self.loaded()
        bad = [dict(place, answer=place["answer"].replace("an hour", "a day")),
               dict(place, rests_on=["something"]),
               dict(place, came_in_by="l1"),
               dict(place, hinge=dict(place["hinge"], thesis="from somewhere")),
               dict(place, question=None), "not a place"]
        for each in bad:
            with self.subTest(each=str(each)[:40]):
                with self.assertRaises(hinges.Refused):
                    hinges.rows(each, "n-tab", "case", ["n-tab"])
        with self.assertRaises(hinges.Refused):
            hinges.rows(place, "n-tab", "a-kind", ["n-tab"])
        with self.assertRaises(hinges.Refused):
            hinges.rows(place, "n tab", "case", ["n tab"])

    def test_a_node_the_key_does_not_list_is_refused(self):
        done = self.rows(self.placed(), node="n-other")
        self.assertEqual(done.returncode, 1)
        self.assertIn("lists no tab 'n-other'", done.stderr)

    def test_the_guard_admits_the_ai_recorder_every_op_on_a_listed_tab_alone(self):
        import test_notebook_gate as gated
        entry = self.entry()
        gate = gated.load_gate()

        def decide(named, agent="principal:ai-recorder"):
            with gated.project(named) as root:
                return gate.decide(gated.call(root, agent, gated.UPDATE, {
                    "container": {"kind": "project", "id": gated.NOTEBOOK},
                    "ref": {"object": "node", "id": entry["node"]},
                    "payload": entry["payload"], "opId": entry["op_id"]}),
                    env={}, plugin="principal")

        listed = {"artifact": gated.SITE + gated.NOTEBOOK, "ai_root": LISTED}
        self.assertEqual(decide(listed), {})
        for op in entry["payload"]["ops"]:
            self.assertTrue(gate._insert_only(op))
        elsewhere = dict(listed, ai_root=[{"node": "n-root", "tab": "t-root"}])
        self.assertEqual(decide(elsewhere)["hookSpecificOutput"]["permissionDecisionReason"],
                         gate.AI_SIDE)
        self.assertEqual(decide({"artifact": gated.SITE + gated.NOTEBOOK})
                         ["hookSpecificOutput"]["permissionDecisionReason"], gate.UNSET)
        # the user's side is not the AI's recorder's, nor the AI's the comparer's
        self.assertEqual(decide(listed, "principal:comparer")
                         ["hookSpecificOutput"]["permissionDecisionReason"], gate.USER_SIDE)

    def test_the_skill_s_rows_line_runs(self):
        import test_sit_skill as walk
        self.placed()
        os.makedirs(os.path.join(self.line, "1"), exist_ok=True)
        shutil.copy(os.path.join(self.dir, "place.json"),
                    os.path.join(self.line, "1", "place.json"))
        (each,) = [s for s in walk.lines(SKILL, "hinges.py") if s.split()[1] == "rows"]
        command = each.replace("tools/", HERE + "/", 1)
        for key, value in {"$SCRATCH": self.dir, "<line>": "l1", "<n>": "1",
                           "<node id>": "n-tab", "<kind>": "case"}.items():
            command = command.replace(key, value)
        self.assertIsNone(walk.UNFILLED.search(command), command)
        os.makedirs(os.path.join(self.dir, ".principal"))
        shutil.copy(self.notebook, os.path.join(self.dir, ".principal", "notebook.json"))
        env = dict(os.environ, CLAUDE_PROJECT_DIR=self.dir)
        done = subprocess.run(["bash", "-c", command], capture_output=True, text=True,
                              timeout=60, env=env, cwd=self.dir)
        self.assertEqual(done.returncode, 0, done.stderr)
        with open(os.path.join(self.line, "1", "rows.json"), encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["node"], "n-tab")


class UnjustifiedTest(unittest.TestCase):
    def graph(self, hinge_text, justified_by_state="in thread"):
        with open(fixture("valid"), encoding="utf-8") as fh:
            data = json.load(fh)
        by = {q["id"]: q for q in data["questions"]}
        by["ti-esti"]["hinge"]["question"] = hinge_text
        by["canon"]["theses"][0]["state"] = justified_by_state
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        path = os.path.join(d, "graph.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        return path

    def listed(self, path):
        done = run("hinges.py", "unjustified", path)
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout)

    def test_every_unjustified_hinge_with_the_builds_under_it(self):
        path = self.graph("that the plants need water (unjustified; came in by l1/1) "
                          "that the post can wait (justified by canon)")
        found = self.listed(path)
        mine = [f for f in found if f["question"] == "ti-esti"]
        self.assertEqual([f["words"] for f in mine], ["that the plants need water"])
        self.assertEqual(mine[0]["came_in_by"], "l1/1")
        apps = {b["application"] for b in mine[0]["builds"]}
        # its own answer's build, and the one below it in the lineage
        self.assertEqual(apps, {"the opening entry", "the shape gate"})

    def test_a_justification_by_no_answer_of_the_ai_s_is_none(self):
        path = self.graph("that the post can wait (justified by canon)",
                          justified_by_state="held")
        found = [f for f in self.listed(path) if f["question"] == "ti-esti"]
        self.assertEqual([(f["words"], f["named"]) for f in found],
                         [("that the post can wait", "canon")])
        path = self.graph("that the post can wait (justified by ti-esti)")
        self.assertEqual(len([f for f in self.listed(path) if f["question"] == "ti-esti"]), 1)

    def test_a_hinge_written_before_the_form_is_one_unjustified(self):
        found = [f for f in self.listed(fixture("valid")) if f["question"] == "ti-esti"]
        self.assertEqual(len(found), 1)
        self.assertIsNone(found[0]["came_in_by"])

    def test_the_skill_s_unjustified_line_runs(self):
        import test_sit_skill as walk
        (each,) = [s for s in walk.lines(SKILL, "hinges.py")
                   if s.split()[1] == "unjustified" and "$SCRATCH" in s]
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        shutil.copy(fixture("valid"), os.path.join(d, "graph.json"))
        command = each.replace("tools/", HERE + "/", 1).replace("$SCRATCH", d)
        done = subprocess.run(["bash", "-c", command], capture_output=True, text=True,
                              timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("unjustified hinge(s)", done.stderr)


if __name__ == "__main__":
    unittest.main()
