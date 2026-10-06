#!/usr/bin/env python3
"""apply.py <graph.json> <question id> [--body | --links | --unlink PAGE]

Prints the operations that put a rendered tab into the document, ready to send
as the `ops` of one prose `update`. Writing a tab is two calls, in this order:

    apply.py graph.json canon --outlines out/ --body    # replace the tab
    apply.py graph.json canon --outlines out/ --links   # put the links on it

with the outlines re-read in between, because the body write mints new block
ids. Neither payload is composed by hand, and the second is not optional: a
body write alone leaves a tab with no in-page links at all.

    apply.py graph.json canon --unlink out/canon.md     # take off the strays

is the third, and it reads the exported page rather than an outline: a link
the sidecar no longer names is on the page and nowhere else.

`--outlines <dir>` holds one `<question id>.xml` per tab, as the document
prints an outline read or a write's ack. `--wanted` lists the tabs the links
step needs before it can run. Refuses (exit 1) on a link whose target no
outline accounts for.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hypo import apply as ops, cli, spec  # noqa: E402

cli.quiet_pipe()


def outlines(graph: model.Graph, directory: str) -> dict:
    """tab id -> its parsed outline, for every `<question id>.xml` on disk."""
    found = {}
    for q in graph.questions:
        path = os.path.join(directory, q.id + ".xml")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                found[q.tab] = ops.parse_outline(fh.read())
    return found


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("graph", help="the graph file")
    ap.add_argument("question", help="the question id to apply")
    ap.add_argument("--outlines", metavar="DIR",
                    help="a directory of <question id>.xml outlines")
    ap.add_argument("--body", action="store_true",
                    help="print the body replace operation")
    ap.add_argument("--links", action="store_true",
                    help="print the format operations for the links")
    ap.add_argument("--unlink", metavar="PAGE",
                    help="print the format operations that take off the links "
                         "the sidecar does not name, given the exported tab")
    ap.add_argument("--wanted", action="store_true",
                    help="list the tabs whose outlines the links step needs")
    args = ap.parse_args(argv)

    graph = cli.load_graph(args.graph)
    if graph is None:
        return 1

    q = graph.get(args.question)
    if q is None:
        print("no question %r in %s" % (args.question, os.path.basename(args.graph)),
              file=sys.stderr)
        return 1

    tab_name = {other.tab: other.id for other in graph.questions}

    if args.wanted:
        for tab in ops.wanted_tabs(graph, args.question):
            print(tab_name.get(tab, tab))
        return 0

    chosen = [name for name, on in (("--body", args.body), ("--links", args.links),
                                    ("--unlink", bool(args.unlink))) if on]
    if not chosen:
        ap.error("give --body, --links, --unlink or --wanted")
    if len(chosen) > 1:
        ap.error("%s are separate calls: the body write mints the ids the "
                 "links need, and a removal is read off the page as it stands"
                 % " and ".join(chosen))
    if not args.outlines and not args.unlink:
        ap.error("give --outlines DIR")

    # the renderer's refusal is the gate on both: a tab the checker reports an
    # ERROR against is not written, links or no links
    blocking = spec.errors(spec.affecting(spec.run(graph), args.question))
    if blocking:
        print("refusing to apply %s: the checker reports %d error(s)"
              % (args.question, len(blocking)), file=sys.stderr)
        for finding in blocking:
            print(finding.line(), file=sys.stderr)
        return 1

    by_tab = outlines(graph, args.outlines) if args.outlines else {}
    try:
        if args.unlink:
            with open(args.unlink, encoding="utf-8") as fh:
                payload = ops.unlink_ops(graph, args.question, fh.read())
        elif args.body:
            mine = by_tab.get(q.tab)
            if mine is None:
                print("no outline for %s in %s" % (args.question, args.outlines),
                      file=sys.stderr)
                return 1
            payload = ops.body_ops(graph, args.question, mine)
        else:
            payload = ops.link_ops(graph, args.question, by_tab, graph.artifact)
    except ops.Unresolved as refusal:
        print("refusing to apply %s: %d link target(s) unresolved"
              % (args.question, len(refusal.missing)), file=sys.stderr)
        for line in refusal.missing:
            print("   " + line, file=sys.stderr)
        absent = [tab_name.get(tab, tab) for tab in ops.wanted_tabs(graph, args.question)
                  if tab not in by_tab]
        if absent:
            print("   no outline on disk for: %s" % ", ".join(absent), file=sys.stderr)
        return 1

    print(json.dumps({"ops": payload}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
