"""The brief and the neighbourhood: the notebook kept in front of a session.

A projection of the graph, written by a tool and never by hand, that the
harness puts in a session's context at its start and after a compaction, and
that a hook gives a helper at its start. Two parts:

- **the standing brief**: the conventions; each project's end and method;
  the open lines by title; the glossary index, each word with the first
  sentence of its entry;
- **the neighbourhood** of the line in hand: for each principle of the line,
  its lineage, the chain from the root down to it, each step by the headline
  of the answer that raised the next question and the sentence of that answer
  the term edge anchors (the sentence that raised it), then the principle's
  own answer sentence by sentence; the glossary entries of the terms in play;
  the tradition edges on the principle's answers; and the standing sentences
  of other answers that share its fixed terms.

Nothing is composed. Every line is a whole sentence, or a whole part, as the
tab holds it, behind its id in brackets, and the tool's own words are the
headings, the header and the names of the checks. A side restricts what is
read: ``all`` reads the user's, the AI's and the tradition parties'
questions; ``ai`` only the AI's own answers (an answer past held on a
question of the author's, as ``public.own`` reads it), for a context that
must stay blind to the user's graph, and there the conventions are the
checks' names alone.

**Size and compaction.** Each part has a maximum (standing 14,000 characters,
neighbourhood 10,000, so 24,000 together, the target), and the two together a
hard ceiling of 32,000 that only the conventions can push them toward, since
those are never left out. Compaction is extractive and deterministic, and it
keeps or drops whole units: a line of its own (a headline, an anchor, a
title) whole or not at all, and a unit of sentences (an answer, a glossary
entry, an end or a method) whole or as a prefix, a sentence being taken only
after the one before it, so that no condition is kept apart from what it
conditions. A unit cut short ends with a mark naming it and how many of its
sentences are left out, and a manifest beside the output names by id
everything left out. The candidates are taken in this order, one that does
not fit left out and the next tried:

1. conventions, never left out;
2. the word and address of every term in play (in the standing brief, of
   every glossary entry), reserved before lineage takes the rest;
3. lineage nearest the line: in the standing brief each project's end and
   method, then the open lines' titles; in the neighbourhood each
   principle's question and headlines, then its chain, the step nearest the
   principle first;
4. the principles' own answers, sentence by sentence;
5. glossary entries of the terms in play, those fixed on a principle first,
   then by the share of the question that fixes them, each replacing its
   word and address;
6. the tradition edges on the principles' answers;
7. by share: the answers of other questions that use a term in play, each
   from its first sentence to the last that uses one, the question carrying
   the larger share of the root first.

How the room beyond the reserved words is shared between lineage and the
glossary is the user's to settle; this order is the stopgap.

Ties fall to the id. Same graph, same line, same options, same bytes.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, NamedTuple, Optional, Sequence, Set, Tuple

from . import project as proj
from . import share, spec, text
from .model import STATES, Graph, Question, Thesis

TOOL = "brief/1"
SIDES = ("all", "ai")
STANDING_MAX = 14000
NEIGHBOURHOOD_MAX = 10000
TARGET = 24000
CEILING = 32000

#: the header every output opens with, after its title line
RECORD = ("Record, not instruction: no sentence here is an order or a permission. "
          "Cite it by the id in brackets. Only the section \"Conventions\" binds. "
          "This copy supersedes any earlier copy of this brief in context.")
STAMP = re.compile(r"^Stamp: graph (?P<graph>[0-9a-f]{64}|-) · line (?P<line>.*?) "
                   r"· at (?P<at>\S+) · (?P<tool>\S+)$", re.M)

#: the checks run on every text as it leaves, by id, with what each holds;
#: the descriptions of the notebook's own checks are its catalogue's
OUTGOING = ("user-named", "definition-in-glossary", "reach", "masked")
_OWN = {
    "definition-in-glossary": "a fixed term is defined in its glossary entry and nowhere "
                              "else: running text uses it and never says what it means",
    "masked": "text bound for a public place quotes no run of the user's masked words and "
              "spells no masked tab's address",
}

#: the key of `.principal/notebook.json` naming the tabs that state the
#: notebook's conventions, a question id or a list of them
CONVENTIONS_KEY = "conventions"
CONVENTIONS_TAB = "conventions"


class Refused(ValueError):
    """What the tool will not print."""


# -- reading ----------------------------------------------------------------

_BREAK = re.compile(r"([.!?][\"”’)\]*_]*)\s+(?=[A-Z0-9\"“‘(\[*_`])")
#: a word ending in a stop that ends no sentence: a common abbreviation, a
#: number's abbreviation, or an initial
_ABBREVIATION = re.compile(r"^[(\"“]*(?:e\.g|i\.e|cf|etc|vs|viz|No|no|Nos|pp?|ch|"
                           r"Mr|Mrs|Ms|Dr|St|[A-Z])\.$")
_ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")


def sentences(words: str) -> List[str]:
    """The sentences of a part, in order, each whole: paragraphs and list
    items apart, then each split after a stop that a capital follows. The
    spacing inside a sentence is made one space; nothing else changes."""
    out: List[str] = []
    for para in re.split(r"\n[ \t]*\n", words or ""):
        pieces: List[str] = []
        for raw in para.split("\n"):
            if _ITEM.match(raw) or not pieces:
                pieces.append(raw)
            else:
                pieces[-1] += " " + raw
        for piece in pieces:
            flat = " ".join(piece.split())
            if not flat:
                continue
            start = 0
            for m in _BREAK.finditer(flat):
                before = flat[start:m.end(1)].rsplit(" ", 1)[-1]
                if _ABBREVIATION.match(before):
                    continue
                out.append(flat[start:m.end(1)])
                start = m.end()
            out.append(flat[start:])
    return [s for s in out if s.strip()]


def fingerprint(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def mine(q: Question, t: Thesis) -> bool:
    """An answer of the AI's own: past held, on a question of the author's."""
    return not q.tradition and t.state != STATES[0]


def seen(q: Question, t: Thesis, side: str) -> bool:
    return side == "all" or mine(q, t)


def visible(q: Question, side: str) -> bool:
    return side == "all" or any(mine(q, t) for t in q.theses)


def conventions_of(graph: Graph, named: Optional[Sequence[str]] = None) -> List[str]:
    """The questions stating the notebook's conventions: those named, else
    the tab the notebook calls `conventions`, where it has one."""
    by_id = graph.by_id()
    if named:
        missing = [n for n in named if resolve_one(graph, n) is None]
        if missing:
            raise Refused(["no question %s states conventions" % ", ".join(missing)])
        return [resolve_one(graph, n).id for n in named]
    return [CONVENTIONS_TAB] if CONVENTIONS_TAB in by_id else []


def notebook_conventions(root: Optional[str]) -> List[str]:
    """The `conventions` key of the project's `.principal/notebook.json`."""
    if not root:
        return []
    try:
        with open(os.path.join(root, ".principal", "notebook.json"), encoding="utf-8") as fh:
            value = json.load(fh).get(CONVENTIONS_KEY)
    except (OSError, ValueError, AttributeError):
        return []
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    if isinstance(value, list):
        return [v.strip() for v in value if isinstance(v, str) and v.strip()]
    return []


