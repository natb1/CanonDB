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
import unittest
import xml.etree.ElementTree as ET

from hypo import appline, inplace, model, page, read, render
from support import chip_ids, load, run

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(HERE, "fixtures")
SESSION = "mq2x81a0kfd"
REV = 7

_INLINE = re.compile(r"(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`|\[[^\]]*\]\([^)]*\)"
                     r"|<\?claude block [0-9A-Za-z_]+\?>)")


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


def view_of(graph, qid, rev=REV, edit=None):
    """A tab's ``view`` read, as the document would print the rendered body:
    and the markdown of each block, by id, to put writes back into. ``edit``
    is applied to each block's markdown first: the sidecar's links are on the
    page and not in the body, so a test that wants one puts it there."""
    chips = render.mention_blocks(graph, qid)
    for key, chip in chips.items():
        if chip.get("type") == "mention":  # the label is the question it names
            chip["label"] = key[2:]
    doc = ET.Element("doc", rev=str(rev), sinceRev="0")
    new_id = _Ids()
    by_id = {}
    for markdown in render.body(graph, qid).strip().split(render.SEPARATOR):
        if edit is not None:
            markdown = edit(markdown)
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
    q = read.parse_tab(markdown, chip_ids(graph))
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

    def test_a_star_among_the_new_words_is_a_letter_the_page_keeps(self):
        """A text write sends letters, and a star among them is one: the page
        speller spells it behind a backslash and the reader keeps it so. It
        was refused as a mark the page would read back, which it no longer
        does."""
        new = "The mark * by which the one with standing binds an entry."
        ops, _, after = inplace.glossary_replace(self.view, self.heading, self.body, new)
        self.assertEqual(after, new.replace("*", "\\*"))
        self.graph.get("canon").definitions[0].body = after
        self.assertEqual(parsed(rewrite(self.by_id, self.body, new=after), self.graph),
                         parsed(render.body(self.graph, "canon"), self.graph))
        self.assertEqual(ops[0]["with"]["from"]["content"], new)

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
                             dict(chip_ids(self.graph), m_canon_b="canon-b"))
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

    def test_a_character_the_page_read_as_a_mark_is_a_letter_it_keeps(self):
        """The stars are letters: the page spells them behind a backslash and
        the reader keeps them so. Refused before as marks the page would read
        back, which it no longer does."""
        new = self.old().replace("a file", "a *file*")
        ops, _, new_md = inplace.thesis_replace(self.view, self.bid, new)
        self.assertIn("a \\*file\\*", new_md)
        self.assertEqual(ops[0]["with"]["from"]["content"], new)


