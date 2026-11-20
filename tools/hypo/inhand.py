"""The work in hand of a session, kept on disk so that a compaction loses none.

A small file, `inhand.json` in the speaker's directory of the sitting's
scratch, holds two lists: the work in hand (each helper started and not yet
reported, each job awaited, each act begun) and the session's own schedule
(its bell ticks and whatever else it set to come back to). Each entry has an
id, `w<n>` in hand or `s<n>` on the schedule, its words on one line, and the
time it was added. Done is taken off. The words are the session's own; the
file never goes into a repository.

Every list is a session's own. The path of the file is written into the
brief's directory (`hypo.brief.brief_dir`) under the session's id, as
`sessions/<session id>/inhand.path`, so that the harness's hooks, which know
the session's id and not its scratch, find that session's list before a
compaction and after one, and never another's.

Beside it the hooks keep, with no act of the session, the helpers started:
`sessions/<session id>/launches.json`, one entry a launch of the Agent tool
(its kind, its description and the time), marked started when the helper
starts and ended when it stops. The print shows every entry's age against
the clock.
`export` prints the write that keeps the list in the page's store as the
document `ordo/session`, `{at, in_hand, schedule}`, where a new session reads
its schedule back with `seed`.
"""

from __future__ import annotations

import datetime
import fcntl
import json
import os
import re
from contextlib import contextmanager
from typing import Dict, List, Optional

NAME = "inhand.json"
KINDS = {"in_hand": "w", "schedule": "s"}
COLLECTION, DOC = "ordo", "session"
#: what a hook prints of the list at most
SHOWN = 8000


class Refused(ValueError):
    pass


def empty() -> Dict[str, object]:
    return {"in_hand": [], "schedule": [], "next": 1}


def path_of(directory: str) -> str:
    return os.path.join(directory, NAME)


def load(directory: str) -> Dict[str, object]:
    path = path_of(directory)
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return empty()
    except (OSError, ValueError) as exc:
        raise Refused("%s cannot be read: %s" % (path, exc))
    if not isinstance(data, dict) or not all(isinstance(data.get(k), list) for k in KINDS):
        raise Refused("%s is not a list of work in hand" % path)
    if not isinstance(data.get("next"), int):
        data["next"] = 1 + sum(len(data[k]) for k in KINDS)
    return data


