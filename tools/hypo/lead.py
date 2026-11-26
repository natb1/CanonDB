"""lead — the record that a question drafted on the user's side was read, by meaning, for
whether it leads the answerer.

A question drafted on the user's side is put to the AI's own record in a
clean turn only once a reader that holds the question's file and the
notebook, the `question-reader` kind, has read it and handed back that it
does not lead: that it hands the answerer no answer, design or position of
the user's record, so that the reply would echo that record instead of being
the AI's own. Whether it leads is a reading; nothing here reads the
question. What this module holds is that the reading was made, by a helper
of that kind, over these exact bytes, and what it handed back.

The reading is a ``lead`` job on the board. The coordinator starts the
reader as ``principal:question-reader`` with the job's id as the launch's
description, writes its reply whole to ``$SCRATCH/coordinator/replies/<job
id>``, and marks the job done with the reply's address and fingerprint.
``record`` takes the board's export, the question's file and the record the
plugin's hooks keep of the session's helpers (``hypo/inhand.py``,
``launches.json``), and writes the record ``clean_turn.py answer --lead``
demands only where:

- the job is on the board, of the kind ``lead``, ``done`` by the
  ``coordinator``, its ``question`` input this file, and its
  ``question_fingerprint`` input the SHA-256 of the file as it stands now;
- its result names a reply whose SHA-256 is the result's fingerprint;
- the reply is three lines and nothing else, ``verdict: leads`` or
  ``verdict: does not lead``, ``reason: <one line>`` no longer than
  ``REASON`` characters, and ``status: ok``;
- the hooks recorded a launch of ``<plugin>:question-reader`` described by
  the job's id, started and ended, launched no earlier than the job was
  added and ended no later than it was marked done;
- the clock reads no earlier than the job was marked done.

The record holds the question's SHA-256, the verdict, the time from the
clock, the job's id, the reply's SHA-256 and the helper's launch as the
hooks recorded it; never the reason, which the speaker reads in the reply.
``led`` writes a record with the verdict ``leads`` and no reading behind it,
for a question found later to have led all the same: a record that only
withholds needs no helper behind it. ``packet.py`` refuses to carry a
question whose directory holds a record with any verdict but ``does not
lead``.

The records are plain files: each binds a check to an exact text and catches
drift, and none is a signature, so one written by hand with the right
hashes passes. The launch record is the hooks', written with no act of the
session; it says that a helper of that kind was started for that job and
stopped, and not what it read or handed back.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
from typing import Dict, List, Optional, Tuple

from . import board

#: the job's kind on the board, and the helper the coordinator starts for it
KIND = "lead"
HELPER = "question-reader"
#: the names the records give the tool's two modes
RECORD_TOOL = "lead.py record"
LED_TOOL = "lead.py led"
#: what a reading can come to; only the second lets a question be put
LEADS, CLEAR = "leads", "does not lead"
VERDICTS = (LEADS, CLEAR)
#: the longest reason a reply may give, so that the reply cannot carry a page
REASON = 300
#: the claimant every helper's job is done by
COORDINATOR = "coordinator"


class Refused(ValueError):
    pass


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _when(text, what: str) -> datetime.datetime:
    try:
        return board.parse_time(text)
    except ValueError:
        raise Refused("%s is no ISO 8601 UTC time: %r" % (what, text))


def _read(path: str, what: str) -> bytes:
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except OSError as exc:
        raise Refused("%s cannot be read: %s" % (what, exc))


def reply(text: str) -> Tuple[str, str]:
    """The verdict and the reason of a reader's reply, which is three lines
    and nothing else: ``verdict: …``, ``reason: …`` and ``status: ok``."""
    lines = [line.rstrip() for line in text.strip().splitlines()]
    if len(lines) != 3:
        raise Refused("the reply is not three lines, a verdict, a reason and the status: it "
                      "holds %d" % len(lines))
    verdict, reason, status = lines
    if status != "status: ok":
        raise Refused("the reply does not end with exactly `status: ok`")
    if not verdict.startswith("verdict: ") or verdict[len("verdict: "):] not in VERDICTS:
        raise Refused("the reply's first line is not `verdict: leads` or `verdict: does not "
                      "lead`")
    if not reason.startswith("reason: ") or not reason[len("reason: "):].strip():
        raise Refused("the reply's second line is not `reason: ` and a reason")
    if len(reason) - len("reason: ") > REASON:
        raise Refused("the reason is longer than %d characters" % REASON)
    return verdict[len("verdict: "):], reason[len("reason: "):].strip()


def launch(rows: List[dict], kind: str, job: dict) -> dict:
    """The one launch the hooks recorded of ``kind`` for ``job``: described
    by its id, started and ended, within the job's time on the board."""
    created = _when(job.get("created"), "the job's creation")
    done = _when(job.get("updated"), "the job's mark of done")
    found = [r for r in rows if isinstance(r, dict) and r.get("kind") == kind
             and r.get("description") == job["id"]]
    if not found:
        raise Refused("the hooks recorded no launch of %s for the job %s: the coordinator "
                      "starts the reader with the job's id as its description" % (kind, job["id"]))
    whole = [r for r in found if r.get("agent_id") and r.get("started") and r.get("ended")]
    if not whole:
        raise Refused("the hooks recorded the launch of %s for the job %s and not that it "
                      "started and ended" % (kind, job["id"]))
    inside = []
    for r in whole:
        try:
            at = _when(r.get("at"), "the launch")
            ended = _when(r.get("ended"), "the end of the launch")
        except Refused:
            continue
        if at >= created and ended <= done:
            inside.append(r)
    if not inside:
        raise Refused("no launch of %s for the job %s was started after the job was added "
                      "and ended before it was marked done" % (kind, job["id"]))
    r = inside[-1]
    return {"kind": r["kind"], "agent_id": r["agent_id"], "launched": r["at"],
            "started": r["started"], "ended": r["ended"]}


