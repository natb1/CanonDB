"""The tab-tree projection is deterministic, total and correctly ordered."""

import copy
import json
import os
import tempfile
import unittest

from hypo import model, project, spec

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def load(name):
    return model.load(os.path.join(FIXTURES, name + ".json"))


def rewrite(name, mutate):
    """Load a fixture, mutate its JSON, and load the result."""
    with open(os.path.join(FIXTURES, name + ".json"), encoding="utf-8") as fh:
        data = json.load(fh)
    mutate(data)
    handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                         encoding="utf-8")
    try:
        json.dump(data, handle)
        handle.close()
        return model.load(handle.name)
    finally:
        os.unlink(handle.name)


class RootTest(unittest.TestCase):
    def setUp(self):
        self.graph = load("valid")

    def test_main_root(self):
        self.assertEqual(project.main_root(self.graph), "ti-esti")

    def test_tradition_roots_are_lexicographic(self):
        self.assertEqual(project.tradition_roots(self.graph), ["plato"])

    def test_roots_put_the_main_root_first(self):
        self.assertEqual(project.roots(self.graph), ["ti-esti", "plato"])


class DistanceTest(unittest.TestCase):
    def setUp(self):
        self.graph = load("valid")

    def test_distances(self):
        d = project.distances(self.graph)
        self.assertEqual(d["ti-esti"], 0)
        self.assertEqual(d["canon"], 1)
        self.assertEqual(d["party"], 1)
        self.assertEqual(d["attenuation"], 2)

    def test_a_tradition_root_is_zero(self):
        self.assertEqual(project.distances(self.graph)["plato"], 0)

    def test_unreached_is_infinite(self):
        # a pair no root reaches: each is the other's only source.
        def add_island(data):
            for a, b in (("x-one", "x-two"), ("x-two", "x-one")):
                data["questions"].append({
                    "id": a, "tab": "tab-" + a, "body": "body-" + a,
                    "question": "?", "state": "held", "kind": "case", "pressure": 0,
                    "theses": [{"title": "t", "assent": "none", "state": "held",
                                "text": "t",
                                "terms": [{"title": "to " + b, "to": b,
                                           "anchors": ["t"]}]}]})
        d = project.distances(rewrite("valid", add_island))
        self.assertEqual(d["x-one"], project.INF)
        self.assertEqual(d["x-two"], project.INF)
        self.assertEqual(d["ti-esti"], 0)


class ParentTest(unittest.TestCase):
    def test_tie_is_broken_lexicographically(self):
        # canon and party both reach attenuation at distance 1; canon < party.
        self.assertEqual(project.parents(load("valid"))["attenuation"], "canon")

    def test_the_nearer_source_wins_over_the_lexicographic_one(self):
        # give ti-esti (distance 0) a term to attenuation: it must take the parent
        # from canon even though "canon" sorts before "ti-esti".
        def add_term(data):
            data["questions"][0]["theses"][0]["terms"].append({
                "title": "Straight to the grading", "to": "attenuation",
                "anchors": ["Authority to act follows how settled the question is"],
                "deadlock": None})
        self.assertEqual(project.parents(rewrite("valid", add_term))["attenuation"],
                         "ti-esti")

    def test_orders_sort_as_strings_the_way_they_do_as_numbers(self):
        """The document's tray sorts orders as strings, so an eleventh
        tradition ordered b10 would stand between b1 and b2. An index is
        padded to the width its group needs, and a group of ten or fewer keeps
        the orders it had."""
        def many(data):
            for n in range(10):
                data["questions"].append({
                    "id": "party-%02d" % n, "tab": "tab-p%02d" % n,
                    "body": "body-p%02d" % n, "question": "?", "state": "held",
                    "kind": "definitional", "pressure": 0, "requires": [],
                    "party": "party-%02d" % n, "theses": []})
        graph = rewrite("valid", many)
        orders = project.orders(graph)
        heads = project.tradition_roots(graph)
        self.assertEqual(len(heads), 11)
        self.assertEqual(sorted(heads, key=lambda h: orders[h]), heads)
        self.assertEqual((orders[heads[0]], orders[heads[-1]]), ("b00", "b10"))
        self.assertEqual(orders["ti-esti"], "a0")
        self.assertEqual(project.orders(load("valid"))["plato"], "b0")

    def test_top_level_questions_have_no_parent(self):
        parents = project.parents(load("valid"))
        self.assertIsNone(parents["ti-esti"])
        self.assertIsNone(parents["plato"])

    def test_a_cycle_does_not_hang_or_loop(self):
        graph = load("invalid-acyclic")
        parents = project.parents(graph)
        for qid in [q.id for q in graph.questions]:
            self.assertNotIn(qid, project.lineage(graph, qid)[:-1])

    def test_lineage(self):
        self.assertEqual(project.lineage(load("valid"), "attenuation"),
                         ["ti-esti", "canon", "attenuation"])


