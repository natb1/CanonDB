#!/usr/bin/env python3
"""clean_turn.py probe | answer | draw — a clean turn, run as a process of its own.

A clean turn is a model run whose context holds only the AI's own earlier
answers, each under the question it was given to, and one question, and
nothing of the user's record. It is not a helper of a session, since a
helper started from a session carries that session's memory index, rules
file, git status and list of skills. It is a separate run of the
command-line harness, started by this script in a fresh, empty directory
under /tmp that is no repository and has a name that means nothing:

    CLAUDE_CODE_DISABLE_AUTO_MEMORY=1 CLAUDE_CODE_DISABLE_CLAUDE_MDS=1 \\
    claude -p --system-prompt-file <the spec's body> --setting-sources "" \\
      --disable-slash-commands --strict-mcp-config --mcp-config '{"mcpServers":{}}' \\
      --tools "" --model <the spec's tier> --no-session-persistence \\
      --output-format stream-json --verbose            (the prompt on stdin)

The run's environment is built from a short list of the caller's variables
(`PASS`: the home, the path, the locale, the certificates and proxies, and
the harness's configuration directory and sign-in token), with `PWD` set to
the run's directory and the two variables above added; nothing else of the
caller's reaches it, a session's project, plugin root or plugin
directories, an address for the service or a remapping of a tier among
them. The system prompt is the whole body of a spec under the plugin's
`clean/`, whose frontmatter `model:` names the tier, the one place a tier
is named; the specs stand outside `agents/`, so no session can start them
as helpers. `stream-json` is read for every `init` event, which lists the
tools, MCP servers, slash commands, skills, agents and plugins the run
holds, and for its result, which counts the model turns: each run is read
for cleanliness from them, mechanically, and never by asking the model.

What is left, the stated residue (`STATED`): the lines the harness adds to
every system prompt and first message: a billing line and an identity line
above the spec's body; a reminder giving the account's email address with
instructions for its use; and an environment block giving the working
directory, whether it is a repository, the platform, the shell, the OS
version, two lines on untrusted downloads, the model's name and exact id,
the knowledge cutoff and the date (no documented way drops them without an
API key); the harness's built-in plugins; the names of its built-in agents,
which a run with no tools cannot start; and a messaging socket the run
opens, which nothing reads. `init` must show the four lists empty, every
plugin built in, the agents a list, no additional directory, the default
output style and the run's own directory; anything else there makes the run
unclean. What `init` does not list is not seen by this script.

The harness reads some of a prompt itself before any model sees it: a token
`@<path>` puts a file of the machine into the run, and a prompt opening with
`/` is a command of the harness's. So every prompt opens with a fixed line
this script writes; a question, packet or redraw signal in which a token
opens with `@` followed by anything but a space is refused before any run,
the token named; a question opening with `/` or `!` is refused; and a draw
whose run made other than one model turn is refused and not kept.

    clean_turn.py probe [--dry-run]
        One run of the probe spec. Prints what the run's context held, as
        JSON. Exit 0 only where nothing but the stated residue was there.

    clean_turn.py answer --packet FILE --question FILE --out DIR [--draws N]
                         (--approval FILE | --drawn-from FILE) --leak FILE [--dry-run]
        N independent draws (3 by default) of the answerer spec, each its own
        process in its own empty directory, over the packet and the question.
        Refuses a packet whose fingerprint file (FILE.fingerprint.json) does
        not name `packet.py` or does not match it; a leak record not naming
        `public.py question` with exit 0, or made over other bytes than the
        question's, or over another graph than the packet's; and a question
        whose origin is not shown: `--approval`, a JSON object holding
        `sha256`, the SHA-256 of exactly this question, and `approved`, the
        ISO time the principal approved it (other keys are let be), or
        `--drawn-from`, a drawer
        run's record in which this exact question stands as a line. These
        records bind each check to an exact text and catch drift; they are
        plain files, and one written by hand with the right hash passes.
        Writes `draw-<i>.json` for each draw (the answer verbatim, the tier,
        the harness's version, the run's session id and cost, the flags, the
        residue seen, and the SHA-256 of spec, packet and question) and
        `manifest.json`. A draw whose run was not clean, made other than one
        model turn, or whose answer holds the account's email address, its
        local part, the run's directory, a packet's mark or a token opening
        with `@`, is refused and not written, and the rest are still drawn.
        A packet cut for question n of a line is taken only with that
        question's `question.md` and `draws/` of the line, and only while
        the line, read again, carries what the packet's fingerprint says it
        carried; a question in a question's directory of a line is refused
        over any other packet. No draw is chosen over another by what it
        says: every one kept is kept, and the first kept is the answer of
        record a later packet carries (`packet.py --line`).

    clean_turn.py draw --packet FILE --out DIR [--from "<opening words>"] [--dry-run]
        One run of the drawer spec over the packet alone. `--from` is the
        redraw signal: the opening words of one answer of the packet, at
        least four words and matching the opening of exactly one answer, so
        that nothing but the AI's own words reaches the run by it and the
        answer meant is not in doubt. Writes `draw-1.json`, with the
        drawer's lines under `answer` and parsed under `questions`, and
        `manifest.json`.

The out directory is claimed by creating its `manifest.json` exclusively
before any run, and every draw is created exclusively: two runs into one
directory never overwrite each other, and the second is refused.

`--dry-run` prints the exact command, the system prompt and the prompt it
would send, after every check but the account's, and runs nothing.

Exit codes, one for each refusal: 0 done; 2 usage, a question that cannot be
read; 3 the packet; 4 the leak record; 5 the question's origin; 6 a run not
clean; 7 an answer that gives the account or the run's directory away; 8 a
run that failed or made other than one model turn; 9 the account's email
address could not be read; 10 a spec; 11 the out directory already holds
draws, is claimed, or is a file; 12 a redraw signal that opens no one answer
of the packet; 13 text the harness would read itself (an `@` token, a
question opening with `/` or `!`; an answer holding an `@` token); 14 a
question or an answer holding a packet's mark.
Where several draws are refused, the first refusal's code is the exit.

Python's standard library only, and `packet.py` beside it for the marks.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile

try:  # stop quietly, rather than with a traceback, when the pipe printed to closes
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
except (AttributeError, ValueError):
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CLEAN = os.path.join(ROOT, "clean")
sys.path.insert(0, HERE)

import packet as packets  # noqa: E402

PROGRAM = "claude"
#: what the run's environment is given beyond what it keeps of the caller's
SET = {"CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1", "CLAUDE_CODE_DISABLE_CLAUDE_MDS": "1"}
#: the caller's variables the run keeps, and no other: where the home, the
#: programs, the locale, the certificates and proxies, and the harness's
#: configuration and sign-in are
PASS = ("HOME", "PATH", "USER", "LOGNAME", "LANG", "LC_ALL", "LC_CTYPE", "TZ", "TERM",
        "SSL_CERT_FILE", "SSL_CERT_DIR", "NIX_SSL_CERT_FILE", "NODE_EXTRA_CA_CERTS",
        "HTTPS_PROXY", "HTTP_PROXY", "NO_PROXY", "https_proxy", "http_proxy", "no_proxy",
        "CLAUDE_CONFIG_DIR", "CLAUDE_CODE_OAUTH_TOKEN")
#: where a run's directory is made, outside any repository
RUNS = "/tmp"
#: how long one run may take, in seconds
TIMEOUT = 900

(DONE, USAGE, PACKET, LEAK, ORIGIN, UNCLEAN, EXPOSED, RUN, ACCOUNT, SPEC, OUT, SIGNAL,
 HARNESS, MARK) = (0, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14)

#: what packet.py writes beside a packet, and the name it gives itself
SIDECAR = packets.SIDECAR
PACKET_TOOL = packets.TOOL
LEAK_TOOL = "public.py question"
#: the fixed first line of every prompt, so that no prompt opens with text
#: of a question's or a packet's
OPENING = ("This is one clean turn. Below are your own earlier answers, each under the "
           "question it was given to, oldest first; then the one question you are asked now.")
NO_EARLIER = ("This is one clean turn. You have given no earlier answer; below is the one "
              "question you are asked now.")
DRAW_OPENING = ("This is one clean turn. Below are your own earlier answers, each under the "
                "question it was given to, oldest first.")
#: the mark the question now put stands under
NOW = "<<< the question you are asked now >>>"
#: the separator of a drawer's line, after its question
FROM = " | from: "
#: a drawer's line, whole
DRAWN = re.compile(r"^(?P<q>.+?) \| from: (?P<from>.+?) \| clause: (?P<clause>.+?) \| "
                   r"direction: (?P<dir>up|down)$")
#: a token the harness expands: `@` not inside a word, an address's, and
#: followed by anything but an ASCII space, tab or line end (the harness's
#: idea of a space is narrower than Python's, so no other is trusted)
AT = re.compile(r"(?<![\w.+\-])@(?![ \t\r\n]|\Z)")
#: the fewest words a redraw signal holds
SIGNAL_WORDS = 4

PROBE_PROMPT = "Reply with the single word: ready"
STATED = ("a billing line and an identity line the harness puts above the spec's body",
          "a reminder giving the account's email address, with instructions for its use",
          "an environment block: the working directory, whether it is a repository, the "
          "platform, the shell, the OS version, two lines on untrusted downloads, the model's "
          "name and exact id, the knowledge cutoff and the date",
          "the harness's built-in plugins",
          "the names of the harness's built-in agents, which a run with no tools cannot start",
          "a messaging socket the run opens, which nothing reads")
#: what `init` must list as empty
EMPTY = ("tools", "mcp_servers", "slash_commands", "skills", "additional_directories")


class Refusal(Exception):
    def __init__(self, code: int, why: str):
        super().__init__(why)
        self.code = code


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# -- the specs -----------------------------------------------------------------

def spec(name: str, where: str = CLEAN) -> dict:
    """A spec of `clean/`: its fields, its body (the whole system prompt),
    and the SHA-256 of the file."""
    path = os.path.join(where, name + ".md")
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError as exc:
        raise Refusal(SPEC, "no spec %s" % name) from exc
    text = raw.decode("utf-8")
    if not text.startswith("---\n"):
        raise Refusal(SPEC, "the spec %s has no frontmatter" % name)
    head, sep, body = text[4:].partition("\n---\n")
    if not sep:
        raise Refusal(SPEC, "the spec %s has an unclosed frontmatter" % name)
    fields = {}
    for line in head.splitlines():
        key, colon, value = line.partition(":")
        if not colon:
            raise Refusal(SPEC, "the spec %s: %r is no field" % (name, line))
        fields[key.strip()] = value.strip()
    if fields.get("name") != name or not fields.get("model") or not body.strip():
        raise Refusal(SPEC, "the spec %s needs its name, a model and a body" % name)
    return {"name": name, "tier": fields["model"], "body": body.strip() + "\n",
            "sha256": sha256(raw)}


# -- what is checked before a run ---------------------------------------------

def _json(path: str, code: int, what: str) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            got = json.load(fh)
    except (OSError, ValueError) as exc:
        raise Refusal(code, "%s cannot be read" % what) from exc
    if not isinstance(got, dict):
        raise Refusal(code, "%s is not an object" % what)
    return got


def expands(text: str, what: str) -> None:
    """Refuse text in which a token opens with `@` and something but a
    space follows: the harness would read a file of the machine into the
    run by it."""
    found = AT.search(text)
    if found:
        start = found.start()
        end = len(text)
        for i in range(start, len(text)):
            if text[i].isspace():
                end = i
                break
        raise Refusal(HARNESS, "%s holds the token %r, which the harness would expand into a "
                               "file of the machine: reword it without a token opening with @"
                      % (what, text[start:end]))


def packet(path: str) -> tuple:
    """The packet's text, its SHA-256 and its fingerprint, where the
    fingerprint file names packet.py and matches it."""
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError as exc:
        raise Refusal(PACKET, "the packet cannot be read") from exc
    side = _json(path + SIDECAR, PACKET, "the packet's fingerprint")
    if side.get("tool") != PACKET_TOOL:
        raise Refusal(PACKET, "the packet's fingerprint does not name %s" % PACKET_TOOL)
    if side.get("sha256") != sha256(raw):
        raise Refusal(PACKET, "the packet does not match its fingerprint")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise Refusal(PACKET, "the packet is not UTF-8") from exc
    expands(text, "the packet")
    return text, sha256(raw), side


def question(path: str) -> tuple:
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError as exc:
        raise Refusal(USAGE, "the question cannot be read") from exc
    try:
        text = raw.decode("utf-8").strip()
    except UnicodeDecodeError as exc:
        raise Refusal(USAGE, "the question is not UTF-8") from exc
    if not text:
        raise Refusal(USAGE, "the question is empty")
    if text[0] in "/!":
        raise Refusal(HARNESS, "the question opens with %r, which the harness reads as its own "
                               "command" % text[0])
    expands(text, "the question")
    mark = packets.forged(text)
    if mark:
        raise Refusal(MARK, "the question holds %r, which marks a packet's parts" % mark)
    return text, sha256(raw)


def leak(path: str, qsha: str, graph_sha) -> str:
    got = _json(path, LEAK, "the leak record")
    if got.get("tool") != LEAK_TOOL or got.get("exit") != 0:
        raise Refusal(LEAK, "the leak record is not a pass of %s" % LEAK_TOOL)
    if got.get("sha256") != qsha:
        raise Refusal(LEAK, "the leak record was made over another text")
    if not graph_sha or got.get("graph_sha256") != graph_sha:
        # the question is checked against the graph the packet was cut from:
        # a graph read again since may hold words the question now quotes
        raise Refusal(LEAK, "the leak record was made over another graph than the packet's; "
                            "check the question again over the packet's graph")
    with open(path, "rb") as fh:
        return sha256(fh.read())


def _time(value) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def drawn_lines(answer: str) -> list:
    """The questions of a drawer's reply: the question of each line in the
    form the drawer's spec gives, and no other line."""
    out = []
    for line in answer.splitlines():
        found = DRAWN.match(line.strip())
        if found and found.group("q").strip():
            out.append(found.group("q").strip())
    return out


