"""The checks: what the renderer cannot enforce by construction.

Each check is a function registered with a stable id, a one-line description and
a severity. ERROR blocks a render of the questions it names; WARN is reported and
does not block. A check yields ``(question id or None, message)`` pairs; the
runner turns them into Findings.

A graph may be **partial**: the tabs a dictation touches and their ancestors,
read for a check over those alone (``Graph.scope``). Every rule runs over it.
What a rule does not report there is only what could be owed to a tab outside
it — a term leading to a question below, whose tab was not read. Nothing
that reads up the lineage is spared, because the ancestors are in the graph or the graph is refused:
``scope-closed`` says where one is missing. What a partial check cannot do is
see a fault that stands wholly outside it, or between a tab in it and one out
of it — a word defined twice, an id used twice — and a change that could
make one is the whole notebook's to check.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, Iterator, List, Optional, Set, Tuple

from . import project, text
from .model import (ANSWERERS, CANON, CITATION_HEADINGS, GLYPHS, Graph, KINDS, MODES, RELATIONS,
                    SECTIONS, STANDINGS, STATES)

ERROR = "ERROR"
WARN = "WARN"

#: The three sources a hinge's thesis part must name, as they are written.
PROVENANCE = ("model:", "harness:", "canon:")

#: A headline that is a machine's handle rather than a reader's: `term-001`.
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


def _overlapping(haystack: str, needle: str) -> int:
    """Occurrences counted the way the renderer places chips: every start,
    overlapping ones included. ``that that`` stands twice in ``that that
    that`` and gets two chips, so it has to count as two here."""
    found, at = 0, haystack.find(needle)
    while at != -1:
        found += 1
        at = haystack.find(needle, at + 1)
    return found


@check("anchor-unique",
       "an anchor occurs once across the answers on the tab it is taken from")
def anchor_unique(graph: Graph) -> Yield:
    """Two occurrences give the renderer two places to put one chip, and give
    the links sidecar two spans to mean by one string. Where a clause really
    is said twice, the term takes the longer passage that says it once.

    The scope is the tab's Thesis section and not the one answer, because
    that is the scope a link is resolved in: the sidecar hands out runs of an
    anchor in page order across the whole section, and the reader files a
    term under the first answer whose text holds its anchors. An anchor that
    stands once in its own answer and once in the answer above it would be
    linked, and read back, on the wrong answer — with nothing said, since
    each answer on its own is fine. A citation's note under an answer stands
    in the same section, so it is counted too.

    Counted plain, as the sidecar resolves an anchor: the page holds the
    characters and keeps the emphasis beside them, so a clause said once in
    bold and once plain is said twice where the link is placed, and the
    link would take the first.
    """
    for q in graph.questions:
        section = "\n\n".join(
            [text.plain(thesis.text) for thesis in q.theses]
            + [text.plain(part) for thesis in q.theses for trad in thesis.traditions
               for part in (trad.note, trad.counter) if part])
        for thesis in q.theses:
            own_text = text.plain(thesis.text)
            for term in list(thesis.terms) + list(thesis.mentions):
                for anchor in term.anchors:
                    plain = text.plain(anchor)
                    own = _overlapping(own_text, plain) if plain else 0
                    found = _overlapping(section, plain) if plain else 0
                    if own > 1:
                        yield q.id, ("term %r: its anchor occurs %d times in the "
                                     "thesis text, so which occurrence carries "
                                     "the chip is undecided" % (term.title, own))
                    elif own and found > 1:
                        yield q.id, ("term %r: its anchor occurs %d times across "
                                     "the answers on this tab, so the link and the "
                                     "reader would take it on another answer"
                                     % (term.title, found))


@check("term-target",
       "every term, mention and shadowing definition names an existing question")
def term_target(graph: Graph) -> Yield:
    """A shadow points a definition at the question its word has earned, so it
    is an edge like the others. It may not point at its own tab: there the
    thesis already fixes the sense, and a definition saying it again is the
    same datum in a second home."""
    known = {q.id for q in graph.questions}
    # a partial graph holds what stands above its questions and not what
    # stands below: a target it does not hold is a tab that was not read
    elsewhere = graph.partial
    for q in graph.questions:
        for term in q.terms():
            if term.to not in known and not elsewhere:
                yield q.id, "term %r leads to %r, which is no question" % (
                    term.title, term.to)
        for mention in q.mentions():
            if mention.to not in known and not elsewhere:
                yield q.id, "mention %r points at %r, which is no question" % (
                    mention.title, mention.to)
        for definition in q.definitions:
            if not definition.question:
                continue
            if definition.question not in known:
                if elsewhere:
                    continue
                yield q.id, "definition %r shadows %r, which is no question" % (
                    definition.word, definition.question)
            elif definition.question == q.id:
                yield q.id, ("definition %r shadows its own question, whose "
                             "thesis already fixes the sense" % definition.word)


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
        edges = [("tradition edge", t.to)
                 for thesis in q.theses for t in thesis.traditions]
        edges += [("definition %r borrows from" % d.word, d.tradition.to)
                  for d in q.definitions if d.tradition]
        for what, to in edges:
            if to not in known:
                if not graph.partial:  # a party's tab this read did not take
                    yield q.id, "%s %r, which is no question" % (what, to)
            elif to not in traditions:
                yield q.id, ("%s %r, which is a question "
                             "of this graph and not a tradition" % (what, to))


@check("term-total", "every term and mention has at least one anchor and a target")
def term_total(graph: Graph) -> Yield:
    # a mention too: no edge, but placed by its anchor as a term is, and one
    # with none has no place on the page and no answer to be read back under
    for q in graph.questions:
        for what, term in ([("term", t) for t in q.terms()]
                           + [("mention", m) for m in q.mentions()]):
            if not [a for a in term.anchors if a.strip()]:
                yield q.id, "%s %r carries no anchor" % (what, term.title)
            if not term.to.strip():
                yield q.id, "%s %r names no target" % (what, term.title)


@check("one-root",
       "exactly one question has no incoming term edge, and it is not a tradition")
def one_root(graph: Graph) -> Yield:
    """The kind says what a question with no raiser may be, and
    ``scope-closed`` leans on it over a partial graph, so a root's kind and
    its place have to agree: a question of kind root has no raiser, and on a
    whole graph a question with no raiser is of kind root.

    A partial graph may stand wholly below the root — a party's tab alone,
    which has no ancestors — so there the root's absence says nothing;
    ``scope-closed`` vouches for the kind of every question read.
    """
    ins = project.in_edges(graph)
    for q in graph.questions:
        if q.kind == "root" and ins.get(q.id) and not q.tradition:
            # a tradition's head with a raiser is ``tradition-isolated``'s
            yield q.id, ("its kind is root, and a term edge leads to it from %s"
                         % ", ".join(sorted(ins[q.id])))
        elif q.kind != "root" and not ins.get(q.id) and not graph.partial:
            yield q.id, "nothing raises it, and its kind is %r rather than root" % q.kind
    roots = sorted(q.id for q in graph.questions if not q.tradition and not ins.get(q.id))
    if len(roots) == 1:
        return
    if not roots:
        if graph.partial:
            return
        yield None, "no question is a root: every non-tradition question has an incoming term edge"
    else:
        yield None, "%d roots, expected one: %s" % (len(roots), ", ".join(roots))


@check("scope-closed",
       "a partial graph holds every question it was read for, and their ancestors")
def scope_closed(graph: Graph) -> Yield:
    """A partial graph is checked as if what stands above its questions were
    all there, so it has to be. A question with no term edge leading to it is
    a root, or a tradition's head, or a question whose raiser's tab was not
    read — and the kind says which of those it can be: only a root is asked
    as one. Nothing below a question is needed; everything above it is.

    The reader holds the same rule from the other side, where it can: a tab
    whose header list names a raiser whose tab was not read is refused before
    the graph is written. This is the half a graph file can decide alone. A
    question with two raisers, one read and one not, has an edge leading to
    it here and looks whole; only the header list shows the other, which is
    why a partial graph is built by ``read.py --scope`` and not by hand.
    """
    if not graph.partial:
        return
    known = {q.id for q in graph.questions}
    for qid in graph.scope:
        if qid not in known:
            yield qid, "the graph was read for %s, and holds no such question" % qid
    ins = project.in_edges(graph)
    for q in graph.questions:
        # a tradition's head is another party's root: nothing of the author's
        # raises it, and its tab was read for the citations that reach it
        if not ins.get(q.id) and q.kind != "root" and not q.tradition:
            yield q.id, ("nothing in the graph raises it, and it is not a root: "
                         "the tab of whatever raises it was not read, so every "
                         "rule over its lineage would read over a gap")


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
    """Depth first, with the path held here rather than on the call stack: a
    chain of a thousand questions, each raising the next, is a graph and not
    a recursion limit. Each cycle is reported once, from the first question
    on it the walk reached."""
    out = project.out_edges(graph)
    colour: Dict[str, int] = {}  # 1 on the path, 2 done
    reported: Set[Tuple[str, ...]] = set()
    for q in sorted(graph.questions, key=lambda x: x.id):
        if q.id in colour:
            continue
        colour[q.id] = 1
        path = [q.id]
        pending = [iter(out.get(q.id, []))]
        while pending:
            nxt = next(pending[-1], None)
            if nxt is None:
                colour[path.pop()] = 2
                pending.pop()
            elif nxt not in colour:
                colour[nxt] = 1
                path.append(nxt)
                pending.append(iter(out.get(nxt, [])))
            elif colour[nxt] == 1:
                cycle = path[path.index(nxt):] + [nxt]
                key = tuple(sorted(set(cycle)))
                if key not in reported:
                    reported.add(key)
                    yield cycle[0], "term edges form a cycle: %s" % " -> ".join(cycle)


@check("unique-ids",
       "question ids, tab ids and body ids are each unique, and a headline on its tab")
def unique_ids(graph: Graph) -> Yield:
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
                          ("body id", [(q.body, q.id) for q in graph.questions])):
        seen: Dict[str, List[str]] = {}
        for value, owner in values:
            seen.setdefault(value, []).append(owner)
        for value, owners in sorted(seen.items()):
            if len(owners) > 1:
                yield owners[0], "%s %r is used by %d questions: %s" % (
                    label, value, len(owners), ", ".join(owners))
    # the page files an application under an answer by its headline alone,
    # and reads two answers at one headline as one
    for q in graph.questions:
        titles: Dict[str, int] = {}
        for thesis in q.theses:
            titles[thesis.title.strip()] = titles.get(thesis.title.strip(), 0) + 1
        for title, times in titles.items():
            if times > 1:
                yield q.id, ("headline %r stands on %d answers of this question, and "
                             "the page tells its answers apart by headline alone"
                             % (_clip(title), times))


@check("no-restatement",
       "the question text restates no anchor of a term edge that leads to it")
def no_restatement(graph: Graph) -> Yield:
    # on the words and not on how they are drawn: an anchor keeps its
    # emphasis and may close its sentence, and a question does neither
    for q in graph.questions:
        target = _norm(text.plain(q.question))
        for src, term in graph.incoming(q.id):
            for anchor in term.anchors:
                plain = text.plain(anchor)
                normalised = _norm(plain).rstrip(".!?;:,")
                if normalised and normalised in target:
                    yield q.id, ("the question restates the anchor of term %r on %s"
                                 % (term.title, src.id))
                    continue
                run = _shared_run(plain, q.question)
                if run:
                    yield q.id, ("the question repeats 8+ words of the anchor of term "
                                 "%r on %s: %r" % (term.title, src.id, run))


@check("vocabulary",
       "mode, state, kind, party, application standing and tradition.relation are "
       "in their vocabularies")
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
            if thesis.state not in STATES:
                yield q.id, "thesis %r: state %r is not one of %s" % (
                    _clip(thesis.title, 30), thesis.state, ", ".join(STATES))
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


@check("headline-not-identifier",
       "a headline names its content rather than standing in as a handle", WARN)
def headline_not_identifier(graph: Graph) -> Yield:
    """What survives of the retired no-ids-in-prose, narrowed to the thing it
    was really after. A headline summarises; it need not be a sentence, and it
    may well be what a link points at. What it may not be is opaque —
    `term-001` tells a reader nothing — or a bare question id, which names a
    tab and not this thing.

    The notebook called it a title until the root's own answer turned out to
    use that word in its ordinary sense ("the commit … is titled"). The field
    in the graph file keeps its old name: it never reaches the page.
    """
    ids = {q.id for q in graph.questions}
    for q in graph.questions:
        titled = [("thesis", t.title) for t in q.theses]
        titled += [("term", t.title) for t in q.terms()]
        titled += [("mention", m.title) for m in q.mentions()]
        titled += [("application", a.name) for _, a in q.applications()]
        for what, title in titled:
            bare = (title or "").strip()
            if bare in ids:
                yield q.id, ("%s headline %r is a question id, which names a tab "
                             "and not this" % (what, bare))
            elif HANDLE.fullmatch(bare):
                yield q.id, "%s headline %r is a handle and not a name" % (what, bare)


@check("verbatim-collision",
       "no landed answer uses a word the notebook defines elsewhere", WARN)
def verbatim_collision(graph: Graph) -> Yield:
    """An answer recorded in canon cannot change; the notebook's defined
    words can. So where a landed answer uses, in any regular form, a word the
    notebook defines on another question, the finding goes where the word is
    defined, since that is the one that can give way. An answer held or in
    thread is in the notebook only, and is reworded like any other part:
    ``reach`` judges it where it stands. `priority` and `title` went that way once the
    root's answer turned out to say "priorities" and "titled".

    Only the word is decided here. Whether the answer uses it in the defined
    sense is a reading, and a word its own question defines is exempt: that
    definition fixed its sense against that very answer.
    """
    # the plain texts and the forms once each, not once per pair: there are
    # as many pairs as definitions times landed answers
    verbatim = [(q, thesis, text.plain(thesis.text)) for q in graph.questions
                for thesis in q.theses if thesis.state == STATES[-1]]
    for owner in graph.questions:
        for definition in owner.definitions:
            if definition.imported:
                continue  # it defines nothing here, and cannot give way
            forms = text.forms(definition.word)
            for q, thesis, body in verbatim:
                if q.id == owner.id:
                    continue
                used = [form for form in forms if text.occurrences(body, form, True)]
                if used:
                    yield owner.id, ("%r is defined here, and the answer on %s, "
                                     "landed in canon, uses it as %s; those words "
                                     "cannot change, so this one should"
                                     % (definition.word, q.id,
                                        ", ".join(repr(u) for u in used)))


@check("assent-present", "every thesis has a non-empty assent")
def assent_present(graph: Graph) -> Yield:
    for q in graph.questions:
        for thesis in q.theses:
            if not thesis.assent.strip():
                yield q.id, "thesis %r records no assent" % _clip(thesis.title)


@check("definition-anchorable",
       "a definition's word occurs in an answer or in the question's hinge")
def definition_anchorable(graph: Graph) -> Yield:
    """As a word, and in whichever regular form the sentence wants.

    A glossary entry is a headword, so a thesis that only ever says `grants`
    has anchored `grant` as properly as one that says the base — and the
    renderer puts the link on the form that stands there. What it cannot do is
    anchor letters hidden inside a longer word, which is what asking for a
    substring allowed: `grant` was found in `grants`, the check passed, and
    the renderer had nowhere to put the link.

    A question brings a word in two ways: through an answer, or through what
    its asking stood on, which is the question half of its hinge. The root
    has no ancestors, so a word its hinge presupposed could be defined
    nowhere it could reach until the hinge counted. The answer's half does
    not count: it records how the answer was drawn, in the encoding's own
    words, and brings none in.
    """
    for q in graph.questions:
        pool = [text.plain(thesis.text) for thesis in q.theses]
        # a note on a tradition edge is part of the answer it hangs on, and an
        # imported word usually stands nowhere else on the tab
        pool += [text.plain("%s %s" % (edge.note, edge.counter))
                 for thesis in q.theses for edge in thesis.traditions]
        if q.hinge is not None:
            pool.append(text.plain(q.hinge.question))
        for definition in q.definitions:
            if not any(text.occurrences(body, form, True)
                       for body in pool for form in text.forms(definition.word)):
                yield q.id, ("definition %r does not occur as a word, in any "
                             "regular form, in an answer or in the question's "
                             "hinge, so the renderer cannot anchor it"
                             % definition.word)




@check("pressure-shape", "every question's pressure is a non-negative integer")
def pressure_shape(graph: Graph) -> Yield:
    """Pressure is the one scheduling number the principal sets by hand.

    The backlog, once stored as a priority and taken on trust because nothing
    recorded what was blocked behind what, is now computed — pressure summed
    along the term edges, since a question cannot be put until the answers
    above it have landed — so the only thing left to check is the shape of
    the number the sum runs over.
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
    a line missing an edge, which ``reach`` decides.

    An import is not counted: it has no body, and what it says is that this
    question brings in a party's word in the party's own sense. The sense is
    still stated once, on the party's tab. Two questions may import the same
    word, because each is declaring its own dependency on it.
    """
    where: Dict[str, List[str]] = {}
    spelling: Dict[str, str] = {}
    for q in graph.questions:
        for definition in q.definitions:
            if definition.imported:
                continue  # a pointer at a party's entry, not a second sense
            key = definition.word.strip().lower()
            if not key:
                continue
            spelling.setdefault(key, definition.word)
            where.setdefault(key, []).append(q.id)  # every entry: two on one tab are two
    for key, owners in where.items():
        if len(owners) > 1:
            yield owners[0], "%r is defined here and again on %s" % (
                spelling[key], ", ".join("this same question" if o == owners[0] else o
                                         for o in owners[1:]))


@check("import-defined", "an imported word is defined by the party it names")
def import_defined(graph: Graph) -> Yield:
    """An import has no body: it says that this question brings in a party's
    word, in the sense the party's own glossary gives it. Where that glossary
    gives none, the word has no sense anywhere and the entry points at
    nothing — which is worse than leaving the word undefined, because the
    reader is sent somewhere for a sense that is not there."""
    for q in graph.questions:
        for definition in q.definitions:
            if not definition.imported:
                continue
            party = graph.get(definition.tradition.to)
            if party is None:
                continue  # tradition-target says so, and says it better
            if not any(text.fold(other.word) == text.fold(definition.word)
                       and not other.imported for other in party.definitions):
                yield q.id, ("imports %r from %s, which does not define it"
                             % (definition.word, definition.tradition.to))


def _senses(graph: Graph) -> Dict[str, Set[str]]:
    """The folded word -> the questions whose glossary fixes its sense.

    One question, where the graph is well formed. A word defined twice is
    ``definition-once``'s to report, and until it is answered a reader
    reaching either entry has reached the word, so both count here.
    """
    out: Dict[str, Set[str]] = {}
    for q in graph.questions:
        for d in q.definitions:
            if d.imported:
                continue
            owners = out.setdefault(text.fold(d.word), set())
            owners.add(q.id)
            if d.question:
                # a shadow: the sense is fixed by the question the word has
                # earned, and the entry stands for the users that cannot reach
                # it; that question, and what stands under it, reach the sense
                owners.add(d.question)
    return out


def _imported(graph: Graph) -> Dict[str, Set[str]]:
    """question -> the folded words it imports from a party."""
    out: Dict[str, Set[str]] = {}
    for q in graph.questions:
        words = {text.fold(d.word) for d in q.definitions if d.imported}
        if words:
            out[q.id] = words
    return out


def _above(graph: Graph, qid: str) -> Set[str]:
    """The questions whose glossary ``qid`` reaches: its ancestors and itself.

    A party's question reaches, besides its own party's lineage, what stands
    above every question that cites it. The reconstruction was made for those
    questions, and the tradition edge is the one thing that crosses between
    two parties; without it a party's root, which has no parent here, would
    reach nothing at all — not even the word `party`.
    """
    seen = project.ancestors(graph, qid) | {qid}
    q = graph.get(qid)
    if q is not None and q.tradition:
        for other in graph.questions:
            cites = {edge.to for thesis in other.theses
                     for edge in thesis.traditions}
            cites |= {d.tradition.to for d in other.definitions if d.tradition}
            if qid in cites:
                seen |= project.ancestors(graph, other.id) | {other.id}
    return seen


def _vocabulary(senses: Dict[str, Set[str]]) -> List[Tuple[str, List[str]]]:
    """The defined words longest first, each with its regular forms: computed
    once for a run, since every part of every question is read against it."""
    return [(word, text.forms(word)) for word in sorted(senses, key=lambda w: -len(w))]


def _words_used(vocabulary: List[Tuple[str, List[str]]], prose: str) -> List[Tuple[str, str]]:
    """Every defined word standing in ``prose`` as a word, longest first.

    Longest first and once per run, so that a word inside a longer defined one
    is counted as the longer: `term` inside `term edge` is the edge.
    """
    plain = text.plain(prose or "")
    taken: List[Tuple[int, int]] = []
    found: List[Tuple[int, str, str]] = []
    for word, forms in vocabulary:
        for form in forms:
            for run in text.occurrences(plain, form, True):
                span = (run.at, run.at + len(form))
                if any(a < span[1] and span[0] < b for a, b in taken):
                    continue
                taken.append(span)
                found.append((span[0], word, form))
    return [(word, form) for _, word, form in sorted(found)]


def _prose(q) -> Iterator[Tuple[str, str]]:
    """What the notebook writes on a question, each part judged on its tab.

    Not the rendered lines, which are the encoding's words and not his; not
    the answer's hinge, which records how the answer was drawn in those same
    words; and not an answer landed in canon, which cannot be reworded at
    all. An answer held or in thread is in the notebook only, whoever gave
    it, so it is judged like the rest.
    """
    yield "the question", q.question
    if q.hinge is not None:
        yield "the question's hinge", q.hinge.question
    for definition in q.definitions:
        yield "%s %s" % (GLYPHS["glossary"], definition.word), definition.body
        if definition.tradition is not None and definition.tradition.note:
            yield ("the note on %s %s" % (GLYPHS["glossary"], definition.word),
                   definition.tradition.note)
    for note in q.notes:
        yield "a note", note.body
    for thesis in q.theses:
        yield "a headline", thesis.title
        if thesis.state != STATES[-1]:  # canon's words are verbatim-collision's
            yield "an answer", thesis.text
        for term in thesis.terms:
            yield "the term %r" % _clip(term.title), term.title
            if term.deadlock:
                yield ("the deadlock on %r" % _clip(term.title),
                       "%s %s" % (term.deadlock.counter, term.deadlock.attenuation))
            if term.suspended:
                yield "the suspension on %r" % _clip(term.title), term.suspended
        for mention in thesis.mentions:
            yield "the mention %r" % _clip(mention.title), mention.title
        for edge in thesis.traditions:
            yield "the note on %s" % edge.to, "%s %s" % (edge.note, edge.counter)
        for app in thesis.applications:
            yield ("%s %s" % (GLYPHS["application"], app.name),
                   "%s %s %s" % (app.name, app.what, app.note))


@check("reach", "a defined word is used where its sense can be reached")
def reach(graph: Graph) -> Yield:
    """The context rule, held over the notebook's own vocabulary.

    A turn carries canon above its question and nothing else. So a word the
    principal writes leans on a sense that will be in the turn only if the
    question fixing it stands above the one he is writing on. Where it does
    not, the line is missing an edge or the definition sits on the wrong
    question — and where the word is a party's, neither remedy applies,
    because a party's notebook never stands above a question of his: the word
    is imported, or it is not used.

    Which parts are his is the whole of what this turns on, and ``_prose``
    says. The rest is the encoding's own words: the rendered lines, the
    answer's hinge, and an answer landed in canon, which he cannot reword and
    which ``verbatim-collision`` reports where the word is defined.
    """
    senses = _senses(graph)
    vocabulary = _vocabulary(senses)
    imports = _imported(graph)
    above = {q.id: _above(graph, q.id) for q in graph.questions}
    parties = set(graph.tradition_ids())
    # one finding per word and part, however often the part uses it: a word
    # used twice in one answer is one thing out of reach, not two
    counted: Dict[Tuple[str, str, str, str], int] = {}
    for q in graph.questions:
        if graph.partial and q.id in parties:
            continue  # a party reaches over what cites it, from anywhere
        seen = above[q.id]
        for what, prose in _prose(q):
            for word, form in _words_used(vocabulary, prose):
                if senses[word] & seen:
                    continue
                if any(word in imports.get(other, set()) for other in seen):
                    continue
                key = (q.id, what, form, word)
                counted[key] = counted.get(key, 0) + 1
    for (qid, what, form, word), times in counted.items():
        fixed = sorted(senses[word])
        # a party's notebook never stands above a question here, so no edge
        # and no move of the definition can bring its word into reach: an
        # import that names the party is the one remedy, and is named
        remedy = ("; a party's word is brought in by an import that names the party"
                  if all(owner in parties for owner in fixed) else "")
        yield qid, ("%s uses %r%s, and its sense is fixed on %s, which %s "
                    "cannot reach%s"
                    % (what, form, _times(times), " and ".join(fixed),
                       qid, remedy))


def _times(n: int) -> str:
    if n < 2:
        return ""
    return " (%s)" % ("twice" if n == 2 else "%d times" % n)


@check("shadow-declared",
       "a definition whose word is another question's id points at that question",
       WARN)
def shadow_declared(graph: Graph) -> Yield:
    """A word that has earned a question of its own has its sense fixed by
    that question's thesis, so a definition of it standing on any other
    question is a shadow: the sense in a sentence, for the users of the word
    that cannot reach the question over their ancestors, and a pointer to
    where the argument is. Whether reach needs the shadow is judged by
    reading. That the entry says what it is can be decided in the one case
    where the word is a question's own id, and is decided here; a word that
    earned a question under another name — `backlog` shadowing `priority` —
    is still the reader's to see.

    An entry on the question's own tab is that question's own definition and
    not a shadow, and `term-target` keeps it from pointing at itself. An
    import is a party's word in the party's sense, and shadows nothing.
    """
    ids = {text.fold(q.id): q.id for q in graph.questions}
    for q in graph.questions:
        for definition in q.definitions:
            if definition.imported or definition.question:
                continue
            target = ids.get(text.fold(definition.word.strip()))
            if target is None or target == q.id:
                continue
            yield q.id, ("definition %r is the word of the question %s and does "
                         "not point at it; a definition standing for a "
                         "question's word is a shadow, and says so"
                         % (definition.word, target))


@check("standing-honest",
       "an application is derived only from an answer that has landed")
def standing_honest(graph: Graph) -> Yield:
    """An artifact built ahead of the answer that would justify it is the
    ordinary way work gets done and the ordinary way a graph rots. Calling it
    a postulate is what keeps the debt visible.

    A postulate is anything the notebook supports and canon does not, whether
    it is an answer or an artifact built from one, and the two are graded in
    two steps. An answer is canon once it has itself landed, which is read off
    its state and so cannot be wrong. An artifact is derived only from an
    answer that is canon, which is necessary and not sufficient: a canon
    answer may have an artifact nobody has diffed against it. That judgement
    is the writer's and is named in the attenuation list; what is checked here
    is the part that is not a judgement at all.
    """
    for q in graph.questions:
        for thesis, app in q.applications():
            if app.standing == "derived" and thesis.state != STATES[-1]:
                yield q.id, ("application %r stands as derived, but the answer it "
                             "comes from is %r and not landed"
                             % (app.name, thesis.state))


@check("state-order", "no answer has got further than its question")
def state_order(graph: Graph) -> Yield:
    """An answer is given to a question that has been put, and merged with it
    or after it. So an answer in thread stands under a question at least in
    thread, and a landed answer under a landed question. The question may be
    ahead — the root landed as a seed before it was answered — but never
    behind."""
    rank = {state: i for i, state in enumerate(STATES)}
    for q in graph.questions:
        if q.state not in rank:
            continue  # vocabulary's to report
        for thesis in q.theses:
            if rank.get(thesis.state, -1) > rank[q.state]:
                yield q.id, ("thesis %r is %r, further than its question, which "
                             "is %r" % (_clip(thesis.title, 30), thesis.state, q.state))


@check("deadlock-complete",
       "a deadlock carries a counter-clause, and once its answer has landed the "
       "attenuation it earns")
def deadlock_complete(graph: Graph) -> Yield:
    """Dissent without a grading is half a record. The counter-clause says what
    the principal holds instead; the attenuation says what the clause may still
    license, which is the whole use of recording the dissent rather than simply
    withholding the merge.

    The grading is owed at the merge and not before. On an open thread the
    clause licenses nothing yet, and a dissent is worth recording while the
    thread runs, before what it will cost is settled.
    """
    for q in graph.questions:
        for thesis in q.theses:
            for term in thesis.terms:
                if term.deadlock is None:
                    continue
                if not term.deadlock.counter.strip():
                    yield q.id, "term %r: deadlock has no counter-clause" % term.title
                if (thesis.state == STATES[-1]
                        and not term.deadlock.attenuation.strip()):
                    yield q.id, ("term %r: deadlock has no attenuation, so what the "
                                 "landed clause may still license is unrecorded"
                                 % term.title)


@check("suspension-open",
       "a clause's acceptance is suspended only while its answer is in thread, "
       "and never beside a deadlock")
def suspension_open(graph: Graph) -> Yield:
    """A suspension is acceptance withheld while the thread runs. The merge
    that ends the thread settles every clause, assented or deadlocked, so a
    landed answer carries none; and an answer that was never put has no
    thread to suspend in. A clause cannot be both suspended and deadlocked:
    one withholds acceptance, the other has refused it."""
    for q in graph.questions:
        for thesis in q.theses:
            for term in thesis.terms:
                if not term.suspended.strip():
                    continue
                if thesis.state != STATES[1]:
                    yield q.id, ("term %r is suspended, but its answer is %r and "
                                 "not in thread" % (term.title, thesis.state))
                if term.deadlock is not None:
                    yield q.id, ("term %r is both suspended and deadlocked"
                                 % term.title)


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


@check("answerer-set",
       "an author question names who answers it; a tradition names no one")
def answerer_set(graph: Graph) -> Yield:
    """Who answers a question is stored and not read off what it waits on: a
    question with nothing left to wait on is not thereby the principal's, and
    one he means to put later changes its answerer and nothing else. A
    tradition is answered by its own party, through a reconstruction, so it
    names none."""
    for q in graph.questions:
        if q.tradition:
            if q.answerer:
                yield q.id, ("a tradition is answered by its own party and names "
                             "no answerer, but this one names %r" % q.answerer)
        elif not q.answerer:
            yield q.id, ("names no answerer; say whether the AI or the principal "
                         "answers it")
        elif q.answerer not in ANSWERERS:
            yield q.id, "answerer %r is not one of %s" % (
                q.answerer, ", ".join(ANSWERERS))


@check("only-ai-put",
       "a question the AI does not answer is never put, so it and its answers stay held")
def only_ai_put(graph: Graph) -> Yield:
    """Only a question the AI answers is ever put, and only the merge of what
    it said lands. A question the principal answers is his own and never goes
    to a turn; another party's is read, not asked. Neither goes into a thread
    or lands, and an answer to either that said it had would read as canon —
    which is what its standing, read off its state, would then claim. So the
    fact the discharge clause and the frontier rest on is held here rather
    than assumed."""
    for q in graph.questions:
        if q.answerer == ANSWERERS[0]:
            continue
        who = "the principal" if q.answerer == ANSWERERS[1] else "another party"
        if q.state != STATES[0]:
            yield q.id, ("the question is %r, but a question %s answers is never "
                         "put" % (q.state, who))
        for thesis in q.theses:
            if thesis.state != STATES[0]:
                yield q.id, ("answer %r is %r, but nothing %s answers lands"
                             % (_clip(thesis.title), thesis.state, who))


@check("put-in-order", "nothing is put below a question that has not been")
def put_in_order(graph: Graph) -> Yield:
    """A turn carries canon above its question, so a question cannot be put
    while one the AI answers above it is still held: that answer is neither
    on main nor on the branch, and the turn would go without it.

    What this cannot see is which thread a question is on. An answer earlier
    in the same thread is in the turn's context without having landed — which
    is how a thread runs on past one question — so what is held here is the
    half that stands either way: the question above has at least been put.
    """
    held = [other for other in graph.questions if not project.put(other)]
    behind = {other.id: project.blocked_behind(graph, other.id) for other in held}
    for q in graph.questions:
        if not project.put(q):
            continue
        for other in held:
            if q.id in behind[other.id]:
                yield q.id, ("is put, but %s, which the AI answers above it, is "
                             "still held" % other.id)


@check("mention-justified",
       "a mention stands where a term in its place would close a cycle", WARN)
def mention_justified(graph: Graph) -> Yield:
    """A mention is an edge the graph has not justified: it points without
    raising, so nothing descends from it. Where the question it points at
    already stands above the clause, a term would close a cycle and the mention
    is the only honest encoding; the renderer says so under it. Anywhere else a
    term would do, and a better line is probably available."""
    known = {x.id for x in graph.questions}
    for q in graph.questions:
        for mention in q.mentions():
            if mention.to not in known:
                continue  # term-target reports it
            if q.id not in project.reachable_from(graph, mention.to):
                yield q.id, ("mention %r points at %s, which does not stand above "
                             "this question, so a term would close no cycle"
                             % (mention.title, mention.to))


@check("anchor-grain",
       "no term's anchor contains or overlaps the anchor of another on the same thesis")
def anchor_grain(graph: Graph) -> Yield:
    """One follow-up is one term. A clause that contains another clause's
    anchor raises the synthesis rather than the parts, and the two links over
    one another are the ones the document skips in silence.

    Two anchors that overlap without one containing the other are as bad on
    the way back: the page spells a chip as its bare label where the anchor
    ends, so the label of one stands inside the other, and the reader can
    take neither off the words."""
    for q in graph.questions:
        for thesis in q.theses:
            anchors = [(term.title, text.plain(a)) for term in thesis.terms
                       for a in term.anchors if a.strip()]
            for outer, big in anchors:
                for inner, small in anchors:
                    if outer != inner and small != big and small in big:
                        yield q.id, ("term %r has an anchor containing the anchor "
                                     "of term %r" % (outer, inner))
            plain_text = text.plain(thesis.text)
            placed = [(title, a, plain_text.find(a))
                      for title, a in anchors + [(m.title, text.plain(a)) for m in thesis.mentions
                                                 for a in m.anchors if a.strip()]]
            spans = [(title, a, at, at + len(a)) for title, a, at in placed if at >= 0]
            for i, (one, a, s1, e1) in enumerate(spans):
                for other, b, s2, e2 in spans[i + 1:]:
                    if s1 < e2 and s2 < e1 and a not in b and b not in a:
                        yield q.id, ("%r has an anchor overlapping the anchor of %r, "
                                     "and the page could take neither chip off the words"
                                     % (one, other))


#: a line break inside a paragraph. A single newline is the markdown's own only
#: where the block is built out of lines — a list, a table, a quotation — so
#: what opens the next line is what decides which it is.
_WRAPPED = re.compile(r"(?<!\n)\n(?!\n)(?! *(?:[>|#]|%s[ \t]))" % text.LIST_MARKER)


@check("text-unwrapped",
       "an answer's text has no line break inside a paragraph, and a citation's note none")
def text_unwrapped(graph: Graph) -> Yield:
    """The document joins a wrapped line back into its paragraph, so a text
    written with hard breaks can never be read back as it was stored: the page
    and the renderer disagree for as long as it stands.

    It arrives from outside — a draft wrapped at whatever column the tool that
    wrote it used — and nothing downstream could see it, because the local
    round trip renders and reads the same breaks straight back.
    """
    for q in graph.questions:
        for thesis in q.theses:
            broken = _WRAPPED.search(thesis.text)
            if broken and broken.end() == len(thesis.text):
                yield q.id, ("the answer's text ends in a line break, which the "
                             "page does not keep")
            elif broken:
                at = broken.start()
                yield q.id, ("the answer's text breaks a line inside a "
                             "paragraph, which the document will join: %r"
                             % thesis.text[max(0, at - 30):at + 30])
        # a citation's note and counter, and a borrowing's note, are each one
        # list item: a line break in one is read back as a second item, or as
        # the item's first words lost
        for what, held in _one_line(q):
            if "\n" in held:
                yield q.id, "%s breaks a line, and is written as one: %r" % (what, _clip(held))


def _one_line(q) -> Iterator[Tuple[str, str]]:
    """The parts the renderer writes as one line each."""
    for thesis in q.theses:
        for edge in thesis.traditions:
            yield "the note on %s" % edge.to, edge.note
            yield "the counter on %s" % edge.to, edge.counter
    for definition in q.definitions:
        if definition.tradition is not None:
            yield ("the note on %s %s" % (GLYPHS["glossary"], definition.word),
                   definition.tradition.note)


#: a block that opens with a quotation mark, at the start of the text or after
#: the blank line that ends the block before it. A ``>`` inside a paragraph is
#: a character; one opening a block is a blockquote.
_QUOTED = re.compile(r"(?:\A|\n[ \t]*\n)[ \t]*>")

#: a block that opens on a heading mark: the reader takes it for a heading of
#: the layout's, and what follows it as under that heading
_HEADED = re.compile(r"(?:\A|\n[ \t]*\n)[ \t]*#")


def _parted(q) -> Iterator[Tuple[str, str]]:
    """The texts the reader parts into blocks, each with what it is."""
    for thesis in q.theses:
        yield "the answer's text", thesis.text
    for definition in q.definitions:
        yield "the body of %s %s" % (GLYPHS["glossary"], definition.word), definition.body
    if q.hinge is not None:
        yield "the hinge's question", q.hinge.question
        yield "the hinge's thesis", q.hinge.thesis


@check("text-unquoted",
       "no text opens a block the reader takes for the layout's own: a blockquote, "
       "a heading, a citation heading")
def text_unquoted(graph: Graph) -> Yield:
    """A blockquote on the page is a note: somebody's own words on a section,
    kept apart from the prose the renderer wrote so that a re-render carries
    them over instead of writing them back as content. The reader holds that
    everywhere, so a blockquote inside an answer's text is read back as a
    note on the Thesis section and the next render moves it out of the
    answer — the one edit to an answer's text that nothing else can see,
    since the local round trip agrees with itself.

    An answer landed in canon is verbatim, so one that quotes cannot be
    reworded to pass. Until the reader can tell a quotation in an answer from a note
    beside it, such an answer is refused here rather than altered in silence.

    The same holds of a block opening on ``#``, which the reader takes for a
    heading and ends the text at, and of a block that is one of the two
    citation headings, which opens the citations; and it holds of every text
    the reader parts into blocks — a definition's body and the hinge's two
    halves as much as an answer's text.
    """
    for q in graph.questions:
        for what, held in _parted(q):
            quoted = _QUOTED.search(held)
            if quoted:
                at = quoted.end() - 1
                yield q.id, ("%s holds a blockquote, which the page reads back "
                             "as a note: %r" % (what, held[at:at + 60]))
            headed = _HEADED.search(held)
            if headed:
                at = headed.end() - 1
                yield q.id, ("%s opens a block on #, which the page reads back as "
                             "a heading and ends the text at: %r" % (what, held[at:at + 60]))
            for block in held.split("\n\n"):
                if block.strip() in CITATION_HEADINGS:
                    yield q.id, ("%s holds a block reading %s, which the page takes "
                                 "for the heading that opens the citations"
                                 % (what, block.strip()))


@check("note-unstopped",
       "no citation's note or counter, and no borrowing's note, ends in a stop: the "
       "renderer closes each with one, and the reader takes that one off")
def note_unstopped(graph: Graph) -> Yield:
    """A citation's note, a divergence's counter and a borrowing's note are
    each closed on the page with one stop, which parts the words from the
    crumb that follows them; the reader takes that one stop back off. A note
    stored with a stop of its own renders as one without and reads back
    without it, so ``etc.`` came back ``etc`` at every rebuild and ``...``
    came back as nothing. The stop is the page's, and the stored note ends
    before it.
    """
    for q in graph.questions:
        for thesis in q.theses:
            for trad in thesis.traditions:
                for field, value in (("note", trad.note), ("counter", trad.counter)):
                    if value.rstrip().endswith("."):
                        yield q.id, ("the %s on the citation of %s ends in a stop, which "
                                     "the renderer adds and the reader takes off: %r"
                                     % (field, trad.to, _clip(value)))
        for definition in q.definitions:
            if definition.tradition and definition.tradition.note.rstrip().endswith("."):
                yield q.id, ("the note on the borrowing of %s %s ends in a stop, which the "
                             "renderer adds and the reader takes off: %r"
                             % (GLYPHS["glossary"], definition.word,
                                _clip(definition.tradition.note)))


@check("fields-parted",
       "no headline, and no application's what or link, carries the · that parts "
       "an application line's fields")
def fields_parted(graph: Graph) -> Yield:
    """An application is written as one line, ``what · ◆ headline · link ·
    standing · note``, and read back by its separators; a field carrying one
    is read as two, and the application is filed under no answer and dropped
    at the next body write. The note is the last field and may say what it
    likes. A headline is judged whether or not an application says it yet, as
    the in-place writer judges it.
    """
    for q in graph.questions:
        for thesis in q.theses:
            if "·" in thesis.title:
                yield q.id, ("the headline %r carries ·, which parts the fields of "
                             "an application line" % _clip(thesis.title))
            for app in thesis.applications:
                for field, value in (("what", app.what), ("link", app.link)):
                    if "·" in value:
                        yield q.id, ("%s %s: its %s carries ·, which parts the fields "
                                     "of its line" % (GLYPHS["application"], app.name, field))


@check("dictation-pending",
       "no note opens with pending: a clause of a dictation no run has applied stands on "
       "its tab as one until a run takes it in", WARN)
def dictation_pending(graph: Graph) -> Yield:
    """A dictation run that cannot apply a clause writes it as a note on the
    tab it bears on, opening with the word *pending*, so that what a run
    owes stands on the page and not in the session that owed it. The note is
    reported for as long as it stands: the next dictation or bootstrap round
    takes it in and takes it off. A warning and not an error, because the
    page is right to hold it; what is wrong is only that nothing has yet done
    what it says.
    """
    for q in graph.questions:
        for note in q.notes:
            words = note.body.strip()
            if words.lower().startswith("pending"):
                yield q.id, ("a pending note on %s, a clause no run has yet applied: %s"
                             % (note.section, _clip(words)))


# -- the runner -------------------------------------------------------------

def run(graph: Graph, only: Optional[Iterable[str]] = None) -> List[Finding]:
    """Every finding, in check order; ``only`` naming no check is refused,
    since running nothing and finding nothing would read as a pass."""
    wanted = set(only) if only else None
    if wanted:
        unknown = sorted(wanted - {spec.id for spec in CHECKS})
        if unknown:
            raise ValueError("no check is named %s" % ", ".join(unknown))
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
