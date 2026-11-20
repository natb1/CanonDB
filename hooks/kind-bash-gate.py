#!/usr/bin/env python3
"""The shell gate of the sitting's kinds: each runs what its work needs, over
its own files, and nothing else.

A PreToolUse hook on Bash, installed by the plugin and so fired on every
Bash call of every turn in a project that has the plugin. It decides only
for this plugin's kinds; every other turn gets no opinion, the main thread
(which carries no `agent_type`) and the interviewer among them, and the
harness's ordinary permissions apply. Bash is the whole machine: the
network, a push, a session of its own with no `agent_type`, which no other
gate binds. So a kind that holds it is held here to its work:

- the checker runs the three tools of its fixed sequence, `page.py`,
  `read.py` and `check.py`, each by its absolute path under this plugin's
  `tools/`, with the options the sequence uses and no other: `page.py`
  over views, `-o` once; `read.py` over a tab list and a tabs directory,
  `--scope` its one listing and `-o` once; `check.py` over one graph. Its
  one listing, `$(ls <dir>/tabs | sed -n 's/\\.md$//p')`, is admitted inside
  the `read.py` command, once, as the `--scope` it builds, over the tabs
  directory that command reads, and no other substitution anywhere; the
  word the listing stands as while the command is read, typed, refuses
  it. What it writes, every `-o`, stands under a directory named `check`;
  what it reads, under a directory named `check` or `coordinator`; each
  below a scratch root the gates recognise (`/tmp/claude-*/…/scratchpad/`
  or `~/.claude/jobs/<id>/tmp/`) and held as `kinds.py` holds a path
  (outside the project, the plugin's root and `~/.claude`). The views it
  reads are named by one `*` in the last component and no other pattern,
  and a view, or a tab in the directory `read.py` lists, whose name
  begins with `-` refuses the command, since that name becomes a word of
  the next tool's arguments;
- the coordinator runs `board.py` and `views.py` by their absolute paths
  under this plugin's `tools/`, `date -u` with at most a format,
  `sha256sum` over files, `mkdir -p`, and `jq` over files, and every path
  it names stands under a directory named `coordinator` below a scratch
  root, held as above (`mkdir -p` may name that directory itself):
  `board.py`'s export, `--versions`, `--out` and `--result`, with the
  modes `next`, `claim`, `done`, `fail`, `status` and `verify` only, and
  `--by coordinator`; `views.py`'s out dir, `--doc` and `--names`, and its
  transcript, which may also be a `.jsonl` file under
  `~/.claude/projects/<the session's project>/`, where the harness keeps a
  helper's transcript, read and never written (the directory named from
  `CLAUDE_PROJECT_DIR`, every character but a letter or a digit read as
  `-`; where that is not set, under any project's directory there);
  `jq` with none of `-n`, `-f`, `-L`, `--rawfile`, `--slurpfile`, `--args`
  or `--jsonargs`, and a program that names neither the environment
  (`env`, `$ENV`, `$JQ_BUILD_CONFIGURATION`) nor where it stands
  (`input_filename`, `$__loc__`, `get_prog_origin`) nor a module
  (`modulemeta`); `mkdir -p` of its own directories;
- the fetcher, the recorder, the clean reader, the reviewer, the grader and
  the canon agent run nothing.

The command is read as the shell would read it, quotes and all, and is
refused where it holds what would make it more than the one program named:
`;`, `&`, `|`, a redirection, a parenthesis, a brace, a line break, a
backslash outside single quotes, `$` or a backtick outside single quotes
(every expansion and substitution), the checker's one listing aside, `#`,
`~`, and a pattern (`*`, `?`, `[`) outside quotes, the checker's one `*`
aside. A program is named by its absolute path for a tool, by its plain
name otherwise; a word in front of it that the shell takes for an
assignment (`NAME=…`, `NAME+=…`) refuses the command, and so does a
program word that holds `=`. Every option is spelled whole: a shortened
one, a joined value (`--out=x`, `-ox`), and one the program's work does not
use are refused.

Which turn is a kind, and which path is held: `kinds.py`, which every gate
of this plugin shares.

A refusal is one plain sentence saying what the kind may run. A confined
turn fails closed: a call the gate cannot make sense of is refused.
"""

from __future__ import annotations

