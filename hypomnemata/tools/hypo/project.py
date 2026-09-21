"""The tab-tree projection.

A question may have several incoming term edges, so the graph is a DAG; the
document's tab tree is a projection of it. Every function here is total and
deterministic, including on a graph the checker rejects, so that ``spec`` may
use them while reporting on a broken graph.
"""

from __future__ import annotations

from collections import deque
from typing import Dict, List, Optional, Set

from .model import Graph

INF = float("inf")


# -- edges ------------------------------------------------------------------

def out_edges(graph: Graph) -> Dict[str, List[str]]:
    """question id -> the ids its term edges lead to (file order, deduplicated)."""
    out: Dict[str, List[str]] = {q.id: [] for q in graph.questions}
    for q in graph.questions:
        for term in q.terms():
            if term.to not in out.setdefault(q.id, []):
                out[q.id].append(term.to)
    return out


def in_edges(graph: Graph) -> Dict[str, List[str]]:
    """question id -> the ids of the questions whose term edges lead to it."""
    ins: Dict[str, List[str]] = {q.id: [] for q in graph.questions}
    for q in graph.questions:
        for term in q.terms():
            if term.to in ins and q.id not in ins[term.to]:
                ins[term.to].append(q.id)
    return ins


# -- roots ------------------------------------------------------------------

def main_root(graph: Graph) -> Optional[str]:
    """The one question that is not a tradition and has no incoming term edge.

    On a graph with none or several, the lexicographically smallest candidate is
    returned so the projection stays total; ``one-root`` reports the fault.
    """
    ins = in_edges(graph)
    cands = sorted(q.id for q in graph.questions if not q.tradition and not ins.get(q.id))
    return cands[0] if cands else None


def tradition_roots(graph: Graph) -> List[str]:
    """The head of each tradition, lexicographically.

    A tradition is another party's notebook and may raise its own questions, so
    being a tradition is not the same as being a root of one: the root is the
    tradition question nothing in its own party reaches.
    """
    ins = in_edges(graph)
    return sorted(q.id for q in graph.questions if q.tradition and not ins.get(q.id))


def roots(graph: Graph) -> List[str]:
    """Every top-level question: the main root first, then the tradition roots."""
    top: List[str] = []
    root = main_root(graph)
    if root is not None:
        top.append(root)
    top.extend(r for r in tradition_roots(graph) if r != root)
    return top


# -- distance, parent, lineage ---------------------------------------------

def distances(graph: Graph) -> Dict[str, float]:
    """Shortest distance over term edges from the nearest root. Roots are 0.

    A question no root reaches is INF, which one-root and acyclic
    between them make impossible.
    """
    out = out_edges(graph)
    dist: Dict[str, float] = {q.id: INF for q in graph.questions}
    queue = deque()
    for r in roots(graph):
        dist[r] = 0
        queue.append(r)
    while queue:
        cur = queue.popleft()
        for nxt in out.get(cur, []):
            if nxt in dist and dist[nxt] == INF:
                dist[nxt] = dist[cur] + 1
                queue.append(nxt)
    return dist


def reachable_from(graph: Graph, start: Optional[str]) -> Set[str]:
    """Every question reachable from ``start`` over term edges, including it."""
    if start is None:
        return set()
    out = out_edges(graph)
    seen = {start}
    queue = deque([start])
    while queue:
        cur = queue.popleft()
        for nxt in out.get(cur, []):
            if nxt not in seen and any(q.id == nxt for q in graph.questions):
                seen.add(nxt)
                queue.append(nxt)
    return seen


def ancestors(graph: Graph, qid: str) -> Set[str]:
    """Every question with a term path to ``qid``. Cycle-safe; excludes ``qid``
    unless a cycle genuinely leads back to it."""
    ins = in_edges(graph)
    seen: Set[str] = set()
    queue = deque(ins.get(qid, []))
    while queue:
        cur = queue.popleft()
        if cur in seen:
            continue
        seen.add(cur)
        queue.extend(ins.get(cur, []))
    return seen


def parents(graph: Graph) -> Dict[str, Optional[str]]:
    """parent(q): the source of an incoming term edge with the smallest distance
    to the root, ties broken lexicographically by question id (smallest wins).

    A top-level question has no parent. A back edge that would make a question
    its own ancestor in the projection is skipped, so the projection is a tree
    even where the term graph has a cycle.
    """
    ins = in_edges(graph)
    dist = distances(graph)
    top = set(roots(graph))
    chosen: Dict[str, Optional[str]] = {}
    for q in graph.questions:
        if q.id in top:
            chosen[q.id] = None
            continue
        sources = sorted(ins.get(q.id, []), key=lambda s: (dist.get(s, INF), s))
        chosen[q.id] = sources[0] if sources else None
    # break any cycle the choice produced, deterministically
    for qid in sorted(chosen):
        seen = {qid}
        cur = chosen[qid]
        while cur is not None:
            if cur in seen:
                chosen[qid] = None
                break
            seen.add(cur)
            cur = chosen.get(cur)
    return chosen


