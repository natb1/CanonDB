#!/usr/bin/env python3
"""project.py <graph.json> [--json] — the tab-tree projection.

Prints the tree listing and the complete tab-placement patch, ready to be sent
as the `tabs` patch of a document update.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hypo import cli, model, project, spec  # noqa: E402

cli.quiet_pipe()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("graph", help="the graph file")
    ap.add_argument("--json", action="store_true", dest="as_json",
                    help="print the patch and the tree as one JSON object")
    args = ap.parse_args(argv)

    try:
        graph = model.load(args.graph)
    except model.ShapeError as exc:
        for problem in exc.problems:
            print("ERROR shape                 -              %s" % problem,
                  file=sys.stderr)
        return 1

    # parents() breaks a cycle deterministically so that every projection stays
    # total on a broken graph, which the checks rely on. That makes it exactly
    # the wrong thing to send: the tree would look well-formed and the cycle
    # would survive unseen in the graph file. Refuse, as render.py refuses.
    blocking = spec.errors(spec.run(graph, only=["acyclic"]))
    if blocking:
        print("refusing to project %s: the term graph has a cycle"
              % os.path.basename(args.graph), file=sys.stderr)
        for finding in blocking:
            print(finding.line(), file=sys.stderr)
        return 1

    patch = project.tabs_patch(graph)
    parents = project.parents(graph)
    distances = project.distances(graph)

    if args.as_json:
        tree = []
        for qid in project.walk(graph):
            distance = distances.get(qid, project.INF)
            tree.append({
                "question": qid,
                "parent": parents.get(qid),
                "order": project.orders(graph).get(qid),
                "distance": None if distance == project.INF else int(distance),
                "load": project.load(graph, qid),
            })
        print(json.dumps({"tabs": patch, "tree": tree}, indent=2, ensure_ascii=False))
        return 0

    for line in project.tree_listing(graph):
        print(line)
    print()
    print(json.dumps(patch, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