import fnmatch
import importlib.util
import json
import os
import re
import shlex
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
AGENTS = os.path.join(ROOT, "agents")


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
    KINDS = _sibling("principal_kinds", "kinds.py")
    if not all(callable(getattr(KINDS, n, None)) for n in SHARED):
        raise ImportError("kinds.py")
except BaseException:  # no rule is no decision: the call is blocked
    sys.stderr.write("The plugin's hooks/kinds.py does not load, so this gate blocks every "
                     "call until the plugin is whole again.\n")
    sys.exit(2)

CHECKER = "checker"
COORDINATOR = "coordinator"
#: the kinds that run nothing in the shell
NO_SHELL = ("canon-answer", "clean-reader", "fetcher", "grader", "recorder", "reviewer")
CONFINED = (CHECKER, COORDINATOR) + NO_SHELL

CHECKER_TOOLS = ("page.py", "read.py", "check.py")
COORDINATOR_TOOLS = ("board.py", "views.py")

#: the checker's one listing, as its definition writes it, over a path of
#: the letters a session's scratch is spelled in
LISTING = re.compile(r"\$\(ls ([A-Za-z0-9_./+-]+)/tabs \| sed -n 's/\\\.md\$//p'\)")
#: the word the listing stands as while the rest is read
SCOPE = "__scope_listing__"

#: outside quotes, each of these makes more than one program, or more than
#: one word of what is written
OPERATORS = set(";&|<>(){}\n\r#~")
PATTERNS = set("*?[")
#: a word the shell takes for an assignment in front of a program
ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\+?=")

#: the board's modes the coordinator runs, and the options each may take
BOARD_MODES = ("next", "claim", "done", "fail", "status", "verify")
BOARD_JOB = ("claim", "done", "fail")
BOARD_PATHS = ("--versions", "--out", "--result")
BOARD_VALUES = ("--now", "--reason", "--by")
BOARD_FLAGS = ("--json",)
VIEWS_PATHS = ("--doc", "--names")
VIEWS_FLAGS = ("--list-only",)
#: jq's options the coordinator may give, and what its program may not name
JQ_FLAGS = set("rcesjaS")
JQ_LONG = ("--raw-output", "--compact-output", "--exit-status", "--slurp", "--join-output",
           "--ascii-output", "--sort-keys")
JQ_PAIRS = ("--arg", "--argjson")
JQ_NAMES = re.compile(r"\benv\b|\$ENV|\binput_filename\b|\$__loc__|\$__prog|\bimport\b"
                      r"|\binclude\b|\bget_search_list\b|\binput_line_number\b"
                      r"|\bget_prog_origin\b|\$JQ_BUILD_CONFIGURATION\b|\bmodulemeta\b")

SAYS = {
    CHECKER: ("a checker runs only page.py, read.py and check.py by their absolute "
              "paths under the plugin's tools directory, with the options and the one "
              "listing its definition gives, writing only under a check directory"),
    COORDINATOR: ("a coordinator runs only board.py and views.py by their absolute paths "
                  "under the plugin's tools directory, date -u, sha256sum, mkdir -p and "
                  "jq, each alone, over paths under its own coordinator directory"),
}
NOTHING = "this kind runs nothing in the shell; its work is done with the tools it was given"


class Refused(Exception):
    """A command the gate will not admit, with why."""


def kind_of(agent, plugin: str, cwd, env, own: str = AGENTS) -> str:
    """The confined kind a turn is, or ''."""
    return KINDS.kind_of(agent, CONFINED, plugin, cwd, env, own)


def scan(command: str, star: bool = False) -> None:
    """Refuse a command that is more than one program: an operator outside
    quotes, an expansion outside single quotes, a backslash, a pattern
    outside quotes (a `*` only where ``star``), an unclosed quote."""
    quote = ""
    for ch in command:
        if quote == "'":
            if ch == "'":
                quote = ""
            continue
        if ch in "$`":
            raise Refused("an expansion or a substitution (%s)" % ch)
        if ch == "\\":
            raise Refused("a backslash outside single quotes")
        if quote == '"':
            if ch == '"':
                quote = ""
            elif ch in "\n\r":
                raise Refused("a line break")
            continue
        if ch in "'\"":
            quote = ch
        elif ch in OPERATORS:
            raise Refused("an operator (%r): one program a call" % ch)
        elif ch in PATTERNS and not (star and ch == "*"):
            raise Refused("a pattern (%r)" % ch)
    if quote:
        raise Refused("an unclosed quote")


