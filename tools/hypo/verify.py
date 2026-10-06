"""The page against the renderer: what reached the document, not what was sent.

Every other check reads the graph file. This one reads the exported page, which
is the only place two kinds of defect can show:

    text      a body that is not what the renderer would produce
    missing   a link the sidecar names that the page does not carry
    misplaced a link standing where the encoding does not put that kind
    astray    a link leading to a tab other than the one its target names
    extra     a link the page carries that the sidecar does not name

``missing`` is why this exists. An in-page link needs a block id, so it is
applied after the body write, and ``read.py`` strips it again before parsing —
by design, or a link on the assent line would take that line out of its own
grammar. So a rebuilt graph is identical whether the links were applied or not,
and every gate on the graph passes over a page that lost all of them. That is
what happened: 192 links across 24 tabs, with the rebuild green.

``extra`` is the other half of the same blindness. A link applied by hand, or
one left behind by a definition that has since moved to another tab, is
invisible to everything else; ten of them had accumulated.

Counting, not presence: an anchor may stand twice on a tab and be linked once,
which a set comparison calls correct. And by span rather than by label, since a
nested link cuts the outer one into pieces and no piece is the anchor.

``misplaced`` is the half neither the renderer nor the graph can hold. A target
names a run by a number and the document resolves that number itself, so the
tool can name the run it meant and the document land on another — which is
what a chip did: a token to the renderer, an atom to the document, and every
later run of the word it spells one too high. Asking again whether the run
the link sits on is one the encoding allows is the only question that does
not go through the tool's own answer.

Where a link **goes** is asked only as far as the page can answer. An href
carries a tab and a block, and a target names the tab it should lead to, so
the tab is checked. The block is not: resolving an id needs the outlines
``apply`` takes, which would make this gate take a second input, for a case
``apply.headings`` already refuses on wherever the page has drifted. What is
left is an outline reused across a body write, whose ids that write retired —
a rule about the input, held by reading rather than by this.

A clause whose own link was skipped because a longer one already covers those
words reads as carried, which is what a reader meets; the sidecar's
``covered_by`` says whose destination it actually has, and such an entry is
left out of the destination check for that reason.
"""

from __future__ import annotations

import difflib
import re
from typing import Dict, Iterable, List, NamedTuple, Optional, Tuple

from . import read, render, text
from .model import Graph

#: emphasis off and case folded. A link may open inside an emphasis span, which
#: leaves the closing marker inside the captured text and the opener outside;
#: and a defined word is capitalised where it opens a sentence, so ``pressure``
#: is linked on the page as ``Pressure``. An underscore is a marker only at a
#: word boundary, as markdown reads it and as ``text.plain`` keeps it: inside
#: ``session_01…`` it is a character the page holds, and a needle without it
#: finds nothing there.
_MARKERS = re.compile(r"[*`]|(?<![0-9A-Za-z])_|_(?![0-9A-Za-z])")

#: the question line's state: a chip in what the renderer writes, the word
#: itself in what the document exports.
_STATE = re.compile(r"^(question:)[^·]*·", re.M)

#: an answer's state, on its metadata line, on the same terms. It stands last
#: before the provenance, so it is found from that end: an assent may carry a
#: separator of its own, and the provenance may carry the link applied to it.
_ANSWER_STATE = re.compile(r"^(assent: .*·)[^·\n]*(· provenance: )", re.M)

#: the same fields, taken off rather than named. The document holds a state
#: as a dropdown — an atom, like a chip — and the export prints the word it
#: shows. Counting that word counts characters the document's own find cannot
#: reach, and every run of them after it comes out one too high.
_STATE_WORD = re.compile(r"^(question: )[^·\n]*(· )", re.M)
_ANSWER_STATE_WORD = re.compile(r"^(assent: .*· )[^·\n]*(· provenance: )", re.M)


#: ``read.IN_PAGE_LINK``, keeping the target as well as the words: the
#: reader drops an href and this has to read one. The two patterns describe
#: the same links and are checked against each other by test.
_HREF = re.compile(
    r"\[([^\]]*)\]\(((?:https?://[^)#]*/artifact/[^)#]*)?#[^)]*)\)")


def bare(words: str) -> str:
    return _MARKERS.sub("", words or "").strip().lower()


