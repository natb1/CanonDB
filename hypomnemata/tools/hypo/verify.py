"""The page against the renderer: what reached the document, not what was sent.

Every other check reads the graph file. This one reads the exported page, which
is the only place two kinds of defect can show:

    text     a body that is not what the renderer would produce
    missing  a link the sidecar names that the page does not carry
    extra    a link the page carries that the sidecar does not name

The middle one is why this exists. An in-page link needs a block id, so it is
applied after the body write, and ``read.py`` strips it again before parsing —
by design, or a link on the assent line would take that line out of its own
grammar. So a rebuilt graph is identical whether the links were applied or not,
and every gate on the graph passes over a page that lost all of them. That is
what happened: 192 links across 24 tabs, with the rebuild green.

The third is the other half of the same blindness. A link applied by hand, or
one left behind by a definition that has since moved to another tab, is
invisible to everything else; ten of them had accumulated.

Counting, not presence: an anchor may stand twice on a tab and be linked once,
which a set comparison calls correct.
"""

from __future__ import annotations

import difflib
import re
from collections import Counter
from typing import Dict, List, NamedTuple

from . import read, render
from .model import Graph

#: emphasis off and case folded. A link may open inside an emphasis span, which
#: leaves the closing marker inside the captured text and the opener outside;
#: and a defined word is capitalised where it opens a sentence, so ``pressure``
#: is linked on the page as ``Pressure``.
_MARKERS = re.compile(r"[*_`]")

#: the question line's state: a chip in what the renderer writes, the word
#: itself in what the document exports.
_STATE = re.compile(r"^(question:)[^·]*·", re.M)


def bare(words: str) -> str:
    return _MARKERS.sub("", words or "").strip().lower()


class Report(NamedTuple):
    question: str
    diff: List[str]
    missing: List[str]
    extra: List[str]
    #: missing anchor -> the anchor whose link already covers those words
    covered: Dict[str, str] = {}

    def ok(self) -> bool:
        return not (self.diff or self.missing or self.extra)

    def lines(self) -> List[str]:
        out = ["=== %s" % self.question]
        out += ["   " + line for line in self.diff]
        for anchor in self.missing:
            under = self.covered.get(anchor)
            out.append("   MISSING LINK on %r%s"
                       % (anchor, " — covered by %r" % under[:48] if under else ""))
        for anchor in self.extra:
            out.append("   LINK NOT IN THE SIDECAR on %r" % anchor)
        return out


def normalise(markdown: str) -> List[str]:
    """A page or a rendered body as the lines the two can be compared on."""
    out = read.IN_PAGE_LINK.sub(r"\1", markdown or "")
    out = read.PLACED_CHIP.sub("", out)
    out = read.ESCAPE.sub(r"\1", out)
    out = _STATE.sub(r"\1 STATE ·", out)
    return [line.rstrip() for line in out.strip().splitlines() if line.strip()]


def applied(page: str) -> Counter:
    """The anchors the page carries an in-page link on, counted."""
    return Counter(bare(m.group(1)) for m in read.IN_PAGE_LINK.finditer(page or ""))


def verify(graph: Graph, qid: str, page: str) -> Report:
    """One tab's page against what the renderer and the sidecar say it holds."""
    diff = list(difflib.unified_diff(
        normalise(page), normalise(render.body(graph, qid)),
        "page", "render", lineterm="", n=0))[2:]
    entries = render.links(graph, qid)["links"]
    wanted = Counter(bare(entry["anchor"]) for entry in entries)
    have = applied(page)
    # a link the page cannot carry because another already covers those words
    covered = {bare(entry["anchor"]): entry["covered_by"]
               for entry in entries if entry.get("covered_by")}
    return Report(question=qid, diff=diff,
                  missing=sorted((wanted - have).elements()),
                  extra=sorted((have - wanted).elements()),
                  covered=covered)


def verify_all(graph: Graph, pages: Dict[str, str]) -> List[Report]:
    """Every question with a page on disk, in the graph's order."""
    return [verify(graph, q.id, pages[q.id])
            for q in graph.questions if q.id in pages]
