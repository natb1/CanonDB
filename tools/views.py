#!/usr/bin/env python3
"""views.py <transcript.jsonl> <out dir> [--names FILE | --doc FILE | --list-only] — the whole-tab reads in a helper's transcript, one file each.

Each ``view`` of a node the transcript holds is written as ``<node id>.json``
under the out dir, and each read of a project's tab list as
``doc-<project id>.json``, the project id being the trailing id of what the
read was handed: the last read of each, a read continued from a cursor
joined to the one it continues (``hypo/views.py`` says how). A tab list is
saved in the shape ``read.py`` takes as its document read, with what the
tool's result held under ``data`` lifted to the top, so the file is handed
to ``read.py`` as it stands; a view is saved as the tool's whole result,
which is what ``page.py`` takes.

With ``--list-only``, only the tab lists are written. With ``--names``, a
tab-separated file whose second column is a name and fifth a node id, a
node's file is ``<name>.json`` instead, which is what ``page.py`` takes.
With ``--doc``, a tab list this saved (the shape ``read.py`` takes), the
name is that of the tab the node is the body of, read as ``read.py`` reads
it, and no tab list is written: the out dir then holds the tabs and nothing
else, so ``page.py <out dir>/*.json`` takes every file in it. The three are
not given together. Prints one line: how many were saved, and their names.

A node whose last piece is not complete, or whose pieces do not join, is
refused by name, any file of its name in the out dir is removed, and the
run exits 1; what was whole is still written. A name that is not a plain
file name (letters, digits, ``.``, ``_`` and ``-``, opening with a letter
or a digit) is refused by name before anything is written, and then
nothing is.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hypo import cli, views  # noqa: E402

cli.quiet_pipe()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("transcript", help="a helper's transcript, one JSON message a line")
    ap.add_argument("out", help="where the files go")
    given = ap.add_mutually_exclusive_group()
    given.add_argument("--names", metavar="FILE",
                       help="tab-separated: a name in the second column, a node id in the fifth")
    given.add_argument("--doc", metavar="FILE",
                       help="a tab list this saved, which names each body; no tab list "
                            "is written")
    given.add_argument("--list-only", action="store_true", dest="list_only",
                       help="write the tab lists and nothing else")
    args = ap.parse_args(argv)
    called = {}
    try:
        if args.names:
            called = views.names(args.names)
        elif args.doc:
            with open(args.doc, encoding="utf-8") as fh:
                saved = json.load(fh)
            called = views.doc_names(saved if isinstance(saved, dict) else {})
            if not called:
                print("ERROR doc: %s names no tab's body" % args.doc, file=sys.stderr)
                return 1
    except (OSError, ValueError) as exc:
        print("ERROR %s: %s" % ("names" if args.names else "doc", exc), file=sys.stderr)
        return 1
    try:
        with open(args.transcript, encoding="utf-8") as fh:
            lifted = views.lift(fh)
    except (OSError, ValueError) as exc:
        print("ERROR transcript: %s" % exc, file=sys.stderr)
        return 1

    def name(key):
        # a name given is a node's; a tab list keeps its own
        return called.get(key[1], key[1]) if key[0] == "node" else views.name_of(key)

    def kept(key):
        # a run handed the tab list writes the tabs alone; --list-only the reverse
        if args.list_only:
            return key[0] == "project"
        return not (args.doc and key[0] == "project")

    every = sorted(k for k in set(lifted.saved) | set(lifted.refused) if kept(k))
    bad = sorted({name(k) for k in every if views.bad_name(name(k))})
    if bad:
        for wrong in bad:
            print("ERROR %r: not a file name; nothing was written" % wrong, file=sys.stderr)
        return 1
    by_name = {}
    for key in every:
        by_name.setdefault(name(key), []).append(key)
    errors = [e for k, e in zip(lifted.refused, lifted.errors) if kept(k)]
    named, refused = {}, {name(k) for k in lifted.refused if kept(k)}
    for each, keys in by_name.items():
        if len(keys) > 1:
            # one file cannot hold two tabs, and neither is the one meant
            errors.extend("%s: the name %s is given to %s as well"
                          % (views.name_of(k), each,
                             ", ".join(views.name_of(o) for o in keys if o != k))
                          for k in keys)
            refused.add(each)
        elif keys[0] in lifted.saved:
            named[each] = keys[0]
    for error in errors:
        print("ERROR %s" % error, file=sys.stderr)
    os.makedirs(args.out, exist_ok=True)
    for each in sorted(refused):
        # a file of a refused name is an earlier run's, and not this tab now
        path = os.path.join(args.out, each + ".json")
        if os.path.lexists(path):
            os.unlink(path)
    for each, key in named.items():
        with open(os.path.join(args.out, each + ".json"), "w", encoding="utf-8") as fh:
            json.dump(lifted.saved[key], fh, ensure_ascii=False)
    print("%d saved%s" % (len(named), ": " + " ".join(sorted(named)) if named else ""))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
