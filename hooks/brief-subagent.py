#!/usr/bin/env python3
"""A helper's own brief, put in its context by the harness as it starts.

A SubagentStart hook, installed by the plugin. The harness documents that
such a hook "can inject context into the subagent": its `additionalContext`
is a "String added to the subagent's context at the start of its
conversation, before its first prompt". So a helper's brief is given here,
and the call that starts it is never rewritten and no launch is approved: a
helper of the plugin's kinds loads no instruction file (`omitClaudeMd`), and
this is how its brief reaches it.

What it gives, by `brief-sides.json` (`briefing.py`), an allow-list by kind
that defaults to nobody: a kind given `all` receives the session's standing
brief and the neighbourhood of the line in hand, as `tools/brief.py install`
last wrote them; a kind given `ai` receives both made again over the AI's
own answers alone, from the graph copied beside them; every other kind, a
helper of no kind, and a start that names no agent, nothing. The hook input
carries no prompt, so the neighbourhood is the line in hand's, not one
picked from the helper's task.

The harness keeps at most 10,000 characters of one hook's context, so the
brief is cut at line ends into parts and `hooks.json` runs this hook once
for each, `brief-subagent.py 1` to `brief-subagent.py 4`; a part past the
last gives nothing. Fail open: where the project names no notebook, or no
brief is installed, nothing is given and nothing is decided; the hook never
blocks a start.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name, file):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, file))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def brief_for(b, directory: str, side: str) -> str:
    """The helper's brief at ``side``: the installed files for `all`, made
    again over the AI's own answers for `ai`; '' where none is installed."""
    brief = b.brief
    if side == "all":
        return "\n".join(t for t in (b.read(os.path.join(directory, brief.FILES[n]))
                                     for n in ("standing", "neighbourhood")) if t)
    graph = b.graph(directory)
    if graph is None:
        return ""
    made = b.source(directory)
    digest = brief.fingerprint(os.path.join(directory, brief.FILES["graph"]))
    first = brief.standing(graph, digest, "ai", made.get("at"))
    line = [q for q in made.get("line") or [] if graph.get(q) is not None]
    words, _ = brief.combine(graph, digest, first, line, "ai", made.get("at"))
    return words


def decide(call, which: int, env=None, b=None, session=None) -> dict:
    env = os.environ if env is None else env
    b = b or _load("principal_briefing", "briefing.py")
    session = session or _load("principal_brief_session", "brief-session.py")
    if not isinstance(call, dict):
        return {}
    cwd = call.get("cwd")
    root, directory = b.where(cwd, env)
    if not root or not directory:
        return {}
    side = b.side_for(call.get("agent_type"), cwd, env, main=False)
    if side is None:
        return {}
    words = brief_for(b, directory, side)
    if not words:
        return {}
    parts = session.split(words, session.PART - 120)
    if which > len(parts):
        return {}
    head = "(The helper's brief, side %s, part %d of %d.)\n" % (side, which, len(parts))
    return {"hookSpecificOutput": {"hookEventName": "SubagentStart",
                                   "additionalContext": head + parts[which - 1]}}


def main(argv) -> int:
    try:
        raw = sys.stdin.buffer.read()
    except (OSError, ValueError):
        raw = b""
    try:
        b = _load("principal_briefing", "briefing.py")
        decision = decide(b.call(raw), int(argv[1]) if len(argv) > 1 else 1, b=b)
    except Exception:  # pragma: no cover - fail open: no brief, no decision
        decision = {}
    print(json.dumps(decision))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
