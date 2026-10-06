"""What a canon turn is put to, and what it carries, is decided from the graph."""

import json
import os
import tempfile
import unittest

from hypo import model, project, spec, turn

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def load(name):
    return model.load(os.path.join(FIXTURES, name + ".json"))


def rewrite(name, mutate):
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


def by_id(data, qid):
    return next(q for q in data["questions"] if q["id"] == qid)


def land(data, qid):
    q = by_id(data, qid)
    q["state"] = "landed"
    for thesis in q["theses"]:
        thesis["state"] = "landed"


def ask_the_ai(data, qid):
    """The fixture's attenuation is the principal's; these tests put it."""
    by_id(data, qid)["answerer"] = "ai"


def ready(data):
    """Everything above attenuation landed, and attenuation the AI's to put."""
    ask_the_ai(data, "attenuation")
    land(data, "ti-esti")
    land(data, "canon")
    land(data, "party")


def open_thread(data):
    """As ready, but canon's answer is on an open thread rather than landed."""
    ready(data)
    q = by_id(data, "canon")
    q["state"] = "in thread"
    q["theses"][0]["state"] = "in thread"


class FrontierTest(unittest.TestCase):
    def test_a_question_the_principal_answers_is_never_on_it(self):
        graph = load("valid")
        ids = [row[0] for row in turn.frontier(graph)]
        for q in graph.questions:
            if q.answerer != "ai":
                self.assertNotIn(q.id, ids)

    def test_a_tradition_is_never_on_it(self):
        self.assertNotIn("plato", [row[0] for row in turn.frontier(load("valid"))])

    def test_a_question_already_put_is_not_on_it(self):
        def put(data):
            by_id(data, "canon")["state"] = "in thread"
        self.assertNotIn("canon", [row[0] for row in turn.frontier(rewrite("valid", put))])

    def test_heaviest_first_then_by_id(self):
        rows = turn.frontier(load("valid"))
        weights = [row[1] for row in rows]
        self.assertEqual(weights, sorted(weights, reverse=True))
        for a, b in zip(rows, rows[1:]):
            if a[1] == b[1]:
                self.assertLess(a[0], b[0])

    def test_backlog_is_the_projection_s(self):
        graph = load("valid")
        for qid, weight, _owed in turn.frontier(graph):
            self.assertEqual(weight, project.backlog(graph, qid))


class WaitsTest(unittest.TestCase):
    def test_an_answer_still_held_above_is_owed(self):
        def held_above(data):
            ask_the_ai(data, "attenuation")
        graph = rewrite("valid", held_above)
        self.assertTrue(any("above it" in line for line in turn.waits(graph, "attenuation")))

    def test_a_landed_answer_above_is_not_owed(self):
        graph = rewrite("valid", ready)
        self.assertEqual(turn.waits(graph, "attenuation"), [])

    def test_a_question_the_principal_answers_is_not_put(self):
        graph = load("valid")
        self.assertIn("the principal answers it, so it is never put",
                      turn.waits(graph, "attenuation"))

    def test_an_answer_in_thread_is_carried_only_on_that_thread(self):
        graph = rewrite("valid", open_thread)
        self.assertTrue(any("canon" in line for line in turn.waits(graph, "attenuation")))
        self.assertEqual(turn.waits(graph, "attenuation", thread=["canon"]), [])

    def test_a_question_the_principal_answers_above_is_not_waited_on(self):
        # make party the principal's: attenuation then waits on nothing by way
        # of it, however its answer stands
        def principal_s(data):
            ask_the_ai(data, "attenuation")
            land(data, "ti-esti")
            land(data, "canon")
            by_id(data, "party")["answerer"] = "principal"
        graph = rewrite("valid", principal_s)
        self.assertEqual(turn.waits(graph, "attenuation"), [])
        self.assertNotIn("party", turn.above(graph, "attenuation"))

    def test_an_unknown_question(self):
        self.assertEqual(turn.waits(load("valid"), "nowhere"), ["no such question"])


class SelectTest(unittest.TestCase):
    def test_nothing_while_everything_waits(self):
        self.assertIsNone(turn.select(load("valid")))

    def test_the_heaviest_ready_question(self):
        def root_landed(data):
            land(data, "ti-esti")
        graph = rewrite("valid", root_landed)
        chosen = turn.select(graph)
        self.assertIsNotNone(chosen)
        ready_rows = [row for row in turn.frontier(graph) if not row[2]]
        self.assertEqual(chosen, ready_rows[0][0])
        self.assertEqual(ready_rows[0][1], max(row[1] for row in ready_rows))


class LineageTest(unittest.TestCase):
    def test_above_walks_only_the_ai_s_questions(self):
        graph = load("valid")
        for qid in turn.above(graph, "attenuation"):
            self.assertEqual(graph.get(qid).answerer, "ai")

    def test_above_is_nearest_the_root_first(self):
        graph = load("valid")
        dist = project.distances(graph)
        chain = turn.above(graph, "attenuation")
        self.assertEqual([dist[c] for c in chain], sorted(dist[c] for c in chain))
        self.assertEqual(chain[0], "ti-esti")

    def test_it_refuses_a_gap(self):
        def held_above(data):
            ask_the_ai(data, "attenuation")
        with self.assertRaises(ValueError) as caught:
            turn.lineage(rewrite("valid", held_above), "attenuation")
        self.assertIn("above it", str(caught.exception))

    def test_it_carries_the_questions_and_the_answers_and_nothing_else(self):
        graph = rewrite("valid", ready)
        text = turn.lineage(graph, "attenuation")
        for qid in turn.above(graph, "attenuation") + ["attenuation"]:
            q = graph.get(qid)
            self.assertIn(q.question.strip(), text)
            if qid != "attenuation":
                self.assertIn(turn.carried(q).text.strip(), text)
                self.assertNotIn(turn.carried(q).title, text)
            for definition in q.definitions:
                self.assertNotIn(definition.body, text)
            if q.hinge:
                self.assertNotIn(q.hinge.question, text)
        self.assertTrue(text.rstrip().endswith(graph.get("attenuation").question.strip()))
        self.assertEqual(text.count(turn.RULE), len(turn.above(graph, "attenuation")))

    def test_no_question_id_stands_in_it(self):
        graph = rewrite("valid", ready)
        text = turn.lineage(graph, "attenuation")
        # the ids are ordinary words that may occur in prose; what is checked is
        # that none heads a section
        for line in text.splitlines():
            self.assertNotIn(line.strip(), [q.id for q in graph.questions])

    def test_the_thread_s_own_answer_is_carried(self):
        graph = rewrite("valid", open_thread)
        text = turn.lineage(graph, "attenuation", thread=["canon"])
        self.assertIn(graph.get("canon").theses[0].text.strip(), text)


if __name__ == "__main__":
    unittest.main()
