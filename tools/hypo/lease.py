"""The lease tab: who is writing the notebook now, and with what tooling.

Several sessions may write one notebook at once. A write in place is guarded
block by block and needs nothing more; a run that writes a section or a body,
changes the specification or sends the tab patch first takes a **lease**: a
line on the notebook's reserved tab, under its ``## Leases`` heading, naming
what it may write (one project, or ``all``), the session and the entry point.
It inserts the line, reads the tab back, and goes on only if no line that
overlaps its own stands above it; otherwise it takes its line off and waits.
The document orders the lines as they land, so the first to land holds the
lease without anyone comparing and swapping. The run takes its line off when
it is done; a line left by a run that died is released by reading it.

The same tab says, under ``## Tooling``, which tooling the notebook was last
written with: the **pin**. A run whose tooling is older does not write.

Everything here reads a ``view`` of the lease tab and prints the operations
that write it, each whole-block one guarded by the block's ``h`` and the
read's ``rev``; nothing here writes.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import List, NamedTuple, Optional, Tuple

from . import page, text

#: the headings of the two sections this reads
LEASES = "Leases"
TOOLING = "Tooling"

#: what the Leases section says when it holds no lease
NONE_HELD = "None held."

#: the parts of a lease line, in order, and what parts them
SEP = " · "

#: what a lease's scope may be beside a project's name
ALL = "all"

#: the pin, as the Tooling paragraph spells it
PIN = re.compile(r"principal plugin ([0-9a-f]{7,40})")


class Block(NamedTuple):
    id: str
    h: str
    text: str


class Lease(NamedTuple):
    scope: str
    session: str
    entry: str
    since: str
    block: Block


class Section(NamedTuple):
    heading: Optional[Block]
    blocks: List[Tuple[str, ET.Element, Block]]  # (tag, node, block)


def _walk(root: ET.Element):
    """Every element with an id, in document order, with its full id."""
    session = ""
    for node in root.iter():
        bid = node.get("id")
        if not bid:
            continue
        full, session = page.expand_id(bid, session)
        yield node, full


def _ids(root: ET.Element) -> dict:
    return {id(node): full for node, full in _walk(root)}


def read(source) -> Tuple[int, ET.Element, dict]:
    """The read's rev, its tree, and every element's full id."""
    root = ET.fromstring(page.view_xml(source))
    return int(root.get("rev", "0") or 0), root, _ids(root)


def _words(node: ET.Element) -> str:
    """A paragraph's words: its runs, or, in an outline read, the words the
    element holds directly."""
    return page.inline(node) or (node.text or "")


def section(root: ET.Element, ids: dict, name: str) -> Section:
    """The blocks under a ``## <name>`` heading, up to the next one."""
    heading: Optional[Block] = None
    out: List[Tuple[str, ET.Element, Block]] = []
    for node in root:
        if node.tag == "gone":
            continue
        if node.tag == "paragraph" and node.get("heading") == "2":
            if heading is not None:
                break
            if _words(node).strip() == name:
                heading = Block(ids[id(node)], node.get("h", ""), name)
            continue
        if heading is not None:
            words = _words(node) if node.tag == "paragraph" else ""
            out.append((node.tag, node, Block(ids[id(node)], node.get("h", ""), words)))
    return Section(heading, out)


def line(scope: str, session: str, entry: str, since: str) -> str:
    """A lease line as the tab holds it."""
    return SEP.join((scope, session, entry, "since " + since))


def leases(source) -> List[Lease]:
    """The leases standing, in the order they landed."""
    _, root, ids = read(source)
    out: List[Lease] = []
    for tag, node, _block in section(root, ids, LEASES).blocks:
        if tag != "list":
            continue
        for item in node:
            if item.tag != "listItem":
                continue
            para = next((c for c in item if c.tag == "paragraph"), None)
            words = _words(para).strip() if para is not None else ""
            parts = words.split(SEP)
            if len(parts) < 4:
                continue
            since = parts[3][len("since "):] if parts[3].startswith("since ") else parts[3]
            out.append(Lease(parts[0].strip(), parts[1].strip(), parts[2].strip(), since.strip(),
                             Block(ids[id(item)], item.get("h", ""), words)))
    return out


