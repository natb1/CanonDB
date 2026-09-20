"""Assemble a graph file from exported tabs and the document's file list.

The document is the source of truth, and this is how it is read: export each
tab as markdown, put the files in a directory named for their questions, and
hand this the document read that lists the tabs. What the markdown carries is
parsed; what belongs to the document rather than the page — a tab's id, its
body's id, and the order from which a tradition root is told — comes from that
list.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Dict, Optional, Set

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:  # a tool piped into head should stop, not traceback
    import signal
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
except (ImportError, AttributeError, ValueError):  # pragma: no cover - not POSIX
    pass

from hypo import model, read, render  # noqa: E402


def assemble(manifest: dict, bodies: dict) -> dict:
    """The graph file, from a document read and a question id to markdown map."""
    value = manifest.get("value", manifest)
    tabs = value.get("tabs", {})
    files = {f["id"]: f for f in manifest.get("files", [])}
    names = {tab_id: meta.get("name", tab_id) for tab_id, meta in tabs.items()}
    ids = {render.chip_key(name): name for name in names.values()}

    # A question belongs to a party. The author's are the main tree; another
    # party's is that party's own notebook, placed at top level in the b
    # series, and anything nested under it is theirs too — a reconstruction
    # may raise its own questions and answer them.
    party_of: Dict[str, str] = {}
    for tab_id, meta in tabs.items():
        if not meta.get("subtabOf") and str(meta.get("order", "")).startswith("b"):
            party_of[tab_id] = str(meta.get("name", tab_id)).lower()

    def party(tab_id: str, seen: Optional[Set[str]] = None) -> str:
        seen = seen or set()
        if tab_id in party_of:
            return party_of[tab_id]
        parent = tabs.get(tab_id, {}).get("subtabOf")
        if not parent or parent in seen:
            return model.AUTHOR
        return party(parent, seen | {tab_id})

    questions = []
    for tab_id, meta in sorted(tabs.items(), key=lambda kv: (kv[1].get("order", ""),
                                                             kv[1].get("name", ""))):
        name = meta.get("name", tab_id)
        if name not in bodies:
            continue
        q = read.parse_tab(bodies[name], ids)
        q.pop("incoming", None)  # projected from the parents' terms, never stored
        q["tab"] = tab_id
        q["body"] = files.get(tab_id, {}).get("content", {}).get("id", "")
        q["party"] = party(tab_id)
        questions.append(q)

    # requires is rendered as the title a reader sees; the id it names is found
    # among the inbox items of every tab, which is why this needs all of them
    by_title = {item["title"]: item["id"]
                for q in questions for item in q.get("inbox", [])}
    for q in questions:
        q["requires"] = [by_title.get(want, want) for want in q.get("requires", [])]

    graph = {"artifact": manifest.get("frame", {}).get("artifactUrl", "")}
    graph["questions"] = questions
    return graph


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("manifest", help="the document read, as JSON")
    ap.add_argument("tabs", help="a directory of <question id>.md exports")
    ap.add_argument("-o", "--out", help="write here instead of stdout")
    args = ap.parse_args(argv)

    try:
        with open(args.manifest, encoding="utf-8") as fh:
            manifest = json.load(fh)
    except (OSError, ValueError) as exc:
        print("ERROR manifest: %s" % exc, file=sys.stderr)
        return 1

    bodies = {}
    for entry in sorted(os.listdir(args.tabs)):
        if entry.endswith(".md"):
            with open(os.path.join(args.tabs, entry), encoding="utf-8") as fh:
                bodies[entry[:-3]] = fh.read()
    if not bodies:
        print("ERROR no .md exports in %s" % args.tabs, file=sys.stderr)
        return 1

    try:
        graph = assemble(manifest, bodies)
    except read.ParseError as exc:
        print("ERROR parse: %s" % exc, file=sys.stderr)
        return 1

    text = json.dumps(graph, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print("%d questions -> %s" % (len(graph["questions"]), args.out))
    else:
        sys.stdout.write(text)

    try:  # a shape problem here is the parser's, and worth saying at once
        model.load(args.out) if args.out else None
    except model.ShapeError as exc:
        for problem in exc.problems:
            print("ERROR shape: %s" % problem, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
