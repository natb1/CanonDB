"""lines — the open lines of the page's collection ``lines``, read and ordered.

Every open line still to be put to the user is one document of the page's
database, in the collection ``lines``. A session exports the collection to a
directory, one JSON file per document, with a versions file naming the
version of each, as the board's store is exported; this module reads the two
and nothing else. It never reaches the network and never writes the store:
what it decides is a list of writes, each an ``update`` of the fields that
change, pinned to the version read, for the session to send.

A write is ``{"op": "update", "collection": "lines", "doc_id": <id>, "data":
{<field>: <value>}, "if_version": <version>}``. The store's ``update`` merges
an object into the one stored and replaces anything else, so a write to
``flags`` names only the kinds it changes; a value written ``None`` is a
stored null, which every reader here takes for absent. Every write stamps
``touched_at`` with the time handed in; nothing here reads a clock.

**What closes a line.** Only the user's word: there is no close without a
sentence of the user's quoted, no drop and no merge without the user's word,
and nothing here closes a line because a reader predicts its answer. A
closed line keeps ``closed_by: {sentence, answer}`` and ``reopenable: true``,
so that the user can reopen it. A line that leaves the live states carries
no rank; a reopened one waits unranked, last, until the next order.

**The order.** Every live line is in one list, anchored or not, and its
weight is

    weight = share * unblocks / cost

``share`` is the share of the root carried by the sentences it is anchored
to: each anchor read as its ``tab/block`` where the shares give one, else as
its ``tab``, each key counted once, the keys summed, and no tab counted for
more than the tab's own share. A line with no anchor the shares key takes
half the least share held by any anchored live line (open or put, the
session's work among them) of its project, and is provisional; so its share
is below that of every anchored line of its project. A line may stand in
several projects: the one its ``project`` names, by the project's name
(read first) or by its root's id where a graph names that root, and, on any
line, each project a graph places one of its anchors' tabs in. A line in
several projects counts as an anchored line of each, and an unanchored
line in several takes the least over all of them. A line in none is of no
project: under a graph of named projects it is of the whole root and takes
the least over every anchored live line; elsewhere the lines of no project
are one group. Under shares alone no tab and no root's id is placed: a
project is then its ``project`` as written, and an anchored line with none
is of no project, which ``check`` warns of. Where its project has no
anchored live line,
it takes half the share of its project's root instead (the whole root's one
where the line names no project the shares know). That fallback is a step:
an unanchored line's share rises to half its root's when the last anchored
line of its project leaves the live states, and the unanchored lines of a
project with no anchored line can weigh above those of a project with one.
An anchored line whose share is zero is no anchored line here: it takes the provisional share
itself. With no shares given at all, every line's share is one and every
line is provisional.
``unblocks`` is one and the number of live lines that wait on it directly:
its children (by either side of ``parent``), those its ``blocks`` names, and
those whose ``waits_on`` names it, each once. ``cost`` is what the line asks
of the user: its stated ``cost``, one of 1, 3 and 9, where set; else 3 for
the user's work and 1 for anything else. Work ``owed_by`` the session costs
the user nothing and is weighed at 1; it is ordered by the same weight but
apart, after every ask, and never stands in the queue: it never holds the
user's card. ``pressure`` is kept on a line as recorded and weighs nothing.

The line ``put`` comes first; then the heaviest; ties by ``opened_at``
(oldest first, a line with none after), then id. ``rank`` is the place in
that order counted from 1, the asks first and the session's work after; the
queue is the open asks in it, the one put being ``ordo/current.next``. Two
live lines of one rank are no fault the order refuses: it is the fault the
order mends. Its writes may land in several batches, and where only some
land the next order starts from what did and writes the rest.

**The user's override.** The user may always take another line ahead of
the order. ``override`` appends one entry to a local log, never the store:
the line taken, the line the order put first ahead of it, each with its
terms as computed, the time handed in, and the user's ground restated in a
few words by the caller; an entry the same as the log's last is not
appended again. ``report`` reads the log against the order as it
was computed: how many overrides, which lines, and which term of the weight
each most contradicts. An override changes no weight; a change to the
method is proposed from the report.

**The weekly chunk.** From the lower half of the queue, the lines at its
far end are shown to the user a few at a time, the oldest of them first,
none shown again within ``min_days`` of its last showing, each showing one
more in its ``review_count``. A line shown ``drop_after`` times since its
count began without its weight rising is marked ``proposed: "drop"`` for
the user, who keeps, merges or drops it; with no shares given, nothing is
proposed, since the weight then says nothing of the line.
"""

from __future__ import annotations

import datetime
import json
import os
import re
from typing import Dict, Iterable, List, NamedTuple, Optional, Set, Tuple

from .board import parse_time

COLLECTION = "lines"
KINDS = ("question", "review", "work")
STATES = ("open", "put", "answered", "closed", "merged", "dropped")
OPEN, PUT, ANSWERED, CLOSED, MERGED, DROPPED = STATES
#: the states of a line still waiting to be put, or now put
LIVE = (OPEN, PUT)
#: the states of a parent that no longer stands for its children
WITHDRAWN = (MERGED, DROPPED)
FLAGS = ("ground-moved", "parent-withdrawn", "touched")
MOVED, ORPHANED, TOUCHED = FLAGS
CHOICES = ("keep", "merge", "drop")
#: who owes a line of work: the user, or the session
OWNERS = ("user", "session")
USER, SESSION = OWNERS
#: the stated scale of what a line costs the user
COSTS = (1, 3, 9)
#: the cost of the user's work where none is stated
WORK_COST = 3
#: what an unanchored line takes of the least share an anchored line of its
#: project holds, or of its project's root where none is anchored
UNANCHORED = 0.5
#: the most words an override's ground is restated in
GROUND_WORDS = 25
#: the terms of the weight, as the report names them
TERMS = ("share", "unblocks", "cost")
#: what the report counts a contradiction of: the terms, the provisional
#: rule apart from the share term, and none
COUNTED = ("share", "provisional", "unblocks", "cost", "none")
#: the weight a weekly chunk's baseline is taken by; a baseline stored by
#: another, or by none named, is stale and begun again
METHOD = "share*unblocks/cost; unanchored: half the least anchored share of its project"
#: the override log's name, beside the records' directory
OVERRIDES = "lines-overrides.jsonl"
DROP_AFTER = 3
CHUNK = 5
MIN_DAYS = 6

ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}")


class Refused(Exception):
    """A write this module will not print, with every reason it will not."""

    def __init__(self, reasons: Iterable[str]):
        self.reasons = list(reasons)
        super().__init__("; ".join(self.reasons))


class Found(NamedTuple):
    """What ``check`` finds: faults that make any decision unsafe; faults a
    mode exists to mend (a rank held twice, which ``order`` mends; a parent
    that is no line, which ``orphans`` flags), refused only by the other
    modes; and warnings, which refuse nothing."""
    faults: List[str]
    mendable: List[str]
    warnings: List[str]


class Lines(NamedTuple):
    records: Dict[str, dict]
    versions: Dict[str, int]
    found: Found

    @property
    def problems(self) -> List[str]:
        """Every fault a mode that mends nothing refuses over."""
        return self.found.faults + self.found.mendable

    def get(self, lid: str) -> dict:
        found = self.records.get(lid)
        if found is None:
            raise Refused(["no line %s" % lid])
        return found


