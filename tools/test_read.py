"""render then read is the identity on everything the markdown carries."""

import os
import re
import unittest

from hypo import model, read, render
import test_render  # the works a party is read from
from support import FIXTURES, chip_ids, load

#: what the document holds and the markdown does not, per class. A question's
#: ``party`` is derived from the tab order; a definition's tradition is on the page,
#: as the chip that closes it, so it is compared like everything else.
UNCARRIED = {
    "Question": ("tab", "body", "party", "project", "rev"),
    "Graph": ("path", "questions", "artifact", "mode", "state_enum", "scope", "projects"),
}


def shed(value):
    """A model object as plain data, dropping what the markdown never carries."""
    if isinstance(value, list):
        return [shed(v) for v in value]
    if hasattr(value, "__dataclass_fields__"):
        out = {}
        for name in value.__dataclass_fields__:
            if name in UNCARRIED.get(type(value).__name__, ()):
                continue
            field = shed(getattr(value, name))
            if field in ([], "", None, False):
                continue
            out[name] = field
        return out
    return value


class RoundTripTest(unittest.TestCase):
    """The hand-written step in the middle of the loop, removed.

    Until this existed the renderer produced a correct tab, the checker
    validated a correct graph, and nothing at all compared the two with what
    was on the page.
    """

    def assert_round_trips(self, name):
        graph = load(name) if isinstance(name, str) else name
        ids = chip_ids(graph)
        for q in graph.questions:
            with self.subTest(fixture=name, question=q.id):
                parsed = read.parse_tab(render.body(graph, q.id), ids)
                # back through the model, so the comparison is of objects and
                # not of the shape this particular parser happens to emit
                again = model.Question.read(model._Reader(), dict(
                    parsed, tab=q.tab, body=q.body), "round-trip")
                self.assertEqual(shed(again), shed(q))

    def test_the_valid_graph(self):
        self.assert_round_trips("valid")

    #: the fixtures whose mutation is a text the page cannot carry back: a
    #: blockquote inside an answer, which the reader files as a note, and a
    #: headline carrying the separator of the application line that says it.
    #: A work's field carrying that separator is the same fault on a party's
    #: works. That they do not round-trip is the finding, and the tests below
    #: hold it.
    NOT_CARRIED = {"invalid-text-unquoted", "invalid-fields-parted", "invalid-note-unstopped",
                   "invalid-work-fields"}

    def test_every_invalid_fixture_too(self):
        """They are whole graphs with one mutation, so they exercise shapes the
        valid one does not — a term deadlock, a second thesis, a bad target."""
        for name in sorted(os.listdir(FIXTURES)):
            if name.startswith("invalid-") and name.endswith(".json"):
                if name[:-5] not in self.NOT_CARRIED:
                    self.assert_round_trips(name[:-5])

    def test_a_note_s_own_stop_does_not_come_back(self):
        """The renderer closes a note with one stop and the reader takes one
        off, so a note stored with its own ends one stop short at every
        rebuild. ``note-unstopped`` refuses the graph before it is written;
        this is what it stands between, and the one stop that does come off
        is the renderer's."""
        graph = load("invalid-note-unstopped")
        edge = graph.get("ti-esti").theses[0].traditions[0]
        self.assertTrue(edge.note.endswith("doing."))
        parsed = read.parse_tab(render.body(graph, "ti-esti"), chip_ids(graph))
        self.assertEqual(parsed["theses"][0]["traditions"][0]["note"], edge.note[:-1])
        edge.note = "asked of what the answerer is doing, etc"
        parsed = read.parse_tab(render.body(graph, "ti-esti"), chip_ids(graph))
        self.assertEqual(parsed["theses"][0]["traditions"][0]["note"], edge.note)

    def test_a_blockquote_in_an_answer_comes_back_as_a_note(self):
        """A blockquote is somebody's note wherever it stands, so one inside
        an answer's text leaves the answer on the way back and the next render
        writes it at the section's foot: the one edit to a verbatim text the
        local round trip cannot see. ``text-unquoted`` refuses the graph
        before it is written; this is what it stands between."""
        graph = load("invalid-text-unquoted")
        thesis = graph.get("canon").theses[0]
        self.assertIn("\n\n> Not a message in a thread.\n\n", thesis.text)
        parsed = read.parse_tab(render.body(graph, "canon"), chip_ids(graph))
        self.assertNotIn(">", parsed["theses"][0]["text"])
        self.assertEqual(parsed["notes"], [{"section": "thesis",
                                            "body": "Not a message in a thread."}])


