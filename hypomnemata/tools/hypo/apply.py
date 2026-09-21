"""The operations that put a rendered tab into the document.

The renderer produces a tab's markdown and the links that belong on it, but
neither can be sent as it stands: an operation names **block ids**, and only the
document mints those. So writing a tab is two calls, and this is what turns the
renderer's output into the payload of each.

    body_ops   replace every top-level block of a tab with the rendered body
    link_ops   put each sidecar link on the words it belongs on

The second is not optional and not something to remember: a body write alone
leaves a tab whose every in-page link is gone, which is what happened, and
nothing downstream could see it. Both payloads come from here so that neither
can be composed by hand and the second cannot be forgotten separately from the
first.

An outline is what the document hands back — a read with ``projection:
outline``, or the ``xml`` of a write's ack. It is parsed rather than trusted:
what is wanted from it is the top-level ids in order, and the block id of every
heading, since that is what a link's target names.
"""

from __future__ import annotations

import re
from typing import Dict, List, NamedTuple, Optional, Tuple
from xml.etree import ElementTree

from . import render
from .model import Graph

#: the wrapper an outline comes in, and the one thing that must not be parsed.
#: A doctype is how an XML parser is made to expand entities without end or
#: fetch what it was not asked for; an outline has no use for one, so it is
#: refused rather than defended against.
_DOC = re.compile(r"</?doc\b[^>]*>")
_DOCTYPE = re.compile(r"<!(?:DOCTYPE|ENTITY)\b", re.IGNORECASE)

#: One element of an outline. ``heading`` is the level the document reports,
#: 0 for a block that is not a heading.
class Block(NamedTuple):
    id: str
    kind: str
    heading: int
    text: str


#: A top-level element of an outline: `<paragraph id='x.0' h='ab12' heading='1'>`
#: …text…`</paragraph>`, or an empty one — `<gap blocks='2'/>`, `<gone id=…/>`.
_ELEMENT = re.compile(
    r"<(?P<kind>[A-Za-z][\w-]*)(?P<attrs>[^>]*?)"
    r"(?:/>|>(?P<text>.*?)</(?P=kind)>)",
    re.DOTALL)
_ATTR = re.compile(r"(\w+)='([^']*)'")
_TAG = re.compile(r"<[^>]*>")

#: A chip, as an outline prints one. It stands in a heading, so it has to come
#: off before the heading's words are compared with a link's target.
_CHIP = re.compile(r"<\?claude block [0-9A-Za-z_]+\?>")


class Unresolved(Exception):
    """A link whose target names a heading no outline accounts for.

    A target the caller cannot find is a link that never lands, so this refuses
    rather than emitting an operation that would silently do nothing.
    """

    def __init__(self, missing: List[str]) -> None:
        super().__init__("; ".join(missing))
        self.missing = missing


def parse_outline(xml: str) -> List[Block]:
    """The top-level blocks of one tab, in order.

    Ids are printed in full once and abbreviated to ``.<clock>`` after that, so
    the session prefix carries forward from the last full id seen. A chip is a
    processing instruction, which the parser drops for us — and must be
    dropped, since a heading ends in one and a target names only the words.
    """
    body = _DOC.sub("", xml or "").strip()
    if _DOCTYPE.search(body):
        raise Unresolved(["the outline declares a doctype or an entity"])
    try:
        root = ElementTree.fromstring("<outline>%s</outline>" % body)
    except ElementTree.ParseError:
        return _scan(body)  # an unescaped character should not lose the tab
    out: List[Block] = []
    prefix = ""
    for el in root:
        bid = el.get("id", "")
        if not bid:
            continue
        bid, prefix = _expand(bid, prefix)
        out.append(Block(id=bid, kind=el.tag,
                         heading=int(el.get("heading", 0) or 0),
                         text=" ".join("".join(el.itertext()).split())))
    return out


def _expand(bid: str, prefix: str) -> Tuple[str, str]:
    """A short id against the session prefix of the last full one."""
    if bid.startswith("."):
        return prefix + bid, prefix
    return bid, bid.split(".")[0]


