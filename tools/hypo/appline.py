"""One application, written where it stands on the page.

A tab reaches the document whole only through a body write, which mints new
ids for every block on the tab and so retires every link into it from
anywhere else. An application is one heading and one line, and a change to
it — a new link, a reworded description, a new application, one withdrawn —
touches those two blocks and nothing else. This writes that change as the
operations of one prose ``update``: a ``replace`` of the line, an ``insert``
of a heading and its line after a block, or the ``delete`` of both, each
guarded by the hash the document printed for the block.

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
from typing import Dict, List, Optional

from . import page, read, render
from .model import STANDINGS, Application

#: the heading an application stands under, as the renderer writes it
MARK = "⚙"

#: containers whose own text is not a block's text
_BLOCKS = ("paragraph", "listItem", "cell", "row", "table", "list",
           "blockquote", "gone", "pending", "gap", "hit")


class Refused(Exception):
    """The change cannot be written as asked; the message says why."""


def _text(node: ET.Element) -> str:
    """The characters a block's hash is taken over: every run of text, with a
    mention contributing nothing."""
    out: List[str] = []
    if node.text and node.tag not in _BLOCKS[:7]:
        out.append(node.text)
    for child in node:
        if child.tag == "mention":
            pass
        elif child.tag == "dropdown":
            out.append(child.text or "")
        else:
            out.append(_text(child))
        if child.tail:
            out.append(child.tail)
    return "".join(out)


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


def blocks(source) -> Dict[str, ET.Element]:
    """Every block of a read by its full id, short ids resolved."""
    root = ET.fromstring(page.view_xml(source))
    out: Dict[str, ET.Element] = {}
    session = ""
    for node in root.iter():
        bid = node.get("id", "")
        if not bid or node.tag not in ("paragraph", "list", "table", "blockquote"):
            continue
        if bid.startswith("."):
            bid = session + bid
        elif "." in bid:
            session = bid.split(".")[0]
        out[bid] = node
    return out


def block(source, bid: str) -> ET.Element:
    """The block ``bid`` of a read, checked against its hash."""
    found = blocks(source).get(bid)
    if found is None:
        raise Refused("the read holds no block %s" % bid)
    _unhit(found)
    if found.get("h") and digest(found) != found.get("h"):
        raise Refused("block %s does not hash to the h the document printed "
                      "(%s, read %s): the read is not the page" %
                      (bid, found.get("h"), digest(found)))
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
    """The line the renderer writes for these fields."""
    standing = fields.get("standing", "").strip()
    if standing not in STANDINGS:
        raise Refused("standing %r is not one of %s" % (standing, ", ".join(STANDINGS)))
    shown = "%s (%s)" % (standing, fields["clause"]) if fields.get("clause") else standing
    app = Application(name=fields.get("name", ""), what=fields["what"],
                      link=fields.get("link", ""), standing=standing,
                      note=fields.get("note", ""))
    return render.application_line(app, fields["thesis"], shown)


def read_line(source, bid: str) -> Dict[str, str]:
    """The fields of the application line ``bid``, with its id and hash; the
    line is rebuilt and must come out as the page holds it."""
    node = block(source, bid)
    text = page.inline(node)
    fields = parse(text)
    if line(fields) != text:
        raise Refused("block %s does not round-trip through the renderer; "
                      "change it by a body write instead" % bid)
    fields.update({"id": bid, "h": node.get("h", "")})
    return fields


def _markdown(content: str) -> dict:
    return {"as": "markdown", "from": {"kind": "inline", "content": content}}


def replace_op(fields: Dict[str, str]) -> dict:
    return {"op": "replace", "target": {"kind": "blocks", "ids": [fields["id"]]},
            "ifHash": fields["h"], "with": _markdown(line(fields))}


def insert_op(after: str, name: str, fields: Dict[str, str]) -> dict:
    if not name.strip():
        raise Refused("an application needs a name")
    content = "### %s %s\n\n%s" % (MARK, name.strip(), line(fields))
    return {"op": "insert", "target": {"kind": "blocks", "ids": [after]},
            "side": "after", "source": _markdown(content)}


def delete_ops(source, heading: str, line_id: str) -> List[dict]:
    """The heading and its line, each guarded; the heading must be an
    application's and the line must be one."""
    head = block(source, heading)
    if not page.inline(head).startswith(MARK + " "):
        raise Refused("block %s is not an application heading" % heading)
    read_line(source, line_id)
    body = block(source, line_id)
    return [{"op": "delete", "target": {"kind": "blocks", "ids": [bid]},
             "ifHash": node.get("h", "")}
            for bid, node in ((heading, head), (line_id, body))]
