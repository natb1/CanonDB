# hypomnemata

The principal's notebook for CanonDB v1: his priors, not canon.

It is **not** homologia. Canon is in the AI's voice, verbatim; this is in the principal's.
It never enters an elenchus turn's context — the contamination rule. Nothing here licenses
an act; it records what the principal holds while the questions are still open.

The published form is a Claude Docs artifact:
<https://claude.ai/code/artifact/47d8730e-0bb8-4995-b3fb-8310665c1528>

The **source of truth is `nodes/*.yml`**, one node per file, the id the filename stem.
The doc is a transcription of what `render.py` prints. The scripts never write the doc.
The schema and the rules are in [SPEC.md](SPEC.md).

## The three commands

```
python3 hypomnemata/tools/check.py                 # validate nodes/; exit 1 on error
python3 hypomnemata/tools/pressure.py              # frontier, inbox and load tables
python3 hypomnemata/tools/render.py ti-esti        # one node as doc-entry markdown
python3 hypomnemata/tools/render.py --all          # every node, parent before child
```

Each runs from any directory: `nodes/` is resolved beside the script, and `--nodes DIR`
overrides it. `pressure.py` takes `--json` and both `pressure.py` and `render.py` take
`--out PATH`. All three print aggregates and findings only, never file contents.

Tests: `python3 -m unittest discover hypomnemata/tools` (stdlib `unittest`; the real
`nodes/` plus synthetic cases in temporary directories — the tests never write to `nodes/`).

Requires Python 3 and PyYAML.

## The flow

1. **Edit `nodes/`** — the notebook is written by hand, one node per question.
2. **`check.py`** — shape, vocabulary, the tree, the references, the hinge rule.
   `E` lines fail the run; `W` lines are heuristics (ledger shape, a duplicated
   definition, a stub carrying more pressure than it should).
3. **`pressure.py`** — what to ask next and what the principal owes:
   *Frontier* (follow-ups, ready first, priority descending), *Inbox* (the undone
   actions, by what they unblock), *Load* (where the weight sits in the tree).
4. **`render.py`** — the doc entry for a node, in the shape the doc already uses.
5. **The main thread transcribes** the render into the doc. Nothing is generated into it.

## How pressure is computed

Weights sit at the top of `pressure.py` (`W_BLOCKED`, `W_LOAD`, `W_DISTANCE`,
`DEFAULT_DISTANCE`).

- `postulate_load` counts the nodes in a postulate's `rests_on` closure — a listed id
  together with everything under it; `"*"` counts every node.
- `load(f)` sums that over the postulates `f` would discharge.
- `intrinsic(f) = blocked + load + (D_MAX + 1 - distance)`, `D_MAX` the largest distance
  on any follow-up.
- `priority(f)` adds the priority of every follow-up that must come after `f`.
- `ready(f)` is: drafted, every required action done, every `after` landed.
- An action's priority is the largest priority it blocks, reached through `after`.

The tree and the `after` graph must be acyclic; a cycle is reported and exits 1.
