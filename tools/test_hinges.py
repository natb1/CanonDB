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

from hypo import hinges, model, text
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


#: answers in the forms a draw gives: a bold lead, code, a star and an
#: entity, numbered items apart, angle brackets, a list straight under a
#: label line, and the closing labelled lines one under the other
MARKED = ("**The morning is for the plants.** Water comes before `post`, and 2 * 3 cans "
          "do it, AT&amp;T or not.\n\n"
          "1. **First** the seedlings_  \n\n"
          "2. Then the <beds> and [the pots](#x) with ``a `b` c``.\n"
          "Rests on: nothing earlier\n"
          "Presupposes:\n"
          "- that the plants need water every morning\n"
          "- that the post can wait an hour")
NOTHING = ("The morning is for the plants.\n\n"
           "Rests on: nothing earlier\n"
           "Presupposes:\n"
           "- nothing")
QUESTION = "What is the *morning* for, `now`?"
#: the key ai_root of an invented notebook
LISTED = [{"node": "n-root", "tab": "t-root"}, {"node": "n-tab", "tab": "t-tab"}]
#: a whole read of a tab just made, holding its heading alone
BLANK = ("<doc rev='5' sinceRev='0'><paragraph id='s1.1' h='0' heading='1'>"
         "<text id='.2'>q-one</text></paragraph></doc>")


def as_view(markdown, rev=6):
    """A tab's markdown as a whole read of the document prints it: a code
    block as the document holds one, ``<codeBlock id h language='text'>``
    with its words in a text run, in CDATA sections and with each angle
    bracket written as an entity between them; a heading by its marks; and
    every other block, which here is one line of the tool's own words, a
    paragraph."""
    def cdata(words):
        parts = re.split(r"([<>])", words)
        return "".join({"<": "&lt;", ">": "&gt;"}.get(p) or
                       ("<![CDATA[%s]]>" % p.replace("]]>", "]]]]><![CDATA[>") if p else "")
                       for p in parts)

    out, ids = [], iter(range(1, 10000))
    found = text.fences(markdown)
    pieces, last = [], 0
    for start, end, language, words in found:
        pieces += [("md", markdown[last:start]), ("code", (language, words))]
        last = end
    pieces.append(("md", markdown[last:]))
    from xml.sax.saxutils import escape
    for kind, piece in pieces:
        if kind == "code":
            out.append("<codeBlock id='s1.%d' h='0' language='%s'><text id='s1.%d'>%s</text>"
                       "</codeBlock>" % (next(ids), piece[0], next(ids), cdata(piece[1])))
            continue
        for block in piece.split("\n\n"):
            if not block.strip():
                continue
            assert "\n" not in block.strip(), block
            head = re.match(r"^(#{1,6}) (.*)$", block.strip())
            words, level = (head.group(2), len(head.group(1))) if head else (block.strip(), 0)
            out.append("<paragraph id='s1.%d' h='0'%s><text id='s1.%d'>%s</text></paragraph>"
                       % (next(ids), " heading='%d'" % level if level else "", next(ids),
                          escape(words)))
    return "<doc rev='%d' sinceRev='0'>%s</doc>" % (rev, "".join(out))


def tab_after(entry, name="q-one"):
    """The tab, its heading alone before, once the entry's inserts have
    landed at its end, as markdown."""
    return "\n\n".join(["# " + name] + [op["source"]["from"]["content"]
                                       for op in entry["payload"]["ops"]])


