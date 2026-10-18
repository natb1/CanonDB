"""drift — the count the prediction is measured by, read off the record.

Alignment's answer predicts that a clause settled by the human's word fails
more often than one the AI would have reached anyway, and drift's says that
cannot be told from the record itself but from the work done on it, counted
over time. This counts what the record holds and asserts nothing: per
question, how many answers were drawn and whether the later draws agree
with the first; per deadlocked clause, whether each later draw still holds
it.

A draw is an answer the AI gave, which `/principal:ask` records with an
assent line opening ``verbatim (AI)``; the principal's own prior is not one.
Whether a later draw agrees is the asking run's reading of it against the
earlier answer, recorded on the same line as ``agrees`` or ``diverges``;
a draw with neither is counted as unread. A deadlocked clause holds in a
later draw when the clause's anchors recur in it verbatim, which is the one
reading of "holds" a script can make.
"""

from __future__ import annotations

from typing import List, NamedTuple, Optional, Sequence

from .model import Graph, Thesis

#: how `/principal:ask` opens the assent line of an answer the AI gave
DRAW = "verbatim (AI)"
AGREES, DIVERGES = "agrees", "diverges"


class Draws(NamedTuple):
    question: str
    drawn: int
    agree: int
    diverge: int
    unread: int


class Held(NamedTuple):
    question: str
    clause: str
    #: per later draw, in the order the tab holds them
    holds: List[bool]


def is_draw(thesis: Thesis) -> bool:
    return thesis.assent.strip().lower().startswith(DRAW.lower())


def reading(thesis: Thesis) -> Optional[bool]:
    """The asking run's reading of a later draw against the earlier answer,
    or None where the line carries none."""
    words = thesis.assent.lower()
    if AGREES in words:
        return True
    if DIVERGES in words:
        return False
    return None


def draws(graph: Graph) -> List[Draws]:
    """Per question of the author's holding a draw: how many, and how the
    later ones were read."""
    rows: List[Draws] = []
    for q in sorted(graph.questions, key=lambda q: q.id):
        if q.tradition:
            continue
        drawn = [t for t in q.theses if is_draw(t)]
        if not drawn:
            continue
        later = [reading(t) for t in drawn[1:]]
        rows.append(Draws(q.id, len(drawn), later.count(True), later.count(False),
                          later.count(None)))
    return rows


def deadlocks(graph: Graph) -> List[Held]:
    """Per deadlocked clause: whether each draw later than the answer it sits
    in still holds it, read as its anchors recurring verbatim."""
    rows: List[Held] = []
    for q in sorted(graph.questions, key=lambda q: q.id):
        if q.tradition:
            continue
        for i, thesis in enumerate(q.theses):
            for term in thesis.terms:
                if term.deadlock is None:
                    continue
                later = [t for t in q.theses[i + 1:] if is_draw(t)]
                rows.append(Held(q.id, term.title,
                                 [all(a in t.text for a in term.anchors) for t in later]))
    return rows


def listing(drawn: Sequence[Draws], held: Sequence[Held]) -> List[str]:
    """The two counts as lines: ids, numbers and clause headlines only."""
    out: List[str] = []
    width = max([len(r.question) for r in drawn] + [len(r.question) for r in held] + [1])
    for r in drawn:
        out.append("%-*s  drawn %d · agree %d · diverge %d · unread %d"
                   % (width, r.question, r.drawn, r.agree, r.diverge, r.unread))
    for r in held:
        later = ("no later draw" if not r.holds
                 else " ".join("holds" if h else "gives way" for h in r.holds))
        out.append("%-*s  deadlock on %r: %s" % (width, r.question, r.clause, later))
    return out
