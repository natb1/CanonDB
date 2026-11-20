#!/usr/bin/env python3
"""The file write gate of the sitting's kinds: the coordinator writes its own
scratch, the interviewer writes nothing the gates or the project's setup
stand on, and every other kind writes no file.

A PreToolUse hook on Write and Edit, and on MultiEdit and NotebookEdit,
which write a file as Edit does, installed by the plugin and so fired on
every such call of every turn in a project that has the plugin. It decides
only for this plugin's kinds; every other turn gets no opinion, the main
thread (which carries no `agent_type`) among them, and the harness's
ordinary permissions apply. A write that is admitted gets no opinion either,
never an allow: the harness's permissions still apply to it.

- The coordinator writes a path under a directory named `coordinator`
  below a scratch root the gates recognise (`/tmp/claude-*/…/scratchpad/`
  or `~/.claude/jobs/<id>/tmp/`), held as `kinds.py` holds a path:
  absolute, no `..`, outside the project, the plugin's root and `~/.claude`
  (a session's `~/.claude/jobs/<id>/tmp` aside), its links resolved. That is
  `$SCRATCH/coordinator/`, where its definition keeps everything it writes.
- The interviewer's Write and Edit are refused, by an absolute path with no
  `..`, its links resolved and its case folded, the project's `.principal/`
  and `.claude/`, any directory named `.principal` or `.claude` wherever it
  stands (a session's `~/.claude/jobs/<id>/tmp` aside), the plugin's root,
  and `~/.claude`; where no project is found at all, every path. That
  holds the interviewer only against a slip of these tools: its shell is
  not confined (the shell gate gives it no opinion), so one shell line
  reaches every file named here, and for the speaker the rule that only
  the recorder writes the notebook is held by its definition and the
  sitting's entry point alone. What it writes elsewhere in the project is
  its definition's to keep.
- Every other kind of this plugin is refused every call the gate fires on:
  none of them is granted a writing tool, and this is the second line.

Which turn is a kind: `kinds.py`, which every gate of this plugin shares.
The path is `file_path`, or `notebook_path` for NotebookEdit; a call that
names neither, or names something that is not a path, is refused to a kind.

A refusal is one plain sentence saying what the kind may write. A guarded
turn fails closed: a call the gate cannot make sense of is refused.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
AGENTS = os.path.join(ROOT, "agents")


def _sibling(name: str, file: str):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, file))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


#: what the gates take from `kinds.py`; a file without them is no rule
SHARED = ("kind_of", "named_any", "spelled", "plugin_name", "places", "defined_here",
          "consumer", "held", "resolved", "within", "within_folded", "claude_home",
          "in_jobs_tmp", "project_roots", "plugin_roots", "under", "below_scratch")

try:
    KINDS = _sibling("principal_kinds", "kinds.py")
    if not all(callable(getattr(KINDS, n, None)) for n in SHARED):
        raise ImportError("kinds.py")
except BaseException:  # no rule is no decision: the call is blocked
    sys.stderr.write("The plugin's hooks/kinds.py does not load, so this gate blocks every "
                     "call until the plugin is whole again.\n")
    sys.exit(2)

COORDINATOR = "coordinator"
SPEAKER = "interviewer"
#: every kind this plugin defines
GUARDED_KINDS = ("ai-recorder", "checker", "clean-reader", "comparer", "coordinator",
                 "fetcher", "grader", "interviewer", "recorder", "reviewer")
#: the tools that write a file
WRITERS = ("Write", "Edit", "MultiEdit", "NotebookEdit")

SAYS = {
    COORDINATOR: "a coordinator writes only under its own coordinator directory in the "
                 "sitting's scratch",
    SPEAKER: "the interviewer writes no file in the project's .principal or .claude, the "
             "plugin's root or ~/.claude, and only by an absolute path",
}
NOTHING = "this kind writes no file; its work is done with the tools it was given"


def kind_of(agent, plugin: str, cwd, env, own: str = AGENTS) -> str:
    return KINDS.kind_of(agent, GUARDED_KINDS, plugin, cwd, env, own)


#: the directories of a project's setup, refused to the interviewer wherever
#: they stand
SETUP = (".principal", ".claude")


def coordinator_may(path, cwd, env) -> bool:
    where = KINDS.held(path, cwd, env)
    return bool(where) and KINDS.under(where, COORDINATOR, env)


def speaker_may(path, cwd, env) -> bool:
    where = KINDS.resolved(path)
    if not where:
        return False
    home = KINDS.claude_home(env)
    roots = KINDS.project_roots(cwd, env)
    if not roots:
        return False
    jobs = KINDS.in_jobs_tmp(where.casefold(), home.casefold())
    for root in roots:
        for kept in SETUP:
            if KINDS.within_folded(where, os.path.join(root, kept)):
                return False
    if not jobs and any(p.casefold() in SETUP for p in where.split(os.sep)):
        return False
    for root in KINDS.plugin_roots(env):
        if KINDS.within_folded(where, root):
            return False
    if KINDS.within_folded(where, home) and not jobs:
        return False
    return True


def _answer(decision: str, reason: str) -> dict:
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                   "permissionDecision": decision,
                                   "permissionDecisionReason": reason}}


def decide(call, env=None, plugin=None, own: str = AGENTS) -> dict:
    """The permission decision for one call, as the hook's JSON output; an
    empty object for every turn that is not a kind, and for a write a kind
    may make."""
    if not isinstance(call, dict):
        return {}
    env = os.environ if env is None else env
    plugin = KINDS.plugin_name() if plugin is None else plugin
    cwd = call.get("cwd")
    kind = kind_of(call.get("agent_type"), plugin, cwd, env, own)
    if not kind:
        return {}
    tool = call.get("tool_name")
    if isinstance(tool, str) and tool not in WRITERS:
        return {}
    if kind not in SAYS:
        return _answer("deny", NOTHING)
    tool_input = call.get("tool_input")
    path = None
    if isinstance(tool_input, dict):
        path = tool_input.get("notebook_path" if tool == "NotebookEdit" else "file_path")
    may = coordinator_may if kind == COORDINATOR else speaker_may
    try:
        if isinstance(tool, str) and isinstance(path, str) and may(path, cwd, env):
            return {}
    except (TypeError, ValueError, OSError):
        pass
    return _answer("deny", SAYS[kind])


#: an agent type in input that does not parse
AGENT = re.compile(rb'"agent_type"\s*:\s*"((?:[^"\\]|\\.)*)"')


def unparsed(raw: bytes) -> dict:
    """Input that does not parse: refused where it names one of the kinds by
    any name, no opinion otherwise."""
    found = AGENT.search(raw)
    if not found:
        return {}
    agent = KINDS.spelled(found.group(1))
    if KINDS.named_any(agent, GUARDED_KINDS):
        return _answer("deny", "the call cannot be read; nothing is written")
    return {}


def main() -> int:
    plugin = KINDS.plugin_name()
    try:
        raw = sys.stdin.buffer.read()
    except (OSError, ValueError):
        raw = b""
    try:
        call = json.loads(raw.decode("utf-8-sig"))
    except (ValueError, RecursionError, MemoryError):
        print(json.dumps(unparsed(raw)))
        return 0
    try:
        decision = decide(call, plugin=plugin)
    except Exception:  # pragma: no cover - a guarded turn fails closed
        agent = call.get("agent_type") if isinstance(call, dict) else None
        decision = _answer("deny", "the call cannot be read; nothing is written") \
            if isinstance(agent, str) and KINDS.named_any(agent, GUARDED_KINDS) else {}
    print(json.dumps(decision))
    return 0


if __name__ == "__main__":
    sys.exit(main())
