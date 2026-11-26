#!/usr/bin/env python3
"""packet.py <graph.json> [<question> | --under ID | --whole] [--line DIR] -o FILE — the AI's own record, for a clean turn.

Writes what a clean turn may hold besides its one question: the AI's own
earlier answers, each under the question it was given to, and nothing else.
An answer without its question loses its meaning, and the question is part
of the AI's public record, so each goes in with its question, marked:

    <<< question >>>
    <the question, as it was put>
    <<< answer >>>
    <the AI's answer, word for word>

the pairs set apart by a blank line. The marks cannot be forged: a question
or an answer whose text holds `<<<` or `>>>` is refused, and no packet is
written. The question now put is not in the packet; `clean_turn.py` puts it
after, under a mark of its own.

    packet.py GRAPH QUESTION -o FILE    the answers above a question of the graph
    packet.py GRAPH --under ID -o FILE  the answers of ID and above it, for a
                                        question not yet on the graph
    packet.py GRAPH --whole -o FILE     every answer of the AI's
    ... --line DIR [--for N]            then the line's own earlier questions
                                        and answers, in the order they were put
    packet.py GRAPH --line DIR -o FILE  the line's alone (a back-brief)

The graph's part comes first, oldest first (nearest the root first, ties by
id). An answer of the graph is the AI's own where its question is one the AI
answers and the answer is past held: one given in a turn is in thread or
landed, and one the user holds as a prior stays held (``hypo.public.own``).
A question above that holds no such answer is not the AI's own, and the
script refuses, naming it, rather than carry it or leave a gap; it refuses
too a graph on which `only-ai-put` or `state-order` fails, since there a
state cannot be trusted to say whose an answer is. Nothing else of a tab goes
in: no headline, hinge, glossary, note, case, application line or id.

The line's part. DIR is a line's directory, `$SCRATCH/lines/<line>`; each
question put on it has a numbered directory, `DIR/<n>`, holding
`question.md` and the draws `clean_turn.py answer` wrote, `draws/manifest.json`
and `draws/draw-<i>.json`. They are read in the order of `<n>`. Several
draws are kept for each question and none is chosen by what it says, so the
rule is fixed in advance: the first draw the manifest lists as kept is the
answer of record, the one later turns carry; the others are the evidence of
whether the answer is stable, and never go in. Each draw carried is checked
against its own `answer_sha256`, against the manifest that lists it, and
against the question's file by `question_sha256`. A numbered directory with
no manifest is a question not yet answered: allowed at the end of the line
(the question about to be put), refused before an answered one, as is a
manifest that kept no draw or one a run claimed and never finished, since
each would leave a gap. The numbers are ASCII digits from 1 with no leading
zero and no hole, no question's directory a link; any other name of digits
is refused. A question whose directory holds `lead.json`, the record of the
reading of whether it leads the answerer (`lead.py`), with any verdict but
`does not lead`, is refused by number: a question found to have led is not
carried, and is set aside with every later question of the line by
`lead.py aside` before the line goes on. So is a question whose manifest
says it was put on a reading (`origin.lead_sha256`) and whose `lead.json` is
gone. A question with neither, one a drawer turn raised or one put before
readings were recorded, is read as before. What a line set aside, under its
`held/`, is not read. A drawer turn's directory, `drawn-<n>`, holds no answer and is
not read.

A packet written into a question's directory of the line, `DIR/<n>/`, or
given `--for <n>`, is for question n: every question before it must be
answered, and n and none after it not yet. Its fingerprint then names the
line's directory and n, and `clean_turn.py answer` reads the line again
before any run and refuses a packet the line has moved past.

Beside FILE it writes FILE.fingerprint.json: the tool's name, the packet's
SHA-256, the graph's, how many answers went in, and for the line each
question's number, its SHA-256, the draw carried and that draw's SHA-256.
The fingerprint binds a check to an exact text and catches drift; it is no
signature, and a fingerprint written by hand with the right hash passes.
Prints one line: the count and where. Exit 1 on a refusal.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hypo import cli, project, public, spec, turn  # noqa: E402

cli.quiet_pipe()

#: the marks a packet sets each question and answer under
QUESTION = "<<< question >>>"
ANSWER = "<<< answer >>>"
#: what no question or answer may hold, so that no mark can be forged
BOUNDARY = ("<<<", ">>>")
#: the sidecar's suffix and the name it gives this tool
SIDECAR = ".fingerprint.json"
TOOL = "packet.py"
#: the checks without which a state cannot be trusted to say whose an answer is
TRUSTED = ("only-ai-put", "state-order")
#: a question's directory: a number in ASCII digits, from 1, no leading zero
NUMBER = re.compile(r"[1-9][0-9]*")
#: the record, in a question's directory, of the reading of whether the
#: question leads the answerer (`lead.py`), and the one verdict that lets
#: its draws be carried
LEAD = "lead.json"
CLEAR = "does not lead"


class Refused(ValueError):
    """A packet that would hold what is not the AI's own, leave a gap, or
    hold a forged mark."""


def forged(text: str) -> str:
    """The boundary a text holds, or ''."""
    for mark in BOUNDARY:
        if mark in text:
            return mark
    return ""


def _pair(question: str, answer: str, where: str) -> tuple:
    question, answer = question.strip(), answer.strip()
    for what, words in (("question", question), ("answer", answer)):
        mark = forged(words)
        if mark:
            raise Refused("the %s of %s holds %r, which marks a packet's parts: not carried"
                          % (what, where, mark))
    return question, answer


def _trusted(graph) -> None:
    found = [f.line() for f in spec.run(graph, only=TRUSTED)]
    if found:
        raise Refused("the graph fails %s, so whose an answer is cannot be read off it: %s"
                      % (" or ".join(TRUSTED), "; ".join(found)))


def _ordered(graph, ids):
    dist = project.distances(graph)
    return sorted(set(ids), key=lambda s: (dist.get(s, project.INF), s))


def _answers(graph, ids):
    _trusted(graph)
    by_id = graph.by_id()
    out = []
    for qid in _ordered(graph, ids):
        q = by_id[qid]
        if q.answerer != project.AI or not q.claude:
            raise Refused("%s holds no answer of the AI's own: it is not carried, and a "
                          "packet with a gap is not written" % qid)
        out += [_pair(q.question, t.text, qid) for t in public.own(q) if t.text.strip()]
    return out


def above(graph, qid):
    """The AI's own answers above a question of the graph, each with its
    question."""
    if qid not in graph.by_id():
        raise Refused("no such question: %s" % qid)
    return _answers(graph, turn.above(graph, qid))


def under(graph, qid):
    """The AI's own answers of ``qid`` and above it."""
    if qid not in graph.by_id():
        raise Refused("no such question: %s" % qid)
    return _answers(graph, [qid] + turn.above(graph, qid))


