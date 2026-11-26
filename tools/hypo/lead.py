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
import re
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
#: the record's name in a question's directory
LEAD = "lead.json"


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


def _agent_rows(rows: List[dict], agent: str) -> List[dict]:
    return [r for r in rows if isinstance(r, dict) and r.get("agent_id") == agent]


def launch(rows: List[dict], kind: str, job: dict) -> dict:
    """The launch the hooks recorded of ``kind`` for ``job``, matched by the
    job's id in its description, and the start and end of the helper that
    launch ran, all within the job's time on the board.

    The helper is the one the launch's own return named (``returned_agent``,
    which the hooks take from the Agent tool's result by the same call), and
    its start and end are read wherever the hooks recorded them, since a
    start is given to a launch by kind and order and may land on another
    row. Where the return named none, the start the launch row was given is
    taken only where no other launch of the kind stood open beside it (made
    before that helper's end and not ended before this launch was made), so
    that two launches made together cannot cross; a launch that never
    started stands open, and so refuses only this road, never the first."""
    created = _when(job.get("created"), "the job's creation")
    done = _when(job.get("updated"), "the job's mark of done")
    mine = []
    for r in rows:
        if not (isinstance(r, dict) and r.get("kind") == kind
                and r.get("description") == job["id"]):
            continue
        try:
            at = _when(r.get("at"), "the launch")
        except Refused:
            continue
        if created <= at <= done:
            mine.append((at, r))
    if not mine:
        raise Refused("the hooks recorded no launch of %s described by the job %s while it "
                      "stood on the board: the coordinator starts the reader with the job's "
                      "id as its description" % (kind, job["id"]))
    for at, r in reversed(mine):
        agent = r.get("returned_agent")
        if isinstance(agent, str) and agent:
            ran = _agent_rows(rows, agent)
            alone = True
        else:
            agent = r.get("agent_id")
            ran = [r] if agent else []
            alone = False
        for x in ran:
            try:
                started = _when(x.get("started"), "the start")
                ended = _when(x.get("ended"), "the end")
            except Refused:
                continue
            if not (at <= started <= ended <= done):
                continue
            if not alone:
                others = []
                for o in rows:
                    if o is r or not isinstance(o, dict) or o.get("kind") != kind:
                        continue
                    try:
                        when = _when(o.get("at"), "a launch")
                    except Refused:
                        others.append(o)
                        continue
                    try:
                        over = _when(o.get("ended"), "an end") if o.get("ended") else None
                    except Refused:
                        over = None
                    if when <= ended and (over is None or over >= at):
                        others.append(o)
                if others:
                    continue
            return {"kind": kind, "agent_id": agent, "launched": r["at"],
                    "started": x["started"], "ended": x["ended"]}
    raise Refused("the hooks recorded the launch of %s for the job %s and not, beyond doubt, "
                  "a helper it ran that started and ended before the job was marked done: "
                  "a new lead job is added for the question" % (kind, job["id"]))


# --- a question's place on its line, and the readings already made --------

#: where a line keeps the questions set aside, each set under a number of its own
HELD = "held"
#: how many drafts of one question may be read as leading before it is put
#: to the principal
DRAFTS = 3
NUMBER = re.compile(r"[1-9][0-9]*")


def place(question: str) -> Tuple[str, str]:
    """The line's directory and the question's number, for a question's file
    ``<line>/<n>/question.md``."""
    where = os.path.dirname(os.path.abspath(question))
    if os.path.basename(question) != "question.md" or not NUMBER.fullmatch(
            os.path.basename(where)):
        raise Refused("%s is not a question's question.md on a line, <line>/<n>/question.md"
                      % question)
    return os.path.dirname(where), os.path.basename(where)


def _load(path: str) -> Optional[dict]:
    try:
        with open(path, encoding="utf-8") as fh:
            got = json.load(fh)
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        return {"verdict": None}
    return got if isinstance(got, dict) else {"verdict": None}


def held_sets(line_dir: str) -> List[str]:
    """The sets of questions the line holds aside, in the order set aside."""
    root = os.path.join(line_dir, HELD)
    try:
        names = [n for n in os.listdir(root) if NUMBER.fullmatch(n)]
    except FileNotFoundError:
        return []
    return [os.path.join(root, n) for n in sorted(names, key=int)]


def held_readings(line_dir: str, n: str) -> List[dict]:
    """The records of the readings of question ``n`` set aside on the line."""
    out = []
    for where in held_sets(line_dir):
        got = _load(os.path.join(where, n, LEAD))
        if got is not None:
            out.append(got)
    return out


