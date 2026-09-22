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

An envelope goes stale the moment the notebook moves, and a party holding a
stale one holds a notebook nobody has. So re-sealing is not a thing to
remember: ``reseal`` puts the current graph over the committed envelope, taking
its ``name`` and ``tools`` from the file it replaces, and ``drift`` says what
that changed in a few lines of ids rather than in the notebook's own words.
"""

from __future__ import annotations

import copy
import json
import os
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

#: How many ids a report names before it stops naming them and counts instead.
#: Re-sealing happens on every run, so what it prints is read on every run; a
#: report whose length follows the notebook's is a report that will be skimmed.
NAMED = 8

#: How to raise the notebook again in a document that does not have it. Carried
#: inside the envelope: the party who receives the file receives the procedure
#: with it, rather than having to be told separately.
STEPS = [
    "Get the tooling named under `tools`, and the dictation skill beside it."
    " Every step below is one of those tools. None is optional, and no tab is"
    " ever hand-written: the renderer is the only sanctioned producer of a tab"
    " body.",
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
    " document, or leave it empty and its standing will say it is owed.",
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
    artifact = data.get("artifact") or ""
    found: List[Dict[str, str]] = []
    if not artifact:
        return found
    for q in data.get("questions", []):
        for t in q.get("theses", []):
            for a in t.get("applications", []):
                if artifact in (a.get("link") or ""):
                    found.append({"question": q.get("id", "?"),
                                  "thesis": t.get("title", ""),
                                  "application": a.get("name", "?")})
    return found


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
    parents = project.parents(graph)
    orders = project.orders(graph)
    return [{"question": qid,
             "parent": parents.get(qid),
             "order": orders.get(qid)}
            for qid in project.walk(graph)]


def seal(graph: model.Graph, name: str = "", tools: str = "") -> Dict[str, Any]:
    """The envelope: the notebook, with nothing in it that names a document."""
    data = copy.deepcopy(_data(graph))
    questions = data.get("questions", [])
    for q in questions:
        for key in QUESTION_KEYS:
            q[key] = ""
    rebind = self_links(data)
    for q in questions:
        for t in q.get("theses", []):
            for a in t.get("applications", []):
                if (data.get("artifact") or "") and \
                        (data["artifact"] in (a.get("link") or "")):
                    a["link"] = ""
    return {
        "format": FORMAT,
        "name": name,
        "tools": tools,
        "mode": data.get("mode", model.NOTEBOOK),
        "states": list(model.STATES),
        "questions": questions,
        "rebind": rebind,
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


#: Where the committed envelope sits, from this file's own place: `hypo` is in
#: `tools`, `tools` in `hypomnemata`, and `hypomnemata` at the branch root.
def root() -> str:
    """The branch root, derived rather than configured."""
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(os.path.dirname(os.path.dirname(here)))


def committed(where: str) -> str:
    """The envelope committed at `where`, by its own `format`; "" if none is.

    The envelope is found rather than named. A path retyped on every run is a
    path that drifts, and the file already says what it is: the one JSON file
    at the branch root whose `format` is ours is the notebook that was handed
    over. A directory holding two of them is a question this cannot answer, so
    it takes the first in name order and says nothing clever about the second.
    """
    try:
        entries = sorted(os.listdir(where))
    except OSError:
        return ""
    for entry in entries:
        if not entry.endswith(".json"):
            continue
        path = os.path.join(where, entry)
        try:
            with open(path, encoding="utf-8") as fh:
                if json.load(fh).get("format") == FORMAT:
                    return path
        except (OSError, ValueError):
            continue
    return ""


def carried(previous: Dict[str, Any]) -> Dict[str, str]:
    """The `name` and `tools` a re-seal takes from the envelope it replaces.

    A re-seal is not a fresh naming. The notebook is the same notebook, and the
    name it went out under is the receiving party's handle for it — so both
    values keep one home, the envelope itself, rather than being retyped on
    every run and silently renaming the thing on the run someone typed it
    differently.
    """
    return {"name": previous.get("name", ""), "tools": previous.get("tools", "")}


def dump(envelope: Dict[str, Any]) -> str:
    """The envelope as it is written: one JSON file, newline-terminated."""
    return json.dumps(envelope, indent=2, ensure_ascii=False) + "\n"


def named(ids: List[str]) -> str:
    """`ids` as a phrase of bounded length: the first `NAMED`, then a count.

    The point of naming them at all is to say which part of the notebook moved,
    and a reader has that from a few. Naming all of them makes the report grow
    with the notebook, which is the one thing a report that prints every run
    must not do.
    """
    shown = sorted(ids)
    if len(shown) <= NAMED:
        return ", ".join(shown)
    return "%s and %d more" % (", ".join(shown[:NAMED]), len(shown) - NAMED)


def drift(previous: Dict[str, Any], current: Dict[str, Any]) -> List[str]:
    """What re-sealing would change — by id and by key, never by content.

    Staleness has to be reportable inside the turn that caused it, and the
    envelope is by far the largest file this tooling touches: printing the
    difference would put the notebook back into the context the tooling exists
    to keep it out of. So what is printed is the *shape* of the difference —
    which questions came, went or moved, and which header values no longer
    agree — and it is bounded twice over: never a value, and never more than
    `NAMED` ids of the ones that moved. It is at most nine short lines for a
    notebook of any size. Whoever wants the text has `git diff`.
    """
    lines: List[str] = []
    for key in ("format", "name", "tools", "mode", "states"):
        if previous.get(key) != current.get(key):
            lines.append("~ %s" % key)
    was = {q.get("id", "?"): q for q in previous.get("questions", [])}
    now = {q.get("id", "?"): q for q in current.get("questions", [])}
    for mark, ids in (("-", [q for q in was if q not in now]),
                      ("+", [q for q in now if q not in was]),
                      ("~", [q for q in now if q in was and now[q] != was[q]])):
        if ids:
            lines.append("%s %d question(s): %s" % (mark, len(ids), named(ids)))
    for key, gloss in (("rebind", "the applications owed a link"),
                       ("expect", "the shape a rebuild must come out to"),
                       ("rebuild", "the steps that ride inside")):
        if previous.get(key) != current.get(key):
            lines.append("~ %s (%s)" % (key, gloss))
    return lines


def compare(graph: model.Graph, path: str) -> tuple:
    """`(the envelope this graph would seal to, what that would change)`.

    Raises `ValueError` where `path` is not one of ours, so a stale-looking
    envelope and a file that was never an envelope are told apart.
    """
    with open(path, encoding="utf-8") as fh:
        previous = json.load(fh)
    if previous.get("format") != FORMAT:
        raise ValueError("not a %s envelope (found %r)"
                         % (FORMAT, previous.get("format")))
    current = seal(graph, **carried(previous))
    return current, drift(previous, current)


def dropped(graph: model.Graph, path: str) -> List[str]:
    """The questions the envelope holds that this graph does not.

    A re-seal that drops questions is a notebook shrinking, which a dictation
    may well intend and a partial read looks exactly like. It is the one drift
    that cannot be undone by re-reading, so it is the one the automatic path
    refuses and leaves to a deliberate one.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            previous = json.load(fh)
    except (OSError, ValueError):
        return []
    here = {q.id for q in graph.questions}
    return sorted(q.get("id", "?") for q in previous.get("questions", [])
                  if q.get("id", "?") not in here)


def reseal(graph: model.Graph, path: str) -> List[str]:
    """Seal `graph` over the envelope at `path`; return what moved.

    The file is written only when something moved, so a run that changed
    nothing leaves the envelope — and its diff — alone.
    """
    current, changed = compare(graph, path)
    if changed:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(dump(current))
    return changed
