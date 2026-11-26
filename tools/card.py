#!/usr/bin/env python3
"""card.py check UPDATE — refuse a write of the page's ordo/current that the page would not draw as meant.

    check UPDATE                   read the object about to be written to
                                   ordo/current (a JSON file, `-` for stdin),
                                   whole or a partial update holding any of
                                   next, context, queue and updated; print
                                   `ok`, or refuse

Refuses (exit 1, one `REFUSED:` line per finding on standard error):
an entry of `context.for` or `context.against` that is not an object with a
non-empty string `who` and `text`; a `context.prediction` that is not an
object, or holds a key other than `predicted`, `diverged` and `addressed`, or
a value that is not a string or a list of strings; a `context.paragraphs` or
`context.notes` that is not a list of strings (a plain string there draws
nothing); a `context.heading` that is not a string; a `paragraphs` of a
`context.log` record that is not a string or a list of strings; a
`context.log` record without `at`; a `context.at`, a log record's `at`,
`next.put_at`, `next.resolved_at` or `updated` that is not an ISO time with
its offset; a write without `updated`; a `next` holding a field the card
draws (`kind`, `prompt`, `case`, `line`, `recommendation`, `how`, `put_at`)
without `kind` and `prompt`; a `kind` of `next` or of a queue entry outside
question, office, work and review; a recommendation that is not a string or a
list of strings; a `question` carrying a recommendation, and a `question` or
`review` carrying a `how`; a `queue` that is not a list of objects each with
a `title` or a `prompt`; a `next.deferred` that is not an object with a
`prompt`; an `office_deferred` whose `since` is not an ISO time with its
offset or whose `bell` is not HHMM; a `background` that is not a list of
strings; and a `next.reading`, the absolute path of the `lead.json` of a
question for the AI's own record that a review shows, that is given on any
kind but a review, cannot be read with the question's `question.md` beside
it, was not written by `lead.py record`, is of another text than that file,
does not say `does not lead`, or whose question is not the prompt word for
word (white space aside). A
`next` holding only `resolved_at`, `asks`, `deferred` or deletion markers
needs no kind or prompt. The deletion marker `{"__delete__": true}` is taken
wherever a field may be removed. Nothing here reaches the network or writes the page.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hypo import card, cli  # noqa: E402

cli.quiet_pipe()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0], epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="mode", required=True)
    p = sub.add_parser("check")
    p.add_argument("update", help="the object about to be written; - for stdin")
    args = ap.parse_args(argv)
    try:
        update = json.loads(cli.source(args.update))
    except (OSError, ValueError) as exc:
        print("REFUSED: %s cannot be read as JSON: %s" % (args.update, exc), file=sys.stderr)
        return 1
    findings = card.check(update)
    for finding in findings:
        print("REFUSED: %s" % finding, file=sys.stderr)
    if findings:
        return 1
    print("ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
