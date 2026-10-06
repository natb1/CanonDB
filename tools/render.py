#!/usr/bin/env python3
"""render.py <graph.json> <question id> [--all] [--links] — the write interface.

Prints the canonical markdown body for a tab. `--all` prints every tab, each
preceded by a `=== <question id> ===` line. `--links` also prints the JSON
sidecar of the links the caller must apply once the write returns block ids.

The renderer refuses (exit 1) if the checker finds any ERROR affecting the
question asked for.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hypo import cli, render, spec  # noqa: E402

cli.quiet_pipe()

LINKS_MARK = "=== links ==="


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("graph", help="the graph file")
    ap.add_argument("question", nargs="?", help="the question id to render")
    ap.add_argument("--all", action="store_true", dest="every",
                    help="render every tab")
    ap.add_argument("--links", action="store_true",
                    help="also print the links sidecar as JSON")
    args = ap.parse_args(argv)

    if not args.every and not args.question:
        ap.error("give a question id, or --all")

    graph = cli.load_graph(args.graph)
    if graph is None:
        return 1

    if not args.every and graph.get(args.question) is None:
        print("no question %r in %s" % (args.question, os.path.basename(args.graph)),
              file=sys.stderr)
        return 1

    findings = spec.run(graph)
    try:
        text = (render.render_all(graph, findings) if args.every
                else render.render(graph, args.question, findings))
    except render.RefusedError as refusal:
        print("refusing to render %s: the checker reports %d error(s)"
              % (refusal.qid, len(refusal.findings)), file=sys.stderr)
        for finding in refusal.findings:
            print(finding.line(), file=sys.stderr)
        return 1

    sys.stdout.write(text)
    if args.links:
        payload = (render.links_all(graph) if args.every
                   else render.links(graph, args.question))
        print()
        print(LINKS_MARK)
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
