"""The renderer: the only sanctioned way to produce a tab's markdown.

A layout violation is impossible if the tool is used, so the layout lives here
and nowhere else. The renderer refuses to print a question the checker reports an
ERROR against, and emits, alongside the markdown, the links sidecar the caller
turns into ``format`` operations once the write has returned real block ids.

One tab points at another with a **mention chip**: the token ``<?claude block
KEY?>`` in the markdown, and an entry under the sidecar's ``blocks`` map naming
the tab it refers to. Every place the specification calls for a reference to a
question is written as a chip and never as a bare id; the one id a tab
carries is its own title, and ``headline-not-identifier`` holds the rest.
"""

from __future__ import annotations

import re
from typing import Callable, Dict, Iterator, List, Optional, Set, Tuple

from . import project, spec, text
from .model import (ANSWERERS, GLYPHS, STANDINGS, STATES, Application, Graph,
                     Hinge, Question, Term, Thesis)

SEPARATOR = "\n\n"


# -- mention chips ----------------------------------------------------------

def chip_key(qid: str) -> str:
    """The ``blocks`` key for a chip pointing at ``qid``: ``m_<id>``, lowered,
    with every non-alphanumeric character replaced by an underscore.

    The document takes a key of ``[a-z0-9_-]`` and nothing else, so a tradition
    named for its author — ``Plato``, ``Aquinas`` — cannot be its own key. Two
    ids that differ only in case would therefore share one chip; ``unique-ids``
    reports that rather than letting one tab's chip point at the other's tab.
    """
    return "m_" + re.sub(r"[^0-9a-z]", "_", qid.lower())


def token(key: str) -> str:
    """The markdown token for a chip written against ``key`` in the blocks
    map: a mention's, or a state dropdown's."""
    return "<?claude block %s?>" % key


def chip(qid: str) -> str:
    """The markdown token for a mention chip pointing at ``qid``."""
    return token(chip_key(qid))


class RefusedError(Exception):
    """The checker reports an ERROR affecting the question asked for."""

    def __init__(self, qid: str, findings: List[spec.Finding]):
        self.qid = qid
        self.findings = findings
        super().__init__("refusing to render %s: %d error(s)" % (qid, len(findings)))


# -- pieces -----------------------------------------------------------------

def _incoming_terms(graph: Graph, qid: str) -> List[Tuple[str, Term]]:
    """The term edges leading here, ordered by (parent id, term title)."""
    return sorted(((src.id, term) for src, term in graph.incoming(qid)),
                  key=lambda pair: (pair[0], pair[1].title))


Parents = Optional[Dict[str, Optional[str]]]


def breadcrumb(graph: Graph, qid: str, par: Parents = None) -> str:
    """The lineage as chips, ` › ` between them: pointing at another tab,
    every step is a chip, or the last step of the path is the one that does
    not lead anywhere. ``par`` is the projection's parents, which a caller
    rendering many computes once."""
    return " › ".join(chip(a) for a in project.lineage(graph, qid, par))


#: What opens a divergence's counter-clause inside its citation item. A
#: divergence is a deadlock with another party, so it says what is held
#: instead; the marker is what lets an export be read back into the field.
INSTEAD = "Instead: "

#: what opens the block pointing a definition at the question its word has
#: earned, where the definition shadows that question for reach
SHADOW = GLYPHS["mention"]

#: what a mention says under its anchors when a term in its place would close a
#: cycle. It is derived from the edges at every render and never stored, so the
#: reason a mention is not a term cannot go stale or be forgotten.
CYCLE_NOTE = ("cycle: a term here would close a cycle, because the question it "
              "points at already stands above this one.")


def _citation_item(graph: Graph, target: str, note: str, counter: str = "",
                   par: Parents = None) -> str:
    crumb = breadcrumb(graph, target, par) if graph.get(target) else chip(target)
    parts = []
    note, counter = note.strip(), counter.strip()
    if note:
        parts.append(note if note.endswith(".") else note + ".")
    if counter:
        parts.append(INSTEAD + (counter if counter.endswith(".") else counter + "."))
    parts.append(crumb)
    return "- " + " ".join(parts)


def _tradition_blocks(graph: Graph, thesis: Thesis, par: Parents = None) -> List[str]:
    """Support and divergence, one bullet list each.

    Two lists and not one line, because the two relations are read differently:
    what a tradition supports can be leaned on, and where it diverges is where
    this graph is on its own and owes an argument.
    """
    blocks: List[str] = []
    for relation, heading in (("support", "Support"), ("divergence", "Divergence")):
        items = [_citation_item(graph, t.to, t.note, t.counter, par)
                 for t in thesis.traditions if t.relation == relation]
        if items:
            blocks.append("**%s**" % heading)
            blocks.append("\n".join(items))
    return blocks


def _citing(graph: Graph, qid: str) -> List[Tuple[str, str]]:
    """(relation, source question) for every thesis that cites ``qid``, sorted.

    A borrowed sense cites the party it was borrowed from as surely as a
    thesis does, so a definition's borrowing counts. It never diverges — a
    definition that departed from the sense it names would not be naming it —
    so it counts as support.

    One function for the list and for its chips. The two used to walk the
    graph separately, and when the list learned to count borrowings the chip
    map did not: a tab cited only through a definition wrote a chip with
    nothing behind it.
    """
    rows: Set[Tuple[str, str]] = set()
    for src in graph.questions:
        for thesis in src.theses:
            for trad in thesis.traditions:
                if trad.to == qid:
                    rows.add((trad.relation, src.id))
        for definition in src.definitions:
            if definition.tradition and definition.tradition.to == qid:
                rows.add(("support", src.id))
    return sorted(rows)


