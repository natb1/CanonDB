#!/usr/bin/env python3
"""due.py <graph.json> [--model NAME] [--backstop DAYS] [--project NAME] [--json] — what is due, and why.

Prints every reading the record says is due, by project: a landed answer
drawn again (with --model, the model answering now, read against git under
--root), a deadlocked clause a later draw gave way on, a pending note, a
suspended clause, a question past its backstop (with --backstop, in days),
and a root whose end reads an earlier project's root, whose rev at the
reading is not recorded. Each with the next step that would take it in. Ids
and reasons only: nothing of the notebook's text is printed beyond the words
a note or a clause opens with. Computed from the graph file and stored
nowhere.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hypo import again, cli, due  # noqa: E402
from read import notebook as read_notebook  # noqa: E402

cli.quiet_pipe()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("graph", help="the graph file")
    ap.add_argument("--model", help="the model answering now; with it, answers due again ride in")
    ap.add_argument("--root", default=".", help="the project root git reads canon under")
    ap.add_argument("--backstop", type=int, metavar="DAYS",
                    help="a question not amended within DAYS is due a reading")
    ap.add_argument("--today", metavar="YYYY-MM-DD", help="the day the backstop is read on")
    ap.add_argument("--project", metavar="NAME",
                    help="one project of a notebook that holds several (default: every project)")
    ap.add_argument("--json", action="store_true", dest="as_json")
    args = ap.parse_args(argv)

    graph = cli.load_graph(args.graph)
    if graph is None:
        return 1
    moved = None
    if args.model is not None:
        named = read_notebook(args.root)
        canon = named.get("canon") if isinstance(named.get("canon"), dict) else {}
        moved = again.git_moved(args.root, canon)
    try:
        today = date.fromisoformat(args.today) if args.today else None
    except ValueError:
        print("ERROR --today is not a date YYYY-MM-DD: %r" % args.today, file=sys.stderr)
        return 1
    rows = due.rows(graph, args.model, moved, args.backstop, today, args.project)
    if args.as_json:
        print(json.dumps([r._asdict() for r in rows], indent=2, ensure_ascii=False))
        return 0
    if not rows:
        print("nothing is due", file=sys.stderr)
        return 0
    for line in due.listing(rows):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
