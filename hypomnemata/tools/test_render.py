"""The renderer produces the one sanctioned layout, and refuses on an ERROR."""

import os
import unittest

from hypo import model, project, render, spec

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def load(name):
    return model.load(os.path.join(FIXTURES, name + ".json"))


def sections(text):
    return [line[3:] for line in text.splitlines() if line.startswith("## ")]


class ChipKeyTest(unittest.TestCase):
    """The document takes a blocks key of ``[a-z0-9_-]`` and nothing else, so a
    tradition named for its author cannot be its own key."""

    def test_a_capitalised_id_makes_a_legal_key(self):
        self.assertEqual(render.chip_key("Aquinas"), "m_aquinas")
        self.assertEqual(render.chip_key("docs-encoding"), "m_docs_encoding")
        self.assertRegex(render.chip_key("Wittgenstein"), r"^[a-z0-9_-]{1,32}$")

    def test_two_ids_that_differ_only_in_case_are_reported(self):
        graph = load("valid")
        graph.get("plato").id = "Canon"
        findings = spec.run(graph, only=["unique-ids"])
        self.assertTrue(any("chip key" in f.message for f in findings))


class RootLayoutTest(unittest.TestCase):
    def setUp(self):
        self.text = render.render(load("valid"), "ti-esti")
        self.lines = [l for l in self.text.splitlines() if l.strip()]

    def test_opens_with_the_lineage_then_the_id(self):
        """The breadcrumb says where the reader is arriving from and the title
        says where he has arrived, so the path stands above the title and does
        not repeat the question's own name at its end."""
        self.assertEqual(self.lines[0], "⌂ root")
        self.assertEqual(self.lines[1], "# ti-esti")

    def test_the_root_carries_no_incoming_anchors(self):
        self.assertEqual(self.lines[2],
                         "*What does a working relationship that continues require of each side?*")
        self.assertNotIn("›", self.text)

    def test_the_question_line_carries_pressure_and_its_two_projections(self):
        """Pressure is stored and priority is summed from it along the term
        edges, so both stand on the page: the one the principal set, and what
        it comes to once everything blocked behind this question is counted."""
        self.assertEqual(
            self.lines[3],
            "question: landed · root · pressure 27 · priority 58 · load 3 · "
            "requires: nothing")

    def test_a_question_line_names_what_it_waits_on(self):
        """The root waits on nothing: its own promulgation follows its answer
        rather than preceding it, and blocks only the questions above it."""
        self.assertIn("requires: promulgate the root answer",
                      render.body(load("valid"), "canon"))

    def test_section_order(self):
        self.assertEqual(sections(self.text),
                         ["Thesis", "Glossary", "Inbox", "Terms", "Applications", "Hinge"])

    def test_thesis_heading_and_provenance(self):
        self.assertIn("### ◆ Each side owes the other what only it can give.", self.text)
        self.assertIn("assent: assented at the merge of the opening entry · "
                      "provenance: thesis hinge", self.text)

    def test_traditions_are_a_list_per_relation(self):
        self.assertIn("**Support**\n\n- the opening move is asked of what the "
                      "answerer is already doing. <?claude block m_plato?>",
                      self.text)
        self.assertNotIn("**Divergence**", self.text)

    def test_glossary_closes_a_borrowed_sense_with_a_chip(self):
        """A borrowed sense ends with the tradition it was borrowed from, and
        the tradition is a chip: hand-applied was the only way to get one until
        the borrowing became an edge."""
        self.assertIn("### ≡ elenchus\n\nThe examination by which a claim is "
                      "tested against what its holder already grants."
                      "\n\n<?claude block m_plato?>", self.text)

    def test_a_borrowing_note_precedes_its_chip(self):
        graph = load("valid")
        graph.get("ti-esti").theses[0].definitions[0].tradition.note = \
            "the sense the dialogues put it to"
        self.assertIn("\n\nthe sense the dialogues put it to. "
                      "<?claude block m_plato?>", render.body(graph, "ti-esti"))

    def test_the_inbox_table_lists_the_children(self):
        self.assertIn("| question | term | kind | priority | requires |", self.text)
        self.assertIn("| <?claude block m_canon?> | The record between them | "
                      "definitional | 17 | promulgate the root answer |", self.text)
        self.assertIn("| <?claude block m_party?> | Two sides, two debts | case | 14 | "
                      "promulgate the root answer |", self.text)

    def test_cited_by_lists_a_party_cited_only_through_a_borrowed_sense(self):
        """A borrowed sense names a party as surely as a thesis does. Read from
        the thesis edges alone this list was short by exactly the tabs whose
        only citation was a definition."""
        graph = load("valid")
        graph.get("ti-esti").theses[0].traditions = []
        self.assertEqual(
            graph.get("ti-esti").theses[0].definitions[0].tradition.to, "plato")
        text = render.body(graph, "plato")
        self.assertIn("**Support**", text)
        self.assertIn("<?claude block m_ti_esti?>", text)

    def test_cited_by_does_not_depend_on_the_graph_order(self):
        """The rows are gathered by walking the graph, whose order is whatever
        the document's tab order happened to be. Every other projection here is
        total and deterministic; this one was not, so the same graph read from a
        differently ordered document rendered a differently ordered list."""
        graph = load("valid")
        graph.get("canon").theses[0].traditions.append(
            model.TraditionEdge(to="plato", relation="support",
                                note="the same method, put to a second use"))
        first = render.body(graph, "plato")
        self.assertIn("**Support**", first)
        graph.questions.reverse()
        self.assertEqual(render.body(graph, "plato"), first)

    def test_the_inbox_table_is_heaviest_first(self):
        """The section answers what to do next; a table in file order answers
        nothing. valid.json happens to be in priority order already, so the
        sort has to be shown by putting it out of order."""
        graph = load("valid")
        graph.get("canon").pressure = 1
        graph.get("party").pressure = 99
        rows = [l for l in render.body(graph, "ti-esti").splitlines()
                if l.startswith("| <?claude")]
        self.assertIn("m_party", rows[0])
        self.assertIn("m_canon", rows[1])

    def test_the_inbox_item(self):
        self.assertIn("### promulgate the root answer", self.text)
        self.assertIn("promulgate · put the opening answer where both sides can see it · "
                      "instances once, before any descendant is asked · not done", self.text)

    def test_terms_and_applications_and_hinge(self):
        self.assertIn("### ▸ The record between them → <?claude block m_canon?>",
                      self.text)
        self.assertIn("*The record kept between them is the only thing both can point at.*",
                      self.text)
        self.assertIn("### ⚙ the opening entry", self.text)
        # the thesis it comes from is named, so which answer it rests on is
        # on the page and not merely in the graph file
        self.assertIn("the first file both sides pointed at · ◆ Each side owes "
                      "the other what only it can give. · entries/opening.md · "
                      "postulate", self.text)
        self.assertIn("### ⚓ question: what the asking presupposes", self.text)
        self.assertIn("### ⚓ thesis: what the answer was drawn from", self.text)

    def test_blocks_are_separated_by_a_blank_line(self):
        self.assertNotIn("\n\n\n", self.text)
        self.assertTrue(self.text.endswith("\n"))


