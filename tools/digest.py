#!/usr/bin/env python3
"""digest.py <graph.json> [--project NAME] [-o FILE] — a project's digest.

The end and its method, the words, the clauses with their cues and the
cases of one project, as the markdown a Claude Project's instructions take.
Every line is a part of a tab as the tab holds it; nothing is composed. The
project is the one named, else the one ``.principal/notebook.json`` names,
else the notebook's one root. Exit 1 where the graph holds no such project.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hypo import cli, digest  # noqa: E402

cli.quiet_pipe()


def _project():
    try:
        with open(os.path.join(".principal", "notebook.json"), encoding="utf-8") as fh:
            found = json.load(fh).get("project")
    except (OSError, ValueError, AttributeError):
        return None
    return found or None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("graph")
    ap.add_argument("--project", metavar="NAME",
                    help="the project to digest (default: the one "
                         ".principal/notebook.json names, else the one root)")
    ap.add_argument("-o", "--out", metavar="FILE")
    args = ap.parse_args(argv)
    graph = cli.load_graph(args.graph)
    if graph is None:
        return 1
    name = args.project if args.project is not None else _project()
    text = digest.digest(graph, name)
    if not text:
        print("ERROR %s holds no project %s" % (os.path.basename(args.graph),
                                               name or "with one root"), file=sys.stderr)
        return 1
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print("%d line(s) -> %s" % (text.count("\n"), args.out), file=sys.stderr)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