def overlaps(a: str, b: str) -> bool:
    return a == ALL or b == ALL or a == b


def ahead(source, session: str) -> Optional[List[Lease]]:
    """The leases that stand above this session's and overlap it: empty when
    the session holds its lease, None when it has no line at all."""
    standing = leases(source)
    mine = next((i for i, l in enumerate(standing) if l.session == session), None)
    if mine is None:
        return None
    return [l for l in standing[:mine] if overlaps(l.scope, standing[mine].scope)]


def take(source, scope: str, session: str, entry: str, since: str) -> List[dict]:
    """The operations that put this session's line under the Leases heading:
    after the last line standing, or in place of the words saying none is."""
    rev, root, ids = read(source)
    sec = section(root, ids, LEASES)
    if sec.heading is None:
        raise ValueError("the tab has no '## %s' section" % LEASES)
    words = line(scope, session, entry, since)
    md = {"from": {"kind": "inline", "content": "- " + text.escape(words)},
          "as": "markdown"}
    lists = [(n, b) for t, n, b in sec.blocks if t == "list"]
    if lists:
        node, _ = lists[-1]
        items = [c for c in node if c.tag == "listItem"]
        return [{"op": "insert", "target": {"kind": "blocks", "ids": [ids[id(items[-1])]]},
                 "side": "after", "source": md}]
    empty = [b for t, _, b in sec.blocks if t == "paragraph" and b.text.startswith(NONE_HELD)]
    if empty:
        return [{"op": "replace", "target": {"kind": "blocks", "ids": [empty[0].id]},
                 "ifHash": empty[0].h, "ifRev": rev, "with": md}]
    return [{"op": "insert", "target": {"kind": "blocks", "ids": [sec.heading.id]},
             "side": "after", "source": md}]


def release(source, session: str) -> List[dict]:
    """The operations that take this session's line off: the whole list,
    replaced by the words saying none is held, when it is the only line."""
    rev, root, ids = read(source)
    standing = leases(source)
    mine = [l for l in standing if l.session == session]
    if not mine:
        return []
    if len(standing) == len(mine):
        sec = section(root, ids, LEASES)
        lists = [b for t, _, b in sec.blocks if t == "list"]
        return [{"op": "replace", "target": {"kind": "blocks", "ids": [lists[-1].id]},
                 "ifHash": lists[-1].h, "ifRev": rev,
                 "with": {"from": {"kind": "inline", "content": NONE_HELD}, "as": "markdown"}}]
    return [{"op": "delete", "target": {"kind": "blocks", "ids": [l.block.id]},
             "ifHash": l.block.h, "ifRev": rev} for l in mine]


def pin(source) -> Optional[str]:
    """The commit the notebook was last written with, or None."""
    _, root, ids = read(source)
    for tag, _node, block in section(root, ids, TOOLING).blocks:
        found = PIN.search(block.text) if tag == "paragraph" else None
        if found:
            return found.group(1)
    return None


def pin_ops(source, commit: str, session: str, when: str) -> List[dict]:
    """The operation that names this tooling as the one the notebook was
    last written with, in place of the Tooling section's first paragraph."""
    rev, root, ids = read(source)
    paras = [b for t, _, b in section(root, ids, TOOLING).blocks if t == "paragraph"]
    if not paras:
        raise ValueError("the tab has no paragraph under '## %s'" % TOOLING)
    words = "principal plugin %s, last written %s by %s." % (commit, when, session)
    return [{"op": "replace", "target": {"kind": "blocks", "ids": [paras[0].id]},
             "ifHash": paras[0].h, "ifRev": rev,
             "with": {"from": {"kind": "inline", "content": text.escape(words)},
                      "as": "markdown"}}]
