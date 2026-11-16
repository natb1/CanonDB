"""public — the copy of the notebook that may be shown, and what may not be in it.

The notebook holds graphs of several parties. Claude's is public: it is
built in turns that hold Claude's own nodes and the question and nothing
else, so nothing private to the user can be in it, and whatever a question
put there is public with it. The user's is private, and of it the copy shows
that a node stands and what it is joined to, never its words, unless the
user has marked the node. A mark is a note on the tab opening with the word
*public*, naming the sections that may be shown or ``all``:

    public: thesis, glossary

A node of Claude's is a question holding an answer in Claude's own words.
The copy shows its question, those answers and what the asking presupposed;
the rest of its tab is the user's and follows the user's marks. A masked
node is named by a fingerprint of its id under a salt the user keeps, so
the copy does not give the tab's name. A party is shown by name where a
shown answer cites it and is masked otherwise, and its lines, which are the
user's reading of it, are never shown.

``leaks`` is the check the copy is made behind: a run of words that stands
both in what is shown and in what is masked is a quotation of the masked
part, and fails. ``question`` holds a question drafted for Claude to the
same rule before it is put.
"""

from __future__ import annotations

import hashlib
import re
from typing import Dict, Iterable, List, NamedTuple, Set, Tuple

from . import text
from .model import SECTIONS, STATES, Graph, Question

OPENING = "public"
ALL = "all"
#: how many words in a row, shared by a shown text and a masked one, make a
#: quotation; a drafted question is held to a shorter run, being new words
RUN = 6
QUESTION_RUN = 5
_WORD = re.compile(r"[^\W_]+(?:['’][^\W_]+)?", re.UNICODE)


class Leak(NamedTuple):
    shown: str
    masked: str
    words: str


def marks(q: Question) -> Set[str]:
    """The sections of ``q``'s tab the user has marked as fit to show."""
    out: Set[str] = set()
    for note in q.notes:
        body = " ".join(note.body.split())
        if not body.lower().startswith(OPENING):
            continue
        rest = body[len(OPENING):].lstrip(": ").lower()
        for name in re.split(r"[,;]\s*|\s+and\s+", rest):
            name = name.strip(" .")
            if name == ALL:
                out.update(SECTIONS)
            elif name in SECTIONS:
                out.add(name)
    return out


def own(q: Question) -> List:
    """The answers on ``q`` that are in Claude's own words."""
    return [t for t in q.theses if t.state != STATES[0]]


def _sections(q: Question) -> Dict[str, List[str]]:
    """Every word on the tab, by the section it stands in."""
    out: Dict[str, List[str]] = {name: [] for name in SECTIONS}
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
        out["hinge"] += [q.hinge.end, q.hinge.method, q.hinge.thesis, q.hinge.cue]
    return out


def shown(q: Question) -> List[str]:
    """The words of ``q``'s tab the copy shows."""
    out: List[str] = []
    marked = marks(q)
    sections = _sections(q)
    if q.claude:
        out.append(q.question)
        for thesis in own(q):
            out += [thesis.title, thesis.text]
        if q.hinge is not None:
            out.append(q.hinge.question)
    for name in marked:
        out += sections[name]
    if marked:
        out.append(q.question)
    return [w for w in out if w and w.strip()]


def masked(q: Question) -> List[str]:
    """The words of ``q``'s tab the copy does not show."""
    marked = marks(q)
    sections = _sections(q)
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
    if not q.claude:
        if not marked:
            out.append(q.question)
        if q.hinge is not None:
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


def leaks(graph: Graph, run: int = RUN) -> List[Leak]:
    """Runs of words that stand both in what is shown and in what is masked.

    A masked node's raising clause stands, word for word, in its parent's
    answer, which is the lineage; where the parent is shown and the child is
    not, the clause is the parent's own and no quotation of the child, so
    a run shared with a node the shown one raises is not counted; nor is a
    run shared between the shown and the masked parts of one tab.
    """
    hidden: Dict[Tuple[str, ...], List[str]] = {}
    for q in graph.questions:
        for key in _runs(masked(q), run):
            hidden.setdefault(key, []).append(q.id)
    out: List[Leak] = []
    for q in graph.questions:
        raised = {term.to for thesis in q.theses for term in thesis.terms}
        seen: Set[str] = set()
        for key in _runs(shown(q), run):
            for other in hidden.get(key, ()):
                if other == q.id or other in raised or other in seen:
                    continue
                seen.add(other)
                out.append(Leak(q.id, other, " ".join(key)))
    return out


def question(graph: Graph, drafted: str, run: int = QUESTION_RUN) -> List[Leak]:
    """What a question drafted for Claude quotes of the masked part."""
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
    return out


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
                if q.hinge is not None and q.hinge.question.strip():
                    node["asking"] = q.hinge.question
            if "thesis" in marked:
                node["answers"] = [{"title": t.title, "text": t.text} for t in q.theses]
            if "glossary" in marked:
                node["glossary"] = [{"word": d.word, "body": d.body} for d in q.definitions]
            if "cases" in marked:
                node["cases"] = [{"name": c.name, "case": c.situation, "verdict": c.verdict,
                                  "reason": c.reason} for c in q.cases]
            if "hinge" in marked and q.hinge is not None:
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
