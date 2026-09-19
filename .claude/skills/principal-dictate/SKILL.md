---
name: principal-dictate
description: The principal dictates a change to the hypomnemata. Plan every edit, map each to the clause of the dictation that motivates it, apply it through the tooling, and — when the dictation changes the spec — tool the new rule, attenuate what cannot be tooled, and bring the whole notebook up to it. Invoke as /principal:dictate <dictation>.
disable-model-invocation: true
---

# /principal:dictate \<dictation\>

A principal entry point. It grants **notebook and canon together**, which is what makes it a
principal entry point and not a canon one: a canon turn answers a question and must never see the
notebook. Never run this inside a turn that is answering a canon question.

`<dictation>` is the principal's description of what should change in the notebook. It may be a
correction, an addition, or a change to the specification the notebook is written in.

## Ground rules

1. **The artifact is the source of truth.** Read it before you write. Ground every edit in what is
   there now, never in a local file and never in what you remember writing. The principal edits the
   artifact asynchronously, outside any session.
2. **Never revert or overwrite a prior you did not write.** A block you have not read is a block you
   do not touch. On a hash or find mismatch, his words win: keep them, and say what you kept.
3. **Never hand-write tab markdown.** `tools/render.py` is the only sanctioned producer of a tab
   body. Hand-written markdown is how the layout drifts.
4. **Every file under `hypomnemata/` is a cache**, including any graph file you export. Nothing on
   disk is authoritative over the artifact, and no export is committed.

## Procedure

**1 — Read.** Read the artifact's tab list, then every tab the dictation could touch. Export what you
read to a graph file in the scratch directory (`$SCRATCH/graph.json`, schema in `tools/hypo/model.py`).

**2 — Plan.** Enter plan mode and write the plan before any write. The plan is a table, one row per
edit:

| edit | motivated by | target | tool |
|---|---|---|---|
| what changes | the clause of the dictation that requires it, quoted | tab and section | the command that makes it |

Every row cites the dictation. An edit no clause motivates does not belong in the plan; raise it
separately instead of folding it in. A clause of the dictation with no row is an omission — say so
rather than dropping it silently.

**3 — If the dictation changes the specification**, the plan carries three further obligations, in
this order:

- **Tool it.** Where a script can decide the rule from the graph file, add a check to
  `tools/hypo/spec.py`, or extend `tools/hypo/render.py` so the shape is produced rather than
  checked. Prefer the renderer: a rule the interface enforces cannot be broken, a rule the checker
  enforces can be broken and then found.
- **Attenuate what cannot be tooled.** Any rule no script can decide is written into the
  **Attenuation** list at the foot of this skill, in the principal's terms. That list is the only
  place an untooled rule lives; a rule in neither the tooling nor that list is a rule that will be
  forgotten.
- **Bring the whole notebook up to it.** Not only the tab the dictation named. Run
  `tools/check.py` over the whole graph and fix every finding the new rule produces.

**4 — Apply.** For each tab: `tools/render.py $SCRATCH/graph.json <question>` for the body and
`--links` for the anchors, write the body through the docs `update` tool, then apply the links as
`format` operations against the block ids the write returned. Then
`tools/project.py $SCRATCH/graph.json` for the tab-placement patch, and send it. The tab tree is
computed, never chosen.

**5 — Re-check.** Re-export from the artifact and run `tools/check.py` again. The run is not done
while any ERROR stands. Report WARN findings rather than fixing them silently.

**6 — Commit** the tooling and skill changes on the `hypomnemata` branch. Nothing is committed for
the notebook's content: it lives in the artifact.

## Attenuation

Rules of the specification that no tool decides. Hold these by reading; they are why this skill has
a procedure rather than a script.

- **The question is only the question.** `no-restatement` catches a literal restatement of a term's
  anchor. A paraphrase of the term, or a gloss that leaks the principal's reading of the clause, it
  cannot catch. Read every question you write against the term that raised it and cut anything that
  tells the answerer what was meant.
- **A thesis in canon is verbatim.** No tool can compare a thesis against the session that produced
  it. Where you did not witness the answer, do not edit its text.
- **Title summaries summarise.** A heading that names rather than says is legal to the checker and
  wrong: `▸ The memory clause` is an identifier, `▸ Memory is the repo` is a summary.
- **A null edge really raises no question.** Leaving a clause without a term is a judgement that
  nothing follows from it. The checker cannot tell a deliberate null edge from a missed term.
- **Tradition relations are marked honestly.** Support and divergence are read, not derived.
- **An application's standing is honest.** `postulate` where it was built ahead of its source
  thesis, `derived` only where that thesis has landed.
- **Hinges are complete.** What the asking presupposes, and what leaked into the wording, are the
  principal's judgement; nothing computes them.
- **No inline documentation.** A tab carries its content; what its shape means belongs on the
  encoding tabs. The checker cannot see the difference.
- **The clean-context rule.** Nothing of the notebook may reach a turn that answers a canon
  question. There is no guard for this yet — it is recorded as an eventuality on the `context` tab —
  so it holds by discipline: never invoke a canon entry point from a session that has run this one.
- **Async edits are preserved.** The read-before-write discipline is not enforceable by a script
  that cannot see the artifact.
