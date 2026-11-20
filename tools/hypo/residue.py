"""residue — what a line leaves open, tracked on the tab it bears on.

Pursuing a line of questions nearly always opens further lines, and a
drawing rarely ends without residue. What a line leaves open is written
where it bears, when it arises, as a note on that tab opening with the word
*open*, in parts set apart by `` · ``:

    open: <what is open, in its own words> · kind: question · whose: user
    · from: <what raised it> · returns: <what brings it back> · case: <the
    case that was put> · read 2030-01-02: <a reading>

``kind`` is ``question`` (one only the principal can answer), ``case`` (a
case awaiting its verdict), ``change`` (a change approved or proposed and
not yet written or built) or ``work`` (work owed). There is no kind for a
reading awaiting confirmation or for a predicted answer: neither is written
on a tab, since a reader that draws the record's answer reads these tabs.
``whose`` is ``user`` or ``ai``, whose move it is; ``from`` says what raised
it and ``returns`` what brings it back; ``case`` may be left out; any
number of ``read <date>:`` parts may follow, kept and never overwritten.
No part may hold the separator `` · `` or a line break, and a date is
``YYYY-MM-DD``: ``compose`` refuses either rather than write a note that
reads back as other parts. A part ``parse`` does not know, and a part given
twice, are kept as ``strays``, which the listing and the check both report.

The note stands until it is taken up, and then it is taken off and what it
held stands on the tab. Nothing here assumes the open lines are ever all
settled: they are listed, weighed and returned to, and their number is
reported and not driven to nothing.
"""

from __future__ import annotations

import datetime
import re
from typing import Dict, List, NamedTuple, Optional, Tuple

from .model import Graph

OPENING = "open"
KIND = ("question", "case", "change", "work")
WHOSE = ("user", "ai")
SEP = " · "
READ = re.compile(r"^read ([0-9]{4}-[0-9]{2}-[0-9]{2}): ?(.*)$", re.S)
DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")
REQUIRED = ("kind", "whose", "from", "returns")
KEYS = ("kind", "whose", "from", "returns", "case")
#: the word itself and its colon: a note opening "opens", "opening" or
#: "open the door" is somebody's prose
_WORD = re.compile(r"^open\s*:", re.I)


class Open(NamedTuple):
    question: str
    project: str
    section: str
    words: str
    kind: str
    whose: str
    raised: str
    returns: str
    case: str
    readings: Tuple[Tuple[str, str], ...]
    missing: Tuple[str, ...]
    strays: Tuple[str, ...] = ()


def is_one(body: str) -> bool:
    return bool(_WORD.match(body.strip()))


def parse(body: str) -> Optional[Dict[str, object]]:
    """The parts of an open note, or None where the note is not one."""
    words = " ".join(body.split())
    if not is_one(words):
        return None
    parts = [p.strip() for p in words.split(SEP)]
    head = parts[0][len(OPENING):].lstrip().lstrip(":").strip()
    out: Dict[str, object] = {"words": head, "kind": "", "whose": "", "from": "",
                              "returns": "", "case": "", "readings": [],
                              "unknown": [], "repeated": []}
    seen = set()
    for part in parts[1:]:
        found = READ.match(part)
        if found:
            out["readings"].append((found.group(1), found.group(2).strip()))
            continue
        key, colon, value = part.partition(":")
        key = key.strip().lower()
        if not colon or key not in KEYS:
            out["unknown"].append(part)
        elif key in seen:
            # the first stands; the second is reported, not taken
            out["repeated"].append(key)
        else:
            seen.add(key)
            out[key] = value.strip()
    return out


def missing(parts: Dict[str, object]) -> List[str]:
    """What an open note leaves untracked."""
    out = [k for k in REQUIRED if not str(parts.get(k, "")).strip()]
    if not str(parts.get("words", "")).strip():
        out.insert(0, "words")
    kind = str(parts.get("kind", "")).strip().lower()
    if kind and kind not in KIND:
        out.append("kind (%s)" % ", ".join(KIND))
    whose = str(parts.get("whose", "")).strip().lower()
    if whose and whose not in WHOSE:
        out.append("whose (user or ai)")
    return out


