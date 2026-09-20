"""The inverse of the renderer: a rendered tab back into a graph file.

Every tool downstream works on a graph file, and until now that file was typed
out by hand from a reading of the artifact. Nothing compared the two, so a
question mistyped or a thesis paraphrased passed every check and was then
written back over the real one. The renderer's output is a fixed grammar, so
the inverse is a function that already exists implicitly; this is it written
down.

Two things the markdown cannot carry, because they belong to the document and
not to the page: a tab's id and its body's id. Those come from the document's
own file list, which is read before any tab is exported, and so does the tab
order — from which ``tradition`` is derived, a tradition root being a top-level
tab outside the main root's tree.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from .model import SECTIONS
from .render import SEPARATOR, chip_key

#: ``<?claude block m_canon?>`` as the renderer writes it.
CHIP = re.compile(r"<\?claude block ([0-9A-Za-z_]+)\?>")

#: what a chip becomes once the document has exported it as markdown.
EXPORTED_CHIP = re.compile(r"\[([^\]]*)\]\(file/([^)]*)\)")

#: A link the caller applied from the sidecar after the write: a bare fragment,
#: or this artifact's own URL with one. The graph never held it — it is
#: computed from the edges at every render — so the inverse keeps the words and
#: drops the target. A link to anywhere else is content and stays: a hinge's
#: commit reference is part of what the principal wrote.
IN_PAGE_LINK = re.compile(
    r"\[([^\]]*)\]\((?:https?://[^)#]*/artifact/[^)#]*)?#[^)]*\)")

QUESTION_LINE = re.compile(
    r"^question: (?P<state>.+?) · (?P<kind>[^·]+?) · priority (?P<priority>-?\d+)"
    r" · load \d+ · requires: (?P<requires>.*)$")
ASSENT_LINE = re.compile(
    r"^assent: (?P<assent>.*?)(?: · deadlock: (?P<deadlock>.*?))?"
    r" · provenance: thesis hinge$")
INBOX_LINE = re.compile(
    r"^(?P<kind>[^·]+?) · (?P<what>.*) · instances (?P<obligation>.*)"
    r" · (?P<done>done|not done) · id (?P<id>\S+)$")
APPLICATION_LINE = re.compile(
    r"^(?P<what>.*?) · ◆ (?P<thesis>.*?) · (?P<link>[^·]*?) · "
    r"(?P<standing>[^·]+?)(?: · (?P<note>.*))?$")
ITEM = re.compile(r"^- (?P<text>.*?)(?: (?P<chip><\?claude block [0-9A-Za-z_]+\?>))?$")

#: a chip with the space the renderer put before it, so removing one leaves the
#: text as it was written rather than a gap where a token used to stand
PLACED_CHIP = re.compile(r" ?(?:<\?claude block [0-9A-Za-z_]+\?>"
                         r"|\[[^\]]*\]\(file/[^)]*\))")


class ParseError(Exception):
    """The markdown is not in the grammar the renderer writes."""


def _chips(line: str) -> List[str]:
    """The chip keys a line carries, in order, in either spelling."""
    return (CHIP.findall(line)
            + [chip_key(label) for label, _ in EXPORTED_CHIP.findall(line)])


def _strip_chips(line: str) -> str:
    return EXPORTED_CHIP.sub(r"\1", CHIP.sub("", line)).strip()


def _blocks(markdown: str) -> List[str]:
    return [b for b in markdown.strip().split(SEPARATOR) if b.strip()]


def _sections(blocks: List[str]) -> Tuple[List[str], Dict[str, List[str]]]:
    """The blocks before the first heading, and those under each ``## ``."""
    head: List[str] = []
    named: Dict[str, List[str]] = {}
    current: Optional[str] = None
    for block in blocks:
        if block.startswith("## "):
            current = block[3:].strip().lower()
            named.setdefault(current, [])
        elif current is None:
            head.append(block)
        else:
            named[current].append(block)
    return head, named


def _subsections(blocks: List[str], marker: str) -> List[Tuple[str, List[str]]]:
    """(heading text after the marker, following blocks) per ``### <marker>``."""
    out: List[Tuple[str, List[str]]] = []
    for block in blocks:
        if block.startswith("### " + marker):
            out.append((block[4 + len(marker):].strip(), []))
        elif out:
            out[-1][1].append(block)
    return out


def _named_subsections(blocks: List[str]) -> List[Tuple[str, List[str]]]:
    """Every ``### `` subsection, whatever marker it carries."""
    out: List[Tuple[str, List[str]]] = []
    for block in blocks:
        if block.startswith("### "):
            out.append((block[4:].strip(), []))
        elif out:
            out[-1][1].append(block)
    return out


def _notes(blocks: List[str], section: str) -> List[dict]:
    notes = []
    for block in blocks:
        if block.startswith(">"):
            body = "\n".join(re.sub(r"^> ?", "", line)
                             for line in block.splitlines())
            notes.append({"section": section, "body": body})
    return notes


def _edge(heading: str) -> Tuple[str, str]:
    """``<title> → <chip>`` from a term or mention heading."""
    title, _, target = heading.rpartition("→")
    keys = _chips(target)
    if not title.strip() or not keys:
        raise ParseError("a term heading needs a title and a chip: %r" % heading)
    return title.strip(), keys[0]


def _citations(blocks: List[str]) -> List[Tuple[str, str, str]]:
    """(relation, note, last chip key) from the Support/Divergence lists."""
    out: List[Tuple[str, str, str]] = []
    relation = ""
    for block in blocks:
        if block.startswith("**") and block.endswith("**"):
            relation = block.strip("*").strip().lower()
        elif block.startswith("- "):
            for line in block.splitlines():
                keys = _chips(line)
                if keys:
                    out.append((relation, _strip_chips(line[2:]).rstrip("."), keys[-1]))
    return out


