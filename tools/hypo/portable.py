"""Part the notebook from its document, so another party can raise its own.

A share of the live document is a share of *this* notebook. A party who wants
one of their own is handed the notebook instead: the questions, their theses,
their edges — everything the graph file holds that is not a name for *this*
document. Four values are such names: the
``artifact`` the file caches, the ``state_enum`` the tabs' state field points at,
and each question's ``tab`` and ``body`` ids — and one more wears content's
clothes, the link of an application whose link is this document
(``self_links``). Sealing empties them; the receiving party's own document
supplies them again, which is what ``STEPS`` says how to do.

Nothing else travels, because nothing else has to. The tab tree is not carried:
``project`` derives it from the term edges, so the receiving document lays out
the same tree from the same graph, and carrying it would only be a second home
for a datum that already has one. It is recorded under ``expect`` instead — not
as input to the rebuild but as the shape the rebuild has to come out to, so the
party who runs it can tell that it did.

What the envelope is *for* is a party who is not here, and so a copy of it
outlives the tooling that sealed it: it is read whenever they get to it, which
may be after a key has changed meaning. `FORMAT` says which shape a file is in
and `READS` which shapes can still be opened, with one step in `FORWARD` per
older format. An old envelope is read forward rather than turned away, because
turning it away leaves its holder with a notebook and no way to raise it, and
read forward in the open rather than quietly, because what comes out is then
not the shape the file says it is.

The questions are sealed by id, not in the order the document's tray happens to
hold the tabs: that order is a projection too, recomputed whenever a sibling is
inserted or a group of tabs grows past ten, so the same notebook sealed twice
came out in two orders. And the envelope carries a ``digest`` of its
questions, which is how a party says which notebook they received: the same
questions seal to the same digest wherever they are sealed. The name and the
file's name carry no version; the format has one, and the digest is what says
which state of the notebook this is.
"""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Dict, Iterator, List, Tuple

from . import model, project

#: The envelope's format, so a reader can tell what it is holding. The version
#: moves when a key changes meaning, not when the notebook does.
FORMAT = "hypomnemata-export/2"

#: The formats this tooling opens. An envelope is handed over once and read
#: whenever the receiving party gets to it, so the version that was current at
#: sealing has to stay readable: what moving the version buys is a reader that
#: knows which shape it is holding, not one that turns the older shape away. A
#: format listed here that is not `FORMAT` needs a step in `FORWARD` saying how
#: to read it.
READS = ("hypomnemata-export/1", FORMAT)

#: What names this document and must not travel: on the graph, and on each
#: question. Emptied rather than dropped, because the model requires the keys
#: and an empty id reads as what it is — unbound, and waiting to be bound.
GRAPH_KEYS = ("artifact", "state_enum")
QUESTION_KEYS = ("tab", "body")

#: How much of the digest is kept. It has to be said and typed — in a message —
#: so it is short, and the notebooks that could collide
#: on sixteen hex digits do not exist.
DIGEST = 16

