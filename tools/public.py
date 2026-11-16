#!/usr/bin/env python3
"""public.py check <graph.json> | question <graph.json> <file> | copy <graph.json> -o DIR --salt-file FILE — the copy of the notebook that may be shown.

``check`` lists what could have carried masked words into what the copy
shows, a question or a marked section that repeats a run of them or a masked
tab's address, and exits 2 where there is one; a likeness between an answer
of Claude's and a masked node is listed and fails nothing, since it is
agreement. ``question`` holds a
question drafted for Claude to the same rule before it is put: it is public
with everything in it. ``copy`` writes the copy, ``graph.json`` and one page
a node, and writes nothing where ``check`` would fail. Claude's graph is
shown whole; of the user's, a node is shown only where its tab carries a
note opening with the word public. The salt names the masked nodes and is
the user's to keep: the same salt gives the same names, and without it a
name cannot be matched to a tab.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hypo import cli, public  # noqa: E402

cli.quiet_pipe()


def _report(found, salt: str) -> None:
    for leak in found:
        print("%s quotes a masked node (%s): \"%s …\""
              % (leak.shown, public.stub(leak.masked, salt) if salt else leak.masked,
                 leak.words))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="mode", required=True)
    p = sub.add_parser("check")
    p.add_argument("graph")
    p = sub.add_parser("question")
    p.add_argument("graph")
    p.add_argument("file", help="the drafted question, or - for stdin")
    p = sub.add_parser("copy")
    p.add_argument("graph")
    p.add_argument("-o", "--out", required=True, metavar="DIR")
    p.add_argument("--salt-file", required=True, metavar="FILE")
    args = ap.parse_args(argv)
    graph = cli.load_graph(args.graph)
    if graph is None:
        return 1
    if args.mode == "question":
        drafted = sys.stdin.read() if args.file == "-" else open(args.file, encoding="utf-8").read()
        found = public.question(graph, drafted)
        _report(found, "")
        if not found:
            print("the question quotes nothing masked; what it presupposes is still to be read")
        return 2 if found else 0
    found = public.leaks(graph)
    alike = public.similar(graph)
    for leak in alike:
        print("%s, an answer of Claude's, is like a masked node (%s): \"%s …\"; no leak, "
              "the answer having been given with nothing of the user's in the turn"
              % (leak.shown, leak.masked, leak.words))
    if args.mode == "check":
        _report(found, "")
        if not found:
            print("nothing masked could have reached what is shown")
        return 2 if found else 0
    if found:
        _report(found, "")
        print("no copy written", file=sys.stderr)
        return 2
    with open(args.salt_file, encoding="utf-8") as fh:
        salt = fh.read().strip()
    if len(salt) < 16:
        print("the salt is too short to keep a name from being guessed", file=sys.stderr)
        return 1
    made = public.copy(graph, salt)
    os.makedirs(os.path.join(args.out, "nodes"), exist_ok=True)
    with open(os.path.join(args.out, "graph.json"), "w", encoding="utf-8") as fh:
        json.dump(made, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    for node in made["nodes"]:
        with open(os.path.join(args.out, "nodes", "%s.md" % node["id"]), "w",
                  encoding="utf-8") as fh:
            fh.write(public.page(node))
    shown = sum(1 for n in made["nodes"] if not n["masked"])
    print("%d nodes, %d shown, %d masked, %d edges"
          % (len(made["nodes"]), shown, len(made["nodes"]) - shown, len(made["edges"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
