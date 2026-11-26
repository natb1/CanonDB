#!/usr/bin/env python3
"""public.py check <graph.json> | question <graph.json> <file> | mark <graph.json> <question> <section>... | copy <graph.json> -o DIR --salt-file FILE — the copy of the notebook that may be shown.

``check`` lists what could have carried masked words into what the copy
shows, a question that repeats a run of them or a masked tab's address, and
exits 2 where there is one; a likeness between an answer of Claude's and a
masked node is listed and fails nothing, since it is agreement; a likeness
between a section the user marked and a masked tab is listed for the user to
consider, and ``copy`` waits for ``--considered``. ``question`` holds a
question drafted for Claude, before it is put, to what a script can decide
of it: it spells no masked tab's address, and it keeps the notebook's rule
for naming the user (``user-named``, the one ``check.py`` holds the
notebook's own words to), saying what it found. It looks for no run of
masked words: whether a question hands the answerer the user's record is a
reading of its meaning, which the ``question-reader`` kind makes and
``lead.py record`` records. With ``--record FILE`` a question that passes
leaves the record ``clean_turn.py answer --leak`` takes, the SHA-256 of
exactly the bytes checked and of the graph, and one that fails leaves none:
a record already at FILE is removed before the check. The record binds the
check to an exact text and graph and catches drift; it is a plain file, and
one written by hand with the right hashes passes. ``copy`` writes the copy, ``graph.json`` and one page
a node, and writes nothing where ``check`` would fail. Claude's graph is
shown whole; of the user's, a node is shown only where its tab carries a
note opening with the word public. ``mark`` prints the words of a mark over the sections named, as they read
now, for the user to put on the tab as a note: everything is masked until it
is explicitly unmasked, and a mark covers the words it was made over, so a
section changed since is masked again and every mode says so. The salt names
the masked nodes and is
the user's to keep: the same salt gives the same names, and without it a
name cannot be matched to a tab.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hypo import cli, public, spec  # noqa: E402

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
    p.add_argument("--record", metavar="FILE",
                   help="where the question passes, write here the record clean_turn.py "
                        "takes as --leak: the SHA-256 of exactly the text checked and "
                        "of the graph")
    p = sub.add_parser("mark")
    p.add_argument("graph")
    p.add_argument("question")
    p.add_argument("sections", nargs="+", metavar="SECTION")
    p = sub.add_parser("copy")
    p.add_argument("graph")
    p.add_argument("-o", "--out", required=True, metavar="DIR")
    p.add_argument("--salt-file", required=True, metavar="FILE")
    p.add_argument("--considered", action="store_true",
                   help="the user has considered every likeness between a marked "
                        "section and a masked tab")
    args = ap.parse_args(argv)
    graph = cli.load_graph(args.graph)
    if graph is None:
        return 1
    if args.mode == "mark":
        q = graph.by_id().get(args.question)
        unknown = [n for n in args.sections if n not in public.SECTIONS]
        if q is None or unknown:
            print("no such question" if q is None else
                  "no such section: %s (one of %s)" % (", ".join(unknown),
                                                       ", ".join(public.SECTIONS)),
                  file=sys.stderr)
            return 1
        print(public.mark(q, args.sections))
        return 0
    for q in graph.questions:
        for name in public.lapsed(q):
            print("%s: the mark on %s no longer matches what the section says, or gives no "
                  "fingerprint; masked until marked again" % (q.id, name))
    if args.mode == "question":
        if args.record:
            # a record stands only for a pass over exactly these bytes: one
            # left from an earlier pass is taken away before the check
            try:
                os.unlink(args.record)
            except FileNotFoundError:
                pass
        raw = (sys.stdin.buffer.read() if args.file == "-"
               else open(args.file, "rb").read())
        drafted = raw.decode("utf-8")
        found = public.addresses(graph, drafted)
        _report(found, "")
        named = spec.not_the_user(drafted)
        if named:
            print("the question says %r where it means the user: the notebook's rule "
                  "(user-named) names the one it is kept for the user" % named)
        if not found and not named:
            print("the question spells no masked tab's address and names the user as the "
                  "notebook does; whether it leads the answerer, and what it presupposes, are "
                  "still to be read")
            if args.record:
                with open(args.graph, "rb") as fh:
                    graph_sha = hashlib.sha256(fh.read()).hexdigest()
                with open(args.record, "w", encoding="utf-8") as fh:
                    json.dump({"tool": "public.py question", "exit": 0,
                               "sha256": hashlib.sha256(raw).hexdigest(),
                               "graph_sha256": graph_sha}, fh, indent=2)
                    fh.write("\n")
        return 2 if found or named else 0
    found = public.leaks(graph)
    alike = public.similar(graph)
    for leak in alike:
        print("%s, an answer of Claude's, is like a masked node (%s): \"%s …\"; no leak, "
              "the answer having been given with nothing of the user's in the turn"
              % (leak.shown, leak.masked, leak.words))
    weigh = public.consider(graph)
    for leak in weigh:
        print("%s, which the user marked, is like a masked node (%s): \"%s …\"; to be "
              "considered: an accidental mark, or the same words in two contexts"
              % (leak.shown, leak.masked, leak.words))
    if args.mode == "check":
        _report(found, "")
        if not found:
            print("nothing masked could have reached what is shown")
        return 2 if found else 0
    if weigh and not args.considered:
        print("no copy written: say --considered once the user has considered each "
              "likeness above", file=sys.stderr)
        return 2
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
