#!/usr/bin/env python3
"""The canon agent's read gate: canon above the question, the packet, nothing else.

A PreToolUse hook on Read, installed by the plugin and so fired on every
Read of every turn in a project that has the plugin. It decides nothing for
any turn but the canon agent's: for those it answers with no opinion, and
the harness's ordinary permissions apply. For the canon agent it is what
keeps the reading to what a clean context carries. The agent's definition
grants it Read and nothing else, and Read is not confined to a path by that
definition, so the gate reads the tool call from stdin and answers with a
permission decision: allow for a path the project counts as canon, or for
the packet the principal entry point wrote for this turn; deny for
everything else, the notebook's tooling included.

What counts as canon on disk is the project's to say, in one place, and it
is short: `.principal/canon` at the project root lists the paths, one per
line, relative to that root. It grows when an answer is promulgated, and
the list is changed then and nowhere else. The packet is the one file
outside the checkout a turn may read: `lineage.md` in a directory named
`packet`, which the plugin's `tools/lineage.py` writes and nothing else does.

A refusal is one line, and it names no file: the turn is told it may not
read outside canon, not what it would have found.
"""

from __future__ import annotations

import json
import os
import sys

#: the agent this gate guards; a plugin's namespace may stand in front of it
AGENT = "canon-answer"

#: the project's list of canon on disk, one path per line relative to the root
CANON_LIST = os.path.join(".principal", "canon")

#: the one file outside the checkout: <anything>/packet/lineage.md
PACKET_DIR = "packet"
PACKET_FILE = "lineage.md"

REFUSED = ("a canon turn reads canon above its question and the packet it "
           "was handed, and nothing else")


def guarded(call: dict) -> bool:
    """Whether the turn making the call is the canon agent's."""
    agent = str(call.get("agent_type") or "")
    return agent == AGENT or agent.endswith(":" + AGENT)


def canon(root: str) -> list:
    """The paths the project lists as canon, relative to its root."""
    try:
        with open(os.path.join(root, CANON_LIST), encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return []
    paths = []
    for line in lines:
        line = line.strip()
        if line and not line.startswith("#"):
            paths.append(line)
    return paths


def resolve(path: str, root: str) -> str:
    """Where a path lands: a relative one is read from the checkout the turn
    runs in, never from wherever this hook happens to be run."""
    return os.path.realpath(os.path.join(root, path))


def is_canon(path: str, root: str) -> bool:
    real = resolve(path, root)
    return any(real == resolve(rel, root) for rel in canon(root))


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
    if tool == "Read" and path and (is_canon(path, root) or is_packet(path, root)):
        decision, reason = "allow", "canon, or the packet"
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
