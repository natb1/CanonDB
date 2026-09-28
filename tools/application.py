#!/usr/bin/env python3
"""application.py replace|insert|delete — write one application in place.

    application.py replace READ --block ID [--what T] [--link T] [--note T] [--standing S] [--clause T]
    application.py insert --after ID --name N --what T --thesis T --link T --standing S [--clause T] [--note T]
    application.py delete READ --heading ID --line ID

READ is a saved ``search`` or ``view`` result of the tab (the tool's JSON, or
its xml alone; `-` for stdin). Prints the ``ops`` of one prose ``update`` as
JSON; the old and new line go to stderr. Refuses (exit 1) a read whose block
does not hash to the ``h`` the document printed, a line that does not
round-trip through the renderer, or a standing outside the vocabulary.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hypo import appline, cli  # noqa: E402

cli.quiet_pipe()

FIELDS = ("what", "link", "note", "standing", "clause", "thesis")


def _source(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="mode", required=True)
    rep = sub.add_parser("replace")
    rep.add_argument("read")
    rep.add_argument("--block", required=True)
    ins = sub.add_parser("insert")
    ins.add_argument("--after", required=True)
    ins.add_argument("--name", required=True)
    for p in (rep, ins):
        for f in FIELDS:
            p.add_argument("--" + f)
    dele = sub.add_parser("delete")
    dele.add_argument("read")
    dele.add_argument("--heading", required=True)
    dele.add_argument("--line", required=True)
    args = ap.parse_args(argv)

    try:
        if args.mode == "replace":
            fields = appline.read_line(_source(args.read), args.block)
            old = appline.line(fields)
            for f in FIELDS:
                if getattr(args, f) is not None:
                    fields[f] = getattr(args, f)
            ops = [appline.replace_op(fields)]
            print("old: %s\nnew: %s" % (old, appline.line(fields)), file=sys.stderr)
        elif args.mode == "insert":
            missing = [f for f in ("what", "thesis", "link", "standing")
                       if getattr(args, f) is None]
            if missing:
                raise appline.Refused("insert needs --" + ", --".join(missing))
            fields = {f: getattr(args, f) or "" for f in FIELDS}
            ops = [appline.insert_op(args.after, args.name, fields)]
            print("new: %s" % appline.line(fields), file=sys.stderr)
        else:
            ops = appline.delete_ops(_source(args.read), args.heading, args.line)
    except appline.Refused as exc:
        print("REFUSED %s" % exc, file=sys.stderr)
        return 1
    print(json.dumps({"ops": ops}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
