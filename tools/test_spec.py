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


class AnchorUniqueTest(unittest.TestCase):
    def test_an_anchor_that_overlaps_itself_is_two_places_for_one_chip(self):
        """Counted without overlap it occurs once; the renderer scans every
        start and puts down two chips."""
        graph = load("valid")
        thesis = graph.get("ti-esti").theses[0]
        thesis.text += " It is so that that that is said."
        thesis.terms[0].anchors.append("that that")
        fired = [f for f in spec.run(graph) if f.check == "anchor-unique"]
        self.assertTrue(fired)

    def test_an_anchor_the_answer_above_also_says_is_linked_on_the_wrong_one(self):
        """Once in its own answer, so the chip has one place; but a link is
        resolved across the tab's Thesis section, and the reader files a term
        under the first answer holding its anchor, so the second answer's term
        would be linked and read back on the first."""
        graph = load("valid")
        q = graph.get("ti-esti")
        self.assertIn("series of errands", q.theses[0].text)
        q.theses.append(model.Thesis(
            title="A series of errands has no memory",
            text="A series of errands has no memory, and a relationship does.",
            assent="none", state="held",
            terms=[model.Term(title="Errands", to="party",
                              anchors=["series of errands"])]))
        findings = spec.run(graph, only=["anchor-unique"])
        self.assertEqual([f.question for f in findings], ["ti-esti"])
        self.assertIn("another answer", findings[0].message)
        self.assertIn("'Errands'", findings[0].message)

    def test_a_citation_s_note_stands_in_the_section_too(self):
        graph = load("valid")
        thesis = graph.get("ti-esti").theses[0]
        thesis.traditions[0].note = "Plato also calls it a series of errands"
        thesis.terms[0].anchors.append("series of errands")
        findings = spec.run(graph, only=["anchor-unique"])
        self.assertEqual([f.question for f in findings], ["ti-esti"])


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

    def test_only_the_ai_s_questions_are_put(self):
        """Another party's question is read, not asked, and lands no more than
        the principal's does; the fixture covers his, this covers theirs."""
        graph = load("valid")
        self.assertEqual(spec.run(graph, only=["only-ai-put"]), [])
        graph.get("plato").state = "landed"
        findings = spec.run(graph, only=["only-ai-put"])
        self.assertEqual([f.question for f in findings], ["plato"])
        self.assertIn("another party", findings[0].message)

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

    def test_a_word_canon_uses_is_the_notebook_s_to_give_up(self):
        """The finding goes where the word is defined, since that is the word
        that can change. An answer held or in thread is in the notebook only,
        and can change too; and a word the answer's own question defines had
        its sense fixed against that very answer."""
        graph = load("invalid-verbatim-collision")
        findings = spec.run(graph, only=["verbatim-collision"])
        self.assertEqual([f.question for f in findings], ["attenuation"])
        self.assertIn("'graded'", findings[0].message)
        root = graph.get("ti-esti")
        for state in ("held", "in thread"):
            root.theses[0].state = state
            self.assertEqual(spec.run(graph, only=["verbatim-collision"]), [], state)
        root.theses[0].state = "landed"
        owner = graph.get("attenuation")
        word = [d for d in owner.definitions if d.word == "grade"][0]
        owner.definitions.remove(word)
        root.definitions.append(word)
        self.assertEqual(spec.run(graph, only=["verbatim-collision"]), [])

    def test_an_answer_is_the_notebook_s_until_it_lands(self):
        """Only what canon records cannot be reworded. An answer in thread is
        dictation like an answer held, so a word out of its reach is reported
        on it, where it can be changed; once landed the words are canon's, and
        the finding moves to where the word is defined."""
        graph = load("invalid-verbatim-collision")
        root = graph.get("ti-esti")
        self.assertEqual(root.theses[0].state, "landed")
        self.assertEqual(spec.run(graph, only=["reach"]), [])
        for state in ("in thread", "held"):
            root.theses[0].state = state
            findings = spec.run(graph, only=["reach"])
            # one finding per form of the word the answer uses
            self.assertEqual({f.question for f in findings}, {"ti-esti"}, state)
            said = " ".join(f.message for f in findings)
            self.assertIn("an answer uses 'graded'", said)
            self.assertIn("fixed on attenuation", said)

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

    def test_a_word_is_used_where_its_sense_can_be_reached(self):
        """The context rule over the notebook's own words: a turn carries
        canon above its question, so a word leans on a sense that will be
        there only if the question fixing it stands above."""
        graph = load("valid")
        self.assertEqual(spec.run(graph, only=["reach"]), [])
        canon = graph.get("canon")
        canon.notes.append(model.Note(section="thesis", body="The grade is his."))
        findings = spec.run(graph, only=["reach"])
        self.assertEqual([f.question for f in findings], ["canon"])
        self.assertIn("attenuation", findings[0].message)

    def test_reach_says_a_word_used_twice_once(self):
        """A word out of reach is one thing out of reach, however often the
        part uses it; the count rides on the one finding."""
        graph = load("valid")
        canon = graph.get("canon")
        canon.notes.append(model.Note(section="thesis",
                                      body="The grade is his, and the grade is read."))
        findings = spec.run(graph, only=["reach"])
        self.assertEqual(len(findings), 1)
        self.assertIn("'grade' (twice)", findings[0].message)

    def test_reach_names_the_import_a_party_s_word_wants(self):
        """No edge and no move of the definition brings a party's word into
        reach, so the one remedy there is gets named."""
        graph = load("valid")
        plato = graph.get("plato")
        plato.theses[0].text += " What he grants is a homologia."
        plato.definitions.append(model.Definition(
            word="homologia", body="What the one questioned has granted."))
        root = graph.get("ti-esti")
        root.theses[0].traditions[0].note += "; the homologia is his"
        findings = spec.run(graph, only=["reach"])
        self.assertEqual(len(findings), 1)
        self.assertIn("import that names the party", findings[0].message)
        canon = graph.get("canon")
        canon.notes.append(model.Note(section="thesis", body="The grade is his."))
        own = [f for f in spec.run(graph, only=["reach"]) if f.question == "canon"]
        self.assertNotIn("import", own[0].message)

    def test_a_definition_of_a_question_s_word_says_it_is_a_shadow(self):
        """The word of a question has its sense on that question's tab; an
        entry for it anywhere else stands in for that tab, and points there."""
        graph = load("valid")
        canon = graph.get("canon")
        canon.theses[0].text += " The party with standing is the one who marks."
        canon.definitions.append(model.Definition(
            word="party", body="Either side of the bond."))
        findings = spec.run(graph, only=["shadow-declared"])
        self.assertEqual([f.question for f in findings], ["canon"])
        self.assertIn("shadow", findings[0].message)
        self.assertEqual(findings[0].severity, spec.WARN)
        canon.definitions[-1].question = "party"
        self.assertEqual(spec.run(graph, only=["shadow-declared"]), [])
        self.assertEqual(spec.run(graph, only=["term-target"]), [])

    def test_a_question_s_own_definition_and_an_import_are_not_shadows(self):
        graph = load("valid")
        party = graph.get("party")
        party.theses[0].text += " A party is either side."
        party.definitions.append(model.Definition(
            word="party", body="Either side of the bond."))
        plato = graph.get("plato")
        plato.theses[0].text += " The one questioned is a party to it."
        plato.definitions.append(model.Definition(
            word="party", body="", tradition=model.Borrowing(to="plato", note="")))
        self.assertEqual(spec.run(graph, only=["shadow-declared"]), [])

    def test_a_party_s_word_is_imported_rather_than_assumed(self):
        """A party's notebook never stands above a question here, so its word
        is brought in by an entry that says so, or it is out of reach."""
        graph = load("valid")
        plato = graph.get("plato")
        plato.theses[0].text += " What he grants is a homologia."
        plato.definitions.append(model.Definition(
            word="homologia", body="What the one questioned has granted."))
        root = graph.get("ti-esti")
        edge = root.theses[0].traditions[0]
        edge.note += "; the homologia is his"
        findings = spec.run(graph, only=["reach"])
        self.assertEqual([f.question for f in findings], ["ti-esti"])
        root.definitions.append(model.Definition(
            word="homologia", body="", tradition=model.Borrowing(to="plato", note="")))
        self.assertEqual(spec.run(graph, only=["reach"]), [])
        self.assertEqual(spec.run(graph, only=["import-defined"]), [])
        self.assertEqual(spec.run(graph, only=["definition-once"]), [])
        self.assertEqual(spec.run(graph, only=["definition-anchorable"]), [])

    def test_an_import_whose_party_defines_nothing_points_at_nothing(self):
        graph = load("valid")
        root = graph.get("ti-esti")
        root.theses[0].traditions[0].note += "; the homologia is his"
        root.definitions.append(model.Definition(
            word="homologia", body="", tradition=model.Borrowing(to="plato", note="")))
        findings = spec.run(graph, only=["import-defined"])
        self.assertEqual([f.question for f in findings], ["ti-esti"])
        self.assertIn("does not define it", findings[0].message)

    def test_nothing_is_put_below_a_question_that_has_not_been(self):
        """A turn carries canon above its question; an answer that was never
        asked for is neither on main nor on the branch."""
        graph = load("valid")
        self.assertEqual(spec.run(graph, only=["put-in-order"]), [])
        root = graph.get("ti-esti")
        root.state, root.theses[0].state = "held", "held"
        graph.get("canon").state = "in thread"
        findings = spec.run(graph, only=["put-in-order"])
        self.assertEqual([f.question for f in findings], ["canon"])
        self.assertIn("ti-esti", findings[0].message)

    def test_a_list_keeps_its_line_breaks_and_a_paragraph_may_not(self):
        """A single newline is the markdown's own inside a list, and a wrap
        anywhere else: the document joins it, so the page and the renderer
        would disagree for as long as the text stood."""
        graph = load("valid")
        thesis = graph.get("ti-esti").theses[0]
        self.assertEqual(spec.run(graph, only=["text-unwrapped"]), [])
        kept = thesis.text
        thesis.text = "What it requires of me\n- Report truthfully.\n- Be predictable."
        self.assertEqual(spec.run(graph, only=["text-unwrapped"]), [])
        thesis.text = kept.replace(" ", "\n", 1)
        findings = spec.run(graph, only=["text-unwrapped"])
        self.assertEqual([f.question for f in findings], ["ti-esti"])

    def test_a_quotation_mark_is_a_character_inside_a_paragraph_and_a_note_at_a_block(self):
        """The reader files a block that opens with ``>`` as a note on the
        section, so an answer's text may not open one; a ``>`` inside a
        paragraph is only a character, and the reader leaves it alone."""
        graph = load("valid")
        thesis = graph.get("canon").theses[0]
        self.assertEqual(spec.run(graph, only=["text-unquoted"]), [])
        thesis.text += " Where a > b, the entry says so."
        self.assertEqual(spec.run(graph, only=["text-unquoted"]), [])
        thesis.text += "\n\n> Said again, as a quotation."
        findings = spec.run(graph, only=["text-unquoted"])
        self.assertEqual([f.question for f in findings], ["canon"])
        self.assertIn("Said again", findings[0].message)
        thesis.text = "> Opening on a quotation."
        self.assertEqual([f.question for f in spec.run(graph, only=["text-unquoted"])],
                         ["canon"])

    def test_findings_render_as_one_line_and_as_json(self):
        finding = spec.run(load("invalid-vocabulary"), only=["vocabulary"])[0]
        self.assertEqual(len(finding.line().splitlines()), 1)
        self.assertEqual(set(finding.as_dict()),
                         {"check", "severity", "question", "message"})


