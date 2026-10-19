"""The other line-shaped parts of a tab, written where they stand.

``appline`` writes an application in place, and the reason it exists holds for
every part of a tab that is a line or two under a heading of its own: a body
write mints new ids for every block on the tab and so retires every link into
it, while the part itself touches two or three blocks. A glossary entry is a
heading and a paragraph; a term is a heading, its anchors, and one item on the
header list of the tab it raises; a paragraph of an answer is one block of
words; an answer's headline is a heading, said again on every application
that derives from it; a hinge's provenance is one line that an amendment
lengthens. Each is
written here as the operations of one prose ``update``, from a read of the page
checked against the hash the document printed, so a dictation that changes
only these reaches the page without a body write and without a relink.

Two ways of writing, and which one a part takes is decided by what it is.

A **new** part — an entry, a term, a header item — is spelled by the
renderer's own functions (``render.glossary_heading``, ``render.term_line``,
``render.anchor_line``, ``render.incoming_item``) and inserted as markdown,
with the chips it carries in the ``blocks`` map beside it. What is inserted is
what a body render would have written, and before it is sent it is read back
through ``read.parse_tab`` inside a tab of its own, so that a part the reader
would take for something else — a body that opens like a note, a word with a
blank line in it — is refused here rather than found on the next rebuild.

An **existing** block of words — a definition's body, a paragraph of an
answer, a hinge's provenance — is re-worded as ``text``: the document keeps
the chips, the links and the emphasis on every run the words do not touch. So
the new words are aligned with the old, run by run, and the write is refused
where it would move a mark it cannot say where to put: a chip or a marked run
inside the changed words, or a changed word carrying a character the page
would read back as a mark of its own. What comes out is the block as the page
will spell it afterwards, chips as the renderer's tokens, and that is what is
read back.

Every other block of words — a hinge's question half, its end or its
method, a note, a paragraph
the writers above do not name — is written by one writer that is decided not
by which part the block is but by its read-back: the whole tab is read
through ``read.parse_tab`` before and after, and the write is refused unless
one field alone differs. A note is inserted at the end of its section, which
is where the renderer writes one. So no part of a tab is left whose only way
to the page is a body write.

A paragraph whose change does reach a mark is written a third
way, when the caller asks for it: given whole, as **markdown** in the
renderer's spelling, so that the caller says where every link and every mark
goes. What is sent is what the document takes, which is not that markdown:
the document takes no in-page link in a replace's markdown, and a ``text``
replace spreads a mark that stood inside the changed stretch over the whole
of the new words. So the paragraph goes as its letters, one ``text`` replace,
and the marks go as ``format`` operations around it — off, before the words
change, every mark the stretch meets or the new words no longer carry; on,
after, every mark the new words carry that did not survive — each found by
its words, counted over the whole tab as the document counts them. The read
is therefore the tab's whole view. The chips are not the caller's to drop
or to move: each one the block held must stand in what he wrote, where it
stood, and clear of the stretch, since a text write cannot carry one.

Every whole-block ``replace`` and ``delete`` carries both guards the document
asks for: the block's ``h`` and the ``rev`` of the read that showed it.

What is not written here: the links. A term's anchor in the answer carries a
chip beside it and a link to the term's heading, and its header item a link
back; both name block ids that only the insert's acknowledgement holds. They
are owed after the write, and this says so rather than send an operation that
would land nowhere.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Dict, List, NamedTuple, Optional, Sequence, Tuple

from . import appline, page, read, render, spec, text
from .appline import Refused, block, blocks, rev
from .model import GLYPHS, Term

#: the glyphs that open each part's heading, as the renderer writes them
GLOSSARY, TERM, THESIS = GLYPHS["glossary"], GLYPHS["term"], GLYPHS["thesis"]

#: the section an application line stands in, as the page heads it
APPLICATIONS = "Applications"

#: a link as the renderer's markdown spells one: its words and where it leads

#: the marks a field of one line of plain words — a headline, a term's title,
#: a glossary word, who amended and from what — may not carry
MARKUP = re.compile(r"[*`\[\]]")

#: the date an amendment names
DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# -- a block as runs --------------------------------------------------------

class Piece(NamedTuple):
    """A run of a block's letters with the marks on it, outermost first, or a
    chip, which is an atom with no letters of its own."""
    marks: Tuple[Tuple[str, str], ...]
    text: str
    chip: Optional[ET.Element] = None


def pieces(node: ET.Element, marks: Tuple[Tuple[str, str], ...] = (),
           top: bool = True) -> List[Piece]:
    """The runs of a paragraph, the way ``page`` walks them and ``appline``
    hashes them: a mention or a dropdown is a chip with no letters."""
    out: List[Piece] = []
    if not top and node.text:
        out.append(Piece(marks, node.text))
    for child in node:
        tag = child.tag
        if tag in ("mention", "dropdown"):
            out.append(Piece(marks, "", child))
        elif tag in (page.ITALIC, page.BOLD, page.CODE):
            out.extend(pieces(child, marks + ((tag, ""),), False))
        elif tag == page.LINK:
            out.extend(pieces(child, marks + ((page.LINK, child.get("href", "")),), False))
        else:
            out.extend(pieces(child, marks, False))
        if child.tail:
            out.append(Piece(marks, child.tail))
    return out


def letters(runs: Sequence[Piece]) -> str:
    """What the block's hash is taken over, and what a ``text`` write sends."""
    return "".join(p.text for p in runs)


def _in_page(mark: Tuple[str, str]) -> bool:
    """A link the sidecar put on the page: the reader drops it, so words may
    move under it and the reading is the same."""
    return mark[0] == page.LINK and bool(read.IN_PAGE_LINK.fullmatch("[x](%s)" % mark[1]))


def _fixed(p: Piece) -> bool:
    """A run whose marks the reader keeps, which a change of words may not
    cut: emphasis, code, or a link to somewhere else."""
    return any(not _in_page(mark) for mark in p.marks)