class OrderTest(unittest.TestCase):
    def setUp(self):
        self.graph = load("valid")

    def test_siblings_are_lexicographic(self):
        orders = project.orders(self.graph)
        self.assertEqual(orders["canon"], "a0")
        self.assertEqual(orders["party"], "a1")

    def test_the_main_root_is_a0_and_traditions_are_the_b_series(self):
        orders = project.orders(self.graph)
        self.assertEqual(orders["ti-esti"], "a0")
        self.assertEqual(orders["plato"], "b0")

    def test_several_tradition_roots_run_b0_b1(self):
        def add_tradition(data):
            second = copy.deepcopy(data["questions"][-1])
            second.update({"id": "aristotle", "tab": "tab-06", "body": "body-06",
                           "party": "aristotle"})
            data["questions"].append(second)
        orders = project.orders(rewrite("valid", add_tradition))
        self.assertEqual(orders["aristotle"], "b0")
        self.assertEqual(orders["plato"], "b1")


class LoadTest(unittest.TestCase):
    def test_a_tradition_may_carry_a_member(self):
        """A tradition is another party's notebook, so it may raise its own
        questions and answer them; the member belongs to that party too. Being
        a tradition is not the same as being the root of one — the root is the
        one nothing in its own party reaches."""
        def hang(data):
            plato = [q for q in data["questions"] if q["id"] == "plato"][0]
            plato["theses"][0]["terms"] = [{
                "title": "What the questioned owes", "to": "member",
                "anchors": ["The one questioned answers in his own voice"]}]
            data["questions"].append({
                "id": "member", "tab": "tab-06", "body": "body-06",
                "question": "What does flattery do to an examination?",
                "state": "held", "kind": "case", "pressure": 0, "requires": [],
                "party": "plato",
                "theses": [{"title": "Flattery answers to please.",
                            "assent": "read, not agreed", "state": "held",
                            "text": "Flattery answers to please.",
                            "terms": [], "traditions": []}],
                "hinge": {"question": "the reading presupposes the text bears on this",
                          "thesis": "model: none · harness: a reading · canon: empty"}})

        graph = rewrite("valid", hang)
        self.assertEqual(spec.run(graph), [])
        self.assertEqual(project.parents(graph)["member"], "plato")
        self.assertEqual(project.distances(graph)["member"], 1)
        self.assertEqual(project.load(graph, "plato"), 1)
        self.assertEqual(project.tradition_roots(graph), ["plato"])

    def test_backlog_is_the_pressure_of_everything_blocked_behind(self):
        """Pressure is set where work waits; the backlog is its total over what
        a question blocks, which is what answers what to do next. A turn
        carries canon above its question and canon holds only the AI's
        answers, so what a question blocks is the AI's questions below it — and
        a question the principal answers is counted by no one but itself."""
        graph = load("valid")
        self.assertEqual(graph.get("attenuation").answerer, "principal")
        self.assertEqual(project.backlog(graph, "canon"),
                         graph.get("canon").pressure)
        self.assertEqual(project.backlog(graph, "attenuation"),
                         graph.get("attenuation").pressure)
        self.assertEqual(project.backlog(graph, "ti-esti"),
                         sum(graph.get(q).pressure
                             for q in ("ti-esti", "canon", "party")))

    def test_blocking_runs_only_through_the_ai_s_questions(self):
        """Nothing the principal answers reaches a turn, so it blocks nothing,
        and a question reached only through it waits on nothing above it. In
        the live notebook `dictate` raised `failures`, and while blocking was
        every term edge `failures` waited on an answer that never lands."""
        graph = load("valid")
        graph.get("attenuation").answerer = "ai"
        graph.get("party").answerer = "principal"
        self.assertEqual(project.blocked_behind(graph, "party"), set())
        self.assertEqual(project.blocked_behind(graph, "canon"), {"attenuation"})
        self.assertEqual(project.blocked_behind(graph, "ti-esti"),
                         {"canon", "attenuation"})
        canon = graph.get("canon").theses[0]
        canon.terms = [t for t in canon.terms if t.to != "attenuation"]
        self.assertEqual(project.blocked_behind(graph, "ti-esti"), {"canon"})

    def test_a_landed_answer_blocks_nothing_and_waits_on_nothing(self):
        graph = load("valid")
        graph.get("canon").theses[0].state = "landed"
        self.assertEqual(project.blocked_behind(graph, "canon"), set())
        self.assertNotIn("canon", project.blocked_behind(graph, "ti-esti"))

    def test_a_question_under_two_parents_is_counted_once(self):
        """The graph is a DAG, so adding up the branches would count the work
        waiting at a shared question once per path to it. What is blocked
        behind a question is a set, each of them blocked once."""
        graph = load("valid")
        graph.get("attenuation").answerer = "ai"  # a shared question that blocks
        shared = set(project.reachable_from(graph, "canon")) & \
            set(project.reachable_from(graph, "party"))
        self.assertTrue(shared)
        self.assertLess(project.backlog(graph, "ti-esti"),
                        graph.get("ti-esti").pressure
                        + project.backlog(graph, "canon")
                        + project.backlog(graph, "party"))

    def test_backlog_is_total_on_a_cycle(self):
        """Every projection here is total on a graph the checker rejects, so a
        question already being summed contributes nothing to itself."""
        graph = load("invalid-acyclic")
        for q in graph.questions:
            self.assertIsInstance(project.backlog(graph, q.id), int)

    def test_load_counts_what_the_term_edges_reach(self):
        graph = load("valid")
        self.assertEqual(project.load(graph, "ti-esti"), 3)
        self.assertEqual(project.load(graph, "canon"), 1)
        # party is a second parent of attenuation: the tab tree hangs
        # attenuation under canon, but party still has it beneath
        self.assertEqual(project.load(graph, "party"), 1)
        self.assertEqual(project.load(graph, "attenuation"), 0)
        self.assertEqual(project.load(graph, "plato"), 0)


