#!/usr/bin/env python3
"""lines.py <mode> <records dir> … — the open lines: checked, swept, ordered, and the writes they need.

A session exports the page's collection ``lines`` to a directory, one JSON
file per document (at ``<dir>/lines/<id>.json``, or ``<dir>/<id>.json``),
with a versions file of ``{"lines/<id>": <version>}``, and runs a mode over
the two:

    check <dir> [--shares FILE | --graph FILE]  every record against the schema and each other,
                                                and the anchored lines of no project
    queue <dir>                                 the queue as the stored ranks give it
    moved <dir> (--blocks FILE | --outlines DIR) [--whole] --at T
                                                flag each line whose anchored block moved, and
                                                count the anchors that could not be judged
    orphans <dir> --at T                        flag each line whose parent is merged, dropped
                                                or no line
    unflag <dir> ID --kind KIND --at T [--blocks FILE | --outlines DIR]
                                                clear one flag once read; for ground-moved,
                                                taking the fingerprints now
    sweep <dir> --answered ID                   the lines an answer may bear on, children first
    close <dir> ID --sentence TEXT --by-answer ID --at T   close by the user's sentence, quoted
    reopen <dir> ID --at T                      reverse a close
    touch-flag <dir> ID --answer ID --at T      flag a line an answer only touches
    order <dir> [--shares FILE | --graph FILE] [--queue-out FILE] --at T
                                                every live line weighed, the ranks, and the
                                                queue, written to FILE where given
    override <dir> --taken ID [--over ID] --ground TEXT [--shares FILE | --graph FILE]
             [--log FILE] --at T                append the user's override to the log
    report <dir> [--log FILE]                   the overrides read against the order
    link <dir> --parent ID --child ID --at T    make a line another's child, both sides
    chunk <dir> [--shares FILE | --graph FILE] --at T [--n 5] [--drop-after 3] [--min-days 6]
                                                the week's lines from the queue's far end
    decide <dir> ID keep|merge|drop [--into ID] [--by-user-word TEXT] --at T

Every writing mode takes ``--versions FILE`` and prints one JSON value on
standard output: ``close``, ``reopen``, ``touch-flag``, ``unflag``,
``link`` and ``decide`` the list of writes, each ``{op, collection, doc_id,
data, if_version}``; ``moved``, ``orphans``, ``order`` and ``chunk`` an
object holding that list under ``writes`` beside what they found.
``order`` prints every live line in order under ``order`` (the asks) and
``session_work`` (the work the session owes, never in the queue), each with
its ``weight``, its three terms ``share``, ``unblocks`` and ``cost``, and
``provisional``; and ``queue``, the projection ``ordo/current.queue`` is set
to, which ``--queue-out`` also writes to a file. ``override`` writes nothing
to the store: it appends one entry to the override log, by default
``lines-overrides.jsonl`` beside the records' directory, and prints it, or
says it is the log's last entry already and appends nothing;
``report`` prints what the log says against the order. The
session sends the writes with its own tool in batches of at most fifty, in
order; where a batch is refused, it exports again and runs the mode again,
which writes what is still owed. ``check`` prints each fault as ``ERROR``
and exits 1; a rank held twice and a parent that is no line are faults
``order`` and ``orphans`` mend and run over; an anchor that names no block
is a ``WARN`` and refuses nothing. A refusal is one ``REFUSED:`` line per reason on standard error and
exits 1; there is no path that closes, merges or drops a line without the
user's words. ``--shares`` takes ``tools/shares.py``'s listing, or a JSON
object of ``tab`` or ``tab/block`` to a share; ``--graph`` computes the
shares from a graph of every tab, and each project's root's share with
them; with neither, no share is known, every line weighs a share of one and
is provisional, and the chunk proposes no drop. ``T`` is an ISO 8601 UTC time such as
``2030-01-02T03:04:05Z``. Nothing here reaches the network or reads a clock.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hypo import cli, lines, project, share  # noqa: E402

cli.quiet_pipe()

#: the modes that print writes, and so take --versions and --at
WRITING = ("moved", "orphans", "unflag", "close", "reopen", "touch-flag", "order", "link",
           "chunk", "decide")


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0], epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="mode", required=True)

    def mode(name, *, line=False):
        p = sub.add_parser(name)
        p.add_argument("records", help="the directory the collection was exported to")
        if line:
            p.add_argument("id", help="the line's id")
        if name in WRITING:
            p.add_argument("--versions", required=True, metavar="FILE",
                           help='{"lines/<id>": version} for every exported document')
            p.add_argument("--at", required=True, metavar="T",
                           help="the time, ISO 8601 UTC, as handed in")
        return p

    def weighed(p):
        g = p.add_mutually_exclusive_group()
        g.add_argument("--shares", metavar="FILE",
                       help="shares.py's listing, or {tab or tab/block: share}")
        g.add_argument("--graph", metavar="FILE", help="a graph of every tab")

    p = mode("check")
    weighed(p)
    mode("queue")
    p = mode("override")
    weighed(p)
    p.add_argument("--taken", required=True, metavar="ID", help="the line the user took")
    p.add_argument("--over", metavar="ID",
                   help="the line it was taken ahead of; the order's first by default")
    p.add_argument("--ground", metavar="TEXT", help="the user's ground, in a few words")
    p.add_argument("--at", required=True, metavar="T", help="the time, ISO 8601 UTC")
    p.add_argument("--log", metavar="FILE", help="the override log, appended to")
    p = mode("report")
    p.add_argument("--log", metavar="FILE", help="the override log")
    def ground(p, required):
        g = p.add_mutually_exclusive_group(required=required)
        g.add_argument("--blocks", metavar="FILE",
                       help="the notebook's blocks now, [{tab, block, h}]")
        g.add_argument("--outlines", metavar="DIR",
                       help="the outlines page.py --outlines wrote, one <tab>.xml a tab")

    p = mode("moved")
    ground(p, True)
    p.add_argument("--whole", action="store_true",
                   help="the read holds every tab: an anchor's tab absent from it is gone")
    mode("orphans")
    p = mode("unflag", line=True)
    ground(p, False)
    p.add_argument("--kind", required=True, choices=lines.FLAGS)
    p = mode("sweep")
    p.add_argument("--answered", required=True, metavar="ID")
    p = mode("close", line=True)
    p.add_argument("--sentence", metavar="TEXT", help="the user's sentence, quoted")
    p.add_argument("--by-answer", metavar="ID", help="the answer it was said in")
    mode("reopen", line=True)
    p = mode("touch-flag", line=True)
    p.add_argument("--answer", required=True, metavar="ID")
    p = mode("order")
    weighed(p)
    p.add_argument("--queue-out", metavar="FILE",
                   help="write the queue, [{kind, title}] in order, to FILE")
    p = mode("link")
    p.add_argument("--parent", required=True, metavar="ID")
    p.add_argument("--child", required=True, metavar="ID")
    p = mode("chunk")
    weighed(p)
    p.add_argument("--n", type=int, default=lines.CHUNK, metavar="N")
    p.add_argument("--drop-after", type=int, default=lines.DROP_AFTER, metavar="N")
    p.add_argument("--min-days", type=int, default=lines.MIN_DAYS, metavar="N",
                   help="days before a line shown is shown again")
    p = mode("decide", line=True)
    p.add_argument("choice", choices=lines.CHOICES)
    p.add_argument("--into", metavar="ID")
    p.add_argument("--by-user-word", metavar="TEXT", help="the user's word, quoted")
    return ap


def _json(path: str, what: str):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError) as exc:
        raise lines.Refused(["the %s file cannot be read: %s" % (what, exc)])


def _ground(args):
    if args.outlines:
        return lines.blocks_of_outlines(args.outlines)
    return _json(args.blocks, "blocks") if args.blocks else None


def _shares(args):
    """The shares, and each project's root's share by the project's name."""
    if not args.graph and not args.shares:
        return {}, {}
    if args.graph:
        graph = cli.load_graph(args.graph)
        if graph is None:
            raise lines.Refused(["the graph cannot be read"])
        carried = share.shares(graph)
        roots = lines.Roots({name: carried.get(found[0], 0.0)
                             for name, found in project.candidates(graph).items()
                             if name and found},
                            of={q.id: q.project or None for q in graph.questions})
        return carried, roots
    try:
        with open(args.shares, encoding="utf-8") as fh:
            return lines.read_shares(fh.read()), {}
    except OSError as exc:
        raise lines.Refused(["the shares file cannot be read: %s" % exc])


