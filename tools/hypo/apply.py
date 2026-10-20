"""The operations that put a rendered tab into the document.

The renderer produces a tab's markdown and the links that belong on it, but
neither can be sent as it stands: an operation names **block ids**, and only the
document mints those. So writing a tab is two calls, and this is what turns the
renderer's output into the payload of each.

    body_ops    replace every top-level block of a tab with the rendered body
    link_ops    put each sidecar link on the words it belongs on
    unlink_ops  take off a mark the sidecar no longer asks for

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
from typing import Dict, List, NamedTuple, Optional
from xml.etree import ElementTree

from . import page, render, text, verify
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
_CHIP_KEY = re.compile(r"<\?claude block ([0-9A-Za-z_]+)\?>")

#: the rev of the read an outline came from, on its ``doc`` element
_REV = re.compile(r"<doc\b[^>]*\brev='(\d+)'")


def outline_rev(xml: str) -> Optional[int]:
    """The rev of the read an outline came from, which a whole-block write
    names as ``ifRev``.

    A replace that names every block of a tab, or every block of a section,
    can carry no hash — a hash is one block's — and the document refuses a
    whole-block operation that names no guard at all. So the rev is the
    guard: the tab as the outline showed it, and no later. An outline with
    none is one the document did not print, and the write is refused rather
    than sent unguarded.
    """
    m = _REV.search(xml or "")
    return int(m.group(1)) if m else None


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
            if el.tag == "gap":  # a sinceRev read folds what did not change
                out.append(Block(id="", kind="gap", heading=0, text=""))
            continue
        bid, prefix = page.expand_id(bid, prefix)
        out.append(Block(id=bid, kind=el.tag,
                         heading=int(el.get("heading", 0) or 0),
                         text=" ".join("".join(el.itertext()).split())))
        prefix = _carried(el, prefix)
    return out


def _carried(el, prefix: str) -> str:
    """The session prefix as it stands after a block. A read prints a full id on
    whatever carries one first, a run of text inside a block included, and
    abbreviates every id after it: so the block after a nested full id takes that
    id's prefix, and not the prefix its own block's id was printed with."""
    for sub in el.iter():
        sid = sub.get("id", "")
        if sid and "." in sid and not sid.startswith("."):
            prefix = sid.split(".")[0]
    return prefix


def _scan(body: str) -> List[Block]:
    """The same, by regex, for an outline the parser will not take."""
    out: List[Block] = []
    prefix = ""
    for m in _ELEMENT.finditer(body):
        attrs = dict(_ATTR.findall(m.group("attrs") or ""))
        bid = attrs.get("id", "")
        if not bid:
            if m.group("kind") == "gap":
                out.append(Block(id="", kind="gap", heading=0, text=""))
            continue
        bid, prefix = page.expand_id(bid, prefix)
        words = _TAG.sub("", _CHIP.sub("", m.group("text") or ""))
        out.append(Block(id=bid, kind=m.group("kind"),
                         heading=int(attrs.get("heading", 0) or 0),
                         text=" ".join(words.split())))
        for name, value in _ATTR.findall(m.group("text") or ""):
            if name == "id" and "." in value and not value.startswith("."):
                prefix = value.split(".")[0]   # as _carried() reads a parsed block
    return out


#: what an outline puts where it stopped printing a block's words.
_ELIDED = "…"

#: a heading line of the rendered body, and the chip that closes one. The
#: marks and then a space, as the document and the reader take a heading; a
#: paragraph opening ``#1`` is a paragraph, and counting it made the outline
#: and the render disagree on every heading of the tab.
_HEADING = re.compile(r"^(#{1,6}) (.*)$")

#: what ``headings`` maps a text to when two headings of the tab spell it: a
#: target naming it means neither, and resolves to nothing
AMBIGUOUS = ""


def rendered_headings(body: str) -> List[str]:
    """The heading text of each heading in a rendered tab, in order.

    The chip that closes a term heading comes off: it is a token before the
    write and a block id after it, and a target names only the words.
    """
    out: List[str] = []
    for chunk in (body or "").split("\n\n"):
        m = _HEADING.match(chunk.strip())
        if m:  # whitespace collapsed, as ``parse_outline`` collapses the outline's
            out.append(" ".join(_CHIP.sub("", m.group(2)).split()))
    return out


def headings(graph: Graph, tab: str, outline: List[Block]) -> Dict[str, str]:
    """Heading text -> block id, paired by position.

    An outline elides a block's words after a few characters, so a heading
    cannot be found on the page by the text a target names. It does not have
    to be: the body is what the renderer produced, so the nth heading of the
    outline is the nth heading of the render. The elided text is kept as a
    check on that pairing rather than as the means of it — if the two have
    drifted, the page is not what was rendered, and ``verify`` says so.
    """
    qid = next((q.id for q in graph.questions if q.tab == tab), None)
    if qid is None:
        return {}
    full = rendered_headings(render.body(graph, qid))
    seen = [block for block in outline if block.heading]
    if len(full) != len(seen):
        return {}  # a heading more or fewer, and the pairing means nothing
    out: Dict[str, str] = {}
    for words, block in zip(full, seen):
        if not spells(words, block.text):
            return {}  # the page is not this render; nothing here can be trusted
        out[words] = AMBIGUOUS if words in out else block.id
    return out


def spells(words: str, shown: str) -> bool:
    """Whether an outline's text for a block is consistent with the words the
    renderer produced for it.

    An outline prints the opening of each text run and elides the rest, so a
    block edited in place across sessions — one run per edit — comes back as
    several openings with an ellipsis after each: ``◆ Whe`` + ``re a calen…``
    + ``; a writte…``. The first piece has to open the words, and each later
    piece has to follow, in order, after the one before; nothing is said about
    what the ellipses hide."""
    pieces = shown.split(_ELIDED)
    if not words.startswith(pieces[0]):
        return False
    at = len(pieces[0])
    for piece in pieces[1:]:
        if not piece:
            continue
        found = words.find(piece, at)
        if found < 0:
            return False
        at = found + len(piece)
    return True


def resolve(graph: Graph, target: str, by_tab: Dict[str, List[Block]],
            artifact: str, own_tab: str,
            cache: Optional[Dict[str, Dict[str, str]]] = None) -> Optional[str]:
    """A sidecar target — ``#<tab>.<heading>`` — as an href the viewer follows.
    ``cache`` holds the headings of each tab already paired, so a tab with
    many links renders once and not once per link."""
    tab, _, heading = target.lstrip("#").partition(".")
    outline = by_tab.get(tab)
    if outline is None:
        return None
    if cache is not None and tab in cache:
        found = cache[tab]
    else:
        found = headings(graph, tab, outline)
        if cache is not None:
            cache[tab] = found
    # a target names the prefix the renderer could promise: a term heading goes
    # on to an arrow and a chip, which are a block id once the tab is written.
    # So the arrow is tried after the words themselves, and nothing looser: one
    # term's title may open another's, and the first heading that merely began
    # with the words was taken for it
    bid = found.get(heading)
    if bid is None:
        bid = found.get("%s →" % heading)
    if not bid:  # no heading spells it, or two do
        return None
    if tab == own_tab:
        return "#%s" % bid
    if not artifact:  # a bare fragment would land on this tab, the wrong page
        return None
    return "%s#%s.%s" % (artifact, tab, bid)


def body_ops(graph: Graph, qid: str, outline: List[Block],
             rev: Optional[int]) -> List[dict]:
    """Replace the whole tab with the rendered body: one operation.

    Every top-level block is named, so the tab is left holding exactly what the
    renderer produced and nothing that was there before. ``rev`` is the
    outline's (``outline_rev``), and the operation's guard.
    """
    if rev is None:
        raise Unresolved(["%s: the outline carries no rev, and a whole-block replace "
                          "names it as its guard" % qid])
    ids = [block.id for block in outline if block.id]
    if not ids:
        raise Unresolved(["%s: the outline names no block to replace" % qid])
    folded = [block for block in outline if block.kind in ("gap", "gone")]
    if folded:
        # a sinceRev read shows what changed and folds the rest into a gap;
        # replacing only the blocks it names would leave the folded ones on
        # the page beside the fresh body
        raise Unresolved(["%s: the outline folds or retires %d block(s) it "
                          "does not show, so it is not the whole tab"
                          % (qid, len(folded))])
    if all(block.heading for block in outline):
        # a tab is headings and the prose under them; an outline of headings
        # alone is a reduced one, kept for resolving link targets. Replacing
        # only the blocks it names would leave the prose of the old tab behind.
        raise Unresolved(["%s: the outline holds headings only, so it is not "
                          "the whole tab" % qid])
    payload = render.links(graph, qid)
    with_ = {"as": "markdown",
             "from": {"kind": "inline", "content": render.body(graph, qid)}}
    if payload["blocks"]:
        with_["blocks"] = payload["blocks"]
    return [{"op": "replace", "target": {"kind": "blocks", "ids": ids},
             "ifRev": rev, "with": with_}]


def _section_chunks(body: str) -> List[Tuple[str, List[str]]]:
    """(section heading, its blocks) per ``## `` section of a rendered body,
    the heading block first; the masthead comes first under ``''``."""
    out: List[Tuple[str, List[str]]] = [("", [])]
    for chunk in body.split(render.SEPARATOR):
        chunk = chunk.strip("\n")
        if not chunk:
            continue
        m = _HEADING.match(chunk.strip())
        if m and len(m.group(1)) == 2:
            out.append((" ".join(m.group(2).split()), [chunk]))
        else:
            out[-1][1].append(chunk)
    return out


def section_headings(body: str, section: str) -> List[str]:
    """The heading text of each heading inside one ``## `` section of a
    rendered body, the section's own first; empty where the body has no
    such section."""
    wanted = section.strip().lower()
    for name, chunks in _section_chunks(body):
        if name.lower() == wanted:
            return [" ".join(_CHIP.sub("", m.group(2)).split())
                    for m in (_HEADING.match(chunk.strip()) for chunk in chunks) if m]
    return []


def section_ops(graph: Graph, qid: str, outline: List[Block], rev: Optional[int],
                section: str) -> List[dict]:
    """Replace one ``## `` section of a tab with its rendered blocks: one
    operation, naming the blocks the outline shows from the section's heading
    to the next section's.

    The path between a part written in place and a tab written whole. A body
    write mints new ids for every block on the tab and so retires every link
    into it; this retires only the links into the section, and ``relink``
    finds no other stale, since every other block keeps its id. The chips
    sent beside the markdown are the section's own.
    """
    if rev is None:
        raise Unresolved(["%s: the outline carries no rev, and a whole-block replace "
                          "names it as its guard" % qid])
    wanted = section.strip().lower()
    body = render.body(graph, qid)
    rendered = next((chunks for name, chunks in _section_chunks(body)
                     if name and name.lower() == wanted), None)
    if rendered is None:
        raise Unresolved(["%s: the render has no section %r" % (qid, section)])
    start = next((i for i, block in enumerate(outline)
                  if block.heading == 2 and block.text
                  and wanted.startswith(block.text.rstrip(_ELIDED).lower())
                  and (block.text.endswith(_ELIDED) or block.text.lower() == wanted)),
                 None)
    if start is None:
        raise Unresolved(["%s: the page has no section %r; a section the page lacks "
                          "is written with the body" % (qid, section)])
    end = next((i for i in range(start + 1, len(outline)) if outline[i].heading == 2),
               len(outline))
    span = outline[start:end]
    if any(block.kind in ("gap", "gone") for block in span):
        raise Unresolved(["%s: the outline folds or retires a block inside %r, so it "
                          "does not show the section whole" % (qid, section)])
    ids = [block.id for block in span if block.id]
    markdown = render.SEPARATOR.join(rendered)
    keys = set(_CHIP_KEY.findall(markdown))
    chips = {key: value for key, value in render.links(graph, qid)["blocks"].items()
             if key in keys}
    with_ = {"as": "markdown", "from": {"kind": "inline", "content": markdown}}
    if chips:
        with_["blocks"] = chips
    return [{"op": "replace", "target": {"kind": "blocks", "ids": ids},
             "ifRev": rev, "with": with_}]


def link_ops(graph: Graph, qid: str, by_tab: Dict[str, List[Block]],
             artifact: str = "", section: Optional[str] = None) -> List[dict]:
    """One ``format`` operation per link the sidecar names.

    The words are found rather than addressed: a link goes on a run of
    characters inside a block, and the ``nth`` the renderer computed is what
    tells one run from another where the same words stand more than once.

    After a write of one ``section`` alone, the links owed are the ones that
    write took off or retired: those standing in the section, whose blocks
    are new, and those leading into it, whose targets are. Every other link
    on the tab stands as it was, and sending it again would be a no-op the
    ack cannot tell from a link that never landed.
    """
    rendered = render.body(graph, qid)
    entries = render.links(graph, qid, rendered=rendered)["links"]
    q = graph.get(qid)
    own = q.tab if q is not None else ""
    if section is not None:
        page_ = render.page_text(graph, qid, rendered)
        spans = render.section_spans(page_)
        name = next((n for n in spans if n and n.lower() == section.strip().lower()), None)
        if name is None:
            raise Unresolved(["%s: the render has no section %r" % (qid, section)])
        inside = spans[name]
        heads = section_headings(rendered, section)

        def leads_in(target: str) -> bool:
            heading = target.lstrip("#").partition(".")[2]
            return any(h == heading or h.startswith(heading + " ") for h in heads)

        entries = [e for e in entries
                   if (e.get("at") is not None and inside[0] <= e["at"] < inside[1])
                   or leads_in(e["target"])]
    ops: List[dict] = []
    missing: List[str] = []
    paired: Dict[str, Dict[str, str]] = {}
    for entry in entries:
        find = entry.get("find")
        if not find:
            missing.append("%s: no occurrence of %r on the page"
                           % (entry["kind"], entry["anchor"]))
            continue
        tab = entry["target"].lstrip("#").partition(".")[0]
        if tab != own and not artifact:
            # a fragment alone leads to the tab it stands on: sent, the link
            # would land on this page rather than the one it names
            missing.append("%s: %s leaves the tab, and the graph names no "
                           "artifact to leave it by" % (entry["kind"], entry["target"]))
            continue
        href = resolve(graph, entry["target"], by_tab, artifact, own, paired)
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


def unlink_ops(graph: Graph, qid: str, page: str) -> List[dict]:
    """One ``format`` operation per in-page link the sidecar does not name.

    A mark outlives what put it there. A definition moves to another tab, an
    anchor is re-scoped, the run a link belongs on stops being the run it was
    applied to — and the words stay, carrying a mark to a heading that may no
    longer exist. Nothing but the page can see that, which is the other half
    of what ``verify`` reads the page for; this is how the page is brought
    back to what the sidecar asks for without rewriting a line of it.

    The page is the argument rather than the outlines, because what is being
    removed is on the page and nowhere else: a graph file never held a link.
    """
    plain, _, _, _, extra = verify.account(graph, qid, page)
    ops: List[dict] = []
    for start, end, _href in extra:
        words = plain[start:end]
        hit = next((run for run in text.occurrences(plain, words)
                    if run.at == start), None)
        if hit is None:  # the span was read off this page, so it stands on it
            raise Unresolved(["%s: no run of %r at %d" % (qid, words, start)])
        ops.append({"op": "format",
                    "target": {"kind": "find", "text": words, "nth": hit.nth},
                    "remove": [{"type": "link"}]})
    return ops


def wanted_tabs(graph: Graph, qid: str) -> List[str]:
    """The tabs whose outlines ``link_ops`` needs: this one, and every tab a
    link on it points at."""
    q = graph.get(qid)
    tabs = {q.tab} if q is not None else set()
    for entry in render.links(graph, qid)["links"]:
        tabs.add(entry["target"].lstrip("#").partition(".")[0])
    return sorted(tabs)
