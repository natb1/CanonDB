"""Plain text from markdown: the characters, without the markers.

The document stores characters and applies emphasis as a range beside them, so
a link the caller applies by searching for ``**record**`` finds nothing — the
page holds ``record``. Anchors are stored with their markup, because that is
what makes them verbatim substrings of a thesis that emphasises part of a
clause; ``plain`` is how they are handed to anything that searches the page.

It is also what comparison wants: whether a question restates an anchor, or
whether a defined word occurs in its thesis, is a question about words and not
about how they are drawn.

``occurrences`` is the other half of that: once the anchor is plain, where on
the page does it stand? A link is applied by searching, so the search has to
name which run of characters it meant.
"""

from __future__ import annotations

import re
from typing import List, NamedTuple

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


#: what counts as being inside a word, for ``whole_word``. An apostrophe is not
#: one of these, so ``party`` is found in ``party's``, which is where a reader
#: meets the word; ``prior`` is not found in ``priority``, which is the case
#: this exists for.
_WORD = re.compile(r"[0-9A-Za-z_]")


#: A run of the page that reads as the needle: where it begins, and the number
#: the document has to count to in order to reach it.
class Run(NamedTuple):
    nth: int
    at: int


def fold(words: str) -> str:
    """Lower case, one character in and one out.

    ``str.lower`` is not length-preserving for every character — ``\u0130``
    becomes two — and an offset into the folded string has to be an offset into
    the original, so a character that will not fold in place is left alone.
    """
    return "".join(c.lower() if len(c.lower()) == 1 else c for c in words or "")


def occurrences(hay: str, needle: str, whole_word: bool = False) -> List[Run]:
    """Which runs of ``hay`` read as ``needle``, and what to count to reach each.

    The page is searched by text, so a link names the nth run of characters
    that reads as ``needle``. Two things decide that number and both are the
    document's rules rather than this module's.

    Every literal match counts, including the ones inside longer words: the
    first standalone ``merge`` in a page that says ``merged`` first is
    occurrence 2, and asking for occurrence 1 links the wrong characters.

    And **case does not count**, because the document's find folds it. A page
    whose ``## Thesis`` heading stands before the word ``thesis`` reaches the
    word at occurrence 2, not 1. Counting here with regard to case is what cost
    the notebook twenty-four links: each ``nth`` named an earlier run that
    already carried a link, so the operation came back a silent no-op and
    nothing downstream could see that the link had not landed.

    ``whole_word`` decides which runs qualify. It never decides the numbering.
    """
    if not needle:
        return []
    hay, needle = fold(hay), fold(needle)
    out: List[Run] = []
    n = 0
    start = 0
    while True:
        at = hay.find(needle, start)
        if at < 0:
            return out
        n += 1
        start = at + 1
        if whole_word:
            before = hay[at - 1] if at else ""
            after = hay[at + len(needle):at + len(needle) + 1]
            if _WORD.match(before) or _WORD.match(after):
                continue
        out.append(Run(nth=n, at=at))
