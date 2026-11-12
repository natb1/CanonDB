"""The share of the root each principle carries, and what follows from it."""

import unittest

from hypo import share
from support import load
from test_crossing import crossed


def plain():
    graph = load("valid")
    for q in graph.questions:
        q.pressure = 0
    return graph


class ShareTest(unittest.TestCase):
    def test_the_root_carries_the_whole_and_hands_it_down_in_equal_parts(self):
        s = share.shares(plain())
        self.assertAlmostEqual(s["ti-esti"], 1.0)
        self.assertAlmostEqual(s["canon"], 0.5)
        self.assertAlmostEqual(s["party"], 0.5)

    def test_a_principle_derived_from_several_carries_the_sum(self):
        s = share.shares(plain())
        self.assertAlmostEqual(s["attenuation"], s["canon"] + s["party"])

    def test_pressure_is_the_correction_of_the_equal_parts(self):
        graph = plain()
        graph.get("canon").pressure = 2
        s = share.shares(graph)
        self.assertAlmostEqual(s["canon"], 0.75)
        self.assertAlmostEqual(s["party"], 0.25)

    def test_a_tradition_carries_no_share(self):
        s = share.shares(plain())
        self.assertFalse(any(q.tradition and q.id in s for q in plain().questions))

    def test_an_actions_price_is_the_shares_it_diverges_from_each_once(self):
        graph = plain()
        self.assertAlmostEqual(share.price(graph, ["canon", "canon", "party"]), 1.0)
        self.assertAlmostEqual(share.price(graph, ["ti-esti"]), 1.0)

    def test_a_raised_entry_takes_its_part_of_the_raisers_share(self):
        graph = crossed()
        for q in graph.questions:
            q.pressure = 0
        s = share.shares(graph)
        self.assertAlmostEqual(s["second"], 1.0 / 3)
        self.assertAlmostEqual(s["canon"], 1.0 / 3)

    def test_pressure_standing_is_the_map_of_sparseness(self):
        graph = plain()
        graph.get("party").pressure = 3
        self.assertEqual(share.pressure_standing(graph), [("party", 3)])

    def test_a_proposal_names_an_arrangement_that_needs_no_pressure(self):
        graph = crossed()
        for q in graph.questions:
            q.pressure = 0
        graph.get("canon").pressure = 1
        found = share.proposals(graph)
        self.assertEqual([p.question for p in found], ["canon"])
        p = found[0]
        self.assertEqual((p.parent, p.siblings, p.groups), ("ti-esti", 3, 1))
        self.assertAlmostEqual(p.share_now, 0.5)
        self.assertAlmostEqual(p.share_after, 0.5)
        self.assertTrue(p.order_kept)
        self.assertIn("order of shares kept", p.line())

    def test_no_pressure_no_proposal(self):
        self.assertEqual(share.proposals(plain()), [])


if __name__ == "__main__":
    unittest.main()
