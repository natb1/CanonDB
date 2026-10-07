"""cli — what every command-line entry point does before its own work.

The scripts beside the package are the tools a run drives, and each of them
prints to whatever it is piped into. A tool piped into ``head`` should stop
when the pipe closes, not print a traceback over the lines the reader asked
for. That is one signal handler, and it stood as seven copies of the same
block at the top of seven scripts until it was one function here — a copy
drifts, and the eighth script would have started from whichever one its
author opened. The same went for loading the graph file and saying what is
wrong with its shape (nine copies, one of them already spelling the line
another way), for taking a saved read from a file or stdin, for reading a
directory of exports or of outlines, and for the question a saved read's
name is of.

What cannot move here is the line before the import: a script finds this
package by its own directory, and has to say so before it can import it.
"""

from __future__ import annotations

import os
import signal
import sys
from typing import Dict, Iterable, List, Optional

from . import apply, model


def quiet_pipe() -> None:
    """Stop, rather than traceback, when the pipe this tool prints to closes.

    Restores the default action for ``SIGPIPE``, which Python turns off at
    start-up in favour of raising on the write. Not POSIX, or not the main
    thread, and there is nothing to restore: the tool prints as it did.
    """
    try:
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    except (AttributeError, ValueError):  # pragma: no cover - not POSIX, not main thread
        pass


def load_graph(path: str) -> Optional[model.Graph]:
    """The graph file, or None once every problem with its shape is said on
    stderr, one ``ERROR shape:`` line each — the one spelling, for every
    tool and whatever greps them."""
    try:
        return model.load(path)
    except model.ShapeError as exc:
        for problem in exc.problems:
            print("ERROR shape: %s" % problem, file=sys.stderr)
        return None


def source(path: str) -> str:
    """A saved read, from its file or from stdin for ``-``."""
    if path == "-":
        return sys.stdin.read()
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def exports(directory: str) -> Dict[str, str]:
    """question id -> its tab's markdown, from a directory of ``<question
    id>.md`` files, in name order."""
    found: Dict[str, str] = {}
    for entry in sorted(os.listdir(directory)):
        if entry.endswith(".md"):
            with open(os.path.join(directory, entry), encoding="utf-8") as fh:
                found[entry[:-3]] = fh.read()
    return found


def outlines(graph: model.Graph, directory: str,
             questions: Optional[Iterable[str]] = None) -> Dict[str, List[apply.Block]]:
    """tab id -> its parsed outline, from the ``<question id>.xml`` files in
    ``directory``: every one on disk, or, with ``questions`` named, those
    tabs' and no other, each of which must be there."""
    by_id = graph.by_id()
    found: Dict[str, List[apply.Block]] = {}
    named = list(questions) if questions is not None else [q.id for q in graph.questions]
    for qid in named:
        path = os.path.join(directory, qid + ".xml")
        if questions is None and not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as fh:
            found[by_id[qid].tab] = apply.parse_outline(fh.read())
    return found


def question_of(path: str) -> str:
    """The question a saved read or view is of, by its file's name: up to
    the first dot, so ``<question>.json`` and ``<question>.<part>.json``
    name one tab."""
    return os.path.basename(path).split(".", 1)[0]
