"""The compaction-complete check over a line doc.

A line doc is the record of one elenchus between the user and the AI: not
a transcript, but admissions in the user's words, the questions put, what
was held, found contradictory, declared or pinned, and at the end the plan
the line was compacted into. The plan is what the notebook takes; the rest
is what the plan has to account for, or the compaction lost it. What a
script can hold of that is here: every admission from the dialog is cited
by a row of the plan, every row that edits the notebook cites what it rests
on, every tab a row names stands in the graph the round ends with, and
nothing pinned open in the dialog is left uncited and unclosed. Whether a
row says what its admissions say is read, never computed.

The doc is read as its markdown export: a ``## `` heading opens each
section, and an item is a bullet opening ``- ID. ``, where an id is a run
of capitals and a number (``B12``, ``DC3``, ``R7``). A row cites by naming
ids, singly or as a span (``B19 to B33``); an id is read against every
section that holds it, since the sections number apart and a plain ``A1``
may be the first admission from the notebook or the first aporia.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, Iterator, List, Optional, Set, Tuple

#: the section of a line doc each kind of item stands in, by the heading's
#: words lowered: the admissions a row rests on, the rows, and the sections
#: whose items are pinned to be closed or carried by a row
ADMISSIONS = "admissions"
PLAN = "the plan"
PINNED = ("held questions", "digressions", "contradictions found", "aporiai",
          "declarations")

#: an item's id: capitals then digits, as the doc numbers its lists
ID = re.compile(r"\b([A-Z]{1,2})(\d+)\b")
ITEM = re.compile(r"^- (?P<id>[A-Z]{1,2}\d+)\. (?P<text>.*)$", re.S)
SPAN = re.compile(r"\b([A-Z]{1,2})(\d+) to \1(\d+)\b")
#: the admissions that are the user's in the dialog, which every row must
#: between them cite; the notebook's own are quoted and may stand uncited
DIALOG = "B"
#: the groups of rows that edit the notebook and so cite what they rest on;
#: a consequence or an open row rests on the line as a whole
EDITING = ("A", "B", "C")
#: the ways a row names a tab of the notebook
TAB = re.compile(r"\b(?:[Nn]ew tab|[Tt]he tab) ([a-z][a-z0-9-]*)\b"
                 r"|\b[Tt]he ([a-z][a-z0-9-]*) (?:answer|root)\b")
#: an item pinned in the dialog is closed by its own words, a status opening
#: a sentence of its own (``Closed by B3``, ``Moved to H4``), or by a row
CLOSED = re.compile(r"(?:^|[.;:] )(?:Closed|Done|Resolved|Withdrawn|Moved to|Superseded)\b")

ERROR, WARN = "ERROR", "WARN"


@dataclass
class Item:
    """One numbered item of a section: its id and its words."""
    section: str
    id: str
    text: str

    @property
    def group(self) -> str:
        return ID.match(self.id).group(1)

    def cites(self) -> List[str]:
        """Every id the item names, a span expanded, in order of first
        naming and once each. Its own id is not left out: a row ``A1`` may
        well cite the first aporia, which is ``A1`` too."""
        out: List[str] = []
        text = self.text
        for letters, lo, hi in SPAN.findall(text):
            for n in range(int(lo), int(hi) + 1):
                found = "%s%d" % (letters, n)
                if found not in out:
                    out.append(found)
        text = SPAN.sub(" ", text)
        for letters, n in ID.findall(text):
            found = "%s%s" % (letters, n)
            if found not in out:
                out.append(found)
        return out

    def tabs(self) -> List[str]:
        """Every tab the item names, once each."""
        out: List[str] = []
        for a, b in TAB.findall(self.text):
            name = a or b
            if name not in out:
                out.append(name)
        return out

    @property
    def closed(self) -> bool:
        return bool(CLOSED.search(self.text))


@dataclass
class Doc:
    """A line doc's sections, each its items in order."""
    sections: Dict[str, List[Item]] = field(default_factory=dict)
    title: str = ""

    def items(self, section: str) -> List[Item]:
        return self.sections.get(section, [])

    def admissions(self) -> List[Item]:
        return self.items(ADMISSIONS)

    def rows(self) -> List[Item]:
        return self.items(PLAN)

    def holding(self, cited: str) -> List[Item]:
        """Every item of any section that carries the id."""
        return [item for items in self.sections.values() for item in items
                if item.id == cited]