def tools_dirs(env) -> list:
    """Where this plugin's tools stand: beside this hook, and under
    `CLAUDE_PLUGIN_ROOT` where it is set."""
    out = [os.path.join(ROOT, "tools")]
    root = env.get("CLAUDE_PLUGIN_ROOT")
    if isinstance(root, str) and root:
        out.append(os.path.join(root, "tools"))
    return [os.path.realpath(d) for d in out]


def is_tool(word: str, names: tuple, env) -> bool:
    """Whether a program word is one of the named tools by its absolute
    path: no `=` in it, an existing file, which is the plugin's own."""
    if not os.path.isabs(word) or "=" in word or "\0" in word:
        return False
    if os.path.basename(word) not in names or not os.path.isfile(word):
        return False
    where = os.path.realpath(word)
    return any(where == os.path.join(d, os.path.basename(word)) for d in tools_dirs(env))


def program(argv: list) -> str:
    """The program word, refusing a command that opens with an assignment."""
    if not argv:
        raise Refused("no program")
    if ASSIGNMENT.match(argv[0]):
        raise Refused("an assignment in front of the program")
    return argv[0]


def parse(args: list, paths=(), values=(), flags=()) -> tuple:
    """A command's words after the program: the positionals, and each
    option with its value, every option spelled whole and known."""
    positional, options = [], []
    i = 0
    while i < len(args):
        word = args[i]
        if word.startswith("-"):
            if word in flags:
                options.append((word, None))
                i += 1
                continue
            if word in paths or word in values:
                if i + 1 >= len(args):
                    raise Refused("%s with no value" % word)
                options.append((word, args[i + 1]))
                i += 2
                continue
            raise Refused("an option its work does not use (%s)" % word)
        positional.append(word)
        i += 1
    return positional, options


def path_in(path: str, names: tuple, cwd, env, star: bool = False, last: bool = False) -> None:
    """Refuse a path that is not held, or not under a directory of one of
    ``names`` below a scratch root; with ``star``, the last component may
    hold one `*`; with ``last``, the path may be that directory itself."""
    if any(ch in path for ch in "*?["):
        head, tail = os.path.split(path)
        if not star or any(ch in head for ch in "*?[") or any(ch in tail for ch in "?[") \
                or tail.count("*") != 1:
            raise Refused("a pattern in a path")
        where = KINDS.held(head, cwd, env)
        where = os.path.join(where, tail) if where else ""
    else:
        where = KINDS.held(path, cwd, env)
    if not where:
        raise Refused("a path outside its scratch (%s)" % path)
    if not any(KINDS.under(where, n, env, last) for n in names):
        raise Refused("a path under no %s directory (%s)" % (" or ".join(names), path))


def no_option_names(pattern: str) -> None:
    """Refuse where a file the shell would list for ``pattern`` (one `*` in
    its last component, or none) is named as an option, `-…`: a view's name
    becomes a tab's, and a tab's a word of `read.py`'s scope."""
    head, tail = os.path.split(pattern)
    try:
        names = os.listdir(head)
    except OSError:
        return
    if any(n.startswith("-") and fnmatch.fnmatchcase(n, tail) for n in names):
        raise Refused("a file named as an option")


