"""The operations that put a rendered tab into the document."""

import re
import unittest

import test_render  # the fixture loader, its graphs, and a party's works
import test_verify  # the page as the document would export one
from hypo import apply, model, render, text, verify

load = test_render.load
page_of = test_verify.page_of


def outline_of(graph, qid, session="mq2x81a0kfd"):
    """An outline as the document would print one for this tab.

    Built from the rendered body rather than written out, so the fixture cannot
    drift from the renderer: block per top-level chunk, headings marked with
    their level and their chip left as the processing instruction it is.
    """
    parts = []
    for n, chunk in enumerate(render.body(graph, qid).split("\n\n")):
        chunk = chunk.strip()
        if not chunk:
            continue
        bid = "%s.%d" % (session, n) if not parts else ".%d" % n
        level = len(re.match(r"#*", chunk).group(0))
        words = chunk[level:].strip() if level else chunk
        parts.append("<paragraph id='%s' h='%08x'%s>%s</paragraph>"
                     % (bid, n, " heading='%d'" % level if level else "", words))
    return "<doc rev='1'>%s</doc>" % "".join(parts)


def outlines(graph, session="mq2x81a0kfd"):
    return {q.tab: apply.parse_outline(outline_of(graph, q.id, session))
            for q in graph.questions}


class OutlineTest(unittest.TestCase):
    def test_a_short_id_takes_the_prefix_of_the_last_full_one(self):
        blocks = apply.parse_outline(
            "<doc><paragraph id='abc.0'>one</paragraph>"
            "<paragraph id='.7'>two</paragraph></doc>")
        self.assertEqual([b.id for b in blocks], ["abc.0", "abc.7"])

    def test_a_block_after_a_nested_full_id_takes_that_ids_prefix(self):
        """A read prints a full id on whatever carries one first, a run of text
        inside a block included, and abbreviates every id after it: the block
        after a nested full id is short under that id's prefix, not its own
        block's. Both parsers read it so."""
        body = ("<paragraph id='abc.1'><text id='.2'>one </text><text id='xyz.3'>two</text></paragraph>"
                "<paragraph id='.4'>three</paragraph>")
        self.assertEqual([b.id for b in apply.parse_outline("<doc>%s</doc>" % body)], ["abc.1", "xyz.4"])
        self.assertEqual([b.id for b in apply._scan(body)], ["abc.1", "xyz.4"])

    def test_a_full_id_inside_a_wrapper_without_one_carries_too(self):
        """A wrapper the read prints with no id of its own still holds ids
        under it, and the prefix carries from those as from any other."""
        body = ("<paragraph id='abc.1'>one</paragraph>"
                "<list kind='bullet'><listItem id='xyz.2'><paragraph id='.3'>x</paragraph></listItem></list>"
                "<paragraph id='.4'>three</paragraph>")
        self.assertEqual([b.id for b in apply.parse_outline("<doc>%s</doc>" % body)], ["abc.1", "xyz.4"])
        self.assertEqual([b.id for b in apply._scan(body)], ["abc.1", "xyz.4"])

    def test_the_scan_takes_an_id_off_a_tag_and_never_off_the_words(self):
        """The fallback reads the outline's tags: ``id='…'`` standing in a
        block's words is words, and an attribute whose name only ends in
        ``id`` is not one. The bare ``&`` is what sends the outline to it."""
        words = ("<paragraph id='abc.1'>say id='zzz.9' here &amp; now &</paragraph>"
                 "<paragraph id='.3'>two</paragraph>")
        self.assertEqual([b.id for b in apply.parse_outline("<doc>%s</doc>" % words)], ["abc.1", "abc.3"])
        nested = ("<paragraph id='abc.1'><text data-id='xyz.3'>two</text></paragraph>"
                  "<paragraph id='.4'>three</paragraph>")
        self.assertEqual([b.id for b in apply._scan(nested)], ["abc.1", "abc.4"])

    def test_a_heading_keeps_its_words_and_drops_its_chip(self):
        """A target names the words a heading opens with; the chip that closes
        it is a token before the write and a block id after it."""
        blocks = apply.parse_outline(
            "<doc><paragraph id='a.1' heading='3'>▸ A term "
            "<?claude block m_canon?></paragraph></doc>")
        self.assertEqual([(b.heading, b.text) for b in blocks], [(3, "▸ A term")])

    def test_a_gap_is_kept_as_the_fold_it_is(self):
        """A `sinceRev` read folds the runs that did not change into a gap. It
        names no block, so it is not one; but an outline holding one is not
        the whole tab, and the body write has to be able to see that."""
        blocks = apply.parse_outline(
            "<doc><paragraph id='a.0'>one</paragraph><gap blocks='3'/>"
            "<paragraph id='.5'>two</paragraph></doc>")
        self.assertEqual([(b.id, b.kind) for b in blocks],
                         [("a.0", "paragraph"), ("", "gap"), ("a.5", "paragraph")])


