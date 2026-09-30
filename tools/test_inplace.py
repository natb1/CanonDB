"""A line-shaped part written in place reads back as a body render would.

Each writer is run over a view of a rendered tab, and what it writes is put
back into the tab's markdown where the document would put it. The result is
read with the reader and compared with the tab rendered from a graph that
holds the same change: the page after an in-place write and the page after a
body write are the same notebook, or the writer is wrong.
"""

import json
import os
import re
import subprocess
import sys
import unittest
import xml.etree.ElementTree as ET

from hypo import appline, inplace, model, page, read, render

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(HERE, "fixtures")
SESSION = "mq2x81a0kfd"
REV = 7

_INLINE = re.compile(r"(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`|\[[^\]]*\]\([^)]*\)"
                     r"|<\?claude block [0-9A-Za-z_]+\?>)")


def load():
    return model.load(os.path.join(FIXTURES, "valid.json"))


def ids(graph):
    return {render.chip_key(q.id): q.id for q in graph.questions}


class _Ids:
    def __init__(self):
        self.n = 0

    def __call__(self):
        self.n += 1
        return "%s.%d" % (SESSION, self.n) if self.n == 1 else ".%d" % self.n


def _inline(parent, line, chips, new_id):
    """A line of the renderer's markdown as the runs a view prints."""
    for piece in _INLINE.split(line):
        if not piece:
            continue
        if piece.startswith("<?claude block"):
            key = piece.split()[2].rstrip("?>").rstrip("?")
            chip = chips.get(key, {})
            if chip.get("type") == "dropdown":
                node = ET.SubElement(parent, "dropdown", id=new_id(), enum="e",
                                     index=str(chip["index"]))
                node.text = model.STATES[chip["index"]]
            else:
                ET.SubElement(parent, "mention", id=new_id(), ref=chip.get("ref", ""),
                              label=key[2:])
            continue
        text = ET.SubElement(parent, "text", id=new_id())
        for mark, pattern in (("bold", r"^\*\*(.+)\*\*$"), ("italic", r"^\*(.+)\*$"),
                              ("code", r"^`(.+)`$")):
            found = re.match(pattern, piece)
            if found:
                ET.SubElement(text, mark).text = found.group(1)
                break
        else:
            link = re.match(r"^\[([^\]]*)\]\(([^)]*)\)$", piece)
            if link:
                ET.SubElement(text, "link", href=link.group(2)).text = link.group(1)
            else:
                text.text = piece


def _hashed(node):
    for para in node.iter("paragraph"):
        para.set("h", appline.digest(para))
    if node.tag != "paragraph":
        node.set("h", "5a5e5a5e")  # a shape's hash, which no read recomputes
    return node


def view_of(graph, qid, rev=REV):
    """A tab's ``view`` read, as the document would print the rendered body:
    and the markdown of each block, by id, to put writes back into."""
    chips = render.mention_blocks(graph, qid)
    for key, chip in chips.items():
        if chip.get("type") == "mention":  # the label is the question it names
            chip["label"] = key[2:]
    doc = ET.Element("doc", rev=str(rev))
    new_id = _Ids()
    by_id = {}
    for markdown in render.body(graph, qid).strip().split(render.SEPARATOR):
        if all(line.startswith("- ") for line in markdown.splitlines()):
            node = ET.SubElement(doc, "list", id=new_id(), kind="bullet")
            for line in markdown.splitlines():
                item = ET.SubElement(node, "listItem", id=new_id())
                para = ET.SubElement(item, "paragraph", id=new_id())
                _inline(para, line[2:], chips, new_id)
        else:
            node = ET.SubElement(doc, "paragraph", id=new_id())
            level = len(markdown) - len(markdown.lstrip("#"))
            if level and markdown[level:level + 1] == " ":
                node.set("heading", str(level))
                markdown_line = markdown[level + 1:]
            else:
                markdown_line = markdown
            _inline(node, markdown_line, chips, new_id)
        _hashed(node)
        bid = node.get("id")
        by_id[SESSION + bid if bid.startswith(".") else bid] = markdown
    return ET.tostring(doc, encoding="unicode"), by_id