def resolve_one(graph: Graph, name: str) -> Optional[Question]:
    for q in graph.questions:
        if name == q.id or name.lower() == q.tab.lower():
            return q
    return None


def resolve(graph: Graph, names: Iterable[str], lines: Optional[Dict[str, dict]] = None
            ) -> List[str]:
    """The questions of the line in hand, by question id, tab id, or an open
    line's id, whose anchors name its tabs; refused where a name is none."""
    out: List[str] = []
    missing: List[str] = []
    for name in names:
        for part in [p for p in re.split(r"[,\s]+", name) if p]:
            q = resolve_one(graph, part)
            found = [q.id] if q else []
            if not found and lines and part in lines:
                for anchor in lines[part].get("anchors") or []:
                    if isinstance(anchor, dict) and isinstance(anchor.get("tab"), str):
                        hit = resolve_one(graph, anchor["tab"])
                        if hit:
                            found.append(hit.id)
            if not found:
                missing.append(part)
            for f in found:
                if f not in out:
                    out.append(f)
    if missing:
        raise Refused(["the line names %s, which is no question, tab or open line of the "
                       "graph" % ", ".join(missing)])
    return out


def vocabulary(graph: Graph, side: str):
    """The fixed terms: every word a glossary fixes, longest first. A blind
    context reads no glossary, and fixes none."""
    if side != "all":
        return {}, []
    senses = spec._senses(graph)
    return senses, spec._vocabulary(senses)


