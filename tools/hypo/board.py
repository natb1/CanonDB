"""board — the jobs of a sitting, and the gate every change to them passes.

One session speaks with the principal; everything else is done by helpers,
and every piece of that work is a **job** on the board. The board is a
published page with its own store. A session exports the store to a
directory, one JSON file per document at ``<dir>/<collection>/<doc_id>.json``,
with a versions file beside it naming the version of every document it
exported; this module reads the two and nothing else. It never reaches the
network and never writes the store: what it decides is a list of writes,
each pinned to the version it read, for the session to send as one batch.

The board holds addresses and kinds of act and never prose. Every value in a
job's ``inputs`` and ``result`` is an address (a string of the characters
an address uses, with no space, or an integer) or a fingerprint, so a
sentence with spaces is refused where it would have been stored. A sentence
run together with underscores is an address all the same: the rule is a
convention the kinds keep, and this enforces its letter.

A job moves ``queued`` to ``claimed`` to ``done`` or ``failed``; a failed
job may be queued again, and a claimed one whose helper went quiet is
released, each time with one more attempt, up to the board's
``max_attempts``. ``waiting`` is a job held for the principal. A job is
runnable when it is queued and every job it waits on is done, and no more
than ``cap_full`` jobs of the full tier are claimed at once.

What a batch reads, it pins. A write pins the job it changes; a claim of
the full tier also writes the meta document, pinned, with its ``claims``
counter one higher, so two claims counted from one export cannot both land
and overrun the cap; an ``add`` writes the meta document, pinned, with the
board's new count of ``jobs``, so two adds cannot both land unseen and an
export that lost a job no longer verifies.

Times are ISO 8601 UTC strings a session hands in, such as
``2030-01-02T03:04:05Z``; nothing here reads a clock. Each is checked where
it is stored, and only ``release`` does arithmetic with them.
"""

from __future__ import annotations

import datetime
import json
import os
import re
from typing import Dict, Iterable, List, NamedTuple, Optional, Tuple

#: the collections this round exports, and the one document of the first
META = "meta"
BOARD = "board"
JOBS = "jobs"
COLLECTIONS = (META, JOBS)
META_KEY = "%s/%s" % (META, BOARD)

#: what the meta document holds: ``claims`` counts claims of the full tier
#: ever made, and moves so that each pins the next; ``jobs`` is how many
#: jobs the board holds
SCHEMA = 1
META_FIELDS = ("schema", "cap_full", "max_attempts", "notebook", "claims", "jobs")
CAP_FULL = 2
MAX_ATTEMPTS = 3

#: the most writes the store takes in one batch
BATCH_LIMIT = 50
#: the longest document id the store takes
ID_LIMIT = 200

KINDS = ("seal", "state", "grade", "remedy", "record", "check", "review", "fetch",
         "turn", "compare", "line", "observe", "place", "probe")
TIERS = ("full", "mid", "small")
FULL = "full"
STATES = ("queued", "claimed", "done", "failed", "waiting")
QUEUED, CLAIMED, DONE, FAILED, WAITING = STATES
REASONS = ("refused", "error", "timeout", "superseded", "helper")
TIMEOUT = "timeout"
#: the reason a job's files went with the session, which may close a job
#: that no one claimed and which is no measure of how a helper fits its work
SUPERSEDED = "superseded"

#: every field a job may carry; the last two only in some states
FIELDS = ("id", "sitting", "batch", "row", "kind", "tier", "state", "waits_on", "inputs",
          "result", "claimed_by", "attempts", "reason", "created", "updated")
#: what a jobs file gives for each job; the gate sets the rest
GIVEN = ("id", "sitting", "batch", "row", "kind", "tier", "waits_on", "inputs")
REQUIRED_GIVEN = ("id", "sitting", "batch", "row", "kind", "tier")

