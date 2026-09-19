# hypomnemata

The principal's notebook: his priors, not canon. It is in his voice, and nothing in it
licenses an act; it records what he holds while the questions are still open.

**The source of truth is the document**, a Claude Docs artifact:

<https://claude.ai/code/artifact/47d8730e-0bb8-4995-b3fb-8310665c1528>

Every file here is a cache. Scripts cannot reach the document, so the tooling works on a
**graph file**: one JSON file the AI writes into a scratch directory from its reads of the
document, and renders canonical markdown back from. The graph file is transient and is
never committed — no copy of the notebook lives in this repository.

The design goal is **enforcement by interface**. `render.py` is the only sanctioned way to
produce a tab's markdown, so a layout violation is impossible if the tool is used;
`check.py` catches what the renderer cannot.

## The graph model

A **question** is the unit of address and gets one document tab; the one with no incoming
term edge is the root. A **thesis** is an articulated answer to exactly one question. A
**term** edge runs from a thesis to the question it opens, carrying **anchors** — passages
of the thesis text, verbatim. A **tradition** edge runs to a tradition question, a root of
its own outside the main tree; an **application** edge to an artifact outside the graph. A
**definition** fixes a word of a thesis in place and opens no question. An **inbox item**
is a human action a question requires before it can be asked.

## The commands

```
python3 hypomnemata/tools/check.py   <graph.json> [--json] [--only ID] [--list]
python3 hypomnemata/tools/project.py <graph.json> [--json]
python3 hypomnemata/tools/render.py  <graph.json> <question id> [--all] [--links]
```

- **check.py** runs the sixteen checks and prints one line per finding and a summary;
  it exits 1 on any ERROR. `--list` prints the checks and their severities.
- **project.py** prints the tab tree and the complete tab-placement patch, ready to send
  as the `tabs` patch of a document update. Parent is the source of an incoming term edge
  nearest the root, ties broken lexicographically; siblings take `a0`, `a1`, …; tradition
  roots are top level and take `b0`, `b1`, ….
- **render.py** prints the canonical markdown body for a tab, `--all` for every tab
  separated by a `=== <question id> ===` line. It refuses (exit 1) if the checker finds any
  ERROR affecting that question. `--links` also prints, after a `=== links ===` line, the
  JSON sidecar of every link the caller must apply once the write has returned real block
  ids: for each anchor the term's target, keyed by the term title, and for each definition
  its `≡` heading. That sidecar is the list the caller turns into `format` operations.

Each script resolves its package beside itself, so it runs from any directory; the graph
file is always an argument. All three print findings and aggregates only, never file
contents.

## The flow

1. **Read the document** and write the graph file into the scratch directory.
2. **`check.py`** — fix the ERRORs in the graph file; the WARNs are judgement.
3. **`project.py`** — send the tabs patch, so the tab tree matches the graph.
4. **`render.py`** — one tab at a time, and write the body back to the document.
5. **Apply the links** from the sidecar once the write returns block ids.
6. **Discard the graph file.** The document is the source of truth; this is a cache.

## Layout

```
tools/hypo/model.py    dataclasses and shape validation of the graph file
tools/hypo/spec.py     the checks, each with an id, a description and a severity
tools/hypo/project.py  distance, parent, order, load, the tabs patch
tools/hypo/render.py   the renderer and the links sidecar
tools/check.py  tools/project.py  tools/render.py   the command line
tools/fixtures/        a valid graph, and one invalid graph per check
```

Tests: `python3 -m unittest discover hypomnemata/tools`. Python 3 standard library only.
