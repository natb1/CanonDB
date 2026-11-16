"""A divergence note: data that contradicts a principle, tracked on its tab."""

import unittest
from datetime import date

from hypo import crossing, divergence, due, spec
from hypo.model import Note
from support import load
from test_crossing import crossed

WHOLE = ("divergence: more plastic bought than the principle allows · action: buy in "
         "bulk from the co-op · whose: user · price: two hours a week · budget: none · "
         "read 2026-11-12: unchanged")


class ParseTest(unittest.TestCase):
    def test_the_parts_of_a_note(self):
        parts = divergence.parse(WHOLE)
        self.assertEqual(parts["data"], "more plastic bought than the principle allows")
        self.assertEqual(parts["action"], "buy in bulk from the co-op")
        self.assertEqual(parts["whose"], "user")
        self.assertEqual(parts["price"], "two hours a week")
        self.assertEqual(parts["readings"], [("2026-11-12", "unchanged")])
        self.assertEqual(divergence.missing(parts), [])

    def test_another_note_is_not_one(self):
        self.assertIsNone(divergence.parse("pending: something a run could not apply"))

    def test_compose_and_parse_agree(self):
        words = divergence.compose("d", "a", "ai", "p", "allocated", [("2026-01-01", "r")])
        parts = divergence.parse(words)
        self.assertEqual((parts["data"], parts["action"], parts["whose"], parts["price"],
                          parts["budget"]), ("d", "a", "ai", "p", "allocated"))

    def test_what_is_left_untracked_is_named(self):
        self.assertEqual(divergence.missing(divergence.parse("divergence: only the data")),
                         ["action", "whose", "price"])
        parts = divergence.parse("divergence: d · action: a · whose: nobody · price: p")
        self.assertIn("whose (user or ai)", divergence.missing(parts))


class RecordTest(unittest.TestCase):
    def graph(self, body=WHOLE):
        graph = load("valid")
        graph.get("canon").notes.append(Note("thesis", body))
        return graph

    def test_a_whole_note_passes_the_check_and_is_due(self):
        graph = self.graph()
        self.assertEqual(spec.run(graph, only=["divergence-complete"]), [])
        rows = [r for r in due.rows(graph, today=date(2026, 11, 12)) if r.kind == "divergence"]
        self.assertEqual([r.question for r in rows], ["canon"])
        self.assertIn("buy in bulk", rows[0].next)

    def test_a_note_that_names_no_action_fails_it(self):
        fired = spec.run(self.graph("divergence: only the data"), only=["divergence-complete"])
        self.assertEqual([f.question for f in fired], ["canon"])

    def test_found_lists_each_with_its_gaps(self):
        found = divergence.found(self.graph("divergence: only the data"))
        self.assertEqual(found[0].missing, ("action", "whose", "price"))


class CrossingTest(unittest.TestCase):
    def test_an_edge_to_a_later_projects_entry_is_reviewed(self):
        found = crossing.edges(crossed())
        self.assertEqual([(e.raiser, e.entry, e.dependent) for e in found],
                         [("ti-esti", "second", "second")])
        self.assertFalse(found[0].unmet)
        self.assertIn("record: nothing diverges", "\n".join(crossing.listing(found)))

    def test_an_entry_whose_clause_cannot_be_met_stands_first_and_says_so(self):
        graph = crossed()
        graph.get("second").notes.append(Note("thesis", divergence.compose(
            "the clause cannot be met in the third case", "restate the case", "user",
            "a line")))
        found = crossing.edges(graph)
        self.assertTrue(found[0].unmet)
        self.assertIn("CANNOT BE MET", crossing.listing(found)[0])

    def test_of_names_the_containing_project(self):
        self.assertEqual(crossing.edges(crossed(), "second"), [])
        self.assertEqual(len(crossing.edges(crossed(), "first")), 1)

    def test_an_edge_inside_a_project_is_not_a_crossing(self):
        self.assertEqual(crossing.edges(load("valid")), [])


if __name__ == "__main__":
    unittest.main()