class HeadingTest(unittest.TestCase):
    """Which block a target's heading is, when the outline will not say."""

    def setUp(self):
        self.graph = load("valid")
        self.tab = self.graph.get("ti-esti").tab
        self.blocks = apply.parse_outline(outline_of(self.graph, "ti-esti"))

    def test_every_rendered_heading_is_paired_with_a_block(self):
        found = apply.headings(self.graph, self.tab, self.blocks)
        self.assertEqual(sorted(found),
                         sorted(apply.rendered_headings(
                             render.body(self.graph, "ti-esti"))))

    def test_an_elided_heading_is_paired_by_position(self):
        """An outline stops printing a block's words after a few characters, so
        a heading cannot be found by the text a target names."""
        short = [b._replace(text=b.text[:8] + "…") if b.heading else b
                 for b in self.blocks]
        self.assertEqual(apply.headings(self.graph, self.tab, short),
                         apply.headings(self.graph, self.tab, self.blocks))

    def test_a_page_that_is_not_this_render_pairs_nothing(self):
        """The elided text is a check on the pairing, not the means of it: if
        the two have drifted, no id here can be trusted."""
        drifted = [b._replace(text="something else") if b.heading else b
                   for b in self.blocks]
        self.assertEqual(apply.headings(self.graph, self.tab, drifted), {})

    def test_a_heading_edited_in_place_pairs_by_its_pieces(self):
        """A block edited in place across sessions comes back as one text run
        per edit, each elided on its own: ``◆ Whe`` + ``re a calen…`` +
        ``; a writte…``. The pieces are checked in order against the render,
        and what the ellipses hide is not."""
        pieced = [b._replace(text=b.text[:5] + b.text[5:14] + "…" + b.text[20:27] + "…")
                  if b.heading else b for b in self.blocks]
        self.assertEqual(apply.headings(self.graph, self.tab, pieced),
                         apply.headings(self.graph, self.tab, self.blocks))

    def test_a_piece_out_of_order_pairs_nothing(self):
        """The pieces have to follow one another as the words do; a later
        piece found only before an earlier one is another page."""
        words = apply.rendered_headings(render.body(self.graph, "ti-esti"))[0]
        self.assertTrue(apply.spells(words, words[:4] + "…" + words[6:9] + "…"))
        self.assertFalse(apply.spells(words, words[:4] + "…" + "zzzz…"))
        self.assertFalse(apply.spells(words, words[6:9] + "…"))

    def test_a_doctype_is_refused_rather_than_parsed(self):
        with self.assertRaises(apply.Unresolved):
            apply.parse_outline("<doc><!DOCTYPE x><paragraph id='a.1'>x</paragraph></doc>")

    def test_an_outline_the_parser_will_not_take_is_still_read(self):
        blocks = apply.parse_outline(
            "<doc><paragraph id='a.1' heading='2'>A & B</paragraph></doc>")
        self.assertEqual([(b.id, b.heading, b.text) for b in blocks],
                         [("a.1", 2, "A & B")])