def origin(approval, drawn_from, qtext: str, qsha: str) -> dict:
    """The question's origin, shown: the principal's approval of exactly
    this text, or a drawer's run in which it stands as a line."""
    if approval:
        got = _json(approval, ORIGIN, "the approval")
        if got.get("sha256") != qsha:
            raise Refusal(ORIGIN, "the approval is of another text")
        if not _time(got.get("approved")):
            raise Refusal(ORIGIN, "the approval says not when the principal approved it: it is a "
                                  "JSON object with the keys \"sha256\" and \"approved\" (an "
                                  "ISO time), and other keys beside them are let be; it holds %s"
                          % (", ".join(sorted(map(repr, got))) or "no key"))
        with open(approval, "rb") as fh:
            return {"approval_sha256": sha256(fh.read()), "approved": got["approved"]}
    got = _json(drawn_from, ORIGIN, "the drawer's record")
    answer = got.get("answer")
    if (got.get("kind") != "drawer" or not isinstance(answer, str)
            or got.get("answer_sha256") != sha256(answer.encode("utf-8"))):
        raise Refusal(ORIGIN, "the drawer's record does not match itself")
    if qtext not in drawn_lines(answer):
        raise Refusal(ORIGIN, "the question does not stand as a line of the drawer's run")
    with open(drawn_from, "rb") as fh:
        return {"drawn_from_sha256": sha256(fh.read())}


