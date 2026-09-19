"""hypo — the tools that enforce the hypomnemata document layout.

The source of truth is the Claude Docs artifact. Scripts cannot reach it, so the
AI writes a *graph file* (one JSON file, in a scratch directory, never committed)
from its reads of the document, and renders canonical markdown back from it.

    model    dataclasses and shape validation of the graph file
    spec     the checks, each with an id, a description and a severity
    project  the tab-tree projection: distance, parent, order, load, tabs patch
    render   the markdown renderer and the links sidecar

Enforcement is by interface: the renderer is the only sanctioned way to produce
tab markdown, so a layout violation is impossible if the tool is used, and the
checker catches what the renderer cannot.
"""

__all__ = ["model", "spec", "project", "render"]
