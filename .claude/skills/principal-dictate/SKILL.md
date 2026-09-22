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
   disk is authoritative over the artifact, and no cache is committed. The one committed file of
   the notebook's content is the sealed envelope at the branch root, which is a projection like
   the rest and committed as a stopgap (see **Carrying**).

## Procedure

**1 — Read.** Read the artifact's tab list, then export every tab as markdown and build the graph
file with `tools/read.py <document read> <directory of exports>` (`$SCRATCH/graph.json`, schema in
`tools/hypo/model.py`). Read the tabs the dictation could touch yourself as well: the reader tells
you what the page holds, not what it means. A complete read also re-seals the committed envelope
(see **Carrying**), which is how an edit the principal made asynchronously reaches it: that read is
the first moment anything here knows the notebook moved.

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

**4 — Apply.** Writing a tab is **two calls**, and the second is not optional: an in-page link
needs a block id, only the document mints one, and a body write mints new ones. Both payloads
come from the tooling, so neither is composed by hand.

For each tab, with its outline in `$SCRATCH/outlines/<question>.xml` — the `xml` of a write's
ack, or a read with `projection: outline`:

1. `tools/apply.py $SCRATCH/graph.json <question> --outlines $SCRATCH/outlines --body` → send it,
   and save the ack's outline over the old one, because the ids have changed.
2. `tools/apply.py … --links` → send it. `--wanted` lists the tabs whose outlines it needs
   first; it refuses rather than emitting an operation that would do nothing. An ack prints one
   element per operation, up to a size cap: past roughly twenty it stops printing and says
   `complete='false'`, which is not a refusal and not a skip but the outcome going unread. Send
   the links of a heavy tab in batches under that, or read the rest back off the page — a
   `no_op` is exactly what this step exists to catch, and it cannot be caught in what was never
   printed.
3. `tools/apply.py … --unlink <the tab's export>` where the page carries a link the sidecar no
   longer names — a definition that has moved tabs leaves its own behind.

When a run writes more than one tab, write every body before any link: a link into a tab whose
body is written after it points at a block that write retires, and nothing can see that it
does. Then `tools/project.py $SCRATCH/graph.json` for the tab-placement patch, and send it. The
tab tree is computed, never chosen.

**5 — Re-check.** Export every tab you touched as markdown, then run both:

- `tools/read.py` to rebuild the graph file and `tools/check.py` on it — no ERROR may stand, and
  the rebuilt file must match the one you sent;
- `tools/verify.py $SCRATCH/graph.json <tabs dir>` — the page against the renderer, links
  included.

The second is not a repetition of the first. A graph file never held a link, so the rebuild is
blind to every one of them: it passed green over a page that had lost all 192. Report WARN
findings rather than fixing them silently.

The rebuild re-seals the committed envelope as it goes, and `verify.py` reports it where it did
not. Both say so in a line; neither prints the notebook. Read that line — it is the whole of what
this run costs you for the export cache being current.

**6 — Commit** the tooling and skill changes on the `hypomnemata` branch, and the re-sealed
envelope with them: it is the one file here that carries the notebook's content, and step 5 has
already written it. Nothing else is committed for that content: it lives in the artifact.

## Carrying

A live document cannot be shared between users, so a party who wants this notebook raises their
own from its graph. `tools/portable.py seal $SCRATCH/graph.json -o <file> --name "<notebook>" --tools "<repo>"`
empties the values that name *this* document — the `artifact`, the `state_enum`, each question's
`tab` and `body`, and the link of any application whose link is this document, recorded under
`rebind` — and says on stderr how many it dropped, or which, with `--verbose`.
It refuses a graph the checker faults: what is handed over stands, or it is not handed over. `tools/portable.py open <file> -o
graph.json` gives the graph back, unbound, and the rebuild steps ride inside the envelope so the
receiving party reads them from the same file.

The tab tree does not travel, because `project.py` derives it; the envelope records it under
`expect` instead, as the shape the rebuild has to come out to. The enum does not travel either —
only its options do, since an enum id is this document's. A document enum only grows, so the new
one is created holding exactly `STATES`, in order, the first time.

