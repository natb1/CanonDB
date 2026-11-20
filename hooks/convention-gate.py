#!/usr/bin/env python3
"""The notebook's conventions, held over every text as it leaves.

A PreToolUse hook on the tools by which text leaves a session: the document
connector's writing tools (`update`, `batch`, `create`, in both spellings),
`ArtifactData`, and `Bash` where a command of the line, read by its program
and subcommand, writes text out: `git commit`, `git tag` with a message or an
annotation, `git merge` with a message, `git notes add` or `append`, `gh pr create|edit|comment|review`,
`gh issue create|edit|comment` and `gh release create|edit`. It checks writes
only: every other command passes, `gh api`, `git log`, `git merge-base`, `git
tag -l` and `git cat-file` among them.
It fires for every turn in a project that names a notebook, the main thread
and every helper alike, and runs the checks of `tools/hypo/outgoing.py`
over the words the call would send, against the graph `tools/brief.py
install` copied into the brief's directory (`briefing.py` says where):

- every call: `user-named` (the user is never "the human") and
  `definition-in-glossary` (a fixed term is not defined in running text);
- a connector write addressed to a tab of the notebook (a `ref` to that
  tab's node): `reach`, a fixed term of the tab's project whose sense the
  tab cannot reach; a party's tab is the party's words, and is held to
  neither `user-named` nor `reach`;
- a commit, a tag, a note or a writing `gh` call, bound for a public place: `masked`, a run of the
  user's masked words or a masked tab's address.

On a finding the call is refused, and the reason hands back each finding,
then the entry the text broke and its lineage, whole sentences behind their
ids: the convention arrives when it is needed. A turn the brief's
allow-list keeps blind (`brief-sides.json`: any side but `all`, or none) is
told the checks and the ids, and no sentence of the notebook.

The words read: for the connector, every string of the call but its ids
(the payload, a batch's members, a document created); for `ArtifactData`, a
writing action's `data` or `new_str`, a batch's `writes`' `data`, and each local JSON file
named by `file_path`, read whole; for `Bash`, the whole command (a message
given by `-m` or in a here-document is in it) and each file `-F`, `--file`
or `--body-file` names. What is staged in a commit is not read.

Fail closed only on a confirmed finding. Where the project names no
notebook, or the call is not one of these, there is no opinion. Where the
brief's directory holds no graph, or the call cannot be read, the call goes
unchecked, and where it had words to check the caller is told so in one
line, as context. A finding is a match of the checks' forms, never a
reading; what they do not catch is read, as the notebook's checks leave it.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shlex
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

CONNECTOR = tuple(p + v for p in ("mcp__claude_ai_Claude_Docs__", "mcp__Claude_Docs__")
                  for v in ("update", "batch", "create"))
STORE = "ArtifactData"
SHELL = "Bash"
#: the store's actions that write
WRITING = ("set", "update", "str_replace", "batch")
#: the commands that write text out, by program and subcommand: a commit, an
#: annotated tag, a note, and the `gh` subcommands that write words; every
#: other command passes, a read among them
GH_WRITES = {"pr": ("create", "edit", "comment", "review"),
             "issue": ("create", "edit", "comment"),
             "release": ("create", "edit")}
#: git's options before its subcommand that take a value of their own
GIT_VALUED = ("-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path",
              "--config-env")
#: the operators that end one command and begin the next
OPERATORS = (";", "&&", "||", "|", "&", "(", ")", ";;", "|&")
#: the options by which `git tag` writes a message
TAG_TEXT = ("-a", "-m", "-F", "-s", "-u", "--annotate", "--message", "--file", "--sign")
#: the options by which `git merge` writes a message of its own
MERGE_TEXT = ("-m", "-F", "--message", "--file")


def commands(command: str) -> list:
    """The simple commands of a shell line, each its words, split at the
    operators; a line that cannot be parsed gives none."""
    try:
        lexer = shlex.shlex(command.replace("\n", " ; "), posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        words = list(lexer)
    except ValueError:
        return []
    out, current = [], []
    for word in words:
        if word in OPERATORS:
            if current:
                out.append(current)
            current = []
        else:
            current.append(word)
    if current:
        out.append(current)
    return out


def _program(words: list) -> list:
    """The words from the program on: leading assignments, `env`, `sudo`,
    `command` and `exec` passed over."""
    i = 0
    while i < len(words) and (re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", words[i])
                              or words[i] in ("env", "sudo", "command", "exec", "time")):
        i += 1
    return words[i:]


def writes_out(command) -> bool:
    """Whether a shell line holds a command that writes text out: `git
    commit`, `git tag` with a message or an annotation, `git merge` with a
    message, `git notes add` or `append`, or a `gh` subcommand of GH_WRITES; read by program and
    subcommand, never by a word anywhere in the line."""
    if not isinstance(command, str):
        return False
    for words in commands(command):
        words = _program(words)
        if not words:
            continue
        name = os.path.basename(words[0])
        rest = words[1:]
        if name == "git":
            i = 0
            while i < len(rest) and rest[i].startswith("-"):
                i += 2 if rest[i] in GIT_VALUED else 1
            if i >= len(rest):
                continue
            sub, args = rest[i], rest[i + 1:]
            if sub == "commit":
                return True
            if sub == "tag" and any(a in TAG_TEXT or a.startswith(("--message=", "--file="))
                                    or re.match(r"^-[a-zA-Z]*[amFs]", a) and not
                                    a.startswith("--") for a in args) \
                    and not any(a in ("-l", "--list", "-d", "--delete", "-v", "--verify")
                                for a in args):
                return True
            if sub == "notes" and args[:1] in (["add"], ["append"]):
                return True
            if sub == "merge" and any(a in MERGE_TEXT or a.startswith(("--message=", "--file="))
                                      or re.match(r"^-[a-zA-Z]*[mF]", a)
                                      and not a.startswith(("--", "-s", "-X")) for a in args):
                return True
        elif name == "gh" and len(rest) >= 2 and rest[1] in GH_WRITES.get(rest[0], ()):
            return True
    return False


#: the options naming a file whose words a command sends
FILE_OPTIONS = ("-F", "--file", "--body-file")
#: a string that is an id, a key or an address, and no words
IDLIKE = re.compile(r"^\S*$")
#: the largest local file read for its words
LARGEST = 1 << 20


def _briefing():
    spec = importlib.util.spec_from_file_location("principal_briefing",
                                                  os.path.join(HERE, "briefing.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def strings(value, skip=("ref", "container", "opId", "op_id", "engine", "ifRev",
                         "answering", "version", "if_version", "verbose")) -> list:
    """Every string of a value that holds words, its ids and keys left out."""
    out = []
    if isinstance(value, str):
        if not IDLIKE.match(value):
            out.append(value)
    elif isinstance(value, dict):
        for key, inner in value.items():
            if key in skip:
                continue
            out += strings(inner, skip)
    elif isinstance(value, list):
        for inner in value:
            out += strings(inner, skip)
    return out


def _file_words(path, cwd) -> str:
    if not isinstance(path, str) or not path or path == "-":
        return ""
    if not os.path.isabs(path) and isinstance(cwd, str):
        path = os.path.join(cwd, path)
    try:
        if os.path.getsize(path) > LARGEST:
            return ""
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def _store_words(given, cwd) -> str:
    action = given.get("action")
    if action not in WRITING:
        return ""
    parts = strings(given.get("data"))
    if isinstance(given.get("new_str"), str):
        parts.append(given["new_str"])
    parts.append(_file_words(given.get("file_path"), cwd))
    for member in given.get("writes") or []:
        if isinstance(member, dict):
            parts += strings(member.get("data"))
            parts.append(_file_words(member.get("file_path"), cwd))
    return "\n\n".join(p for p in parts if p)


def _shell_words(command: str, cwd) -> str:
    parts = [command]
    try:
        words = shlex.split(command, posix=True)
    except ValueError:
        words = []
    for i, word in enumerate(words):
        for option in FILE_OPTIONS:
            if word == option and i + 1 < len(words):
                parts.append(_file_words(words[i + 1], cwd))
            elif word.startswith(option + "="):
                parts.append(_file_words(word[len(option) + 1:], cwd))
        # a short -F bundled behind other flags (-nF FILE) or with its file attached (-FFILE)
        m = re.match(r"^-([a-zA-Z]*)F(.*)$", word)
        if m and not word.startswith("--") and word != "-F":
            if m.group(2):
                parts.append(_file_words(m.group(2), cwd))
            elif i + 1 < len(words):
                parts.append(_file_words(words[i + 1], cwd))
    return "\n\n".join(p for p in parts if p)


def _target(graph, given):
    """The question of the notebook's tab a connector write is addressed to,
    and whether it is a party's: by its ref to the tab's node."""
    refs = []
    if isinstance(given.get("ref"), dict):
        refs.append(given["ref"])
    for member in given.get("batch") or []:
        if isinstance(member, dict) and isinstance(member.get("ref"), dict):
            refs.append(member["ref"])
    by_tab = {q.tab.lower(): q for q in graph.questions}
    for ref in refs:
        rid = ref.get("id")
        if isinstance(rid, str) and ref.get("object") == "node":
            q = by_tab.get(rid.split(".", 1)[0].lower())
            if q is not None:
                return q.id, q.tradition
    return None, False


def _said(words: str) -> dict:
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": words}}


def _deny(reason: str) -> dict:
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                   "permissionDecisionReason": reason}}


def decide(call, env=None, b=None) -> dict:
    env = os.environ if env is None else env
    if not isinstance(call, dict):
        return {}
    tool = call.get("tool_name")
    given = call.get("tool_input")
    if tool not in CONNECTOR + (STORE, SHELL) or not isinstance(given, dict):
        return {}
    cwd = call.get("cwd")
    if tool == SHELL:
        command = given.get("command")
        if not writes_out(command):
            return {}
    elif tool == STORE and given.get("action") not in WRITING:
        return {}
    b = _briefing() if b is None else b
    root, directory = b.where(cwd, env)
    if not root:
        return {}
    graph = b.graph(directory) if directory else None
    if tool == SHELL:
        words, target, party, public = _shell_words(given["command"], cwd), None, False, True
    elif tool == STORE:
        words, target, party, public = _store_words(given, cwd), None, False, False
    else:
        words, public = "\n\n".join(strings(given)), False
        target, party = _target(graph, given) if graph is not None else (None, False)
    if not words.strip():
        return {}
    if graph is None:
        return _said("The convention check had no graph to read (no brief is installed for "
                     "this project), so this text went unchecked.")
    from hypo import outgoing
    found = outgoing.findings(graph, words, target, public, party)
    if not found:
        return {}
    side = b.side_for(call.get("agent_type"), cwd, env)
    made = b.source(directory)
    conventions = [c for c in made.get("conventions") or [] if graph.get(c) is not None]
    return _deny(outgoing.refusal(graph, found, side or "none", conventions))


def _passes(raw: bytes) -> bool:
    """A call no check can bear on, told without loading the tools: a shell
    command that writes nothing public, a read of the store."""
    try:
        call = json.loads(raw.decode("utf-8-sig"))
    except (ValueError, RecursionError, MemoryError):
        return True
    if not isinstance(call, dict) or not isinstance(call.get("tool_input"), dict):
        return True
    given = call["tool_input"]
    if call.get("tool_name") == SHELL:
        return not writes_out(given.get("command"))
    if call.get("tool_name") == STORE:
        return given.get("action") not in WRITING
    return call.get("tool_name") not in CONNECTOR


def main() -> int:
    try:
        raw = sys.stdin.buffer.read()
    except (OSError, ValueError):
        raw = b""
    if _passes(raw):
        print(json.dumps({}))
        return 0
    try:
        b = _briefing()
        decision = decide(b.call(raw), b=b)
    except Exception as exc:  # pragma: no cover - fail open, in one line
        decision = _said("The convention check could not run (%s), so this text went "
                         "unchecked." % type(exc).__name__)
    print(json.dumps(decision))
    return 0


if __name__ == "__main__":
    sys.exit(main())
