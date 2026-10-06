#!/usr/bin/env python3
"""Assemble a graph file from exported tabs and the document's file list.

The document is the source of truth, and this is how it is read: export each
tab as markdown, put the files in a directory named for their questions, and
hand this the document read that lists the tabs. What the markdown carries is
parsed; what belongs to the document rather than the page — a tab's id, its
body's id, and the order from which a tradition root is told — comes from that
list.

A dictation that touches a few tabs need not read the rest. With `--scope`
naming the questions it touches, the directory holds those tabs and their
ancestors and nothing else, and the graph file says so: it records the scope,
and `check.py` holds over it every rule that does not need a tab outside it.
The ancestors are supplied, never assumed — a tab whose header list names a
raiser whose tab is not in the directory is refused, since every rule that
reads over the lineage would read over a gap.

The enum the states point at is in neither the document read nor the exports,
so `--state-enum ID` names it, and a rebuild over an existing graph file keeps
the one that file holds rather than dropping it — dropped, every state would
render as a word rather than a dropdown, and no gate can see the difference.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Optional, Sequence

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hypo import cli, model, read, render  # noqa: E402

cli.quiet_pipe()


class OutOfScope(Exception):
    """A scoped read that is missing a tab it cannot do without."""


class Stray(Exception):
    """An export whose name is no tab's: misnamed, it would be left out of
    the graph in silence, and the tab it was meant for with it."""


def assemble(manifest: dict, bodies: dict, scope: Sequence[str] = ()) -> dict:
    """The graph file, from a document read and a question id to markdown map.

    ``scope`` names the questions a partial read is for; every one of them,
    and every raiser a read tab's header list names, must be among
    ``bodies``, or ``OutOfScope`` says which is not.
    """
    value = manifest.get("value", manifest)
    tabs = value.get("tabs", {})
    files = {f["id"]: f for f in manifest.get("files", [])}
    names = {tab_id: meta.get("name", tab_id) for tab_id, meta in tabs.items()}
    ids = {render.chip_key(name): name for name in names.values()}
    party = read.parties(tabs)

    missing = [qid for qid in scope if qid not in bodies]
    if missing:
        raise OutOfScope("no tab read for %s, which the scope names"
                         % ", ".join(missing))
    stray = sorted(set(bodies) - set(names.values()))
    if stray:
        raise Stray("%s.md names no tab of the document" % ".md, ".join(stray))
    questions = []
    # as text, as ``read.parties`` takes the same fields: an order the document
    # reports as a number would otherwise not sort beside the others
    for tab_id, meta in sorted(tabs.items(), key=lambda kv: (str(kv[1].get("order", "")),
                                                             str(kv[1].get("name", "")))):
        name = meta.get("name", tab_id)
        if name not in bodies:
            continue
        q = read.parse_tab(bodies[name], ids)
        # projected from the parents' terms, never stored; over a scope it is
        # what says an ancestor's tab is missing, which nothing else can
        incoming = q.pop("incoming", None) or []
        if scope:
            absent = sorted({src for _, src in incoming if src and src not in bodies})
            if absent:
                raise OutOfScope("%s is raised on %s, whose tab was not read; a "
                                 "scoped read takes the ancestors of every tab it "
                                 "reads" % (q["id"], ", ".join(absent)))
        q["tab"] = tab_id
        q["body"] = files.get(tab_id, {}).get("content", {}).get("id", "")
        q["party"] = party.get(tab_id, model.AUTHOR)
        questions.append(q)

    graph = {"artifact": manifest.get("frame", {}).get("artifactUrl", "")}
    graph["questions"] = questions
    if scope:
        graph["scope"] = list(scope)
    return graph


def notebook_enum(root: str = ".") -> str:
    """The enum ``.principal/notebook.json`` names at the project's root,
    which is where the tools are run from; empty where there is none."""
    try:
        with open(os.path.join(root, ".principal", "notebook.json"), encoding="utf-8") as fh:
            return str(json.load(fh).get("state_enum") or "")
    except (OSError, ValueError):
        return ""


def kept(path: Optional[str]) -> str:
    """The `state_enum` of the graph file this read is about to rewrite.

    The document read names the tabs and the artifact, and the exports carry
    the words; the enum the states point at is in neither. It is the document's
    — set from it once, as the skill says — and a rebuild keeps it from the
    file it replaces, rather than retyped on every run.
    """
    if not path:
        return ""
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh).get("state_enum") or ""
    except (OSError, ValueError):
        return ""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("manifest", help="the document read, as JSON")
    ap.add_argument("tabs", help="a directory of <question id>.md exports")
    ap.add_argument("-o", "--out", help="write here instead of stdout")
    ap.add_argument("--state-enum", metavar="ID", dest="state_enum",
                    help="the document enum the states point at (else the one "
                         ".principal/notebook.json names, else kept from the "
                         "graph file being rewritten)")
    ap.add_argument("--scope", nargs="+", metavar="QUESTION", default=[],
                    help="the questions a dictation touches; the directory holds "
                         "their tabs and their ancestors'")
    args = ap.parse_args(argv)

    try:
        with open(args.manifest, encoding="utf-8") as fh:
            manifest = json.load(fh)
    except (OSError, ValueError) as exc:
        print("ERROR manifest: %s" % exc, file=sys.stderr)
        return 1

    try:
        bodies = cli.exports(args.tabs)
    except OSError as exc:
        print("ERROR tabs: %s" % exc, file=sys.stderr)
        return 1
    if not bodies:
        print("ERROR no .md exports in %s" % args.tabs, file=sys.stderr)
        return 1

    try:
        graph = assemble(manifest, bodies, args.scope)
    except read.ParseError as exc:
        print("ERROR parse: %s" % exc, file=sys.stderr)
        return 1
    except OutOfScope as exc:
        print("ERROR scope: %s" % exc, file=sys.stderr)
        return 1
    except Stray as exc:
        print("ERROR exports: %s" % exc, file=sys.stderr)
        return 1

    # the enum, from the flag, else from the project's notebook.json, else as
    # the file being rewritten held it: a graph without one renders every
    # state as a word, and a body write then puts words where the page had
    # its dropdowns
    enum, whence = args.state_enum, ""
    if not enum:
        enum, whence = notebook_enum(), " (state_enum from .principal/notebook.json)"
    if not enum:
        enum, whence = kept(args.out), " (state_enum kept)"
    if enum:
        graph["state_enum"] = enum
    else:
        whence = ""

    text = json.dumps(graph, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print("%d questions -> %s%s" % (len(graph["questions"]), args.out, whence))
    else:
        sys.stdout.write(text)
        return 0

    # a shape problem here is the parser's, and worth saying at once
    return 0 if cli.load_graph(args.out) is not None else 1


if __name__ == "__main__":
    sys.exit(main())
