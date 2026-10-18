"""again — which landed answers are due to be drawn again, read off the record.

One answer is one draw, and a second one dates the first: an answer drawn
from a model other than the one answering now, or against canon that has
since moved above its question, is no longer evidence of what the AI would
say now. ``due`` lists every such question of the author's that the AI
answers and has landed, with what moved, so that the entry point can put one
again in a fresh context. Nothing is stored: the hinge's thesis half records
what the answer was drawn from, and this reads it back.

What the hinge names is ``model: … · harness: … · canon: …``; ``provenance``
parses that line, the canon as plain text or as the page's link. Whether
canon above a question has moved since the commit the hinge names is read
off git by ``git_moved``, over the files under ``canon/``; a commit git does
not know is reported as such and never read as current.
"""

from __future__ import annotations

import re
import subprocess
from typing import Callable, List, NamedTuple, Optional, Sequence

from . import project, turn
from .model import Graph

#: a hinge's thesis half, as the renderer writes it and every tab spells it
PROVENANCE = re.compile(
    r"^model: (?P<model>.+?) · harness: (?P<harness>.+?) · canon: (?P<canon>.+?)(?: · |$)",
    re.S)
#: the canon commit as the page links it
_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")


class Provenance(NamedTuple):
    model: str
    harness: str
    canon: str


class Due(NamedTuple):
    question: str
    model: str
    canon: str
    reasons: List[str]


#: (question, the commit its hinge names, the questions above it) -> the
#: questions above whose canon has moved since, or None where the commit
#: cannot be read
Moved = Callable[[str, str, Sequence[str]], Optional[List[str]]]


def provenance(text: str) -> Optional[Provenance]:
    """What a hinge's thesis half names, or None where it does not name the
    three the renderer writes."""
    m = PROVENANCE.match(text.strip())
    if m is None:
        return None
    canon = _LINK.sub(lambda mm: mm.group(1), m.group("canon")).strip()
    return Provenance(m.group("model").strip(), m.group("harness").strip(), canon)


def due(graph: Graph, model: str, moved: Moved) -> List[Due]:
    """Every landed question of the author's the AI answers whose answer is
    dated: by the model, by the canon above it, or by a hinge that names
    neither. Each with its reasons, by id."""
    rows: List[Due] = []
    for q in sorted(graph.questions, key=lambda q: q.id):
        if q.tradition or q.answerer != turn.AI or not project.landed(q):
            continue
        prov = provenance(q.hinge.thesis) if q.hinge is not None else None
        reasons: List[str] = []
        if prov is None:
            rows.append(Due(q.id, "", "", ["its hinge names no model and canon, so what "
                                           "the answer was drawn from is not recorded"]))
            continue
        if prov.model != model:
            reasons.append("model: %s, now %s" % (prov.model, model))
        above = turn.above(graph, q.id)
        changed = moved(q.id, prov.canon, above)
        if changed is None:
            reasons.append("canon %s is not a commit here, so whether canon above "
                           "has moved cannot be read" % prov.canon)
        elif changed:
            reasons.append("canon above moved since %s: %s" % (prov.canon, ", ".join(changed)))
        if reasons:
            rows.append(Due(q.id, prov.model, prov.canon, reasons))
    return rows


def git_moved(root: str) -> Moved:
    """The reading off git under ``root``: canon is what is under ``canon/``,
    one file per question, and a question's canon has moved when a commit
    after the one named touches its file."""
    def run(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "-C", root] + list(args),
                              capture_output=True, text=True)

    def moved(qid: str, canon: str, above: Sequence[str]) -> Optional[List[str]]:
        if run("rev-parse", "--verify", "--quiet", canon + "^{commit}").returncode != 0:
            return None
        out: List[str] = []
        for other in above:
            log = run("log", "--format=%h", canon + "..HEAD", "--", "canon/%s.md" % other)
            if log.returncode == 0 and log.stdout.strip():
                out.append(other)
        return out
    return moved


def listing(rows: Sequence[Due]) -> List[str]:
    """One line per question due: its id and the reasons."""
    width = max([len(r.question) for r in rows] + [1])
    return ["%-*s  %s" % (width, r.question, "; ".join(r.reasons)) for r in rows]