def _cited_by_blocks(graph: Graph, q: Question, par: Parents = None) -> List[str]:
    """The mirror: the theses that reach this question by a tradition edge.

    A tradition's lineage is not this graph's, so nothing leads to it in the
    tab tree and its masthead carries no terms. This is the list that would
    otherwise be missing — what a tradition is doing here at all.

    Sorted by source, because the rows are gathered by walking the graph and
    the graph's own order is whatever the document's tab order happened to be.
    Every other projection here is total and deterministic; this one was not,
    so the same graph read from a differently ordered document rendered a
    differently ordered list.
    """
    rows = _citing(graph, q.id)
    blocks: List[str] = []
    for relation, heading in (("support", "Support"), ("divergence", "Divergence")):
        items = ["- %s" % breadcrumb(graph, src, par)
                 for rel, src in rows if rel == relation]
        if items:
            blocks.append("**%s**" % heading)
            blocks.append("\n".join(items))
    return blocks


#: a line that opens a list item, in either spelling markdown allows
_LIST_ITEM = re.compile(r"^[ \t]*(%s)[ \t]+" % text.LIST_MARKER)

#: what separates one paragraph block from the next
BLANK_LINE = re.compile(r"\n[ \t]*\n")


def _block_spans(body_text: str) -> List[Tuple[int, int]]:
    """(start, end) of each paragraph block, split on a blank line."""
    spans: List[Tuple[int, int]] = []
    start = 0
    for gap in BLANK_LINE.finditer(body_text):
        spans.append((start, gap.start()))
        start = gap.end()
    spans.append((start, len(body_text)))
    return spans


def _is_list(block: str) -> bool:
    lines = [line for line in block.splitlines() if line.strip()]
    return bool(lines) and all(_LIST_ITEM.match(line) for line in lines)


def _placement(body_text: str, end: int) -> int:
    """Where the chip for an anchor ending at ``end`` is written.

    In a paragraph it follows the anchor, which is where the reader meets the
    clause. In a list item it goes at the end of the item: a bulleted clause is
    read as one thing, and a chip dropped after its first sentence cuts the
    item in half — which is exactly what the live notebook does on the root
    answer, where eight of ten chips sit after the bolded lead of a bullet
    rather than after the clause they belong to.
    """
    for start, stop in _block_spans(body_text):
        if not start <= end <= stop:
            continue
        block = body_text[start:stop]
        if not _is_list(block):
            return end
        offset = start
        item_end = stop
        for line in block.splitlines(keepends=True):
            if _LIST_ITEM.match(line) and offset > start and offset > end:
                item_end = offset
                break
            offset += len(line)
        return len(body_text[:item_end].rstrip())
    return end


def anchor_cuts(body_text: str, edges: List[Tuple[str, List[str]]]
                ) -> List[Tuple[int, int, str]]:
    """Where a chip goes, as ``(position, edge order, target)``, sorted.

    Named on its own because the inverse needs it: a chip the export kept as
    its bare label can only be told from the same word in prose by the place
    it stands in, and this is what decides that place going forward.
    """
    cuts: List[Tuple[int, int, str]] = []
    for order, (to, anchors) in enumerate(edges):
        for anchor in anchors:
            if not anchor:
                continue
            at = body_text.find(anchor)
            while at != -1:
                cuts.append((_placement(body_text, at + len(anchor)), order, to))
                at = body_text.find(anchor, at + 1)
    return sorted(cuts)


def anchored(body_text: str, edges: List[Tuple[str, List[str]]],
             token_of: Optional[Callable[[str], str]] = None) -> str:
    """``body_text`` with a chip after every occurrence of every anchor.

    One pass over the original text, occurrences taken left to right, so an
    inserted token is never itself scanned for an anchor that overlaps it.

    ``edges`` is one ``(target, anchors)`` pair per term and mention, in the
    order the renderer writes them. It is taken apart from the thesis so that
    the reader can run this forward over a candidate and check its own inverse
    against it: only insertion is defined here, so the inverse is a removal
    that this function has to agree with.
    """
    token_of = token_of or (lambda to: " " + chip(to))
    out: List[str] = []
    last = 0
    for at, _, to in anchor_cuts(body_text, edges):  # sorted, as it returns them
        out.append(body_text[last:at])
        out.append(token_of(to))
        last = at
    out.append(body_text[last:])
    return "".join(out)


def _anchored_text(thesis: Thesis) -> str:
    return anchored(thesis.text,
                    [(edge.to, list(edge.anchors))
                     for edge in list(thesis.terms) + list(thesis.mentions)])


def _thesis_blocks(graph: Graph, thesis: Thesis, index: int) -> List[str]:
    blocks = ["### %s %s" % (GLYPHS["thesis"], thesis.title)]
    # the answer's own state, and no standing beside it: the standing is read
    # off the state, so writing both would state one datum twice
    blocks.append("assent: %s · %s · provenance: thesis hinge"
                  % (thesis.assent, _dropdown(graph, thesis.state, answer_state_key(index))))
    blocks.append(_anchored_text(thesis))
    return blocks


