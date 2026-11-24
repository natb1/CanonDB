"""ai_tab — the tabs of the AI's own record: made, and named in the key that holds them.

The AI's own record stands under a root of its own in the notebook, and the
key ``ai_root`` of ``.principal/notebook.json`` lists its tabs, the root's
first. The notebook's guard (``hooks/notebook-gate.py``) reads that key: the
``ai-recorder`` inserts on the tabs it lists, and makes a new tab only under
one whose tab id it gives; the speaker makes the root once, while the key is
unset. This module prints the one batch either sends, and writes the key.

**The batch.** A tab is made by four calls of one ``batch`` of the
notebook, the shape the connector gives for adding a tab and the only one the
guard admits: the tab's file created, named ``<name>.ldoc``, its body
created as the tab's heading ``# <name>`` and nothing else, the body set as
the file's content, and the new tab's placement set in the document's
``tabs``, nested under the parent's tab id by ``subtabOf``; the root stands
at the top level. What the tab says is inserted on it after, as on any tab
of the AI's. The operation id is fixed by what is made: a root by the
notebook's id alone, so that a second root sent lands as the first; a tab by
its parent's tab id and its name.

**The key.** Each entry this module writes is ``{"node": <the body's node
id>, "tab": <the tab's own id>}``: the node id is what an ``update`` names,
the tab id what a new tab is nested under. An entry that is a bare node id,
as the key was first written, is still read, and no tab can be made under
it. An entry is added only from the batch this module printed, printed again
from the key as it stands now and found the same, so that the parent it was
made under is one the key gives (the root only while the key is unset), and
from the connector's answer to that batch, whose ids for the aliases ``f``
and ``n`` are the entry's; never an id the key holds already. That those
ids are the ones the connector made is not checked here, having no live
notebook: the tab is read back for that.

Nothing here reaches the network or writes the notebook.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from typing import List, Optional, Tuple

KEY = "ai_root"
NOTEBOOK = os.path.join(".principal", "notebook.json")

#: a tab's name, which the reader takes as a question's id
NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
#: tabs a notebook keeps that are no question (``model.RESERVED``)
RESERVED = ("lease",)
#: an id the guard takes from the key: plain letters, digits, ``_`` and ``-``
PLAIN_ID = re.compile(r"^[A-Za-z0-9_-]+$")
#: a tab's place among its siblings, as the connector orders them
ORDER = re.compile(r"^[a-z][0-9a-z]*$")
#: the id at the end of a document's address
UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
TAIL = re.compile(r"(?:^|-)([0-9a-z_]{16,})$")


class Refused(ValueError):
    """A tab or an entry this module will not print or write."""


def find(cwd: str, env=None) -> str:
    """The notebook file the guard reads: under ``CLAUDE_PROJECT_DIR`` where
    it is set and holds one, else the nearest from ``cwd`` upward."""
    env = os.environ if env is None else env
    project = env.get("CLAUDE_PROJECT_DIR")
    if project and os.path.isfile(os.path.join(project, NOTEBOOK)):
        return os.path.join(project, NOTEBOOK)
    here = os.path.abspath(cwd)
    while True:
        path = os.path.join(here, NOTEBOOK)
        if os.path.isfile(path):
            return path
        up = os.path.dirname(here)
        if up == here:
            raise Refused("no %s here or above" % NOTEBOOK)
        here = up


def load(path: str) -> dict:
    try:
        with open(path, encoding="utf-8-sig") as fh:
            named = json.load(fh)
    except (OSError, ValueError) as exc:
        raise Refused("%s cannot be read: %s" % (path, exc)) from exc
    if not isinstance(named, dict) or not named.get("artifact"):
        raise Refused("%s names no document" % path)
    return named


def document(named: dict) -> str:
    """The notebook's id, the trailing id of its address."""
    text = str(named["artifact"]).strip().split("#", 1)[0].split("?", 1)[0].rstrip("/")
    segment = text.rsplit("/", 1)[-1].lower()
    found = UUID.search(segment) or TAIL.search(segment)
    if not found:
        raise Refused("the notebook's address holds no id")
    return found.group(found.lastindex or 0)


def entries(named: dict) -> List[Tuple[str, Optional[str]]]:
    """The key's entries, each (node id, tab id or None), as the guard reads
    them; refused where the key is not one of its shapes."""
    value = named.get(KEY)
    if value is None or value == "" or value == []:
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        raise Refused("the key %s is not a list" % KEY)
    out = []
    for entry in value:
        if isinstance(entry, str) and entry.strip():
            out.append((entry.strip(), None))
        elif (isinstance(entry, dict) and set(entry) == {"node", "tab"}
              and all(isinstance(entry[k], str) and entry[k].strip() for k in entry)):
            out.append((entry["node"].strip(), entry["tab"].strip()))
        else:
            raise Refused("an entry of the key %s is neither a node id nor "
                          "{\"node\": …, \"tab\": …}" % KEY)
    return out


def plain_id(value: str, what: str) -> str:
    if not isinstance(value, str) or not PLAIN_ID.match(value):
        raise Refused("%s %r is not a plain id (letters, digits, _ and -)" % (what, value))
    return value


def check_name(name: str) -> str:
    if not isinstance(name, str) or not NAME.match(name) or name in RESERVED:
        raise Refused("a tab's name is a question's id: lower-case letters and digits in "
                      "words joined by -, and not %s; got %r" % (" or ".join(RESERVED), name))
    return name


def check_order(order: str) -> str:
    if not isinstance(order, str) or not ORDER.match(order):
        raise Refused("an order is a letter and then letters or digits, as a0; got %r"
                      % (order,))
    return order