def checker(command: str, cwd, env) -> None:
    if SCOPE in command:
        raise Refused("the listing's stand-in word typed")
    found = LISTING.findall(command)
    if len(found) > 1:
        raise Refused("the listing more than once")
    if found:
        command = LISTING.sub(SCOPE, command)
    scan(command, star=True)
    argv = shlex.split(command)
    word = program(argv)
    if not is_tool(word, CHECKER_TOOLS, env):
        raise Refused("a program outside the sequence")
    name, args = os.path.basename(word), argv[1:]
    if SCOPE in args and name != "read.py":
        raise Refused("the listing anywhere but as read.py's --scope")
    reads = ("check", "coordinator")
    if name == "page.py":
        positional, options = parse(args, paths=("-o",))
        if not positional or [o for o, _ in options] != ["-o"]:
            raise Refused("page.py other than over views, -o once")
        for p in positional:
            path_in(p, reads, cwd, env, star=True)
            no_option_names(p)
        path_in(options[0][1], ("check",), cwd, env)
    elif name == "read.py":
        if not found:
            raise Refused("read.py with a scope other than its listing")
        positional, options = parse(args, paths=("-o", "--scope"))
        if [o for o, _ in options] != ["--scope", "-o"] and \
                [o for o, _ in options] != ["-o", "--scope"]:
            raise Refused("read.py other than --scope its listing and -o once")
        given = dict(options)
        if given["--scope"] != SCOPE or len(positional) != 2 or SCOPE in positional:
            raise Refused("read.py other than a tab list, a tabs directory and its listing")
        listed, tabs = positional
        if found[0] + "/tabs" != tabs:
            raise Refused("the listing of a directory read.py does not read")
        path_in(listed, reads, cwd, env)
        path_in(tabs, ("check",), cwd, env)
        no_option_names(os.path.join(tabs, "*.md"))
        path_in(given["-o"], ("check",), cwd, env)
    else:
        positional, options = parse(args)
        if len(positional) != 1 or options:
            raise Refused("check.py other than over one graph")
        path_in(positional[0], ("check",), cwd, env)


def board(args: list, cwd, env) -> None:
    if not args or args[0] not in BOARD_MODES:
        raise Refused("a mode of the board it does not run")
    mode = args[0]
    positional, options = parse(args[1:], paths=BOARD_PATHS, values=BOARD_VALUES,
                                flags=BOARD_FLAGS)
    want = 2 if mode in BOARD_JOB else 1
    if len(positional) != want:
        raise Refused("board.py %s other than an export%s" % (
            mode, " and a job's id" if want == 2 else ""))
    mine = ("coordinator",)
    path_in(positional[0], mine, cwd, env)
    if want == 2 and ("/" in positional[1] or not positional[1]):
        raise Refused("a job's id that is a path")
    for option, value in options:
        if option in BOARD_PATHS:
            path_in(value, mine, cwd, env)
        elif option == "--by" and value != COORDINATOR:
            raise Refused("--by other than coordinator")


def session_projects(env) -> list:
    """Where the harness keeps this session's transcripts: under
    `~/.claude/projects/` the directory named for the session's project,
    `CLAUDE_PROJECT_DIR` with every character but a letter or a digit read as
    `-`, as given and resolved; empty where the project is not known."""
    project = env.get("CLAUDE_PROJECT_DIR")
    if not isinstance(project, str) or not project:
        return []
    projects = os.path.join(KINDS.claude_home(env), "projects")
    return [os.path.join(projects, re.sub(r"[^A-Za-z0-9]", "-", p))
            for p in {project, os.path.realpath(project)}]


def transcript(path: str, cwd, env) -> None:
    """A helper's transcript: in the coordinator's own scratch, or a
    `.jsonl` file under `~/.claude/projects/<the session's project>/`, where
    the harness keeps one; under any project's there where the session's
    project is not known."""
    try:
        path_in(path, ("coordinator",), cwd, env)
        return
    except Refused:
        pass
    where = KINDS.resolved(path)
    roots = session_projects(env) or [os.path.join(KINDS.claude_home(env), "projects")]
    if not where or not where.endswith(".jsonl") \
            or not any(KINDS.within(where, r) and where != r for r in roots):
        raise Refused("a transcript that is not a helper's")


def views(args: list, cwd, env) -> None:
    positional, options = parse(args, paths=VIEWS_PATHS, flags=VIEWS_FLAGS)
    if len(positional) != 2 or len(options) > 1:
        raise Refused("views.py other than a transcript, an out dir and one of its options")
    transcript(positional[0], cwd, env)
    path_in(positional[1], ("coordinator",), cwd, env)
    for option, value in options:
        if value is not None:
            path_in(value, ("coordinator",), cwd, env)