class DescendantLayoutTest(unittest.TestCase):
    def setUp(self):
        self.graph = load("valid")
        self.text = render.render(self.graph, "attenuation")
        self.lines = [l for l in self.text.splitlines() if l.strip()]

    def test_incoming_anchors_are_a_list_naming_every_parent(self):
        """A question with several parents lists them all — that is how the
        graph stays a graph while the tabs are a tree — and each item ends in a
        chip to the tab whose term section holds it."""
        self.assertEqual(self.lines[2],
                         "- Authority to act on an unassented entry is graded down, "
                         "never removed. <?claude block m_canon?>")
        self.assertEqual(self.lines[3],
                         "- the act that would settle it is graded down until the "
                         "standing side speaks <?claude block m_party?>")

    def test_the_lineage_line_is_the_lineage_alone(self):
        self.assertEqual(self.lines[0],
                         "⌂ <?claude block m_ti_esti?> › <?claude block m_canon?>")
        self.assertNotIn("› attenuation", self.text)

    def test_a_deadlock_is_two_labelled_blocks_under_its_term(self):
        """Dissent falls on the clause it is dissent from, not on the answer
        that clause sits in, and it carries the grading it earns beside it:
        what the principal holds instead, and what the clause may still
        license."""
        text = render.body(self.graph, "party")
        self.assertIn("deadlock: one side holds that the other may act meanwhile; "
                      "the other holds that it may not", text)
        self.assertIn("attenuation: the clause licenses reversible acts only, and "
                      "nothing that cannot be undone", text)
        self.assertNotIn("· deadlock:", text)

    def test_empty_sections_are_omitted(self):
        self.assertEqual(sections(self.text),
                         ["Thesis", "Glossary", "Applications", "Hinge"])

    def test_a_term_deadlock_is_rendered_under_terms(self):
        text = render.render(self.graph, "party")
        self.assertIn("### ▸ Deadlock waits on standing → <?claude block m_attenuation?>",
                      text)
        self.assertIn("one side holds that the other may act meanwhile", text)

    def test_a_tradition_root_takes_the_root_line(self):
        self.assertIn("⌂ root", render.render(self.graph, "plato"))

    def test_a_tradition_says_who_cites_it(self):
        """Its lineage is not this graph's, so nothing leads to it in the tab
        tree and its masthead carries no terms. Without the mirror, a tradition
        tab does not say what it is doing here."""
        text = render.render(self.graph, "plato")
        self.assertIn("## Cited by", text)
        self.assertIn("**Support**\n\n- <?claude block m_ti_esti?>", text)
        self.assertLess(text.index("## Cited by"), text.index("## Hinge"))

    def test_only_a_cited_question_gets_the_mirror(self):
        self.assertNotIn("## Cited by", render.render(self.graph, "canon"))


