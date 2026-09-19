"""The renderer: the only sanctioned way to produce a tab's markdown.

A layout violation is impossible if the tool is used, so the layout lives here
and nowhere else. The renderer refuses to print a question the checker reports an
ERROR against, and emits, alongside the markdown, the links sidecar the caller
turns into ``format`` operations once the write has returned real block ids.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from . import project, spec
from .model import Graph, Question, Term, Thesis

SEPARATOR = "\n\n"


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


def _tradition_line(thesis: Thesis) -> Optional[str]:
    if not thesis.traditions:
        return None
    parts = []
    for trad in thesis.traditions:
        note = trad.note.strip()
        parts.append("%s %s — %s." % (trad.to, trad.relation, note) if note
                     else "%s %s." % (trad.to, trad.relation))
    return "Traditions: " + " ".join(parts)


def _thesis_blocks(thesis: Thesis) -> List[str]:
    blocks = ["### ◆ %s" % thesis.title]
    line = "assent: %s" % thesis.assent
    if thesis.deadlock:
        line += " · deadlock: %s" % thesis.deadlock
    line += " · provenance: thesis hinge"
    blocks.append(line)
    blocks.append(thesis.text)
    traditions = _tradition_line(thesis)
    if traditions:
        blocks.append(traditions)
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
            term.to, term.title,
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


def _term_blocks(q: Question) -> List[str]:
    blocks: List[str] = []
    for term in q.terms():
        blocks.append("### ▸ %s → %s" % (term.title, term.to))
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
        blocks.append("⌂ " + " › ".join(project.lineage(graph, qid)))

    blocks.append("question: %s · %s · priority %d · load %d · requires: %s" % (
        q.state, q.kind, q.priority, project.load(graph, qid), _requires(q)))

    thesis_blocks: List[str] = []
    for thesis in q.theses:
        thesis_blocks.extend(_thesis_blocks(thesis))
    for heading, section in (("## Thesis", thesis_blocks),
                             ("## Glossary", _glossary_blocks(q)),
                             ("## Inbox", _inbox_blocks(graph, q)),
                             ("## Terms", _term_blocks(q)),
                             ("## Applications", _application_blocks(q)),
                             ("## Hinge", _hinge_blocks(q))):
        if section:
            blocks.append(heading)
            blocks.extend(section)

    return SEPARATOR.join(b.strip("\n") for b in blocks) + "\n"


def links(graph: Graph, qid: str) -> Dict[str, object]:
    """Every link the caller must apply after the write.

    Block ids are unknown until the write returns, so each target carries the
    term title (or the definition's heading) as the placeholder key.
    """
    q = graph.get(qid)
    if q is None:
        raise KeyError("no question %r" % qid)
    by_id = graph.by_id()
    out: List[Dict[str, str]] = []
    for term in q.terms():
        target_tab = by_id[term.to].tab if term.to in by_id else term.to
        for anchor in term.anchors:
            out.append({
                "kind": "term",
                "term": term.title,
                "anchor": anchor,
                "to": term.to,
                "target": "#%s.%s" % (target_tab, term.title),
            })
    for _, definition in q.definitions():
        heading = "≡ %s" % definition.word
        out.append({
            "kind": "definition",
            "word": definition.word,
            "anchor": definition.word,
            "heading": heading,
            "target": "#%s.%s" % (q.tab, heading),
        })
    return {"question": q.id, "tab": q.tab, "links": out}


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
