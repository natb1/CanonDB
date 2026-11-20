#!/usr/bin/env python3
"""inhand.py add|done|list|export|seed DIR … — the work in hand of a session, kept on disk.

    inhand.py add DIR WORDS [--at T] [--schedule]  add an entry; prints its id
    inhand.py done DIR ID                          take an entry off
    inhand.py list DIR                             print the list
    inhand.py export DIR [--at T] [--if-version N] print the write of ordo/session
    inhand.py seed DIR FILE [--at T]               take a stored ordo/session back

Every mode takes `--session ID`, the session's id, which defaults to
`$CLAUDE_CODE_SESSION_ID`, the id the harness gives the session's shell and
its hooks alike; `--at` defaults to the clock, in UTC.

DIR is the speaker's directory of the sitting's scratch, `$SCRATCH/speaker`,
and the list is `DIR/inhand.json`. An entry is in hand (`w<n>`: a helper
started and not yet reported, a job awaited, an act begun) or, with
`--schedule`, on the session's own schedule (`s<n>`: a bell tick, a time to
come back). Each writing mode also records the list's path in the brief's
directory (`brief.py where`) under the session's id, where the harness's
hooks find that session's list before and after a compaction and never
another's; where there is no project to brief, or no session's id, it says
so and the list is kept all the same. `list` prints the entries with their
ages, and the helpers the hooks recorded as started and not yet ended. `export` prints the one write that keeps the
list in the page's store, `{"op": "set", "collection": "ordo", "doc_id":
"session", "data": {at, in_hand, schedule}}`, for `ArtifactData`; `seed`
reads such a document back (as `get` saves it) so that a new session sets
its schedule again. Exit 1 on a refusal.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hypo import brief, cli, inhand  # noqa: E402

cli.quiet_pipe()


def _brief_dir():
    root = brief.project_root(os.getcwd(), os.environ)
    if not root:
        return None, "no project to brief here"
    try:
        return brief.brief_dir(root, os.environ), ""
    except brief.Refused as exc:
        return None, exc.args[0][0]


def _register(directory: str, session) -> None:
    where, why = _brief_dir()
    path = inhand.pointer(where, session) if where else None
    if not path:
        print("the list is kept, and no hook will find it: %s"
              % (why or "the session's id is not known (--session)"), file=sys.stderr)
        return
    inhand._private(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(os.path.realpath(inhand.path_of(directory)) + "\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="mode", required=True)
    p = sub.add_parser("add")
    p.add_argument("dir")
    p.add_argument("words")
    p.add_argument("--at")
    p.add_argument("--schedule", action="store_true")
    p = sub.add_parser("done")
    p.add_argument("dir")
    p.add_argument("id")
    p = sub.add_parser("list")
    p.add_argument("dir")
    p = sub.add_parser("export")
    p.add_argument("dir")
    p.add_argument("--at")
    p.add_argument("--if-version", type=int)
    p = sub.add_parser("seed")
    p.add_argument("dir")
    p.add_argument("file")
    p.add_argument("--at")
    for sp in sub.choices.values():
        sp.add_argument("--session", default=os.environ.get("CLAUDE_CODE_SESSION_ID"))
    args = ap.parse_args(argv)
    if hasattr(args, "at") and not args.at:
        args.at = inhand.now()
    if not os.path.isabs(args.dir):
        print("REFUSED: the directory is named by an absolute path", file=sys.stderr)
        return 1
    try:
        data = inhand.load(args.dir)
        if args.mode == "list":
            where, _ = _brief_dir()
            sys.stdout.write(inhand.listing(data, inhand.path_of(args.dir), args.session or "",
                                            inhand.launches(where, args.session) if where
                                            else None))
            return 0
        if args.mode == "export":
            print(json.dumps(inhand.export(data, args.at, args.if_version), sort_keys=True))
            return 0
        if args.mode == "add":
            print(inhand.add(data, args.words, args.at, args.schedule))
        elif args.mode == "done":
            print("done: %s" % inhand.done(data, args.id)["id"])
        else:
            with open(args.file, encoding="utf-8") as fh:
                stored = json.load(fh)
            if not isinstance(stored, dict):
                raise inhand.Refused("%s is not a stored ordo/session" % args.file)
            added = inhand.seed(data, stored, args.at)
            print("%d entry(ies) taken back%s" % (len(added),
                                                 ": " + " ".join(added) if added else ""))
        inhand.save(args.dir, data)
        _register(args.dir, args.session)
    except (inhand.Refused, ValueError, OSError) as exc:
        print("REFUSED: %s" % exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
