#!/usr/bin/env python3
"""crossing.py <graph.json> [--project NAME] — the review of the edges that cross projects.

For each entry an earlier project raises: the clause that raises it, the
end the entry states, and what the entry records against the clause. An
entry whose record says the clause cannot be met stands first. ``--project``
names the containing project. This is the derivation reading. Exit 2 where
an entry cannot be met, so a review can be told there is a finding.
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hypo import cli, crossing  # noqa: E402

cli.quiet_pipe()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("graph")
    ap.add_argument("--project", metavar="NAME")
    args = ap.parse_args(argv)
    graph = cli.load_graph(args.graph)
    if graph is None:
        return 1
    found = crossing.edges(graph, args.project)
    for line in crossing.listing(found):
        print(line)
    print("%d crossing edge(s) · %d cannot be met"
          % (len(found), sum(1 for e in found if e.unmet)), file=sys.stderr)
    return 2 if any(e.unmet for e in found) else 0


if __name__ == "__main__":
    sys.exit(main())