# --- reading -------------------------------------------------------------

def where(directory: str) -> str:
    """The directory holding the documents: ``<dir>/lines`` where an export
    of the store put them there, else the directory itself."""
    inner = os.path.join(directory, COLLECTION)
    return inner if os.path.isdir(inner) else directory


def read(directory: str, versions: Optional[dict] = None) -> Lines:
    """Every ``*.json`` file of the export, by its id, with what ``check``
    finds in them."""
    records: Dict[str, dict] = {}
    faults: List[str] = []
    base = where(directory)
    try:
        names = sorted(n for n in os.listdir(base) if n.endswith(".json"))
    except OSError as exc:
        return Lines({}, {}, Found(["the records directory cannot be read: %s" % exc], [], []))
    for name in names:
        stem = name[:-len(".json")]
        try:
            with open(os.path.join(base, name), encoding="utf-8") as fh:
                doc = json.load(fh)
        except (OSError, ValueError) as exc:
            faults.append("%s cannot be read: %s" % (name, exc))
            continue
        if not isinstance(doc, dict):
            faults.append("%s is not an object" % name)
            continue
        if doc.get("id") != stem:
            faults.append("%s: its id %r is not its file's name" % (name, doc.get("id")))
            continue
        records[stem] = doc
    found = check(records)
    return Lines(records, dict(versions or {}),
                 Found(faults + found.faults, found.mendable, found.warnings))


def _str(v) -> bool:
    return isinstance(v, str) and v.strip() != ""


def _ids(v) -> bool:
    return isinstance(v, list) and all(isinstance(x, str) and ID.fullmatch(x) for x in v)


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def children(rec: dict) -> List[str]:
    kids = rec.get("children")
    return [k for k in kids if isinstance(k, str)] if isinstance(kids, list) else []


def parent(rec: dict) -> Optional[str]:
    p = rec.get("parent")
    return p if isinstance(p, str) and p else None


def flags(rec: dict) -> Dict[str, dict]:
    """The flags a line stands under, by kind; a kind stored null is none."""
    got = rec.get("flags")
    return {k: v for k, v in got.items() if v is not None} if isinstance(got, dict) else {}


def shape(rec: dict) -> List[str]:
    """What is wrong with one record's fields, each a sentence."""
    lid = rec.get("id")
    out: List[str] = []

    def bad(field, what):
        out.append("%s: %s %s" % (lid, field, what))

    if not isinstance(lid, str) or not ID.fullmatch(lid):
        bad("id", "is not an id")
    if not _str(rec.get("title")):
        bad("title", "is missing or empty")
    if rec.get("kind") not in KINDS:
        bad("kind", "is not one of %s" % ", ".join(KINDS))
    if rec.get("state") not in STATES:
        bad("state", "is not one of %s" % ", ".join(STATES))
    ask = rec.get("ask")
    if ask is not None and not isinstance(ask, dict):
        bad("ask", "is not {case, prompt, recommendation}")
    anchors = rec.get("anchors", [])
    if not isinstance(anchors, list):
        bad("anchors", "is not a list")
        anchors = []
    for i, a in enumerate(anchors):
        if not isinstance(a, dict) or not _str(a.get("tab")):
            bad("anchors[%d]" % i, "has no tab")
            continue
        for key in ("block", "h", "words"):
            if a.get(key) is not None and not isinstance(a.get(key), str):
                bad("anchors[%d].%s" % (i, key), "is not a string")
        if a.get("h") and not a.get("block"):
            bad("anchors[%d]" % i, "has a fingerprint and no block")
        if a.get("gone") not in (None, True, False):
            bad("anchors[%d].gone" % i, "is not true or false")
    p = rec.get("parent")
    if p is not None and not (isinstance(p, str) and ID.fullmatch(p)):
        bad("parent", "is not one line id")
    for field in ("children", "blocks", "waits_on"):
        if rec.get(field) is not None and not _ids(rec.get(field)):
            bad(field, "is not a list of line ids")
    cost = rec.get("cost")
    if cost is not None and (not isinstance(cost, int) or isinstance(cost, bool)
                             or cost not in COSTS):
        bad("cost", "is not one of %s" % ", ".join(str(c) for c in COSTS))
    if rec.get("owed_by") not in (None,) + OWNERS:
        bad("owed_by", "is not one of %s" % ", ".join(OWNERS))
    if rec.get("owed_by") == SESSION:
        if rec.get("kind") != "work":
            bad("owed_by", "names the session on a line that is not work")
        if cost is not None:
            bad("cost", "is set on the session's work, which costs the user nothing")
        if rec.get("state") == PUT:
            bad("state", "is put on the session's work, which never holds the user's card")
    if rec.get("review_method") is not None and not _str(rec.get("review_method")):
        bad("review_method", "is not the name of a weight")
    if rec.get("project") is not None and not _str(rec.get("project")):
        bad("project", "is not a project's name")
    for field in ("rank", "review_count", "review_since"):
        v = rec.get(field)
        if v is not None and not (isinstance(v, int) and not isinstance(v, bool) and v >= 0):
            bad(field, "is not a whole number")
    for field in ("pressure", "review_weight"):
        v = rec.get(field)
        if v is not None and not (_num(v) and v >= 0):
            bad(field, "is not a number of zero or more")
    for field in ("opened_at", "touched_at", "reviewed_at"):
        if rec.get(field) is not None and not _str(rec.get(field)):
            bad(field, "is not a time")
    got = rec.get("flags")
    if got is not None:
        if not isinstance(got, dict):
            bad("flags", "is not {kind: {at, …}}")
        else:
            for kind, flag in got.items():
                if kind not in FLAGS:
                    bad("flags", "holds %r, not one of %s" % (kind, ", ".join(FLAGS)))
                elif flag is not None and not (isinstance(flag, dict) and _str(flag.get("at"))):
                    bad("flags.%s" % kind, "is not {at, …}")
    if rec.get("proposed") not in (None, "drop"):
        bad("proposed", "is not \"drop\"")
    if rec.get("reopenable") not in (None, True, False):
        bad("reopenable", "is not true or false")
    closed_by = rec.get("closed_by")
    if closed_by is not None and not (isinstance(closed_by, dict)
                                      and _str(closed_by.get("sentence"))):
        bad("closed_by", "quotes no sentence of the user's")
    state = rec.get("state")
    if state == CLOSED and closed_by is None and not _str(rec.get("answered_by")):
        bad("state", "is closed with neither the user's sentence nor an answer")
    if state in LIVE and closed_by is not None:
        bad("state", "is %s and the line still carries closed_by" % state)
    if state == MERGED and not _str(rec.get("answered_by")):
        bad("state", "is merged into no line")
    decision = rec.get("decision")
    if state == DROPPED and not (isinstance(decision, dict) and _str(decision.get("word"))):
        bad("state", "is dropped without the user's word")
    if rec.get("proposed") and state not in LIVE:
        bad("proposed", "stands on a line that is %s" % state)
    return out