def led_drafts(line_dir: str, n: str) -> int:
    """How many drafts at question ``n`` were set aside as leading."""
    return sum(1 for r in held_readings(line_dir, n) if r.get("verdict") != CLEAR)


def may_read(question: str, qsha: str) -> None:
    """Refuse a reading of a text already read, of a question whose record
    says it leads, and of a question drafted the most times allowed."""
    line_dir, n = place(question)
    here = _load(os.path.join(os.path.dirname(os.path.abspath(question)), LEAD))
    if here is not None and here.get("verdict") != CLEAR:
        raise Refused("question %s of the line is recorded as leading, which is final for "
                      "that number: set it aside with lead.py aside, and draft it again" % n)
    if here is not None and here.get("sha256") == qsha:
        raise Refused("this text of question %s was read already: one reading for one text" % n)
    if any(r.get("sha256") == qsha for r in held_readings(line_dir, n)):
        raise Refused("this text of question %s was read already and set aside: one reading "
                      "for one text" % n)
    if led_drafts(line_dir, n) >= DRAFTS:
        raise Refused("%d drafts of question %s were read as leading: no draft is read again; "
                      "it is put to the principal that the question could not be drafted "
                      "without leading" % (DRAFTS, n))


def job(question: str, jid: str, notebook: str) -> List[dict]:
    """The jobs file of one ``lead`` job reading ``question`` as it stands."""
    found = board.JOB_ID.fullmatch(jid or "")
    if not found or found.group(4) != KIND:
        raise Refused("%r is not a job id <sitting>-<batch>-<row>-lead" % jid)
    if not board.is_address(notebook):
        raise Refused("the notebook's address is not an address")
    qsha = sha256(_read(question, "the question"))
    may_read(question, qsha)
    sitting, batch, row, kind = found.groups()
    return [{"id": jid, "sitting": sitting, "batch": batch, "row": row, "kind": kind,
             "tier": "full", "waits_on": [],
             "inputs": {"notebook": notebook, "question": os.path.abspath(question),
                        "question_fingerprint": qsha}}]


def aside(line_dir: str, n: str) -> Dict[str, object]:
    """Set aside question ``n``, recorded as leading, with every later
    question of the line, whose packets carried its answer, and every drawer
    turn whose packet carried any of them: moved together under
    ``held/<k>/``, nothing renumbered and nothing removed, so that the line
    reads on without a gap from ``n``. Returns what was moved and which of
    the moved questions had an answer placed."""
    if not NUMBER.fullmatch(n or ""):
        raise Refused("%r is no question's number" % n)
    import packet  # the line's own reading of its numbers
    try:
        numbers = packet.numbered(line_dir)
    except packet.Refused as exc:
        raise Refused(str(exc))
    if n not in numbers:
        raise Refused("the line holds no question %s" % n)
    got = _load(os.path.join(line_dir, n, LEAD))
    if got is None or got.get("verdict") == CLEAR:
        raise Refused("question %s is not recorded as leading: lead.py record or led first"
                      % n)
    moved = [m for m in numbers if int(m) >= int(n)]
    drawn = []
    for name in sorted(os.listdir(line_dir)):
        if not name.startswith("drawn-"):
            continue
        side = _load(os.path.join(line_dir, name, "packet.md" + packet.SIDECAR))
        carried = (side or {}).get("line")
        if side is None and not os.path.exists(os.path.join(line_dir, name, "packet.md")):
            continue
        if not isinstance(carried, list) or any(
                not isinstance(c, dict) or not isinstance(c.get("n"), int)
                or c["n"] >= int(n) for c in carried):
            drawn.append(name)
    sets = held_sets(line_dir)
    k = str(1 + max([int(os.path.basename(w)) for w in sets], default=0))
    target = os.path.join(line_dir, HELD, k)
    os.makedirs(target)
    placed = [m for m in moved if os.path.exists(os.path.join(line_dir, m, "place.json"))]
    for name in moved + drawn:
        os.rename(os.path.join(line_dir, name), os.path.join(target, name))
    return {"held": target, "questions": [int(m) for m in moved], "drawn": drawn,
            "placed": [int(m) for m in placed], "led_drafts": led_drafts(line_dir, n)}


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
    may_read(question, qsha)
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
    """Write the record whole beside its place and put it there in one
    rename, so that a record is never removed or half written."""
    temporary = "%s.%d.tmp" % (path, os.getpid())
    with open(temporary, "w", encoding="utf-8") as fh:
        json.dump(record_, fh, indent=2)
        fh.write("\n")
    os.replace(temporary, path)