def record(question: str, export: Optional[board.Board], job_id: str, launches: List[dict],
           plugin: str, clock: str) -> Dict[str, object]:
    """The record of one reading of ``question``, checked against the
    board's export and the hooks' launches; Refused where any check fails."""
    if export is None:
        raise Refused("no board was read")
    if export.problems:
        raise Refused("the board's export is not sound: %s" % "; ".join(export.problems))
    job = export.jobs.get(job_id)
    if job is None:
        raise Refused("the board holds no job %s" % job_id)
    if job.get("kind") != KIND:
        raise Refused("the job %s is of the kind %r, not %r" % (job_id, job.get("kind"), KIND))
    if job.get("state") != board.DONE or job.get("claimed_by") != COORDINATOR:
        raise Refused("the job %s is not done by the coordinator" % job_id)
    inputs = job.get("inputs") or {}
    given = inputs.get("question")
    if not isinstance(given, str) or os.path.realpath(given) != os.path.realpath(question):
        raise Refused("the job %s was a reading of another file than %s" % (job_id, question))
    raw = _read(question, "the question")
    qsha = sha256(raw)
    if inputs.get("question_fingerprint") != qsha:
        raise Refused("the job %s was a reading of another text than the question as it "
                      "stands: read it again" % job_id)
    result = job.get("result") or {}
    path, fingerprint = result.get("reply"), result.get("fingerprint")
    if not isinstance(path, str) or not isinstance(fingerprint, str):
        raise Refused("the job %s names no reply and fingerprint" % job_id)
    body = _read(path, "the reply")
    if sha256(body) != fingerprint:
        raise Refused("the reply does not match the fingerprint on the board")
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        raise Refused("the reply is not UTF-8")
    verdict, _reason = reply(text)
    helper = launch(launches, "%s:%s" % (plugin, HELPER), job)
    if _when(clock, "the clock") < _when(job.get("updated"), "the job's mark of done"):
        raise Refused("the clock reads earlier than the job's mark of done")
    return {"tool": RECORD_TOOL, "sha256": qsha, "verdict": verdict, "read": clock,
            "job": job_id, "reply_sha256": fingerprint, "helper": helper}


def led(question: str, clock: str) -> Dict[str, object]:
    """The record of a question found to have led all the same."""
    raw = _read(question, "the question")
    _when(clock, "the clock")
    return {"tool": LED_TOOL, "sha256": sha256(raw), "verdict": LEADS, "found": clock}


def write(path: str, record_: Dict[str, object]) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(record_, fh, indent=2)
        fh.write("\n")
