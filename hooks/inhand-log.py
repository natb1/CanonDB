#!/usr/bin/env python3
"""The helpers a session starts, recorded with no act of the session.

One hook on three events, installed by the plugin, each by the session's id
the harness gives it (`hypo/inhand.py`):

- PreToolUse on the Agent tool: a launch is recorded, its kind (the
  `subagent_type`, `general-purpose` where none is named), its description
  and the time;
- SubagentStart: the oldest launch of that kind not yet started is given the
  helper's id; a start with no launch recorded is added;
- SubagentStop: the helper's launch is marked ended, and is no longer in
  hand;
- PostToolUse on the Agent tool: the newest launch of that kind and
  description not yet returned is marked returned, with the helper's id the
  tool's result names, so that a launch is tied to the helper it ran by its
  own call, whatever row the start was given.

What is recorded is printed back, with its age, before a compaction
(`inhand-precompact.py`) and after one (`brief-session.py inhand`), beside
the list the session keeps itself. The record is kept in the brief's
directory under the session's id, outside every repository. The hook decides
nothing and prints nothing a model reads; where the project names no
notebook, or the call cannot be read, it records nothing.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def _briefing():
    spec = importlib.util.spec_from_file_location("principal_briefing",
                                                  os.path.join(HERE, "briefing.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def record(call, env=None, b=None) -> bool:
    env = os.environ if env is None else env
    if not isinstance(call, dict):
        return False
    b = b or _briefing()
    root, directory = b.where(call.get("cwd"), env)
    if not root or not directory:
        return False
    from hypo import inhand
    session = call.get("session_id")
    event = call.get("hook_event_name")
    at = inhand.now()
    if event == "PreToolUse" and call.get("tool_name") in ("Agent", "Task"):
        given = call.get("tool_input") if isinstance(call.get("tool_input"), dict) else {}
        return inhand.launched(directory, session, given.get("subagent_type"),
                               given.get("description"), at)
    if event == "SubagentStart" and call.get("agent_id"):
        return inhand.started(directory, session, call.get("agent_type"), call["agent_id"], at)
    if event == "PostToolUse" and call.get("tool_name") in ("Agent", "Task"):
        given = call.get("tool_input") if isinstance(call.get("tool_input"), dict) else {}
        return inhand.returned(directory, session, given.get("subagent_type"),
                               given.get("description"), inhand.agent_of(
                                   call.get("tool_response")), at)
    if event == "SubagentStop" and call.get("agent_id"):
        return inhand.stopped(directory, session, call["agent_id"], at)
    return False


def main() -> int:
    try:
        raw = sys.stdin.buffer.read()
    except (OSError, ValueError):
        raw = b""
    try:
        b = _briefing()
        record(b.call(raw), b=b)
    except Exception:  # pragma: no cover - a record not made decides nothing
        pass
    print(json.dumps({}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
