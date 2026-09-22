"""render then read is the identity on everything the markdown carries."""

import os
import unittest

from hypo import model, read, render

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def load(name):
    return model.load(os.path.join(FIXTURES, name + ".json"))


def chip_ids(graph):
    """The map the document's file list supplies: chip key back to question."""
    return {render.chip_key(q.id): q.id for q in graph.questions}


#: what the document holds and the markdown does not, per class. A question's
#: ``party`` is derived from the tab order; a definition's tradition is on the page,
#: as the chip that closes it, so it is compared like everything else.
UNCARRIED = {
    "Question": ("tab", "body", "party", "requires"),
    "Graph": ("path", "questions", "artifact", "mode", "state_enum"),
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
        graph = load(name)
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

    def test_every_invalid_fixture_too(self):
        """They are whole graphs with one mutation, so they exercise shapes the
        valid one does not — a term deadlock, a second thesis, a bad target."""
        for name in sorted(os.listdir(FIXTURES)):
            if name.startswith("invalid-") and name.endswith(".json"):
                self.assert_round_trips(name[:-5])


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

    def test_requires_comes_back_as_the_rendered_title(self):
        """The page shows titles; ids are resolved against the inbox items of
        every tab, which is why assembling a graph needs all of them."""
        self.assertEqual(self.parse("canon")["requires"],
                         ["promulgate the root answer"])

    def test_a_tab_that_is_not_a_tab_is_refused(self):
        with self.assertRaises(read.ParseError):
            read.parse_tab("just some prose", self.ids)

    def test_a_question_that_ends_in_emphasis_comes_back_whole(self):
        """The line is the question in italics; one layer comes off, and not
        the closing marker of a word the question itself emphasises."""
        self.graph.get("canon").question = "What makes an entry *binding*"
        parsed = read.parse_tab(render.body(self.graph, "canon"), self.ids)
        self.assertEqual(parsed["question"], "What makes an entry *binding*")

    def test_an_inbox_line_that_does_not_parse_is_refused(self):
        """Skipped, the item would leave the graph in silence and the page on
        the next body write — a prior overwritten without a word."""
        body = render.body(self.graph, "ti-esti")
        self.assertIn(" · not done · ", body)
        with self.assertRaises(read.ParseError):
            read.parse_tab(body.replace(" · not done · ", " · pending · ", 1),
                           self.ids)

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


if __name__ == "__main__":
    unittest.main()
