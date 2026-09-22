"""hypo — the tools that enforce the hypomnemata document layout.

The source of truth is the Claude Docs artifact. Scripts cannot reach it, so the
AI writes a *graph file* (one JSON file, in a scratch directory, never committed)
from its reads of the document, and renders canonical markdown back from it.

    model    dataclasses and shape validation of the graph file
    spec     the checks, each with an id, a description and a severity
    project  the tab-tree projection: distance, parent, order, load, tabs patch
    render   the markdown renderer and the links sidecar
    read     the inverse of the renderer: an exported tab back into a question
    apply    the operations that put a rendered tab into the document
    verify   the page against the renderer, links included
    portable the notebook parted from its document, and the export cache
    text     plain text from markdown, and where a run of it stands

Enforcement is by interface: the renderer is the only sanctioned way to produce
tab markdown, so a layout violation is impossible if the tool is used, and the
checker catches what the renderer cannot.

What the checker cannot catch is anything that happens after the graph file:
the page is a second artifact, and a link on it was never in the graph. So
``apply`` composes both calls a write takes — the body, and the links the body
write cannot carry — and ``verify`` reads the page back. Every other check in
here would pass over a tab that reached the document with none of its links,
which is exactly what happened.
"""

__all__ = ["model", "spec", "project", "render", "read", "apply", "verify",
           "portable", "text"]
