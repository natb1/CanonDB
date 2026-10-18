"""One application, written where it stands on the page.

A tab reaches the document whole only through a body write, which mints new
ids for every block on the tab and so retires every link into it from
anywhere else. An application is one heading and one line, and a change to
it — a new link, a reworded description, a new application, one withdrawn —
touches those two blocks and nothing else. This writes that change as the
operations of one prose ``update``: a ``replace`` of the line, an ``insert``
of a heading and its line after a block, or the ``delete`` of both, each
guarded by the hash the document printed for the block and by the ``rev`` of
the read that printed it. The document takes a whole-block ``replace`` or
``delete`` only with both: the hash says the block is the one read, the rev
says which read that was.

The line is the renderer's (``render.application_line``), and an existing
line is read with the reader's own pattern (``read.APPLICATION_LINE``), so
what is written in place is what a body render would have written. The block
is taken from a read of the page — a ``search`` or a ``view`` — and checked
against its hash before anything is built from it: the document's ``h`` is the
first eight hex digits of sha256 over the block's text, so a read that was
copied by hand and drifted is refused rather than written back.
"""

from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Sequence

from . import page, read, render
from .model import GLYPHS, STANDINGS, Application, Question, Thesis

#: the heading an application stands under, as the renderer writes it
MARK = GLYPHS["application"]

#: containers whose own text is not a block's text
_CONTAINERS = ("paragraph", "listItem", "cell", "row", "table", "list",
               "blockquote")


class Refused(Exception):
    """The change cannot be written as asked; the message says why."""


def _text(node: ET.Element) -> str:
    """The characters a block's hash is taken over: every run of text, with a
    chip contributing nothing — a mention, and a dropdown too, whose word is
    the enum's and not the block's letters. The question line hashes as
    ``question:  · …``, the state's word left out."""
    out: List[str] = []
    if node.text and node.tag not in _CONTAINERS:
        out.append(node.text)
    for child in node:
        if child.tag not in ("mention", "dropdown"):
            out.append(_text(child))
        if child.tail:
            out.append(child.tail)
    return "".join(out)


def _chips_alone(node: ET.Element) -> bool:
    """Whether a paragraph holds chips and no letters: a Cited by line that
    names one tab, a glossary entry's lone reference."""
    return not _text(node).strip() and any(
        child.tag in ("mention", "dropdown") for child in node.iter())


def digest(node: ET.Element) -> str:
    """What the document prints as the block's ``h``."""
    return hashlib.sha256(_text(node).encode("utf-8")).hexdigest()[:8]


def _unhit(node: ET.Element) -> None:
    """A search wraps what it found in ``hit``; the page holds the words, so
    each hit's text is folded back into the run it interrupted."""
    for parent in list(node.iter()):
        i = 0
        while i < len(parent):
            child = parent[i]
            if child.tag != "hit":
                i += 1
                continue
            if len(child):
                raise Refused("a search hit spans marks; read the block with a view")
            text = (child.text or "") + (child.tail or "")
            if i == 0:
                parent.text = (parent.text or "") + text
            else:
                parent[i - 1].tail = (parent[i - 1].tail or "") + text
            parent.remove(child)


def rev(source) -> int:
    """The ``rev`` of the read: what a whole-block write names as ``ifRev``."""
    found = ET.fromstring(page.view_xml(source)).get("rev", "")
    if not found.isdigit():
        raise Refused("the read carries no rev; a whole-block write needs the "
                      "rev of the read that showed the block")
    return int(found)


def blocks(source) -> Dict[str, ET.Element]:
    """Every block of a read by its full id, short ids resolved. A list's
    items are blocks of their own: one can be written or dropped without the
    rest of its list."""
    try:
        root = ET.fromstring(page.view_xml(source))
    except (ET.ParseError, ValueError) as exc:
        raise Refused("the read is not a view or a search result: %s" % exc)
    out: Dict[str, ET.Element] = {}
    session = ""
    for node in root.iter():
        # the session prefix is printed once, on whatever carries an id
        # first — a retired block's ``gone`` as often as not — so it is
        # taken from every id and not only from a block's
        bid, session = page.expand_id(node.get("id", ""), session)
        if bid and node.tag in ("paragraph", "list", "listItem", "table",
                                "blockquote"):
            out[bid] = node
    return out


