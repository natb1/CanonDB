#!/usr/bin/env python3
"""registry.py export <graph.json> [-o FILE] — every party's works, as one registry.

Prints, as JSON, each key a party's tab lists under its works, with the party
that lists it and the work's filled fields:

    registry.py export graph.json -o sources.json

A repository's check reads that file in place of a registry of its own. It is
a projection of the notebook: exported again whenever a work changes on its
party's tab, and never committed by the notebook's tooling.

Refuses (exit 1) where the checker reports an ERROR on the works themselves —
a work on a tab that is no party's, a key of the wrong shape or defined twice,
a field that would not read back — since a registry built over those says
something the notebook does not. Refuses a partial graph too: a read scoped
to a few tabs need not hold every party, and a registry missing one would
make every key that party defines read as unregistered.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hypo import cli, registry, spec  # noqa: E402

cli.quiet_pipe()

#: the checks on the works themselves, which the export stands on
WORK_CHECKS = ("works-on-party", "work-key-shape", "work-key-unique", "work-fields")


def _export(args) -> int:
    graph = cli.load_graph(args.graph)
    if graph is None:
        return 1
    if graph.partial:
        print("refusing to export %s: it was read for %s alone, and the registry "
              "is every party's" % (os.path.basename(args.graph), ", ".join(graph.scope)),
              file=sys.stderr)
        return 1
    blocking = spec.errors(spec.run(graph, only=WORK_CHECKS))
    if blocking:
        print("refusing to export %s: the checker reports %d error(s) on the works"
              % (os.path.basename(args.graph), len(blocking)), file=sys.stderr)
        for finding in blocking:
            print(finding.line(), file=sys.stderr)
        return 1

    found = registry.export(graph)
    text = json.dumps(found, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print("%d source(s) -> %s" % (len(found["sources"]), args.out), file=sys.stderr)
    else:
        sys.stdout.write(text)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    subs = ap.add_subparsers(dest="verb", required=True)

    e = subs.add_parser("export", help="a graph file -> every party's works")
    e.add_argument("graph", help="the graph file")
    e.add_argument("-o", "--out", help="write here instead of stdout")
    e.set_defaults(run=_export)

    args = ap.parse_args(argv)
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main())