def spelled(runs: Sequence[Piece]) -> Tuple[str, Dict[str, dict]]:
    """The block as markdown the renderer would write, a chip as its token,
    and the ``blocks`` map the tokens are written against."""
    chips: Dict[str, dict] = {}
    runs_out: List[page.Run] = []
    for p in runs:
        if p.chip is not None and p.chip.tag == "dropdown":
            runs_out.append((p.marks, p.chip.text or ""))  # the word it shows
        elif p.chip is not None:
            key = render.chip_key(p.chip.get("label", ""))
            chips[key] = {"type": "mention", "ref": p.chip.get("ref", "")}
            runs_out.append((p.marks, render.token(key)))
        else:
            runs_out.append((p.marks, page.literal(p.text, p.marks)))
    return page.spell(runs_out), chips


def reworded(runs: Sequence[Piece], new: str,
             remedy: str = "change the words around it, or write the tab whole"
             ) -> List[Piece]:
    """The runs after a ``text`` write of ``new`` over them.

    The old letters and the new are aligned, and every chip and every marked
    run has to stand inside a stretch the two share — which is where the
    document keeps it. Where one does not, the document either refuses the
    write or puts the mark somewhere nobody chose, and this refuses first.
    ``remedy`` is what the refusal then sends the caller to: only a paragraph
    of an answer has a markdown way, so the caller that has one names it.
    """
    old = letters(runs)
    if "\n" in new:
        raise Refused("the words break a line, which the document would read "
                      "as a second block")
    # The document does not align words: it keeps the letters the old and the
    # new share at the front and at the back, and writes everything between as
    # one run, which takes the marks of what it covered. That stretch is the
    # one thing the placing follows: a run before it keeps its place, and one
    # after it moves by the difference. (Aligned by a diff instead, a run the
    # document left whole was refused as inside the changed words.)
    s0, e0 = _span(old, new)
    # A star or a bracket among the new letters is a letter: the page spells
    # it behind a backslash and the reader keeps it so, which the caller's
    # read-back of what is said here confirms.
    # New words beside a link came back linked from the first change to the
    # last. So no marked run and no chip may meet that stretch, not even an
    # in-page link the reader drops; a block whose changes reach one is
    # written as markdown.
    at = 0
    hit: List[Tuple[int, Piece]] = []
    for p in runs:
        end = at + len(p.text)
        if (p.chip is not None or (p.marks and p.text)) and s0 <= end and e0 >= at:
            hit.append((at, p))
        at = end
    # A chip is named before a run beside it: a chip has no letters, so the
    # usual way the stretch reaches one is new words that dropped the letters
    # around it, and the run before it is only the first thing the stretch
    # touches. Said that way, the caller knows what to keep.
    chips = [(at, p) for at, p in hit if p.chip is not None]
    if chips:
        at, p = chips[0]
        before, after = old[max(0, at - 12):at], old[at:at + 12]
        raise Refused("a chip to %s stands in the stretch the document rewrites (from "
                      "the first changed letter to the last) and would be lost: the new "
                      "words must keep the letters around it as they stand, %r before it "
                      "and %r after, or the change reaches the chip; %s"
                      % (p.chip.get("label", "?"), before, after, remedy))
    if hit:
        raise Refused("the marked run %r stands in or against the stretch the document "
                      "rewrites (from the first changed letter to the last), and would "
                      "lose its mark or carry it onto the new words; %s"
                      % (hit[0][1].text, remedy))
    # every chip and every marked run stands clear of the stretch, so each
    # keeps its letters and its marks — the in-page links too, so that what
    # is said back is what the page will hold
    kept: List[Tuple[int, int, Piece]] = []
    at = 0
    for p in runs:
        end = at + len(p.text)
        if p.chip is not None or (p.marks and p.text):
            moved = at if end < s0 else at + len(new) - len(old)
            kept.append((moved, moved + len(p.text), p))
        at = end
    out: List[Piece] = []
    cursor = 0
    for start, stop, p in kept:
        if start > cursor:
            out.append(Piece((), new[cursor:start]))
        out.append(p)
        cursor = max(cursor, stop)
    if cursor < len(new):
        out.append(Piece((), new[cursor:]))
    return out


def _span(old: str, new: str) -> Tuple[int, int]:
    """The stretch of ``old`` the document rewrites: after the letters the
    two share at the front, before those they share at the back."""
    front = 0
    while front < min(len(old), len(new)) and old[front] == new[front]:
        front += 1
    back = 0
    while (back < min(len(old), len(new)) - front
           and old[len(old) - 1 - back] == new[len(new) - 1 - back]):
        back += 1
    return front, len(old) - back


def _reader_md(md: str) -> str:
    """Markdown as the reader holds it in a thesis: chips off, the sidecar's
    links reduced to their words, and the exporter's backslashes off, as
    ``read.parse_tab`` takes every tab."""
    return text.canonical(read.PLACED_CHIP.sub("", read.IN_PAGE_LINK.sub(r"\1", md))).strip()


def _reader_text(runs: Sequence[Piece]) -> str:
    """The block as the reader holds it in a thesis."""
    return _reader_md(spelled(runs)[0])


def _words_op(bid: str, node: ET.Element, at: int, new: str) -> dict:
    return {"op": "replace", "target": {"kind": "blocks", "ids": [bid]},
            "ifHash": node.get("h", ""), "ifRev": at,
            "with": {"as": "text", "from": {"kind": "inline", "content": new}}}


def _paragraph(source, bid: str) -> ET.Element:
    node = block(source, bid)
    if node.tag != "paragraph":
        raise Refused("block %s is a %s and not a paragraph" % (bid, node.tag))
    return node


def _heading(source, bid: str, glyph: str) -> Tuple[ET.Element, str]:
    """A level-three heading that opens with ``glyph``, and what follows it."""
    node = _paragraph(source, bid)
    text = page.inline(node)
    if node.get("heading") != "3" or not text.startswith(glyph + " "):
        raise Refused("block %s is not a %s heading: %r" % (bid, glyph, text[:60]))
    return node, text[len(glyph) + 1:].strip()


# -- reading back -----------------------------------------------------------

def _tab(*sections: Tuple[str, List[str]]) -> str:
    """The least tab the reader takes: its lineage, its id, and sections."""
    blocks_ = [read.LINEAGE + " root", "# here", "question: held · case · pressure 0 · backlog 0 "
               "· load 0"]
    for name, body in sections:
        blocks_.append("## %s" % name)
        blocks_.extend(body)
    return render.SEPARATOR.join(blocks_) + "\n"


