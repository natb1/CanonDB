"""hinges — what a question of the AI's record took for granted, placed and read back.

A question's hinge (``model.Hinge``) holds, in its question part, "what the
asking presupposes", and in its thesis part what the answer was drawn from.
For a question put on a line in the AI's graph, the presuppositions are the
AI's own: the clean turn's answer ends with a ``Presupposes:`` line and then
one presupposition a line, each opening with ``- `` (``clean/answerer.md``).
A draw made before that rule gives them on the label's own line, run
together; they are parted there at each ``that`` a comma or an ``and``
opens, else at the commas and the ``and``. Nothing of the user's record
enters here.

**The place.** A question's answer of record is placed with its question,
its answer word for word, and its presuppositions as the hinge's question
part, each written as one line that ends with its standing:

    <the presupposition> (unjustified; came in by <line>/<n>)

A hinge is justified only by a later answer of the AI's own that it is
linked to; the line then ends ``(justified by <question id>)``, the id of a
question of the AI's that answers past held. Any other line, a hinge's
question part with no such ending among them, is unjustified: it stands on
nothing nearer the root.

**The unjustified.** ``unjustified`` lists every unjustified hinge of the
AI's graph, each with the builds that cite an answer resting on it: the
applications of its own question's answers and of every question below it.

**The rows.** ``rows`` turns one place into the rows entry the
``ai-recorder`` sends unchanged: one ``update`` of the tab's body node whose
operations are three inserts of markdown at the tab's end, on a tab that
holds its heading, ``# <name>``, and nothing else, as ``ai_tab`` makes one.
Together they write the tab in the form the renderer writes and the reader
reads (``render.body``, ``read.parse_tab``), with the sections a place has
and no other:

    *<the question>*

    question: in thread · <kind> · answerer: ai · pressure 0 · backlog 0 · load 0

    ## Thesis

    ### ◆ <the answer's opening words>

    assent: none · in thread · provenance: thesis hinge

    <the answer, word for word: the second insert, and nothing else>

    ## Hinge

    ### ⚓ question: what the asking presupposes

    <each presupposition, a paragraph each, ending with its standing>

    ### ⚓ thesis: what the answer was drawn from

    <what the answer was drawn from>

The answer carries its own ``Rests on:`` and ``Presupposes:`` lines, which
are words of it. The question and its answer are both in thread, the AI's
answer to a question put to it, so the reader takes it for an answer of the
AI's past held and ``packet.py`` carries it under its question. The
headline is the answer's first eight words with every mark taken out; the
answer itself is never altered. The operation id is fixed by the line, the
question's number and the node, so that a second sending lands once.

What the page would not give back as it stands is refused, naming why,
never placed altered: a text with space at its ends, a gap that is not one
blank line, a line indented or ending in a space, a line break inside a
paragraph or a list straight under a paragraph's line (the document joins
the one, ``text-unwrapped``, and parts the other), a block the reader takes
for the layout's own (a heading, a blockquote, a citation heading,
``text-unquoted``), a code fence or a rule, a list marker the page spells
otherwise, a chip or a link into the page, a packet's mark, a backslash, a
bracket, an underscore at a word's edge, and an unpaired star or backtick.
The question is one line and holds no star, as it stands in italics.
"""

from __future__ import annotations

import hashlib
import re
from typing import Dict, Iterable, List, NamedTuple, Optional, Tuple

from . import project
from .model import ANSWERERS, CITATION_HEADINGS, GLYPHS, KINDS, STATES, Graph, Hinge as Part

PRESUPPOSES = "Presupposes:"
RESTS_ON = "Rests on:"
#: what ends a presupposition on a hinge's question part
ENDING = re.compile(r"\s*\((?:unjustified; came in by (?P<came>[^()]+)|justified by "
                    r"(?P<by>[^()\s]+))\)")
NOTHING = ("nothing", "none", "nothing earlier")


class Refused(ValueError):
    """A place this module will not print."""


class Hinge(NamedTuple):
    question: str
    words: str
    came_in_by: Optional[str]
    justified_by: Optional[str]