class RowsTest(unittest.TestCase):
    """The rows that place an answer of record on its tab: every text of the
    line held word for word in a code block, read back as the AI's answer;
    the place checked against the line's directory; the tab read blank; the
    operation id; the refusals; and the guard."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.line = os.path.join(self.dir, "lines", "l1")
        answered(self.line, 1, QUESTION + "\n", MARKED)
        answered(self.line, 2, "And the evening?\n", ANSWER)
        answered(self.line, 3, "And at night?\n", NOTHING + "\n")
        self.notebook = os.path.join(self.dir, "notebook.json")
        with open(self.notebook, "w", encoding="utf-8") as fh:
            json.dump({"artifact": "https://example.invalid/code/artifact/"
                                   "0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0",
                       "ai_root": LISTED}, fh)
        self.blank = self.file("blank.xml", BLANK)

    def file(self, name, words):
        path = os.path.join(self.dir, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(words)
        return path

    def placed(self, n=1, line=None, name="l1"):
        args = ["place", line or self.line, "--n", str(n), "--under", "ai-root"]
        if name:
            args += ["--line-name", name]
        done = run("hinges.py", *args)
        self.assertEqual(done.returncode, 0, done.stderr)
        return self.file("place-%d.json" % n, done.stdout)

    def loaded(self, n=1):
        with open(self.placed(n), encoding="utf-8") as fh:
            return json.load(fh)

    def rows(self, place, node="n-tab", kind="definitional", read=None, line=None,
             name="l1"):
        return run("hinges.py", "rows", place, "--line", line or self.line, "--line-name", name,
                   "--node", node, "--kind", kind, "--read", read or self.blank,
                   "--notebook", self.notebook)

    def entry(self, n=1, **kw):
        done = self.rows(self.placed(n), **kw)
        self.assertEqual(done.returncode, 0, done.stderr)
        out = json.loads(done.stdout)
        self.assertEqual(len(out), 1)
        return out[0]

    def draw(self, n):
        with open(os.path.join(self.line, str(n), "draws", "draw-1.json"), encoding="utf-8") as fh:
            return json.load(fh)["answer"]

    def test_a_rows_file_of_one_update_guarded_by_the_read_s_rev(self):
        entry = self.entry()
        self.assertEqual(sorted(entry), ["n", "node", "op_id", "payload"])
        self.assertEqual((entry["node"], entry["n"]), ("n-tab", 1))
        self.assertEqual(sorted(entry["payload"]), ["ifRev", "ops"])
        self.assertEqual(entry["payload"]["ifRev"], 5)
        self.assertEqual(len(entry["payload"]["ops"]), 3)
        for op in entry["payload"]["ops"]:
            self.assertEqual(op, {"op": "insert", "target": {"kind": "root"}, "side": "end",
                                  "source": {"as": "markdown", "from": {
                                      "kind": "inline",
                                      "content": op["source"]["from"]["content"]}}})

    def test_every_text_of_the_line_stands_in_a_code_block_and_the_rest_is_the_tool_s(self):
        ops = [op["source"]["from"]["content"] for op in self.entry()["payload"]["ops"]]
        self.assertEqual(ops[0], "```text\n" + QUESTION + "\n```\n\n"
                         "question: in thread · definitional · answerer: ai · pressure 0 · "
                         "backlog 0 · load 0\n\n## Thesis\n\n"
                         "### ◆ answer of record of l1/1\n\n"
                         "assent: none · in thread · provenance: thesis hinge")
        # the answer holds a run of two backticks: the fence is longer
        self.assertEqual(ops[1], "```text\n" + MARKED + "\n```")
        self.assertEqual(ops[2], "## Hinge\n\n"
                         "### ⚓ question: what the asking presupposes\n\n```text\n"
                         "that the plants need water every morning (unjustified; came in by "
                         "l1/1)\nthat the post can wait an hour (unjustified; came in by l1/1)"
                         "\n```\n\n### ⚓ thesis: what the answer was drawn from\n\n```text\n"
                         "model: a-model · harness: a clean turn with no tools, over the "
                         "line's packet · canon: the AI's answers of ai-root and above it, and "
                         "the line l1 before question 1\n```")
        self.assertEqual(text.fence("a ```` b"), "`````text\na ```` b\n`````")

    def test_the_answer_insert_holds_the_draw_s_answer_word_for_word(self):
        for n in (1, 2, 3):
            with self.subTest(n=n):
                (start, end, language, words), = text.fences(
                    self.entry(n)["payload"]["ops"][1]["source"]["from"]["content"])
                self.assertEqual((language, words), ("text", self.draw(n).strip()))

    def test_the_tab_reads_back_as_the_ai_s_answer_word_for_word(self):
        """Each answer, its marks, lists and spacing included, rendered into
        the view a read prints, spelled by page.py, read by read.py and
        carried by packet.py: the AI's answer past held under its question,
        the hinges read back, and the checks clean, an answer that
        presupposes nothing among them."""
        import packet
        import read as reader
        from hypo import page, spec
        for n, question in ((1, QUESTION), (2, "And the evening?"), (3, "And at night?")):
            with self.subTest(n=n):
                entry = self.entry(n)
                bodies = {"q-one": page.markdown(as_view(tab_after(entry)))}
                manifest = {"value": {"tabs": {"t-tab": {"name": "q-one", "order": "a0"}}},
                            "files": [{"id": "t-tab", "content": {"id": "n-tab"}}]}
                graph_path = self.file("graph.json", json.dumps(
                    reader.assemble(manifest, bodies)))
                out = os.path.join(self.dir, "packet.md")
                done = run("packet.py", graph_path, "--whole", "-o", out)
                self.assertEqual(done.returncode, 0, done.stderr)
                with open(out, encoding="utf-8") as fh:
                    self.assertEqual(packet.parse(fh.read()), [(question, self.draw(n).strip())])
                graph = model.load(graph_path)
                (q,) = graph.questions
                self.assertEqual((q.question, q.fenced, q.answerer, q.state, q.claude),
                                 (question, True, "ai", "in thread", True))
                self.assertEqual(q.theses[0].text, self.draw(n).strip())
                got = [(h.words, h.came_in_by) for h in hinges.read(q)]
                self.assertEqual(got, [] if n == 3 else
                                 [("that the plants need water every morning", "l1/%d" % n),
                                  ("that the post can wait an hour", "l1/%d" % n)])
                # every error but the two a lone tab owes to the graph around it
                errors = [f.line() for f in spec.run(graph) if f.severity == spec.ERROR
                          and f.check not in ("one-root", "end-stated")]
                self.assertEqual(errors, [])
                # the renderer writes a held tab back as it stands
                from hypo import read, render
                again = read.parse_tab(render.body(graph, q.id))
                self.assertEqual((again["question"], again["theses"][0]["text"],
                                  again["hinge"], again["fenced"]),
                                 (q.question, q.theses[0].text,
                                  {"question": q.hinge.question, "thesis": q.hinge.thesis},
                                  True))

    def test_a_prose_tab_quoting_code_is_read_as_it_always_was(self):
        from hypo import read
        tab = ("# q-two\n\n*Why?*\n\nquestion: held · case · pressure 0 · backlog 0 · load 0"
               "\n\n## Thesis\n\n### ◆ A reason\n\nassent: none · held · provenance: thesis "
               "hinge\n\nSay it so:\n\n```text\nx\n```")
        q = read.parse_tab(tab)
        self.assertNotIn("fenced", q)
        self.assertEqual(q["theses"][0]["text"], "Say it so:\n\n```text\nx\n```")
        for bad in (tab.replace("*Why?*", "```text\nWhy?\n```").replace(
                        "Say it so:\n\n```text\nx\n```", "Prose."),
                    tab.replace("*Why?*", "```text\nWhy?\n```")):
            with self.subTest(bad=bad[-30:]):
                with self.assertRaises(read.ParseError):
                    read.parse_tab(bad)

    def test_the_operation_id_covers_the_line_the_number_the_node_and_the_words(self):
        first = self.entry()
        self.assertEqual(first, self.entry())
        self.assertEqual(self.entry(node="N-TAB")["op_id"], first["op_id"])
        self.assertTrue(first["op_id"].startswith("ai-place-"))
        for other in (self.entry(node="n-root"), self.entry(kind="case"), self.entry(2)):
            self.assertNotEqual(other["op_id"], first["op_id"])
        place = self.loaded()
        edited = dict(place, answer=place["answer"] + " More.")
        self.assertNotEqual(hinges.rows(edited, "n-tab", "definitional", ["n-tab"], 5)[0]
                            ["op_id"], first["op_id"])

    def test_only_what_a_code_block_cannot_hold_is_refused(self):
        for words, why in (("", "empty"), ("\nA", "line break"), ("A\n", "line break"),
                           ("A\rB", "U+000D"), ("A\x01B", "U+0001")):
            with self.subTest(words=words):
                with self.assertRaises(hinges.Refused) as caught:
                    hinges.held(words, "the answer")
                self.assertIn(why, str(caught.exception))
        for words in (MARKED, ANSWER.strip(), "> a\n\n## b\n\n**Support**\n\n<div>c</div>",
                      "- \n\n```\nd\n```", "a  \n\tb"):
            with self.subTest(words=words):
                self.assertEqual(text.fences(hinges.held(words, "the answer"))[0][3], words)

    def test_a_place_not_as_the_line_s_directory_gives_it_is_refused(self):
        place = self.loaded()
        for name, edited in (
                ("an answer", dict(place, answer=place["answer"] + " More.")),
                ("a question", dict(place, question="Another?")),
                ("a thesis", dict(place, hinge=dict(place["hinge"], thesis="model: x · "
                                                    "harness: y · canon: z"))),
                ("a number", dict(place, came_in_by="l1/2")),
                ("an under", dict(place, under="elsewhere"))):
            with self.subTest(name=name):
                done = self.rows(self.file("edited.json", json.dumps(edited)))
                self.assertEqual(done.returncode, 1)
                self.assertIn("REFUSED", done.stderr)
        # a place from another line, and a line whose directory is not its name
        other = os.path.join(self.dir, "lines", "run")
        answered(other, 1, QUESTION + "\n", ANSWER)
        done = self.rows(self.placed(line=other, name=None), line=other, name="l9")
        self.assertIn("names the line 'run'", done.stderr)
        done = self.rows(self.placed(line=other, name="l9"), line=self.line, name="l9")
        self.assertEqual(done.returncode, 1)
        self.assertIn("not what place prints", done.stderr)

    def test_a_tab_that_holds_more_than_its_heading_is_refused(self):
        held = self.file("held.xml", as_view(tab_after(self.entry())))
        done = self.rows(self.placed(2), read=held)
        self.assertEqual(done.returncode, 1)
        self.assertIn("holds more than its heading", done.stderr)
        other = self.file("other.xml", BLANK.replace("<doc ", "<doc node='n-root' "))
        self.assertIn("not 'n-tab'", self.rows(self.placed(), read=other).stderr)
        norev = self.file("norev.xml", BLANK.replace(" rev='5'", ""))
        self.assertIn("no rev", self.rows(self.placed(), read=norev).stderr)

    def test_a_node_the_key_does_not_list_and_a_kind_outside_the_vocabulary_are_refused(self):
        done = self.rows(self.placed(), node="n-other")
        self.assertEqual(done.returncode, 1)
        self.assertIn("lists no tab 'n-other'", done.stderr)
        self.assertEqual(self.rows(self.placed(), kind="principle").returncode, 2)

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

        def reason(found):
            return found["hookSpecificOutput"]["permissionDecisionReason"]

        listed = {"artifact": gated.SITE + gated.NOTEBOOK, "ai_root": LISTED}
        self.assertEqual(decide(listed), {})
        for op in entry["payload"]["ops"]:
            self.assertTrue(gate._insert_only(op))
        elsewhere = dict(listed, ai_root=[{"node": "n-root", "tab": "t-root"}])
        self.assertEqual(reason(decide(elsewhere)), gate.AI_SIDE)
        self.assertEqual(reason(decide({"artifact": gated.SITE + gated.NOTEBOOK})), gate.UNSET)
        self.assertEqual(reason(decide(listed, "principal:comparer")), gate.USER_SIDE)

    def test_the_skill_s_rows_line_runs(self):
        import test_sit_skill as walk
        place = os.path.join(self.line, "1", "place.json")
        shutil.copy(self.placed(), place)
        os.makedirs(os.path.join(self.dir, "rows"))
        (each,) = [s for s in walk.lines(SKILL, "hinges.py") if s.split()[1] == "rows"]
        command = each.replace("tools/", HERE + "/", 1)
        for key, value in {"$SCRATCH": self.dir, "<line>": "l1", "<n>": "1",
                           "<node id>": "n-tab", "<kind>": "case",
                           "<the tab's read>": self.blank, "<job id>": "j1"}.items():
            command = command.replace(key, value)
        self.assertIsNone(walk.UNFILLED.search(command), command)
        os.makedirs(os.path.join(self.dir, ".principal"))
        shutil.copy(self.notebook, os.path.join(self.dir, ".principal", "notebook.json"))
        env = dict(os.environ, CLAUDE_PROJECT_DIR=self.dir)
        done = subprocess.run(["bash", "-c", command], capture_output=True, text=True,
                              timeout=60, env=env, cwd=self.dir)
        self.assertEqual(done.returncode, 0, done.stderr)
        with open(os.path.join(self.dir, "rows", "j1.json"), encoding="utf-8") as fh:
            self.assertEqual([e["node"] for e in json.load(fh)], ["n-tab"])


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