class MentionTest(unittest.TestCase):
    """A cross-reference points somewhere without raising it."""

    def setUp(self):
        self.graph = load("valid")
        thesis = self.graph.get("canon").theses[0]
        self.anchor = thesis.text.split(".")[0] + "."
        thesis.mentions.append(model.Mention(
            title="Where assent is recorded", to="party", anchors=[self.anchor]))

    def test_it_is_not_an_edge(self):
        """The failure mode worth a test of its own: a mention that leaked
        into the term graph would make its target a child, and a clause that
        leans on a question already asked elsewhere is how a cycle starts."""
        self.assertNotIn("party", project.out_edges(self.graph)["canon"])
        self.assertNotIn("canon", project.in_edges(self.graph)["party"])
        self.assertEqual(project.parents(self.graph)["party"], "ti-esti")
        self.assertEqual(project.load(self.graph, "canon"), 1)
        self.assertEqual(spec.run(self.graph), [])

    def test_it_is_listed_apart_from_the_terms(self):
        text = render.body(self.graph, "canon")
        self.assertIn("### ↗ Where assent is recorded → <?claude block m_party?>",
                      text)
        self.assertIn("*%s*" % self.anchor, text)

    def test_the_thesis_text_carries_its_chip(self):
        self.assertIn("%s <?claude block m_party?>" % self.anchor,
                      render.body(self.graph, "canon"))

    def test_a_mention_going_nowhere_is_reported(self):
        self.graph.get("canon").theses[0].mentions[0].to = "nowhere"
        findings = spec.run(self.graph, only=["term-target"])
        self.assertEqual(findings[0].question, "canon")
        self.assertIn("mention", findings[0].message)


class SurvivesReRenderTest(unittest.TestCase):
    """The renderer replaces a whole tab body, so anything on the page the
    model does not hold is destroyed the next time the tab is written."""

    def setUp(self):
        self.graph = load("valid")

    def test_a_note_is_kept_as_a_blockquote(self):
        self.graph.get("canon").notes.append(model.Note(
            section="thesis", body="Consider asking this one next."))
        text = render.body(self.graph, "canon")
        self.assertIn("> Consider asking this one next.", text)
        self.assertEqual(spec.run(self.graph), [])

    def test_a_note_opens_a_section_that_is_otherwise_empty(self):
        """Or it is written to a heading that never renders, and is lost."""
        self.assertNotIn("## Cited by", render.body(self.graph, "canon"))
        self.graph.get("canon").notes.append(model.Note(
            section="cited by", body="Nothing cites this yet."))
        text = render.body(self.graph, "canon")
        self.assertIn("## Cited by", text)
        self.assertIn("> Nothing cites this yet.", text)

    def test_a_note_on_an_unknown_section_is_reported(self):
        self.graph.get("canon").notes.append(model.Note(
            section="preamble", body="x"))
        findings = spec.run(self.graph, only=["vocabulary"])
        self.assertIn("never", findings[0].message)

    def test_the_state_renders_as_a_dropdown_where_the_doc_has_one(self):
        self.assertIn("question: landed ·", render.body(self.graph, "ti-esti"))
        self.graph.state_enum = "000e742f-9e41"
        self.assertIn("question: <?claude block state?> ·",
                      render.body(self.graph, "ti-esti"))
        self.assertEqual(render.links(self.graph, "ti-esti")["blocks"]["state"],
                         {"type": "dropdown", "enum": "000e742f-9e41", "index": 2})


