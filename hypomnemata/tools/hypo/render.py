"""The renderer: the only sanctioned way to produce a tab's markdown.

A layout violation is impossible if the tool is used, so the layout lives here
and nowhere else. The renderer refuses to print a question the checker reports an
ERROR against, and emits, alongside the markdown, the links sidecar the caller
turns into ``format`` operations once the write has returned real block ids.

One tab points at another with a **mention chip**: the token ``<?claude block
KEY?>`` in the markdown, and an entry under the sidecar's ``blocks`` map naming
the tab it refers to. Every place the specification calls for a reference to a
question is written as a chip and never as a bare id, so the rule that no
identifier appears in prose is kept by construction.
"""

from __future__ import annotations

import re
from typing import Callable, Dict, List, Optional, Set, Tuple

from . import project, spec, text
from .model import (ANSWERERS, STANDINGS, STATES, Application, Graph, Question,
                     Term, Thesis)

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


def chip(qid: str) -> str:
    """The markdown token for a mention chip pointing at ``qid``."""
    return "<?claude block %s?>" % chip_key(qid)


class RefusedError(Exception):
    """The checker reports an ERROR affecting the question asked for."""

    def __init__(self, qid: str, findings: List[spec.Finding]):
        self.qid = qid
        self.findings = findings
        super().__init__("refusing to render %s: %d error(s)" % (qid, len(findings)))


# -- pieces -----------------------------------------------------------------

def _inbox_titles(graph: Graph) -> Dict[str, str]:
    """Every inbox item's id to the title a reader is shown."""
    return {item.id: item.title for q in graph.questions for item in q.inbox}


def _requires(graph: Graph, q: Optional[Question]) -> str:
    """What a question waits on, named by title and never by handle.

    The title is rendered and the id is stored, so rewording an item carries
    everywhere it is mentioned without a single edit elsewhere — which is the
    whole reason the two are separate.
    """
    if q is None:
        return "?"
    if not q.requires:
        return "nothing"
    titles = _inbox_titles(graph)
    return ", ".join(titles.get(want, want) for want in q.requires)


def _incoming_terms(graph: Graph, qid: str) -> List[Tuple[str, Term]]:
    """The term edges leading here, ordered by (parent id, term title)."""
    return sorted(((src.id, term) for src, term in graph.incoming(qid)),
                  key=lambda pair: (pair[0], pair[1].title))


def breadcrumb(graph: Graph, qid: str, plain_last: bool = True) -> str:
    """The lineage as chips, ` › ` between them.

    ``plain_last`` leaves the final element as text, which is right where the
    breadcrumb says where the reader already is. Pointing at another tab it
    must be a chip, or the last step of the path is the one that does not lead
    anywhere.
    """
    line = project.lineage(graph, qid)
    if plain_last:
        return " › ".join([chip(a) for a in line[:-1]] + line[-1:])
    return " › ".join(chip(a) for a in line)


#: What opens a divergence's counter-clause inside its citation item. A
#: divergence is a deadlock with another party, so it says what is held
#: instead; the marker is what lets an export be read back into the field.
INSTEAD = "Instead: "

#: what opens the block pointing a definition at the question its word has
#: earned, where the definition shadows that question for reach
SHADOW = "↗"

#: what a mention says under its anchors when a term in its place would close a
#: cycle. It is derived from the edges at every render and never stored, so the
#: reason a mention is not a term cannot go stale or be forgotten.
CYCLE_NOTE = ("cycle: a term here would close a cycle, because the question it "
              "points at already stands above this one.")


def _citation_item(graph: Graph, target: str, note: str, counter: str = "") -> str:
    crumb = breadcrumb(graph, target, plain_last=False) if graph.get(target) \
        else chip(target)
    parts = []
    note, counter = note.strip(), counter.strip()
    if note:
        parts.append(note if note.endswith(".") else note + ".")
    if counter:
        parts.append(INSTEAD + (counter if counter.endswith(".") else counter + "."))
    parts.append(crumb)
    return "- " + " ".join(parts)


