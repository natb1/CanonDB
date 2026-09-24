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
from .model import (ANSWERERS, CANON, Graph, INBOX_KINDS, KINDS, MODES,
                    RELATIONS, SECTIONS, STANDINGS, STATES)

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
    """
    for q in graph.questions:
        section = "\n\n".join(
            [thesis.text for thesis in q.theses]
            + [part for thesis in q.theses for trad in thesis.traditions
               for part in (trad.note, trad.counter) if part])
        for thesis in q.theses:
            for term in list(thesis.terms) + list(thesis.mentions):
                for anchor in term.anchors:
                    own = _overlapping(thesis.text, anchor) if anchor else 0
                    found = _overlapping(section, anchor) if anchor else 0
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
    for q in graph.questions:
        for term in q.terms():
            if term.to not in known:
                yield q.id, "term %r leads to %r, which is no question" % (
                    term.title, term.to)
        for mention in q.mentions():
            if mention.to not in known:
                yield q.id, "mention %r points at %r, which is no question" % (
                    mention.title, mention.to)
        for definition in q.definitions:
            if not definition.question:
                continue
            if definition.question not in known:
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
        titled += [("inbox item", i.title) for i in q.inbox]
        titled += [("application", a.name) for _, a in q.applications()]
        for what, title in titled:
            bare = (title or "").strip()
            if bare in ids:
                yield q.id, ("%s headline %r is a question id, which names a tab "
                             "and not this" % (what, bare))
            elif HANDLE.fullmatch(bare):
                yield q.id, "%s headline %r is a handle and not a name" % (what, bare)


@check("verbatim-collision",
       "no answer in the AI's words uses a word the notebook defines elsewhere", WARN)
def verbatim_collision(graph: Graph) -> Yield:
    """The AI's words are canon's and cannot change; the notebook's defined
    words can. So where an answer given in the AI's words — one in thread or
    landed — uses, in any regular form, a word the notebook defines on another
    question, the finding goes where the word is defined, since that is the
    one that can give way. `priority` and `title` went that way once the
    root's answer turned out to say "priorities" and "titled".

    Only the word is decided here. Whether the answer uses it in the defined
    sense is a reading, and a word its own question defines is exempt: that
    definition fixed its sense against that very answer.
    """
    verbatim = [(q, thesis) for q in graph.questions for thesis in q.theses
                if thesis.state in STATES[1:]]
    for owner in graph.questions:
        for definition in owner.definitions:
            for q, thesis in verbatim:
                if q.id == owner.id:
                    continue
                body = text.plain(thesis.text)
                used = [form for form in text.forms(definition.word)
                        if text.occurrences(body, form, True)]
                if used:
                    yield owner.id, ("%r is defined here, and the answer on %s, in "
                                     "the AI's words, uses it as %s; those words "
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


@check("requires-discharged",
       "a question that has been put waits on nothing that is not done")
def requires_discharged(graph: Graph) -> Yield:
    """``requires`` names what must be done before a question can be put, so a
    question that has been put waited on nothing still undone.

    A question has been put when a thread is open on it, or when an answer to
    it stands in one or has landed. Landing alone does not say so: a question
    lands when it reaches main, and the root reached main as the seed it was
    asked from, before anyone had put it. The root once carried its own
    promulgation here, which is the act that follows its answer rather than
    one that precedes it. An entry naming no item at all is
    `requires-exist`'s to report, not this one's.
    """
    done = {item.id: item.done for q in graph.questions for item in q.inbox}
    for q in graph.questions:
        if not _put(q):
            continue
        pending = sorted(w for w in q.requires if w in done and not done[w])
        if pending:
            yield q.id, ("has been put but still waits on %s, which %s not done"
                         % (", ".join(repr(p) for p in pending),
                            "is" if len(pending) == 1 else "are"))


_put = project.put


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

    A done item is exempt here: it blocks nothing, and it stays only while some
    question still names it, which is how a question shows that what it waited
    on is done. Once nothing names it, it is history, and `inbox-history` says
    so. `inbox-placement` asks a different question of the same field and skips
    this case, which is why it is a rule of its own.
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
            if q.id not in where.setdefault(key, []):
                where[key].append(q.id)
    for key, owners in where.items():
        if len(owners) > 1:
            yield owners[0], "%r is defined here and again on %s" % (
                spelling[key], ", ".join(owners[1:]))


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
            if not d.imported:
                out.setdefault(text.fold(d.word), set()).add(q.id)
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


def _words_used(senses: Dict[str, str], prose: str) -> List[Tuple[str, str]]:
    """Every defined word standing in ``prose`` as a word, longest first.

    Longest first and once per run, so that a word inside a longer defined one
    is counted as the longer: `term` inside `term edge` is the edge.
    """
    plain = text.plain(prose or "")
    taken: List[Tuple[int, int]] = []
    found: List[Tuple[int, str, str]] = []
    for word in sorted(senses, key=lambda w: -len(w)):
        for form in text.forms(word):
            for run in text.occurrences(plain, form, True):
                span = (run.at, run.at + len(form))
                if any(a < span[1] and span[0] < b for a, b in taken):
                    continue
                taken.append(span)
                found.append((span[0], word, form))
    return [(word, form) for _, word, form in sorted(found)]


def _prose(graph: Graph, q) -> Iterator[Tuple[str, str, Optional[List[str]]]]:
    """What the principal writes on a question, and where each part is judged.

    Not the rendered lines, which are the encoding's words and not his; not
    the answer's hinge, which records how the answer was drawn in those same
    words; and not an answer in the AI's words, which cannot be reworded at
    all. An inbox item is hoisted to a common ancestor to make a dashboard, so
    it is judged from every question that requires it — the tabs it was
    lifted from — and from its own only when nothing does.
    """
    yield "the question", q.question, None
    if q.hinge is not None:
        yield "the question's hinge", q.hinge.question, None
    for definition in q.definitions:
        yield "≡ %s" % definition.word, definition.body, None
    for note in q.notes:
        yield "a note", note.body, None
    for item in q.inbox:
        wants = [other.id for other in graph.questions if item.id in other.requires]
        yield ("inbox item %r" % item.id,
               "%s %s %s" % (item.title, item.what, item.obligation), wants or None)
    for thesis in q.theses:
        yield "a headline", thesis.title, None
        if thesis.state == STATES[0]:  # the AI's words are verbatim-collision's
            yield "an answer", thesis.text, None
        for term in thesis.terms:
            yield "the term %r" % _clip(term.title), term.title, None
            if term.deadlock:
                yield ("the deadlock on %r" % _clip(term.title),
                       "%s %s" % (term.deadlock.counter, term.deadlock.attenuation), None)
            if term.suspended:
                yield "the suspension on %r" % _clip(term.title), term.suspended, None
        for mention in thesis.mentions:
            yield "the mention %r" % _clip(mention.title), mention.title, None
        for edge in thesis.traditions:
            yield ("the note on %s" % edge.to,
                   "%s %s" % (edge.note, edge.counter), None)
        for app in thesis.applications:
            yield ("⚙ %s" % app.name, "%s %s" % (app.name, app.note), None)


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
    answer's hinge, and an answer in the AI's words, which he cannot reword
    and which ``verbatim-collision`` reports where the word is defined.
    """
    senses = _senses(graph)
    imports = _imported(graph)
    above = {q.id: _above(graph, q.id) for q in graph.questions}
    parties = set(graph.tradition_ids())
    # one finding per word and part, however often the part uses it: a word
    # used twice in one answer is one thing out of reach, not two
    counted: Dict[Tuple[str, str, str, str, str], int] = {}
    for q in graph.questions:
        for what, prose, wants in _prose(graph, q):
            for word, form in _words_used(senses, prose):
                for judged in (wants or [q.id]):
                    seen = above.get(judged, {judged})
                    if senses[word] & seen:
                        continue
                    if any(word in imports.get(other, set()) for other in seen):
                        continue
                    key = (q.id, what, form, judged, word)
                    counted[key] = counted.get(key, 0) + 1
    for (qid, what, form, judged, word), times in counted.items():
        where = "" if judged == qid else ", which %s requires" % judged
        fixed = sorted(senses[word])
        # a party's notebook never stands above a question here, so no edge
        # and no move of the definition can bring its word into reach: an
        # import that names the party is the one remedy, and is named
        remedy = ("; a party's word is brought in by an import that names the party"
                  if all(owner in parties for owner in fixed) else "")
        yield qid, ("%s uses %r%s%s, and its sense is fixed on %s, which %s "
                    "cannot reach%s"
                    % (what, form, _times(times), where, " and ".join(fixed),
                       judged, remedy))


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
    """Who answers a question is stored, because `requires` only blocks: a
    question with nothing left to wait on is not thereby the principal's, and
    one he means to put later changes its answerer rather than its requires. A
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


@check("requires-put", "a question the AI does not answer waits on nothing")
def requires_put(graph: Graph) -> Yield:
    """``requires`` names what must be done before a question can be put, and
    a question the AI does not answer is never put. The entry is not merely
    idle: an item nothing else names stays alive on ``inbox-required``
    because of it, and ``inbox-placement`` drags the item's home toward a
    question that is not waiting for anything."""
    for q in graph.questions:
        if q.answerer == ANSWERERS[0] or not q.requires:
            continue
        who = "the principal" if q.answerer == ANSWERERS[1] else "another party"
        yield q.id, ("waits on %s, but a question %s answers is never put"
                     % (", ".join(repr(w) for w in q.requires), who))


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
    for q in graph.questions:
        if not _put(q):
            continue
        for other in graph.questions:
            if other.id == q.id or _put(other):
                continue
            if q.id in project.blocked_behind(graph, other.id):
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
    for q in graph.questions:
        for mention in q.mentions():
            if mention.to not in {x.id for x in graph.questions}:
                continue  # term-target reports it
            if q.id not in project.reachable_from(graph, mention.to):
                yield q.id, ("mention %r points at %s, which does not stand above "
                             "this question, so a term would close no cycle"
                             % (mention.title, mention.to))


@check("anchor-grain",
       "no term's anchor contains the anchor of another term on the same thesis")
def anchor_grain(graph: Graph) -> Yield:
    """One follow-up is one term. A clause that contains another clause's
    anchor raises the synthesis rather than the parts, and the two links over
    one another are the ones the document skips in silence."""
    for q in graph.questions:
        for thesis in q.theses:
            anchors = [(term.title, text.plain(a)) for term in thesis.terms
                       for a in term.anchors if a.strip()]
            for outer, big in anchors:
                for inner, small in anchors:
                    if outer != inner and small != big and small in big:
                        yield q.id, ("term %r has an anchor containing the anchor "
                                     "of term %r" % (outer, inner))


@check("inbox-history",
       "a done inbox item is named by some question's requires", WARN)
def inbox_history(graph: Graph) -> Yield:
    """An action exists only as something a question requires. A done item
    stays while a question still names it, since that is how the question
    shows its wait is over; when none does, the item is a record of an act,
    and the notebook keeps states rather than a log."""
    wanted: Set[str] = set()
    for q in graph.questions:
        wanted.update(q.requires)
    for q in graph.questions:
        for item in q.inbox:
            if item.done and item.id not in wanted:
                yield q.id, ("inbox item %r is done and no question names it; it "
                             "is history, so drop it" % item.id)


#: a line break inside a paragraph. A single newline is the markdown's own only
#: where the block is built out of lines — a list, a table, a quotation — so
#: what opens the next line is what decides which it is.
_WRAPPED = re.compile(r"(?<!\n)\n(?!\n)(?! *(?:[-*>|#]|\d+\.))")


@check("text-unwrapped",
       "an answer's text has no line break inside a paragraph")
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
            if broken:
                at = broken.start()
                yield q.id, ("the answer's text breaks a line inside a "
                             "paragraph, which the document will join: %r"
                             % thesis.text[max(0, at - 30):at + 30])


#: a block that opens with a quotation mark, at the start of the text or after
#: the blank line that ends the block before it. A ``>`` inside a paragraph is
#: a character; one opening a block is a blockquote.
_QUOTED = re.compile(r"(?:\A|\n[ \t]*\n)[ \t]*>")


@check("text-unquoted", "an answer's text has no blockquote")
def text_unquoted(graph: Graph) -> Yield:
    """A blockquote on the page is a note: somebody's own words on a section,
    kept apart from the prose the renderer wrote so that a re-render carries
    them over instead of writing them back as content. The reader holds that
    everywhere, so a blockquote inside an answer's text is read back as a
    note on the Thesis section and the next render moves it out of the
    answer — the one edit to an answer's text that nothing else can see,
    since the local round trip agrees with itself.

    An answer in canon is verbatim, so one that quotes cannot be reworded to
    pass. Until the reader can tell a quotation in an answer from a note
    beside it, such an answer is refused here rather than altered in silence.
    """
    for q in graph.questions:
        for thesis in q.theses:
            quoted = _QUOTED.search(thesis.text)
            if quoted:
                at = quoted.end() - 1
                yield q.id, ("the answer's text holds a blockquote, which the "
                             "page reads back as a note: %r"
                             % thesis.text[at:at + 60])


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