#: the least metadata line an answer carries, for a read-back
ASSENT = "assent: none · held · provenance: thesis hinge"


def _thesis_tab(heading: str, text: str, *more: Tuple[str, List[str]]) -> str:
    """The least tab holding one answer: its heading as it will stand, glyph
    and all, its metadata line and one block of words; then any sections."""
    return _tab(("Thesis", ["### %s" % heading, ASSENT, text]), *more)


def _read_back(markdown: str, ids: Optional[Dict[str, str]] = None) -> dict:
    try:
        return read.parse_tab(markdown, ids)
    except read.ParseError as exc:
        raise Refused("the reader does not take what would be written: %s" % exc)


def _plain_block(words: str, what: str) -> None:
    """One paragraph of words that the reader takes as words: not a heading,
    a note, a list, a label line or a citation list's opening."""
    stripped = words.strip()
    if not stripped:
        raise Refused("%s is empty" % what)
    if render.BLANK_LINE.search(words) or "\n" in stripped:
        raise Refused("%s breaks a line, so it would be more than one block" % what)
    if re.match(r"^(#|>|[-*+] |\d+[.)] |%s|\|)" % re.escape(read.LINEAGE), stripped):
        raise Refused("%s opens like a heading, a note, a list or a table: %r"
                      % (what, stripped[:40]))
    for label in ("assent: ", "question: ", "suspended: ", "deadlock: ",
                  "attenuation: "):
        if stripped.startswith(label):
            raise Refused("%s opens with %r, which the reader takes as a line of "
                          "its own" % (what, label))
    if stripped in read.CITATION_HEADINGS:
        raise Refused("%s is a citation list's heading" % what)
    if read.CHIP.search(stripped):
        raise Refused("%s carries a chip; a chip is the renderer's to place" % what)


# -- glossary ---------------------------------------------------------------

def glossary_insert(after: str, word: str, body: str,
                    open_section: bool = False) -> Tuple[List[dict], str]:
    """A new entry, heading and body, after ``after``; with ``open_section``
    the ``## Glossary`` heading it opens with."""
    word = word.strip()
    if not word or "\n" in word or MARKUP.search(word):
        raise Refused("a glossary word is one line of plain letters: %r" % word)
    _plain_block(body, "the definition")
    if body.strip().startswith(render.SHADOW):
        raise Refused("the definition opens with %s, which the reader takes as a "
                      "shadow's pointer" % render.SHADOW)
    content = "### %s%s%s" % (render.glossary_heading(word), render.SEPARATOR, body.strip())
    got = _read_back(_tab(("Glossary", content.split(render.SEPARATOR))))
    if got["definitions"] != [{"word": word, "body": body.strip()}]:
        raise Refused("the entry does not read back as written: %r" % got["definitions"])
    if open_section:
        content = "## Glossary" + render.SEPARATOR + content
    op = {"op": "insert", "target": {"kind": "blocks", "ids": [after]},
          "side": "after", "source": appline.inline_markdown(content)}
    return [op], content


def glossary_replace(source, heading: str, body: str,
                     new: str) -> Tuple[List[dict], str, str]:
    """The body of an entry re-worded; the heading is read to say which."""
    _, word = _heading(source, heading, GLOSSARY)
    node = _paragraph(source, body)
    runs = pieces(node)
    if any(p.chip is not None for p in runs):
        raise Refused("block %s carries a chip, so it is a borrowing or a shadow "
                      "and not a definition's words" % body)
    old, _ = spelled(runs)
    after, _ = spelled(reworded(runs, new))
    _plain_block(after, "the definition")
    got = _read_back(_tab(("Glossary", ["### %s" % render.glossary_heading(word), after])))
    if got["definitions"] != [{"word": word, "body": text.canonical(after)}]:
        raise Refused("the entry does not read back as written: %r" % got["definitions"])
    return [_words_op(body, node, rev(source), new)], old, after


def glossary_delete(source, heading: str, body: Sequence[str]) -> List[dict]:
    """An entry withdrawn: its heading and every block under it, each guarded."""
    _heading(source, heading, GLOSSARY)
    if not body:
        raise Refused("name every block under the heading, or the entry's words "
                      "are left under whatever heading stands above them")
    return appline.guarded_delete(source, [heading] + list(body))


# -- terms ------------------------------------------------------------------

def _anchor(anchor: str) -> str:
    if not anchor.strip() or "\n" in anchor:
        raise Refused("an anchor is one run of the answer's words: %r" % anchor)
    return anchor


def thesis_text(source, bid: str) -> str:
    """A paragraph of an answer as the reader holds it."""
    return _reader_text(pieces(_paragraph(source, bid)))


def term_insert(after: str, title: str, to: str, to_tab: str,
                anchors: Sequence[str], thesis: Optional[str] = None,
                open_section: bool = False) -> Tuple[List[dict], str]:
    """A term's heading and its anchors after ``after``, the chip to the
    question it raises in the ``blocks`` map.

    ``thesis``, the answer's words as the reader holds them, is what every
    anchor must stand in verbatim — the rule ``anchor-substring`` holds on a
    graph, held here before the term reaches the page.
    """
    title = title.strip()
    if not title or "\n" in title or MARKUP.search(title):
        raise Refused("a term's headline is one line of plain letters: %r" % title)
    if not to.strip() or not to_tab.strip():
        raise Refused("a term names the question it raises and that question's tab")
    anchors = [_anchor(a) for a in anchors]
    if not anchors:
        raise Refused("a term carries at least one anchor")
    if thesis is not None:
        for anchor in anchors:
            if anchor not in thesis:
                raise Refused("the anchor is not a verbatim run of the answer's "
                              "words: %r" % anchor[:60])
    term = Term(title=title, to=to, anchors=list(anchors))
    lines = ["### %s" % render.term_line(term)] + [render.anchor_line(a) for a in anchors]
    ids = {render.chip_key(to): to}
    got = _read_back(_thesis_tab("%s answer" % THESIS,
                                 thesis if thesis is not None else " ".join(anchors),
                                 ("Terms", lines)), ids)
    read_terms = [t for th in got["theses"] for t in th["terms"]]
    if read_terms != [{"title": title, "to": to, "anchors": list(anchors)}]:
        raise Refused("the term does not read back as written: %r" % read_terms)
    content = render.SEPARATOR.join(lines)
    if open_section:
        content = "## Terms" + render.SEPARATOR + content
    chips = {render.chip_key(to): {"type": "mention", "ref": "file/%s" % to_tab}}
    op = {"op": "insert", "target": {"kind": "blocks", "ids": [after]},
          "side": "after", "source": appline.inline_markdown(content, chips)}
    return [op], content


