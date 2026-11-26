"""public — the copy of the notebook that may be shown, and what may not be in it.

The notebook holds graphs of several parties. Claude's is public: it is
built in turns that hold Claude's own nodes and the question and nothing
else, so nothing private to the user can be in it, and whatever a question
put there is public with it. The user's is private, and of it the copy shows
that a node stands and what it is joined to, never its words, unless the
user has marked the node. Everything is masked until it is explicitly
unmasked. A mark is a note on the tab opening with the word *public*, naming
each section that may be shown with a fingerprint of the section as it read
when the mark was made (``public.py mark`` writes one):

    public: thesis 3fa91c20, glossary 77b0e4d1

A section changed after its mark no longer matches the fingerprint and is
masked again until the user marks it anew.

A node of Claude's is a question holding an answer in Claude's own words.
The copy shows its question and those answers. The rest of its tab, the
hinge included, is the user's until Claude has written its own, and follows
the user's marks: what an asking presupposed is for the one answering to
say, in the turn that answers. A masked node is named by a fingerprint of
its id under a salt the user keeps, so the copy does not give the tab's
name. A party is shown by name where a shown answer cites it and is masked
otherwise, and its lines, which are the user's reading of it, are never
shown.

What the copy is made behind is a check of how words could have got from
the masked part to the shown one, and never of likeness alone. An answer of
Claude's is given in a turn that holds nothing of the user's, so where its
words are like the user's the two agree, and that is no leak: ``similar``
lists such runs for the user to see and fails nothing. The question is the
one channel into Claude's graph and is drafted on the user's side, so a run
of masked words in a question is a leak, and so is a masked tab's address
spelled anywhere in what is shown: ``leaks`` lists those and the copy is
not made while one stands. A section the user marked may be shown whatever
it is like, the marking being sound; where it is like a masked tab
``consider`` lists the run, since the mark may have taken in something
sensitive by accident or the words may merely stand in two contexts, and
the copy waits on the user's having considered it. ``question`` holds a
text bound for a public place to the same rule as ``leaks``; a question
drafted for Claude is held before it is put to ``addresses`` alone, and
whether it hands the answerer the user's record is read by meaning.
"""

from __future__ import annotations

import hashlib
import re
from typing import Dict, Iterable, List, NamedTuple, Set, Tuple

from . import text
from .model import SECTIONS, STATES, Graph, Question

OPENING = "public"
#: how many words in a row, shared by a shown text and a masked one, make a
#: quotation; ``question`` takes a shorter run by default, being new words
RUN = 6
QUESTION_RUN = 5
_WORD = re.compile(r"[^\W_]+(?:['’][^\W_]+)?", re.UNICODE)


class Leak(NamedTuple):
    shown: str
    masked: str
    words: str


def seal(parts: Iterable[str]) -> str:
    """The fingerprint a mark carries of the words it was made over."""
    words = " ".join(" ".join(part.split()) for part in parts if part and part.strip())
    return hashlib.sha256(words.encode("utf-8")).hexdigest()[:8]


def _claims(q: Question) -> Dict[str, str]:
    """Each section a mark on ``q`` names, with the fingerprint it gives; the
    fingerprint is empty where the mark gives none."""
    out: Dict[str, str] = {}
    for note in q.notes:
        body = " ".join(note.body.split())
        if not body.lower().startswith(OPENING):
            continue
        rest = body[len(OPENING):].lstrip(": ")
        for item in re.split(r"[,;]\s*|\s+and\s+", rest):
            words = item.strip(" .").lower().split()
            mark = ""
            if words and re.fullmatch(r"[0-9a-f]{8}", words[-1]):
                mark = words.pop()
            name = " ".join(words)
            if name in SECTIONS:
                out[name] = mark
    return out


def marks(q: Question) -> Set[str]:
    """The sections of ``q``'s tab the user has marked as fit to show, and
    that still read as they did when the mark was made.

    Everything is masked until it is explicitly unmasked, so a mark covers
    the words it was made over and nothing written since: it carries a
    fingerprint of the section, and a section that no longer matches it is
    masked again until the user marks it anew. A mark with no fingerprint
    marks nothing.
    """
    sections = _sections_of(q)
    return {name for name, mark in _claims(q).items()
            if mark and mark == seal(sections[name])}