def strays(parts: Dict[str, object]) -> List[str]:
    """What an open note holds that ``parse`` could not place: each part it
    does not know, and each part given twice."""
    out = ["a part it does not know (%s)" % p for p in parts.get("unknown", [])]
    out.extend("%s given twice" % k for k in parts.get("repeated", []))
    return out


def compose(words: str, kind: str, whose: str, raised: str, returns: str,
            case: str = "", readings: Optional[List[Tuple[str, str]]] = None) -> str:
    """The note's words, from its parts. Raises ``ValueError`` on a part
    that holds the separator or a line break, a date that is not
    ``YYYY-MM-DD``, or anything else that would not read back as given."""
    given = [("words", words), ("kind", kind), ("whose", whose), ("from", raised),
             ("returns", returns), ("case", case)]
    for when, reading in readings or []:
        given.append(("read %s" % when, reading))
        if not DATE.match(when):
            raise ValueError("the date %r of a reading is not YYYY-MM-DD" % when)
        try:
            datetime.date.fromisoformat(when)
        except ValueError:
            raise ValueError("the date %r of a reading is not a date" % when)
    for name, value in given:
        if "\n" in value or "\r" in value:
            raise ValueError("the %s holds a line break" % name)
        if SEP.strip() in " ".join(value.split()).split():
            raise ValueError("the %s holds the separator %r" % (name, SEP.strip()))
    out = _composed(words, kind, whose, raised, returns, case, readings)
    back = parse(out)
    if back is None or strays(back) or (
            back["words"], back["kind"], back["whose"], back["from"], back["returns"],
            back["case"], back["readings"]) != (
            " ".join(words.split()), kind.strip().lower(), whose.strip().lower(),
            " ".join(raised.split()), " ".join(returns.split()), " ".join(case.split()),
            [(w, " ".join(r.split())) for w, r in readings or []]):
        raise ValueError("the note would not read back as its parts: %s" % out)
    return out


def _composed(words: str, kind: str, whose: str, raised: str, returns: str,
              case: str, readings: Optional[List[Tuple[str, str]]]) -> str:
    parts = ["%s: %s" % (OPENING, words.strip()), "kind: %s" % kind.strip().lower(),
             "whose: %s" % whose.strip().lower(), "from: %s" % raised.strip(),
             "returns: %s" % returns.strip()]
    if case.strip():
        parts.append("case: %s" % case.strip())
    for when, reading in readings or []:
        parts.append("read %s: %s" % (when, reading.strip()))
    return SEP.join(parts)


def found(graph: Graph, of: Optional[str] = None) -> List[Open]:
    """Every open note on an author's tab, by question.

    The listing skips tradition tabs and the check (``open-complete``) holds
    every tab, as the divergence pair does."""
    out: List[Open] = []
    for q in sorted(graph.questions, key=lambda x: x.id):
        if q.tradition or (of is not None and q.project != of):
            continue
        for note in q.notes:
            parts = parse(note.body)
            if parts is None:
                continue
            out.append(Open(q.id, q.project, note.section, str(parts["words"]),
                            str(parts["kind"]).lower(), str(parts["whose"]).lower(),
                            str(parts["from"]), str(parts["returns"]), str(parts["case"]),
                            tuple(parts["readings"]), tuple(missing(parts)),
                            tuple(strays(parts))))
    return out


def count(notes: List[Open]) -> str:
    """The count line: how many are open, by kind and by whose move. A kind
    or a whose the note does not give, or gives out of its set, is counted
    under ``?``."""
    def tally(values: List[str], known: Tuple[str, ...]) -> str:
        seen = {k: 0 for k in known}
        for v in values:
            key = v if v in known else "?"
            seen[key] = seen.get(key, 0) + 1
        return ", ".join("%s %d" % (k, n) for k, n in seen.items() if n or k in known)
    return "%d open · by kind: %s · by whose: %s" % (
        len(notes), tally([n.kind for n in notes], KIND),
        tally([n.whose for n in notes], WHOSE))
