#!/usr/bin/env python3
"""The notebook's write gate: the recorder writes it, and no other helper.

A PreToolUse hook on the document connector's writing tools, `update`,
`batch`, `create` and `delete`, and its `export`, in both spellings the
surfaces give them, and on `Artifact`, `ArtifactData` and
`ArtifactComments`, installed by the plugin and so fired on every such call
of every turn in a project that has the plugin. Every kind of this plugin but the recorder and
the interviewer is denied the writing tools by its own definition, and the
gate is the second line for those; the interviewer may write a document of
its own, and for it, and for every helper the plugin does not define, the
gate is the only line between it and the notebook.

Who writes. A turn that carries no `agent_type` is the main thread, an entry
point there among them, and gets no opinion: the harness's ordinary
permissions apply. The recorder by this plugin's name in front of it (read
from the plugin's `.claude-plugin/plugin.json`) gets no opinion either: it
is the one writer. By its bare name it is the writer only in a project whose
own `.claude/agents/recorder.md` is byte for byte this plugin's
`agents/recorder.md`, which is how this repository's own checkout defines
it; in any other project a bare `recorder` is a project's or a user's own
agent, and a helper like any other. Where the manifest cannot be read no
name makes the writer but the bare one so defined. Every other turn that
carries an `agent_type` is a helper, whatever defined it, a fork and a
general helper included, and another plugin's name in front of `recorder`
makes no writer.

Which turn is a kind of this plugin is the rule every gate of the plugin
shares, in `kinds.py`: by this plugin's name in front of it; by its bare
name where the project defines it byte for byte as the plugin does, or
names a notebook;
and where the manifest cannot be read, by any name ending `:<kind>`. A kind
of this plugin that holds no writing tool is refused every call of the
connector's writing tools, whatever it names. Any other helper, a project's
own `reviewer` or `coordinator` among them, is refused a call aimed at the
notebook, and a call it names plainly as another document's is not this
gate's. In a project that names a notebook a bare kind's name is the kind
whether or not its copy there is the plugin's (`kinds.py`); a differing
bare `recorder` is then a helper and no writer.

A part of a document. The connector's `update` takes a `ref` to a node, a
file or an utterance, and the connector says the ref may be one of a
document the given document links to: a `ref` of any object but `project`
could reach the notebook from a container that is not it. So a helper other
than the interviewer, the recorder aside, gets the UNCLEAR refusal for any
call that holds such a ref (in the call or in a member of a `batch`) and is
not already refused as aimed at the notebook; it names its own document by
its id and writes it by refs of object `project`. The interviewer writes its
line doc by its nodes and is not held to this: a ref of its that follows a
link into the notebook is a residue, unchecked against the live connector,
and what holds it is its definition and the sitting's entry point.

The other tools. `Artifact`, `ArtifactData`, `ArtifactComments` and the
connector's `export` take an address (`url`, `from_url`, `type_url`, a
published file's `artifact`, or `container.id`), and so does `delete`: every
turn that carries an `agent_type`, the recorder included, is refused a call
of these whose address is the notebook's; a call of the four naming nothing
the gate can read as an id is no opinion. What they would do to the
notebook is not checked here; none is a helper's to do.

The bare recorder's residue, left by decision. Whether the bare name is the
writer is read from the file named `recorder.md` in the project's
`.claude/agents/`, not from the definition the harness resolved: a second
file there whose front matter says `name: recorder`, or an agent given on
the command line, beside an identical `recorder.md`, would be taken for the
writer if the harness prefers it; and with no `CLAUDE_PROJECT_DIR` the
nearest `.claude/agents/recorder.md` from the cwd decides. A missing or
differing project file makes no writer; a link to the plugin's file is the
plugin's file.

Which notebook. The document `.principal/notebook.json` names, read as
`tools/read.py` reads it: under `CLAUDE_PROJECT_DIR` where the harness sets
it, else the nearest of the call's `cwd` and its ancestors, so that a `cd`
does not move the guard. The id is the trailing id of the last path segment
of the file's `artifact`: a bare id, a link, or the connector's titled link
`…/artifact/<title>-<id>`. A project where no such file is found has no
notebook to guard here. That is a residue the gate keeps, by decision: a
session started outside the project, with no `CLAUDE_PROJECT_DIR` in its
environment, finds no notebook file, and the gate then has no opinion even
for the interviewer; what keeps it off the notebook there is its
definition alone, as the sitting's entry point says.

Aimed at it. The fields that address a document are read and nothing else:
`container.id` (a container being of kind `project`), a `ref` of object
`project`, `artifact` on `create`, and for `batch` its container's
`create.artifact` and each member's `ref` and `container`. A field is aimed
at the notebook where its trailing id is the notebook's or the notebook's id
occurs in it, in whatever shape it is written, with or without its hyphens;
and where the field's trailing id, or any part of its last segment after a
hyphen, is with its hyphens removed a beginning of at least `SHORTEST`
characters of the notebook's id with its hyphens removed: an id written
short, or without hyphens, is the notebook's all the same. Before any of
this a field is read as the id it spells: percent-encoding is decoded (to
three levels), compatibility forms are folded (full-width letters and
digits to their plain forms), every Unicode hyphen and dash to `-`, and
zero-width and other invisible characters are dropped. A call that names no document
is one the gate cannot make sense of, except a `batch` whose container
creates a new one.

A guarded turn fails closed: what the gate cannot make sense of, a call or
a notebook file, is refused with a sentence that says what to supply; a call
aimed at the notebook is refused with one that says who writes it. Neither
names a document.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
import unicodedata
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.join(os.path.dirname(HERE), ".claude-plugin", "plugin.json")
#: this plugin's own definitions, which a project's bare kind must match
AGENTS = os.path.join(os.path.dirname(HERE), "agents")


def _sibling(name: str, file: str):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, file))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


#: what the gates take from `kinds.py`; a file without them is no rule
SHARED = ("kind_of", "named_any", "spelled", "plugin_name", "places", "defined_here",
          "consumer", "held", "resolved", "within", "within_folded", "claude_home",
          "in_jobs_tmp", "project_roots", "plugin_roots", "under", "below_scratch")

try:
    KINDS_MODULE = _sibling("principal_kinds", "kinds.py")
    if not all(callable(getattr(KINDS_MODULE, n, None)) for n in SHARED):
        raise ImportError("kinds.py")
except BaseException:  # no rule is no decision: the call is blocked
    sys.stderr.write("The plugin's hooks/kinds.py does not load, so this gate blocks every "
                     "call until the plugin is whole again.\n")
    sys.exit(2)

#: the one kind that writes the notebook
WRITER = "recorder"

#: the kind that may write a document of its own, and never the notebook
SPEAKER = "interviewer"

#: every kind this plugin defines
KINDS = ("canon-answer", "checker", "clean-reader", "coordinator", "fetcher",
         "grader", "interviewer", "recorder", "reviewer")

#: the connector's writing tools, under both spellings
VERBS = ("update", "batch", "create", "delete")
PREFIXES = ("mcp__claude_ai_Claude_Docs__", "mcp__Claude_Docs__")
GUARDED = tuple(p + v for p in PREFIXES for v in VERBS)
#: tools that act on a document or an artifact by its address and write no
#: part of the notebook by a ref: every helper is refused one that names the
#: notebook, the recorder included
NAMING = tuple(p + "export" for p in PREFIXES) + ("Artifact", "ArtifactData",
                                                   "ArtifactComments")
#: the connector's delete, which the recorder too is refused on the notebook
DELETES = tuple(p + "delete" for p in PREFIXES)
#: the fields of those tools that hold an address
ADDRESSES = ("url", "from_url", "type_url")

#: an id at the end of a path segment: a UUID, or a run of 16 or more id
#: characters after the last hyphen of a titled segment
UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
TAIL = re.compile(r"(?:^|-)([0-9a-z_]{16,})$")

#: the shortest notebook id the gate will look for inside another string
SHORTEST = 8

REFUSED = ("only the recorder writes the notebook; hand back the rows for a "
           "record job instead")
UNCLEAR = ("this write does not say plainly which document it is for; name the "
           "document by its id in the container, and send nothing else in its place")


class Unclear(Exception):
    """A call, or a notebook file, the gate cannot make sense of."""


def plugin_name(path: str = PLUGIN) -> str:
    """This plugin's name, as its manifest gives it; '' where it cannot be
    read, and then only the recorder's bare name writes."""
    return KINDS_MODULE.plugin_name(path)