def _write_queue(path: str, queue) -> None:
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(queue, fh, indent=1, ensure_ascii=False)
            fh.write("\n")
    except OSError as exc:
        raise lines.Refused(["the queue file cannot be written: %s" % exc])


def _run(found: lines.Lines, args):
    m = args.mode
    if m == "queue":
        return {"queue": lines.queue(found)}
    if m == "sweep":
        return {"answered": args.answered, "lines": lines.sweep(found, args.answered)}
    if m == "moved":
        hit, writes, blind = lines.moved(found, _ground(args), args.at, args.whole)
        return {"moved": hit, "unjudged_anchors": blind, "writes": writes}
    if m == "orphans":
        lines.sound(found, mends=True)
        hit, writes = lines.orphans(found, args.at)
        return {"orphans": hit, "writes": writes}
    if m == "unflag":
        return lines.unflag(found, args.id, args.kind, args.at, _ground(args))
    if m == "close":
        return lines.close(found, args.id, args.sentence, args.by_answer, args.at)
    if m == "reopen":
        return lines.reopen(found, args.id, args.at)
    if m == "touch-flag":
        return lines.touch(found, args.id, args.answer, args.at)
    if m == "order":
        shares, roots = _shares(args)
        done = lines.order(found, shares, args.at, roots)
        if args.queue_out:
            _write_queue(args.queue_out, done.queue)
        return {"order": done.asks, "session_work": done.session, "queue": done.queue,
                "writes": done.writes}
    if m == "override":
        shares, roots = _shares(args)
        entry = lines.override(found, shares, args.taken, args.ground, args.at, args.over,
                               roots)
        log = args.log or lines.log_path(args.records)
        if lines.append_override(log, entry):
            return {"log": log, "appended": entry}
        return {"log": log, "appended": None,
                "already": "the log's last entry is this override: not appended again"}
    if m == "report":
        return lines.report(lines.read_overrides(args.log or lines.log_path(args.records)))
    if m == "link":
        return lines.link(found, args.parent, args.child, args.at)
    if m == "chunk":
        shares, roots = _shares(args)
        shown, writes = lines.chunk(found, shares, args.n, args.at, args.drop_after,
                                    args.min_days, roots)
        return {"shown": shown, "writes": writes}
    return lines.decide(found, args.id, args.choice, args.by_user_word, args.at, args.into)


