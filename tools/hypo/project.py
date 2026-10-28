"""The tab-tree projection.

A question may have several incoming term edges, so the graph is a DAG; the
document's tab tree is a projection of it. Every function here is total and
deterministic, including on a graph the checker rejects, so that ``spec`` may
use them while reporting on a broken graph.
"""

from __future__ import annotations

from collections import deque
from typing import Dict, List, Optional, Set

from . import text
from .model import ANSWERERS, STATES, TRADITION, Graph, Question

#: who a question is put to; nothing else is ever put
AI = ANSWERERS[0]

INF = float("inf")


# -- edges ------------------------------------------------------------------

def out_edges(graph: Graph) -> Dict[str, List[str]]:
    """question id -> the ids its term edges lead to (file order, deduplicated)."""
    out: Dict[str, List[str]] = {q.id: [] for q in graph.questions}
    for q in graph.questions:
        for term in q.terms():
            if term.to not in out[q.id]:
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

def projects(graph: Graph) -> List[str]:
    """The projects the notebook holds, in the order their roots stand: the
    graph's own list, or the one empty project of a notebook that names none.
    A project a question names and the list does not is put last, so that a
    stray project is reported where it stands rather than lost."""
    out = list(graph.projects) or [""]
    for q in graph.questions:
        if not q.tradition and q.project not in out:
            out.append(q.project)
    return out


def candidates(graph: Graph) -> Dict[str, List[str]]:
    """project -> its questions that are not a tradition and have no incoming
    term edge, lexicographically: a project's root, where it has one."""
    ins = in_edges(graph)
    out: Dict[str, List[str]] = {p: [] for p in projects(graph)}
    for q in sorted(graph.questions, key=lambda x: x.id):
        if not q.tradition and not ins.get(q.id):
            out.setdefault(q.project, []).append(q.id)
    return out


def project_roots(graph: Graph) -> List[str]:
    """Each project's root, in project order: the lexicographically smallest
    candidate where there are several, so the projection stays total;
    ``one-root`` reports the fault."""
    found = candidates(graph)
    return [found[p][0] for p in projects(graph) if found.get(p)]


def main_root(graph: Graph) -> Optional[str]:
    """The first project's root: the one root of a notebook of one project.

    On a graph with none or several, the lexicographically smallest candidate is
    returned so the projection stays total; ``one-root`` reports the fault.
    """
    top = project_roots(graph)
    return top[0] if top else None


def tradition_roots(graph: Graph) -> List[str]:
    """The head of each tradition, lexicographically.

    A tradition is another party's notebook and may raise its own questions, so
    being a tradition is not the same as being a root of one: the root is the
    tradition question nothing in its own party reaches.
    """
    ins = in_edges(graph)
    return sorted(q.id for q in graph.questions if q.tradition and not ins.get(q.id))


def roots(graph: Graph) -> List[str]:
    """Every top-level question of the lineage: each project's root, in
    project order, then the tradition roots."""
    top = project_roots(graph)
    top.extend(r for r in tradition_roots(graph) if r not in top)
    return top


def tradition_project_root(graph: Graph) -> Optional[str]:
    """The root of the tradition project, where the notebook holds one: the
    question every party is placed under."""
    if TRADITION not in graph.projects:
        return None
    found = candidates(graph).get(TRADITION) or []
    return found[0] if found else None


def party_heads(graph: Graph) -> Dict[str, str]:
    """tradition root -> the tradition root it is placed under, for a party
    reconstructed more than once: the one named for the party heads it, and
    each other reconstruction of the same party stands under the head."""
    by_id = graph.by_id()
    groups: Dict[str, List[str]] = {}
    for tid in tradition_roots(graph):
        groups.setdefault(by_id[tid].party, []).append(tid)
    out: Dict[str, str] = {}
    for party, members in groups.items():
        named = [m for m in members if text.fold(m) == text.fold(party)]
        head = named[0] if named else sorted(members)[0]
        for m in members:
            if m != head:
                out[m] = head
    return out


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
    ids = {q.id for q in graph.questions}
    seen = {start}
    queue = deque([start])
    while queue:
        cur = queue.popleft()
        for nxt in out.get(cur, []):
            if nxt not in seen and nxt in ids:
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