places = KINDS_MODULE.places
defined_here = KINDS_MODULE.defined_here


def own_kind(agent, plugin: str, cwd=None, env=None, own: str = AGENTS) -> str:
    """The kind of this plugin an agent type is, or '', by the rule every
    gate of the plugin shares."""
    return KINDS_MODULE.kind_of(agent, KINDS, plugin, cwd, {} if env is None else env, own)


#: every hyphen and dash Unicode spells, read as `-`
HYPHENS = {ord(c): "-" for c in "\u2010\u2011\u2012\u2013\u2014\u2015\u2043\u2212"
           "\ufe58\ufe63\uff0d\u058a\u05be\u1806\u2e3a\u2e3b\u301c\u30a0"}
#: what no reader sees, dropped
INVISIBLE = re.compile("[\u00ad\u034f\u061c\u115f\u1160\u17b4\u17b5\u180b-\u180f"
                       "\u200b-\u200f\u202a-\u202e\u2060-\u206f\u3164\ufe00-\ufe0f"
                       "\ufeff\uffa0\U000e0000-\U000e0fff]")


def plain(value) -> str:
    """A field as the id it spells: percent-encoding decoded, compatibility
    forms folded, every hyphen `-`, the invisible dropped."""
    text = str(value)
    for _ in range(3):
        decoded = urllib.parse.unquote(text)
        if decoded == text:
            break
        text = decoded
    text = INVISIBLE.sub("", unicodedata.normalize("NFKC", text))
    return INVISIBLE.sub("", text.translate(HYPHENS))