The sealed envelope is committed, at the branch root, and is the one exception to the rule that
nothing is committed for the notebook's content. It is an accepted exception and not a second
source: the envelope is only ever a projection of the notebook, which stays the source of truth,
and it is committed as a stopgap while the document cannot be shared between users. A party who
has it must be able to say which notebook they received, and when the document can be shared the
stopgap goes. What it was sealed from — the graph file and the tab exports — stays a cache and
stays uncommitted.

An envelope goes stale the moment the notebook moves, so it is not left to be remembered.
`tools/read.py` seals the rebuilt graph over it on every complete read, taking the `name` and the
`tools` from the file it replaces — nothing is retyped, so nothing drifts, and the envelope is
found at the branch root by its own `format` rather than named. It costs no call of its own and one
line of output.

That line is the shape of the difference and never the notebook: which questions came, went or
moved, by id, at most eight of them named before it counts instead, and which header values no
longer agree. It is a handful of lines for a notebook of any size. The words are in `git diff`,
which is the right place for them — putting a diff of the export into a turn puts the whole
notebook back into the context this tooling exists to keep it out of.

It declines rather than seal something partial, and says which: a read that left tabs out, a graph
the checker faults, or a re-seal that would drop questions — a partial read is indistinguishable
from a notebook that lost them, and that drift is the one re-reading cannot undo. Where the drop is
the change, `tools/portable.py reseal $SCRATCH/graph.json --force` says so deliberately, and
`tools/portable.py stale $SCRATCH/graph.json` asks the question without answering it. `verify.py`
asks it at the close of every write, so a run cannot end green over an export cache that went out
of date.

## Attenuation

Rules of the specification that no tool decides. Hold these by reading; they are why this skill has
a procedure rather than a script.

- **The question is only the question.** `no-restatement` catches a literal restatement of a term's
  anchor. A paraphrase of the term, or a gloss that leaks the principal's reading of the clause, it
  cannot catch. Read every question you write against the term that raised it and cut anything that
  tells the answerer what was meant.
- **A thesis in canon is verbatim.** No tool can compare a thesis against the session that produced
  it. Where you did not witness the answer, do not edit its text.
- **A headline names its content.** It summarises what the section says. It need not be a sentence,
  and it may well be the handle a link points at — neither of those makes it wrong.
  `headline-not-identifier` catches the two shapes a script can decide: an opaque handle like
  `term-001`, and a bare question id, which names a tab and not the thing it sits on. What is left
  to read is whether the headline actually says what the thing says, rather than merely pointing
  at it.
- **An identifier on the page must be earned.** Headlines are what a reader is given; an id is a
  handle for a machine. An id earns its place either by having a machine that needs it — an
  inbox item's, which a question's `requires` names, so the item may be reworded without
  anything following — or by a named exception. There is one: a tab's top heading is the
  question id, and so is its name in the navigation, because the two must agree and a tab is
  addressed by it. Everywhere else the headline stands. `headline-not-identifier` catches the two
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
  A note carries only what the renderer cannot say: eight application notes once restated the
  discharge condition, which is derived, and six went stale at once when the answerer field
  arrived.
- **Discharge is an act, not a state.** A postulate is anything the notebook supports and canon
  does not, whether it is an answer or an artifact built from one, and the two are graded in two
  steps. An answer is `canon` once it has itself landed — merged, which is promulgation — and
  that is read off its own state, so the step cannot be wrong. An artifact is `derived` only from
  an answer that is `canon`, which `standing-honest` checks; that is necessary and not
  sufficient. What would discharge a postulate is rendered beside its standing, read off the
  answer and never written: its landing and then the diff, or the diff alone once it has landed.
  Nothing the principal answers lands, so what rests on his own answer stays a postulate while
  he answers — and the clause says so. What no check reads is whether the artifact exists, or
  whether anyone diffed it against what the landed answer would have produced. An application
  stays `postulate` until that diff is done, however green the check. Saying so is the writer's
  judgement.
