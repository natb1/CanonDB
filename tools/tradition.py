#!/usr/bin/env python3
"""tradition.py rows … — the rows that record the readings of tradition given in a round, as notes.

    rows READINGS --after ID --node NODE --sitting YYYY-MM-DD --op-id OP
                                   a rows file for the recorder: one entry,
                                   one insert after block ID on the tab whose
                                   node id is NODE, holding one note per
                                   reading, joined by a blank line, in the
                                   file's order

READINGS is a JSON file (`-` for stdin) holding a list of objects
`{"party": ..., "position": ...}`, each a reading given on the page. Each note
reads `> pending: a tradition reading given in the sitting of <date>, a lead,
not verified against the source and owed to a tab of its party: <party>:
<position>`. ID is the last block of the section the notes go under, as
`inplace.py note insert` takes it. The document takes no second insert after
one block, so the notes are one insert. Refuses (exit 1, one `REFUSED:` line)
an empty list, a reading with an empty party or position, a party or position
that breaks a line, a date not of the form YYYY-MM-DD, and a note the reader
would not take back as written. Nothing here reaches the network or writes
the notebook.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hypo import cli, tradition  # noqa: E402
from hypo.appline import Refused  # noqa: E402

cli.quiet_pipe()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0], epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="mode", required=True)
    p = sub.add_parser("rows")
    p.add_argument("readings", help="the readings, a JSON list; - for stdin")
    p.add_argument("--after", required=True, metavar="ID")
    p.add_argument("--node", required=True)
    p.add_argument("--sitting", required=True, metavar="YYYY-MM-DD")
    p.add_argument("--op-id", required=True, metavar="OP")
    args = ap.parse_args(argv)
    try:
        try:
            readings = json.loads(cli.source(args.readings))
        except ValueError as exc:
            raise Refused("%s is no JSON: %s" % (args.readings, exc))
        out = tradition.rows(readings, args.after, args.node, args.sitting, args.op_id)
    except (Refused, OSError) as exc:
        print("REFUSED: %s" % exc, file=sys.stderr)
        return 1
    print(json.dumps(out, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