PART = re.compile(r"[a-z0-9]+")
JOB_ID = re.compile(r"([a-z0-9]+)-([a-z0-9]+)-([a-z0-9]+)-([a-z]+)")
ADDRESS = re.compile(r"[A-Za-z0-9_.:/#@+~-]{1,200}")
FINGERPRINT = re.compile(r"[0-9a-f]{16,}")
KEY = re.compile(r"[a-z_]{1,40}")


class Refused(Exception):
    """A change the gate will not make, with every reason it will not."""

    def __init__(self, reasons: Iterable[str]):
        self.reasons = list(reasons)
        super().__init__("; ".join(self.reasons))


class Board(NamedTuple):
    """An export as the gate sees it: the meta document or None, the jobs by
    id, the version of every exported document by ``<collection>/<doc_id>``,
    and every problem with the export's shape."""
    meta: Optional[dict]
    jobs: Dict[str, dict]
    versions: Dict[str, int]
    problems: List[str]


# --- what a value may be -------------------------------------------------

def is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def is_address(value) -> bool:
    """A string of 1 to 200 address characters with no space, or an integer."""
    return is_int(value) or (isinstance(value, str) and bool(ADDRESS.fullmatch(value)))


def is_fingerprint(value) -> bool:
    return isinstance(value, str) and bool(FINGERPRINT.fullmatch(value))


def parse_time(text) -> datetime.datetime:
    """An ISO 8601 UTC time, ``2030-01-02T03:04:05Z``; ValueError otherwise."""
    if not isinstance(text, str) or not text.endswith("Z") or "T" not in text \
            or not ADDRESS.fullmatch(text):
        raise ValueError("%r is not an ISO 8601 UTC time ending in Z" % (text,))
    when = datetime.datetime.fromisoformat(text[:-1])
    if when.tzinfo is not None:
        raise ValueError("%r is not an ISO 8601 UTC time ending in Z" % (text,))
    return when.replace(tzinfo=datetime.timezone.utc)


def is_time(value) -> bool:
    try:
        parse_time(value)
    except ValueError:
        return False
    return True


def _values(where: str, value, allow_fingerprint: bool) -> List[str]:
    """What is wrong with an ``inputs`` or ``result`` object."""
    if not isinstance(value, dict):
        return ["%s is not an object" % where]
    out: List[str] = []
    for key in sorted(value, key=str):
        if not isinstance(key, str) or not KEY.fullmatch(key):
            out.append("%s key %r is not [a-z_]{1,40}" % (where, key))
            continue
        v = value[key]
        if is_address(v) or (allow_fingerprint and is_fingerprint(v)):
            continue
        kinds = "an address, an integer or a fingerprint" if allow_fingerprint \
            else "an address"
        out.append("%s.%s is not %s" % (where, key, kinds))
    return out


def inputs_problems(value) -> List[str]:
    return _values("inputs", value, allow_fingerprint=False)


def result_problems(value) -> List[str]:
    return _values("result", value, allow_fingerprint=True)


def job_id(sitting: str, batch: str, row: str, kind: str) -> str:
    return "%s-%s-%s-%s" % (sitting, batch, row, kind)


# --- the shape of a document ---------------------------------------------

def meta_problems(doc) -> List[str]:
    """What is wrong with the meta document."""
    if not isinstance(doc, dict):
        return ["meta/board is not an object"]
    out: List[str] = []
    for key in sorted(set(doc) - set(META_FIELDS), key=str):
        out.append("meta/board carries an unknown field %r" % key)
    for key in META_FIELDS:
        if key not in doc:
            out.append("meta/board has no %s" % key)
    if "schema" in doc and doc["schema"] != SCHEMA:
        out.append("meta/board schema is %r, not %d" % (doc["schema"], SCHEMA))
    if "notebook" in doc and not is_address(doc["notebook"]):
        out.append("meta/board notebook is not an address")
    for key, least in (("cap_full", 1), ("max_attempts", 0), ("claims", 0), ("jobs", 0)):
        if key in doc and not (is_int(doc[key]) and doc[key] >= least):
            out.append("meta/board %s is not a whole number of at least %d" % (key, least))
    return out


