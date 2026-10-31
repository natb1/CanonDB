"""A line doc's compaction, checked: every dialog admission carried by a
row, every editing row resting on one, every named tab in the graph, and
nothing pinned left open and uncited."""

import os
import tempfile
import unittest

from hypo import line
from support import FIXTURES, fixture, load, read_fixture, run

DOC = read_fixture("line-doc.md")


class ParseTest(unittest.TestCase):
    def setUp(self):
        self.doc = line.parse(DOC)

    def test_sections_and_items(self):
        self.assertEqual(self.doc.title, "The line on a record")
        self.assertEqual([a.id for a in self.doc.admissions()], ["A1", "A2", "B1", "B2",
                                                                 "B3", "B4"])
        self.assertEqual([r.id for r in self.doc.rows()], ["A1", "A2", "C1", "E1"])
        self.assertEqual(self.doc.admissions()[0].text,
                         '"The record kept between them is the only thing both can point at."')
        # a bullet that is not numbered is no item
        self.assertEqual(self.doc.items("how the line is run"), [])

    def test_an_id_is_read_against_every_section_holding_it(self):
        self.assertEqual([i.section for i in self.doc.holding("A1")],
                         ["admissions", "aporiai", "the plan"])

    def test_a_row_cites_singly_and_by_span(self):
        rows = {r.id: r for r in self.doc.rows()}
        self.assertEqual(rows["A1"].cites(), ["B1", "B2", "A1"])
        self.assertEqual(rows["A2"].cites(), ["B3", "D1", "C1"])
        self.assertEqual(rows["E1"].cites(), ["D2"])
        self.assertEqual(line.Item("the plan", "A3", "B19 to B21, DC4 and B20").cites(),
                         ["B19", "B20", "B21", "DC4"])

    def test_a_row_names_tabs(self):
        rows = {r.id: r for r in self.doc.rows()}
        self.assertEqual(rows["A1"].tabs(), ["canon"])
        self.assertEqual(rows["A2"].tabs(), ["lot"])
        self.assertEqual(rows["C1"].tabs(), [])
        self.assertEqual(line.Item("the plan", "A9", "the archai root's answer and the "
                                   "tab living-well").tabs(), ["archai", "living-well"])

    def test_groups_and_closure(self):
        self.assertEqual([r.group for r in self.doc.rows()], ["A", "A", "C", "E"])
        held = {h.id: h for h in self.doc.items("held questions")}
        self.assertFalse(held["H1"].closed)
        self.assertTrue(held["H2"].closed)


class CheckTest(unittest.TestCase):
    def setUp(self):
        self.doc = line.parse(DOC)
        self.questions = {q.id for q in load("valid").questions} | {"lot"}

    def test_the_fixture_is_complete(self):
        findings = line.check(self.doc, self.questions)
        self.assertEqual([f.severity for f in findings], [line.WARN, line.WARN])
        self.assertTrue(findings[0].message.startswith(
            "admission A2, the notebook's own, is cited by no row"), findings[0].message)
        self.assertTrue(findings[1].message.startswith(
            "held questions H1 is neither closed nor cited by a row"), findings[1].message)
        self.assertEqual(line.errors(findings), [])

    def test_an_uncited_dialog_admission_is_an_error(self):
        rows = self.doc.rows()
        rows[2].text = "tools/x.py: the check. B1."
        findings = line.errors(line.check(self.doc, self.questions))
        self.assertEqual([f.message[:31] for f in findings],
                         ["admission B4 is cited by no row"])

    def test_an_editing_row_that_cites_nothing_is_an_error(self):
        self.doc.rows()[2].text = "tools/x.py: the check."
        findings = line.errors(line.check(self.doc, self.questions))
        self.assertEqual([f.message for f in findings], [
            "row C1 cites no admission, and a row that edits the notebook rests on one",
            "admission B4 is cited by no row: A note is kept until a run takes it in."])
        # an open row rests on the line as a whole
        self.doc.rows()[3].text = "The ledger's listing rule. Waiting on the user."
        self.assertEqual(len(line.errors(line.check(self.doc, self.questions))), 2)

    def test_a_named_tab_the_graph_lacks(self):
        findings = line.check(self.doc, self.questions - {"lot"})
        self.assertIn("ERROR row A2 names the tab 'lot', which the graph does not hold",
                      [f.line() for f in findings])
        # without a graph no tab is judged
        self.assertNotIn("names the tab", " ".join(f.line() for f in line.check(self.doc)))

    def test_an_open_pinned_item_a_row_carries_is_not_reported(self):
        # C1 is open and cited by row A2; D2 is open and cited by E1
        said = " ".join(f.line() for f in line.check(self.doc, self.questions))
        self.assertNotIn("contradictions found C1", said)
        self.assertNotIn("digressions D2", said)

    def test_a_doc_without_a_plan_is_not_compacted(self):
        doc = line.parse(DOC.split("## The plan")[0])
        findings = line.check(doc)
        self.assertEqual([f.severity for f in findings], [line.ERROR])
        self.assertIn("not compacted", findings[0].message)


class CliTest(unittest.TestCase):
    def test_check_and_rows(self):
        done = run("line.py", "check", fixture("line-doc.md"), fixture("valid"))
        self.assertEqual(done.returncode, 1, done.stderr)  # the lot is not in valid
        self.assertIn("ERROR row A2 names the tab 'lot'", done.stdout)
        self.assertIn("rows 4 · admissions 6 · errors 1 · warnings 2", done.stdout)
        done = run("line.py", "check", fixture("line-doc.md"))
        self.assertEqual(done.returncode, 0, done.stderr)
        done = run("line.py", "rows", fixture("line-doc.md"))
        self.assertEqual(done.stdout.splitlines()[0], "A1 · cites B1, B2, A1 · tabs canon")
        done = run("line.py", "rows", fixture("line-doc.md"), "--json")
        self.assertIn('"cites": [', done.stdout)

    def test_a_graph_that_does_not_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "g.json")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("not a graph")
            done = run("line.py", "check", fixture("line-doc.md"), path)
            self.assertEqual(done.returncode, 1)
            self.assertIn("ERROR shape", done.stderr)