def check(records: Dict[str, dict]) -> Found:
    """Every record's shape, then the records against each other: each
    child, blocked line and merge names a line that exists; a parent and its
    child agree on both sides; no line is its own ancestor and no chain of
    ``blocks`` returns to where it began; at most one line is put. A parent
    that is no line, and a rank two live lines hold, are mendable; an anchor
    with no block, which no move of the notebook can be judged against, is a
    warning."""
    faults: List[str] = []
    mendable: List[str] = []
    warnings: List[str] = []
    for lid in sorted(records):
        faults.extend(shape(records[lid]))
    for lid in sorted(records):
        rec = records[lid]
        p = parent(rec)
        if p is not None:
            if p not in records:
                mendable.append("%s: its parent %s is no line" % (lid, p))
            elif lid not in children(records[p]):
                faults.append("%s: its parent %s does not list it among its children" % (lid, p))
        for c in children(rec):
            if c not in records:
                faults.append("%s: its child %s is no line" % (lid, c))
            elif parent(records[c]) != lid:
                faults.append("%s: lists %s as a child whose parent is %s"
                              % (lid, c, parent(records[c])))
        for b in rec["blocks"] if isinstance(rec.get("blocks"), list) else []:
            if b not in records:
                faults.append("%s: blocks %s, which is no line" % (lid, b))
            elif b == lid:
                faults.append("%s: blocks itself" % lid)
        for w in rec["waits_on"] if isinstance(rec.get("waits_on"), list) else []:
            if w not in records:
                faults.append("%s: waits on %s, which is no line" % (lid, w))
            elif w == lid:
                faults.append("%s: waits on itself" % lid)
        if rec.get("state") == MERGED and _str(rec.get("answered_by")) \
                and rec["answered_by"] not in records:
            faults.append("%s: merged into %s, which is no line" % (lid, rec["answered_by"]))
    for lid in sorted(records):
        seen, cur = {lid}, parent(records[lid])
        while cur is not None and cur in records:
            if cur in seen:
                faults.append("%s: its line of parents returns to %s, a cycle" % (lid, cur))
                break
            seen.add(cur)
            cur = parent(records[cur])
    for cycle in _blocks_cycles(records):
        faults.append("a cycle of blocks and waits_on: %s" % " -> ".join(cycle))
    put = sorted(l for l, r in records.items() if r.get("state") == PUT)
    if len(put) > 1:
        faults.append("more than one line is put: %s" % ", ".join(put))
    ranks: Dict[int, List[str]] = {}
    for lid, rec in records.items():
        if rec.get("state") in LIVE and isinstance(rec.get("rank"), int):
            ranks.setdefault(rec["rank"], []).append(lid)
    for rank in sorted(ranks):
        if len(ranks[rank]) > 1:
            mendable.append("rank %d is held by %s; order mends it"
                            % (rank, ", ".join(sorted(ranks[rank]))))
    blind = [(lid, a) for lid in sorted(records) if records[lid].get("state") in LIVE
             for a in records[lid].get("anchors") or []
             if isinstance(a, dict) and not a.get("block")]
    if blind:
        warnings.append("%d anchor(s) on %d open line(s) name no block and cannot be "
                        "verified against the notebook: give each its tab's id, block and h"
                        % (len(blind), len({l for l, _ in blind})))
    return Found(faults, mendable, warnings)


def _blocks_cycles(records: Dict[str, dict]) -> List[List[str]]:
    """Each cycle of holding up once, read from its least id: a line holds
    up those its ``blocks`` names and those whose ``waits_on`` names it."""
    found: List[List[str]] = []
    seen: Set[Tuple[str, ...]] = set()
    held: Dict[str, Set[str]] = {lid: set() for lid in records}
    for lid, rec in records.items():
        for x in rec["blocks"] if isinstance(rec.get("blocks"), list) else []:
            if x in records and x != lid:
                held[lid].add(x)
        for x in rec["waits_on"] if isinstance(rec.get("waits_on"), list) else []:
            if x in records and x != lid:
                held[x].add(lid)

    def edges(lid):
        return sorted(held[lid])

    def walk(start, cur, path):
        for nxt in edges(cur):
            if nxt == start:
                key = tuple(sorted(path))
                if key not in seen:
                    seen.add(key)
                    found.append(path + [start])
            elif nxt not in path and nxt > start:
                walk(start, nxt, path + [nxt])

    for lid in sorted(records):
        walk(lid, lid, [lid])
    return found


def sound(lines: Lines, mends: bool = False) -> None:
    """Refuse to decide anything over an export that does not check; a mode
    that mends (``order``, ``orphans``, ``link``) runs over what it mends."""
    bad = lines.found.faults if mends else lines.problems
    if bad:
        raise Refused(["the records do not check: %s" % p for p in bad])


# --- the writes ----------------------------------------------------------

def _time(at: str, flag: str = "--at") -> None:
    try:
        parse_time(at)
    except ValueError as exc:
        raise Refused(["%s: %s" % (flag, exc)])


def write(lines: Lines, lid: str, at: str, **changes) -> dict:
    """The ``update`` of one line's changed fields, stamped and pinned."""
    key = "%s/%s" % (COLLECTION, lid)
    if key not in lines.versions:
        raise Refused(["the versions file does not name %s" % key])
    data = dict(changes)
    data["touched_at"] = at
    return {"op": "update", "collection": COLLECTION, "doc_id": lid, "data": data,
            "if_version": lines.versions[key]}


def live(rec: dict) -> bool:
    return rec.get("state") in LIVE


def _summary(rec: dict, **more) -> dict:
    out = {"id": rec["id"], "title": rec.get("title"), "state": rec.get("state")}
    out.update(more)
    return out


# --- 2: the ground moved -------------------------------------------------

def read_blocks(entries) -> Dict[str, Dict[str, Optional[str]]]:
    """The notebook's current blocks, ``[{tab, block, h}]`` or ``{"blocks":
    [...]}``, as tab -> block -> h. A tab named only by ``{tab}`` is read
    and holds no block."""
    if isinstance(entries, dict):
        entries = entries.get("blocks")
    if not isinstance(entries, list):
        raise Refused(["the blocks file is not a list of {tab, block, h}"])
    out: Dict[str, Dict[str, Optional[str]]] = {}
    for i, e in enumerate(entries):
        if not isinstance(e, dict) or not _str(e.get("tab")):
            raise Refused(["the blocks file's entry %d names no tab" % i])
        tab = out.setdefault(e["tab"], {})
        if e.get("block") is not None:
            tab[str(e["block"])] = e.get("h")
    return out


def blocks_of_outlines(directory: str) -> List[dict]:
    """The notebook's blocks from the outlines ``tools/page.py --outlines``
    writes, one ``<tab>.xml`` a tab read whole: ``[{tab, block, h}]``, and
    ``{tab}`` for a tab that holds no block."""
    from . import appline, page
    out: List[dict] = []
    try:
        names = sorted(n for n in os.listdir(directory) if n.endswith(".xml"))
    except OSError as exc:
        raise Refused(["the outlines directory cannot be read: %s" % exc])
    for name in names:
        tab = name[:-len(".xml")]
        with open(os.path.join(directory, name), encoding="utf-8") as fh:
            source = fh.read()
        try:
            found = appline.blocks(page.outline(source))
        except (appline.Refused, ValueError) as exc:
            raise Refused(["%s: %s" % (name, exc)])
        out.append({"tab": tab})
        out.extend({"tab": tab, "block": bid, "h": node.get("h")}
                   for bid, node in found.items())
    return out


