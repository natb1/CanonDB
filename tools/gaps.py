#!/usr/bin/env python3
"""gaps.py APPS [--root DIR] [--repo OWNER/NAME] — a bootstrap round's review, both ways.

APPS is a JSON list of the applications the round read off the page, each
{"tab", "name", "link"} with the link as the page read spells it. Prints, per
application, whether its link's path is in the checkout; then every tracked
file that no link, no entry of `.principal/bootstrap.json` and no line of
`.principal/canon` accounts for. Paths and verdicts only; what the files are
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
    files = subprocess.run(["git", "-C", root, "ls-files"], capture_output=True,
                           text=True, check=True).stdout.split()
    repo = args.repo or gaps.repo_of(subprocess.run(
        ["git", "-C", root, "remote", "get-url", "origin"],
        capture_output=True, text=True).stdout) or ""
    apps = json.loads(_read(args.apps, "[]"))
    manifest = json.loads(_read(os.path.join(root, ".principal", "bootstrap.json"), "{}"))
    canon = gaps.canon_list(_read(os.path.join(root, ".principal", "canon")))

    print("applications (%s):" % (repo or "no origin"))
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
