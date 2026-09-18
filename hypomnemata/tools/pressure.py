#!/usr/bin/env python3
"""pressure.py -- priority and load over hypomnemata/nodes/*.yml.

Emits the frontier, the inbox and the load tables as markdown (or JSON).
Prints aggregates only; never file contents.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

# --- config ---------------------------------------------------------------
W_BLOCKED = 1.0
W_LOAD = 1.0
W_DISTANCE = 1.0
DEFAULT_DISTANCE = 3
# --------------------------------------------------------------------------

DEFAULT_NODES = Path(__file__).resolve().parent.parent / "nodes"
TERMINAL_FOLLOWUP = {"landed", "abandoned"}


class GraphError(Exception):
    """A defect that stops the computation (a cycle, a broken tree)."""


def as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def load_yaml_nodes(nodes_dir):
    nodes = {}
    for path in sorted(Path(nodes_dir).glob("*.yml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            nodes[path.stem] = data
    return nodes


class Graph:
    """The node tree with the pressure computation over it."""

    def __init__(self, nodes):
        self.nodes = nodes
        self.children = {nid: [] for nid in nodes}
        self.roots = []
        for nid in sorted(nodes):
            parent = nodes[nid].get("parent")
            if isinstance(parent, str) and parent in nodes and parent != nid:
                self.children[parent].append(nid)
            else:
                self.roots.append(nid)
        self._check_tree()

        self.followups = {}        # (node, followup) -> dict
        self.order = []            # (node, followup) in tree then file order
        self.actions = {}          # (node, action) -> dict
        for nid in self.tree_order():
            for fu in as_list(nodes[nid].get("followups")):
                if isinstance(fu, dict) and isinstance(fu.get("id"), str):
                    key = (nid, fu["id"])
                    self.followups[key] = fu
                    self.order.append(key)
            for action in as_list(nodes[nid].get("actions")):
                if isinstance(action, dict) and isinstance(action.get("id"), str):
                    self.actions[(nid, action["id"])] = action

        self.by_followup_id = {}
        for nid, fid in self.order:
            self.by_followup_id.setdefault(fid, []).append(nid)

        self.after = {key: self._resolve_after(key) for key in self.order}
        self.after_dependents = {key: [] for key in self.order}
        for key, befores in self.after.items():
            for other in befores:
                self.after_dependents.setdefault(other, []).append(key)
        self._check_after_acyclic()

        self.d_max = max(
            [self.distance(k) for k in self.order] or [DEFAULT_DISTANCE]
        )
        self._priority = {}
        self._node_load = {}

    # --- structure --------------------------------------------------------
    def _check_tree(self):
        for nid in sorted(self.nodes):
            seen = {nid}
            cur = self.nodes[nid].get("parent")
            while isinstance(cur, str) and cur in self.nodes:
                if cur in seen:
                    raise GraphError("parent chain is cyclic at %s (from %s)" % (cur, nid))
                seen.add(cur)
                cur = self.nodes[cur].get("parent")

    def _resolve_after(self, key):
        nid, fid = key
        out = []
        for other in as_list(self.followups[key].get("after")):
            owners = self.by_followup_id.get(other)
            if not owners:
                continue
            owner = nid if nid in owners else owners[0]
            out.append((owner, other))
        return out

    def _check_after_acyclic(self):
        colour = {}
        stack = []

        def visit(key):
            colour[key] = 1
            stack.append(key)
            for nxt in self.after.get(key, []):
                if colour.get(nxt, 0) == 0:
                    visit(nxt)
                elif colour.get(nxt) == 1:
                    start = stack.index(nxt)
                    loop = stack[start:] + [nxt]
                    raise GraphError("followup after cycle: %s"
                                     % " -> ".join("%s/%s" % k for k in loop))
            stack.pop()
            colour[key] = 2

        for key in self.order:
            if colour.get(key, 0) == 0:
                visit(key)

    def tree_order(self):
        """Every node, parent before child."""
        out = []
        seen = set()

        def walk(nid):
            if nid in seen:
                return
            seen.add(nid)
            out.append(nid)
            for child in self.children.get(nid, []):
                walk(child)

        for root in self.roots:
            walk(root)
        for nid in sorted(self.nodes):
            walk(nid)
        return out

    def descendants(self, nid):
        """nid and everything under it."""
        out = []
        stack = [nid]
        seen = set()
        while stack:
            cur = stack.pop()
            if cur in seen or cur not in self.nodes:
                continue
            seen.add(cur)
            out.append(cur)
            stack.extend(self.children.get(cur, []))
        return out

    def ancestors(self, nid):
        out = []
        seen = {nid}
        cur = self.nodes[nid].get("parent")
        while isinstance(cur, str) and cur in self.nodes and cur not in seen:
            out.append(cur)
            seen.add(cur)
            cur = self.nodes[cur].get("parent")
        return out

    def subtree_size(self, nid):
        return len(self.descendants(nid))

    # --- pressure ---------------------------------------------------------
    def distance(self, key):
        pressure = self.followups[key].get("pressure") or {}
        value = pressure.get("distance", DEFAULT_DISTANCE)
        return value if isinstance(value, (int, float)) else DEFAULT_DISTANCE

    def blocked(self, key):
        pressure = self.followups[key].get("pressure") or {}
        value = pressure.get("blocked", 0)
        return value if isinstance(value, (int, float)) else 0

    def postulate_load(self, postulate):
        """Nodes in the rests_on closure; '*' is every node."""
        rests = as_list(postulate.get("rests_on"))
        if "*" in rests:
            return len(self.nodes)
        closure = set()
        for ref in rests:
            if isinstance(ref, str) and ref in self.nodes:
                closure.update(self.descendants(ref))
        return len(closure)

    def load(self, key):
        """Σ postulate_load over the postulates this followup would discharge."""
        _, fid = key
        total = 0
        for nid in self.tree_order():
            for postulate in as_list(self.nodes[nid].get("postulates")):
                if isinstance(postulate, dict) and postulate.get("discharge") == fid:
                    total += self.postulate_load(postulate)
        return total

    def intrinsic(self, key):
        return (W_BLOCKED * self.blocked(key)
                + W_LOAD * self.load(key)
                + W_DISTANCE * (self.d_max + 1 - self.distance(key)))

    def priority(self, key):
        """intrinsic plus the priority of everything that must come after it."""
        if key in self._priority:
            return self._priority[key]
        self._priority[key] = self.intrinsic(key)   # provisional, tree is acyclic
        total = self.intrinsic(key)
        for dependent in self.after_dependents.get(key, []):
            total += self.priority(dependent)
        self._priority[key] = total
        return total

    def active_followups(self, nid):
        return [k for k in self.order
                if k[0] == nid and self.followups[k].get("state") not in TERMINAL_FOLLOWUP]

    def node_load(self, nid):
        if nid in self._node_load:
            return self._node_load[nid]
        total = sum(self.intrinsic(k) for k in self.active_followups(nid))
        for child in self.children.get(nid, []):
            total += self.node_load(child)
        self._node_load[nid] = total
        return total

    def action_done(self, nid, aid):
        """The action as seen from nid: on the node or on an ancestor."""
        for owner in [nid] + self.ancestors(nid):
            action = self.actions.get((owner, aid))
            if action is not None:
                return bool(action.get("done")), (owner, aid)
        return False, None

    def undone_requires(self, key):
        nid, _ = key
        out = []
        for aid in as_list(self.followups[key].get("requires")):
            done, _found = self.action_done(nid, aid)
            if not done:
                out.append(aid)
        return out

    def unlanded_after(self, key):
        out = []
        for other in self.after.get(key, []):
            if self.followups[other].get("state") != "landed":
                out.append(other[1])
        return out

    def ready(self, key):
        return (self.followups[key].get("state") == "drafted"
                and not self.undone_requires(key)
                and not self.unlanded_after(key))

    def blockers(self, key):
        return self.undone_requires(key) + self.unlanded_after(key)

    def requiring_followups(self, nid, aid):
        """Followups this action blocks: the direct requirers, then their after-dependents."""
        direct = [k for k in self.order
                  if aid in as_list(self.followups[k].get("requires"))
                  and self.action_done(k[0], aid)[1] == (nid, aid)]
        out = []
        seen = set()
        stack = list(direct)
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            out.append(cur)
            stack.extend(self.after_dependents.get(cur, []))
        return direct, out

    def action_priority(self, nid, aid):
        _direct, reach = self.requiring_followups(nid, aid)
        if not reach:
            return 0.0
        return max(self.priority(k) for k in reach)

    # --- tables -----------------------------------------------------------
    def frontier_rows(self):
        rows = []
        for key in self.order:
            fu = self.followups[key]
            if fu.get("state") in TERMINAL_FOLLOWUP:
                continue
            rows.append({
                "id": key[1],
                "node": key[0],
                "kind": fu.get("kind"),
                "target": fu.get("toward"),
                "priority": self.priority(key),
                "ready": self.ready(key),
                "blocked_by": self.blockers(key),
            })
        rows.sort(key=lambda r: (0 if r["ready"] else 1, -r["priority"], r["node"], r["id"]))
        return rows

    def inbox_rows(self):
        rows = []
        for (nid, aid), action in self.actions.items():
            if action.get("done"):
                continue
            direct, reach = self.requiring_followups(nid, aid)
            rows.append({
                "action": aid,
                "node": nid,
                "kind": action.get("kind"),
                "what": action.get("what"),
                "obligation": action.get("obligation"),
                "unblocks": len(direct),
                "priority": max([self.priority(k) for k in reach], default=0.0),
            })
        rows.sort(key=lambda r: (-r["priority"], r["node"], r["action"]))
        return rows

    def load_rows(self):
        rows = []
        for nid in self.tree_order():
            rows.append({
                "node": nid,
                "load": self.node_load(nid),
                "followups": len(self.active_followups(nid)),
                "subtree": self.subtree_size(nid),
            })
        return rows


def load_graph(nodes_dir=DEFAULT_NODES):
    return Graph(load_yaml_nodes(nodes_dir))


def num(value):
    value = float(value)
    return str(int(value)) if value == int(value) else "%.2f" % value


def cell(value):
    if value is None:
        return "—"
    if isinstance(value, list):
        return ", ".join(str(v) for v in value) if value else "—"
    text = str(value).replace("|", "\\|").replace("\n", " ").strip()
    return text or "—"


def table(headers, rows):
    out = ["| " + " | ".join(headers) + " |",
           "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        out.append("| " + " | ".join(row) + " |")
    return out


def render_markdown(graph):
    out = ["## Frontier", ""]
    out += table(
        ["id", "node", "kind", "target", "priority", "ready", "blocked by"],
        [[r["id"], r["node"], cell(r["kind"]), cell(r["target"]), num(r["priority"]),
          "yes" if r["ready"] else "no", cell(r["blocked_by"])]
         for r in graph.frontier_rows()])
    out += ["", "## Inbox", ""]
    out += table(
        ["action", "kind", "what", "obligation", "unblocks", "max priority"],
        [[r["action"], cell(r["kind"]), cell(r["what"]), cell(r["obligation"]),
          str(r["unblocks"]), num(r["priority"])]
         for r in graph.inbox_rows()])
    out += ["", "## Load", ""]
    out += table(
        ["node", "load", "direct followups", "subtree size"],
        [[r["node"], num(r["load"]), str(r["followups"]), str(r["subtree"])]
         for r in graph.load_rows()])
    return "\n".join(out) + "\n"


def render_json(graph):
    return json.dumps({
        "frontier": graph.frontier_rows(),
        "inbox": graph.inbox_rows(),
        "load": graph.load_rows(),
    }, indent=2) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Compute hypomnemata pressure.")
    parser.add_argument("--nodes", default=str(DEFAULT_NODES), help="nodes directory")
    parser.add_argument("--out", default=None, help="write to this path instead of stdout")
    parser.add_argument("--json", action="store_true", help="emit JSON")
    args = parser.parse_args(argv)
    try:
        graph = load_graph(args.nodes)
    except GraphError as exc:
        print("pressure: %s" % exc, file=sys.stderr)
        return 1
    text = render_json(graph) if args.json else render_markdown(graph)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print("pressure: wrote %s (%d frontier, %d inbox, %d nodes)"
              % (args.out, len(graph.frontier_rows()), len(graph.inbox_rows()), len(graph.nodes)))
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