- **Assent in the notebook is not assent to canon.** The principal may note his assent on an
  open thread so that the next question can be drafted from it. The answer stays in thread:
  nothing is merged, and nothing is canon, until the merge, which is promulgation, and the
  answer's own state says which it is — a question and its answers each carry one, and a question
  can land before its answer does. While the thread is open he may also suspend his acceptance of
  one clause, saying what it waits on, or record a deadlock on it. A suspension is settled before
  the merge, and a deadlock's attenuation is owed at the merge. `state-order` and
  `suspension-open` hold that shape. What no check reads is the assent line itself — a noted
  assent, a gloss confirmed, acceptance withheld from the whole answer — so read it.
- **Who answers is the principal's call.** `answerer` is stored, and `answerer-set` checks that
  every author question names one. Which one is right — a question he answers from his own
  priors, or one to put to the AI — no script decides. `requires` only blocks: an empty one
  says nothing about who answers. A question the principal answers is never put: it blocks
  nothing, waits on nothing and is never on the frontier, and `only-ai-put` keeps it and its
  answers held. Another party's is read, not asked, and is held the same way.
- **A defined word is used only in its defined sense.** `definition-once` finds the word, not
  the sense. The notebook once used "line" for a run of the elenchus and for a line of text in
  the same breath. Where the ordinary sense of a defined word is wanted, use another word.
- **A defined word yields to canon's words.** The AI's words in an answer in thread or landed
  cannot change, so a word the notebook defines must not be one of them. `priority` and `title`
  gave way to `backlog` and `headline` when the root's answer turned out to say "priorities" and
  "titled". `verbatim-collision` finds a defined word in such an answer and reports it where the
  word is defined, since that is the word that can change. It finds the word and not the sense,
  so a text the principal wrote using a defined word in another sense is still found by reading.