def op_id(*parts: str) -> str:
    """An operation id fixed by what the batch makes, so that a batch sent
    twice lands once."""
    digest = hashlib.sha256("\x00".join(parts).encode("utf-8")).hexdigest()[:16]
    return "ai-tab-" + digest


def batch(notebook: str, name: str, order: str, under: Optional[str]) -> dict:
    """The container and the four calls of one batch that make one tab of
    the notebook named ``name``, its body its heading alone, and place it,
    under the tab id ``under`` where one is given."""
    check_name(name)
    check_order(order)
    if under is not None:
        plain_id(under, "the parent's tab id")
    text = "# %s" % name
    birth = name + ".ldoc"
    where = {"name": name, "order": order}
    if under is not None:
        where["subtabOf"] = under
    return {
        "container": {"kind": "project", "id": notebook},
        "batch": [
            {"$lid": "f", "verb": "create", "object": "file",
             "payload": {"value": {"birthName": birth}}},
            {"$lid": "n", "verb": "create", "object": "node", "engine": "prose",
             "payload": {"parent": {"object": "file", "id": "$lid:f"},
                         "source": {"as": "markdown",
                                    "from": {"kind": "inline", "content": text}}}},
            {"verb": "update", "ref": {"object": "file", "id": "$lid:f"},
             "payload": {"kind": "value",
                         "value": {"birthName": birth,
                                   "content": {"kind": "node", "id": "$lid:n"}}}},
            {"verb": "update", "ref": {"object": "project", "id": notebook},
             "payload": {"kind": "patch", "patch": [
                 {"op": "set", "path": ["tabs", "$lid:f"], "value": where}]}},
        ],
    }


def root(named: dict, name: str, order: str) -> dict:
    """The speaker's batch that makes the AI's root at the top level,
    refused once the key names one; as the ``batch`` call's arguments, with
    the one ``opId`` every root of this notebook is sent with."""
    if entries(named):
        raise Refused("the key %s names a root already; the root is made once" % KEY)
    notebook = document(named)
    out = batch(notebook, name, order, None)
    out["opId"] = op_id("root", notebook)
    return out


def tab(named: dict, parent: str, name: str, order: str) -> dict:
    """The rows entry for the ``ai-recorder`` that makes a tab under the
    tab of the AI's whose node id is ``parent``: its node, the batch's
    container and calls, and the operation id."""
    plain_id(parent, "the parent's node id")
    found = {node.lower(): t for node, t in entries(named)}
    if not found:
        raise Refused("the key %s is unset: the root is made first" % KEY)
    if parent.lower() not in found:
        raise Refused("the key %s lists no tab %r" % (KEY, parent))
    under = found[parent.lower()]
    if under is None:
        raise Refused("the key %s gives no tab id for %r, so nothing can be made under it; "
                      "write its entry as {\"node\": …, \"tab\": …}" % (KEY, parent))
    return {"node": parent, "batch": batch(document(named), name, order, under),
            "op_id": op_id("tab", under, name)}


def _placed(call: dict) -> dict:
    """The placement a printed batch sets: the tab's name and order."""
    try:
        return call["batch"][3]["payload"]["patch"][0]["value"]
    except (KeyError, IndexError, TypeError) as exc:
        raise Refused("that is no batch this tool printed") from exc


def lids(answer) -> Tuple[str, str]:
    """The ids the connector's answer to a batch gives its aliases ``f``
    and ``n``, under a key ``lids`` at its top or within it."""
    stack = [answer]
    while stack:
        part = stack.pop(0)
        if isinstance(part, dict):
            got = part.get("lids")
            if isinstance(got, dict) and isinstance(got.get("f"), str) and isinstance(
                    got.get("n"), str):
                return got["f"], got["n"]
            stack.extend(part.values())
        elif isinstance(part, list):
            stack.extend(part)
    raise Refused("the answer gives no ids under lids for the aliases f and n")


#: what ``add`` says it could not check
UNCHECKED = ("not checked, there being no live notebook here: that the tab %s and the body "
             "%s are the ones the connector made for this batch; read the tab back to see it")


def add(named: dict, made: dict, answer) -> Tuple[dict, str]:
    """The notebook file with a tab put in the key, and the line that says
    what was not checked. ``made`` is what this tool printed, the root's
    batch or a tab's rows entry, and it must be what the tool prints from
    the key as it stands now; ``answer`` the connector's answer to it."""
    if not isinstance(made, dict):
        raise Refused("that is no batch this tool printed")
    have = entries(named)
    if "node" in made:
        call = made.get("batch")
        where = _placed(call)
        again = tab(named, made["node"], where.get("name"), where.get("order"))
        if again != made:
            raise Refused("the entry is not the one this tool prints from the key as it "
                          "stands, so the tab it made is not under a tab the key gives")
    else:
        where = _placed(made)
        if have:
            raise Refused("the key %s names a root already" % KEY)
        if root(named, where.get("name"), where.get("order")) != made:
            raise Refused("the batch is not the root this tool prints")
    tab_id, node = lids(answer)
    plain_id(node, "the body's node id")
    plain_id(tab_id, "the tab id")
    if node.lower() == tab_id.lower():
        raise Refused("the answer gives one id for the tab and its body")
    held = {n.lower() for n, _ in have} | {(t or "").lower() for _, t in have}
    if node.lower() in held or tab_id.lower() in held:
        raise Refused("the key %s lists that tab already" % KEY)
    out = dict(named)
    out[KEY] = [n if t is None else {"node": n, "tab": t} for n, t in have] + [
        {"node": node, "tab": tab_id}]
    return out, UNCHECKED % (tab_id, node)


def write(path: str, named: dict) -> None:
    """The notebook file written whole, through a file beside it."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(named, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, path)
