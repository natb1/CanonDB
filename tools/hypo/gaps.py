"""The decidable half of a bootstrap round's review, in both directions.

From the notebook to the checkout: for each application, whether the path its
link names is there. From the checkout to the notebook: every tracked file
that no application's link and no manifest entry accounts for, and that is
not canon. Canon on disk is what is under ``canon/``; nothing lists it.
Whether a present thing does what its application says, and
whether an unaccounted file is an undocumented requirement or stale, is read
and never computed; this only says where to look.

A link to a tree covers what is under it, except a link to the repository's
root, which would cover everything and so justifies nothing.
"""

from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional, Tuple

#: ``[text](url)`` — the spelling a page read gives a link
_MD_LINK = re.compile(r"\[[^\]]*\]\(([^)]*)\)")
#: a GitHub address inside a repository: owner/repo, blob|tree, ref, path
_GITHUB = re.compile(r"^https://github\.com/([^/]+/[^/]+)/(blob|tree)/[^/]+/?(.*)$")

PRESENT, ABSENT, ELSEWHERE, NONE, EVERYTHING = (
    "present", "absent", "not this repository", "no link", "covers everything")


def url_of(link: str) -> str:
    match = _MD_LINK.search(link or "")
    return match.group(1) if match else (link or "").strip()


def address(link: str, repo: str) -> Tuple[str, str]:
    """(kind, path) for a link: kind is blob, tree, elsewhere or none."""
    url = url_of(link)
    if not url.startswith("http"):
        return "none", ""
    match = _GITHUB.match(url)
    if not match or match.group(1).lower() != repo.lower():
        return "elsewhere", url
    return match.group(2), match.group(3).strip("/")


def status(link: str, repo: str, files: Iterable[str]) -> str:
    kind, path = address(link, repo)
    if kind == "none":
        return NONE
    if kind == "elsewhere":
        return ELSEWHERE
    files = list(files)
    if kind == "tree" and not path:
        return EVERYTHING
    if kind == "blob":
        return PRESENT if path in files else ABSENT
    return PRESENT if any(f.startswith(path + "/") for f in files) else ABSENT


def covered(files: Iterable[str], links: Iterable[str], repo: str,
            manifest: dict, canon: Iterable[str]) -> Dict[str, str]:
    """What accounts for each tracked file that something accounts for."""
    why: Dict[str, str] = {}
    blobs, trees = set(), []
    for link in links:
        kind, path = address(link, repo)
        if kind == "blob":
            blobs.add(path)
        elif kind == "tree" and path:
            trees.append(path)
    owned = {f: a.get("application", "") for a in manifest.get("applications", [])
             for f in a.get("files", [])}
    canon = set(canon)
    for f in files:
        if f in canon:
            why[f] = "canon"
        elif f in owned:
            why[f] = "manifest: %s" % owned[f]
        elif f in blobs:
            why[f] = "link"
        else:
            tree = next((t for t in trees if f.startswith(t + "/")), None)
            if tree:
                why[f] = "link: %s/" % tree
    return why


def orphans(files: Iterable[str], why: Dict[str, str]) -> List[str]:
    return [f for f in files if f not in why]


#: where canon lives on disk; nothing lists it, the directory says it
CANON_DIR = "canon"


def canon_files(files: Iterable[str]) -> List[str]:
    return [f for f in files if f.startswith(CANON_DIR + "/")]


def repo_of(remote: str) -> Optional[str]:
    match = re.search(r"github\.com[:/]([^/]+/[^/.]+?)(?:\.git)?$", remote.strip())
    return match.group(1) if match else None
