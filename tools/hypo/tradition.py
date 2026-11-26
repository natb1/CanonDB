"""tradition — the rows that record the readings of tradition given in a round.

A reading of tradition given on the page after an answer is recorded in the
notebook in the same round, before the next action is put. Where its party
has a tab and rows can be made for it, the reading goes there as a note
(``inplace.py note insert``). Where the party has no tab, or no rows can be
made for its tab, the reading goes as a note opening with the word
*pending* on the ``dictate`` tab, naming its party and stating the party's
position only, called a lead and never marked verified. This module prints
the one rows entry that carries those notes.

The document connector refuses several inserts after one block, so the
notes of a round are one insert, their words joined by a blank line, in the
order the readings were given. The insert goes after the last block of a
section of the tab, which a saved read of the tab is checked for as
``inplace.py note insert`` checks it; each note's words are checked as that
mode checks a note's, and the joined insert is read back as that many notes
of that section, in that order.

Nothing here reaches the network or writes the notebook.
"""

from __future__ import annotations

import datetime
import re
from typing import List

from . import inplace
from .appline import Refused

#: the date of a sitting, as the note gives it
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

#: what an id on the command line may not hold: it is sent as it stands
UNSAFE_ID = re.compile(r"[\s\"'`\\]")

#: every character Python's reader of lines breaks a line at
BREAKS = "\n\r\v\f\x1c\x1d\x1e\x85  "

#: the most a round's file may hold, so that a slip cannot write a page of notes
MAX_READINGS = 50
MAX_PARTY = 200
MAX_POSITION = 2000

#: the words every note opens with, before its party and its position
OPENING = ("pending: a tradition reading given in the sitting of %s, a lead, not verified "
           "against the source and owed to a tab of its party: ")


def note(date: str, party: str, position: str) -> str:
    """One note's words, without the ``> `` that makes it a note."""
    return OPENING % date + "%s: %s" % (party, position)


def _date(sitting: str) -> str:
    if not DATE.match(sitting or ""):
        raise Refused("--sitting %r is not a date of the form YYYY-MM-DD" % sitting)
    try:
        datetime.date.fromisoformat(sitting)
    except ValueError as exc:
        raise Refused("--sitting %r is no date: %s" % (sitting, exc))
    return sitting


def _id(name: str, value) -> str:
    if not isinstance(value, str) or not value:
        raise Refused("%s is empty" % name)
    if UNSAFE_ID.search(value):
        raise Refused("%s %r holds whitespace, a quote or a backslash" % (name, value))
    return value


def _readings(readings) -> List[dict]:
    if not isinstance(readings, list) or not readings:
        raise Refused("the readings are not a non-empty list")
    if len(readings) > MAX_READINGS:
        raise Refused("the readings hold %d, more than %d" % (len(readings), MAX_READINGS))
    problems = []
    for n, item in enumerate(readings, 1):
        if not isinstance(item, dict):
            problems.append("reading %d is not an object" % n)
            continue
        for key, most in (("party", MAX_PARTY), ("position", MAX_POSITION)):
            value = item.get(key)
            if not isinstance(value, str) or not value.strip():
                problems.append("reading %d has no %s" % (n, key))
            elif any(ch in BREAKS for ch in value):
                problems.append("reading %d: its %s breaks a line" % (n, key))
            elif len(value) > most:
                problems.append("reading %d: its %s is longer than %d characters"
                                % (n, key, most))
            elif key == "party" and ": " in value:
                problems.append("reading %d: its party holds \": \", which would part the "
                                "party from the position in the wrong place" % n)
    if problems:
        raise Refused("; ".join(problems))
    return readings


def rows(source, readings, after: str, node: str, sitting: str, op_id: str) -> List[dict]:
    """The rows entry for the recorder: one insert after block ``after`` of the
    tab ``source`` is a saved read of, whose node id is ``node``, holding one
    note per reading."""
    after, node, op_id = _id("--after", after), _id("--node", node), _id("--op-id", op_id)
    date = _date(sitting)
    items = _readings(readings)
    section = inplace.note_place(source, after)
    bodies = []
    for item in items:
        body = note(date, item["party"].strip(), item["position"].strip())
        inplace._plain_block(body, "the note of %s" % item["party"].strip())
        bodies.append(body)
    content = "\n\n".join("> " + body for body in bodies)
    read_back(section, content, bodies)
    op = {"op": "insert", "target": {"kind": "blocks", "ids": [after]}, "side": "after",
          "source": {"as": "markdown", "from": {"kind": "inline", "content": content}}}
    return [{"node": node, "payload": {"ops": [op]}, "op_id": op_id}]


def read_back(section: str, content: str, bodies: List[str]) -> None:
    """Refuse an insert the reader would not take back as these notes, in order."""
    got = inplace._read_back(inplace._tab((section, [content])))
    if got.get("notes") != [{"section": section.lower(), "body": body} for body in bodies]:
        raise Refused("the notes do not read back as written: %d note(s) read back for %d "
                      "reading(s)" % (len(got.get("notes") or []), len(bodies)))