class BodyTest(unittest.TestCase):
    def test_one_operation_naming_every_block_the_tab_holds(self):
        graph = load("valid")
        blocks = apply.parse_outline(outline_of(graph, "canon"))
        ops = apply.body_ops(graph, "canon", blocks, 1)
        self.assertEqual(len(ops), 1)
        self.assertEqual(ops[0]["op"], "replace")
        self.assertEqual(ops[0]["target"]["ids"], [b.id for b in blocks])
        self.assertEqual(ops[0]["with"]["as"], "markdown")
        self.assertEqual(ops[0]["with"]["from"]["content"],
                         render.body(graph, "canon"))

    def test_the_chip_map_rides_the_body(self):
        """A chip is a token in the markdown and an entry beside it; sending
        one without the other writes the token as words."""
        graph = load("valid")
        ops = apply.body_ops(graph, "ti-esti",
                             apply.parse_outline(outline_of(graph, "ti-esti")), 1)
        self.assertEqual(ops[0]["with"]["blocks"],
                         render.links(graph, "ti-esti")["blocks"])

    def test_an_empty_outline_is_refused(self):
        graph = load("valid")
        with self.assertRaises(apply.Unresolved):
            apply.body_ops(graph, "canon", [], 1)

    def test_an_outline_of_headings_alone_is_refused(self):
        """A reduced outline is kept for resolving link targets. Replacing only
        the blocks it names would leave the prose of the old tab behind."""
        graph = load("valid")
        whole = apply.parse_outline(outline_of(graph, "canon"))
        with self.assertRaises(apply.Unresolved):
            apply.body_ops(graph, "canon", [b for b in whole if b.heading], 1)

    def test_an_outline_that_folds_blocks_is_refused(self):
        """Replacing only the blocks a `sinceRev` read shows would leave the
        folded ones on the page beside the fresh body."""
        graph = load("valid")
        whole = apply.parse_outline(outline_of(graph, "canon"))
        folded = whole[:2] + [apply.Block("", "gap", 0, "")] + whole[4:]
        with self.assertRaises(apply.Unresolved) as caught:
            apply.body_ops(graph, "canon", folded, 1)
        self.assertIn("fold", caught.exception.missing[0])


class LinkTest(unittest.TestCase):
    def setUp(self):
        self.graph = load("valid")
        self.graph.artifact = "https://claude.ai/code/artifact/abc-123"
        self.by_tab = outlines(self.graph)

    def test_one_format_operation_per_link(self):
        ops = apply.link_ops(self.graph, "ti-esti", self.by_tab, self.graph.artifact)
        self.assertEqual(len(ops), len(render.links(self.graph, "ti-esti")["links"]))
        self.assertEqual({op["op"] for op in ops}, {"format"})

    def test_a_link_on_this_tab_is_a_bare_fragment(self):
        ops = apply.link_ops(self.graph, "ti-esti", self.by_tab, self.graph.artifact)
        hrefs = [op["add"][0]["href"] for op in ops]
        own = [h for h in hrefs if h.startswith("#")]
        self.assertTrue(own)
        for href in own:
            self.assertRegex(href, r"^#[\w.]+$")

    def test_a_link_to_another_tab_carries_the_artifact_and_the_tab(self):
        """A fragment alone would land on this tab; the reader is going
        somewhere else."""
        ops = apply.link_ops(self.graph, "attenuation", self.by_tab,
                             self.graph.artifact)
        away = [op["add"][0]["href"] for op in ops
                if not op["add"][0]["href"].startswith("#")]
        self.assertTrue(away)
        for href in away:
            self.assertTrue(href.startswith(self.graph.artifact + "#"))

    def test_the_target_finds_the_words_and_says_which_run(self):
        ops = apply.link_ops(self.graph, "ti-esti", self.by_tab, self.graph.artifact)
        entries = render.links(self.graph, "ti-esti")["links"]
        self.assertEqual([op["target"] for op in ops],
                         [{"kind": "find", "text": e["find"]["text"],
                           "nth": e["find"]["nth"]} for e in entries])

    def test_a_target_no_outline_accounts_for_refuses(self):
        """A target the caller cannot find is a link that never lands, so it is
        refused rather than sent as an operation that does nothing."""
        with self.assertRaises(apply.Unresolved) as caught:
            apply.link_ops(self.graph, "ti-esti", {}, self.graph.artifact)
        self.assertTrue(caught.exception.missing)

    def test_a_link_that_leaves_the_tab_needs_an_artifact_to_leave_it_by(self):
        """With no artifact the href would be a bare fragment, which the
        document takes as a link on this tab: the wrong page, sent."""
        with self.assertRaises(apply.Unresolved) as caught:
            apply.link_ops(self.graph, "attenuation", self.by_tab, "")
        self.assertTrue(any("artifact" in line for line in caught.exception.missing),
                        caught.exception.missing)

    def test_a_term_whose_title_opens_another_s_resolves_to_its_own_heading(self):
        """`▸ The record` opens `▸ The record between them →` as well, and the
        first heading that merely began with the words was taken for it."""
        q = self.graph.get("ti-esti")
        q.theses[0].text += " The record."
        q.theses[0].terms.append(model.Term(title="The record", to="party",
                                            anchors=["The record."]))
        by_tab = outlines(self.graph)
        found = apply.headings(self.graph, q.tab, by_tab[q.tab])
        href = apply.resolve(self.graph, "#%s.▸ The record" % q.tab, by_tab,
                              self.graph.artifact, q.tab)
        self.assertEqual(href, "#" + found["▸ The record →"])
        self.assertNotEqual(href, "#" + found["▸ The record between them →"])

    def test_wanted_names_this_tab_and_every_tab_it_points_at(self):
        wanted = apply.wanted_tabs(self.graph, "attenuation")
        self.assertIn(self.graph.get("attenuation").tab, wanted)
        self.assertEqual(
            set(wanted),
            {e["target"].lstrip("#").partition(".")[0]
             for e in render.links(self.graph, "attenuation")["links"]}
            | {self.graph.get("attenuation").tab})


