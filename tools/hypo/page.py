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

A character the page holds that markdown would read as a mark — a star, a
bracket, a backslash — is spelled behind a backslash, as the exporter
spelled it, so that the reader takes it for the character; spelled bare, the
next render wrote it as a mark. Inside code nothing is a mark, and a code
run is spelled as it stands.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from typing import List, Sequence, Tuple

from . import text

#: the marks a run of text may carry, outermost first as the export spells them
ITALIC, BOLD, CODE, LINK = "italic", "bold", "code", "link"

SEPARATOR = "\n\n"


def expand_id(bid: str, session: str) -> Tuple[str, str]:
    """A block id as a read prints it, made whole, and the session as it then
    stands. The session prefix is printed once, on whatever carries an id
    first, and every id after it is short — ``.5`` for ``<session>.5``. An id
    with no dot at all leaves the session as it was."""
    if bid.startswith("."):
        return session + bid, session
    if "." in bid:
        return bid, bid.split(".")[0]
    return bid, session


def view_xml(source) -> str:
    """The view's xml, from the tool's result (JSON, as text or parsed) or
    from the bare xml."""
    if isinstance(source, dict):
        data = source.get("data", source)
        try:
            return data["xml"] if isinstance(data, dict) else source["xml"]
        except KeyError:
            raise ValueError("the read carries no xml: it is not a view or a search result")
    body = source.strip()
    if body.startswith("{"):
        return view_xml(json.loads(body))
    return body


# --- runs ---------------------------------------------------------------

Run = Tuple[Tuple[Tuple[str, str], ...], str]  # ((mark, arg), ...), text


def literal(chars: str, marks: Tuple[Tuple[str, str], ...] = ()) -> str:
    """A run's characters as markdown spells them: a backslash before each
    one markdown would read as a mark, so a star the page holds comes back a
    star. Inside code a backslash is a character and nothing is a mark, so a
    code run is spelled as it stands."""
    if any(kind == CODE for kind, _ in marks):
        return chars
    return text.escape(chars)


def _runs(node: ET.Element, marks: Tuple[Tuple[str, str], ...] = (),
          top: bool = True) -> List[Run]:
    """The runs of text under a paragraph, each with its marks outermost first.

    A mention is its label and a dropdown the word it shows; the letters of
    every other element, known or not, are kept — the one walk, as
    ``inplace.pieces`` walks the tree and ``appline.digest`` hashes it. A
    walker that skipped an element it did not know spelled a line without a
    word the hash still counted, and the write put that line back.
    """
    out: List[Run] = []
    if not top and node.text:
        out.append((marks, literal(node.text, marks)))
    for child in node:
        tag = child.tag
        if tag == "mention":
            out.append((marks, child.get("label", "")))
        elif tag == "dropdown":
            out.append((marks, child.text or ""))
        elif tag in (ITALIC, BOLD, CODE):
            out.extend(_runs(child, marks + ((tag, ""),), False))
        elif tag == LINK:
            out.extend(_runs(child, marks + ((LINK, child.get("href", "")),), False))
        else:
            out.extend(_runs(child, marks, False))
        if child.tail:
            out.append((marks, literal(child.tail, marks)))
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


def spell(runs: Sequence[Run], depth: int = 0) -> str:
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
        out.append(_wrap(mark, spell(runs[i:j], depth + 1)))
        i = j
    return "".join(out)


def inline(node: ET.Element) -> str:
    """A paragraph's text in the export's spelling."""
    return spell(_runs(node))


# --- blocks -------------------------------------------------------------

def _paragraph(node: ET.Element) -> str:
    level = node.get("heading")
    words = inline(node)
    return ("#" * int(level) + " " + words) if level else words


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
    for row in node:
        if row.tag != "row":
            continue
        cells = []
        for cell in row:
            if cell.tag != "cell":
                continue
            cells.append(" ".join(inline(p) for p in cell if p.tag == "paragraph")
                         .replace("|", "\\|"))
        rows.append(cells)
    if not rows:
        return ""
    lines = ["| " + " | ".join(rows[0]) + " |",
             "| " + " | ".join("---" for _ in rows[0]) + " |"]
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
    # spelled as nothing, a code block or a divider would be gone from the
    # markdown and from everything downstream, and the next body write would
    # take it off the page; a tab holding one is not rewritten from a read
    raise ValueError("a block the tab's grammar does not hold: <%s>" % tag)


def blocks(source) -> List[Tuple[str, str]]:
    """(block id, markdown) per block of the tab, in order; a ``gone`` block is
    not a block."""
    root = ET.fromstring(view_xml(source))
    if root.get("sinceRev", "0") != "0" or root.find(".//gap") is not None:
        raise ValueError("a partial view, since rev %s: it folds the blocks that did "
                         "not change, and spells no whole tab" % root.get("sinceRev"))
    session = ""
    out: List[Tuple[str, str]] = []
    for node in root:
        bid, session = expand_id(node.get("id", ""), session)
        if node.tag == "gone":
            continue
        words = _block(node)
        if words.strip():
            out.append((bid, words))
    return out


def markdown(source) -> str:
    """The tab as an export spelled it: blocks parted by a blank line, and a
    newline at the end."""
    return SEPARATOR.join(words for _, words in blocks(source)) + "\n"