class WorksTest(unittest.TestCase):
    """A party's works come back exactly, in any spelling a read gives them."""

    def setUp(self):
        self.graph = test_render.with_works(load("valid"))
        self.ids = chip_ids(self.graph)
        self.page = render.body(self.graph, "plato")

    def test_they_round_trip(self):
        RoundTripTest.assert_round_trips(self, self.graph)

    def test_they_are_left_off_a_tab_without_them(self):
        self.assertNotIn("works", read.parse_tab(render.body(self.graph, "canon"), self.ids))

    def test_the_url_is_read_off_the_target_in_any_spelling(self):
        """The renderer's link, its words as the page speller spells them; an
        autolink; and the bare url a read gives where the link was lost."""
        url = self.graph.get("plato").works[0].url
        written = "[%s](%s)" % (url.replace("_", "\\_"), url)
        self.assertIn(written, self.page)
        for spelled in ("[%s](%s)" % (url, url), "<%s>" % url, url):
            with self.subTest(spelled=spelled):
                again = read.parse_tab(self.page.replace(written, spelled), self.ids)
                self.assertEqual(again["works"][0]["url"], url)

    def test_a_line_out_of_order_is_refused(self):
        stale = self.page.replace("work: *Euthyphro* · author: Plato",
                                  "author: Plato · work: *Euthyphro*")
        self.assertNotEqual(stale, self.page)
        with self.assertRaises(read.ParseError) as caught:
            read.parse_tab(stale, self.ids)
        self.assertIn("a work's line is malformed", str(caught.exception))

    def test_a_field_carrying_the_separator_does_not_come_back(self):
        """``work-fields`` refuses the graph before it is written; this is
        what it stands between."""
        graph = load("invalid-work-fields")
        with self.assertRaises(read.ParseError):
            read.parse_tab(render.body(graph, "plato"), chip_ids(graph))

    def test_a_note_with_no_line_reads_as_the_note(self):
        works = self.graph.get("plato").works
        works[1].verified, works[1].note = "", "Owed a reading."
        again = read.parse_tab(render.body(self.graph, "plato"), self.ids)
        self.assertEqual(again["works"][1], {"key": "RB-5", "note": "Owed a reading."})