class MarkdownTest(unittest.TestCase):
    """A paragraph whose change reaches a link or a chip, written whole. The
    link is the sidecar's — the term's anchor, linked to the term's heading —
    and the chip is the one that stands after it."""

    LINK = "#%s.40" % SESSION
    LINKED = "[held down, never removed.](%s)" % LINK
    CHIP = "<?claude block m_attenuation?>"

    def setUp(self):
        self.graph = load()
        self.view, self.by_id = view_of(
            self.graph, "canon",
            edit=lambda md: md.replace("held down, never removed.", self.LINKED))
        self.bid = block_of(self.by_id, "An entry is a file")
        self.old = self.by_id[self.bid]

    def text(self):
        return self.graph.get("canon").theses[0].text

    def test_the_view_holds_the_link_and_the_chip(self):
        self.assertIn(self.LINKED + " " + self.CHIP, self.old)
        with self.assertRaises(appline.Refused) as caught:
            inplace.thesis_replace(self.view, self.bid, inplace.letters(inplace.pieces(
                appline.block(self.view, self.bid))).replace("held down, never", "never"))
        self.assertIn("--markdown", str(caught.exception))

    def letters(self, markdown):
        return inplace.letters(inplace.runs_of_markdown(markdown))

    def test_a_linked_word_removed_goes_as_the_document_takes_it(self):
        """The link meets the stretch: off first, then the letters, then on
        again over the new words — none of it as markdown, which the document
        refuses for an in-page link."""
        new = self.old.replace("[held down, never removed.]", "[never removed.]")
        ops, old, after, off, on = inplace.thesis_markdown(self.view, self.bid, new)
        # the term's own anchor line is another block, and another write
        got = parsed(rewrite(self.by_id, self.bid, new=after), self.graph)
        self.assertEqual(got["theses"][0]["text"], self.text().replace(
            "held down, never removed.", "never removed."))
        self.assertEqual(old, self.old)
        self.assertEqual([op["op"] for op in ops], ["format", "replace", "format"])
        self.assertEqual(ops[0]["target"], {"kind": "find", "text": "held down, never removed.",
                                            "nth": 1})
        self.assertEqual(ops[0]["remove"], [{"type": "link"}])
        self.assertEqual((ops[1]["target"]["ids"], ops[1]["ifHash"], ops[1]["ifRev"]),
                         ([self.bid], appline.block(self.view, self.bid).get("h"), REV))
        self.assertEqual(ops[1]["with"], {"as": "text", "from": {
            "kind": "inline", "content": self.letters(new)}})
        self.assertNotIn("<?claude", ops[1]["with"]["from"]["content"])
        self.assertNotIn("[", ops[1]["with"]["from"]["content"])
        self.assertEqual(ops[2]["target"], {"kind": "find", "text": "never removed.", "nth": 1})
        self.assertEqual(ops[2]["add"], [{"type": "link", "href": self.LINK}])
        self.assertEqual(off, [("link", "held down, never removed.", self.LINK)])
        self.assertEqual(on, [("link", "never removed.", self.LINK)])

    def test_a_link_dropped_whole_is_one_format_off_and_no_words(self):
        new = self.old.replace(self.LINKED, "held down, never removed.")
        ops, _, _, off, on = inplace.thesis_markdown(self.view, self.bid, new)
        self.assertEqual([op["op"] for op in ops], ["format"])
        self.assertIn("remove", ops[0])
        self.assertEqual((off, on), ([("link", "held down, never removed.", self.LINK)], []))

    def test_a_link_added_is_one_format_on_counted_over_the_tab(self):
        there = "#%s.77" % SESSION
        new = self.old.replace("a file in the repository",
                               "[a file](%s) in the repository" % there)
        ops, _, after, off, on = inplace.thesis_markdown(
            self.view, self.bid, new,
            ["Authority to act on an unassented entry is held down, never removed."])
        self.assertEqual((off, on), ([], [("link", "a file", there)]))
        self.assertEqual(ops, [{"op": "format",
                                "target": {"kind": "find", "text": "a file", "nth": 1},
                                "add": [{"type": "link", "href": there}]}])
        self.assertEqual(parsed(rewrite(self.by_id, self.bid, new=after), self.graph),
                         parsed(render.body(self.graph, "canon"), self.graph))

    def test_a_mark_clear_of_the_stretch_is_kept_and_the_letters_alone_are_sent(self):
        """The chip and the link stand after the changed words: the document
        keeps both through a text write, so neither is sent again."""
        new = self.old.replace("not a message in a thread", "never a chat message")
        ops, _, _, off, on = inplace.thesis_markdown(self.view, self.bid, new)
        self.assertEqual([op["op"] for op in ops], ["replace"])
        self.assertEqual(ops[0]["with"]["as"], "text")
        self.assertEqual(ops[0]["with"]["from"]["content"], self.letters(new))
        self.assertNotIn("blocks", ops[0]["with"])
        self.assertEqual((off, on), ([], []))

    def test_a_mark_inside_the_stretch_comes_off_before_the_words_change(self):
        """A text write spreads a mark the changed stretch meets over the whole
        of the new words; so it is taken off first, counted over the tab as
        it stands, and put on again over the new run."""
        view, by_id = view_of(
            self.graph, "canon",
            edit=lambda md: md.replace("An entry is a file", "An **entry** is a file"))
        bid = block_of(by_id, "An **entry**")
        new = by_id[bid].replace("An **entry** is a file", "An **item** is a file")
        ops, _, _, off, on = inplace.thesis_markdown(view, bid, new)
        self.assertEqual([op["op"] for op in ops], ["format", "replace", "format"])
        # the question says `entry` once and the answer's headline once before it
        self.assertEqual(ops[0]["target"], {"kind": "find", "text": "entry", "nth": 3})
        self.assertEqual(ops[0]["remove"], [{"type": "bold"}])
        self.assertEqual(ops[1]["with"]["from"]["content"], self.letters(new))
        self.assertEqual(ops[2]["target"], {"kind": "find", "text": "item", "nth": 1})
        self.assertEqual(ops[2]["add"], [{"type": "bold"}])
        self.assertEqual((off, on), ([("bold", "entry", "")], [("bold", "item", "")]))

    def test_a_mark_the_stretch_stops_short_of_is_kept(self):
        """The document rewrites from the first changed letter to the last;
        a mark a space away from that stretch keeps its place."""
        view, by_id = view_of(
            self.graph, "canon",
            edit=lambda md: md.replace("An entry is a file", "An **entry** is a file"))
        bid = block_of(by_id, "An **entry**")
        new = by_id[bid].replace("An **entry** is a file", "Every **entry** is a file")
        ops, _, _, off, on = inplace.thesis_markdown(view, bid, new)
        self.assertEqual([op["op"] for op in ops], ["replace"])
        self.assertEqual((off, on), ([], []))

    def test_the_words_as_they_stand_are_refused(self):
        with self.assertRaises(appline.Refused):
            inplace.thesis_markdown(self.view, self.bid, self.old)

    def test_a_chip_moved_is_refused(self):
        """The letters as they stand, the chip elsewhere among them: a text
        write keeps a chip where the document holds it."""
        view, by_id = view_of(
            self.graph, "canon",
            edit=lambda md: md.replace("An entry is a file", "An %s is a file" % self.CHIP))
        bid = block_of(by_id, "An " + self.CHIP)
        old = by_id[bid]
        new = old.replace("An %s is" % self.CHIP, "An  is").replace(
            "repository, not", "repository, %snot" % self.CHIP)
        self.assertEqual(self.letters(new), self.letters(old))
        with self.assertRaises(appline.Refused) as caught:
            inplace.thesis_markdown(view, bid, new)
        self.assertIn("elsewhere", str(caught.exception))

    def test_a_chip_against_the_stretch_is_refused(self):
        """Words appended to a paragraph that ends in a chip meet the chip,
        and a text write cannot carry one."""
        new = self.old.replace(self.LINKED + " " + self.CHIP, self.LINKED + " Ever. " + self.CHIP)
        self.assertNotEqual(new, self.old)
        with self.assertRaises(appline.Refused) as caught:
            inplace.thesis_markdown(self.view, self.bid, new)
        self.assertIn("chip to attenuation", str(caught.exception))

    def test_a_partial_read_is_refused(self):
        partial = self.view.replace("sinceRev=\"0\"", "sinceRev=\"3\"")
        with self.assertRaises(appline.Refused) as caught:
            inplace.thesis_markdown(partial, self.bid, self.old + " More.")
        self.assertIn("whole", str(caught.exception))

    def test_a_chip_dropped_is_refused_by_name(self):
        new = self.old.replace(" " + self.CHIP, "")
        with self.assertRaises(appline.Refused) as caught:
            inplace.thesis_markdown(self.view, self.bid, new)
        self.assertIn("attenuation", str(caught.exception))

    def test_a_chip_the_paragraph_never_held_is_refused(self):
        with self.assertRaises(appline.Refused):
            inplace.thesis_markdown(self.view, self.bid,
                                    self.old + " <?claude block m_party?>")

    def test_a_chip_said_twice_is_refused(self):
        """The blocks map carries the chip once; a second token is a chip the
        paragraph did not hold."""
        with self.assertRaises(appline.Refused) as caught:
            inplace.thesis_markdown(self.view, self.bid,
                                    self.old.replace(self.CHIP, self.CHIP + " " + self.CHIP))
        self.assertIn("did not hold", str(caught.exception))

    def test_an_anchor_that_no_longer_stands_is_refused(self):
        new = self.old.replace("never removed", "sometimes removed")
        with self.assertRaises(appline.Refused):
            inplace.thesis_markdown(
                self.view, self.bid, new,
                ["Authority to act on an unassented entry is held down, never removed."])

    def test_words_the_reader_would_take_for_something_else_are_refused(self):
        for bad in ("> " + self.old, self.old + "\n\nand a second block",
                    "assent: " + self.old):
            with self.subTest(text=bad[:12]), self.assertRaises(appline.Refused):
                inplace.thesis_markdown(self.view, self.bid, bad)

    def test_a_read_that_is_not_the_page_is_refused(self):
        stale = self.view.replace("An entry is a file", "An entry is one file", 1)
        with self.assertRaises(appline.Refused):
            inplace.thesis_markdown(stale, self.bid, self.old)