def given_problems(job, where: str) -> List[str]:
    """What is wrong with the fields a jobs file gives: the id and its parts,
    the kind, the tier, what it waits on and its inputs."""
    if not isinstance(job, dict):
        return ["%s is not an object" % where]
    out: List[str] = []
    for key in REQUIRED_GIVEN:
        if key not in job:
            out.append("%s has no %s" % (where, key))
    for key in ("sitting", "batch", "row"):
        if key in job and not (isinstance(job[key], str) and PART.fullmatch(job[key])):
            out.append("%s %s is not [a-z0-9]+" % (where, key))
    if "kind" in job and job["kind"] not in KINDS:
        out.append("%s kind %r is not one of %s" % (where, job["kind"], ", ".join(KINDS)))
    if "tier" in job and job["tier"] not in TIERS:
        out.append("%s tier %r is not one of %s" % (where, job["tier"], ", ".join(TIERS)))
    jid = job.get("id")
    if "id" in job:
        if not isinstance(jid, str) or not JOB_ID.fullmatch(jid):
            out.append("%s id is not <sitting>-<batch>-<row>-<kind>" % where)
        else:
            if len(jid) > ID_LIMIT:
                out.append("%s id is longer than %d characters" % (where, ID_LIMIT))
            if all(isinstance(job.get(k), str) for k in ("sitting", "batch", "row", "kind")) \
                    and jid != job_id(job["sitting"], job["batch"], job["row"], job["kind"]):
                out.append("%s id does not match its sitting, batch, row and kind" % where)
    waits = job.get("waits_on", [])
    if not isinstance(waits, list):
        out.append("%s waits_on is not a list" % where)
    else:
        for w in waits:
            if not isinstance(w, str) or not JOB_ID.fullmatch(w):
                out.append("%s waits on %r, which is not a job id" % (where, w))
        named = [w for w in waits if isinstance(w, str)]
        for w in sorted({w for w in named if named.count(w) > 1}):
            out.append("%s waits on %s twice" % (where, w))
    if "inputs" in job:
        out.extend("%s %s" % (where, p) for p in inputs_problems(job["inputs"]))
    return out


def job_problems(job, where: str) -> List[str]:
    """What is wrong with a job as the board holds it."""
    out = given_problems(job, where)
    if not isinstance(job, dict):
        return out
    for key in sorted(set(job) - set(FIELDS), key=str):
        out.append("%s carries an unknown field %r" % (where, key))
    for key in ("state", "waits_on", "inputs", "result", "attempts", "created", "updated"):
        if key not in job:
            out.append("%s has no %s" % (where, key))
    state = job.get("state")
    if "state" in job and state not in STATES:
        out.append("%s state %r is not one of %s" % (where, state, ", ".join(STATES)))
    if "result" in job:
        out.extend("%s %s" % (where, p) for p in result_problems(job["result"]))
    if "attempts" in job and not (is_int(job["attempts"]) and job["attempts"] >= 0):
        out.append("%s attempts is not a whole number of at least 0" % where)
    for key in ("created", "updated"):
        if key in job and not is_time(job[key]):
            out.append("%s %s is not an ISO 8601 UTC time" % (where, key))
    if job.get("claimed_by") is not None and not is_address(job["claimed_by"]):
        out.append("%s claimed_by is not an address" % where)
    if state == CLAIMED and job.get("claimed_by") is None:
        out.append("%s is claimed by no one" % where)
    reason = job.get("reason")
    if reason is not None and reason not in REASONS:
        out.append("%s reason %r is not one of %s" % (where, reason, ", ".join(REASONS)))
    if state == FAILED and reason is None:
        out.append("%s failed with no reason" % where)
    if state in STATES and state != FAILED and reason is not None:
        out.append("%s is %s and carries a reason" % (where, state))
    return out