class DetailTest(unittest.TestCase):
    def setUp(self):
        self.graph = load("valid")
        self.ids = chip_ids(self.graph)

    def parse(self, qid):
        return read.parse_tab(render.body(self.graph, qid), self.ids)

    def test_the_breadcrumb_is_not_stored(self):
        """It is projected from the edges at every render, so reading it back
        would be storing a second copy of the tree."""
        self.assertNotIn("lineage", self.parse("attenuation"))

    def test_the_incoming_anchors_come_back_with_their_source(self):
        incoming = self.parse("attenuation")["incoming"]
        self.assertEqual([src for _, src in incoming], ["canon", "party"])

    def test_a_section_the_renderer_does_not_write_is_refused(self):
        """Read on, the section would leave the page in silence at the next
        body write. The page is brought up to the grammar first."""
        body = render.body(self.graph, "canon")
        stale = body.replace("## Terms", "## Elsewhere\n\n### a heading of its own"
                             "\n\nwords the renderer never wrote\n\n## Terms", 1)
        self.assertNotEqual(stale, body)
        with self.assertRaises(read.ParseError) as caught:
            read.parse_tab(stale, self.ids)
        self.assertIn("a section the renderer does not write", str(caught.exception))
        self.assertIn("## elsewhere", str(caught.exception).lower())

    def test_a_question_line_with_a_field_it_does_not_hold_is_refused(self):
        body = render.body(self.graph, "canon")
        stale = re.sub(r"(?m)^(question: .*)$", r"\1 · due: tomorrow", body, count=1)
        self.assertNotEqual(stale, body)
        with self.assertRaises(read.ParseError) as caught:
            read.parse_tab(stale, self.ids)
        self.assertIn("the question line is malformed", str(caught.exception))

    def test_a_tab_that_is_not_a_tab_is_refused(self):
        with self.assertRaises(read.ParseError):
            read.parse_tab("just some prose", self.ids)

    def test_a_question_that_ends_in_emphasis_comes_back_whole(self):
        """The line is the question in italics; one layer comes off, and not
        the closing marker of a word the question itself emphasises."""
        self.graph.get("canon").question = "What makes an entry *binding*"
        parsed = read.parse_tab(render.body(self.graph, "canon"), self.ids)
        self.assertEqual(parsed["question"], "What makes an entry *binding*")

    def test_a_term_on_a_second_answer_comes_back_on_it(self):
        """The page files every term under one section; which answer raised
        it is said only by the chip in that answer's text."""
        q = self.graph.get("canon")
        q.theses.append(model.Thesis(
            title="A second reading",
            text="An entry is also a promise that binds.",
            assent="none", state="held",
            terms=[model.Term(title="A promise", to="attenuation",
                              anchors=["a promise that binds"])]))
        parsed = read.parse_tab(render.body(self.graph, "canon"), self.ids)
        self.assertEqual([t["title"] for t in parsed["theses"][1]["terms"]],
                         ["A promise"])
        self.assertNotIn("A promise",
                         [t["title"] for t in parsed["theses"][0]["terms"]])

    def test_an_exported_chip_reads_the_same_as_a_token(self):
        """The document flattens a chip to a link when it exports markdown."""
        body = render.body(self.graph, "ti-esti")
        exported = body.replace("<?claude block m_canon?>", "[canon](file/tab-02)")
        self.assertEqual(read.parse_tab(exported, self.ids),
                         read.parse_tab(body, self.ids))

    def test_the_sidecar_links_come_back_off(self):
        """A link is applied to the page after the body is written, so every
        export carries links no graph file ever held. Left in, the one on
        `provenance: thesis hinge` would take the assent line out of its own
        grammar and the assent with it."""
        body = render.body(self.graph, "ti-esti")
        applied = body
        for words, href in (
                ("assent: assented at the merge of the opening entry",
                 "#mg8.1"),  # the same paragraph as the provenance link
                ("The record kept between them is the only thing both can point at.",
                 "https://claude.ai/artifact/9sZhZQn34X8FRkU2U8i51Z#tab-01.mg8.44"),
                ("elenchus", "#tab-01.mg8.90")):
            applied = applied.replace(words, "[%s](%s)" % (words, href), 1)
        self.assertNotEqual(applied, body)
        self.assertEqual(read.parse_tab(applied, self.ids),
                         read.parse_tab(body, self.ids))

    def test_a_chip_kept_as_text_reads_the_same_as_a_token(self):
        """The export writes a chip as `[label](file/…)` sometimes and as the
        bare label at others — `kept_as_text`, its own note for the second.
        The label is the question id, so the edge survives; what is lost is
        the mark that it was a chip, and it is found back by the place it
        stands in."""
        for q in self.graph.questions:
            with self.subTest(question=q.id):
                body = render.body(self.graph, q.id)
                bare = render.CHIP_TOKEN.sub(
                    lambda m: (m.group(0)[:-len(m.group(1))
                                          - len("<?claude block ?>")]
                               + self.ids[m.group(1)])
                    if m.group(1) in self.ids else m.group(0), body)
                self.assertNotEqual(bare, body)
                self.assertEqual(read.parse_tab(bare, self.ids),
                                 read.parse_tab(body, self.ids))

    def test_a_word_of_prose_that_is_a_question_id_is_not_eaten(self):
        """The removal is checked by running the insertion forward over what
        it leaves, so a thesis that uses a target's name as an ordinary word
        keeps it — which the live notebook does, on several tabs at once."""
        graph = load("valid")
        thesis = graph.get("ti-esti").theses[0]
        thesis.text = ("A relationship that continues. The canon is the record "
                       "between them, and canon is what both can point at.")
        thesis.terms[0].anchors = ["A relationship that continues"]
        ids = chip_ids(graph)
        body = render.body(graph, "ti-esti")
        bare = render.CHIP_TOKEN.sub(
            lambda m: (m.group(0)[:-len(m.group(1)) - len("<?claude block ?>")]
                       + ids[m.group(1)]) if m.group(1) in ids else m.group(0),
            body)
        self.assertEqual(read.parse_tab(bare, ids)["theses"][0]["text"],
                         thesis.text)

    def test_a_bulleted_thesis_keeps_its_bullets_and_its_citations(self):
        """Citations were told from prose by shape — a block opening `**` or
        `- ` — which swallowed every bolded lead and every list a thesis
        writes. On the root answer that is most of the answer. They close the
        subsection, so the split is positional."""
        graph = load("valid")
        thesis = graph.get("ti-esti").theses[0]
        thesis.text = ("**What it requires of me**\n\n"
                       "- **Report truthfully.** Say what I ran.\n"
                       "- The record kept between them is the only thing both "
                       "can point at.")
        parsed = read.parse_tab(render.body(graph, "ti-esti"), self.ids)
        self.assertEqual(parsed["theses"][0]["text"], thesis.text)
        self.assertEqual([t["to"] for t in parsed["theses"][0]["traditions"]],
                         ["plato"])

    def test_an_anchor_keeps_the_emphasis_that_makes_it_verbatim(self):
        """The anchor line is the anchor in italics, so exactly one layer comes
        off. `strip("*")` took the anchor's own bold with it, and an anchor
        without it is no longer a substring of the thesis."""
        graph = load("valid")
        thesis = graph.get("ti-esti").theses[0]
        anchor = "**Be predictable.** Keep the same conventions."
        thesis.text = "A relationship. " + anchor
        thesis.terms[0].anchors = [anchor]
        parsed = read.parse_tab(render.body(graph, "ti-esti"), self.ids)
        self.assertEqual(parsed["theses"][0]["terms"][0]["anchors"], [anchor])

    def test_a_mention_does_not_become_an_anchor_of_the_last_term(self):
        """`↗` follows `▸` in the same section. A subsection that ran to the
        next heading of its own marker read every mention's anchor back as one
        more anchor of the last term — a term edge the graph never had, and on
        a mention put there to break a cycle, the cycle back."""
        graph = load("valid")
        thesis = graph.get("ti-esti").theses[0]
        thesis.mentions.append(model.Mention(
            title="Where assent is recorded", to="party",
            anchors=["Authority to act follows how settled the question is"]))
        parsed = read.parse_tab(render.body(graph, "ti-esti"), self.ids)
        self.assertEqual(parsed["theses"][0]["terms"][-1]["anchors"],
                         thesis.terms[-1].anchors)
        self.assertEqual([m["anchors"] for m in parsed["theses"][0]["mentions"]],
                         [thesis.mentions[0].anchors])

    def test_a_suspended_clause_comes_back_with_what_it_waits_on(self):
        graph = load("valid")
        term = graph.get("ti-esti").theses[0].terms[0]
        term.suspended = "whether the other side would say it unprompted"
        parsed = read.parse_tab(render.body(graph, "ti-esti"), self.ids)
        self.assertEqual(parsed["theses"][0]["terms"][0]["suspended"],
                         "whether the other side would say it unprompted")

    def test_a_cue_comes_back_on_its_term_and_on_no_other(self):
        """The situation the clause governs, a labelled block after the
        anchors: read as the term's cue, and never as an anchor or as
        what the clause waits on."""
        parsed = self.parse("canon")
        term = parsed["theses"][0]["terms"][0]
        self.assertEqual(term["cue"], "an act is proposed on an entry nobody with "
                                      "standing has marked")
        self.assertEqual(term["anchors"], ["Authority to act on an unassented entry is "
                                           "held down, never removed."])
        self.assertNotIn("suspended", term)
        self.assertTrue(all("cue" not in t for t in self.parse("ti-esti")["theses"][0]["terms"]))

    def test_a_cue_stands_beside_a_suspension_and_a_deadlock(self):
        graph = load("valid")
        term = graph.get("party").theses[0].terms[0]
        term.cue = "one side means to act while the other has not spoken"
        parsed = read.parse_tab(render.body(graph, "party"), self.ids)
        got = parsed["theses"][0]["terms"][0]
        self.assertEqual((got["cue"], got["deadlock"]["counter"]),
                         (term.cue, term.deadlock.counter))

    def test_an_answer_s_state_comes_back_off_its_own_line(self):
        """Its own, and not the question's: the root is landed and its answer
        is in thread."""
        parsed = self.parse("ti-esti")
        self.assertEqual((parsed["state"], parsed["theses"][0]["state"]),
                         ("landed", "in thread"))
        self.assertNotIn("standing", parsed)
        self.assertNotIn("standing", parsed["theses"][0])

    def test_a_note_is_not_read_as_a_deadlock(self):
        """A note closes its section, so it lands after the last subsection.
        Taken into that subsection it becomes the human's dissent from a clause
        he never dissented from."""
        graph = load("valid")
        graph.get("ti-esti").notes.append(
            model.Note(section="terms", body="Ask Plato about this one."))
        parsed = read.parse_tab(render.body(graph, "ti-esti"), self.ids)
        self.assertEqual([t.get("deadlock") for t in parsed["theses"][0]["terms"]],
                         [None] * len(parsed["theses"][0]["terms"]))
        self.assertIn({"section": "terms", "body": "Ask Plato about this one."},
                      parsed["notes"])

    def test_a_deadlock_comes_back_in_both_its_parts(self):
        graph = load("valid")
        term = graph.get("canon").theses[0].terms[0]
        term.deadlock = model.Deadlock(
            counter="the record is the transcript and not a projection of it",
            attenuation="nothing is written from this clause without asking")
        parsed = read.parse_tab(render.body(graph, "canon"), self.ids)
        self.assertEqual(parsed["theses"][0]["terms"][0]["deadlock"],
                         {"counter": term.deadlock.counter,
                          "attenuation": term.deadlock.attenuation})

    def test_a_divergence_keeps_its_counter_clause_apart_from_its_note(self):
        """The counter-clause rides in the citation item after its marker, so
        the two come back as the two fields they were written as."""
        graph = load("valid")
        edge = graph.get("ti-esti").theses[0].traditions[0]
        edge.relation = "divergence"
        edge.counter = "the opening move may be asked of anything at all"
        parsed = read.parse_tab(render.body(graph, "ti-esti"), self.ids)
        self.assertEqual(parsed["theses"][0]["traditions"][0],
                         {"to": "plato", "relation": "divergence",
                          "note": edge.note, "counter": edge.counter})

    def test_the_export_s_backslashes_come_off(self):
        """The document escapes what markdown would otherwise read as a
        marker, so a session id comes back `session\\_01Jjv…`. The backslash is
        the exporter's, not the page's."""
        graph = load("valid")
        graph.get("canon").hinge.thesis = "harness: session_01JjvCcM5QM8JTTCsN2PEKCD"
        exported = render.body(graph, "canon").replace(
            "session_01Jjv", "session\\_01Jjv")
        parsed = read.parse_tab(exported, self.ids)
        self.assertEqual(parsed["hinge"]["thesis"],
                         "harness: session_01JjvCcM5QM8JTTCsN2PEKCD")

    def test_the_page_s_backslashes_stay(self):
        """A graph text spells a literal star `\\*`, as markdown does. The
        renderer writes it so and the page speller spells the page's star so;
        taken off here, the next render wrote the star as a mark."""
        graph = load("valid")
        canon = graph.get("canon")
        canon.hinge.thesis = "a literal \\* star, a \\[bracket\\] and a back\\\\slash"
        canon.definitions[0].body = "The mark \\* by which the one with standing binds."
        parsed = read.parse_tab(render.body(graph, "canon"), self.ids)
        self.assertEqual(parsed["hinge"]["thesis"], canon.hinge.thesis)
        self.assertEqual(parsed["definitions"][0]["body"], canon.definitions[0].body)

    def test_an_exported_chip_leaves_no_label_in_a_citation(self):
        """A chip carries an edge, not a word. Flattened to `[Plato](file/…)`
        on export and read back as its label, the tradition's name ended up
        inside the note that cites it."""
        body = render.body(self.graph, "ti-esti")
        exported = body.replace("<?claude block m_plato?>",
                                "[Plato](file/0c4d2d88-79ab)")
        parsed = read.parse_tab(exported, self.ids)
        thesis = parsed["theses"][0]
        self.assertEqual(parsed["definitions"][0]["tradition"],
                         {"to": "plato", "note": ""})
        self.assertEqual([t["note"] for t in thesis["traditions"]],
                         ["the opening move is asked of what the answerer "
                          "is already doing"])

    def test_a_shadow_comes_back_as_the_question_it_points_at(self):
        """A shadow is its own block after the body and after any borrowing,
        so neither is read as the other — in the token spelling or the
        exported one."""
        graph = load("valid")
        word = graph.get("ti-esti").definitions[0]
        word.question = "canon"
        body = render.body(graph, "ti-esti")
        for page in (body, body.replace("↗ <?claude block m_canon?>",
                                        "↗ [canon](file/tab-02)")):
            parsed = read.parse_tab(page, self.ids)["definitions"][0]
            self.assertEqual(parsed["question"], "canon")
            self.assertEqual(parsed["tradition"]["to"], "plato")
            self.assertEqual(parsed["body"], word.body)

    def test_the_answerer_comes_back_off_the_question_line(self):
        self.assertEqual(self.parse("attenuation")["answerer"], "principal")
        self.assertNotIn("answerer", self.parse("plato"))

    def test_the_cycle_note_is_derived_and_not_read_back(self):
        graph = load("valid")
        graph.get("canon").theses[0].mentions.append(model.Mention(
            title="What the entry answers", to="ti-esti",
            anchors=["An entry is a file in the repository, not a message in a thread."]))
        body = render.body(graph, "canon")
        self.assertIn(render.CYCLE_NOTE, body)
        parsed = read.parse_tab(body, self.ids)["theses"][0]["mentions"]
        self.assertEqual(parsed, [{"title": "What the entry answers", "to": "ti-esti",
                                   "anchors": ["An entry is a file in the repository, "
                                               "not a message in a thread."]}])

    def test_the_discharge_clause_is_the_renderer_s_and_comes_back_off(self):
        """It is read off the answer, so it is not stored and not read back;
        the note after it is the writer's and is."""
        graph = load("valid")
        _, app = list(graph.get("attenuation").applications())[0]
        app.note = "the gate is a script (for now)"
        body = render.body(graph, "attenuation")
        self.assertIn("(while the principal answers this question)", body)
        parsed = read.parse_tab(body, self.ids)
        got = parsed["theses"][0]["applications"][0]
        self.assertEqual((got["standing"], got["note"]),
                         ("postulate", "the gate is a script (for now)"))

    def test_a_link_out_of_the_document_is_content(self):
        """A hinge names the commit it was answered against; that link is the
        principal's own words and is read back with them."""
        graph = load("valid")
        commit = "[dba4d22](https://github.com/natb1/CanonDB/commit/dba4d22)"
        graph.get("canon").hinge.thesis += " · canon: " + commit
        parsed = read.parse_tab(render.body(graph, "canon"), self.ids)
        self.assertIn(commit, parsed["hinge"]["thesis"])



