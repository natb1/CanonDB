"""The drift count: draws, their readings, and deadlocked clauses, off the record."""

from __future__ import annotations

import copy
import json
import os
import tempfile
import unittest

from support import fixture, run

from hypo import drift, model


def _data(mutate=None):
    with open(fixture("valid"), encoding="utf-8") as fh:
        data = json.load(fh)
    if mutate:
        mutate(data)
    return data


def _graph(data):
    handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(data, handle)
    handle.close()
    try:
        return model.load(handle.name)
    finally:
        os.unlink(handle.name)


def by_id(data, qid):
    return next(q for q in data["questions"] if q["id"] == qid)


def draw(data, qid, assent, text="Another answer."):
    """A further thesis on ``qid``, as `/principal:ask` records one."""
    q = by_id(data, qid)
    thesis = copy.deepcopy(q["theses"][0])
    thesis.update(title="A further draw", text=text, assent=assent, state="in thread",
                  terms=[], mentions=[], applications=[])
    q["theses"].append(thesis)


class ReadingTest(unittest.TestCase):
    def test_a_draw_is_an_answer_the_ai_gave(self):
        t = model.Thesis(title="t", text="x", assent="verbatim (AI), assented (principal)")
        self.assertTrue(drift.is_draw(t))
        self.assertFalse(drift.is_draw(model.Thesis(title="t", text="x", assent="none")))

    def test_the_reading_is_the_word_on_the_line(self):
        self.assertIs(drift.reading(model.Thesis(title="t", text="x",
                                                 assent="verbatim (AI), agrees with the earlier draw")), True)
        self.assertIs(drift.reading(model.Thesis(title="t", text="x",
                                                 assent="verbatim (AI), diverges from the earlier draw")), False)
        self.assertIsNone(drift.reading(model.Thesis(title="t", text="x", assent="verbatim (AI)")))


class DrawsTest(unittest.TestCase):
    def test_the_draws_are_counted_and_the_later_ones_read(self):
        def mutate(d):
            by_id(d, "ti-esti")["theses"][0]["assent"] = "verbatim (AI), assented (principal)"
            draw(d, "ti-esti", "verbatim (AI), agrees with the earlier draw")
            draw(d, "ti-esti", "verbatim (AI), diverges from the earlier draw")
            draw(d, "ti-esti", "verbatim (AI)")
            draw(d, "ti-esti", "none")  # the principal's own prior is not a draw
        rows = drift.draws(_graph(_data(mutate)))
        self.assertEqual(rows, [drift.Draws("ti-esti", 4, 1, 1, 1)])

    def test_a_question_with_no_draw_and_a_tradition_s_are_absent(self):
        def mutate(d):
            by_id(d, "plato")["theses"][0]["assent"] = "verbatim (AI)"
        self.assertEqual(drift.draws(_graph(_data(mutate))), [])


class DeadlockTest(unittest.TestCase):
    ANCHOR = "the act that would settle it is held down until the standing side speaks"

    def test_a_clause_holds_where_its_anchor_recurs_and_gives_way_where_it_does_not(self):
        def mutate(d):
            draw(d, "party", "verbatim (AI)", text="Still: %s." % self.ANCHOR)
            draw(d, "party", "verbatim (AI)", text="Something else entirely.")
            draw(d, "party", "none", text="Not a draw: %s." % self.ANCHOR)
        rows = drift.deadlocks(_graph(_data(mutate)))
        self.assertEqual(rows, [drift.Held("party", "Deadlock waits on standing", [True, False])])

    def test_with_no_later_draw_nothing_is_asserted(self):
        rows = drift.deadlocks(_graph(_data()))
        self.assertEqual(rows, [drift.Held("party", "Deadlock waits on standing", [])])


class CliTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "graph.json")

    def _write(self, data):
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(data, fh)

    def test_the_counts_print_as_lines_and_as_json(self):
        def mutate(d):
            by_id(d, "ti-esti")["theses"][0]["assent"] = "verbatim (AI)"
            draw(d, "ti-esti", "verbatim (AI), agrees with the earlier draw")
            draw(d, "party", "verbatim (AI)", text=DeadlockTest.ANCHOR)
        self._write(_data(mutate))
        done = run("drift.py", self.path)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("ti-esti  drawn 2 · agree 1 · diverge 0 · unread 0", done.stdout)
        self.assertIn("deadlock on 'Deadlock waits on standing': holds", done.stdout)
        done = run("drift.py", self.path, "--json")
        out = json.loads(done.stdout)
        drawn = {row["question"]: row["drawn"] for row in out["draws"]}
        self.assertEqual(drawn, {"party": 1, "ti-esti": 2})
        self.assertEqual(out["deadlocks"][0]["holds"], [True])

    def test_a_record_with_no_draw_says_so(self):
        self._write(_data())
        done = run("drift.py", self.path)
        self.assertEqual(done.returncode, 0)
        self.assertIn("deadlock on", done.stdout)  # the deadlocked clause is still listed


if __name__ == "__main__":
    unittest.main()
