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
from typing import Dict, List, Optional, Tuple

from . import project, spec, text
from .model import STATES, Graph, Question, Term, Thesis

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


def _citation_item(graph: Graph, target: str, note: str) -> str:
    crumb = breadcrumb(graph, target, plain_last=False) if graph.get(target) \
        else chip(target)
    note = note.strip()
    if not note:
        return "- %s" % crumb
    return "- %s %s" % (note if note.endswith(".") else note + ".", crumb)


def _tradition_blocks(graph: Graph, thesis: Thesis) -> List[str]:
    """Support and divergence, one bullet list each.

    Two lists and not one line, because the two relations are read differently:
    what a tradition supports can be leaned on, and where it diverges is where
    this graph is on its own and owes an argument.
    """
    blocks: List[str] = []
    for relation, heading in (("support", "Support"), ("divergence", "Divergence")):
        items = [_citation_item(graph, t.to, t.note)
                 for t in thesis.traditions if t.relation == relation]
        if items:
            blocks.append("**%s**" % heading)
            blocks.append("\n".join(items))
    return blocks


def _cited_by_blocks(graph: Graph, q: Question) -> List[str]:
    """The mirror: the theses that reach this question by a tradition edge.

    A tradition's lineage is not this graph's, so nothing leads to it in the
    tab tree and its masthead carries no terms. This is the list that would
    otherwise be missing — what a tradition is doing here at all.
    """
    rows: List[Tuple[str, str]] = []
    for src in graph.questions:
        for thesis in src.theses:
            for trad in thesis.traditions:
                if trad.to == q.id:
                    rows.append((trad.relation, src.id))
    blocks: List[str] = []
    for relation, heading in (("support", "Support"), ("divergence", "Divergence")):
        items = ["- %s" % breadcrumb(graph, src, plain_last=False)
                 for rel, src in rows if rel == relation]
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


def _anchored_text(thesis: Thesis) -> str:
    """The thesis text with a chip after every occurrence of every anchor.

    One pass over the original text, occurrences taken left to right, so an
    inserted token is never itself scanned for an anchor that overlaps it.
    """
    cuts: List[Tuple[int, int, str]] = []
    for order, term in enumerate(list(thesis.terms) + list(thesis.mentions)):
        token = " " + chip(term.to)
        for anchor in term.anchors:
            if not anchor:
                continue
            at = thesis.text.find(anchor)
            while at != -1:
                cuts.append((_placement(thesis.text, at + len(anchor)), order, token))
                at = thesis.text.find(anchor, at + 1)
    if not cuts:
        return thesis.text
    out: List[str] = []
    last = 0
    for at, _, token in sorted(cuts, key=lambda cut: (cut[0], cut[1])):
        out.append(thesis.text[last:at])
        out.append(token)
        last = at
    out.append(thesis.text[last:])
    return "".join(out)


def _thesis_blocks(graph: Graph, thesis: Thesis) -> List[str]:
    blocks = ["### ◆ %s" % thesis.title]
    line = "assent: %s" % thesis.assent
    if thesis.deadlock:
        line += " · deadlock: %s" % thesis.deadlock
    line += " · provenance: thesis hinge"
    blocks.append(line)
    blocks.append(_anchored_text(thesis))
    return blocks


def _glossary_blocks(q: Question) -> List[str]:
    """A definition, and where a borrowed sense was borrowed from.

    The borrowing closes the subsection as its own block, ending in the chip,
    so that a reader who wants the lineage has somewhere to click and a parser
    can tell the borrowing from the body it follows. Appended to the body's
    own paragraph neither would be true.
    """
    blocks: List[str] = []
    for _, definition in q.definitions():
        blocks.append("### ≡ %s" % definition.word)
        blocks.append(definition.body)
        if definition.tradition:
            note = definition.tradition.note.strip()
            line = chip(definition.tradition.to)
            if note:
                line = "%s %s" % (note if note.endswith(".") else note + ".", line)
            blocks.append(line)
    return blocks


def _inbox_order(graph: Graph, q: Question) -> List[Term]:
    """The frontier, heaviest first, ties by question id.

    The order is what the section is for: it answers what to do next, and a
    table in file order answers nothing.
    """
    by_id = graph.by_id()

    def weight(term: Term) -> Tuple[int, str]:
        child = by_id.get(term.to)
        return (-(child.priority if child else 0), term.to)

    return sorted(q.terms(), key=weight)