def terms_in(vocab, words: str) -> List[str]:
    return [w for w, _ in spec._words_used(vocab, words)] if vocab else []


# -- items and their choice -------------------------------------------------

@dataclass
class Item:
    id: str
    tier: int
    rank: tuple
    section: str
    line: str
    keep: bool = False
    #: what renders it: the principle a lineage line is under, and its depth
    group: str = ""
    depth: int = 0
    #: the item before it in its unit: a sentence is taken only after the
    #: one before it, so a unit is kept whole or as a prefix, never with a
    #: gap
    needs: str = ""
    #: the unit it is a sentence of (an answer, an entry, a part), whose cut
    #: is marked where it falls
    unit: str = ""
    #: the floor this item stands in for once taken: an entry's first
    #: sentence replaces the word and address reserved for it
    upgrades: str = ""
    #: a floor: the word and address of a term in play, reserved before
    #: lineage takes the rest
    floor: bool = False

    @property
    def cost(self) -> int:
        return len(self.line) + 1


class Choice(NamedTuple):
    taken: List[Item]
    left: List[Item]
    #: the floors an entry's first sentence replaced, not rendered
    replaced: Set[str]


def choose(items: List[Item], room: int) -> Choice:
    """The items taken in priority order within ``room`` characters. The
    conventions are always taken; a sentence only after the one before it in
    its unit; an entry's first sentence in place of its floor, paying only
    the difference."""
    by_id = {i.id: i for i in items}
    taken: List[Item] = []
    ids: Set[str] = set()
    replaced: Set[str] = set()
    used = 0
    for it in sorted(items, key=lambda i: (i.tier, i.rank, i.id)):
        if it.id in ids:
            continue
        if it.needs and it.needs not in ids:
            continue
        cost = it.cost
        if it.upgrades and it.upgrades in ids:
            cost -= by_id[it.upgrades].cost
        if it.keep or used + cost <= room:
            taken.append(it)
            ids.add(it.id)
            used += cost
            if it.upgrades and it.upgrades in ids:
                replaced.add(it.upgrades)
    left = [it for it in items if it.id not in ids and not it.floor]
    return Choice(taken, left, replaced)


def _quote(words: str) -> str:
    return " ".join((words or "").split())


@dataclass
class Output:
    text: str
    manifest: dict


def header(title: str, digest: str, line: Sequence[str], at: Optional[str]) -> List[str]:
    return ["# %s" % title, "", RECORD,
            "Stamp: graph %s · line %s · at %s · %s"
            % (digest or "-", " ".join(line) if line else "-", at or "unstated", TOOL), ""]


def _fit(items: List[Item], limit: int, render) -> Tuple[str, Choice]:
    """Render within ``limit``: the room given to the items shrinks by what
    the rendering ran over, until it fits or nothing but the conventions is
    left."""
    room = limit
    while True:
        choice = choose(items, max(room, 0))
        out = render(choice)
        if len(out) <= limit or room <= 0:
            return out, choice
        room -= len(out) - limit


def _manifest(mode: str, side: str, digest: str, line, at, limit: int, out: str,
              choice: Choice) -> dict:
    floors = {i.id for i in choice.taken if i.floor} - choice.replaced
    left = sorted({i.id for i in choice.left})
    return {"tool": TOOL, "mode": mode, "side": side, "graph_sha256": digest,
            "line": list(line), "at": at, "chars": len(out), "max": limit,
            "order": list(ORDER),
            "included": sorted({i.id for i in choice.taken if not i.floor}),
            "kept_as_word_and_address": sorted(floors),
            "cut": sorted(_cuts(choice)),
            "left_out": left}


ORDER = ("conventions", "the word and address of every term in play",
         "lineage nearest the line", "the principles' own answers",
         "glossary entries of the terms in play", "tradition on the line", "by share")


def _cuts(choice: Choice) -> Dict[str, int]:
    """Each unit kept as a prefix, with how many of its sentences are left
    out."""
    kept = {i.unit for i in choice.taken if i.unit}
    out: Dict[str, int] = {}
    for i in choice.left:
        if i.unit and i.unit in kept:
            out[i.unit] = out.get(i.unit, 0) + 1
    return out


