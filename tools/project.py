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

from hypo import cli, project, spec  # noqa: E402

cli.quiet_pipe()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("graph", help="the graph file")
    ap.add_argument("--json", action="store_true", dest="as_json",
                    help="print the patch and the tree as one JSON object")
    ap.add_argument("--project", metavar="NAME",
                    help="place one project's tabs alone, for a run that read that "
                         "project (the tradition project's include every party)")
    args = ap.parse_args(argv)

    graph = cli.load_graph(args.graph)
    if graph is None:
        return 1

    # parents() breaks a cycle deterministically so that every projection stays
    # total on a broken graph, which the checks rely on. That makes it exactly
    # the wrong thing to send: the tree would look well-formed and the cycle
    # would survive unseen in the graph file. The same of a second root, whose
    # subtree the walk never reaches and the patch silently leaves out, and of
    # a tradition that is not isolated, whose tab the patch hangs under the
    # author's or his under its, and of a term edge across projects, which
    # would hang one project's question under another's. Refuse, as render.py
    # refuses.
    blocking = spec.errors(spec.run(graph, only=["acyclic", "one-root", "tradition-isolated",
                                                 "project-order"]))
    if blocking:
        print("refusing to project %s: the tree would hide what the checks found "
              "(a cycle, a second root, or a tradition not isolated)"
              % os.path.basename(args.graph), file=sys.stderr)
        for finding in blocking:
            print(finding.line(), file=sys.stderr)
        return 1

    if args.project is not None and args.project not in project.projects(graph):
        print("no project %r in %s" % (args.project, os.path.basename(args.graph)),
              file=sys.stderr)
        return 1
    patch = project.tabs_patch(graph, args.project)

    if args.as_json:
        print(json.dumps({"tabs": patch, "tree": project.tree_rows(graph)},
                         indent=2, ensure_ascii=False))
        return 0

    for line in project.tree_listing(graph):
        print(line)
    print()
    print(json.dumps(patch, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
