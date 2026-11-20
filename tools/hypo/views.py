"""views — the whole-tab reads a helper made, lifted out of its transcript.

A helper that fetches tabs has no way to save what it read: the document
connector returns a tab's view into the conversation and nowhere else. The
harness keeps each helper's conversation as a JSON-lines transcript, one
message a line, so what the helper read is on disk after all, and this
lifts it out: each read tab into a file of its own, which ``page.py`` takes
as it takes a read a session saved itself. Nothing is read from the
document; only the transcript, and the files it names.

A read is a call of the connector's read tool in an assistant message, by
either spelling of its name (both end in ``Claude_Docs__read``); what it
asked is its ``ref`` (the object and its id) and its ``payload`` kind, each
of which may arrive as an object or as a JSON string. Its answer is the
tool result that carries the call's id, and the read's object is the first
text part of that result that decodes as a JSON object, whatever text
follows the object. A result too large for the conversation is replaced by
the harness's short text, ``… Output has been saved to <path>.``; only a
result that holds no object, and only that wording, names a side file. The
file is a JSON list of ``{"type", "text"}`` parts, and the object is taken
from its parts the same way, or it is the bare object itself. A result with
no object and no such wording (a refusal, an error) saved nothing and is
passed over, leaving any read before it; a side file that cannot be read,
or that yields no object, is an error, since the read it held is then
unknown.

What is kept: a ``view`` of a node, under ``("node", <node id>)``; a read of
a project (the tab list) that is not a search, under ``("project",
<project id>)``. Which of the two a read was is the read's own object,
carried through, never a name's spelling. A search, and any other kind of
node read, is passed over, and so is a view whose object carries no xml.
Where one node was viewed more than once the last view wins, except a view
that carries a ``from`` cursor and follows a view of the same node that
says it is not complete: that one continues it, and the two are joined:

- ``data.xml`` is the first piece's xml without its closing ``</doc>``,
  then the second's without its opening ``<doc …>`` tag;
- every other key of ``data`` is the second piece's (so ``complete``, and
  any cursor, are the last piece's);
- every key outside ``data`` (the verdict, the rev the read answered with)
  is the first piece's.

A chain of pieces joins the same way, one at a time. A join is refused,
naming the node, unless every piece's ``<doc>`` tag carries the same
``node`` and the same ``rev`` (a write built from the file names the rev
the tag gives, and half a tab read at another is not that read); a piece
that repeats one before it in the chain, by its cursor or by its content,
is refused rather than joined twice or dropped; and the joined xml must
parse and hold no block id twice. A node whose last piece still says it is
not complete is refused, and so is a view with a ``from`` cursor that has
no incomplete piece before it to continue: either would be saved as less
than the whole tab.

Which piece continues which. A view that carries ``from`` is always read
as a continuation. A view that carries any other key besides ``kind`` and
``sinceRev`` is one too where it follows a view of the same node that says
it is not complete, whatever the cursor's key is called; where nothing
incomplete comes before it, it is a read of its own.

A tab list is saved in the shape ``read.py`` takes as the document read:
where the tool's result holds the list under ``data``, what ``data`` holds
is lifted to the top, beside every other key of the result (``frame``
among them), so ``value``, ``files`` and ``frame`` stand where ``read.py``
looks for them. ``doc_names`` reads that shape and no other.

A file's name is the node id, ``doc-<project id>``, or a name given for
the node; the project id is the trailing id of what the read was handed
(a bare id, a link, or a titled link ``…/<title>-<id>``). Only a name of
``NAME``'s letters is ever a file name, so that a name a transcript or a tab
carries cannot reach outside the out dir.
"""

from __future__ import annotations

import json
import os
import re
import xml.etree.ElementTree as ET
from collections import Counter
from typing import Dict, Iterable, Iterator, List, NamedTuple, Optional, Tuple

from . import page