#: How to raise the notebook again in a document that does not have it. Carried
#: inside the envelope: the party who receives the file receives the procedure
#: with it, rather than having to be told separately.
STEPS = [
    "Get the tooling named under `tools`, and the dictation skill beside it."
    " Every step below that runs a tool runs one of those, and the skill says"
    " how each is driven. None is optional, and no tab is ever hand-written:"
    " the renderer is the only sanctioned producer of a tab body.",
    "Create a document for the notebook.",
    "Create an enum whose options are exactly `states`, in that order, and"
    " nothing else. A document enum only grows — an option can be appended,"
    " never renamed, reordered or removed — so it has to be right the first"
    " time.",
    "`portable.py open <this file> -o graph.json` writes the graph back out"
    " with `artifact`, `state_enum`, and every `tab` and `body` empty.",
    "Set `artifact` to the new document's artifact URL and `state_enum` to the"
    " id of the enum just created. Each application named under `rebind` is an"
    " application whose link was the old document — the notebook is an"
    " application of some of its own theses. Point each one's `link` at the new"
    " document; one left empty is owed a link, and no check will say so.",
    "Create one tab per question, each named by that question's `id`, and"
    " record the tab's id in its question's `tab` and the tab's body block id"
    " in its `body`. A tab whose ids are still empty is not yet bound.",
    "`check.py graph.json` must report no ERROR before anything is written."
    " Until the tabs are bound it reports `unique-ids` on the empty `tab`"
    " and `body` ids, which is the check saying what is still missing:"
    " binding them is what clears it.",
    "Write each tab with `apply.py`, which needs `--outlines DIR` holding one"
    " `<question id>.xml` outline per tab as the document prints it: `--body`"
    " first, which replaces the tab with the rendered body and mints the block"
    " ids, then — the outline re-read, since those ids are new — `--links`,"
    " which needs them; `--wanted` lists the outlines the links call needs."
    " Writing several tabs, send every body before any links. Never hand-write"
    " a tab.",
    "`project.py graph.json` prints the tab-placement patch — send it as the"
    " document's `tabs` patch — and, with `--json`, the tree it derived, whose"
    " entries must match `expect.tree` on `question`, `parent` and `order`"
    " (they carry `distance` and `load` besides).",
    "`verify.py graph.json <exported tabs dir>` reads the pages back. It is the"
    " closing gate: a graph file never held a link, so nothing else can see"
    " whether the links reached the page.",
]


def _data(graph: model.Graph) -> Dict[str, Any]:
    """The graph file as it sits on disk."""
    if not graph.path:
        raise ValueError("the graph was not loaded from a file")
    with open(graph.path, encoding="utf-8") as fh:
        return json.load(fh)


def _self_linked(data: Dict[str, Any]) -> Iterator[Tuple[dict, dict, dict]]:
    """``(question, thesis, application)`` per application whose link is the
    document being sealed — the one place that decides what a self-link is,
    so that what ``seal`` empties is exactly what ``self_links`` reports."""
    artifact = data.get("artifact") or ""
    if not artifact:
        return
    for q in data.get("questions", []):
        for t in q.get("theses", []):
            for a in t.get("applications", []):
                if artifact in (a.get("link") or ""):
                    yield q, t, a


def self_links(data: Dict[str, Any]) -> List[Dict[str, str]]:
    """Every application whose link is the document being sealed.

    The notebook is an application of some of its own theses, and an
    application's link is the artifact it names — so where that artifact is
    this document, the link is a binding like any other, wearing content's
    clothes. It cannot travel: it would tell the receiving party that their
    notebook is this one. Sealing empties it and records where it stood, since
    the application itself is content and stays, owed a link to a document that
    does not exist yet.
    """
    return [{"question": q.get("id", "?"),
             "thesis": t.get("title", ""),
             "application": a.get("name", "?")}
            for q, t, a in _self_linked(data)]


def bindings(data: Dict[str, Any]) -> List[str]:
    """Every document-local value the file carries, as `where=value` lines.

    What sealing is about to drop, named so that dropping it can be seen.
    """
    found = []
    for key in GRAPH_KEYS:
        if data.get(key):
            found.append("%s=%s" % (key, data[key]))
    for q in data.get("questions", []):
        for key in QUESTION_KEYS:
            if q.get(key):
                found.append("%s.%s=%s" % (q.get("id", "?"), key, q[key]))
    for at in self_links(data):
        found.append("%s/%s/%s.link=the document itself"
                     % (at["question"], at["thesis"], at["application"]))
    return found


def tree(graph: model.Graph) -> List[Dict[str, Any]]:
    """The projected tree, in walk order: what a rebuild must come out to."""
    return [{key: row[key] for key in ("question", "parent", "order")}
            for row in project.tree_rows(graph)]