class BareLabelTest(unittest.TestCase):
    """The page spells a chip as its bare label, so the reader finds the label
    where the renderer put a chip — at the end of the line, alone or as the
    tail of a crumb — and nowhere else."""
    LABELS = {"plato", "gorgias", "canon", "plato dialogues"}

    def test_every_step_of_a_crumb_is_read(self):
        line = "the opening move is asked. plato › gorgias"
        at, found = read._label_run(line, self.LABELS)
        self.assertEqual(found, ["plato", "gorgias"])
        self.assertEqual(line[:at], "the opening move is asked.")
        self.assertEqual(read.strip_chips(line, self.LABELS), "the opening move is asked.")

    def test_a_label_with_a_space_in_it_is_one_label(self):
        at, found = read._label_run("already doing. plato dialogues", self.LABELS)
        self.assertEqual(found, ["plato dialogues"])
        self.assertEqual(at, len("already doing."))

    def test_a_trailing_space_does_not_hide_the_label(self):
        self.assertEqual(read._label_run("already doing. canon ", self.LABELS)[1], ["canon"])

    def test_a_word_of_prose_that_is_an_id_is_prose(self):
        self.assertIsNone(read._label_run("the canon is settled", self.LABELS))
        self.assertIsNone(read._label_run("as the canon.", self.LABELS))