def placed(side: dict, packet_path: str, question_path: str, out: str) -> None:
    """The packet, the question and the out directory are of one place on
    a line, and the line still stands as the packet was cut from it.

    A packet cut for question n of a line (its fingerprint names the line
    and n) is answered only for ``<line>/<n>/question.md`` into
    ``<line>/<n>/draws``, and only while the line, read again now, carries
    what the fingerprint says it carried. A question in a question's
    directory of a line, ``<line>/<n>/``, and an out directory that is a
    question's ``draws``, each read through any link, are answered only over
    such a packet."""
    real = os.path.realpath
    upto, line_dir = side.get("for"), side.get("line_dir")
    qdir = os.path.dirname(real(question_path))
    if upto is None:
        if packets.NUMBER.fullmatch(os.path.basename(qdir)):
            raise Refusal(PACKET, "the question stands in question %s's directory of a line, "
                                  "and the packet was not cut for it: cut it with "
                                  "packet.py --line" % os.path.basename(qdir))
        target = real(out)
        if os.path.basename(target) == "draws" \
                and packets.NUMBER.fullmatch(os.path.basename(os.path.dirname(target))):
            raise Refusal(PACKET, "the out directory is the draws of question %s of a line, "
                                  "and the packet was not cut for it: cut it with "
                                  "packet.py --line"
                          % os.path.basename(os.path.dirname(target)))
        return
    if not isinstance(upto, int) or isinstance(upto, bool) or not isinstance(line_dir, str):
        raise Refusal(PACKET, "the packet's fingerprint names no line and question rightly")
    where = os.path.join(line_dir, str(upto))
    for given, want, what in ((packet_path, "packet.md", "the packet"),
                              (question_path, "question.md", "the question"),
                              (out, "draws", "the out directory")):
        if real(given) != real(os.path.join(where, want)):
            raise Refusal(PACKET, "the packet is for question %d of its line, and %s is not "
                                  "%s" % (upto, what, os.path.join(where, want)))
    try:
        _pairs, carried = packets.line(line_dir, upto)
    except packets.Refused as exc:
        raise Refusal(PACKET, "the line no longer stands as the packet was cut from it: %s"
                      % exc) from exc
    if carried != side.get("line"):
        raise Refusal(PACKET, "the line no longer stands as the packet was cut from it: cut "
                              "the packet again")