def digest(questions: List[Dict[str, Any]]) -> str:
    """The questions' fingerprint: what a party quotes to say which notebook
    they hold. It is of the questions alone — not the name, the tools or the
    steps, which are about the file rather than the notebook — and of their
    content in one canonical spelling, so two envelopes sealed from the same
    questions agree on it wherever and whenever they were sealed."""
    text = json.dumps(sorted(questions, key=_by_id), sort_keys=True,
                      ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:DIGEST]


def _by_id(q: Dict[str, Any]) -> str:
    return str(q.get("id", ""))


def seal(graph: model.Graph, name: str = "", tools: str = "") -> Dict[str, Any]:
    """The envelope: the notebook, with nothing in it that names a document."""
    data = copy.deepcopy(_data(graph))
    questions = sorted(data.get("questions", []), key=_by_id)
    for q in questions:
        for key in QUESTION_KEYS:
            q[key] = ""
    rebind = self_links(data)
    for _, _, a in _self_linked(data):
        a["link"] = ""
    return {
        "format": FORMAT,
        "name": name,
        "tools": tools,
        "mode": data.get("mode", model.NOTEBOOK),
        "states": list(model.STATES),
        "digest": digest(questions),
        "questions": questions,
        "rebind": rebind,
        "expect": {"questions": len(questions), "tree": tree(graph)},
        "rebuild": STEPS,
    }


def _glossary_to_question(questions: List[Dict[str, Any]]) -> str:
    """`hypomnemata-export/1`: the glossary hung off an answer, not its question.

    One sense per word left nothing for an answer to own, and a word a hinge
    brought in belongs to no answer at all, so the glossary moved up to the
    question. An envelope sealed before that carries each word under the answer
    that used it, in the order a reader already filed them, so the words come
    up in that order and land on the question whose answer held them.

    It is done here because here is the only place that knows the envelope is
    an old one. The model refuses a `definitions` key on a thesis outright —
    deliberately, so that an old *graph file* cannot lose its glossary in
    silence — which means nothing downstream of this can do the move instead:
    the receiving party would get a graph the checker faults once per question,
    on a key their envelope never said was wrong.
    """
    moved = 0
    for q in questions:
        carried: List[Any] = []
        for t in q.get("theses", []):
            carried.extend(t.pop("definitions", []))
        if carried:
            q["definitions"] = list(q.get("definitions", [])) + carried
            moved += len(carried)
    if not moved:
        return ""
    return ("hypomnemata-export/1: %d definition(s) move from their answer to "
            "their question" % moved)


#: How to read each format older than `FORMAT`: one step per format, run over
#: the questions as they come out of the envelope. A step says what it moved,
#: in a line, because reading an old envelope produces a graph in a shape that
#: envelope does not have, and that is a thing to be told rather than to notice.
FORWARD = {"hypomnemata-export/1": _glossary_to_question}


def opened(envelope: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """`(the graph file again, what reading an older format moved)`.

    The inverse of `seal` up to the binding it dropped, which is the point —
    what comes out is the same notebook, waiting for a document to name it —
    and up to whatever `FORWARD` had to do to read the shape it was sealed in.
    """
    found = envelope.get("format")
    if found not in READS:
        raise ValueError("not a %s envelope (found %r)" % (FORMAT, found))
    questions = copy.deepcopy(envelope.get("questions", []))
    if not isinstance(questions, list) or not all(isinstance(q, dict)
                                                  for q in questions):
        raise ValueError("an envelope's `questions` is a list of question "
                         "objects")
    notes: List[str] = []
    if found != FORMAT:
        said = FORWARD[found](questions)
        if said:
            notes.append(said)
    for q in questions:
        for key in QUESTION_KEYS:
            q[key] = ""
    return {
        "artifact": "",
        "mode": envelope.get("mode", model.NOTEBOOK),
        "state_enum": None,
        "questions": questions,
    }, notes


def dump(envelope: Dict[str, Any]) -> str:
    """The envelope as it is written: one JSON file, newline-terminated."""
    return json.dumps(envelope, indent=2, ensure_ascii=False) + "\n"
