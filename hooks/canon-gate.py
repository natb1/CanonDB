#!/usr/bin/env python3
"""The canon agent's read gate: the packet, and nothing else.

A PreToolUse hook on Read, installed by the plugin and so fired on every
Read of every turn in a project that has the plugin. It decides nothing for
any turn but the canon agent's: for those it answers with no opinion, and
the harness's ordinary permissions apply. For the canon agent it is what
keeps the reading to what a clean context carries. The agent's definition
grants it Read and nothing else, and Read is not confined to a path by that
definition, so the gate reads the tool call from stdin and answers with a
permission decision: allow for the packet the principal entry point wrote
for this turn; deny for everything else, canon on disk and the notebook's
tooling included.

The packet is the one file a turn may read: `lineage.md` in a directory
named `packet`, which the plugin's `tools/lineage.py` writes and nothing
else does. It holds canon above the question, which is all of canon the turn
carries. There is no reading past it: what an answer collides with outside
its lineage, on another thread or in the notebook, is found by the entry
point that put the question, which holds both. So nothing lists what counts
as canon on disk, and the gate asks no file.

A refusal is one line, and it names no file: the turn is told it may not
read outside its packet, not what it would have found.
"""

from __future__ import annotations

import json
import os
import sys

#: the agent this gate guards; a plugin's namespace may stand in front of it
AGENT = "canon-answer"

#: the one file: <anything>/packet/lineage.md
PACKET_DIR = "packet"
PACKET_FILE = "lineage.md"

REFUSED = ("a canon turn reads the packet it was handed, which holds canon "
           "above its question, and nothing else")


def guarded(call: dict) -> bool:
    """Whether the turn making the call is the canon agent's."""
    agent = str(call.get("agent_type") or "")
    return agent == AGENT or agent.endswith(":" + AGENT)


def resolve(path: str, root: str) -> str:
    """Where a path lands: a relative one is read from the checkout the turn
    runs in, never from wherever this hook happens to be run."""
    return os.path.realpath(os.path.join(root, path))


def is_packet(path: str, root: str) -> bool:
    head, name = os.path.split(resolve(path, root))
    return name == PACKET_FILE and os.path.basename(head) == PACKET_DIR


def decide(call: dict) -> dict:
    """The permission decision for one tool call, as the hook's JSON output.
    An empty object is no decision, which is what every turn but the canon
    agent's gets."""
    if not guarded(call):
        return {}
    root = call.get("cwd") or os.getcwd()
    tool = call.get("tool_name", "")
    path = str((call.get("tool_input") or {}).get("file_path", ""))
    if tool == "Read" and path and is_packet(path, root):
        decision, reason = "allow", "the packet"
    else:
        decision, reason = "deny", REFUSED
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                   "permissionDecision": decision,
                                   "permissionDecisionReason": reason}}


def main() -> int:
    try:
        call = json.load(sys.stdin)
    except ValueError:
        call = {}
    print(json.dumps(decide(call)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
