#!/usr/bin/env python3
"""The clean reader's read gate: the question it was handed, and nothing else.

A PreToolUse hook on Read, installed by the plugin and so fired on every
Read of every turn in a project that has the plugin. It decides nothing for
any turn but the clean reader's: for those it answers with no opinion, and
the harness's ordinary permissions apply. For the clean reader it is what
keeps a reader whose answer is the whole of a fidelity test from the
sitting's other files: the principal's answers, the sealed replies and
their grades, the rows files, the results, and the transcripts. The
reader's definition grants it Read to take the question's file, and Read is
not confined to a path by that definition, so this gate is, as
`canon-gate.py` is for the canon agent.

The one place a clean reader may read: a file whose parent directory is
named `questions`, with no directory on its path named `answers`,
`replies`, `results`, `sealed`, `rows`, `check` or `coordinator`, its links
resolved, held as `kinds.py` holds a path (outside the project, the
plugin's root and `~/.claude`, a session's `~/.claude/jobs/<id>/tmp` aside),
and below a scratch root the gates recognise (`/tmp/claude-*/…/scratchpad/`
or `~/.claude/jobs/<id>/tmp/`): the sitting's scratch, where the entry point
writes each question. Such a file is admitted with an allow. A file of that
shape that is not below a recognised scratch root gets no opinion, never an
allow, and the harness's ordinary permissions apply to it; every other read
is refused. The project is found
as every gate of the plugin finds it: `CLAUDE_PROJECT_DIR`, the cwd, and the
nearest ancestor of the cwd that holds `.principal` or `.git`. Which
question it was handed is not known here, so a reader could open another
question of the same sitting; a question holds no answer, and that is the
residue. A sitting's scratch therefore has no directory of those five names
on its own path, as the sitting's entry point says.

Which turn is the clean reader: `kinds.py`, which every gate of this plugin
shares. By this plugin's name in front of it always; by its bare name in a
project whose own definition is byte for byte the plugin's, or that names a
notebook (a differing copy there is confined all the same); and where
the plugin's manifest cannot be read, by any name ending `:clean-reader`.

A guarded turn fails closed: a call the gate cannot make sense of is
refused, input that does not parse among them where it names the clean
reader by any name. A refusal is one line and names no file.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
AGENTS = os.path.join(os.path.dirname(HERE), "agents")


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

#: the agent this gate guards
AGENT = "clean-reader"

#: the directory a question stands in, and those no path may pass through
QUESTIONS = "questions"
FORBIDDEN = ("answers", "replies", "results", "sealed", "rows", "check", "coordinator")

REFUSED = ("a clean reader reads the question file it was handed, in the "
           "sitting's questions directory, and the notebook, and nothing else")


def guarded(call: dict, env, plugin: str, own: str = AGENTS) -> bool:
    """Whether the turn making the call is the clean reader's."""
    return KINDS.kind_of(call.get("agent_type"), (AGENT,), plugin, call.get("cwd"),
                         env, own) == AGENT


def is_question(path: str, cwd, env) -> str:
    """Whether a path is a question file: its parent named `questions`,
    through no forbidden directory, held outside the project, the plugin's
    root and `~/.claude`. "scratch" where it stands below a recognised
    scratch root, "elsewhere" where not, '' where it is no question."""
    if isinstance(cwd, str) and cwd and not os.path.isabs(path):
        path = os.path.join(cwd, path)
    where = KINDS.held(path, cwd, env)
    if not where:
        return ""
    parts = where.split(os.sep)
    if len(parts) < 3 or parts[-2] != QUESTIONS or not parts[-1]:
        return ""
    if any(p in FORBIDDEN for p in parts[:-1]):
        return ""
    return "scratch" if KINDS.under(where, QUESTIONS, env) else "elsewhere"


def _answer(decision: str, reason: str) -> dict:
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                   "permissionDecision": decision,
                                   "permissionDecisionReason": reason}}


def decide(call, env=None, plugin=None, own: str = AGENTS) -> dict:
    """The permission decision for one tool call, as the hook's JSON output.
    An empty object is no decision, which is what every turn but the clean
    reader's gets."""
    if not isinstance(call, dict):
        return {}
    env = os.environ if env is None else env
    plugin = KINDS.plugin_name() if plugin is None else plugin
    if not guarded(call, env, plugin, own):
        return {}
    tool = call.get("tool_name", "")
    tool_input = call.get("tool_input")
    path = tool_input.get("file_path", "") if isinstance(tool_input, dict) else ""
    try:
        admitted = tool == "Read" and isinstance(path, str) and bool(path) \
            and is_question(path, call.get("cwd"), env)
    except (TypeError, ValueError, OSError):  # a path the system cannot resolve is no question
        admitted = ""
    if admitted == "scratch":
        return _answer("allow", "the question")
    if admitted == "elsewhere":
        return {}
    return _answer("deny", REFUSED)


#: an agent type in input that does not parse
NAMED = re.compile(rb'"agent_type"\s*:\s*"((?:[^"\\]|\\.)*)"')


def unparsed(raw: bytes) -> dict:
    """Input that does not parse: refused where it names the clean reader by
    any name, no opinion otherwise."""
    found = NAMED.search(raw)
    if not found:
        return {}
    agent = KINDS.spelled(found.group(1))
    return _answer("deny", REFUSED) if KINDS.named_any(agent, (AGENT,)) else {}


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
        decision = _answer("deny", REFUSED) \
            if isinstance(agent, str) and KINDS.named_any(agent, (AGENT,)) else {}
    print(json.dumps(decision))
    return 0


if __name__ == "__main__":
    sys.exit(main())