READ_TOOL = "Claude_Docs__read"
#: the harness's wording for a result too large for the conversation
SAVED_TO = re.compile(r"Output has been saved to:?\s+(\S+)")
OPENING = re.compile(r"^\s*<doc\b[^>]*>")
ATTRIBUTE = re.compile(r"""\b(node|rev)\s*=\s*(?:'([^']*)'|"([^"]*)")""")
CLOSING = "</doc>"
#: a document id at the end of a link's last segment: a UUID, or a run of 16
#: or more id characters after the last hyphen of a titled segment
UUID = re.compile(r"[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}$")
TAIL = re.compile(r"(?:^|-)([0-9A-Za-z_]{16,})$")
#: the payload keys a whole view carries that are no cursor
PLAIN = ("kind", "sinceRev")
#: what a file may be called: a name and no path
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")
BLOCKS = ("paragraph", "list", "listItem", "table", "blockquote")
_DECODER = json.JSONDecoder()

#: what is saved is keyed by the read's object and id
Key = Tuple[str, str]


class Read(NamedTuple):
    """What a read asked: the object (``node`` or ``project``), its id,
    the payload kind, the ``from`` cursor it continues from, if any, and
    every other key of its payload but ``kind`` and ``sinceRev``, if any,
    which is a cursor under another name where an incomplete read of the
    node comes before it."""
    object: str
    id: str
    kind: str
    cursor: Optional[str]
    extra: Optional[str] = None

    @property
    def continues(self) -> bool:
        return self.cursor is not None


class Lifted(NamedTuple):
    """What a transcript gave: the object to save by its key, every error,
    each naming its node, and the key of every read refused."""
    saved: Dict[Key, dict]
    errors: List[str]
    refused: List[Key]


def name_of(key: Key) -> str:
    """A read's file name before any other is given: ``<node id>``, or
    ``doc-<project id>`` for a tab list."""
    kind, ident = key
    return "doc-%s" % trailing_id(ident) if kind == "project" else ident


def trailing_id(value: str) -> str:
    """A document's id as a file may carry it: the trailing id of the last
    path segment of a link, without a query or a fragment; a bare id as it
    is."""
    text = value.strip().split("#", 1)[0].split("?", 1)[0].rstrip("/")
    segment = text.rsplit("/", 1)[-1]
    found = UUID.search(segment)
    if found:
        return found.group(0)
    found = TAIL.search(segment)
    return found.group(1) if found else segment


def bad_name(name: str) -> bool:
    """Whether a name cannot be a file's: anything but ``NAME``'s letters."""
    return not NAME.match(name)


def arguments(value) -> dict:
    """An argument as an object, whether it arrived as one or as JSON text;
    anything else is empty."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return {}
    return value if isinstance(value, dict) else {}


def asked(call: dict) -> Optional[Read]:
    """What a ``tool_use`` part asked, where it is a read of the connector."""
    if not str(call.get("name", "")).endswith(READ_TOOL):
        return None
    given = arguments(call.get("input"))
    ref, payload = arguments(given.get("ref")), arguments(given.get("payload"))
    cursor = payload.get("from")
    rest = {k: v for k, v in payload.items() if k not in PLAIN and k != "from"}
    return Read(str(ref.get("object", "")), str(ref.get("id", "")),
                str(payload.get("kind", "")),
                None if cursor is None else json.dumps(cursor, sort_keys=True),
                json.dumps(rest, sort_keys=True) if rest else None)


def first_object(texts: Iterable[str]) -> Optional[dict]:
    """The first text that opens with a JSON object, decoded; what follows
    the object is not read."""
    for words in texts:
        words = words.lstrip()
        if not words.startswith("{"):
            continue
        try:
            found, _ = _DECODER.raw_decode(words)
        except ValueError:
            continue
        if isinstance(found, dict):
            return found
    return None


def texts_of(content) -> List[str]:
    """A result's text parts: a list of parts, or a bare string."""
    if isinstance(content, str):
        return [content]
    if isinstance(content, list):
        return [p["text"] for p in content
                if isinstance(p, dict) and isinstance(p.get("text"), str)]
    return []


def side_file(texts: Iterable[str]) -> Optional[str]:
    """The path a result too large for the conversation was saved to, as
    the harness's wording names it; a full stop or a bracket that ends the
    sentence is not part of the path."""
    for words in texts:
        found = SAVED_TO.search(words)
        if found:
            path = found.group(1)
            return path if os.path.exists(path) else path.rstrip(".,;:)'\"")
    return None


