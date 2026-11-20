#!/usr/bin/env python3
"""residue.py list <graph.json> [--project NAME] [--json] [--by-share] | note --words … --kind K --whose user|ai --from … --returns … — what a line leaves open, tracked.

``list`` prints every open note the graph holds, with its tab, its kind,
whose move it is, what brings it back, what raised it, what it leaves
untracked and any part it holds that cannot be placed; the last line is the
count, by kind and by whose move, which is reported and not driven to
nothing. With ``--json`` the count is the object's ``count`` field instead.
``--by-share`` orders the notes by the share of the root their tab carries,
heaviest first, as ``shares.py`` computes it. A share is right only over
the whole graph: every tab of the notebook, read as one. Over a graph built
from some tabs and their ancestors, a share that holds the root is still
wrong, since what the tabs left out carry is missing from every sum, and
nothing in such a graph shows it unless it was built with ``read.py
--scope``; so run it only over the graph of a whole-notebook read. A graph
built with ``--scope`` is read as rootless, and so is one where the
author's top-level questions (each project's entries that nothing raises)
are not exactly one, or the one there is not the first project's; stderr
then says that shares cannot be read without the root, and the notes are
listed in tab order with no share. ``note`` prints the words of a note from
its parts, to hand to ``inplace.py note insert`` on the tab it bears on, and
refuses a part holding the separator or a line break and a date that is not
YYYY-MM-DD; ``inplace.py note delete`` takes it off once what it held
stands on the tab.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hypo import cli, project, residue, share  # noqa: E402

cli.quiet_pipe()


def _note(args) -> int:
    for name, value in (("words", args.words), ("from", args.raised),
                        ("returns", args.returns)):
        if not value.strip():
            print("REFUSED an open note names its %s" % name, file=sys.stderr)
            return 1
    try:
        words = residue.compose(args.words, args.kind, args.whose, args.raised,
                                args.returns, args.case, [tuple(r) for r in args.read])
    except ValueError as exc:
        print("REFUSED %s" % exc, file=sys.stderr)
        return 1
    print(words)
    return 0


def rootless(graph) -> bool:
    """Whether the graph lacks the author's one root: its top-level author
    questions (every project's entries that nothing raises) are not exactly
    one, or the one is not the first project's, the project the notebook
    names first and whose entry is the root."""
    ins = project.in_edges(graph)
    by_id = graph.by_id()
    tops = [qid for found in project.candidates(graph).values() for qid in found
            if not ins.get(qid)]
    if graph.partial:
        # a scoped read holds some tabs; its shares leave out the rest
        return True
    if len(tops) != 1:
        return True
    return bool(graph.projects) and by_id[tops[0]].project != graph.projects[0]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="mode", required=True)
    p = sub.add_parser("list")
    p.add_argument("graph")
    p.add_argument("--project", metavar="NAME")
    p.add_argument("--json", action="store_true", dest="as_json",
                   help="print the notes and the count as one JSON object; the count "
                        "is its count field, not a last line")
    p.add_argument("--by-share", action="store_true", dest="by_share",
                   help="heaviest share of the root first; right only over the graph of "
                        "the whole notebook, and refused over a scoped one")
    p = sub.add_parser("note")
    p.add_argument("--words", required=True)
    p.add_argument("--kind", required=True, choices=residue.KIND)
    p.add_argument("--whose", required=True, choices=residue.WHOSE)
    p.add_argument("--from", required=True, dest="raised")
    p.add_argument("--returns", required=True)
    p.add_argument("--case", default="")
    p.add_argument("--read", nargs=2, action="append", metavar=("DATE", "READING"), default=[])
    args = ap.parse_args(argv)
    if args.mode == "note":
        return _note(args)
    graph = cli.load_graph(args.graph)
    if graph is None:
        return 1
    found = residue.found(graph, args.project)
    carried = None
    if args.by_share:
        # a scoped graph's top question carries one whatever it is, of
        # whatever kind; a share is the root's only where the root is there
        if rootless(graph):
            print("shares cannot be read without the root, and this graph does not "
                  "hold it; listed in tab order, with no share", file=sys.stderr)
        else:
            carried = share.shares(graph)
            found = sorted(found, key=lambda o: -carried.get(o.question, 0.0))
    if args.as_json:
        rows = [dict(o._asdict(), readings=[list(r) for r in o.readings],
                     missing=list(o.missing), strays=list(o.strays)) for o in found]
        if carried is not None:
            for row in rows:
                row["share"] = carried.get(row["question"], 0.0)
        print(json.dumps({"open": rows, "count": residue.count(found)},
                         ensure_ascii=False, indent=2))
        return 0
    for o in found:
        gap = ("  UNTRACKED: no %s" % ", ".join(o.missing)) if o.missing else ""
        gap += ("  STRAY: %s" % "; ".join(o.strays)) if o.strays else ""
        weight = ("  share %.4f" % carried.get(o.question, 0.0)) if carried is not None else ""
        print("%s  %s · kind: %s · whose: %s · returns: %s · from: %s%s%s"
              % (o.question, o.words, o.kind or "?", o.whose or "?", o.returns or "?",
                 o.raised or "?", weight, gap))
    print(residue.count(found))
    return 0


if __name__ == "__main__":
    sys.exit(main())