def block(source, bid: str, parsed: Optional[Dict[str, ET.Element]] = None) -> ET.Element:
    """The block ``bid`` of a read, checked against its hash; ``parsed`` is
    ``blocks(source)``, where the caller has parsed the read already."""
    found = (blocks(source) if parsed is None else parsed).get(bid)
    if found is None:
        raise Refused("the read holds no block %s" % bid)
    _unhit(found)
    # a paragraph's h is over its letters; a list's, an item's or a table's is
    # over its shape, which a read does not print, so what is checked there is
    # every paragraph inside it
    for node in found.iter("paragraph"):
        if _chips_alone(node):
            # a paragraph of chips and no letters: the document's hash of it
            # is its own and no read can rebuild it, so the h it printed is
            # the guard, and there are no words a hand copy could get wrong
            continue
        if node.get("h") and digest(node) != node.get("h"):
            raise Refused("block %s does not hash to the h the document printed "
                          "(%s, read %s): the read is not the page" %
                          (node.get("id", bid), node.get("h"), digest(node)))
    return found


def parse(line: str) -> Dict[str, str]:
    """An application line's fields, by the reader's own pattern."""
    match = read.APPLICATION_LINE.match(line)
    if not match:
        raise Refused("not an application line: %r" % line[:80])
    fields = {k: (match.group(k) or "") for k in
              ("what", "thesis", "link", "standing", "clause", "note")}
    fields["standing"] = fields["standing"].strip()
    return fields


def line(fields: Dict[str, str]) -> str:
    """The line the renderer writes for these fields — and reads back as
    them: a field carrying the separator, or a line break, or a clause with
    a bracket, would come back as other fields, under another answer, or not
    at all."""
    standing = fields.get("standing", "").strip()
    if standing not in STANDINGS:
        raise Refused("standing %r is not one of %s" % (standing, ", ".join(STANDINGS)))
    for field in ("what", "thesis", "link"):
        if "·" in (fields.get(field) or ""):
            raise Refused("the %s carries ·, which parts the fields of the line; "
                          "the note alone may" % field)
    shown = "%s (%s)" % (standing, fields["clause"]) if fields.get("clause") else standing
    app = Application(name=fields.get("name", ""), what=fields["what"],
                      link=fields.get("link", ""), standing=standing,
                      note=fields.get("note", ""))
    out = render.application_line(app, fields["thesis"], shown)
    if "\n" in out:
        raise Refused("a field breaks a line, and the line is one block")
    want = {k: (fields.get(k) or "") for k in ("what", "thesis", "link", "clause", "note")}
    want.update(standing=standing, note=want["note"].strip())
    if parse(out) != want:
        raise Refused("the line does not read back as its fields: %r" % out)
    return out


def read_line(source, bid: str) -> Dict[str, str]:
    """The fields of the application line ``bid``, with its id and hash; the
    line is rebuilt and must come out as the page holds it."""
    node = block(source, bid)
    text = page.inline(node)
    fields = parse(text)
    if line(fields) != text:
        raise Refused("block %s does not round-trip through the renderer; "
                      "change it by a body write instead" % bid)
    fields.update({"id": bid, "h": node.get("h", ""), "rev": rev(source)})
    return fields


def clause_of(source, thesis_title: str, standing: str) -> str:
    """The discharge clause an inserted application carries, read off the tab
    and given by nobody.

    The renderer derives it (``render.discharge_clause``) from who answers
    the question and the state of the answer the application rests on. The
    first is on the question line, the second on the metadata line under the
    answer's heading, and both are in a view of the tab; a search for the
    application lines shows neither, so an insert takes the view. Written by
    hand it went stale: eight notes once said it, and six were wrong at once.
    """
    answerer: Optional[str] = None
    state: Optional[str] = None
    order = list(blocks(source).items())
    for i, (_bid, node) in enumerate(order):
        if node.tag != "paragraph":
            continue
        words = read.IN_PAGE_LINK.sub(r"\1", page.inline(node))
        if words.startswith("question: ") and not node.get("heading"):
            try:
                answerer = read.question_line(words).group("answerer") or ""
            except read.ParseError as exc:
                raise Refused(str(exc))
        elif (node.get("heading") == "3"
              and words == "%s %s" % (GLYPHS["thesis"], thesis_title.strip())):
            below = next((n for _, n in order[i + 1:] if n.tag == "paragraph"), None)
            found = read.ASSENT_LINE.match(
                read.IN_PAGE_LINK.sub(r"\1", page.inline(below))) if below is not None else None
            if not found:
                raise Refused("no metadata line under the answer %r, whose state the "
                              "discharge clause is read off" % thesis_title)
            state = found.group("state").strip()
    if answerer is None:
        raise Refused("the read holds no question line, which names who answers; an "
                      "insert takes the tab's view, since the discharge clause is read "
                      "off it")
    if state is None:
        raise Refused("the read holds no answer headed %r, whose state the discharge "
                      "clause is read off" % thesis_title)
    q = Question(id="", tab="", body="", question="", state="", kind="", pressure=0,
                 answerer=answerer)
    return render.discharge_clause(q, Thesis(title=thesis_title, text="", state=state),
                                   Application(name="", what="", standing=standing.strip()))


