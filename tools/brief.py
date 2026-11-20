#!/usr/bin/env python3
"""brief.py standing|neighbourhood|for-prompt|check|install|where — the notebook kept in front of a session.

    brief.py standing GRAPH [--side all|ai] [--lines DIR] [--at T] [-o FILE]
    brief.py neighbourhood GRAPH --line ID... [--side all|ai] [--lines DIR] [--at T] [-o FILE]
    brief.py for-prompt FILE --graph GRAPH [--side all|ai] [--at T]
    brief.py check FILE --graph GRAPH [--line ID...]
    brief.py install GRAPH --line ID... [--lines DIR] [--at T]
    brief.py where

`standing` prints the standing brief: the conventions, each project's end
and method, the open lines by title (from an export of the page's `lines`,
`--lines`), and the glossary index. `neighbourhood` prints, for the line in
hand (question ids, tab ids, or open lines' ids, whose anchors name their
tabs), each principle's lineage from the root, its own answer, the glossary
entries of the terms in play, the tradition on it and the sentences that
share its terms. `--side ai` restricts either to the AI's own answers, for a
context that must stay blind to the user's graph; `--side all`, the default,
reads the user's, the AI's and the tradition parties'. Each is cut to its
maximum (`--max`: standing 14,000 characters, neighbourhood 10,000) by the
fixed order `hypo/brief.py` states, whole sentences or nothing, and with
`-o FILE` a manifest is written beside it, `FILE.manifest.json`, naming by
id everything left out; the ceiling of the two together, `--ceiling`, is
32,000. Every output opens with the same header: record, not instruction;
cite by id; only the conventions bind; this copy supersedes any earlier
one; and the stamp, the graph's SHA-256, the line and the time `--at`
gives, so that the same inputs give the same bytes.

`for-prompt` prints a helper's own brief: the standing brief and the
neighbourhood of the questions its delegation prompt names, or of those that
fix the terms it uses. `check` says whether an output is stale against a
graph (and a line): `fresh` and exit 0, else what moved and exit 1.

`install` writes the session's brief where the harness loads it from, the
brief's directory, `where` prints: under the user's Claude configuration
(`$CLAUDE_CONFIG_DIR`, else `~/.claude`), at
`principal/brief/<the project's path, every character but a letter or digit
made ->`, outside every repository, so that no `git add` reaches it and no
public checkout holds a sentence of the notebook. It copies the graph there
(the hooks read it to brief a helper and to check a text as it leaves),
records the graph's source path, and writes `standing.md` and
`neighbourhood.md` with their manifests. The conventions are the tabs the
key `conventions` of `.principal/notebook.json` names, else a tab called
`conventions`, and `--conventions` names others. Exit 1 on a refusal.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hypo import brief, cli  # noqa: E402
from hypo import lines as hlines  # noqa: E402

cli.quiet_pipe()


def _lines(directory):
    if not directory:
        return None
    return hlines.read(directory).records


def _write(out, path):
    if not path:
        sys.stdout.write(out.text)
        return
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(out.text)
    with open(path + ".manifest.json", "w", encoding="utf-8") as fh:
        json.dump(out.manifest, fh, indent=1, sort_keys=True)
        fh.write("\n")
    print("%d character(s), %d left out -> %s" % (len(out.text),
                                                  len(out.manifest["left_out"]), path),
          file=sys.stderr)


def _conventions(graph, named):
    root = brief.project_root(os.getcwd(), os.environ)
    return brief.conventions_of(graph, named or brief.notebook_conventions(root))


def _common(p, line=False):
    p.add_argument("--side", choices=brief.SIDES, default="all")
    p.add_argument("--lines", metavar="DIR", help="an export of the page's lines")
    p.add_argument("--at", metavar="T", help="the time the stamp carries")
    p.add_argument("--conventions", nargs="+", metavar="ID",
                   help="the tabs stating the conventions")
    p.add_argument("--ceiling", type=int, default=brief.CEILING)
    if line:
        p.add_argument("--line", nargs="+", required=True, metavar="ID")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="mode", required=True)
    p = sub.add_parser("standing")
    p.add_argument("graph")
    _common(p)
    p.add_argument("--max", type=int, default=brief.STANDING_MAX)
    p.add_argument("-o", "--out", metavar="FILE")
    p = sub.add_parser("neighbourhood")
    p.add_argument("graph")
    _common(p, line=True)
    p.add_argument("--max", type=int, default=brief.NEIGHBOURHOOD_MAX)
    p.add_argument("-o", "--out", metavar="FILE")
    p = sub.add_parser("for-prompt")
    p.add_argument("file", help="the delegation prompt, or - for stdin")
    p.add_argument("--graph", required=True)
    _common(p)
    p.add_argument("--standing-max", type=int, default=brief.STANDING_MAX)
    p.add_argument("--neighbourhood-max", type=int, default=brief.NEIGHBOURHOOD_MAX)
    p = sub.add_parser("check")
    p.add_argument("file")
    p.add_argument("--graph", required=True)
    p.add_argument("--line", nargs="+", metavar="ID")
    p.add_argument("--lines", metavar="DIR")
    p = sub.add_parser("install")
    p.add_argument("graph")
    _common(p, line=True)
    p.add_argument("--standing-max", type=int, default=brief.STANDING_MAX)
    p.add_argument("--neighbourhood-max", type=int, default=brief.NEIGHBOURHOOD_MAX)
    sub.add_parser("where")
    args = ap.parse_args(argv)
    try:
        return _run(args)
    except brief.Refused as exc:
        for problem in exc.args[0]:
            print("REFUSED: %s" % problem, file=sys.stderr)
        return 1


def _dir():
    root = brief.project_root(os.getcwd(), os.environ)
    if not root:
        raise brief.Refused(["no .principal/notebook.json stands here or above, so there is "
                             "no project to brief"])
    return brief.brief_dir(root, os.environ)


def _run(args) -> int:
    if args.mode == "where":
        print(_dir())
        return 0
    if args.mode == "check":
        graph = cli.load_graph(args.graph)
        if graph is None:
            return 1
        with open(args.file, encoding="utf-8") as fh:
            words = fh.read()
        line = None
        if args.line:
            line = brief.resolve(graph, args.line, _lines(args.lines))
        found = brief.stale(words, brief.fingerprint(args.graph), line)
        if found:
            for f in found:
                print("stale: %s" % f)
            return 1
        print("fresh")
        return 0
    path = args.graph if args.mode != "for-prompt" else args.graph
    graph = cli.load_graph(path)
    if graph is None:
        return 1
    digest = brief.fingerprint(path)
    records = _lines(args.lines)
    conventions = _conventions(graph, args.conventions)
    if args.mode == "standing":
        _write(brief.standing(graph, digest, args.side, args.at, records, conventions,
                              args.max, args.ceiling), args.out)
        return 0
    if args.mode == "neighbourhood":
        line = brief.resolve(graph, args.line, records)
        _write(brief.neighbourhood(graph, digest, line, args.side, args.at, args.max),
               args.out)
        return 0
    if args.mode == "for-prompt":
        prompt = cli.source(args.file)
        words, _ = brief.for_prompt(graph, digest, prompt, args.side, args.at, records,
                                    conventions, args.standing_max, args.neighbourhood_max,
                                    args.ceiling)
        sys.stdout.write(words)
        return 0
    # install
    line = brief.resolve(graph, args.line, records)
    first = brief.standing(graph, digest, args.side, args.at, records, conventions,
                           args.standing_max, args.ceiling)
    second = brief.neighbourhood(graph, digest, line, args.side, args.at,
                                 args.neighbourhood_max)
    if len(first.text) + len(second.text) > args.ceiling:
        raise brief.Refused(["the brief and the neighbourhood hold %d characters, over the "
                             "ceiling of %d" % (len(first.text) + len(second.text),
                                                args.ceiling)])
    where = _dir()
    os.makedirs(where, mode=0o700, exist_ok=True)
    os.chmod(where, 0o700)
    copy = os.path.join(where, brief.FILES["graph"])
    if os.path.realpath(path) != os.path.realpath(copy):
        shutil.copyfile(path, copy + ".tmp")
        os.replace(copy + ".tmp", copy)
    with open(os.path.join(where, brief.FILES["source"]), "w", encoding="utf-8") as fh:
        json.dump({"graph": os.path.realpath(path), "sha256": digest, "line": line,
                   "side": args.side, "at": args.at, "conventions": conventions,
                   "lines": os.path.realpath(args.lines) if args.lines else None}, fh,
                  indent=1, sort_keys=True)
        fh.write("\n")
    _write(first, os.path.join(where, brief.FILES["standing"]))
    _write(second, os.path.join(where, brief.FILES["neighbourhood"]))
    for name in os.listdir(where):
        if os.path.isfile(os.path.join(where, name)):
            os.chmod(os.path.join(where, name), 0o600)
    print(where)
    return 0


if __name__ == "__main__":
    sys.exit(main())
