"""cli — what every command-line entry point does before its own work.

The scripts beside the package are the tools a run drives, and each of them
prints to whatever it is piped into. A tool piped into ``head`` should stop
when the pipe closes, not print a traceback over the lines the reader asked
for. That is one signal handler, and it stood as seven copies of the same
block at the top of seven scripts until it was one function here — a copy
drifts, and the eighth script would have started from whichever one its
author opened.

What cannot move here is the line before the import: a script finds this
package by its own directory, and has to say so before it can import it.
"""

from __future__ import annotations

import signal


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
