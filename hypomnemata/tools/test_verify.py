"""The page against the renderer: the one check that reads what reached the page."""

import re
import unittest

import test_render  # the fixture loader and its graphs
from hypo import model, read, render, verify

load = test_render.load

#: a link as the document exports one it was given: the words, and a fragment.
LINK = "[%s](#%s.%d)"

#: what the graph names when a fixture does not carry one of its own.
ARTIFACT = "https://claude.ai/code/artifact/abc-123"


def href_of(graph, qid, entry, session, n):
    """The target as the caller resolves it.

    A bare fragment leads to the tab it stands on, so it is what a same-tab
    link takes; anywhere else the href names the artifact and the tab in
    front of the block, or the reader lands on the wrong page.
    """
    tab = entry["target"].lstrip("#").partition(".")[0]
    if tab == graph.get(qid).tab:
        return "#%s.%d" % (session, n)
    return "%s#%s.%s.%d" % (graph.artifact or ARTIFACT, tab, session, n)


def _loose(anchor):
    """The anchor as the body spells it: the plain characters, with emphasis
    markers allowed between them.

    An anchor is stored marked up — `**Be predictable.** Keep …` — and handed
    over plain, because the page holds characters and applies emphasis beside
    them. Placing a link on the page has to find the marked form again.
    """
    return re.compile("".join(re.escape(c) + r"[*_`]*" for c in anchor))


def page_of(graph, qid, applied=(), session="mq2x81a0kfd"):
    """The rendered body as the document would export it, with links applied.

    ``applied`` is the entries whose links reached the page — every one, for a
    tab written properly; none, for a tab whose body was replaced and whose
    format operations were never sent.
    """
    out = render.body(graph, qid)
    for n, entry in enumerate(applied):
        found = list(_loose(entry["anchor"]).finditer(out))
        nth = (entry.get("find") or {}).get("nth", 1)
        if len(found) < nth:
            continue
        at = found[nth - 1]
        out = "%s[%s](%s)%s" % (out[:at.start()], at.group(0),
                                href_of(graph, qid, entry, session, n),
                                out[at.end():])
    return out