def lineage(graph: Graph, qid: str) -> List[str]:
    """The projection path from the top-level ancestor down to ``qid``."""
    chain = [qid]
    par = parents(graph)
    cur = par.get(qid)
    while cur is not None and cur not in chain:
        chain.append(cur)
        cur = par.get(cur)
    chain.reverse()
    return chain


# -- order and load ---------------------------------------------------------

def tree(graph: Graph) -> Dict[Optional[str], List[str]]:
    """parent id (None for top level) -> child ids, lexicographically."""
    par = parents(graph)
    dist = distances(graph)
    kids: Dict[Optional[str], List[str]] = {}
    for q in graph.questions:
        if dist.get(q.id, INF) == INF:
            continue  # no root reaches it: only possible on a cycle
        kids.setdefault(par.get(q.id), []).append(q.id)
    for key in kids:
        kids[key].sort()
    return kids


def orders(graph: Graph) -> Dict[str, str]:
    """question id -> its order string among its siblings.

    Siblings take a0, a1, a2, … lexicographically by id. The main root is top
    level with order a0; the tradition roots are top level, lexicographically,
    with b0, b1, ….
    """
    kids = tree(graph)
    out: Dict[str, str] = {}
    root = main_root(graph)
    if root is not None:
        out[root] = "a0"
    for i, tid in enumerate(tradition_roots(graph)):
        if tid != root:
            out[tid] = "b%d" % i
    for parent, children in kids.items():
        if parent is None:
            continue
        for i, child in enumerate(children):
            out[child] = "a%d" % i
    return out


def load(graph: Graph, qid: str) -> int:
    """How many questions lie beneath ``qid``: those its term edges reach.

    Counted over the term graph and not the tab tree, because the graph is a
    DAG and the tree is only a projection of it: a question with two parents
    hangs under one of them, so a tree walk credits its weight to that parent
    alone and reports nothing beneath the other. Reachability credits both,
    which is what "what lies beneath this question" means. It is also total on
    a graph with a cycle, which a tree walk was only by accident.
    """
    return len(reachable_from(graph, qid)) - 1


def backlog(graph: Graph, qid: str) -> int:
    """A question's own pressure plus the pressure of everything blocked behind it.

    Pressure is set by hand on the question where work is actually waiting,
    which need not be a leaf: an interior question can have an application
    blocked on it too. The backlog is its transitive sum — the work held up
    behind a question — and it answers what to do next: a question that
    unblocks many is heavy even when little lies beneath it. Load is not a
    sum of pressure at all; it counts.

    It was called priority until the root's own answer turned out to use that
    word in its ordinary sense ("I cannot read your priorities"). The AI's
    words cannot change, so the notebook's did.

    The blocking relation is not stored. It is read off the term graph,
    because a turn answering a question carries canon above that question, so
    a question cannot be put until the answer to every question above it has
    landed. That makes the questions blocked behind ``qid`` exactly the ones
    its term edges reach, and it is what makes the backlog computable at all. Once a
    question-to-question blocking edge exists in its own right the two will
    part company, and this is the half that will have to move.

    Summed over the reachable set and not down the children, for the reason
    ``load`` counts a set: the graph is a DAG, so a question with two parents
    is reached twice, and adding up the branches would count the work waiting
    at it once per path to it. What is blocked behind a question is a set of
    questions, each of them blocked once.

    Total on a cycle, since a set has no depth to run away down.
    """
    by_id = {q.id: q for q in graph.questions}
    return sum(by_id[reached].pressure
               for reached in reachable_from(graph, qid) if reached in by_id)


# -- the patch --------------------------------------------------------------

def walk(graph: Graph) -> List[str]:
    """Every projected question: the main root's tree first, depth first and
    lexicographic, then each tradition root's."""
    kids = tree(graph)
    order: List[str] = []

    def descend(qid: str) -> None:
        order.append(qid)
        for child in kids.get(qid, []):
            descend(child)

    for top in roots(graph):
        if top not in order:
            descend(top)
    return order


def tabs_patch(graph: Graph) -> List[dict]:
    """The complete tab-placement patch, ready to send as a document's `tabs` patch."""
    by_id = graph.by_id()
    par = parents(graph)
    ordr = orders(graph)
    patch = []
    for qid in walk(graph):
        q = by_id[qid]
        value = {"name": q.id, "order": ordr.get(qid, "a0")}
        parent = par.get(qid)
        if parent is not None:
            value["subtabOf"] = by_id[parent].tab
        patch.append({"op": "set", "path": ["tabs", q.tab], "value": value})
    return patch


def tree_listing(graph: Graph) -> List[str]:
    """One line per projected question: order, id, load, distance."""
    dist = distances(graph)
    lines = []
    for qid in walk(graph):
        depth = len(lineage(graph, qid)) - 1
        d = dist.get(qid, INF)
        lines.append("%s%s %s  (load %d, distance %s)" % (
            "  " * depth, orders(graph).get(qid, "?"), qid,
            load(graph, qid), "-" if d == INF else int(d)))
    missing = sorted(q.id for q in graph.questions if dist.get(q.id, INF) == INF)
    for qid in missing:
        lines.append("(unprojected) %s" % qid)
    return lines