class RenderAllTest(unittest.TestCase):
    def test_every_tab_in_projection_order(self):
        text = render.render_all(load("valid"))
        marks = [l for l in text.splitlines() if l.startswith("=== ")]
        self.assertEqual(marks, ["=== %s ===" % qid for qid in
                                 project.walk(load("valid"))])
        self.assertEqual(len(marks), 5)


class ChipTest(unittest.TestCase):
    """A reference to a question is written as a mention chip, never as an id."""

    def test_the_key_replaces_every_non_alphanumeric_character(self):
        self.assertEqual(render.chip_key("ti-esti"), "m_ti_esti")
        self.assertEqual(render.chip_key("docs encoding"), "m_docs_encoding")
        self.assertEqual(render.chip("canon"), "<?claude block m_canon?>")

    def test_the_thesis_text_carries_a_chip_after_its_anchor(self):
        self.assertIn("The record kept between them is the only thing both can point "
                      "at. <?claude block m_canon?>", render.body(load("valid"), "ti-esti"))

    def test_a_chip_in_a_list_item_goes_at_the_end_of_the_item(self):
        """A bulleted clause is read as one thing, so a chip dropped after its
        first sentence cuts the item in half — which is what the live notebook
        does on the root answer, eight bullets out of ten."""
        thesis = model.Thesis(
            title="t",
            text=("What it requires of me\n\n"
                  "- **Be predictable.** Keep the same conventions.\n"
                  "- **Report truthfully.** Say what you ran.\n\n"
                  "A closing clause here and then more."),
            terms=[model.Term(title="predictable", to="canon",
                              anchors=["**Be predictable.** Keep the same conventions."]),
                   model.Term(title="closing", to="party",
                              anchors=["A closing clause here"])])
        out = render._anchored_text(thesis)
        self.assertIn("- **Be predictable.** Keep the same conventions. "
                      "<?claude block m_canon?>\n- **Report truthfully.**", out)
        self.assertIn("A closing clause here <?claude block m_party?> and then more.",
                      out)

    def test_placement_is_unchanged_on_a_plain_paragraph(self):
        """The guard on the block-aware placement: a text with no blank line
        and no list marker must come out byte for byte as it did before."""
        thesis = model.Thesis(
            title="t", text="One sentence. A clause here. And a third.",
            terms=[model.Term(title="c", to="canon", anchors=["A clause here."])])
        self.assertEqual(render._anchored_text(thesis),
                         "One sentence. A clause here. <?claude block m_canon?> "
                         "And a third.")

    def test_a_chip_follows_every_occurrence_of_a_repeated_anchor(self):
        thesis = model.Thesis(
            title="t", text="Here it stands. Here it stands. And then the rest.",
            terms=[model.Term(title="twice", to="canon", anchors=["Here it stands."])])
        self.assertEqual(
            render._anchored_text(thesis),
            "Here it stands. <?claude block m_canon?> Here it stands. "
            "<?claude block m_canon?> And then the rest.")

    def test_an_inserted_chip_is_not_itself_scanned(self):
        thesis = model.Thesis(
            title="t", text="block m_canon is what it is.",
            terms=[model.Term(title="short", to="canon", anchors=["block m_canon"])])
        self.assertEqual(
            render._anchored_text(thesis).count("<?claude block m_canon?>"), 1)

    def test_no_bare_id_is_left_where_a_chip_belongs(self):
        text = render.body(load("valid"), "attenuation")
        self.assertNotIn("› canon", text)
        self.assertIn("› <?claude block m_canon?>", text)