def inline_markdown(content: str, chips: Optional[Dict[str, dict]] = None) -> dict:
    """The source of an insert or a replace: markdown, and the blocks map its
    chips are written against where it has any."""
    out: dict = {"as": "markdown", "from": {"kind": "inline", "content": content}}
    if chips:
        out["blocks"] = chips
    return out


def guarded_delete(source, ids: Sequence[str]) -> List[dict]:
    """A delete per block, each guarded by the block's hash and the read's rev."""
    at = rev(source)
    return [{"op": "delete", "target": {"kind": "blocks", "ids": [bid]},
             "ifHash": block(source, bid).get("h", ""), "ifRev": at}
            for bid in ids]


def replace_op(fields: Dict[str, str]) -> dict:
    return {"op": "replace", "target": {"kind": "blocks", "ids": [fields["id"]]},
            "ifHash": fields["h"], "ifRev": fields["rev"],
            "with": inline_markdown(line(fields))}


SECTION = "Applications"
# the sections the renderer writes after Applications, in its order
AFTER_SECTION = ("Cited by", "Hinge")


def opens_section(source, after: str) -> bool:
    """Whether an application inserted after block ``after`` must open the
    Applications section, which the tab does not have yet: true when the view
    holds neither that heading nor any application. The renderer puts the
    section ahead of Cited by and Hinge, so ``after`` must be the last block
    of the section that stands before it, or the tab would read back with
    the new section out of its place."""
    root = ET.fromstring(page.view_xml(source))
    own = set(id(child) for child in root)
    top: List[tuple] = []
    session = ""
    for node in root.iter():
        # the session prefix carries over every id, nested ones included,
        # as ``blocks`` reads it
        bid, session = page.expand_id(node.get("id", ""), session)
        if bid and id(node) in own and node.tag != "gone":
            top.append((bid, node))
    names = [(i, page.inline(node).strip()) for i, (_, node) in enumerate(top)
             if node.get("heading") == "2"]
    if any(name == SECTION for _, name in names) or any(
            node.get("heading") == "3" and page.inline(node).startswith(MARK + " ")
            for _, node in top):
        return False
    ids = [bid for bid, _ in top]
    if after not in ids:
        raise Refused("the tab has no %s section, and block %s is not one of the "
                      "view's top-level blocks, so where the section opens cannot "
                      "be told" % (SECTION, after))
    at = ids.index(after)
    named = dict(names)
    following = named.get(at + 1) if at + 1 < len(top) else None
    preceding = next((name for i, name in reversed(names) if i <= at), None)
    last = at + 1 == len(top)
    if (not last and following not in AFTER_SECTION) or preceding in AFTER_SECTION:
        raise Refused("the tab has no %s section, and the renderer opens it ahead "
                      "of %s: insert after the last block before the first of them"
                      % (SECTION, " and ".join(AFTER_SECTION)))
    return True


def insert_op(after: str, name: str, fields: Dict[str, str],
              opens: bool = False) -> dict:
    """An application's heading and line after block ``after``; with
    ``opens``, preceded by the Applications heading the tab lacks."""
    if not name.strip():
        raise Refused("an application needs a name")
    if "\n" in name:
        raise Refused("an application's name is one line, its heading")
    content = "### %s %s\n\n%s" % (MARK, name.strip(), line(fields))
    if opens:
        content = "## %s\n\n%s" % (SECTION, content)
    return {"op": "insert", "target": {"kind": "blocks", "ids": [after]},
            "side": "after", "source": inline_markdown(content)}


def delete_ops(source, heading: str, line_id: str) -> List[dict]:
    """The heading and its line, each guarded; the heading must be an
    application's and the line must be one."""
    head = block(source, heading)
    if not page.inline(head).startswith(MARK + " "):
        raise Refused("block %s is not an application heading" % heading)
    read_line(source, line_id)
    order = list(blocks(source))
    if order.index(line_id) != order.index(heading) + 1:
        # another application's line under this one's heading: both would be
        # left half there, each hashing as it should
        raise Refused("block %s is not the line under the heading %s" % (line_id, heading))
    return guarded_delete(source, [heading, line_id])