def _tradition_blocks(graph: Graph, thesis: Thesis) -> List[str]:
    """Support and divergence, one bullet list each.

    Two lists and not one line, because the two relations are read differently:
    what a tradition supports can be leaned on, and where it diverges is where
    this graph is on its own and owes an argument.
    """
    blocks: List[str] = []
    for relation, heading in (("support", "Support"), ("divergence", "Divergence")):
        items = [_citation_item(graph, t.to, t.note, t.counter)
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


def _cited_by_blocks(graph: Graph, q: Question) -> List[str]:
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
        items = ["- %s" % breadcrumb(graph, src, plain_last=False)
                 for rel, src in sorted(rows) if rel == relation]
        if items:
            blocks.append("**%s**" % heading)
            blocks.append("\n".join(items))
    return blocks


#: a line that opens a list item, in either spelling markdown allows
_LIST_ITEM = re.compile(r"^[ \t]*([-*+]|\d+[.)])[ \t]+")

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
    cuts = [(at, order, token_of(to)) for at, order, to in anchor_cuts(body_text, edges)]
    if not cuts:
        return body_text
    out: List[str] = []
    last = 0
    for at, _, token in sorted(cuts, key=lambda cut: (cut[0], cut[1])):
        out.append(body_text[last:at])
        out.append(token)
        last = at
    out.append(body_text[last:])
    return "".join(out)


def _anchored_text(thesis: Thesis) -> str:
    return anchored(thesis.text,
                    [(edge.to, list(edge.anchors))
                     for edge in list(thesis.terms) + list(thesis.mentions)])


def _thesis_blocks(graph: Graph, thesis: Thesis, index: int) -> List[str]:
    blocks = ["### ◆ %s" % thesis.title]
    # the answer's own state, and no standing beside it: the standing is read
    # off the state, so writing both would state one datum twice
    blocks.append("assent: %s · %s · provenance: thesis hinge"
                  % (thesis.assent, _answer_state(graph, thesis, index)))
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
        blocks.append("### ≡ %s" % definition.word)
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


def _inbox_order(graph: Graph, q: Question) -> List[Term]:
    """The frontier, heaviest first, ties by question id.

    The order is what the section is for: it answers what to do next, and a
    table in file order answers nothing.
    """
    by_id = graph.by_id()

    def weight(term: Term) -> Tuple[int, str]:
        child = by_id.get(term.to)
        return (-(project.backlog(graph, term.to) if child else 0), term.to)

    def open_(term: Term) -> bool:
        # the frontier is what is still to be put: a question the principal
        # answers never is, and one whose answer has landed already was. A
        # dangling target stays, so that the row shows what term-target says
        child = by_id.get(term.to)
        return child is None or (child.answerer == project.AI
                                 and not project.landed(child))

    return sorted((term for term in q.terms() if open_(term)), key=weight)


def _inbox_blocks(graph: Graph, q: Question) -> List[str]:
    by_id = graph.by_id()
    rows = []
    for term in _inbox_order(graph, q):
        child = by_id.get(term.to)
        rows.append("| %s | %s | %s | %s | %s |" % (
            chip(term.to), term.title,
            child.kind if child else "?",
            project.backlog(graph, term.to) if child else "?",
            _requires(graph, child)))
    blocks: List[str] = []
    if rows:
        blocks.append("\n".join(
            ["| question | term | kind | backlog | requires |",
             "| --- | --- | --- | --- | --- |"] + rows))
    for item in q.inbox:
        blocks.append("### %s" % item.title)
        blocks.append("%s · %s · instances %s · %s · id %s" % (
            item.kind, item.what, item.obligation,
            "done" if item.done else "not done", item.id))
    return blocks


def term_heading(term: Term) -> str:
    """The part of a term's heading that is stable text a link can name.

    The heading ends in a chip, which is a token before the write and a block
    id after it, so only this prefix can be searched for on the page.
    """
    return "▸ %s" % term.title


def _term_blocks(graph: Graph, q: Question) -> List[str]:
    blocks: List[str] = []
    for term in q.terms():
        blocks.append("### %s → %s" % (term_heading(term), chip(term.to)))
        for anchor in term.anchors:
            blocks.append("*%s*" % anchor)
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
        blocks.append("### ↗ %s → %s" % (mention.title, chip(mention.to)))
        for anchor in mention.anchors:
            blocks.append("*%s*" % anchor)
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
        blocks.append("### ⚙ %s" % app.name)
        standing = app.standing
        clause = discharge_clause(q, thesis, app)
        if clause:
            standing = "%s (%s)" % (standing, clause)
        line = "%s · ◆ %s · %s · %s" % (app.what, thesis.title, app.link,
                                        standing)
        if app.note.strip():
            line += " · %s" % app.note.strip()
        blocks.append(line)
    return blocks


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


#: the heading of a hinge's question half: what the asking stood on, and so
#: the one place besides an answer where a question brings a word in
HINGE_QUESTION = "⚓ question: what the asking presupposes"

#: the heading of a hinge's thesis half, which every answer's provenance names
HINGE_THESIS = "⚓ thesis: what the answer was drawn from"

#: the words on an answer's metadata line that carry its provenance link
PROVENANCE_ANCHOR = "thesis hinge"

#: the blocks key for the question's state dropdown, one per tab
STATE_KEY = "state"


def answer_state_key(index: int) -> str:
    """The blocks key for an answer's state dropdown: one per answer, counted
    from one in the order the answers stand on the tab."""
    return "%s_%d" % (STATE_KEY, index + 1)


def _answer_state(graph: Graph, thesis: Thesis, index: int) -> str:
    """An answer's state as the page holds it, on the same terms as the
    question's: a dropdown against the same enum where the doc has one."""
    if graph.state_enum and thesis.state in STATES:
        return "<?claude block %s?>" % answer_state_key(index)
    return thesis.state


def _state(graph: Graph, q: Question) -> str:
    """The state as the page holds it: a dropdown where the doc has an enum.

    Rendered as plain text when the graph file names no enum, so a fresh graph
    still writes a readable tab rather than a chip against an enum that does
    not exist.
    """
    if graph.state_enum and q.state in STATES:
        return "<?claude block %s?>" % STATE_KEY
    return q.state


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
    if q.hinge.question.strip():
        blocks.append("### %s" % HINGE_QUESTION)
        blocks.append(q.hinge.question)
    if q.hinge.thesis.strip():
        blocks.append("### %s" % HINGE_THESIS)
        blocks.append(q.hinge.thesis)
    return blocks


# -- the body ---------------------------------------------------------------

def body(graph: Graph, qid: str) -> str:
    """The canonical markdown body for one tab. Empty sections are omitted."""
    q = graph.get(qid)
    if q is None:
        raise KeyError("no question %r" % qid)
    top_level = project.parents(graph).get(qid) is None

    # the breadcrumb stands above the title and carries the lineage alone: it
    # says where the reader is arriving from, and the title says where he has
    # arrived, so repeating the question's own name at the end of the path
    # only asserts it twice. A root has no path and says so.
    ancestry = project.lineage(graph, qid)[:-1]
    blocks: List[str] = ["⌂ " + " › ".join(chip(a) for a in ancestry)
                         if ancestry else "⌂ root"]

    blocks.append("# %s" % q.id)

    if not top_level:
        # one item per anchor, each ending in a chip to the tab whose term
        # section holds it, so a question with several parents names them all
        # and the reader can get back to any of them
        blocks.append("\n".join(
            "- %s %s" % (anchor, chip(src))
            for src, term in _incoming_terms(graph, qid)
            for anchor in term.anchors))

    blocks.append("*%s*" % q.question)

    # no standing here: it is read off the state, and a question's answers
    # carry states of their own on their own sections
    meta = "question: %s · %s" % (_state(graph, q), q.kind)
    if q.answerer:
        meta += " · answerer: %s" % q.answerer
    meta += " · pressure %d · backlog %d · load %d · requires: %s" % (
        q.pressure, project.backlog(graph, qid), project.load(graph, qid),
        _requires(graph, q))
    blocks.append(meta)

    thesis_blocks: List[str] = []
    for index, thesis in enumerate(q.theses):
        thesis_blocks.extend(_thesis_blocks(graph, thesis, index))
        thesis_blocks.extend(_tradition_blocks(graph, thesis))
    for name, section in (("thesis", thesis_blocks),
                          ("glossary", _glossary_blocks(q)),
                          ("inbox", _inbox_blocks(graph, q)),
                          ("terms", _term_blocks(graph, q)),
                          ("applications", _application_blocks(q)),
                          ("cited by", _cited_by_blocks(graph, q)),
                          ("hinge", _hinge_blocks(q))):
        notes = _note_blocks(q, name)
        # a note opens its section even when the section is otherwise empty,
        # or it is written to a heading that is never rendered and is lost
        if section or notes:
            blocks.append("## %s" % name.title().replace(" By", " by"))
            blocks.extend(section)
            blocks.extend(notes)

    return SEPARATOR.join(b.strip("\n") for b in blocks) + "\n"


def mention_targets(graph: Graph, qid: str) -> List[str]:
    """The questions this tab points at with a chip, in order of first use."""
    q = graph.get(qid)
    if q is None:
        raise KeyError("no question %r" % qid)
    targets: List[str] = []

    def add(target: str) -> None:
        if target and target not in targets:
            targets.append(target)

    if project.parents(graph).get(qid) is not None:
        for ancestor in project.lineage(graph, qid)[:-1]:
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
            for step in (project.lineage(graph, trad.to)
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
        for step in project.lineage(graph, src):
            add(step)
    return targets


def mention_blocks(graph: Graph, qid: str) -> Dict[str, Dict[str, str]]:
    """The ``blocks`` map the markdown's chips are written against.

    A target no question in the graph answers to carries no tab to refer to, so
    it is omitted here; ``term-target`` reports it.
    """
    by_id = graph.by_id()
    blocks = {chip_key(target): {"type": "mention", "ref": "file/%s" % by_id[target].tab}
              for target in mention_targets(graph, qid) if target in by_id}
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


def links(graph: Graph, qid: str) -> Dict[str, object]:
    """Every link the caller must apply after the write, and the chips' blocks.

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
    take successive runs. Without the first of those, an inbox row whose title
    also opens a clause of the thesis linked the clause instead — the same
    words, saying something else.

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
        heading = "≡ %s" % definition.word
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
    titles = _inbox_titles(graph)
    homes = {item.id: home for home in graph.questions for item in home.inbox}
    for term in _inbox_order(graph, q):
        out.append({
            "kind": "inbox-term",
            "term": term.title,
            "anchor": text.plain(term.title),
            "target": "#%s.%s" % (q.tab, term_heading(term)),
        })
        child = by_id.get(term.to)
        for want in (child.requires if child else []):
            home = homes.get(want)
            if home is None:  # requires-exist reports it
                continue
            # the table's requires cell names what the row's question waits on,
            # and each name goes to the item it names, wherever that item lives
            out.append({
                "kind": "inbox-requires",
                "item": want,
                "anchor": text.plain(titles[want]),
                "target": "#%s.%s" % (home.tab, titles[want]),
            })
    for want in q.requires:
        home = homes.get(want)
        if home is None:  # requires-exist reports it; there is nothing to point at
            continue
        out.append({
            "kind": "requires",
            "item": want,
            "anchor": text.plain(titles[want]),
            "target": "#%s.%s" % (home.tab, titles[want]),
        })
    page = _as_the_page_holds_it(body(graph, qid))
    fixed = _fixed_spans(page)
    sections = _section_spans(page)
    taken: Dict[Tuple[str, Optional[str]], int] = {}
    spans: List[Optional[Tuple[int, int]]] = []
    for entry in out:
        anchor = entry["anchor"]
        entry["whole_word"] = _candidates(entry["kind"], anchor)[1]
        runs = eligible(page, entry["kind"], anchor, fixed, sections)
        # successive runs are handed out per anchor within one section. The
        # key folds case for the same reason the counting does — a clause and
        # the title of the term it raises are often the same words — and it
        # carries the section because the two draw from different pools: a
        # thesis clause and an inbox row are each the first run of their own.
        home = _HOME[entry["kind"]]
        if (entry["kind"] == "definition" and runs
                and not _inside(runs[0][1].at, sections.get(home))):
            home = HINGE_QUESTION  # a word the hinge brought in
        key = (text.fold(anchor), home)
        used = taken.get(key, 0)
        chosen = runs[used] if used < len(runs) else None
        entry["find"] = ({"text": chosen[0], "nth": chosen[1].nth}
                         if chosen else None)
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
            "blocks": mention_blocks(graph, qid), "links": out}


#: a chip, as the renderer writes one, with the space that carries it.
CHIP_TOKEN = re.compile(r" ?<\?claude block ([0-9A-Za-z_]+)\?>")
_CHIP_TOKEN = CHIP_TOKEN


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
    return _CHIP_TOKEN.sub("", text.plain(rendered))


def page_text(graph: Graph, qid: str) -> str:
    """A tab's characters as the document counts them, chips not among them.

    What ``links`` counts a run against, named so that the gate can ask for
    the same string rather than rebuild it.
    """
    return _as_the_page_holds_it(body(graph, qid))


#: which section of the page each kind of link is a link *in*. Every one of
#: these is the encoding's own statement: a clause of the thesis is anchor
#: text linked to its term section, the defined word is anchor text in the
#: thesis text, each answer's metadata line links its provenance, the inbox
#: table's term column is linked to the term section and its requires column
#: to the items, and the incoming anchors and the question line's requires
#: stand above the first heading. A link put anywhere else is a link on words
#: that mean the same and say something else.
_HOME = {"incoming": None, "requires": None,   # None: above the first section
         "term": "Thesis", "definition": "Thesis", "provenance": "Thesis",
         "inbox-term": "Inbox", "inbox-requires": "Inbox"}


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
    runs = _eligible_in(page, kind, anchor, fixed, home) if home else []
    if kind == "definition" and not runs:
        # a question brings a word in through an answer or through what its
        # asking stood on; a word only the hinge brought in is linked there,
        # in the question half and never in the answer's provenance
        hinge = _hinge_question_span(page)
        runs = _eligible_in(page, kind, anchor, fixed, hinge) if hinge else []
    return runs


def _eligible_in(page: str, kind: str, anchor: str,
                 fixed: List[Tuple[int, int]],
                 home: Tuple[int, int]) -> List[Tuple[str, "text.Run"]]:
    """The runs of one span a link of this kind may stand on."""
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
            if not home[0] <= run.at < home[1]:
                continue
            seen.add(run.at)
            out.append((run.at, form, run))
    out.sort()
    return [(form, run) for _, form, run in out]


def _inside(at: int, span: Optional[Tuple[int, int]]) -> bool:
    return span is not None and span[0] <= at < span[1]


def _hinge_question_span(page: str) -> Optional[Tuple[int, int]]:
    """Where the question half of the hinge stands, heading excluded."""
    start: Optional[int] = None
    at = 0
    for line in (page or "").splitlines(keepends=True):
        if start is None:
            if line.strip() == "### " + HINGE_QUESTION:
                start = at + len(line)
        elif line.startswith("#"):
            return (start, at)
        at += len(line)
    return None if start is None else (start, len(page or ""))


def _section_spans(page: str) -> Dict[Optional[str], Tuple[int, int]]:
    """Where each `## ` section of the page begins and ends.

    ``None`` is the masthead: everything above the first section.
    """
    marks: List[Tuple[Optional[str], int]] = [(None, 0)]
    at = 0
    for line in (page or "").splitlines(keepends=True):
        if line.startswith("## ") and not line.startswith("###"):
            marks.append((line[3:].strip(), at))
        at += len(line)
    out: Dict[Optional[str], Tuple[int, int]] = {}
    for i, (name, start) in enumerate(marks):
        end = marks[i + 1][1] if i + 1 < len(marks) else len(page or "")
        out.setdefault(name, (start, end))
    return out


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
    out: List[Tuple[int, int]] = []
    at = 0
    for line in (page or "").splitlines(keepends=True):
        if line.lstrip().startswith("#") or line.startswith("assent:"):
            out.append((at, at + len(line)))
        at += len(line)
    return out


def _metadata_spans(page: str) -> List[Tuple[int, int]]:
    """The answer metadata lines alone: where the provenance link stands."""
    out: List[Tuple[int, int]] = []
    at = 0
    for line in (page or "").splitlines(keepends=True):
        if line.startswith("assent:"):
            out.append((at, at + len(line)))
        at += len(line)
    return out


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
    parts = []
    for qid in order:
        parts.append("=== %s ===\n\n%s" % (qid, body(graph, qid)))
    return "\n".join(parts)


def links_all(graph: Graph) -> List[Dict[str, object]]:
    order = project.walk(graph)
    order += [q.id for q in graph.questions if q.id not in order]
    return [links(graph, qid) for qid in order]