def moved_anchors(rec: dict, blocks: Dict[str, Dict[str, Optional[str]]],
                  whole: bool = False) -> Tuple[List[dict], int]:
    """The anchors of a line whose block is gone from a tab the blocks read
    (or, the read being ``whole``, whose tab is gone), or whose fingerprint
    differs from the block's now; and how many anchors could not be judged:
    those with no block, and those on a tab a partial read does not hold.
    An anchor already read as gone is not judged again."""
    out, blind = [], 0
    for a in rec.get("anchors") or []:
        tab, block = a.get("tab"), a.get("block")
        if a.get("gone"):
            continue
        if not block:
            blind += 1
            continue
        if tab not in blocks:
            if whole:
                out.append({"tab": tab, "block": block, "was": a.get("h"), "now": None,
                            "tab_gone": True})
            else:
                blind += 1
            continue
        if block not in blocks[tab]:
            out.append({"tab": tab, "block": block, "was": a.get("h"), "now": None})
        elif a.get("h") and blocks[tab][block] and blocks[tab][block] != a.get("h"):
            out.append({"tab": tab, "block": block, "was": a.get("h"),
                        "now": blocks[tab][block]})
    return out, blind


def moved(lines: Lines, blocks, at: str, whole: bool = False) -> Tuple[List[dict], List[dict], int]:
    """Each live line with an anchor that moved, the writes flagging it
    ``ground-moved``, and the count of anchors that could not be judged; a
    line already flagged for the same anchors is listed and not written
    again."""
    sound(lines)
    _time(at)
    current = read_blocks(blocks)
    found, writes, blind = [], [], 0
    for lid in sorted(lines.records):
        rec = lines.records[lid]
        if not live(rec):
            continue
        anchors, n = moved_anchors(rec, current, whole)
        blind += n
        if not anchors:
            continue
        found.append(_summary(rec, anchors=anchors))
        if flags(rec).get(MOVED, {}).get("anchors") == anchors:
            continue
        writes.append(write(lines, lid, at, flags={MOVED: {"anchors": anchors, "at": at}}))
    return found, writes, blind


def orphans(lines: Lines, at: str, gone: Iterable[str] = ()) -> Tuple[List[dict], List[dict]]:
    """Each live line whose parent is merged, dropped or no line (or one of
    ``gone``, being dropped or merged in the same batch), and the writes
    flagging it ``parent-withdrawn``."""
    _time(at)
    gone = set(gone)
    found, writes = [], []
    for lid in sorted(lines.records):
        rec = lines.records[lid]
        p = parent(rec)
        if not live(rec) or p is None or lid in gone:
            continue
        prec = lines.records.get(p)
        if p in gone or prec is None or prec.get("state") in WITHDRAWN:
            found.append(_summary(rec, parent=p))
            if flags(rec).get(ORPHANED, {}).get("parent") == p:
                continue
            writes.append(write(lines, lid, at, flags={ORPHANED: {"parent": p, "at": at}}))
    return found, writes


def unflag(lines: Lines, lid: str, kind: str, at: str, blocks=None) -> List[dict]:
    """The write clearing one kind of flag once it has been read, the other
    kinds left standing. Clearing ``ground-moved`` with the notebook's
    blocks, each anchor whose block still stands takes its fingerprint now,
    and each whose block (or tab) is gone is kept as read gone, so that the
    same move is not flagged again."""
    sound(lines)
    _time(at)
    rec = lines.get(lid)
    if kind not in FLAGS:
        raise Refused(["the flag's kind is one of %s" % ", ".join(FLAGS)])
    if kind not in flags(rec):
        raise Refused(["%s carries no %s flag" % (lid, kind)])
    if blocks is not None and kind != MOVED:
        raise Refused(["fingerprints are taken only in clearing a ground-moved flag"])
    changes: dict = {"flags": {kind: None}}
    if blocks is not None:
        current = read_blocks(blocks)
        anchors = []
        for a in rec.get("anchors") or []:
            a = dict(a)
            tab, block = a.get("tab"), a.get("block")
            if block and tab in current:
                if block in current[tab]:
                    if current[tab][block]:
                        a["h"] = current[tab][block]
                else:
                    a["gone"] = True
            anchors.append(a)
        changes["anchors"] = anchors
    return [write(lines, lid, at, **changes)]


# --- 3: the sweep, and what closes a line --------------------------------

def _shares_anchor(mine: dict, other: dict) -> bool:
    """One tab, and the same block, or no block on either side: an anchor of
    the whole tab shares with every anchor on it."""
    if mine.get("tab") != other.get("tab"):
        return False
    a, b = mine.get("block") or None, other.get("block") or None
    return a is None or b is None or a == b


def sweep(lines: Lines, answered: str) -> List[dict]:
    """The live lines an answer to ``answered`` may bear on: its children
    first, then those sharing its parent, then those sharing an anchor (one
    tab and the same block, an anchor of the whole tab sharing with every
    anchor on it), each group by rank and id, each line once with every
    reason it is there. The answered line itself is never among them."""
    sound(lines)
    rec = lines.get(answered)
    mine = [a for a in rec.get("anchors") or [] if isinstance(a, dict)]
    kids = set(children(rec)) | {l for l, r in lines.records.items() if parent(r) == answered}
    p = parent(rec)
    groups: Dict[str, Tuple[int, List[str]]] = {}
    for lid, other in lines.records.items():
        if lid == answered or not live(other):
            continue
        why = []
        if lid in kids:
            why.append("child")
        if p is not None and parent(other) == p:
            why.append("sibling")
        shared = set()
        for a in mine:
            for b in other.get("anchors") or []:
                if isinstance(b, dict) and _shares_anchor(a, b):
                    block = a.get("block") or b.get("block")
                    shared.add((a["tab"], block or ""))
        why.extend("anchor %s/%s" % (t, b) if b else "anchor %s" % t for t, b in sorted(shared))
        if why:
            first = 0 if "child" in why else 1 if "sibling" in why else 2
            groups[lid] = (first, why)
    order = sorted(groups, key=lambda l: (groups[l][0], _rank_key(lines.records[l]), l))
    return [_summary(lines.records[l], why=groups[l][1]) for l in order]


def _rank_key(rec: dict) -> int:
    r = rec.get("rank")
    return r if isinstance(r, int) and not isinstance(r, bool) else 1 << 30


def close(lines: Lines, lid: str, sentence: Optional[str], answer: Optional[str],
          at: str) -> List[dict]:
    """The write closing a line by the user's sentence. Refused without the
    sentence quoted: no line is closed on a prediction."""
    sound(lines)
    reasons = []
    if not _str(sentence):
        reasons.append("a line is closed only by the user's sentence, quoted: give --sentence")
    if not _str(answer):
        reasons.append("name the answer the sentence was given in: give --by-answer")
    _time(at)
    rec = lines.get(lid)
    if not live(rec):
        reasons.append("%s is %s, not open" % (lid, rec.get("state")))
    if reasons:
        raise Refused(reasons)
    return [write(lines, lid, at, state=CLOSED,
                  closed_by={"sentence": sentence, "answer": answer},
                  answered_by=answer, reopenable=True, proposed=None, rank=None)]