def doc_id(value) -> str:
    """The id a document is written as: the trailing id of the last path
    segment, without a query or a fragment, in lower case."""
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise Unclear("an id that is not a string")
    text = plain(value).strip().split("#", 1)[0].split("?", 1)[0].rstrip("/")
    segment = text.rsplit("/", 1)[-1].lower()
    if not segment:
        raise Unclear("an empty id")
    found = UUID.search(segment)
    if found:
        return found.group(0)
    found = TAIL.search(segment)
    return found.group(1) if found else segment


def _segment(value) -> str:
    """The last path segment of a field, without a query or a fragment, in
    lower case."""
    text = plain(value).strip().split("#", 1)[0].split("?", 1)[0].rstrip("/")
    return text.rsplit("/", 1)[-1].lower()


def aimed(value, notebook: str) -> bool:
    """Whether an addressing field names the notebook: its trailing id is the
    notebook's, the notebook's id occurs anywhere in it with or without
    hyphens, or its trailing id or a part of its last segment after a hyphen
    is, hyphens removed, a beginning of at least ``SHORTEST`` characters of
    the notebook's id."""
    text = plain(value).lower()
    if doc_id(value) == notebook or notebook in text:
        return True
    flat = notebook.replace("-", "")
    if flat in text.replace("-", ""):
        return True
    segment = _segment(value)
    parts = segment.split("-")
    tails = {doc_id(value)} | {"-".join(parts[i:]) for i in range(len(parts))}
    for tail in tails:
        short = tail.replace("-", "")
        if len(short) >= SHORTEST and flat.startswith(short):
            return True
    return False


def _aimed(value, notebook: str) -> bool:
    """`aimed`, for a field read loosely: one that is no id names nothing."""
    try:
        return aimed(value, notebook)
    except Unclear:
        return False


