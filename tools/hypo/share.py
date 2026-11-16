"""share — how much of the root each principle carries.

A node is a principle and an edge runs to a principle derived from it. An
action supports some principles and compromises others, and a compromise
runs along the lineage to the root: a small promise broken reaches the rule
of life, and so does the rule of life compromised outright, yet the two do
not cost the same. The measure of the difference is a share.

The root carries the whole, one. Each principle hands what it carries to
the principles derived from it, in equal parts unless the user has set
pressure among them, a question's part being one and its pressure; a
principle derived from several carries the sum of what each hands it. So a
share is smaller the further a principle stands from the root and the more
ways its parents divide, and larger the more it is derived from.

Writing a region out re-divides its share and cannot enlarge it, so the
measure does not favour what happens to be written, which a count of
descendants does. The equal parts are a norm the graph is written toward,
not a fact about it: where a case shows they are wrong, the graph is
reorganized, or, short of that, pressure is set, and pressure standing is
the mark of where the graph is sparse. An action's price in what it
compromises is the sum of the shares of the principles it diverges from.

Computed from a graph file and stored nowhere. Tradition questions carry
no share: they are other parties' and nothing of the author's is derived
from them.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, NamedTuple, Optional, Tuple

from . import project
from .model import Graph


def _weight(graph: Graph, qid: str, override: Optional[Dict[str, float]] = None) -> float:
    if override and qid in override:
        return override[qid]
    q = graph.get(qid)
    return 1.0 + (q.pressure if q is not None else 0)


def shares(graph: Graph, override: Optional[Dict[str, float]] = None) -> Dict[str, float]:
    """question id -> the share of the root it carries. Each top-level root
    of the author's carries one; a question no root reaches carries none.
    ``override`` gives a question a part other than one and its pressure,
    which a proposal uses to try an arrangement without writing it."""
    by_id = graph.by_id()
    out_edges = project.out_edges(graph)
    dist = project.distances(graph)
    carry: Dict[str, float] = {q.id: 0.0 for q in graph.questions if not q.tradition}
    for rid in project.roots(graph):
        if rid in carry:
            carry[rid] = 1.0
    # shallowest first: on a DAG every raiser of a question stands no deeper
    # than the question's own longest path, so the pass is run to a fixed
    # point over the topological order the distances give
    order = _topological(graph, out_edges, carry)
    for qid in order:
        kids = [k for k in out_edges.get(qid, []) if k in carry]
        if not kids or not carry[qid]:
            continue
        total = sum(_weight(graph, k, override) for k in kids)
        for k in kids:
            carry[k] += carry[qid] * _weight(graph, k, override) / total
    return carry


def _topological(graph: Graph, out_edges: Dict[str, List[str]],
                 carry: Dict[str, float]) -> List[str]:
    """The author's questions with every raiser before what it raises; a
    cycle's back edge is dropped, as the projection drops it."""
    indeg: Dict[str, int] = {q: 0 for q in carry}
    for src in carry:
        for dst in out_edges.get(src, []):
            if dst in indeg:
                indeg[dst] += 1
    ready = sorted(q for q, n in indeg.items() if n == 0)
    order: List[str] = []
    while ready:
        cur = ready.pop(0)
        order.append(cur)
        for dst in out_edges.get(cur, []):
            if dst in indeg:
                indeg[dst] -= 1
                if indeg[dst] == 0:
                    ready.append(dst)
                    ready.sort()
    return order


def price(graph: Graph, questions: Iterable[str],
          carried: Optional[Dict[str, float]] = None) -> float:
    """What an action compromises: the sum of the shares of the principles
    it diverges from, each once."""
    carried = shares(graph) if carried is None else carried
    return sum(carried.get(q, 0.0) for q in dict.fromkeys(questions))


def pressure_standing(graph: Graph, of: Optional[str] = None) -> List[Tuple[str, int]]:
    """Where pressure is set, heaviest first: the map of where the graph is
    sparse, and where the next line is best drawn."""
    found = [(q.id, q.pressure) for q in graph.questions
             if not q.tradition and q.pressure > 0 and (of is None or q.project == of)]
    return sorted(found, key=lambda x: (-x[1], x[0]))


class Proposal(NamedTuple):
    question: str
    parent: str
    pressure: int
    siblings: int
    groups: int
    share_now: float
    share_after: float
    order_kept: bool

    def line(self) -> str:
        return ("%s under %s: pressure %d among %d siblings carries %.4f; with the "
                "other %d written beneath %d question%s it would carry %.4f with no "
                "pressure; order of shares %s"
                % (self.question, self.parent, self.pressure, self.siblings,
                   self.share_now, self.siblings - 1, self.groups,
                   "" if self.groups == 1 else "s", self.share_after,
                   "kept" if self.order_kept else "changed"))


def _ranking(carried: Dict[str, float]) -> List[Tuple[str, ...]]:
    """The questions grouped by share, largest first; ties are one group."""
    groups: Dict[float, List[str]] = {}
    for q, s in carried.items():
        groups.setdefault(round(s, 9), []).append(q)
    return [tuple(sorted(groups[s])) for s in sorted(groups, reverse=True)]


def _order_kept(before: Dict[str, float], after: Dict[str, float]) -> bool:
    """Whether no pair of questions changed places: every strict order
    before is a strict order, the same way, after."""
    ids = sorted(before)
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            x, y = before[a] - before[b], after.get(a, 0.0) - after.get(b, 0.0)
            if abs(x) > 1e-9 and abs(y) > 1e-9 and (x > 0) != (y > 0):
                return False
    return True


def proposals(graph: Graph, of: Optional[str] = None) -> List[Proposal]:
    """For each question that carries pressure among siblings, the nearest
    arrangement by equal parts that needs none: the other siblings written
    beneath some number of questions, a principle divided beneath itself and
    never beside. Each says what the question would then carry and whether
    any two questions' shares change places. A proposal is read and never
    applied: a reorganization is a dictation."""
    by_id = graph.by_id()
    out_edges = project.out_edges(graph)
    now = shares(graph)
    found: List[Proposal] = []
    for parent, kids in sorted(out_edges.items()):
        src = by_id.get(parent)
        if src is None or src.tradition:
            continue
        kids = [k for k in kids if k in now]
        if len(kids) < 3:
            continue
        for k in kids:
            q = by_id[k]
            if q.pressure <= 0 or (of is not None and q.project != of):
                continue
            n = len(kids)
            total = sum(_weight(graph, x) for x in kids)
            want = _weight(graph, k) / total
            # the other n-1 siblings beneath g questions: k carries 1/(g+1)
            best = min(range(1, n - 1), key=lambda g: abs(1.0 / (g + 1) - want))
            others = [x for x in kids if x != k]
            override = {k: 1.0}
            for x in others:
                override[x] = float(best) / len(others)
            after = shares(graph, override)
            found.append(Proposal(k, parent, q.pressure, n, best, now[k], after[k],
                                  _order_kept(now, after)))
    return sorted(found, key=lambda p: (not p.order_kept, -p.pressure, p.question))


def listing(graph: Graph, of: Optional[str] = None) -> List[str]:
    """One line per question, largest share first."""
    carried = shares(graph)
    by_id = graph.by_id()
    rows = [(s, q) for q, s in carried.items() if of is None or by_id[q].project == of]
    width = max([len(q) for _, q in rows] + [1])
    out = []
    for s, q in sorted(rows, key=lambda r: (-r[0], r[1])):
        p = by_id[q].pressure
        out.append("%-*s  %.4f%s" % (width, q, s, ("  pressure %d" % p) if p else ""))
    return out
