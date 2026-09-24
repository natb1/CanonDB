#!/usr/bin/env python3
"""lineage.py <graph.json> <question> -o FILE [--thread ID ...] — canon above a question.

Writes what a turn that answers <question> may carry, and nothing else: the
question and the one answer a turn may carry for each question the AI answers
above it, oldest first, and then the question itself. It is written out of the
graph file by this script and never transcribed by the turn that read the
notebook, so nothing of the notebook is in it — no headline, hinge, glossary,
note or question id. It refuses, saying what is owed, where a question above
has no answer a turn could carry. Prints one line: how many answers went in
and where. `--thread` names the questions of the open thread being continued,
whose answers in thread are carried without having landed.
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hypo import cli, model, turn  # noqa: E402

cli.quiet_pipe()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("graph", help="the graph file")
    ap.add_argument("question", help="the question to be put, by id")
    ap.add_argument("-o", "--out", required=True, help="write the lineage here")
    ap.add_argument("--thread", nargs="*", default=[], metavar="ID",
                    help="questions on the open thread being continued")
    args = ap.parse_args(argv)

    try:
        graph = model.load(args.graph)
    except model.ShapeError as exc:
        for problem in exc.problems:
            print("ERROR shape: %s" % problem, file=sys.stderr)
        return 1

    try:
        text = turn.lineage(graph, args.question, args.thread)
    except ValueError as exc:
        print("not written: %s" % exc, file=sys.stderr)
        return 1
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(text)
    print("%s: %d answer(s) above it -> %s"
          % (args.question, len(turn.above(graph, args.question)), args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
