"""The frontier, read off the page where it stands.

``next.py`` answers which question to put: the heaviest with nothing left to
wait on, from a graph file, which is built from every tab read whole. Most
callers ask something smaller — what could be put at all — and need none of
the words for it. The frontier is every question of the author's that the AI
answers, that has not landed, and whose lineage has: every question the AI
answers above it, by a path through the AI's questions, carries an answer that
has landed. That is ``turn.above`` and ``project.landed``, the relation a turn
carries and the backlog is summed over, and nothing here re-states it; this
builds just enough of a graph for them to run on.

Just enough is three kinds of line, each of which the renderer writes in a
fixed shape and a ``search`` finds without reading the body:

- the question line (``question: … · pressure N · …``): the question's state,
  who answers it, and its pressure — the number the frontier is ordered by;
- each answer's metadata line (``assent: … · <state> · provenance: thesis
  hinge``): whether an answer has landed;
- each term's heading (``▸ <headline> → <chip>``): the edges, whose chips name
  the tabs they raise, so the lineage is the inverse of what the tabs above
  say they raise.

So a caller makes one or two small searches per tab of the author's — `` · ``
catches the question line and every answer's line at once, and ``▸ `` every
term — and never a whole-body view. Every block used is checked against the
hash the document printed, as ``appline`` checks what it writes from.

Where a question stands on the frontier and ``next.py`` would not put it, the
difference is what the page does not say at a glance: whether it is already
in a thread. Pressure, not backlog, is the
order here, because the backlog is a projection of the whole graph and the
frontier's own members block nothing that is not below them.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Dict, List, Sequence, Tuple

from . import appline, page, project, read, turn
from .appline import Refused
from .model import AUTHOR, STATES, Graph, Question, Term, Thesis


def _lines(source) -> List[Tuple[str, ET.Element]]:
    """(block id, node) for every paragraph of a read, each checked."""
    out = []
    parsed = appline.blocks(source)
    for bid, node in parsed.items():
        if node.tag == "paragraph":
            out.append((bid, appline.block(source, bid, parsed)))
    return out


def question(name: str, tab: str, party: str, reads: Sequence,
             names: Dict[str, str]) -> Question:
    """A question as the frontier needs it, from the reads of its tab."""
    line = None
    answers: Dict[str, str] = {}
    terms: List[Term] = []
    seen_terms = set()
    for source in reads:
        for bid, node in _lines(source):
            text = read.IN_PAGE_LINK.sub(r"\1", page.inline(node))
            if node.get("heading") == "3" and text.startswith("▸ "):
                chips = list(node.iter("mention"))
                if not chips or bid in seen_terms:
                    continue
                seen_terms.add(bid)
                ref = chips[-1].get("ref", "")
                to = names.get(ref.rpartition("/")[2]) or chips[-1].get("label", "")
                terms.append(Term(title=text[2:].rpartition("→")[0].strip(), to=to))
                continue
            if node.get("heading"):
                continue
            if text.startswith("question: "):
                found = read.QUESTION_LINE.match(text)
                if read.REMOVED_FIELD in text:
                    raise Refused("%s: %s" % (name, read.REMOVED % (
                        "a `requires:` field on its question line")))
                if not found:
                    raise Refused("%s: the question line is malformed" % name)
                line = found
            else:
                found = read.ASSENT_LINE.match(text)
                if found:
                    answers[bid] = found.group("state").strip()
    if line is None:
        raise Refused("%s: no read of its tab holds the question line; search the "
                      "tab for ' · pressure '" % name)
    theses = [Thesis(title="", text="", state=state) for _, state in sorted(answers.items())]
    # the edges ride on an answer of their own, held, so that they neither
    # land nor count as put: the graph only has to carry them
    theses.append(Thesis(title="", text="", state=STATES[0], terms=terms))
    return Question(id=name, tab=tab, body="", question="",
                    state=line.group("state").strip(), kind=line.group("kind").strip(),
                    pressure=int(line.group("pressure")),
                    answerer=(line.group("answerer") or "").strip(),
                    party=party, theses=theses)


def graph(manifest: dict, reads: Dict[str, Sequence]) -> Graph:
    """The author's questions, each from the reads of its tab.

    Every author tab must have been read: a tab not read is a question whose
    edges and answers are unknown, and a frontier computed without it would
    put a question under an answer nobody looked for.
    """
    tabs = manifest.get("value", manifest).get("tabs", {})
    names = {tab_id: meta.get("name", tab_id) for tab_id, meta in tabs.items()}
    party = read.parties(tabs)
    author = {names[t]: t for t in tabs if party.get(t) == AUTHOR}
    unknown = sorted(set(reads) - set(author))
    if unknown:
        raise Refused("reads for %s, which the document read names as no tab of "
                      "the author's" % ", ".join(unknown))
    missing = sorted(set(author) - set(reads))
    if missing:
        raise Refused("no read of %s; every tab of the author's is read for the "
                      "frontier" % ", ".join(missing))
    questions = [question(name, author[name], AUTHOR, reads[name], names)
                 for name in sorted(author)]
    return Graph(artifact="", questions=questions)


def frontier(g: Graph) -> List[Tuple[str, int]]:
    """(question, pressure) for every question on the frontier, heaviest
    first, ties by id."""
    by_id = g.by_id()
    rows = []
    for q in g.questions:
        if q.tradition or q.answerer != project.AI or project.landed(q):
            continue
        if all(project.landed(by_id[a]) for a in turn.above(g, q.id)):
            rows.append((q.id, q.pressure))
    rows.sort(key=lambda r: (-r[1], r[0]))
    return rows
