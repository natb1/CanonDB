"""Dataclasses for the graph file, and validation of its shape.

Shape validation is separate from the checks in ``spec``: it establishes that the
JSON can be loaded into the model at all (required keys, types), so that every
check may then assume a well-shaped graph and report on its *content*.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional, Tuple

STATES = ("held", "in line", "landed", "revised", "deadlocked")
KINDS = ("definitional", "case", "consistency", "root")
STANDINGS = ("derived", "postulate")
RELATIONS = ("support", "divergence")
INBOX_KINDS = ("promulgate", "provide", "dispose", "build")

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
class Term:
    """A term edge: thesis -> question, carrying verbatim anchors."""

    title: str
    to: str
    anchors: List[str] = field(default_factory=list)
    deadlock: Optional[str] = None

    @staticmethod
    def read(r: _Reader, data: Any, where: str) -> "Term":
        d = r.obj(data, where)
        return Term(
            title=r.text(d, "title", where),
            to=r.text(d, "to", where),
            anchors=r.strings(d, "anchors", where),
            deadlock=r.opt_text(d, "deadlock", where),
        )


@dataclass
class Definition:
    """A word of a thesis fixed in place; it opens no descendant question."""

    word: str
    body: str
    tradition: Optional[str] = None

    @staticmethod
    def read(r: _Reader, data: Any, where: str) -> "Definition":
        d = r.obj(data, where)
        return Definition(
            word=r.text(d, "word", where),
            body=r.text(d, "body", where),
            tradition=r.opt_text(d, "tradition", where),
        )


@dataclass
class TraditionEdge:
    """A tradition edge: thesis -> a tradition question."""

    to: str
    relation: str
    note: str = ""

    @staticmethod
    def read(r: _Reader, data: Any, where: str) -> "TraditionEdge":
        d = r.obj(data, where)
        return TraditionEdge(
            to=r.text(d, "to", where),
            relation=r.text(d, "relation", where),
            note=r.text(d, "note", where, required=False),
        )


@dataclass
class Thesis:
    """An articulated answer to exactly one question."""

    title: str
    text: str
    assent: str = ""
    deadlock: Optional[str] = None
    terms: List[Term] = field(default_factory=list)
    definitions: List[Definition] = field(default_factory=list)
    traditions: List[TraditionEdge] = field(default_factory=list)

    @staticmethod
    def read(r: _Reader, data: Any, where: str) -> "Thesis":
        d = r.obj(data, where)
        return Thesis(
            title=r.text(d, "title", where),
            text=r.text(d, "text", where),
            assent=r.text(d, "assent", where, required=False),
            deadlock=r.opt_text(d, "deadlock", where),
            terms=[Term.read(r, v, "%s.terms[%d]" % (where, i))
                   for i, v in enumerate(r.seq(d, "terms", where))],
            definitions=[Definition.read(r, v, "%s.definitions[%d]" % (where, i))
                         for i, v in enumerate(r.seq(d, "definitions", where))],
            traditions=[TraditionEdge.read(r, v, "%s.traditions[%d]" % (where, i))
                        for i, v in enumerate(r.seq(d, "traditions", where))],
        )


@dataclass
class InboxItem:
    """A human action a question requires before it can be asked."""

    title: str
    kind: str
    what: str
    obligation: str = ""
    done: bool = False

    @staticmethod
    def read(r: _Reader, data: Any, where: str) -> "InboxItem":
        d = r.obj(data, where)
        return InboxItem(
            title=r.text(d, "title", where),
            kind=r.text(d, "kind", where),
            what=r.text(d, "what", where),
            obligation=r.text(d, "obligation", where, required=False),
            done=r.flag(d, "done", where),
        )


@dataclass
class Application:
    """An artifact outside the graph that a thesis reaches."""

    name: str
    what: str
    link: str = ""
    standing: str = ""

    @staticmethod
    def read(r: _Reader, data: Any, where: str) -> "Application":
        d = r.obj(data, where)
        return Application(
            name=r.text(d, "name", where),
            what=r.text(d, "what", where),
            link=r.text(d, "link", where, required=False),
            standing=r.text(d, "standing", where),
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
    priority: int
    requires: List[str] = field(default_factory=list)
    tradition: bool = False
    theses: List[Thesis] = field(default_factory=list)
    inbox: List[InboxItem] = field(default_factory=list)
    applications: List[Application] = field(default_factory=list)
    hinge: Optional[Hinge] = None

    def terms(self) -> Iterator[Term]:
        for t in self.theses:
            for term in t.terms:
                yield term

    def definitions(self) -> Iterator[Tuple[Thesis, Definition]]:
        for t in self.theses:
            for d in t.definitions:
                yield t, d

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
            priority=r.number(d, "priority", here),
            requires=r.strings(d, "requires", here),
            tradition=r.flag(d, "tradition", here),
            theses=[Thesis.read(r, v, "%s.theses[%d]" % (here, i))
                    for i, v in enumerate(r.seq(d, "theses", here))],
            inbox=[InboxItem.read(r, v, "%s.inbox[%d]" % (here, i))
                   for i, v in enumerate(r.seq(d, "inbox", here))],
            applications=[Application.read(r, v, "%s.applications[%d]" % (here, i))
                          for i, v in enumerate(r.seq(d, "applications", here))],
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
            questions=[Question.read(r, v, "questions[%d]" % i)
                       for i, v in enumerate(r.seq(d, "questions", where))],
        )


def load(path: str) -> Graph:
    """Load a graph file. Raises ShapeError with every shape problem found."""
    with open(path, "r", encoding="utf-8") as fh:
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