class PlainWordsTest(unittest.TestCase):
    """The checks that compare words compare them as the page holds them:
    the characters, with the emphasis beside them and not among them."""

    def test_an_anchor_said_once_in_bold_and_once_plain_is_said_twice(self):
        """The sidecar resolves an anchor on the plain page, so the bold
        occurrence and the plain one are two runs, and the link takes the
        first; the marked-up count alone saw one."""
        graph = load("valid")
        thesis = graph.get("ti-esti").theses[0]
        term = thesis.terms[0]
        anchor = term.anchors[0]
        self.assertEqual(thesis.text.count(anchor), 1)
        thesis.text = thesis.text.replace(anchor, "**%s**" % anchor) + " " + anchor + "."
        term.anchors[0] = "**%s**" % anchor
        self.assertEqual(spec.run(graph, only=["anchor-substring"]), [])
        findings = spec.run(graph, only=["anchor-unique"])
        self.assertEqual([f.question for f in findings], ["ti-esti"])

    def test_a_restatement_is_found_through_emphasis_and_a_closing_stop(self):
        graph = load("valid")
        src = graph.get("ti-esti")
        term = next(t for t in src.terms())
        anchor = term.anchors[0]
        src.theses[0].text = src.theses[0].text.replace(anchor, "**%s**" % anchor, 1)
        term.anchors[0] = "**%s**" % anchor
        graph.get(term.to).question = "%s: what is it?" % anchor.rstrip(".")
        findings = spec.run(graph, only=["no-restatement"])
        self.assertEqual([f.question for f in findings], [term.to])