class PatchTest(unittest.TestCase):
    def setUp(self):
        self.graph = load("valid")
        self.patch = project.tabs_patch(self.graph)

    def test_one_operation_per_question(self):
        self.assertEqual(len(self.patch), len(self.graph.questions))
        for op in self.patch:
            self.assertEqual(op["op"], "set")
            self.assertEqual(op["path"][0], "tabs")

    def test_the_patch_addresses_tabs_and_names_questions(self):
        by_tab = {op["path"][1]: op["value"] for op in self.patch}
        self.assertEqual(by_tab["tab-01"], {"name": "ti-esti", "order": "a0"})
        self.assertEqual(by_tab["tab-04"], {"name": "attenuation", "order": "a0",
                                           "subtabOf": "tab-02"})

    def test_roots_carry_no_subtab(self):
        by_name = {op["value"]["name"]: op["value"] for op in self.patch}
        self.assertNotIn("subtabOf", by_name["ti-esti"])
        self.assertNotIn("subtabOf", by_name["plato"])
        self.assertIn("subtabOf", by_name["party"])

    def test_the_patch_is_stable(self):
        self.assertEqual(self.patch, project.tabs_patch(load("valid")))

    def test_tree_listing_covers_every_question(self):
        lines = project.tree_listing(self.graph)
        self.assertEqual(len(lines), len(self.graph.questions))
        self.assertTrue(lines[0].startswith("a0 ti-esti"))


if __name__ == "__main__":
    unittest.main()
