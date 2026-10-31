"""A project's digest: what a Project's sessions open with.

The end and its method off the root's hinge, the words a project defines, the
clauses that raise questions with the cue each carries, and the cases the
user has judged, in the order the tabs stand in. It is a projection of the
graph, computed and stored nowhere, written as markdown for the instructions
of a Claude Project. Nothing in it is composed: every line is a part of a tab
as the tab holds it, so a session that reads the digest reads the record and
not a summary of it.
"""

from __future__ import annotations

from typing import List, Optional

from . import project as proj
from .model import Graph, Question


def root_of(graph: Graph, name: Optional[str]) -> Optional[Question]:
    """The root of the project ``name``, or the main root where the notebook
    holds one project and no name is given."""
    by_id = graph.by_id()
    if name is None:
        rid = proj.main_root(graph)
        return by_id.get(rid) if rid else None
    for rid in proj.project_roots(graph):
        q = by_id.get(rid)
        if q is not None and (q.project == name or (not q.project and rid == name)):
            return q
    return None


def questions_of(graph: Graph, root: Question) -> List[Question]:
    """The author's questions under ``root``, in the order the tabs stand in:
    the root first, then its descendants as the tree walks them."""
    by_id = graph.by_id()
    under = proj.reachable_from(graph, root.id)
    out: List[Question] = []
    for qid in proj.walk(graph):
        q = by_id.get(qid)
        if q is None or q.tradition or (qid != root.id and qid not in under):
            continue
        out.append(q)
    if root.id not in {q.id for q in out}:
        out.insert(0, root)
    return out


def _line(label: str, words: str) -> str:
    return "- **%s** %s" % (label, " ".join(words.split()))


def digest(graph: Graph, name: Optional[str] = None) -> str:
    """The digest of one project as markdown, or an empty string where the
    graph holds no such project."""
    root = root_of(graph, name)
    if root is None:
        return ""
    questions = questions_of(graph, root)
    title = root.project or root.id
    out: List[str] = ["# %s" % title, ""]
    out.append("*%s*" % " ".join(root.question.split()))
    out.append("")
    hinge = root.hinge
    if hinge is not None and (hinge.end or hinge.method):
        out.append("## The end and its method")
        out.append("")
        if hinge.end:
            out.append(_line("end:", hinge.end))
        if hinge.method:
            out.append(_line("method:", hinge.method))
        out.append("")
    answers = [(q, t) for q in questions for t in q.theses]
    if answers:
        out.append("## The answers")
        out.append("")
        for q, t in answers:
            out.append(_line("%s:" % q.id, t.title))
        out.append("")
    words = [(q, d) for q in questions for d in q.definitions if d.body]
    if words:
        out.append("## The words")
        out.append("")
        for q, d in words:
            out.append(_line("%s (%s):" % (d.word, q.id), d.body))
        out.append("")
    clauses = [(q, term) for q in questions for term in q.terms()]
    if clauses:
        out.append("## The clauses")
        out.append("")
        for q, term in clauses:
            anchor = term.anchors[0] if term.anchors else ""
            text = "%s → %s" % (anchor, term.to) if anchor else term.to
            if term.cue:
                text += " · cue: " + term.cue
            out.append(_line("%s (%s):" % (term.title, q.id), text))
        out.append("")
    cases = [(q, case) for q in questions for case in q.cases]
    if cases:
        out.append("## The cases")
        out.append("")
        for q, case in cases:
            text = "case: %s · verdict: %s · reason: %s" % (case.situation, case.verdict,
                                                              case.reason)
            if case.clause:
                text += " · clause: " + case.clause
            out.append(_line("%s (%s):" % (case.name, q.id), text))
        out.append("")
    return "\n".join(out).rstrip("\n") + "\n"
