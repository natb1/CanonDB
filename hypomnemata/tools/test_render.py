"""The renderer produces the one sanctioned layout, and refuses on an ERROR."""

import os
import unittest

from hypo import model, project, render, spec

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def load(name):
    return model.load(os.path.join(FIXTURES, name + ".json"))


def sections(text):
    return [line[3:] for line in text.splitlines() if line.startswith("## ")]


class RootLayoutTest(unittest.TestCase):
    def setUp(self):
        self.text = render.render(load("valid"), "ti-esti")
        self.lines = [l for l in self.text.splitlines() if l.strip()]

    def test_opens_with_the_id(self):
        self.assertEqual(self.lines[0], "# ti-esti")

    def test_the_root_carries_no_incoming_anchors_and_the_root_line(self):
        self.assertEqual(self.lines[1],
                         "*What does a working relationship that continues require of each side?*")
        self.assertEqual(self.lines[2], "⌂ root")
        self.assertNotIn("›", self.text)

    def test_the_question_line(self):
        self.assertEqual(
            self.lines[3],
            "question: landed · root · priority 27 · load 3 · "
            "requires: promulgate the root answer")

    def test_section_order(self):
        self.assertEqual(sections(self.text),
                         ["Thesis", "Glossary", "Inbox", "Terms", "Applications", "Hinge"])

    def test_thesis_heading_and_provenance(self):
        self.assertIn("### ◆ Each side owes the other what only it can give.", self.text)
        self.assertIn("assent: assented at the merge of the opening entry · "
                      "provenance: thesis hinge", self.text)

    def test_traditions_line(self):
        self.assertIn("Traditions: plato support — the opening move is asked of what "
                      "the answerer is already doing.", self.text)

    def test_glossary_carries_the_tradition_after_the_body(self):
        self.assertIn("### ≡ elenchus", self.text)
        self.assertIn("already grants. Plato.", self.text)

    def test_the_inbox_table_lists_the_children(self):
        self.assertIn("| question | term | kind | priority | requires |", self.text)
        self.assertIn("| canon | The record between them | definitional | 12 | nothing |",
                      self.text)
        self.assertIn("| party | Two sides, two debts | case | 9 | nothing |", self.text)

    def test_the_inbox_item(self):
        self.assertIn("### promulgate the root answer", self.text)
        self.assertIn("promulgate · put the opening answer where both sides can see it · "
                      "instances once, before any descendant is asked · not done", self.text)

    def test_terms_and_applications_and_hinge(self):
        self.assertIn("### ▸ The record between them → canon", self.text)
        self.assertIn("*The record kept between them is the only thing both can point at.*",
                      self.text)
        self.assertIn("### ⚙ the opening entry", self.text)
        self.assertIn("the first file both sides pointed at · entries/opening.md · postulate",
                      self.text)
        self.assertIn("### ⚓ question: what the asking presupposes", self.text)
        self.assertIn("### ⚓ thesis: what the answer was drawn from", self.text)

    def test_blocks_are_separated_by_a_blank_line(self):
        self.assertNotIn("\n\n\n", self.text)
        self.assertTrue(self.text.endswith("\n"))


class DescendantLayoutTest(unittest.TestCase):
    def setUp(self):
        self.graph = load("valid")
        self.text = render.render(self.graph, "attenuation")
        self.lines = [l for l in self.text.splitlines() if l.strip()]

    def test_incoming_anchors_come_first_ordered_by_parent_then_term(self):
        self.assertEqual(self.lines[1],
                         "Authority to act on an unassented entry is graded down, never removed.")
        self.assertEqual(self.lines[2],
                         "the act that would settle it is graded down until the standing "
                         "side speaks")

    def test_the_lineage_line(self):
        self.assertIn("⌂ ti-esti › canon › attenuation", self.text)

    def test_deadlock_on_the_assent_line(self):
        self.assertIn("assent: none · deadlock: whether an unsettled entry may act at all "
                      "is not settled · provenance: thesis hinge", self.text)

    def test_empty_sections_are_omitted(self):
        self.assertEqual(sections(self.text),
                         ["Thesis", "Glossary", "Applications", "Hinge"])

    def test_a_term_deadlock_is_rendered_under_terms(self):
        text = render.render(self.graph, "party")
        self.assertIn("### ▸ Deadlock waits on standing → attenuation", text)
        self.assertIn("one side holds that the other may act meanwhile", text)

    def test_a_tradition_root_takes_the_root_line(self):
        self.assertIn("⌂ root", render.render(self.graph, "plato"))


class RenderAllTest(unittest.TestCase):
    def test_every_tab_in_projection_order(self):
        text = render.render_all(load("valid"))
        marks = [l for l in text.splitlines() if l.startswith("=== ")]
        self.assertEqual(marks, ["=== %s ===" % qid for qid in
                                 project.walk(load("valid"))])
        self.assertEqual(len(marks), 5)


class LinksTest(unittest.TestCase):
    def setUp(self):
        self.sidecar = render.links(load("valid"), "ti-esti")

    def test_the_sidecar_names_the_tab(self):
        self.assertEqual(self.sidecar["question"], "ti-esti")
        self.assertEqual(self.sidecar["tab"], "tab-01")

    def test_one_entry_per_anchor_with_the_term_title_as_placeholder(self):
        terms = [l for l in self.sidecar["links"] if l["kind"] == "term"]
        self.assertEqual(len(terms), 2)
        first = terms[0]
        self.assertEqual(first["to"], "canon")
        self.assertEqual(first["target"], "#tab-02.The record between them")
        self.assertIn(first["anchor"],
                      load("valid").get("ti-esti").theses[0].text)

    def test_definitions_carry_their_heading(self):
        defs = [l for l in self.sidecar["links"] if l["kind"] == "definition"]
        self.assertEqual(defs[0]["word"], "elenchus")
        self.assertEqual(defs[0]["heading"], "≡ elenchus")
        self.assertEqual(defs[0]["target"], "#tab-01.≡ elenchus")

    def test_links_all_covers_every_question(self):
        self.assertEqual(len(render.links_all(load("valid"))), 5)


class RefusalTest(unittest.TestCase):
    def test_an_error_on_the_question_refuses(self):
        graph = load("invalid-anchor-substring")
        with self.assertRaises(render.RefusedError) as caught:
            render.render(graph, "ti-esti")
        self.assertEqual(caught.exception.qid, "ti-esti")
        self.assertTrue(caught.exception.findings)

    def test_an_error_elsewhere_does_not_refuse(self):
        graph = load("invalid-anchor-substring")
        self.assertIn("# plato", render.render(graph, "plato"))

    def test_a_graph_wide_error_refuses_everywhere(self):
        graph = load("invalid-one-root")
        with self.assertRaises(render.RefusedError):
            render.render(graph, "plato")

    def test_a_warning_does_not_refuse(self):
        graph = load("invalid-no-ids-in-prose")
        self.assertTrue(spec.run(graph))
        self.assertIn("# canon", render.render(graph, "canon"))

    def test_render_all_refuses_on_any_error(self):
        with self.assertRaises(render.RefusedError):
            render.render_all(load("invalid-acyclic"))

    def test_an_unknown_question_is_a_key_error(self):
        with self.assertRaises(KeyError):
            render.body(load("valid"), "absent")


if __name__ == "__main__":
    unittest.main()
