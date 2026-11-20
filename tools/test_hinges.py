"""The AI's presuppositions as hinges: read off an answer one a line, placed
with the question and the answer word for word, each unjustified and named
by the question it came in by; and every unjustified hinge of the AI's graph
listed with the builds that rest on it. Every line here is invented."""

import hashlib
import json
import os
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
