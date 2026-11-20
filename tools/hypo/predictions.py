"""predictions — the failed predictions the notebook records, read back and stamped.

The notebook is the one home of what is learned about predicting the
principal. A prediction that fails, in whole or in part, is recorded as the
notebook records any divergence (``hypo.divergence``): a note opening with
the word *divergence*, its data a fixed form that names who predicted, the
kind of action, the grade and the direction, and never the sealed text,
the answer or the case, and names the seal it graded by an id alone, so that
two failures in the same words are two notes:

    divergence: prediction s203001020300-review-3 by speaker of a review, graded diverges,
    direction expected-more-limits · action: <the lesson> · whose: ai ·
    price: <what applying it costs> · budget: none

The ``action`` is the lesson: what would have kept the prediction from
failing. A lesson two or more predictions carry is written again, once, on
the tab the notebook keeps for how the record predicts the user, as a
divergence whose data opens with ``a lesson recurs`` and whose ``action``
is the lesson. Nothing here writes: ``compose`` gives a note's words for
``inplace.py note insert``, and the rest read.

**The stamp.** A prediction of the speaker's own is sealed only after the
speaker has read the tally of every failed prediction: those of the graph
the sitting opened on, and those graded since, whose note words wait in a
directory of the sitting's own until the next opening's read carries them.
``stamp`` prints the tally and ends with ``predictions-read: <sha256> <T>``,
the fingerprint of every prediction note's words (spacing folded, sorted,
one entry a note, as compact JSON in UTF-8); a note of the graph and a file
of the directory are one prediction where they name the same seal. ``check_seal`` refuses a sealed file
that does not end with that line for the record as it now stands, so a note
added since the stamp, the lesson just graded among them, is read before
the next seal.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Dict, Iterable, List, NamedTuple, Optional

from . import divergence
from .board import parse_time
from .model import Graph

BY = ("speaker", "clean-reader")
KINDS = ("question", "review", "act")
#: the grader's grades of a prediction that failed, in whole or in part;
#: ``agrees`` and ``silent`` failed in nothing and are counted where the
#: line doc's Fidelity rounds keep every grade
FAILED = ("verdict only", "short of the edge", "diverges")
#: the grades that gave another verdict or reason, and so say which way
DIRECTED = ("verdict only", "diverges")
DIRECTIONS = ("expected-more-limits", "expected-fewer-limits", "expected-less-change",
              "expected-more-change", "missed-recorded-sentence", "other")
RECURS = 2
OPENING = "prediction "
RECURRING = "a lesson recurs"

SEAL = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}")
FORM = re.compile(r"prediction (?P<seal>\S+) by (?P<by>[a-z-]+) of an? (?P<kind>[a-z]+), graded "
                  r"(?P<grade>[a-z ]+?)(?:, direction (?P<direction>[a-z-]+)"
                  r"(?:: (?P<text>.+))?)?")
STAMP = re.compile(r"predictions-read: ([0-9a-f]{64}) (\S+)")


class Refused(Exception):
    """What this module will not print, with every reason it will not."""

    def __init__(self, reasons: Iterable[str]):
        self.reasons = list(reasons)
        super().__init__("; ".join(self.reasons))


class Prediction(NamedTuple):
    where: str
    seal: str
    by: str
    kind: str
    grade: str
    direction: str
    text: str
    lesson: str
    body: str


def fold(text: str) -> str:
    return " ".join(text.split())


def _norm(text: str) -> str:
    return fold(text).casefold().rstrip(" .;:")


# --- a note's words --------------------------------------------------------

def compose(seal: str, by: str, kind: str, grade: str, lesson: str, price: str,
            direction: Optional[str] = None, text: Optional[str] = None) -> str:
    """A failed prediction's note words, refused outside the lists."""
    bad = []
    if not SEAL.fullmatch(seal or ""):
        bad.append("the seal is not an id: name the seal graded, by its job or file id, "
                   "never its text")
    if by not in BY:
        bad.append("by is not one of %s" % ", ".join(BY))
    if kind not in KINDS:
        bad.append("kind is not one of %s" % ", ".join(KINDS))
    if grade not in FAILED:
        bad.append("grade %r is not a failure the grader gives (%s); agrees and silent are "
                   "counted in the line doc's Fidelity rounds" % (grade, ", ".join(FAILED)))
    if direction is None and grade in DIRECTED:
        bad.append("a grade of %s says which way: give a direction" % grade)
    if direction is not None and direction not in DIRECTIONS:
        bad.append("direction is not one of %s" % ", ".join(DIRECTIONS))
    if direction == "other" and not (text or "").strip():
        bad.append("a direction of other says it in words")
    if text is not None and direction is None:
        bad.append("words for a direction need a direction")
    for name, value in (("lesson", lesson), ("price", price), ("text", text)):
        if value is not None and (divergence.SEP.strip() in value or "\n" in value):
            bad.append("the %s holds a line break or %r, which parts a note" % (
                name, divergence.SEP.strip()))
    if not lesson.strip():
        bad.append("the lesson is empty: say what would have kept the prediction from "
                   "failing")
    if not price.strip():
        bad.append("the price is empty")
    if bad:
        raise Refused(bad)
    data = "prediction %s by %s of %s %s, graded %s" % (
        seal, by, "an" if kind == "act" else "a", kind, grade)
    if direction:
        data += ", direction %s" % direction
        if text and text.strip():
            data += ": %s" % fold(text)
    return divergence.compose(data, lesson, "ai", price)