def _mark(unit: str, n: int, indent: str = "") -> str:
    return "%s[%s …] cut here: %d more sentence(s) of this left out, each named in " \
           "the manifest" % (indent, unit, n)


def _omitted(choice: Choice) -> str:
    floors = len({i.id for i in choice.taken if i.floor} - choice.replaced)
    left = {i.id for i in choice.left}
    if not left and not floors:
        return "Left out: nothing."
    return ("Left out: %d line(s)%s, each named by id in the manifest beside this copy."
            % (len(left), "; %d entry(ies) kept as word and address" % floors if floors
               else ""))


def _rows(choice: Choice, section: str, group: Optional[str] = None) -> List[str]:
    """The lines of a section in reading order, each unit's cut marked after
    the last of its sentences kept."""
    cuts = _cuts(choice)
    rows = [i for i in choice.taken if i.section == section and i.id not in choice.replaced
            and (group is None or i.group == group)]
    rows.sort(key=lambda i: (i.depth, i.tier if not i.unit else 0, i.rank, i.id)
              if group is not None else (i.rank, i.id))
    out: List[str] = []
    for n, i in enumerate(rows):
        indent = "  " * i.depth if group is not None else ""
        out.append(indent + i.line)
        nxt = rows[n + 1] if n + 1 < len(rows) else None
        if i.unit and i.unit in cuts and (nxt is None or nxt.unit != i.unit):
            out.append(_mark(i.unit, cuts[i.unit], indent))
    return out


# -- the standing brief -----------------------------------------------------

def _check_lines() -> List[Tuple[str, str]]:
    known = {cid: desc for cid, _, desc in spec.catalogue()}
    return [(cid, known.get(cid) or _OWN[cid]) for cid in OUTGOING]


def _conventions(graph: Graph, side: str, named: Sequence[str]) -> List[Item]:
    items: List[Item] = []
    by_id = graph.by_id()
    for n, qid in enumerate(named):
        q = by_id[qid]
        for k, t in enumerate(q.theses, 1):
            if not seen(q, t, side):
                continue
            for s, sentence in enumerate(sentences(t.text), 1):
                items.append(Item("%s/a%d.s%d" % (qid, k, s), 0, (0, n, k, s), "conventions",
                                  "[%s/a%d.s%d] %s" % (qid, k, s, sentence), keep=True))
    for n, (cid, desc) in enumerate(_check_lines()):
        items.append(Item("check:" + cid, 0, (1, n), "conventions",
                          "[check:%s] %s" % (cid, desc), keep=True))
    return items


def _chain(base: str, words: List[str], tier: int, rank: tuple, section: str, line,
           **more) -> List[Item]:
    """A unit's sentences, each taken only after the one before it."""
    out: List[Item] = []
    for s, sentence in enumerate(words, 1):
        iid = "%s.s%d" % (base, s)
        out.append(Item(iid, tier, rank + (s,), section, line(iid, s, sentence),
                        needs="%s.s%d" % (base, s - 1) if s > 1 else "", unit=base, **more))
    return out


def _ends(graph: Graph) -> List[Item]:
    items: List[Item] = []
    by_id = graph.by_id()
    for n, rid in enumerate(proj.project_roots(graph)):
        q = by_id[rid]
        if q.hinge is None:
            continue
        for p, part in enumerate(("end", "method")):
            items += _chain("%s/%s" % (rid, part), sentences(getattr(q.hinge, part)), 2,
                            (n, p), "ends",
                            lambda iid, s, w, part=part: "[%s] %s%s" % (
                                iid, part + ": " if s == 1 else "", w))
    return items


def _open_lines(lines: Optional[Dict[str, dict]]) -> List[Item]:
    items: List[Item] = []
    for lid, rec in sorted((lines or {}).items()):
        if rec.get("state") not in ("open", "put") or not isinstance(rec.get("title"), str):
            continue
        rank = rec.get("rank")
        rank = rank if isinstance(rank, (int, float)) and not isinstance(rank, bool) else 1e9
        put = 0 if rec.get("state") == "put" else 1
        items.append(Item("lines/" + lid, 3, (put, rank, lid), "lines",
                          "[lines/%s] %s%s" % (lid, _quote(rec["title"]),
                                               " (put now)" if put == 0 else "")))
    return items


