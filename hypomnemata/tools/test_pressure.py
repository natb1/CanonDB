"""Tests for pressure.py: the real nodes/ plus synthetic cases."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import yaml

import pressure

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
    """root -> a -> b, with three followups and two postulates on the root."""
    root = {
        "id": "root", "q": "Root?", "parent": None, "state": "in-line", "stub": False,
        "thesis": "prior",
        "hinge": {"model": "m", "harness": "h", "canon_sha": "s", "presuppositions": ["p"]},
        "terms": [{"id": "t-one", "clause": "One.", "group": "of-the-human",
                   "state": "dormant", "child": None}],
        "postulates": [
            {"id": "p-sub", "claim": "c", "rests_on": ["a"], "discharge": "f1"},
            {"id": "p-all", "claim": "c", "rests_on": ["*"], "discharge": "f2"},
        ],
        "followups": [
            {"id": "f1", "term": "t-one", "kind": "case", "q": "?", "toward": "a",
             "state": "drafted", "requires": [], "after": [],
             "pressure": {"blocked": 1, "distance": 1}},
            {"id": "f2", "term": "t-one", "kind": "definitional", "q": "?", "toward": "b",
             "state": "drafted", "requires": ["a1"], "after": [],
             "pressure": {"blocked": 0, "distance": 2}},
            {"id": "f3", "term": "t-one", "kind": "case", "q": "?", "toward": "b",
             "state": "drafted", "requires": [], "after": ["f1"],
             "pressure": {"blocked": 0, "distance": 3}},
        ],
        "actions": [{"id": "a1", "kind": "build", "what": "x",
                     "obligation": "t-one", "done": False}],
    }
    a = {"id": "a", "q": "A?", "parent": "root", "state": "held", "stub": True, "thesis": "p"}
    b = {"id": "b", "q": "B?", "parent": "a", "state": "held", "stub": True, "thesis": "p"}
    return {"root": root, "a": a, "b": b}


class SyntheticTest(unittest.TestCase):
    def setUp(self):
        self.dir = NodesDir(sample())
        self.graph = pressure.load_graph(self.dir.path)

    def tearDown(self):
        self.dir.tmp.cleanup()

    def test_tree_order_is_parent_before_child(self):
        self.assertEqual(["root", "a", "b"], self.graph.tree_order())
        self.assertEqual(3, self.graph.subtree_size("root"))
        self.assertEqual(2, self.graph.subtree_size("a"))

    def test_postulate_load(self):
        posts = {p["id"]: p for p in self.graph.nodes["root"]["postulates"]}
        self.assertEqual(3, self.graph.postulate_load(posts["p-all"]))   # "*" is every node
        self.assertEqual(2, self.graph.postulate_load(posts["p-sub"]))   # a and its descendant b

    def test_load_is_summed_over_discharged_postulates(self):
        self.assertEqual(2, self.graph.load(("root", "f1")))
        self.assertEqual(3, self.graph.load(("root", "f2")))
        self.assertEqual(0, self.graph.load(("root", "f3")))

    def test_intrinsic(self):
        self.assertEqual(3, self.graph.d_max)
        self.assertEqual(6.0, self.graph.intrinsic(("root", "f1")))   # 1 + 2 + (4-1)
        self.assertEqual(5.0, self.graph.intrinsic(("root", "f2")))   # 0 + 3 + (4-2)
        self.assertEqual(1.0, self.graph.intrinsic(("root", "f3")))   # 0 + 0 + (4-3)

    def test_priority_carries_the_dependents(self):
        self.assertEqual(7.0, self.graph.priority(("root", "f1")))     # 6 + f3
        self.assertEqual(5.0, self.graph.priority(("root", "f2")))
        self.assertEqual(1.0, self.graph.priority(("root", "f3")))

    def test_node_load(self):
        self.assertEqual(12.0, self.graph.node_load("root"))
        self.assertEqual(0.0, self.graph.node_load("a"))

    def test_ready(self):
        self.assertTrue(self.graph.ready(("root", "f1")))     # nothing required
        self.assertFalse(self.graph.ready(("root", "f2")))    # a1 undone
        self.assertFalse(self.graph.ready(("root", "f3")))    # f1 not landed
        self.assertEqual(["a1"], self.graph.blockers(("root", "f2")))
        self.assertEqual(["f1"], self.graph.blockers(("root", "f3")))

    def test_ready_when_the_action_is_done_and_the_after_landed(self):
        mapping = sample()
        mapping["root"]["actions"][0]["done"] = True
        mapping["root"]["followups"][0]["state"] = "landed"
        with NodesDir(mapping) as path:
            graph = pressure.load_graph(path)
        self.assertTrue(graph.ready(("root", "f2")))
        self.assertTrue(graph.ready(("root", "f3")))

    def test_action_priority_reaches_through_after(self):
        self.assertEqual(5.0, self.graph.action_priority("root", "a1"))
        rows = self.graph.inbox_rows()
        self.assertEqual(1, len(rows))
        self.assertEqual(("a1", 1, 5.0), (rows[0]["action"], rows[0]["unblocks"], rows[0]["priority"]))

    def test_frontier_is_ready_first_then_priority_desc(self):
        rows = self.graph.frontier_rows()
        self.assertEqual(["f1", "f2", "f3"], [r["id"] for r in rows])
        self.assertTrue(rows[0]["ready"])
        self.assertFalse(rows[1]["ready"])

    def test_terminal_followups_leave_the_frontier(self):
        mapping = sample()
        mapping["root"]["followups"][0]["state"] = "abandoned"
        with NodesDir(mapping) as path:
            graph = pressure.load_graph(path)
        self.assertEqual(["f2", "f3"], [r["id"] for r in graph.frontier_rows()])
        self.assertEqual(6.0, graph.node_load("root"))

    def test_default_distance(self):
        mapping = sample()
        del mapping["root"]["followups"][2]["pressure"]
        with NodesDir(mapping) as path:
            graph = pressure.load_graph(path)
        self.assertEqual(pressure.DEFAULT_DISTANCE, graph.distance(("root", "f3")))


class CycleTest(unittest.TestCase):
    def test_after_cycle_is_an_error(self):
        mapping = sample()
        mapping["root"]["followups"][0]["after"] = ["f3"]
        with NodesDir(mapping) as path:
            with self.assertRaises(pressure.GraphError):
                pressure.load_graph(path)
            self.assertEqual(1, pressure.main(["--nodes", str(path)]))

    def test_tree_cycle_is_an_error(self):
        mapping = sample()
        mapping["root"]["parent"] = "b"
        with NodesDir(mapping) as path:
            with self.assertRaises(pressure.GraphError):
                pressure.load_graph(path)
            self.assertEqual(1, pressure.main(["--nodes", str(path)]))


class OutputTest(unittest.TestCase):
    def setUp(self):
        self.dir = NodesDir(sample())
        self.graph = pressure.load_graph(self.dir.path)

    def tearDown(self):
        self.dir.tmp.cleanup()

    def test_markdown_shape(self):
        text = pressure.render_markdown(self.graph)
        self.assertIn("## Frontier", text)
        self.assertIn("## Inbox", text)
        self.assertIn("## Load", text)
        self.assertIn("| id | node | kind | target | priority | ready | blocked by |", text)
        self.assertIn("| action | kind | what | obligation | unblocks | max priority |", text)
        self.assertIn("| node | load | direct followups | subtree size |", text)

    def test_json_shape(self):
        data = json.loads(pressure.render_json(self.graph))
        self.assertEqual({"frontier", "inbox", "load"}, set(data))
        self.assertEqual(3, len(data["frontier"]))
        self.assertEqual(3, len(data["load"]))

    def test_out_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "pressure.md"
            self.assertEqual(0, pressure.main(["--nodes", str(self.dir.path), "--out", str(out)]))
            self.assertIn("## Frontier", out.read_text(encoding="utf-8"))


class RealNodesTest(unittest.TestCase):
    def setUp(self):
        if not REAL_NODES.is_dir():
            self.skipTest("no nodes/ directory")
        self.graph = pressure.load_graph(REAL_NODES)

    def test_root_and_tree(self):
        self.assertEqual("ti-esti", self.graph.tree_order()[0])
        self.assertEqual(len(self.graph.nodes), self.graph.subtree_size("ti-esti"))

    def test_star_counts_every_node(self):
        posts = {p["id"]: p for p in self.graph.nodes["ti-esti"]["postulates"]}
        self.assertEqual(len(self.graph.nodes),
                         self.graph.postulate_load(posts["merge-is-assent"]))

    def test_frontier_head(self):
        rows = self.graph.frontier_rows()
        self.assertEqual("f2", rows[0]["id"])
        self.assertEqual(sorted([r["priority"] for r in rows], reverse=True),
                         [r["priority"] for r in rows])
        self.assertFalse(any(r["ready"] for r in rows))   # a1 and a2 are undone


if __name__ == "__main__":
    unittest.main()
