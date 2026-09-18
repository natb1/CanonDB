#!/usr/bin/env python3
"""render.py -- render a hypomnemata node (or the whole tree) as doc-entry markdown.

The main thread transcribes this output into the published doc; the shape is
fixed by hypomnemata/SPEC.md. Priority and ready come from pressure.py.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pressure
from pressure import DEFAULT_NODES, GraphError, as_list, cell, num, table

HINGE_KEYS = ("model", "harness", "canon_sha", "presuppositions")


def flat(value):
    """One line of text: block scalars collapse to single spaces."""
    if value is None:
        return ""
    return " ".join(str(value).split())


def block(value):
    return str(value).strip("\n").rstrip() if value else ""


def hinge_lines(graph, nid):
    node = graph.nodes[nid]
    hinge = node.get("hinge") or {}
    parent = node.get("parent")
    out = []
    if isinstance(parent, str) and parent in graph.nodes:
        out.append("- inherits %s" % parent)
    keys = [k for k in HINGE_KEYS if k in hinge] + [k for k in hinge if k not in HINGE_KEYS]
    for key in keys:
        value = hinge[key]
        if isinstance(value, list):
            out.append("- %s:" % key)
            for item in value:
                out.append("  - %s" % flat(item))
        else:
            out.append("- %s: %s" % (key, flat(value)))
    return out


def postulate_note(postulate):
    if postulate.get("decided_not_to_examine"):
        return "decided not to examine"
    return postulate.get("note")


def render_node(graph, nid):
    node = graph.nodes[nid]
    state = node.get("state")
    out = []

    if node.get("stub"):
        out.append("### %s · stub · %s" % (nid, flat(node.get("q"))))
        thesis = block(node.get("thesis"))
        if thesis:
            out += ["", thesis]
        return "\n".join(out) + "\n"

    header = "### %s · %s" % (nid, state)
    if node.get("canon"):
        header += " · canon: %s" % flat(node.get("canon"))
    out.append(header)
    out += ["", "**Q** %s" % flat(node.get("q"))]
    thesis = block(node.get("thesis"))
    if thesis:
        out += ["", thesis]

    defs = [d for d in as_list(node.get("defs")) if isinstance(d, dict)]
    if defs:
        out += ["", "**Defines**", ""]
        out += table(["term", "sense"],
                     [[cell(d.get("term")), cell(d.get("sense"))] for d in defs])

    if node.get("hinge"):
        out += ["", "**Hinge**", ""]
        out += hinge_lines(graph, nid)

    postulates = [p for p in as_list(node.get("postulates")) if isinstance(p, dict)]
    if postulates:
        out += ["", "**Postulates**", ""]
        out += table(["id", "claim", "rests on", "discharged by", "note"],
                     [[cell(p.get("id")), cell(p.get("claim")), cell(as_list(p.get("rests_on"))),
                       cell(p.get("discharge")), cell(postulate_note(p))] for p in postulates])

    terms = [t for t in as_list(node.get("terms")) if isinstance(t, dict)]
    if terms:
        out += ["", "**Terms**", ""]
        out += table(["id", "clause", "group", "state", "child"],
                     [[cell(t.get("id")), cell(t.get("clause")), cell(t.get("group")),
                       cell(t.get("state")), cell(t.get("child"))] for t in terms])

    followups = [(nid, f["id"]) for f in as_list(node.get("followups"))
                 if isinstance(f, dict) and isinstance(f.get("id"), str)]
    if followups:
        out += ["", "**Follow-ups**", ""]
        rows = []
        for key in followups:
            fu = graph.followups[key]
            rows.append([cell(fu.get("id")), cell(flat(fu.get("q"))), cell(fu.get("kind")),
                         cell(fu.get("term")), cell(fu.get("toward")),
                         cell(as_list(fu.get("requires"))), cell(as_list(fu.get("after"))),
                         num(graph.priority(key)), "yes" if graph.ready(key) else "no"])
        out += table(["id", "q", "kind", "term", "toward", "requires", "after",
                      "priority", "ready"], rows)
        drafts = [key for key in followups if flat(graph.followups[key].get("draft"))]
        if drafts:
            out.append("")
            for key in drafts:
                out.append("> **draft %s** — %s" % (key[1], flat(graph.followups[key].get("draft"))))

    actions = [a for a in as_list(node.get("actions")) if isinstance(a, dict)]
    if actions:
        out += ["", "**Actions**", ""]
        out += table(["id", "kind", "what", "obligation", "done"],
                     [[cell(a.get("id")), cell(a.get("kind")), cell(a.get("what")),
                       cell(a.get("obligation")), "yes" if a.get("done") else "no"]
                      for a in actions])

    traditions = [t for t in as_list(node.get("traditions")) if isinstance(t, dict)]
    if traditions:
        out += ["", "**Traditions**", ""]
        out += table(["name", "relation", "note"],
                     [[cell(t.get("name")), cell(t.get("relation")), cell(t.get("note"))]
                      for t in traditions])

    return "\n".join(out) + "\n"


def render(graph, ids):
    return "\n".join(render_node(graph, nid) for nid in ids)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Render hypomnemata nodes as doc markdown.")
    parser.add_argument("ids", nargs="*", help="node ids to render")
    parser.add_argument("--all", action="store_true", help="every node, tree order")
    parser.add_argument("--nodes", default=str(DEFAULT_NODES), help="nodes directory")
    parser.add_argument("--out", default=None, help="write to this path instead of stdout")
    args = parser.parse_args(argv)

    try:
        graph = pressure.load_graph(args.nodes)
    except GraphError as exc:
        print("render: %s" % exc, file=sys.stderr)
        return 1

    if args.all:
        ids = graph.tree_order()
    elif args.ids:
        ids = args.ids
    else:
        print("render: name a node id or pass --all", file=sys.stderr)
        return 1
    missing = [nid for nid in ids if nid not in graph.nodes]
    if missing:
        print("render: no such node: %s" % ", ".join(missing), file=sys.stderr)
        return 1

    text = render(graph, ids)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print("render: wrote %s (%d nodes)" % (args.out, len(ids)))
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
