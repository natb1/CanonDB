"""due — what is due and why, read off the record and stored nowhere.

A reading of the notebook used to run on the calendar: the sitting read the
week and the backlog the month. What makes a reading due is not the date but
something the record holds, and this lists it: by project, each thing that
is due, the kind of trigger that made it so, why, and the next step that
would take it in. Five kinds the record can read, and a sixth it can only
name:

- ``again``: a landed answer the AI gave, dated by the model or by the canon
  above it (the due-again read);
- ``drift``: a deadlocked clause that a later draw gave way on (the drift
  count);
- ``pending``: a note opening with *pending*, a clause of a dictation no run
  has applied;
- ``suspended``: a clause whose acceptance is withheld while its thread is
  open;
- ``backstop``: a question whose hinge records no amendment within the
  backstop, where one is given: nothing fired for too long;
- ``upstream``: a root whose end reads an earlier project's root. The rev it
  was read at is not recorded, so whether the upstream moved cannot be read;
  the row says so and never guesses.

Computed from a graph file, as the other projections are, and stored
nowhere. Every row names a next step: a list of what is due with nothing to
do about it is a museum, and the page is not to become one.
"""

from __future__ import annotations

import re
from datetime import date
from typing import List, NamedTuple, Optional

from . import again, drift, project
from .model import Graph, Question

#: how a hinge's thesis part dates an amendment
AMENDED = re.compile(r"amended (\d{4}-\d{2}-\d{2})")
#: how a note opens that a dictation run could not apply
PENDING = "pending"
KINDS = ("again", "drift", "pending", "suspended", "backstop", "upstream")


class Row(NamedTuple):
    project: str
    question: str
    kind: str
    why: str
    next: str


def last_amended(hinge_thesis: str) -> Optional[date]:
    """The latest amendment a hinge's thesis part records, or None where it
    records none."""
    found = [date.fromisoformat(m) for m in AMENDED.findall(hinge_thesis or "")]
    return max(found) if found else None


def _in(q: Question, of: Optional[str]) -> bool:
    return not q.tradition and (of is None or q.project == of)


def _clip(words: str, n: int = 72) -> str:
    words = " ".join(words.split())
    return words if len(words) <= n else words[:n - 1] + "…"


def rows(graph: Graph, model: Optional[str] = None, moved: Optional[again.Moved] = None,
         backstop: Optional[int] = None, today: Optional[date] = None,
         of: Optional[str] = None) -> List[Row]:
    """Everything due, by project then by kind then by question. ``model`` and
    ``moved`` are the due-again read's and ride in only when both are given;
    ``backstop`` is a number of days, and ``of`` names one project."""
    out: List[Row] = []
    by_id = graph.by_id()
    if model is not None and moved is not None:
        for d in again.due(graph, model, moved, of):
            q = by_id.get(d.question)
            out.append(Row(q.project if q is not None else "", d.question, "again",
                           "; ".join(d.reasons),
                           "put it again: /principal:ask --again %s" % d.question))
    for held in drift.deadlocks(graph):
        q = by_id[held.question]
        if not _in(q, of) or all(held.holds):
            continue
        gave = sum(1 for h in held.holds if not h)
        out.append(Row(q.project, q.id, "drift",
                       "the deadlocked clause %r gave way in %d later draw%s"
                       % (held.clause, gave, "" if gave == 1 else "s"),
                       "put the clause again, in a question that carries the user's "
                       "counter-clause with it"))
    for q in sorted(graph.questions, key=lambda x: x.id):
        if not _in(q, of):
            continue
        for note in q.notes:
            if note.body.strip().lower().startswith(PENDING):
                out.append(Row(q.project, q.id, "pending",
                               "a pending note on %s: %s" % (note.section, _clip(note.body)),
                               "take it in: /principal:dictate in the project's checkout"))
        for thesis in q.theses:
            for term in thesis.terms:
                if term.suspended.strip():
                    out.append(Row(q.project, q.id, "suspended",
                                   "the clause %r waits on: %s"
                                   % (term.title, _clip(term.suspended)),
                                   "settle what it waits on, then the merge"))
        if backstop is not None:
            when = today or date.today()
            last = last_amended(q.hinge.thesis) if q.hinge is not None else None
            if last is None:
                out.append(Row(q.project, q.id, "backstop",
                               "its hinge records no amendment, so nothing dates its "
                               "last reading",
                               "read it; the backstop is %d days" % backstop))
            elif (when - last).days > backstop:
                out.append(Row(q.project, q.id, "backstop",
                               "last amended %s, %d days ago, past the backstop of %d"
                               % (last.isoformat(), (when - last).days, backstop),
                               "read it: nothing has fired since"))
    roots = project.project_roots(graph)
    for i, rid in enumerate(roots):
        r = by_id.get(rid)
        if r is None or r.hinge is None or not _in(r, of):
            continue
        for earlier in roots[:i]:
            e = by_id.get(earlier)
            name = e.project if e is not None else ""
            if name and re.search(r"\b%s\b" % re.escape(name), r.hinge.end):
                out.append(Row(r.project, r.id, "upstream",
                               "its end reads %s, and the rev %s was read at is not "
                               "recorded, so whether it moved cannot be read" % (name, name),
                               "record the rev the end was read at, and read this root "
                               "when that rev moves"))
    order = {k: i for i, k in enumerate(KINDS)}
    out.sort(key=lambda r: (r.project, order[r.kind], r.question))
    return out


def listing(found: List[Row]) -> List[str]:
    """One line per row: project, question, kind, why, and the next step."""
    width = max([len(r.question) for r in found] + [1])
    out = []
    for r in found:
        head = ("%s · " % r.project) if r.project else ""
        out.append("%s%-*s  %-9s %s · next: %s" % (head, width, r.question, r.kind, r.why, r.next))
    return out
