"""Plain text from markdown: the characters, without the markers.

The document stores characters and applies emphasis as a range beside them, so
a link the caller applies by searching for ``**record**`` finds nothing — the
page holds ``record``. Anchors are stored with their markup, because that is
what makes them verbatim substrings of a thesis that emphasises part of a
clause; ``plain`` is how they are handed to anything that searches the page.

It is also what comparison wants: whether a question restates an anchor, or
whether a defined word occurs in its thesis, is a question about words and not
about how they are drawn.
"""

from __future__ import annotations

import re

#: ``[text](url)`` keeps its text and drops its target.
_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")

#: `` `code` `` keeps what it wraps.
_CODE = re.compile(r"`+([^`]*)`+")

#: ``*x*``, ``**x**``, ``***x***``. The lookarounds keep a lone asterisk whole.
_STARS = re.compile(r"(\*{1,3})(?=\S)(.+?)(?<=\S)\1", re.DOTALL)

#: the underscore spelling, which markdown honours only at a word boundary —
#: otherwise ``snake_case_word`` would come back as ``snakecaseword``.
_UNDERS = re.compile(r"(?<![0-9A-Za-z_])(_{1,3})(?=\S)(.+?)(?<=\S)\1(?![0-9A-Za-z_])",
                     re.DOTALL)


def plain(markdown: str) -> str:
    """``markdown`` with the inline markers removed and the characters kept."""
    out = markdown or ""
    out = _LINK.sub(r"\1", out)
    out = _CODE.sub(r"\1", out)
    for _ in range(3):  # ***both*** unwraps one layer per pass
        unwrapped = _UNDERS.sub(r"\2", _STARS.sub(r"\2", out))
        if unwrapped == out:
            break
        out = unwrapped
    return out