def labelled(answer: str, label: str) -> Tuple[Optional[str], List[str]]:
    """What follows a labelled line of an answer: the words on the label's
    own line, and the lines under it that open with ``- ``, up to a blank
    line or another label."""
    rows = answer.splitlines()
    for i, row in enumerate(rows):
        if row.strip().startswith(label):
            same = row.strip()[len(label):].strip() or None
            items: List[str] = []
            for nxt in rows[i + 1:]:
                s = nxt.strip()
                if not s:
                    continue
                if not s.startswith("- "):
                    break
                items.append(s[2:].strip())
            return same, items
    return None, []


def run_together(same: str) -> List[str]:
    """Presuppositions given on the label's own line, parted: at each ``that``
    a comma or an ``and`` opens where there are such, else at the commas and
    a closing ``and``."""
    text = same.strip().rstrip(".")
    parts = re.split(r",\s*(?:and\s+)?(?=that\b)|\s+and\s+(?=that\b)", text)
    if len(parts) < 2:
        parts = re.split(r",\s*(?:and\s+)?|\s+and\s+", text)
    return [p.strip() for p in parts if p.strip()]


def presuppositions(answer: str) -> List[str]:
    """The answer's presuppositions, one a line, or on the label's own line
    for a draw made before that rule; refused where it gives none."""
    same, items = labelled(answer, PRESUPPOSES)
    if same is None and not items:
        raise Refused("the answer has no line opening %r with its presuppositions"
                      % PRESUPPOSES)
    if same is not None and items:
        raise Refused("the answer gives presuppositions both on the label's line and under "
                      "it: %r" % same[:60])
    if same is not None:
        items = run_together(same)
    kept = [i for i in items if i.strip().lower().rstrip(".") not in NOTHING]
    for item in kept:
        if "(" in item or ")" in item:
            raise Refused("a presupposition holds a parenthesis, which a hinge's line keeps "
                          "for its standing: %r" % item[:60])
    return kept


def rests_on(answer: str) -> List[str]:
    same, items = labelled(answer, RESTS_ON)
    return items or ([same] if same else [])


def line(words: str, came_in_by: str) -> str:
    return "%s (unjustified; came in by %s)" % (words.rstrip(" ."), came_in_by)


def thesis(line_name: str, n: int, under: Optional[str], model: Optional[str]) -> str:
    """The hinge's thesis part, what the answer was drawn from, in the form
    the notebook's hinges give it."""
    return " · ".join((
        "model: %s" % (model or "not recorded"),
        "harness: a clean turn with no tools, over the line's packet",
        "canon: %s" % ("the AI's answers of %s and above it, and the line %s before question %d"
                       % (under, line_name, n) if under else
                       "the line %s before question %d" % (line_name, n))))


def place(question: str, answer: str, line_name: str, n: int, under: Optional[str],
          model: Optional[str] = None) -> dict:
    """What places one answer of record in the AI's graph: the question, the
    answer, and the hinge's question and thesis parts."""
    came = "%s/%d" % (line_name, n)
    found = presuppositions(answer)
    return {"under": under, "came_in_by": came, "question": question.strip(),
            "answer": answer, "rests_on": rests_on(answer),
            "hinge": {"question": "\n".join(line(p, came) for p in found),
                      "thesis": thesis(line_name, n, under, model)},
            "hinges": [{"words": p, "came_in_by": came, "justified": False} for p in found]}


def read(q) -> List[Hinge]:
    """The presuppositions a question's hinge holds, each with its standing;
    a hinge's question part with no ending is one presupposition, unjustified."""
    text = (q.hinge.question if q.hinge else "") or ""
    if not text.strip():
        return []
    out: List[Hinge] = []
    at = 0
    for m in ENDING.finditer(text):
        words = " ".join(text[at:m.start()].split())
        if words:
            out.append(Hinge(q.id, words, m["came"], m["by"]))
        at = m.end()
    rest = " ".join(text[at:].split())
    if rest:
        out.append(Hinge(q.id, rest, None, None))
    return out


