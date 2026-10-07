#!/usr/bin/env python3
"""next.py <graph.json> [--thread ID ...] [--all] — the next question to put.

Prints the question the AI answers that waits heaviest with nothing left to
wait on, which is what a caller outside this plugin reads off the notebook. With `--all`, every
question not yet put, heaviest first, with what each still waits on. A
question's answer that stands earlier on the thread being continued is
carried without having landed, so `--thread` names that thread's questions.
Ids and numbers only: nothing of the notebook's text is printed.
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hypo import cli, turn  # noqa: E402

cli.quiet_pipe()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("graph", help="the graph file")
    ap.add_argument("--thread", nargs="*", default=[], metavar="ID",
                    help="questions on the open thread being continued")
    ap.add_argument("--all", action="store_true", dest="everything",
                    help="list every question not yet put, and what it waits on")
    args = ap.parse_args(argv)

    graph = cli.load_graph(args.graph)
    if graph is None:
        return 1

    rows = turn.frontier(graph, args.thread)
    if args.everything:
        for line in turn.listing(rows):
            print(line)
        return 0
    chosen = turn.select(graph, args.thread)
    if chosen is None:
        print("nothing can be put: %d question(s) wait; --all says on what"
              % len(rows), file=sys.stderr)
        return 1
    print(chosen)
    return 0


if __name__ == "__main__":
    sys.exit(main())
