"""A tab as the document reads it, spelled as the reader takes it.

The document is shared, so a run reads a tab where it stands rather than
exporting it: a ``view`` read of the tab's body with ``sinceRev`` 0 is the
whole tab, every block with every run of its text and the marks on each —
links with their hrefs, code, italic, bold, mentions with their labels,
dropdowns with the word they show. This turns that read into the markdown
the export used to give and ``read.py`` parses, in the export's own
spelling: a mention as its bare label, a dropdown as its word, blocks parted
by a blank line. So nothing downstream changes — the reader, the page check
and the relink tool take the file this writes as they took an export — and
nothing is exported.

What the export lost, this keeps in reach: ``blocks`` gives each block's id
beside its markdown, which is what the page check would need to tell which
block a link leads to and not only which tab.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Sequence, Tuple

#: the marks a run of text may carry, outermost first as the export spells them
ITALIC, BOLD, CODE, LINK = "italic", "bold", "code", "link"

SEPARATOR = "\n\n"


def view_xml(source) -> str:
    """The view's xml, from the tool's result (JSON, as text or parsed) or
    from the bare xml."""
    if isinstance(source, dict):
        data = source.get("data", source)
        return data["xml"] if isinstance(data, dict) else source["xml"]
    text = source.strip()
    if text.startswith("{"):
        return view_xml(json.loads(text))
    return text


# --- runs ---------------------------------------------------------------

Run = Tuple[Tuple[Tuple[str, str], ...], str]  # ((mark, arg), ...), text


def _runs(node: ET.Element, marks: Tuple[Tuple[str, str], ...] = ()) -> List[Run]:
    """The runs of text under a paragraph, each with its marks outermost first."""
    out: List[Run] = []
    for child in node:
        tag = child.tag
        if tag == "text":
            out.extend(_text_runs(child, marks))
        elif tag == "mention":
            out.append((marks, child.get("label", "")))
        elif tag == "dropdown":
            out.append((marks, child.text or ""))
        elif tag in (ITALIC, BOLD, CODE):
            out.extend(_text_runs(child, marks + ((tag, ""),)))
        elif tag == LINK:
            out.extend(_text_runs(child, marks + ((LINK, child.get("href", "")),)))
        else:
            out.extend(_runs(child, marks))
        if child.tail:
            out.append((marks, child.tail))
    return out


def _text_runs(node: ET.Element, marks: Tuple[Tuple[str, str], ...]) -> List[Run]:
    out: List[Run] = []
    if node.text:
        out.append((marks, node.text))
    for child in node:
        tag = child.tag
        if tag in (ITALIC, BOLD, CODE):
            out.extend(_text_runs(child, marks + ((tag, ""),)))
        elif tag == LINK:
            out.extend(_text_runs(child, marks + ((LINK, child.get("href", "")),)))
        elif tag == "mention":
            out.append((marks, child.get("label", "")))
        elif tag == "dropdown":
            out.append((marks, child.text or ""))
        else:
            out.extend(_text_runs(child, marks))
        if child.tail:
            out.append((marks, child.tail))
    return out


def _wrap(mark: Tuple[str, str], inner: str) -> str:
    kind, arg = mark
    if kind == ITALIC:
        return "*%s*" % inner
    if kind == BOLD:
        return "**%s**" % inner
    if kind == CODE:
        return "`%s`" % inner
    return "[%s](%s)" % (inner, arg)


def _spell(runs: Sequence[Run], depth: int = 0) -> str:
    """Adjacent runs that share a mark are spelled inside one pair of its
    delimiters, so a link split across two runs is one link on the page."""
    out: List[str] = []
    i = 0
    while i < len(runs):
        marks, text = runs[i]
        if len(marks) <= depth:
            out.append(text)
            i += 1
            continue
        mark = marks[depth]
        j = i
        while j < len(runs) and len(runs[j][0]) > depth and runs[j][0][depth] == mark:
            j += 1
        out.append(_wrap(mark, _spell(runs[i:j], depth + 1)))
        i = j
    return "".join(out)


def inline(node: ET.Element) -> str:
    """A paragraph's text in the export's spelling."""
    return _spell(_runs(node))


# --- blocks -------------------------------------------------------------

def _paragraph(node: ET.Element) -> str:
    level = node.get("heading")
    text = inline(node)
    return ("#" * int(level) + " " + text) if level else text


def _list(node: ET.Element, indent: int = 0) -> str:
    kind = node.get("kind", "bullet")
    lines: List[str] = []
    n = 0
    for item in node:
        if item.tag != "listItem":
            continue
        n += 1
        marker = "%d. " % n if kind == "ordered" else "- "
        if kind == "check":
            marker += "[x] " if item.get("checked") == "true" else "[ ] "
        first = True
        for child in item:
            if child.tag == "paragraph":
                head = " " * indent + (marker if first else " " * len(marker))
                lines.append(head + inline(child))
                first = False
            elif child.tag == "list":
                lines.append(_list(child, indent + len(marker)))
    return "\n".join(lines)


def _blockquote(node: ET.Element) -> str:
    inner = SEPARATOR.join(_block(child) for child in node if child.tag != "gone")
    return "\n".join("> " + line if line else ">" for line in inner.split("\n"))


def _table(node: ET.Element) -> str:
    rows: List[List[str]] = []
    header = False
    for row in node:
        if row.tag != "row":
            continue
        cells = []
        for cell in row:
            if cell.tag != "cell":
                continue
            if cell.get("header") == "true" and not rows:
                header = True
            cells.append(" ".join(inline(p) for p in cell if p.tag == "paragraph")
                         .replace("|", "\\|"))
        rows.append(cells)
    if not rows:
        return ""
    lines = ["| " + " | ".join(rows[0]) + " |"]
    if header or True:
        lines.append("| " + " | ".join("---" for _ in rows[0]) + " |")
    for cells in rows[1:]:
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _block(node: ET.Element) -> str:
    tag = node.tag
    if tag == "paragraph":
        return _paragraph(node)
    if tag == "list":
        return _list(node)
    if tag == "blockquote":
        return _blockquote(node)
    if tag == "table":
        return _table(node)
    if tag == "pending":
        return ""
    return inline(node)


def blocks(source) -> List[Tuple[str, str]]:
    """(block id, markdown) per block of the tab, in order; a ``gone`` block is
    not a block."""
    root = ET.fromstring(view_xml(source))
    session = ""
    out: List[Tuple[str, str]] = []
    for node in root:
        bid = node.get("id", "")
        if bid.startswith("."):
            bid = session + bid
        elif "." in bid:
            session = bid.split(".")[0]
        if node.tag == "gone":
            continue
        text = _block(node)
        if text.strip():
            out.append((bid, text))
    return out


def markdown(source) -> str:
    """The tab as an export spelled it: blocks parted by a blank line, and a
    newline at the end."""
    return SEPARATOR.join(text for _, text in blocks(source)) + "\n"