def _waits(job) -> List[str]:
    waits = job.get("waits_on", []) if isinstance(job, dict) else []
    return [w for w in waits if isinstance(w, str)] if isinstance(waits, list) else []


def cycle(jobs: Dict[str, dict]) -> Optional[List[str]]:
    """One cycle among the jobs' waits, as the ids around it, or None.
    A wait on an id not among them is not followed."""
    WHITE, GREY, BLACK = 0, 1, 2
    colour = {jid: WHITE for jid in jobs}
    for start in sorted(jobs):
        if colour[start] != WHITE:
            continue
        path = [start]
        stack = [iter(sorted(_waits(jobs[start])))]
        colour[start] = GREY
        while stack:
            nxt = next(stack[-1], None)
            if nxt is None:
                colour[path.pop()] = BLACK
                stack.pop()
                continue
            if nxt not in colour:
                continue
            if colour[nxt] == GREY:
                return path[path.index(nxt):] + [nxt]
            if colour[nxt] == WHITE:
                colour[nxt] = GREY
                path.append(nxt)
                stack.append(iter(sorted(_waits(jobs[nxt]))))
    return None


def waited_first(jobs: Dict[str, dict]) -> List[str]:
    """The ids of acyclic jobs with every job one waits on before it, and
    by id where the waits leave the order open."""
    out: List[str] = []
    placed = set()

    def place(jid: str) -> None:
        stack = [(jid, iter(sorted(_waits(jobs[jid]))))]
        while stack:
            top, waits = stack[-1]
            nxt = next(waits, None)
            if nxt is None:
                stack.pop()
                if top not in placed:
                    placed.add(top)
                    out.append(top)
            elif nxt in jobs and nxt not in placed:
                stack.append((nxt, iter(sorted(_waits(jobs[nxt])))))

    for jid in sorted(jobs):
        if jid not in placed:
            place(jid)
    return out


# --- reading an export ---------------------------------------------------

def _read_json(path: str):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load(directory: str, versions_path: str) -> Board:
    """The export and its versions, with every problem of shape: a document
    against its schema, a wait on a job not on the board, a cycle among the
    waits, a document the versions file does not name or names without its
    document, and a count of jobs other than the board's own."""
    problems: List[str] = []
    meta: Optional[dict] = None
    jobs: Dict[str, dict] = {}
    versions: Dict[str, int] = {}
    try:
        raw = _read_json(versions_path)
    except (OSError, ValueError) as exc:
        problems.append("the versions file cannot be read: %s" % exc)
        raw = {}
    if not isinstance(raw, dict):
        problems.append("the versions file is not an object")
        raw = {}
    for key, value in raw.items():
        if not (is_int(value) and value >= 1):
            problems.append("the version of %s is not a whole number of at least 1" % key)
            continue
        versions[key] = value
    if not os.path.isdir(directory):
        problems.append("no export directory at %s" % directory)
        return Board(meta, jobs, versions, problems)
    exported: List[str] = []
    for collection in sorted(os.listdir(directory)):
        where = os.path.join(directory, collection)
        if not os.path.isdir(where):
            continue
        if collection not in COLLECTIONS:
            problems.append("the export holds an unknown collection %s" % collection)
            continue
        for name in sorted(os.listdir(where)):
            if not name.endswith(".json"):
                continue
            doc_id = name[:-5]
            key = "%s/%s" % (collection, doc_id)
            exported.append(key)
            try:
                doc = _read_json(os.path.join(where, name))
            except (OSError, ValueError) as exc:
                problems.append("%s cannot be read: %s" % (key, exc))
                continue
            if collection == META:
                if doc_id != BOARD:
                    problems.append("the export holds an unknown document %s" % key)
                    continue
                meta = doc if isinstance(doc, dict) else None
                problems.extend(meta_problems(doc))
                continue
            problems.extend(job_problems(doc, key))
            if isinstance(doc, dict):
                if doc.get("id") != doc_id:
                    problems.append("%s holds the job %r" % (key, doc.get("id")))
                jobs[doc_id] = doc
    for jid in sorted(jobs):
        for w in _waits(jobs[jid]):
            if w not in jobs:
                problems.append("jobs/%s waits on %s, which is not on the board" % (jid, w))
    loop = cycle(jobs)
    if loop:
        problems.append("the waits run in a cycle: %s" % " -> ".join(loop))
    for key in exported:
        if key not in versions:
            problems.append("the versions file does not name %s" % key)
    for key in sorted(set(versions) - set(exported)):
        problems.append("the versions file names %s, which the export does not hold" % key)
    if meta is not None and is_int(meta.get("jobs")) and meta["jobs"] != len(jobs):
        problems.append("the board holds %d job(s) and the export %d: the export is partial"
                        % (meta["jobs"], len(jobs)))
    return Board(meta, jobs, versions, problems)


