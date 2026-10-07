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

A backslash before punctuation is markdown's spelling of the literal
character. The page speller writes one before anything the page holds that
markdown would otherwise read as a mark (``escape``); the reader keeps those
and takes off the ones the exporter adds beyond them (``canonical``); and
``plain`` reads an escaped character as the character, which is what the
page holds. Without the three agreeing, a literal star was spelled bare on
the way out of the page and read as a mark on the way back in.
"""

from __future__ import annotations

import re
from typing import List, NamedTuple, Tuple

#: ``[text](url)``: the text, and the target. ``plain`` keeps the first and
#: drops the second; what wants the target reads the second group.
LINK = re.compile(r"\[([^\]]*)\]\(([^)]*)\)")

#: `` `code` `` keeps what it wraps.
_CODE = re.compile(r"`+([^`]*)`+")

#: ``*x*``, ``**x**``, ``***x***``. The lookarounds keep a lone asterisk whole.
_STARS = re.compile(r"(\*{1,3})(?=\S)(.+?)(?<=\S)\1", re.DOTALL)

#: the underscore spelling, which markdown honours only at a word boundary —
#: otherwise ``snake_case_word`` would come back as ``snakecaseword``.
_UNDERS = re.compile(r"(?<![0-9A-Za-z_])(_{1,3})(?=\S)(.+?)(?<=\S)\1(?![0-9A-Za-z_])",
                     re.DOTALL)


#: A backslash before ASCII punctuation: markdown's spelling of the literal
#: character, and the one thing in a text that is neither a word nor a mark.
#: The exporter writes one before anything it would otherwise read as a
#: marker — ``session\_01Jjv…`` for a word with an underscore in it.
ESCAPE = re.compile(r"\\([!-/:-@\[-`{-~])")

#: an escape, or a code span, whichever comes first: inside code a backslash
#: is a character, so a span is passed over whole and an escaped backtick
#: cannot open one
_HOLDABLE = re.compile(r"(`+[^`]*`+)|\\([!-/:-@\[-`{-~])")

#: a character standing in for one escape while the marks are taken off
_HELD = "\ue000"

#: the characters markdown reads as a mark wherever they stand in a run of
#: text: the backslash itself, the emphasis and code marks, and the brackets
#: a link is spelled in. An underscore is one only at a word boundary, where
#: markdown reads it; inside ``session_01`` it is a character.
_ALWAYS_A_MARK = "\\*`[]"
_WORDISH = re.compile(r"[0-9A-Za-z]")


def marked(before: str, char: str, after: str) -> bool:
    """Whether markdown reads ``char``, between these neighbours, as a mark —
    and so whether a literal one is spelled behind a backslash. One rule for
    the speller that writes the backslash and the reader that keeps it."""
    if char in _ALWAYS_A_MARK:
        return True
    return char == "_" and not (_WORDISH.match(before or " ")
                                and _WORDISH.match(after or " "))


def hold(markdown: str) -> Tuple[str, List[str]]:
    """``markdown`` with each escape replaced by one placeholder, and the
    characters held, in order. A held character is neither a mark nor a
    word: taking the marks off a string with ``\\*`` in it would otherwise
    pair that star with another."""
    held: List[str] = []

    def take(m: "re.Match[str]") -> str:
        if m.group(1) is not None:
            return m.group(1)  # a code span, as it stands
        held.append(m.group(2))
        return _HELD

    return _HOLDABLE.sub(take, markdown or ""), held


def release(held_text: str, held: List[str]) -> str:
    """The placeholders put back as the characters they held."""
    it = iter(held)
    return re.sub(_HELD, lambda m: next(it), held_text)


def unmarked(held_text: str) -> str:
    """The inline marks off a string whose escapes are held: a link to its
    words, code to what it wraps, emphasis to what it emphasises."""
    out = LINK.sub(r"\1", held_text)
    out = _CODE.sub(r"\1", out)
    for _ in range(3):  # ***both*** unwraps one layer per pass
        unwrapped = _UNDERS.sub(r"\2", _STARS.sub(r"\2", out))
        if unwrapped == out:
            break
        out = unwrapped
    return out


def plain(markdown: str) -> str:
    """``markdown`` with the inline markers removed and the characters kept:
    an escaped character is the character, as the page holds it."""
    markdown = markdown or ""
    if "\\" not in markdown:
        return unmarked(markdown)
    held_text, held = hold(markdown)
    return release(unmarked(held_text), held)


def escape(chars: str) -> str:
    """Characters as markdown spells them literally: a backslash before each
    one it would read as a mark. What the page speller writes for a run of
    the page's text; ``canonical`` is what the reader keeps of it."""
    chars = chars or ""
    if not any(c in chars for c in _ALWAYS_A_MARK + "_"):
        return chars
    out: List[str] = []
    for i, char in enumerate(chars):
        if marked(chars[i - 1] if i else "", char, chars[i + 1:i + 2]):
            out.append("\\")
        out.append(char)
    return "".join(out)


def canonical(markdown: str) -> str:
    """``markdown`` with the escapes markdown needs and no other.

    The exporter escapes more than it must — a stop, a dash, the underscore
    inside a word — and those backslashes are the exporter's, so they come
    off. One before a character ``escape`` would write it before is the
    page's: it spells a literal star or bracket, and stays, or the next
    render would write the character as a mark. Code is passed over whole.
    """
    markdown = markdown or ""
    if "\\" not in markdown:
        return markdown

    def keep(m: "re.Match[str]") -> str:
        if m.group(1) is not None:
            return m.group(1)
        char = m.group(2)
        before = markdown[m.start() - 1] if m.start() else ""
        return m.group() if marked(before, char, markdown[m.end():m.end() + 1]) else char

    return _HOLDABLE.sub(keep, markdown)


#: what counts as being inside a word, for ``whole_word``. An apostrophe is not
#: one of these, so ``party`` is found in ``party's``, which is where a reader
#: meets the word; ``prior`` is not found in ``priority``, which is the case
#: this exists for. Any script's letters count, so ``merge`` is not found
#: inside ``mergé`` either.
_WORD = re.compile(r"\w")

#: what opens a list item, as the page writes one and the renderer places a
#: chip by one: a bullet or a number and its stop, and then a space. The
#: renderer and the checks read the same pattern, so a line one takes for an
#: item the other does not take for a wrapped paragraph.
LIST_MARKER = r"(?:[-*+]|\d+[.)])"


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
    words = words or ""
    lowered = words.lower()
    # ``str.lower`` is the same thing, character for character, for every
    # string but two: one holding İ, which comes out two long, and one holding
    # a capital sigma, which lowers by its place in the word. Where the length
    # holds and no sigma stands, the fast path is this function; the rest take
    # the slow one, which this used to be for every string
    if len(lowered) == len(words) and "\u03a3" not in words:
        return lowered
    return "".join(c.lower() if len(c.lower()) == 1 else c for c in words)


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

#: the vowels: a short vowel before a final consonant is what doubles it
#: (stop -> stopped), and a consonant before a final y is what turns it to -ies.
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
