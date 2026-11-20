#!/usr/bin/env python3
"""The work in hand, put into what a compaction reads.

A PreCompact hook (triggers `manual` and `auto`), installed by the plugin.
The harness takes this hook's output into the instructions of the
compaction's summary, so what it prints lands in the compaction's input: the
work in hand of this session, by the session's id, the path of the file the
session keeps its list in (`tools/inhand.py`), the list as it stands and the
helpers the hooks recorded as started and not yet ended, each with its age, said as a record of what is pending and holding
no instruction. After the compaction `brief-session.py inhand` prints the
list back from the file, so nothing in hand rests on the summary alone.

Only the speaking session's own compaction is given it: where the input
carries an agent id (a helper's), names a kind the allow-list gives less
than all, or cannot be read, nothing is printed. Fail open, in one line: where the project names no notebook nothing is
printed; where no list is kept, that is said. It never blocks a compaction.
"""

from __future__ import annotations

import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name, file):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, file))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    try:
        raw = sys.stdin.buffer.read()
    except (OSError, ValueError):
        raw = b""
    try:
        b = _load("principal_briefing", "briefing.py")
        session = _load("principal_brief_session", "brief-session.py")
        call = b.call(raw)
        # a helper's compaction, or one that cannot be told apart from it,
        # is given nothing of the session's work in hand
        if not session.speaking(b, call):
            return 0
        root, directory = b.where(call.get("cwd") or os.getcwd(), os.environ)
        if not root or not directory:
            return 0
        sys.stdout.write(session.inhand_words(b, directory, call.get("session_id")))
    except Exception as exc:  # pragma: no cover - fail open, in one line
        print("The work in hand could not be read: %s" % type(exc).__name__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