def _glossary(graph: Graph, shares: Dict[str, float], first: Set[str], only: Optional[Set[str]],
              tier: int, section: str) -> List[Item]:
    """Glossary entries: for each, its word and address as a floor, taken
    right after the conventions, then its sentences in order at ``tier``,
    the first replacing the floor."""
    items: List[Item] = []
    for q in graph.questions:
        for d in q.definitions:
            word = text.fold(d.word)
            if only is not None and word not in only:
                continue
            base = "%s/≡%s" % (q.id, d.word)
            rank_q = (0 if q.id in first else 1, -shares.get(q.id, 0.0), q.id, word)
            body = sentences(d.body) if d.body.strip() else []
            if not body and d.tradition is not None:
                body = ["imported from %s" % d.tradition.to]
            items.append(Item(base, 1, rank_q + (0,), section, "[%s] ≡ %s" % (base, d.word),
                              floor=True))
            entry = _chain(base, body, tier, rank_q + (1,), section,
                           lambda iid, s, w, word=d.word: (
                               "[%s] ≡ %s: %s" % (iid, word, w) if s == 1
                               else "[%s]   %s" % (iid, w)))
            if entry:
                entry[0].upgrades = base
            items += entry
    return items


def _answers_index(graph: Graph, shares: Dict[str, float]) -> List[Item]:
    items: List[Item] = []
    for q in graph.questions:
        for k, t in enumerate(q.theses, 1):
            if mine(q, t):
                iid = "%s/a%d.h" % (q.id, k)
                items.append(Item(iid, 3, (-shares.get(q.id, 0.0), q.id, k), "answers",
                                  "[%s] %s" % (iid, _quote(t.title))))
    return items


SECTIONS_STANDING = (("conventions", "Conventions"), ("ends", "Ends and methods"),
                     ("lines", "Open lines"), ("glossary", "Glossary index"),
                     ("answers", "The AI's answers"))


def _render_sections(head: List[str], order, choice: Choice) -> str:
    out = list(head)
    for key, title in order:
        rows = _rows(choice, key)
        if not rows:
            continue
        out.append("## %s" % title)
        out.extend(rows)
        out.append("")
    out.append(_omitted(choice))
    return "\n".join(out) + "\n"


def standing(graph: Graph, digest: str, side: str = "all", at: Optional[str] = None,
             lines: Optional[Dict[str, dict]] = None, conventions: Sequence[str] = (),
             limit: int = STANDING_MAX, ceiling: int = CEILING) -> Output:
    if side not in SIDES:
        raise Refused(["the side is all or ai"])
    shares = share.shares(graph)
    items = _conventions(graph, side, conventions)
    if side == "all":
        items += _ends(graph) + _open_lines(lines)
        items += _glossary(graph, shares, set(), None, 4, "glossary")
    else:
        items += _answers_index(graph, shares)
    head = header("Brief: standing (side %s)" % side, digest, [], at)
    out, choice = _fit(items, limit, lambda c: _render_sections(head, SECTIONS_STANDING, c))
    if len(out) > ceiling:
        raise Refused(["the conventions alone hold %d characters, over the ceiling of %d"
                       % (len(out), ceiling)])
    return Output(out, _manifest("standing", side, digest, [], at, limit, out, choice))


# -- the neighbourhood ------------------------------------------------------

def _edge(graph: Graph, parent: str, child: str, side: str):
    """The answer of ``parent`` whose term raised ``child``, its index, and
    the term's index; None where none it may show does."""
    q = graph.get(parent)
    if q is None:
        return None
    for k, t in enumerate(q.theses, 1):
        if not seen(q, t, side):
            continue
        for m, term in enumerate(t.terms, 1):
            if term.to == child:
                return q, k, t, m, term
    return None


