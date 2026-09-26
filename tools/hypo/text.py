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

#: a final consonant, for the endings that want the vowel kept short.
_VOWEL = "aeiou"


def forms(word: str) -> List[str]:
    """A headword and the regular inflections a thesis might use it in.

    A glossary entry is a **headword**: the form a dictionary files the word
    under. Prose uses whichever inflection the sentence wants — a thesis that
    fixes the sense of ``grant`` may only ever say ``grants`` — and the entry
    is no less anchored for that. So the word to look for on the page is the
    headword or any regular form of it, and the link goes on the form that
    actually stands there rather than on the base hidden inside it.

    Regular inflection only, and deliberately: an irregular form is rare
    enough in this prose to be worth noticing by hand, and a stemmer that
    guessed at them would also match words that are not the headword at all.
    A phrase inflects on its last word, which is where English puts it. And
    a phrase put in front of a noun is hyphenated — a *clean-context* answer —
    so each of its forms is looked for that way too. Without it the notebook's
    "clean-context" was read as no use of ``clean context`` at all, by the
    checker and by the probe alike, on thirteen tabs.

    Longest first, so a caller matching at a position takes ``grants`` rather
    than the ``grant`` inside it.
    """
    head, sep, last = (word or "").rpartition(" ")
    if not last:
        return []
    out = {last}
    if last.endswith("y") and len(last) > 1 and last[-2] not in _VOWEL:
        out.update({last[:-1] + "ies", last[:-1] + "ied", last + "ing"})
    elif last.endswith("e"):
        out.update({last + "s", last + "d", last[:-1] + "ing"})
    elif last.endswith(("s", "x", "z", "ch", "sh", "o")):
        out.update({last + "es", last + "ed", last + "ing"})
    else:
        out.update({last + "s", last + "ed", last + "ing"})
        if (len(last) > 2 and last[-1] not in _VOWEL + "wxy"
                and last[-2] in _VOWEL and last[-3] not in _VOWEL):
            out.update({last + last[-1] + "ed", last + last[-1] + "ing"})
    spaced = {head + sep + form for form in out}
    hyphenated = {form.replace(" ", "-") for form in spaced if " " in form}
    return sorted(spaced | hyphenated, key=lambda f: (-len(f), f))