def _ai(q) -> bool:
    return q.answerer == project.AI and q.claude


def unjustified(graph: Graph) -> List[dict]:
    """Every unjustified hinge of the AI's graph, with the builds that cite an
    answer resting on it."""
    by_id = graph.by_id()
    par = project.parents(graph)
    kids: Dict[str, List[str]] = {}
    for child, parent in par.items():
        if parent is not None:
            kids.setdefault(parent, []).append(child)

    def below(qid: str) -> List[str]:
        out, todo = [], [qid]
        while todo:
            cur = todo.pop()
            if cur in out:
                continue
            out.append(cur)
            todo.extend(sorted(kids.get(cur, ())))
        return out

    found: List[dict] = []
    for q in sorted(graph.questions, key=lambda x: x.id):
        if not _ai(q):
            continue
        for h in read(q):
            target = by_id.get(h.justified_by) if h.justified_by else None
            if target is not None and target.id != q.id and _ai(target):
                continue
            builds = []
            for qid in below(q.id):
                for _, app in by_id[qid].applications():
                    builds.append({"question": qid, "application": app.name,
                                   "link": app.link})
            found.append({"question": q.id, "words": h.words, "came_in_by": h.came_in_by,
                          "named": h.justified_by, "builds": builds})
    return found


# -- the rows that place an answer on its tab ---------------------------------

#: the states the placed question and its answer stand in: put, and answered
#: in a turn, and not landed
IN_THREAD = STATES[1]
#: what a place's operation id opens with
PLACE_OP = "ai-place-"
#: how many of the answer's opening words its headline takes
HEADLINE_WORDS = 8
#: what a place's ``came_in_by`` is: the line's name and the question's number
CAME = re.compile(r"^(?P<line>[^\s/][^/]*)/(?P<n>[1-9][0-9]*)$")
#: a node id as the guard takes it from the ai-recorder
PLAIN_ID = re.compile(r"^[A-Za-z0-9_-]+$")

#: a line that opens a list item, and its marker
_ITEM = re.compile(r"^(?P<marker>[-*+]|\d+[.)])[ \t]")
#: a heading's mark, as the page reads one (``read``, ``text-unquoted``)
_HEADING = re.compile(r"^#{1,6}(?:[ \t]|$)")
#: a code fence, and a rule
_FENCE = re.compile(r"^(?:```|~~~)")
_RULE = re.compile(r"^([-*_])(?:[ \t]*\1){2,}[ \t]*$")
#: what the reader takes off a text: a chip, a chip as exported, a link into
#: the page (``read.PLACED_CHIP``, ``read.IN_PAGE_LINK``)
_TAKEN_OFF = re.compile(r"<\?claude block|\]\(file/|\]\((?:https?://[^)#]*/artifact/[^)#]*)?#")
#: a packet's marks, which no question or answer may hold (``packet.BOUNDARY``)
_MARKS = ("<<<", ">>>")
#: an underscore at a word's edge, which markdown may read as emphasis
_EDGE_UNDERSCORE = re.compile(r"(?<![0-9A-Za-z])_|_(?![0-9A-Za-z])")
#: a star standing alone between spaces, which markdown reads as no mark
_LONE_STAR = re.compile(r"(?:^|\s)\*+(?:\s|$)")
#: what a headline's words lose: every character markdown reads as a mark
_HEADLINE_MARKS = re.compile(r"[\\*_`\[\]()<>#|~]")


