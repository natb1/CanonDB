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

    def test_id_pattern_matches_whole_words_only(self):
        pattern = spec._id_pattern("ti-esti")
        self.assertTrue(pattern.search("the ti-esti is asked"))
        self.assertTrue(pattern.search("TI-ESTI"))
        self.assertFalse(pattern.search("proto-ti-estian"))

    def test_findings_render_as_one_line_and_as_json(self):
        finding = spec.run(load("invalid-vocabulary"), only=["vocabulary"])[0]
        self.assertEqual(len(finding.line().splitlines()), 1)
        self.assertEqual(set(finding.as_dict()),
                         {"check", "severity", "question", "message"})


if __name__ == "__main__":
    unittest.main()