def lapsed(q: Question) -> List[str]:
    """Sections a mark names whose words have changed since, or whose mark
    gives no fingerprint: masked until marked again."""
    sections = _sections_of(q)
    return sorted(name for name, mark in _claims(q).items()
                  if not mark or mark != seal(sections[name]))


def mark(q: Question, names: Iterable[str]) -> str:
    """The words of a mark over ``names`` as ``q``'s tab reads now."""
    sections = _sections_of(q)
    chosen = [n for n in SECTIONS if n in set(names)]
    return "%s: %s" % (OPENING, ", ".join("%s %s" % (n, seal(sections[n])) for n in chosen))


def own(q: Question) -> List:
    """The answers on ``q`` that are in Claude's own words."""
    return [t for t in q.theses if t.state != STATES[0]]


def _sections_of(q: Question) -> Dict[str, List[str]]:
    """Every word on the tab, by the section it stands in."""
    out: Dict[str, List[str]] = {name: [] for name in SECTIONS}
    out["thesis"].append(q.question)
    for thesis in q.theses:
        out["thesis"] += [thesis.title, thesis.text]
        out["thesis"] += [e.note + " " + e.counter for e in thesis.traditions]
        for term in thesis.terms:
            out["terms"] += [term.title, term.cue, term.suspended] + list(term.anchors)
        for app in thesis.applications:
            out["applications"] += [app.name, app.what, app.note]
    for d in q.definitions:
        out["glossary"] += [d.word, d.body]
    for c in q.cases:
        out["cases"] += [c.name, c.situation, c.verdict, c.reason, c.clause]
    for w in q.works:
        out["works"] += [w.work, w.note]
    if q.hinge is not None:
        out["hinge"] += [q.hinge.question, q.hinge.end, q.hinge.method, q.hinge.thesis,
                         q.hinge.cue]
    return out


def shown(q: Question) -> List[str]:
    """The words of ``q``'s tab the copy shows."""
    out: List[str] = []
    marked = marks(q)
    sections = _sections_of(q)
    if q.claude:
        out.append(q.question)
        for thesis in own(q):
            out += [thesis.title, thesis.text]
    for name in marked:
        out += sections[name]
    if marked:
        out.append(q.question)
    return [w for w in out if w and w.strip()]


def masked(q: Question) -> List[str]:
    """The words of ``q``'s tab the copy does not show."""
    marked = marks(q)
    sections = _sections_of(q)
    out: List[str] = []
    for name in SECTIONS:
        if name in marked:
            continue
        words = list(sections[name])
        if name == "thesis" and q.claude:
            mine = {id(t) for t in own(q)}
            words = []
            for thesis in q.theses:
                if id(thesis) not in mine:
                    words += [thesis.title, thesis.text]
                words += [e.note + " " + e.counter for e in thesis.traditions]
        out += words
    if not q.claude and not marked:
        out.append(q.question)
    if q.hinge is not None and "hinge" not in marked:
        out.append(q.hinge.question)
    out += [n.body for n in q.notes]
    return [w for w in out if w and w.strip()]


def _words(s: str) -> List[str]:
    return [w.lower() for w in _WORD.findall(text.plain(s))]


def _runs(parts: Iterable[str], n: int) -> Dict[Tuple[str, ...], None]:
    out: Dict[Tuple[str, ...], None] = {}
    for part in parts:
        words = _words(part)
        for i in range(len(words) - n + 1):
            out.setdefault(tuple(words[i:i + n]))
    return out


def stub(qid: str, salt: str) -> str:
    """The name a masked node goes by in the copy."""
    return "n-" + hashlib.sha256(("%s:%s" % (salt, qid)).encode("utf-8")).hexdigest()[:12]


