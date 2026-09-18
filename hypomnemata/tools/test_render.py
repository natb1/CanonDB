"""Tests for render.py: the real nodes/ plus synthetic cases."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import yaml

import pressure
import render

REAL_NODES = Path(__file__).resolve().parent.parent / "nodes"


class NodesDir:
    def __init__(self, mapping):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name)
        for stem, node in mapping.items():
            (self.path / (stem + ".yml")).write_text(
                yaml.safe_dump(node, sort_keys=False), encoding="utf-8")

    def __enter__(self):
        return self.path

    def __exit__(self, *exc):
        self.tmp.cleanup()


def sample():
    root = {
        "id": "root", "q": "Root?", "parent": None, "state": "landed",
        "canon": "v1:canon/root.md", "stub": False,
        "thesis": "the prior\nover two lines",
        "defs": [{"term": "party", "sense": "an end of a bond"}],
        "hinge": {"model": "m", "harness": "h", "canon_sha": "s",
                  "presuppositions": ["the human continues"]},
        "postulates": [{"id": "p1", "claim": "assumed", "rests_on": ["*"],
                        "discharge": "f1", "decided_not_to_examine": False},
                       {"id": "p2", "claim": "assumed too", "rests_on": ["a"],
                        "discharge": None, "decided_not_to_examine": True}],
        "terms": [{"id": "t-one", "clause": "One.", "group": "of-the-human",
                   "state": "dormant", "child": None}],
        "followups": [{"id": "f1", "term": "t-one", "kind": "case", "q": "Why?",
                       "toward": "a", "state": "drafted", "requires": ["a1"],
                       "after": [], "pressure": {"blocked": 1, "distance": 1},
                       "draft": "the prior on the answer\nwrapped"}],
        "actions": [{"id": "a1", "kind": "build", "what": "x",
                     "obligation": "t-one", "done": False}],
        "traditions": [{"name": "Plato, Meno", "relation": "support", "note": "the prior question"}],
    }
    a = {"id": "a", "q": "A?", "parent": "root", "state": "held", "stub": True,
         "thesis": "a stub prior", "hinge": {"harness": "another harness"}}
    return {"root": root, "a": a}


class RenderTest(unittest.TestCase):
    def setUp(self):
        self.dir = NodesDir(sample())
        self.graph = pressure.load_graph(self.dir.path)
        self.text = render.render_node(self.graph, "root")

    def tearDown(self):
        self.dir.tmp.cleanup()

    def test_header_carries_state_and_canon(self):
        self.assertTrue(self.text.startswith("### root · landed · canon: v1:canon/root.md\n"))

    def test_question_and_thesis(self):
        self.assertIn("**Q** Root?", self.text)
        self.assertIn("the prior\nover two lines", self.text)

    def test_section_order(self):
        wanted = ["**Q**", "**Defines**", "**Hinge**", "**Postulates**", "**Terms**",
                  "**Follow-ups**", "**Actions**", "**Traditions**"]
        found = [self.text.index(label) for label in wanted]
        self.assertEqual(sorted(found), found)

    def test_table_headers(self):
        for header in ["| term | sense |",
                       "| id | claim | rests on | discharged by | note |",
                       "| id | clause | group | state | child |",
                       "| id | q | kind | term | toward | requires | after | priority | ready |",
                       "| id | kind | what | obligation | done |",
                       "| name | relation | note |"]:
            self.assertIn(header, self.text)

    def test_hinge_is_full_on_the_root(self):
        self.assertIn("- model: m", self.text)
        self.assertIn("- presuppositions:\n  - the human continues", self.text)
        self.assertNotIn("inherits", self.text)

    def test_postulate_note_from_decided_not_to_examine(self):
        self.assertIn("| p2 | assumed too | a | — | decided not to examine |", self.text)

    def test_priority_and_ready_come_from_pressure(self):
        priority = pressure.num(self.graph.priority(("root", "f1")))
        self.assertIn("| f1 | Why? | case | t-one | a | a1 | — | %s | no |" % priority, self.text)

    def test_draft_is_one_blockquote_line(self):
        self.assertIn("> **draft f1** — the prior on the answer wrapped", self.text)

    def test_stub_is_one_line_plus_thesis(self):
        text = render.render_node(self.graph, "a")
        self.assertTrue(text.startswith("### a · stub · A?\n"))
        self.assertIn("a stub prior", text)
        self.assertNotIn("**Q**", text)

    def test_all_is_tree_order(self):
        text = render.render(self.graph, self.graph.tree_order())
        self.assertLess(text.index("### root"), text.index("### a"))

    def test_main_writes_and_rejects(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "doc.md"
            self.assertEqual(0, render.main(["--nodes", str(self.dir.path), "--all",
                                             "--out", str(out)]))
            self.assertIn("### root", out.read_text(encoding="utf-8"))
        self.assertEqual(1, render.main(["--nodes", str(self.dir.path), "ghost"]))
        self.assertEqual(1, render.main(["--nodes", str(self.dir.path)]))


class NonRootHingeTest(unittest.TestCase):
    def test_override_says_what_it_inherits(self):
        mapping = sample()
        mapping["a"]["stub"] = False
        mapping["a"]["terms"] = []
        with NodesDir(mapping) as path:
            graph = pressure.load_graph(path)
            text = render.render_node(graph, "a")
        self.assertIn("- inherits root", text)
        self.assertIn("- harness: another harness", text)
        self.assertNotIn("- model:", text)


class RealNodesTest(unittest.TestCase):
    def setUp(self):
        if not REAL_NODES.is_dir():
            self.skipTest("no nodes/ directory")
        self.graph = pressure.load_graph(REAL_NODES)

    def test_ti_esti_entry(self):
        text = render.render_node(self.graph, "ti-esti")
        self.assertTrue(text.startswith("### ti-esti · in-line\n"))
        for label in ["**Q**", "**Defines**", "**Hinge**", "**Postulates**", "**Terms**",
                      "**Follow-ups**", "**Actions**", "**Traditions**"]:
            self.assertIn(label, text)
        self.assertIn("> **draft f1** —", text)

    def test_every_node_renders(self):
        for nid in self.graph.tree_order():
            self.assertTrue(render.render_node(self.graph, nid).startswith("### %s ·" % nid))

    def test_stubs_render_as_one_line(self):
        text = render.render_node(self.graph, "canon")
        self.assertTrue(text.startswith("### canon · stub · What is the body both act on?"))


if __name__ == "__main__":
    unittest.main()