def fresh(out: str) -> None:
    if os.path.exists(out) and not os.path.isdir(out):
        raise Refusal(OUT, "the out directory names a file")
    if os.path.isdir(out) and any(n.startswith("draw-") or n == "manifest.json"
                                  for n in os.listdir(out)):
        raise Refusal(OUT, "the out directory already holds draws; every draw is kept, so "
                           "give a new one")


def opening_of(answers, signal: str) -> str:
    """The redraw signal, its whitespace made single, where it opens exactly
    one answer of the packet at a word's end and holds at least
    ``SIGNAL_WORDS`` words; refused otherwise."""
    words = signal.split()
    if len(words) < SIGNAL_WORDS:
        raise Refusal(SIGNAL, "the redraw signal holds fewer than %d words" % SIGNAL_WORDS)
    signal = " ".join(words)
    opens = 0
    for answer in answers:
        flat = " ".join(answer.split())
        if flat.startswith(signal) and (len(flat) == len(signal)
                                        or not flat[len(signal)].isalnum()):
            opens += 1
    if opens != 1:
        raise Refusal(SIGNAL, "the redraw signal opens %s answer of the packet, and must open "
                              "exactly one" % ("no" if not opens else "more than one"))
    return signal


# -- the run -------------------------------------------------------------------

def flags(system_file: str, tier: str) -> list:
    return ["-p", "--system-prompt-file", system_file, "--setting-sources", "",
            "--disable-slash-commands", "--strict-mcp-config",
            "--mcp-config", '{"mcpServers":{}}', "--tools", "", "--model", tier,
            "--no-session-persistence", "--output-format", "stream-json", "--verbose"]