def _lineage(graph: Graph, pid: str, n: int, side: str, par) -> List[Item]:
    """One principle's lineage: its question and headlines and the chain
    above it (tier 2, nearest the principle first), then its own answers,
    each a unit of sentences (tier 3)."""
    items: List[Item] = []
    q = graph.get(pid)
    chain = proj.lineage(graph, pid, par)
    depth = len(chain) - 1
    if visible(q, side):
        items.append(Item("%s/q" % pid, 2, (0, n, 0), "lineage",
                          "[%s/q] %s: %s" % (pid, q.id, _quote(q.question)),
                          group=pid, depth=depth))
    for k, t in enumerate(q.theses, 1):
        if not seen(q, t, side):
            continue
        items.append(Item("%s/a%d.h" % (pid, k), 2, (0, n, 1, k), "lineage",
                          "[%s/a%d.h] %s" % (pid, k, _quote(t.title)), group=pid, depth=depth))
        items += _chain("%s/a%d" % (pid, k), sentences(t.text), 3, (n, k), "lineage",
                        lambda iid, s, w: "[%s] %s" % (iid, w), group=pid, depth=depth + 1)
    for i in range(len(chain) - 1):
        parent, child = chain[i], chain[i + 1]
        dist = len(chain) - 1 - i
        found = _edge(graph, parent, child, side)
        if found is None:
            continue
        _, k, t, m, term = found
        items.append(Item("%s/a%d.h" % (parent, k), 2, (dist, n, 0), "lineage",
                          "[%s/a%d.h] %s: %s" % (parent, k, parent, _quote(t.title)),
                          group=pid, depth=i))
        for a, anchor in enumerate(term.anchors, 1):
            iid = "%s/a%d.t%d.%d" % (parent, k, m, a)
            items.append(Item(iid, 2, (dist, n, 1, a), "lineage",
                              "[%s] raises %s: \"%s\"" % (iid, child, _quote(anchor)),
                              group=pid, depth=i))
    return items


def chain_lines(graph: Graph, qid: str, side: str = "all") -> List[str]:
    """A question's chain from the root, its own question and headlines
    last, as the neighbourhood prints it."""
    items = [i for i in _lineage(graph, qid, 0, side, proj.parents(graph)) if i.tier == 2]
    return ["  " * i.depth + i.line for i in sorted(items, key=lambda i: (i.depth, i.rank, i.id))]


def _traditions(graph: Graph, principles: List[str]) -> List[Item]:
    items: List[Item] = []
    by_id = graph.by_id()
    for n, pid in enumerate(principles):
        q = by_id[pid]
        for k, t in enumerate(q.theses, 1):
            for e, edge in enumerate(t.traditions, 1):
                iid = "%s/a%d.x%d" % (pid, k, e)
                note = _quote("%s %s" % (edge.note, edge.counter))
                items.append(Item(iid, 5, (n, k, e), "tradition",
                                  "[%s] %s %s%s" % (iid, edge.relation, edge.to,
                                                    ": " + note if note else "")))
    return items


def _sharing(graph: Graph, principles: List[str], terms: Set[str], vocab, shares,
             side: str) -> List[Item]:
    """The answers of other questions that use a term in play, each as a
    unit from its first sentence to the last that uses one, so that no
    sentence stands without those before it."""
    items: List[Item] = []
    if not terms:
        return items
    for q in graph.questions:
        if q.id in principles:
            continue
        for k, t in enumerate(q.theses, 1):
            if not seen(q, t, side):
                continue
            words = sentences(t.text)
            uses = [[w for w in terms_in(vocab, s) if w in terms] for s in words]
            last = max((i for i, u in enumerate(uses) if u), default=-1)
            if last < 0:
                continue
            items += _chain("%s/a%d" % (q.id, k), words[:last + 1], 6,
                            (-shares.get(q.id, 0.0), q.id, k), "sharing",
                            lambda iid, s, w, uses=uses: "[%s] %s%s" % (
                                iid, "(%s) " % ", ".join(sorted(set(uses[s - 1])))
                                if uses[s - 1] else "", w))
    return items


def in_play(graph: Graph, principles: List[str], vocab, side: str,
            more: str = "") -> Set[str]:
    """The fixed terms in play: those the principles' answers use, those
    their questions fix, and those of ``more``, a prompt."""
    out: Set[str] = set(terms_in(vocab, more))
    by_id = graph.by_id()
    for pid in principles:
        q = by_id[pid]
        for t in q.theses:
            if seen(q, t, side):
                out.update(terms_in(vocab, t.title + "\n\n" + t.text))
        if side == "all":
            out.update(text.fold(d.word) for d in q.definitions)
    return out