class WholeGraphTest(unittest.TestCase):
    def test_a_word_defined_twice_on_one_question_is_defined_twice(self):
        graph = load("valid")
        canon = graph.get("canon")
        self.assertIn("assent", [d.word for d in canon.definitions])
        canon.definitions.append(model.Definition(word="assent", body="A second sense."))
        findings = spec.run(graph, only=["definition-once"])
        self.assertEqual([f.question for f in findings], ["canon"])
        self.assertIn("this same question", findings[0].message)

    def test_the_shadowed_question_reaches_its_own_word(self):
        """A shadow fixes nothing: the sense is the question's own, and the
        question and what stands under it reach it."""
        graph = load("valid")
        graph.get("canon").definitions.append(
            model.Definition(word="party", body="Either side of the bond.", question="party"))
        graph.get("party").theses[0].text += " A party is either side."
        findings = spec.run(graph, only=["reach"])
        self.assertEqual([f.message for f in findings if f.question == "party"], [])

    def test_an_import_is_not_where_a_word_is_defined(self):
        graph = load("valid")
        graph.get("canon").definitions.append(
            model.Definition(word="grade", body="", tradition=model.Borrowing(to="plato")))
        root = graph.get("ti-esti").theses[0]
        root.state = "landed"
        root.text += " The grade is settled."
        findings = spec.run(graph, only=["verbatim-collision"])
        self.assertEqual([f.question for f in findings], ["attenuation"])

    def test_what_an_application_says_is_judged_for_reach(self):
        graph = load("valid")
        _, app = next(graph.get("ti-esti").applications())
        app.what = "it reads the grade off the state"
        findings = spec.run(graph, only=["reach"])
        self.assertTrue([f for f in findings if f.question == "ti-esti" and "⚙" in f.message])

    def test_a_mention_without_an_anchor_is_refused(self):
        graph = load("valid")
        graph.get("ti-esti").theses[0].mentions.append(
            model.Mention(title="Where authority is settled", to="canon", anchors=[]))
        findings = spec.run(graph, only=["term-total"])
        self.assertEqual([f.question for f in findings], ["ti-esti"])
        self.assertIn("mention", findings[0].message)

    def test_a_check_that_is_not_there_is_refused(self):
        with self.assertRaises(ValueError):
            spec.run(load("valid"), only=["acylic"])

    def test_two_answers_at_one_headline_are_refused(self):
        graph = load("valid")
        q = graph.get("ti-esti")
        q.theses.append(model.Thesis(title=q.theses[0].title, text="Said again.",
                                     assent="none", state="held"))
        findings = spec.run(graph, only=["unique-ids"])
        self.assertEqual([f.question for f in findings], ["ti-esti"])

    def test_two_anchors_that_overlap_are_refused(self):
        graph = load("valid")
        thesis = graph.get("ti-esti").theses[0]
        thesis.text = "The record kept between them is the only thing both can point at."
        thesis.terms = [model.Term(title="a", to="canon", anchors=["The record kept between them"]),
                        model.Term(title="b", to="party", anchors=["between them is the only thing"])]
        findings = spec.run(graph, only=["anchor-grain"])
        self.assertEqual([f.question for f in findings], ["ti-esti"])
        self.assertIn("overlapping", findings[0].message)