def answer(content) -> Tuple[Optional[dict], Optional[str]]:
    """A result's object, and an error where the side file it names cannot
    be read."""
    texts = texts_of(content)
    found = first_object(texts)
    if found is not None:
        return found, None
    path = side_file(texts)
    if path is None:
        return None, None
    try:
        with open(path, encoding="utf-8") as fh:
            parts = json.load(fh)
    except (OSError, ValueError) as exc:
        return None, "the result was saved to %s, which cannot be read: %s" % (path, exc)
    if isinstance(parts, dict) and not (parts.get("type") == "text"
                                        and isinstance(parts.get("text"), str)):
        return parts, None
    found = first_object(texts_of([parts] if isinstance(parts, dict) else parts))
    if found is None:
        return None, "the result was saved to %s, which holds no object" % path
    return found, None


def reads(lines: Iterable[str]) -> Iterator[Tuple[Read, Optional[dict], Optional[str]]]:
    """Each read the transcript answers, in its order, with its object and
    any error; a line that is not JSON is skipped."""
    calls: Dict[str, Read] = {}
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        message = row.get("message") if isinstance(row, dict) else None
        if not isinstance(message, dict) or not isinstance(message.get("content"), list):
            continue
        for part in message["content"]:
            if not isinstance(part, dict):
                continue
            if part.get("type") == "tool_use" and message.get("role") == "assistant":
                read = asked(part)
                if read is not None and part.get("id"):
                    calls[part["id"]] = read
            elif part.get("type") == "tool_result" and part.get("tool_use_id") in calls:
                found, error = answer(part.get("content"))
                yield calls[part["tool_use_id"]], found, error


def data_of(view: dict) -> dict:
    data = view.get("data")
    return data if isinstance(data, dict) else {}


def complete(view: dict) -> bool:
    """Whether a view holds the whole tab; one that does not say holds it."""
    return data_of(view).get("complete") is not False


def tag_of(view: dict) -> Dict[str, str]:
    """The ``node`` and ``rev`` the view's opening ``<doc>`` tag carries."""
    found = OPENING.match(data_of(view).get("xml", ""))
    if not found:
        return {}
    return {m.group(1): m.group(2) if m.group(2) is not None else m.group(3)
            for m in ATTRIBUTE.finditer(found.group(0))}


def unjoinable(chain: List[Tuple[Optional[str], dict]], cursor: Optional[str],
               piece: dict) -> Optional[str]:
    """Why ``piece``, read from ``cursor``, cannot continue ``chain`` (each
    piece before it with its cursor), or None where it can."""
    tag = tag_of(piece)
    if not tag.get("node") or not tag.get("rev"):
        return "a continued piece whose <doc> tag carries no node or no rev"
    for at, before in chain:
        if tag_of(before) != tag:
            return ("pieces of a continued read at different tabs or revs: %s and %s"
                    % (_tagged(tag_of(before)), _tagged(tag)))
        if at == cursor:
            return "a piece read twice from the cursor %s" % cursor
        if data_of(before).get("xml") == data_of(piece).get("xml"):
            return "a piece of a continued read that repeats one before it"
    return None


def _tagged(tag: Dict[str, str]) -> str:
    return "node %s rev %s" % (tag.get("node", "?"), tag.get("rev", "?"))


def unsound(view: dict) -> Optional[str]:
    """Why a joined view is not a whole tab: xml that does not parse, or a
    block id held twice; None where it is sound."""
    try:
        root = ET.fromstring(data_of(view).get("xml", ""))
    except ET.ParseError as exc:
        return "the joined pieces do not parse: %s" % exc
    ids = Counter(bid for node, bid in page.full_ids(root).items()
                  if bid and node.tag in BLOCKS)
    twice = sorted(bid for bid, n in ids.items() if n > 1)
    if twice:
        return "the joined pieces hold a block twice: %s" % ", ".join(twice)
    return None


