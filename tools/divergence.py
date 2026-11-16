#!/usr/bin/env python3
"""divergence.py list <graph.json> [--project NAME] | note --data … --action … --whose user|ai --price … — data that contradicts a principle, tracked.

``list`` prints every divergence note the graph holds, with what each
leaves untracked. ``note`` prints the words of a note from its parts, to
hand to ``inplace.py note insert`` on the tab of the principle; a dictation
writes the note and takes no action.
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hypo import cli, divergence  # noqa: E402

cli.quiet_pipe()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="mode", required=True)
    p = sub.add_parser("list")
    p.add_argument("graph")
    p.add_argument("--project", metavar="NAME")
    p = sub.add_parser("note")
    p.add_argument("--data", required=True)
    p.add_argument("--action", required=True)
    p.add_argument("--whose", required=True, choices=divergence.WHOSE)
    p.add_argument("--price", required=True)
    p.add_argument("--budget", default="none", choices=divergence.BUDGET)
    p.add_argument("--read", nargs=2, action="append", metavar=("DATE", "READING"), default=[])
    args = ap.parse_args(argv)
    if args.mode == "note":
        print(divergence.compose(args.data, args.action, args.whose, args.price,
                                 args.budget, [tuple(r) for r in args.read]))
        return 0
    graph = cli.load_graph(args.graph)
    if graph is None:
        return 1
    found = divergence.found(graph, args.project)
    for d in found:
        gap = ("  UNTRACKED: no %s" % ", ".join(d.missing)) if d.missing else ""
        print("%s  %s · action: %s · whose: %s · price: %s · budget: %s%s"
              % (d.question, d.data, d.action or "?", d.whose or "?", d.price or "?",
                 d.budget, gap))
    print("%d divergence(s)" % len(found), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