# --- the writes ----------------------------------------------------------

def entry(collection: str, doc_id: str, data: dict, version: Optional[int]) -> dict:
    """One write of the batch: a whole document, pinned to the version read,
    or, for a document being created, not pinned."""
    out = {"op": "set", "collection": collection, "doc_id": doc_id, "data": data}
    if version is not None:
        out["if_version"] = version
    return out


def _sound(board: Board) -> None:
    """Refuse to decide anything over an export that does not verify, or
    one with no board yet."""
    if board.problems:
        raise Refused(["the export does not verify: %s" % p for p in board.problems])
    if board.meta is None:
        raise Refused(["the board has no meta/board; run init first"])


def _time(now: str) -> None:
    try:
        parse_time(now)
    except ValueError as exc:
        raise Refused(["--now: %s" % exc])


def _job(board: Board, jid: str) -> dict:
    job = board.jobs.get(jid)
    if job is None:
        raise Refused(["no job %s on the board" % jid])
    return job


def _write(board: Board, job: dict, **changes) -> dict:
    """The job's whole document after ``changes``, pinned; a change to None
    takes the field off."""
    data = dict(job)
    for key, value in changes.items():
        if value is None:
            data.pop(key, None)
        else:
            data[key] = value
    return entry(JOBS, job["id"], data, board.versions["%s/%s" % (JOBS, job["id"])])


def _meta(board: Board, **changes) -> dict:
    """The meta document after ``changes``, pinned."""
    data = dict(board.meta)
    data.update(changes)
    return entry(META, BOARD, data, board.versions[META_KEY])


def init(board: Board, notebook, cap: int = CAP_FULL,
         max_attempts: int = MAX_ATTEMPTS) -> List[dict]:
    """The write that creates the board's meta document."""
    reasons = ["the export does not verify: %s" % p for p in board.problems]
    if board.meta is not None or META_KEY in board.versions:
        reasons.append("the board already exists")
    data = {"schema": SCHEMA, "cap_full": cap, "max_attempts": max_attempts,
            "notebook": notebook, "claims": 0, "jobs": len(board.jobs)}
    reasons.extend(meta_problems(data))
    if reasons:
        raise Refused(reasons)
    return [entry(META, BOARD, data, None)]


