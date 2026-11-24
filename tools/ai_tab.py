#!/usr/bin/env python3
"""ai_tab.py root|tab|add … — the tabs of the AI's own record: the batch that makes one, and the key that names them.

    root --name NAME [--order ORDER] [--under-tab TAB] [--content FILE]
                                   the batch that makes the AI's root, as the
                                   connector's `batch` arguments with its opId,
                                   for the speaker to send once; refused once the
                                   key ai_root names a root
    tab --parent NODE --name NAME [--order ORDER] [--content FILE]
                                   a rows entry for the ai-recorder: the batch
                                   that makes a tab under the AI's tab whose node
                                   id is NODE, with the entry's node and op_id
    add --node NODE --tab TAB [--parent NODE]
                                   put a tab just made in the key ai_root of the
                                   notebook file: the root where no --parent is
                                   given, which the key must not yet name, else a
                                   tab under a tab the key lists

NODE is the node id of a tab's body, the id an `update` names; TAB is the
tab's own id, the one a tab is nested under. Both are in the batch's answer,
under its aliases: `n` the body's node, `f` the tab. A tab's NAME is a
question's id, and it names neither the user nor anything private. ORDER
defaults to a0. A new tab holds its heading alone unless --content gives the
markdown of its body. The notebook file is the nearest
`.principal/notebook.json` from the working directory, or --notebook. Only
`add` writes a file; nothing here reaches the network or writes the notebook.
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
    p.add_argument("--under-tab", metavar="TAB", help="the tab id the root is nested under")
    p.add_argument("--content", metavar="FILE", help="the markdown of the root's body")
    p = sub.add_parser("tab")
    p.add_argument("--parent", required=True, metavar="NODE")
    p.add_argument("--name", required=True)
    p.add_argument("--order", default="a0")
    p.add_argument("--content", metavar="FILE", help="the markdown of the tab's body")
    p = sub.add_parser("add")
    p.add_argument("--node", required=True)
    p.add_argument("--tab", required=True)
    p.add_argument("--parent", metavar="NODE")
    args = ap.parse_args(argv)
    try:
        path = args.notebook or ai_tab.find(os.getcwd())
        named = ai_tab.load(path)
        content = None
        if getattr(args, "content", None):
            with open(args.content, encoding="utf-8") as fh:
                content = fh.read()
        if args.mode == "root":
            out = ai_tab.root(named, args.name, args.order, args.under_tab, content)
        elif args.mode == "tab":
            out = ai_tab.tab(named, args.parent, args.name, args.order, content)
        else:
            ai_tab.write(path, ai_tab.add(named, args.node, args.tab, args.parent))
            print("%s: %s now lists %d tab(s)" % (path, ai_tab.KEY,
                                                  len(ai_tab.entries(ai_tab.load(path)))))
            return 0
    except (ai_tab.Refused, OSError) as exc:
        print("REFUSED: %s" % exc, file=sys.stderr)
        return 1
    print(json.dumps(out, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
