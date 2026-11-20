"""What the plugin's gates share: which turn is one of this plugin's kinds,
and which paths stand outside everything a kind must not write.

Not a hook: `hooks.json` names none of it. Each gate loads it by its path
beside the gate, so the rules below are spelled once.

Which turn is a kind. The plugin's name in front of the kind, read from the
plugin's `.claude-plugin/plugin.json`, always is. Where that file cannot be
read the gate fails closed: any name ending in `:<kind>` is the kind. The
bare name is the kind where the project's own
`.claude/agents/<kind>.md`, the nearest found from `CLAUDE_PROJECT_DIR` and
then the call's cwd and its ancestors, is byte for byte the plugin's
`agents/<kind>.md`, as in this repository's own checkout; elsewhere a bare
`reviewer` or `coordinator` is the project's own agent, and no gate has an
opinion on it.

A bare name whose project copy differs, or is missing, is still the kind
where the project uses this plugin, that is where a `.principal/notebook.json`
is found in the same places: there it is confined as the kind and never
freed by a byte of difference (fail closed), the writer excepted, which the
notebook gate takes for the writer only where the copy is the plugin's. In
a project that names no notebook a bare name is the project's own.

Which paths a kind's scratch may be. A path is held where it is absolute,
holds no `..`, and is neither in nor above the project, the plugin's root,
or `~/.claude`, save that `~/.claude/jobs/<id>/tmp` and what is under it,
which is a session's scratch, is not refused for being under `~/.claude`.
The project is `CLAUDE_PROJECT_DIR`, the call's cwd, and the nearest
ancestor of the cwd below the home directory that holds `.principal` or
`.git` (a home directory kept under git is not taken for a project, or
every session's scratch under it would be refused). The plugin's root is
the directory above this file and `CLAUDE_PLUGIN_ROOT`. A path is read with
its links resolved, so a link into the project is the project. Whether a
path is in or above one of these is read with case folded, so that on a
volume that folds case `~/.CLAUDE` is `~/.claude`; where the volume does
not, that refuses a little more and admits nothing more.

A kind's own directory, `coordinator` or `check`, counts only below a
scratch root the gates recognise: `/tmp/claude-*/…/scratchpad/` (the
session's scratchpad, `/tmp` resolved) and `~/.claude/jobs/<id>/tmp/`, with
no directory named for the sitting (`questions`, `answers`, `replies`,
`results`, `sealed`, `rows`, `check`, `coordinator`) between the root and
it. A directory of that name anywhere else is no kind's.
"""

from __future__ import annotations

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PLUGIN = os.path.join(ROOT, ".claude-plugin", "plugin.json")
#: this plugin's own definitions, which a project's bare kind must match
AGENTS = os.path.join(ROOT, "agents")

#: what marks a project's root, above the cwd
MARKS = (".principal", ".git")
#: what marks a project that uses this plugin
NOTEBOOK = os.path.join(".principal", "notebook.json")
#: the directories a sitting names in its scratch
SITTING = ("questions", "answers", "replies", "results", "sealed", "rows", "check",
           "coordinator", "speaker")


def plugin_name(path: str = PLUGIN) -> str:
    """This plugin's name, as its manifest gives it; '' where it cannot be
    read."""
    try:
        with open(path, encoding="utf-8-sig") as fh:
            name = json.load(fh).get("name")
    except (OSError, ValueError, AttributeError):
        return ""
    return name if isinstance(name, str) else ""


def places(cwd, env) -> list:
    """Where a project is looked for: `CLAUDE_PROJECT_DIR` where it is set,
    then the cwd, where the call gives one, and each of its ancestors."""
    out = []
    project = env.get("CLAUDE_PROJECT_DIR")
    if isinstance(project, str) and project:
        out.append(project)
    if not isinstance(cwd, str) or not cwd:
        return out
    here = os.path.abspath(cwd)
    while True:
        out.append(here)
        up = os.path.dirname(here)
        if up == here:
            break
        here = up
    return out


def defined_here(kind: str, cwd, env, own: str = AGENTS) -> bool:
    """Whether a kind's bare name is this plugin's kind in this project: the
    nearest `.claude/agents/<kind>.md` is byte for byte this plugin's own."""
    try:
        with open(os.path.join(own, kind + ".md"), "rb") as fh:
            mine = fh.read()
    except OSError:
        return False
    for root in places(cwd, env):
        try:
            with open(os.path.join(root, ".claude", "agents", kind + ".md"), "rb") as fh:
                return fh.read() == mine
        except FileNotFoundError:
            continue
        except OSError:
            return False
    return False


def consumer(cwd, env) -> bool:
    """Whether the project uses this plugin: a `.principal/notebook.json`
    stands in one of the places a project is looked for."""
    for root in places(cwd, env):
        try:
            if os.path.lexists(os.path.join(root, NOTEBOOK)):
                return True
        except (OSError, ValueError):
            return True
    return False


def kind_of(agent, kinds, plugin: str, cwd, env, own: str = AGENTS) -> str:
    """The kind of this plugin, of ``kinds``, a turn is, or ''. A bare name
    is the kind where the project defines it byte for byte as the plugin
    does, and, failing closed, wherever the project uses this plugin."""
    if not isinstance(agent, str) or not agent:
        return ""
    for kind in kinds:
        if plugin and agent == plugin + ":" + kind:
            return kind
        if not plugin and agent.endswith(":" + kind):
            return kind
        if agent == kind and (defined_here(kind, cwd, env, own) or consumer(cwd, env)):
            return kind
    return ""