def add(board: Board, given, now: str) -> List[dict]:
    """The writes that put the jobs of a jobs file on the board, queued, each
    after the jobs it waits on, with the meta document's count of jobs
    raised and pinned. A job already there with the same fields is skipped;
    one with other fields, a wait on a job neither there nor in the file, a
    cycle, an id that does not match its own parts, and more jobs than one
    batch holds are refused."""
    _sound(board)
    _time(now)
    if not isinstance(given, list):
        raise Refused(["the jobs file is not a list"])
    reasons: List[str] = []
    new: Dict[str, dict] = {}
    for i, job in enumerate(given):
        where = "job %d" % i
        if isinstance(job, dict) and isinstance(job.get("id"), str):
            where = "job %s" % job["id"]
        if isinstance(job, dict):
            for key in sorted(set(job) - set(GIVEN), key=str):
                reasons.append("%s gives %r, which the gate sets or the file may not give"
                               % (where, key))
        found = given_problems(job, where)
        reasons.extend(found)
        if found or not isinstance(job, dict) or set(job) - set(GIVEN):
            continue
        job = {"id": job["id"], "sitting": job["sitting"], "batch": job["batch"],
               "row": job["row"], "kind": job["kind"], "tier": job["tier"],
               "waits_on": list(job.get("waits_on", [])), "inputs": dict(job.get("inputs", {}))}
        jid = job["id"]
        if jid in new:
            if _same(new[jid], job):
                continue
            reasons.append("%s is given twice with different fields" % where)
            continue
        if jid in board.jobs:
            held = {k: board.jobs[jid].get(k) for k in GIVEN}
            if not _same(held, job):
                differ = [k for k in GIVEN if not _same({k: held[k]}, {k: job[k]})]
                reasons.append("%s is on the board with other %s" % (where, ", ".join(differ)))
            continue
        new[jid] = job
    if reasons:
        raise Refused(reasons)
    every = dict(board.jobs)
    every.update(new)
    for jid in sorted(new):
        for w in new[jid]["waits_on"]:
            if w not in every:
                reasons.append("job %s waits on %s, which is neither on the board nor in "
                               "the file" % (jid, w))
    loop = cycle(every)
    if loop:
        reasons.append("the waits would run in a cycle: %s" % " -> ".join(loop))
    if len(new) + 1 > BATCH_LIMIT:
        reasons.append("%d new jobs and the board's count make %d writes, over the %d one "
                       "batch takes: split the jobs file, what is waited on first"
                       % (len(new), len(new) + 1, BATCH_LIMIT))
    if reasons:
        raise Refused(reasons)
    if not new:
        return []
    out: List[dict] = [_meta(board, jobs=len(board.jobs) + len(new))]
    for jid in waited_first(new):
        data = dict(new[jid])
        data.update({"state": QUEUED, "result": {}, "attempts": 0, "created": now,
                     "updated": now})
        out.append(entry(JOBS, jid, data, None))
    return out


def _same(a: dict, b: dict) -> bool:
    """Two jobs' given fields alike, what each waits on compared as a set."""
    def norm(job):
        out = dict(job)
        if isinstance(out.get("waits_on"), list):
            out["waits_on"] = sorted(map(str, out["waits_on"]))
        return out
    return norm(a) == norm(b)


def is_runnable(board: Board, job: dict) -> bool:
    return job.get("state") == QUEUED and all(
        board.jobs.get(w, {}).get("state") == DONE for w in _waits(job))


def claimed_full(board: Board) -> int:
    return sum(1 for j in board.jobs.values()
               if j.get("state") == CLAIMED and j.get("tier") == FULL)


def blocked(board: Board) -> List[str]:
    """The queued jobs that cannot run until a failed job is queued again:
    each waits, directly or through jobs not yet done, on one that failed."""
    memo: Dict[str, bool] = {}

    def stuck(jid: str) -> bool:
        if jid in memo:
            return memo[jid]
        memo[jid] = False
        job = board.jobs[jid]
        found = False
        for w in _waits(job):
            dep = board.jobs.get(w)
            if dep is None or dep["state"] == DONE:
                continue
            if dep["state"] == FAILED or stuck(w):
                found = True
                break
        memo[jid] = found
        return found

    return [jid for jid in sorted(board.jobs)
            if board.jobs[jid]["state"] == QUEUED and stuck(jid)]


def _oldest(job: dict):
    return (parse_time(job["created"]), job["id"])


def runnable(board: Board) -> Tuple[List[str], List[str]]:
    """The runnable jobs, oldest first then by id, and those of them the cap
    on the full tier withholds."""
    _sound(board)
    ready = sorted((j for j in board.jobs.values() if is_runnable(board, j)), key=_oldest)
    full = claimed_full(board) >= board.meta["cap_full"]
    shown = [j["id"] for j in ready if not (full and j["tier"] == FULL)]
    held = [j["id"] for j in ready if full and j["tier"] == FULL]
    return shown, held


