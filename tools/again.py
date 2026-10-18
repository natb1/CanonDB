#!/usr/bin/env python3
"""again.py <graph.json> --model NAME [--root DIR] [--json] — the landed answers due again.

Prints every landed question of the author's that the AI answers and whose
answer is dated: its hinge names a model other than NAME, or canon above it
has moved since the commit its hinge names, read off git under DIR (the
working directory by default). Each line is the question's id and what
moved; nothing of the notebook's text is printed, only what the hinge
recorded. `/principal:ask --again` puts one of them in a fresh context and
records what comes back as a further answer on its tab.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hypo import again, cli  # noqa: E402

cli.quiet_pipe()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("graph", help="the graph file")
    ap.add_argument("--model", required=True, help="the model answering now")
    ap.add_argument("--root", default=".", help="the project root git reads canon under")
    ap.add_argument("--json", action="store_true", dest="as_json")
    args = ap.parse_args(argv)

    graph = cli.load_graph(args.graph)
    if graph is None:
        return 1
    rows = again.due(graph, args.model, again.git_moved(args.root))
    if args.as_json:
        print(json.dumps([r._asdict() for r in rows], indent=2, ensure_ascii=False))
        return 0
    if not rows:
        print("nothing is due again", file=sys.stderr)
        return 0
    for line in again.listing(rows):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