def reopen(lines: Lines, lid: str, at: str) -> List[dict]:
    """The write reversing a close: the line open again, its close cleared,
    unranked until the next order."""
    sound(lines)
    _time(at)
    rec = lines.get(lid)
    if rec.get("state") != CLOSED:
        raise Refused(["%s is %s, not closed" % (lid, rec.get("state"))])
    if rec.get("reopenable") is False:
        raise Refused(["%s was closed as not reopenable" % lid])
    return [write(lines, lid, at, state=OPEN, closed_by=None, answered_by=None,
                  reopenable=None, rank=None)]


def touch(lines: Lines, lid: str, answer: str, at: str) -> List[dict]:
    """The write flagging a line an answer only touches: it stays open."""
    sound(lines)
    _time(at)
    rec = lines.get(lid)
    reasons = []
    if not live(rec):
        reasons.append("%s is %s, not open" % (lid, rec.get("state")))
    if not _str(answer):
        reasons.append("name the answer that touches it: give --answer")
    if reasons:
        raise Refused(reasons)
    return [write(lines, lid, at, flags={TOUCHED: {"answer": answer, "at": at}})]


# --- 4: the order --------------------------------------------------------

def read_shares(text: str) -> Dict[str, float]:
    """The shares, as a JSON object of ``tab`` or ``tab/block`` to a number,
    or as ``tools/shares.py`` prints them, one ``<question>  <share>`` a line."""
    try:
        doc = json.loads(text)
    except ValueError:
        doc = None
    if isinstance(doc, dict):
        bad = [k for k, v in doc.items() if not _num(v)]
        if bad:
            raise Refused(["the shares give no number for %s" % ", ".join(sorted(bad))])
        return {k: float(v) for k, v in doc.items()}
    if doc is not None:
        raise Refused(["the shares file is neither an object nor the shares listing"])
    out: Dict[str, float] = {}
    for n, row in enumerate(text.splitlines(), 1):
        if not row.strip():
            continue
        m = re.match(r"\s*(\S+)\s+([0-9]+(?:\.[0-9]+)?)(?:\s|$)", row)
        if not m:
            raise Refused(["the shares listing's line %d is not <question> <share>" % n])
        out[m.group(1)] = float(m.group(2))
    return out


def share_of(rec: dict, shares: Dict[str, float]) -> float:
    """The share the anchored sentences carry: each anchor read as
    ``tab/block`` where the shares give it, else as ``tab``, each key once,
    and no tab counted for more than its own share where the shares give
    one."""
    by_tab: Dict[str, Set[str]] = {}
    for a in rec.get("anchors") or []:
        if not isinstance(a, dict):
            continue
        tab, block = a.get("tab"), a.get("block")
        fine = "%s/%s" % (tab, block) if block else None
        by_tab.setdefault(tab, set()).add(fine if fine in shares else tab)
    total = 0.0
    for tab, keys in by_tab.items():
        part = sum(shares.get(k, 0.0) for k in keys)
        total += min(part, shares[tab]) if tab in shares else part
    return total


def blocked(lines: Lines, rec: dict) -> List[str]:
    """The live lines that wait on this one directly: its children, by
    either side of ``parent``, those its ``blocks`` names, and those whose
    ``waits_on`` names it, each once."""
    held = set(rec.get("blocks") or []) | set(children(rec))
    held |= {l for l, r in lines.records.items() if parent(r) == rec["id"]}
    held |= {l for l, r in lines.records.items()
             if isinstance(r.get("waits_on"), list) and rec["id"] in r["waits_on"]}
    held.discard(rec["id"])
    return sorted(l for l in held if l in lines.records and live(lines.records[l]))


def session_s(rec: dict) -> bool:
    """Whether a line is work the session owes, and not the user."""
    return rec.get("owed_by") == SESSION


def cost_of(rec: dict) -> int:
    """What a line asks of the user: its stated cost where set; else 3 for
    the user's work and 1 for anything else; the session's work 1."""
    if session_s(rec):
        return 1
    stated = rec.get("cost")
    if isinstance(stated, int) and not isinstance(stated, bool) and stated in COSTS:
        return stated
    return WORK_COST if rec.get("kind") == "work" else 1


class Terms(NamedTuple):
    """A line's weight and the three terms it is made of; ``provisional``
    names why the share is not the line's own, or is None."""
    share: float
    unblocks: int
    cost: int
    provisional: Optional[str]

    @property
    def weight(self) -> float:
        return self.share * self.unblocks / self.cost


def root_share(rec: dict, shares: Dict[str, float],
               roots: Optional[Dict[str, float]] = None) -> Tuple[float, bool]:
    """The share of the line's project's root, and whether the project was
    known: from ``roots`` (a project's name to its root's share, as a graph
    gives them), else from ``shares`` keyed by the root's question id; one,
    the whole root's, where neither knows it."""
    name = rec.get("project")
    if _str(name):
        for known in (roots or {}, shares):
            if name in known and known[name] > 0:
                return known[name], True
    return 1.0, False


def project_root(lines: Lines, rec: dict, shares: Dict[str, float],
                 roots: Optional[Dict[str, float]]) -> Tuple[float, Optional[str]]:
    """The share of the line's project's root, or the whole root's one where
    the shares know no project of the line's, with that said: the base of
    the provisional rule where the project has no anchored line."""
    root, known = root_share(rec, shares, roots)
    return root, None if known else "no project the shares know, the whole root"


class Roots(dict):
    """Each project's name to its root's share, as a graph gives them;
    ``of``: each question id of the graph (its tabs, the roots among them)
    to the name of its project; and ``ids``: each project's root's id to
    the project's name. In a notebook of one project the name is None, and
    its questions are of the lines naming none. A plain dict of the shares
    by name serves where no question's project is known. A ``Roots`` of one
    project is an empty dict, and so false: read ``of`` and ``ids`` from
    it, never test it for truth."""

    def __init__(self, shares=(), of: Optional[Dict[str, Optional[str]]] = None,
                 ids: Optional[Dict[str, Optional[str]]] = None):
        super().__init__(shares)
        self.of: Dict[str, Optional[str]] = dict(of or {})
        self.ids: Dict[str, Optional[str]] = dict(ids or {})


def _names(roots) -> Set[Optional[str]]:
    """The projects' names the roots know."""
    return (set(roots or {}) | set((getattr(roots, "of", None) or {}).values())
            | set((getattr(roots, "ids", None) or {}).values()))


def several(roots) -> bool:
    """Whether the roots place questions in named projects: a graph of
    several projects, or of one named."""
    return any(v is not None for v in (getattr(roots, "of", None) or {}).values())


def project_keys(rec: dict, roots: Optional[Dict[str, float]] = None) -> Set[Optional[str]]:
    """The projects a line is of, one key or several: its ``project`` read as
    a project's name where the roots know that name, before all else; else
    as a project's root's id the roots' ``ids`` names; else as it is
    written; and, on any line, the project of each anchor's tab the roots'
    ``of`` places. A line of none of these is of no project, the key None."""
    of = getattr(roots, "of", None) or {}
    ids = getattr(roots, "ids", None) or {}
    keys: Set[Optional[str]] = set()
    name = rec.get("project")
    if _str(name):
        keys.add(name if name in _names(roots) or name not in ids else ids[name])
    for a in rec.get("anchors") or []:
        if isinstance(a, dict) and a.get("tab") in of:
            keys.add(of[a["tab"]])
    return keys or {None}


