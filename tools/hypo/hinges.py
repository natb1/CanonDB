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

**The rows.** ``rows`` turns one place into the rows file the
``ai-recorder`` sends unchanged: one entry, one ``update`` of the tab's body
node, guarded by the rev of a read that showed the tab holding its heading
alone, ``# <name>``, as ``ai_tab`` makes one, so that a tab that already
holds an answer refuses it. Its operations are three inserts of markdown at
the tab's end, in the form the renderer writes for a tab held word for word
(``Question.fenced``) and the reader reads back:

    ```text
    <the question>
    ```

    question: in thread · <kind> · answerer: ai · pressure 0 · backlog 0 · load 0

    ## Thesis

    ### ◆ answer of record of <line>/<n>

    assent: none · in thread · provenance: thesis hinge

    ```text
    <the answer, word for word: the second insert, and nothing else>
    ```

    ## Hinge

    ### ⚓ question: what the asking presupposes

    ```text
    <each presupposition on a line, ending with its standing; or nothing>
    ```

    ### ⚓ thesis: what the answer was drawn from

    ```text
    <what the answer was drawn from>
    ```

Every text that comes from the line stands in a code block of its own,
which the document gives back character for character whatever marks,
lines and spacing it holds; its fence is longer than any run of backticks
in it, so no line of it closes the block (``text.fence``). A code block
cannot hold an empty text, one that opens or ends with a line break, a
carriage return or a character XML cannot carry, and only such a text is
refused; nothing is altered. Every other word of the inserts is the tool's
own. The answer carries its own ``Rests on:`` and ``Presupposes:`` lines,
which are words of it; where it presupposes nothing the hinge's question
part says ``nothing``, which ``read`` takes for no presupposition. The
question and its answer are both in thread, so the reader takes the answer
for one of the AI's past held and ``packet.py`` carries it under its
question. The operation id is fixed by the line, the question's number, the
node and every word the inserts carry.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Dict, Iterable, List, NamedTuple, Optional, Tuple

from . import project, text
from .model import ANSWERERS, GLYPHS, KINDS, STATES, Graph, Hinge as Part

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
    if not text.strip() or text.strip().lower().rstrip(".") in NOTHING:
        return []  # the answer presupposed nothing, and the hinge says so
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
#: a line's name, as it stands in a hinge's ending and in the headline: the
#: shape of a question's id, so that it holds no mark
LINE_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
#: what a place's ``came_in_by`` is: the line's name and the question's number
CAME = re.compile(r"^(?P<line>[^/]+)/(?P<n>[1-9][0-9]*)$")
#: a node id as the guard takes it from the ai-recorder
PLAIN_ID = re.compile(r"^[A-Za-z0-9_-]+$")
#: what the hinge's question part says where the answer presupposes nothing
NOTHING_HELD = "nothing"


def came_in_by(placed) -> Tuple[str, int]:
    """The line's name and the question's number a place names."""
    found = CAME.match(placed.get("came_in_by", "")) if isinstance(placed, dict) else None
    if not found or not isinstance(placed.get("came_in_by"), str):
        raise Refused("that is no place this tool printed: it names no <line>/<n>")
    return found["line"], int(found["n"])


def headline(line_name: str, n: int) -> str:
    """The answer's headline: what it is, by the line and the number that
    name it, and nothing of its words, so that it holds no mark."""
    return "answer of record of %s/%d" % (line_name, n)


def held(words: str, what: str) -> str:
    """``words`` in a code block of their own, word for word; refused,
    saying why, where a code block cannot hold them as they stand."""
    if not isinstance(words, str):
        raise Refused("%s is not a text" % what)
    why = text.unfenceable(words)
    if why:
        raise Refused("%s cannot be held word for word in a code block: %s" % (what, why))
    return text.fence(words)


def _insert(content: str) -> dict:
    return {"op": "insert", "target": {"kind": "root"}, "side": "end",
            "source": {"as": "markdown", "from": {"kind": "inline", "content": content}}}


def place_op_id(line_name: str, n: int, node: str, ops: List[dict]) -> str:
    """The operation id of a place's rows, fixed by the line, the question's
    number, the node, in lower case, and every word the inserts carry, so
    that a second sending of the same entry lands once and a changed answer,
    question or kind is a new operation."""
    body = json.dumps({"line": line_name, "n": n, "node": node.lower(), "ops": ops},
                      sort_keys=True, ensure_ascii=False)
    return PLACE_OP + hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]


def blank_tab(blocks: List[Tuple[str, str]]) -> str:
    """The tab's name, where a read of it shows its heading alone, the tab
    as ``ai_tab`` makes it; refused where it holds anything more."""
    if len(blocks) != 1 or not blocks[0][1].startswith("# "):
        raise Refused("the tab holds more than its heading (%d block(s)): an answer is placed "
                      "only on a tab that holds nothing yet" % len(blocks))
    return blocks[0][1][2:].strip()


def rows(placed: dict, node: str, kind: str, listed: Iterable[str], rev: int) -> List[dict]:
    """The rows file for the ``ai-recorder`` that places one answer of
    record at the end of the AI's tab whose body's node id is ``node``,
    which ``listed``, the node ids of the key ``ai_root``, must hold, read
    at ``rev`` holding its heading alone: one entry, its node, the number of
    the question on its line, the payload of one ``update`` guarded by that
    rev, three inserts, and the operation id. ``placed`` is what ``place``
    printed, already checked against the line's directory."""
    if not isinstance(node, str) or not PLAIN_ID.fullmatch(node):
        raise Refused("the node id %r is not a plain id (letters, digits, _ and -)" % (node,))
    if node.lower() not in {n.lower() for n in listed}:
        raise Refused("the key ai_root lists no tab %r: a tab made is the AI's only once "
                      "ai_tab.py add has put it in the key" % node)
    if kind not in KINDS:
        raise Refused("a question's kind is one of %s; got %r" % (", ".join(KINDS), kind))
    if isinstance(rev, bool) or not isinstance(rev, int) or rev < 0:
        raise Refused("the tab's read gives no rev to guard the write by")
    line_name, n = came_in_by(placed)
    if not LINE_NAME.fullmatch(line_name):
        raise Refused("the line's name %r is not lower-case words joined by -" % line_name)
    hinge = placed.get("hinge") if isinstance(placed.get("hinge"), dict) else {}
    heading = {name: "%s %s: %s" % (GLYPHS["hinge"], name, gloss)
               for name, gloss, _ in Part.PARTS}
    head = "\n\n".join((
        held(placed.get("question"), "the question"),
        "question: %s · %s · answerer: %s · pressure 0 · backlog 0 · load 0"
        % (IN_THREAD, kind, ANSWERERS[0]),
        "## Thesis",
        "### %s %s" % (GLYPHS["thesis"], headline(line_name, n)),
        "assent: none · %s · provenance: thesis hinge" % IN_THREAD))
    answer = held(placed.get("answer"), "the answer")
    tail = "\n\n".join((
        "## Hinge",
        "### " + heading["question"],
        held(hinge.get("question") or NOTHING_HELD, "the hinge's question part"),
        "### " + heading["thesis"],
        held(hinge.get("thesis"), "the hinge's thesis part")))
    ops = [_insert(head), _insert(answer), _insert(tail)]
    return [{"node": node, "n": n, "payload": {"ifRev": rev, "ops": ops},
             "op_id": place_op_id(line_name, n, node, ops)}]
