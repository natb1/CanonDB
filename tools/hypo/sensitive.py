"""sensitive — the private list of what never leaves for a repository.

Sensitive information the user reports never reaches a public repository:
not a commit's, tag's, note's or merge's message, not a pull request's,
issue's or release's words, not a file's content. What counts as sensitive
is the user's, and it is never in a repository: it is a file on the machine,
`<config home>/principal/sensitive.txt` (the config home is
`$CLAUDE_CONFIG_DIR`, else `~/.claude`), beside the brief's directory and
outside every checkout; `$PRINCIPAL_SENSITIVE` names another file.

The file holds one pattern a line. A blank line, or one opening with `#`,
is none. A line opening with `re:` is a regular expression, the rest of the
line, matched with case folded. Every other line is plain words, matched
with case folded where no letter or digit stands against either end, any
run of white space between its words matching any other.

A match names the pattern by its line number in the file and never by its
words, and never quotes the text it matched: the place, a field or a file
and line, and the number are all that is said, so that a refusal or an
audit report repeats nothing of the list or of what matched it.
"""

from __future__ import annotations

import os
import re
from typing import Dict, Iterable, List, NamedTuple, Optional, Tuple

from .brief import config_home

#: the environment variable naming the list's file in place of the default
ENV = "PRINCIPAL_SENSITIVE"
#: the list's file name under `<config home>/principal/`
NAME = "sensitive.txt"


class Pattern(NamedTuple):
    line: int
    regex: "re.Pattern"


class Patterns(NamedTuple):
    path: str
    patterns: List[Pattern]
    #: line numbers of `re:` lines that do not compile, so check nothing
    broken: List[int]


def path(env) -> str:
    """The list's file: `$PRINCIPAL_SENSITIVE` where set, else
    `<config home>/principal/sensitive.txt`."""
    named = env.get(ENV)
    if isinstance(named, str) and named:
        return named
    return os.path.join(config_home(env), "principal", NAME)


def compile_line(text: str) -> Optional["re.Pattern"]:
    """One line's pattern, or None where it is no pattern; raises re.error
    for a regular expression that does not compile."""
    text = text.rstrip("\r\n")
    stripped = text.strip()
    if not stripped or stripped.startswith("#"):
        return None
    if stripped.startswith("re:"):
        return re.compile(stripped[3:].strip(), re.IGNORECASE)
    words = [re.escape(w) for w in stripped.split()]
    return re.compile(r"(?<![^\W_])" + r"\s+".join(words) + r"(?![^\W_])", re.IGNORECASE)


def load(env) -> Optional[Patterns]:
    """The list, or None where its file cannot be read."""
    where = path(env)
    try:
        with open(where, encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
    except OSError:
        return None
    patterns, broken = [], []
    for number, text in enumerate(lines, 1):
        try:
            regex = compile_line(text)
        except re.error:
            broken.append(number)
            continue
        if regex is not None:
            patterns.append(Pattern(number, regex))
    return Patterns(where, patterns, broken)


def matches(patterns: Patterns, text: str) -> List[int]:
    """The line numbers of the patterns the text matches, in the list's order."""
    if not text:
        return []
    return [p.line for p in patterns.patterns if p.regex.search(text)]


class Added(NamedTuple):
    file: str
    line: int
    text: str


def added_lines(diff: str) -> Iterable[Added]:
    """The lines a unified diff adds, each with its file and its line number
    in the new file; a commit's diff from `git log -p` is read the same way,
    its `commit` lines starting each commit."""
    current, number = "", 0
    for raw in diff.splitlines():
        if raw.startswith("+++ "):
            name = raw[4:]
            current = name[2:] if name.startswith("b/") else name
            continue
        if raw.startswith("@@"):
            m = re.match(r"^@@ -\S+ \+(\d+)(?:,\d+)? @@", raw)
            number = int(m.group(1)) if m else 0
            continue
        if raw.startswith("+"):
            yield Added(current, number, raw[1:])
            number += 1
        elif raw.startswith(" "):
            number += 1


def scan_diff(patterns: Patterns, diff: str) -> List[Tuple[str, int, int]]:
    """(file, line, pattern line) for every added line a pattern matches."""
    out = []
    for added in added_lines(diff):
        for n in matches(patterns, added.text):
            out.append((added.file, added.line, n))
    return out


def scan_fields(patterns: Patterns, fields: Dict[str, str]) -> List[Tuple[str, int]]:
    """(field, pattern line) for every field a pattern matches."""
    out = []
    for name, text in fields.items():
        for n in matches(patterns, text):
            out.append((name, n))
    return out


def missing(where: str) -> str:
    return ("The sensitive-terms check had no list to read (%s is missing), so this text "
            "was not checked for sensitive information the user reports. One pattern a line "
            "makes it." % where)


def broken(patterns: Patterns) -> str:
    return ("Line(s) %s of the sensitive list %s are regular expressions that do not "
            "compile, and checked nothing." % (", ".join(map(str, patterns.broken)),
                                               patterns.path))


def refusal(patterns: Patterns, found: List[Tuple[str, int]]) -> str:
    """The refusal: each place and the pattern's line, never the words."""
    seen, places = set(), []
    for place, n in found:
        if (place, n) not in seen:
            seen.add((place, n))
            places.append("%s: pattern on line %d" % (place, n))
    return ("Refused: this text would carry sensitive information the user reports to a "
            "repository. It matches the private list %s at:\n- %s\nRestate it without what "
            "the pattern names (the list's own line says what), and leave it out of any staged "
            "file too; never copy the list or the matched words into the restatement."
            % (patterns.path, "\n- ".join(places)))