def term_delete(source, heading: str, under: Sequence[str]) -> List[dict]:
    """A term withdrawn: its heading and its anchors, each guarded. Its chip in
    the answer and its item on the raised tab's header list go by their own
    writes, on their own tabs."""
    _heading(source, heading, TERM)
    if not under:
        raise Refused("name the term's anchor blocks, or they are left under "
                      "the heading above them")
    for bid in under:
        text = page.inline(_paragraph(source, bid))
        if not (text.startswith("*") or text.startswith(("suspended: ", "deadlock: ",
                                                         "attenuation: "))):
            raise Refused("block %s is not a line of a term: %r" % (bid, text[:60]))
    return appline.guarded_delete(source, [heading] + list(under))


def _items(source, header: str) -> List[Tuple[str, str]]:
    """(item id, the raiser its last chip names) per item of a header list."""
    out = []
    for bid, item in _item_nodes(source, header):
        chips = [p.chip for child in item if child.tag == "paragraph"
                 for p in pieces(child) if p.chip is not None]
        if not chips:
            raise Refused("item %s of the list carries no chip, so it is not a "
                          "header list's" % bid)
        out.append((bid, chips[-1].get("label", "")))
    return out


def _item_nodes(source, header: str) -> List[Tuple[str, ET.Element]]:
    """The items of the list ``header``, each with its full id — read from one
    parse, since an item's id is resolved against the ids printed above it."""
    found = blocks(source)
    ids = {id(n): bid for bid, n in found.items()}
    return [(ids.get(id(item), ""), item) for item in found[header]
            if item.tag == "listItem"]


def incoming_insert(source, header: str, anchor: str, raiser: str,
                    raiser_tab: str, after_item: Optional[str] = None
                    ) -> Tuple[List[dict], str]:
    """One item on the header list of the tab a term raises: the anchor, and
    the chip back to the raiser.

    The renderer orders the list by raiser and then by the term's headline,
    and the headline is not on the list; so the place is computed only where
    the raiser has no item yet, and otherwise named with ``after_item``.
    """
    node = block(source, header)
    if node.tag != "list":
        raise Refused("block %s is not the header list" % header)
    items = _items(source, header)
    if not items:
        raise Refused("the list %s holds no item in this read: it is not the header "
                      "list, or the read is partial" % header)
    line = render.incoming_item(_anchor(anchor), raiser)
    got = _read_back("%s root\n\n# here\n\n%s\n" % (read.LINEAGE, line),
                     {render.chip_key(raiser): raiser})
    if got["incoming"] != [(read.strip_chips(anchor), raiser)]:
        raise Refused("the item does not read back as written: %r" % got["incoming"])
    if after_item is None:
        if any(src == raiser for _, src in items):
            raise Refused("%s already has an item here, and which comes first is "
                          "its terms' headlines' order; name it with --after-item"
                          % raiser)
        before = [bid for bid, src in items if src < raiser]
        target, side = (before[-1], "after") if before else (items[0][0], "before")
    else:
        if after_item not in [bid for bid, _ in items]:
            raise Refused("%s is not an item of the list %s" % (after_item, header))
        target, side = after_item, "after"
    chips = {render.chip_key(raiser): {"type": "mention", "ref": "file/%s" % raiser_tab}}
    op = {"op": "insert", "target": {"kind": "blocks", "ids": [target]},
          "side": side, "source": appline.inline_markdown(line, chips)}
    return [op], line


def incoming_delete(source, header: str, item: str) -> List[dict]:
    """One item off a header list, guarded; the list's last item goes with the
    list, which the document keeps whole."""
    if block(source, header).tag != "list":
        raise Refused("block %s is not the header list" % header)
    items = _items(source, header)
    if item not in [bid for bid, _ in items]:
        raise Refused("%s is not an item of the list %s" % (item, header))
    return appline.guarded_delete(source, [header] if len(items) == 1 else [item])


# -- an answer's words ------------------------------------------------------

def thesis_replace(source, bid: str, new: str,
                   anchors: Sequence[str] = ()) -> Tuple[List[dict], str, str]:
    """A paragraph of an answer re-worded, its chips and marks kept.

    Every anchor given that stood in the paragraph must still stand in it:
    a term whose clause was re-worded out from under it is an edge the page
    no longer shows.
    """
    node = _paragraph(source, bid)
    if node.get("heading"):
        raise Refused("block %s is a heading" % bid)
    runs = pieces(node)
    old_md, _ = spelled(runs)
    after = reworded(runs, new, "write the block as markdown instead (--markdown)")
    new_md, _ = spelled(after)
    _plain_block(read.PLACED_CHIP.sub("", new_md), "the answer's paragraph")
    before, now = _reader_text(runs), _reader_text(after)
    for anchor in anchors:
        if anchor in before and anchor not in now:
            raise Refused("the anchor no longer stands in the paragraph: %r"
                          % anchor[:60])
    got = _read_back(_thesis_tab("%s answer" % THESIS, new_md))
    if [t["text"] for t in got["theses"]] != [now]:
        raise Refused("the paragraph does not read back as written")
    return [_words_op(bid, node, rev(source), new)], old_md, new_md


class Mark(NamedTuple):
    """One mark over one run of a paragraph's letters: its kind, its argument
    (a link's target, else empty) and the run, as offsets into the letters."""
    kind: str
    arg: str
    start: int
    end: int