def _glossary_blocks(q: Question) -> List[str]:
    """A definition, and where a borrowed sense was borrowed from.

    The borrowing closes the subsection as its own block, ending in the chip,
    so that a reader who wants the lineage has somewhere to click and a parser
    can tell the borrowing from the body it follows. Appended to the body's
    own paragraph neither would be true.

    An import has no body: the heading and the party's chip, because the sense
    is the party's and stands on the party's tab, where it has one home.
    """
    blocks: List[str] = []
    for definition in q.definitions:
        blocks.append("### %s" % glossary_heading(definition.word))
        if definition.body.strip():
            blocks.append(definition.body)
        if definition.tradition:
            note = definition.tradition.note.strip()
            line = chip(definition.tradition.to)
            if note:
                line = "%s %s" % (note if note.endswith(".") else note + ".", line)
            blocks.append(line)
        if definition.question:
            # a definition standing for a word that has earned a question of
            # its own: the sense here, for the users of the word that cannot
            # reach that question, and a pointer to where the argument is
            blocks.append("%s %s" % (SHADOW, chip(definition.question)))
    return blocks


def glossary_heading(word: str) -> str:
    """A definition's heading without its level: the glyph and the word.

    Named because two things spell it — the glossary, and the link a thesis
    carries to the entry — and a run writing one entry in place is a third.
    """
    return "%s %s" % (GLYPHS["glossary"], word)


def term_heading(term: Term) -> str:
    """The part of a term's heading that is stable text a link can name.

    The heading ends in a chip, which is a token before the write and a block
    id after it, so only this prefix can be searched for on the page.
    """
    return "%s %s" % (GLYPHS["term"], term.title)


def term_line(term: Term) -> str:
    """A term's whole heading without its level: the stable part and the chip
    to the question it raises."""
    return "%s → %s" % (term_heading(term), chip(term.to))


def anchor_line(anchor: str) -> str:
    """An anchor as its own block under a term or a mention: the clause,
    italicised, and nothing else — one layer, which the reader takes off."""
    return "*%s*" % anchor


def incoming_item(anchor: str, source: str) -> str:
    """One item of a tab's header list: an anchor of a term that leads here,
    and the chip back to the tab whose term section holds it."""
    return "- %s %s" % (anchor, chip(source))


def _term_blocks(graph: Graph, q: Question) -> List[str]:
    blocks: List[str] = []
    for term in q.terms():
        blocks.append("### %s" % term_line(term))
        for anchor in term.anchors:
            blocks.append(anchor_line(anchor))
        if term.cue:
            # the situation the clause governs, the label the AI reads
            # records by: after the anchors, before what stands on the clause
            blocks.append("cue: %s" % term.cue)
        if term.suspended:
            # acceptance withheld while the thread is open, and what it waits
            # on; a paragraph of its own for the reason a deadlock has two
            blocks.append("suspended: %s" % term.suspended)
        if term.deadlock:
            # two labelled blocks and not one: the dissent and the grading it
            # earns are separate data, and a reader looking for what a
            # deadlocked clause may still license should not have to find it
            # inside a sentence about something else.
            blocks.append("deadlock: %s" % term.deadlock.counter)
            if term.deadlock.attenuation:
                blocks.append("attenuation: %s" % term.deadlock.attenuation)
    for mention in q.mentions():
        # ↗ and not ▸: a cross-reference is listed with the terms because it is
        # a clause pointing somewhere, and marked apart from them because it
        # raised nothing. Without an entry of its own it could not be told from
        # a term on the page at all, and the next export would read it as one.
        blocks.append("### %s %s → %s" % (SHADOW, mention.title, chip(mention.to)))
        for anchor in mention.anchors:
            blocks.append(anchor_line(anchor))
        if q.id in project.reachable_from(graph, mention.to):
            blocks.append(CYCLE_NOTE)
    return blocks


def _application_blocks(q: Question) -> List[str]:
    """One subsection per artifact, saying which thesis it comes from.

    The thesis is named and not merely implied: a question may carry several
    answers, and an artifact built from one of them is not built from the
    others. It also has to be legible on the page — an application that did not
    say whose it was could not be read back off the render at all.
    """
    blocks: List[str] = []
    for thesis, app in q.applications():
        blocks.append("### %s %s" % (GLYPHS["application"], app.name))
        standing = app.standing
        clause = discharge_clause(q, thesis, app)
        if clause:
            standing = "%s (%s)" % (standing, clause)
        blocks.append(application_line(app, thesis.title, standing))
    return blocks


def application_line(app: Application, thesis_title: str, standing: str) -> str:
    """An application's one line, as a tab carries it under its heading.

    ``standing`` is the whole standing as the page shows it, the discharge
    clause included. The line is written here and nowhere else, so that a run
    changing one application in place writes what a body render would have.
    """
    line = "%s · %s %s · %s · %s" % (app.what, GLYPHS["thesis"], thesis_title,
                                     app.link, standing)
    if app.note.strip():
        line += " · %s" % app.note.strip()
    return line


