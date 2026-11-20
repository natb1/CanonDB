#!/usr/bin/env python3
"""The session's brief, put in context by the harness at its start, at a
resume and after a compaction.

A SessionStart hook (sources `startup`, `resume`, `clear` and `compact`), installed
by the plugin. It prints, as plain text the harness adds to the session's
context, what `tools/brief.py install` last wrote into the brief's directory
(`briefing.py` says where): one line of staleness, then the standing brief
and the neighbourhood of the line in hand. The harness keeps at most 10,000
characters of one hook's output in context (over that, it keeps a path and
a preview), so the text is cut at line
boundaries into parts of at most `PART` characters and `hooks.json` runs
this hook once for each, `brief-session.py 1` to `brief-session.py 4`, each
printing its own part under a line saying which it is; a part past the last
prints nothing. Run as `brief-session.py inhand`, it prints the work in hand
of this session, by the session's id the harness gives it: the list the
session keeps (`tools/inhand.py`) and the helpers the hooks recorded as
started and not yet ended, each with its age; never another session's.

Staleness. The stamp of each part written is held against the graph copied
beside it, and that copy against the graph it was made from: a graph that
has moved since is said in one line, with the command that makes the brief
again, and where that file is gone the line says freshness cannot be told.
The time it was made is shown with its age. A hook cannot read the notebook, so a
move made by another session is seen at the next fetch and not before.

Fail open, in one line: where the project names no notebook nothing is
printed; where the brief's directory holds no brief, that is said, and
nothing else. The hook decides nothing and never blocks.
"""

from __future__ import annotations

import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

#: what one part holds at most, under the harness's 10,000-character cap
PART = 9500
#: how many parts `hooks.json` runs
PARTS = 4


def _briefing():
    spec = importlib.util.spec_from_file_location("principal_briefing",
                                                  os.path.join(HERE, "briefing.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def split(words: str, size: int = PART) -> list:
    """``words`` in parts of at most ``size`` characters, cut at line ends."""
    parts, current = [], ""
    for line in words.splitlines(keepends=True):
        while len(line) > size:
            if current:
                parts.append(current)
                current = ""
            parts.append(line[:size])
            line = line[size:]
        if len(current) + len(line) > size:
            parts.append(current)
            current = ""
        current += line
    if current:
        parts.append(current)
    return parts


def status(b, directory: str) -> str:
    brief = b.brief
    made = b.source(directory)
    copy = os.path.join(directory, brief.FILES["graph"])
    if not os.path.isfile(copy):
        return "No brief is installed for this project: run tools/brief.py install over the opening's graph."
    digest = brief.fingerprint(copy)
    stale = []
    for name in ("standing", "neighbourhood"):
        found = brief.stale(b.read(os.path.join(directory, brief.FILES[name])), digest)
        stale += ["%s: %s" % (name, f) for f in found]
    origin = made.get("graph")
    made_at = made.get("at") or "an unstated time"
    from hypo import inhand
    old = inhand.age(made.get("at")) if made.get("at") else "age unknown"
    if stale:
        return ("The brief is stale (%s); run tools/brief.py install again over the graph as "
                "it now stands." % "; ".join(stale))
    if not (isinstance(origin, str) and os.path.isfile(origin)):
        return ("Whether the brief is fresh cannot be told: the graph it was made from is no "
                "longer on disk. It was made at %s (%s ago) for the line %s; install it again "
                "over the opening's graph." % (made_at, old, " ".join(made.get("line") or [])
                                               or "-"))
    if brief.fingerprint(origin) != digest:
        return ("The brief is stale (the graph at %s has changed since it was made); run "
                "tools/brief.py install again over the graph as it now stands." % origin)
    return ("The brief matches the graph it was made from (%s), made at %s (%s ago) for the "
            "line %s; a move of the notebook since the last fetch is not seen here."
            % (origin, made_at, old, " ".join(made.get("line") or []) or "-"))


def whole(b, directory: str) -> str:
    brief = b.brief
    words = [status(b, directory), ""]
    for name in ("standing", "neighbourhood"):
        text = b.read(os.path.join(directory, brief.FILES[name]))
        if text:
            words.append(text)
    return "\n".join(words)


def inhand_words(b, directory: str, session) -> str:
    """The session's own work in hand, and the helpers the hooks recorded as
    started and not yet ended; never another session's."""
    from hypo import inhand
    path = inhand.pointer(directory, session)
    if not path:
        return "No session's id was given, so no work in hand can be shown.\n"
    kept = b.read(path).strip()
    data, where = None, ""
    if kept and os.path.isfile(kept):
        try:
            data, where = inhand.load(os.path.dirname(kept)), kept
        except inhand.Refused as exc:
            return "The work in hand of session %s cannot be read: %s\n" % (session, exc)
    words = inhand.listing(data, where, session, inhand.launches(directory, session))
    if kept and not where:
        words += "Its list was last kept at %s, which is gone.\n" % kept
    elif not kept:
        words += "The session has kept no list of its own (tools/inhand.py).\n"
    return words


def speaking(b, call) -> bool:
    """Whether the hook fires in the speaking session's own turn: an input
    that parsed, with no agent id, whose agent type (where the session was
    started as one) is given all."""
    if not isinstance(call, dict) or not call:
        return False
    if call.get("agent_id"):
        return False
    return b.side_for(call.get("agent_type"), call.get("cwd"), os.environ) == "all"


def main(argv) -> int:
    which = argv[1] if len(argv) > 1 else "1"
    try:
        raw = sys.stdin.buffer.read()
    except (OSError, ValueError):
        raw = b""
    try:
        b = _briefing()
        call = b.call(raw)
        if not isinstance(call, dict):
            return 0
        root, directory = b.where(call.get("cwd") or os.getcwd(), os.environ)
        if not root:
            return 0
        # only the speaking session's own turn is given the brief or the
        # work in hand: never a helper (an agent id), never a kind the
        # allow-list gives less than all, never a call that cannot tell
        if not speaking(b, call):
            return 0
        if not directory:
            if which == "1":
                print("No brief can be kept for this project: its directory would stand in a checkout.")
            return 0
        if which == "inhand":
            sys.stdout.write(inhand_words(b, directory, call.get("session_id")))
            return 0
        n = int(which)
        parts = split(whole(b, directory), PART - 120)
        if n > len(parts):
            return 0
        head = "(The brief, part %d of %d, from %s.)\n" % (n, len(parts), directory)
        if n == PARTS and len(parts) > PARTS:
            rest = "\n(The brief runs past what is loaded here; the rest is in %s.)\n" % directory
            sys.stdout.write(head + parts[n - 1][:PART - len(head) - len(rest)] + rest)
            return 0
        sys.stdout.write(head + parts[n - 1])
    except Exception as exc:  # pragma: no cover - fail open, in one line
        print("The brief could not be loaded: %s" % type(exc).__name__)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
