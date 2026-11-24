#!/usr/bin/env python3
"""sensitive.py pr NUMBER [--repo OWNER/NAME] | range REVS [-C DIR] | text FILE... | where — audit what already left.

    sensitive.py pr 42 [--repo natb1/CanonDB]
    sensitive.py range origin/main..HEAD [-C DIR]
    sensitive.py text FILE...
    sensitive.py where

Reads what has already gone to a repository against the private list of
sensitive information the user reports (`hypo/sensitive.py`: one pattern a
line, at `<config home>/principal/sensitive.txt`, or `$PRINCIPAL_SENSITIVE`),
the list the convention gate holds every repository-bound write to.

`pr` reads a pull request by `gh`: its title and body, every comment, every
review's body, every review comment on a line, every commit's message, and
the lines its diff adds. `range` reads a commit range by `git log` (any
revisions `git log` takes): each commit's message, and the lines each commit
adds, so that a line added and later taken out is still found. `text` reads
files whole. `where` prints the list's path.

Each match prints one line, the place (a field, or a file and line, with the
commit) and the pattern's line number in the list, and never the matched
text or the pattern. Exit 0 with nothing found, 1 on a match, 2 where the
list is missing or what was asked for cannot be read.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hypo import cli  # noqa: E402
from hypo import sensitive as listed  # noqa: E402

cli.quiet_pipe()


class Unread(Exception):
    pass


def _run(argv, cwd=None) -> str:
    try:
        done = subprocess.run(argv, cwd=cwd, capture_output=True, timeout=300)
    except (OSError, subprocess.SubprocessError) as exc:
        raise Unread("%s: %s" % (argv[0], type(exc).__name__))
    if done.returncode != 0:
        raise Unread("%s exited %d: %s" % (" ".join(argv[:3]), done.returncode,
                                           done.stderr.decode("utf-8", "replace").strip()[:300]))
    return done.stdout.decode("utf-8", errors="replace")


def _gh(args, repo):
    return _run(["gh"] + args + (["--repo", repo] if repo else []))


def pr(patterns, number, repo):
    view = json.loads(_gh(["pr", "view", str(number), "--json",
                           "title,body,comments,reviews,commits"], repo))
    fields = {"title": view.get("title") or "", "body": view.get("body") or ""}
    for i, c in enumerate(view.get("comments") or [], 1):
        fields["comment %d" % i] = c.get("body") or ""
    for i, r in enumerate(view.get("reviews") or [], 1):
        fields["review %d" % i] = r.get("body") or ""
    for c in view.get("commits") or []:
        oid = (c.get("oid") or "")[:12]
        fields["commit %s message" % oid] = "%s\n\n%s" % (c.get("messageHeadline") or "",
                                                          c.get("messageBody") or "")
    path = "repos/%s/pulls/%s/comments" % (repo or "{owner}/{repo}", number)
    inline = json.loads(_run(["gh", "api", "--paginate", "--slurp", path]))
    flat = [c for page in inline for c in (page if isinstance(page, list) else [page])]
    for i, c in enumerate(flat, 1):
        fields["review comment %d (%s)" % (i, c.get("path") or "?")] = c.get("body") or ""
    found = ["%s: pattern on line %d" % (f, n) for f, n in listed.scan_fields(patterns, fields)]
    diff = _gh(["pr", "diff", str(number)], repo)
    found += ["%s:%d (diff): pattern on line %d" % (f, line, n)
              for f, line, n in listed.scan_diff(patterns, diff)]
    return found


def commit_range(patterns, revs, where):
    found = []
    log = _run(["git", "log", "--format=%H%x1f%B%x1e", revs], cwd=where)
    for record in log.split("\x1e"):
        record = record.strip("\n")
        if not record:
            continue
        oid, _, message = record.partition("\x1f")
        for _, n in listed.scan_fields(patterns, {"m": message}):
            found.append("commit %s message: pattern on line %d" % (oid[:12], n))
    patches = _run(["git", "log", "--format=%x1e%H", "-p", "-U0", "--no-color", "--no-ext-diff",
                    revs], cwd=where)
    for record in patches.split("\x1e"):
        oid, _, diff = record.partition("\n")
        for f, line, n in listed.scan_diff(patterns, diff):
            found.append("commit %s %s:%d: pattern on line %d" % (oid[:12], f, line, n))
    return found


def text(patterns, files):
    found = []
    for name in files:
        try:
            with open(name, encoding="utf-8", errors="replace") as fh:
                lines = fh.read().splitlines()
        except OSError as exc:
            raise Unread("%s: %s" % (name, exc.strerror))
        for number, line in enumerate(lines, 1):
            for n in listed.matches(patterns, line):
                found.append("%s:%d: pattern on line %d" % (name, number, n))
    return found


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="mode", required=True)
    p = sub.add_parser("pr")
    p.add_argument("number")
    p.add_argument("--repo")
    r = sub.add_parser("range")
    r.add_argument("revs")
    r.add_argument("-C", dest="where")
    t = sub.add_parser("text")
    t.add_argument("files", nargs="+")
    sub.add_parser("where")
    args = parser.parse_args(argv)
    if args.mode == "where":
        print(listed.path(os.environ))
        return 0
    patterns = listed.load(os.environ)
    if patterns is None:
        print("no list at %s: nothing was checked" % listed.path(os.environ), file=sys.stderr)
        return 2
    if patterns.broken:
        print(listed.broken(patterns), file=sys.stderr)
    try:
        if args.mode == "pr":
            found = pr(patterns, args.number, args.repo)
        elif args.mode == "range":
            found = commit_range(patterns, args.revs, args.where)
        else:
            found = text(patterns, args.files)
    except (Unread, ValueError) as exc:
        print("could not read: %s" % exc, file=sys.stderr)
        return 2
    for line in found:
        print(line)
    print("%d match(es) against %d pattern(s)" % (len(found), len(patterns.patterns)),
          file=sys.stderr)
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