class RefusedShapeTest(unittest.TestCase):
    """What the reader cannot carry back it says, rather than dropping."""

    def setUp(self):
        self.graph = load("valid")
        self.ids = chip_ids(self.graph)
        self.body = render.body(self.graph, "ti-esti")
        self.title = self.graph.get("ti-esti").theses[0].title

    def test_an_application_under_no_answer_is_refused(self):
        self.assertIn("· ◆ %s ·" % self.title, self.body)
        with self.assertRaises(read.ParseError):
            read.parse_tab(self.body.replace("· ◆ %s ·" % self.title, "· ◆ Nope ·"), self.ids)

    def test_two_answers_at_one_headline_are_refused(self):
        heading = "### ◆ %s" % self.title
        doubled = self.body.replace(
            heading, heading + "\n\nassent: none · held · provenance: thesis hinge"
                               "\n\nSaid again.\n\n" + heading, 1)
        with self.assertRaises(read.ParseError):
            read.parse_tab(doubled, self.ids)

    def test_an_extra_blank_line_parts_no_section(self):
        self.assertIn("\n\n## Thesis", self.body)
        self.assertEqual(read.parse_tab(self.body.replace("\n\n## Thesis", "\n\n \n\n## Thesis"),
                                        self.ids),
                         read.parse_tab(self.body, self.ids))

    def test_a_section_the_renderer_does_not_write_is_refused(self):
        with self.assertRaises(read.ParseError):
            read.parse_tab(self.body.rstrip("\n") + "\n\n## Another\n\nLost.\n", self.ids)

    def test_a_heading_the_renderer_does_not_write_is_refused(self):
        parts = self.body.split("\n\n## ")
        parts[1] = parts[1].rstrip("\n") + "\n\n### A sub-heading\n\nLost."
        with self.assertRaises(read.ParseError):
            read.parse_tab("\n\n## ".join(parts), self.ids)

    def test_the_renderer_s_own_state_chips_are_refused(self):
        self.graph.state_enum = "000e742f-9e41"
        with self.assertRaises(read.ParseError):
            read.parse_tab(render.body(self.graph, "ti-esti"), self.ids)

    def test_a_support_s_note_keeps_its_own_words(self):
        edge = next(e for t in self.graph.get("ti-esti").theses for e in t.traditions)
        self.assertEqual(edge.relation, "support")
        edge.note = "he asks first. Instead: of lecturing"
        parsed = read.parse_tab(render.body(self.graph, "ti-esti"), self.ids)
        trad = parsed["theses"][0]["traditions"][0]
        self.assertEqual((trad["note"], trad.get("counter", "")), (edge.note, ""))


