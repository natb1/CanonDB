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
order the readings were given. Each note's words are checked as
``inplace.py`` checks a note's, and the joined insert is read back as that
many notes, in that order.

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


def _readings(readings) -> List[dict]:
    if not isinstance(readings, list) or not readings:
        raise Refused("the readings are not a non-empty list")
    problems = []
    for n, item in enumerate(readings, 1):
        if not isinstance(item, dict):
            problems.append("reading %d is not an object" % n)
            continue
        for key in ("party", "position"):
            value = item.get(key)
            if not isinstance(value, str) or not value.strip():
                problems.append("reading %d has no %s" % (n, key))
            elif "\n" in value or "\r" in value:
                problems.append("reading %d: its %s breaks a line" % (n, key))
    if problems:
        raise Refused("; ".join(problems))
    return readings


def rows(readings, after: str, node: str, sitting: str, op_id: str) -> List[dict]:
    """The rows entry for the recorder: one insert after block ``after`` on
    the tab whose node id is ``node``, holding one note per reading."""
    for name, value in (("--after", after), ("--node", node), ("--op-id", op_id)):
        if not isinstance(value, str) or not value.strip():
            raise Refused("%s is empty" % name)
    date = _date(sitting)
    bodies = []
    for item in _readings(readings):
        body = note(date, item["party"].strip(), item["position"].strip())
        inplace._plain_block(body, "the note of %s" % item["party"].strip())
        bodies.append(body)
    content = "\n\n".join("> " + body for body in bodies)
    got = inplace._read_back(inplace._tab(("Hinge", [content])))
    if got.get("notes") != [{"section": "hinge", "body": body} for body in bodies]:
        raise Refused("the notes do not read back as written: %r" % got.get("notes"))
    op = {"op": "insert", "target": {"kind": "blocks", "ids": [after]}, "side": "after",
          "source": {"as": "markdown", "from": {"kind": "inline", "content": content}}}
    return [{"node": node, "payload": {"ops": [op]}, "op_id": op_id}]