def unheld(words: str, what: str) -> Optional[str]:
    """Why the page would not give ``words`` back as they stand, or None.

    The page joins a wrapped line into its paragraph and parts a list from
    a paragraph line above it; the reader takes a heading, a blockquote and
    a citation heading for the layout's own and takes chips and links into
    the page off; the page's speller writes a mark it reads in the text as
    a mark, and a literal one behind a backslash. Each of those would bring
    the words back other than they went in."""
    if words != words.strip():
        return "%s has space at its ends, which the page does not keep" % what
    if not words:
        return "%s is empty" % what
    if "\r" in words or "\t" in words:
        return "%s holds a carriage return or a tab, which the page does not keep" % what
    for mark in _MARKS:
        if mark in words:
            return "%s holds %r, which marks a packet's parts" % (what, mark)
    if _TAKEN_OFF.search(words):
        return "%s holds a chip or a link into the page, which the reader takes off" % what
    if "\\" in words:
        return ("%s holds a backslash, which the page reads as an escape and the reader may "
                "take off" % what)
    if "[" in words or "]" in words:
        return ("%s holds a bracket, which the page spells back as a link or behind a "
                "backslash" % what)
    if _EDGE_UNDERSCORE.search(words):
        return ("%s holds an underscore at a word's edge, which the page may read as emphasis "
                "and spell with a star" % what)
    for block in words.split("\n\n"):
        why = _block_unheld(block, what)
        if why:
            return why
    return None


def _block_unheld(block: str, what: str) -> Optional[str]:
    rows = block.split("\n")
    for row in rows:
        if row != row.strip():
            return ("%s has a line indented, ending in a space or holding spaces alone, "
                    "which the page indents again, reads as a break or drops: %r"
                    % (what, row[:60]))
        if not row:
            return ("%s parts its blocks by more than one blank line, which the page gives "
                    "back as one" % what)
        if _FENCE.match(row) or _RULE.match(row):
            return ("%s holds a code fence or a rule, which a tab of the notebook does not "
                    "hold: %r" % (what, row[:60]))
    first = rows[0]
    if _HEADING.match(first):
        return ("%s opens a block on #, which the reader takes for a heading and ends the "
                "text at: %r" % (what, first[:60]))
    if first.startswith(">"):
        return ("%s holds a blockquote, which the reader takes for a note: %r"
                % (what, first[:60]))
    if block in CITATION_HEADINGS:
        return ("%s holds a block reading %s, which the reader takes for the heading that "
                "opens the citations" % (what, block))
    items = [_ITEM.match(row) for row in rows]
    if len(rows) > 1 and not all(items):
        return ("%s breaks a line inside a paragraph, or opens a list straight under a "
                "paragraph's line: the document joins the one and parts the other with a "
                "blank line: %r" % (what, block[:60]))
    found = [m.group("marker") for m in items if m]
    if found:
        if all(m == "-" for m in found):
            pass
        elif all(m.endswith(".") and m[:-1].isdigit() for m in found) and \
                [int(m[:-1]) for m in found] == list(range(1, len(found) + 1)):
            pass
        else:
            return ("%s holds a list whose markers the page spells otherwise, as - or as "
                    "1. 2. 3.: %r" % (what, block[:60]))
    for row in rows:
        text = row[_ITEM.match(row).end():] if _ITEM.match(row) else row
        if _LONE_STAR.search(text) or text.count("*") % 2 or text.count("`") % 2:
            return ("%s holds a star or a backtick the page would read as no mark and spell "
                    "behind a backslash: %r" % (what, row[:60]))
    return None


def _refuse(words: str, what: str) -> str:
    why = unheld(words, what)
    if why:
        raise Refused(why)
    return words


def headline(answer: str) -> str:
    """The answer's opening words, which name it where another answer rests
    on it: the first line's first eight words, a list's marker and every
    mark taken out."""
    first = answer.strip().split("\n", 1)[0]
    item = _ITEM.match(first)
    if item:
        first = first[item.end():]
    words = [_HEADLINE_MARKS.sub("", w) for w in first.split()]
    words = [w for w in words if w][:HEADLINE_WORDS]
    out = " ".join(words).rstrip(" ,;:")
    if not out:
        raise Refused("the answer's first line gives no words for its headline")
    return out


def place_op_id(line_name: str, n: int, node: str) -> str:
    """The operation id of a place's rows, fixed by the line, the question's
    number and the node, in lower case, as the guard compares it."""
    digest = hashlib.sha256("\x00".join(("place", line_name, str(n), node.lower()))
                            .encode("utf-8")).hexdigest()[:16]
    return PLACE_OP + digest


