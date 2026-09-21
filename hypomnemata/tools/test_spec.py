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
    #: unavoidable. None does: the one pairing there was, `invalid-one-root`
    #: also tripping `reachable`, went when `reachable` did.
    COLLATERAL = {}

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

    def test_a_tradition_needs_a_hinge_too(self):
        """It was once exempt, as something read rather than asked. A reading
        presupposes things of its own, and the reconstruction came from a run."""
        graph = load("valid")
        plato = graph.get("plato")
        self.assertTrue(plato.tradition)
        self.assertEqual(spec.run(graph, only=["hinge-present"]), [])
        plato.hinge = None
        findings = spec.run(graph, only=["hinge-present"])
        self.assertEqual([f.question for f in findings], ["plato"])

    def test_tradition_target_covers_a_definition_borrowing(self):
        """A borrowed sense names a tradition the same way a citation does, so
        a dangling one is caught by the same rule and not by a second."""
        graph = load("valid")
        borrowing = graph.get("ti-esti").theses[0].definitions[0].tradition
        self.assertEqual(borrowing.to, "plato")
        self.assertEqual(spec.run(graph, only=["tradition-target"]), [])
        borrowing.to = "socrates"
        findings = spec.run(graph, only=["tradition-target"])
        self.assertEqual([f.question for f in findings], ["ti-esti"])
        self.assertIn("definition 'elenchus' borrows from", findings[0].message)
        borrowing.to = "canon"
        findings = spec.run(graph, only=["tradition-target"])
        self.assertIn("not a tradition", findings[0].message)

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

    def test_renaming_an_inbox_item_leaves_requires_alone(self):
        """The rename that stranded twenty-four requires entries in the live
        notebook. Naming the handle rather than the summary makes it a
        non-event: nothing else in the graph mentions the title."""
        graph = load("valid")
        item = graph.get("ti-esti").inbox[0]
        item.title = "Put the opening answer where both can see it"
        self.assertEqual(spec.run(graph, only=["requires-exist"]), [])

    def test_requires_names_an_id_and_not_a_title(self):
        graph = load("valid")
        graph.get("ti-esti").requires = [graph.get("ti-esti").inbox[0].title]
        findings = spec.run(graph, only=["requires-exist"])
        self.assertTrue(findings)

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

    def test_a_title_may_be_a_phrase_and_may_carry_a_link(self):
        """The narrowing that replaces no-ids-in-prose: a title summarises and
        need not be a sentence, and may well be the handle a link points at.
        Only an opaque handle or a bare question id is wrong."""
        graph = load("valid")
        term = graph.get("ti-esti").theses[0].terms[0]
        for allowed in ("The record between them", "Memory is the repo",
                        "≡ ti esti", "GPT is not a handle"):
            term.title = allowed
            self.assertEqual(spec.run(graph, only=["title-not-identifier"]), [],
                             allowed)
        for refused in ("term-001", "node_3"):
            term.title = refused
            self.assertTrue(spec.run(graph, only=["title-not-identifier"]), refused)

    def test_a_deadlock_sentinel_is_a_vocabulary_finding(self):
        """assent is required, so `none` is a real value there. A deadlock is
        optional, so a word standing in for its absence is pure noise — which
        the live root answer wrote and every other tab omitted."""
        graph = load("valid")
        term = graph.get("canon").theses[0].terms[0]
        self.assertEqual(spec.run(graph, only=["vocabulary"]), [])
        term.deadlock = model.Deadlock(counter="none", attenuation="none")
        findings = spec.run(graph, only=["vocabulary"])
        self.assertEqual(findings[0].question, "canon")
        self.assertIn("leave it out", findings[0].message)

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

    def test_a_landed_question_waits_on_nothing_that_is_not_done(self):
        """`requires` names what must be done before a question can be asked,
        so a question that has landed was asked. The live root waited on its
        own promulgation, which is the act that follows an answer."""
        graph = load("valid")
        self.assertEqual(spec.run(graph, only=["requires-discharged"]), [])
        graph.get("ti-esti").requires = ["promulgate-the-root-answer"]
        findings = spec.run(graph, only=["requires-discharged"])
        self.assertEqual([f.question for f in findings], ["ti-esti"])
        self.assertIn("has landed but still waits on", findings[0].message)
        graph.get("ti-esti").inbox[0].done = True
        self.assertEqual(spec.run(graph, only=["requires-discharged"]), [])

    def test_an_undone_item_nothing_requires_is_reported(self):
        """An action exists only as something a question requires. A done item
        is exempt: its requirers drop the entry when it is discharged."""
        graph = load("valid")
        self.assertEqual(spec.run(graph, only=["inbox-required"]), [])
        for q in graph.questions:
            q.requires = []
        findings = spec.run(graph, only=["inbox-required"])
        self.assertEqual([f.question for f in findings], ["ti-esti"])
        graph.get("ti-esti").inbox[0].done = True
        self.assertEqual(spec.run(graph, only=["inbox-required"]), [])

    def test_a_deadlock_carries_both_its_parts(self):
        """Dissent without a grading is half a record: what the principal holds
        instead, and what the clause may still license."""
        graph = load("valid")
        self.assertEqual(spec.run(graph, only=["deadlock-complete"]), [])
        term = [t for q in graph.questions for th in q.theses for t in th.terms
                if t.deadlock][0]
        term.deadlock.attenuation = ""
        findings = spec.run(graph, only=["deadlock-complete"])
        self.assertIn("no attenuation", findings[0].message)
        term.deadlock.counter = ""
        self.assertEqual(len(spec.run(graph, only=["deadlock-complete"])), 2)

    def test_a_divergence_says_what_is_held_instead(self):
        """A tradition edge is the canon between two parties: support is assent
        and divergence is deadlock, so a divergence carries a counter-clause.
        It carries no attenuation — a tradition licenses no action here."""
        graph = load("valid")
        edge = graph.get("ti-esti").theses[0].traditions[0]
        self.assertEqual(spec.run(graph, only=["divergence-counter"]), [])
        edge.relation = "divergence"
        self.assertIn("nothing of what is held instead",
                      spec.run(graph, only=["divergence-counter"])[0].message)
        edge.counter = "the opening move may be asked of anything at all"
        self.assertEqual(spec.run(graph, only=["divergence-counter"]), [])
        edge.relation = "support"
        self.assertIn("makes it a divergence",
                      spec.run(graph, only=["divergence-counter"])[0].message)

    def test_a_thesis_is_canon_only_where_its_question_landed(self):
        """A postulate is anything the notebook supports and canon does not,
        whether it is a thesis or an artifact built from one, so the two are
        graded by one rule in two steps."""
        graph = load("valid")
        self.assertEqual(spec.run(graph, only=["standing-honest"]), [])
        held = graph.get("attenuation")
        self.assertNotEqual(held.state, "landed")
        held.theses[0].standing = "canon"
        self.assertIn("not landed",
                      spec.run(graph, only=["standing-honest"])[0].message)

    def test_an_application_is_derived_only_from_a_canon_thesis(self):
        graph = load("valid")
        thesis, app = list(graph.get("ti-esti").applications())[0]
        app.standing = "derived"
        self.assertIn("comes from stands as 'unset'",
                      spec.run(graph, only=["standing-honest"])[0].message)
        thesis.standing = "canon"
        self.assertEqual(spec.run(graph, only=["standing-honest"]), [])

    def test_pressure_is_the_one_number_set_by_hand(self):
        graph = load("valid")
        self.assertEqual(spec.run(graph, only=["pressure-shape"]), [])
        graph.get("canon").pressure = -1
        self.assertTrue(spec.run(graph, only=["pressure-shape"]))

    def test_a_tradition_may_be_reached_from_its_own_party(self):
        """A reconstruction may raise its own questions and answer them. What
        it may not have is a term edge from the principal's own lineage."""
        graph = load("valid")
        member = load("valid").get("canon")
        member.id, member.tab, member.body = "member", "tab-09", "body-09"
        member.party = "plato"
        member.theses[0].terms = []
        member.inbox = []
        member.requires = []
        graph.questions.append(member)
        graph.get("plato").theses[0].terms.append(model.Term(
            title="What the questioned owes", to="member",
            anchors=["The one questioned answers in his own voice"]))
        self.assertEqual(spec.run(graph, only=["tradition-isolated"]), [])
        member.party = "author"
        self.assertIn("a term edge runs inside one party's lineage",
                      spec.run(graph, only=["tradition-isolated"])[0].message)

    def test_a_definition_may_be_used_in_any_regular_form(self):
        """A glossary entry is a headword. What it may not be is letters
        hidden inside a longer word: asking for a substring passed a thesis
        that says `grants` and never `grant`, and the renderer then had
        nothing to put the link on."""
        graph = load("valid")
        thesis = graph.get("canon").theses[0]
        word = thesis.definitions[0].word
        self.assertEqual(spec.run(graph, only=["definition-anchorable"]), [])
        thesis.text = thesis.text.replace(word, word + "s")
        self.assertEqual(spec.run(graph, only=["definition-anchorable"]), [])
        thesis.text = thesis.text.replace(word + "s", "un" + word + "ish")
        findings = spec.run(graph, only=["definition-anchorable"])
        self.assertEqual([f.question for f in findings], ["canon"])
        self.assertIn("in any regular form", findings[0].message)

    def test_findings_render_as_one_line_and_as_json(self):
        finding = spec.run(load("invalid-vocabulary"), only=["vocabulary"])[0]
        self.assertEqual(len(finding.line().splitlines()), 1)
        self.assertEqual(set(finding.as_dict()),
                         {"check", "severity", "question", "message"})


if __name__ == "__main__":
    unittest.main()
