#!/usr/bin/env python3
"""gaps.py APPS [--root DIR] [--repo OWNER/NAME] — a bootstrap round's review, both ways.

APPS is a JSON list of the applications the round read off the page, each
{"tab", "name", "link"} with the link as the page read spells it. Prints, per
application, whether its link's path is in the checkout; then every tracked
file that no link and no entry of `.principal/bootstrap.json` accounts for,
and that is not canon, which is what is under `canon/`. Paths and verdicts only; what the files are
is for the round to read.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hypo import cli, gaps  # noqa: E402

cli.quiet_pipe()


def _read(path: str, default: str = "") -> str:
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return default


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("apps")
    ap.add_argument("--root", default=".")
    ap.add_argument("--repo", help="owner/name of this repository (else origin's)")
    args = ap.parse_args(argv)

    root = os.path.abspath(args.root)
    # NUL-parted: a path with a space in it is one path, and one with a letter
    # outside ASCII is spelled as itself and not in git's quoted form
    files = [f for f in subprocess.run(["git", "-C", root, "ls-files", "-z"], capture_output=True,
                                       text=True, check=True).stdout.split("\0") if f]
    repo = args.repo or gaps.repo_of(subprocess.run(
        ["git", "-C", root, "remote", "get-url", "origin"],
        capture_output=True, text=True).stdout) or ""
    try:  # the manifest may be absent; the list this round wrote may not
        with open(args.apps, encoding="utf-8") as fh:
            apps = json.load(fh)
    except (OSError, ValueError) as exc:
        print("ERROR apps: %s" % exc, file=sys.stderr)
        return 1
    if not isinstance(apps, list) or not all(isinstance(a, dict) for a in apps):
        print("ERROR apps: %s is not a list of applications, each an object with its "
              "tab, name and link" % args.apps, file=sys.stderr)
        return 1
    manifest = json.loads(_read(os.path.join(root, ".principal", "bootstrap.json"), "{}"))
    canon = gaps.canon_files(files)

    print("applications (%s), against %s:" % (repo or "no origin", root))
    for app in apps:
        print("  %-22s %-30s %s" % (app.get("tab", ""), app.get("name", ""),
                                   gaps.status(app.get("link", ""), repo, files)))
    why = gaps.covered(files, [a.get("link", "") for a in apps], repo, manifest, canon)
    lost = gaps.orphans(files, why)
    print("files nothing accounts for: %d" % len(lost))
    for f in lost:
        print("  " + f)
    return 0


if __name__ == "__main__":
    sys.exit(main())
