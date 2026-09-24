#!/usr/bin/env python3
"""The canon agent's read gate: canon above the question, the packet, nothing else.

A PreToolUse hook on the canon agent's Read tool. The agent's definition
grants it Read and nothing else, and Read is not confined to a path by that
definition, so this is what keeps its reading to what a clean context
carries. It reads the tool call from stdin and answers with a permission
decision: allow for a path this notebook counts as canon, or for the packet
the principal entry point wrote for this turn; deny for everything else, the
committed envelope at the branch root and the notebook's tooling included.

What counts as canon on disk is listed here, in one place, and is short:
the root question at the branch root. It grows when an answer is promulgated,
and the list is changed then and nowhere else. The packet is the one file
outside the checkout a turn may read: `lineage.md` in a directory named
`packet`, which `hypomnemata/tools/lineage.py` writes and nothing else does.

A refusal is one line, and it names no file: the turn is told it may not
read outside canon, not what it would have found.
"""

from __future__ import annotations

import json
import os
import sys

#: paths under the checkout that are canon, relative to its root
CANON = ("ti-esti.md",)

#: the one file outside the checkout: <anything>/packet/lineage.md
PACKET_DIR = "packet"
PACKET_FILE = "lineage.md"

REFUSED = ("a canon turn reads canon above its question and the packet it "
           "was handed, and nothing else")


def resolve(path: str, root: str) -> str:
    """Where a path lands: a relative one is read from the checkout the turn
    runs in, never from wherever this hook happens to be run."""
    return os.path.realpath(os.path.join(root, path))


def is_canon(path: str, root: str) -> bool:
    real = resolve(path, root)
    return any(real == resolve(rel, root) for rel in CANON)


def is_packet(path: str, root: str) -> bool:
    head, name = os.path.split(resolve(path, root))
    return name == PACKET_FILE and os.path.basename(head) == PACKET_DIR


def decide(call: dict) -> dict:
    """The permission decision for one tool call, as the hook's JSON output."""
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
