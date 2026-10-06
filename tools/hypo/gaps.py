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
from urllib.parse import unquote, urlsplit

from . import text
#: a GitHub address inside a repository: owner/repo, blob|tree, then the ref
#: and the path, which only the checkout can part (a ref may carry a slash)
_GITHUB = re.compile(r"^https://github\.com/([^/]+/[^/]+)/(blob|tree)/(.*)$")

PRESENT, ABSENT, ELSEWHERE, NONE, EVERYTHING = (
    "present", "absent", "not this repository", "no link", "covers everything")


def url_of(link: str) -> str:
    match = text.LINK.search(link or "")
    return match.group(2) if match else (link or "").strip()


def address(link: str, repo: str, files: Iterable[str] = ()) -> Tuple[str, str]:
    """(kind, path) for a link: kind is blob, tree, elsewhere or none.

    The line anchor and the query a GitHub link may carry are not the path,
    and a space in the path is percent-encoded. The ref and the path share
    one run of segments, and a ref may carry a slash, so the path is the
    tail that names something tracked; failing that, what follows the first
    segment.
    """
    url = url_of(link)
    if not url.startswith("http"):
        return "none", ""
    parts = urlsplit(url)
    match = _GITHUB.match("%s://%s%s" % (parts.scheme, parts.netloc, parts.path))
    if not match or match.group(1).lower() != repo.lower():
        return "elsewhere", url
    kind, rest = match.group(2), unquote(match.group(3)).strip("/")
    files = list(files)
    for at in [i for i, c in enumerate(rest) if c == "/"]:
        tail = rest[at + 1:]
        if (kind == "blob" and tail in files) or (
                kind == "tree" and any(f.startswith(tail + "/") for f in files)):
            return kind, tail
    return kind, rest.partition("/")[2]


def status(link: str, repo: str, files: Iterable[str]) -> str:
    files = list(files)
    kind, path = address(link, repo, files)
    if kind == "none":
        return NONE
    if kind == "elsewhere":
        return ELSEWHERE
    if kind == "tree" and not path:
        return EVERYTHING
    if kind == "blob":
        return PRESENT if path in files else ABSENT
    return PRESENT if any(f.startswith(path + "/") for f in files) else ABSENT


def covered(files: Iterable[str], links: Iterable[str], repo: str,
            manifest: dict, canon: Iterable[str]) -> Dict[str, str]:
    """What accounts for each tracked file that something accounts for."""
    why: Dict[str, str] = {}
    files = list(files)
    blobs, trees = set(), []
    for link in links:
        kind, path = address(link, repo, files)
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
    """owner/name from a GitHub remote, in either spelling; a name may carry
    a dot, and the remote a trailing slash."""
    match = re.search(r"github\.com[:/]([^/]+/[^/]+?)(?:\.git)?/?$", remote.strip())
    return match.group(1) if match else None