class RootKindTest(unittest.TestCase):
    def test_a_question_of_kind_root_with_a_raiser_is_refused(self):
        graph = load("valid")
        graph.get("canon").kind = "root"
        findings = spec.run(graph, only=["one-root"])
        self.assertEqual([f.question for f in findings], ["canon"])

    def test_a_party_s_tab_alone_is_a_graph_without_a_root(self):
        """Its ancestors are none, so a scoped read of it holds no root, and
        that is not a finding: the root stands above the scope."""
        graph = load("valid")
        graph.questions = [graph.get("plato")]
        graph.scope = ["plato"]
        self.assertEqual(spec.run(graph, only=["one-root"]), [])


class PartedTextTest(unittest.TestCase):
    def test_a_heading_inside_an_answer_is_refused(self):
        graph = load("valid")
        graph.get("ti-esti").theses[0].text += "\n\n### A sub-heading\n\nA closing paragraph."
        findings = spec.run(graph, only=["text-unquoted"])
        self.assertEqual([f.question for f in findings], ["ti-esti"])
        self.assertIn("heading", findings[0].message)

    def test_a_citation_heading_inside_an_answer_is_refused(self):
        graph = load("valid")
        graph.get("ti-esti").theses[0].text += "\n\n**Support**\n\nA closing paragraph."
        findings = spec.run(graph, only=["text-unquoted"])
        self.assertEqual([f.question for f in findings], ["ti-esti"])

    def test_a_blockquote_in_the_hinge_is_refused(self):
        graph = load("valid")
        q = graph.get("canon")
        self.assertIsNotNone(q.hinge)
        q.hinge.question = "> what the asking presumes"
        findings = spec.run(graph, only=["text-unquoted"])
        self.assertEqual([f.question for f in findings], ["canon"])
        self.assertIn("hinge", findings[0].message)

    def test_a_text_ending_in_a_line_break_is_said_so(self):
        graph = load("valid")
        graph.get("canon").theses[0].text += "\n"
        findings = spec.run(graph, only=["text-unwrapped"])
        self.assertEqual([f.question for f in findings], ["canon"])
        self.assertIn("ends in a line break", findings[0].message)

    def test_a_list_item_is_one_the_page_writes(self):
        """A bullet wants its space: ``-b`` is a wrapped line, ``+ b`` and
        ``1) b`` are items the renderer places a chip by."""
        graph = load("valid")
        thesis = graph.get("canon").theses[0]
        kept = thesis.text
        for text in ("Two things:\n+ the first\n+ the second", "Two:\n1) a\n2) b"):
            thesis.text = text
            self.assertEqual(spec.run(graph, only=["text-unwrapped"]), [], text)
        thesis.text = "What it needs\n-b"
        self.assertEqual([f.question for f in spec.run(graph, only=["text-unwrapped"])],
                         ["canon"])
        thesis.text = kept

    def test_a_citation_s_note_is_one_line(self):
        graph = load("valid")
        edge = next(e for t in graph.get("ti-esti").theses for e in t.traditions)
        edge.note = "first line\nsecond line"
        findings = spec.run(graph, only=["text-unwrapped"])
        self.assertEqual([f.question for f in findings], ["ti-esti"])
        self.assertIn("one", findings[0].message)