class HeadlineTest(unittest.TestCase):
    """The headline stands on the answer's heading and again on every
    application that derives from the answer; all of them move together."""

    OLD = "Each side owes the other what only it can give."
    NEW = "Each side owes what only it can give"

    def setUp(self):
        self.graph = load()
        thesis = self.graph.get("ti-esti").theses[0]
        thesis.applications.append(model.Application(
            name="the second entry", what="the file that followed it",
            link="[entries/second.md](https://example.org/second.md)",
            standing="postulate", note="kept beside `opening.md`"))
        self.view, self.by_id = view_of(self.graph, "ti-esti")
        self.heading = block_of(self.by_id, "### ◆ ")
        self.lines = [bid for bid, md in self.by_id.items() if " · ◆ " in md]

    def written(self, ops):
        """The page after the ops: each block as the op spells it."""
        by_id = dict(self.by_id)
        for op in ops:
            bid = op["target"]["ids"][0]
            content = op["with"]["from"]["content"]
            by_id[bid] = "### " + content if bid == self.heading else content
        return render.SEPARATOR.join(by_id.values()) + "\n"

    def test_the_heading_and_both_applications_read_back_as_the_graph(self):
        self.assertEqual(len(self.lines), 2)
        ops, old, new = inplace.thesis_headline(self.view, self.heading, self.NEW)
        self.assertEqual((old, new), ("◆ " + self.OLD, "◆ " + self.NEW))
        self.assertEqual([o["target"]["ids"][0] for o in ops],
                         [self.heading] + self.lines)
        self.assertEqual(ops[0]["with"], {"as": "text", "from": {
            "kind": "inline", "content": "◆ " + self.NEW}})
        self.assertTrue(all(o["with"]["as"] == "markdown" for o in ops[1:]))
        self.assertTrue(all(o["ifRev"] == REV and o["ifHash"] for o in ops))
        self.graph.get("ti-esti").theses[0].title = self.NEW
        self.assertEqual(parsed(self.written(ops), self.graph),
                         parsed(render.body(self.graph, "ti-esti"), self.graph))

    def test_only_the_headline_moves_on_an_application_line(self):
        ops, _, _ = inplace.thesis_headline(self.view, self.heading, self.NEW)
        for op, bid in zip(ops[1:], self.lines):
            self.assertEqual(op["with"]["from"]["content"],
                             self.by_id[bid].replace(self.OLD, self.NEW))
        self.assertIn("[entries/second.md](https://example.org/second.md)",
                      ops[2]["with"]["from"]["content"])
        self.assertIn("`opening.md`", ops[2]["with"]["from"]["content"])

    def test_an_application_of_another_answer_is_left(self):
        q = self.graph.get("ti-esti")
        q.theses.append(model.Thesis(
            title="The principal's own prior", text="He holds otherwise.",
            assent="none", state="held",
            applications=[model.Application(name="his note", what="a note of his",
                                            link="notes/own.md", standing="postulate")]))
        view, by_id = view_of(self.graph, "ti-esti")
        ops, _, _ = inplace.thesis_headline(view, block_of(by_id, "### ◆ Each"), self.NEW)
        self.assertEqual(len(ops), 3)
        with self.assertRaises(appline.Refused):
            inplace.thesis_headline(view, block_of(by_id, "### ◆ Each"),
                                    "The principal's own prior")

    def test_a_heading_that_is_not_an_answer_s_is_refused(self):
        for starts in ("### ▸ ", "### ⚙ ", "## Thesis", "A relationship that"):
            with self.subTest(block=starts), self.assertRaises(appline.Refused):
                inplace.thesis_headline(self.view, block_of(self.by_id, starts), self.NEW)

    def test_a_headline_that_is_not_plain_letters_is_refused(self):
        for bad in ("Each side *owes*", "Each `side`", "[Each](#x) side", "one\ntwo", " "):
            with self.subTest(title=bad), self.assertRaises(appline.Refused):
                inplace.thesis_headline(self.view, self.heading, bad)

    def test_a_headline_an_application_line_would_not_give_back_is_refused(self):
        with self.assertRaises(appline.Refused):
            inplace.thesis_headline(self.view, self.heading, "What is owed · and by whom")

    def test_the_separator_is_refused_before_any_application_says_the_headline(self):
        """Accepted while no line says it, the headline would part the fields of
        the first application line written for it, and the reader would file
        that application under no answer."""
        self.graph.get("ti-esti").theses[0].applications = []
        view, by_id = view_of(self.graph, "ti-esti")
        with self.assertRaises(appline.Refused) as caught:
            inplace.thesis_headline(view, block_of(by_id, "### ◆ "),
                                    "What is owed · and by whom")
        self.assertIn("·", str(caught.exception))

    def test_the_section_is_found_as_the_reader_finds_it(self):
        """The reader folds the case of a section's name; the lines under a
        heading it would read must move with the headline all the same."""
        view, by_id = view_of(self.graph, "ti-esti",
                              edit=lambda md: md.replace("## Applications", "## applications"))
        ops, _, _ = inplace.thesis_headline(view, block_of(by_id, "### ◆ "), self.NEW)
        self.assertEqual(len(ops), 1 + len(self.lines))

    def test_another_answer_s_line_that_does_not_round_trip_is_left_alone(self):
        """Whose a line is comes before its shape: a line the renderer would not
        have written, under another answer, is not this headline's to refuse."""
        q = self.graph.get("ti-esti")
        q.theses.append(model.Thesis(
            title="The principal's own prior", text="He holds otherwise.",
            assent="none", state="held",
            applications=[model.Application(name="his note", what="a note of his",
                                            link="notes/own.md", standing="postulate")]))
        view, by_id = view_of(
            self.graph, "ti-esti",
            edit=lambda md: md.replace("notes/own.md · postulate (",
                                       "notes/own.md · postulate  ("))
        other = next(bid for bid, md in by_id.items() if "notes/own.md" in md)
        with self.assertRaises(appline.Refused):
            appline.read_line(view, other)
        ops, _, _ = inplace.thesis_headline(view, block_of(by_id, "### ◆ Each"), self.NEW)
        self.assertEqual(len(ops), 3)
        self.assertNotIn(other, [op["target"]["ids"][0] for op in ops])

    def test_a_partial_read_is_refused(self):
        """A search, or a view since a later rev, may not hold every
        application that says the headline."""
        search = self.view.replace(" sinceRev=\"0\"", "", 1)
        since = self.view.replace("sinceRev=\"0\"", "sinceRev=\"5\"", 1)
        folded = self.view.replace("</doc>", "<gap blocks=\"3\" /></doc>")
        for read_ in (search, since, folded):
            self.assertNotEqual(read_, self.view)
            with self.subTest(read=read_[:40]), self.assertRaises(appline.Refused) as caught:
                inplace.thesis_headline(read_, self.heading, self.NEW)
            self.assertIn("whole view", str(caught.exception))

    def test_a_read_that_is_not_the_page_is_refused(self):
        stale = self.view.replace("the first file both", "the one file both", 1)
        self.assertNotEqual(stale, self.view)
        with self.assertRaises(appline.Refused):
            inplace.thesis_headline(stale, self.heading, self.NEW)


