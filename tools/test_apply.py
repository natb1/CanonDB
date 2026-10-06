"""The operations that put a rendered tab into the document."""

import re
import unittest

import test_render  # the fixture loader and its graphs
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
        ops = apply.body_ops(graph, "canon", blocks)
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
                             apply.parse_outline(outline_of(graph, "ti-esti")))
        self.assertEqual(ops[0]["with"]["blocks"],
                         render.links(graph, "ti-esti")["blocks"])

    def test_an_empty_outline_is_refused(self):
        graph = load("valid")
        with self.assertRaises(apply.Unresolved):
            apply.body_ops(graph, "canon", [])

    def test_an_outline_of_headings_alone_is_refused(self):
        """A reduced outline is kept for resolving link targets. Replacing only
        the blocks it names would leave the prose of the old tab behind."""
        graph = load("valid")
        whole = apply.parse_outline(outline_of(graph, "canon"))
        with self.assertRaises(apply.Unresolved):
            apply.body_ops(graph, "canon", [b for b in whole if b.heading])

    def test_an_outline_that_folds_blocks_is_refused(self):
        """Replacing only the blocks a `sinceRev` read shows would leave the
        folded ones on the page beside the fresh body."""
        graph = load("valid")
        whole = apply.parse_outline(outline_of(graph, "canon"))
        folded = whole[:2] + [apply.Block("", "gap", 0, "")] + whole[4:]
        with self.assertRaises(apply.Unresolved) as caught:
            apply.body_ops(graph, "canon", folded)
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
        href = apply._resolve(self.graph, "#%s.▸ The record" % q.tab, by_tab,
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
        self.assertIsNone(apply._resolve(graph, "#%s.▸ %s" % (q.tab, first.title), by_tab,
                                         graph.artifact, q.tab))


if __name__ == "__main__":
    unittest.main()
