"""A body write retires the blocks other tabs link into, and relink repoints them."""

import unittest

import test_apply
import test_render
from hypo import apply, render
import relink

load = test_render.load


def pages_with(graph, session):
    """Every tab as the document would export it, its links applied against
    outlines the document minted in ``session``."""
    by_tab = test_apply.outlines(graph, session)
    pages = {}
    for q in graph.questions:
        out = render.body(graph, q.id)
        for entry in render.links(graph, q.id)["links"]:
            href = apply.resolve(graph, entry["target"], by_tab, graph.artifact, q.tab)
            if href is None:
                continue
            find = entry["find"]
            found = out.split(find["text"])
            if len(found) <= find["nth"]:
                continue
            before = find["text"].join(found[:find["nth"]])
            after = find["text"].join(found[find["nth"]:])
            out = "%s[%s](%s)%s" % (before, find["text"], href, after)
        pages[q.id] = out
    return pages


class RelinkTest(unittest.TestCase):
    def setUp(self):
        self.graph = load("valid")
        self.pages = pages_with(self.graph, "old")

    def outline(self, qid, session):
        return {self.graph.get(qid).tab:
                apply.parse_outline(test_apply.outline_of(self.graph, qid, session))}

    def test_nothing_to_repoint_while_the_blocks_stand(self):
        self.assertEqual(relink.stale_links(self.graph, ["ti-esti"], self.pages,
                                            self.outline("ti-esti", "old")), {})

    def test_a_rewrite_retires_what_other_tabs_point_at(self):
        out = relink.stale_links(self.graph, ["ti-esti"], self.pages,
                                 self.outline("ti-esti", "new"))
        linking = {q.id for q in self.graph.questions
                   if q.id != "ti-esti" and "#tab-01." in self.pages[q.id]}
        self.assertEqual(set(out), linking)
        self.assertTrue(linking)
        for qid, ops in out.items():
            for op in ops:
                href = op["add"][0]["href"]
                self.assertIn("#tab-01.new.", href)
                self.assertEqual(op["op"], "format")
                self.assertIn(op["target"]["text"], self.pages[qid])

    def test_the_rewritten_tab_itself_is_left_alone(self):
        out = relink.stale_links(self.graph, ["ti-esti"], self.pages,
                                 self.outline("ti-esti", "new"))
        self.assertNotIn("ti-esti", out)

    def test_links_into_other_tabs_are_not_touched(self):
        out = relink.stale_links(self.graph, ["ti-esti"], self.pages,
                                 self.outline("ti-esti", "new"))
        for ops in out.values():
            for op in ops:
                self.assertIn("#tab-01.", op["add"][0]["href"])

    def test_every_op_points_at_a_block_the_new_outline_holds(self):
        new = self.outline("ti-esti", "new")
        ids = {b.id for blocks in new.values() for b in blocks if b.id}
        out = relink.stale_links(self.graph, ["ti-esti"], self.pages, new)
        for ops in out.values():
            for op in ops:
                self.assertIn(op["add"][0]["href"].rsplit("#", 1)[-1].split(".", 1)[1], ids)



class UnresolvedTest(unittest.TestCase):
    def test_an_outline_that_pairs_with_no_render_is_said_not_passed(self):
        """Nothing repointed is not the same as nothing stale."""
        graph = load("valid")
        pages = pages_with(graph, "old")
        tab = graph.get("canon").tab
        self.assertTrue(any(("#%s." % tab) in page for page in pages.values()))
        drifted = {tab: apply.parse_outline(test_apply.outline_of(graph, "canon", "new"))}
        drifted[tab].append(apply.Block(id="new.99", kind="paragraph", heading=2, text="Another"))
        with self.assertRaises(apply.Unresolved):
            relink.stale_links(graph, ["canon"], pages, drifted)


if __name__ == "__main__":
    unittest.main()
