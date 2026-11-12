"""A project's entry may be raised from an earlier project: the edge that
makes one project's end a question of another's, and what follows from it
for the roots, the tab tree, the orders and the reader."""

import copy
import unittest

from hypo import project, read, spec
from support import load


def crossed():
    """The two-project fixture with its fault taken out and the edge the
    other way: the first project's root raises the second's entry."""
    graph = load("invalid-project-order")
    second = graph.get("second")
    for thesis in second.theses:
        thesis.terms = [t for t in thesis.terms if t.to != "canon"]
    root = graph.get("ti-esti")
    term = copy.deepcopy(root.theses[0].terms[0])
    term.to = "second"
    term.title = "What the second is for"
    root.theses[0].terms.append(term)
    return graph


class CrossingEdgeTest(unittest.TestCase):
    def test_an_earlier_project_may_raise_a_later_ones_entry(self):
        fired = [f.line() for f in spec.run(crossed(), only=["project-order", "one-root"])]
        self.assertEqual(fired, [])

    def test_a_later_project_may_not_raise_an_earlier_ones_question(self):
        fired = [f for f in spec.run(load("invalid-project-order"), only=["project-order"])]
        self.assertTrue(fired)
        self.assertIn("only from an earlier project", fired[0].message)

    def test_the_entry_is_still_its_projects_root_and_no_longer_top_level(self):
        graph = crossed()
        self.assertEqual(project.project_roots(graph), ["ti-esti", "second"])
        self.assertEqual(project.raised_entries(graph), ["second"])
        self.assertNotIn("second", project.roots(graph))
        self.assertEqual(project.placement(graph)["second"], "ti-esti")
        self.assertEqual(project.distances(graph)["second"], 1)

    def test_a_raised_entry_takes_an_order_in_the_p_series(self):
        graph = crossed()
        orders = project.orders(graph)
        self.assertEqual(orders["second"], "p0")
        self.assertEqual(orders["ti-esti"], "a0")
        siblings = sorted(orders[c] for c in ("canon", "party"))
        self.assertEqual(siblings, ["a0", "a1"])

    def test_a_root_raised_from_its_own_project_is_still_a_fault(self):
        graph = crossed()
        graph.get("second").project = "first"
        fired = [f for f in spec.run(graph, only=["one-root"])]
        self.assertTrue(any("its kind is root" in f.message for f in fired))

    def test_members_are_what_the_entry_reaches(self):
        graph = crossed()
        self.assertEqual(project.members(graph, "second"), {"second"})
        self.assertIn("second", project.members(graph, "first"))


class ReaderTest(unittest.TestCase):
    TABS = {
        "t1": {"name": "first", "order": "a0"},
        "t2": {"name": "canon", "order": "a0", "subtabOf": "t1"},
        "t3": {"name": "second", "order": "p0", "subtabOf": "t1"},
        "t4": {"name": "below", "order": "a0", "subtabOf": "t3"},
        "t5": {"name": "lease", "order": "z0"},
    }

    def test_a_p_series_tab_is_a_project_wherever_it_stands(self):
        self.assertEqual(read.project_order(self.TABS), ["first", "second"])
        of = read.projects(self.TABS)
        self.assertEqual(of["t2"], "first")
        self.assertEqual(of["t3"], "second")
        self.assertEqual(of["t4"], "second")
        self.assertEqual(of["t5"], "")

    def test_one_project_is_still_the_empty_project(self):
        tabs = {k: v for k, v in self.TABS.items() if k in ("t1", "t2")}
        self.assertEqual(set(read.projects(tabs).values()), {""})


if __name__ == "__main__":
    unittest.main()