class UnlinkTest(unittest.TestCase):
    """Taking off a mark the sidecar no longer asks for."""

    def setUp(self):
        self.graph = load("valid")
        self.qid = "canon"
        self.entries = render.links(self.graph, self.qid)["links"]

    def test_a_page_carrying_exactly_what_is_asked_for_gives_no_operation(self):
        for q in self.graph.questions:
            with self.subTest(question=q.id):
                page = page_of(self.graph, q.id,
                               render.links(self.graph, q.id)["links"])
                self.assertEqual(apply.unlink_ops(self.graph, q.id, page), [])

    def test_a_stray_link_is_taken_off_by_the_words_it_stands_on(self):
        """A definition that has moved to another tab leaves its link behind,
        pointing at a heading that is not there any more."""
        words = "a file in the repository"
        page = page_of(self.graph, self.qid, self.entries).replace(
            words, test_verify.LINK % (words, "zz", 9), 1)
        ops = apply.unlink_ops(self.graph, self.qid, page)
        self.assertEqual(len(ops), 1)
        self.assertEqual(ops[0]["op"], "format")
        self.assertEqual(ops[0]["target"]["text"], words)
        self.assertEqual(ops[0]["remove"], [{"type": "link"}])
        self.assertNotIn("add", ops[0])

    def test_the_run_is_counted_the_way_the_document_counts_it(self):
        """The same rule as a link that is being put on: every literal match
        counts, case does not, and the run named is the one the mark is on."""
        words = "canon"
        page = page_of(self.graph, self.qid, self.entries)
        plain, _ = verify.linked_spans(page)
        runs = text.occurrences(plain, words)
        self.assertGreater(len(runs), 1, "the case this exists for")
        at = runs[-1]
        page = "%s%s%s" % (page[: page.rindex(words)],
                           test_verify.LINK % (words, "zz", 9),
                           page[page.rindex(words) + len(words):])
        ops = apply.unlink_ops(self.graph, self.qid, page)
        self.assertEqual([op["target"]["nth"] for op in ops], [at.nth])

    def test_a_link_the_sidecar_wants_is_left_alone(self):
        """The two are the same page read twice; only the stray comes off."""
        page = page_of(self.graph, self.qid, self.entries)
        stray = "a file in the repository"
        both = page.replace(stray, test_verify.LINK % (stray, "zz", 9), 1)
        self.assertEqual(len(apply.unlink_ops(self.graph, self.qid, both)), 1)
        self.assertEqual(apply.unlink_ops(self.graph, self.qid, page), [])



class HeadingShapeTest(unittest.TestCase):
    def test_a_paragraph_opening_on_a_number_sign_is_not_a_heading(self):
        self.assertEqual(apply.rendered_headings("# Title\n\n#1 on the list is the merge.\n\n## Thesis"),
                         ["Title", "Thesis"])

    def test_a_heading_s_whitespace_is_collapsed_as_the_outline_s_is(self):
        self.assertEqual(apply.rendered_headings("### ▸ The record  between them → <?claude block m_canon?>"),
                         ["▸ The record between them →"])

    def test_two_headings_spelling_one_text_resolve_to_neither(self):
        graph = load("valid")
        q = graph.get("ti-esti")
        thesis = q.theses[0]
        first = thesis.terms[0]
        tail = thesis.text.rstrip(".").rsplit(". ", 1)[-1]
        thesis.terms.append(model.Term(title=first.title, to="party", anchors=[tail]))
        by_tab = outlines(graph)
        found = apply.headings(graph, q.tab, by_tab[q.tab])
        self.assertEqual(found["▸ %s →" % first.title], apply.AMBIGUOUS)
        self.assertIsNone(apply.resolve(graph, "#%s.▸ %s" % (q.tab, first.title), by_tab,
                                         graph.artifact, q.tab))


