#!/usr/bin/env python3
"""predictions.py <mode> … — the failed predictions the notebook records: a note's words, the tally, the stamp, and a seal checked.

The notebook is the one home: a prediction that fails, in whole or in part,
is a divergence note on the notebook, written through the recorder, and
this tool reads it back from a graph. Those graded since the graph was read
wait as note words, one ``*.txt`` file each, in a directory passed as
``--added``, so that the next stamp holds them.

    note --seal ID --by WHO --kind KIND --grade GRADE --lesson L --price P
         [--direction D [--text T]]
                                    print a failed prediction's note words, for
                                    ``inplace.py note insert``
    tally GRAPH [--added DIR]       counts by kind, by who predicted, by grade
                                    and by direction, and the lessons two or
                                    more predictions carry, as JSON
    stamp GRAPH --at T [--added DIR]
                                    the tally as text, ending with the line
                                    ``predictions-read: <sha256> <T>``
    check-seal FILE --graph GRAPH --stamp FILE [--added DIR]
                                    refuse a sealed file of the speaker's own that
                                    does not end with the stamp of the record as
                                    it stands, or whose stamp file is not what
                                    ``stamp`` prints

``note`` refuses a grade that is not a failure (``diverges in part``,
``diverges``, ``verdict only``, ``short of the edge``), a direction outside
its list, and a grade of ``diverges in part``, ``diverges`` or ``verdict
only`` without one; ``agrees`` is refused, nothing having diverged. A refusal is one ``REFUSED:``
line per reason on standard error and exits 1. ``T`` is an ISO 8601 UTC time
such as ``2030-01-02T03:04:05Z``. Nothing here reaches the network or reads
a clock.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hypo import cli, predictions  # noqa: E402

cli.quiet_pipe()


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0], epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="mode", required=True)
    p = sub.add_parser("note")
    p.add_argument("--seal", required=True, metavar="ID",
                   help="the seal graded, by its id: the seal job's, or the sealed file's")
    p.add_argument("--by", required=True)
    p.add_argument("--kind", required=True)
    p.add_argument("--grade", required=True)
    p.add_argument("--lesson", required=True)
    p.add_argument("--price", required=True)
    p.add_argument("--direction")
    p.add_argument("--text")
    for name in ("tally", "stamp"):
        p = sub.add_parser(name)
        p.add_argument("graph", help="the opening's graph")
        p.add_argument("--added", metavar="DIR",
                       help="the note words of predictions graded since, one *.txt a note")
        if name == "stamp":
            p.add_argument("--at", required=True, metavar="T")
    p = sub.add_parser("check-seal")
    p.add_argument("sealed")
    p.add_argument("--graph", required=True)
    p.add_argument("--stamp", required=True, metavar="FILE")
    p.add_argument("--added", metavar="DIR")
    return ap


def _read(path: str, what: str) -> str:
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except (OSError, ValueError) as exc:
        raise predictions.Refused(["the %s file cannot be read: %s" % (what, exc)])


def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.mode == "note":
            print(predictions.compose(args.seal, args.by, args.kind, args.grade, args.lesson,
                                      args.price, args.direction, args.text))
            return 0
        graph = cli.load_graph(args.graph)
        if graph is None:
            raise predictions.Refused(["the graph cannot be read"])
        preds, recorded = predictions.gather(graph, args.added)
        if args.mode == "tally":
            print(json.dumps(predictions.tally(preds, recorded), indent=1, ensure_ascii=False))
        elif args.mode == "stamp":
            sys.stdout.write(predictions.stamp(preds, recorded, args.at))
        else:
            print("ok: %s" % predictions.check_seal(_read(args.sealed, "sealed"),
                                                    _read(args.stamp, "stamp"),
                                                    preds, recorded))
    except predictions.Refused as exc:
        for reason in exc.reasons:
            print("REFUSED: %s" % reason, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
