#!/usr/bin/env python3
"""frontier.py <document read> <reads> [--json] — the frontier, off the page.

Prints every question of the author's that the AI answers, that has not
landed, and whose lineage has — each with its pressure, heaviest first. Ids
and numbers only: nothing of the notebook's text is printed. It reads the
document where it stands and needs no graph file, so any caller can ask it.

<reads> is a directory of saved ``search`` (or ``view``) results, or the files
themselves, each named ``<question>.json`` or ``<question>.<anything>.json``
(or ``.xml``) for the tab it is of — several per tab are taken together. Per
tab of the author's, a search for `` · `` finds the question line and every
answer's line, and a search for ``▸ `` every term; nothing reads a body whole.
Every tab of the author's must be read. Refuses (exit 1) a missing tab, a tab
with no question line, and a block that does not hash to the ``h`` the
document printed.

`next.py` is the other reading of the same relation: the heaviest question
with nothing left to wait on, threads included, from a graph
file built out of every tab read whole. This is what the page says at a
glance; that is what a turn may be put to.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Dict, List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hypo import cli, frontier  # noqa: E402
from hypo.appline import Refused  # noqa: E402

cli.quiet_pipe()


def _reads(paths: List[str]) -> Dict[str, List[str]]:
    """question -> the reads of its tab, by the files' names."""
    files: List[str] = []
    for path in paths:
        if os.path.isdir(path):
            files.extend(os.path.join(path, f) for f in sorted(os.listdir(path))
                         if f.endswith((".json", ".xml")))
        else:
            files.append(path)
    out: Dict[str, List[str]] = {}
    for path in files:
        name = os.path.basename(path).rsplit(".", 1)[0].split(".", 1)[0]
        with open(path, encoding="utf-8") as fh:
            out.setdefault(name, []).append(fh.read())
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("manifest", help="the document read, as JSON")
    ap.add_argument("reads", nargs="+", help="saved reads, or directories of them")
    ap.add_argument("--json", action="store_true", dest="as_json",
                    help="print the frontier as JSON")
    args = ap.parse_args(argv)

    try:
        with open(args.manifest, encoding="utf-8") as fh:
            manifest = json.load(fh)
        rows = frontier.frontier(frontier.graph(manifest, _reads(args.reads)))
    except (OSError, ValueError) as exc:
        print("ERROR %s" % exc, file=sys.stderr)
        return 1
    except Refused as exc:
        print("REFUSED %s" % exc, file=sys.stderr)
        return 1

    if args.as_json:
        print(json.dumps({"frontier": [{"question": q, "pressure": p} for q, p in rows]},
                         indent=2))
        return 0
    if not rows:
        print("nothing is on the frontier", file=sys.stderr)
    width = max([len(q) for q, _ in rows] + [1])
    for qid, pressure in rows:
        print("%-*s  %4d" % (width, qid, pressure))
    return 0


if __name__ == "__main__":
    sys.exit(main())
