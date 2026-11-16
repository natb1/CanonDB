"""crossing — the review of the edges that cross from one project to another.

A project is a subtree scoped so that its end is a question of the
containing project: a clause of the containing project raises the project's
entry. The containing project never writes the subtree and the subtree never
writes above itself, so what passes between them passes along that edge, and
this reads it: for each entry an earlier project raises, the clause that
raises it, the end the entry states, and what the entry records against the
clause, its divergences, each with the action that would resolve it. An
entry whose record says the clause cannot be met stands first: that is the
finding the containing project's review must resolve, by refining its own
notebook or by an action tracked to its end. A price is information and is
never a finding.

This is the derivation reading: a dependent's end read against the clause
that raises it, and through that clause against the end above. Computed
from a graph file and stored nowhere.
"""

from __future__ import annotations

from typing import List, NamedTuple, Optional

from . import divergence, project
from .model import Graph

#: how a divergence's data says the clause cannot be met at all
CANNOT = "cannot be met"


class Edge(NamedTuple):
    project: str        # the containing project
    raiser: str         # its question
    clause: str         # the clause that raises the entry
    entry: str          # the dependent's entry
    dependent: str      # the dependent project
    end: str            # the end the entry's hinge states
    divergences: tuple  # the entry's divergence notes

    @property
    def unmet(self) -> bool:
        return any(CANNOT in d.data.lower() for d in self.divergences)


def edges(graph: Graph, of: Optional[str] = None) -> List[Edge]:
    """Every edge from a question of one project to the entry of a later
    one, the unmet first; ``of`` names the containing project."""
    by_id = graph.by_id()
    entries = set(project.project_roots(graph))
    notes = {}
    for d in divergence.found(graph):
        notes.setdefault(d.question, []).append(d)
    out: List[Edge] = []
    for src, term in graph.term_edges():
        target = by_id.get(term.to)
        if target is None or term.to not in entries or src.tradition:
            continue
        if target.project == src.project:
            continue
        if of is not None and src.project != of:
            continue
        clause = "; ".join(a for a in term.anchors if a.strip()) or term.title
        end = target.hinge.end.strip() if target.hinge is not None else ""
        out.append(Edge(src.project, src.id, clause, target.id, target.project, end,
                        tuple(notes.get(target.id, []))))
    return sorted(out, key=lambda e: (not e.unmet, e.project, e.dependent, e.raiser))


def listing(found: List[Edge]) -> List[str]:
    """A block per edge: the clause, the end read against it, the record."""
    out: List[str] = []
    for e in found:
        out.append("%s › %s%s" % (e.raiser, e.entry, "  CANNOT BE MET" if e.unmet else ""))
        out.append("  clause: %s" % e.clause)
        out.append("  end:    %s" % (e.end or "(the entry's hinge states no end)"))
        if not e.divergences:
            out.append("  record: nothing diverges")
        for d in e.divergences:
            out.append("  record: %s · action: %s · whose: %s · price: %s · budget: %s"
                       % (d.data, d.action or "?", d.whose or "?", d.price or "?", d.budget))
            for when, reading in d.readings:
                out.append("          read %s: %s" % (when, reading))
    return out