def unknown_projects(lines: Lines, roots: Optional[Dict[str, float]] = None) -> List[str]:
    """The live lines whose ``project`` is neither a project's name the
    roots know nor a root's id they name; nothing is unknown where the roots
    place no question."""
    if not (getattr(roots, "of", None) or {}):
        return []
    known = _names(roots) | set(getattr(roots, "ids", None) or {})
    return sorted(lid for lid, r in lines.records.items()
                  if live(r) and _str(r.get("project")) and r["project"] not in known)


def unprojected(lines: Lines, roots: Optional[Dict[str, float]] = None) -> List[str]:
    """The live lines with no anchor and no ``project``, where the roots
    place questions in named projects: each is weighed against the anchored
    lines of every project."""
    if not several(roots):
        return []
    return sorted(lid for lid, r in lines.records.items()
                  if live(r) and not _str(r.get("project"))
                  and not any(isinstance(a, dict) for a in r.get("anchors") or []))


def unplaced(lines: Lines, roots: Optional[Dict[str, float]] = None) -> List[str]:
    """The live anchored lines no project can be taken for: no ``project``,
    and no anchor whose tab the roots' ``of`` places. They are of the lines
    naming none, and set no share for an unanchored line of a named
    project."""
    of = getattr(roots, "of", None) or {}
    return sorted(lid for lid, r in lines.records.items()
                  if live(r) and not _str(r.get("project"))
                  and any(isinstance(a, dict) for a in r.get("anchors") or [])
                  and not any(isinstance(a, dict) and a.get("tab") in of
                              for a in r.get("anchors") or []))


def least_anchored(lines: Lines, rec: dict, shares: Dict[str, float],
                   roots: Optional[Dict[str, float]]) -> Tuple[float, Optional[str]]:
    """The base of the provisional rule as adopted: the least share held by
    any live line (open or put, the session's work among them) of any
    project the line is of, by ``project_keys``, whose anchors the shares
    key (a share above zero). A line of no project, where the roots place
    questions in named projects, is of the whole root: the least is taken
    over every anchored live line. Elsewhere the lines of no project are one
    group. Where there is no such line, ``project_root``'s, with that said.
    The line itself is never counted: it is weighed by this rule only where
    its own share is zero."""
    mine = project_keys(rec, roots)
    whole = mine == {None} and several(roots)
    held = [share_of(r, shares) for r in lines.records.values()
            if live(r) and (whole or mine & project_keys(r, roots))]
    held = [s for s in held if s > 0]
    if held:
        return min(held), "of no project, every project's lines" if whole else None
    root, said = project_root(lines, rec, shares, roots)
    none = "no anchored line in its project"
    return root, "%s, its project's root" % none if said is None else "%s; %s" % (none, said)


def provisional_share(lines: Lines, rec: dict, shares: Dict[str, float],
                      roots: Optional[Dict[str, float]] = None,
                      fraction: float = UNANCHORED, base=least_anchored) -> Tuple[float, str]:
    """The provisional rule: the share a line takes where no anchor of it
    is keyed by the shares, ``fraction`` of what ``base`` gives (a function
    of the line, the shares and the roots returning a share and what to say
    of it, or None), with why the share is provisional. Another reading of
    the rule is another ``fraction`` or ``base`` here, and nothing else."""
    anchored = any(isinstance(a, dict) for a in rec.get("anchors") or [])
    why = "no anchor the shares key" if anchored else "no anchor"
    got, said = base(lines, rec, shares, roots)
    return got * fraction, why if said is None else "%s; %s" % (why, said)


def terms(lines: Lines, rec: dict, shares: Dict[str, float],
          roots: Optional[Dict[str, float]] = None) -> Terms:
    """The weight's terms for one line (the module's docstring)."""
    unblocks = 1 + len(blocked(lines, rec))
    cost = cost_of(rec)
    if not shares and not roots:
        return Terms(1.0, unblocks, cost, "no shares given")
    s = share_of(rec, shares)
    if s > 0:
        return Terms(s, unblocks, cost, None)
    got, why = provisional_share(lines, rec, shares, roots)
    return Terms(got, unblocks, cost, why)


def weight(lines: Lines, rec: dict, shares: Dict[str, float],
           roots: Optional[Dict[str, float]] = None) -> float:
    return terms(lines, rec, shares, roots).weight


def when(value) -> Optional[datetime.datetime]:
    """An ISO date or time as a UTC instant, a date read as its midnight;
    None where it is no such thing."""
    if not _str(value):
        return None
    try:
        got = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if got.tzinfo is None:
        got = got.replace(tzinfo=datetime.timezone.utc)
    return got.astimezone(datetime.timezone.utc)


_LAST = datetime.datetime.max.replace(tzinfo=datetime.timezone.utc)


def _age(rec: dict) -> datetime.datetime:
    return when(rec.get("opened_at")) or _LAST


def weighed(lines: Lines, shares: Dict[str, float],
            roots: Optional[Dict[str, float]] = None) -> List[Tuple[str, Terms]]:
    """The live lines in their order, each with its terms: the asks, the
    put line first, then the heaviest, ties by ``opened_at``, oldest first,
    then id; then the session's work, in the same order."""
    rows = [(lid, terms(lines, rec, shares, roots))
            for lid, rec in lines.records.items() if live(rec)]
    return sorted(rows, key=lambda r: (session_s(lines.records[r[0]]),
                                       lines.records[r[0]].get("state") != PUT,
                                       -round(r[1].weight, 12),
                                       _age(lines.records[r[0]]), r[0]))


def ordered(lines: Lines, shares: Dict[str, float],
            roots: Optional[Dict[str, float]] = None) -> List[Tuple[str, float]]:
    """The live lines in their order, each with its weight."""
    return [(lid, t.weight) for lid, t in weighed(lines, shares, roots)]


def row(rec: dict, rank: int, t: Terms) -> dict:
    """One line of the printed order: its place, its weight and the terms."""
    return {"rank": rank, "id": rec["id"], "kind": rec.get("kind"),
            "title": rec.get("title"), "state": rec.get("state"),
            "weight": round(t.weight, 6), "share": round(t.share, 6),
            "unblocks": t.unblocks, "cost": t.cost,
            "provisional": t.provisional is not None,
            "provisional_why": t.provisional, "opened_at": rec.get("opened_at")}


def projection(lines: Lines, order: List[str]) -> List[dict]:
    """The queue the page draws: the open asks in order, ``{kind, title}``;
    the session's work is never in it."""
    return [{"kind": lines.records[l].get("kind"), "title": lines.records[l].get("title")}
            for l in order if lines.records[l].get("state") == OPEN
            and not session_s(lines.records[l])]


class Order(NamedTuple):
    writes: List[dict]
    queue: List[dict]
    asks: List[dict]
    session: List[dict]


def order(lines: Lines, shares: Dict[str, float], at: str,
          roots: Optional[Dict[str, float]] = None) -> Order:
    """The rank writes for every live line whose rank changes, the order's
    head first; the queue; and the order printed, the asks and the
    session's work apart. It runs over ranks held twice, and mends them; a
    line not live that still holds a rank has it taken off."""
    sound(lines, mends=True)
    _time(at)
    rows = weighed(lines, shares, roots)
    writes, asks, session = [], [], []
    for n, (lid, t) in enumerate(rows, 1):
        rec = lines.records[lid]
        if rec.get("rank") != n:
            writes.append(write(lines, lid, at, rank=n))
        (session if session_s(rec) else asks).append(row(rec, n, t))
    for lid in sorted(lines.records):
        rec = lines.records[lid]
        if not live(rec) and rec.get("rank") is not None:
            writes.append(write(lines, lid, at, rank=None))
    return Order(writes, projection(lines, [l for l, _ in rows]), asks, session)