def _render_neighbourhood(head: List[str], principles: List[str], choice: Choice) -> str:
    out = list(head)
    out.append("## The line")
    out.append(", ".join(principles))
    out.append("")
    if any(i.section == "lineage" for i in choice.taken):
        out.append("## Lineage")
        for pid in principles:
            rows = _rows(choice, "lineage", pid)
            if rows:
                out.append("### %s" % pid)
                out.extend(rows)
        out.append("")
    for key, title in (("glossary", "Glossary of the terms in play"),
                       ("tradition", "Tradition on the line"),
                       ("sharing", "Answers sharing its terms")):
        rows = _rows(choice, key)
        if rows:
            out.append("## %s" % title)
            out.extend(rows)
            out.append("")
    out.append(_omitted(choice))
    return "\n".join(out) + "\n"


def neighbourhood(graph: Graph, digest: str, principles: List[str], side: str = "all",
                  at: Optional[str] = None, limit: int = NEIGHBOURHOOD_MAX,
                  more: str = "", title: str = "") -> Output:
    if side not in SIDES:
        raise Refused(["the side is all or ai"])
    if not principles:
        raise Refused(["the line names no question"])
    shares = share.shares(graph)
    _, words = vocabulary(graph, side)
    terms = in_play(graph, principles, words, side, more)
    par = proj.parents(graph)
    items: List[Item] = []
    listed: Set[str] = set()
    for n, pid in enumerate(principles):
        # a shared ancestor is listed under each principle it stands above,
        # each its own line: where an earlier principle listed it, its id
        # names the principle it is listed under too
        mine_ = _lineage(graph, pid, n, side, par)
        again = {it.id for it in mine_ if it.id in listed}
        units = {it.unit for it in mine_ if it.id in again and it.unit}
        for it in mine_:
            if it.id in again or it.unit in units:
                it.id = "%s@%s" % (it.id, pid)
                it.needs = "%s@%s" % (it.needs, pid) if it.needs else ""
                it.unit = "%s@%s" % (it.unit, pid) if it.unit else ""
            listed.add(it.id)
            items.append(it)
    if side == "all":
        items += _glossary(graph, shares, set(principles), terms, 4, "glossary")
        items += _traditions(graph, principles)
    lineage_units = {i.unit for i in items if i.section == "lineage" and i.unit}
    items += [i for i in _sharing(graph, principles, terms, words, shares, side)
              if i.unit not in lineage_units]
    head = header(title or "Brief: neighbourhood of the line (side %s)" % side, digest,
                  principles, at)
    out, choice = _fit(items, limit, lambda c: _render_neighbourhood(head, principles, c))
    return Output(out, _manifest("neighbourhood", side, digest, principles, at, limit, out,
                                 choice))


# -- a helper's prompt ------------------------------------------------------

def principles_of_prompt(graph: Graph, prompt: str, side: str) -> List[str]:
    """The questions a prompt names, by id or tab id, as words; else those
    fixing the terms it uses, the larger share first."""
    found: List[str] = []
    folded = text.fold(prompt or "")
    for q in graph.questions:
        if not visible(q, side):
            continue
        for name in (q.id, q.tab):
            if name and text.occurrences(folded, text.fold(name), True):
                if q.id not in found:
                    found.append(q.id)
                break
    if found:
        return found
    senses, words = vocabulary(graph, side)
    shares = share.shares(graph)
    owners: Set[str] = set()
    for word in terms_in(words, prompt or ""):
        owners |= senses.get(word, set())
    by_id = graph.by_id()
    return sorted((o for o in owners if o in by_id), key=lambda o: (-shares.get(o, 0.0), o))


def for_prompt(graph: Graph, digest: str, prompt: str, side: str = "all",
               at: Optional[str] = None, lines=None, conventions: Sequence[str] = (),
               standing_max: int = STANDING_MAX, neighbourhood_max: int = NEIGHBOURHOOD_MAX,
               ceiling: int = CEILING) -> Tuple[str, dict]:
    """A helper's own brief: the standing brief and the neighbourhood the
    prompt's terms pick, together; the manifests beside each other."""
    first = standing(graph, digest, side, at, lines, conventions, standing_max, ceiling)
    picked = principles_of_prompt(graph, prompt, side)
    return combine(graph, digest, first, picked, side, at, neighbourhood_max, ceiling,
                   more=prompt, title="Brief: neighbourhood of the prompt (side %s)" % side)


