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

from .model import (AUTHOR, CITATION_HEADINGS, GLYPHS, RESERVED, SECTIONS, TRADITION, Hinge,
                    Work)
from . import render, text
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
#: the situation a clause governs, under a term or under the hinge's end
CUE_LINE = re.compile(r"^cue: (?P<cue>.*)$", re.S)
#: a case's labelled lines, under its heading; ``case:`` is the situation
CASE_LINES = {"case": re.compile(r"^case: (?P<words>.*)$", re.S),
              "verdict": re.compile(r"^verdict: (?P<words>.*)$", re.S),
              "reason": re.compile(r"^reason: (?P<words>.*)$", re.S),
              "clause": re.compile(r"^clause: (?P<words>.*)$", re.S)}
CASE_FIELDS = {"case": "situation", "verdict": "verdict", "reason": "reason",
               "clause": "clause"}
APPLICATION_LINE = re.compile(
    r"^(?P<what>.*?) · %s (?P<thesis>.*?) · (?P<link>[^·]*?) · "
    r"(?P<standing>[^·(]+?)(?: \((?P<clause>[^)]*)\))?(?: · (?P<note>.*))?$"
    % re.escape(GLYPHS["thesis"]))
ITEM = re.compile(r"^- (?P<text>.*?)(?: (?P<chip><\?claude block [0-9A-Za-z_]+\?>))?$")

#: a chip with the space the renderer put before it, so removing one leaves the
#: text as it was written rather than a gap where a token used to stand
PLACED_CHIP = re.compile(r" ?(?:<\?claude block [0-9A-Za-z_]+\?>"
                         r"|\[[^\]]*\]\(file/[^)]*\))")

#: what a breadcrumb leaves behind once its chips are gone: the separators
#: that stood between them
CRUMB_TAIL = re.compile(r"[\s›]+$")

#: the heading glyphs the renderer writes under each section; a ``### `` under
#: a section with any other glyph is a heading the grammar does not hold
MARKERS = {"thesis": (GLYPHS["thesis"],), "glossary": (GLYPHS["glossary"],),
           "terms": (GLYPHS["term"], GLYPHS["mention"]), "cases": (GLYPHS["case"],),
           "applications": (GLYPHS["application"],), "works": (GLYPHS["work"],),
           "hinge": (GLYPHS["hinge"],)}

#: what opens the lineage line, the one block above a tab's title
LINEAGE = GLYPHS["lineage"]

CHIPPED_STATE = ("a state is a chip and not a word: this is the renderer's markdown, "
                 "and the reader takes the page as the page spells it")


class ParseError(Exception):
    """The markdown is not in the grammar the renderer writes."""


def question_line(block: str) -> "re.Match[str]":
    """The question line's fields, or a ``ParseError`` saying what is wrong
    with it: the one reading, for the tab parser and the frontier alike."""
    found = QUESTION_LINE.match(block)
    if not found:
        raise ParseError("the question line is malformed: %r" % block)
    return found


def _top(tabs: Dict[str, dict], tab_id: str) -> str:
    """The top-level tab a tab stands under, itself if it is one."""
    seen: Set[str] = set()
    cur = tab_id
    while True:
        parent = tabs.get(cur, {}).get("subtabOf")
        if not parent or parent in seen or parent not in tabs:
            return cur
        seen.add(cur)
        cur = parent


def reserved(tabs: Dict[str, dict]) -> Set[str]:
    """The tabs that are no question: a top-level tab named for a reserved
    tab (the lease tab), and anything under one."""
    heads = {t for t, meta in tabs.items() if not meta.get("subtabOf")
             and str(meta.get("name", "")) in RESERVED}
    return {t for t in tabs if _top(tabs, t) in heads}


def projects(tabs: Dict[str, dict]) -> Dict[str, str]:
    """tab id -> the project the tab is in, from the tab list.

    A notebook may hold several projects, each a root at the top level with
    an order in the a series; a tab is in the project of the top-level tab it
    stands under. A notebook of one project has one such tab, and every tab
    in it is in the empty project, as every question of a graph file that
    names no projects is. The b series and the reserved tabs are no project.
    """
    tops = project_order(tabs)
    if len(tops) < 2:
        return {t: "" for t in tabs}
    names = {t: str(tabs[t].get("name", t)) for t in tabs}
    out: Dict[str, str] = {}
    for tab_id in tabs:
        top = _top(tabs, tab_id)
        out[tab_id] = names[top] if names.get(top) in tops else ""
    return out


