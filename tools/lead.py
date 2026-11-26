#!/usr/bin/env python3
"""lead.py job | record | led | aside — the reading of whether a question drafted on the user's side leads, and its record.

    job --question FILE --id ID --notebook ADDR
        The jobs file of one `lead` job, for `board.py add`: the job ID,
        tier full, its inputs the notebook's address, the question's path
        and the SHA-256 of the question as it stands. Refused for a text
        already read (one reading for one text, whether its record stands
        beside it or was set aside), for a question whose record says it
        leads (final for that number: set it aside first), and once three
        drafts of the question were set aside as leading: it is then put to
        the principal that the question could not be drafted without
        leading.

    record --question FILE --board DIR --versions FILE --job ID -o FILE [--session ID]
        The record of one `lead` job's reading of the question's file, which
        `clean_turn.py answer --lead` demands of a question put on the
        principal's approval and `card.py check` of a review that shows it.
        DIR and --versions are an export of the board, taken after the job
        was marked done. Written only where the job is on the board, of the
        kind `lead`, done by the coordinator, its inputs this file and the
        SHA-256 of the file as it stands; its result names a reply whose
        SHA-256 is the result's fingerprint; the reply is three lines,
        `verdict: leads` or `verdict: does not lead`, `reason: <one line>`
        and `status: ok`; the plugin's hooks recorded, under the session's
        id, a launch of `principal:question-reader` described by the job's
        id inside the job's time on the board, and the start and end of the
        helper it ran (the one the launch's return named, or, where none
        was named, the start its row was given, with no other launch of the
        kind made between) before the job was marked done; the clock reads
        no earlier than the job's mark of done; and `job`'s refusals do not
        apply. The record holds the question's SHA-256, the verdict, the
        time from the clock as `read`, the job's id, the reply's SHA-256 and
        the helper's run, never the reason. Exit 0 where the verdict is
        `does not lead`, 2 where it is `leads` (the record is written all
        the same), 1 on a refusal. A refusal leaves whatever stood at FILE
        as it stood; a record is written beside it and renamed into place.
        Where the hooks attest no run, the job is not run again: a new
        `lead` job, under a new id, is added for the question.

    led --question FILE -o FILE
        A record with the verdict `leads` and no reading behind it, for a
        question found later to have led all the same.

    aside --line DIR --from N
        Set aside question N, recorded as leading, with every later question
        of the line, whose packets carried its answer, and every drawer turn
        whose packet carried any of them: all moved together under
        `DIR/held/<k>/`, nothing renumbered and nothing removed, so that the
        line reads on from N without a gap and a newly drafted question is
        put at N. Prints what was set aside and which of it had an answer
        placed in the AI's record.

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
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hypo import board, brief, cli, inhand, lead  # noqa: E402

cli.quiet_pipe()

PLUGIN = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      ".claude-plugin", "plugin.json")


def _plugin() -> str:
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
    p = sub.add_parser("job")
    p.add_argument("--question", required=True)
    p.add_argument("--id", required=True, dest="jid", metavar="ID")
    p.add_argument("--notebook", required=True, metavar="ADDR")
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
    p = sub.add_parser("aside")
    p.add_argument("--line", required=True, metavar="DIR")
    p.add_argument("--from", required=True, dest="start", metavar="N")
    args = ap.parse_args(argv)
    try:
        if args.mode == "job":
            print(json.dumps(lead.job(args.question, args.jid, args.notebook), indent=1))
            return 0
        if args.mode == "aside":
            moved = lead.aside(args.line, args.start)
            print("set aside under %s: question(s) %s%s" % (
                moved["held"], ", ".join(map(str, moved["questions"])),
                "; drawer turn(s) %s" % ", ".join(moved["drawn"]) if moved["drawn"] else ""))
            if moved["placed"]:
                print("placed in the AI's record, each carried as an open note of kind "
                      "change: question(s) %s" % ", ".join(map(str, moved["placed"])))
            print("%d of %d drafts of question %s set aside as leading%s" % (
                moved["led_drafts"], lead.DRAFTS, args.start,
                ": put it to the principal that it could not be drafted without leading"
                if moved["led_drafts"] >= lead.DRAFTS else ""))
            return 0
        if args.mode == "led":
            made = lead.led(args.question, lead.now())
        else:
            export = board.load(args.board, args.versions)
            made = lead.record(args.question, export, args.job, _launches(args.session),
                               _plugin(), lead.now())
        lead.write(args.out, made)
    except (lead.Refused, OSError) as exc:
        print("REFUSED: %s" % exc, file=sys.stderr)
        return 1
    print("%s: %s -> %s" % (made["verdict"], args.question, args.out))
    return 2 if made["verdict"] == lead.LEADS and args.mode == "record" else 0


if __name__ == "__main__":
    sys.exit(main())
