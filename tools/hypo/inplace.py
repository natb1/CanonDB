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

A paragraph of an answer whose change does reach a mark is written a third
way, when the caller asks for it: whole, as **markdown**, in the renderer's
spelling of it. The caller then says where every link and every mark goes,
so nothing is left for the document to place; the chips are not his to
drop, and each one the block held must stand in what he wrote.

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
    for p in runs:
        end = at + len(p.text)
        if (p.chip is not None or (p.marks and p.text)) and s0 <= end and e0 >= at:
            what = ("a chip to %s" % p.chip.get("label", "?") if p.chip is not None
                    else "the marked run %r" % p.text)
            raise Refused("%s stands in or against the stretch the document rewrites "
                          "(from the first changed letter to the last), and would lose "
                          "its mark or carry it onto the new words; %s" % (what, remedy))
        at = end
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


def thesis_markdown(source, bid: str, new: str, anchors: Sequence[str] = ()
                    ) -> Tuple[List[dict], str, str, List[Tuple[str, str]],
                               List[Tuple[str, str]]]:
    """A paragraph of an answer written whole, as the markdown the renderer
    would spell it: what ``thesis_replace`` sends a caller to when the change
    reaches a link, a chip or a marked run.

    ``new`` is the paragraph in that spelling — a link as ``[words](target)``,
    a chip as its token. A chip is an edge and not the paragraph's to lose, so
    every chip the block held must stand in ``new``, and none it did not hold
    may. The links are the caller's to place, and the ones the new words drop
    and add are returned, each as its words and its target, to be said.
    """
    node = _paragraph(source, bid)
    if node.get("heading"):
        raise Refused("block %s is a heading" % bid)
    runs = pieces(node)
    if any(p.chip is not None and p.chip.tag == "dropdown" for p in runs):
        raise Refused("block %s carries a dropdown, which markdown cannot spell" % bid)
    old_md, chips = spelled(runs)
    new_md = new.strip()
    if "\n" in new_md:
        raise Refused("the words break a line, which the document would read "
                      "as a second block")
    # counted and not merely looked for: a chip said twice is one the
    # paragraph did not hold, and the blocks map would carry it once
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
    had, has = text.LINK.findall(old_md), text.LINK.findall(new_md)
    dropped = [link for link in had if link not in has]
    added = [link for link in has if link not in had]
    op = {"op": "replace", "target": {"kind": "blocks", "ids": [bid]},
          "ifHash": node.get("h", ""), "ifRev": rev(source),
          "with": appline.inline_markdown(new_md, chips)}
    return [op], old_md, new_md, dropped, added


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
    new_md, _ = spelled(reworded(runs, new))
    if new_md != render.amended(old_md, day, by.strip(), origin.strip()):
        raise Refused("the amendment does not land at the end of the line")
    got = _read_back(_tab(("Hinge", ["### %s" % render.HINGE_THESIS, new_md])))
    if got.get("hinge", {}).get("thesis") != text.canonical(new_md):
        raise Refused("the provenance does not read back as written")
    return [_words_op(bid, node, rev(source), new)], old_md, new_md
