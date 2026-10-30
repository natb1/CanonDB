"""The works every party is read from, as one registry a repository reads.

A repository's prose cites works by bracketed keys, and its check needs to
know which keys stand for a work. It used to keep a registry of its own for
that, which gave each key a second home, and the notebook — where the
parties that are read from those works stand — could not see it. The keys
are defined on the parties' tabs now (``model.Work``), and a repository's
check reads this file in place of a registry of its own.

It is a projection, like the frontier and the drift count: computed from the
graph whenever it is wanted, never committed by the notebook's tooling, and
never edited. The notebook is its source, so a work is added or set aside on
its party's tab and the file is exported again; an edit to the file is lost
at the next export, and should be.
"""

from __future__ import annotations

from typing import Any, Dict

from .model import Graph, Work

#: the fields a source carries besides its party, each where it is filled,
#: under the names a repository's check reads
FIELDS = Work.FIELDS + ("note",)


class Doubled(ValueError):
    """A key two works carry: the registry would hold one of them, and which
    is the order the tabs happened to be read in. ``work-key-unique``
    reports it on the graph; this refuses it on the way out."""


def export(graph: Graph) -> Dict[str, Any]:
    """``{"sources": {KEY: {"party": <question id>, <field>: ...}}}``, the
    keys sorted and each source's fields only where filled.

    The party is the question whose tab lists the work, so a repository's
    check can say where a key is defined and a reader can go there.
    """
    sources: Dict[str, Dict[str, str]] = {}
    for q in graph.questions:
        for work in q.works:
            if work.key in sources:
                raise Doubled("the key %s is defined on %s and again on %s"
                              % (work.key, sources[work.key]["party"], q.id))
            source = {"party": q.id}
            source.update((name, getattr(work, name)) for name in FIELDS
                          if getattr(work, name))
            sources[work.key] = source
    return {"sources": {key: sources[key] for key in sorted(sources)}}
