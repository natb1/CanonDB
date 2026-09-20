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
- **An identifier on the page must be earned.** Titles are what a reader is given; an id is a
  handle for a machine. An id earns its place either by having a machine that needs it — an
  inbox item's, which a question's `requires` names, so the item may be reworded without
  anything following — or by a named exception. There is one: a tab's top heading is the
  question id, and so is its name in the navigation, because the two must agree and a tab is
  addressed by it. Everywhere else the title stands. `title-not-identifier` catches the two
  shapes a script can decide in a *heading*; in prose nothing can, because most question ids
  here are ordinary words — `canon`, `context`, `party`, `priority`. Read every thesis for a
  bare id standing in for a name. Naming a file that happens to share an id is not one: the
  root's hinge records that the filename leaked the frame, and it can only do that by naming
  the file. A glossary heading is not an identifier either — it is the word itself, which is
  what a reader looking for that word is looking for.
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
- **Discharge is an act, not a state.** A postulate is anything the notebook supports and canon
  does not, whether it is a thesis or an artifact built from one, and `standing-honest` grades
  both in two steps: a thesis is `canon` only where its question landed, and an artifact is
  `derived` only from a thesis that is `canon`. Both are necessary and neither is sufficient.
  The check cannot tell whether a landed answer has been promulgated, whether the artifact
  exists, or whether anyone diffed it against what the landed answer would have produced. A
  thesis stays `postulate` until it is promulgated and an application stays `postulate` until
  that diff is done, however green the check, and saying so is the writer's judgement.
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
- **Pressure is the principal's, priority is the tooling's.** Pressure is the one scheduling
  number set by hand — what work is actually waiting at this question — and it is his judgement,
  never invented to make a sum come out. Priority is computed from it along the term edges, on
  the reading that a turn carries canon above its question and so nothing below a question can
  be put until that question has landed. That reading makes blocking and lineage the same
  relation today; they are not the same relation, and when a question-to-question blocking edge
  is recorded in its own right the two will part company and this sum will have to move. The
  debt is that edge, not wherever it happens to be written down.

## Drafting a line

A **line** is one run of the elenchus: the questions put from one admission until a disposition
ends it. Nothing here is decidable by a script — a question is well drawn or it is not — so it
sits with the rest of the attenuation. It is the part that decides what the graph becomes, and
a badly drawn question is not corrected later: whatever is built above it is built on a step
that was granted rather than reached.

**Selecting the admission.** Selection is the whole of the steering. The questioner never
asserts; his view enters as a question or not at all. What he steers *toward* is not his own
conclusion but a latent conflict between two things the answerer has already said, or a place
where one of them runs out of coverage — that is where the answerer moves under his own power.
If selection cannot reach a point, the point is a dictate, and knowing that is worth as much as
reaching it. Two grains run at once: the target picks the admission, the admission picks the
question.

**What ranks.** Four factors, ordered and not weighted. Step size is a **gate**, not a rank.
Blocked action ranks first while anything is blocked — what does the answer unblock. Target
distance ranks second, and takes over once nothing is blocked. Cost sets how many questions go
in a batch and never which.

**The kind.** Definitional (*ti esti* on a word the answer used), case (*would you still say
that if…*), consistency (two admissions in tension). Prefer the consistency question where a
tension already stands: it is the elenctic one. The case question is the coverage test, and
every real task done on canon supplies one for free.

**Step size.** A question too far from the last admission is **decomposed, not deferred**: ask
the question it presupposes. Ranking it lower only postpones an admission that will be hollow
whenever it is granted. The failure of a far question is not refusal — it is a step granted out
of politeness with a hollow chain built above it. Too open is also too far: a diffuse question
is a distant one. An overreach is a disposition with a retreat, not an error.

**Framing.** Open on what the answerer is already doing. Presuppose only what the act of asking
makes true; everything contested goes into the question. Minimise the hinges the other party is
not already standing on, rather than the count of them. One question per question — a second
clause loads the hinge and pre-empts the derivation. Never restate the term that raised it: it
is an implied gloss that leaks the principal's reading, and it makes the answering turn parse
the question for a prior instead of answering it. Leakage travels through a filename, a commit
title and a path, not only through wording. And nothing of the notebook may stand in the
answerer's context while he answers.

**Topology.** The tab tree is a projection; the graph is a **DAG**. A question may be raised by
several clauses and usually should be, and what stands above it — for a definition, for a
hinge, for a reader — is its **ancestors** and never its breadcrumb.

- The parent is the raiser nearest the root, ties lexicographic, so **the shallowest raiser wins
  the tree**. When a question belongs beneath a later synthesis, the remedy is to re-scope the
  question, not to rewire the edge.
- A question scoped narrower than the answer it will receive lands under the wrong parent.
- Prefer a term edge to a mention. A mention that crosses subtrees is an edge the graph has not
  justified, and it is a sign that a better line is available. Reach for one only where a term
  edge would close a cycle, and record that reason on it.
- Consider a new middle question before rewiring an old edge.
- A clause that defers to a question some other clause raised is a mention; a clause that raises
  it is a term.
- A term whose anchor contains another term's anchor is at the wrong grain: one follow-up is one
  term, and a container clause raises the synthesis rather than the parts.
- A word belongs on the question that introduces it, not the one that presents it. Where a user
  cannot reach it over the ancestors, either the line is missing an edge or the definition is on
  the wrong tab.
- A hinge is a term taken for granted. It is inherited down the lineage and stated only where it
  differs, and one repeated across siblings belongs to a question above them.