def _hidden(graph: Graph, run: int) -> Dict[Tuple[str, ...], List[str]]:
    hidden: Dict[Tuple[str, ...], List[str]] = {}
    for q in graph.questions:
        for key in _runs(masked(q), run):
            hidden.setdefault(key, []).append(q.id)
    return hidden


def _shared(graph: Graph, q: Question, parts: List[str], run: int,
            hidden: Dict[Tuple[str, ...], List[str]]) -> List[Leak]:
    """Runs ``parts`` of ``q`` share with masked nodes other than ``q`` and
    than the nodes ``q`` raises, whose quoting of its clause is the lineage."""
    raised = {term.to for thesis in q.theses for term in thesis.terms}
    out: List[Leak] = []
    seen: Set[str] = set()
    for key in _runs(parts, run):
        for other in hidden.get(key, ()):
            if other == q.id or other in raised or other in seen:
                continue
            seen.add(other)
            out.append(Leak(q.id, other, " ".join(key)))
    return out


def similar(graph: Graph, run: int = RUN) -> List[Leak]:
    """Runs of words an answer of Claude's shares with a masked node.

    No leak: the answer was given in a turn that held nothing of the user's,
    so the likeness is agreement. Listed so that the user, whose act the
    copy is, sees them before it is made.
    """
    hidden = _hidden(graph, run)
    out: List[Leak] = []
    for q in graph.questions:
        if q.claude:
            mine: List[str] = []
            for thesis in own(q):
                mine += [thesis.title, thesis.text]
            out += _shared(graph, q, mine, run, hidden)
    return out


def leaks(graph: Graph, run: int = RUN) -> List[Leak]:
    """What could have carried masked words into what is shown.

    The question put to Claude, which is drafted on the user's side: a run
    of words it shares with a masked node. And a masked tab's address
    spelled in anything shown. An answer of Claude's is not looked at for
    likeness (``similar``), nor is a section the user marked (``consider``).
    """
    hidden = _hidden(graph, run)
    out: List[Leak] = []
    for q in graph.questions:
        found = _shared(graph, q, [q.question], run, hidden) if q.claude else []
        out += found
        seen = {leak.masked for leak in found}
        for other in links(graph, shown(q)):
            if other != q.id and other not in seen:
                out.append(Leak(q.id, other, "a link into its tab"))
    return out


def consider(graph: Graph, run: int = RUN) -> List[Leak]:
    """Runs of words a section the user marked shares with a masked node.

    What the user has marked may be shown whatever it is like, so long as
    the marking is sound. A likeness to a masked tab may mean the mark took
    in something sensitive by accident, or only that the same words stand
    in two contexts, which is fine: it is for the user to consider, and the
    copy is made once the user has.
    """
    hidden = _hidden(graph, run)
    out: List[Leak] = []
    for q in graph.questions:
        marked = marks(q)
        if not marked:
            continue
        sections = _sections_of(q)
        parts: List[str] = [q.question]
        for name in marked:
            parts += sections[name]
        out += _shared(graph, q, parts, run, hidden)
    return out


def links(graph: Graph, words: Iterable[str]) -> List[str]:
    """The masked nodes ``words`` link into: a tab's id spelled in the text,
    as an address of the notebook spells it."""
    out: List[str] = []
    joined = "\n".join(words)
    for q in graph.questions:
        if q.claude or marks(q):
            continue
        if q.tab and q.tab in joined and q.id not in out:
            out.append(q.id)
    return out


def question(graph: Graph, drafted: str, run: int = QUESTION_RUN) -> List[Leak]:
    """What a text quotes of the masked part, a run of ``run`` words, or
    links into. The check on a text bound for a public place calls it
    (``outgoing``); a question drafted for Claude is no longer held to it,
    but to ``addresses`` and to a reading by meaning."""
    hidden: Dict[Tuple[str, ...], str] = {}
    for q in graph.questions:
        for key in _runs(masked(q), run):
            hidden.setdefault(key, q.id)
    out: List[Leak] = []
    seen: Set[str] = set()
    for key in _runs([drafted], run):
        other = hidden.get(key)
        if other is not None and other not in seen:
            seen.add(other)
            out.append(Leak("the question", other, " ".join(key)))
    for other in links(graph, [drafted]):
        if other not in seen:
            out.append(Leak("the question", other, "a link into its tab"))
    return out