def lineage(graph: Graph, qid: str,
            par: Optional[Dict[str, Optional[str]]] = None) -> List[str]:
    """The projection path from the top-level ancestor down to ``qid``.
    ``par`` is ``parents(graph)``, which a caller asking for many lineages
    computes once."""
    chain = [qid]
    par = parents(graph) if par is None else par
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
    """question id -> its order string among its siblings in the tab tray.

    Siblings take a0, a1, a2, … lexicographically by id. A notebook of one
    project puts its root at top level with order a0 and the tradition roots
    at top level too, lexicographically, with b0, b1, …. A notebook of
    several puts each project's root at top level, a0, a1, … in project
    order; a party's head under the tradition project's root, among the
    root's children, lexicographically; and each further reconstruction of
    a party under its head.

    The document's tray sorts orders as strings, so an index is padded to the
    width the largest in its group needs: an eleventh tradition ordered b10
    would otherwise stand between b1 and b2. A group of ten or fewer needs no
    padding and keeps the orders it had.
    """
    out: Dict[str, str] = {}
    for parent, children in placement_children(graph).items():
        if parent is None:
            continue
        for i, child in enumerate(children):
            out[child] = "a" + _index(i, len(children))
    tops = project_roots(graph)
    for i, rid in enumerate(tops):
        out[rid] = "a" + _index(i, len(tops))
    if tradition_project_root(graph) is None:
        heads = [tid for tid in tradition_roots(graph) if tid not in tops]
        for i, tid in enumerate(heads):
            out[tid] = "b" + _index(i, len(heads))
    return out


def placement(graph: Graph) -> Dict[str, Optional[str]]:
    """question id -> the question whose tab its tab is placed under; None at
    top level. The projection's parents, except that under a tradition
    project a party's head is placed under that project's root and a further
    reconstruction under its head: placement and not lineage, since nothing
    raises a party, and a breadcrumb follows the lineage."""
    par = dict(parents(graph))
    troot = tradition_project_root(graph)
    if troot is not None:
        alt = party_heads(graph)
        for tid in tradition_roots(graph):
            par[tid] = alt.get(tid, troot)
    return par


def placement_children(graph: Graph) -> Dict[Optional[str], List[str]]:
    """placed-under id (None for top level) -> the tabs placed there,
    lexicographically."""
    par = placement(graph)
    dist = distances(graph)
    kids: Dict[Optional[str], List[str]] = {}
    for q in graph.questions:
        if dist.get(q.id, INF) == INF:
            continue
        kids.setdefault(par.get(q.id), []).append(q.id)
    for key in kids:
        kids[key].sort()
    return kids


def _index(i: int, count: int) -> str:
    """``i`` padded to the width of the largest index in a group of ``count``."""
    return str(i).zfill(len(str(max(count - 1, 0))))


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


#: the link an application carries while the thing it names is nothing yet
NOT_YET = "not yet written"


def derived_pressure(graph: Graph, qid: str, regressed: Optional[Dict[str, int]] = None) -> int:
    """The pressure at ``qid`` as the record can read it, where none is stored.

    The hand's value stands over the default: a question with a pressure set
    keeps it. Where none is set, one is counted for each application blocked
    on the question, a link of not yet written; one for each postulate its
    answers carry, the load it bears if the answer turns out false; and one
    for each deadlocked clause a later draw gave way on, which ``regressed``
    gives per question (the drift count's reading, since this module reads
    no draw). An answer due again is the due-again read's and rides in the
    same way, through ``regressed``, where a caller has it.
    """
    q = graph.by_id().get(qid)
    if q is None:
        return 0
    if q.pressure > 0:
        return q.pressure
    n = 0
    for thesis in q.theses:
        for app in thesis.applications:
            if app.link.strip().lower() == NOT_YET:
                n += 1
            elif app.standing.strip() == "postulate":
                n += 1
    return n + (regressed or {}).get(qid, 0)


def backlog(graph: Graph, qid: str, derived: bool = False,
            regressed: Optional[Dict[str, int]] = None) -> int:
    """A question's own pressure plus the pressure of everything blocked behind it.

    With ``derived``, a question with no pressure stored takes the one the
    record reads for it (``derived_pressure``); the hand's value stands.

    Pressure is set by hand on the question where work is actually waiting,
    which need not be a leaf: an interior question can have an application
    blocked on it too. The backlog is its transitive sum — the work held up
    behind a question — and it answers what to do next: a question that
    unblocks many is heavy even when little lies beneath it. Load is not a
    sum of pressure at all; it counts.

    It was called priority until the root's own answer turned out to use that
    word in its ordinary sense ("I cannot read your priorities"). The AI's
    words cannot change, so the notebook's did.

    The blocking relation is not stored. It is read off the term graph as far
    as a turn carries — see ``blocked_behind`` — which is what makes the
    backlog computable at all. It already parts from lineage at the
    principal's questions and at landed answers; where else the two differ
    waits on a question-to-question blocking edge recorded in its own right.

    Summed over a set and not down the children, for the reason ``load``
    counts a set: the graph is a DAG, so a question with two parents is
    reached twice, and adding up the branches would count the work waiting at
    it once per path to it. Total on a cycle, since a set has no depth to run
    away down.

    The relation reads "landed", and a turn takes an answer earlier in its own
    thread as well: a thread runs on past one question, and what it answered
    is on its branch. Which thread a question is on is not recorded, so that
    half is the principal's to keep and this half is the one a script holds.
    """
    by_id = graph.by_id()
    q = by_id.get(qid)
    if q is None:
        return 0
    if derived:
        weigh = lambda x: derived_pressure(graph, x, regressed)  # noqa: E731
    else:
        weigh = lambda x: by_id[x].pressure  # noqa: E731
    return weigh(qid) + sum(weigh(b) for b in blocked_behind(graph, qid))