class NoteUnstoppedTest(unittest.TestCase):
    def test_a_citation_s_note_ending_in_a_stop_is_refused(self):
        findings = spec.run(load("invalid-note-unstopped"), only=["note-unstopped"])
        self.assertEqual([f.question for f in findings], ["ti-esti"])
        self.assertIn("the note on the citation of plato", findings[0].message)
        self.assertEqual(spec.run(load("valid"), only=["note-unstopped"]), [])

    def test_a_counter_and_a_borrowing_s_note_are_judged_too(self):
        graph = load("valid")
        edge = graph.get("ti-esti").theses[0].traditions[0]
        edge.relation, edge.counter = "divergence", "he asks first..."
        graph.get("ti-esti").definitions[0].tradition.note = "a borrowed sense."
        messages = [f.message for f in spec.run(graph, only=["note-unstopped"])]
        self.assertEqual(len(messages), 2)
        self.assertTrue(any("the counter on the citation" in m for m in messages))
        self.assertTrue(any("the borrowing of" in m for m in messages))


class FieldsPartedTest(unittest.TestCase):
    def test_a_headline_carrying_the_separator_is_refused_before_any_application_says_it(self):
        graph = load("valid")
        canon = graph.get("canon")
        self.assertEqual(list(canon.applications()), [])
        canon.theses[0].title = "An entry binds · when marked."
        findings = spec.run(graph, only=["fields-parted"])
        self.assertEqual([f.question for f in findings], ["canon"])

    def test_an_application_s_link_carrying_it_is_refused(self):
        graph = load("valid")
        _, app = next(graph.get("ti-esti").applications())
        app.link = "entries/a · b.md"
        findings = spec.run(graph, only=["fields-parted"])
        self.assertEqual([f.question for f in findings], ["ti-esti"])
        self.assertIn("link", findings[0].message)


if __name__ == "__main__":
    unittest.main()
