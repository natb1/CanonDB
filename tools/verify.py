#!/usr/bin/env python3
"""verify.py <graph.json> <tabs dir> [--only ID] — the page against the renderer.

Reads the exported tabs — one `<question id>.md` per tab — and reports, per tab,
the body that is not what the renderer would produce, the links the sidecar
names that the page does not carry, the links standing where the encoding
does not put that kind, the links leading to a tab other than the one they
name, and the links the page carries that the sidecar does not name.

This is the closing gate of a write. Every other check reads the graph file,
and a graph file never held a link, so nothing else can see whether the links
reached the page. Exits 1 on any finding — a tab with no export to read
included, since a tab this could not read is a tab this did not verify.
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hypo import cli, verify as check  # noqa: E402

cli.quiet_pipe()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("graph", help="the graph file")
    ap.add_argument("tabs", help="a directory of <question id>.md exports")
    ap.add_argument("--only", action="append", metavar="ID",
                    help="verify only this question (repeatable)")
    args = ap.parse_args(argv)

    graph = cli.load_graph(args.graph)
    if graph is None:
        return 1

    try:
        found = cli.exports(args.tabs)
    except OSError as exc:
        print("ERROR tabs: %s" % exc, file=sys.stderr)
        return 1
    if not found:
        print("ERROR no .md exports in %s" % args.tabs, file=sys.stderr)
        return 1
    if args.only:  # everything not named is absent on purpose; the named is owed
        wanted = set(args.only)
        unknown = sorted(wanted - {q.id for q in graph.questions})
        if unknown:
            print("no question %s in %s" % (", ".join(unknown), os.path.basename(args.graph)),
                  file=sys.stderr)
            return 1
        found = {qid: page for qid, page in found.items() if qid in wanted}
        absent = sorted(qid for qid in wanted if qid not in found)
    else:
        absent = [q.id for q in graph.questions if q.id not in found]

    reports = check.verify_all(graph, found)
    bad = [report for report in reports if not report.ok()]
    for report in bad:
        for line in report.lines():
            print(line)
    if absent:  # a finding: a green exit over it would pass what was never read
        print("no export on disk for: %s" % ", ".join(absent))
    print("%d of %d tabs differ, %d link(s) missing, %d out of place, "
          "%d astray, %d unaccounted"
          % (len(bad), len(reports),
             sum(len(r.missing) for r in reports),
             sum(len(r.misplaced) for r in reports),
             sum(len(r.astray) for r in reports),
             sum(len(r.extra) for r in reports)))
    return 1 if (bad or absent) else 0


if __name__ == "__main__":
    sys.exit(main())
