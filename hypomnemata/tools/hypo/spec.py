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

from . import project, text
from .model import (CANON, Graph, INBOX_KINDS, KINDS, MODES, NODE_STANDINGS,
                    RELATIONS, SECTIONS, STANDINGS, STATES)

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

    A definition's borrowing is the same edge under another name and is checked
    here rather than under a rule of its own.
    """
    known = {q.id for q in graph.questions}
    traditions = set(graph.tradition_ids())
    for q in graph.questions:
        for thesis in q.theses:
            edges = [("tradition edge", t.to) for t in thesis.traditions]
            edges += [("definition %r borrows from" % d.word, d.tradition.to)
                      for d in thesis.definitions if d.tradition]
            for what, to in edges:
                if to not in known:
                    yield q.id, "%s %r, which is no question" % (what, to)
                elif to not in traditions:
                    yield q.id, ("%s %r, which is a question "
                                 "of this graph and not a tradition" % (what, to))


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
       "a tradition is reached only from its own party, and never from the main tree")
def tradition_isolated(graph: Graph) -> Yield:
    """A tradition is another party's notebook, joined to this one by tradition
    edges and by nothing else.

    Within that party's own lineage a term edge is ordinary: the reconstruction
    may raise its own questions and answer them, which is what makes it a
    notebook rather than a stub. What it may not have is a term edge from
    somewhere in the principal's lineage, which would put another party's
    answer under his own question.
    """
    by_id = graph.by_id()
    main = project.reachable_from(graph, project.main_root(graph))
    for src, term in graph.term_edges():
        target = by_id.get(term.to)
        if target is not None and target.party != src.party:
            yield src.id, ("term %r raises a question whose party is %r; a term edge "
                           "runs inside one party's lineage, and a tradition edge is "
                           "the only thing that crosses" % (term.title, target.party))
    for q in graph.questions:
        if q.tradition and q.id in main:
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
    # another, so the reader could not tell which of them was meant. Asked of
    # the renderer rather than spelled again here: a second copy of the rule is
    # a second rule, and this one was already a case behind.
    from .render import chip_key  # here, because render imports this module
    chips = [(chip_key(q.id), q.id) for q in graph.questions]
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
       "mode, state, kind, party, standing and tradition.relation are in their vocabularies")
def vocabulary(graph: Graph) -> Yield:
    if graph.mode not in MODES:
        yield None, "mode %r is not one of %s" % (graph.mode, ", ".join(MODES))
    for q in graph.questions:
        if q.state not in STATES:
            yield q.id, "state %r is not one of %s" % (q.state, ", ".join(STATES))
        if q.kind not in KINDS:
            yield q.id, "kind %r is not one of %s" % (q.kind, ", ".join(KINDS))
        if not q.party.strip():
            yield q.id, "party is empty; every question belongs to one"
        if q.standing and q.standing not in NODE_STANDINGS:
            yield q.id, "standing %r is not one of %s" % (
                q.standing, ", ".join(NODE_STANDINGS))
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
            if thesis.standing and thesis.standing not in NODE_STANDINGS:
                yield q.id, "thesis %r: standing %r is not one of %s" % (
                    _clip(thesis.title, 30), thesis.standing, ", ".join(NODE_STANDINGS))
            # assent is required, so "none" is a real value there; a deadlock is
            # optional, so a word standing in for its absence is pure noise
            for term in thesis.terms:
                if term.deadlock and term.deadlock.counter.strip().lower() in SENTINELS:
                    yield q.id, ("term %r: deadlock reads %r; leave it out instead"
                                 % (term.title, term.deadlock.counter.strip()))
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
    """As a word, and in whichever regular form the sentence wants.

    A glossary entry is a headword, so a thesis that only ever says `grants`
    has anchored `grant` as properly as one that says the base — and the
    renderer puts the link on the form that stands there. What it cannot do is
    anchor letters hidden inside a longer word, which is what asking for a
    substring allowed: `grant` was found in `grants`, the check passed, and
    the renderer had nowhere to put the link.
    """
    for q in graph.questions:
        for thesis, definition in q.definitions():
            body = text.plain(thesis.text)
            if not any(text.occurrences(body, form, True)
                       for form in text.forms(definition.word)):
                yield q.id, ("definition %r does not occur in the thesis text as a "
                             "word, in any regular form, so the renderer cannot "
                             "anchor it" % definition.word)


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


@check("requires-discharged", "a landed question waits on nothing that is not done")
def requires_discharged(graph: Graph) -> Yield:
    """``requires`` names what must be done before a question can be asked, so a
    question that has landed was asked, and everything it waited on was done.

    The root carried its own promulgation, which is the act that follows its
    answer rather than one that precedes it — it blocks every question above
    and never blocked the root. An entry naming no item at all is
    `requires-exist`'s to report, not this one's.
    """
    done = {item.id: item.done for q in graph.questions for item in q.inbox}
    for q in graph.questions:
        if q.state != "landed":
            continue
        pending = sorted(w for w in q.requires if w in done and not done[w])
        if pending:
            yield q.id, ("has landed but still waits on %s, which %s not done"
                         % (", ".join(repr(p) for p in pending),
                            "is" if len(pending) == 1 else "are"))


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


@check("inbox-required",
       "an inbox item that is not done is required by at least one question")
def inbox_required(graph: Graph) -> Yield:
    """An action exists only as something a question requires, and a question is
    scheduled only by what it requires. An item nothing waits on is either debt
    with no bearing on any question, or the same debt written twice — once on an
    application as a postulate, and again here.

    A done item is exempt: a requirer drops the entry when the item is
    discharged, so the discharged item is left with no requirers by design.
    `inbox-placement` asks a different question of the same field and skips this
    case, which is why it is a rule of its own.
    """
    wanted: Set[str] = set()
    for q in graph.questions:
        wanted.update(q.requires)
    for q in graph.questions:
        for item in q.inbox:
            if not item.done and item.id not in wanted:
                yield q.id, ("inbox item %r is not done and no question requires "
                             "it, so nothing waits on it" % item.id)


@check("pressure-shape", "every question's pressure is a non-negative integer")
def pressure_shape(graph: Graph) -> Yield:
    """Pressure is the one scheduling number the principal sets by hand.

    Priority used to be stored and taken on trust, because nothing recorded
    what was blocked behind what. It is now computed — pressure summed along
    the term edges, since a question cannot be put until the questions above
    it have landed — so the only thing left to check is the shape of the
    number the sum runs over.
    """
    for q in graph.questions:
        if isinstance(q.pressure, bool) or not isinstance(q.pressure, int) or q.pressure < 0:
            yield q.id, "pressure %r is not a non-negative integer" % (q.pressure,)


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
    exactly the drift it was meant to catch: `prior` stood defined twice, on
    `alignment` and on `hypomnemata`, with nothing firing — and a reader who
    met the word on a third tab had no way to tell which entry he was reading.
    The defect was the second entry, not the sense: a word may well have one
    sense and two bearers, as `prior` does. A word that must carry two senses
    needs two words; a word with one needs one entry.

    What the entry must be reachable from is the users of the word, and the
    reader reaches it over the graph's ancestors rather than over the
    breadcrumb: a question may be raised by several clauses, so the tab tree
    is one path through a DAG and not the whole of what stands above. A word
    no user can reach that way is either a definition on the wrong question or
    a line missing an edge, and neither is decidable here — which is why this
    check counts entries and the reachability is read rather than run.
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
       "a thesis is canon only where its question landed, and an application is "
       "derived only from a canon thesis")
def standing_honest(graph: Graph) -> Yield:
    """An artifact built ahead of the answer that would justify it is the
    ordinary way work gets done and the ordinary way a graph rots. Calling it
    a postulate is what keeps the debt visible.

    A postulate is anything the notebook supports and canon does not, whether
    it is a thesis or an artifact built from one, so the two are graded by one
    rule in two steps: a thesis is canon only where its question has landed,
    and an artifact is derived only from a thesis that is canon.

    Both are necessary and neither is sufficient. A landed question may hold a
    thesis the principal has not yet promulgated, and a canon thesis may have
    an artifact nobody has diffed against it. That judgement is the writer's
    and is named in the attenuation list; what is checked here is the part
    that is not a judgement at all.
    """
    for q in graph.questions:
        for thesis in q.theses:
            if thesis.standing == "canon" and q.state != "landed":
                yield q.id, ("thesis %r stands as canon, but the question is %r "
                             "and not landed" % (_clip(thesis.title, 30), q.state))
        for thesis, app in q.applications():
            if app.standing != "derived":
                continue
            if thesis.standing != "canon":
                yield q.id, ("application %r stands as derived, but the thesis it "
                             "comes from stands as %r" % (app.name,
                                                          thesis.standing or "unset"))


@check("deadlock-complete",
       "a deadlock carries both a counter-clause and the attenuation it earns")
def deadlock_complete(graph: Graph) -> Yield:
    """Dissent without a grading is half a record. The counter-clause says what
    the principal holds instead; the attenuation says what the clause may still
    license, which is the whole use of recording the dissent rather than simply
    withholding the merge.
    """
    for q in graph.questions:
        for thesis in q.theses:
            for term in thesis.terms:
                if term.deadlock is None:
                    continue
                if not term.deadlock.counter.strip():
                    yield q.id, "term %r: deadlock has no counter-clause" % term.title
                if not term.deadlock.attenuation.strip():
                    yield q.id, ("term %r: deadlock has no attenuation, so what the "
                                 "clause may still license is unrecorded" % term.title)


@check("divergence-counter",
       "a divergence from a tradition says what is held instead")
def divergence_counter(graph: Graph) -> Yield:
    """A tradition edge is the canon between two parties: support is assent and
    divergence is deadlock. A deadlock carries a counter-clause, so a divergence
    does too — it carries no attenuation, because a tradition licenses no action
    here and there is no authority to grade.
    """
    for q in graph.questions:
        for thesis in q.theses:
            for trad in thesis.traditions:
                if trad.relation == "divergence" and not trad.counter.strip():
                    yield q.id, ("divergence from %r says nothing of what is held "
                                 "instead" % trad.to)
                if trad.relation == "support" and trad.counter.strip():
                    yield q.id, ("support for %r carries a counter-clause; a "
                                 "counter-clause is what makes it a divergence" % trad.to)


@check("answer-cardinality", "in canon mode a question has exactly one thesis")
def answer_cardinality(graph: Graph) -> Yield:
    """A notebook holds as many theses as the principal is entertaining, so the
    check does not run there; a canon answers each question once.

    There is no deadlocked twin. A deadlock falls on the clause it is dissent
    from, not on the answer that clause sits in, which is what lets the answer
    be merged whole while the dissent is still recorded.
    """
    if graph.mode != CANON:
        return
    for q in graph.questions:
        if len(q.theses) != 1:
            yield q.id, "%d theses, expected exactly one" % len(q.theses)


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