def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    try:
        versions = _json(args.versions, "versions") if args.mode in WRITING else {}
        if not isinstance(versions, dict):
            raise lines.Refused(["the versions file is not an object"])
        found = lines.read(args.records, versions)
        if args.mode == "check":
            for problem in found.problems:
                print("ERROR %s" % problem)
            if not found.problems:
                n = sum(1 for r in found.records.values() if lines.live(r))
                print("ok: %d line(s), %d open or put" % (len(found.records), n))
            for warning in found.found.warnings:
                print("WARN %s" % warning)
            stray = lines.unplaced(found, _shares(args)[1])
            if stray:
                print("WARN %d live anchored line(s) are of no project: %s; give each its "
                      "project, or check with --graph to take it from its anchors' tabs"
                      % (len(stray), ", ".join(stray)) if not args.graph else
                      "WARN %d live anchored line(s) are of no project: %s; no anchor's tab "
                      "is in a project of the graph, give each its project"
                      % (len(stray), ", ".join(stray)))
            return 1 if found.problems else 0
        out = _run(found, args)
    except lines.Refused as exc:
        stale = getattr(args, "queue_out", None)
        if stale and os.path.exists(stale):
            os.remove(stale)  # no queue is left standing from an earlier order
        for reason in exc.reasons:
            print("REFUSED: %s" % reason, file=sys.stderr)
        return 1
    print(json.dumps(out, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
