"""divergence — data that contradicts a principle, tracked on its tab.

A principle stands when the data does not fit it; what the record owes is
the divergence itself, the action that would resolve it, whose that action
is, and its price, which is the action required and nothing measured
against another principle. It is kept as a note on the tab of the principle,
opening with the word *divergence*, in parts set apart by `` · ``:

    divergence: <the data> · action: <what would resolve it> · whose: user
    · price: <the action required> · budget: none · read 2026-11-12: <a
    reading>

``whose`` is ``user`` or ``ai``; ``budget`` is ``allocated`` or ``none`` and
may be left out, which reads as none; any number of ``read <date>:`` parts
may follow, one per review, kept and never overwritten. A dictation writes
the note and takes no action. The note stands until the action is done or
the principle is refined on an inconsistency, and the due reading lists it
for as long as it stands.
"""

from __future__ import annotations

import re
from typing import Dict, List, NamedTuple, Optional, Tuple

from .model import Graph

OPENING = "divergence"
WHOSE = ("user", "ai")
BUDGET = ("allocated", "none")
SEP = " · "
READ = re.compile(r"^read (\d{4}-\d{2}-\d{2}): ?(.*)$", re.S)
REQUIRED = ("action", "whose", "price")


class Divergence(NamedTuple):
    question: str
    project: str
    section: str
    data: str
    action: str
    whose: str
    price: str
    budget: str
    readings: Tuple[Tuple[str, str], ...]
    missing: Tuple[str, ...]


def is_one(body: str) -> bool:
    return body.strip().lower().startswith(OPENING)


def parse(body: str) -> Optional[Dict[str, object]]:
    """The parts of a divergence note, or None where the note is not one."""
    words = " ".join(body.split())
    if not is_one(words):
        return None
    parts = [p.strip() for p in words.split(SEP)]
    head = parts[0][len(OPENING):].lstrip(": ").strip()
    out: Dict[str, object] = {"data": head, "action": "", "whose": "", "price": "",
                              "budget": "none", "readings": []}
    for part in parts[1:]:
        found = READ.match(part)
        if found:
            out["readings"].append((found.group(1), found.group(2).strip()))
            continue
        key, colon, value = part.partition(":")
        key = key.strip().lower()
        if colon and key in ("action", "whose", "price", "budget"):
            out[key] = value.strip()
    return out


def missing(parts: Dict[str, object]) -> List[str]:
    """What a divergence note leaves untracked."""
    out = [k for k in REQUIRED if not str(parts.get(k, "")).strip()]
    if not str(parts.get("data", "")).strip():
        out.insert(0, "data")
    whose = str(parts.get("whose", "")).strip().lower()
    if whose and whose not in WHOSE:
        out.append("whose (user or ai)")
    budget = str(parts.get("budget", "")).strip().lower()
    if budget and budget not in BUDGET:
        out.append("budget (allocated or none)")
    return out


def compose(data: str, action: str, whose: str, price: str, budget: str = "none",
            readings: Optional[List[Tuple[str, str]]] = None) -> str:
    """The note's words, from its parts."""
    parts = ["%s: %s" % (OPENING, data.strip()), "action: %s" % action.strip(),
             "whose: %s" % whose.strip().lower(), "price: %s" % price.strip(),
             "budget: %s" % (budget.strip().lower() or "none")]
    for when, reading in readings or []:
        parts.append("read %s: %s" % (when, reading.strip()))
    return SEP.join(parts)


def found(graph: Graph, of: Optional[str] = None) -> List[Divergence]:
    """Every divergence note on an author's tab, by question."""
    out: List[Divergence] = []
    for q in sorted(graph.questions, key=lambda x: x.id):
        if q.tradition or (of is not None and q.project != of):
            continue
        for note in q.notes:
            parts = parse(note.body)
            if parts is None:
                continue
            out.append(Divergence(q.id, q.project, note.section, str(parts["data"]),
                                  str(parts["action"]), str(parts["whose"]).lower(),
                                  str(parts["price"]), str(parts["budget"]).lower(),
                                  tuple(parts["readings"]), tuple(missing(parts))))
    return out