def _inbox_blocks(graph: Graph, q: Question) -> List[str]:
    by_id = graph.by_id()
    rows = []
    for term in _inbox_order(graph, q):
        child = by_id.get(term.to)
        rows.append("| %s | %s | %s | %s | %s |" % (
            chip(term.to), term.title,
            child.kind if child else "?",
            child.priority if child else "?",
            _requires(graph, child)))
    blocks: List[str] = []
    if rows:
        blocks.append("\n".join(
            ["| question | term | kind | priority | requires |",
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


def _term_blocks(q: Question) -> List[str]:
    blocks: List[str] = []
    for term in q.terms():
        blocks.append("### %s → %s" % (term_heading(term), chip(term.to)))
        for anchor in term.anchors:
            blocks.append("*%s*" % anchor)
        if term.deadlock:
            blocks.append(term.deadlock)
    for mention in q.mentions():
        # ↗ and not ▸: a cross-reference is listed with the terms because it is
        # a clause pointing somewhere, and marked apart from them because it
        # raised nothing. Without an entry of its own it could not be told from
        # a term on the page at all, and the next export would read it as one.
        blocks.append("### ↗ %s → %s" % (mention.title, chip(mention.to)))
        for anchor in mention.anchors:
            blocks.append("*%s*" % anchor)
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
        line = "%s · ◆ %s · %s · %s" % (app.what, thesis.title, app.link,
                                        app.standing)
        if app.note.strip():
            line += " · %s" % app.note.strip()
        blocks.append(line)
    return blocks


#: the blocks key for the state dropdown, one per tab
STATE_KEY = "state"


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
        blocks.append("### ⚓ question: what the asking presupposes")
        blocks.append(q.hinge.question)
    if q.hinge.thesis.strip():
        blocks.append("### ⚓ thesis: what the answer was drawn from")
        blocks.append(q.hinge.thesis)
    return blocks


# -- the body ---------------------------------------------------------------

def body(graph: Graph, qid: str) -> str:
    """The canonical markdown body for one tab. Empty sections are omitted."""
    q = graph.get(qid)
    if q is None:
        raise KeyError("no question %r" % qid)
    top_level = project.parents(graph).get(qid) is None

    blocks: List[str] = ["# %s" % q.id]

    if not top_level:
        # one item per anchor, each ending in a chip to the tab whose term
        # section holds it, so a question with several parents names them all
        # and the reader can get back to any of them
        blocks.append("\n".join(
            "- %s %s" % (anchor, chip(src))
            for src, term in _incoming_terms(graph, qid)
            for anchor in term.anchors))

    blocks.append("*%s*" % q.question)

    if top_level:
        blocks.append("⌂ root")
    else:
        blocks.append("⌂ " + breadcrumb(graph, qid))

    blocks.append("question: %s · %s · priority %d · load %d · requires: %s" % (
        _state(graph, q), q.kind, q.priority, project.load(graph, qid),
        _requires(graph, q)))

    thesis_blocks: List[str] = []
    for thesis in q.theses:
        thesis_blocks.extend(_thesis_blocks(graph, thesis))
        thesis_blocks.extend(_tradition_blocks(graph, thesis))
    for name, section in (("thesis", thesis_blocks),
                          ("glossary", _glossary_blocks(q)),
                          ("inbox", _inbox_blocks(graph, q)),
                          ("terms", _term_blocks(q)),
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
        for definition in thesis.definitions:
            # a borrowing is one chip and not a breadcrumb: it closes a
            # sentence rather than standing on a line of its own
            if definition.tradition:
                add(definition.tradition.to)
    for src in graph.questions:  # the mirror, on a tab something cites
        if any(trad.to == qid for thesis in src.theses
               for trad in thesis.traditions):
            for step in project.lineage(graph, src.id):
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
    ``occurrence`` numbers the entries that share an anchor, in the order they
    are emitted, so the caller can tell one from another where the same words
    stand in more than one place on a tab.
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
    for _, definition in q.definitions():
        heading = "≡ %s" % definition.word
        out.append({
            "kind": "definition",
            "word": definition.word,
            "anchor": text.plain(definition.word),
            "heading": heading,
            "target": "#%s.%s" % (q.tab, heading),
        })
    for term in _inbox_order(graph, q):
        out.append({
            "kind": "inbox-term",
            "term": term.title,
            "anchor": text.plain(term.title),
            "target": "#%s.%s" % (q.tab, term_heading(term)),
        })
    titles = _inbox_titles(graph)
    homes = {item.id: home for home in graph.questions for item in home.inbox}
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
    seen: Dict[str, int] = {}
    for entry in out:
        anchor = entry["anchor"]
        seen[anchor] = seen.get(anchor, 0) + 1
        entry["occurrence"] = seen[anchor]
    return {"question": q.id, "tab": q.tab,
            "blocks": mention_blocks(graph, qid), "links": out}


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