def environment(base=None, cwd=None) -> dict:
    """The run's environment: the caller's variables `PASS` names and no
    other, `PWD` the run's directory, and `SET`."""
    base = os.environ if base is None else base
    env = {k: base[k] for k in PASS if k in base}
    if cwd:
        env["PWD"] = cwd
    env.update(SET)
    return env


def in_repository(path: str) -> bool:
    """Whether the path or a directory above it holds `.git`."""
    path = os.path.realpath(path)
    while True:
        if os.path.exists(os.path.join(path, ".git")):
            return True
        parent = os.path.dirname(path)
        if parent == path:
            return False
        path = parent


def shown(cmd: list) -> str:
    return " ".join("%s=%s" % kv for kv in sorted(SET.items())) + " " + shlex.join(cmd)


def dry(cmd: list, system: str, prompt: str) -> None:
    print("command, run in a fresh empty directory under %s, the prompt on stdin:" % RUNS)
    print(shown(cmd))
    print("\nsystem prompt:")
    print(system, end="" if system.endswith("\n") else "\n")
    print("\nprompt:")
    print(prompt, end="" if prompt.endswith("\n") else "\n")


def events(stdout: str) -> list:
    out = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            got = json.loads(line)
        except ValueError:
            continue
        if isinstance(got, dict):
            out.append(got)
    return out


