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
from .model import Graph, Question, Term, Thesis

SEPARATOR = "\n\n"


# -- mention chips ----------------------------------------------------------

def chip_key(qid: str) -> str:
    """The ``blocks`` key for a chip pointing at ``qid``: ``m_<id>`` with every
    non-alphanumeric character replaced by an underscore."""
    return "m_" + re.sub(r"[^0-9A-Za-z]", "_", qid)


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

def _requires(q: Optional[Question]) -> str:
    if q is None:
        return "?"
    return ", ".join(q.requires) if q.requires else "nothing"


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


def _anchored_text(thesis: Thesis) -> str:
    """The thesis text with a chip after every occurrence of every anchor.

    One pass over the original text, occurrences taken left to right, so an
    inserted token is never itself scanned for an anchor that overlaps it.
    """
    cuts: List[Tuple[int, int, str]] = []
    for order, term in enumerate(thesis.terms):
        token = " " + chip(term.to)
        for anchor in term.anchors:
            if not anchor:
                continue
            at = thesis.text.find(anchor)
            while at != -1:
                cuts.append((at + len(anchor), order, token))
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
    blocks: List[str] = []
    for _, definition in q.definitions():
        blocks.append("### ≡ %s" % definition.word)
        body = definition.body
        if definition.tradition:
            body = "%s %s." % (body, definition.tradition)
        blocks.append(body)
    return blocks


def _inbox_blocks(graph: Graph, q: Question) -> List[str]:
    by_id = graph.by_id()
    rows = []
    for term in q.terms():
        child = by_id.get(term.to)
        rows.append("| %s | %s | %s | %s | %s |" % (
            chip(term.to), term.title,
            child.kind if child else "?",
            child.priority if child else "?",
            _requires(child)))
    blocks: List[str] = []
    if rows:
        blocks.append("\n".join(
            ["| question | term | kind | priority | requires |",
             "| --- | --- | --- | --- | --- |"] + rows))
    for item in q.inbox:
        blocks.append("### %s" % item.title)
        blocks.append("%s · %s · instances %s · %s" % (
            item.kind, item.what, item.obligation,
            "done" if item.done else "not done"))
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
    return blocks


def _application_blocks(q: Question) -> List[str]:
    blocks: List[str] = []
    for app in q.applications:
        blocks.append("### ⚙ %s" % app.name)
        blocks.append("%s · %s · %s" % (app.what, app.link, app.standing))
    return blocks


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
        for _, term in _incoming_terms(graph, qid):
            blocks.extend(term.anchors)

    blocks.append("*%s*" % q.question)

    if top_level:
        blocks.append("⌂ root")
    else:
        blocks.append("⌂ " + breadcrumb(graph, qid))

    blocks.append("question: %s · %s · priority %d · load %d · requires: %s" % (
        q.state, q.kind, q.priority, project.load(graph, qid), _requires(q)))

    thesis_blocks: List[str] = []
    for thesis in q.theses:
        thesis_blocks.extend(_thesis_blocks(graph, thesis))
        thesis_blocks.extend(_tradition_blocks(graph, thesis))
    for heading, section in (("## Thesis", thesis_blocks),
                             ("## Glossary", _glossary_blocks(q)),
                             ("## Inbox", _inbox_blocks(graph, q)),
                             ("## Terms", _term_blocks(q)),
                             ("## Applications", _application_blocks(q)),
                             ("## Cited by", _cited_by_blocks(graph, q)),
                             ("## Hinge", _hinge_blocks(q))):
        if section:
            blocks.append(heading)
            blocks.extend(section)

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
    for thesis in q.theses:
        for term in thesis.terms:
            add(term.to)
        for trad in thesis.traditions:
            # a citation is a breadcrumb, so every step of it carries a chip
            for step in (project.lineage(graph, trad.to)
                         if graph.get(trad.to) else [trad.to]):
                add(step)
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
    return {chip_key(target): {"type": "mention", "ref": "file/%s" % by_id[target].tab}
            for target in mention_targets(graph, qid) if target in by_id}


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