def parse_tab(markdown: str, ids: Optional[Dict[str, str]] = None) -> dict:
    """One rendered tab as the question object a graph file holds.

    ``ids`` maps a chip key back to a question id. The key drops every
    character an id may carry and a tab does not, so it is not reversible on
    its own; the document's file list supplies the map.
    """
    ids = ids or {}
    # the sidecar's links are applied to the page after the body is written, so
    # every export carries them and no graph file ever did. They come off here,
    # before the grammar is read, or they would land inside a thesis text and
    # break the one line whose shape is fixed — `· provenance: thesis hinge`.
    markdown = IN_PAGE_LINK.sub(r"\1", markdown)

    def target(key: str) -> str:
        # a key with no question behind it names something the graph does not
        # hold; term-target reports it, so read back the best guess and let the
        # checker say so rather than inventing a second spelling for it here
        return ids.get(key) or (key[2:] if key.startswith("m_") else key)

    blocks = _blocks(markdown)
    if not blocks or not blocks[0].startswith("# "):
        raise ParseError("a tab opens with its question id")
    q: dict = {"id": blocks[0][2:].strip()}

    head, named = _sections(blocks[1:])
    incoming: List[Tuple[str, str]] = []
    for block in head:
        if block.startswith("- "):
            for line in block.splitlines():
                item = ITEM.match(line)
                if item:
                    keys = _chips(line)
                    incoming.append((_strip_chips(item.group("text")),
                                     target(keys[0]) if keys else ""))
        elif block.startswith("*") and block.endswith("*"):
            q["question"] = block.strip("*")
        elif block.startswith("⌂"):
            continue  # the breadcrumb is projected, never stored
        elif block.startswith("question: "):
            line = QUESTION_LINE.match(block)
            if not line:
                raise ParseError("the question line is malformed: %r" % block)
            q["state"] = _strip_chips(line.group("state"))
            q["kind"] = line.group("kind")
            q["priority"] = int(line.group("priority"))
            q["requires"] = ([] if line.group("requires") == "nothing"
                             else [w.strip() for w in line.group("requires").split(",")])
    q["incoming"] = incoming

    theses = []
    for title, body in _subsections(named.get("thesis", []), "◆"):
        thesis: dict = {"title": title, "terms": [], "mentions": [],
                        "definitions": [], "traditions": [], "applications": []}
        rest = []
        for block in body:
            line = ASSENT_LINE.match(block)
            if line and "assent" not in thesis:
                thesis["assent"] = line.group("assent")
                if line.group("deadlock"):
                    thesis["deadlock"] = line.group("deadlock")
            elif block.startswith("**") or block.startswith("- "):
                rest.append(("citation", block))
            elif not block.startswith(">"):
                rest.append(("text", block))
        text = SEPARATOR.join(b for kind, b in rest if kind == "text")
        thesis["text"] = PLACED_CHIP.sub("", text)
        for relation, note, key in _citations([b for kind, b in rest
                                               if kind == "citation"]):
            thesis["traditions"].append({"to": target(key), "relation": relation,
                                         "note": note})
        theses.append(thesis)

    for heading, body in _subsections(named.get("terms", []), "▸"):
        title, key = _edge(heading)
        anchors = [b.strip("*") for b in body if b.startswith("*")]
        term = {"title": title, "to": target(key), "anchors": anchors}
        deadlock = [b for b in body if not b.startswith("*")]
        if deadlock:
            term["deadlock"] = SEPARATOR.join(deadlock)
        if theses:
            theses[0]["terms"].append(term)
    for heading, body in _subsections(named.get("terms", []), "↗"):
        title, key = _edge(heading)
        if theses:
            theses[0]["mentions"].append({
                "title": title, "to": target(key),
                "anchors": [b.strip("*") for b in body if b.startswith("*")]})

    for word, body in _subsections(named.get("glossary", []), "≡"):
        if not theses:
            continue
        definition = {"word": word}
        # the renderer closes a borrowed sense with its own block, ending in
        # the chip; nothing else under a definition carries one
        if body and _chips(body[-1]):
            borrowing, body = body[-1], body[:-1]
            definition["tradition"] = {"to": target(_chips(borrowing)[-1]),
                                       "note": _strip_chips(borrowing).rstrip(".")}
        definition["body"] = SEPARATOR.join(body)
        theses[0]["definitions"].append(definition)

    for name, body in _subsections(named.get("applications", []), "⚙"):
        line = APPLICATION_LINE.match(body[0]) if body else None
        if not line:
            raise ParseError("an application line is malformed under %r" % name)
        app = {"name": name, "what": line.group("what"),
               "link": line.group("link"), "standing": line.group("standing")}
        if line.group("note"):
            app["note"] = line.group("note")
        for thesis in theses:
            if thesis["title"] == line.group("thesis"):
                thesis.setdefault("applications", []).append(app)
                break

    inbox = []
    for title, body in _named_subsections(named.get("inbox", [])):
        line = INBOX_LINE.match(body[0]) if body else None
        if line:
            inbox.append({"id": line.group("id"), "title": title,
                          "kind": line.group("kind").strip(),
                          "what": line.group("what"),
                          "obligation": line.group("obligation"),
                          "done": line.group("done") == "done"})
    q["inbox"] = inbox

    hinge: dict = {}
    for heading, body in _subsections(named.get("hinge", []), "⚓"):
        part = "question" if heading.startswith("question:") else "thesis"
        hinge[part] = SEPARATOR.join(body)
    if hinge:
        q["hinge"] = hinge

    q["notes"] = [note for section in SECTIONS
                  for note in _notes(named.get(section, []), section)]
    q["theses"] = theses
    return q
