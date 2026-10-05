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
from typing import Dict, Iterable, List, Optional, Set, Tuple

from .model import AUTHOR, SECTIONS
from . import render
from .render import INSTEAD, SEPARATOR, SHADOW, chip_key

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

#: A backslash the export put in front of punctuation the markdown would
#: otherwise read as a marker — `session\_01Jjv…` for a word with an
#: underscore in it. It is the exporter's and not the page's, so it comes off;
#: this is the ordinary markdown reading of a backslash escape.
ESCAPE = re.compile(r"\\([!-/:-@\[-`{-~])")

#: Only pressure is read back. Backlog and load are projections of the graph
#: and standing is read off the state, so reading any of them would store a
#: second copy of something already derivable.
QUESTION_LINE = re.compile(
    r"^question: (?P<state>.+?) · (?P<kind>[^·]+?)"
    r"(?: · answerer: (?P<answerer>[^·]+?))?"
    r" · pressure (?P<pressure>-?\d+) · backlog -?\d+"
    r" · load \d+$")
#: An answer's metadata: its assent, its own state, and its provenance.
ASSENT_LINE = re.compile(
    r"^assent: (?P<assent>.*?) · (?P<state>[^·]+?)"
    r" · provenance: thesis hinge$")
DEADLOCK_LINE = re.compile(r"^deadlock: (?P<counter>.*)$", re.S)
SUSPENDED_LINE = re.compile(r"^suspended: (?P<suspended>.*)$", re.S)
ATTENUATION_LINE = re.compile(r"^attenuation: (?P<attenuation>.*)$", re.S)
APPLICATION_LINE = re.compile(
    r"^(?P<what>.*?) · ◆ (?P<thesis>.*?) · (?P<link>[^·]*?) · "
    r"(?P<standing>[^·(]+?)(?: \((?P<clause>[^)]*)\))?(?: · (?P<note>.*))?$")
ITEM = re.compile(r"^- (?P<text>.*?)(?: (?P<chip><\?claude block [0-9A-Za-z_]+\?>))?$")

#: what opens the tradition edges at the foot of a thesis subsection. Nothing
#: the renderer writes follows them, which is what makes the split positional.
CITATION_HEADINGS = ("**Support**", "**Divergence**")

#: a chip with the space the renderer put before it, so removing one leaves the
#: text as it was written rather than a gap where a token used to stand
PLACED_CHIP = re.compile(r" ?(?:<\?claude block [0-9A-Za-z_]+\?>"
                         r"|\[[^\]]*\]\(file/[^)]*\))")

#: what a breadcrumb leaves behind once its chips are gone: the separators that
#: stood between them, and the full stop that closed the note before it
CRUMB_TAIL = re.compile(r"[\s›.]+$")


class ParseError(Exception):
    """The markdown is not in the grammar the renderer writes."""


#: what a page written while a tab had an inbox still carries, and what is
#: said of it. Read on, such a page would lose the section in silence at the
#: next body write, so it is refused until it has been brought up.
REMOVED_SECTION = "inbox"
REMOVED_FIELD = " · requires:"
REMOVED = ("the inbox was removed, and this page still has %s: bring the "
           "page up to the grammar the renderer writes before it is read")


def parties(tabs: Dict[str, dict]) -> Dict[str, str]:
    """tab id -> the party whose notebook the tab is in, from the tab list.

    A question belongs to a party. The author's are the main tree; another
    party's is that party's own notebook, placed at top level in the b
    series, and anything nested under it is theirs too — a reconstruction
    may raise its own questions and answer them. Read off the document's tab
    list alone, so a caller that has not read a single body can tell whose a
    tab is.
    """
    heads: Dict[str, str] = {}
    for tab_id, meta in tabs.items():
        if not meta.get("subtabOf") and str(meta.get("order", "")).startswith("b"):
            heads[tab_id] = str(meta.get("name", tab_id)).lower()

    def party(tab_id: str, seen: Set[str]) -> str:
        if tab_id in heads:
            return heads[tab_id]
        parent = tabs.get(tab_id, {}).get("subtabOf")
        if not parent or parent in seen:
            return AUTHOR
        return party(parent, seen | {tab_id})

    return {tab_id: party(tab_id, set()) for tab_id in tabs}