def marks_of(runs: Sequence[Piece]) -> List[Mark]:
    """Every mark over the letters of ``runs``, each over the longest stretch
    of adjacent runs that carry it, in the order the marks open. A chip has
    no letters and breaks nothing: a link that runs through one is one link."""
    out: List[Mark] = []
    open_: Dict[Tuple[str, str], int] = {}
    at = 0
    for p in runs:
        end = at + len(p.text)
        for key in [k for k in open_ if k not in p.marks]:
            del open_[key]
        for key in p.marks:
            if key in open_:
                out[open_[key]] = out[open_[key]]._replace(end=end)
            else:
                open_[key] = len(out)
                out.append(Mark(key[0], key[1], at, end))
        at = end
    return [m for m in out if m.end > m.start]


def runs_of_markdown(markdown: str, marks: Tuple[Tuple[str, str], ...] = ()
                     ) -> List[Piece]:
    """The caller's markdown as the runs a view would print once it is on the
    page: the renderer's spelling and no other — a link as ``[words](target)``,
    emphasis with stars, code in backticks, a chip as its token, a literal
    mark behind a backslash. A chip comes back as a piece with no letters
    whose ``chip`` carries the token's key."""
    out: List[Piece] = []
    buf: List[str] = []

    def flush() -> None:
        if buf:
            out.append(Piece(marks, "".join(buf)))
            buf.clear()

    i = 0
    while i < len(markdown):
        c = markdown[i]
        escaped = c == "\\" and text.ESCAPE.match(markdown, i)
        if escaped:
            buf.append(markdown[i + 1])
            i += 2
            continue
        if c == "`":
            close = markdown.find("`", i + 1)
            if close > i:
                flush()
                out.append(Piece(marks + ((page.CODE, ""),), markdown[i + 1:close]))
                i = close + 1
                continue
        if c == "<":
            chip = read.CHIP.match(markdown, i)
            if chip:
                flush()
                out.append(Piece(marks, "", ET.Element("mention", key=chip.group(1))))
                i = chip.end()
                continue
        if c == "[":
            link = text.LINK.match(markdown, i)
            if link:
                flush()
                out.extend(runs_of_markdown(link.group(1),
                                            marks + ((page.LINK, link.group(2)),)))
                i = link.end()
                continue
        if c == "*":
            stars = 3 if markdown.startswith("***", i) else 2 if markdown.startswith("**", i) else 1
            close = markdown.find("*" * stars, i + stars)
            if close > i + stars:
                flush()
                added = {1: ((page.ITALIC, ""),), 2: ((page.BOLD, ""),),
                         3: ((page.BOLD, ""), (page.ITALIC, ""))}[stars]
                out.extend(runs_of_markdown(markdown[i + stars:close], marks + added))
                i = close + stars
                continue
        buf.append(c)
        i += 1
    flush()
    return out


def _chip_key(p: Piece) -> str:
    """The chip's key, from a view's mention (its label) or from a token."""
    return p.chip.get("key") or render.chip_key(p.chip.get("label", ""))


def _chip_places(runs: Sequence[Piece]) -> List[Tuple[int, str]]:
    """(offset into the letters, key) per chip, in order."""
    out: List[Tuple[int, str]] = []
    at = 0
    for p in runs:
        if p.chip is not None:
            out.append((at, _chip_key(p)))
        at += len(p.text)
    return out


def tab_letters(source) -> List[Tuple[str, str]]:
    """(block id, its letters) for every paragraph of a view, in page order:
    the characters the document's find counts over, a chip and a dropdown
    among them as atoms with none."""
    return [(bid, letters(pieces(node))) for bid, node in blocks(source).items()
            if node.tag == "paragraph"]


def _format_op(tab: str, offset: int, mark: Mark, words: str, verb: str) -> Optional[dict]:
    """One ``format`` operation for ``mark`` over ``words`` of a block that
    starts at ``offset`` in ``tab``, found by its words and the number the
    document counts to in order to reach them."""
    run = words[mark.start:mark.end]
    lead = len(run) - len(run.lstrip())
    run = run.strip()
    if not run:
        return None
    at = offset + mark.start + lead
    hit = next((r for r in text.occurrences(tab, run) if r.at == at), None)
    if hit is None:  # the run was read off this tab, so it stands on it
        raise Refused("no run of %r at %d of the tab, which the words were read off"
                      % (run, at))
    what: dict = {"type": mark.kind}
    if mark.kind == page.LINK and verb == "add":
        what["href"] = mark.arg
    return {"op": "format", "target": {"kind": "find", "text": run, "nth": hit.nth},
            verb: [what]}


def thesis_markdown(source, bid: str, new: str, anchors: Sequence[str] = ()
                    ) -> Tuple[List[dict], str, str, List[Tuple[str, str, str]],
                               List[Tuple[str, str, str]]]:
    """A paragraph of an answer given whole, as the markdown the renderer
    would spell it: what ``thesis_replace`` sends a caller to when the change
    reaches a link, a chip or a marked run.

    ``new`` is the paragraph in that spelling — a link as ``[words](target)``,
    a chip as its token. What goes to the document is what it takes: the
    marks the change takes off, as ``format`` operations; the letters, as one
    ``text`` replace, where they change; the marks the new words carry that
    did not survive, as ``format`` operations after. Each is found by its
    words counted over the tab, so the read is the tab's whole view. A chip
    is an edge and not the paragraph's to lose or to move: every chip the
    block held must stand in ``new`` where it stood, clear of the stretch the
    document rewrites. Returned with the ops: the old and new markdown, and
    the marks taken off and put on, each as its kind, its words and its
    target, to be said.
    """
    _whole(source)
    node = _paragraph(source, bid)
    if node.get("heading"):
        raise Refused("block %s is a heading" % bid)
    runs = pieces(node)
    if any(p.chip is not None and p.chip.tag == "dropdown" for p in runs):
        raise Refused("block %s carries a dropdown, which markdown cannot spell" % bid)
    old_md, _ = spelled(runs)
    new_md = new.strip()
    if "\n" in new_md:
        raise Refused("the words break a line, which the document would read "
                      "as a second block")
    # counted and not merely looked for: a chip said twice is one the
    # paragraph did not hold
    held, written = read.CHIP.findall(old_md), read.CHIP.findall(new_md)
    for key in held:
        if written.count(key) < held.count(key):
            raise Refused("the chip to %s stood in the paragraph and is not in "
                          "the new words; write it where it belongs, as "
                          "<?claude block %s?>" % (key[2:], key))
    for key in written:
        if written.count(key) > held.count(key):
            raise Refused("the new words carry a chip the paragraph did not "
                          "hold (%s); a new chip is a term's or a mention's to "
                          "bring" % key)
    _plain_block(read.PLACED_CHIP.sub("", new_md), "the answer's paragraph")
    before, now = _reader_text(runs), _reader_md(new_md)
    for anchor in anchors:
        if anchor not in now:
            raise Refused("the anchor %s in the paragraph: %r"
                          % ("no longer stands" if anchor in before
                             else "does not stand", anchor[:60]))
    got = _read_back(_thesis_tab("%s answer" % THESIS, new_md))
    if [t["text"] for t in got["theses"]] != [now]:
        raise Refused("the paragraph does not read back as written")
    ops, said_off, said_on = _mark_ops(source, bid, node, runs, new_md)
    return ops, old_md, new_md, said_off, said_on