def discharge_clause(q: Question, thesis: Thesis, app: Application) -> str:
    """What would discharge a postulate, read off its answer and never written.

    It was written, into eight notes, and six went stale at once when the
    answerer field arrived: they promised a discharge on questions whose
    answers never land. Derived, it cannot. Nothing the principal answers
    lands, so what rests on it stays a postulate while he answers; an AI
    answer discharges it by landing and then by the diff, which no state
    records, so once it has landed the clause names the diff alone.
    """
    if app.standing != STANDINGS[1]:
        return ""
    if q.answerer == ANSWERERS[1]:
        return "while the principal answers this question"
    if q.answerer != ANSWERERS[0]:
        return ""
    if thesis.state == STATES[-1]:
        return "until the artifact is diffed against this answer"
    return "until this answer lands and the artifact is diffed against it"


#: the heading of each part of a hinge, by the part's name: the glyph, the
#: name and what the part says, as ``Hinge.PARTS`` spells them; the reader
#: takes a part back by the name its heading opens with
HINGE_HEADING = {name: "%s %s: %s" % (GLYPHS["hinge"], name, gloss)
                 for name, gloss, _ in Hinge.PARTS}

#: the heading of a hinge's question half: what the asking stood on, and so
#: one place besides an answer where a question brings a word in
HINGE_QUESTION = HINGE_HEADING["question"]

#: the heading of a hinge's end: what the asking is for, in the human's own
#: words, stated at a root and inherited below it; it brings words in too
HINGE_END = HINGE_HEADING["end"]

#: the heading of a hinge's method: how the end is read and pursued
HINGE_METHOD = HINGE_HEADING["method"]

#: the asker's parts of the hinge with their headings, in page order
HINGE_ASKING = tuple((name, HINGE_HEADING[name]) for name in Hinge.ASKING)

#: the heading of a hinge's thesis half, which every answer's provenance names
HINGE_THESIS = HINGE_HEADING["thesis"]

#: what a hinge's thesis half says when a run amends the answer it records:
#: the day, who amended it, and from what. Appended to the provenance and
#: never written over it, because the provenance is what the answer was
#: drawn from and the amendment is one more thing it now stands on.
AMENDED = "amended %s by %s, from %s"


def amended(provenance: str, day: str, by: str, source: str) -> str:
    """A hinge's thesis half with one amendment clause appended."""
    return "%s · %s" % (provenance.rstrip(), AMENDED % (day, by, source))


#: the words on an answer's metadata line that carry its provenance link
PROVENANCE_ANCHOR = "thesis hinge"

#: the blocks key for the question's state dropdown, one per tab
STATE_KEY = "state"


def answer_state_key(index: int) -> str:
    """The blocks key for an answer's state dropdown: one per answer, counted
    from one in the order the answers stand on the tab."""
    return "%s_%d" % (STATE_KEY, index + 1)


def _dropdown(graph: Graph, state: str, key: str) -> str:
    """A state as the page holds it — the question's, or an answer's on the
    same terms: a dropdown against the document's enum where the graph names
    one, written against ``key`` in the blocks map. Plain text where it
    names none, so a fresh graph still writes a readable tab rather than a
    chip against an enum that does not exist."""
    if graph.state_enum and state in STATES:
        return token(key)
    return state


def _note_blocks(q: Question, section: str) -> List[str]:
    """A human's own notes on a section, as a blockquote.

    Marked, because the export has to be able to tell them from the prose the
    renderer wrote — otherwise the round trip reads a note as content and the
    next render writes it back as content.
    """
    out: List[str] = []
    for note in q.notes:
        if note.section.strip().lower() != section:
            continue
        out.append("\n".join("> %s" % line if line.strip() else ">"
                              for line in note.body.splitlines()))
    return out


def _hinge_blocks(q: Question) -> List[str]:
    if q.hinge is None or q.hinge.empty():
        return []
    blocks: List[str] = []
    for name, part in q.hinge.parts():
        # the end's cue stands under the end's heading, right after its
        # words: a labelled block and not a fifth part, so it takes no
        # heading of its own and is written even where the end is blank,
        # since a block with no heading over it would be lost to the reader
        cue = q.hinge.cue if name == "end" else ""
        if part.strip() or cue.strip():
            blocks.append("### %s" % HINGE_HEADING[name])
            if part.strip():
                blocks.append(part)
            if cue.strip():
                blocks.append("cue: %s" % cue)
    return blocks


# -- the body ---------------------------------------------------------------