def claim(board: Board, jid: str, by, now: str) -> List[dict]:
    """A runnable job claimed. A claim of the full tier also raises the meta
    document's ``claims``, pinned, so that of two claims counted from one
    export only the first can land."""
    _sound(board)
    _time(now)
    job = _job(board, jid)
    reasons: List[str] = []
    if not is_address(by):
        reasons.append("the claimant %r is not an address" % by)
    if not is_runnable(board, job):
        if job["state"] != QUEUED:
            reasons.append("job %s is %s, not queued" % (jid, job["state"]))
        else:
            open_ = [w for w in _waits(job) if board.jobs[w]["state"] != DONE]
            reasons.append("job %s waits on %s, not done" % (jid, ", ".join(open_)))
    if job["tier"] == FULL and claimed_full(board) >= board.meta["cap_full"]:
        reasons.append("the cap is reached: %d of the full tier claimed, cap %d"
                       % (claimed_full(board), board.meta["cap_full"]))
    if reasons:
        raise Refused(reasons)
    out = [_write(board, job, state=CLAIMED, claimed_by=by, updated=now)]
    if job["tier"] == FULL:
        out.insert(0, _meta(board, claims=board.meta["claims"] + 1))
    return out


def _held_by(job: dict, by, reasons: List[str]) -> None:
    if job["state"] != CLAIMED:
        reasons.append("job %s is %s, not claimed" % (job["id"], job["state"]))
    elif job.get("claimed_by") != by:
        reasons.append("job %s is claimed by %s, not %s" % (job["id"], job["claimed_by"], by))


def done(board: Board, jid: str, by, result, now: str) -> List[dict]:
    """A claimed job done by its claimant, with its result."""
    _sound(board)
    _time(now)
    job = _job(board, jid)
    reasons: List[str] = []
    _held_by(job, by, reasons)
    reasons.extend(result_problems(result))
    if reasons:
        raise Refused(reasons)
    return [_write(board, job, state=DONE, result=dict(result), updated=now)]


def fail(board: Board, jid: str, by, reason: str, now: str) -> List[dict]:
    """A claimed job failed by its claimant, with the code of the reason.
    A job ``queued`` or ``waiting`` is failed ``superseded`` with no claim,
    its attempts unchanged, since a job that waits on one not done can never
    be claimed and a sitting that ended left its jobs to no one; every other
    reason needs the claim."""
    _sound(board)
    _time(now)
    job = _job(board, jid)
    reasons: List[str] = []
    if not is_address(by):
        reasons.append("the claimant %r is not an address" % by)
    if not (reason == SUPERSEDED and job["state"] in (QUEUED, WAITING)):
        _held_by(job, by, reasons)
    if reason not in REASONS:
        reasons.append("the reason %r is not one of %s" % (reason, ", ".join(REASONS)))
    if reasons:
        raise Refused(reasons)
    return [_write(board, job, state=FAILED, reason=reason, updated=now)]


def retry(board: Board, jid: str, now: str) -> List[dict]:
    """A failed job queued again, with one more attempt; refused once its
    attempts are at the board's limit."""
    _sound(board)
    _time(now)
    job = _job(board, jid)
    reasons: List[str] = []
    if job["state"] != FAILED:
        reasons.append("job %s is %s, not failed" % (jid, job["state"]))
    if job["attempts"] >= board.meta["max_attempts"]:
        reasons.append("job %s is at the limit of %d attempts"
                       % (jid, board.meta["max_attempts"]))
    if reasons:
        raise Refused(reasons)
    return [_write(board, job, state=QUEUED, attempts=job["attempts"] + 1, reason=None,
                   claimed_by=None, updated=now)]


