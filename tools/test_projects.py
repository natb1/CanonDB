"""A notebook of several projects: the reader tells projects, parties and the
reserved tab off the tab list; the projection places each project's root at
the top and every party under the tradition project; the checks keep each
project's lineage and vocabulary its own; the reads filter by project."""

import copy
import json
import os
import tempfile
import unittest

from hypo import model, project, read, spec, turn
from support import fixture

TABS = {
    "t-arch": {"name": "archai", "order": "a0"},
    "t-cdb": {"name": "canondb", "order": "a1"},
    "t-cdb-x": {"name": "canon", "order": "a0", "subtabOf": "t-cdb"},
    "t-trad": {"name": "tradition", "order": "a2"},
    "t-plato": {"name": "Plato", "order": "a0", "subtabOf": "t-trad"},
    "t-plato2": {"name": "Plato-ordo", "order": "a0", "subtabOf": "t-plato"},
    "t-lease": {"name": "lease", "order": "z0"},
}


class ReaderTest(unittest.TestCase):
    def test_projects_are_the_top_level_a_series(self):
        self.assertEqual(read.project_order(TABS), ["archai", "canondb", "tradition"])
        of = read.projects(TABS)
        self.assertEqual(of["t-cdb-x"], "canondb")
        self.assertEqual(of["t-plato2"], "tradition")
        self.assertEqual(of["t-lease"], "")

    def test_parties_stand_under_the_tradition_root(self):
        party = read.parties(TABS)
        self.assertEqual(party["t-plato"], "plato")
        self.assertEqual(party["t-plato2"], "plato")
        self.assertEqual(party["t-trad"], model.AUTHOR)
        self.assertEqual(party["t-cdb-x"], model.AUTHOR)

    def test_the_lease_tab_is_reserved(self):
        self.assertEqual(read.reserved(TABS), {"t-lease"})

    def test_one_project_is_the_empty_one(self):
        one = {"a": {"name": "ti-esti", "order": "a0"}, "b": {"name": "Plato", "order": "b0"}}
        self.assertEqual(set(read.projects(one).values()), {""})
        self.assertEqual(read.parties(one)["b"], "plato")


def q(qid, proj, kind="definitional", terms=(), mentions=(), party=None, defs=(),
      text="It holds what it holds.", notes=(), answerer="ai"):
    out = {"id": qid, "tab": "tab-" + qid, "body": "body-" + qid, "project": proj,
           "question": "What does %s hold?" % qid, "state": "held", "kind": kind,
           "pressure": 1, "answerer": answerer,
           "theses": [{"title": "It holds " + qid, "assent": "none", "state": "held",
                       "text": text,
                       "terms": [{"title": "to " + t, "to": t, "anchors": [a]} for t, a in terms],
                       "mentions": [{"title": "at " + t, "to": t, "anchors": [a]} for t, a in mentions],
                       "traditions": []}],
           "definitions": [{"word": w, "body": b} for w, b in defs],
           "notes": [{"section": "thesis", "body": n} for n in notes],
           "hinge": {"question": "that %s holds anything" % qid,
                     "thesis": "model: m · harness: h · canon: c"}}
    if kind == "root" and not party and proj != "tradition":
        out["hinge"].update({"end": "that it holds", "method": "read at each entry"})
    if party:
        out["party"] = party
        out["answerer"] = ""
        out.pop("project")
    return out


def graph(questions, projects=("archai", "canondb", "tradition")):
    data = {"artifact": "", "projects": list(projects), "questions": questions}
    handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    try:
        json.dump(data, handle)
        handle.close()
        return model.load(handle.name)
    finally:
        os.unlink(handle.name)


def base():
    return [
        q("archai", "archai", kind="root"),
        q("canondb", "canondb", kind="root", text="It keeps a canon of entries.",
          terms=[("canon", "a canon of entries")]),
        q("canon", "canondb", text="A record is kept."),
        q("tradition", "tradition", kind="root", answerer="principal"),
        q("Plato", None, kind="root", party="plato"),
        q("Plato-ordo", None, kind="root", party="plato"),
    ]