def residue(inits: list, cwd: str) -> tuple:
    """What the `init` events show the run held, and what of it is beyond
    the stated residue. Every `init` is read, and a key missing counts as
    held."""
    first = inits[0]
    seen = {k: first.get(k) for k in EMPTY + ("plugins", "agents", "cwd", "original_cwd",
                                              "output_style", "apiKeySource")}
    extra = []

    def add(key):
        if key not in extra:
            extra.append(key)
    if len(inits) > 1:
        add("init")
    for init in inits:
        for key in EMPTY:
            if not isinstance(init.get(key), list) or init.get(key) != []:
                add(key)
        plugins = init.get("plugins")
        if not isinstance(plugins, list) or any(
                not isinstance(p, dict) or p.get("path") != "builtin"
                or p.get("source") != "%s@builtin" % p.get("name") for p in plugins):
            add("plugins")
        if not isinstance(init.get("agents"), list):
            add("agents")
        if init.get("output_style") != "default":
            add("output_style")
        for key in ("cwd", "original_cwd"):
            if os.path.realpath(str(init.get(key) or "")) != os.path.realpath(cwd):
                add(key)
    return seen, extra


def run(system: str, prompt: str, tier: str, runner=subprocess.run) -> dict:
    """One run, in a fresh empty directory, its system prompt in a file of
    another; both are removed after. Returns what the run showed."""
    where = RUNS if os.path.isdir(RUNS) else None
    work = tempfile.mkdtemp(prefix="t", dir=where)
    keep = tempfile.mkdtemp(prefix="s", dir=where)
    try:
        if in_repository(work):
            return {"ok": False, "why": "the run's directory is inside a repository", "cwd": work}
        system_file = os.path.join(keep, "p")
        with open(system_file, "w", encoding="utf-8") as fh:
            fh.write(system)
        cmd = [PROGRAM] + flags(system_file, tier)
        try:
            done = runner(cmd, input=prompt, cwd=work, env=environment(cwd=work),
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=TIMEOUT)
        except (OSError, subprocess.SubprocessError) as exc:
            return {"ok": False, "why": "the run could not be started: %s" % exc,
                    "cwd": work}
        got = events(done.stdout or "")
        inits = [e for e in got if e.get("type") == "system" and e.get("subtype") == "init"]
        result = next((e for e in reversed(got) if e.get("type") == "result"), None)
        out = {"ok": True, "cwd": work, "returncode": done.returncode,
               "flags": [PROGRAM] + flags("<the spec's body>", tier)}
        if done.returncode != 0 or not inits or result is None \
                or result.get("is_error") or not isinstance(result.get("result"), str):
            out.update(ok=False, why="the run failed (exit %s)" % done.returncode)
            return out
        turns = result.get("num_turns")
        if turns != 1:
            # a prompt the harness answered itself makes no model turn; one
            # that ran on makes more than one; neither is a model's answer
            out.update(ok=False, why="the run made %s model turn(s), not one" % turns)
            return out
        seen, extra = residue(inits, work)
        out.update(answer=result["result"], seen=seen, extra=extra,
                   session_id=result.get("session_id") or inits[0].get("session_id"),
                   cost_usd=result.get("total_cost_usd"),
                   cli_version=inits[0].get("claude_code_version"), model=inits[0].get("model"))
        return out
    finally:
        shutil.rmtree(work, ignore_errors=True)
        shutil.rmtree(keep, ignore_errors=True)


def account(runner=subprocess.run) -> str:
    """The account's email address, read from the harness, to be kept out of
    every answer and never written anywhere."""
    try:
        done = runner([PROGRAM, "auth", "status", "--json"], capture_output=True, text=True,
                      timeout=60, env=environment(), cwd=RUNS)
        email = json.loads(done.stdout).get("email")
    except (OSError, ValueError, AttributeError, subprocess.SubprocessError) as exc:
        raise Refusal(ACCOUNT, "the account's email address could not be read") from exc
    if not isinstance(email, str) or "@" not in email:
        raise Refusal(ACCOUNT, "the account's email address could not be read")
    return email


def exposed(answer: str, email: str, cwd: str) -> str:
    """What of the account or the run an answer gives away, or ''."""
    low = answer.casefold()
    if email.casefold() in low:
        return "the account's email address"
    local = email.split("@", 1)[0].casefold()
    if local and re.search(r"(?<![\w.])%s(?!\w)" % re.escape(local), low):
        return "the local part of the account's email address"
    if cwd and (cwd in answer or os.path.basename(cwd).casefold() in low):
        return "the run's working directory"
    return ""


