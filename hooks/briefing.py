"""What the brief's hooks share: where the brief lives, who receives one, and
the plugin's tools loaded beside them.

Not a hook: `hooks.json` names none of it. Each of `brief-session.py`,
`brief-subagent.py`, `inhand-log.py`, `inhand-precompact.py` and
`convention-gate.py` loads it by its path beside the hook.

Where the brief lives. `tools/brief.py install` writes it, and these hooks
read it, at `<config home>/principal/brief/<the project's path, every
character but a letter or digit made ->`, the config home being
`$CLAUDE_CONFIG_DIR` where it is set and `~/.claude` otherwise
(`hypo.brief.brief_dir`): outside every repository, so that no `git add`
stages it and no public checkout holds a sentence of the notebook, and keyed
by the checkout, so that two checkouts do not share one. The project is the
nearest of `CLAUDE_PROJECT_DIR`, the cwd and its ancestors that holds
`.principal/notebook.json`; where none does, there is no project, and every
one of these hooks prints and decides nothing.

Who receives a brief. `brief-sides.json` beside this file, an allow-list by
kind that defaults to nobody: a kind it names receives the side it gives
(`all`, the user's, the AI's and the tradition parties'; `ai`, the AI's own
answers alone), a kind it gives `null`, or does not name, receives nothing,
and a helper that is no kind of the plugin receives what `no_kind` gives,
which is nothing. A kind is matched by its name with case folded, with or
without the plugin's name in front; another plugin's name in front makes
no kind of ours.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TOOLS = os.path.join(ROOT, "tools")
AGENTS = os.path.join(ROOT, "agents")
SIDES_FILE = os.path.join(HERE, "brief-sides.json")

if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

from hypo import brief  # noqa: E402


def _sibling(name: str, file: str):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, file))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


try:
    KINDS = _sibling("principal_kinds", "kinds.py")
except BaseException:  # pragma: no cover - the gates say so; here no brief is given
    KINDS = None


def sides(path: str = SIDES_FILE) -> dict:
    """The allow-list: {"no_kind": side or None, "kinds": {kind: side or None}};
    a file that cannot be read gives nobody anything."""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {"no_kind": None, "kinds": {}}
    kinds = data.get("kinds") if isinstance(data, dict) else None
    out = {"no_kind": data.get("no_kind") if isinstance(data, dict) else None,
           "kinds": kinds if isinstance(kinds, dict) else {}}
    for key in list(out["kinds"]):
        if out["kinds"][key] not in brief.SIDES:
            out["kinds"][key] = None
    if out["no_kind"] not in brief.SIDES:
        out["no_kind"] = None
    return out


def defined_kinds(own: str = AGENTS) -> tuple:
    try:
        return tuple(sorted(n[:-3] for n in os.listdir(own) if n.endswith(".md")))
    except OSError:
        return ()


def side_for(agent, cwd, env, table=None, own: str = AGENTS, main: bool = True):
    """The side a turn or a helper of type ``agent`` receives, or None. A
    turn that names no agent is the main thread, the speaker's, and receives
    all where ``main``; a helper that names none receives nothing. A kind is
    matched with case folded, with or without the plugin's name in front;
    a helper of no kind receives what `no_kind` gives, nothing by default."""
    table = sides() if table is None else table
    if not isinstance(agent, str) or not agent.strip():
        return "all" if main else None
    names = {k.lower(): k for k in set(defined_kinds(own)) | set(table["kinds"])}
    name = agent.strip().lower()
    plugin = ((KINDS.plugin_name() if KINDS is not None else "") or "principal").lower()
    if name.startswith(plugin + ":"):
        name = name[len(plugin) + 1:]
    if name in names:
        return table["kinds"].get(names[name])
    return table["no_kind"]


def where(cwd, env):
    """The project and the brief's directory, or (None, None)."""
    root = brief.project_root(cwd, env)
    if not root:
        return None, None
    try:
        return root, brief.brief_dir(root, env)
    except brief.Refused:
        return root, None


def read(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except (OSError, ValueError):
        return ""


def source(directory: str) -> dict:
    try:
        with open(os.path.join(directory, brief.FILES["source"]), encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def graph(directory: str):
    """The graph the brief was made from, as copied beside it, or None."""
    from hypo import model
    try:
        return model.load(os.path.join(directory, brief.FILES["graph"]))
    except model.ShapeError:
        return None


def call(raw: bytes):
    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except (ValueError, RecursionError, MemoryError):
        return None
    return data if isinstance(data, dict) else None