class SpanTest(unittest.TestCase):
    """The document rewrites one stretch, first changed letter to last, and
    the stretch takes the marks it covered; a link beside new words once came
    back spread over all of them."""

    RUNS = [inplace.Piece((), "it is never a "),
            inplace.Piece(((page.LINK, "#mg8a8pjx8b4.1"),), "work item"),
            inplace.Piece((), " competing for the slot, and more words here.")]

    def test_a_change_clear_of_every_mark_is_written(self):
        new = "it is never a work item competing for the slot, and more words there."
        after = inplace.reworded(self.RUNS, new)
        self.assertEqual(inplace.letters(after), new)
        self.assertIn(self.RUNS[1], after)

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

    def test_a_refusal_sends_to_the_write_that_takes_the_block_whole(self):
        """A provenance that ends in a link cannot take the amendment as text;
        the remedy named is ``words replace --markdown``, and not a body
        write, which would retire every link into the tab."""
        view, by_id = view_of(self.graph, "canon", edit=lambda md: md.replace(
            "canon: the opening entry", "canon: [the opening entry](https://example.org/c)"))
        with self.assertRaises(appline.Refused) as caught:
            inplace.hinge_amend(view, block_of(by_id, "model:"), "2026-10-06", "p", "d")
        self.assertIn("words replace --markdown", str(caught.exception))
        self.assertNotIn("write the tab whole", str(caught.exception))


