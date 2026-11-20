#!/usr/bin/env python3
"""hinges.py place|unjustified … — the AI's presuppositions placed as hinges, and the unjustified ones listed.

    place DIR --n N [--under ID] [--line-name NAME]
                                   for question N of the line in DIR, its answer
                                   of record (the first kept draw, checked as a
                                   packet checks it): the question, the answer word
                                   for word, what it rests on, and each line of its
                                   ``Presupposes:`` as a hinge marked unjustified,
                                   naming the question it came in by, and the
                                   hinge's thesis part from the draw, as JSON;
                                   the line's name is NAME, or DIR's own name
    unjustified GRAPH
                                   every unjustified hinge of the AI's graph, with
                                   the builds that cite an answer resting on it

A hinge is justified only by a later answer of the AI's own that it is
linked to: its line ends ``(justified by <question id>)``. ``place`` refuses
an answer whose presuppositions are not one a line under the label, a
question of the line not yet answered, and a draw that is not the one
``clean_turn.py`` wrote. Nothing of the user's record is read. Nothing here
reaches the network or writes the notebook.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hypo import cli, hinges  # noqa: E402

cli.quiet_pipe()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0], epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="mode", required=True)
    p = sub.add_parser("place")
    p.add_argument("line", help="the line's directory, $SCRATCH/lines/<line>")
    p.add_argument("--n", type=int, required=True, help="the question's number on the line")
    p.add_argument("--under", metavar="ID", help="the tab of the AI's the line stands under")
    p.add_argument("--line-name", metavar="NAME",
                   help="the line's name, where its directory is not named for it")
    p = sub.add_parser("unjustified")
    p.add_argument("graph")
    args = ap.parse_args(argv)
    if args.mode == "unjustified":
        graph = cli.load_graph(args.graph)
        if graph is None:
            return 1
        found = hinges.unjustified(graph)
        print(json.dumps(found, indent=1, ensure_ascii=False))
        print("%d unjustified hinge(s)" % len(found), file=sys.stderr)
        return 0
    import packet
    try:
        pairs, carried = packet.line(args.line)
        if args.n < 1 or args.n > len(pairs):
            raise hinges.Refused("the line holds no answered question %d" % args.n)
        question, answer = pairs[args.n - 1]
        draw = os.path.join(args.line, str(args.n), "draws", carried[args.n - 1]["draw"])
        with open(draw, encoding="utf-8") as fh:
            model = json.load(fh).get("model")
        name = args.line_name or os.path.basename(os.path.normpath(args.line))
        out = hinges.place(question, answer, name, args.n, args.under,
                           model if isinstance(model, str) else None)
    except (hinges.Refused, packet.Refused) as exc:
        print("REFUSED: %s" % exc, file=sys.stderr)
        return 1
    print(json.dumps(out, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
