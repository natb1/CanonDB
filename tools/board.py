#!/usr/bin/env python3
"""board.py <mode> <export dir> [ID] --versions FILE [--out DIR] … — the gate on the board of jobs.

A session exports the board's store to a directory, one JSON file per
document at ``<dir>/<collection>/<doc_id>.json``, with a versions file
naming the version of each, and runs a mode over the two:

    init <dir> --notebook ADDR [--cap N] [--max-attempts N]   create meta/board
    add <dir> --jobs FILE --now T             queue the jobs of a jobs file
    next <dir> [--json]                       the runnable jobs, oldest first
    claim <dir> ID --by ADDR --now T          queued to claimed
    done <dir> ID --by ADDR --result FILE --now T   claimed to done, by its claimant
    fail <dir> ID --by ADDR --reason CODE --now T   claimed to failed, by its claimant;
                                              queued or waiting to failed, with
                                              --reason superseded only
    retry <dir> ID --now T                    failed to queued, one more attempt
    release <dir> --older-than SECONDS --now T   claimed and quiet, back to queued
    wait <dir> ID --now T / resume <dir> ID --now T   queued to waiting and back
    status <dir> [--json]                     counts, waits, blocks and fit by kind
    verify <dir>                              the export against the schema

Every mode takes ``--versions FILE``. A writing mode first removes
``<out>/batch.json`` and every ``<out>/write-<n>.json`` (``--out`` defaults
to the export directory), then writes the new ones whole: each document to
be written as ``write-<n>.json``, and ``batch.json``, the writes, each
naming its document's file by ``file_path`` and pinned to the version read,
for the session to send as one batch, entry for entry, so that no document
passes through the session's words. Where nothing needs writing it leaves
no file and says so. A refusal is one ``REFUSED:`` line per reason, leaves no
file and exits 1. ``T`` is an ISO 8601 UTC time such as
``2030-01-02T03:04:05Z``. Nothing here reaches the network or reads a clock.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hypo import board, cli  # noqa: E402

cli.quiet_pipe()

BATCH = "batch.json"
#: each written document's own file: write-<n>.json
WRITE = re.compile(r"write-[0-9]+\.json\Z")
#: the modes that write a batch
WRITING = ("init", "add", "claim", "done", "fail", "retry", "release", "wait", "resume")


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0], epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="mode", required=True)

    def mode(name, *, job=False, now=False):
        p = sub.add_parser(name)
        p.add_argument("export", help="the directory the store was exported to")
        if job:
            p.add_argument("id", help="the job's id, <sitting>-<batch>-<row>-<kind>")
        p.add_argument("--versions", required=True, metavar="FILE",
                       help='{"<collection>/<doc_id>": version} for every exported document')
        if name in WRITING:
            p.add_argument("--out", metavar="DIR",
                           help="where batch.json goes (default: the export)")
        if now:
            p.add_argument("--now", required=True, metavar="T",
                           help="the time, ISO 8601 UTC, as handed in")
        return p

    p = mode("init")
    p.add_argument("--notebook", required=True, metavar="ADDR")
    p.add_argument("--cap", type=int, default=board.CAP_FULL, metavar="N")
    p.add_argument("--max-attempts", type=int, default=board.MAX_ATTEMPTS, metavar="N")
    p = mode("add", now=True)
    p.add_argument("--jobs", required=True, metavar="FILE")
    p = mode("next")
    p.add_argument("--json", action="store_true")
    p = mode("claim", job=True, now=True)
    p.add_argument("--by", required=True, metavar="ADDR")
    p = mode("done", job=True, now=True)
    p.add_argument("--by", required=True, metavar="ADDR", help="the claimant")
    p.add_argument("--result", required=True, metavar="FILE")
    p = mode("fail", job=True, now=True)
    p.add_argument("--by", required=True, metavar="ADDR", help="the claimant")
    p.add_argument("--reason", required=True, metavar="CODE",
                   help=", ".join(board.REASONS))
    mode("retry", job=True, now=True)
    p = mode("release", now=True)
    p.add_argument("--older-than", required=True, type=int, metavar="SECONDS")
    mode("wait", job=True, now=True)
    mode("resume", job=True, now=True)
    p = mode("status")
    p.add_argument("--json", action="store_true")
    mode("verify")
    return ap


def _file(path: str, what: str):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError) as exc:
        raise board.Refused(["the %s file cannot be read: %s" % (what, exc)])


def _writes(found: board.Board, args) -> list:
    m = args.mode
    if m == "init":
        return board.init(found, args.notebook, args.cap, args.max_attempts)
    if m == "add":
        return board.add(found, _file(args.jobs, "jobs"), args.now)
    if m == "claim":
        return board.claim(found, args.id, args.by, args.now)
    if m == "done":
        return board.done(found, args.id, args.by, _file(args.result, "result"), args.now)
    if m == "fail":
        return board.fail(found, args.id, args.by, args.reason, args.now)
    if m == "retry":
        return board.retry(found, args.id, args.now)
    if m == "release":
        writes, left = board.release(found, args.older_than, args.now)
        if left:
            print("%d more quiet claim(s) than one batch takes: send this one, export "
                  "again and release again" % left, file=sys.stderr)
        return writes
    if m == "wait":
        return board.wait(found, args.id, args.now)
    return board.resume(found, args.id, args.now)


def _clear(path: str) -> None:
    """Take off a batch an earlier run left, and the documents it named, so
    that none can be sent for this one."""
    where = os.path.dirname(path) or "."
    try:
        os.remove(path)
    except FileNotFoundError:
        pass
    except OSError as exc:
        raise board.Refused(["the earlier batch at %s cannot be removed: %s" % (path, exc)])
    try:
        names = os.listdir(where)
    except (FileNotFoundError, NotADirectoryError):
        return
    except OSError as exc:
        raise board.Refused(["the earlier batch's directory %s cannot be read: %s"
                             % (where, exc)])
    for name in names:
        if WRITE.match(name):
            try:
                os.remove(os.path.join(where, name))
            except OSError as exc:
                raise board.Refused(["the earlier write %s cannot be removed: %s"
                                     % (name, exc)])


def _dump(path: str, value) -> None:
    """One file, written under another name and moved into place whole."""
    part = path + ".part"
    try:
        with open(part, "w", encoding="utf-8") as fh:
            json.dump(value, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        os.replace(part, path)
    except OSError:
        try:
            os.remove(part)
        except OSError:
            pass
        raise


def _save(path: str, writes: list) -> None:
    """Each document to its own file, then the batch naming them; the batch
    last, so that a batch on disk always names files that are there."""
    where = os.path.abspath(os.path.dirname(path) or ".")
    entries = []
    try:
        os.makedirs(where, exist_ok=True)
        for n, w in enumerate(writes, 1):
            doc = os.path.join(where, "write-%d.json" % n)
            _dump(doc, w["data"])
            entry = {k: v for k, v in w.items() if k != "data"}
            entry["file_path"] = doc
            entries.append(entry)
        _dump(path, entries)
    except OSError as exc:
        for n in range(1, len(writes) + 1):
            try:
                os.remove(os.path.join(where, "write-%d.json" % n))
            except OSError:
                pass
        raise board.Refused(["the batch cannot be written to %s: %s" % (path, exc)])


def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    try:
        path = None
        if args.mode in WRITING:
            path = os.path.join(args.out or args.export, BATCH)
            _clear(path)
        found = board.load(args.export, args.versions)
        if args.mode == "verify":
            for p in found.problems:
                print(p)
            if found.problems:
                return 1
            print("the board verifies: %d job(s)" % len(found.jobs), file=sys.stderr)
            return 0
        if args.mode == "next":
            shown, held = board.runnable(found)
            if args.json:
                print(json.dumps({"runnable": shown, "withheld": held}))
            else:
                for jid in shown:
                    print(jid)
            for jid in held:
                print("withheld by the cap: %s" % jid, file=sys.stderr)
            for jid in board.blocked(found):
                print("blocked by a failed job: %s" % jid, file=sys.stderr)
            return 0
        if args.mode == "status":
            counted = board.status(found)
            if args.json:
                print(json.dumps(counted, indent=2))
            else:
                for line in board.status_lines(counted):
                    print(line)
            return 0
        writes = _writes(found, args)
        if not writes:
            print("nothing to write")
            return 0
        _save(path, writes)
    except board.Refused as exc:
        for reason in exc.reasons:
            print("REFUSED: %s" % reason)
        return 1
    for w in writes:
        print("%s %s/%s%s" % (w["op"], w["collection"], w["doc_id"],
                              " if_version %d" % w["if_version"] if "if_version" in w
                              else " (new)"))
    print("wrote %s: %d write(s)" % (path, len(writes)), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