def block_of(by_id, starts):
    """The id of the first block whose markdown starts with ``starts``."""
    return next(bid for bid, md in by_id.items() if md.startswith(starts))


def rewrite(by_id, bid, new=None, after=None):
    """The tab's markdown with one block replaced or one block's worth added."""
    out = []
    for key, md in by_id.items():
        if key == bid and new is not None:
            out.append(new)
            continue
        out.append(md)
        if key == bid and after is not None:
            out.append(after)
    return render.SEPARATOR.join(out) + "\n"


def parsed(markdown, graph):
    q = read.parse_tab(markdown, ids(graph))
    q.pop("incoming", None)
    return q


class ViewTest(unittest.TestCase):
    def test_the_view_is_the_page_and_hashes_as_the_document_does(self):
        graph = load()
        view, by_id = view_of(graph, "canon")
        for bid in by_id:
            appline.block(view, bid)  # refuses a block that does not hash
        self.assertEqual(parsed(render.SEPARATOR.join(by_id.values()), graph),
                         parsed(render.body(graph, "canon"), graph))


class GlossaryTest(unittest.TestCase):
    def setUp(self):
        self.graph = load()
        self.view, self.by_id = view_of(self.graph, "canon")
        self.heading = block_of(self.by_id, "### ≡ assent")
        self.body = block_of(self.by_id, "The mark by which")

    def test_a_replaced_body_reads_back_as_the_graph_holding_it(self):
        new = "The mark by which the one with standing binds an entry."
        ops, _, after = inplace.glossary_replace(self.view, self.heading, self.body, new)
        self.graph.get("canon").definitions[0].body = new
        self.assertEqual(parsed(rewrite(self.by_id, self.body, new=after), self.graph),
                         parsed(render.body(self.graph, "canon"), self.graph))
        self.assertEqual(ops[0]["ifRev"], REV)
        self.assertEqual(ops[0]["with"], {"as": "text", "from": {"kind": "inline",
                                                                 "content": new}})

    def test_an_inserted_entry_reads_back_as_the_graph_holding_it(self):
        ops, content = inplace.glossary_insert(self.body, "entry", "A file in the repository.")
        self.graph.get("canon").definitions.append(
            model.Definition(word="entry", body="A file in the repository."))
        self.assertEqual(parsed(rewrite(self.by_id, self.body, after=content), self.graph),
                         parsed(render.body(self.graph, "canon"), self.graph))
        self.assertEqual(ops[0]["target"]["ids"], [self.body])

    def test_a_read_that_is_not_the_page_is_refused(self):
        stale = self.view.replace("The mark by which", "A mark by which", 1)
        with self.assertRaises(appline.Refused):
            inplace.glossary_replace(stale, self.heading, self.body, "x")

    def test_a_body_the_reader_would_take_for_something_else_is_refused(self):
        for bad in ("> a note", "## Terms", "one\n\ntwo", "↗ elsewhere", "- a list"):
            with self.subTest(body=bad), self.assertRaises(appline.Refused):
                inplace.glossary_insert(self.body, "entry", bad)

    def test_delete_takes_the_heading_and_its_body_each_guarded(self):
        ops = inplace.glossary_delete(self.view, self.heading, [self.body])
        self.assertEqual([o["target"]["ids"][0] for o in ops], [self.heading, self.body])
        self.assertTrue(all(o["ifRev"] == REV and o["ifHash"] for o in ops))


