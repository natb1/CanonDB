#!/usr/bin/env python3
"""drift.py <graph.json> [--json] — the drift count, off the record.

Prints, per question of the author's that holds an answer the AI gave, how
many answers were drawn and how many of the later ones were read as agreeing
or diverging; and per deadlocked clause, whether each later draw holds it.
A projection, computed as pressure, backlog and load are and stored nowhere;
it asserts nothing, since a question with one draw has nothing later to
read. Ids, numbers and clause headlines only.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hypo import cli, drift  # noqa: E402

cli.quiet_pipe()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("graph", help="the graph file")
    ap.add_argument("--json", action="store_true", dest="as_json")
    args = ap.parse_args(argv)

    graph = cli.load_graph(args.graph)
    if graph is None:
        return 1
    drawn, held = drift.draws(graph), drift.deadlocks(graph)
    if args.as_json:
        print(json.dumps({"draws": [r._asdict() for r in drawn],
                          "deadlocks": [r._asdict() for r in held]},
                         indent=2, ensure_ascii=False))
        return 0
    if not drawn and not held:
        print("no answer the AI gave is on the record", file=sys.stderr)
        return 0
    for line in drift.listing(drawn, held):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