def body(graph: Graph, qid: str, par: Parents = None) -> str:
    """The canonical markdown body for one tab. Empty sections are omitted.
    ``par`` is the projection's parents, which a caller rendering every tab
    computes once: the body asks for it, and for a lineage from it, per
    citation and per cited-by row."""
    q = graph.get(qid)
    if q is None:
        raise KeyError("no question %r" % qid)
    par = project.parents(graph) if par is None else par
    top_level = par.get(qid) is None

    # the breadcrumb stands above the title and carries the lineage alone: it
    # says where the reader is arriving from, and the title says where he has
    # arrived, so repeating the question's own name at the end of the path
    # only asserts it twice. A root has no path and says so.
    ancestry = project.lineage(graph, qid, par)[:-1]
    blocks: List[str] = ["%s %s" % (GLYPHS["lineage"], " › ".join(chip(a) for a in ancestry)
                                    if ancestry else "root")]

    blocks.append("# %s" % q.id)

    if not top_level:
        # one item per anchor, each ending in a chip to the tab whose term
        # section holds it, so a question with several parents names them all
        # and the reader can get back to any of them
        blocks.append("\n".join(
            incoming_item(anchor, src)
            for src, term in _incoming_terms(graph, qid)
            for anchor in term.anchors))

    blocks.append("*%s*" % q.question)

    # no standing here: it is read off the state, and a question's answers
    # carry states of their own on their own sections
    meta = "question: %s · %s" % (_dropdown(graph, q.state, STATE_KEY), q.kind)
    if q.answerer:
        meta += " · answerer: %s" % q.answerer
    meta += " · pressure %d · backlog %d · load %d" % (
        q.pressure, project.backlog(graph, qid), project.load(graph, qid))
    blocks.append(meta)

    thesis_blocks: List[str] = []
    for index, thesis in enumerate(q.theses):
        thesis_blocks.extend(_thesis_blocks(graph, thesis, index))
        thesis_blocks.extend(_tradition_blocks(graph, thesis, par))
    for name, section in (("thesis", thesis_blocks),
                          ("glossary", _glossary_blocks(q)),
                          ("terms", _term_blocks(graph, q)),
                          ("applications", _application_blocks(q)),
                          ("cited by", _cited_by_blocks(graph, q, par)),
                          ("hinge", _hinge_blocks(q))):
        notes = _note_blocks(q, name)
        # a note opens its section even when the section is otherwise empty,
        # or it is written to a heading that is never rendered and is lost
        if section or notes:
            blocks.append("## %s" % name.title().replace(" By", " by"))
            blocks.extend(section)
            blocks.extend(notes)

    return SEPARATOR.join(b.strip("\n") for b in blocks) + "\n"


def mention_targets(graph: Graph, qid: str, par: Parents = None) -> List[str]:
    """The questions this tab points at with a chip, in order of first use."""
    q = graph.get(qid)
    par = project.parents(graph) if par is None else par
    if q is None:
        raise KeyError("no question %r" % qid)
    targets: List[str] = []

    def add(target: str) -> None:
        if target and target not in targets:
            targets.append(target)

    if par.get(qid) is not None:
        for ancestor in project.lineage(graph, qid, par)[:-1]:
            add(ancestor)
        for src, _ in _incoming_terms(graph, qid):
            add(src)  # a parent outside the lineage still gets its chip
    for thesis in q.theses:
        for term in thesis.terms:
            add(term.to)
        for mention in thesis.mentions:
            add(mention.to)
        for trad in thesis.traditions:
            # a citation is a breadcrumb, so every step of it carries a chip
            for step in (project.lineage(graph, trad.to, par)
                         if graph.get(trad.to) else [trad.to]):
                add(step)
    for definition in q.definitions:
        # a borrowing is one chip and not a breadcrumb: it closes a
        # sentence rather than standing on a line of its own
        if definition.tradition:
            add(definition.tradition.to)
        if definition.question:
            add(definition.question)
    for _, src in _citing(graph, qid):  # the mirror, on a tab something cites
        for step in project.lineage(graph, src, par):
            add(step)
    return targets


def mention_blocks(graph: Graph, qid: str, par: Parents = None) -> Dict[str, Dict[str, str]]:
    """The ``blocks`` map the markdown's chips are written against.

    A target no question in the graph answers to carries no tab to refer to, so
    it is omitted here; ``term-target`` reports it.
    """
    by_id = graph.by_id()
    blocks = {chip_key(target): {"type": "mention", "ref": "file/%s" % by_id[target].tab}
              for target in mention_targets(graph, qid, par) if target in by_id}
    q = graph.get(qid)
    if graph.state_enum and q is not None and q.state in STATES:
        blocks[STATE_KEY] = {"type": "dropdown", "enum": graph.state_enum,
                             "index": STATES.index(q.state)}
    if graph.state_enum and q is not None:
        for index, thesis in enumerate(q.theses):
            if thesis.state in STATES:
                blocks[answer_state_key(index)] = {
                    "type": "dropdown", "enum": graph.state_enum,
                    "index": STATES.index(thesis.state)}
    return blocks