def _chips_kept(old_md: str, new_md: str) -> None:
    """Every chip the block held stands in the new words, and no other does:
    counted and not merely looked for, since a chip said twice is one the
    block did not hold."""
    held, written = read.CHIP.findall(old_md), read.CHIP.findall(new_md)
    for key in held:
        if written.count(key) < held.count(key):
            raise Refused("the chip to %s stood in the block and is not in "
                          "the new words; write it where it belongs, as "
                          "<?claude block %s?>" % (key[2:], key))
    for key in written:
        if written.count(key) > held.count(key):
            raise Refused("the new words carry a chip the block did not "
                          "hold (%s); a new chip is a term's or a mention's to "
                          "bring" % key)


def _mark_ops(source, bid: str, node: ET.Element, runs: Sequence[Piece], new_md: str
              ) -> Tuple[List[dict], List[Tuple[str, str, str]], List[Tuple[str, str, str]]]:
    """What the document takes for a block given whole as markdown: the marks
    the change takes off, the letters as one ``text`` replace, the marks the
    new words carry that did not survive — each found by its words counted
    over the whole tab."""
    after = runs_of_markdown(new_md)
    old, fresh = letters(runs), letters(after)
    changed = old != fresh
    s0, e0 = _span(old, fresh) if changed else (len(old) + 1, len(old) + 1)
    shift = len(fresh) - len(old)

    def meets(start: int, end: int) -> bool:
        return changed and s0 <= end and e0 >= start

    def moved(at: int) -> int:
        return at if at < s0 else at + shift

    # a chip is an atom the text write keeps where the document holds it,
    # so it may neither meet the stretch nor stand elsewhere in the new words
    for at, key in _chip_places(runs):
        if meets(at, at):
            raise Refused("the chip to %s stands in or against the stretch the document "
                          "rewrites (from the first changed letter to the last), which a "
                          "text write cannot carry; change the words around it, or "
                          "write the tab whole" % key[2:])
    if sorted((moved(at), key) for at, key in _chip_places(runs)) != sorted(_chip_places(after)):
        raise Refused("a chip stands elsewhere in the new words than the document holds "
                      "it; a text write keeps every chip where it stood")

    was, wanted = marks_of(runs), marks_of(after)
    survive = [m._replace(start=moved(m.start), end=moved(m.end))
               for m in was if not meets(m.start, m.end)]
    kept = [m for m in survive if m in wanted]
    off = [m for m in was if m._replace(start=moved(m.start), end=moved(m.end)) not in kept
           or meets(m.start, m.end)]
    on = [m for m in wanted if m not in kept]

    tab = tab_letters(source)
    offsets: Dict[str, int] = {}
    at = 0
    for block_id, words in tab:
        offsets[block_id] = at
        at += len(words) + 1  # the separator the page puts between two blocks
    if bid not in offsets:
        raise Refused("block %s is not a paragraph of the view" % bid)
    tab_old = "\n".join(words for _, words in tab)
    tab_new = "\n".join(fresh if block_id == bid else words for block_id, words in tab)

    ops: List[dict] = []
    said_off: List[Tuple[str, str, str]] = []
    said_on: List[Tuple[str, str, str]] = []
    for m in off:
        op = _format_op(tab_old, offsets[bid], m, old, "remove")
        if op is not None:
            ops.append(op)
            said_off.append((m.kind, op["target"]["text"], m.arg))
    if changed:
        ops.append(_words_op(bid, node, rev(source), fresh))
    for m in on:
        op = _format_op(tab_new, offsets[bid], m, fresh, "add")
        if op is not None:
            ops.append(op)
            said_on.append((m.kind, op["target"]["text"], m.arg))
    if not ops:
        raise Refused("the new words are the paragraph as it stands")
    return ops, said_off, said_on


# -- any block of words -----------------------------------------------------

def _flatten(value, path: str = "", out: Optional[Dict[str, object]] = None
             ) -> Dict[str, object]:
    out = {} if out is None else out
    if isinstance(value, dict):
        for key, inner in value.items():
            _flatten(inner, "%s.%s" % (path, key) if path else str(key), out)
    elif isinstance(value, list):
        for i, inner in enumerate(value):
            _flatten(inner, "%s[%d]" % (path, i), out)
    else:
        out[path] = value
    return out


def one_field(before: dict, after: dict) -> str:
    """The one field of a parsed tab that differs between two readings of it,
    as its path (``hinge.question``, ``theses[0].text``, ``notes[1].body``).

    What decides whether a block may be re-worded in place is not which part
    it is but what the reader makes of the tab afterwards: one field changed
    and nothing else, or the words have moved something the writer did not
    name — a paragraph that opens like a label, a line the reader files
    elsewhere — and the write is refused.
    """
    a, b = _flatten(before), _flatten(after)
    changed = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
    if not changed:
        raise Refused("the new words are the block as it stands")
    if len(changed) > 1:
        raise Refused("the change reaches more than one field of the tab (%s), so it "
                      "is not one block's re-wording; write the section or the tab whole"
                      % ", ".join(changed[:4]))
    return changed[0]


