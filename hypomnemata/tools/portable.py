#!/usr/bin/env python3
"""portable.py seal <graph.json> | open <envelope.json> — the carry interface.

A party who wants a notebook of their own, rather than a share of this one, is
handed its graph, with every value that names *this* document emptied:

    portable.py seal graph.json -o hypomnemata.json    # part it from the document
    portable.py open hypomnemata.json -o graph.json    # the graph again, unbound

`seal` refuses (exit 1) if the checker reports an ERROR: what is handed over is
a notebook that stands, not one that is owed repairs. `--force` seals anyway and
says so. `open` writes a graph whose `artifact`, `state_enum`, `tab` and `body`
are empty, which the receiving party fills from their own document; the steps
for that ride inside the envelope. An envelope sealed under an older format is
read forward rather than refused, and `open` says on stderr what that moved.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hypo import cli, model, portable, spec  # noqa: E402

cli.quiet_pipe()


def _write(payload, out) -> None:
    text = portable.dump(payload)
    if out:
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(text)
    else:
        sys.stdout.write(text)


def _seal(args) -> int:
    try:
        graph = model.load(args.file)
    except model.ShapeError as exc:
        for problem in exc.problems:
            print("ERROR shape: %s" % problem, file=sys.stderr)
        return 1

    blocking = spec.errors(spec.run(graph))
    if blocking and not args.force:
        print("refusing to seal %s: the checker reports %d error(s)"
              % (os.path.basename(args.file), len(blocking)), file=sys.stderr)
        for finding in blocking:
            print(finding.line(), file=sys.stderr)
        return 1

    with open(args.file, encoding="utf-8") as fh:
        bound = portable.bindings(json.load(fh))
    envelope = portable.seal(graph, name=args.name, tools=args.tools)
    _write(envelope, args.out)
    if args.out:
        print("%d questions, %d binding(s) dropped -> %s"
              % (len(envelope["questions"]), len(bound), args.out),
              file=sys.stderr)
        # the bindings are two per question and grow with the notebook, so
        # naming each one is asked for rather than assumed: the count is what
        # says sealing dropped them, and the list is for reading one by one
        if args.verbose:
            for line in bound:
                print("  dropped %s" % line, file=sys.stderr)
    if blocking:
        print("sealed with %d unresolved error(s) (--force)" % len(blocking),
              file=sys.stderr)
    return 0


def _open(args) -> int:
    try:
        with open(args.file, encoding="utf-8") as fh:
            envelope = json.load(fh)
    except (OSError, ValueError) as exc:
        print("ERROR envelope: %s" % exc, file=sys.stderr)
        return 1
    try:
        data, notes = portable.opened(envelope)
    except ValueError as exc:
        print("ERROR envelope: %s" % exc, file=sys.stderr)
        return 1

    _write(data, args.out)
    if args.out:
        print("%d questions -> %s (unbound: fill artifact, state_enum, tab, body)"
              % (len(data["questions"]), args.out), file=sys.stderr)
    # an envelope sealed under an older format is read forward rather than
    # refused, and what that moved is said whether or not the graph went to a
    # file: it is the one difference between the notebook sealed and the one
    # opened, and the only run that can report it is this one
    for line in notes:
        print("  read forward: %s" % line, file=sys.stderr)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    subs = ap.add_subparsers(dest="verb", required=True)

    s = subs.add_parser("seal", help="a graph file -> a portable envelope")
    s.add_argument("file", help="the graph file")
    s.add_argument("-o", "--out", help="write here instead of stdout")
    s.add_argument("--name", default="", help="what to call the notebook")
    s.add_argument("--tools", default="",
                   help="where the tooling that rebuilds it is kept")
    s.add_argument("--force", action="store_true",
                   help="seal even though the checker reports errors")
    s.add_argument("-v", "--verbose", action="store_true",
                   help="name every binding dropped, not only how many")
    s.set_defaults(run=_seal)

    o = subs.add_parser("open", help="an envelope -> an unbound graph file")
    o.add_argument("file", help="the envelope")
    o.add_argument("-o", "--out", help="write here instead of stdout")
    o.set_defaults(run=_open)

    args = ap.parse_args(argv)
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main())
