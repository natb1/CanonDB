"""turn — which question a canon turn is put to, and what the turn carries.

The notebook's rule for a turn that answers on canon is short: it carries
the question, the earlier turns of its own thread, and canon above the
question, and nothing else. Two things in that rule are decidable from the
graph file, and this module decides them so that the entry point which
holds the notebook does not compose them by hand.

``frontier`` is every question the AI answers that has not been put, with
what each still waits on; ``select`` is the heaviest of those with nothing
owed. A question is put only to the AI, only once, and only when nothing it
waits on is still owed: every
question the AI answers above it — by a path through the AI's questions,
which is the blocking relation ``project.blocked_behind`` reads — has an
answer that has landed, or stands earlier in the thread the question is being
put on. Which thread a
question is on is not recorded, so the caller names the thread. ``select``
weighs by backlog, ties by id, which is what a caller outside this plugin
reads off the notebook as the next question.

``lineage`` is the canon above a question, written out as text: for each
question the AI answers above it, the question and the one answer a turn may
carry, oldest first; then the question itself. Nothing of the notebook goes
in — no headline, no hinge, no glossary, no note, and no question id, which
is the notebook's name for a tab and a frame a filename could leak — so the
file can be handed to a turn that must not see the notebook. It refuses,
naming what is waited on, rather than write a lineage with a gap in it.
"""

from __future__ import annotations

from typing import Iterable, List, Optional, Sequence, Set, Tuple

from . import project
from .model import ANSWERERS, STATES, Graph, Question, Thesis

AI = project.AI
_, IN_THREAD, LANDED = STATES

#: what separates one question's entry from the next in a lineage file
RULE = "---"


def carried(q: Question, thread: Iterable[str] = ()) -> Optional[Thesis]:
    """The one answer to ``q`` a turn may carry: the landed one, or, when
    ``q`` is on the thread the turn is put on, the one in thread."""
    for thesis in q.theses:
        if thesis.state == LANDED:
            return thesis
    if q.id in set(thread):
        for thesis in q.theses:
            if thesis.state == IN_THREAD:
                return thesis
    return None


def above(graph: Graph, qid: str) -> List[str]:
    """The questions the AI answers above ``qid``, by a path through the AI's
    questions; nearest the root first, ties by id.

    This is the lineage as a turn carries it: Claude's own graph and nothing
    of the user's. A question the principal answers is never put, so nothing
    of it reaches a turn, and neither does anything above it by way of it
    alone. The path runs on across a project's edge where the question there
    is already Claude's, so a turn carries the whole of Claude's line, and
    stops where the question there is a prior the user holds.
    """
    by_id = graph.by_id()
    ins = project.in_edges(graph)
    seen: Set[str] = set()
    mine = by_id[qid].project if qid in by_id else ""

    def carried(s: str) -> bool:
        # a turn carries Claude's own nodes and no one else's. Above the
        # question, in its own project, every question the AI answers is on
        # the path, and one still held is owed before the turn. Across a
        # project's edge only a node already Claude's is on it: a question of
        # an earlier project that the user holds as a prior constrains the
        # later one in the notebook and at the review, is never put into a
        # turn, and is not waited on
        q = by_id.get(s)
        if q is None or q.answerer != AI:
            return False
        return q.project == mine or q.claude

    queue = [s for s in ins.get(qid, []) if carried(s)]
    while queue:
        cur = queue.pop()
        if cur in seen:
            continue
        seen.add(cur)
        queue.extend(s for s in ins.get(cur, []) if carried(s))
    seen.discard(qid)
    dist = project.distances(graph)
    return sorted(seen, key=lambda s: (dist.get(s, project.INF), s))


def waits(graph: Graph, qid: str, thread: Iterable[str] = ()) -> List[str]:
    """Why ``qid`` cannot be put now; empty when it can.

    Each line names one thing owed: a question above it whose answer a turn
    could not carry.
    """
    by_id = graph.by_id()
    q = by_id.get(qid)
    if q is None:
        return ["no such question"]
    out: List[str] = []
    if q.answerer != AI:
        out.append("the %s answers it, so it is never put"
                   % ("principal" if q.answerer == ANSWERERS[1] else "party"))
    if project.put(q):
        out.append("it has been put already")
    for other in above(graph, qid):
        if carried(by_id[other], thread) is None:
            state = _answer_state(by_id[other])
            out.append("%s, above it, has %s" % (other, state))
    return out


def _answer_state(q: Question) -> str:
    if not q.theses:
        return "no answer"
    if any(t.state == IN_THREAD for t in q.theses):
        return "an answer in thread, on a thread this question is not on"
    return "an answer still held"


def frontier(graph: Graph, thread: Iterable[str] = (),
             of: Optional[str] = None) -> List[Tuple[str, int, List[str]]]:
    """Every question the AI answers that has not been put, with its backlog
    and what it waits on; heaviest first, ties by id. ``of`` names one
    project of a notebook that holds several. A question a session has
    claimed is out: it is being put."""
    thread = list(thread)
    rows = []
    for q in graph.questions:
        if q.tradition or q.answerer != AI or project.put(q) or q.claimed:
            continue
        if of is not None and q.project != of:
            continue
        rows.append((q.id, project.backlog(graph, q.id), waits(graph, q.id, thread)))
    rows.sort(key=lambda r: (-r[1], r[0]))
    return rows


def select(graph: Graph, thread: Iterable[str] = (),
           of: Optional[str] = None) -> Optional[str]:
    """The heaviest question with nothing left to wait on, or None."""
    for qid, _backlog, owed in frontier(graph, thread, of):
        if not owed:
            return qid
    return None


def lineage(graph: Graph, qid: str, thread: Iterable[str] = ()) -> str:
    """Canon above ``qid`` and then ``qid``, as text a turn may carry.

    Raises ``ValueError`` naming what is owed when a question above has no
    answer the turn could carry: a lineage with a gap is not a lineage.
    """
    by_id = graph.by_id()
    q = by_id.get(qid)
    if q is None:
        raise ValueError("no such question: %s" % qid)
    thread = list(thread)
    gaps = [line for line in waits(graph, qid, thread) if ", above it, has " in line]
    if gaps:
        raise ValueError("; ".join(gaps))
    parts: List[str] = []
    for other in above(graph, qid):
        thesis = carried(by_id[other], thread)
        assert thesis is not None
        if thesis.state == STATES[0]:
            # held is a prior of the user's: carried() never returns one, and
            # this keeps it so whatever carried() comes to return
            raise ValueError("%s, above it, is a prior the user holds: a turn "
                             "carries Claude's own words alone" % other)
        parts.append("%s\n\n%s" % (by_id[other].question.strip(), thesis.text.strip()))
    parts.append(q.question.strip())
    return ("\n\n%s\n\n" % RULE).join(parts) + "\n"


def listing(rows: Sequence[Tuple[str, int, List[str]]]) -> List[str]:
    """The frontier as lines: id, backlog, and what is owed or `ready`."""
    width = max([len(r[0]) for r in rows] + [1])
    out = []
    for qid, weight, owed in rows:
        out.append("%-*s  %4d  %s" % (width, qid, weight,
                                      "ready" if not owed else "; ".join(owed)))
    return out