def _label_run(line: str, labels: Iterable[str]) -> Optional[Tuple[int, List[str]]]:
    """The trailing run of bare question ids on a line, and where it begins.

    A third spelling, and the export's own: it writes a mention chip as
    ``[label](file/<tab>)`` sometimes and as the bare label at others, saying
    ``kept_as_text`` when it does the second. The label is the question id, so
    the datum survives; what is lost is any mark that it was a chip at all.

    It is read back only where the renderer puts a chip — at the end of a
    line, alone or as the tail of a ` › ` breadcrumb, and preceded by a space
    or nothing. A bare id anywhere else is prose and is left alone, which is
    the whole reason this is a run at the end rather than a search for words.
    """
    labels = set(labels)
    if not labels:
        return None
    at, found = len(line), []
    while True:
        head, sep, word = line[:at].rpartition(" › " if found else " ")
        if not sep and found:
            break
        candidate = (word if sep else line[:at]).strip()
        if candidate not in labels:
            break
        found.insert(0, candidate)
        at = len(head)
        if not sep:  # the run reaches the start of the line
            break
    return (at, found) if found else None


def _closing(line: str, labels: Iterable[str]) -> Set[str]:
    """``labels``, but only where a bare run really closes this block.

    The renderer writes a borrowed sense as a block of its own: the chip
    alone, or a note that ends in a full stop and then the chip. Requiring
    that shape keeps a definition body whose last word happens to be a
    question id from being read as a borrowing from that question.
    """
    run = _label_run(line, labels)
    if run and (run[0] == 0 or line[:run[0]].rstrip().endswith(".")):
        return set(labels)
    return set()


def _chips(line: str, labels: Iterable[str] = ()) -> List[str]:
    """The chip keys a line carries, in order, in any of the three spellings."""
    keys = (CHIP.findall(line)
            + [chip_key(label) for label, _ in EXPORTED_CHIP.findall(line)])
    if keys:
        return keys
    run = _label_run(line, labels)
    return [chip_key(word) for word in run[1]] if run else []


def _strip_chips(line: str, labels: Iterable[str] = ()) -> str:
    """The line without its chips, in any spelling.

    A chip goes entirely, label and all. It is a token the renderer put there
    for the edge it stands on, and the edge is read from `_chips`; keeping the
    label put the tradition's name inside the note that cites it — `…already
    prosecuting for impiety. Plato`.
    """
    out = PLACED_CHIP.sub("", line)
    if out == line:
        run = _label_run(line, labels)
        if run:
            out = line[:run[0]]
    return out.strip()


def _unchip_prose(body_text: str, edges: List[Tuple[str, List[str]]],
                  labels: Iterable[str]) -> str:
    """The answer's own words, with the chips the export kept as text removed.

    Only a removal is possible, since the renderer only ever inserts: it puts
    ``` <label>``` wherever ``_placement`` sends a chip. So the candidate is
    checked by running that insertion forward again over it, and taken only if
    it comes back as the page reads. A word of prose that happens to be a
    question id therefore cannot be eaten quietly — the check fails, the words
    are left exactly as the page had them, and ``verify`` reports the
    difference rather than a graph file being silently wrong.
    """
    labels = set(labels)
    if not {to for to, _ in edges if to in labels}:
        return body_text
    bare = lambda to: " " + to  # noqa: E731 - the export's own spelling
    wanted: Dict[int, List[str]] = {}
    for at, _, to in render.anchor_cuts(body_text, edges):
        wanted.setdefault(at, []).append(to)
    out = body_text
    # Right to left, so removing one label does not move the place of the next.
    # A paragraph puts the chip after the anchor, where the cut is; a list item
    # puts it at the end of the item, so over the page the cut lands after it.
    # Several anchors in one item stack their chips there, and each removal
    # moves the end, which is why the position is carried rather than reused.
    for at in sorted(wanted, reverse=True):
        here, end, moved = list(wanted[at]), at, True
        while here and moved:
            moved = False
            for to in list(here):
                token = bare(to)
                if out[end:end + len(token)] == token:
                    out = out[:end] + out[end + len(token):]
                elif end >= len(token) and out[end - len(token):end] == token:
                    out = out[:end - len(token)] + out[end:]
                    end -= len(token)
                else:
                    continue
                here.remove(to)
                moved = True
                break
    return out if render.anchored(out, edges, bare) == body_text else body_text


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
    """(heading text after the marker, following blocks) per ``### <marker>``.

    A subsection ends at the next ``### `` of any marker, not only at the next
    one of this marker. The terms section holds ``▸`` and then ``↗``, so a run
    that did not stop would read every mention's anchor back as one more anchor
    of the last term — which is a term edge the graph never had.

    A blockquote is never part of a subsection: it is somebody's note, and
    ``_notes`` collects it from the section itself.
    """
    out: List[Tuple[str, List[str]]] = []
    current: Optional[List[str]] = None
    for block in blocks:
        if block.startswith("### "):
            current = None
            if block.startswith("### " + marker):
                out.append((block[4 + len(marker):].strip(), []))
                current = out[-1][1]
        elif current is not None and not block.startswith(">"):
            current.append(block)
    return out


