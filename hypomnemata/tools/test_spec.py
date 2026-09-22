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
        borrowing = graph.get("ti-esti").definitions[0].tradition
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
        word = canon.definitions[0]
        self.assertEqual(spec.run(graph, only=["definition-once"]), [])
        party.definitions.append(word)
        findings = spec.run(graph, only=["definition-once"])
        self.assertEqual(findings[0].question, "canon")
        self.assertIn("party", findings[0].message)

    def test_a_headline_may_be_a_phrase_and_may_carry_a_link(self):
        """The narrowing that replaces no-ids-in-prose: a headline summarises
        and need not be a sentence, and may well be the handle a link points
        at. Only an opaque handle or a bare question id is wrong."""
        graph = load("valid")
        term = graph.get("ti-esti").theses[0].terms[0]
        for allowed in ("The record between them", "Memory is the repo",
                        "≡ ti esti", "GPT is not a handle"):
            term.title = allowed
            self.assertEqual(spec.run(graph, only=["headline-not-identifier"]), [],
                             allowed)
        for refused in ("term-001", "node_3"):
            term.title = refused
            self.assertTrue(spec.run(graph, only=["headline-not-identifier"]), refused)

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

    def test_a_question_that_has_been_put_waits_on_nothing_undone(self):
        """`requires` names what must be done before a question can be put.
        The root's answer is in thread, so the root has been put, and it may
        not still wait on its own promulgation, which is the act that follows
        an answer."""
        graph = load("valid")
        self.assertEqual(spec.run(graph, only=["requires-discharged"]), [])
        graph.get("ti-esti").requires = ["promulgate-the-root-answer"]
        findings = spec.run(graph, only=["requires-discharged"])
        self.assertEqual([f.question for f in findings], ["ti-esti"])
        self.assertIn("has been put but still waits on", findings[0].message)
        graph.get("ti-esti").inbox[0].done = True
        self.assertEqual(spec.run(graph, only=["requires-discharged"]), [])

    def test_landing_alone_is_not_being_put(self):
        """A question lands when it reaches main, and the root reached main as
        the seed it was asked from, before anyone put it. Until a thread is
        open on it, what it waits on may still be undone."""
        graph = load("valid")
        root = graph.get("ti-esti")
        root.requires = ["promulgate-the-root-answer"]
        root.theses[0].state = "held"
        self.assertEqual(root.state, "landed")
        self.assertEqual(spec.run(graph, only=["requires-discharged"]), [])
        root.state = "in thread"
        self.assertTrue(spec.run(graph, only=["requires-discharged"]))

    def test_an_undone_item_nothing_requires_is_reported(self):
        """An action exists only as something a question requires. A done item
        is exempt here: it blocks nothing, and while a question still names it
        the name shows that the wait is over. `inbox-history` reports it once
        nothing does."""
        graph = load("valid")
        self.assertEqual(spec.run(graph, only=["inbox-required"]), [])
        for q in graph.questions:
            q.requires = []
        findings = spec.run(graph, only=["inbox-required"])
        self.assertEqual([f.question for f in findings], ["ti-esti"])
        graph.get("ti-esti").inbox[0].done = True
        self.assertEqual(spec.run(graph, only=["inbox-required"]), [])

    def test_a_deadlock_carries_its_counter_and_once_landed_its_grading(self):
        """Dissent without a grading is half a record: what the principal holds
        instead, and what the clause may still license. The grading is owed at
        the merge: on an open thread the clause licenses nothing yet."""
        graph = load("valid")
        self.assertEqual(spec.run(graph, only=["deadlock-complete"]), [])
        thesis, term = [(th, t) for q in graph.questions for th in q.theses
                        for t in th.terms if t.deadlock][0]
        self.assertNotEqual(thesis.state, "landed")
        term.deadlock.attenuation = ""
        self.assertEqual(spec.run(graph, only=["deadlock-complete"]), [])
        thesis.state = "landed"
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

    def test_no_answer_gets_further_than_its_question(self):
        """An answer is given to a question that has been put, and merged with
        it or after it. The question may be ahead — the root landed as a seed
        before it was answered — and never behind."""
        graph = load("valid")
        self.assertEqual(spec.run(graph, only=["state-order"]), [])
        root = graph.get("ti-esti")
        self.assertEqual((root.state, root.theses[0].state), ("landed", "in thread"))
        root.state = "held"
        findings = spec.run(graph, only=["state-order"])
        self.assertEqual([f.question for f in findings], ["ti-esti"])
        self.assertIn("further than its question", findings[0].message)

    def test_standing_is_read_off_the_state(self):
        """Canon once landed, a postulate until then: one datum, one home."""
        root = load("valid").get("ti-esti")
        self.assertEqual((root.standing, root.theses[0].standing),
                         ("canon", "postulate"))
        root.theses[0].state = "landed"
        self.assertEqual(root.theses[0].standing, "canon")

    def test_an_application_is_derived_only_from_a_landed_answer(self):
        graph = load("valid")
        thesis, app = list(graph.get("ti-esti").applications())[0]
        app.standing = "derived"
        self.assertIn("comes from is 'in thread' and not landed",
                      spec.run(graph, only=["standing-honest"])[0].message)
        thesis.state = "landed"
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
        word = graph.get("canon").definitions[0].word
        self.assertEqual(spec.run(graph, only=["definition-anchorable"]), [])
        thesis.text = thesis.text.replace(word, word + "s")
        self.assertEqual(spec.run(graph, only=["definition-anchorable"]), [])
        # the question's hinge brings words in too, so it is cleared of this one
        graph.get("canon").hinge.question = "that a mark can be made at all"
        thesis.text = thesis.text.replace(word + "s", "un" + word + "ish")
        findings = spec.run(graph, only=["definition-anchorable"])
        self.assertEqual([f.question for f in findings], ["canon"])
        self.assertIn("in any regular form", findings[0].message)

    def test_a_word_may_come_in_on_the_question_s_hinge(self):
        """A question brings a word in through an answer, or through what its
        asking stood on. The root has no ancestors, so a word its hinge
        presupposed could be defined nowhere it reached until the hinge
        counted. The answer's half of the hinge records how the answer was
        drawn and brings no word in."""
        graph = load("valid")
        canon = graph.get("canon")
        word = canon.definitions[0].word
        canon.theses[0].text = canon.theses[0].text.replace(
            "marked %s" % word, "marked accord")
        self.assertIn(word, canon.hinge.question)
        self.assertEqual(spec.run(graph, only=["definition-anchorable"]), [])
        canon.hinge.question = "that a mark can be made at all"
        canon.hinge.thesis += " · the %s was noted" % word
        findings = spec.run(graph, only=["definition-anchorable"])
        self.assertEqual([f.question for f in findings], ["canon"])

    def test_an_author_question_names_its_answerer_and_a_tradition_does_not(self):
        graph = load("valid")
        self.assertEqual(spec.run(graph, only=["answerer-set"]), [])
        graph.get("plato").answerer = "principal"
        graph.get("canon").answerer = "the AI"
        findings = spec.run(graph, only=["answerer-set"])
        self.assertEqual(sorted(f.question for f in findings), ["canon", "plato"])

    def test_a_shadow_names_another_question(self):
        graph = load("valid")
        word = graph.get("canon").definitions[0]
        word.question = "party"
        self.assertEqual(spec.run(graph, only=["term-target"]), [])
        word.question = "canon"
        self.assertIn("its own question",
                      spec.run(graph, only=["term-target"])[0].message)
        word.question = "nowhere"
        self.assertIn("no question", spec.run(graph, only=["term-target"])[0].message)

    def test_a_term_inside_another_is_at_the_wrong_grain(self):
        findings = spec.run(load("invalid-anchor-grain"), only=["anchor-grain"])
        self.assertEqual([f.question for f in findings], ["ti-esti"])
        self.assertIn("'Two sides, two debts'", findings[0].message)

    def test_a_word_the_ai_uses_is_the_notebook_s_to_give_up(self):
        """The finding goes where the word is defined, since that is the word
        that can change. A held answer is the principal's own, and can change
        too; and a word the answer's own question defines had its sense fixed
        against that very answer."""
        graph = load("invalid-verbatim-collision")
        findings = spec.run(graph, only=["verbatim-collision"])
        self.assertEqual([f.question for f in findings], ["attenuation"])
        self.assertIn("'graded'", findings[0].message)
        root = graph.get("ti-esti")
        root.theses[0].state = "held"
        self.assertEqual(spec.run(graph, only=["verbatim-collision"]), [])
        root.theses[0].state = "in thread"
        owner = graph.get("attenuation")
        word = [d for d in owner.definitions if d.word == "grade"][0]
        owner.definitions.remove(word)
        root.definitions.append(word)
        self.assertEqual(spec.run(graph, only=["verbatim-collision"]), [])

    def test_a_clause_is_suspended_only_on_an_open_thread(self):
        """Acceptance withheld while the thread runs. The merge settles every
        clause, so a landed answer carries no suspension, and an answer never
        put has no thread to suspend in."""
        graph = load("valid")
        root = graph.get("ti-esti")
        term = root.theses[0].terms[0]
        term.suspended = "whether the other side would say it unprompted"
        self.assertEqual(root.theses[0].state, "in thread")
        self.assertEqual(spec.run(graph, only=["suspension-open"]), [])
        root.theses[0].state = "landed"
        self.assertIn("not in thread",
                      spec.run(graph, only=["suspension-open"])[0].message)
        root.theses[0].state = "in thread"
        term.deadlock = model.Deadlock(counter="the principal holds otherwise")
        self.assertIn("both suspended and deadlocked",
                      spec.run(graph, only=["suspension-open"])[0].message)

    def test_a_done_item_is_history_once_nothing_names_it(self):
        graph = load("valid")
        item = graph.get("ti-esti").inbox[0]
        item.done = True
        # still named by the questions that waited on it: it shows they are ready
        self.assertEqual(spec.run(graph, only=["inbox-history"]), [])
        for q in graph.questions:
            q.requires = []
        self.assertEqual([f.question for f in spec.run(graph, only=["inbox-history"])],
                         ["ti-esti"])

    def test_findings_render_as_one_line_and_as_json(self):
        finding = spec.run(load("invalid-vocabulary"), only=["vocabulary"])[0]
        self.assertEqual(len(finding.line().splitlines()), 1)
        self.assertEqual(set(finding.as_dict()),
                         {"check", "severity", "question", "message"})


if __name__ == "__main__":
    unittest.main()