class CliTest(unittest.TestCase):
    def test_a_glossary_replace_prints_the_ops_and_the_words(self):
        graph = load()
        view, by_id = view_of(graph, "canon")
        done = run("inplace.py", "glossary", "replace", "-",
                   "--heading", block_of(by_id, "### ≡"), "--block",
                   block_of(by_id, "The mark"), "--body", "The mark that binds.", stdin=view)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout)["ops"][0]["ifRev"], REV)
        self.assertIn("new: The mark that binds.", done.stderr)

    def test_a_headline_prints_an_op_per_block_and_the_words(self):
        graph = load()
        view, by_id = view_of(graph, "ti-esti")
        done = run("inplace.py", "thesis", "headline", "-",
                   "--heading", block_of(by_id, "### ◆ "), "--title", "What each side owes",
                   stdin=view)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(len(json.loads(done.stdout)["ops"]), 2)
        self.assertIn("old: ◆ Each side owes the other what only it can give.", done.stderr)
        self.assertIn("new: ◆ What each side owes", done.stderr)

    def test_a_markdown_replace_says_what_it_takes_off_and_puts_on(self):
        graph = load()
        view, by_id = view_of(
            graph, "canon",
            edit=lambda md: md.replace("An entry is a file", "An entry is [a file](#s.5)"))
        bid = block_of(by_id, "An entry is ")
        new = by_id[bid].replace("[a file](#s.5)", "a file").replace(
            "the repository", "[the repository](#s.6)")
        done = run("inplace.py", "thesis", "replace", "-",
                   "--block", bid, "--text", new, "--markdown", stdin=view)
        self.assertEqual(done.returncode, 0, done.stderr)
        ops = json.loads(done.stdout)["ops"]
        self.assertEqual([op["op"] for op in ops], ["format", "format"])
        self.assertIn("remove", ops[0])
        self.assertIn("add", ops[1])
        self.assertIn("off: the link on 'a file' to #s.5", done.stderr)
        self.assertIn("on: the link on 'the repository' to #s.6", done.stderr)
        self.assertIn("the letters unchanged", done.stderr)

    def test_an_incoming_insert_says_where_the_next_item_goes(self):
        graph = load()
        view, by_id = view_of(graph, "attenuation")
        done = run("inplace.py", "incoming", "insert", "-", "--list", block_of(by_id, "- "),
                   "--anchor", "A clause.", "--from", "canon-b", "--from-tab", "tab-9",
                   stdin=view)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(len(json.loads(done.stdout)["ops"]), 1)
        self.assertIn("next: a further item of the list goes in a call of its own, "
                      "--after-item", done.stderr)

    def test_a_refusal_exits_one(self):
        done = run("inplace.py", "hinge", "amend", "-",
                   "--block", "nope.1", "--date", "2026-09-30", "--by", "p", "--from", "d",
                   stdin="<doc rev='1'/>")
        self.assertEqual(done.returncode, 1)
        self.assertIn("REFUSED", done.stderr)