def whole(graph):
    """Every answer of the AI's."""
    return _answers(graph, [q.id for q in graph.questions
                            if q.answerer == project.AI and q.claude])


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read(path: str, what: str) -> bytes:
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except OSError as exc:
        raise Refused("%s cannot be read" % what) from exc


def _json(path: str, what: str) -> dict:
    try:
        got = json.loads(_read(path, what).decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise Refused("%s is not JSON" % what) from exc
    if not isinstance(got, dict):
        raise Refused("%s is not an object" % what)
    return got


def numbered(directory: str) -> list:
    """The line's question directories, by number: each named in ASCII
    digits from 1 with no leading zero, none a link, the numbers 1 to k
    without a hole. Any other name of digits alone is refused, since two
    names of one number, or a number the order cannot read, would carry a
    question twice or in no fixed order."""
    try:
        names = os.listdir(directory)
    except OSError as exc:
        raise Refused("the line's directory cannot be read") from exc
    found = []
    for n in names:
        if NUMBER.fullmatch(n):
            if os.path.islink(os.path.join(directory, n)):
                raise Refused("question %s of the line is a link: a question's directory is "
                              "its own" % n)
            found.append(n)
        elif n.isdigit() or n.isdecimal() or n.isnumeric():
            raise Refused("%r is no question's number: a line's questions are numbered 1, 2, "
                          "3 in ASCII digits, with no leading zero" % n)
    found.sort(key=int)
    for want, n in enumerate(found, 1):
        if int(n) != want:
            raise Refused("the line has no question %d, and has %s: a line is numbered "
                          "without a hole" % (want, n))
    return found


def line(directory: str, upto=None):
    """The line's own earlier questions and answers, in the order they were
    put, the first kept draw of each; and what was carried, for the
    fingerprint. With ``upto`` N, the packet is for question N: every
    question before it must be answered and N not yet, nor any after it."""
    numbers = numbered(directory)
    if upto is not None:
        if upto < 1:
            raise Refused("a line's questions are counted from 1")
        later = [n for n in numbers if int(n) > upto]
        if later:
            raise Refused("the packet is for question %d, and the line already holds "
                          "question %s" % (upto, later[0]))
        missing = [n for n in range(1, upto) if str(n) not in numbers]
        if missing:
            raise Refused("the packet is for question %d, and the line holds no question %d "
                          "before it" % (upto, missing[0]))
    pairs, carried, pending = [], [], []
    for n in numbers:
        where = "question %s of the line" % n
        manifest_path = os.path.join(directory, n, "draws", "manifest.json")
        if upto is not None and int(n) == upto:
            if os.path.exists(manifest_path):
                raise Refused("question %d of the line is answered already: a packet is cut "
                              "for the question about to be put" % upto)
            continue
        if not os.path.exists(manifest_path):
            if upto is not None:
                raise Refused("%s is not answered, and the packet is for question %d after "
                              "it: a packet with a gap is not written" % (where, upto))
            pending.append(n)
            continue
        if pending:
            raise Refused("question %s of the line is not answered, and %s after it is: a "
                          "packet with a gap is not written" % (pending[0], n))
        raw_q = _read(os.path.join(directory, n, "question.md"), "the question of " + where)
        try:
            qtext = raw_q.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise Refused("the question of %s is not UTF-8" % where) from exc
        manifest = _json(manifest_path, "the manifest of " + where)
        whence = manifest.get("origin") if isinstance(manifest.get("origin"), dict) else {}
        if os.path.lexists(os.path.join(directory, n, LEAD)) or "lead_sha256" in whence:
            if not os.path.lexists(os.path.join(directory, n, LEAD)):
                raise Refused("%s was put on a reading whose record is gone: it is not "
                              "carried" % where)
            reading = _json(os.path.join(directory, n, LEAD), "the record of the reading of "
                            + where)
            if reading.get("verdict") != CLEAR:
                raise Refused("%s was found to lead the answerer: its draws are not carried; "
                              "set it aside, with every later question of the line, by "
                              "lead.py aside, before the line goes on" % where)
        if manifest.get("state") == "running":
            raise Refused("%s was claimed by a run that did not finish: put it again under a "
                          "new number, or drop it, before the line goes on" % where)
        if manifest.get("kind") != "answerer" or manifest.get("question_sha256") != sha256(raw_q):
            raise Refused("the manifest of %s is not of its question as it stands" % where)
        kept = [d.get("file") for d in manifest.get("draws") or ()
                if isinstance(d, dict) and isinstance(d.get("file"), str)]
        if not kept:
            raise Refused("%s kept no draw: put it again under a new number, or drop it, "
                          "before the line goes on" % where)
        name = kept[0]
        if os.path.basename(name) != name or not re.fullmatch(r"draw-\d+\.json", name):
            raise Refused("the manifest of %s names no draw file" % where)
        record = _json(os.path.join(directory, n, "draws", name), "the draw of " + where)
        answer = record.get("answer")
        if (record.get("kind") != "answerer" or not isinstance(answer, str)
                or record.get("answer_sha256") != sha256(answer.encode("utf-8"))
                or record.get("question_sha256") != sha256(raw_q)):
            raise Refused("the draw %s of %s is not the one clean_turn.py wrote over its "
                          "question" % (name, where))
        pairs.append(_pair(qtext, answer, where))
        carried.append({"n": int(n), "question_sha256": sha256(raw_q), "draw": name,
                        "answer_sha256": record["answer_sha256"]})
    return pairs, carried


def text(pairs) -> str:
    """The packet: each answer under its question, the pairs set apart by a
    blank line."""
    return "\n\n".join("%s\n%s\n%s\n%s" % (QUESTION, q, ANSWER, a) for q, a in pairs) \
        + ("\n" if pairs else "")


def parse(packet: str) -> list:
    """A packet's pairs, (question, answer), as `text` wrote them."""
    pairs, part, q, buf = [], None, None, []

    def close():
        nonlocal q
        body = "\n".join(buf).strip()
        if part == QUESTION:
            q = body
        elif part == ANSWER:
            pairs.append((q, body))
    for row in packet.splitlines():
        if row in (QUESTION, ANSWER):
            close()
            part, buf = row, []
        else:
            buf.append(row)
    close()
    return pairs


def placed(directory: str, out: str, given=None):
    """The question a line's packet is for: ``given`` (``--for``), or the
    number of the directory the packet is written into where that is a
    question's directory of the line; the two must agree."""
    parent = os.path.dirname(os.path.abspath(out))
    by_place = None
    if os.path.realpath(os.path.dirname(parent)) == os.path.realpath(directory) \
            and NUMBER.fullmatch(os.path.basename(parent)):
        by_place = int(os.path.basename(parent))
    if given is not None and by_place is not None and given != by_place:
        raise Refused("the packet is for question %d and is written into question %d's "
                      "directory" % (given, by_place))
    return given if given is not None else by_place


def write(out: str, body: str, graph_path: str, count: int, carried=None,
          line_dir=None, upto=None) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    data = body.encode("utf-8")
    with open(out, "wb") as fh:
        fh.write(data)
    with open(graph_path, "rb") as fh:
        graph_sha = sha256(fh.read())
    with open(out + SIDECAR, "w", encoding="utf-8") as fh:
        side = {"tool": TOOL, "sha256": sha256(data), "graph_sha256": graph_sha,
                "answers": count, "line": carried}
        if upto is not None:
            side.update(line_dir=os.path.realpath(line_dir), **{"for": upto})
        json.dump(side, fh, indent=2)
        fh.write("\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("graph", help="the graph file")
    ap.add_argument("question", nargs="?", help="a question of the graph, by id")
    ap.add_argument("--under", metavar="ID", help="the answers of ID and above it")
    ap.add_argument("--whole", action="store_true", help="every answer of the AI's")
    ap.add_argument("--line", metavar="DIR",
                    help="then the line's own earlier questions and answers, from its directory")
    ap.add_argument("--for", dest="upto", type=int, metavar="N",
                    help="the line's question the packet is for (by default, the number of "
                         "the question's directory it is written into)")
    ap.add_argument("-o", "--out", required=True, help="write the packet here")
    args = ap.parse_args(argv)
    modes = sum(bool(x) for x in (args.question, args.under, args.whole))
    if modes > 1 or (modes == 0 and not args.line):
        ap.error("give one of a question, --under or --whole, or --line alone")
    if args.upto is not None and not args.line:
        ap.error("--for is a question of a line: give --line")

    graph = cli.load_graph(args.graph)
    if graph is None:
        return 1
    try:
        if args.whole:
            pairs = whole(graph)
        elif args.under:
            pairs = under(graph, args.under)
        elif args.question:
            pairs = above(graph, args.question)
        else:
            _trusted(graph)
            pairs = []
        carried = upto = None
        if args.line:
            upto = placed(args.line, args.out, args.upto)
            more, carried = line(args.line, upto)
            pairs += more
    except Refused as exc:
        print("not written: %s" % exc, file=sys.stderr)
        return 1
    write(args.out, text(pairs), args.graph, len(pairs), carried, args.line, upto)
    print("%d answer(s) of the AI's own, each with its question -> %s" % (len(pairs), args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