def addresses(graph: Graph, drafted: str) -> List[Leak]:
    """The masked tabs a question drafted for Claude spells the address of:
    the mechanical part of what ``public.py question`` holds it to. Whether
    the question hands over what a masked tab says is read by meaning, and
    no run of words is looked for here."""
    return [Leak("the question", other, "a link into its tab")
            for other in links(graph, [drafted])]


def copy(graph: Graph, salt: str) -> Dict[str, object]:
    """The public copy: every node, its words where shown, and the edges."""
    by_id = graph.by_id()
    cited: Set[str] = set()
    for q in graph.questions:
        theses = own(q) if q.claude else (q.theses if "thesis" in marks(q) else [])
        for thesis in theses:
            cited.update(e.to for e in thesis.traditions)

    def visible(q: Question) -> bool:
        if q.tradition:
            return q.id in cited
        return q.claude or bool(marks(q))

    def name(qid: str) -> str:
        q = by_id.get(qid)
        return qid if q is not None and visible(q) else stub(qid, salt)

    nodes: List[Dict[str, object]] = []
    edges: List[Dict[str, str]] = []
    for q in graph.questions:
        whose = "tradition" if q.tradition else ("claude" if q.claude else "user")
        node: Dict[str, object] = {"id": name(q.id), "whose": whose,
                                   "masked": not visible(q)}
        if q.project and visible(q):
            node["project"] = q.project
        if visible(q) and not q.tradition:
            marked = marks(q)
            node["question"] = q.question
            if q.claude:
                node["answers"] = [{"title": t.title, "text": t.text} for t in own(q)]
            if "thesis" in marked:
                node["answers"] = [{"title": t.title, "text": t.text} for t in q.theses]
            if "glossary" in marked:
                node["glossary"] = [{"word": d.word, "body": d.body} for d in q.definitions]
            if "cases" in marked:
                node["cases"] = [{"name": c.name, "case": c.situation, "verdict": c.verdict,
                                  "reason": c.reason} for c in q.cases]
            if "hinge" in marked and q.hinge is not None:
                node["asking"] = q.hinge.question
                node["end"], node["method"] = q.hinge.end, q.hinge.method
        nodes.append(node)
        for thesis in q.theses:
            for term in thesis.terms:
                edges.append({"from": name(q.id), "to": name(term.to), "kind": "raises"})
            for edge in thesis.traditions:
                edges.append({"from": name(q.id), "to": name(edge.to), "kind": edge.relation})
    nodes.sort(key=lambda n: str(n["id"]))
    edges = sorted({(e["from"], e["to"], e["kind"]) for e in edges})
    return {"nodes": nodes,
            "edges": [{"from": a, "to": b, "kind": k} for a, b, k in edges]}


def page(node: Dict[str, object]) -> str:
    """One node of the copy as markdown."""
    lines = ["# %s" % node["id"], "", "%s%s" % (node["whose"],
             ", masked" if node["masked"] else "")]
    if node.get("question"):
        lines += ["", "*%s*" % str(node["question"]).strip()]
    if node.get("asking"):
        lines += ["", "What the asking presupposed: %s" % str(node["asking"]).strip()]
    for answer in node.get("answers", []):  # type: ignore[union-attr]
        lines += ["", "## %s" % answer["title"], "", answer["text"].strip()]
    for entry in node.get("glossary", []):  # type: ignore[union-attr]
        lines += ["", "### %s" % entry["word"], "", entry["body"].strip()]
    for case in node.get("cases", []):  # type: ignore[union-attr]
        lines += ["", "### %s" % case["name"], "", "case: %s" % case["case"],
                  "verdict: %s" % case["verdict"], "reason: %s" % case["reason"]]
    for part in ("end", "method"):
        if node.get(part):
            lines += ["", "%s: %s" % (part, str(node[part]).strip())]
    return "\n".join(lines) + "\n"