class Report(NamedTuple):
    question: str
    diff: List[str]
    missing: List[str]
    extra: List[str]
    #: missing anchor -> the anchor whose link already covers those words
    covered: Dict[str, str] = {}
    #: anchors whose link stands on a run the encoding does not allow
    misplaced: List[str] = []
    #: anchors whose link leads to a tab other than the one it names
    astray: List[str] = []

    def ok(self) -> bool:
        return not (self.diff or self.missing or self.extra
                    or self.misplaced or self.astray)

    def lines(self) -> List[str]:
        out = ["=== %s" % self.question]
        out += ["   " + line for line in self.diff]
        for anchor in self.missing:
            under = self.covered.get(anchor)
            out.append("   MISSING LINK on %r%s"
                       % (anchor, " — covered by %r" % under[:48] if under else ""))
        for anchor in self.misplaced:
            out.append("   LINK OUT OF PLACE on %r — the run it names is not "
                       "one the encoding allows" % anchor)
        for anchor in self.astray:
            out.append("   LINK LEADS ASTRAY on %r — the tab it goes to is "
                       "not the one its target names" % anchor)
        for anchor in self.extra:
            out.append("   LINK NOT IN THE SIDECAR on %r" % anchor)
        return out


def labels_of(graph: Graph) -> Dict[str, str]:
    """Chip key to the label the document shows for it, which is the id."""
    return {render.chip_key(q.id): q.id for q in graph.questions}


def normalise(markdown: str, labels: Optional[Dict[str, str]] = None) -> List[str]:
    """A page or a rendered body as the lines the two can be compared on.

    With ``labels``, a chip reads as its label on both sides. The markdown
    export writes one as ``[label](file/<tab>)`` sometimes and as the bare
    label at others — ``kept_as_text``, its own note for the second — and a
    bare label cannot be told from prose by looking. Taking both sides to the
    label compares them without having to: the renderer knows where its chips
    are, so nothing here has to guess.
    """
    out = read.IN_PAGE_LINK.sub(r"\1", markdown or "")
    if labels is not None:
        out = read.CHIP.sub(lambda m: labels.get(m.group(1), m.group(1)), out)
        out = read.EXPORTED_CHIP.sub(r"\1", out)
    else:
        out = read.PLACED_CHIP.sub("", out)
    out = read.ESCAPE.sub(r"\1", out)
    out = _STATE.sub(r"\1 STATE ·", out)
    out = _ANSWER_STATE.sub(r"\1 STATE \2", out)
    # a blank line parts two blocks, and one block with a soft break is not
    # two: the parting is kept as one empty line, however many stood there
    lines: List[str] = []
    for line in out.strip().splitlines():
        if line.strip():
            lines.append(line.rstrip())
        elif lines and lines[-1]:
            lines.append("")
    return lines


class Link(NamedTuple):
    """A run of the page a link stands on, and where it leads."""
    at: int
    end: int
    href: str


def linked_spans(page: str, atoms: bool = True) -> Tuple[str, List[Link]]:
    """The page as plain characters, and which of them a link stands on.

    Compared by span rather than by label, because a link does not survive as
    one label: a nested link cuts it into pieces, and the page then reads

        [The ](#a)[merge](#b)[ is the human's assent and his only act](#a)

    where all three are right and none is the anchor. Matching labels would
    call the whole clause missing and the two halves unaccounted for.

    ``atoms`` says whether the page holds each state as a dropdown — the graph
    names an enum — in which case the word the export prints for it is not
    counted, since the document's own find cannot reach it. Without an enum
    the renderer wrote the word and the document holds it as characters, so it
    counts like any other; taken off, every later run of those letters came
    out one short of where the sidecar counted it.
    """
    page = page or ""
    if atoms:
        page = _STATE_WORD.sub(r"\1\2", page)
        page = _ANSWER_STATE_WORD.sub(r"\1\2", page)
    out: List[str] = []
    spans: List[Link] = []
    where = 0

    def take(raw: str, href) -> None:
        """One run of the page, and where it lands once the markup is off."""
        nonlocal where
        words = plainly(raw)
        if href is not None and words.strip():
            spans.append(Link(where + len(words) - len(words.lstrip()),
                              where + len(words.rstrip()), href))
        out.append(words)
        where += len(words)

    at = 0
    for m in _HREF.finditer(page):
        take(page[at:m.start()], None)
        take(m.group(1), m.group(2))
        at = m.end()
    take(page[at:], None)
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


def _leads_to(href: str, tab: str, own: str) -> bool:
    """Whether an href leads to ``tab``.

    A bare fragment leads to the tab it stands on and nowhere else, so it is
    right only where that is the tab wanted; anything else names its tab in
    front of the block.
    """
    if href.startswith("#"):
        return tab == own
    return href.partition("#")[2].partition(".")[0] == tab


