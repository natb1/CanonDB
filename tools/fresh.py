#!/usr/bin/env python3
"""fresh.py <graph.json> <reads>... — has any tab moved since the graph was read?

The graph records, per question, the rev its tab answered with when it was
read (`page.py` writes it beside each spelled read, and `read.py` keeps it).
Before a run's first write, and again before its links, read each tab in scope
with `{"kind":"view","sinceRev":<that rev>}`, save the reads as
`<question>.json`, and run this. A read that shows any block that changed is a
tab another session (or the principal's hand) moved: the run reads it again,
rebuilds and re-plans, and never writes over it. Exits 1 naming each moved
tab, and each question the graph holds no rev for.
"""

from __future__ import annotations

import argparse
import os
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hypo import cli, page  # noqa: E402

cli.quiet_pipe()


def moved(source) -> bool:
    """Whether a sinceRev read shows anything but unchanged runs."""
    root = ET.fromstring(page.view_xml(source))
    return any(child.tag != "gap" for child in root)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("graph", help="the graph file")
    ap.add_argument("reads", nargs="+", help="sinceRev reads, one per tab, <question>.json")
    args = ap.parse_args(argv)
    graph = cli.load_graph(args.graph)
    if graph is None:
        return 1
    by_id = graph.by_id()
    stale = []
    for path in args.reads:
        qid = cli.question_of(path)
        q = by_id.get(qid)
        if q is None:
            print("ERROR %s: no question %s in the graph" % (path, qid), file=sys.stderr)
            return 1
        if not q.rev:
            stale.append("%s: the graph holds no rev for it, so it cannot be told fresh" % qid)
            continue
        with open(path, encoding="utf-8") as fh:
            if moved(fh.read()):
                stale.append("%s: moved since rev %d" % (qid, q.rev))
    for line in stale:
        print(line)
    if not stale:
        print("%d tab(s) unchanged since the graph was read" % len(args.reads), file=sys.stderr)
    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main())
