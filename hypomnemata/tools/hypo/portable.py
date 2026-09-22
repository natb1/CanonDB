"""Part the notebook from its document, so another party can raise its own.

A live document cannot be handed to anyone. What can be handed over is the
notebook: the questions, their theses, their edges — everything the graph file
holds that is not a name for *this* document. Four values are such names, and
this is the whole of the coupling: the ``artifact`` the file caches, the
``state_enum`` the tabs' state field points at, and each question's ``tab`` and
``body`` ids. Sealing empties them; the receiving party's own document supplies
them again, which is what ``STEPS`` says how to do.

Nothing else travels, because nothing else has to. The tab tree is not carried:
``project`` derives it from the term edges, so the receiving document lays out
the same tree from the same graph, and carrying it would only be a second home
for a datum that already has one. It is recorded under ``expect`` instead — not
as input to the rebuild but as the shape the rebuild has to come out to, so the
party who runs it can tell that it did.
"""

from __future__ import annotations

import copy
import json
from typing import Any, Dict, List

from . import model, project

#: The envelope's format, so a reader can tell what it is holding. The version
#: moves when a key changes meaning, not when the notebook does.
FORMAT = "hypomnemata-export/1"

#: What names this document and must not travel: on the graph, and on each
#: question. Emptied rather than dropped, because the model requires the keys
#: and an empty id reads as what it is — unbound, and waiting to be bound.
GRAPH_KEYS = ("artifact", "state_enum")
QUESTION_KEYS = ("tab", "body")

#: How to raise the notebook again in a document that does not have it. Carried
#: inside the envelope: the party who receives the file receives the procedure
#: with it, rather than having to be told separately.
STEPS = [
    "Create a document for the notebook.",
    "Create an enum whose options are exactly `states`, in that order, and"
    " nothing else. A document enum only grows — an option can be appended,"
    " never renamed, reordered or removed — so it has to be right the first"
    " time.",
    "`portable.py open <this file> -o graph.json` writes the graph back out"
    " with `artifact`, `state_enum`, and every `tab` and `body` empty.",
    "Set `artifact` to the new document's artifact URL and `state_enum` to the"
    " id of the enum just created.",
    "Create one tab per question, each named by that question's `id`, and"
    " record the tab's id in its question's `tab` and the tab's body block id"
    " in its `body`. A tab whose ids are still empty is not yet bound.",
    "`check.py graph.json` must report no ERROR before anything is written."
    " Until the tabs are bound it reports `unique-ids` on the empty `tab`"
    " and `body` ids, which is the check saying what is still missing:"
    " binding them is what clears it.",
    "Write each tab with `render.py` and `apply.py`: the body first, which"
    " mints the block ids, then the links, which need those ids. Writing"
    " several tabs, send every body before any links. Never hand-write a tab.",
    "`project.py graph.json` prints the tab-placement patch; send it as the"
    " document's `tabs` patch. The tree it prints must match `expect.tree`.",
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
    return found


def tree(graph: model.Graph) -> List[Dict[str, Any]]:
    """The projected tree, in walk order: what a rebuild must come out to."""
    parents = project.parents(graph)
    orders = project.orders(graph)
    return [{"question": qid,
             "parent": parents.get(qid),
             "order": orders.get(qid)}
            for qid in project.walk(graph)]


def seal(graph: model.Graph, name: str = "") -> Dict[str, Any]:
    """The envelope: the notebook, with nothing in it that names a document."""
    data = copy.deepcopy(_data(graph))
    questions = data.get("questions", [])
    for q in questions:
        for key in QUESTION_KEYS:
            q[key] = ""
    return {
        "format": FORMAT,
        "name": name,
        "mode": data.get("mode", model.NOTEBOOK),
        "states": list(model.STATES),
        "questions": questions,
        "expect": {"questions": len(questions), "tree": tree(graph)},
        "rebuild": STEPS,
    }


def unseal(envelope: Dict[str, Any]) -> Dict[str, Any]:
    """The graph file again, unbound: every document-local value empty.

    The inverse of `seal` up to the binding it dropped, which is the point —
    what comes out is the same notebook, waiting for a document to name it.
    """
    if envelope.get("format") != FORMAT:
        raise ValueError("not a %s envelope (found %r)"
                         % (FORMAT, envelope.get("format")))
    questions = copy.deepcopy(envelope.get("questions", []))
    for q in questions:
        for key in QUESTION_KEYS:
            q[key] = ""
    return {
        "artifact": "",
        "mode": envelope.get("mode", model.NOTEBOOK),
        "state_enum": None,
        "questions": questions,
    }