def _as_the_document_holds_it(plain: str, spans: List[Link], target: str,
                              labels: Iterable[str]) -> Tuple[str, List[Link]]:
    """The page's characters as the document counts them, and the link spans.

    A chip is an atom in the document and not text: a search for ``party`` on
    a tab whose answer carries a chip labelled ``party`` finds the word and
    not the chip. The markdown export writes that label out as words, so the
    page read back holds characters the document does not, and a ``nth``
    counted over it lands one run late.

    The two strings are the same but for those labels, so they are walked in
    step and a label is cut where they part. Nothing else is: where the
    divergence is not a label this gives the page back untouched, because
    then it is a real difference and the text comparison is what reports it.
    """
    if plain == target:
        return plain, spans
    forms = [form for label in sorted(set(labels), key=len, reverse=True)
             for form in (" " + label, label + " ", label)]
    out: List[str] = []
    shift: List[Tuple[int, int]] = []  # from this offset on, subtract this much
    gone = i = j = 0
    while i < len(plain):
        if j < len(target) and plain[i] == target[j]:
            out.append(plain[i])
            i += 1
            j += 1
            continue
        cut = next((len(f) for f in forms if plain.startswith(f, i)), 0)
        if not cut:
            return plain, spans
        i += cut
        gone += cut
        shift.append((i, gone))

    def moved(at: int) -> int:
        return at - next((g for end, g in reversed(shift) if at >= end), 0)

    return "".join(out), [Link(moved(s.at), moved(s.end), s.href) for s in spans]


def account(graph: Graph, qid: str, page: str,
            entries: Optional[List[dict]] = None, rendered: Optional[str] = None
            ) -> Tuple[str, List[str], List[str], List[str], List[Link]]:
    """The page as plain characters, what it does not carry, what it carries
    in the wrong place, and what it carries that nothing asked for.

    The strays come back as spans rather than as their words, because taking
    one off has to name the run the mark stands on and two runs may read
    alike. ``verify`` reports the words, which is what a reader is shown;
    ``apply`` needs the position, which is what an operation takes.

    Place is asked of **this** page rather than of the rendered one. The
    sidecar's number was counted on the page the renderer built; the document
    counts it again on the page it holds, and the two are not obliged to
    agree. Resolving the number here the way the document does and then
    asking the encoding whether that run is allowed is what makes the answer
    a fact about the page rather than a restatement of the tool.

    Where a link leads is asked of the tab alone, and only of an entry the
    page can carry: one covered by a longer link has the outer one's
    destination by design, and reporting it would be reporting the design.

    ``entries`` and ``rendered`` are the sidecar's links and the rendered
    body, where the caller has them: ``verify`` has both, and rendering the
    tab once rather than four times is most of what it costs.
    """
    if rendered is None:
        rendered = render.body(graph, qid)
    if entries is None:
        entries = render.links(graph, qid, rendered=rendered)["links"]
    plain, spans = _as_the_document_holds_it(
        *linked_spans(page, atoms=bool(graph.state_enum)),
        render.page_text(graph, qid, rendered),
        [q.id for q in graph.questions])
    own = graph.get(qid).tab if graph.get(qid) is not None else ""
    missing: List[str] = []
    misplaced: List[str] = []
    astray: List[str] = []
    accounted: List[Link] = []
    for entry in entries:
        find = entry.get("find")
        want = _where(plain, find)
        if want is None:
            missing.append(bare(entry["anchor"]))
            continue
        allowed = {(form, run.nth) for form, run in
                   render.eligible(plain, entry["kind"], entry["anchor"])}
        if (plainly(find["text"]), int(find["nth"])) not in allowed:
            misplaced.append(bare(entry["anchor"]))
        under = [span for span in spans
                 if span[0] < want[1] and want[0] < span[1]]
        if _whole(plain, want, under):
            accounted.extend(under)
        else:
            missing.append(bare(entry["anchor"]))
        tab = entry["target"].lstrip("#").partition(".")[0]
        if under and not entry.get("covered_by") and not any(
                _leads_to(link.href, tab, own) for link in under):
            astray.append(bare(entry["anchor"]))
    extra = [span for span in spans if span not in accounted]
    return plain, sorted(missing), sorted(misplaced), sorted(astray), extra


def verify(graph: Graph, qid: str, page: str) -> Report:
    """One tab's page against what the renderer and the sidecar say it holds."""
    labels = labels_of(graph)
    rendered = render.body(graph, qid)
    entries = render.links(graph, qid, rendered=rendered)["links"]
    diff = list(difflib.unified_diff(
        normalise(page, labels), normalise(rendered, labels),
        "page", "render", lineterm="", n=0))[2:]
    plain, missing, misplaced, astray, extra = account(graph, qid, page, entries, rendered)
    # a link the page cannot carry because another already covers those words
    covered = {bare(entry["anchor"]): entry["covered_by"]
               for entry in entries if entry.get("covered_by")}
    return Report(question=qid, diff=diff, missing=missing,
                  extra=sorted(plain[start:end].strip().lower()
                               for start, end, _ in extra),
                  covered=covered, misplaced=misplaced, astray=astray)


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
           under: List[Link]) -> bool:
    """Whether the link spans between them cover the anchor end to end.

    Contiguity is what makes a split link one link again. Whitespace between
    two of them does not break it: a link that ends in a space is reported
    without it, and the gap is the space, not a hole in the link.
    """
    at = want[0]
    for start, end, _href in sorted(under):
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