class HingePartsTest(unittest.TestCase):
    """Each part of the hinge reads back as the part its heading names."""

    def test_the_end_and_the_method_read_back_as_their_own_parts(self):
        graph = load("valid")
        root = graph.get("ti-esti")
        parsed = read.parse_tab(render.body(graph, "ti-esti"), chip_ids(graph))
        self.assertEqual(parsed["hinge"], {
            "question": root.hinge.question, "end": root.hinge.end,
            "method": root.hinge.method, "thesis": root.hinge.thesis,
            "cue": root.hinge.cue})

    def test_the_end_s_cue_comes_back_apart_from_the_end(self):
        """The cue stands right after the end's words, before the method's
        heading, as a labelled block; it is read as the cue and never
        folded into the end's text."""
        graph = load("valid")
        root = graph.get("ti-esti")
        page = render.body(graph, "ti-esti")
        self.assertIn("%s\n\ncue: %s\n\n### %s" % (root.hinge.end, root.hinge.cue,
                                                   render.HINGE_METHOD), page)
        parsed = read.parse_tab(page, chip_ids(graph))
        self.assertEqual(parsed["hinge"]["end"], root.hinge.end)
        self.assertEqual(parsed["hinge"]["cue"], root.hinge.cue)
        root.hinge.cue = ""
        parsed = read.parse_tab(render.body(graph, "ti-esti"), chip_ids(graph))
        self.assertNotIn("cue", parsed["hinge"])

    def test_a_cue_under_an_end_of_two_paragraphs_is_still_apart(self):
        graph = load("valid")
        root = graph.get("ti-esti")
        root.hinge.end += "\n\nand that each can say so in the record."
        parsed = read.parse_tab(render.body(graph, "ti-esti"), chip_ids(graph))
        self.assertEqual(parsed["hinge"]["end"], root.hinge.end)
        self.assertEqual(parsed["hinge"]["cue"], root.hinge.cue)

    def test_a_cue_with_no_end_still_reaches_the_page_and_comes_back(self):
        graph = load("valid")
        root = graph.get("ti-esti")
        root.hinge.end = ""
        parsed = read.parse_tab(render.body(graph, "ti-esti"), chip_ids(graph))
        self.assertEqual(parsed["hinge"]["cue"], root.hinge.cue)
        self.assertEqual(parsed["hinge"].get("end", ""), "")

    def test_a_cue_given_twice_under_the_end_is_refused(self):
        """The second would replace the first, whose words would be lost."""
        graph = load("valid")
        page = render.body(graph, "ti-esti")
        at = page.index("### " + render.HINGE_METHOD)
        edited = page[:at] + "cue: a second situation, over the first\n\n" + page[at:]
        with self.assertRaises(read.ParseError) as caught:
            read.parse_tab(edited, chip_ids(graph))
        self.assertIn("cue is given twice", str(caught.exception))

    def test_a_hinge_without_them_reads_back_without_them(self):
        graph = load("valid")
        parsed = read.parse_tab(render.body(graph, "canon"), chip_ids(graph))
        self.assertEqual(sorted(parsed["hinge"]), ["question", "thesis"])

    def test_a_hinge_heading_naming_no_part_is_refused(self):
        """A part under a heading the renderer does not write would read
        back under another part's name — the end as the provenance, which the
        real provenance then overwrote — or not at all; it is refused like
        every other heading the grammar does not hold."""
        graph = load("valid")
        page = render.body(graph, "ti-esti")
        for heading in ("End: what the asking is for", "ends: what the asking is for",
                        "end what the asking is for"):
            edited = page.replace(render.HINGE_END, "%s %s" % (render.GLYPHS["hinge"], heading))
            with self.subTest(heading=heading), self.assertRaises(read.ParseError) as caught:
                read.parse_tab(edited, chip_ids(graph))
            self.assertIn("hinge heading", str(caught.exception))


    def test_a_hinge_part_given_twice_is_refused(self):
        """The second would replace the first, and the first's words would be
        gone from the graph and, at the next body write, from the page."""
        graph = load("valid")
        page = render.body(graph, "ti-esti")
        at = page.index("### " + render.HINGE_METHOD)
        edited = page[:at] + "### %s\n\nA second end.\n\n" % render.HINGE_END + page[at:]
        with self.assertRaises(read.ParseError) as caught:
            read.parse_tab(edited, chip_ids(graph))
        self.assertIn("given twice", str(caught.exception))