def spelled(captured: bytes) -> str:
    """An agent type captured from input that does not parse, its JSON
    escapes read; as it stands where they cannot be."""
    try:
        text = json.loads(b'"' + captured + b'"')
        if isinstance(text, str):
            return text
    except (ValueError, RecursionError):
        pass
    return captured.decode("utf-8", "replace")


def named_any(agent: str, kinds) -> bool:
    """Whether a name read from input that does not parse names one of
    ``kinds`` by any name: bare, or after any prefix."""
    return agent.rsplit(":", 1)[-1] in kinds


def _real(path: str) -> str:
    return os.path.realpath(path)


def within(where: str, root: str) -> bool:
    """Whether ``where`` is ``root`` or under it; both already resolved."""
    return where == root or where.startswith(root.rstrip(os.sep) + os.sep)


def within_folded(where: str, root: str) -> bool:
    """`within` with case folded, for what is refused: on a volume that
    folds case another spelling is the same directory."""
    return within(where.casefold(), root.casefold())


def project_roots(cwd, env) -> list:
    """The project's roots, resolved: `CLAUDE_PROJECT_DIR`, the cwd, and the
    nearest ancestor of the cwd that holds a project's mark."""
    out = []
    project = env.get("CLAUDE_PROJECT_DIR")
    if isinstance(project, str) and project:
        out.append(_real(project))
    if isinstance(cwd, str) and cwd:
        here = _real(cwd)
        out.append(here)
        home = os.path.dirname(claude_home(env))
        while True:
            if within(home, here):
                # a home directory kept under git is no project
                break
            if any(os.path.lexists(os.path.join(here, m)) for m in MARKS):
                out.append(here)
                break
            up = os.path.dirname(here)
            if up == here:
                break
            here = up
    return out


def plugin_roots(env) -> list:
    """The plugin's roots, resolved: above this file, and
    `CLAUDE_PLUGIN_ROOT` where it is set."""
    out = [_real(ROOT)]
    root = env.get("CLAUDE_PLUGIN_ROOT")
    if isinstance(root, str) and root:
        out.append(_real(root))
    return out


def claude_home(env) -> str:
    """`~/.claude`, resolved, by the environment's HOME."""
    home = env.get("HOME")
    if not isinstance(home, str) or not home:
        home = os.path.expanduser("~")
    return _real(os.path.join(home, ".claude"))


def in_jobs_tmp(where: str, home: str) -> bool:
    """Whether a resolved path is `~/.claude/jobs/<id>/tmp` or under it."""
    if not within(where, home) or where == home:
        return False
    parts = where[len(home.rstrip(os.sep)) + 1:].split(os.sep)
    return len(parts) >= 3 and parts[0] == "jobs" and parts[1] and parts[2] == "tmp"


def resolved(path) -> str:
    """A path as written, resolved; '' where it is not absolute, holds a
    `..`, or cannot be resolved."""
    if not isinstance(path, str) or not os.path.isabs(path) or "\0" in path:
        return ""
    if ".." in path.split("/"):
        return ""
    try:
        return _real(path)
    except (OSError, ValueError):
        return ""


def held(path, cwd, env) -> str:
    """The resolved path where it is held, outside the project, the plugin's
    root and `~/.claude` (but a session's `~/.claude/jobs/<id>/tmp`), in and
    above each, case folded; '' otherwise."""
    where = resolved(path)
    if not where:
        return ""
    home = claude_home(env)
    roots = project_roots(cwd, env)
    if not roots:
        return ""
    for root in roots + plugin_roots(env):
        if within_folded(where, root) or within_folded(root, where):
            return ""
    if within_folded(home, where):
        return ""
    if within_folded(where, home) and not in_jobs_tmp(where.casefold(), home.casefold()):
        return ""
    return where


def below_scratch(where: str, env) -> list | None:
    """The components of a resolved path below the scratch root it stands
    under, `/tmp/claude-*/…/scratchpad` or `~/.claude/jobs/<id>/tmp`; None
    where it stands under neither."""
    tmp = _real("/tmp")
    if within(where, tmp) and where != tmp:
        parts = where[len(tmp.rstrip(os.sep)) + 1:].split(os.sep)
        if parts[0].startswith("claude-") and "scratchpad" in parts[1:]:
            return parts[parts.index("scratchpad", 1) + 1:]
    home = claude_home(env)
    if in_jobs_tmp(where, home):
        return where[len(home.rstrip(os.sep)) + 1:].split(os.sep)[3:]
    return None


def under(where: str, name: str, env, last: bool = False) -> bool:
    """Whether a resolved path has a directory named ``name`` below a
    scratch root and above its last component (or, with ``last``, as its
    last component), with no other directory of the sitting's names between
    the root and it."""
    parts = below_scratch(where, env)
    if not parts:
        return False
    if name not in (parts if last else parts[:-1]):
        return False
    return not any(p in SITTING for p in parts[:parts.index(name)])