def _insert(content: str) -> dict:
    return {"op": "insert", "target": {"kind": "root"}, "side": "end",
            "source": {"as": "markdown", "from": {"kind": "inline", "content": content}}}


def _checked(placed) -> Tuple[str, int]:
    """The place as ``place`` prints it from its own answer, or refused;
    the line's name and the question's number."""
    if not isinstance(placed, dict):
        raise Refused("that is no place this tool printed")
    for key, kind in (("question", str), ("answer", str), ("came_in_by", str),
                      ("rests_on", list), ("hinge", dict)):
        if not isinstance(placed.get(key), kind):
            raise Refused("the place gives no %s" % key)
    came = CAME.match(placed["came_in_by"])
    if not came:
        raise Refused("the place's came_in_by is not <line>/<n>: %r" % placed["came_in_by"])
    hinge = placed["hinge"]
    if not isinstance(hinge.get("question"), str) or not isinstance(hinge.get("thesis"), str):
        raise Refused("the place's hinge gives no question part or no thesis part")
    answer = placed["answer"]
    want = "\n".join(line(p, placed["came_in_by"]) for p in presuppositions(answer))
    if hinge["question"] != want or placed["rests_on"] != rests_on(answer):
        raise Refused("the place's hinge or its Rests on is not what place prints from its "
                      "own answer")
    lowered = hinge["thesis"].lower()
    if "\n" in hinge["thesis"] or not all(m in lowered for m in ("model:", "harness:",
                                                                 "canon:")):
        raise Refused("the hinge's thesis part is not one line naming a model, a harness and "
                      "a canon")
    return came["line"], int(came["n"])


def rows(placed: dict, node: str, kind: str, listed: Iterable[str]) -> dict:
    """The rows entry for the ``ai-recorder`` that places one answer of
    record at the end of the AI's tab whose body's node id is ``node``,
    which ``listed``, the node ids of the key ``ai_root``, must hold: its
    node, the payload of one ``update``, three inserts, and the operation
    id."""
    if not isinstance(node, str) or not PLAIN_ID.fullmatch(node):
        raise Refused("the node id %r is not a plain id (letters, digits, _ and -)" % (node,))
    if node.lower() not in {n.lower() for n in listed}:
        raise Refused("the key ai_root lists no tab %r: a tab made is the AI's only once "
                      "ai_tab.py add has put it in the key" % node)
    if kind not in KINDS:
        raise Refused("a question's kind is one of %s; got %r" % (", ".join(KINDS), kind))
    line_name, n = _checked(placed)
    question, answer = placed["question"], placed["answer"]
    _refuse(question, "the question")
    if "\n" in question or "*" in question:
        raise Refused("the question breaks a line or holds a star, and it stands as one line "
                      "in italics")
    _refuse(answer, "the answer")
    parts = [p for p in placed["hinge"]["question"].split("\n") if p]
    for p in parts:
        _refuse(p, "a presupposition")
    _refuse(placed["hinge"]["thesis"], "the hinge's thesis part")
    title = headline(answer)
    heading = {name: "%s %s: %s" % (GLYPHS["hinge"], name, gloss)
               for name, gloss, _ in Part.PARTS}
    head = "\n\n".join((
        "*%s*" % question,
        "question: %s · %s · answerer: %s · pressure 0 · backlog 0 · load 0"
        % (IN_THREAD, kind, ANSWERERS[0]),
        "## Thesis",
        "### %s %s" % (GLYPHS["thesis"], title),
        "assent: none · %s · provenance: thesis hinge" % IN_THREAD))
    tail = ["## Hinge"]
    if parts:
        tail += ["### " + heading["question"]] + parts
    tail += ["### " + heading["thesis"], placed["hinge"]["thesis"]]
    return {"node": node,
            "payload": {"ops": [_insert(head), _insert(answer), _insert("\n\n".join(tail))]},
            "op_id": place_op_id(line_name, n, node)}
