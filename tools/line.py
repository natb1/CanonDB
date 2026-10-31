#!/usr/bin/env python3
"""line.py check DOC [GRAPH] | line.py rows DOC [--json] — a line doc against its plan.

DOC is the markdown export of a line doc, the record of one elenchus
compacted into a plan (``page.py`` writes one from a saved read). ``check``
says what the compaction left out: a dialog admission no row cites, a row
that edits the notebook and cites nothing, a tab a row names that GRAPH
does not hold, and an item pinned in the dialog that is neither closed nor
carried by a row. ``rows`` lists the plan's rows, with what each cites and
the tabs it names, as lines or as JSON. Exit 1 on an error.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hypo import cli, line  # noqa: E402

cli.quiet_pipe()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    modes = ap.add_subparsers(dest="mode", required=True)
    p = modes.add_parser("check")
    p.add_argument("doc")
    p.add_argument("graph", nargs="?", help="the graph the round ends with")
    p = modes.add_parser("rows")
    p.add_argument("doc")
    p.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    with open(args.doc, encoding="utf-8") as fh:
        doc = line.parse(fh.read())
    if args.mode == "rows":
        rows = line.rows_json(doc)
        if args.json:
            print(json.dumps(rows, ensure_ascii=False, indent=1))
        else:
            for row in rows:
                print("%s · cites %s · tabs %s" % (
                    row["id"], ", ".join(row["cites"]) or "nothing",
                    ", ".join(row["tabs"]) or "none"))
        return 0
    questions = None
    if args.graph:
        graph = cli.load_graph(args.graph)
        if graph is None:
            return 1
        questions = {q.id for q in graph.questions}
    findings = line.check(doc, questions)
    for finding in findings:
        print(finding.line())
    print("rows %d · admissions %d · errors %d · warnings %d" % (
        len(doc.rows()), len(doc.admissions()), len(line.errors(findings)),
        len(findings) - len(line.errors(findings))))
    return 1 if line.errors(findings) else 0


if __name__ == "__main__":
    sys.exit(main())