def combine(graph, digest, first: Output, picked: List[str], side: str, at,
            neighbourhood_max: int = NEIGHBOURHOOD_MAX, ceiling: int = CEILING,
            more: str = "", title: str = "") -> Tuple[str, dict]:
    parts = [first.text]
    manifest = {"standing": first.manifest}
    if picked:
        second = neighbourhood(graph, digest, picked, side, at, neighbourhood_max, more=more,
                               title=title)
        parts.append(second.text)
        manifest["neighbourhood"] = second.manifest
    whole = "\n".join(parts)
    if len(whole) > ceiling:
        raise Refused(["the brief holds %d characters, over the ceiling of %d"
                       % (len(whole), ceiling)])
    return whole, manifest


# -- staleness --------------------------------------------------------------

def stamp_of(words: str) -> Optional[dict]:
    m = STAMP.search(words or "")
    if not m:
        return None
    line = m.group("line")
    return {"graph": m.group("graph"), "line": [] if line == "-" else line.split(),
            "at": m.group("at"), "tool": m.group("tool")}


def stale(words: str, digest: str, line: Optional[Sequence[str]] = None) -> List[str]:
    """What makes an output stale against a graph and a line; empty where it
    is fresh."""
    found = stamp_of(words)
    if found is None:
        return ["the output carries no stamp"]
    out: List[str] = []
    if found["tool"] != TOOL:
        out.append("made by %s, and this tool is %s" % (found["tool"], TOOL))
    if found["graph"] != digest:
        out.append("made from graph %s, and the graph is now %s"
                   % (found["graph"][:12], digest[:12]))
    if line is not None and list(line) != found["line"]:
        out.append("made for the line %s, and the line in hand is %s"
                   % (" ".join(found["line"]) or "-", " ".join(line) or "-"))
    return out


# -- where it lives ---------------------------------------------------------

def config_home(env) -> str:
    base = env.get("CLAUDE_CONFIG_DIR")
    if not isinstance(base, str) or not base:
        home = env.get("HOME") or os.path.expanduser("~")
        base = os.path.join(home, ".claude")
    return os.path.realpath(base)


def project_root(cwd: Optional[str], env) -> Optional[str]:
    """The project the brief is for: `CLAUDE_PROJECT_DIR` where it holds a
    notebook file, else the nearest of the cwd and its ancestors that does."""
    places: List[str] = []
    named = env.get("CLAUDE_PROJECT_DIR")
    if isinstance(named, str) and named:
        places.append(named)
    if isinstance(cwd, str) and cwd:
        here = os.path.abspath(cwd)
        while True:
            places.append(here)
            up = os.path.dirname(here)
            if up == here:
                break
            here = up
    for place in places:
        if os.path.isfile(os.path.join(place, ".principal", "notebook.json")):
            return os.path.realpath(place)
    return None


def slug(path: str) -> str:
    """The path with every character but a letter or digit made `-`, and a
    fingerprint of the path after it, so that two paths that differ only in
    their punctuation do not share one directory."""
    return "%s-%s" % (re.sub(r"[^A-Za-z0-9]", "-", path)[-120:],
                      hashlib.sha256(path.encode("utf-8")).hexdigest()[:12])


def in_checkout(path: str) -> Optional[str]:
    """The nearest directory at or above ``path`` that holds `.git`, or None."""
    here = os.path.realpath(path)
    while True:
        if os.path.lexists(os.path.join(here, ".git")):
            return here
        up = os.path.dirname(here)
        if up == here:
            return None
        here = up


def brief_dir(root: str, env) -> str:
    """`<config home>/principal/brief/<the project's path, every character but
    a letter or digit made ->`: under the user's Claude configuration, beside
    nothing of any repository. Refused where it would stand in a checkout or
    in the project itself."""
    where = os.path.join(config_home(env), "principal", "brief", slug(root))
    real_root = os.path.realpath(root)
    if where == real_root or where.startswith(real_root.rstrip(os.sep) + os.sep):
        raise Refused(["the brief's directory %s is inside the project" % where])
    checkout = in_checkout(os.path.dirname(where))
    if checkout:
        raise Refused(["the brief's directory %s would stand in the checkout %s"
                       % (where, checkout)])
    return where


#: the files of the brief's directory
FILES = {"graph": "graph.json", "source": "source.json", "standing": "standing.md",
         "neighbourhood": "neighbourhood.md", "inhand": "inhand.path"}