def links(graph: Graph, qid: str, par: Parents = None,
          rendered: Optional[str] = None) -> Dict[str, object]:
    """Every link the caller must apply after the write, and the chips' blocks.
    ``rendered`` is the body, where the caller has it already; ``par`` the
    projection's parents, where it renders many.

    Block ids are unknown until the write returns, so a target names a tab and
    a string that stands verbatim in that tab's body — a heading, glyph and
    all — which the caller resolves to a block id once it has one. The incoming
    entries are the anchors this tab opens with: the terms that lead here, made
    clickable back to the term section on the tab they were written on.

    ``anchor`` is the plain form: the page holds characters and applies
    emphasis beside them, so a search for the marked-up spelling finds nothing.
    ``find`` is that anchor as a target the document can take — the text and
    the ``nth`` occurrence of it on this tab, counted the way the document
    counts — resolved here rather than left to the caller, because most
    anchors repeat and a one-word anchor repeats inside longer words.

    Which run is meant is decided by where the link lives. An entry is
    eligible only for a run inside its own section (``_HOME``) and never for
    one inside a heading, and two entries sharing an anchor within a section
    take successive runs. Without the first of those, words that stand in two
    sections are linked in whichever comes first — the same words, saying
    something else.

    A definition's anchor is a headword rather than a passage, so every
    regular form of it is looked for and ``find`` names the one that stands on
    the page: a thesis that says ``grants`` and never ``grant`` has anchored
    the word, and the link goes on the whole of ``grants``.

    ``find`` is null where no run qualifies, which ``anchor-substring`` and
    ``definition-anchorable`` between them prevent — the second asks for what
    is asked for here, a whole run of some form of the word in the thesis.
    """
    q = graph.get(qid)
    if q is None:
        raise KeyError("no question %r" % qid)
    by_id = graph.by_id()
    out: List[Dict[str, str]] = []
    for parent_id, term in _incoming_terms(graph, qid):
        parent_tab = by_id[parent_id].tab if parent_id in by_id else parent_id
        for anchor in term.anchors:
            out.append({
                "kind": "incoming",
                "from": parent_id,
                "term": term.title,
                "anchor": text.plain(anchor),
                "target": "#%s.%s" % (parent_tab, term_heading(term)),
            })
    for term in q.terms():
        for anchor in term.anchors:
            out.append({
                "kind": "term",
                "term": term.title,
                "anchor": text.plain(anchor),
                "to": term.to,
                # the term's own section, on this tab: the reader follows a
                # clause down to the term that carries it, and the chip beside
                # the anchor is what navigates to the question it raises
                "target": "#%s.%s" % (q.tab, term_heading(term)),
            })
    for definition in q.definitions:
        heading = glossary_heading(definition.word)
        out.append({
            "kind": "definition",
            "word": definition.word,
            "anchor": text.plain(definition.word),
            "heading": heading,
            "target": "#%s.%s" % (q.tab, heading),
        })
    if q.hinge is not None and q.hinge.thesis.strip():
        # each answer's metadata names its provenance, and the provenance is
        # the thesis half of the hinge: one link per answer, on its own line
        for _ in q.theses:
            out.append({
                "kind": "provenance",
                "anchor": PROVENANCE_ANCHOR,
                "target": "#%s.%s" % (q.tab, HINGE_THESIS),
            })
    page = _as_the_page_holds_it(body(graph, qid, par) if rendered is None else rendered)
    fixed = _fixed_spans(page)
    sections = _section_spans(page)
    taken: Dict[Tuple[str, Optional[str]], int] = {}
    spans: List[Optional[Tuple[int, int]]] = []
    for entry in out:
        anchor = entry["anchor"]
        runs = eligible(page, entry["kind"], anchor, fixed, sections)
        # successive runs are handed out per anchor within one section. The
        # key folds case for the same reason the counting does — a clause and
        # the title of the term it raises are often the same words — and it
        # carries the section because each draws from a pool of its own: an
        # incoming anchor and a thesis clause are each the first run of theirs.
        home = _HOME[entry["kind"]]
        if (entry["kind"] == "definition" and runs
                and not _inside(runs[0][1].at, sections.get(home))):
            home = _HINGE_POOL  # a word the hinge's asking brought in
        key = (text.fold(anchor), home)
        used = taken.get(key, 0)
        chosen = runs[used] if used < len(runs) else None
        entry["find"] = ({"text": chosen[0], "nth": chosen[1].nth}
                         if chosen else None)
        # where the run stands on the page as the document holds it: what a
        # write of one section asks, to keep the links that stand in it
        entry["at"] = chosen[1].at if chosen else None
        taken[key] = used + 1
        spans.append((chosen[1].at, chosen[1].at + len(chosen[0]))
                     if chosen else None)
    # a clause may be anchored whole and one of its sentences anchored again:
    # two links over one another. The document takes the outer and skips the
    # inner — silently, as a no-op rather than a refusal — so the entry is
    # marked rather than dropped. It is still sent, because which overlaps
    # actually land is the document's call and not this one's: a link that
    # begins where the outer one begins is skipped, one that starts inside it
    # is not. What this field is for is explaining a link that never arrives.
    for entry, mine in zip(out, spans):
        entry["covered_by"] = next(
            (other["anchor"] for other, theirs in zip(out, spans)
             if other is not entry and mine and theirs
             and theirs[0] <= mine[0] and mine[1] <= theirs[1]
             and theirs[1] - theirs[0] > mine[1] - mine[0]),
            None)
    return {"question": q.id, "tab": q.tab,
            "blocks": mention_blocks(graph, qid, par), "links": out}


#: a chip, as the renderer writes one, with the space that carries it.
CHIP_TOKEN = re.compile(r" ?<\?claude block ([0-9A-Za-z_]+)\?>")


def _as_the_page_holds_it(rendered: str) -> str:
    """A rendered body as the characters the document will hold.

    Emphasis comes off because the page stores it beside the words rather
    than in them. A **chip** comes off because it is a token here and an atom
    there: the word inside ``<?claude block m_priority?>`` is not a word the
    document can find, so counting it makes every later run of that word one
    too high. Two links went that way — ``\u2261 state`` onto the letters inside
    *stated*, and ``\u2261 priority`` onto its own heading — and neither is
    visible afterwards, since the page the checker reads back has no chips in
    it either and agrees with the document about where the link is.
    """
    return CHIP_TOKEN.sub("", text.plain(rendered))


def page_text(graph: Graph, qid: str, rendered: Optional[str] = None) -> str:
    """A tab's characters as the document counts them, chips not among them.

    What ``links`` counts a run against, named so that the gate can ask for
    the same string rather than rebuild it; ``rendered`` is the body, where
    the gate has rendered it already.
    """
    return _as_the_page_holds_it(body(graph, qid) if rendered is None else rendered)


