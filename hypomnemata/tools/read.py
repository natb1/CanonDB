"""Assemble a graph file from exported tabs and the document's file list.

The document is the source of truth, and this is how it is read: export each
tab as markdown, put the files in a directory named for their questions, and
hand this the document read that lists the tabs. What the markdown carries is
parsed; what belongs to the document rather than the page — a tab's id, its
body's id, and the order from which a tradition root is told — comes from that
list.

Every complete read re-seals the envelope committed at the branch root, because
this is the only tool that learns what the notebook now says: the export cache
moves with the notebook rather than in the runs somebody remembered to move it.
It costs no extra call and one line of output, and it declines — out loud —
rather than seal a partial read. `--no-seal` turns it off; `--envelope` seals
over a named file instead of the committed one.
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

from hypo import model, portable, read, render, spec  # noqa: E402


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


def uncovered(manifest: dict, bodies: dict) -> list:
    """The tabs the document lists that the exports on disk do not carry.

    `assemble` skips them, quietly and correctly — a read of some tabs is a
    graph of those questions. What it cannot say is whether that was meant, and
    the envelope is where the difference matters: sealing a partial read hands
    the other party a notebook with the rest cut out of it.
    """
    value = manifest.get("value", manifest)
    tabs = value.get("tabs", {})
    return sorted(meta.get("name", tab_id) for tab_id, meta in tabs.items()
                  if meta.get("name", tab_id) not in bodies)


def carry(graph: model.Graph, envelope: str, absent: list) -> None:
    """Put the graph into the committed envelope, or say why it was not.

    Refusing is the common case and has to read as a decision rather than a
    silence, so every path here prints exactly one line. None of them prints a
    value out of the notebook: what moved is named by id, bounded, and the rest
    is `git diff`.
    """
    name = os.path.basename(envelope)
    if absent:
        print("not sealed over %s: the read left out %d tab(s): %s"
              % (name, len(absent), portable.named(absent)), file=sys.stderr)
        return
    blocking = spec.errors(spec.run(graph))
    if blocking:
        print("not sealed over %s: the checker reports %d error(s) — check.py "
              "says which" % (name, len(blocking)), file=sys.stderr)
        return
    gone = portable.dropped(graph, envelope)
    if gone:
        print("not sealed over %s: it would drop %d question(s): %s — "
              "`portable.py reseal --force` if that is the change"
              % (name, len(gone), portable.named(gone)), file=sys.stderr)
        return
    try:
        changed = portable.reseal(graph, envelope)
    except (OSError, ValueError) as exc:
        print("not sealed over %s: %s" % (name, exc), file=sys.stderr)
        return
    if not changed:
        print("%s is current" % name, file=sys.stderr)
        return
    print("re-sealed %s: %s" % (name, "; ".join(changed)), file=sys.stderr)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("manifest", help="the document read, as JSON")
    ap.add_argument("tabs", help="a directory of <question id>.md exports")
    ap.add_argument("-o", "--out", help="write here instead of stdout")
    ap.add_argument("--envelope", metavar="FILE",
                    help="seal over this envelope instead of the committed one")
    ap.add_argument("--no-seal", action="store_true", dest="no_seal",
                    help="leave the committed envelope alone")
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

    if not args.out:  # sealing needs a graph on disk, and stdout is not one
        return 0

    try:  # a shape problem here is the parser's, and worth saying at once
        built = model.load(args.out)
    except model.ShapeError as exc:
        for problem in exc.problems:
            print("ERROR shape: %s" % problem, file=sys.stderr)
        return 1

    if not args.no_seal:
        envelope = args.envelope or portable.committed(portable.root())
        if envelope:
            carry(built, envelope, uncovered(manifest, bodies))
    return 0


if __name__ == "__main__":
    sys.exit(main())
