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
    """The tradition questions, lexicographically. Each is a root of its own."""
    return sorted(q.id for q in graph.questions if q.tradition)


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

    A question no root reaches is INF; ``reachable`` reports it.
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
            continue  # no root reaches it; `reachable` reports it
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


def subtree(graph: Graph, qid: str) -> List[str]:
    """``qid`` and every question under it in the projection, lexicographically."""
    kids = tree(graph)
    found = [qid]
    queue = deque([qid])
    while queue:
        cur = queue.popleft()
        for child in kids.get(cur, []):
            if child not in found:
                found.append(child)
                queue.append(child)
    return found


def load(graph: Graph, qid: str) -> int:
    """The number of questions in ``qid``'s subtree under the projection, minus one."""
    return len(subtree(graph, qid)) - 1


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
