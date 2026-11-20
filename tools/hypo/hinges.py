"""hinges — what a question of the AI's record took for granted, placed and read back.

A question's hinge (``model.Hinge``) holds, in its question part, "what the
asking presupposes", and in its thesis part what the answer was drawn from.
For a question put on a line in the AI's graph, the presuppositions are the
AI's own: the clean turn's answer ends with a ``Presupposes:`` line and then
one presupposition a line, each opening with ``- `` (``clean/answerer.md``).
A draw made before that rule gives them on the label's own line, run
together; they are parted there at each ``that`` a comma or an ``and``
opens, else at the commas and the ``and``. Nothing of the user's record
enters here.

**The place.** A question's answer of record is placed with its question,
its answer word for word, and its presuppositions as the hinge's question
part, each written as one line that ends with its standing:

    <the presupposition> (unjustified; came in by <line>/<n>)

A hinge is justified only by a later answer of the AI's own that it is
linked to; the line then ends ``(justified by <question id>)``, the id of a
question of the AI's that answers past held. Any other line, a hinge's
question part with no such ending among them, is unjustified: it stands on
nothing nearer the root.

**The unjustified.** ``unjustified`` lists every unjustified hinge of the
AI's graph, each with the builds that cite an answer resting on it: the
applications of its own question's answers and of every question below it.
"""

from __future__ import annotations

import re
from typing import Dict, List, NamedTuple, Optional, Tuple

from . import project
from .model import Graph

PRESUPPOSES = "Presupposes:"
RESTS_ON = "Rests on:"
#: what ends a presupposition on a hinge's question part
ENDING = re.compile(r"\s*\((?:unjustified; came in by (?P<came>[^()]+)|justified by "
                    r"(?P<by>[^()\s]+))\)")
NOTHING = ("nothing", "none", "nothing earlier")


class Refused(ValueError):
    """A place this module will not print."""


class Hinge(NamedTuple):
    question: str
    words: str
    came_in_by: Optional[str]
    justified_by: Optional[str]


def labelled(answer: str, label: str) -> Tuple[Optional[str], List[str]]:
    """What follows a labelled line of an answer: the words on the label's
    own line, and the lines under it that open with ``- ``, up to a blank
    line or another label."""
    rows = answer.splitlines()
    for i, row in enumerate(rows):
        if row.strip().startswith(label):
            same = row.strip()[len(label):].strip() or None
            items: List[str] = []
            for nxt in rows[i + 1:]:
                s = nxt.strip()
                if not s:
                    continue
                if not s.startswith("- "):
                    break
                items.append(s[2:].strip())
            return same, items
    return None, []


def run_together(same: str) -> List[str]:
    """Presuppositions given on the label's own line, parted: at each ``that``
    a comma or an ``and`` opens where there are such, else at the commas and
    a closing ``and``."""
    text = same.strip().rstrip(".")
    parts = re.split(r",\s*(?:and\s+)?(?=that\b)|\s+and\s+(?=that\b)", text)
    if len(parts) < 2:
        parts = re.split(r",\s*(?:and\s+)?|\s+and\s+", text)
    return [p.strip() for p in parts if p.strip()]


def presuppositions(answer: str) -> List[str]:
    """The answer's presuppositions, one a line, or on the label's own line
    for a draw made before that rule; refused where it gives none."""
    same, items = labelled(answer, PRESUPPOSES)
    if same is None and not items:
        raise Refused("the answer has no line opening %r with its presuppositions"
                      % PRESUPPOSES)
    if same is not None and items:
        raise Refused("the answer gives presuppositions both on the label's line and under "
                      "it: %r" % same[:60])
    if same is not None:
        items = run_together(same)
    kept = [i for i in items if i.strip().lower().rstrip(".") not in NOTHING]
    for item in kept:
        if "(" in item or ")" in item:
            raise Refused("a presupposition holds a parenthesis, which a hinge's line keeps "
                          "for its standing: %r" % item[:60])
    return kept


def rests_on(answer: str) -> List[str]:
    same, items = labelled(answer, RESTS_ON)
    return items or ([same] if same else [])


def line(words: str, came_in_by: str) -> str:
    return "%s (unjustified; came in by %s)" % (words.rstrip(" ."), came_in_by)


def thesis(line_name: str, n: int, under: Optional[str], model: Optional[str]) -> str:
    """The hinge's thesis part, what the answer was drawn from, in the form
    the notebook's hinges give it."""
    return " · ".join((
        "model: %s" % (model or "not recorded"),
        "harness: a clean turn with no tools, over the line's packet",
        "canon: %s" % ("the AI's answers of %s and above it, and the line %s before question %d"
                       % (under, line_name, n) if under else
                       "the line %s before question %d" % (line_name, n))))


def place(question: str, answer: str, line_name: str, n: int, under: Optional[str],
          model: Optional[str] = None) -> dict:
    """What places one answer of record in the AI's graph: the question, the
    answer, and the hinge's question and thesis parts."""
    came = "%s/%d" % (line_name, n)
    found = presuppositions(answer)
    return {"under": under, "came_in_by": came, "question": question.strip(),
            "answer": answer, "rests_on": rests_on(answer),
            "hinge": {"question": "\n".join(line(p, came) for p in found),
                      "thesis": thesis(line_name, n, under, model)},
            "hinges": [{"words": p, "came_in_by": came, "justified": False} for p in found]}


def read(q) -> List[Hinge]:
    """The presuppositions a question's hinge holds, each with its standing;
    a hinge's question part with no ending is one presupposition, unjustified."""
    text = (q.hinge.question if q.hinge else "") or ""
    if not text.strip():
        return []
    out: List[Hinge] = []
    at = 0
    for m in ENDING.finditer(text):
        words = " ".join(text[at:m.start()].split())
        if words:
            out.append(Hinge(q.id, words, m["came"], m["by"]))
        at = m.end()
    rest = " ".join(text[at:].split())
    if rest:
        out.append(Hinge(q.id, rest, None, None))
    return out


def _ai(q) -> bool:
    return q.answerer == project.AI and q.claude


def unjustified(graph: Graph) -> List[dict]:
    """Every unjustified hinge of the AI's graph, with the builds that cite an
    answer resting on it."""
    by_id = graph.by_id()
    par = project.parents(graph)
    kids: Dict[str, List[str]] = {}
    for child, parent in par.items():
        if parent is not None:
            kids.setdefault(parent, []).append(child)

    def below(qid: str) -> List[str]:
        out, todo = [], [qid]
        while todo:
            cur = todo.pop()
            if cur in out:
                continue
            out.append(cur)
            todo.extend(sorted(kids.get(cur, ())))
        return out

    found: List[dict] = []
    for q in sorted(graph.questions, key=lambda x: x.id):
        if not _ai(q):
            continue
        for h in read(q):
            target = by_id.get(h.justified_by) if h.justified_by else None
            if target is not None and target.id != q.id and _ai(target):
                continue
            builds = []
            for qid in below(q.id):
                for _, app in by_id[qid].applications():
                    builds.append({"question": qid, "application": app.name,
                                   "link": app.link})
            found.append({"question": q.id, "words": h.words, "came_in_by": h.came_in_by,
                          "named": h.justified_by, "builds": builds})
    return found