def _top_block_of(source, bid: str) -> Optional[str]:
    """The id of the top-level block that holds ``bid``: itself, or the
    list or blockquote it stands in."""
    root = ET.fromstring(page.view_xml(source))
    session = ""
    for child in root:
        own: Optional[str] = None
        for node in child.iter():
            full, session = page.expand_id(node.get("id", ""), session)
            if own is None and full:
                own = full
            if full == bid:
                return own
    return None


def _as_page(runs: Sequence[Piece], labels: Dict[str, str]) -> str:
    """The block as the page read spells it, a chip as its label: what the
    reader is given, and what a read-back of the tab substitutes."""
    out: List[page.Run] = []
    for p in runs:
        if p.chip is None:
            out.append((p.marks, page.literal(p.text, p.marks)))
        elif p.chip.tag == "dropdown":
            out.append((p.marks, p.chip.text or ""))
        else:
            out.append((p.marks, labels.get(_chip_key(p), p.chip.get("label", ""))))
    return page.spell(out)


def _labels_of(source) -> Dict[str, str]:
    """Chip key to label for every mention the view carries: the map the
    reader takes a chip's label back through, which the document's file
    list supplies to a rebuild and the page itself supplies here."""
    root = ET.fromstring(page.view_xml(source))
    return {render.chip_key(node.get("label", "")): node.get("label", "")
            for node in root.iter("mention") if node.get("label")}


def _one_field_after(source, bid: str, old: str, new: str,
                     ids: Optional[Dict[str, str]] = None) -> str:
    """The one field that changes when block ``bid``, spelled ``old`` as the
    page reads it, is spelled ``new``: the whole tab read back before and
    after, through the reader, and compared."""
    ids = _labels_of(source) if ids is None else ids
    top = _top_block_of(source, bid)
    try:
        blocks_ = page.blocks(source)
    except ValueError as exc:
        raise Refused(str(exc))
    before_md = render.SEPARATOR.join(md for _, md in blocks_) + "\n"
    after_parts: List[str] = []
    hit = False
    for key, md in blocks_:
        if key == top:
            if old not in md:
                raise Refused("block %s is not spelled inside its block as the page "
                              "reads it" % bid)
            md = md.replace(old, new, 1)
            hit = True
        after_parts.append(md)
    if not hit:
        raise Refused("block %s is not a block of the view" % bid)
    after_md = render.SEPARATOR.join(after_parts) + "\n"
    before, after = _read_back(before_md, ids), _read_back(after_md, ids)
    field = one_field(before, after)
    m = re.match(r"theses\[(\d+)\]\.text$", field)
    if m:
        i = int(m.group(1))
        now = after["theses"][i].get("text", "")
        thesis = before["theses"][i]
        for edge in thesis.get("terms", []) + thesis.get("mentions", []):
            for anchor in edge.get("anchors", []):
                if anchor and anchor not in now:
                    raise Refused("the anchor no longer stands in the paragraph: %r"
                                  % anchor[:60])
    return field


def _words_block(source, bid: str) -> Tuple[ET.Element, List[Piece], Dict[str, str]]:
    _whole(source)
    node = _paragraph(source, bid)
    if node.get("heading"):
        raise Refused("block %s is a heading: an answer's headline is thesis headline's "
                      "to re-word, and a word is its glossary entry's" % bid)
    runs = pieces(node)
    labels = {_chip_key(p): p.chip.get("label", "") for p in runs if p.chip is not None}
    if _as_page(runs, labels) != page.inline(node):
        raise Refused("block %s cannot be spelled as the page reads it" % bid)
    return node, runs, labels


def words_replace(source, bid: str, new: str, ids: Optional[Dict[str, str]] = None
                  ) -> Tuple[List[dict], str, str, str]:
    """Any block of words re-worded in place as ``text``, chips and marks
    kept: a hinge's question half, a note, a paragraph the other writers
    do not name. Decided by its read-back, not by which part it is: the
    whole tab is read before and after, and the write is refused unless
    one field alone differs. A thesis keeps the anchors of its terms.
    Returned with the op: the old and new markdown, and the field."""
    node, runs, labels = _words_block(source, bid)
    old_md, _ = spelled(runs)
    after = reworded(runs, new, "write the block as markdown instead "
                                "(words replace --markdown)")
    new_md, _ = spelled(after)
    field = _one_field_after(source, bid, _as_page(runs, labels), _as_page(after, labels), ids)
    return [_words_op(bid, node, rev(source), new)], old_md, new_md, field


def words_markdown(source, bid: str, new: str, ids: Optional[Dict[str, str]] = None
                   ) -> Tuple[List[dict], str, str, str, List[Tuple[str, str, str]],
                              List[Tuple[str, str, str]]]:
    """Any block of words given whole as the markdown the renderer would
    spell it: what ``words_replace`` sends a caller to when the change
    reaches a link, a chip or a marked run. The same read-back decides it,
    and what goes to the document is what ``thesis_markdown`` sends."""
    node, runs, labels = _words_block(source, bid)
    if any(p.chip is not None and p.chip.tag == "dropdown" for p in runs):
        raise Refused("block %s carries a dropdown, which markdown cannot spell" % bid)
    old_md, _ = spelled(runs)
    new_md = new.strip()
    if "\n" in new_md:
        raise Refused("the words break a line, which the document would read "
                      "as a second block")
    _chips_kept(old_md, new_md)
    after = runs_of_markdown(new_md)
    field = _one_field_after(source, bid, _as_page(runs, labels), _as_page(after, labels), ids)
    ops, said_off, said_on = _mark_ops(source, bid, node, runs, new_md)
    return ops, old_md, new_md, field, said_off, said_on


# -- a note -----------------------------------------------------------------

