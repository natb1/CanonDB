#!/usr/bin/env python3
"""inplace.py <part> <mode> — write one line-shaped part of a tab in place.

    inplace.py glossary insert --after ID --word W --body T [--open-section]
    inplace.py glossary replace READ --heading ID --block ID --body T
    inplace.py glossary delete READ --heading ID --block ID [--block ID ...]
    inplace.py term insert --after ID --title T --to Q --to-tab TAB --anchor A [--anchor A ...]
                           [--thesis-read READ --thesis ID] [--open-section]
    inplace.py term delete READ --heading ID --block ID [--block ID ...]
    inplace.py incoming insert READ --list ID --anchor A --from Q --from-tab TAB [--after-item ID]
    inplace.py incoming delete READ --list ID --item ID
    inplace.py thesis replace READ --block ID --text T [--anchor A ...]
    inplace.py hinge amend READ --block ID --date YYYY-MM-DD --by WHO --from WHAT

READ is a saved ``search`` or ``view`` result of the tab (the tool's JSON, or
its xml alone; `-` for stdin). Prints the ``ops`` of one prose ``update`` as
JSON, for the tab READ is of; the old and new text go to stderr, with what the
write leaves owed. Refuses (exit 1) a read whose block does not hash to the
``h`` the document printed, a part that would not read back as written, a
re-wording that cuts a chip or a marked run, and a term whose anchor is not a
verbatim run of the answer read with it. An application is ``application.py``'s.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hypo import cli, inplace  # noqa: E402
from hypo.appline import Refused  # noqa: E402

cli.quiet_pipe()


def _source(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parts = ap.add_subparsers(dest="part", required=True)

    glossary = parts.add_parser("glossary").add_subparsers(dest="mode", required=True)
    p = glossary.add_parser("insert")
    p.add_argument("--after", required=True)
    p.add_argument("--word", required=True)
    p.add_argument("--body", required=True)
    p.add_argument("--open-section", action="store_true",
                   help="open the tab's Glossary section with it")
    p = glossary.add_parser("replace")
    p.add_argument("read")
    p.add_argument("--heading", required=True)
    p.add_argument("--block", required=True)
    p.add_argument("--body", required=True)
    p = glossary.add_parser("delete")
    p.add_argument("read")
    p.add_argument("--heading", required=True)
    p.add_argument("--block", action="append", default=[])

    term = parts.add_parser("term").add_subparsers(dest="mode", required=True)
    p = term.add_parser("insert")
    p.add_argument("--after", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--to", required=True)
    p.add_argument("--to-tab", required=True, dest="to_tab")
    p.add_argument("--anchor", action="append", default=[])
    p.add_argument("--thesis-read", dest="thesis_read")
    p.add_argument("--thesis", help="the answer's paragraph the anchors stand in")
    p.add_argument("--open-section", action="store_true",
                   help="open the tab's Terms section with it")
    p = term.add_parser("delete")
    p.add_argument("read")
    p.add_argument("--heading", required=True)
    p.add_argument("--block", action="append", default=[])

    incoming = parts.add_parser("incoming").add_subparsers(dest="mode", required=True)
    p = incoming.add_parser("insert")
    p.add_argument("read")
    p.add_argument("--list", required=True, dest="header")
    p.add_argument("--anchor", required=True)
    p.add_argument("--from", required=True, dest="raiser")
    p.add_argument("--from-tab", required=True, dest="raiser_tab")
    p.add_argument("--after-item", dest="after_item")
    p = incoming.add_parser("delete")
    p.add_argument("read")
    p.add_argument("--list", required=True, dest="header")
    p.add_argument("--item", required=True)

    thesis = parts.add_parser("thesis").add_subparsers(dest="mode", required=True)
    p = thesis.add_parser("replace")
    p.add_argument("read")
    p.add_argument("--block", required=True)
    p.add_argument("--text", required=True)
    p.add_argument("--anchor", action="append", default=[],
                   help="an anchor of a term on this answer, which must still stand")

    hinge = parts.add_parser("hinge").add_subparsers(dest="mode", required=True)
    p = hinge.add_parser("amend")
    p.add_argument("read")
    p.add_argument("--block", required=True)
    p.add_argument("--date", required=True)
    p.add_argument("--by", required=True)
    p.add_argument("--from", required=True, dest="origin")
    return ap


def _ops(args) -> list:
    """The operations, with what they replace and what they leave owed said
    on stderr."""
    say = lambda text: print(text, file=sys.stderr)  # noqa: E731
    part, mode = args.part, args.mode
    if part == "glossary" and mode == "insert":
        ops, content = inplace.glossary_insert(args.after, args.word, args.body,
                                               args.open_section)
        say("new: %s" % content)
        say("owed: the links from the answer's uses of the word to the entry")
        return ops
    if part == "glossary" and mode == "replace":
        ops, old, new = inplace.glossary_replace(_source(args.read), args.heading,
                                                 args.block, args.body)
        say("old: %s\nnew: %s" % (old, new))
        return ops
    if part == "glossary" and mode == "delete":
        return inplace.glossary_delete(_source(args.read), args.heading, args.block)
    if part == "term" and mode == "insert":
        thesis = None
        if args.thesis:
            if not args.thesis_read:
                raise Refused("--thesis names a block of --thesis-read")
            thesis = inplace.thesis_text(_source(args.thesis_read), args.thesis)
        ops, content = inplace.term_insert(args.after, args.title, args.to, args.to_tab,
                                           args.anchor, thesis, args.open_section)
        say("new: %s" % content)
        if thesis is None:
            say("unchecked: no answer was read with it, so the anchors were not "
                "held against its words")
        say("owed: the chip after each anchor in the answer, its item on %s's "
            "header list (incoming insert), and the links to the term" % args.to)
        return ops
    if part == "term" and mode == "delete":
        return inplace.term_delete(_source(args.read), args.heading, args.block)
    if part == "incoming" and mode == "insert":
        ops, line = inplace.incoming_insert(_source(args.read), args.header, args.anchor,
                                            args.raiser, args.raiser_tab, args.after_item)
        say("new: %s" % line)
        say("owed: the link on the anchor back to the term on %s" % args.raiser)
        return ops
    if part == "incoming" and mode == "delete":
        return inplace.incoming_delete(_source(args.read), args.header, args.item)
    if part == "thesis" and mode == "replace":
        ops, old, new = inplace.thesis_replace(_source(args.read), args.block,
                                               args.text, args.anchor)
        say("old: %s\nnew: %s" % (old, new))
        return ops
    if part == "hinge" and mode == "amend":
        ops, old, new = inplace.hinge_amend(_source(args.read), args.block, args.date,
                                            args.by, args.origin)
        say("old: %s\nnew: %s" % (old, new))
        return ops
    raise Refused("no %s %s" % (part, mode))  # pragma: no cover - argparse decides


def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    try:
        ops = _ops(args)
    except Refused as exc:
        print("REFUSED %s" % exc, file=sys.stderr)
        return 1
    print(json.dumps({"ops": ops}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
