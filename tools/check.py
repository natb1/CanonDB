#!/usr/bin/env python3
"""check.py <graph.json> [--json] — run every check over a graph file.

Prints one line per finding and a summary; exits 1 if any finding is an ERROR.
Findings and aggregates only: no file contents are printed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hypo import cli, model, spec  # noqa: E402

cli.quiet_pipe()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("graph", nargs="?", help="the graph file")
    ap.add_argument("--json", action="store_true", dest="as_json",
                    help="print the findings as JSON")
    ap.add_argument("--only", action="append", metavar="CHECK",
                    help="run only this check (repeatable)")
    ap.add_argument("--list", action="store_true",
                    help="list the checks and exit")
    args = ap.parse_args(argv)

    if args.list:
        for cid, severity, description in spec.catalogue():
            print("%-5s %-21s %s" % (severity, cid, description))
        return 0
    if not args.graph:
        ap.error("give a graph file, or --list")

    try:
        graph = model.load(args.graph)
    except model.ShapeError as exc:
        findings = [spec.Finding("shape", spec.ERROR, None, p) for p in exc.problems]
        _report(findings, args.as_json, args.graph, 0)
        return 1

    findings = spec.run(graph, only=args.only)
    _report(findings, args.as_json, args.graph, len(graph.questions))
    return 1 if spec.errors(findings) else 0


def _report(findings, as_json: bool, path: str, questions: int) -> None:
    errors = [f for f in findings if f.severity == spec.ERROR]
    warns = [f for f in findings if f.severity == spec.WARN]
    if as_json:
        print(json.dumps({
            "graph": os.path.basename(path),
            "questions": questions,
            "errors": len(errors),
            "warnings": len(warns),
            "findings": [f.as_dict() for f in findings],
        }, indent=2, ensure_ascii=False))
        return
    for finding in findings:
        print(finding.line())
    print("%s: %d questions, %d errors, %d warnings" % (
        os.path.basename(path), questions, len(errors), len(warns)))


if __name__ == "__main__":
    sys.exit(main())