def project_order(tabs: Dict[str, dict]) -> List[str]:
    """The projects' names in the order their roots stand at the top level."""
    tops = [(str(meta.get("order", "")), str(meta.get("name", t)))
            for t, meta in tabs.items()
            if not meta.get("subtabOf") and str(meta.get("order", "")).startswith("a")
            and str(meta.get("name", "")) not in RESERVED]
    return [name for _, name in sorted(tops)]


def parties(tabs: Dict[str, dict]) -> Dict[str, str]:
    """tab id -> the party whose notebook the tab is in, from the tab list.

    A question belongs to a party. The author's are the projects' trees;
    another party's is that party's own notebook, and anything nested under
    it is theirs too — a reconstruction may raise its own questions and
    answer them. Where the notebook holds a tradition project, a party's
    notebook is a tab directly under that project's root; otherwise it is
    placed at top level in the b series. Read off the document's tab list
    alone, so a caller that has not read a single body can tell whose a tab
    is.
    """
    heads: Dict[str, str] = {}
    tradition_root = [t for t, meta in tabs.items() if not meta.get("subtabOf")
                      and str(meta.get("name", "")) == TRADITION
                      and str(meta.get("order", "")).startswith("a")]
    for tab_id, meta in tabs.items():
        top_b = not meta.get("subtabOf") and str(meta.get("order", "")).startswith("b")
        under = bool(tradition_root) and meta.get("subtabOf") == tradition_root[0]
        if top_b or under:
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
    labels = sorted(set(labels), key=len, reverse=True)
    if not labels:
        return None

    def ends_with_label(text: str) -> Optional[str]:
        # whole, and after a space or nothing: a label is a question id, and
        # one may carry a space, so it is matched as itself and not as a word
        for label in labels:
            if text.endswith(label) and (len(text) == len(label)
                                         or text[-len(label) - 1] == " "):
                return label
        return None

    at, found = len(line.rstrip()), []
    while True:
        label = ends_with_label(line[:at])
        if label is None:
            break
        found.insert(0, label)
        at -= len(label)
        before = line[:at]
        # a step of the crumb, if the one before it is a label too; else the
        # space that parted the run from the words
        if before.endswith(" › ") and ends_with_label(before[:-3]):
            at -= 3
            continue
        if before.endswith(" "):
            at -= 1
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


def strip_chips(line: str, labels: Iterable[str] = ()) -> str:
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


#: what parts one block from the next: a blank line, whatever whitespace it
#: carries and however many stand together. Split on the exact separator, an
#: extra newline before ``## Thesis`` made that heading a prose block, and the
#: section with every answer under it was dropped in silence.
BLANK = re.compile(r"\n[ \t]*\n+")


def _blocks(markdown: str) -> List[str]:
    return [b for b in BLANK.split(markdown.strip()) if b.strip()]


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


#: a work's url as a line may spell it: the renderer's link, whose words are
#: the url and whose target is kept; an autolink; or the url bare, as a read
#: spells a link the document made of the words alone. A target may hold a
#: pair of parentheses, as an encyclopedia's do, and ``work-fields`` holds
#: that a url holds no other
_URL = re.compile(r"^(?:\[(?:[^\]\\]|\\.)*\]\((?P<href>%s)\)|<(?P<auto>[^>]*)>|(?P<bare>\S+))$"
                  % Work.URL)


def work_fields(block: str) -> Optional[Dict[str, str]]:
    """A work's line back into its fields, or None where the block is not one.

    Every part the separator parts must open with a field's label, each label
    once and in ``Work.FIELDS`` order, as ``render.work_line`` writes them; a
    block that does not open with a label is the work's note. The url is read
    off its link's target and not its words, which are the url again behind
    whatever backslashes the page spells it with.
    """
    if not block.startswith(tuple("%s: " % name for name in Work.FIELDS)):
        return None
    out: Dict[str, str] = {}
    last = -1
    for part in block.split(render.WORK_SEPARATOR):
        name, sep, value = part.partition(": ")
        if not sep or name not in Work.FIELDS or Work.FIELDS.index(name) <= last:
            raise ParseError("a work's line is malformed at %r: its fields are "
                             "labelled, once each, in the order %s"
                             % (part[:40], ", ".join(Work.FIELDS)))
        last = Work.FIELDS.index(name)
        if name == "url":
            url = _URL.match(value.strip())
            if not url:
                raise ParseError("a work's url is neither a link nor one word: %r"
                                 % value[:60])
            value = next(found for found in url.group("href", "auto", "bare")
                         if found is not None)
        out[name] = value
    return out