class TermTest(unittest.TestCase):
    def setUp(self):
        self.graph = load()
        self.view, self.by_id = view_of(self.graph, "canon")
        self.thesis = block_of(self.by_id, "An entry is a file")
        self.last = block_of(self.by_id, "*Authority to act")

    def test_an_inserted_term_reads_back_as_the_graph_holding_it(self):
        anchor = "An entry is a file in the repository, not a message in a thread."
        text = inplace.thesis_text(self.view, self.thesis)
        ops, content = inplace.term_insert(self.last, "Where the record is", "party",
                                           "tab-03", [anchor], thesis=text)
        thesis = self.graph.get("canon").theses[0]
        thesis.terms.append(model.Term(title="Where the record is", to="party",
                                       anchors=[anchor]))
        self.assertEqual(parsed(rewrite(self.by_id, self.last, after=content), self.graph),
                         parsed(render.body(self.graph, "canon"), self.graph))
        self.assertEqual(ops[0]["source"]["blocks"],
                         {"m_party": {"type": "mention", "ref": "file/tab-03"}})

    def test_an_anchor_the_answer_does_not_say_is_refused(self):
        text = inplace.thesis_text(self.view, self.thesis)
        with self.assertRaises(appline.Refused):
            inplace.term_insert(self.last, "T", "party", "tab-03",
                                ["words the answer never says"], thesis=text)

    def test_delete_takes_the_heading_and_its_anchors(self):
        heading = block_of(self.by_id, "### ▸ Authority")
        ops = inplace.term_delete(self.view, heading, [self.last])
        self.assertEqual([o["target"]["ids"][0] for o in ops], [heading, self.last])
        with self.assertRaises(appline.Refused):
            inplace.term_delete(self.view, heading, [self.thesis])


class IncomingTest(unittest.TestCase):
    def setUp(self):
        self.graph = load()
        self.view, self.by_id = view_of(self.graph, "attenuation")
        self.header = block_of(self.by_id, "- ")
        root = ET.fromstring(self.view)
        self.items = [SESSION + i.get("id") for i in root.iter("listItem")]

    def test_an_item_goes_where_the_renderer_would_put_its_raiser(self):
        ops, line = inplace.incoming_insert(self.view, self.header, "A clause.",
                                            "canon-b", "tab-9")
        # canon < canon-b < party: after canon's item, before party's
        self.assertEqual(ops[0]["target"]["ids"], [self.items[0]])
        self.assertEqual(ops[0]["side"], "after")
        self.assertEqual(line, "- A clause. <?claude block m_canon_b?>")

    def test_a_raiser_already_listed_needs_its_place_named(self):
        with self.assertRaises(appline.Refused):
            inplace.incoming_insert(self.view, self.header, "A clause.", "canon", "t")
        ops, _ = inplace.incoming_insert(self.view, self.header, "A clause.", "canon",
                                         "t", after_item=self.items[0])
        self.assertEqual(ops[0]["target"]["ids"], [self.items[0]])

    def test_the_list_read_back_holds_the_new_raiser(self):
        _, line = inplace.incoming_insert(self.view, self.header, "A clause.",
                                          "canon-b", "tab-9")
        md = self.by_id[self.header].splitlines()
        md.insert(1, line)
        got = read.parse_tab(rewrite(self.by_id, self.header, new="\n".join(md)),
                             dict(ids(self.graph), m_canon_b="canon-b"))
        self.assertIn(("A clause.", "canon-b"), got["incoming"])

    def test_delete_takes_one_item_guarded(self):
        ops = inplace.incoming_delete(self.view, self.header, self.items[1])
        self.assertEqual(ops[0]["target"]["ids"], [self.items[1]])
        self.assertEqual(ops[0]["ifRev"], REV)


class ThesisTest(unittest.TestCase):
    def setUp(self):
        self.graph = load()
        self.view, self.by_id = view_of(self.graph, "canon")
        self.bid = block_of(self.by_id, "An entry is a file")
        self.anchor = "Authority to act on an unassented entry is held down, never removed."

    def old(self):
        return inplace.letters(inplace.pieces(appline.block(self.view, self.bid)))

    def test_new_words_read_back_as_the_graph_holding_them(self):
        new = self.old().replace("not a message in a thread", "never a chat message")
        ops, _, after = inplace.thesis_replace(self.view, self.bid, new, [self.anchor])
        thesis = self.graph.get("canon").theses[0]
        thesis.text = thesis.text.replace("not a message in a thread",
                                          "never a chat message")
        self.assertEqual(parsed(rewrite(self.by_id, self.bid, new=after), self.graph),
                         parsed(render.body(self.graph, "canon"), self.graph))
        self.assertEqual((ops[0]["ifHash"], ops[0]["ifRev"]),
                         (appline.block(self.view, self.bid).get("h"), REV))

    def test_words_cut_from_under_an_anchor_are_refused(self):
        new = self.old().replace("never removed", "sometimes removed")
        with self.assertRaises(appline.Refused):
            inplace.thesis_replace(self.view, self.bid, new, [self.anchor])

    def test_a_chip_inside_the_changed_words_is_refused(self):
        new = self.old().replace("held down, never removed. ", "gone.")
        with self.assertRaises(appline.Refused):
            inplace.thesis_replace(self.view, self.bid, new)

    def test_a_character_the_page_reads_as_a_mark_is_refused(self):
        new = self.old().replace("a file", "a *file*")
        with self.assertRaises(appline.Refused):
            inplace.thesis_replace(self.view, self.bid, new)