class LinksTest(unittest.TestCase):
    def setUp(self):
        self.sidecar = render.links(load("valid"), "ti-esti")

    def test_the_sidecar_names_the_tab(self):
        self.assertEqual(self.sidecar["question"], "ti-esti")
        self.assertEqual(self.sidecar["tab"], "tab-01")

    def test_one_entry_per_anchor_pointing_at_its_own_term_section(self):
        terms = [l for l in self.sidecar["links"] if l["kind"] == "term"]
        self.assertEqual(len(terms), 2)
        first = terms[0]
        self.assertEqual(first["to"], "canon")
        # tab-01, not canon's tab-02: the term section is written on the tab
        # whose clause raised the question, and the chip does the navigating
        self.assertEqual(first["target"], "#tab-01.▸ The record between them")
        self.assertIn(first["anchor"],
                      load("valid").get("ti-esti").theses[0].text)

    def test_definitions_carry_their_heading(self):
        defs = [l for l in self.sidecar["links"] if l["kind"] == "definition"]
        self.assertEqual(defs[0]["word"], "elenchus")
        self.assertEqual(defs[0]["heading"], "≡ elenchus")
        self.assertEqual(defs[0]["target"], "#tab-01.≡ elenchus")

    def test_the_blocks_map_names_the_tab_of_every_chip(self):
        self.assertEqual(self.sidecar["blocks"], {
            "m_canon": {"type": "mention", "ref": "file/tab-02"},
            "m_party": {"type": "mention", "ref": "file/tab-03"},
            "m_plato": {"type": "mention", "ref": "file/tab-05"}})

    def test_the_breadcrumb_and_every_parent_carry_a_block(self):
        """party is a parent of attenuation but not on its breadcrumb — the
        tree hangs it under canon. Its chip is in the incoming list, so it
        needs an entry or the item ends in an unresolved token."""
        self.assertEqual(sorted(render.links(load("valid"), "attenuation")["blocks"]),
                         ["m_canon", "m_party", "m_ti_esti"])

    def test_a_target_outside_the_graph_carries_no_block(self):
        sidecar = render.links(load("invalid-term-target"), "canon")
        self.assertNotIn("m_nowhere", sidecar["blocks"])

    def test_incoming_terms_make_the_lead_in_clickable(self):
        incoming = [l for l in render.links(load("valid"), "attenuation")["links"]
                    if l["kind"] == "incoming"]
        self.assertEqual([l["from"] for l in incoming], ["canon", "party"])
        self.assertEqual(incoming[0]["term"], "Grading of authority")
        self.assertEqual(incoming[0]["target"], "#tab-02.▸ Grading of authority")
        self.assertEqual(incoming[0]["anchor"],
                         "Authority to act on an unassented entry is graded down, "
                         "never removed.")

    def test_the_root_has_no_incoming_links(self):
        self.assertEqual(
            [l for l in self.sidecar["links"] if l["kind"] == "incoming"], [])

    def test_links_all_covers_every_question(self):
        self.assertEqual(len(render.links_all(load("valid"))), 5)

    def test_every_heading_target_stands_in_the_tab_it_names(self):
        """A target the caller cannot find is a link that never lands. This
        caught a term entry naming its heading on the child's tab, where no
        such heading is written — the term section is on the tab the clause
        was written on."""
        graph = load("valid")
        bodies = {q.tab: render.body(graph, q.id) for q in graph.questions}
        checked = 0
        for sidecar in render.links_all(graph):
            for link in sidecar["links"]:
                tab, _, heading = link["target"].lstrip("#").partition(".")
                if not heading:
                    continue
                with self.subTest(target=link["target"]):
                    self.assertIn(tab, bodies)
                    self.assertIn(heading, bodies[tab])
                    checked += 1
        self.assertTrue(checked)

    def test_an_anchor_is_handed_over_in_its_plain_form(self):
        """The page holds characters and applies emphasis beside them, so a
        search for the marked-up spelling would find nothing."""
        graph = load("valid")
        thesis = graph.get("canon").theses[0]
        term = thesis.terms[0]
        marked = "**%s**" % term.anchors[0]
        thesis.text = thesis.text.replace(term.anchors[0], marked)
        term.anchors[0] = marked
        entry = [l for l in render.links(graph, "canon")["links"]
                 if l["kind"] == "term"][0]
        self.assertNotIn("**", entry["anchor"])
        self.assertEqual(entry["occurrence"], 1)


class RefusalTest(unittest.TestCase):
    def test_an_error_on_the_question_refuses(self):
        graph = load("invalid-anchor-substring")
        with self.assertRaises(render.RefusedError) as caught:
            render.render(graph, "ti-esti")
        self.assertEqual(caught.exception.qid, "ti-esti")
        self.assertTrue(caught.exception.findings)

    def test_an_error_elsewhere_does_not_refuse(self):
        graph = load("invalid-anchor-substring")
        self.assertIn("# plato", render.render(graph, "plato"))

    def test_a_graph_wide_error_refuses_everywhere(self):
        graph = load("invalid-one-root")
        with self.assertRaises(render.RefusedError):
            render.render(graph, "plato")

    def test_a_warning_does_not_refuse(self):
        graph = load("invalid-title-not-identifier")
        self.assertTrue(spec.run(graph))
        self.assertIn("# canon", render.render(graph, "canon"))

    def test_render_all_refuses_on_any_error(self):
        with self.assertRaises(render.RefusedError):
            render.render_all(load("invalid-acyclic"))

    def test_an_unknown_question_is_a_key_error(self):
        with self.assertRaises(KeyError):
            render.body(load("valid"), "absent")


if __name__ == "__main__":
    unittest.main()
