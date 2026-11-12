#!/usr/bin/env python3
"""shares.py <graph.json> [--project NAME] [--price Q,Q…] [--propose] — the share of the root each principle carries.

Each principle hands what it carries to the principles derived from it, in
equal parts unless pressure is set among them; an action's price in what it
compromises is the shares of the principles it diverges from. ``--price``
sums the shares of the questions named. ``--propose`` lists, for each
question carrying pressure, the arrangement by equal parts that would need
none, and whether it changes the order of any two shares; it proposes and
never applies. Reads a graph of every tab: a share is handed down from the
root, so a scoped graph without the root has none to hand.
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hypo import cli, share  # noqa: E402

cli.quiet_pipe()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("graph")
    ap.add_argument("--project", metavar="NAME")
    ap.add_argument("--price", metavar="Q,Q", help="the questions an action diverges from")
    ap.add_argument("--propose", action="store_true")
    args = ap.parse_args(argv)
    graph = cli.load_graph(args.graph)
    if graph is None:
        return 1
    if args.price:
        named = [q.strip() for q in args.price.split(",") if q.strip()]
        unknown = [q for q in named if graph.get(q) is None]
        if unknown:
            print("ERROR no question %s" % ", ".join(unknown), file=sys.stderr)
            return 1
        print("%.4f" % share.price(graph, named))
        return 0
    if args.propose:
        standing = share.pressure_standing(graph, args.project)
        print("pressure standing: %d on %d question(s)"
              % (sum(p for _, p in standing), len(standing)))
        for p in share.proposals(graph, args.project):
            print(p.line())
        return 0
    for line in share.listing(graph, args.project):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