def judged(got: dict, email: str) -> tuple:
    """A run's code and the reason, where it is refused; (0, '') where kept."""
    if not got.get("ok"):
        return RUN, got.get("why", "the run failed")
    if got["extra"]:
        return UNCLEAN, "the run held more than the stated residue: %s" % ", ".join(got["extra"])
    why = exposed(got["answer"], email, got["cwd"])
    if why:
        return EXPOSED, "the answer holds %s" % why
    # an answer no later packet could carry, or no later turn could be
    # given, is not kept: the next kept draw is of record by the same rule
    mark = packets.forged(got["answer"])
    if mark:
        return MARK, "the answer holds %r, which marks a packet's parts" % mark
    if AT.search(got["answer"]):
        return HARNESS, "the answer holds a token opening with @, which the harness would " \
                        "expand in every later turn that carries it"
    return DONE, ""


def record(got: dict, kind: str, index: int, sp: dict, shas: dict) -> dict:
    return dict({"kind": kind, "index": index, "answer": got["answer"],
                 "answer_sha256": sha256(got["answer"].encode("utf-8")),
                 "tier": sp["tier"], "cli_version": got.get("cli_version"),
                 "model": got.get("model"), "session_id": got.get("session_id"),
                 "cost_usd": got.get("cost_usd"), "flags": got["flags"],
                 "environment": SET,
                 "residue": {"stated": list(STATED), "seen": got["seen"]},
                 "spec_sha256": sp["sha256"], "created": now()}, **shas)


def _dump(fh, obj) -> None:
    json.dump(obj, fh, indent=2, ensure_ascii=False)
    fh.write("\n")


def _create(path: str, obj) -> None:
    """A file created exclusively: never over one that stands."""
    try:
        with open(path, "x", encoding="utf-8") as fh:
            _dump(fh, obj)
    except FileExistsError as exc:
        raise Refusal(OUT, "%s already stands; every draw is kept, so give a new directory"
                      % os.path.basename(path)) from exc


def claim(out: str, kind: str) -> None:
    """The out directory claimed for this run, by creating its manifest
    exclusively, before any run; a second claim is refused."""
    try:
        os.makedirs(out, exist_ok=True)
    except OSError as exc:
        raise Refusal(OUT, "the out directory cannot be made") from exc
    _create(os.path.join(out, "manifest.json"),
            {"kind": kind, "state": "running", "created": now()})


def finish(out: str, manifest: dict) -> None:
    """The manifest written whole over the claim, by a rename."""
    path = os.path.join(out, "manifest.json")
    part = path + ".part"
    with open(part, "w", encoding="utf-8") as fh:
        _dump(fh, manifest)
    os.replace(part, path)


# -- the modes -----------------------------------------------------------------

def probe(args, runner) -> int:
    sp = spec("probe")
    if args.dry_run:
        dry([PROGRAM] + flags("<a file holding the system prompt>", sp["tier"]), sp["body"],
            PROBE_PROMPT)
        return DONE
    got = run(sp["body"], PROBE_PROMPT + "\n", sp["tier"], runner)
    if not got.get("ok"):
        print(json.dumps({"clean": False, "why": got.get("why")}, indent=2))
        return RUN
    print(json.dumps({"clean": not got["extra"], "beyond_the_stated_residue": got["extra"],
                      "stated_residue": list(STATED), "seen": got["seen"],
                      "cli_version": got.get("cli_version")}, indent=2))
    return UNCLEAN if got["extra"] else DONE


def answer_prompt(ptext: str, qtext: str) -> str:
    if ptext.strip():
        return "%s\n\n%s\n%s\n%s\n" % (OPENING, ptext.rstrip("\n"), NOW, qtext)
    return "%s\n\n%s\n%s\n" % (NO_EARLIER, NOW, qtext)