def find_notebook(cwd: str, env) -> str | None:
    """The guarded document's id; None where no notebook file is found."""
    for root in places(cwd, env):
        path = os.path.join(root, ".principal", "notebook.json")
        try:
            with open(path, encoding="utf-8-sig") as fh:
                named = json.load(fh)
        except FileNotFoundError:
            continue
        except (OSError, ValueError) as exc:
            raise Unclear("the notebook file") from exc
        if not isinstance(named, dict) or not named.get("artifact"):
            raise Unclear("the notebook file names no document")
        found = doc_id(named["artifact"])
        if len(found) < SHORTEST:
            raise Unclear("the notebook file names too short an id")
        return found
    return None


def _object(part, what: str):
    """A part of the call: an object, or the text of one, or absent."""
    if isinstance(part, str):
        try:
            part = json.loads(part)
        except ValueError as exc:
            raise Unclear(what) from exc
    if part is not None and not isinstance(part, dict):
        raise Unclear(what)
    return part


def _container(part, fields: list) -> bool:
    """Read a container's addressing fields into ``fields``; whether it
    creates a new document."""
    container = _object(part, "container")
    if container is None:
        return False
    if container.get("kind") != "project":
        raise Unclear("a container the gate does not know")
    if container.get("id") is not None:
        fields.append(container["id"])
    if "create" not in container:
        return False
    create = _object(container["create"], "create")
    if create is not None and create.get("artifact") not in (None, ""):
        fields.append(create["artifact"])
    return True


def _ref(part, fields: list, parts: list = None) -> None:
    """Read a ref's address into ``fields``; a ref of any other object, one
    that names a part of a document, into ``parts``."""
    ref = _object(part, "ref")
    if ref is not None and ref.get("object") == "project":
        if ref.get("id") is None:
            raise Unclear("a project ref with no id")
        fields.append(ref["id"])
    elif ref is not None and parts is not None:
        parts.append(ref)


def named(tool: str, tool_input) -> list:
    """The fields of a call of a naming tool, or of a delete, that hold an
    address: `url`, `from_url` and `type_url`, an artifact a published file
    is copied from, the container's id and a project ref's id."""
    if not isinstance(tool_input, dict):
        raise Unclear("the input")
    fields = [tool_input[k] for k in ADDRESSES if tool_input.get(k) not in (None, "")]
    files = tool_input.get("files")
    if isinstance(files, dict):
        files = list(files.values())
    for source in files if isinstance(files, list) else ():
        if isinstance(source, dict) and source.get("artifact") not in (None, ""):
            fields.append(source["artifact"])
    container = _object(tool_input.get("container"), "container")
    if container is not None and container.get("id") not in (None, ""):
        fields.append(container["id"])
    _ref(tool_input.get("ref"), fields)
    return fields


def addresses(tool: str, tool_input, parts: list = None) -> list:
    """The fields of a call that address a document. A call that names none
    is one the gate cannot make sense of, unless it is a `batch` that
    creates a new document. A ref that names a part of a document, not the
    document, goes into ``parts`` where it is given."""
    if not isinstance(tool_input, dict):
        raise Unclear("the input")
    verb = tool.rsplit("__", 1)[-1]
    fields = []
    creates = _container(tool_input.get("container"), fields)
    _ref(tool_input.get("ref"), fields, parts)
    if verb == "create" and tool_input.get("artifact") not in (None, ""):
        fields.append(tool_input["artifact"])
    if verb == "batch":
        members = tool_input.get("batch")
        if isinstance(members, str):
            try:
                members = json.loads(members)
            except ValueError as exc:
                raise Unclear("the batch") from exc
        if members is not None and not isinstance(members, list):
            raise Unclear("the batch")
        for member in members or ():
            member = _object(member, "a member")
            if member is None:
                raise Unclear("an empty member")
            _container(member.get("container"), fields)
            _ref(member.get("ref"), fields, parts)
    if not fields and not (verb == "batch" and creates):
        raise Unclear("no document")
    return fields


def _answer(decision: str, reason: str) -> dict:
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                   "permissionDecision": decision,
                                   "permissionDecisionReason": reason}}


