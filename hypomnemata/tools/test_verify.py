"""The page against the renderer: the one check that reads what reached the page."""

import re
import unittest

import test_render  # the fixture loader and its graphs
from hypo import model, render, verify

load = test_render.load

#: a link as the document exports one it was given: the words, and a fragment.
LINK = "[%s](#%s.%d)"


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
        out = "%s%s%s" % (out[:at.start()],
                          LINK % (at.group(0), session, n),
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
        thesis.definitions.append(model.Definition(word=inner, body="A part."))
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
        cut = len(anchor) // 2
        page = page.replace(
            LINK % (anchor, "mq2x81a0kfd", 0),
            (LINK % (anchor[:cut], "mq2x81a0kfd", 0)
             + LINK % (anchor[cut:], "mq2x81a0kfd", 9)), 1)
        report = verify.verify(self.graph, qid, page)
        self.assertNotIn(verify.bare(anchor), report.missing)
        self.assertEqual(report.extra, [])

    def test_a_body_that_is_not_what_the_renderer_makes_is_reported(self):
        page = page_of(self.graph, "canon", self.links("canon"))
        report = verify.verify(self.graph, "canon", page + "\n\nA line nobody rendered.")
        self.assertTrue(report.diff)


class NormaliseTest(unittest.TestCase):
    def test_a_chip_reads_the_same_either_way_it_is_spelled(self):
        """The renderer writes a token; the document exports a link. Neither is
        a difference in the page."""
        graph = load("valid")
        body = render.body(graph, "ti-esti")
        exported = body.replace("<?claude block m_canon?>", "[canon](file/tab-02)")
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
