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
which a set comparison calls correct. And by span rather than by label, since a
nested link cuts the outer one into pieces and no piece is the anchor.

What it does not check is where a link goes. An href names a block id, which
this cannot resolve without the outlines ``apply`` takes; so a clause whose own
link was skipped because a longer one already covers those words reads as
carried — which is what a reader meets — and the sidecar's ``covered_by`` is
what says whose destination it actually has.
"""

from __future__ import annotations

import difflib
import re
from collections import Counter
from typing import Dict, List, NamedTuple, Optional, Tuple

from . import read, render, text
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


def linked_spans(page: str) -> Tuple[str, List[Tuple[int, int]]]:
    """The page as plain characters, and which of them a link stands on.

    Compared by span rather than by label, because a link does not survive as
    one label: a nested link cuts it into pieces, and the page then reads

        [The ](#a)[merge](#b)[ is the human's assent and his only act](#a)

    where all three are right and none is the anchor. Matching labels would
    call the whole clause missing and the two halves unaccounted for.
    """
    out: List[str] = []
    spans: List[Tuple[int, int]] = []
    where = 0

    def take(raw: str, linked: bool) -> None:
        """One run of the page, and where it lands once the markup is off."""
        nonlocal where
        words = plainly(raw)
        if linked and words.strip():
            spans.append((where + len(words) - len(words.lstrip()),
                          where + len(words.rstrip())))
        out.append(words)
        where += len(words)

    at = 0
    for m in read.IN_PAGE_LINK.finditer(page or ""):
        take((page or "")[at:m.start()], False)
        take(m.group(1), True)
        at = m.end()
    take((page or "")[at:], False)
    return "".join(out), spans


def plainly(markdown: str) -> str:
    """Chips, escapes and emphasis off — the characters a reader sees.

    Run over one piece of the page at a time, so what is left is consistent
    with the offsets taken beside it. A link may open inside an emphasis span,
    which leaves a marker without its pair in one of the pieces; those come off
    too, or the offsets would count characters nobody sees.
    """
    out = read.ESCAPE.sub(r"\1", markdown or "")
    out = read.PLACED_CHIP.sub("", out)
    return _MARKERS.sub("", text.plain(out))


def account(graph: Graph, qid: str,
            page: str) -> Tuple[str, List[str], List[Tuple[int, int]]]:
    """The page as plain characters, what it does not carry, and what it
    carries that nothing asked for.

    The strays come back as spans rather than as their words, because taking
    one off has to name the run the mark stands on and two runs may read
    alike. ``verify`` reports the words, which is what a reader is shown;
    ``apply`` needs the position, which is what an operation takes.
    """
    entries = render.links(graph, qid)["links"]
    plain, spans = linked_spans(page)
    missing: List[str] = []
    accounted: List[Tuple[int, int]] = []
    for entry in entries:
        want = _where(plain, entry.get("find"))
        if want is None:
            missing.append(bare(entry["anchor"]))
            continue
        under = [span for span in spans
                 if span[0] < want[1] and want[0] < span[1]]
        if _whole(plain, want, under):
            accounted.extend(under)
        else:
            missing.append(bare(entry["anchor"]))
    extra = [span for span in spans if span not in accounted]
    return plain, sorted(missing), extra


def verify(graph: Graph, qid: str, page: str) -> Report:
    """One tab's page against what the renderer and the sidecar say it holds."""
    diff = list(difflib.unified_diff(
        normalise(page), normalise(render.body(graph, qid)),
        "page", "render", lineterm="", n=0))[2:]
    plain, missing, extra = account(graph, qid, page)
    # a link the page cannot carry because another already covers those words
    covered = {bare(entry["anchor"]): entry["covered_by"]
               for entry in render.links(graph, qid)["links"]
               if entry.get("covered_by")}
    return Report(question=qid, diff=diff, missing=missing,
                  extra=sorted(plain[start:end].strip().lower()
                               for start, end in extra),
                  covered=covered)


def _where(plain: str, find) -> Optional[Tuple[int, int]]:
    """Where on the page the run a link was meant for stands.

    Counted by the same rule that chose it, so that a disagreement between
    this and the page is a fact about the page. Resolving the ``nth`` here with
    regard to case, while the document resolves it without, would make this
    agree with the tool instead — which is how twenty-four links that never
    landed read as landed.
    """
    if not find:
        return None
    words = plainly(find["text"])
    hit = next((run for run in text.occurrences(plain, words)
                if run.nth == int(find["nth"])), None)
    return None if hit is None else (hit.at, hit.at + len(words))


def _whole(plain: str, want: Tuple[int, int],
           under: List[Tuple[int, int]]) -> bool:
    """Whether the link spans between them cover the anchor end to end.

    Contiguity is what makes a split link one link again. Whitespace between
    two of them does not break it: a link that ends in a space is reported
    without it, and the gap is the space, not a hole in the link.
    """
    at = want[0]
    for start, end in sorted(under):
        while at < start and plain[at].isspace():
            at += 1
        if start > at:
            return False
        at = max(at, end)
    while at < want[1] and plain[at].isspace():
        at += 1
    return at >= want[1]


def verify_all(graph: Graph, pages: Dict[str, str]) -> List[Report]:
    """Every question with a page on disk, in the graph's order."""
    return [verify(graph, q.id, pages[q.id])
            for q in graph.questions if q.id in pages]
