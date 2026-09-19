"""Every check fires on its own fixture, and none fires on the valid one."""

import os
import unittest

from hypo import model, spec

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def load(name):
    return model.load(os.path.join(FIXTURES, name + ".json"))


class CatalogueTest(unittest.TestCase):
    def test_ids_are_unique_and_severities_known(self):
        ids = [c.id for c in spec.CHECKS]
        self.assertEqual(len(ids), len(set(ids)))
        for c in spec.CHECKS:
            self.assertIn(c.severity, (spec.ERROR, spec.WARN))
            self.assertTrue(c.description.strip())
            self.assertEqual(len(c.description.splitlines()), 1)

    def test_every_check_has_a_fixture(self):
        for c in spec.CHECKS:
            with self.subTest(check=c.id):
                self.assertTrue(os.path.exists(
                    os.path.join(FIXTURES, "invalid-%s.json" % c.id)))


class ValidGraphTest(unittest.TestCase):
    def test_no_findings_at_all(self):
        findings = spec.run(load("valid"))
        self.assertEqual([f.line() for f in findings], [])


class InvalidGraphTest(unittest.TestCase):
    def test_each_fixture_fires_its_check(self):
        for c in spec.CHECKS:
            with self.subTest(check=c.id):
                findings = spec.run(load("invalid-%s" % c.id))
                fired = [f for f in findings if f.check == c.id]
                self.assertTrue(fired, "%s did not fire on its own fixture" % c.id)
                for f in fired:
                    self.assertEqual(f.severity, c.severity)

    def test_error_fixtures_are_errors_and_warn_fixtures_are_not(self):
        for c in spec.CHECKS:
            with self.subTest(check=c.id):
                findings = spec.run(load("invalid-%s" % c.id), only=[c.id])
                self.assertEqual(bool(spec.errors(findings)), c.severity == spec.ERROR)

    #: A fixture may fire a second check only where its mutation makes that
    #: unavoidable. The question `invalid-one-root` adds is a root of its own,
    #: so no term edge from the main root reaches it either.
    COLLATERAL = {"one-root": {"reachable"}}

    def test_no_fixture_fires_a_check_it_does_not_name(self):
        """A fixture that drifts into firing a second check stops isolating
        the rule it was written for, and the next mechanical edit across all
        of them would not be reviewable."""
        for c in spec.CHECKS:
            with self.subTest(check=c.id):
                fired = {f.check for f in spec.run(load("invalid-%s" % c.id))}
                self.assertEqual(fired - {c.id} - self.COLLATERAL.get(c.id, set()),
                                 set())


class DetailTest(unittest.TestCase):
    def test_only_narrows_the_run(self):
        findings = spec.run(load("invalid-vocabulary"), only=["vocabulary"])
        self.assertEqual({f.check for f in findings}, {"vocabulary"})

    def test_affecting_keeps_graph_wide_findings(self):
        findings = spec.run(load("invalid-one-root"))
        self.assertTrue(any(f.question is None for f in findings))
        self.assertTrue(all(f.question in ("plato", None)
                            for f in spec.affecting(findings, "plato")))

    def test_anchor_substring_names_the_term(self):
        findings = spec.run(load("invalid-anchor-substring"), only=["anchor-substring"])
        self.assertEqual(findings[0].question, "ti-esti")
        self.assertIn("The record between them", findings[0].message)

    def test_shared_run_finds_eight_words(self):
        anchor = "one two three four five six seven eight nine"
        self.assertIsNotNone(spec._shared_run(anchor, "and " + anchor + " then"))
        self.assertIsNone(spec._shared_run(anchor, "one two three four five six seven"))

    def test_no_restatement_catches_a_long_echo(self):
        findings = spec.run(load("invalid-no-restatement"), only=["no-restatement"])
        self.assertEqual(findings[0].question, "canon")

    def test_hinge_present_names_the_part_that_is_missing(self):
        graph = load("valid")
        graph.get("canon").hinge.thesis = ""
        findings = spec.run(graph, only=["hinge-present"])
        self.assertEqual(findings[0].question, "canon")
        self.assertIn("no thesis part", findings[0].message)

    def test_a_tradition_needs_no_hinge(self):
        graph = load("invalid-hinge-present")
        self.assertTrue(graph.get("plato").tradition)
        findings = spec.run(graph, only=["hinge-present"])
        self.assertEqual([f.question for f in findings], ["canon"])

    def test_provenance_complete_names_what_is_missing(self):
        findings = spec.run(load("invalid-provenance-complete"),
                            only=["provenance-complete"])
        self.assertEqual(findings[0].question, "attenuation")
        self.assertIn("no canon", findings[0].message)

    def test_definition_once_names_both_places(self):
        findings = spec.run(load("invalid-definition-once"), only=["definition-once"])
        self.assertEqual(findings[0].question, "canon")
        self.assertIn("'grade'", findings[0].message)
        self.assertIn("attenuation", findings[0].message)

    def test_definition_once_reaches_siblings(self):
        """Neither tab is under the other, so the old tab-tree scoping let this
        through — which is how one word came to carry two senses."""
        graph = load("valid")
        canon, party = graph.get("canon"), graph.get("party")
        word = canon.theses[0].definitions[0]
        self.assertEqual(spec.run(graph, only=["definition-once"]), [])
        party.theses[0].definitions.append(word)
        findings = spec.run(graph, only=["definition-once"])
        self.assertEqual(findings[0].question, "canon")
        self.assertIn("party", findings[0].message)

    def test_answer_cardinality_runs_in_canon_mode_only(self):
        self.assertEqual(spec.run(load("valid"), only=["answer-cardinality"]), [])
        graph = load("invalid-answer-cardinality")
        self.assertTrue(spec.run(graph, only=["answer-cardinality"]))
        graph.mode = model.NOTEBOOK
        self.assertEqual(spec.run(graph, only=["answer-cardinality"]), [])

    def test_an_unknown_mode_is_a_vocabulary_finding(self):
        graph = load("valid")
        graph.mode = "ledger"
        findings = spec.run(graph, only=["vocabulary"])
        self.assertIsNone(findings[0].question)
        self.assertIn("ledger", findings[0].message)

    def test_findings_render_as_one_line_and_as_json(self):
        finding = spec.run(load("invalid-vocabulary"), only=["vocabulary"])[0]
        self.assertEqual(len(finding.line().splitlines()), 1)
        self.assertEqual(set(finding.as_dict()),
                         {"check", "severity", "question", "message"})


if __name__ == "__main__":
    unittest.main()