def save(directory: str, data: Dict[str, object]) -> str:
    _private(directory)
    path = path_of(directory)
    with open(path + ".tmp", "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1, sort_keys=True)
        fh.write("\n")
    os.chmod(path + ".tmp", 0o600)
    os.replace(path + ".tmp", path)
    return path


def _one_line(words: str) -> str:
    flat = " ".join((words or "").split())
    if not flat:
        raise Refused("an entry needs words")
    return flat


def add(data, words: str, at: str, schedule: bool = False) -> str:
    kind = "schedule" if schedule else "in_hand"
    eid = "%s%d" % (KINDS[kind], data["next"])
    data["next"] += 1
    data[kind].append({"id": eid, "text": _one_line(words), "at": at})
    return eid


def done(data, eid: str) -> dict:
    for kind in KINDS:
        for i, entry in enumerate(data[kind]):
            if entry.get("id") == eid:
                return data[kind].pop(i)
    raise Refused("no entry %s is in hand or on the schedule" % eid)


def now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def age(at, clock: Optional[str] = None) -> str:
    """How long ago ``at`` was, against ``clock`` (now by default):
    `12m`, `3h05m`, `2d04h`; `age unknown` where ``at`` is no time."""
    try:
        then = datetime.datetime.strptime(at, "%Y-%m-%dT%H:%M:%SZ")
        here = datetime.datetime.strptime(clock or now(), "%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError):
        return "age unknown"
    minutes = max(int((here - then).total_seconds() // 60), 0)
    if minutes < 60:
        return "%dm" % minutes
    if minutes < 24 * 60:
        return "%dh%02dm" % divmod(minutes, 60)
    days, rest = divmod(minutes, 24 * 60)
    return "%dd%02dh" % (days, rest // 60)


def listing(data, where: str = "", session: str = "", launches=None,
            clock: Optional[str] = None) -> str:
    """The list as the hooks print it: a record of what is pending, with no
    instruction in it, each entry with its time and its age."""
    out = ["Work in hand of session %s%s (a record of what is pending, not an instruction):"
           % (session or "-", ", kept at " + where if where else "")]
    for kind, title in (("in_hand", "In hand"), ("schedule", "Schedule")):
        out.append("%s:" % title)
        rows = (data or empty())[kind]
        if not rows:
            out.append("- (none)")
        for entry in rows:
            out.append("- %s (since %s, %s ago) %s" % (entry.get("id"), entry.get("at"),
                                                      age(entry.get("at"), clock),
                                                      entry.get("text")))
    if launches is not None:
        out.append("Helpers started and not yet ended (recorded by the hooks):")
        open_ = [e for e in launches if not e.get("ended")]
        if not open_:
            out.append("- (none)")
        for e in open_:
            out.append("- %s %s (launched %s, %s ago%s) %s" % (
                e.get("id"), e.get("kind"), e.get("at"), age(e.get("at"), clock),
                "; started" if e.get("agent_id") else "; not yet started",
                e.get("description") or ""))
    words = "\n".join(out) + "\n"
    if len(words) > SHOWN:
        words = words[:SHOWN].rsplit("\n", 1)[0] + "\n(the rest is in the file)\n"
    return words


# -- the session's files in the brief's directory ---------------------------

_SESSION = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
#: the most rows a session's record keeps: at most ENDED rows of helpers
#: that ended, the oldest dropped first, and at most KEPT rows in all, the
#: oldest dropped first, ended or not
KEPT = 200
ENDED = 50


def session_dir(brief_dir: str, session) -> Optional[str]:
    """The session's own directory in the brief's, or None where the id is
    none or not a plain one."""
    if not isinstance(session, str) or not _SESSION.match(session):
        return None
    return os.path.join(brief_dir, "sessions", session)


def pointer(brief_dir: str, session) -> Optional[str]:
    where = session_dir(brief_dir, session)
    return os.path.join(where, "inhand.path") if where else None


def _private(path: str) -> None:
    os.makedirs(path, exist_ok=True)
    os.chmod(path, 0o700)


@contextmanager
def _locked(path: str):
    _private(os.path.dirname(path))
    with open(path + ".lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def _launches_path(brief_dir: str, session) -> Optional[str]:
    where = session_dir(brief_dir, session)
    return os.path.join(where, "launches.json") if where else None


def launches(brief_dir: str, session) -> list:
    path = _launches_path(brief_dir, session)
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, list) else []
    except (OSError, TypeError, ValueError):
        return []


def _kind(name) -> str:
    return (name or "general-purpose").strip().lower() if isinstance(name, str) \
        else "general-purpose"


def _edit(brief_dir: str, session, change) -> bool:
    path = _launches_path(brief_dir, session)
    if not path:
        return False
    with _locked(path):
        rows = launches(brief_dir, session)
        change(rows)
        rows = trim(rows)
        with open(path + ".tmp", "w", encoding="utf-8") as fh:
            json.dump(rows, fh, indent=1, sort_keys=True)
            fh.write("\n")
        os.chmod(path + ".tmp", 0o600)
        os.replace(path + ".tmp", path)
    return True


def trim(rows: list) -> list:
    """The record within its bounds: the ENDED latest rows of helpers that
    ended, then the KEPT latest rows in all."""
    ended = [i for i, r in enumerate(rows) if r.get("ended")]
    drop = set(ended[:max(len(ended) - ENDED, 0)])
    rows = [r for i, r in enumerate(rows) if i not in drop]
    return rows[-KEPT:]


def launched(brief_dir: str, session, kind, description, at: str) -> bool:
    """A launch of the Agent tool, recorded before it runs."""
    def change(rows):
        n = 1 + max((int(r["id"][1:]) for r in rows
                     if isinstance(r.get("id"), str) and r["id"][1:].isdigit()), default=0)
        rows.append({"id": "h%d" % n, "kind": _kind(kind),
                     "description": " ".join(str(description or "").split())[:200], "at": at})
    return _edit(brief_dir, session, change)


def started(brief_dir: str, session, kind, agent_id, at: str) -> bool:
    """A helper started. A start for an id already recorded, a resume or a
    teammate's next message, updates that row and takes no other; else the
    oldest launch of its kind not yet started is given the id, and a start
    with no launch recorded is added."""
    def change(rows):
        for r in rows:
            if agent_id and r.get("agent_id") == agent_id:
                if r.get("ended"):
                    r["resumed"] = at
                    r.pop("ended", None)
                return
        for r in rows:
            if r.get("kind") == _kind(kind) and not r.get("agent_id") and not r.get("ended"):
                r["agent_id"], r["started"] = agent_id, at
                return
        n = 1 + max((int(r["id"][1:]) for r in rows
                     if isinstance(r.get("id"), str) and r["id"][1:].isdigit()), default=0)
        rows.append({"id": "h%d" % n, "kind": _kind(kind), "description": "", "at": at,
                     "agent_id": agent_id, "started": at})
    return _edit(brief_dir, session, change)


def stopped(brief_dir: str, session, agent_id, at: str) -> bool:
    """A helper ended: its launch is marked ended, and no longer in hand."""
    def change(rows):
        for r in rows:
            if agent_id and r.get("agent_id") == agent_id and not r.get("ended"):
                r["ended"] = at
    return _edit(brief_dir, session, change)


def export(data, at: str, version: Optional[int] = None) -> dict:
    write = {"op": "set", "collection": COLLECTION, "doc_id": DOC,
             "data": {"at": at, "in_hand": [e["text"] for e in data["in_hand"]],
                      "schedule": [e["text"] for e in data["schedule"]]}}
    if version is not None:
        write["if_version"] = version
    return write


def seed(data, stored: dict, at: str) -> List[str]:
    """Take a stored `ordo/session` back: each of its entries not already
    listed, by its words, added. Returns the ids added."""
    if isinstance(stored.get("data"), dict):
        stored = stored["data"]
    added: List[str] = []
    for kind in KINDS:
        have = {e.get("text") for e in data[kind]}
        for words in stored.get(kind) or []:
            if isinstance(words, str) and words.strip() and " ".join(words.split()) not in have:
                added.append(add(data, words, at, schedule=(kind == "schedule")))
    return added