#: which section of the page each kind of link is a link *in*. Every one of
#: these is the encoding's own statement: a clause of the thesis is anchor
#: text linked to its term section, the defined word is anchor text in the
#: thesis text, each answer's metadata line links its provenance, and the
#: incoming anchors stand above the first heading. A link put anywhere else is a link on words
#: that mean the same and say something else.
#:
#: The home is the section and not the one answer: a term's runs are handed
#: out in page order across every answer under ``## Thesis``, so a term on a
#: second answer whose anchor the first answer also says would be linked on
#: the first. ``anchor-unique`` counts across the answers on the tab for that
#: reason, and stands between this scope and the wrong answer.
_HOME = {"incoming": None,   # None: above the first section
         "term": "Thesis", "definition": "Thesis", "provenance": "Thesis"}

#: the one pool a definition's runs are drawn from where the hinge's asking
#: brought the word in: its parts share it, so it is named for none of them
_HINGE_POOL = GLYPHS["hinge"]


def _candidates(kind: str, anchor: str) -> Tuple[List[str], bool]:
    """The spellings to look for on the page, and whether each stands whole.

    A one-word anchor is a substring of longer words — `merge` of `merged`,
    `prior` of `priority` — so which run of characters is meant has to be
    decided against the page and handed over as a number the document can
    count to.

    A definition's anchor is a headword rather than a passage: the thesis
    uses whichever inflection its sentence wants, so every regular form is
    looked for and the link goes on the one that actually stands there.
    Longest first, so `grants` is linked whole instead of as the `grant`
    hiding inside it — which is also why a headword is matched as a word
    however many words it has.
    """
    if kind == "definition":
        return text.forms(anchor), True
    return [anchor], len(anchor.split()) == 1


def eligible(page: str, kind: str, anchor: str,
             fixed: Optional[List[Tuple[int, int]]] = None,
             sections: Optional[Dict[Optional[str], Tuple[int, int]]] = None,
             ) -> List[Tuple[str, "text.Run"]]:
    """The runs of ``page`` a link of this kind and anchor may stand on.

    Where a link may go is the encoding's business and not the caller's: the
    section that kind of link lives in, and that a heading and the answer
    metadata line are destinations rather than sources. So it is decided
    here, once — and it is a function of a page rather than of the graph,
    because the checker has to ask the same question of the page it reads
    back.

    That is the whole reason this is not private. The renderer's guarantee
    ends at the payload: it names a run by a number, and the **document**
    resolves that number against characters of its own. Where the two
    disagree about which run was meant, nothing upstream can see it — the
    tool believes the link went where it asked, and the graph file never held
    a link at all. Only the page knows, so only the page can be asked.
    """
    fixed = _fixed_spans(page) if fixed is None else fixed
    sections = _section_spans(page) if sections is None else sections
    # a section the page does not have holds no run: an absent home is not
    # licence to link anywhere
    home = sections.get(_HOME[kind])
    runs = _eligible_in(page, kind, anchor, fixed, [home]) if home else []
    if kind == "definition" and not runs:
        # a question brings a word in through an answer or through the
        # asker's parts of its hinge: what the asking stood on, what it is
        # for, how that is read. A word only the hinge brought in is linked
        # there, in those parts and never in the answer's provenance
        asking = _hinge_asking_spans(page)
        runs = _eligible_in(page, kind, anchor, fixed, asking) if asking else []
    return runs


def _eligible_in(page: str, kind: str, anchor: str,
                 fixed: List[Tuple[int, int]],
                 homes: List[Tuple[int, int]]) -> List[Tuple[str, "text.Run"]]:
    """The runs inside any of the spans ``homes`` a link of this kind may
    stand on, in page order: the page is scanned once per form, whichever
    span the run falls in."""
    candidates, whole = _candidates(kind, anchor)
    # the provenance link is the one link the answer metadata line carries, so
    # it may stand there and nowhere else; every other kind is kept off it
    metadata = _metadata_spans(page) if kind == "provenance" else []
    out: List[Tuple[int, str, text.Run]] = []
    seen: Set[int] = set()
    for form in candidates:
        for run in text.occurrences(page, form, whole):
            if run.at in seen:
                continue  # a longer form already claimed this run
            if kind == "provenance":
                if not any(at <= run.at < end for at, end in metadata):
                    continue
            elif any(at <= run.at < end for at, end in fixed):
                continue
            if not any(at <= run.at < end for at, end in homes):
                continue
            seen.add(run.at)
            out.append((run.at, form, run))
    out.sort()
    return [(form, run) for _, form, run in out]


def _inside(at: int, span: Optional[Tuple[int, int]]) -> bool:
    return span is not None and span[0] <= at < span[1]


#: a heading line as the page takes one: the marks and then a space, so a
#: paragraph opening ``#1`` is a paragraph. The one test for every walker
#: here: a walker that took any line opening ``#`` for a heading ended the
#: hinge's end at a line of it that counted, and the word on that line was
#: found nowhere, while the reader and the checker took the line for prose
_HEADING = re.compile(r"(#{1,6}) ")