def answer(args, runner) -> int:
    sp = spec("answerer")
    ptext, psha, side = packet(args.packet)
    qtext, qsha = question(args.question)
    placed(side, args.packet, args.question, args.out)
    leak_sha = leak(args.leak, qsha, side.get("graph_sha256"))
    whence = origin(args.approval, args.drawn_from, qtext, qsha)
    fresh(args.out)
    prompt = answer_prompt(ptext, qtext)
    if args.dry_run:
        dry([PROGRAM] + flags("<a file holding the system prompt>", sp["tier"]), sp["body"],
            prompt)
        return DONE
    email = account(runner)
    claim(args.out, "answerer")
    shas = {"packet_sha256": psha, "question_sha256": qsha}
    draws, first = [], DONE
    for i in range(1, args.draws + 1):
        got = run(sp["body"], prompt, sp["tier"], runner)
        code, why = judged(got, email)
        if code:
            draws.append({"index": i, "refused": why})
            first = first or code
            print("draw %d refused: %s" % (i, why), file=sys.stderr)
            continue
        name = "draw-%d.json" % i
        _create(os.path.join(args.out, name), record(got, "answerer", i, sp, shas))
        draws.append({"index": i, "file": name})
    finish(args.out, dict(
        {"kind": "answerer", "tier": sp["tier"], "spec_sha256": sp["sha256"],
         "leak_sha256": leak_sha, "origin": whence, "draws": draws, "chosen": None,
         "of_record": next((d["file"] for d in draws if "file" in d), None),
         "created": now()}, **shas))
    kept = sum(1 for d in draws if "file" in d)
    print("%d of %d draw(s) kept, none chosen by what it says -> %s" % (kept, args.draws,
                                                                       args.out))
    return first


def draw(args, runner) -> int:
    sp = spec("drawer")
    ptext, psha, _side = packet(args.packet)
    if not ptext.strip():
        raise Refusal(PACKET, "the packet holds no answer, so nothing is raised")
    signal = None
    if args.from_words is not None:
        expands(args.from_words, "the redraw signal")
        signal = opening_of([a for _q, a in packets.parse(ptext)], args.from_words)
    fresh(args.out)
    prompt = "%s\n\n%s%s" % (DRAW_OPENING,
                             "Draw from the answer that opens: %s\n\n" % signal if signal else "",
                             ptext)
    if args.dry_run:
        dry([PROGRAM] + flags("<a file holding the system prompt>", sp["tier"]), sp["body"],
            prompt)
        return DONE
    email = account(runner)
    claim(args.out, "drawer")
    got = run(sp["body"], prompt, sp["tier"], runner)
    code, why = judged(got, email)
    shas = {"packet_sha256": psha, "signal": signal}
    if code:
        finish(args.out, dict(
            {"kind": "drawer", "tier": sp["tier"], "spec_sha256": sp["sha256"],
             "draws": [{"index": 1, "refused": why}], "created": now()}, **shas))
        print("draw refused: %s" % why, file=sys.stderr)
        return code
    got_record = record(got, "drawer", 1, sp, shas)
    got_record["questions"] = drawn_lines(got["answer"])
    _create(os.path.join(args.out, "draw-1.json"), got_record)
    finish(args.out, dict(
        {"kind": "drawer", "tier": sp["tier"], "spec_sha256": sp["sha256"],
         "draws": [{"index": 1, "file": "draw-1.json"}], "created": now()}, **shas))
    print("%d question(s) drawn -> %s" % (len(got_record["questions"]), args.out))
    return DONE


def main(argv=None, runner=subprocess.run) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="mode", required=True)
    p = sub.add_parser("probe")
    p.add_argument("--dry-run", action="store_true")
    p = sub.add_parser("answer")
    p.add_argument("--packet", required=True)
    p.add_argument("--question", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--draws", type=int, default=3)
    whence = p.add_mutually_exclusive_group(required=True)
    whence.add_argument("--approval")
    whence.add_argument("--drawn-from")
    p.add_argument("--leak", required=True)
    p.add_argument("--dry-run", action="store_true")
    p = sub.add_parser("draw")
    p.add_argument("--packet", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--from", dest="from_words", metavar="OPENING WORDS")
    p.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    if args.mode == "answer" and args.draws < 1:
        ap.error("--draws is at least 1")
    try:
        return {"probe": probe, "answer": answer, "draw": draw}[args.mode](args, runner)
    except Refusal as exc:
        print("refused: %s" % exc, file=sys.stderr)
        return exc.code


if __name__ == "__main__":
    sys.exit(main())