class SpanTest(unittest.TestCase):
    """The document rewrites one stretch, first changed letter to last, and
    the stretch takes the marks it covered; a link beside new words once came
    back spread over all of them."""

    RUNS = [inplace.Piece((), "it is never a "),
            inplace.Piece(((page.LINK, "#mg8a8pjx8b4.1"),), "work item"),
            inplace.Piece((), " competing for the slot, and more words here.")]

    def test_a_change_clear_of_every_mark_is_written(self):
        inplace.reworded(self.RUNS, "it is never a work item competing for the slot, "
                                    "and more words there.")

    def test_a_stretch_that_covers_a_link_is_refused(self):
        with self.assertRaises(appline.Refused):
            inplace.reworded(self.RUNS, "It is a work item like any other, and more words here.")

    def test_a_change_against_a_link_is_refused(self):
        with self.assertRaises(appline.Refused):
            inplace.reworded(self.RUNS, "it is never a work item, competing for the slot, "
                                        "and more words here.")


class HingeTest(unittest.TestCase):
    def setUp(self):
        self.graph = load()
        self.view, self.by_id = view_of(self.graph, "canon")
        self.bid = block_of(self.by_id, "model:")

    def test_an_amendment_reads_back_as_the_graph_holding_it(self):
        ops, _, after = inplace.hinge_amend(self.view, self.bid, "2026-09-30",
                                            "the principal", "a dictation")
        hinge = self.graph.get("canon").hinge
        hinge.thesis = render.amended(hinge.thesis, "2026-09-30", "the principal",
                                      "a dictation")
        self.assertEqual(parsed(rewrite(self.by_id, self.bid, new=after), self.graph),
                         parsed(render.body(self.graph, "canon"), self.graph))
        self.assertTrue(ops[0]["with"]["from"]["content"].endswith(
            "· amended 2026-09-30 by the principal, from a dictation"))

    def test_a_line_that_is_not_the_provenance_is_refused(self):
        other = block_of(self.by_id, "that a mark of assent")
        with self.assertRaises(appline.Refused):
            inplace.hinge_amend(self.view, other, "2026-09-30", "p", "d")

    def test_a_date_out_of_shape_is_refused(self):
        with self.assertRaises(appline.Refused):
            inplace.hinge_amend(self.view, self.bid, "30 Sept", "p", "d")


class CliTest(unittest.TestCase):
    def test_a_glossary_replace_prints_the_ops_and_the_words(self):
        graph = load()
        view, by_id = view_of(graph, "canon")
        done = subprocess.run(
            [sys.executable, os.path.join(HERE, "inplace.py"), "glossary", "replace", "-",
             "--heading", block_of(by_id, "### ≡"), "--block",
             block_of(by_id, "The mark"), "--body", "The mark that binds."],
            input=view, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout)["ops"][0]["ifRev"], REV)
        self.assertIn("new: The mark that binds.", done.stderr)

    def test_a_refusal_exits_one(self):
        done = subprocess.run(
            [sys.executable, os.path.join(HERE, "inplace.py"), "hinge", "amend", "-",
             "--block", "nope.1", "--date", "2026-09-30", "--by", "p", "--from", "d"],
            input="<doc rev='1'/>", capture_output=True, text=True)
        self.assertEqual(done.returncode, 1)
        self.assertIn("REFUSED", done.stderr)


if __name__ == "__main__":
    unittest.main()