if __name__ == "__main__":
    unittest.main()


class RevTest(unittest.TestCase):
    def test_the_rev_is_read_off_the_outline(self):
        self.assertEqual(apply.outline_rev("<doc node='n' rev='42' sinceRev='0'></doc>"), 42)
        self.assertIsNone(apply.outline_rev("<outline></outline>"))

    def test_the_body_replace_carries_the_rev_as_its_guard(self):
        """A replace naming every block carries no hash, and the document
        refuses a whole-block operation that names no guard."""
        graph = load("valid")
        outline = apply.parse_outline(outline_of(graph, "canon"))
        self.assertEqual(apply.body_ops(graph, "canon", outline, 7)[0]["ifRev"], 7)
        with self.assertRaises(apply.Unresolved) as caught:
            apply.body_ops(graph, "canon", outline, None)
        self.assertIn("rev", caught.exception.missing[0])


class SectionTest(unittest.TestCase):
    def setUp(self):
        self.graph = load("valid")
        self.graph.artifact = "https://claude.ai/code/artifact/abc-123"
        self.outline = apply.parse_outline(outline_of(self.graph, "canon"))

    def span(self, section):
        start = next(i for i, b in enumerate(self.outline)
                     if b.heading == 2 and b.text.lower() == section)
        end = next((i for i in range(start + 1, len(self.outline))
                    if self.outline[i].heading == 2), len(self.outline))
        return start, end

    def test_one_operation_naming_the_sections_blocks_alone(self):
        ops = apply.section_ops(self.graph, "canon", self.outline, 3, "hinge")
        start, end = self.span("hinge")
        self.assertEqual(len(ops), 1)
        self.assertEqual(ops[0]["target"]["ids"], [b.id for b in self.outline[start:end]])
        self.assertEqual(ops[0]["ifRev"], 3)
        content = ops[0]["with"]["from"]["content"]
        self.assertTrue(content.startswith("## Hinge"))
        self.assertIn(content, render.body(self.graph, "canon"))
        self.assertNotIn("## Glossary", content)
        for key in ops[0]["with"].get("blocks", {}):
            self.assertIn(key, content)

    def test_the_chips_sent_are_the_sections_own(self):
        ops = apply.section_ops(self.graph, "canon", self.outline, 3, "thesis")
        content = ops[0]["with"]["from"]["content"]
        sent = set(ops[0]["with"].get("blocks", {}))
        wanted = set(re.findall(r"<\?claude block ([0-9A-Za-z_]+)\?>", content))
        self.assertEqual(sent, wanted)

    def test_a_section_the_render_lacks_is_refused(self):
        with self.assertRaises(apply.Unresolved) as caught:
            apply.section_ops(self.graph, "canon", self.outline, 3, "cited by")
        self.assertIn("render", caught.exception.missing[0])

    def test_a_section_the_page_lacks_is_opened_after_the_one_before_it(self):
        """The hinge stands last; a page without it takes it after the last
        block of the section before it, heading and all, in one insert."""
        start, _ = self.span("hinge")
        without = [b for i, b in enumerate(self.outline) if i < start]
        ops = apply.section_ops(self.graph, "canon", without, 3, "hinge")
        self.assertEqual(len(ops), 1)
        self.assertEqual(ops[0]["op"], "insert")
        self.assertEqual(ops[0]["side"], "after")
        self.assertEqual(ops[0]["target"], {"kind": "blocks", "ids": [without[-1].id]})
        content = ops[0]["source"]["from"]["content"]
        self.assertTrue(content.startswith("## Hinge"))
        self.assertIn(content, render.body(self.graph, "canon"))


    def test_a_fold_inside_the_section_is_refused(self):
        start, end = self.span("hinge")
        folded = self.outline[:start + 1] + [apply.Block("", "gap", 0, "")] + self.outline[start + 1:]
        with self.assertRaises(apply.Unresolved):
            apply.section_ops(self.graph, "canon", folded, 3, "hinge")

    def test_the_links_of_one_section_are_those_in_it_and_those_into_it(self):
        by_tab = outlines(self.graph)
        every = apply.link_ops(self.graph, "canon", by_tab, self.graph.artifact)
        hinge = apply.link_ops(self.graph, "canon", by_tab, self.graph.artifact, "hinge")
        self.assertTrue(hinge)
        self.assertLess(len(hinge), len(every))
        # the provenance link stands on the answer's metadata line and leads
        # into the hinge, so a write of the hinge retires it
        self.assertTrue(any(op["target"]["text"] == render.PROVENANCE_ANCHOR for op in hinge))
        for op in hinge:
            self.assertIn(op, every)
        with self.assertRaises(apply.Unresolved):
            apply.link_ops(self.graph, "canon", by_tab, self.graph.artifact, "nowhere")