class WholeTabTest(unittest.TestCase):
    def setUp(self):
        self.graph = load("valid")

    def links(self, qid):
        return render.links(self.graph, qid)["links"]

    def test_a_tab_written_properly_is_clean(self):
        for q in self.graph.questions:
            with self.subTest(question=q.id):
                page = page_of(self.graph, q.id, self.links(q.id))
                self.assertTrue(verify.verify(self.graph, q.id, page).ok())

    def test_a_body_write_with_no_links_is_the_defect_this_exists_for(self):
        """192 links over 24 tabs went this way, and every gate on the graph
        file stayed green: the reader strips an in-page link before parsing, so
        a rebuilt graph is the same whether they were applied or not."""
        report = verify.verify(self.graph, "ti-esti",
                               page_of(self.graph, "ti-esti"))
        self.assertFalse(report.ok())
        self.assertEqual(len(report.missing), len(self.links("ti-esti")))
        self.assertEqual(report.diff, [])
        self.assertEqual(report.extra, [])

    def test_one_link_of_two_on_the_same_words_is_still_missing_one(self):
        """Counting, not presence. A set comparison calls this correct, which
        is how a half-applied tab passes."""
        qid = "canon"
        thesis = self.graph.get(qid).theses[0]
        # two clauses of one answer may stand on the same words and raise
        # different questions; each wants its own link
        first = thesis.terms[0]
        thesis.text += " " + first.anchors[0]
        thesis.terms.append(model.Term(title="A second reading",
                                       to=first.to, anchors=list(first.anchors)))
        entries = self.links(qid)
        anchor = verify.bare(first.anchors[0])
        self.assertEqual(sum(1 for e in entries if verify.bare(e["anchor"]) == anchor), 2)

        both = page_of(self.graph, qid, entries)
        self.assertTrue(verify.verify(self.graph, qid, both).ok())

        one = page_of(self.graph, qid,
                      [e for e in entries if verify.bare(e["anchor"]) != anchor][:]
                      + [e for e in entries if verify.bare(e["anchor"]) == anchor][:1])
        self.assertEqual(verify.verify(self.graph, qid, one).missing, [anchor])

    def test_a_link_the_sidecar_does_not_name_is_reported(self):
        """A link applied by hand, or one left behind by a definition that has
        since moved to another tab. Ten of those had accumulated."""
        qid = "canon"
        page = page_of(self.graph, qid, self.links(qid))
        page = page.replace("a file in the repository",
                            LINK % ("a file in the repository", "zz", 9), 1)
        report = verify.verify(self.graph, qid, page)
        self.assertEqual(report.missing, [])
        self.assertIn("a file in the repository", report.extra)

    def test_a_link_the_page_cannot_carry_says_what_covers_it(self):
        """Two links over one another: the document takes the outer and skips
        the inner. The words still carry a link, which is what a reader meets,
        so they are not missing — but where that link goes is the outer one's
        business, and the report says so."""
        qid = "canon"
        thesis = self.graph.get(qid).theses[0]
        outer = thesis.terms[0].anchors[0]
        inner = outer.split(".")[0] if "." in outer else outer[: len(outer) // 2]
        self.graph.get(qid).definitions.append(model.Definition(word=inner, body="A part."))
        entries = self.links(qid)
        covered = [e for e in entries if e["covered_by"]]
        self.assertTrue(covered, "the inner anchor should be covered")

        page = page_of(self.graph, qid,
                       [e for e in entries if not e["covered_by"]])
        report = verify.verify(self.graph, qid, page)
        anchor = verify.bare(covered[0]["anchor"])
        self.assertNotIn(anchor, report.missing)
        self.assertIn(anchor, report.covered)
        self.assertEqual(report.extra, [])

    def test_a_split_link_is_one_link_again(self):
        """A nested link cuts the outer one into pieces, and no piece is the
        anchor. Compared by label the clause reads as missing and its halves as
        unaccounted for; compared by span it is what it is."""
        qid = "canon"
        entries = self.links(qid)
        whole = entries[0]
        page = page_of(self.graph, qid, entries)
        anchor = whole["anchor"]
        outer = href_of(self.graph, qid, whole, "mq2x81a0kfd", 0)
        inner = href_of(self.graph, qid, whole, "mq2x81a0kfd", 9)
        cut = len(anchor) // 2
        page = page.replace(
            "[%s](%s)" % (anchor, outer),
            "[%s](%s)[%s](%s)" % (anchor[:cut], outer, anchor[cut:], inner), 1)
        report = verify.verify(self.graph, qid, page)
        self.assertNotIn(verify.bare(anchor), report.missing)
        self.assertEqual(report.extra, [])

    def test_a_body_that_is_not_what_the_renderer_makes_is_reported(self):
        page = page_of(self.graph, "canon", self.links("canon"))
        report = verify.verify(self.graph, "canon", page + "\n\nA line nobody rendered.")
        self.assertTrue(report.diff)


class KeptAsTextTest(unittest.TestCase):
    """The export does not always write a chip as a link."""

    def bare(self, graph, page):
        ids = {render.chip_key(q.id): q.id for q in graph.questions}
        return render.CHIP_TOKEN.sub(
            lambda m: (m.group(0)[:-len(m.group(1)) - len("<?claude block ?>")]
                       + ids[m.group(1)]) if m.group(1) in ids else m.group(0),
            page)

    def test_a_page_whose_chips_are_labels_still_verifies(self):
        graph = load("valid")
        for q in graph.questions:
            with self.subTest(question=q.id):
                entries = render.links(graph, q.id)["links"]
                page = self.bare(graph, page_of(graph, q.id, entries))
                report = verify.verify(graph, q.id, page)
                self.assertTrue(report.ok(), report.lines())

    def test_a_label_does_not_move_the_run_a_link_is_counted_to(self):
        """A chip is an atom to the document and text to the export, so a
        label that repeats a word the page already carries would push every
        later run of it one too high. That is what put a link on the wrong
        `party` and then reported the right one missing."""
        graph = load("valid")
        graph.state_enum = "000e742f-9e41"  # as the document has one
        qid = "ti-esti"
        entries = render.links(graph, qid)["links"]
        page = self.bare(graph, page_of(graph, qid, entries))
        plain, _ = verify._as_the_document_holds_it(
            *verify.linked_spans(page), render.page_text(graph, qid),
            [q.id for q in graph.questions])
        self.assertEqual(plain, render.page_text(graph, qid))



class MisplacedTest(unittest.TestCase):
    """A link standing where the encoding does not put that kind.

    The sidecar counts its runs on the page the renderer built; the document
    counts again on the page it holds, and the two are not obliged to agree.
    A chip is a token to one and an atom to the other, so a word spelled
    inside a chip key shifts every later run of it — and the link lands a run
    early, invisibly, because afterwards both sides agree about where it is.
    Asking the encoding whether that run is allowed is what breaks the tie.
    """

    def setUp(self):
        self.graph = load("valid")
        self.qid = "canon"
        self.entries = render.links(self.graph, self.qid)["links"]

    def test_a_tab_written_properly_has_nothing_out_of_place(self):
        for q in self.graph.questions:
            with self.subTest(question=q.id):
                page = page_of(self.graph, q.id,
                               render.links(self.graph, q.id)["links"])
                self.assertEqual(verify.verify(self.graph, q.id, page).misplaced, [])

    def test_a_run_the_encoding_forbids_is_reported(self):
        entry = next(e for e in self.entries
                     if (e.get("find") or {}).get("nth") == 1)
        words = entry["find"]["text"]
        page = page_of(self.graph, self.qid, self.entries)
        # the same words, earlier, in the tab's own heading. Nothing about
        # the sidecar changes; what changes is which run the page counts to.
        page = page.replace("# %s" % self.qid, "# %s %s" % (self.qid, words), 1)
        report = verify.verify(self.graph, self.qid, page)
        self.assertIn(verify.bare(entry["anchor"]), report.misplaced)
        self.assertFalse(report.ok())

    def test_the_state_word_is_an_atom_and_is_not_counted(self):
        """The document holds the state as a dropdown and the export prints
        the word it shows. Counted, it would shift every run after it — the
        chip fault one field along."""
        graph = load("valid")
        q = graph.get("canon")
        q.state = "in line"
        entries = render.links(graph, q.id)["links"]
        page = page_of(graph, q.id, entries).replace(
            "<?claude block state?>", "in line", 1)
        report = verify.verify(graph, q.id, page)
        self.assertEqual(report.misplaced, [])
        self.assertEqual(report.missing, [])


class HingeWordTest(unittest.TestCase):
    def test_a_word_the_hinge_brought_in_is_placed_and_accounted(self):
        """The link stands in the hinge, so the page check has to allow it
        there — or a correct page reads as a link out of place."""
        graph = load("valid")
        canon = graph.get("canon")
        word = canon.definitions[0].word
        canon.theses[0].text = canon.theses[0].text.replace(
            "marked %s" % word, "marked accord")
        entries = render.links(graph, "canon")["links"]
        report = verify.verify(graph, "canon", page_of(graph, "canon", entries))
        self.assertTrue(report.ok(), report.lines())


class AnswerStateTest(unittest.TestCase):
    """An answer's state is a dropdown too, and the same fault waits for it.

    The export prints the word the dropdown shows; the document's own find
    does not see it. "in thread" holds "thread", so a page that counted it
    would put every later run of that word one further along.
    """

    def test_the_answer_s_state_word_is_not_counted(self):
        graph = load("valid")
        graph.state_enum = "cc6462ad-8c3e"
        thesis = graph.get("ti-esti").theses[0]
        thesis.text += " The answer waits in a thread until the merge."
        graph.get("ti-esti").definitions.append(model.Definition(
            word="thread", body="An open line of questions."))
        entries = render.links(graph, "ti-esti")["links"]
        self.assertIn("thread", [e["anchor"] for e in entries])
        page = (page_of(graph, "ti-esti", entries)
                .replace("<?claude block state?>", "landed", 1)
                .replace("<?claude block state_1?>", "in thread", 1))
        self.assertIn("· in thread · provenance: ", page)
        report = verify.verify(graph, "ti-esti", page)
        self.assertEqual((report.diff, report.missing, report.misplaced,
                          report.extra), ([], [], [], []))


class AstrayTest(unittest.TestCase):
    """Where a link leads, as far as the page can say.

    An href carries a tab and a block. The block cannot be resolved without
    the outlines `apply` takes, and that would make the closing check take a
    second input; the tab is on the page already, and the target names which
    tab it should be.
    """

    def setUp(self):
        self.graph = load("valid")

    def links(self, qid):
        return render.links(self.graph, qid)["links"]

    def test_a_tab_written_properly_leads_nowhere_astray(self):
        for q in self.graph.questions:
            with self.subTest(question=q.id):
                page = page_of(self.graph, q.id, self.links(q.id))
                self.assertEqual(verify.verify(self.graph, q.id, page).astray, [])

    def test_a_link_to_another_tab_that_names_this_one_is_reported(self):
        """A bare fragment leads to the tab it stands on. On an anchor whose
        question is elsewhere that is the wrong page, and the words give no
        sign of it."""
        qid = "attenuation"
        entries = self.links(qid)
        away = next(e for e in entries
                    if e["target"].lstrip("#").partition(".")[0]
                    != self.graph.get(qid).tab)
        page = page_of(self.graph, qid, entries)
        page = page.replace("](%s)" % href_of(self.graph, qid, away,
                                              "mq2x81a0kfd", entries.index(away)),
                            "](#mq2x81a0kfd.1)", 1)
        report = verify.verify(self.graph, qid, page)
        self.assertEqual(report.astray, [verify.bare(away["anchor"])])
        self.assertEqual(report.missing, [])
        self.assertFalse(report.ok())

    def test_the_reader_and_the_checker_describe_the_same_links(self):
        """One drops an href and the other reads it; a link only one of them
        sees is a link the round trip and the gate disagree about."""
        page = ("[a](#mg8.1) [b](https://claude.ai/code/artifact/x#t.mg8.2) "
                "[c](https://example.com/out) [d](file/0c4d2d88-79ab)")
        self.assertEqual([m.group(0) for m in read.IN_PAGE_LINK.finditer(page)],
                         [m.group(0) for m in verify._HREF.finditer(page)])


class NormaliseTest(unittest.TestCase):
    def test_a_chip_reads_the_same_either_way_it_is_spelled(self):
        """The renderer writes a token; the document exports a link. Neither is
        a difference in the page."""
        graph = load("valid")
        body = render.body(graph, "ti-esti")
        exported = body.replace("<?claude block m_canon?>", "[canon](file/tab-02)")
        self.assertEqual(verify.normalise(exported), verify.normalise(body))

    def test_an_answer_s_state_is_a_chip_on_one_side_and_a_word_on_the_other(self):
        graph = load("valid")
        graph.state_enum = "cc6462ad-8c3e"
        body = render.body(graph, "ti-esti")
        self.assertIn("<?claude block state_1?>", body)
        exported = (body.replace("<?claude block state?>", "landed")
                        .replace("<?claude block state_1?>", "in thread"))
        self.assertEqual(verify.normalise(exported), verify.normalise(body))

    def test_the_state_is_a_chip_on_one_side_and_a_word_on_the_other(self):
        graph = load("valid")
        body = render.body(graph, "canon")
        exported = body.replace("<?claude block state?>", "held")
        self.assertEqual(verify.normalise(exported), verify.normalise(body))

    def test_an_applied_link_is_not_a_difference(self):
        graph = load("valid")
        body = render.body(graph, "canon")
        applied = body.replace("a file in the repository",
                               LINK % ("a file in the repository", "z", 1), 1)
        self.assertEqual(verify.normalise(applied), verify.normalise(body))

    def test_a_link_out_of_the_document_is_content_and_stays(self):
        """A hinge names the commit it was answered against; that link is the
        principal's own words."""
        commit = "[dba4d22](https://github.com/natb1/CanonDB/commit/dba4d22)"
        self.assertIn(commit, "\n".join(verify.normalise("see %s here" % commit)))


class ReportTest(unittest.TestCase):
    def test_every_question_with_a_page_is_covered(self):
        graph = load("valid")
        pages = {q.id: page_of(graph, q.id, render.links(graph, q.id)["links"])
                 for q in graph.questions}
        reports = verify.verify_all(graph, pages)
        self.assertEqual([r.question for r in reports], [q.id for q in graph.questions])
        self.assertTrue(all(r.ok() for r in reports))

    def test_a_question_with_no_export_is_left_out(self):
        graph = load("valid")
        self.assertEqual(verify.verify_all(graph, {}), [])

    def test_the_lines_name_the_question_and_each_finding(self):
        graph = load("valid")
        report = verify.verify(graph, "ti-esti", page_of(graph, "ti-esti"))
        lines = report.lines()
        self.assertEqual(lines[0], "=== ti-esti")
        self.assertTrue(any("MISSING LINK" in line for line in lines))


if __name__ == "__main__":
    unittest.main()