def queue(lines: Lines) -> List[dict]:
    """The queue as the records stand, by their stored rank, a line with
    none after, then by ``opened_at`` and id. A rank held twice is read as
    it stands, by ``opened_at`` and id."""
    sound(lines, mends=True)
    live_ids = [l for l, r in lines.records.items() if live(r)]
    live_ids.sort(key=lambda l: (lines.records[l].get("state") != PUT,
                                 _rank_key(lines.records[l]), _age(lines.records[l]), l))
    return projection(lines, live_ids)


# --- the user's override -------------------------------------------------

def log_path(directory: str) -> str:
    """The override log's default place: beside the records' directory."""
    base = os.path.dirname(os.path.abspath(os.path.normpath(directory)))
    return os.path.join(base, OVERRIDES)


def _side(rec: dict, place: int, t: Terms) -> dict:
    return {"id": rec["id"], "place": place, "weight": round(t.weight, 6),
            "share": round(t.share, 6), "unblocks": t.unblocks, "cost": t.cost,
            "provisional": t.provisional is not None, "put": rec.get("state") == PUT}


def override(lines: Lines, shares: Dict[str, float], taken: str, ground: Optional[str],
             at: str, over: Optional[str] = None,
             roots: Optional[Dict[str, float]] = None) -> dict:
    """The log entry of the user taking ``taken`` ahead of the order: by
    default ahead of the ask the order puts first, or ahead of ``over``,
    which must stand before it. Refused without the ground, with a ground of
    more than a few words, or where nothing is overridden. It writes nothing
    to the store and changes no weight."""
    sound(lines, mends=True)
    _time(at)
    reasons = []
    if not _str(ground):
        reasons.append("an override keeps the user's ground, restated: give --ground")
    elif len(ground.split()) > GROUND_WORDS:
        reasons.append("restate the ground in a few words, %d at most" % GROUND_WORDS)
    rec = lines.get(taken)
    rows = [(l, t) for l, t in weighed(lines, shares, roots)
            if not session_s(lines.records[l])]
    place = {l: n for n, (l, _) in enumerate(rows, 1)}
    if not live(rec):
        reasons.append("%s is %s, not open" % (taken, rec.get("state")))
    elif session_s(rec):
        reasons.append("%s is the session's work, which never holds the user's card" % taken)
    if over is None and rows:
        over = rows[0][0]
    if over is not None and not reasons:
        lines.get(over)
        if over == taken:
            reasons.append("%s is first by the order already: nothing is overridden" % taken)
        elif over not in place:
            reasons.append("%s is not an ask the order holds" % over)
        elif place[over] > place[taken]:
            reasons.append("%s stands after %s in the order: nothing is overridden"
                           % (over, taken))
    if over is None and not reasons:
        reasons.append("the order holds no ask")
    if reasons:
        raise Refused(reasons)
    t = dict(rows)
    return {"at": at, "taken": _side(rec, place[taken], t[taken]),
            "over": _side(lines.records[over], place[over], t[over]),
            "head": rows[0][0], "ground": " ".join(ground.split())}


def _same(a: dict, b: dict) -> bool:
    """One override twice: the same time, line taken and line passed over."""
    return (a.get("at") == b.get("at") and a["taken"].get("id") == b["taken"].get("id")
            and a["over"].get("id") == b["over"].get("id"))