def _edge(heading: str, labels: Iterable[str] = ()) -> Tuple[str, str]:
    """``<title> → <chip>`` from a term or mention heading."""
    title, _, target = heading.rpartition("→")
    keys = _chips(target, labels)
    if not title.strip() or not keys:
        raise ParseError("a term heading needs a title and a chip: %r" % heading)
    return title.strip(), keys[0]


def _unstopped(words: str) -> str:
    """A note without the one stop the renderer closed it with. One and not
    every trailing stop: ``note-unstopped`` holds that the stored note had
    none of its own, so one off is the note as it was stored, and ``etc.``
    is a finding on the graph rather than ``etc`` on the way back."""
    words = words.strip()
    return words[:-1].rstrip() if words.endswith(".") else words


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
                    # with the file list in hand a bare label is readable, so a
                    # citation that names nothing is malformed; without it the
                    # label is not readable, and the item is left as it was
                    if labels:
                        raise ParseError("a citation names no question: %r" % line[:60])
                    continue
                # the crumb is a breadcrumb, so taking its chips out leaves the
                # separators that stood between them; they belong to the path
                # and not to the note that precedes it
                words = CRUMB_TAIL.sub("", strip_chips(line[2:], labels))
                # only a divergence holds something instead; in a support's
                # note the words are the note's own
                note, _, counter = (words.partition(INSTEAD) if relation == "divergence"
                                    else (words, "", ""))
                out.append((relation, _unstopped(note),
                            _unstopped(CRUMB_TAIL.sub("", counter)), keys[-1]))
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
    # So do the exporter's own backslashes, and only those: one before a
    # character markdown reads as a mark spells the literal character, and
    # stays, or the next render would write a star the page holds as a mark.
    markdown = text.canonical(IN_PAGE_LINK.sub(r"\1", markdown))

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
    if not titles or any(not b.startswith(LINEAGE) for b in blocks[:titles[0]]):
        raise ParseError("a tab opens with its lineage and then its question id")
    at = titles[0]
    q: dict = {"id": blocks[at][2:].strip()}

    head, named = _sections(blocks[at + 1:])
    foreign = sorted(set(named) - set(SECTIONS))
    if foreign:
        raise ParseError("a section the renderer does not write, whose blocks would "
                         "be lost: %s" % ", ".join("## %s" % s for s in foreign))
    for section, held in named.items():
        for block in held:
            if block.startswith("### ") and not any(
                    block.startswith("### " + marker) for marker in MARKERS.get(section, ())):
                raise ParseError("a heading the renderer does not write under %s, which "
                                 "would end the text before it: %r" % (section, block[:50]))
    incoming: List[Tuple[str, str]] = []
    for block in head:
        if block.startswith("- "):
            for line in block.splitlines():
                item = ITEM.match(line)
                if item:
                    keys = _chips(line, labels)
                    if not keys and labels:
                        raise ParseError("an item of the header list names no "
                                         "raiser: %r" % line[:60])
                    incoming.append((strip_chips(item.group("text"), labels),
                                     target(keys[0]) if keys else ""))
        elif block.startswith("*") and block.endswith("*"):
            q["question"] = _unwrap(block)  # one layer: the question's own
        elif block.startswith(LINEAGE):
            continue  # the breadcrumb is projected, never stored
        elif block.startswith("question: "):
            line = question_line(block)
            q["state"] = strip_chips(line.group("state"))
            if not q["state"]:
                raise ParseError(CHIPPED_STATE)
            q["kind"] = line.group("kind")
            if line.group("answerer"):
                q["answerer"] = line.group("answerer").strip()
            q["pressure"] = int(line.group("pressure"))
    q["incoming"] = incoming

    theses = []
    for title, body in _subsections(named.get("thesis", []), GLYPHS["thesis"]):
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
                thesis["state"] = strip_chips(line.group("state")).strip()
                if not thesis["state"]:
                    raise ParseError(CHIPPED_STATE)
            elif not block.startswith(">"):
                rest.append(block)
        thesis["text"] = PLACED_CHIP.sub("", SEPARATOR.join(rest))
        for relation, note, counter, key in _citations(cited, labels):
            thesis["traditions"].append({"to": target(key), "relation": relation,
                                         "note": note, "counter": counter})
        theses.append(thesis)

    for heading, body in _subsections(named.get("terms", []), GLYPHS["term"]):
        title, key = _edge(heading, labels)
        anchors = [_unwrap(b) for b in body if b.startswith("*")]
        term = {"title": title, "to": target(key), "anchors": anchors}
        deadlock: dict = {}
        for block in body:
            counter = DEADLOCK_LINE.match(block)
            attenuation = ATTENUATION_LINE.match(block)
            suspended = SUSPENDED_LINE.match(block)
            cue = CUE_LINE.match(block)
            if counter:
                deadlock["counter"] = counter.group("counter")
            elif attenuation:
                deadlock["attenuation"] = attenuation.group("attenuation")
            elif suspended:
                term["suspended"] = suspended.group("suspended")
            elif cue:
                term["cue"] = cue.group("cue")
        if deadlock:
            term["deadlock"] = deadlock
        if theses:
            _owner(theses, anchors)["terms"].append(term)
    for heading, body in _subsections(named.get("terms", []), GLYPHS["mention"]):
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
    for word, body in _subsections(named.get("glossary", []), GLYPHS["glossary"]):
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
                                       "note": _unstopped(strip_chips(borrowing, here))}
        definition["body"] = SEPARATOR.join(body)
        definitions.append(definition)

    titles = [thesis["title"] for thesis in theses]
    doubled = sorted({t for t in titles if titles.count(t) > 1})
    if doubled:
        raise ParseError("two answers carry one headline, and the page tells its answers "
                         "apart by headline alone: %r" % doubled[0])
    for name, body in _subsections(named.get("applications", []), GLYPHS["application"]):
        line = APPLICATION_LINE.match(body[0]) if body else None
        if not line:
            raise ParseError("an application line is malformed under %r" % name)
        app = {"name": name, "what": line.group("what"),
               "link": line.group("link"), "standing": line.group("standing")}
        if line.group("note"):
            app["note"] = line.group("note")
        owner = next((thesis for thesis in theses
                      if thesis["title"].strip() == line.group("thesis").strip()), None)
        if owner is None:
            # dropped, it would be gone from the page at the next body write
            raise ParseError("the application %r names an answer no heading on the tab "
                             "carries: %r" % (name, line.group("thesis")))
        owner["applications"].append(app)

    hinge: dict = {}
    for heading, body in _subsections(named.get("hinge", []), GLYPHS["hinge"]):
        # the heading opens with the part's name, as the renderer writes it;
        # a heading naming no part would be read back under another's name
        # or not at all, so it is refused as the other foreign headings are
        part = next((name for name, _, _ in Hinge.PARTS
                     if heading.startswith(name + ":")), None)
        if part is None:
            raise ParseError("a hinge heading that names none of the hinge's parts, "
                             "whose words would be lost: %r" % heading[:50])
        if part in hinge:
            # the second would replace the first, whose words would be lost
            raise ParseError("the hinge's %s is given twice: %r" % (part, heading[:50]))
        if part == "end":
            # the end may carry one cue, a labelled block of its own after the
            # end's words; it is the situation the end's clauses govern and
            # not a line of the end, so it is not folded into the text
            cues = [found for found in map(CUE_LINE.match, body) if found]
            if len(cues) > 1:
                raise ParseError("the end's cue is given twice, and the second would "
                                 "replace the first: %r" % cues[1].group("cue")[:50])
            if cues:
                hinge["cue"] = cues[0].group("cue")
                body = [block for block in body if not CUE_LINE.match(block)]
        hinge[part] = SEPARATOR.join(body)
    if hinge:
        q["hinge"] = hinge

    # a party's works: the key under its heading, the labelled line where any
    # field is filled, and the note as what follows it. Left off a question
    # that carries none, as the graph file leaves it off, since only a party
    # carries any
    works = []
    for key, body in _subsections(named.get("works", []), GLYPHS["work"]):
        work: dict = {"key": key}
        fields = work_fields(body[0]) if body else None
        if fields is not None:
            work.update(fields)
            body = body[1:]
        if body:
            work["note"] = SEPARATOR.join(body)
        works.append(work)
    if works:
        q["works"] = works

    # the user's cases: the name under its heading and the labelled lines
    # under it, each read by its label and left off where the page has none.
    # Left off a question that carries none, as the graph file leaves it off
    cases = []
    for name, body in _subsections(named.get("cases", []), GLYPHS["case"]):
        case: dict = {"name": name}
        for block in body:
            for label, pattern in CASE_LINES.items():
                found = pattern.match(block)
                if found:
                    case[CASE_FIELDS[label]] = found.group("words")
                    break
            else:
                raise ParseError("a line under the case %r the renderer does not write, "
                                 "which would be lost: %r" % (name, block[:50]))
        cases.append(case)
    if cases:
        q["cases"] = cases

    q["notes"] = [note for section in SECTIONS
                  for note in _notes(named.get(section, []), section)]
    q["theses"] = theses
    q["definitions"] = definitions
    return q
