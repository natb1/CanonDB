"""The other line-shaped parts of a tab, written where they stand.

``appline`` writes an application in place, and the reason it exists holds for
every part of a tab that is a line or two under a heading of its own: a body
write mints new ids for every block on the tab and so retires every link into
it, while the part itself touches two or three blocks. A glossary entry is a
heading and a paragraph; a term is a heading, its anchors, and one item on the
header list of the tab it raises; a paragraph of an answer is one block of
words; a hinge's provenance is one line that an amendment lengthens. Each is
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

Every whole-block ``replace`` and ``delete`` carries both guards the document
asks for: the block's ``h`` and the ``rev`` of the read that showed it.

What is not written here: the links. A term's anchor in the answer carries a
chip beside it and a link to the term's heading, and its header item a link
back; both name block ids that only the insert's acknowledgement holds. They
are owed after the write, and this says so rather than send an operation that
would land nowhere.
"""

from __future__ import annotations

import difflib
import re
import xml.etree.ElementTree as ET
from typing import Dict, List, NamedTuple, Optional, Sequence, Tuple

from . import page, read, render, spec
from .appline import Refused, block, blocks, rev

#: the glyphs that open each part's heading, as the renderer writes them
GLOSSARY, TERM = "≡", "▸"

#: marks the page reads back as markup, and so must not arrive as letters
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
        if tag == "mention":
            out.append(Piece(marks, "", child))
        elif tag == "dropdown":
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
            runs_out.append((p.marks, "<?claude block %s?>" % key))
        else:
            runs_out.append((p.marks, p.text))
    return page._spell(runs_out), chips


def reworded(runs: Sequence[Piece], new: str) -> List[Piece]:
    """The runs after a ``text`` write of ``new`` over them.

    The old letters and the new are aligned, and every chip and every marked
    run has to stand inside a stretch the two share — which is where the
    document keeps it. Where one does not, the document either refuses the
    write or puts the mark somewhere nobody chose, and this refuses first.
    """
    old = letters(runs)
    if "\n" in new:
        raise Refused("the words break a line, which the document would read "
                      "as a second block")
    same = [(a, b, size) for a, b, size in
            difflib.SequenceMatcher(None, old, new, autojunk=False).get_matching_blocks()
            if size]

    def where(at: int, end: int) -> Optional[int]:
        for a, b, size in same:
            if a <= at and end <= a + size:
                return b + (at - a)
        return None

    for a, b, size in _changes(old, new, same):
        if MARKUP.search(new[b:b + size]):
            raise Refused("the new words carry %r, which the page reads back as "
                          "a mark; write it as a body write instead"
                          % MARKUP.search(new[b:b + size]).group())
    kept: List[Tuple[int, int, Piece]] = []
    at = 0
    for p in runs:
        end = at + len(p.text)
        if p.chip is not None or (_fixed(p) and p.text):
            moved = where(at, end)
            if moved is None:
                what = ("a chip to %s" % p.chip.get("label", "?") if p.chip is not None
                        else "the marked run %r" % p.text)
                raise Refused("%s stands inside the changed words; change the words "
                              "around it, or write the tab whole" % what)
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


def _changes(old: str, new: str, same) -> List[Tuple[int, int, int]]:
    """The stretches of ``new`` that are not the old letters: (old at, new at,
    length in new)."""
    out = []
    a0 = b0 = 0
    for a, b, size in list(same) + [(len(old), len(new), 0)]:
        if b > b0:
            out.append((a0, b0, b - b0))
        a0, b0 = a + size, b + size
    return out


def _reader_text(runs: Sequence[Piece]) -> str:
    """The block as the reader holds it in a thesis: chips off, and the
    sidecar's links reduced to their words."""
    md, _ = spelled(runs)
    return read.PLACED_CHIP.sub("", read.IN_PAGE_LINK.sub(r"\1", md)).strip()


def _words_op(bid: str, node: ET.Element, at: int, new: str) -> dict:
    return {"op": "replace", "target": {"kind": "blocks", "ids": [bid]},
            "ifHash": node.get("h", ""), "ifRev": at,
            "with": {"as": "text", "from": {"kind": "inline", "content": new}}}


def _markdown(content: str, chips: Optional[Dict[str, dict]] = None) -> dict:
    out = {"as": "markdown", "from": {"kind": "inline", "content": content}}
    if chips:
        out["blocks"] = chips
    return out


