#!/usr/bin/env python3
"""verify.py <graph.json> <tabs dir> [--only ID] — the page against the renderer.

Reads the exported tabs — one `<question id>.md` per tab — and reports, per tab,
the body that is not what the renderer would produce, the links the sidecar
names that the page does not carry, the links standing where the encoding
does not put that kind, the links leading to a tab other than the one they
name, and the links the page carries that the sidecar does not name.

This is the closing gate of a write. Every other check reads the graph file,
and a graph file never held a link, so nothing else can see whether the links
reached the page. Exits 1 on any finding.

Being the closing gate, it also says whether the committed envelope still holds
this notebook. `read.py` re-seals it on every complete read, but it declines on
a partial one, on a checker error and on a re-seal that would drop questions —
so the last word on whether the export cache went out with the change belongs
here, where the run ends. It reports the shape of the difference and never the
notebook. `--no-envelope` leaves it out.
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:  # a tool piped into head should stop, not traceback
    import signal
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
except (ImportError, AttributeError, ValueError):  # pragma: no cover - not POSIX
    pass

from hypo import model, portable, verify as check  # noqa: E402


def pages(directory: str) -> dict:
    found = {}
    for entry in sorted(os.listdir(directory)):
        if entry.endswith(".md"):
            with open(os.path.join(directory, entry), encoding="utf-8") as fh:
                found[entry[:-3]] = fh.read()
    return found


def stale(graph: model.Graph, args) -> bool:
    """Whether the committed envelope no longer holds this notebook.

    A finding like any other here, and printed like the rest of them: what
    changed, by id and by key, in lines that do not grow with the notebook.
    """
    if args.no_envelope:
        return False
    envelope = args.envelope or portable.committed(portable.root())
    if not envelope:
        return False
    name = os.path.basename(envelope)
    try:
        _, changed = portable.compare(graph, envelope)
    except (OSError, ValueError) as exc:
        print("ERROR envelope %s: %s" % (name, exc))
        return True
    if not changed:
        return False
    print("%s is stale — `portable.py reseal` puts this graph in it:" % name)
    for line in changed:
        print("  " + line)
    return True


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("graph", help="the graph file")
    ap.add_argument("tabs", help="a directory of <question id>.md exports")
    ap.add_argument("--only", action="append", metavar="ID",
                    help="verify only this question (repeatable)")
    ap.add_argument("--envelope", metavar="FILE",
                    help="check this envelope instead of the committed one")
    ap.add_argument("--no-envelope", action="store_true", dest="no_envelope",
                    help="do not ask whether the export cache is current")
    args = ap.parse_args(argv)

    try:
        graph = model.load(args.graph)
    except model.ShapeError as exc:
        for problem in exc.problems:
            print("ERROR shape: %s" % problem, file=sys.stderr)
        return 1

    try:
        found = pages(args.tabs)
    except OSError as exc:
        print("ERROR tabs: %s" % exc, file=sys.stderr)
        return 1
    if not found:
        print("ERROR no .md exports in %s" % args.tabs, file=sys.stderr)
        return 1
    if args.only:
        found = {qid: page for qid, page in found.items() if qid in set(args.only)}

    reports = check.verify_all(graph, found)
    bad = [report for report in reports if not report.ok()]
    for report in bad:
        for line in report.lines():
            print(line)
    if not args.only:  # with --only, everything else is absent on purpose
        absent = [q.id for q in graph.questions if q.id not in found]
        if absent:
            print("no export on disk for: %s" % ", ".join(absent))
    print("%d of %d tabs differ, %d link(s) missing, %d out of place, "
          "%d astray, %d unaccounted"
          % (len(bad), len(reports),
             sum(len(r.missing) for r in reports),
             sum(len(r.misplaced) for r in reports),
             sum(len(r.astray) for r in reports),
             sum(len(r.extra) for r in reports)))
    return 1 if (bad or stale(graph, args)) else 0


if __name__ == "__main__":
    sys.exit(main())
