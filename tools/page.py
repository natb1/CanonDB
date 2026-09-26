#!/usr/bin/env python3
"""page.py <view file>... -o DIR — a tab's view read, as the markdown the reader takes.

Each file is a `view` read of one tab's body (the tool's JSON result, or its
xml alone), named `<question id>.<anything>`; `<question id>.md` is written
under DIR in the export's spelling, so `read.py`, `verify.py` and `relink.py`
take the directory as they took a directory of exports. Nothing is exported.
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hypo import cli, page  # noqa: E402

cli.quiet_pipe()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("views", nargs="+", help="view reads, one per tab, named <question id>.*")
    ap.add_argument("-o", "--out", required=True, metavar="DIR", help="where the .md files go")
    args = ap.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)
    failed = 0
    for path in args.views:
        qid = os.path.splitext(os.path.basename(path))[0]
        try:
            with open(path, encoding="utf-8") as fh:
                text = page.markdown(fh.read())
        except Exception as exc:  # a view that is not one is said, not skipped
            print("ERROR %s: %s" % (path, exc), file=sys.stderr)
            failed += 1
            continue
        target = os.path.join(args.out, qid + ".md")
        with open(target, "w", encoding="utf-8") as fh:
            fh.write(text)
        print("%s: %d bytes" % (target, len(text.encode("utf-8"))), file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
