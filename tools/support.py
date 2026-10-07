"""What the test modules share, spelled once.

The fixtures directory, a graph loaded from a fixture, a fixture rewritten
before it is loaded, the chip map a document's file list would supply, and
a tool run in this process with its streams captured. Eleven modules each
carried a copy of the first three, and six spawned the tools as processes:
forty spawns, and a third of the suite's time, to test what a call tests.

Not a test module: ``unittest`` collects ``test_*.py`` and this is not one.
"""

from __future__ import annotations

import contextlib
import importlib
import io
import json
import os
import sys
import tempfile
from typing import Callable, NamedTuple, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(HERE, "fixtures")
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from hypo import model, render  # noqa: E402


def fixture(name: str) -> str:
    """The path of a fixture: a graph by its bare name, anything else by its
    file name."""
    return os.path.join(FIXTURES, name if "." in name else name + ".json")


def read_fixture(name: str) -> str:
    """A fixture's text, by its file name."""
    with open(fixture(name), encoding="utf-8") as fh:
        return fh.read()


def load(name: str = "valid") -> model.Graph:
    """A fixture graph, loaded."""
    return model.load(fixture(name))


def rewrite(name: str, mutate: Callable[[dict], None]) -> model.Graph:
    """A fixture loaded after ``mutate`` has changed its JSON: the shape
    checks run on the result, as they would on a file."""
    with open(fixture(name), encoding="utf-8") as fh:
        data = json.load(fh)
    mutate(data)
    handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                         encoding="utf-8")
    try:
        json.dump(data, handle)
        handle.close()
        return model.load(handle.name)
    finally:
        os.unlink(handle.name)


def chip_ids(graph: model.Graph) -> dict:
    """The map the document's file list supplies: chip key back to question."""
    return {render.chip_key(q.id): q.id for q in graph.questions}


class Done(NamedTuple):
    """What a run of a tool came to: its exit code and its two streams, under
    the names a finished process gives them."""
    returncode: int
    stdout: str
    stderr: str


def run(script: str, *args: str, stdin: Optional[str] = None,
        cwd: Optional[str] = None) -> Done:
    """A tool's ``main`` in this process, as a run from the command line would
    have it: its arguments, what it reads from standard input, the directory
    it runs in, and its exit code and streams back. ``argparse`` ends a run
    with ``SystemExit``, which is the exit code it means. One process test per
    tool (``test_cli.EntryPointTest``) keeps the shebang, the mode bits and
    the real exit honest."""
    tool = importlib.import_module(script[:-3] if script.endswith(".py") else script)
    out, err = io.StringIO(), io.StringIO()
    was, was_stdin = os.getcwd(), sys.stdin
    try:
        if cwd:
            os.chdir(cwd)
        if stdin is not None:
            sys.stdin = io.StringIO(stdin)
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = tool.main(list(args))
            except SystemExit as exc:
                code = exc.code if isinstance(exc.code, int) else (1 if exc.code else 0)
    finally:
        os.chdir(was)
        sys.stdin = was_stdin
    return Done(code or 0, out.getvalue(), err.getvalue())