class WorksSectionTest(unittest.TestCase):
    """A party's first work opens its Works section in one insert, after the
    last block of Applications, or of whatever stands before it on the page."""

    def setUp(self):
        self.graph = test_render.with_works(load("valid"))
        self.graph.artifact = "https://claude.ai/code/artifact/abc-123"
        bare = load("valid")  # the page as it stood before the works
        self.outline = apply.parse_outline(outline_of(bare, "plato"))

    def heading(self, name, outline=None):
        return next(i for i, b in enumerate(outline or self.outline)
                    if b.heading == 2 and b.text == name)

    def test_the_section_goes_after_the_last_block_of_the_one_before_it(self):
        self.assertNotIn("Works", [b.text for b in self.outline if b.heading == 2])
        ops = apply.section_ops(self.graph, "plato", self.outline, 3, "works")
        last = self.outline[self.heading("Cited by") - 1]
        self.assertEqual(ops, [{
            "op": "insert", "target": {"kind": "blocks", "ids": [last.id]},
            "side": "after",
            "source": {"as": "markdown", "from": {"kind": "inline", "content": ops[0][
                "source"]["from"]["content"]}}}])
        content = ops[0]["source"]["from"]["content"]
        self.assertTrue(content.startswith("## Works\n\n### ❦ PLATO-EUTH"))
        self.assertNotIn("## Cited by", content)
        self.assertIn(content, render.body(self.graph, "plato"))
        self.assertNotIn("blocks", ops[0]["source"])  # a work carries no chip

    def test_after_applications_where_the_page_has_them(self):
        bare = load("valid")
        for graph in (self.graph, bare):
            graph.get("plato").theses[0].applications.append(model.Application(
                name="a reading", what="a page of notes", link="notes/plato.md",
                standing="postulate"))
        outline = apply.parse_outline(outline_of(bare, "plato"))
        ops = apply.section_ops(self.graph, "plato", outline, 3, "works")
        last = outline[self.heading("Cited by", outline) - 1]
        self.assertEqual(ops[0]["target"]["ids"], [last.id])
        self.assertTrue(any(b.heading == 3 and b.text.startswith("⚙")
                            for b in outline[:self.heading("Cited by", outline)]))

    def test_a_fold_where_it_opens_is_refused(self):
        at = self.heading("Cited by")
        folded = self.outline[:at] + [apply.Block("", "gap", 0, "")] + self.outline[at:]
        with self.assertRaises(apply.Unresolved) as caught:
            apply.section_ops(self.graph, "plato", folded, 3, "works")
        self.assertIn("folds", caught.exception.missing[0])

    def test_a_fold_anywhere_is_refused_since_it_may_hide_the_section(self):
        folded = self.outline[:2] + [apply.Block("", "gap", 0, "")] + self.outline[2:]
        with self.assertRaises(apply.Unresolved):
            apply.section_ops(self.graph, "plato", folded, 3, "works")

    def test_with_no_section_before_it_it_opens_after_the_masthead(self):
        first = self.heading("Thesis")
        masthead = self.outline[:first]
        rest = self.outline[self.heading("Cited by"):]
        ops = apply.section_ops(self.graph, "plato", masthead + rest, 3, "works")
        self.assertEqual(ops[0]["target"]["ids"], [masthead[-1].id])

    def test_once_written_its_links_are_none(self):
        """A work carries no link, and an insert retires none: there is
        nothing for the links call of that write to put back."""
        by_tab = outlines(self.graph)
        self.assertEqual(apply.link_ops(self.graph, "plato", by_tab,
                                        self.graph.artifact, "works"), [])