def writes(agent, plugin: str, cwd=None, env=None, own: str = AGENTS) -> bool:
    """Whether a turn keeps what the harness gives it: the main thread, which
    carries no agent type, and the recorder: by this plugin's name, or by
    its bare name in a project that defines it as this plugin does."""
    if agent is None or agent == "":
        return True
    if not isinstance(agent, str):
        return False
    if plugin and agent == plugin + ":" + WRITER:
        return True
    return agent == WRITER and defined_here(WRITER, cwd, {} if env is None else env, own)


def decide(call, env=None, plugin=None, own: str = AGENTS) -> dict:
    """The permission decision for one tool call, as the hook's JSON output.
    An empty object is no decision, which is what the main thread, the
    recorder, and a helper writing plainly to another document get."""
    if not isinstance(call, dict):
        return {}
    env = os.environ if env is None else env
    plugin = plugin_name() if plugin is None else plugin
    agent = call.get("agent_type")
    tool = call.get("tool_name")
    if agent not in (None, "") and tool in NAMING + DELETES:
        # every helper, the recorder too: no export, no artifact tool and
        # no delete of the notebook
        try:
            cwd = call.get("cwd")
            notebook = find_notebook(cwd if isinstance(cwd, str) and cwd else None, env)
            if notebook is not None and any(_aimed(f, notebook)
                                            for f in named(tool, call.get("tool_input"))):
                return _answer("deny", REFUSED)
        except (Unclear, TypeError, ValueError, RecursionError):
            if tool in NAMING:
                return _answer("deny", UNCLEAR)
        if tool in NAMING:
            return {}
    if writes(agent, plugin, call.get("cwd"), env, own):
        return {}
    if isinstance(tool, str) and tool not in GUARDED:
        return {}
    kind = own_kind(agent, plugin, call.get("cwd"), env, own)
    if kind == WRITER:
        # a bare recorder this project does not define as ours: a helper
        kind = ""
    if kind and kind != SPEAKER:
        return _answer("deny", REFUSED)
    try:
        if not isinstance(tool, str):
            raise Unclear("the tool")
        cwd = call.get("cwd")
        if not isinstance(cwd, str) or not cwd:
            raise Unclear("the project")
        notebook = find_notebook(cwd, env)
        if notebook is None:
            return {}
        parts = []
        fields = addresses(tool, call.get("tool_input"), parts)
        if any(aimed(field, notebook) for field in fields):
            return _answer("deny", REFUSED)
        if parts and kind != SPEAKER:
            # a part of a document named by a ref the gate cannot place: the
            # connector may follow it into a document the call does not name
            raise Unclear("a ref to a part of a document")
    except (Unclear, TypeError, ValueError, RecursionError):
        return _answer("deny", UNCLEAR)
    return {}


#: an agent type in input that does not parse
AGENT = re.compile(rb'"agent_type"\s*:\s*"((?:[^"\\]|\\.)*)"')


def unparsed(raw: bytes, plugin: str) -> dict:
    """What input that does not parse gets: refused where it names an agent
    type other than the writer by this plugin's name, no opinion otherwise.
    The bare name is refused here: with no cwd there is no project to read
    its definition from."""
    found = AGENT.search(raw)
    if not found:
        return {}
    agent = KINDS_MODULE.spelled(found.group(1))
    return {} if writes(agent, plugin) else _answer("deny", UNCLEAR)


def main() -> int:
    plugin = plugin_name()
    try:
        raw = sys.stdin.buffer.read()
    except (OSError, ValueError):
        raw = b""
    try:
        call = json.loads(raw.decode("utf-8-sig"))
    except (ValueError, RecursionError, MemoryError):
        print(json.dumps(unparsed(raw, plugin)))
        return 0
    try:
        decision = decide(call, plugin=plugin)
    except Exception:  # pragma: no cover - a guarded turn fails closed
        agent = call.get("agent_type") if isinstance(call, dict) else None
        decision = {} if writes(agent, plugin, call.get("cwd") if isinstance(call, dict)
                                else None, os.environ) else _answer("deny", UNCLEAR)
    print(json.dumps(decision))
    return 0


if __name__ == "__main__":
    sys.exit(main())