def landed(q: Question) -> bool:
    """Whether an answer to ``q`` has been merged, and so is canon."""
    return any(thesis.state == STATES[-1] for thesis in q.theses)


def put(q: Question) -> bool:
    """Whether ``q`` has been put: a thread is open on it, or an answer to it
    is in one or has landed. Landing alone does not say so — the root reached
    main as the seed it was asked from, before anyone had put it."""
    return (q.state == STATES[1]
            or any(thesis.state in STATES[1:] for thesis in q.theses))


def blocked_behind(graph: Graph, qid: str) -> Set[str]:
    """The questions that cannot be put until ``qid``'s answer has landed.

    Blocking is what a turn carries. A turn carries canon above its question,
    and canon holds only the AI's answers: nothing the principal answers
    reaches a turn, since nothing of the notebook may. So a question waits on
    each question above it that the AI answers, by a path through the AI's
    questions, until that answer has landed — and a question the AI does not
    answer blocks nothing and waits on nothing.

    This is where blocking and lineage first part company without a stored
    edge. `dictate`, which the principal answers, raises `failures`; while
    blocking was every term edge, `failures` waited on an answer that never
    lands. A landed answer blocks nothing either, and a question that has
    one is not waiting.
    """
    by_id = graph.by_id()
    q = by_id.get(qid)
    if q is None or q.answerer != AI or landed(q):
        return set()
    out = out_edges(graph)
    seen: Set[str] = set()
    queue = deque([qid])
    while queue:
        cur = queue.popleft()
        for nxt in out.get(cur, []):
            child = by_id.get(nxt)
            if child is None or nxt in seen or child.answerer != AI:
                continue
            seen.add(nxt)
            queue.append(nxt)
    seen.discard(qid)
    return {b for b in seen if not landed(by_id[b])}


# -- the patch --------------------------------------------------------------

def walk(graph: Graph) -> List[str]:
    """Every projected question in tray order: each top-level tab's tree in
    turn, depth first and lexicographic."""
    kids = placement_children(graph)
    ordr = orders(graph)
    order: List[str] = []

    def descend(qid: str) -> None:
        order.append(qid)
        for child in sorted(kids.get(qid, []), key=lambda c: (ordr.get(c, ""), c)):
            if child not in order:
                descend(child)

    for top in sorted(kids.get(None, []), key=lambda c: (ordr.get(c, ""), c)):
        if top not in order:
            descend(top)
    return order


def in_project(graph: Graph, qid: str, name: str) -> bool:
    """Whether a question's tab is the project's to place: its own questions,
    and for the tradition project every party's too."""
    q = graph.get(qid)
    if q is None:
        return False
    if q.tradition:
        return name == TRADITION
    return q.project == name


def tabs_patch(graph: Graph, project: Optional[str] = None) -> List[dict]:
    """The complete tab-placement patch, ready to send as a document's `tabs`
    patch; with ``project``, that project's tabs alone, so that a run reading
    one project places nothing of another's."""
    by_id = graph.by_id()
    par = placement(graph)
    ordr = orders(graph)
    patch = []
    for qid in walk(graph):
        if project is not None and not in_project(graph, qid, project):
            continue
        q = by_id[qid]
        value = {"name": q.id, "order": ordr.get(qid, "a0")}
        parent = par.get(qid)
        if parent is not None:
            value["subtabOf"] = by_id[parent].tab
        patch.append({"op": "set", "path": ["tabs", q.tab], "value": value})
    return patch


def tree_rows(graph: Graph) -> List[Dict[str, object]]:
    """One row per projected question, in walk order: question, parent,
    order, distance and load — what project.py prints and what a rebuild
    from a portable notebook must come out to."""
    par, ordr, dist = placement(graph), orders(graph), distances(graph)
    rows: List[Dict[str, object]] = []
    for qid in walk(graph):
        d = dist.get(qid, INF)
        rows.append({"question": qid, "parent": par.get(qid), "order": ordr.get(qid),
                     "distance": None if d == INF else int(d), "load": load(graph, qid)})
    return rows


def tree_listing(graph: Graph) -> List[str]:
    """One line per projected question: order, id, load, distance, indented
    by where its tab is placed."""
    par, ordr, dist = placement(graph), orders(graph), distances(graph)
    lines = []
    for qid in walk(graph):
        depth = len(lineage(graph, qid, par)) - 1
        d = dist.get(qid, INF)
        lines.append("%s%s %s  (load %d, distance %s)" % (
            "  " * depth, ordr.get(qid, "?"), qid,
            load(graph, qid), "-" if d == INF else int(d)))
    missing = sorted(q.id for q in graph.questions if dist.get(q.id, INF) == INF)
    for qid in missing:
        lines.append("(unprojected) %s" % qid)
    return lines