def join(first: dict, second: dict) -> dict:
    """A view continued by the next piece, as the module's docstring says."""
    head = data_of(first).get("xml", "").rstrip()
    if head.endswith(CLOSING):
        head = head[:-len(CLOSING)]
    tail = OPENING.sub("", data_of(second).get("xml", ""), count=1)
    out = dict(first)
    out["data"] = dict(data_of(second), xml=head + tail)
    return out


def lift(lines: Iterable[str]) -> Lifted:
    """Every tab and tab list the transcript read, by its key."""
    saved: Dict[Key, dict] = {}
    errors: Dict[Key, str] = {}
    chains: Dict[Key, List[Tuple[Optional[str], dict]]] = {}
    for read, found, error in reads(lines):
        if read.kind == "search":
            continue
        if read.object not in ("project", "node") or (
                read.object == "node" and read.kind != "view"):
            continue
        key = (read.object, read.id)
        if error:
            # what came before is no longer known to be the last read
            errors[key] = error
            saved.pop(key, None)
            chains.pop(key, None)
            continue
        if found is None:
            continue
        if read.object == "node" and "xml" not in data_of(found):
            continue
        before = saved.get(key)
        cursor = read.cursor
        if cursor is None and read.extra is not None and before is not None \
                and not complete(before):
            # a cursor under a name other than ``from``, after a read that
            # said there is more: it continues that read, never replaces it
            cursor = read.extra
        if cursor is not None and read.object == "node":
            if before is None or complete(before):
                # a chain refused already keeps the reason it was refused for
                errors[key] = (errors.get(key) or "a read continued from a cursor with "
                               "no incomplete read before it")
                saved.pop(key, None)
                chains.pop(key, None)
                continue
            why = unjoinable(chains.get(key, []), cursor, found)
            if why:
                errors[key] = why
                saved.pop(key, None)
                chains.pop(key, None)
                continue
            saved[key] = join(before, found)
            chains[key].append((cursor, found))
        else:
            saved[key] = tab_list(found) if read.object == "project" else found
            chains[key] = [(None, found)]
        errors.pop(key, None)
    for key, got in list(saved.items()):
        if key[0] != "node":
            continue
        why = None if complete(got) else "its last piece is still not complete"
        if why is None and len(chains.get(key, [])) > 1:
            why = unsound(got)
        if why:
            errors[key] = why
            del saved[key]
    return Lifted(saved, ["%s: %s" % (name_of(k), errors[k]) for k in sorted(errors)],
                  sorted(errors))


def tab_list(found: dict) -> dict:
    """A read of the tab list in the shape ``read.py`` takes: where the
    result holds ``files`` or ``value`` under ``data``, what ``data`` holds
    lifted to the top beside the result's other keys; else as it is."""
    data = found.get("data")
    if not (isinstance(data, dict) and ("files" in data or "value" in data)):
        return found
    out = {k: v for k, v in found.items() if k != "data"}
    out.update(data)
    return out


def doc_names(saved: dict) -> Dict[str, str]:
    """node id -> name, from a saved read of the document's tab list in the
    shape ``read.py`` takes, the one ``tab_list`` gives: each entry of
    ``files`` is a tab (``id``) and the node that is its body
    (``content.id``), and the tab's name is ``value.tabs[<tab>].name``, the
    tab id where it has none."""
    value = saved.get("value", saved)
    tabs = value.get("tabs", {}) if isinstance(value, dict) else {}
    out: Dict[str, str] = {}
    for entry in saved.get("files", []) or []:
        if not isinstance(entry, dict):
            continue
        tab = str(entry.get("id", ""))
        content = entry.get("content")
        body = str(content.get("id", "")) if isinstance(content, dict) else ""
        if tab and body:
            meta = tabs.get(tab)
            out[body] = str(meta.get("name", tab)) if isinstance(meta, dict) else tab
    return out


def names(path: str) -> Dict[str, str]:
    """node id -> name, from a tab-separated file whose second column is a
    name and fifth a node id; a line with fewer columns is passed over."""
    out: Dict[str, str] = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            cols = line.rstrip("\n").split("\t")
            if len(cols) >= 5 and cols[1].strip() and cols[4].strip():
                out[cols[4].strip()] = cols[1].strip()
    return out