class RewordedTest(unittest.TestCase):
    def test_a_mark_the_document_leaves_whole_is_kept(self):
        """Aligned by a diff, the bold A was taken for part of the change; the
        document keeps the letters shared at the front, and the mark on them."""
        runs = [inplace.Piece((("bold", ""),), "A"), inplace.Piece((), " A B")]
        after = inplace.reworded(runs, "A B")
        self.assertEqual(inplace.letters(after), "A B")
        self.assertEqual(after[0], runs[0])

    def test_an_in_page_link_clear_of_the_change_is_said_back_linked(self):
        runs = [inplace.Piece((), "see "), inplace.Piece(((page.LINK, "#abc.1"),), "the entry"),
                inplace.Piece((), " here")]
        after = inplace.reworded(runs, "see the entry there")
        self.assertEqual(inplace.spelled(after)[0], "see [the entry](#abc.1) there")

    def test_the_reader_s_unescaping_is_applied_on_this_side_too(self):
        self.assertEqual(inplace._reader_md("session\\_01 [x](#a.1)"), "session_01 x")

    def test_a_list_with_no_live_item_is_refused(self):
        src = "<doc rev='1' sinceRev='0'><list id='a.3' kind='bullet' h='%s'><gone id='.4'/></list></doc>"
        src = src % appline.digest(ET.fromstring("<list><gone/></list>"))
        with self.assertRaises(appline.Refused) as caught:
            inplace.incoming_insert(src, "a.3", "an anchor", "ti-esti", "tab-01")
        self.assertIn("no item", str(caught.exception))


if __name__ == "__main__":
    unittest.main()


