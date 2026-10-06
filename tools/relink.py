#!/usr/bin/env python3
"""relink.py <graph.json> --tabs DIR --outlines DIR <question> [...] — repoint the links into rewritten tabs.

A link into a tab carries the id of a block on it, and a body write mints
new ids for every block on the tab it writes. So every link into a rewritten
tab from a tab outside the run points, from that write on, at a block that
no longer exists — and nothing else here can see it: the graph file never
held a link, and the page verifier resolves an href to the tab it is on and
no further. This reads each other tab's export for such links, resolves the
target afresh against the rewritten tab's outline (read after its write),
and prints one `format` operation per stale link, grouped by the tab that
carries it, as JSON: {question id: [ops]}. A format operation on a linked run
of text replaces its href, so the operations are sent as they stand. Ids and
counts on stderr; the operations are the only text printed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hypo import apply, cli, model, render  # noqa: E402

cli.quiet_pipe()


def stale_links(graph: model.Graph, targets, pages: dict, by_tab: dict) -> dict:
    """{question id: [format ops]} for every link on another tab that points
    into one of ``targets`` at a block its current outline does not hold.

    ``pages`` maps a question id to its export; ``by_tab`` maps a target's
    tab id to its parsed outline.
    """
    by_id = graph.by_id()
    target_tabs = {by_id[qid].tab for qid in targets if qid in by_id}
    out = {}
    lost = []
    for q in graph.questions:
        if q.id in targets or q.id not in pages:
            continue
        page = pages[q.id]
        if not any(("#%s." % tab) in page for tab in target_tabs):
            continue  # nothing links into a rewritten tab, so nothing is stale
        ops = []
        for entry in render.links(graph, q.id)["links"]:
            tab = entry["target"].lstrip("#").partition(".")[0]
            if tab not in target_tabs:
                continue
            href = apply.resolve(graph, entry["target"], by_tab, graph.artifact, q.tab)
            if href is None:
                lost.append("%s: %s" % (q.id, entry["target"]))
                continue
            # stale: the page links into that tab, and not by the href the
            # tab's outline now resolves to. A page that linked one block twice,
            # once fresh and once stale, would hide the stale one; a run that
            # repoints every link into a rewritten tab at once never leaves one.
            # The href is looked for whole, in its brackets: one block's id
            # opens another's, and .15 is inside .150
            if ("#%s." % tab) in page and ("(%s)" % href) not in page:
                find = entry["find"]
                ops.append({"op": "format",
                            "target": {"kind": "find", "text": find["text"], "nth": find["nth"]},
                            "add": [{"type": "link", "href": href}]})
        if ops:
            out[q.id] = ops
    if lost:
        raise apply.Unresolved(lost)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("graph", help="the graph file")
    ap.add_argument("questions", nargs="+", help="the questions whose tabs were rewritten")
    ap.add_argument("--tabs", required=True, help="a directory of <question id>.md exports")
    ap.add_argument("--outlines", required=True,
                    help="a directory holding <question id>.xml for each rewritten tab, "
                         "read after its write")
    args = ap.parse_args(argv)

    graph = cli.load_graph(args.graph)
    if graph is None:
        return 1
    by_id = graph.by_id()
    by_tab = {}
    for qid in args.questions:
        if qid not in by_id:
            print("ERROR no such question: %s" % qid, file=sys.stderr)
            return 1
        path = os.path.join(args.outlines, qid + ".xml")
        try:
            with open(path, encoding="utf-8") as fh:
                by_tab[by_id[qid].tab] = apply.parse_outline(fh.read())
        except OSError as exc:
            print("ERROR outline: %s" % exc, file=sys.stderr)
            return 1
    try:
        pages = cli.exports(args.tabs)
    except OSError as exc:
        print("ERROR tabs: %s" % exc, file=sys.stderr)
        return 1

    try:
        out = stale_links(graph, args.questions, pages, by_tab)
    except apply.Unresolved as refusal:
        # an outline that pairs with no render resolves nothing, and nothing
        # repointed is not the same as nothing stale
        print("ERROR %d link target(s) unresolved, so nothing can be said of "
              "what is stale:" % len(refusal.args[0]), file=sys.stderr)
        for target in refusal.args[0]:
            print("  " + target, file=sys.stderr)
        return 1
    print(json.dumps(out, indent=1, ensure_ascii=False))
    for qid, ops in sorted(out.items()):
        print("%s: %d link(s) to repoint" % (qid, len(ops)), file=sys.stderr)
    print("%d tab(s), %d link(s)" % (len(out), sum(len(v) for v in out.values())),
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
