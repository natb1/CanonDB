#!/usr/bin/env python3
"""page.py <view file>... -o DIR — a tab's view read, as the markdown the reader takes.

Each file is a `view` read of one tab's body (the tool's JSON result, or its
xml alone), named `<question id>.<anything>`; `<question id>.md` is written
under DIR in the export's spelling, with `<question id>.rev` beside it holding the
rev the read answered with, so `read.py`, `verify.py` and `relink.py`
take the directory as they took a directory of exports. Nothing is exported.

With `--outlines DIR`, each read is also written there as `<question id>.xml`,
the outline `apply.py --outlines` takes: every id whole and the retired
blocks left out, the rev kept on it as the write's guard. One read serves
the reader and the writer.
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
    ap.add_argument("--outlines", metavar="DIR",
                    help="also write each read as <question id>.xml, the outline apply.py takes")
    args = ap.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)
    if args.outlines:
        os.makedirs(args.outlines, exist_ok=True)
    failed = 0
    for path in args.views:
        qid = cli.question_of(path)
        try:
            with open(path, encoding="utf-8") as fh:
                source = fh.read()
            text = page.markdown(source)
            stamp = page.rev(source)
            shape = page.outline(source) if args.outlines else None
        except Exception as exc:  # a view that is not one is said, not skipped
            print("ERROR %s: %s" % (path, exc), file=sys.stderr)
            failed += 1
            continue
        target = os.path.join(args.out, qid + ".md")
        with open(target, "w", encoding="utf-8") as fh:
            fh.write(text)
        if stamp is not None:
            # the bookmark read.py keeps on the question, for the freshness check
            with open(os.path.join(args.out, qid + ".rev"), "w", encoding="utf-8") as fh:
                fh.write("%d\n" % stamp)
        if shape is not None:
            with open(os.path.join(args.outlines, qid + ".xml"), "w", encoding="utf-8") as fh:
                fh.write(shape)
        print("%s: %d bytes" % (target, len(text.encode("utf-8"))), file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