class WordsTest(unittest.TestCase):
    """Any block of words, written in place and decided by its read-back."""

    def setUp(self):
        self.graph = load()
        self.view, self.by_id = view_of(self.graph, "canon")
        self.q = self.graph.get("canon")

    def test_a_hinge_question_half_reads_back_as_the_graph_holding_it(self):
        bid = next(b for b, md in self.by_id.items() if md == self.q.hinge.question)
        new = self.q.hinge.question + " And that a door turns."
        ops, old, after, field = inplace.words_replace(self.view, bid, new)
        self.assertEqual(field, "hinge.question")
        self.assertEqual(ops[0]["with"]["from"]["content"], new)
        self.q.hinge.question = new
        self.assertEqual(parsed(rewrite(self.by_id, bid, new=after), self.graph),
                         parsed(render.body(self.graph, "canon"), self.graph))

    def test_a_pressure_is_one_field_and_a_kind_with_it_is_two(self):
        bid = block_of(self.by_id, "question: ")
        node = appline.block(self.view, bid)
        letters = inplace.letters(inplace.pieces(node))
        self.assertIn("pressure %d" % self.q.pressure, letters)
        one = letters.replace("pressure %d" % self.q.pressure, "pressure %d" % (self.q.pressure + 3))
        _, _, _, field = inplace.words_replace(self.view, bid, one)
        self.assertEqual(field, "pressure")
        two = one.replace(" · %s · " % self.q.kind, " · case · ")
        self.assertNotEqual(two, one)
        with self.assertRaises(appline.Refused) as caught:
            inplace.words_replace(self.view, bid, two)
        self.assertIn("more than one field", str(caught.exception))

    def test_the_words_as_they_stand_are_refused(self):
        bid = next(b for b, md in self.by_id.items() if md == self.q.hinge.question)
        with self.assertRaises(appline.Refused):
            inplace.words_replace(self.view, bid, self.q.hinge.question)

    def test_a_thesis_keeps_the_anchors_of_its_terms(self):
        thesis = self.q.theses[0]
        anchor = next(a for t in thesis.terms for a in t.anchors)
        bid = next(b for b, md in self.by_id.items()
                   if anchor in md and not md.startswith("#") and not md.startswith("*"))
        node = appline.block(self.view, bid)
        letters = inplace.letters(inplace.pieces(node))
        self.assertIn(anchor, letters)
        with self.assertRaises(appline.Refused) as caught:
            inplace.words_replace(self.view, bid, letters.replace(anchor, "something else"))
        self.assertIn("anchor", str(caught.exception))

    def test_a_heading_is_refused(self):
        with self.assertRaises(appline.Refused):
            inplace.words_replace(self.view, block_of(self.by_id, "### "), "words")

    def test_a_provenance_ending_in_a_link_is_amended_as_markdown(self):
        view, by_id = view_of(self.graph, "canon", edit=lambda md: md.replace(
            "canon: the opening entry", "canon: [the opening entry](https://example.org/c)"))
        bid = block_of(by_id, "model:")
        new_md = by_id[bid] + " · amended 2026-10-06 by p, from d"
        ops, old, after, field, off, on = inplace.words_markdown(view, bid, new_md)
        self.assertEqual(field, "hinge.thesis")
        # the link closes the old words, so the stretch meets it: off before
        # the letters change, on after, as thesis replace --markdown sends it
        link = ("link", "the opening entry", "https://example.org/c")
        self.assertEqual((off, on), ([link], [link]))
        self.assertEqual([op["op"] for op in ops], ["format", "replace", "format"])
        self.assertTrue(ops[1]["with"]["from"]["content"].endswith("by p, from d"))
        self.assertTrue(after.endswith("[the opening entry](https://example.org/c) · amended "
                                       "2026-10-06 by p, from d"))


