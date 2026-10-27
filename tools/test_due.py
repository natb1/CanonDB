"""The due reading: what the record says is due, by kind, with a next step."""

from __future__ import annotations

import json
import unittest
from datetime import date

from support import load, run

from hypo import due, model


class DueTest(unittest.TestCase):
    def setUp(self):
        self.graph = load("valid")
        self.by_id = self.graph.by_id()

    def kinds(self, **kw):
        return [(r.question, r.kind) for r in due.rows(self.graph, **kw)]

    def test_nothing_is_due_on_the_fixture_as_it_stands(self):
        self.assertEqual(self.kinds(), [])

    def test_a_pending_note_is_due_with_its_dictation_as_the_next_step(self):
        self.by_id["canon"].notes.append(model.Note(section="thesis", body="pending: a clause no run applied"))
        rows = due.rows(self.graph)
        self.assertEqual([(r.question, r.kind) for r in rows], [("canon", "pending")])
        self.assertIn("/principal:dictate", rows[0].next)
        self.assertIn("a clause no run applied", rows[0].why)

    def test_a_note_that_does_not_open_with_pending_is_not(self):
        self.by_id["canon"].notes.append(model.Note(section="thesis", body="claimed by a session; pending nothing"))
        self.assertEqual(self.kinds(), [])

    def test_a_suspended_clause_is_due_until_the_merge(self):
        self.by_id["canon"].theses[0].terms[0].suspended = "waits on attenuation's answer"
        rows = due.rows(self.graph)
        self.assertEqual([(r.question, r.kind) for r in rows], [("canon", "suspended")])
        self.assertIn("the merge", rows[0].next)

    def test_a_deadlocked_clause_a_later_draw_gave_way_on_is_due(self):
        party = self.by_id["party"]
        party.theses.append(model.Thesis(title="drawn again", text="nothing of the anchors recurs here",
                                         assent="verbatim (AI), diverges", state="held"))
        rows = due.rows(self.graph)
        self.assertEqual([(r.question, r.kind) for r in rows], [("party", "drift")])
        self.assertIn("gave way in 1 later draw", rows[0].why)

    def test_a_deadlocked_clause_every_later_draw_holds_is_not(self):
        party = self.by_id["party"]
        anchors = party.theses[0].terms[0].anchors
        party.theses.append(model.Thesis(title="drawn again", text=" ".join(anchors),
                                         assent="verbatim (AI), agrees", state="held"))
        self.assertEqual(self.kinds(), [])

    def test_the_backstop_reads_the_hinge_s_amendments(self):
        for q in self.graph.questions:
            if q.hinge is not None and not q.tradition:
                q.hinge.thesis += " · amended 2026-01-01 by the principal's dictation"
        self.assertEqual(self.kinds(backstop=30, today=date(2026, 1, 20)), [])
        rows = due.rows(self.graph, backstop=30, today=date(2026, 3, 1))
        self.assertEqual(sorted(r.question for r in rows), ["attenuation", "canon", "party", "ti-esti"])
        self.assertTrue(all(r.kind == "backstop" and "past the backstop of 30" in r.why for r in rows))

    def test_a_hinge_with_no_amendment_is_due_when_a_backstop_is_read(self):
        rows = due.rows(self.graph, backstop=30, today=date(2026, 3, 1), of="")
        self.assertEqual(len(rows), 4)
        self.assertTrue(all("no amendment" in r.why for r in rows))
        self.assertEqual(self.kinds(), [])   # no backstop given: nothing is due by it

    def test_answers_due_again_ride_in_with_a_model(self):
        self.by_id["ti-esti"].theses[0].state = "landed"
        moved = lambda qid, canon, above: []  # noqa: E731
        rows = due.rows(self.graph, model="another model", moved=moved)
        self.assertEqual([(r.question, r.kind) for r in rows], [("ti-esti", "again")])
        self.assertIn("--again ti-esti", rows[0].next)
        self.assertEqual(self.kinds(), [])   # without a model, the kind is left out, not guessed

    def two_projects(self):
        """The fixture as two projects: ti-esti's tree is alpha, and party is
        beta's root, whose end reads alpha. Returns party."""
        self.graph.projects = ["alpha", "beta"]
        for q in self.graph.questions:
            q.project = "alpha"
        party = self.by_id["party"]
        self.by_id["ti-esti"].theses[0].terms = [t for t in self.by_id["ti-esti"].theses[0].terms
                                                  if t.to != "party"]
        party.project = "beta"
        party.hinge.end = "For the sake of what alpha names, which is read here and not restated."
        return party

    def test_a_root_whose_end_reads_an_earlier_project_is_named_as_unreadable(self):
        self.two_projects()
        rows = due.rows(self.graph)
        self.assertEqual([(r.project, r.question, r.kind) for r in rows], [("beta", "party", "upstream")])
        self.assertIn("not recorded", rows[0].why)
        # the next step is the clause the provenance is to carry, naming the root it reads
        self.assertIn("'upstream: ti-esti at rev <n>, <what is read>'", rows[0].next)
        self.assertIn("provenance", rows[0].next)
        self.assertEqual(due.rows(self.graph, of="alpha"), [])

    def test_an_upstream_that_moved_past_the_rev_recorded_is_due(self):
        """The provenance records the rev the upstream was read at; the
        upstream's own rev is past it, so the end and the clauses the hinge
        names are to be re-read and the line amended."""
        party = self.two_projects()
        party.hinge.thesis += " · upstream: ti-esti at rev 15, its end and the clause kept as a means"
        self.by_id["ti-esti"].rev = 17
        rows = due.rows(self.graph)
        self.assertEqual([(r.project, r.question, r.kind) for r in rows], [("beta", "party", "upstream")])
        self.assertEqual(rows[0].why, "ti-esti moved: read at rev 15, now rev 17")
        self.assertEqual(rows[0].next, "re-read ti-esti's end and the clauses the hinge names, "
                                       "and amend the line to 'upstream: ti-esti at rev 17'")
        self.assertEqual(due.rows(self.graph, of="alpha"), [])

    def test_an_upstream_that_has_not_moved_is_not(self):
        """Nor is one whose rev the graph does not hold: a rev of 0 says the
        read gave none, and nothing is guessed from it. The clause covers the
        earlier project, so the not-recorded row does not fire beside it."""
        party = self.two_projects()
        party.hinge.thesis += " · upstream: ti-esti at rev 15, its end and the clause kept as a means"
        self.by_id["ti-esti"].rev = 15
        self.assertEqual(self.kinds(), [])
        self.by_id["ti-esti"].rev = 0
        self.assertEqual(self.kinds(), [])

    def test_an_upstream_the_graph_does_not_hold_is_due_a_read(self):
        party = self.two_projects()
        party.hinge.thesis += " · upstream: archai at rev 15, its end"
        rows = due.rows(self.graph)
        kinds = [(r.project, r.question, r.kind) for r in rows]
        self.assertEqual(kinds, [("beta", "party", "upstream"), ("beta", "party", "upstream")])
        said = {r.why: r.next for r in rows}
        self.assertEqual(said["archai is not in this graph"], "read archai with this project")
        # the clause names no question of alpha, so alpha's rev is still not recorded
        self.assertTrue(any("not recorded" in why for why in said))

    def test_an_upstream_clause_is_read_on_any_question_of_the_author_s(self):
        """Not only on a root: a question below that read a question of an
        earlier project records the rev the same way. A clause names the
        project itself where the question is not in the graph."""
        party = self.two_projects()
        canon = self.by_id["canon"]
        canon.hinge.thesis += " · upstream: plato at rev 3, its one answer"
        self.by_id["plato"].rev = 4
        party.hinge.thesis += " · upstream: alpha at rev 2, the root"
        rows = due.rows(self.graph)
        self.assertEqual([(r.project, r.question, r.kind) for r in rows],
                         [("alpha", "canon", "upstream"), ("beta", "party", "upstream")])
        self.assertEqual(rows[0].why, "plato moved: read at rev 3, now rev 4")
        self.assertEqual(rows[1].why, "alpha is not in this graph")

    def test_several_upstream_clauses_are_each_read(self):
        party = self.two_projects()
        party.hinge.thesis += (" · upstream: ti-esti at rev 15, its end"
                               " · upstream: canon at rev 2, the entry"
                               " · upstream: archai at rev 1, nothing here")
        self.by_id["ti-esti"].rev = 15
        self.by_id["canon"].rev = 3
        rows = due.rows(self.graph)
        self.assertEqual([r.why for r in rows],
                         ["canon moved: read at rev 2, now rev 3", "archai is not in this graph"])

    def test_the_listing_and_the_order(self):
        self.by_id["canon"].notes.append(model.Note(section="thesis", body="pending: one"))
        self.by_id["party"].theses[0].terms[0].suspended = "waits"
        rows = due.rows(self.graph)
        self.assertEqual([r.kind for r in rows], ["pending", "suspended"])
        lines = due.listing(rows)
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[0].startswith("canon") and "next:" in lines[0])


class CliTest(unittest.TestCase):
    def test_the_script_prints_rows_and_json(self):
        import json as _json
        import os
        import tempfile
        from support import fixture
        with open(fixture("valid"), encoding="utf-8") as fh:
            data = _json.load(fh)
        q = next(q for q in data["questions"] if q["id"] == "canon")
        q.setdefault("notes", []).append({"section": "thesis", "body": "pending: one"})
        handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
        _json.dump(data, handle)
        handle.close()
        try:
            out = run("due.py", handle.name)
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertIn("pending", out.stdout)
            out = run("due.py", handle.name, "--json")
            self.assertEqual(_json.loads(out.stdout)[0]["kind"], "pending")
        finally:
            os.unlink(handle.name)


if __name__ == "__main__":
    unittest.main()