def parse(markdown: str) -> Doc:
    """The doc off its markdown: sections by their ``## `` headings, items by
    their numbered bullets. A bullet that is not numbered is a line of the
    section and no item; a bullet continuing an item's words (``- H8,
    revised``) is kept as its own words and not as an item."""
    doc = Doc()
    section: Optional[str] = None
    for block in re.split(r"\n\s*\n", markdown):
        block = block.strip()
        if not block:
            continue
        if block.startswith("# ") and not doc.title:
            doc.title = block[2:].strip()
            continue
        if block.startswith("## "):
            section = block[3:].strip().lower()
            doc.sections.setdefault(section, [])
            continue
        if section is None:
            continue
        for line in block.splitlines():
            found = ITEM.match(line.strip())
            if found:
                doc.sections[section].append(Item(section, found.group("id"),
                                                  found.group("text").strip()))
    return doc


@dataclass
class Finding:
    severity: str
    message: str

    def line(self) -> str:
        return "%s %s" % (self.severity, self.message)


def check(doc: Doc, questions: Optional[Set[str]] = None) -> List[Finding]:
    """What the compaction left out, as far as a script can tell.

    ``questions`` is the ids of the graph the round ends with, where one is
    given: a tab a row names that is not among them was never written, or
    was named by another name.
    """
    out: List[Finding] = []
    rows = doc.rows()
    if PLAN not in doc.sections:
        out.append(Finding(ERROR, "the doc has no section '%s': the line is not "
                                  "compacted" % PLAN.title()))
        return out
    if not rows:
        out.append(Finding(ERROR, "the plan has no rows"))
    cited: Set[str] = set()
    for row in rows:
        cited.update(row.cites())
        if row.group in EDITING and not row.cites():
            out.append(Finding(ERROR, "row %s cites no admission, and a row that edits the "
                                      "notebook rests on one" % row.id))
        if questions is not None:
            for tab in row.tabs():
                if tab not in questions:
                    out.append(Finding(ERROR if row.group == "A" else WARN,
                                       "row %s names the tab %r, which the graph does not "
                                       "hold" % (row.id, tab)))
    for admission in doc.admissions():
        if admission.id in cited:
            continue
        if admission.group == DIALOG:
            out.append(Finding(ERROR, "admission %s is cited by no row: %s"
                               % (admission.id, _clip(admission.text))))
        else:
            out.append(Finding(WARN, "admission %s, the notebook's own, is cited by no "
                                     "row: %s" % (admission.id, _clip(admission.text))))
    for section in PINNED:
        for item in doc.items(section):
            if item.id in cited or item.closed:
                continue
            out.append(Finding(WARN, "%s %s is neither closed nor cited by a row: %s"
                               % (section, item.id, _clip(item.text))))
    for name in (ADMISSIONS,):
        if name not in doc.sections:
            out.append(Finding(ERROR, "the doc has no section '%s'" % name.title()))
    return out


def errors(findings: List[Finding]) -> List[Finding]:
    return [f for f in findings if f.severity == ERROR]


def rows_json(doc: Doc) -> List[dict]:
    """The plan's rows as data: id, group, words, what each cites and names."""
    return [{"id": row.id, "group": row.group, "text": row.text,
             "cites": row.cites(), "tabs": row.tabs()} for row in doc.rows()]


def _clip(text: str, width: int = 70) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= width else text[:width - 1].rstrip() + "…"