def _scan(body: str) -> List[Block]:
    """The same, by regex, for an outline the parser will not take."""
    out: List[Block] = []
    prefix = ""
    for m in _ELEMENT.finditer(body):
        attrs = dict(_ATTR.findall(m.group("attrs") or ""))
        bid = attrs.get("id", "")
        if not bid:
            continue
        bid, prefix = _expand(bid, prefix)
        words = _TAG.sub("", _CHIP.sub("", m.group("text") or ""))
        out.append(Block(id=bid, kind=m.group("kind"),
                         heading=int(attrs.get("heading", 0) or 0),
                         text=" ".join(words.split())))
    return out


def headings(outline: List[Block]) -> Dict[str, str]:
    """Heading text -> block id, first one wins.

    A link's target names a heading by the words it opens with, glyph and all,
    because the chip that closes it is a token before the write and a block id
    after it. So the match is on the prefix the renderer could promise.
    """
    found: Dict[str, str] = {}
    for block in outline:
        if block.heading and block.text:
            found.setdefault(block.text, block.id)
    return found


def _resolve(target: str, by_tab: Dict[str, List[Block]],
             artifact: str, own_tab: str) -> Optional[str]:
    """A sidecar target — ``#<tab>.<heading>`` — as an href the viewer follows."""
    tab, _, heading = target.lstrip("#").partition(".")
    outline = by_tab.get(tab)
    if outline is None:
        return None
    found = headings(outline)
    bid = found.get(heading)
    if bid is None:  # the heading may carry a chip the outline spells out
        for words, candidate in found.items():
            if words.startswith(heading):
                bid = candidate
                break
    if bid is None:
        return None
    if tab == own_tab:
        return "#%s" % bid
    return "%s#%s.%s" % (artifact, tab, bid)


def body_ops(graph: Graph, qid: str, outline: List[Block]) -> List[dict]:
    """Replace the whole tab with the rendered body: one operation.

    Every top-level block is named, so the tab is left holding exactly what the
    renderer produced and nothing that was there before.
    """
    ids = [block.id for block in outline if block.id]
    if not ids:
        raise Unresolved(["%s: the outline names no block to replace" % qid])
    payload = render.links(graph, qid)
    with_ = {"as": "markdown",
             "from": {"kind": "inline", "content": render.body(graph, qid)}}
    if payload["blocks"]:
        with_["blocks"] = payload["blocks"]
    return [{"op": "replace", "target": {"kind": "blocks", "ids": ids},
             "with": with_}]


def link_ops(graph: Graph, qid: str, by_tab: Dict[str, List[Block]],
             artifact: str = "") -> List[dict]:
    """One ``format`` operation per link the sidecar names.

    The words are found rather than addressed: a link goes on a run of
    characters inside a block, and the ``nth`` the renderer computed is what
    tells one run from another where the same words stand more than once.
    """
    entries = render.links(graph, qid)["links"]
    q = graph.get(qid)
    own = q.tab if q is not None else ""
    ops: List[dict] = []
    missing: List[str] = []
    for entry in entries:
        find = entry.get("find")
        if not find:
            missing.append("%s: no occurrence of %r on the page"
                           % (entry["kind"], entry["anchor"]))
            continue
        href = _resolve(entry["target"], by_tab, artifact, own)
        if href is None:
            missing.append("%s: %s" % (entry["kind"], entry["target"]))
            continue
        ops.append({"op": "format",
                    "target": {"kind": "find", "text": find["text"],
                               "nth": find["nth"]},
                    "add": [{"type": "link", "href": href}]})
    if missing:
        raise Unresolved(missing)
    return ops


def wanted_tabs(graph: Graph, qid: str) -> List[str]:
    """The tabs whose outlines ``link_ops`` needs: this one, and every tab a
    link on it points at."""
    q = graph.get(qid)
    tabs = {q.tab} if q is not None else set()
    for entry in render.links(graph, qid)["links"]:
        tabs.add(entry["target"].lstrip("#").partition(".")[0])
    return sorted(tabs)