def append_override(path: str, entry: dict) -> bool:
    """Append one entry to the log, one JSON object a line; never rewrite.
    An entry the same as the log's last (a command run again) is not
    appended, and False says so. A last line that lost its newline is ended
    before the entry, so that the two stay apart."""
    found = read_overrides(path)
    if found and _same(found[-1], entry):
        return False
    try:
        lead = ""
        if os.path.exists(path) and os.path.getsize(path):
            with open(path, "rb") as fh:
                fh.seek(-1, os.SEEK_END)
                lead = "" if fh.read(1) == b"\n" else "\n"
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(lead + json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
    except OSError as exc:
        raise Refused(["the override log cannot be written: %s" % exc])
    return True


def _entry(entry) -> bool:
    """Whether a log line is an override: a time, and two sides each with an
    id, a weight and the three terms as numbers."""
    if not isinstance(entry, dict) or not _str(entry.get("at")):
        return False
    for key in ("taken", "over"):
        got = entry.get(key)
        if not (isinstance(got, dict) and _str(got.get("id"))
                and all(_num(got.get(t)) for t in ("weight",) + TERMS)
                and got.get("cost") > 0 and got.get("unblocks") > 0):
            return False
    return True


def read_overrides(path: str) -> List[dict]:
    """The log's entries in order; none where there is no log yet."""
    if not os.path.exists(path):
        return []
    out = []
    try:
        with open(path, encoding="utf-8") as fh:
            for n, text in enumerate(fh, 1):
                if not text.strip():
                    continue
                try:
                    entry = json.loads(text)
                except ValueError:
                    raise Refused(["the override log's line %d is not JSON" % n])
                if not _entry(entry):
                    raise Refused(["the override log's line %d is not an override" % n])
                out.append(entry)
    except OSError as exc:
        raise Refused(["the override log cannot be read: %s" % exc])
    return out


def contradicted(entry: dict) -> List[str]:
    """What an override most contradicts. None where the line taken weighed
    no less than the line passed over: no weight is contradicted, as where
    the line passed over stood first by being put and not by its weight.
    Else the term on which the line taken stood worst, by the ratio of the
    two (share and unblocks taken over passed; cost passed over taken),
    each term tied for the least named; the share term named
    ``provisional`` where either side's share was provisional, since what
    is contradicted is then the provisional rule."""
    a, b = entry["taken"], entry["over"]
    if a["weight"] >= b["weight"]:
        return []

    def ratio(x, y):
        return x / y if y else (1.0 if not x else float("inf"))

    got = {"share": ratio(a["share"], b["share"]),
           "unblocks": ratio(a["unblocks"], b["unblocks"]),
           "cost": ratio(b["cost"], a["cost"])}
    least = min(got.values())
    if least >= 1:
        return []
    hit = [k for k in TERMS if abs(got[k] - least) < 1e-12]
    if a.get("provisional") or b.get("provisional"):
        hit = ["provisional" if k == "share" else k for k in hit]
    return hit


def report(entries: List[dict]) -> dict:
    """The overrides read against the order as it was computed: how many,
    over what span, which lines were taken and passed over and how often,
    how many passed over a line first by being put, which term each most
    contradicts and which most often, the provisional rule counted apart
    from the share term, and each entry with its provisional flags."""
    taken: Dict[str, int] = {}
    over: Dict[str, int] = {}
    count = {k: 0 for k in COUNTED}
    provisional = put = 0
    rows = []
    for e in entries:
        taken[e["taken"]["id"]] = taken.get(e["taken"]["id"], 0) + 1
        over[e["over"]["id"]] = over.get(e["over"]["id"], 0) + 1
        hit = contradicted(e)
        for k in hit or ["none"]:
            count[k] += 1
        if e["taken"].get("provisional") or e["over"].get("provisional"):
            provisional += 1
        if e["over"].get("put"):
            put += 1
        rows.append({"at": e.get("at"), "taken": e["taken"]["id"], "over": e["over"]["id"],
                     "taken_provisional": bool(e["taken"].get("provisional")),
                     "over_provisional": bool(e["over"].get("provisional")),
                     "over_put": bool(e["over"].get("put")),
                     "contradicts": hit, "ground": e.get("ground")})
    named = [k for k in COUNTED if k != "none"]
    top = max(count[k] for k in named)
    times = sorted(e["at"] for e in entries if _str(e.get("at")))
    return {"overrides": len(entries),
            "first": times[0] if times else None, "last": times[-1] if times else None,
            "taken": dict(sorted(taken.items(), key=lambda kv: (-kv[1], kv[0]))),
            "passed_over": dict(sorted(over.items(), key=lambda kv: (-kv[1], kv[0]))),
            "passed_over_the_put_line": put,
            "contradicts": count,
            "most_contradicted": [k for k in named if top and count[k] == top],
            "on_a_provisional_share": provisional,
            "entries": rows}


# --- 5: parent and children ----------------------------------------------

def link(lines: Lines, parent_id: str, child_id: str, at: str) -> List[dict]:
    """The two writes making ``child_id`` a child of ``parent_id``: the
    child's ``parent`` and the parent's ``children``. Refused where the child
    has another parent that stands, where the link would close a cycle, or
    where the parent is merged or dropped. A child whose parent is no line
    may be linked anew."""
    sound(lines, mends=True)
    _time(at)
    if parent_id == child_id:
        raise Refused(["a line is not its own parent"])
    p, c = lines.get(parent_id), lines.get(child_id)
    reasons = []
    if parent(c) not in (None, parent_id) and parent(c) in lines.records:
        reasons.append("%s already has the parent %s" % (child_id, parent(c)))
    if p.get("state") in WITHDRAWN:
        reasons.append("%s is %s and stands for no children" % (parent_id, p.get("state")))
    cur, seen = parent_id, set()
    while cur is not None and cur in lines.records and cur not in seen:
        if cur == child_id:
            reasons.append("%s is an ancestor of %s: the link would close a cycle"
                           % (child_id, parent_id))
            break
        seen.add(cur)
        cur = parent(lines.records[cur])
    if reasons:
        raise Refused(reasons)
    writes = []
    if child_id not in children(p):
        writes.append(write(lines, parent_id, at, children=children(p) + [child_id]))
    if parent(c) != parent_id:
        writes.append(write(lines, child_id, at, parent=parent_id))
    return writes


# --- 6: the weekly chunk, and the user's decision ------------------------

def chunk(lines: Lines, shares: Dict[str, float], n: int, at: str,
          drop_after: int = DROP_AFTER, min_days: int = MIN_DAYS,
          roots: Optional[Dict[str, float]] = None) -> Tuple[List[dict], List[dict]]:
    """The ``n`` open asks at the far end of the queue, from its lower half
    and never its head, the oldest of them shown first, none shown within
    ``min_days`` of its last showing; and the writes adding one to each
    one's ``review_count`` and stamping ``reviewed_at``. A line's weight
    when its count began is kept as ``review_weight``, the count then as
    ``review_since``; where its weight has risen since, both are taken
    afresh, and so where the baseline was taken by a weight other than
    ``METHOD`` (stale, rebased, and proposed for nothing at that showing).
    A line shown ``drop_after`` times since, its weight not risen,
    is marked ``proposed: "drop"``, but only where shares were given. A line
    already proposed waits for the user and is not shown again."""
    sound(lines)
    _time(at)
    if n < 1:
        raise Refused(["--n must be one or more"])
    if drop_after < 1:
        raise Refused(["--drop-after must be one or more"])
    if min_days < 0:
        raise Refused(["--min-days must be zero or more"])
    now = parse_time(at)
    rows = ordered(lines, shares, roots)
    weights = dict(rows)
    rank = {lid: i for i, (lid, _) in enumerate(rows, 1)}
    open_ids = [l for l, _ in rows if lines.records[l].get("state") == OPEN
                and not session_s(lines.records[l])]
    head = (len(open_ids) + 1) // 2
    pool = []
    for lid in reversed(open_ids[head:]):
        rec = lines.records[lid]
        last = when(rec.get("reviewed_at"))
        if rec.get("proposed") or (last is not None
                                   and now - last < datetime.timedelta(days=min_days)):
            continue
        pool.append(lid)
    picked = sorted(pool[:n], key=lambda l: (_age(lines.records[l]), l))
    shown, writes = [], []
    for lid in picked:
        rec = lines.records[lid]
        count = (rec.get("review_count") or 0) + 1
        base, since = rec.get("review_weight"), rec.get("review_since")
        w = round(weights[lid], 12)
        changes = {"review_count": count, "reviewed_at": at}
        stale = base is not None and rec.get("review_method") != METHOD
        if base is None or since is None or stale or w > base:
            base, since = w, count - 1
            changes.update(review_weight=base, review_since=since, review_method=METHOD)
        if shares and not stale and count - since >= drop_after and w <= base:
            changes["proposed"] = "drop"
        shown.append(_summary(rec, rank=rank[lid], review_count=count,
                              proposed=changes.get("proposed"), rebased=stale))
        writes.append(write(lines, lid, at, **changes))
    return shown, writes


def decide(lines: Lines, lid: str, choice: str, word: Optional[str], at: str,
           into: Optional[str] = None) -> List[dict]:
    """The write of the user's decision on a line: ``keep`` clears a
    proposal and counts afresh; ``merge`` carries the line on by ``into``;
    ``drop`` drops it. A merge or a drop is refused without the user's word,
    takes the line's rank off, and flags the children it leaves."""
    sound(lines)
    _time(at)
    rec = lines.get(lid)
    reasons = []
    if choice not in CHOICES:
        reasons.append("the choice is one of %s" % ", ".join(CHOICES))
    if choice in ("merge", "drop") and not _str(word):
        reasons.append("a line is %s only at the user's word: give --by-user-word"
                       % ("merged" if choice == "merge" else "dropped"))
    if not live(rec):
        reasons.append("%s is %s, not open" % (lid, rec.get("state")))
    if choice == "merge":
        if not into:
            reasons.append("a merge names the line it is carried on by: give --into")
        elif into == lid:
            reasons.append("a line is not merged into itself")
        elif into not in lines.records:
            reasons.append("no line %s" % into)
        elif not live(lines.records[into]):
            reasons.append("%s is %s, not open" % (into, lines.records[into].get("state")))
    elif into:
        reasons.append("--into is for a merge only")
    if reasons:
        raise Refused(reasons)
    decision = {"choice": choice, "word": word if _str(word) else None, "at": at}
    if choice == "keep":
        count = rec.get("review_count") or 0
        return [write(lines, lid, at, proposed=None, decision=decision,
                      review_weight=None, review_since=count)]
    changes = {"state": DROPPED if choice == "drop" else MERGED, "proposed": None,
               "decision": decision, "rank": None}
    if choice == "merge":
        changes["answered_by"] = into
    writes = [write(lines, lid, at, **changes)]
    writes.extend(w for w in orphans(lines, at, gone=[lid])[1]
                  if parent(lines.records[w["doc_id"]]) == lid)
    return writes
