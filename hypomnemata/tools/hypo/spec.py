"""The checks: what the renderer cannot enforce by construction.

Each check is a function registered with a stable id, a one-line description and
a severity. ERROR blocks a render of the questions it names; WARN is reported and
does not block. A check yields ``(question id or None, message)`` pairs; the
runner turns them into Findings.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, Iterator, List, Optional, Set, Tuple

from . import project
from .model import (CANON, Graph, INBOX_KINDS, KINDS, MODES, RELATIONS,
                    SECTIONS, STANDINGS, STATES)

ERROR = "ERROR"
WARN = "WARN"

#: The three sources a hinge's thesis part must name, as they are written.
PROVENANCE = ("model:", "harness:", "canon:")

#: A title that is a machine's handle rather than a reader's: `term-001`.
HANDLE = re.compile(r"[A-Za-z]\w*[-_]\d+")

#: Words that stand in for an absent optional field instead of leaving it out.
SENTINELS = ("none", "n/a", "na", "-", "\u2014", "nil", "null")

Yield = Iterator[Tuple[Optional[str], str]]


@dataclass
class Check:
    id: str
    description: str
    severity: str
    fn: Callable[[Graph], Yield]


@dataclass
class Finding:
    check: str
    severity: str
    question: Optional[str]
    message: str

    def line(self) -> str:
        return "%-5s %-21s %-14s %s" % (
            self.severity, self.check, self.question or "-", self.message)

    def as_dict(self) -> dict:
        return {"check": self.check, "severity": self.severity,
                "question": self.question, "message": self.message}


CHECKS: List[Check] = []


def check(cid: str, description: str, severity: str = ERROR):
    def register(fn: Callable[[Graph], Yield]) -> Callable[[Graph], Yield]:
        CHECKS.append(Check(cid, description, severity, fn))
        return fn
    return register


# -- text helpers -----------------------------------------------------------

def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()


def _words(text: str) -> List[str]:
    return re.findall(r"[0-9a-z']+", (text or "").lower())


def _shared_run(anchor: str, target: str, n: int = 8) -> Optional[str]:
    """The first run of ``n`` or more consecutive anchor words found in target."""
    a, t = _words(anchor), _words(target)
    if len(a) < n or len(t) < n:
        return None
    windows = {" ".join(t[i:i + n]) for i in range(len(t) - n + 1)}
    for i in range(len(a) - n + 1):
        run = " ".join(a[i:i + n])
        if run in windows:
            return run
    return None


def _clip(text: str, width: int = 60) -> str:
    one = re.sub(r"\s+", " ", (text or "").strip())
    return one if len(one) <= width else one[:width - 1] + "…"


# -- structural checks ------------------------------------------------------

@check("anchor-substring",
       "every anchor of every term is an exact substring of its thesis text")
def anchor_substring(graph: Graph) -> Yield:
    for q in graph.questions:
        for thesis in q.theses:
            for term in list(thesis.terms) + list(thesis.mentions):
                for anchor in term.anchors:
                    if anchor not in thesis.text:
                        yield q.id, ("term %r: anchor is not a verbatim substring "
                                     "of the thesis text: %r"
                                     % (term.title, _clip(anchor)))
                    elif re.search(r"\n[ \t]*\n", anchor):
                        # the renderer places a chip within one block; an anchor
                        # crossing a blank line has no one place to put it
                        yield q.id, ("term %r: anchor runs across a blank line, so "
                                     "it spans two blocks: %r"
                                     % (term.title, _clip(anchor)))


@check("anchor-unique", "an anchor occurs once in the thesis text it is taken from")
def anchor_unique(graph: Graph) -> Yield:
    """Two occurrences give the renderer two places to put one chip, and give
    the links sidecar two spans to mean by one string. Where a clause really
    is said twice, the term takes the longer passage that says it once.
    """
    for q in graph.questions:
        for thesis in q.theses:
            for term in list(thesis.terms) + list(thesis.mentions):
                for anchor in term.anchors:
                    found = thesis.text.count(anchor) if anchor else 0
                    if found > 1:
                        yield q.id, ("term %r: its anchor occurs %d times in the "
                                     "thesis text, so which occurrence carries "
                                     "the chip is undecided" % (term.title, found))


@check("term-target", "every term and every mention names an existing question")
def term_target(graph: Graph) -> Yield:
    known = {q.id for q in graph.questions}
    for q in graph.questions:
        for term in q.terms():
            if term.to not in known:
                yield q.id, "term %r leads to %r, which is no question" % (
                    term.title, term.to)
        for mention in q.mentions():
            if mention.to not in known:
                yield q.id, "mention %r points at %r, which is no question" % (
                    mention.title, mention.to)


@check("tradition-target", "every tradition edge names a question that is a tradition")
def tradition_target(graph: Graph) -> Yield:
    """Nothing validated these at all, so a citation could name a tradition
    that was never written and the renderer would drop the chip in silence —
    which is how the live notebook came to cite a Foucault it does not hold.
    """
    known = {q.id for q in graph.questions}
    traditions = set(graph.tradition_ids())
    for q in graph.questions:
        for thesis in q.theses:
            for trad in thesis.traditions:
                if trad.to not in known:
                    yield q.id, "tradition edge leads to %r, which is no question" % trad.to
                elif trad.to not in traditions:
                    yield q.id, ("tradition edge leads to %r, which is a question "
                                 "of this graph and not a tradition" % trad.to)


@check("term-total", "every term has at least one anchor and a target")
def term_total(graph: Graph) -> Yield:
    for q in graph.questions:
        for term in q.terms():
            if not [a for a in term.anchors if a.strip()]:
                yield q.id, "term %r carries no anchor" % term.title
            if not term.to.strip():
                yield q.id, "term %r names no target" % term.title


@check("one-root",
       "exactly one question has no incoming term edge, and it is not a tradition")
def one_root(graph: Graph) -> Yield:
    ins = project.in_edges(graph)
    roots = sorted(q.id for q in graph.questions if not q.tradition and not ins.get(q.id))
    if len(roots) == 1:
        return
    if not roots:
        yield None, "no question is a root: every non-tradition question has an incoming term edge"
    else:
        yield None, "%d roots, expected one: %s" % (len(roots), ", ".join(roots))


@check("tradition-isolated",
       "a tradition question has no incoming term edges and is not in the main tree")
def tradition_isolated(graph: Graph) -> Yield:
    ins = project.in_edges(graph)
    main = project.reachable_from(graph, project.main_root(graph))
    for q in graph.questions:
        if not q.tradition:
            continue
        sources = ins.get(q.id, [])
        if sources:
            yield q.id, "tradition question has incoming term edges from: %s" % (
                ", ".join(sorted(sources)))
        if q.id in main:
            yield q.id, "tradition question is reachable from the root, so it is in the main tree"


@check("acyclic", "the term graph is acyclic")
def acyclic(graph: Graph) -> Yield:
    out = project.out_edges(graph)
    colour: Dict[str, int] = {}
    reported: Set[Tuple[str, ...]] = set()

    def walk(node: str, stack: List[str]) -> Iterator[List[str]]:
        colour[node] = 1
        stack.append(node)
        for nxt in out.get(node, []):
            if nxt not in colour:
                for cyc in walk(nxt, stack):
                    yield cyc
            elif colour.get(nxt) == 1:
                cycle = stack[stack.index(nxt):] + [nxt]
                yield cycle
        stack.pop()
        colour[node] = 2

    for q in sorted(graph.questions, key=lambda x: x.id):
        if q.id not in colour:
            for cycle in walk(q.id, []):
                key = tuple(sorted(set(cycle)))
                if key in reported:
                    continue
                reported.add(key)
                yield cycle[0], "term edges form a cycle: %s" % " -> ".join(cycle)


@check("unique-ids",
       "question ids, tab ids, body ids and inbox item ids are each unique")
def unique_ids(graph: Graph) -> Yield:
    inbox = [(item.id, q.id) for q in graph.questions for item in q.inbox]
    # the chip key drops every character an id may carry and a key may not, so
    # two ids can collide on one key — and a chip is how a rendered tab names
    # another, so the reader could not tell which of them was meant
    chips = [("m_" + re.sub(r"[^0-9A-Za-z]", "_", q.id), q.id)
             for q in graph.questions]
    for label, values in (("question id", [(q.id, q.id) for q in graph.questions]),
                          ("chip key", chips),
                          ("tab id", [(q.tab, q.id) for q in graph.questions]),
                          ("body id", [(q.body, q.id) for q in graph.questions]),
                          ("inbox item id", inbox)):
        seen: Dict[str, List[str]] = {}
        for value, owner in values:
            seen.setdefault(value, []).append(owner)
        for value, owners in sorted(seen.items()):
            if len(owners) > 1:
                yield owners[0], "%s %r is used by %d questions: %s" % (
                    label, value, len(owners), ", ".join(owners))


@check("no-restatement",
       "the question text restates no anchor of a term edge that leads to it")
def no_restatement(graph: Graph) -> Yield:
    for q in graph.questions:
        target = _norm(q.question)
        for src, term in graph.incoming(q.id):
            for anchor in term.anchors:
                normalised = _norm(anchor)
                if normalised and normalised in target:
                    yield q.id, ("the question restates the anchor of term %r on %s"
                                 % (term.title, src.id))
                    continue
                run = _shared_run(anchor, q.question)
                if run:
                    yield q.id, ("the question repeats 8+ words of the anchor of term "
                                 "%r on %s: %r" % (term.title, src.id, run))


@check("vocabulary",
       "mode, state, kind, application.standing and tradition.relation are in their vocabularies")
def vocabulary(graph: Graph) -> Yield:
    if graph.mode not in MODES:
        yield None, "mode %r is not one of %s" % (graph.mode, ", ".join(MODES))
    for q in graph.questions:
        if q.state not in STATES:
            yield q.id, "state %r is not one of %s" % (q.state, ", ".join(STATES))
        if q.kind not in KINDS:
            yield q.id, "kind %r is not one of %s" % (q.kind, ", ".join(KINDS))
        for note in q.notes:
            if note.section.strip().lower() not in SECTIONS:
                yield q.id, ("a note names the section %r, which is none of %s; "
                             "it would be written to a heading that never "
                             "renders" % (note.section, ", ".join(SECTIONS)))
        for _, app in q.applications():
            if app.standing not in STANDINGS:
                yield q.id, "application %r: standing %r is not one of %s" % (
                    app.name, app.standing, ", ".join(STANDINGS))
        for thesis in q.theses:
            # assent is required, so "none" is a real value there; a deadlock is
            # optional, so a word standing in for its absence is pure noise
            for where, value in ([("thesis %r" % _clip(thesis.title, 30), thesis.deadlock)]
                                 + [("term %r" % t.title, t.deadlock)
                                    for t in thesis.terms]):
                if value is not None and value.strip().lower() in SENTINELS:
                    yield q.id, ("%s: deadlock reads %r; leave it out instead"
                                 % (where, value.strip()))
            for trad in thesis.traditions:
                if trad.relation not in RELATIONS:
                    yield q.id, "tradition %r: relation %r is not one of %s" % (
                        trad.to, trad.relation, ", ".join(RELATIONS))


@check("title-not-identifier",
       "a title names its content rather than standing in as a handle", WARN)
def title_not_identifier(graph: Graph) -> Yield:
    """What survives of the retired no-ids-in-prose, narrowed to the thing it
    was really after. A title summarises; it need not be a sentence, and it may
    well be what a link points at. What it may not be is opaque — `term-001`
    tells a reader nothing — or a bare question id, which names a tab and not
    this thing.
    """
    ids = {q.id for q in graph.questions}
    for q in graph.questions:
        titled = [("thesis", t.title) for t in q.theses]
        titled += [("term", t.title) for t in q.terms()]
        titled += [("mention", m.title) for m in q.mentions()]
        titled += [("inbox item", i.title) for i in q.inbox]
        titled += [("application", a.name) for _, a in q.applications()]
        for what, title in titled:
            bare = (title or "").strip()
            if bare in ids:
                yield q.id, ("%s title %r is a question id, which names a tab "
                             "and not this" % (what, bare))
            elif HANDLE.fullmatch(bare):
                yield q.id, "%s title %r is a handle and not a name" % (what, bare)


@check("assent-present", "every thesis has a non-empty assent")
def assent_present(graph: Graph) -> Yield:
    for q in graph.questions:
        for thesis in q.theses:
            if not thesis.assent.strip():
                yield q.id, "thesis %r records no assent" % _clip(thesis.title)


@check("definition-anchorable", "a definition's word occurs in its thesis text")
def definition_anchorable(graph: Graph) -> Yield:
    for q in graph.questions:
        for thesis, definition in q.definitions():
            if definition.word.lower() not in thesis.text.lower():
                yield q.id, ("definition %r does not occur in the thesis text, so the "
                             "renderer cannot anchor it" % definition.word)


@check("requires-exist",
       "every requires entry names an inbox item on that question or an ancestor")
def requires_exist(graph: Graph) -> Yield:
    by_id = graph.by_id()
    for q in graph.questions:
        if not q.requires:
            continue
        scope = {q.id} | project.ancestors(graph, q.id)
        known = {item.id for qid in scope if qid in by_id for item in by_id[qid].inbox}
        for want in q.requires:
            if want not in known:
                yield q.id, ("requires %r, which no inbox item on it or on an "
                             "ancestor defines" % want)


@check("inbox-placement",
       "an inbox item sits on the most descendant common ancestor of its requirers",
       WARN)
def inbox_placement(graph: Graph) -> Yield:
    dist = project.distances(graph)
    requirers: Dict[str, List[str]] = {}
    for q in graph.questions:
        for want in q.requires:
            requirers.setdefault(want, []).append(q.id)
    for q in graph.questions:
        for item in q.inbox:
            asked = sorted(set(requirers.get(item.id, [])))
            if not asked:
                continue
            common: Optional[Set[str]] = None
            for qid in asked:
                scope = {qid} | project.ancestors(graph, qid)
                common = scope if common is None else (common & scope)
            common = common or set()
            if not common:
                yield q.id, ("inbox item %r is required by %s, which share no ancestor"
                             % (item.id, ", ".join(asked)))
                continue
            def depth(i: str) -> float:
                d = dist.get(i, project.INF)
                return -d if d != project.INF else 1.0  # unreachable sorts last

            home = sorted(common, key=lambda i: (depth(i), i))[0]
            if home != q.id:
                yield q.id, ("inbox item %r belongs on %s, the most descendant "
                             "question that is an ancestor of every question "
                             "requiring it (%s)" % (item.id, home, ", ".join(asked)))


@check("priority-recompute",
       "priority agrees with its recomputation, or is at least a non-negative integer",
       WARN)
def priority_recompute(graph: Graph) -> Yield:
    """priority(q) = own pressure + the priority of every question blocked behind q.

    The graph file carries no question-to-question requires graph (``requires``
    names inbox items, and no own-pressure term is recorded), so there is nothing
    to recompute from: the stored priority is authoritative and only its shape is
    checked, as the specification directs for that case.
    """
    for q in graph.questions:
        if isinstance(q.priority, bool) or not isinstance(q.priority, int) or q.priority < 0:
            yield q.id, "priority %r is not a non-negative integer" % (q.priority,)


@check("hinge-present",
       "every question carries a hinge with both its parts filled")
def hinge_present(graph: Graph) -> Yield:
    """A tradition was once exempt, on the reading that it is read rather than
    asked and so presupposes nothing here. But a reading has presuppositions of
    its own — that the text answers this question at all, and that what it says
    can be told from what the reader wants it to say — and the reconstruction
    was produced by some run, which is what the thesis part records. A
    tradition differs from the rest of the graph in its lineage and in nothing
    else.
    """
    for q in graph.questions:
        if q.hinge is None:
            yield q.id, ("no hinge: neither what the asking presupposes nor what "
                         "the answer was drawn from is recorded")
            continue
        missing = [name for name, part in (("question", q.hinge.question),
                                           ("thesis", q.hinge.thesis))
                   if not part.strip()]
        if missing:
            yield q.id, "the hinge records no %s part" % " and no ".join(missing)


@check("provenance-complete",
       "a hinge's thesis part names a model, a harness and a canon reference",
       WARN)
def provenance_complete(graph: Graph) -> Yield:
    for q in graph.questions:
        if q.hinge is None or not q.hinge.thesis.strip():
            continue  # `hinge-present` reports the absence itself
        lowered = q.hinge.thesis.lower()
        missing = [mark[:-1] for mark in PROVENANCE if mark not in lowered]
        if missing:
            yield q.id, "the hinge thesis names no %s" % ", no ".join(missing)


@check("inbox-kind", "every inbox item's kind is in its vocabulary")
def inbox_kind(graph: Graph) -> Yield:
    for q in graph.questions:
        for item in q.inbox:
            if item.kind not in INBOX_KINDS:
                yield q.id, "inbox item %r: kind %r is not one of %s" % (
                    item.title, item.kind, ", ".join(INBOX_KINDS))


@check("definition-once", "a word is defined once in the whole graph")
def definition_once(graph: Graph) -> Yield:
    """One sense per word, everywhere — the glossary's own presupposition.

    The rule was once scoped to the tab tree, on the reading that a word
    defined on two questions neither of which is under the other is two words
    and the reader is told which by the tab he is on. That reading licenses
    exactly the drift it was meant to catch: `prior` came to mean what a model
    produces unprompted on one tab and a thesis the human holds on another,
    with nothing firing. A word that must carry two senses needs two words.
    """
    where: Dict[str, List[str]] = {}
    spelling: Dict[str, str] = {}
    for q in graph.questions:
        for _, definition in q.definitions():
            key = definition.word.strip().lower()
            if not key:
                continue
            spelling.setdefault(key, definition.word)
            if q.id not in where.setdefault(key, []):
                where[key].append(q.id)
    for key, owners in where.items():
        if len(owners) > 1:
            yield owners[0], "%r is defined here and again on %s" % (
                spelling[key], ", ".join(owners[1:]))


@check("standing-honest",
       "an application is derived only where the question it comes from has landed")
def standing_honest(graph: Graph) -> Yield:
    """An artifact built ahead of the answer that would justify it is the
    ordinary way work gets done and the ordinary way a graph rots. Calling it
    a postulate is what keeps the debt visible, and whether it may be called
    derived instead is not a matter of judgement: the source question has
    landed or it has not.
    """
    for q in graph.questions:
        if q.state == "landed":
            continue
        for _, app in q.applications():
            if app.standing == "derived":
                yield q.id, ("application %r stands as derived, but the question "
                             "it comes from is %r and not landed" % (app.name, q.state))


@check("answer-cardinality",
       "in canon mode a question has one thesis without a deadlock and at most one with")
def answer_cardinality(graph: Graph) -> Yield:
    """A notebook holds as many theses as the principal is entertaining, so the
    check does not run there; a canon answers each question once."""
    if graph.mode != CANON:
        return
    for q in graph.questions:
        settled = [t for t in q.theses if not (t.deadlock or "").strip()]
        open_ = [t for t in q.theses if (t.deadlock or "").strip()]
        if len(settled) != 1:
            yield q.id, "%d theses without a deadlock, expected exactly one" % len(settled)
        if len(open_) > 1:
            yield q.id, "%d theses with a deadlock, expected at most one" % len(open_)


# -- the runner -------------------------------------------------------------

def run(graph: Graph, only: Optional[Iterable[str]] = None) -> List[Finding]:
    """Every finding, in check order."""
    wanted = set(only) if only else None
    findings: List[Finding] = []
    for spec in CHECKS:
        if wanted and spec.id not in wanted:
            continue
        for qid, message in spec.fn(graph):
            findings.append(Finding(spec.id, spec.severity, qid, message))
    return findings


def errors(findings: Iterable[Finding]) -> List[Finding]:
    return [f for f in findings if f.severity == ERROR]


def affecting(findings: Iterable[Finding], qid: str) -> List[Finding]:
    """The findings that bear on one question: its own, and the graph-wide ones."""
    return [f for f in findings if f.question in (qid, None)]


def catalogue() -> List[Tuple[str, str, str]]:
    return [(c.id, c.severity, c.description) for c in CHECKS]