def _guarded_delete(source, ids: Sequence[str]) -> List[dict]:
    at = rev(source)
    return [{"op": "delete", "target": {"kind": "blocks", "ids": [bid]},
             "ifHash": block(source, bid).get("h", ""), "ifRev": at}
            for bid in ids]


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
    blocks_ = ["⌂ root", "# here", "question: held · case · pressure 0 · backlog 0 "
               "· load 0 · requires: nothing"]
    for name, body in sections:
        blocks_.append("## %s" % name)
        blocks_.extend(body)
    return render.SEPARATOR.join(blocks_) + "\n"


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
    if re.match(r"^(#|>|[-*+] |\d+[.)] |⌂|\|)", stripped):
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
          "side": "after", "source": _markdown(content)}
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
    if got["definitions"] != [{"word": word, "body": after}]:
        raise Refused("the entry does not read back as written: %r" % got["definitions"])
    return [_words_op(body, node, rev(source), new)], old, after


def glossary_delete(source, heading: str, body: Sequence[str]) -> List[dict]:
    """An entry withdrawn: its heading and every block under it, each guarded."""
    _heading(source, heading, GLOSSARY)
    if not body:
        raise Refused("name every block under the heading, or the entry's words "
                      "are left under whatever heading stands above them")
    return _guarded_delete(source, [heading] + list(body))


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
    from .model import Term  # the renderer's own shape, for its own spelling
    term = Term(title=title, to=to, anchors=list(anchors))
    lines = ["### %s" % render.term_line(term)] + [render.anchor_line(a) for a in anchors]
    ids = {render.chip_key(to): to}
    got = _read_back(_tab(("Thesis", ["### ◆ answer",
                                      "assent: none · held · provenance: thesis hinge",
                                      thesis if thesis is not None else " ".join(anchors)]),
                          ("Terms", lines)), ids)
    read_terms = [t for th in got["theses"] for t in th["terms"]]
    if read_terms != [{"title": title, "to": to, "anchors": list(anchors)}]:
        raise Refused("the term does not read back as written: %r" % read_terms)
    content = render.SEPARATOR.join(lines)
    if open_section:
        content = "## Terms" + render.SEPARATOR + content
    chips = {render.chip_key(to): {"type": "mention", "ref": "file/%s" % to_tab}}
    op = {"op": "insert", "target": {"kind": "blocks", "ids": [after]},
          "side": "after", "source": _markdown(content, chips)}
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
    return _guarded_delete(source, [heading] + list(under))


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
    line = render.incoming_item(_anchor(anchor), raiser)
    got = _read_back("⌂ root\n\n# here\n\n%s\n" % line, {render.chip_key(raiser): raiser})
    if got["incoming"] != [(read._strip_chips(anchor), raiser)]:
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
          "side": side, "source": _markdown(line, chips)}
    return [op], line


def incoming_delete(source, header: str, item: str) -> List[dict]:
    """One item off a header list, guarded; the list's last item goes with the
    list, which the document keeps whole."""
    if block(source, header).tag != "list":
        raise Refused("block %s is not the header list" % header)
    items = _items(source, header)
    if item not in [bid for bid, _ in items]:
        raise Refused("%s is not an item of the list %s" % (item, header))
    return _guarded_delete(source, [header] if len(items) == 1 else [item])


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
    after = reworded(runs, new)
    new_md, _ = spelled(after)
    _plain_block(read.PLACED_CHIP.sub("", new_md), "the answer's paragraph")
    before, now = _reader_text(runs), _reader_text(after)
    for anchor in anchors:
        if anchor in before and anchor not in now:
            raise Refused("the anchor no longer stands in the paragraph: %r"
                          % anchor[:60])
    got = _read_back(_tab(("Thesis", ["### ◆ answer",
                                      "assent: none · held · provenance: thesis hinge",
                                      new_md])))
    if [t["text"] for t in got["theses"]] != [now]:
        raise Refused("the paragraph does not read back as written")
    return [_words_op(bid, node, rev(source), new)], old_md, new_md


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
    if got.get("hinge", {}).get("thesis") != new_md:
        raise Refused("the provenance does not read back as written")
    return [_words_op(bid, node, rev(source), new)], old_md, new_md
