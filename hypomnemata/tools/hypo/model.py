"""Dataclasses for the graph file, and validation of its shape.

Shape validation is separate from the checks in ``spec``: it establishes that the
JSON can be loaded into the model at all (required keys, types), so that every
check may then assume a well-shaped graph and report on its *content*.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional, Tuple

#: How far a question has got. It is held while drafted and not yet put; in
#: thread while it is put on an elenchus branch and not yet merged, however
#: many turns the thread has taken; landed once merged, which is when it is
#: canon. The principal may note his assent on an open thread to draft the
#: next question from it, and the question is still in thread: only the
#: merge records assent to canon, and the merge is promulgation.
STATES = ("held", "in thread", "landed")
KINDS = ("definitional", "case", "consistency", "root")

#: An application's standing: the artifact exists and its landed source has
#: been diffed against it, or it was built ahead of that and owes the diff.
STANDINGS = ("derived", "postulate")

#: A question's or a thesis's standing: supported by canon, or supported by
#: the notebook only and so assumed ahead of the elenchus reaching it.
NODE_STANDINGS = ("canon", "postulate")

RELATIONS = ("support", "divergence")

#: Who answers a question: the AI, by a turn in a clean context, or the
#: principal, from his own priors. A question the principal answers is not
#: put. It is stored rather than read off `requires`, which only blocks: a
#: question with nothing left to wait on is not thereby his, and one he means
#: to put later changes its answerer, not its requires. A tradition names
#: none, because its party answers it.
ANSWERERS = ("ai", "principal")
INBOX_KINDS = ("promulgate", "provide", "dispose", "build")

#: The party whose notebook a question belongs to, where none is named. A
#: question whose party is someone else is a tradition: a root of its own,
#: outside this graph's lineage. The principal is the party with recognition
#: of the term at deadlock, which is a role in a bond and not a field here.
AUTHOR = "author"

#: The section a note may be attached to, as the renderer names them.
SECTIONS = ("thesis", "glossary", "inbox", "terms", "applications",
            "cited by", "hinge")

NOTEBOOK = "notebook"
CANON = "canon"
MODES = (NOTEBOOK, CANON)


class ShapeError(Exception):
    """The graph file cannot be loaded into the model."""

    def __init__(self, problems: List[str]):
        self.problems = problems
        super().__init__("%d shape problem(s)" % len(problems))


class _Reader:
    """Accumulates shape problems instead of raising on the first one."""

    def __init__(self) -> None:
        self.problems: List[str] = []

    def fail(self, where: str, msg: str) -> None:
        self.problems.append("%s: %s" % (where, msg))

    def obj(self, value: Any, where: str) -> Dict[str, Any]:
        if not isinstance(value, dict):
            self.fail(where, "expected an object, found %s" % type(value).__name__)
            return {}
        return value

    def text(self, d: Dict[str, Any], key: str, where: str,
             required: bool = True, default: str = "") -> str:
        if key not in d:
            if required:
                self.fail(where, "missing %r" % key)
            return default
        v = d[key]
        if v is None and not required:
            return default
        if not isinstance(v, str):
            self.fail(where, "%r must be a string" % key)
            return default
        return v

    def opt_text(self, d: Dict[str, Any], key: str, where: str) -> Optional[str]:
        v = d.get(key)
        if v is None:
            return None
        if not isinstance(v, str):
            self.fail(where, "%r must be a string or null" % key)
            return None
        return v

    def flag(self, d: Dict[str, Any], key: str, where: str, default: bool = False) -> bool:
        v = d.get(key, default)
        if not isinstance(v, bool):
            self.fail(where, "%r must be true or false" % key)
            return default
        return v

    def number(self, d: Dict[str, Any], key: str, where: str) -> int:
        if key not in d:
            self.fail(where, "missing %r" % key)
            return 0
        v = d[key]
        if isinstance(v, bool) or not isinstance(v, int):
            self.fail(where, "%r must be an integer" % key)
            return 0
        return v

    def seq(self, d: Dict[str, Any], key: str, where: str) -> List[Any]:
        v = d.get(key, [])
        if v is None:
            return []
        if not isinstance(v, list):
            self.fail(where, "%r must be a list" % key)
            return []
        return v

    def strings(self, d: Dict[str, Any], key: str, where: str) -> List[str]:
        out = []
        for i, v in enumerate(self.seq(d, key, where)):
            if not isinstance(v, str):
                self.fail("%s.%s[%d]" % (where, key, i), "expected a string")
                continue
            out.append(v)
        return out


@dataclass
class Deadlock:
    """The principal's dissent from a clause, and what it costs the clause.

    Two parts and not one string. The counter-clause is what he holds instead;
    the attenuation is the authority the clause keeps, which is less than an
    answer both parties would reach independently and never enough for
    anything irreversible. Recording only the dissent leaves the grading to be
    remembered, and the grading is the whole use of a deadlock.
    """

    counter: str
    attenuation: str = ""

    @staticmethod
    def read(r: _Reader, data: Any, where: str) -> "Deadlock":
        d = r.obj(data, where)
        return Deadlock(
            counter=r.text(d, "counter", where),
            attenuation=r.text(d, "attenuation", where, required=False),
        )


@dataclass
class Term:
    """A term edge: thesis -> question, carrying verbatim anchors.

    A deadlock lives here and nowhere else. Dissent falls on the clause it is
    dissent from, so that it need not withhold the merge of the answer the
    clause sits in.
    """

    title: str
    to: str
    anchors: List[str] = field(default_factory=list)
    deadlock: Optional[Deadlock] = None

    @staticmethod
    def read(r: _Reader, data: Any, where: str) -> "Term":
        d = r.obj(data, where)
        raw = d.get("deadlock")
        if raw is None:
            deadlock = None
        elif isinstance(raw, dict):
            deadlock = Deadlock.read(r, raw, where + ".deadlock")
        else:
            r.fail(where + ".deadlock", "expected an object or null")
            deadlock = None
        return Term(
            title=r.text(d, "title", where),
            to=r.text(d, "to", where),
            anchors=r.strings(d, "anchors", where),
            deadlock=deadlock,
        )


@dataclass
class Mention:
    """A cross-reference: a clause points at a question it does not raise.

    The same shape as a term and deliberately not one. A clause that leans on
    a question already asked elsewhere should take the reader there, but it did
    not raise that question and must not become its parent — which is how a
    graph acquires cycles. It carries no deadlock, because there is no
    agreement on a pointer to dissent from.
    """

    title: str
    to: str
    anchors: List[str] = field(default_factory=list)

    @staticmethod
    def read(r: _Reader, data: Any, where: str) -> "Mention":
        d = r.obj(data, where)
        return Mention(
            title=r.text(d, "title", where),
            to=r.text(d, "to", where),
            anchors=r.strings(d, "anchors", where),
        )


@dataclass
class Borrowing:
    """Where a definition takes its sense from: definition -> a tradition.

    A ``TraditionEdge`` without the relation, because there is nothing for a
    borrowed sense to diverge from: a definition that departed from the sense
    it cites would not be citing it. It is an edge and not the free text it
    used to be so that the renderer can make the chip the layout asks for, and
    so that ``tradition-target`` catches a borrowing from a tradition the
    graph does not hold.
    """

    to: str
    note: str = ""

    @staticmethod
    def read(r: _Reader, data: Any, where: str) -> "Borrowing":
        d = r.obj(data, where)
        return Borrowing(
            to=r.text(d, "to", where),
            note=r.text(d, "note", where, required=False),
        )


@dataclass
class Definition:
    """A word of a thesis fixed in place; it opens no descendant question."""

    word: str
    body: str
    tradition: Optional[Borrowing] = None
    #: The question this word has earned, where the definition shadows it: the
    #: sense in a sentence for users of the word that cannot reach the question
    #: over their ancestors, and a pointer to where the argument is.
    question: str = ""

    @staticmethod
    def read(r: _Reader, data: Any, where: str) -> "Definition":
        d = r.obj(data, where)
        raw = d.get("tradition")
        if raw is None:
            tradition = None
        elif isinstance(raw, dict):
            tradition = Borrowing.read(r, raw, where + ".tradition")
        else:
            r.fail(where + ".tradition", "expected an object or null")
            tradition = None
        return Definition(
            word=r.text(d, "word", where),
            body=r.text(d, "body", where),
            tradition=tradition,
            question=r.text(d, "question", where, required=False),
        )


@dataclass
class TraditionEdge:
    """A tradition edge: thesis -> a question whose party is someone else.

    This is the canon between two parties, and it is encoded as canon is.
    Support is assent; divergence is deadlock, so a divergence carries the
    counter-clause a deadlock carries. It carries no attenuation, because a
    tradition licenses no action here and there is no authority to grade.

    It is not THE canon of the repository, which is the agreement between the
    principal and the AI over the questions in his own lineage.
    """

    to: str
    relation: str
    note: str = ""
    counter: str = ""

    @staticmethod
    def read(r: _Reader, data: Any, where: str) -> "TraditionEdge":
        d = r.obj(data, where)
        return TraditionEdge(
            to=r.text(d, "to", where),
            relation=r.text(d, "relation", where),
            note=r.text(d, "note", where, required=False),
            counter=r.text(d, "counter", where, required=False),
        )


@dataclass
class Application:
    """An artifact outside the graph that a thesis reaches."""

    name: str
    what: str
    link: str = ""
    standing: str = ""
    note: str = ""

    @staticmethod
    def read(r: _Reader, data: Any, where: str) -> "Application":
        d = r.obj(data, where)
        return Application(
            name=r.text(d, "name", where),
            what=r.text(d, "what", where),
            link=r.text(d, "link", where, required=False),
            standing=r.text(d, "standing", where),
            note=r.text(d, "note", where, required=False),
        )


@dataclass
class Thesis:
    """An articulated answer to exactly one question."""

    title: str
    text: str
    assent: str = ""
    standing: str = ""
    terms: List[Term] = field(default_factory=list)
    mentions: List[Mention] = field(default_factory=list)
    definitions: List[Definition] = field(default_factory=list)
    traditions: List[TraditionEdge] = field(default_factory=list)
    applications: List[Application] = field(default_factory=list)

    @staticmethod
    def read(r: _Reader, data: Any, where: str) -> "Thesis":
        d = r.obj(data, where)
        return Thesis(
            title=r.text(d, "title", where),
            text=r.text(d, "text", where),
            assent=r.text(d, "assent", where, required=False),
            standing=r.text(d, "standing", where, required=False),
            terms=[Term.read(r, v, "%s.terms[%d]" % (where, i))
                   for i, v in enumerate(r.seq(d, "terms", where))],
            mentions=[Mention.read(r, v, "%s.mentions[%d]" % (where, i))
                      for i, v in enumerate(r.seq(d, "mentions", where))],
            definitions=[Definition.read(r, v, "%s.definitions[%d]" % (where, i))
                         for i, v in enumerate(r.seq(d, "definitions", where))],
            traditions=[TraditionEdge.read(r, v, "%s.traditions[%d]" % (where, i))
                        for i, v in enumerate(r.seq(d, "traditions", where))],
            applications=[Application.read(r, v, "%s.applications[%d]" % (where, i))
                          for i, v in enumerate(r.seq(d, "applications", where))],
        )


@dataclass
class InboxItem:
    """A human action a question requires before it can be asked.

    ``id`` is what a question's ``requires`` names, and ``title`` is what a
    reader is shown. They are separate because they change for different
    reasons: the title is a summary and may be reworded at any time, while the
    id is a handle and may not. Naming items by title is what let a rename
    strand twenty-four requires entries pointing at nothing.
    """

    id: str
    title: str
    kind: str
    what: str
    obligation: str = ""
    done: bool = False

    @staticmethod
    def read(r: _Reader, data: Any, where: str) -> "InboxItem":
        d = r.obj(data, where)
        return InboxItem(
            id=r.text(d, "id", where),
            title=r.text(d, "title", where),
            kind=r.text(d, "kind", where),
            what=r.text(d, "what", where),
            obligation=r.text(d, "obligation", where, required=False),
            done=r.flag(d, "done", where),
        )


@dataclass
class Note:
    """Something a human wrote on a tab for their own use.

    The renderer replaces a whole tab body, so anything on the page the model
    does not hold is destroyed the next time the tab is written. A note is how
    the model holds it: attached to a section, rendered as a blockquote, and
    carried back out on the next export.
    """

    section: str
    body: str

    @staticmethod
    def read(r: _Reader, data: Any, where: str) -> "Note":
        d = r.obj(data, where)
        return Note(
            section=r.text(d, "section", where),
            body=r.text(d, "body", where),
        )


@dataclass
class Hinge:
    """What the asking presupposes, and what the answer was drawn from."""

    question: str = ""
    thesis: str = ""

    def empty(self) -> bool:
        return not (self.question.strip() or self.thesis.strip())

    @staticmethod
    def read(r: _Reader, data: Any, where: str) -> "Hinge":
        d = r.obj(data, where)
        return Hinge(
            question=r.text(d, "question", where, required=False),
            thesis=r.text(d, "thesis", where, required=False),
        )


@dataclass
class Question:
    """The unit of address; one document tab each."""

    id: str
    tab: str
    body: str
    question: str
    state: str
    kind: str
    pressure: int
    requires: List[str] = field(default_factory=list)
    party: str = AUTHOR
    standing: str = ""
    answerer: str = ""
    theses: List[Thesis] = field(default_factory=list)
    inbox: List[InboxItem] = field(default_factory=list)
    notes: List[Note] = field(default_factory=list)
    hinge: Optional[Hinge] = None

    @property
    def tradition(self) -> bool:
        """Whether this question is a root of its own lineage.

        Derived and not stored: a question belongs to a party, and a question
        whose party is not the author is that party's, joined to this graph by
        tradition edges rather than by a term edge.
        """
        return self.party != AUTHOR

    def terms(self) -> Iterator[Term]:
        for t in self.theses:
            for term in t.terms:
                yield term

    def mentions(self) -> Iterator[Mention]:
        """Every cross-reference on this question. Never a graph edge."""
        for t in self.theses:
            for m in t.mentions:
                yield m

    def definitions(self) -> Iterator[Tuple[Thesis, Definition]]:
        for t in self.theses:
            for d in t.definitions:
                yield t, d

    def applications(self) -> Iterator[Tuple[Thesis, Application]]:
        """Every application on this question, with the thesis it derives from."""
        for t in self.theses:
            for a in t.applications:
                yield t, a

    @staticmethod
    def read(r: _Reader, data: Any, where: str) -> "Question":
        d = r.obj(data, where)
        qid = r.text(d, "id", where)
        here = "%s (%s)" % (where, qid) if qid else where
        hinge = Hinge.read(r, d["hinge"], here + ".hinge") if isinstance(d.get("hinge"), dict) else None
        if "hinge" in d and d["hinge"] is not None and not isinstance(d["hinge"], dict):
            r.fail(here + ".hinge", "expected an object or null")
        return Question(
            id=qid,
            tab=r.text(d, "tab", here),
            body=r.text(d, "body", here),
            question=r.text(d, "question", here),
            state=r.text(d, "state", here),
            kind=r.text(d, "kind", here),
            pressure=r.number(d, "pressure", here),
            requires=r.strings(d, "requires", here),
            party=r.text(d, "party", here, required=False, default=AUTHOR) or AUTHOR,
            standing=r.text(d, "standing", here, required=False),
            answerer=r.text(d, "answerer", here, required=False),
            theses=[Thesis.read(r, v, "%s.theses[%d]" % (here, i))
                    for i, v in enumerate(r.seq(d, "theses", here))],
            inbox=[InboxItem.read(r, v, "%s.inbox[%d]" % (here, i))
                   for i, v in enumerate(r.seq(d, "inbox", here))],
            notes=[Note.read(r, v, "%s.notes[%d]" % (here, i))
                   for i, v in enumerate(r.seq(d, "notes", here))],
            hinge=hinge,
        )


@dataclass
class Graph:
    """The graph file: the artifact it caches, its mode, and its questions.

    The mode says what the file is: a ``notebook`` holds as many theses as the
    principal is entertaining, a ``canon`` at most one settled answer per
    question. It is absent from a notebook, which is the default.
    """

    artifact: str
    mode: str = NOTEBOOK
    state_enum: Optional[str] = None
    questions: List[Question] = field(default_factory=list)
    path: Optional[str] = None

    # -- lookups -------------------------------------------------------
    def by_id(self) -> Dict[str, Question]:
        return {q.id: q for q in self.questions}

    def get(self, qid: str) -> Optional[Question]:
        for q in self.questions:
            if q.id == qid:
                return q
        return None

    def term_edges(self) -> List[Tuple[Question, Term]]:
        """Every term edge, in file order: (source question, term)."""
        return [(q, term) for q in self.questions for term in q.terms()]

    def incoming(self, qid: str) -> List[Tuple[Question, Term]]:
        """The term edges that lead to ``qid``, in file order."""
        return [(src, term) for src, term in self.term_edges() if term.to == qid]

    def tradition_ids(self) -> List[str]:
        return [q.id for q in self.questions if q.tradition]

    @staticmethod
    def read(r: _Reader, data: Any, where: str = "graph") -> "Graph":
        d = r.obj(data, where)
        return Graph(
            artifact=r.text(d, "artifact", where, required=False),
            mode=r.text(d, "mode", where, required=False, default=NOTEBOOK) or NOTEBOOK,
            state_enum=r.opt_text(d, "state_enum", where),
            questions=[Question.read(r, v, "questions[%d]" % i)
                       for i, v in enumerate(r.seq(d, "questions", where))],
        )


def load(path: str) -> Graph:
    """Load a graph file. Raises ShapeError with every shape problem found.

    A file that cannot be opened is a shape problem like any other, so that
    every tool reports it the way it reports the rest rather than by traceback.
    """
    try:
        handle = open(path, "r", encoding="utf-8")
    except OSError as exc:
        raise ShapeError(["%s: cannot be read (%s)" % (path, exc.strerror or exc)])
    with handle as fh:
        try:
            data = json.load(fh)
        except ValueError as exc:
            raise ShapeError(["%s: not valid JSON (%s)" % (path, exc)])
    r = _Reader()
    graph = Graph.read(r, data)
    graph.path = path
    if r.problems:
        raise ShapeError(r.problems)
    return graph
