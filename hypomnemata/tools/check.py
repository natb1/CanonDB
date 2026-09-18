#!/usr/bin/env python3
"""check.py -- validate hypomnemata/nodes/*.yml against hypomnemata/SPEC.md.

Prints an aggregate summary line and one line per finding; never file contents.
Exits 1 iff there is at least one error.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

DEFAULT_NODES = Path(__file__).resolve().parent.parent / "nodes"

NODE_STATES = {"held", "in-line", "landed", "revised", "deadlocked"}
NEEDS_CANON = {"landed", "deadlocked"}
TERM_STATES = {"dormant", "drawn", "landed"}
FOLLOWUP_KINDS = {"definitional", "case", "consistency"}
FOLLOWUP_STATES = {"drafted", "asked", "landed", "abandoned"}
ACTION_KINDS = {"promulgate", "provide", "dispose", "build"}
RELATIONS = {"support", "divergence", "island"}
HINGE_KEYS = ("model", "harness", "canon_sha", "presuppositions")
HUMAN_GROUP = "of-the-human"
STUB_TOWARD_LIMIT = 3

KEBAB = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")


class Findings:
    """Collected errors and warnings, kept as (node, message) pairs."""

    def __init__(self):
        self.errors = []
        self.warnings = []

    def error(self, node, message):
        self.errors.append((node, message))

    def warn(self, node, message):
        self.warnings.append((node, message))

    def lines(self):
        out = []
        for node, message in self.errors:
            out.append("E %s: %s" % (node, message))
        for node, message in self.warnings:
            out.append("W %s: %s" % (node, message))
        return out


def as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def text_of(value):
    return value if isinstance(value, str) else ""


def load_nodes(nodes_dir, findings):
    """Read every *.yml in nodes_dir. Keyed by filename stem."""
    nodes = {}
    declared = {}
    for path in sorted(Path(nodes_dir).glob("*.yml")):
        stem = path.stem
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            findings.error(stem, "YAML parse failed: %s" % str(exc).splitlines()[0])
            continue
        if not isinstance(data, dict):
            findings.error(stem, "top level is not a mapping")
            continue
        if not KEBAB.match(stem):
            findings.error(stem, "filename stem is not kebab-case")
        nid = data.get("id")
        if nid is None:
            findings.error(stem, "missing id")
        elif not isinstance(nid, str):
            findings.error(stem, "id is not a string")
        else:
            if nid != stem:
                findings.error(stem, "id %r does not match filename stem" % nid)
            if not KEBAB.match(nid):
                findings.error(stem, "id %r is not kebab-case" % nid)
            declared.setdefault(nid, []).append(stem)
        nodes[stem] = data
    for nid, stems in sorted(declared.items()):
        if len(stems) > 1:
            findings.error(nid, "id declared by %d files: %s" % (len(stems), ", ".join(stems)))
    return nodes


def effective_hinge(nid, nodes, cache=None):
    """Hinge of nid with every ancestor override applied, root first."""
    if cache is None:
        cache = {}
    if nid in cache:
        return cache[nid]
    node = nodes.get(nid) or {}
    parent = node.get("parent")
    if isinstance(parent, str) and parent in nodes and parent != nid:
        base = dict(effective_hinge(parent, nodes, cache))
    else:
        base = {}
    own = node.get("hinge")
    if isinstance(own, dict):
        base.update(own)
    cache[nid] = base
    return base


def ancestors_of(nid, nodes):
    """Ancestor ids, nearest first. Stops on a missing parent or a cycle."""
    out = []
    seen = {nid}
    cur = (nodes.get(nid) or {}).get("parent")
    while isinstance(cur, str) and cur in nodes and cur not in seen:
        out.append(cur)
        seen.add(cur)
        cur = (nodes.get(cur) or {}).get("parent")
    return out


def check(nodes_dir):
    findings = Findings()
    nodes = load_nodes(nodes_dir, findings)

    # --- tree -------------------------------------------------------------
    roots = []
    for nid, node in sorted(nodes.items()):
        parent = node.get("parent")
        if parent is None:
            roots.append(nid)
        elif not isinstance(parent, str):
            findings.error(nid, "parent is neither null nor an id")
        elif parent not in nodes:
            findings.error(nid, "parent %r does not exist" % parent)
        elif parent == nid:
            findings.error(nid, "parent is itself")
    if not roots:
        findings.error("nodes/", "no root node (none with parent: null)")
    elif len(roots) > 1:
        findings.error("nodes/", "%d roots: %s" % (len(roots), ", ".join(roots)))
    for nid in sorted(nodes):
        seen = {nid}
        cur = nodes[nid].get("parent")
        while isinstance(cur, str) and cur in nodes:
            if cur in seen:
                findings.error(nid, "parent chain is cyclic at %r" % cur)
                break
            seen.add(cur)
            cur = nodes[cur].get("parent")

    # --- indexes ----------------------------------------------------------
    followup_ids = {}          # followup id -> [node id, ...]
    actions_by_node = {}       # node id -> {action id: done}
    terms_by_node = {}         # node id -> {term id: group}
    all_terms = {}             # term id -> group (first seen)
    toward_counts = {}
    for nid, node in sorted(nodes.items()):
        actions_by_node[nid] = {}
        terms_by_node[nid] = {}
        for action in as_list(node.get("actions")):
            if isinstance(action, dict) and isinstance(action.get("id"), str):
                actions_by_node[nid][action["id"]] = bool(action.get("done"))
        for term in as_list(node.get("terms")):
            if isinstance(term, dict) and isinstance(term.get("id"), str):
                terms_by_node[nid][term["id"]] = term.get("group")
                all_terms.setdefault(term["id"], term.get("group"))
        for fu in as_list(node.get("followups")):
            if isinstance(fu, dict) and isinstance(fu.get("id"), str):
                followup_ids.setdefault(fu["id"], []).append(nid)

    for fid, owners in sorted(followup_ids.items()):
        if len(owners) > 1:
            findings.warn("nodes/", "followup id %r used on %s" % (fid, ", ".join(owners)))

    # --- per node ---------------------------------------------------------
    hinge_cache = {}
    def_senses = {}
    after_edges = {}           # (node, followup) -> [(node, followup), ...]

    for nid, node in sorted(nodes.items()):
        stub = bool(node.get("stub"))
        state = node.get("state")
        if not isinstance(node.get("q"), str) or not node.get("q").strip():
            findings.error(nid, "missing q")
        if state not in NODE_STATES:
            findings.error(nid, "state %r not in vocabulary" % state)
        elif state in NEEDS_CANON and not text_of(node.get("canon")).strip():
            findings.error(nid, "state %s requires a canon ref" % state)
        if "thesis" not in node:
            findings.error(nid, "missing thesis")
        if DATE_RE.search(text_of(node.get("thesis"))):
            findings.warn(nid, "ISO date in thesis (ledger shape)")

        # defs
        for entry in as_list(node.get("defs")):
            if not isinstance(entry, dict):
                findings.error(nid, "defs entry is not a mapping")
                continue
            term = entry.get("term")
            if not isinstance(term, str) or not term.strip():
                findings.error(nid, "defs entry without a term")
                continue
            if term in def_senses and def_senses[term] != nid:
                findings.warn(nid, "term %r is also defined on %s" % (term, def_senses[term]))
            else:
                def_senses.setdefault(term, nid)

        # hinge
        hinge = node.get("hinge")
        if hinge is not None and not isinstance(hinge, dict):
            findings.error(nid, "hinge is not a mapping")
            hinge = None
        if node.get("parent") is None:
            missing = [k for k in HINGE_KEYS if k not in (hinge or {})]
            if missing:
                findings.error(nid, "root hinge is missing %s" % ", ".join(missing))
        elif hinge:
            parent = node.get("parent")
            inherited = {}
            if isinstance(parent, str) and parent in nodes:
                inherited = effective_hinge(parent, nodes, hinge_cache)
            for key, value in hinge.items():
                if key not in HINGE_KEYS:
                    findings.warn(nid, "unknown hinge key %r" % key)
                if key in inherited and inherited[key] == value:
                    findings.error(nid, "hinge key %r repeats the inherited value" % key)

        # terms
        seen_terms = set()
        for term in as_list(node.get("terms")):
            if not isinstance(term, dict):
                findings.error(nid, "terms entry is not a mapping")
                continue
            tid = term.get("id")
            if not isinstance(tid, str):
                findings.error(nid, "term without an id")
                continue
            if tid in seen_terms:
                findings.error(nid, "duplicate term id %r" % tid)
            seen_terms.add(tid)
            tstate = term.get("state")
            if tstate not in TERM_STATES:
                findings.error(nid, "term %s: state %r not in vocabulary" % (tid, tstate))
            child = term.get("child")
            if tstate == "landed":
                if not isinstance(child, str) or child not in nodes:
                    findings.error(nid, "term %s is landed but has no existing child" % tid)
                elif nodes[child].get("parent") != nid:
                    findings.error(nid, "term %s child %s has parent %r" % (tid, child, nodes[child].get("parent")))
            elif isinstance(child, str) and child not in nodes:
                findings.error(nid, "term %s names a child %r that does not exist" % (tid, child))
            if DATE_RE.search(text_of(term.get("clause"))):
                findings.warn(nid, "term %s: ISO date in clause (ledger shape)" % tid)

        # actions
        seen_actions = set()
        for action in as_list(node.get("actions")):
            if not isinstance(action, dict):
                findings.error(nid, "actions entry is not a mapping")
                continue
            aid = action.get("id")
            if not isinstance(aid, str):
                findings.error(nid, "action without an id")
                continue
            if aid in seen_actions:
                findings.error(nid, "duplicate action id %r" % aid)
            seen_actions.add(aid)
            if action.get("kind") not in ACTION_KINDS:
                findings.error(nid, "action %s: kind %r not in vocabulary" % (aid, action.get("kind")))
            obligation = action.get("obligation")
            if obligation is None:
                findings.error(nid, "action %s has no obligation" % aid)
            elif obligation not in all_terms:
                findings.error(nid, "action %s: obligation %r is not a term anywhere" % (aid, obligation))
            elif all_terms[obligation] != HUMAN_GROUP:
                findings.warn(nid, "action %s: obligation %s is not in group %s" % (aid, obligation, HUMAN_GROUP))

        # postulates
        seen_postulates = set()
        for post in as_list(node.get("postulates")):
            if not isinstance(post, dict):
                findings.error(nid, "postulates entry is not a mapping")
                continue
            pid = post.get("id")
            if not isinstance(pid, str):
                findings.error(nid, "postulate without an id")
                pid = "?"
            elif pid in seen_postulates:
                findings.error(nid, "duplicate postulate id %r" % pid)
            seen_postulates.add(pid)
            discharge = post.get("discharge")
            if discharge is not None and discharge not in followup_ids:
                findings.error(nid, "postulate %s: discharge %r is not a followup id" % (pid, discharge))
            rests = as_list(post.get("rests_on"))
            if not rests:
                findings.error(nid, "postulate %s has no rests_on" % pid)
            for ref in rests:
                if ref == "*":
                    continue
                if ref not in nodes:
                    findings.error(nid, "postulate %s rests on %r, which does not exist" % (pid, ref))

        # followups
        node_actions = dict(actions_by_node[nid])
        for anc in ancestors_of(nid, nodes):
            for aid, done in actions_by_node.get(anc, {}).items():
                node_actions.setdefault(aid, done)
        seen_followups = set()
        for fu in as_list(node.get("followups")):
            if not isinstance(fu, dict):
                findings.error(nid, "followups entry is not a mapping")
                continue
            fid = fu.get("id")
            if not isinstance(fid, str):
                findings.error(nid, "followup without an id")
                continue
            if fid in seen_followups:
                findings.error(nid, "duplicate followup id %r" % fid)
            seen_followups.add(fid)
            if fu.get("term") not in terms_by_node[nid]:
                findings.error(nid, "followup %s: term %r is not a term of this node" % (fid, fu.get("term")))
            if fu.get("kind") not in FOLLOWUP_KINDS:
                findings.error(nid, "followup %s: kind %r not in vocabulary" % (fid, fu.get("kind")))
            if fu.get("state") not in FOLLOWUP_STATES:
                findings.warn(nid, "followup %s: state %r not in vocabulary" % (fid, fu.get("state")))
            toward = fu.get("toward")
            if not isinstance(toward, str) or toward not in nodes:
                findings.error(nid, "followup %s: toward %r does not exist" % (fid, toward))
            else:
                toward_counts[toward] = toward_counts.get(toward, 0) + 1
            for aid in as_list(fu.get("requires")):
                if aid not in node_actions:
                    findings.error(nid, "followup %s requires %r, not an action of this node or an ancestor" % (fid, aid))
            edges = []
            for other in as_list(fu.get("after")):
                if other not in followup_ids:
                    findings.error(nid, "followup %s: after %r is not a followup id" % (fid, other))
                    continue
                owners = followup_ids[other]
                edges.append((nid if nid in owners else owners[0], other))
            after_edges[(nid, fid)] = edges
            if DATE_RE.search(text_of(fu.get("draft"))):
                findings.warn(nid, "followup %s: ISO date in draft (ledger shape)" % fid)

        # traditions
        for tradition in as_list(node.get("traditions")):
            if not isinstance(tradition, dict):
                findings.error(nid, "traditions entry is not a mapping")
                continue
            if tradition.get("relation") not in RELATIONS:
                findings.warn(nid, "tradition %r: relation %r not in vocabulary"
                              % (tradition.get("name"), tradition.get("relation")))

    # --- after acyclicity -------------------------------------------------
    for cycle in find_cycles(after_edges):
        findings.error(cycle[0][0], "followup after cycle: %s" % " -> ".join(f for _, f in cycle))

    # --- overloaded stubs -------------------------------------------------
    for nid, count in sorted(toward_counts.items()):
        if count > STUB_TOWARD_LIMIT and bool(nodes.get(nid, {}).get("stub")):
            findings.warn(nid, "stub is the target of %d followups (> %d); draw it"
                          % (count, STUB_TOWARD_LIMIT))

    return nodes, findings


def find_cycles(edges):
    """Every cycle in a {key: [key, ...]} graph, each as a list of keys."""
    cycles = []
    colour = {}
    stack = []

    def visit(key):
        colour[key] = 1
        stack.append(key)
        for nxt in edges.get(key, []):
            if colour.get(nxt, 0) == 0:
                visit(nxt)
            elif colour.get(nxt) == 1:
                start = stack.index(nxt)
                cycles.append(stack[start:] + [nxt])
        stack.pop()
        colour[key] = 2

    for key in sorted(edges):
        if colour.get(key, 0) == 0:
            visit(key)
    return cycles


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate the hypomnemata nodes.")
    parser.add_argument("--nodes", default=str(DEFAULT_NODES), help="nodes directory")
    args = parser.parse_args(argv)
    nodes_dir = Path(args.nodes)
    if not nodes_dir.is_dir():
        print("check: %s is not a directory" % nodes_dir, file=sys.stderr)
        return 1
    nodes, findings = check(nodes_dir)
    print("check: %d nodes, %d errors, %d warnings"
          % (len(nodes), len(findings.errors), len(findings.warnings)))
    for line in findings.lines():
        print(line)
    return 1 if findings.errors else 0


if __name__ == "__main__":
    sys.exit(main())