- **A shadow only where reach needs it.** A definition may stand for a word that has earned a
  question of its own (`term-target` keeps it off that question's own tab) only when some user
  of the word cannot reach the question over its ancestors. It gives the sense in a sentence
  and points at the question, and the argument stays on the question's tab. Whether reach needs
  it is judged by reading.
- **A deadlock is what no question reaches.** A clause you cannot accept is recorded as a
  deadlock only where the point cannot be put as a question in the lineage. Where it can, suspend
  acceptance of the clause, put the question, and settle it before the merge — and where selection
  cannot reach the point at all, the deadlock is what says so, which is worth as much as reaching
  it. Nothing computes which case you are in.
- **Reach is judged where a part is written.** `reach` holds the context rule over the notebook's
  vocabulary, and holds it on what you write: the question, its hinge, your answers and their
  headlines, glossary bodies, notes, tradition notes and counters, deadlocks and suspensions. An
  inbox item is hoisted to a common ancestor to make a dashboard, so it is judged from every
  question that requires it and written plainly enough for all of them. What the check cannot
  judge is whether a word in reach is used in the sense that was fixed for it.
- **A party's word is imported, never assumed.** A party's notebook never stands above a question
  of yours, so its term of art is brought in by an entry that names the party and takes its sense
  — and a word of the notebook's own that a question cannot reach is a missing edge or a
  definition on the wrong question, never an import.
- **Two open threads must not depend on each other.** `put-in-order` holds the half a script can:
  nothing is put below a question that has not been. Which thread a question is on is not
  recorded, so a turn carrying an answer from another open thread, or missing one it needs, is
  yours to see.
- **The clean-context rule.** Nothing of the notebook may reach a turn that answers a canon
  question. There is no guard for this yet — it is recorded as an eventuality on the `context` tab —
  so it holds by discipline: never invoke a canon entry point from a session that has run this one.
- **The page is a second artifact.** A tab reaches the document in two calls, because a link
  needs a block id the document mints and a body write mints new ones. Nothing in the graph
  file records a link, so nothing that reads the graph can tell whether the second call was
  made: the rebuild, the checks and the tab patch all passed green over a page that had lost
  every one of its 192 links. What sees it is `verify.py`, which reads the page back — the
  body against the renderer, the links the sidecar names against the links the page carries,
  and the links the page carries that the sidecar does not name. Run it at the end of every
  write, and read what it says about that third class: a link applied by hand, or left behind
  by a definition that has moved, is invisible to everything else.
- **Async edits are preserved.** The read-before-write discipline is not enforceable by a script
  that cannot see the artifact.
- **An outline is read for the write it is used in.** `apply` pairs a target's heading to a
  block id by position, and refuses when the outline's text has drifted from what the renderer
  makes — so an outline stale in the words is caught. The other way it goes stale cannot be:
  a body write mints new block ids, and an outline read before one still reads correctly while
  naming blocks that write retired. `verify` cannot see it either, because an href resolves to
  a block and the page only shows which tab it is on. So read an outline in the call before the
  one that spends it, and never carry a file of them between runs.
- **The enum holds the model's states and nothing else.** A state — the question's, and each
  answer's on its own metadata line — renders as a dropdown by index against the one enum the
  graph file names, so it must list exactly `STATES` — `held · in thread · landed` — in that
  order. A document enum only grows: an option can be appended, never
  renamed, reordered or removed. So when the states change, create a new enum holding exactly
  `STATES`, set `state_enum` to it, and re-render every tab so that no dropdown still points at
  the old one. A stale option left where a reader can pick it is a state the model will not
  take. Nothing can check the document's enum from the graph file. Read it once, and again
  after anyone edits the enum.
- **A note is somebody's and stays theirs.** The renderer round-trips a note as a blockquote, so it
  survives a re-render. What it cannot tell you is that a blockquote someone wrote on the page has
  not yet been taken into the graph file: export before you write, always, or you will replace it.
- **Pressure is the principal's, backlog is the tooling's.** Pressure is the one scheduling
  number set by hand — what work is actually waiting at this question — and it is his judgement,
  never invented to make a sum come out. The backlog is computed from it over what a question
  blocks, and blocking is what a turn carries: canon above its question, which is the AI's
  answers alone, since nothing the principal answers reaches a turn. So a question waits on each
  question above it that the AI answers, by a path through the AI's questions, until that answer
  has landed. Blocking and lineage already part there — at the principal's questions and at
  landed answers. Where else they differ waits on a question-to-question blocking edge recorded
  in its own right; the debt is that edge, not wherever it happens to be written down.

## Drafting a line

A **line** is any line of questions, each drawn from an admission of the last. A **thread** is a
line put on an elenchus branch, from the admission it starts at to the disposition that ends it.
Almost nothing here is decidable by a script — a question is well drawn or it is not — so it
sits with the rest of the attenuation; the one rule a script could decide, the grain of an
anchor, is `anchor-grain` now and has left this list. The framing rules below are the notebook's
own answer on `wording`, and this section is that answer's application: when they change there,
they change here. It is the part that decides what the graph becomes, and
a badly drawn question is not corrected later: whatever is built above it is built on a step
that was admitted rather than reached.

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
whenever it is made. The failure of a far question is not refusal — it is a step admitted out
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
  edge would close a cycle. The renderer states that reason under the mention, and
  `mention-justified` warns where no cycle forces it; whether a better line exists is still the
  writer's to find.
- Consider a new middle question before rewiring an old edge.
- A clause that defers to a question some other clause raised is a mention; a clause that raises
  it is a term.
- A word belongs on the question that introduces it, not the one that presents it. A question
  introduces a word through an answer, or through what its asking stood on: the question half of
  its hinge, which is how the root, with no ancestors, brings in "party" and "leak". The answer's
  half records how the answer was drawn, in the encoding's own words, like the question's and
  the answer's metadata; it introduces nothing and is not a user. Where a user cannot reach a
  word over the ancestors, either the line is missing an edge or the definition is on the wrong
  tab.
- A word comes in on a hinge only because the asking stood on it. Every question sits below the
  root, so the root's hinge is where any hard-to-reach word could be parked — and parking it
  there silences the one signal reach gives, a missing edge. The hinge must be true before it
  is useful.
- A hinge is what an act stands on without examining it. It is inherited down the lineage and
  stated only where it differs, and one repeated across siblings belongs to a question above
  them.