def _owner(theses: List[dict], anchors: List[str]) -> dict:
    """The answer a term or mention was read off.

    The page files every term under one section, and which answer raised it is
    said only by the chip in that answer's text — so the answer is the one
    whose text holds the anchors. A term with no anchor, or one no answer holds
    whole, goes to the first: the graph has to say something, and the checker
    says if that was wrong. Two answers holding the same anchor would file it
    under the first, which ``anchor-unique`` refuses on the graph before it
    is written.
    """
    for thesis in theses:
        if anchors and all(anchor in thesis.get("text", "") for anchor in anchors):
            return thesis
    return theses[0]


def _unwrap(block: str) -> str:
    """An anchor line back to the anchor: one layer of italics off, no more.

    ``strip("*")`` would take the anchor's own emphasis with it —
    ``***Be predictable.** …*`` is the italicised form of an anchor that opens
    in bold, and the bold is part of what makes the anchor a verbatim substring
    of the thesis.
    """
    if len(block) > 1 and block.startswith("*") and block.endswith("*"):
        return block[1:-1]
    return block


def _notes(blocks: List[str], section: str) -> List[dict]:
    notes = []
    for block in blocks:
        if block.startswith(">"):
            body = "\n".join(re.sub(r"^> ?", "", line)
                             for line in block.splitlines())
            notes.append({"section": section, "body": body})
    return notes


def _edge(heading: str, labels: Iterable[str] = ()) -> Tuple[str, str]:
    """``<title> → <chip>`` from a term or mention heading."""
    title, _, target = heading.rpartition("→")
    keys = _chips(target, labels)
    if not title.strip() or not keys:
        raise ParseError("a term heading needs a title and a chip: %r" % heading)
    return title.strip(), keys[0]


def _citations(blocks: List[str],
               labels: Iterable[str] = ()) -> List[Tuple[str, str, str, str]]:
    """(relation, note, counter, last chip key) from the Support/Divergence lists.

    A divergence is a deadlock with another party, so it says what is held
    instead; the counter-clause rides in the item after its marker, which is
    what lets it come back off the page into a field of its own.
    """
    out: List[Tuple[str, str, str, str]] = []
    relation = ""
    for block in blocks:
        if block.startswith("**") and block.endswith("**"):
            relation = block.strip("*").strip().lower()
        elif block.startswith("- "):
            for line in block.splitlines():
                keys = _chips(line, labels)
                if not keys:
                    continue
                # the crumb is a breadcrumb, so taking its chips out leaves the
                # separators that stood between them; they belong to the path
                # and not to the note that precedes it
                text = CRUMB_TAIL.sub("", _strip_chips(line[2:], labels))
                note, _, counter = text.partition(INSTEAD)
                out.append((relation, note.strip().rstrip("."),
                            CRUMB_TAIL.sub("", counter).strip(), keys[-1]))
    return out