def note_insert(source, after: str, body: str) -> Tuple[List[dict], str, str]:
    """A note inserted after block ``after``, which must be the last block of
    its section: the renderer writes a section's notes at its end, so a note
    put anywhere else would move at the next body write. Read back as one
    note of that section. Returned with the op: the section and the block."""
    try:
        blocks_ = page.blocks(source)
    except ValueError as exc:
        raise Refused(str(exc))
    ids = [bid for bid, _ in blocks_]
    if after not in ids:
        raise Refused("the read holds no block %s" % after)
    at = ids.index(after)
    section: Optional[str] = None
    for _, md in blocks_[:at + 1]:
        if md.startswith("## "):
            section = md[3:].strip()
    if section is None:
        raise Refused("block %s stands above the first section, where the renderer "
                      "writes no note" % after)
    if at + 1 < len(blocks_) and not blocks_[at + 1][1].startswith("## "):
        last = next((ids[i] for i in range(at + 1, len(ids))
                     if i + 1 == len(ids) or blocks_[i + 1][1].startswith("## ")), ids[-1])
        raise Refused("block %s is not the last block of %s; the renderer puts a note "
                      "at the end of its section, so it goes after %s" % (after, section, last))
    _plain_block(body, "the note")
    content = "> " + body.strip()
    got = _read_back(_tab((section, [content])))
    if got.get("notes") != [{"section": section.lower(), "body": body.strip()}]:
        raise Refused("the note does not read back as written: %r" % got.get("notes"))
    op = {"op": "insert", "target": {"kind": "blocks", "ids": [after]},
          "side": "after", "source": appline.inline_markdown(content)}
    return [op], section, content


# -- an answer's headline ---------------------------------------------------

def _whole(source) -> None:
    """Refuse a read that is not the tab whole: a search, or a view since a
    later rev, shows some blocks and says nothing of the rest."""
    root = ET.fromstring(page.view_xml(source))
    if root.get("sinceRev") != "0" or root.find(".//gap") is not None:
        raise Refused("the read is not the whole tab, so an application that "
                      "says the headline may stand outside it; a whole view is "
                      "needed (sinceRev 0)")


def _application_lines(source) -> List[str]:
    """The id of every application's line on the tab: the block under each
    ``⚙`` heading of the Applications section."""
    out: List[str] = []
    inside = headed = False
    for bid, markdown in page.blocks(source):
        # as ``read._sections`` and ``read._subsections`` take them: the
        # section's name with case folded, the heading by its glyph alone
        if markdown.startswith("## "):
            inside, headed = markdown[3:].strip().lower() == APPLICATIONS.lower(), False
        elif inside and markdown.startswith("### "):
            headed = markdown.startswith("### " + appline.MARK)
        elif inside and headed and not markdown.startswith(">"):
            out.append(bid)
            headed = False
    return out


def thesis_headline(source, heading: str, title: str) -> Tuple[List[dict], str, str]:
    """An answer's headline re-worded, and with it every application line on
    the tab that says it.

    The headline stands once as the answer's heading and again on each
    application that derives from the answer, which is how the reader tells
    whose the application is: a heading re-worded alone would leave those
    lines naming an answer the tab no longer has. So the read must be the tab
    whole, and each line is rebuilt as ``application.py replace --thesis``
    would write it.
    """
    title = title.strip()
    if not title or "\n" in title or MARKUP.search(title):
        raise Refused("an answer's headline is one line of plain letters: %r" % title)
    if "·" in title:
        # an application line parts its fields with it, and says the headline
        # among them; one that carried it would read back as another answer's
        raise Refused("an answer's headline carries no ·, which parts the fields "
                      "of the application lines that say it: %r" % title)
    _whole(source)
    node, old = _heading(source, heading, THESIS)
    for bid, other in blocks(source).items():
        if (bid != heading and other.tag == "paragraph" and other.get("heading") == "3"
                and page.inline(other) == "%s %s" % (THESIS, title)):
            raise Refused("another answer on the tab is already headed %r, and an "
                          "application could not say which it derives from" % title)
    new = "%s %s" % (THESIS, title)
    after, _ = spelled(reworded(pieces(node), new))
    got = _read_back(_thesis_tab(after, "words"))
    if [t["title"] for t in got["theses"]] != [title]:
        raise Refused("the headline does not read back as written: %r"
                      % [t["title"] for t in got["theses"]])
    ops = [_words_op(heading, node, rev(source), new)]
    for bid in _application_lines(source):
        # whose the line is, before its shape is judged: another answer's line
        # that would not round-trip is not a reason to refuse this headline
        if appline.parse(page.inline(block(source, bid)))["thesis"] != old:
            continue
        fields = appline.read_line(source, bid)
        fields["thesis"] = title
        if appline.parse(appline.line(fields))["thesis"] != title:
            raise Refused("the headline does not read back off an application "
                          "line as written: %r" % title)
        ops.append(appline.replace_op(fields))
    return ops, "%s %s" % (THESIS, old), after


# -- a hinge's provenance ---------------------------------------------------

def hinge_amend(source, bid: str, day: str, by: str,
                origin: str) -> Tuple[List[dict], str, str]:
    """An ``amended <day> by <who> from <what>`` clause on a hinge's thesis
    half. The block must be the provenance line — it names a model, a harness
    and a canon reference — and the clause is appended, never written over."""
    if not DAY.match(day):
        raise Refused("an amendment is dated YYYY-MM-DD: %r" % day)
    for what, value in (("who", by), ("from what", origin)):
        if not value.strip() or "\n" in value or MARKUP.search(value) or "·" in value:
            raise Refused("%s is one run of plain words: %r" % (what, value))
    node = _paragraph(source, bid)
    runs = pieces(node)
    old = letters(runs)
    missing = [mark for mark in spec.PROVENANCE if mark not in old.lower()]
    if missing:
        raise Refused("block %s is not a hinge's provenance; it names no %s"
                      % (bid, ", no ".join(m[:-1] for m in missing)))
    if any(p.chip is not None for p in runs):
        raise Refused("block %s carries a chip, which a provenance does not" % bid)
    new = render.amended(old, day, by.strip(), origin.strip())
    old_md, _ = spelled(runs)
    new_md, _ = spelled(reworded(runs, new, "write the block as markdown instead "
                                            "(words replace --markdown)"))
    if new_md != render.amended(old_md, day, by.strip(), origin.strip()):
        raise Refused("the amendment does not land at the end of the line")
    got = _read_back(_tab(("Hinge", ["### %s" % render.HINGE_THESIS, new_md])))
    if got.get("hinge", {}).get("thesis") != text.canonical(new_md):
        raise Refused("the provenance does not read back as written")
    return [_words_op(bid, node, rev(source), new)], old_md, new_md