class PlacementTest(unittest.TestCase):
    def setUp(self):
        self.g = graph(base())

    def test_each_project_root_is_at_the_top_in_order(self):
        self.assertEqual(project.project_roots(self.g), ["archai", "canondb", "tradition"])
        ordr = project.orders(self.g)
        self.assertEqual([ordr[r] for r in ("archai", "canondb", "tradition")], ["a0", "a1", "a2"])

    def test_parties_are_placed_under_tradition_and_a_second_reading_under_its_head(self):
        par = project.placement(self.g)
        self.assertEqual(par["Plato"], "tradition")
        self.assertEqual(par["Plato-ordo"], "Plato")
        self.assertIsNone(par["canondb"])
        # placement, not lineage: nothing raises a party
        self.assertIsNone(project.parents(self.g)["Plato"])

    def test_the_patch_places_parties_under_the_tradition_tab(self):
        patch = {p["path"][1]: p["value"] for p in project.tabs_patch(self.g)}
        self.assertEqual(patch["tab-Plato"]["subtabOf"], "tab-tradition")
        self.assertEqual(patch["tab-Plato-ordo"]["subtabOf"], "tab-Plato")
        self.assertNotIn("subtabOf", patch["tab-canondb"])

    def test_a_project_patch_places_that_project_alone(self):
        names = {p["value"]["name"] for p in project.tabs_patch(self.g, "canondb")}
        self.assertEqual(names, {"canondb", "canon"})
        trad = {p["value"]["name"] for p in project.tabs_patch(self.g, "tradition")}
        self.assertEqual(trad, {"tradition", "Plato", "Plato-ordo"})

    def test_the_valid_graph_still_places_as_before(self):
        g = model.load(fixture("valid"))
        self.assertEqual(project.orders(g)["plato"], "b0")
        self.assertEqual(project.orders(g)["ti-esti"], "a0")


def findings(g, check):
    return [f for f in spec.run(g, only=[check])]


class ChecksTest(unittest.TestCase):
    def test_the_base_is_clean(self):
        self.assertEqual([f.line() for f in spec.errors(spec.run(graph(base())))], [])

    def test_one_root_holds_per_project(self):
        qs = base() + [q("stray", "canondb", kind="root")]
        out = findings(graph(qs), "one-root")
        self.assertEqual(len(out), 1)
        self.assertIn("in project canondb", out[0].message)

    def test_a_term_never_crosses_projects(self):
        qs = base()
        qs[1]["theses"][0]["terms"].append({"title": "to archai", "to": "archai",
                                            "anchors": ["It keeps"]})
        self.assertTrue(findings(graph(qs), "project-order"))

    def test_a_mention_runs_only_to_an_earlier_project_or_tradition(self):
        qs = base()
        qs[1]["theses"][0]["mentions"] = [{"title": "at archai", "to": "archai",
                                           "anchors": ["It keeps"]}]
        qs[0]["theses"][0]["text"] = "It holds what it holds, as the canon does."
        qs[0]["theses"][0]["mentions"] = [{"title": "at canondb", "to": "canondb",
                                           "anchors": ["as the canon does"]}]
        out = findings(graph(qs), "project-order")
        self.assertEqual([f.question for f in out], ["archai"])
        qs[0]["theses"][0]["mentions"][0]["to"] = "tradition"
        self.assertEqual(findings(graph(qs), "project-order"), [])

    def test_a_word_is_one_sense_per_project(self):
        qs = base()
        qs[0]["definitions"] = [{"word": "record", "body": "What archai keeps."}]
        qs[0]["theses"][0]["text"] = "It holds a record."
        qs[2]["definitions"] = [{"word": "record", "body": "What canon keeps."}]
        self.assertEqual(findings(graph(qs), "definition-once"), [])

    def test_another_project_s_word_is_not_reached_for(self):
        qs = base()
        qs[2]["definitions"] = [{"word": "record", "body": "What canon keeps."}]
        qs[0]["theses"][0]["text"] = "It holds a record of its own."
        self.assertEqual(findings(graph(qs), "reach"), [])

    def test_a_cross_project_mention_needs_no_cycle(self):
        qs = base()
        qs[1]["theses"][0]["mentions"] = [{"title": "at archai", "to": "archai",
                                           "anchors": ["It keeps"]}]
        self.assertEqual(findings(graph(qs), "mention-justified"), [])

    def test_the_tradition_root_states_no_end(self):
        self.assertEqual(findings(graph(base()), "end-stated"), [])

    def test_a_claim_is_seen(self):
        qs = base()
        qs[2]["notes"] = [{"section": "thesis", "body": "claimed by s-1 on 2026-10-22"}]
        self.assertEqual([f.question for f in findings(graph(qs), "claim-open")], ["canon"])


class ReadsTest(unittest.TestCase):
    def test_the_frontier_filters_by_project_and_leaves_claims_out(self):
        qs = base()
        g = graph(qs)
        everyone = {r[0] for r in turn.frontier(g)}
        self.assertTrue({"archai", "canondb"} <= everyone)
        self.assertEqual({r[0] for r in turn.frontier(g, of="canondb")}, {"canondb", "canon"})
        qs[1]["notes"] = [{"section": "thesis", "body": "claimed by s-1"}]
        self.assertEqual({r[0] for r in turn.frontier(graph(qs), of="canondb")}, {"canon"})


class FreshTest(unittest.TestCase):
    def test_a_read_of_gaps_is_fresh(self):
        import fresh
        self.assertFalse(fresh.moved("<doc rev='9' sinceRev='9'><gap blocks='12'/></doc>"))
        self.assertTrue(fresh.moved("<doc rev='10' sinceRev='9'><gap blocks='3'/>"
                                    "<paragraph id='s.1' h='a'><text id='.2'>x</text></paragraph></doc>"))


if __name__ == "__main__":
    unittest.main()
