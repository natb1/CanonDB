#!/usr/bin/env python3
"""hinges.py place|rows|unjustified … — the AI's presuppositions placed as hinges, and the unjustified ones listed.

    place DIR --n N [--under ID] [--line-name NAME]
                                   for question N of the line in DIR, its answer
                                   of record (the first kept draw, checked as a
                                   packet checks it): the question, the answer word
                                   for word, what it rests on, and each line of its
                                   ``Presupposes:`` as a hinge marked unjustified,
                                   naming the question it came in by, and the
                                   hinge's thesis part from the draw, as JSON;
                                   the line's name is NAME, or DIR's own name
    rows PLACE --line DIR --line-name NAME --node NODE --kind KIND --read VIEW
                                   the rows file the ai-recorder sends unchanged
                                   to place what `place` printed (the file PLACE)
                                   on the AI's tab whose body's node id is NODE:
                                   a list of one entry, one update of three
                                   inserts at the tab's end, the question and its
                                   line, the answer word for word in a code block
                                   as an insert of its own, and the hinge, guarded
                                   by the rev of VIEW, a whole read of that tab
                                   showing its heading alone; NAME the line's
                                   name, KIND the question's kind
    unjustified GRAPH
                                   every unjustified hinge of the AI's graph, with
                                   the builds that cite an answer resting on it

A hinge is justified only by a later answer of the AI's own that it is
linked to: its line ends ``(justified by <question id>)``. ``place`` refuses
an answer whose presuppositions are not one a line under the label, a
question of the line not yet answered, and a draw that is not the one
``clean_turn.py`` wrote. ``rows`` opens the line's directory and prints
nothing unless PLACE is what ``place`` prints from it for the question PLACE
names, under the line's name NAME (a directory named otherwise is named by
``place --line-name``); it refuses a node the key ai_root does not list, a
read that shows the tab holding more than its heading, and a text a code
block cannot hold as it stands, saying why, and never alters one. The key
ai_root is read from the notebook file the guard reads, or --notebook.
Nothing of the user's record is read. Nothing here reaches the network or
writes the notebook.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hypo import ai_tab, cli, hinges  # noqa: E402

cli.quiet_pipe()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0], epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="mode", required=True)
    p = sub.add_parser("place")
    p.add_argument("line", help="the line's directory, $SCRATCH/lines/<line>")
    p.add_argument("--n", type=int, required=True, help="the question's number on the line")
    p.add_argument("--under", metavar="ID", help="the tab of the AI's the line stands under")
    p.add_argument("--line-name", metavar="NAME",
                   help="the line's name, where its directory is not named for it")
    p = sub.add_parser("rows")
    p.add_argument("place", help="what place printed, a file")
    p.add_argument("--line", required=True, metavar="DIR", help="the line's directory")
    p.add_argument("--line-name", required=True, metavar="NAME", help="the line's name")
    p.add_argument("--node", required=True, metavar="NODE",
                   help="the node id of the AI's tab's body, which the key ai_root lists")
    p.add_argument("--kind", required=True, choices=hinges.KINDS,
                   help="the question's kind")
    p.add_argument("--read", required=True, metavar="VIEW",
                   help="a whole view read of the tab, showing its heading alone")
    p.add_argument("--notebook", metavar="FILE",
                   help="the notebook file, else the nearest .principal/notebook.json")
    p = sub.add_parser("unjustified")
    p.add_argument("graph")
    args = ap.parse_args(argv)
    if args.mode == "rows":
        return rows(args)
    if args.mode == "unjustified":
        graph = cli.load_graph(args.graph)
        if graph is None:
            return 1
        found = hinges.unjustified(graph)
        print(json.dumps(found, indent=1, ensure_ascii=False))
        print("%d unjustified hinge(s)" % len(found), file=sys.stderr)
        return 0
    try:
        out = placed(args.line, args.n, args.under, args.line_name)
    except hinges.Refused as exc:
        print("REFUSED: %s" % exc, file=sys.stderr)
        return 1
    print(json.dumps(out, indent=1, ensure_ascii=False))
    return 0


def placed(line: str, n: int, under, line_name) -> dict:
    """What ``place`` prints for question ``n`` of the line in ``line``."""
    import packet
    try:
        pairs, carried = packet.line(line)
        if n < 1 or n > len(pairs):
            raise hinges.Refused("the line holds no answered question %d" % n)
        question, answer = pairs[n - 1]
        draw = os.path.join(line, str(n), "draws", carried[n - 1]["draw"])
        with open(draw, encoding="utf-8") as fh:
            model = json.load(fh).get("model")
    except packet.Refused as exc:
        raise hinges.Refused(str(exc)) from exc
    name = line_name or os.path.basename(os.path.normpath(line))
    return hinges.place(question, answer, name, n, under,
                        model if isinstance(model, str) else None)


def rows(args) -> int:
    """The rows file that places a checked place on a blank tab of the AI's."""
    from hypo import page
    try:
        path = args.notebook or ai_tab.find(os.getcwd())
        listed = [n for n, _ in ai_tab.entries(ai_tab.load(path))]
        try:
            with open(args.place, encoding="utf-8") as fh:
                given = json.load(fh)
        except ValueError as exc:
            raise hinges.Refused("the place is no JSON: %s" % exc) from exc
        line_name, n = hinges.came_in_by(given)
        if line_name != args.line_name:
            raise hinges.Refused("the place names the line %r and this is the line %r: a "
                                 "directory not named for its line is named by place "
                                 "--line-name" % (line_name, args.line_name))
        under = given.get("under")
        if under is not None and not isinstance(under, str):
            raise hinges.Refused("the place's under is not a tab's name")
        if placed(args.line, n, under, args.line_name) != given:
            raise hinges.Refused("the place is not what place prints from the line's directory "
                                 "for question %d" % n)
        with open(args.read, encoding="utf-8") as fh:
            view = fh.read()
        try:
            shown = page.blocks(view)
            rev = page.rev(view)
            root = page.ET.fromstring(page.view_xml(view))
        except (ValueError, page.ET.ParseError) as exc:
            raise hinges.Refused("the tab's read is not a whole view: %s" % exc) from exc
        if root.get("node") and root.get("node").lower() != args.node.lower():
            raise hinges.Refused("the read is of the node %r, not %r"
                                 % (root.get("node"), args.node))
        hinges.blank_tab(shown)
        out = hinges.rows(given, args.node, args.kind, listed, rev)
    except (hinges.Refused, ai_tab.Refused, OSError) as exc:
        print("REFUSED: %s" % exc, file=sys.stderr)
        return 1
    print(json.dumps(out, indent=1, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    sys.exit(main())