if __name__ == "__main__":
    unittest.main()


class CaseTest(unittest.TestCase):
    """A case comes back whole off its labelled lines, and a line under a
    case the renderer does not write is refused rather than lost."""

    def setUp(self):
        self.graph = load("valid")
        self.ids = chip_ids(self.graph)
        self.graph.get("canon").cases = [model.Case(
            name="The vote taken on the day",
            situation="a side is asked to act on an entry it did not mark",
            verdict="it waits", reason="nothing stands on an unmarked entry",
            clause="Authority held down")]

    def test_a_case_round_trips(self):
        parsed = read.parse_tab(render.body(self.graph, "canon"), self.ids)
        self.assertEqual(parsed["cases"], [{
            "name": "The vote taken on the day",
            "situation": "a side is asked to act on an entry it did not mark",
            "verdict": "it waits", "reason": "nothing stands on an unmarked entry",
            "clause": "Authority held down"}])
        self.assertNotIn("cases", read.parse_tab(render.body(self.graph, "ti-esti"),
                                                 self.ids))

    def test_a_note_on_the_section_is_a_note_and_not_a_line(self):
        self.graph.get("canon").notes.append(model.Note(section="cases", body="One more owed."))
        parsed = read.parse_tab(render.body(self.graph, "canon"), self.ids)
        self.assertEqual(len(parsed["cases"]), 1)
        self.assertIn({"section": "cases", "body": "One more owed."}, parsed["notes"])

    def test_a_line_the_renderer_does_not_write_is_refused(self):
        page = render.body(self.graph, "canon").replace(
            "verdict: it waits", "verdict: it waits\n\nIt waited last time too.")
        with self.assertRaises(read.ParseError) as caught:
            read.parse_tab(page, self.ids)
        self.assertIn("under the case", str(caught.exception))
