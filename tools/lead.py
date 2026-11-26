#!/usr/bin/env python3
"""lead.py record | led — the record that a question drafted on the user's side was read for whether it leads.

    record --question FILE --board DIR --versions FILE --job ID -o FILE [--session ID]
        The record of one `lead` job's reading of the question's file, which
        `clean_turn.py answer --lead` demands of a question put on the
        principal's approval. DIR and --versions are an export of the board,
        taken after the job was marked done. Written only where the job is
        on the board, of the kind `lead`, done by the coordinator, its inputs
        this file and the SHA-256 of the file as it stands; its result names
        a reply whose SHA-256 is the result's fingerprint; the reply is
        three lines, `verdict: leads` or `verdict: does not lead`, `reason:
        <one line>` and `status: ok`; the plugin's hooks recorded, under the
        session's id, a launch of `principal:question-reader` described by
        the job's id, started and ended, inside the job's time on the board;
        and the clock reads no earlier than the job's mark of done. The
        record holds the question's SHA-256, the verdict, the time from the
        clock as `read`, the job's id, the reply's SHA-256 and the launch as
        the hooks recorded it, never the reason. Exit 0 where the verdict is
        `does not lead`, 2 where it is `leads` (the record is written all
        the same, and the clean turn refuses it), 1 on a refusal, which
        leaves no record: a record already at FILE is removed first.

    led --question FILE -o FILE
        A record with the verdict `leads` and no reading behind it, for a
        question found later to have led all the same: `packet.py` then
        refuses to carry the question's draws, and the clean turn to put it.

`--session` defaults to `$CLAUDE_CODE_SESSION_ID`, the id the harness gives
the session's shell and its hooks alike; the hooks' record is found as
`inhand.py` finds the session's list, in the brief's directory of the
project the cwd stands in. Whether the question leads is the reader's
reading, and nothing here reads it. The records are plain files: each binds
a check to an exact text and catches drift, and one written by hand with the
right hashes passes.
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hypo import board, brief, cli, inhand, lead  # noqa: E402

cli.quiet_pipe()

PLUGIN = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      ".claude-plugin", "plugin.json")


def _plugin() -> str:
    import json
    try:
        with open(PLUGIN, encoding="utf-8-sig") as fh:
            name = json.load(fh).get("name")
    except (OSError, ValueError, AttributeError):
        name = None
    return name if isinstance(name, str) and name else "principal"


def _launches(session) -> list:
    root = brief.project_root(os.getcwd(), os.environ)
    if not root:
        raise lead.Refused("no project here whose hooks keep a record of the helpers")
    try:
        where = brief.brief_dir(root, os.environ)
    except brief.Refused as exc:
        raise lead.Refused(exc.args[0][0])
    if not inhand.session_dir(where, session):
        raise lead.Refused("the session's id is not known (--session)")
    return inhand.launches(where, session)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0], epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="mode", required=True)
    p = sub.add_parser("record")
    p.add_argument("--question", required=True)
    p.add_argument("--board", required=True, metavar="DIR")
    p.add_argument("--versions", required=True)
    p.add_argument("--job", required=True, metavar="ID")
    p.add_argument("-o", "--out", required=True, metavar="FILE")
    p.add_argument("--session", default=os.environ.get("CLAUDE_CODE_SESSION_ID"))
    p = sub.add_parser("led")
    p.add_argument("--question", required=True)
    p.add_argument("-o", "--out", required=True, metavar="FILE")
    args = ap.parse_args(argv)
    try:
        os.unlink(args.out)
    except FileNotFoundError:
        pass
    except OSError as exc:
        print("REFUSED: the record at %s cannot be removed: %s" % (args.out, exc),
              file=sys.stderr)
        return 1
    try:
        if args.mode == "led":
            made = lead.led(args.question, lead.now())
        else:
            export = board.load(args.board, args.versions)
            made = lead.record(args.question, export, args.job, _launches(args.session),
                               _plugin(), lead.now())
    except lead.Refused as exc:
        print("REFUSED: %s" % exc, file=sys.stderr)
        return 1
    lead.write(args.out, made)
    print("%s: %s -> %s" % (made["verdict"], args.question, args.out))
    return 2 if made["verdict"] == lead.LEADS and args.mode == "record" else 0


if __name__ == "__main__":
    sys.exit(main())
