"""Tests for check.py: the real nodes/ plus synthetic cases."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import yaml

import check

REAL_NODES = Path(__file__).resolve().parent.parent / "nodes"


def root_node(**over):
    node = {
        "id": "root", "q": "Root?", "parent": None, "state": "in-line",
        "canon": None, "stub": False, "thesis": "the prior",
        "hinge": {"model": "m", "harness": "h", "canon_sha": "s",
                  "presuppositions": ["p"]},
        "terms": [{"id": "t-one", "clause": "One.", "group": "of-the-human",
                   "state": "dormant", "child": None}],
    }
    node.update(over)
    return node


def stub_node(nid, parent="root", **over):
    node = {"id": nid, "q": "Q %s?" % nid, "parent": parent,
            "state": "held", "stub": True, "thesis": "the prior"}
    node.update(over)
    return node


class NodesDir:
    """A temporary nodes/ directory built from {stem: node dict}."""

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


def findings_of(mapping):
    with NodesDir(mapping) as path:
        _nodes, findings = check.check(path)
    return findings


def errors(mapping):
    return [m for _n, m in findings_of(mapping).errors]


def warnings(mapping):
    return [m for _n, m in findings_of(mapping).warnings]


def has(messages, fragment):
    return any(fragment in m for m in messages)


class RealNodesTest(unittest.TestCase):
    def test_real_nodes_are_clean(self):
        if not REAL_NODES.is_dir():
            self.skipTest("no nodes/ directory")
        nodes, findings = check.check(REAL_NODES)
        self.assertTrue(nodes)
        self.assertEqual([], ["%s: %s" % f for f in findings.errors])

    def test_exit_code_is_zero(self):
        if not REAL_NODES.is_dir():
            self.skipTest("no nodes/ directory")
        self.assertEqual(0, check.main(["--nodes", str(REAL_NODES)]))


class SyntheticTest(unittest.TestCase):
    def test_minimal_tree_is_clean(self):
        f = findings_of({"root": root_node(), "leaf": stub_node("leaf")})
        self.assertEqual([], f.errors)
        self.assertEqual([], f.warnings)

    def test_id_must_match_stem(self):
        self.assertTrue(has(errors({"root": root_node(), "other": stub_node("leaf")}),
                            "does not match filename stem"))

    def test_kebab_case(self):
        self.assertTrue(has(errors({"root": root_node(), "Not_Kebab": stub_node("Not_Kebab")}),
                            "kebab-case"))

    def test_parent_must_exist(self):
        self.assertTrue(has(errors({"root": root_node(), "leaf": stub_node("leaf", parent="ghost")}),
                            "does not exist"))

    def test_exactly_one_root(self):
        self.assertTrue(has(errors({"root": root_node(), "leaf": stub_node("leaf", parent=None)}),
                            "2 roots"))
        self.assertTrue(has(errors({"a": stub_node("a", parent="b"), "b": stub_node("b", parent="a")}),
                            "no root node"))

    def test_parent_cycle(self):
        msgs = errors({"root": root_node(),
                       "a": stub_node("a", parent="b"), "b": stub_node("b", parent="a")})
        self.assertTrue(has(msgs, "cyclic"))

    def test_state_vocabulary_and_canon(self):
        self.assertTrue(has(errors({"root": root_node(state="musing")}), "not in vocabulary"))
        self.assertTrue(has(errors({"root": root_node(state="landed", canon=None)}),
                            "requires a canon ref"))
        self.assertFalse(has(errors({"root": root_node(state="landed", canon="v1:canon/root.md")}),
                             "requires a canon ref"))

    def test_terms(self):
        dupe = root_node(terms=[{"id": "t-one", "clause": "a", "state": "dormant"},
                                {"id": "t-one", "clause": "b", "state": "dormant"}])
        self.assertTrue(has(errors({"root": dupe}), "duplicate term id"))
        bad_state = root_node(terms=[{"id": "t-one", "clause": "a", "state": "asleep"}])
        self.assertTrue(has(errors({"root": bad_state}), "not in vocabulary"))
        landed = root_node(terms=[{"id": "t-one", "clause": "a", "state": "landed", "child": None}])
        self.assertTrue(has(errors({"root": landed, "leaf": stub_node("leaf")}),
                            "no existing child"))
        wrong = root_node(terms=[{"id": "t-one", "clause": "a", "state": "landed", "child": "leaf"}])
        msgs = errors({"root": wrong, "leaf": stub_node("leaf", parent="mid"),
                       "mid": stub_node("mid")})
        self.assertTrue(has(msgs, "has parent"))

    def test_followups(self):
        def with_fu(**over):
            fu = {"id": "f1", "term": "t-one", "kind": "case", "q": "?",
                  "toward": "leaf", "state": "drafted", "requires": [], "after": []}
            fu.update(over)
            return {"root": root_node(followups=[fu],
                                      actions=[{"id": "a1", "kind": "build", "what": "x",
                                                "obligation": "t-one", "done": False}]),
                    "leaf": stub_node("leaf")}

        self.assertEqual([], findings_of(with_fu()).errors)
        self.assertTrue(has(errors(with_fu(term="t-ghost")), "is not a term of this node"))
        self.assertTrue(has(errors(with_fu(kind="rhetorical")), "kind"))
        self.assertTrue(has(errors(with_fu(toward="ghost")), "toward"))
        self.assertTrue(has(errors(with_fu(requires=["a9"])), "not an action of this node"))
        self.assertTrue(has(errors(with_fu(after=["f9"])), "is not a followup id"))

    def test_requires_may_name_an_ancestor_action(self):
        root = root_node(actions=[{"id": "a1", "kind": "build", "what": "x",
                                   "obligation": "t-one", "done": False}])
        child = {"id": "leaf", "q": "Q?", "parent": "root", "state": "held", "stub": False,
                 "thesis": "p",
                 "terms": [{"id": "t-two", "clause": "c", "state": "dormant"}],
                 "followups": [{"id": "f1", "term": "t-two", "kind": "case", "q": "?",
                                "toward": "leaf", "state": "drafted",
                                "requires": ["a1"], "after": []}]}
        self.assertEqual([], findings_of({"root": root, "leaf": child}).errors)

    def test_after_cycle(self):
        fus = [{"id": "f1", "term": "t-one", "kind": "case", "q": "?", "toward": "root",
                "state": "drafted", "after": ["f2"]},
               {"id": "f2", "term": "t-one", "kind": "case", "q": "?", "toward": "root",
                "state": "drafted", "after": ["f1"]}]
        self.assertTrue(has(errors({"root": root_node(followups=fus)}), "after cycle"))

    def test_postulates(self):
        def with_p(**over):
            p = {"id": "p1", "claim": "c", "rests_on": ["*"], "discharge": None}
            p.update(over)
            return {"root": root_node(postulates=[p])}

        self.assertEqual([], findings_of(with_p()).errors)
        self.assertTrue(has(errors(with_p(discharge="f9")), "is not a followup id"))
        self.assertTrue(has(errors(with_p(rests_on=["ghost"])), "does not exist"))
        self.assertTrue(has(errors(with_p(rests_on=[])), "no rests_on"))

    def test_hinge(self):
        short = root_node(hinge={"model": "m"})
        self.assertTrue(has(errors({"root": short}), "root hinge is missing"))
        child = {"id": "leaf", "q": "Q?", "parent": "root", "state": "held", "stub": True,
                 "thesis": "p", "hinge": {"model": "m"}}
        self.assertTrue(has(errors({"root": root_node(), "leaf": child}),
                            "repeats the inherited value"))
        child["hinge"] = {"model": "other"}
        self.assertEqual([], findings_of({"root": root_node(), "leaf": child}).errors)

    def test_actions(self):
        def with_a(**over):
            a = {"id": "a1", "kind": "build", "what": "x", "obligation": "t-one", "done": False}
            a.update(over)
            return {"root": root_node(actions=[a])}

        self.assertEqual([], findings_of(with_a()).errors)
        self.assertTrue(has(errors(with_a(kind="ponder")), "kind"))
        self.assertTrue(has(errors(with_a(obligation="t-ghost")), "is not a term anywhere"))
        root = root_node(terms=[{"id": "t-one", "clause": "c", "group": "of-the-AI",
                                 "state": "dormant"}],
                         actions=[{"id": "a1", "kind": "build", "what": "x",
                                   "obligation": "t-one", "done": False}])
        self.assertTrue(has(warnings({"root": root}), "is not in group of-the-human"))

    def test_duplicate_def_term_warns(self):
        root = root_node(defs=[{"term": "party", "sense": "one"}])
        leaf = stub_node("leaf", defs=[{"term": "party", "sense": "two"}])
        self.assertTrue(has(warnings({"root": root, "leaf": leaf}), "is also defined on"))

    def test_iso_date_warns(self):
        self.assertTrue(has(warnings({"root": root_node(thesis="settled 2026-09-18")}),
                            "ISO date in thesis"))
        root = root_node(
            terms=[{"id": "t-one", "clause": "on 2026-09-18", "state": "dormant"}],
            followups=[{"id": "f1", "term": "t-one", "kind": "case", "q": "?",
                        "toward": "root", "state": "drafted", "draft": "by 2026-09-18"}])
        msgs = warnings({"root": root})
        self.assertTrue(has(msgs, "ISO date in clause"))
        self.assertTrue(has(msgs, "ISO date in draft"))

    def test_hinge_dates_are_exempt(self):
        root = root_node(hinge={"model": "m", "harness": "h", "canon_sha": "2026-09-18",
                                "presuppositions": ["p"]})
        self.assertEqual([], findings_of({"root": root}).warnings)

    def test_overloaded_stub_warns(self):
        fus = [{"id": "f%d" % i, "term": "t-one", "kind": "case", "q": "?",
                "toward": "leaf", "state": "drafted"} for i in range(1, 5)]
        msgs = warnings({"root": root_node(followups=fus), "leaf": stub_node("leaf")})
        self.assertTrue(has(msgs, "target of 4 followups"))

    def test_main_exits_one_on_error(self):
        with NodesDir({"root": root_node(state="musing")}) as path:
            self.assertEqual(1, check.main(["--nodes", str(path)]))


if __name__ == "__main__":
    unittest.main()