def parse(body: str, where: str) -> Optional[Prediction]:
    """A prediction note's parts; None where the note is no prediction's;
    Refused where it opens as one and does not hold the form."""
    parts = divergence.parse(body)
    if parts is None:
        return None
    data = str(parts["data"])
    if not data.startswith(OPENING):
        return None
    m = FORM.fullmatch(data)
    if not m or not SEAL.fullmatch(m["seal"]) or m["by"] not in BY or m["kind"] not in KINDS or m["grade"] not in FAILED \
            or (m["direction"] is not None and m["direction"] not in DIRECTIONS) \
            or (m["direction"] is None and m["grade"] in DIRECTED):
        raise Refused(["%s: a prediction's note does not hold the form: %r" % (where, data)])
    if not str(parts["action"]).strip():
        raise Refused(["%s: a prediction's note names no lesson" % where])
    return Prediction(where, m["seal"], m["by"], m["kind"], m["grade"], m["direction"] or "",
                      m["text"] or "", str(parts["action"]), fold(body))


# --- the record --------------------------------------------------------------

def gather(graph: Graph, added: Optional[str] = None):
    """Every prediction note: the graph's, each by its place, then the added
    directory's (``*.txt``, one note's words a file) where no note of the
    graph names the same seal; and the lessons already written as
    recurring."""
    found: List[Prediction] = []
    recorded: List[str] = []
    for q in sorted(graph.questions, key=lambda x: x.id):
        for i, note in enumerate(q.notes):
            p = parse(note.body, "%s note %d" % (q.id, i + 1))
            if p is not None:
                found.append(p)
            parts = divergence.parse(note.body)
            if parts and str(parts["data"]).startswith(RECURRING):
                recorded.append(_norm(str(parts["action"])))
    seen = {p.seal for p in found}
    if added is not None:
        try:
            names = sorted(n for n in os.listdir(added) if n.endswith(".txt"))
        except OSError as exc:
            raise Refused(["the added directory cannot be read: %s" % exc])
        for name in names:
            try:
                with open(os.path.join(added, name), encoding="utf-8") as fh:
                    body = fh.read()
            except (OSError, ValueError) as exc:
                raise Refused(["%s cannot be read: %s" % (name, exc)])
            p = parse(body, name)
            if p is None:
                raise Refused(["%s is no prediction's note" % name])
            if p.seal in seen:
                continue
            found.append(p)
    return sorted(found, key=lambda p: (p.seal, p.where)), recorded


def digest(preds: List[Prediction]) -> str:
    body = json.dumps(sorted(p.body for p in preds), ensure_ascii=False,
                      separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def tally(preds: List[Prediction], recorded: Iterable[str] = ()) -> dict:
    def count(values, keys):
        return {k: sum(1 for v in values if v == k) for k in keys}

    lessons: Dict[str, dict] = {}
    for p in preds:
        got = lessons.setdefault(_norm(p.lesson), {"lesson": p.lesson, "count": 0})
        got["count"] += 1
    done = set(recorded)
    recurring = sorted((dict(v, written=k in done) for k, v in lessons.items()
                        if v["count"] >= RECURS), key=lambda v: (-v["count"], v["lesson"]))
    return {"failed": len(preds),
            "by_kind": count([p.kind for p in preds], KINDS),
            "by_who": count([p.by for p in preds], BY),
            "by_grade": count([p.grade for p in preds], FAILED),
            "by_direction": count([p.direction for p in preds if p.direction], DIRECTIONS),
            "lessons": recurring}


def stamp(preds: List[Prediction], recorded: Iterable[str], at: str) -> str:
    try:
        parse_time(at)
    except ValueError as exc:
        raise Refused(["--at: %s" % exc])
    t = tally(preds, recorded)

    def row(name, counts):
        return "%s: %s" % (name, ", ".join("%s %d" % kv for kv in counts.items()))

    out = ["failed predictions recorded: %d" % t["failed"], row("by kind", t["by_kind"]),
           row("by who predicted", t["by_who"]), row("by grade", t["by_grade"]),
           row("by direction", t["by_direction"])]
    if t["lessons"]:
        out.append("lessons carried by %d or more:" % RECURS)
        out.extend("- (%d) %s%s" % (v["count"], v["lesson"],
                                    "" if v["written"] else " [not yet on the notebook]")
                   for v in t["lessons"])
    else:
        out.append("lessons carried by %d or more: none" % RECURS)
    out.append("predictions-read: %s %s" % (digest(preds), at))
    return "\n".join(out) + "\n"


def check_seal(sealed: str, stamped: str, preds: List[Prediction],
               recorded: Iterable[str]) -> str:
    """The stamp a sealed file ends with, where it is the record's as it
    stands and the stamp file is what ``stamp`` prints for it."""
    rows = sealed.split("\n")
    if rows and rows[-1] == "":
        rows.pop()
    last = rows[-1] if rows else ""
    m = STAMP.fullmatch(last)
    if not m:
        raise Refused(["the sealed file does not end with a line of its own "
                       "`predictions-read: <sha256> <time>`: stamp, read, and seal again"])
    if not any(x.strip() for x in rows[:-1]):
        raise Refused(["the sealed file holds nothing but the stamp"])
    if stamped.rstrip("\n").split("\n")[-1] != last:
        raise Refused(["the sealed file's stamp is not the stamp file's last line"])
    try:
        fresh = stamp(preds, recorded, m.group(2))
    except Refused:
        raise Refused(["the stamp's time is not an ISO 8601 UTC time"])
    if m.group(1) != digest(preds):
        raise Refused(["the stamp is not of the record as it stands: a prediction was "
                       "recorded since it was read; stamp, read and seal again"])
    if stamped != fresh:
        raise Refused(["the stamp file is not what stamp prints for the record as it stands"])
    return last
