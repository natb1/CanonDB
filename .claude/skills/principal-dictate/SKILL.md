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

**1 — Read.** Read the artifact's tab list, then export every tab as markdown and build the graph
file with `tools/read.py <document read> <directory of exports>` (`$SCRATCH/graph.json`, schema in
`tools/hypo/model.py`). Read the tabs the dictation could touch yourself as well: the reader tells
you what the page holds, not what it means.

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

**5 — Re-check.** Export every tab you touched as markdown, rebuild the graph file with
`tools/read.py`, and run `tools/check.py` on it. The run is not done while any ERROR stands, and the
rebuilt file must match the one you sent — that diff is the only thing that compares what you
rendered with what reached the page. Report WARN findings rather than fixing them silently.

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
- **A title names its content.** It summarises what the section says. It need not be a sentence, and
  it may well be the handle a link points at — neither of those makes it wrong.
  `title-not-identifier` catches the two shapes a script can decide: an opaque handle like
  `term-001`, and a bare question id, which names a tab and not the thing it sits on. What is left
  to read is whether the title actually says what the thing says, rather than merely pointing at it.
- **No identifiers in prose.** A question is named by its tab and an item by its title.
  `title-not-identifier` catches the two shapes a script can decide in a *heading*; in prose
  nothing can, because most question ids here are ordinary words — `canon`, `context`, `party`,
  `priority`. Read every thesis for a bare id standing in for a name. Naming a file that
  happens to share an id is not one: the root's hinge records that the filename leaked the
  frame, and it can only do that by naming the file.
- **A null edge really raises no question.** Leaving a clause without a term is a judgement that
  nothing follows from it. The checker cannot tell a deliberate null edge from a missed term.
- **Tradition relations are marked honestly.** Support and divergence are read, not derived.
- **Hinges are complete.** What the asking presupposes, and what leaked into the wording, are the
  principal's judgement; nothing computes them.
- **No inline documentation.** A tab carries its content; what its shape means belongs on the
  encoding tabs. The checker cannot see the difference.
- **Every datum has one home.** A question's metadata on its question line, an answer's on its
  own section, a term's on its term section — stated once and linked from wherever else it
  bears. No script can tell a second statement of one datum from two data, and the second one
  is usually added in good faith: an inbox item for debt an application already carries as a
  postulate, a note restating a field. Read for it whenever a field, a note or an item is added.
- **Discharge is an act, not a state.** `standing-honest` refuses `derived` where the source
  question has not landed. It cannot tell whether the artifact exists, and it cannot tell
  whether anyone diffed it against the landed answer. A landed source is necessary and not
  sufficient: an application stays `postulate` until that diff is done, however green the
  check, and saying so is the writer's judgement.
- **The clean-context rule.** Nothing of the notebook may reach a turn that answers a canon
  question. There is no guard for this yet — it is recorded as an eventuality on the `context` tab —
  so it holds by discipline: never invoke a canon entry point from a session that has run this one.
- **Async edits are preserved.** The read-before-write discipline is not enforceable by a script
  that cannot see the artifact.
- **The enum options are in the model's order.** A state renders as a dropdown by index, so the
  document's enum must list its options exactly as `STATES` does. Nothing can check the document's
  enum from the graph file. Read it once, and again after anyone edits the enum.
- **A note is somebody's and stays theirs.** The renderer round-trips a note as a blockquote, so it
  survives a re-render. What it cannot tell you is that a blockquote someone wrote on the page has
  not yet been taken into the graph file: export before you write, always, or you will replace it.
- **Stored priority is trusted.** `priority-recompute` only checks that the number is a non-negative
  integer, because the graph carries no question-to-question blocking edge yet — the half of the
  requires graph that runs from a question to a human action is recorded, the half that runs from
  question to question is not. Until that edge exists the ordering is the principal's judgement and
  the number is a note of it. The gap is an inbox item on the `priority` tab, not a licence to invent
  numbers.