def _lines(page: str) -> Iterator[Tuple[int, str]]:
    """Each line of the page with the offset it starts at, newline kept. A
    line ends at a newline only, as the reader's blocks do: ``splitlines``
    also breaks at a form feed, a vertical tab or a line separator, which the
    page holds inside a line."""
    at = 0
    for line in re.findall(r"[^\n]*\n|[^\n]+", page or ""):
        yield at, line
        at += len(line)


def _headings(page: str) -> Iterator[Tuple[int, str, int]]:
    """Each heading line of the page as the reader takes one, (offset, line,
    marks): a block's first line, unindented, the marks and a space. A line
    inside a paragraph, or an indented one, is prose to the reader, and so it
    is here."""
    opens = True
    for at, line in _lines(page):
        m = _HEADING.match(line) if opens else None
        if m:
            yield at, line, len(m.group(1))
        opens = not line.strip()


def _heading_spans(page: str, level: int) -> List[Tuple[str, int, int, int]]:
    """Every heading of exactly ``level`` marks, in page order, as (its
    text, where it starts, where its body starts, where the body ends): a
    body runs to the next heading of ``level`` or fewer marks, or to the end
    of the page."""
    out: List[Tuple[str, int, int, int]] = []
    opened: Optional[Tuple[str, int, int]] = None
    for at, line, marks in _headings(page):
        if marks <= level:
            if opened is not None:
                out.append(opened + (at,))
                opened = None
            if marks == level:
                opened = (line[marks + 1:].strip(), at, at + len(line))
    if opened is not None:
        out.append(opened + (len(page or ""),))
    return out


def _hinge_asking_spans(page: str) -> List[Tuple[int, int]]:
    """Where the asker's parts of the hinge stand — the question half, the
    end and the method — each heading excluded, in page order."""
    headings = {heading for _, heading in HINGE_ASKING}
    return [(body, end) for name, _, body, end in _heading_spans(page, 3)
            if name in headings]


def section_spans(page: str) -> Dict[Optional[str], Tuple[int, int]]:
    """Where each ``## `` section of a page begins and ends, by its heading;
    what a write of one section asks, to keep the links that stand in it."""
    return _section_spans(page)


def _section_spans(page: str) -> Dict[Optional[str], Tuple[int, int]]:
    """Where each `## ` section of the page begins and ends.

    ``None`` is the masthead: everything above the first section; a section
    is its heading and what stands under it, to the next ``## ``.
    """
    spans = _heading_spans(page, 2)
    out: Dict[Optional[str], Tuple[int, int]] = {
        None: (0, spans[0][1] if spans else len(page or ""))}
    for name, start, _, end in spans:
        out.setdefault(name, (start, end))
    return out


def _line_spans(page: str, is_one: Callable[[str], bool]) -> List[Tuple[int, int]]:
    """(start, end) of every line ``is_one`` takes."""
    return [(at, at + len(line)) for at, line in _lines(page) if is_one(line)]


def _fixed_spans(page: str) -> List[Tuple[int, int]]:
    """The lines whose links the encoding already decides.

    A **heading** is a link's destination and never its source. A definition's
    target is the glossary heading that spells the word, so the word's first
    standalone run on the page is that heading unless it is ruled out here —
    which is how `\u2261 grant` came to link to itself while the clause that
    uses the word went unlinked. The same rule keeps a link off a section
    heading that happens to spell the word, which is where the one meant for
    *thesis* in the prose landed.

    The **answer metadata** line is the other. It carries the assent, the
    standing and the provenance link "and nowhere else", and the section it
    opens says a defined word is anchor text *in the thesis text* — which the
    line before that text is not. Left eligible, four definitions took it, and
    `\u2261 thesis` pointed at the words `provenance: thesis hinge` rather than at
    the sentence that says what a thesis is.
    """
    heads = {at for at, _, _ in _headings(page)}
    return [(at, at + len(line)) for at, line in _lines(page)
            if at in heads or line.startswith("assent:")]


def _metadata_spans(page: str) -> List[Tuple[int, int]]:
    """The answer metadata lines alone: where the provenance link stands."""
    return _line_spans(page, lambda line: line.startswith("assent:"))


# -- the refusal ------------------------------------------------------------

def render(graph: Graph, qid: str,
           findings: Optional[List[spec.Finding]] = None) -> str:
    """The body, or RefusedError if an ERROR affects this question."""
    if findings is None:
        findings = spec.run(graph)
    blocking = spec.errors(spec.affecting(findings, qid))
    if blocking:
        raise RefusedError(qid, blocking)
    return body(graph, qid)


def render_all(graph: Graph,
               findings: Optional[List[spec.Finding]] = None) -> str:
    """Every tab, in projection order, separated by a `=== <question id> ===` line."""
    if findings is None:
        findings = spec.run(graph)
    blocking = spec.errors(findings)
    if blocking:
        raise RefusedError("--all", blocking)
    order = project.walk(graph)
    order += [q.id for q in graph.questions if q.id not in order]
    par = project.parents(graph)
    parts = []
    for qid in order:
        parts.append("=== %s ===\n\n%s" % (qid, body(graph, qid, par)))
    return "\n".join(parts)


def links_all(graph: Graph) -> List[Dict[str, object]]:
    order = project.walk(graph)
    order += [q.id for q in graph.questions if q.id not in order]
    par = project.parents(graph)
    return [links(graph, qid, par) for qid in order]