class NoteTest(unittest.TestCase):
    def setUp(self):
        self.graph = load()
        self.view, self.by_id = view_of(self.graph, "canon")
        self.blocks = page.blocks(self.view)

    def last_of(self, section):
        ids = [bid for bid, _ in self.blocks]
        start = next(i for i, (_, md) in enumerate(self.blocks) if md == "## " + section)
        end = next((i for i in range(start + 1, len(ids)) if self.blocks[i][1].startswith("## ")),
                   len(ids))
        return ids[end - 1], ids[start]

    def test_a_note_lands_at_the_end_of_its_section_as_the_renderer_writes_it(self):
        after, _ = self.last_of("Thesis")
        ops, section, content = inplace.note_insert(
            self.view, after, "pending: a clause this run could not apply")
        self.assertEqual(section, "Thesis")
        self.assertEqual(content, "> pending: a clause this run could not apply")
        self.assertEqual(ops[0]["target"]["ids"], [after])
        q = self.graph.get("canon")
        q.notes.append(model.Note(section="thesis",
                                  body="pending: a clause this run could not apply"))
        self.assertEqual(parsed(rewrite(self.by_id, after, after=content), self.graph),
                         parsed(render.body(self.graph, "canon"), self.graph))

    def test_a_note_mid_section_or_above_the_first_is_refused(self):
        _, heading = self.last_of("Thesis")
        with self.assertRaises(appline.Refused) as caught:
            inplace.note_insert(self.view, heading, "pending: words")
        self.assertIn("last block", str(caught.exception))
        with self.assertRaises(appline.Refused) as caught:
            inplace.note_insert(self.view, block_of(self.by_id, "# canon"), "pending: words")
        self.assertIn("above the first section", str(caught.exception))

    def test_a_note_that_opens_like_a_heading_is_refused(self):
        after, _ = self.last_of("Thesis")
        with self.assertRaises(appline.Refused):
            inplace.note_insert(self.view, after, "## not a note")


class WordsCliTest(unittest.TestCase):
    def test_words_replace_and_note_insert_run(self):
        graph = load()
        view, by_id = view_of(graph, "canon")
        q = graph.get("canon")
        bid = next(b for b, md in by_id.items() if md == q.hinge.question)
        done = run("inplace.py", "words", "replace", "-", "--block", bid,
                   "--text", q.hinge.question + " And more.", stdin=view)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(len(json.loads(done.stdout)["ops"]), 1)
        self.assertIn("field: hinge.question", done.stderr)
        last = [b for b, _ in page.blocks(view)]
        thesis_end = next(i for i, (_, md) in enumerate(page.blocks(view)) if md == "## Glossary") - 1
        done = run("inplace.py", "note", "insert", "-", "--after", last[thesis_end],
                   "--text", "pending: a clause", stdin=view)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("on: Thesis", done.stderr)


class ChipRefusalTest(unittest.TestCase):
    """New words that dropped the letters around a chip are told so, not told
    of the run that happens to stand before the chip."""

    def test_the_chip_is_named_before_the_run_beside_it(self):
        chip = ET.Element("mention", {"label": "disposition", "ref": "file/x"})
        runs = [inplace.Piece(((page.LINK, "https://example.org/a"),), "his only act"),
                inplace.Piece((), " "), inplace.Piece((), "", chip),
                inplace.Piece((), "; the words")]
        with self.assertRaises(appline.Refused) as caught:
            inplace.reworded(runs, "his only act; the words")
        said = str(caught.exception)
        self.assertIn("chip to disposition", said)
        self.assertIn("act ' before it and '; the words' after", said)
        self.assertNotIn("marked run", said)

    def test_a_run_beside_the_stretch_with_no_chip_in_it_is_still_named(self):
        runs = [inplace.Piece(((page.LINK, "https://example.org/a"),), "his only act"),
                inplace.Piece((), "; the words")]
        with self.assertRaises(appline.Refused) as caught:
            inplace.reworded(runs, "his only acts; the words")
        self.assertIn("marked run", str(caught.exception))


class EndWordsTest(unittest.TestCase):
    """The end and the method are blocks of words like the question half:
    written in place, and decided by their read-back."""

    def setUp(self):
        self.graph = load()
        self.view, self.by_id = view_of(self.graph, "ti-esti")
        self.q = self.graph.get("ti-esti")

    def test_the_end_reads_back_as_the_end(self):
        bid = next(b for b, md in self.by_id.items() if md == self.q.hinge.end)
        new = self.q.hinge.end + " And nothing more."
        ops, old, after, field = inplace.words_replace(self.view, bid, new)
        self.assertEqual(field, "hinge.end")
        self.q.hinge.end = new
        self.assertEqual(parsed(rewrite(self.by_id, bid, new=after), self.graph),
                         parsed(render.body(self.graph, "ti-esti"), self.graph))

    def test_the_method_reads_back_as_the_method(self):
        bid = next(b for b, md in self.by_id.items() if md == self.q.hinge.method)
        _, _, _, field = inplace.words_replace(self.view, bid, self.q.hinge.method + " And again.")
        self.assertEqual(field, "hinge.method")
