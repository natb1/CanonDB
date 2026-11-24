#!/usr/bin/env python3
"""ai_tab.py root|tab|add … — the tabs of the AI's own record: the batch that makes one, and the key that names them.

    root --name NAME [--order ORDER]
                                   the batch that makes the AI's root at the top
                                   level, as the connector's `batch` arguments
                                   with its opId, for the speaker to send once;
                                   refused once the key ai_root names a root
    tab --parent NODE --name NAME [--order ORDER]
                                   a rows entry for the ai-recorder: the batch
                                   that makes a tab under the AI's tab whose node
                                   id is NODE, with the entry's node and op_id
    add --made FILE --answer FILE
                                   put a tab just made in the key ai_root of the
                                   notebook file: FILE what `root` or `tab`
                                   printed, which must be what they print from
                                   the key as it stands now, and the connector's
                                   answer to that batch, whose ids for the
                                   aliases f (the tab) and n (its body) go in

NODE is the node id of a tab's body, the id an `update` names; the tab's own
id is the one a tab is nested under. A tab's NAME is a question's id, and it
names neither the user nor anything private. ORDER defaults to a0. A new tab
holds its heading alone; what it says is inserted on it after. The notebook
file is the one the guard reads, under CLAUDE_PROJECT_DIR, else the nearest
`.principal/notebook.json` from the working directory, or --notebook. Only
`add` writes a file, and it prints what it could not check: that the ids are
the ones the connector made. Nothing here reaches the network or writes the
notebook.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hypo import ai_tab, cli  # noqa: E402

cli.quiet_pipe()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0], epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--notebook", metavar="FILE",
                    help="the notebook file, else the nearest .principal/notebook.json")
    sub = ap.add_subparsers(dest="mode", required=True)
    p = sub.add_parser("root")
    p.add_argument("--name", required=True)
    p.add_argument("--order", default="a0")
    p = sub.add_parser("tab")
    p.add_argument("--parent", required=True, metavar="NODE")
    p.add_argument("--name", required=True)
    p.add_argument("--order", default="a0")
    p = sub.add_parser("add")
    p.add_argument("--made", required=True, metavar="FILE",
                   help="what root or tab printed")
    p.add_argument("--answer", required=True, metavar="FILE",
                   help="the connector's answer to that batch")
    args = ap.parse_args(argv)
    try:
        path = args.notebook or ai_tab.find(os.getcwd())
        named = ai_tab.load(path)
        if args.mode == "root":
            out = ai_tab.root(named, args.name, args.order)
        elif args.mode == "tab":
            out = ai_tab.tab(named, args.parent, args.name, args.order)
        else:
            parts = []
            for name in (args.made, args.answer):
                try:
                    with open(name, encoding="utf-8") as fh:
                        parts.append(json.load(fh))
                except ValueError as exc:
                    raise ai_tab.Refused("%s is no JSON: %s" % (name, exc)) from exc
            named, unchecked = ai_tab.add(named, *parts)
            ai_tab.write(path, named)
            print("%s: %s now lists %d tab(s)" % (path, ai_tab.KEY, len(ai_tab.entries(named))))
            print(unchecked)
            return 0
    except (ai_tab.Refused, OSError) as exc:
        print("REFUSED: %s" % exc, file=sys.stderr)
        return 1
    print(json.dumps(out, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
