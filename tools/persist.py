#!/usr/bin/env python3
"""Persist a harness session's logs to the notebook's transcript directory.

Usage: persist.py [--session-id ID] [--source DIR] [--dest DIR] [--dry-run]

The notebook's theses cite the session that produced them ("this design session, claude.ai/code,
session_..."). This copies that session's log, and every subagent log the harness wrote under it, into
`transcripts/` at the project's root, and records what it copied in `transcripts/index.json` with sha256
hashes so a citation can be resolved and a copy can be checked.

The session is resolved by id -- --session-id, else $CLAUDE_CODE_SESSION_ID, else the single log under
the source directory; with several candidates and no id the script stops and lists them. It never
guesses by file size, because the largest log is not reliably the live one.

Idempotent: a second run over unchanged logs rewrites the same bytes and reports "unchanged". A log
that grew is re-copied and its hash replaced; the entry keeps its first-seen timestamp.

This is a cache of the harness's own files, not a source. The artifact remains the source of truth for
the notebook's content; these logs are only what the notebook's provenance lines point at.
"""
import argparse
import datetime
import hashlib
import json
import os
import shutil
import sys

#: the project the session ran in: the harness's, else the working directory
PROJECT = os.path.realpath(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
#: where the harness keeps that project's logs: the path with its separators
#: turned to dashes, under ~/.claude/projects
DEFAULT_SOURCE = os.path.expanduser(os.path.join("~", ".claude", "projects",
                                                 PROJECT.replace(os.sep, "-")))
#: the transcripts live with the project whose notebook cites them, not with the plugin
DEFAULT_DEST = os.path.join(PROJECT, "transcripts")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def count_turns(path):
    """Author turns in a .jsonl log: records whose type is 'user' and whose message is not a tool result."""
    n = 0
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if rec.get("type") != "user":
                continue
            content = (rec.get("message") or {}).get("content")
            if isinstance(content, list) and any(
                isinstance(b, dict) and b.get("type") == "tool_result" for b in content
            ):
                continue
            n += 1
    return n


def walk_side_files(root):
    """(relative path, absolute path) for every log and meta file the harness wrote beside a session.

    The harness nests subagent logs (today under <session>/subagents/), so this walks rather than
    listing one level, and keeps the relative path so the copy mirrors the layout it found.
    """
    if not os.path.isdir(root):
        return
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            if not (name.endswith(".jsonl") or name.endswith(".meta.json")):
                continue
            src = os.path.join(dirpath, name)
            yield os.path.relpath(src, root), src


def resolve(source, session_id):
    if session_id:
        path = os.path.join(source, session_id + ".jsonl")
        if not os.path.exists(path):
            sys.exit("no log for session %s under %s" % (session_id, source))
        return session_id, path
    env = os.environ.get("CLAUDE_CODE_SESSION_ID")
    if env:
        return resolve(source, env)
    logs = sorted(f for f in os.listdir(source) if f.endswith(".jsonl"))
    if len(logs) == 1:
        return logs[0][:-6], os.path.join(source, logs[0])
    sys.exit(
        "cannot resolve the session: pass --session-id. candidates under %s:\n  %s"
        % (source, "\n  ".join(logs) or "(none)")
    )


def copy_if_changed(src, dst, dry_run):
    """Return 'created', 'updated' or 'unchanged'."""
    digest = sha256(src)
    if os.path.exists(dst) and sha256(dst) == digest:
        return "unchanged", digest
    state = "updated" if os.path.exists(dst) else "created"
    if not dry_run:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
    return state, digest


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--session-id")
    ap.add_argument("--source", default=DEFAULT_SOURCE)
    ap.add_argument("--dest", default=DEFAULT_DEST)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not os.path.isdir(args.source):
        sys.exit("no such source directory: %s" % args.source)

    sid, log = resolve(args.source, args.session_id)
    dest = os.path.abspath(args.dest)
    index_path = os.path.join(dest, "index.json")
    index = {"sessions": {}}
    if os.path.exists(index_path):
        with open(index_path) as fh:
            index = json.load(fh)
    index.setdefault("sessions", {})

    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    entry = index["sessions"].get(sid, {"first_seen": now})
    entry["updated"] = now

    state, digest = copy_if_changed(log, os.path.join(dest, sid + ".jsonl"), args.dry_run)
    entry["log"] = {
        "file": sid + ".jsonl",
        "sha256": digest,
        "bytes": os.path.getsize(log),
        "author_turns": count_turns(log),
    }
    states = {state: 1}

    agents = {}
    for rel, src in sorted(walk_side_files(os.path.join(args.source, sid))):
        st, dg = copy_if_changed(src, os.path.join(dest, sid + "-agents", rel), args.dry_run)
        states[st] = states.get(st, 0) + 1
        agents[rel] = {"sha256": dg, "bytes": os.path.getsize(src)}
    entry["agents"] = agents

    index["sessions"][sid] = entry
    if not args.dry_run:
        os.makedirs(dest, exist_ok=True)
        with open(index_path, "w") as fh:
            json.dump(index, fh, indent=2, sort_keys=True)
            fh.write("\n")

    total = entry["log"]["bytes"] + sum(a["bytes"] for a in agents.values())
    print(
        "%s: %d files (%s), %d author turns, %.1f MiB%s"
        % (
            sid,
            1 + len(agents),
            ", ".join("%d %s" % (v, k) for k, v in sorted(states.items())),
            entry["log"]["author_turns"],
            total / (1 << 20),
            " [dry run]" if args.dry_run else "",
        )
    )


if __name__ == "__main__":
    main()