def jq(args: list, cwd, env) -> None:
    text, files, i = None, [], 0
    while i < len(args):
        word = args[i]
        if text is None and word.startswith("-"):
            if word in JQ_PAIRS:
                if i + 2 >= len(args):
                    raise Refused("%s with no name or value" % word)
                i += 3
                continue
            if word in JQ_LONG or (len(word) > 1 and not word.startswith("--")
                                   and set(word[1:]) <= JQ_FLAGS):
                i += 1
                continue
            raise Refused("a jq option it does not use (%s)" % word)
        if text is None:
            text = word
        else:
            files.append(word)
        i += 1
    if text is None or not files:
        raise Refused("jq other than a program over files")
    if JQ_NAMES.search(text):
        raise Refused("a jq program that names the environment, a file or a module")
    for path in files:
        path_in(path, ("coordinator",), cwd, env)


def coordinator(command: str, cwd, env) -> None:
    scan(command)
    argv = shlex.split(command)
    word, args = program(argv), argv[1:]
    if is_tool(word, ("board.py",), env):
        return board(args, cwd, env)
    if is_tool(word, ("views.py",), env):
        return views(args, cwd, env)
    if word == "date":
        if args[:1] == ["-u"] and (len(args) == 1 or (len(args) == 2 and args[1].startswith("+"))):
            return None
        raise Refused("date other than date -u with a format")
    if word == "sha256sum":
        if args and not any(a.startswith("-") for a in args):
            for path in args:
                path_in(path, ("coordinator",), cwd, env)
            return None
        raise Refused("sha256sum other than over files")
    if word == "mkdir":
        if args[:1] == ["-p"] and len(args) > 1:
            for path in args[1:]:
                path_in(path, ("coordinator",), cwd, env, last=True)
            return None
        raise Refused("mkdir other than mkdir -p of its own directories")
    if word == "jq":
        return jq(args, cwd, env)
    raise Refused("a program it does not run")


def _answer(decision: str, reason: str) -> dict:
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                   "permissionDecision": decision,
                                   "permissionDecisionReason": reason}}


def decide(call, env=None, plugin=None, own: str = AGENTS) -> dict:
    """The permission decision for one Bash call, as the hook's JSON output;
    an empty object for every turn that is not a confined kind."""
    if not isinstance(call, dict):
        return {}
    env = os.environ if env is None else env
    plugin = KINDS.plugin_name() if plugin is None else plugin
    cwd = call.get("cwd")
    kind = kind_of(call.get("agent_type"), plugin, cwd, env, own)
    if not kind:
        return {}
    tool = call.get("tool_name")
    # only a name plainly of another tool passes by; "", "bash" or "Bash "
    # is read as the shell
    if isinstance(tool, str) and tool.strip() and tool.strip().lower() != "bash":
        return {}
    if kind in NO_SHELL:
        return _answer("deny", NOTHING)
    tool_input = call.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    try:
        if not isinstance(command, str) or not command.strip():
            raise Refused("no command")
        (checker if kind == CHECKER else coordinator)(command, cwd, env)
    except (Refused, ValueError, TypeError, KeyError) as exc:
        return _answer("deny", "%s; refused: %s" % (SAYS[kind], exc))
    return {}


#: an agent type in input that does not parse
AGENT = re.compile(rb'"agent_type"\s*:\s*"((?:[^"\\]|\\.)*)"')


def unparsed(raw: bytes) -> dict:
    """Input that does not parse: refused where it names one of the confined
    kinds by any name, no opinion otherwise."""
    found = AGENT.search(raw)
    if not found:
        return {}
    agent = KINDS.spelled(found.group(1))
    if KINDS.named_any(agent, CONFINED):
        return _answer("deny", "the call cannot be read; nothing is run")
    return {}


def main() -> int:
    plugin = KINDS.plugin_name()
    try:
        raw = sys.stdin.buffer.read()
    except (OSError, ValueError):
        raw = b""
    try:
        call = json.loads(raw.decode("utf-8-sig"))
    except (ValueError, RecursionError, MemoryError):
        print(json.dumps(unparsed(raw)))
        return 0
    try:
        decision = decide(call, plugin=plugin)
    except Exception:  # pragma: no cover - a confined turn fails closed
        agent = call.get("agent_type") if isinstance(call, dict) else None
        decision = _answer("deny", "the call cannot be read; nothing is run") \
            if isinstance(agent, str) and KINDS.named_any(agent, CONFINED) else {}
    print(json.dumps(decision))
    return 0


if __name__ == "__main__":
    sys.exit(main())
