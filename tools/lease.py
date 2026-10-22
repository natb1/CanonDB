#!/usr/bin/env python3
"""lease.py take|check|release|pin <lease tab view> — the notebook's lease and pin.

A run that writes a section or a body, changes the specification or sends the
tab patch holds a lease while it does. Read the lease tab (a `view`, sinceRev
0) and:

    lease.py take <view> --scope <project|all> --session <id> --entry <entry point>
        prints the ops that put this session's line under ## Leases; send them,
        read the tab again, then
    lease.py check <view> --session <id>
        exits 0 when no overlapping line stands above this session's, 1 naming
        the ones that do (take the line off and wait), 2 when there is none;
    lease.py release <view> --session <id>
        prints the ops that take the line off;
    lease.py pin <view> [--write <commit> --session <id>]
        prints the commit the notebook was last written with, or the op that
        names this tooling instead.

Every whole-block op is guarded by the block's h and the view's rev. Nothing
here writes.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hypo import cli, lease  # noqa: E402

cli.quiet_pipe()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("action", choices=("take", "check", "release", "pin"))
    ap.add_argument("view", help="a whole view read of the lease tab, or - for stdin")
    ap.add_argument("--scope", help="the project the run writes, or all")
    ap.add_argument("--session", help="the session taking or holding the lease")
    ap.add_argument("--entry", help="the entry point that runs, e.g. /principal:dictate")
    ap.add_argument("--write", metavar="COMMIT", help="with pin: name this commit")
    ap.add_argument("--when", help="the time to stamp (default: now, UTC)")
    args = ap.parse_args(argv)

    source = cli.source(args.view)
    when = args.when or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    try:
        if args.action == "take":
            if not (args.scope and args.session and args.entry):
                ap.error("take needs --scope, --session and --entry")
            print(json.dumps({"ops": lease.take(source, args.scope, args.session,
                                                args.entry, when)}, indent=2, ensure_ascii=False))
            return 0
        if args.action == "check":
            if not args.session:
                ap.error("check needs --session")
            found = lease.ahead(source, args.session)
            if found is None:
                print("no lease line for %s" % args.session, file=sys.stderr)
                return 2
            if found:
                for l in found:
                    print("held: %s" % l.block.text)
                return 1
            print("held by %s" % args.session, file=sys.stderr)
            return 0
        if args.action == "release":
            if not args.session:
                ap.error("release needs --session")
            print(json.dumps({"ops": lease.release(source, args.session)}, indent=2,
                             ensure_ascii=False))
            return 0
        if args.write:
            if not args.session:
                ap.error("pin --write needs --session")
            print(json.dumps({"ops": lease.pin_ops(source, args.write, args.session, when)},
                             indent=2, ensure_ascii=False))
            return 0
        found = lease.pin(source)
        if found is None:
            print("the notebook names no tooling", file=sys.stderr)
            return 1
        print(found)
        return 0
    except (ValueError, ET.ParseError) as exc:
        print("ERROR %s is not a read of the lease tab: %s" % (args.view, exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