def parse_tab(markdown: str, ids: Optional[Dict[str, str]] = None) -> dict:
    """One rendered tab as the question object a graph file holds.

    ``ids`` maps a chip key back to a question id. The key drops every
    character an id may carry and a tab does not, so it is not reversible on
    its own; the document's file list supplies the map.
    """
    ids = ids or {}
    # a chip the export kept as text is its label, and the label is the id
    labels = set(ids.values())
    # the sidecar's links are applied to the page after the body is written, so
    # every export carries them and no graph file ever did. They come off here,
    # before the grammar is read, or they would land inside a thesis text and
    # break the one line whose shape is fixed — `· provenance: thesis hinge`.
    markdown = ESCAPE.sub(r"\1", IN_PAGE_LINK.sub(r"\1", markdown))

    def target(key: str) -> str:
        # a key with no question behind it names something the graph does not
        # hold; term-target reports it, so read back the best guess and let the
        # checker say so rather than inventing a second spelling for it here
        return ids.get(key) or (key[2:] if key.startswith("m_") else key)

    blocks = _blocks(markdown)
    # the breadcrumb stands above the title, so the title is the first heading
    # rather than the first block; anything before it is the lineage, which is
    # projected and never stored
    titles = [i for i, b in enumerate(blocks) if b.startswith("# ")]
    if not titles or any(not b.startswith("⌂") for b in blocks[:titles[0]]):
        raise ParseError("a tab opens with its lineage and then its question id")
    at = titles[0]
    q: dict = {"id": blocks[at][2:].strip()}

    head, named = _sections(blocks[at + 1:])
    if REMOVED_SECTION in named:
        raise ParseError(REMOVED % "an Inbox section")
    incoming: List[Tuple[str, str]] = []
    for block in head:
        if block.startswith("- "):
            for line in block.splitlines():
                item = ITEM.match(line)
                if item:
                    keys = _chips(line, labels)
                    incoming.append((_strip_chips(item.group("text"), labels),
                                     target(keys[0]) if keys else ""))
        elif block.startswith("*") and block.endswith("*"):
            q["question"] = _unwrap(block)  # one layer: the question's own
        elif block.startswith("⌂"):
            continue  # the breadcrumb is projected, never stored
        elif block.startswith("question: "):
            if REMOVED_FIELD in block:
                raise ParseError(REMOVED % "a `requires:` field on its "
                                 "question line")
            line = QUESTION_LINE.match(block)
            if not line:
                raise ParseError("the question line is malformed: %r" % block)
            q["state"] = _strip_chips(line.group("state"))
            q["kind"] = line.group("kind")
            if line.group("answerer"):
                q["answerer"] = line.group("answerer").strip()
            q["pressure"] = int(line.group("pressure"))
    q["incoming"] = incoming

    theses = []
    for title, body in _subsections(named.get("thesis", []), "◆"):
        thesis: dict = {"title": title, "terms": [], "mentions": [],
                        "traditions": [], "applications": []}
        # The citations close the subsection — the renderer appends them after
        # the text and nothing follows them — so the split is positional and
        # not by shape. Reading it by shape swallowed every bolded lead and
        # every bullet list a thesis writes, which on the root answer is most
        # of the answer.
        opened = [i for i, block in enumerate(body)
                  if block.strip() in CITATION_HEADINGS]
        cut = opened[0] if opened else len(body)
        prose, cited = body[:cut], body[cut:]
        rest = []
        for block in prose:
            line = ASSENT_LINE.match(block)
            if line and "assent" not in thesis:
                thesis["assent"] = line.group("assent")
                thesis["state"] = _strip_chips(line.group("state")).strip()
            elif not block.startswith(">"):
                rest.append(("text", block))
        text = SEPARATOR.join(b for kind, b in rest if kind == "text")
        thesis["text"] = PLACED_CHIP.sub("", text)
        for relation, note, counter, key in _citations(cited, labels):
            thesis["traditions"].append({"to": target(key), "relation": relation,
                                         "note": note, "counter": counter})
        theses.append(thesis)

    for heading, body in _subsections(named.get("terms", []), "▸"):
        title, key = _edge(heading, labels)
        anchors = [_unwrap(b) for b in body if b.startswith("*")]
        term = {"title": title, "to": target(key), "anchors": anchors}
        deadlock: dict = {}
        for block in body:
            counter = DEADLOCK_LINE.match(block)
            attenuation = ATTENUATION_LINE.match(block)
            suspended = SUSPENDED_LINE.match(block)
            if counter:
                deadlock["counter"] = counter.group("counter")
            elif attenuation:
                deadlock["attenuation"] = attenuation.group("attenuation")
            elif suspended:
                term["suspended"] = suspended.group("suspended")
        if deadlock:
            term["deadlock"] = deadlock
        if theses:
            _owner(theses, anchors)["terms"].append(term)
    for heading, body in _subsections(named.get("terms", []), "↗"):
        title, key = _edge(heading, labels)
        anchors = [_unwrap(b) for b in body if b.startswith("*")]
        if theses:
            _owner(theses, anchors)["mentions"].append({
                "title": title, "to": target(key), "anchors": anchors})

    for thesis in theses:
        thesis["text"] = _unchip_prose(
            thesis["text"],
            [(edge["to"], edge["anchors"])
             for edge in thesis["terms"] + thesis["mentions"]],
            labels)

    # the glossary is the question's: a word may have come in on the hinge,
    # and one sense per word leaves nothing for an answer to own
    definitions = []
    for word, body in _subsections(named.get("glossary", []), "≡"):
        definition = {"word": word}
        # a shadow is the last block when there is one: the question the word
        # has earned, pointed at from the definition that stands in for it
        if body and body[-1].startswith(SHADOW) and _chips(body[-1], labels):
            definition["question"] = target(_chips(body[-1], labels)[0])
            body = body[:-1]
        # the renderer closes a borrowed sense with its own block, ending in
        # the chip; nothing else under a definition carries one
        if body and _chips(body[-1], _closing(body[-1], labels)):
            borrowing, body = body[-1], body[:-1]
            here = _closing(borrowing, labels)
            definition["tradition"] = {"to": target(_chips(borrowing, here)[-1]),
                                       "note": _strip_chips(borrowing, here).rstrip(".")}
        definition["body"] = SEPARATOR.join(body)
        definitions.append(definition)

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

    hinge: dict = {}
    for heading, body in _subsections(named.get("hinge", []), "⚓"):
        part = "question" if heading.startswith("question:") else "thesis"
        hinge[part] = SEPARATOR.join(body)
    if hinge:
        q["hinge"] = hinge

    q["notes"] = [note for section in SECTIONS
                  for note in _notes(named.get(section, []), section)]
    q["theses"] = theses
    q["definitions"] = definitions
    return q