def stale(board: Board, older_than: int, now: str) -> List[dict]:
    """The claimed jobs not updated for more than ``older_than`` seconds
    before ``now``, longest quiet first."""
    at = parse_time(now)
    found = [j for j in board.jobs.values() if j["state"] == CLAIMED
             and (at - parse_time(j["updated"])).total_seconds() > older_than]
    return sorted(found, key=lambda j: (parse_time(j["updated"]), j["id"]))


def release(board: Board, older_than: int, now: str) -> Tuple[List[dict], int]:
    """Every claimed job not updated for more than ``older_than`` seconds,
    queued again with one more attempt, or failed with ``timeout`` once its
    attempts are at the limit; the longest quiet first, as many as one batch
    takes, with the number left for another run."""
    _sound(board)
    _time(now)
    if not (is_int(older_than) and older_than >= 0):
        raise Refused(["--older-than is not a whole number of seconds"])
    quiet = stale(board, older_than, now)
    out: List[dict] = []
    for job in quiet[:BATCH_LIMIT]:
        if job["attempts"] >= board.meta["max_attempts"]:
            out.append(_write(board, job, state=FAILED, reason=TIMEOUT, updated=now))
        else:
            out.append(_write(board, job, state=QUEUED, attempts=job["attempts"] + 1,
                              claimed_by=None, updated=now))
    return out, max(0, len(quiet) - BATCH_LIMIT)


def wait(board: Board, jid: str, now: str) -> List[dict]:
    """A queued job held for the principal."""
    _sound(board)
    _time(now)
    job = _job(board, jid)
    if job["state"] != QUEUED:
        raise Refused(["job %s is %s, not queued" % (jid, job["state"])])
    return [_write(board, job, state=WAITING, updated=now)]


def resume(board: Board, jid: str, now: str) -> List[dict]:
    """A job the principal held, queued again."""
    _sound(board)
    _time(now)
    job = _job(board, jid)
    if job["state"] != WAITING:
        raise Refused(["job %s is %s, not waiting" % (jid, job["state"])])
    return [_write(board, job, state=QUEUED, updated=now)]


def status(board: Board) -> dict:
    """Counts by state and by kind, the ids waiting on the principal, the
    queued ids a failure blocks, and per kind how many jobs failed and how
    many took more than one attempt: the measure of how well a helper fits
    its work. A job failed ``superseded`` is counted by state and kind and
    not in the fit, failed or retried: it was closed with its sitting, and
    says nothing of the helper."""
    _sound(board)
    jobs = [board.jobs[j] for j in sorted(board.jobs)]
    states = {s: sum(1 for j in jobs if j["state"] == s) for s in STATES}
    kinds = {k: sum(1 for j in jobs if j["kind"] == k) for k in KINDS
             if any(j["kind"] == k for j in jobs)}
    measured = [j for j in jobs if j.get("reason") != SUPERSEDED]
    fit = {k: {"failed": sum(1 for j in measured if j["kind"] == k and j["state"] == FAILED),
               "retried": sum(1 for j in measured if j["kind"] == k and j["attempts"] > 0)}
           for k in kinds}
    return {"states": states, "kinds": kinds,
            "waiting": [j["id"] for j in jobs if j["state"] == WAITING],
            "blocked": blocked(board), "fit": fit}


def status_lines(found: dict) -> List[str]:
    """The status as the command prints it."""
    out = ["states: " + ", ".join("%s %d" % (s, n) for s, n in found["states"].items())]
    out.append("kinds: " + (", ".join("%s %d" % (k, n) for k, n in found["kinds"].items())
                            or "none"))
    out.append("waiting on the principal: " + (", ".join(found["waiting"]) or "none"))
    out.append("blocked by a failed job: " + (", ".join(found["blocked"]) or "none"))
    for kind, f in found["fit"].items():
        out.append("fit %s: failed %d, retried %d" % (kind, f["failed"], f["retried"]))
    return out
