---
name: dictate
description: The principal dictates a change to the hypomnemata. Plan every edit, map each to the clause of the dictation that motivates it, apply it through the tooling, and — when the dictation changes the spec — tool the new rule, attenuate what cannot be tooled, and bring the whole notebook up to it. Invoke as /principal:dictate <dictation>.
disable-model-invocation: true
allowed-tools: mcp__claude_ai_Claude_Docs__read, mcp__claude_ai_Claude_Docs__update, mcp__claude_ai_Claude_Docs__batch, mcp__Claude_Docs__read, mcp__Claude_Docs__update, mcp__Claude_Docs__batch
---

# /principal:dictate \<dictation\>

A principal entry point. It grants **notebook and canon together**, which is what makes it a
principal entry point and not a canon one: a canon turn answers a question and must never see the
notebook. Never run this inside a turn that is answering a canon question.

`<dictation>` is the principal's description of what should change in the notebook. It may be a
correction, an addition, or a change to the specification the notebook is written in. Where the
principal keeps it before it is run, and what brings it up, is that place's own concern and none of this
skill's: the run is made with the prose as its argument, and that is the whole of the interface.

The notebook is the document `.principal/notebook.json` names at the project's root, with the
enum its states point at. `tools/` below is the plugin's own, at `${CLAUDE_PLUGIN_ROOT}/tools/`;
`$SCRATCH` is the session's scratch directory, and nothing of the notebook is written under the
project. The document tools this run reads and writes the notebook with are granted in its
frontmatter under `allowed-tools`: invoking the entry point is the grant, and no other turn
holds one. Each tool is named in both spellings the surfaces give it,
`mcp__claude_ai_Claude_Docs__…` and `mcp__Claude_Docs__…`; a name the surface lacks grants
nothing.

A notebook may hold several projects, each a root at the top level, with `tradition` a project
of its own whose root holds every party beneath it; where it does, `.principal/notebook.json`
names the project this checkout keeps under `project`, and the run's **author tabs** are that
project's: the tabs under its root. Its reads, its checks, its selection and its tab patch are
that project's too — `read.py --project`, and `next.py`, `frontier.py`, `again.py` and
`project.py --project`, which take the project from the file — and the parties it cites are
read with it wherever a rule reaches them. No term edge crosses projects; a mention crosses
only to a project earlier in the order the roots stand in, or to `tradition` (`project-order`).
The tab named `lease` is reserved: it is no question, the reader never takes it for one, and it
holds the leases, the pin and the notebook's provenance (**Several sessions** below).

## Ground rules

1. **The artifact is the source of truth.** Read it before you write. Ground every edit in what is
   there now, never in a local file and never in what you remember writing. The principal edits the
   artifact asynchronously, outside any session.
2. **Never revert or overwrite a prior you did not write.** A block you have not read is a block you
   do not touch. On a hash or find mismatch, the principal's words win: keep them, and say what you kept.
3. **Never hand-write a tab body.** `tools/render.py` is the only sanctioned producer of one. A
   line changed in place follows the shape the renderer writes for that line, because the next
   read of the page parses that shape and no other; hand-written layout is how it drifts.
4. **Every graph file is a cache.** Nothing on disk is authoritative over the artifact, and no
   cache is committed. Nothing is exported: the document is shared, and it is read where it
   stands.

## Procedure

**1 — Read.** Read the artifact's tab list, then the tabs the dictation could touch, in place:
each tab's outline, and in full, block by block, the blocks the dictation bears on. Read them
yourself: a read tells you what the page holds, not what it means. Where the run needs the
project whole as a graph file — a new question, a state, a check over every tab of the project
— read each of its tabs' bodies whole (`view` with `sinceRev` 0), and the tabs of the parties
it cites, save the reads as `$SCRATCH/views/<question>.json`, spell them with
`tools/page.py $SCRATCH/views/*.json -o $SCRATCH/tabs` (which writes each tab's `rev` beside
it), and build the graph with `tools/read.py <document read> $SCRATCH/tabs --project <project>
-o $SCRATCH/graph.json`; a change to the specification reads every tab of every project and
builds the graph without `--project` (schema in
`tools/hypo/model.py`; the enum the states point at is read from `.principal/notebook.json`, or
given with `--state-enum`, and the notebook's URL from the same file where the document read
does not carry it). Nothing is exported: `page.py` spells the read as the export did, so the
reader, the page check and the relink tool take the directory unchanged.

Where the dictation changes only line-shaped parts of a few tabs — step 4 names them — the run
reads only those blocks, a `search` or a `view` of each saved as
`$SCRATCH/reads/<question>.<part>.json`, and for the check the touched tabs and their ancestors
whole, spelled as above into `$SCRATCH/tabs` and read with `tools/read.py <document read>
$SCRATCH/tabs --scope <touched questions>`. It refuses a tab whose header list names a raiser
whose tab was not read: the ancestors are supplied, never assumed.

**2 — Plan.** Enter plan mode and write the plan before any write. The plan is a table, one row per
edit:

| edit | motivated by | target | tool |
|---|---|---|---|
| what changes | the clause of the dictation that requires it, quoted | tab and section | the command that makes it |

Every row cites the dictation. An edit no clause motivates does not belong in the plan; raise it
separately instead of folding it in. A clause of the dictation with no row is an omission — say so
rather than dropping it silently. A clause the run can see but cannot apply — a part no tool
writes, a change the tooling refuses, a write out of all proportion to the clause — is neither
an omission nor a thing to say in the report: it is a row that writes the clause as a **pending
note** on the tab it bears on (`tools/inplace.py note insert`, after the last block of the
section it concerns), opening with the word *pending*, so that what the run owes stands on the
page and `tools/check.py` reports it (`dictation-pending`) until a run takes it in.

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

**4 — Apply.** A dictation that changes only line-shaped parts of a few tabs is written **in
place**, block by block: an application with `tools/application.py`; a glossary entry, a term
and its item on the header list of the tab it raises, the words of an answer, an answer's
headline, or an amendment to a hinge's provenance with `tools/inplace.py`; and any other block of
words — a hinge's question half, its end or its method, a note, a paragraph the modes above do
not name — with
`tools/inplace.py words replace`, which is decided not by which part the block is but by its
read-back: the tab is read before and after, and the write is refused unless one field alone
differs, with `--markdown` where the change reaches a link, a chip or a marked run. A replace or a delete
takes the saved read of its blocks, an insert names the block it follows — and an
application's insert takes the tab's view besides, since the discharge clause beside its
standing is read off the question line and the answer's state and given by nobody — and each
prints the ops of one prose `update` for that tab, every whole-block op guarded by the block's
`h` and the read's `rev`; send them as printed. A refusal is a block that moved or a part the
reader would not take back, and either is read again, never forced; an answer's paragraph
whose change reaches a link, a chip or a marked run is given whole with `--markdown`, over the
tab's whole view, which is the tool's own way and not a way round it: what it prints is what
the document takes — the paragraph's words as one text replace, and one format operation per
mark the change takes off or puts on, since the document takes no in-page link in a replace's
markdown and a text replace spreads a mark inside the changed words over all of them. A term's
items on a header list go one insert per call, each named after the one the last ack placed,
as the tool says. No body is written, so no
link into the tab is retired and nothing is relinked. What a write leaves owed — a new term's
chip in the answer, and the links a new term or entry wants — it names on stderr, and those go
as format operations once the insert's ack has given the new heading its id.

Between a part written in place and a tab written whole stands the section: `tools/apply.py
$SCRATCH/graph.json <question> --outlines $SCRATCH/outlines --body --section <name>` renders one
`## ` section and replaces its blocks alone, and `… --links --section <name>` puts back the
links that write took off or retired. Only the links into that section retire, so `relink.py`
finds nothing else stale, and a change the in-place tools refuse — a section's shape, a part
whose change reaches more than one field — goes that way before it goes whole.

Everything else is written whole: a change to the specification, a new question, a state, or a
change to a question's or a term's structure the in-place and section writes refuse. Writing a
tab whole is **two calls**, and the second is not optional: an in-page link needs a block id,
only the document mints one, and a body write mints new ones. Both payloads come from the
tooling, so neither is composed by hand. A body's replace names every block of the tab, so it
carries no hash; its guard is the rev of the read its outline came from, which `apply.py` reads
off the outline file and refuses to do without.

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
4. Once every rewritten tab has its links, `tools/relink.py $SCRATCH/graph.json <rewritten
   tabs> --tabs <exports> --outlines $SCRATCH/outlines` → send what it prints, per tab: the
   links into the rewritten tabs from every other tab, which the body writes retired (see
   **Attenuation**).

When a run writes more than one tab, write every body before any link: a link into a tab whose
body is written after it points at a block that write retires, and nothing can see that it
does. Then `tools/project.py $SCRATCH/graph.json --project <project>` for the tab-placement
patch of the project the run read (without `--project` only over a graph of every tab), and
send it. The tab tree is computed, never chosen.

**5 — Re-check.** Read every tab you touched back off the page, the relinked ones included,
then run both:

- `tools/read.py` to rebuild the graph file and `tools/check.py` on it — no ERROR may stand, and
  the rebuilt file must match the one you sent;
- `tools/verify.py $SCRATCH/graph.json <tabs dir>` — the page against the renderer, links
  included.

The second is not a repetition of the first. A graph file never held a link, so the rebuild is
blind to every one of them: it passed green over a page that had lost all 192. Report WARN
findings rather than fixing them silently.

After an in-place write, read each touched block back with `sinceRev` at the read's `rev`, then
re-read the touched tabs and their ancestors as step 1 does and run `tools/check.py` on that
graph: it records its scope, every rule runs over it, and one that needs a tab outside it — what
a term leads to below — says nothing there. A missing ancestor is
an ERROR (`scope-closed`), not a gap read over.

**6 — Commit** the tooling and skill changes on a branch of their own and open a pull request
against `main`. There is one standing branch, `main`, and every other is a pull request's, so
nothing waits on a branch that is not going to be merged. Nothing is committed for the
notebook's content: it lives in the artifact, which is shared between users as it stands. What
a turn may carry is decided by the configuration of the entry point that runs it — a skill, an
agent, a gate — and never by which branch is checked out.

## Several sessions

The notebook is one document that several sessions, and the principal's own hand, write at
once. A write in place is guarded block by block and needs nothing more. What else holds:

- **A write carries the rev of the read it came from, and a run refuses a graph older than the
  page.** The graph records each tab's `rev` as it was read. Before the first write, and again
  before the links, read each tab in scope with `{"kind":"view","sinceRev":<its rev>}`, save the
  reads as `$SCRATCH/since/<question>.json` and run `tools/fresh.py $SCRATCH/graph.json
  $SCRATCH/since/*.json`. A tab it names moved: read it again, rebuild, re-plan, and never write
  over it. The page check treats a page newer than the graph as another session's, never as
  drift.
- **A run takes a lease before it writes a section or a body, changes the specification or
  sends the tab patch.** Read the lease tab whole and `tools/lease.py take <read> --scope
  <project, or all for a spec change or a patch over every tab> --session <this session's id>
  --entry /principal:dictate`; send the ops, read the tab again, and `tools/lease.py check
  <read> --session <id>`. Exit 0: the lease is held. Exit 1: a line that overlaps stands above
  this one — take this one off (`lease.py release`) and stop, saying whose it is. Release the
  lease when the run ends, whatever it came to.
- **The notebook names the tooling it was last written with.** `tools/lease.py pin <read>`
  prints the plugin commit. Where it is not this plugin's, `git merge-base --is-ancestor <pin>
  <this plugin's commit>` in a CanonDB checkout must succeed before anything is written —
  older tooling never writes over newer — and the run that writes names its own commit with
  `lease.py pin <read> --write <commit> --session <id>`.
- **Every update carries an `opId`**, `<session>-<step>-<n>`, so that a call retried after a
  dropped connection replays rather than writing twice.

## Carrying

The live document is shared between users as it stands, so a party who wants to read this notebook
reads the document. A party who wants a notebook of their own raises it from the graph.
`tools/portable.py seal $SCRATCH/graph.json -o <file> --name "<notebook>" --tools "<repo>"`
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

What a party says is the envelope's `name` and its `digest`. The name is the notebook's handle and
never a version of it, and the `format` carries the one version the tooling has. The digest is of
the questions alone, in one canonical spelling, so the same notebook seals to the same digest
wherever it is sealed. The questions stand in the file by id, not in the tray's order, which is a
projection recomputed when a sibling is inserted or a group grows past ten.

An envelope is sealed when a party asks for one, never on every change, and nothing sealed is
committed: what it was sealed from — the graph file and the tab exports — stays a cache, and the
envelope is a projection of the notebook like the rest.

## Attenuation

Rules of the specification that no tool decides. Hold these by reading; they are why this skill has
a procedure rather than a script.

- **The question is only the question.** `no-restatement` catches a literal restatement of a term's
  anchor. A paraphrase of the term, or a gloss that leaks the principal's reading of the clause, it
  cannot catch. Read every question you write against the term that raised it and cut anything that
  tells the answerer what was meant.
- **Canon alone is verbatim.** The recorded answer in canon is what cannot be modified. An answer
  that has landed is canon's, and the notebook reflects it word for word. An answer held or in
  thread is in the notebook only: it is dictation, and is reworded under the rules of dictation
  like any other part. No script compares a landed answer with canon's text, so it is held by
  reading: where an answer has landed, do not edit its text.
- **A headline names its content.** It summarises what the section says. It need not be a sentence,
  and it may well be the handle a link points at — neither of those makes it wrong.
  `headline-not-identifier` catches the two shapes a script can decide: an opaque handle like
  `term-001`, and a bare question id, which names a tab and not the thing it sits on. What is left
  to read is whether the headline actually says what the thing says, rather than merely pointing
  at it.
- **An identifier on the page must be earned.** Headlines are what a reader is given; an id is a
  handle for a machine. An id earns its place only by a named exception, and there is one: a
  tab's top heading is the question id, and so is its name in the navigation, because the two
  must agree and a tab is addressed by it. Everywhere else the headline stands. `headline-not-identifier` catches the two
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
- **The end is the principal's, and never put.** A root's hinge states what the asking is for and
  how that end is read and pursued, and a question below inherits both. `end-stated` holds the half
  a script can: the author's root states both parts, a question below states the two together or
  neither, and a party's question states none; and `reach` holds the end's words to what the root
  can reach, as it holds the question half's, since the end brings words in and the root has no
  ancestors. What is left to read: that each word the end uses is used in the sense fixed where it
  is defined; that the method names counts which are applications elsewhere, and restates none of
  them; that an end stated below the root is narrower than its lineage's and not a second statement
  of it; and whether the end is right at all, which is examined where the principal keeps what
  things are kept for — the user's own notebook of ends — and never here. No turn that answers a canon
  question sees the end: the clean-context rule keeps the hinge out, and the end goes with it.
- **No inline documentation.** A tab carries its content; what its shape means belongs on the
  encoding tabs. The checker cannot see the difference.
- **Every datum has one home.** A question's metadata on its question line, an answer's on its
  own section, a term's on its term section — stated once and linked from wherever else it
  bears. No script can tell a second statement of one datum from two data, and the second one
  is usually added in good faith: a note restating a field. Read for it whenever a field or a
  note is added.
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
  Nothing the principal answers lands, so what rests on the principal's own answer stays a postulate while
  the principal answers — and the clause says so. What no check reads is whether the artifact exists, or
  whether anyone diffed it against what the landed answer would have produced. An application
  stays `postulate` until that diff is done, however green the check. Saying so is the writer's
  judgement.
- **Assent in the notebook is not assent to canon.** The principal may note assent on an
  open thread so that the next question can be drafted from it. The answer stays in thread:
  nothing is merged, and nothing is canon, until the merge, which is promulgation, and the
  answer's own state says which it is — a question and its answers each carry one, and a question
  can land before its answer does. While the thread is open the principal may also suspend acceptance of
  one clause, saying what it waits on, or record a deadlock on it. A suspension is settled before
  the merge, and a deadlock's attenuation is owed at the merge. `state-order` and
  `suspension-open` hold that shape. What no check reads is the assent line itself — a noted
  assent, a gloss confirmed, acceptance withheld from the whole answer — so read it.
- **Who answers is the principal's call.** `answerer` is stored, and `answerer-set` checks that
  every author question names one. Which one is right — a question the principal answers from the principal's own
  priors, or one to put to the AI — no script decides. A question with nothing
  left to wait on is not thereby the principal's. A question the principal answers is never put: it blocks
  nothing, waits on nothing and is never on the frontier, and `only-ai-put` keeps it and its
  answers held. Another party's is read, not asked, and is held the same way.
- **A defined word is used only in its defined sense.** `definition-once` finds the word, not
  the sense. The notebook once used "line" for a run of the elenchus and for a line of text in
  the same breath. Where the ordinary sense of a defined word is wanted, use another word.
- **The user is named the user.** The one the notebook is kept for is named the user wherever
  the notebook speaks of that party, on an author's tab and where a party's tab speaks of the
  user too, as the encoding's answer says. `user-named` finds "the human" in the notebook's own
  words, the answer's hinge among them. What it cannot find is a pronoun: he, him, his or himself
  standing for the user is the same fault, and whom a pronoun stands for is read, since a party's
  tab says "he" of its author and an answer says it of Euthyphro. Write the user, or the
  principal where the role is meant, and never a pronoun for either. Canon's words are left as
  they stand: a landed question or answer keeps "a human" if it says so.
- **A defined word yields to canon's words.** The words of a landed answer cannot change, so a
  word the notebook defines must not be one of them. `priority` and `title` gave way to
  `backlog` and `headline` when the root's answer turned out to say "priorities" and "titled".
  `verbatim-collision` finds a defined word in a landed answer and reports it where the word is
  defined, since that is the word that can change. An answer held or in thread can change too,
  so there the word is `reach`'s to judge, on the answer. It finds the word and not the sense,
  so a text the principal wrote using a defined word in another sense is still found by reading.
- **A shadow only where reach needs it.** A definition may stand for a word that has earned a
  question of its own (`term-target` keeps it off that question's own tab) only when some part
  using the word cannot reach the question over its ancestors. It gives the sense in a sentence
  and points at the question, and the argument stays on the question's tab. Whether reach needs
  it is judged by reading. That the entry points at the question is decided in the one case a
  script can see, a word that is a question's own id, by `shadow-declared`; a word that earned
  its question under another name — `backlog` shadowing `priority` — is still read for.
- **A deadlock is what no line reaches.** A clause you cannot accept is recorded as a
  deadlock only where the point cannot be put as a question in the lineage, and no other line
  or thread could reach it either. Where one can, suspend acceptance of the clause, put the
  question, and settle it before the merge. A dissent is aporia in the principal, and it stays
  suspended while a line that could reach it remains to be drawn; only where selection cannot
  reach the point at all is the deadlock what says so, which is worth as much as reaching it.
  Nothing computes which case you are in, and nothing counts the lines still to be drawn.
- **Reach is judged where a part is written.** `reach` holds the context rule over the notebook's
  vocabulary, and holds it on what the notebook writes: the question, its hinge, every answer
  that has not landed, every answer's headline, glossary bodies and the notes on their
  borrowings, notes, term and mention headlines, tradition notes and counters, deadlocks,
  suspensions and cues, and what each application is named and said to be. Each is judged from the tab it
  is written on. What the check cannot judge is whether a word in reach is used in the sense
  that was fixed for it.
- **A party's word is imported, never assumed.** A party's notebook never stands above a question
  of yours, so its term of art is brought in by an entry that names the party and takes its sense
  — and a word of the notebook's own that a question cannot reach is a missing edge or a
  definition on the wrong question, never an import.
- **Two open threads must not depend on each other.** `put-in-order` holds the half a script can:
  nothing is put below a question that has not been. Which thread a question is on is not
  recorded, so `next.py` and `lineage.py` are told it (`--thread`), and a turn carrying an
  answer from another open thread, or missing one it needs, is yours to see.
- **The clean-context rule.** Nothing of the notebook may reach a turn that answers a canon
  question. The guard the `context` tab describes is built: `/principal:ask`, which holds
  notebook and canon together, selects the question and launches `canon-answer`, whose
  definition under the plugin's `agents/` is the grant — Read and nothing else, no shell, no
  search, no git, no `CLAUDE.md`, and a gate on Read (the plugin's `hooks/canon-gate.py`) that
  lets through the packet and refuses the rest, canon on disk included. The packet is the question and a reference to its lineage, which `tools/lineage.py`
  writes out of the graph file and the selecting turn never transcribes. What is left to hold by
  reading is what no configuration decides. The question's wording is the one thing of the
  selecting turn's that enters the packet, held by the rule that the question is only the
  question, and the prompt around it is read once more before it is sent. Nothing lists
  canon on disk: it is what is under `canon/`, the agent reads none of it, and what its answer
  collides with outside its lineage is the selecting run's to find. A checkout is not a context: the same files are on
  every branch, and what a turn may read is the gate's decision, not the branch's. And the guard holds only where the agent is used: a canon question answered in any
  other way — in this run, in a session that has read the notebook, by a turn composed by hand —
  is answered in a context nobody vouched for, whatever it was given.
- **A lease and a claim are released by reading.** Nothing expires: a run that dies leaves its
  lease line, or a question's claim note, on the page. Whether the session that wrote it is
  still at work is read — its transcript, the time on the line — and a line left by a dead one
  is taken off by hand or by the next run that reads it so, never on a guess.
- **What a run cannot apply stands on the page.** A run ends with nothing owed in the session
  that owed it: a clause it could not apply is a pending note on the tab it bears on, and the
  checker reports the note until a run takes it in. What no script decides is whether the
  clause really could not be applied — a hinge's part and a note are written in place, a
  section is written alone, and only what those refuse earns a note — and whether the note
  says the clause faithfully enough for a later run to apply it without the session it came
  from. Read every pending note you write as the dictation it will be.
- **The page is a second artifact.** A tab written whole reaches the document in two calls,
  because a link needs a block id the document mints and a body write mints new ones. A part
  written in place is one call and retires nothing, but a part it inserts is a block no link
  can name until the ack is back, so its links are owed the same way, and the tool says which. Nothing in the graph
  file records a link, so nothing that reads the graph can tell whether the second call was
  made: the rebuild, the checks and the tab patch all passed green over a page that had lost
  every one of its 192 links. What sees it is `verify.py`, which reads the page back — the
  body against the renderer, the links the sidecar names against the links the page carries,
  and the links the page carries that the sidecar does not name. Run it at the end of every
  write, and read what it says about that third class: a link applied by hand, or left behind
  by a definition that has moved, is invisible to everything else.
- **A scoped check sees its scope.** Over the touched tabs and their ancestors every rule
  runs, and the ones that need a tab below say nothing. What no scoped check can see is a
  fault between a touched tab and one it did not read — a word defined twice, an id used twice,
  a word used below that a changed definition no longer reaches. A dictation that could make
  one — a definition's word, a question's id, a term's target — is checked over the whole graph.
- **A body write retires what other tabs point at.** Only a body write: a part written in place
  keeps every id on the tab it did not insert. A link into a tab carries the id of a
  block on it, and a body write mints new ids for every block on the tab it writes, so every
  link into a rewritten tab from a tab outside the run points, from that write on, at a block
  that no longer exists. Nothing in the run can see it: the graph file never held a link, and
  `verify.py` resolves an href to the tab it is on and no further. Seventeen tabs pointed at
  retired blocks of the root tab after one rewrite of it, and two had pointed at retired
  blocks since the run before. So after the bodies and their own links are written, run
  `tools/relink.py $SCRATCH/graph.json <the rewritten tabs> --tabs <exports> --outlines
  $SCRATCH/outlines` over the exports the run began from: it prints, per other tab, the format
  operations that repoint the links into the rewritten tabs, resolved against the outlines
  the writes acknowledged. Send them, and export those tabs too before the re-check. A format
  operation on a linked run of text replaces its href, so nothing is unlinked first.
- **The document is read in place, and nothing is exported.** The document is shared, so the
  copy a run works from is the page itself: the outline for the shape, a `view` of a block for
  its words, the hash of the block as the guard on the write. An export was the cache a party
  who could not read the document needed, and nothing needs it now. What takes a tab's
  markdown — `read.py`, `verify.py`, `relink.py`, `--unlink` — takes what `tools/page.py`
  spells from a whole-body `view` read, in the export's own spelling, so a page read and an
  export are the same file to them. What the read keeps and the export lost is each block's
  id beside its text (`page.blocks`), which is what would let the page check tell which block
  a link leads to; that use is not built.
- **Async edits are preserved.** The read-before-write discipline is not enforceable by a script
  that cannot see the artifact. And the cheap witness is not a witness: an `export` refused at
  `maxBytes: 1` names the tab's exact size, which looks like a way to tell a moved page from a
  still one without pulling the body back. It is not. The export writes a chip sometimes as a
  link and sometimes as its bare label, so a tab can lose a hundred bytes and more with nothing
  on the page having changed — and, the other way, an edit that trades one word for another of
  the same length moves no byte at all. A size that differs is a reason to look; a size that
  agrees is not a reason not to. What settles it is `verify.py` over a real export, which
  compares at the label and is blind to the spelling.
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
  not yet been taken into the graph file: read before you write, always, or you will replace it.
  The same mark cuts the other way: a blockquote is a note wherever it stands, so one inside an
  answer's text is read back as a note on the section and the next render moves it out of the
  answer. `text-unquoted` refuses such an answer rather than let that happen in silence. An answer
  landed in canon is verbatim, so one that quotes cannot be reworded to pass: until the reader can tell a
  quotation in an answer from a note beside it, it is an answer the notebook cannot hold, and the
  refusal is where that is said.
- **Pressure is the principal's, backlog is the tooling's.** Pressure is the one scheduling
  number set by hand — what work is actually waiting at this question — and it is the principal's judgement,
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
asserts; the questioner's view enters as a question or not at all. What selection steers *toward* is not the
questioner's own conclusion but a latent conflict between two things the answerer has already said, or a place
where one of them runs out of coverage — that is where the answerer moves under its own power.
If selection cannot reach a point, the point is a dictate, and knowing that is worth as much as
reaching it. Two grains run at once: the target picks the admission, the admission picks the
question. Which drawn question is put next is not drafting and is not steering: `next.py`
reads it off the graph as the heaviest with nothing left to wait on, and `/principal:ask`
puts it.

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

**Compaction.** The answering turn sees its lineage and nothing else, so a conflict between
its answer and an admission on another line is the questioner's to see, and the notebook's
`elenchus` answer says how it is met. Seen coming, the question is not put as drawn: put
instead the question that carries the other line's admission with it, so the two are
reconciled in one answer rather than admitted, collided and reconstructed over three. Seen
only in the answer, withdraw the line to the admission it left and put the carrying question
there. Either is a compaction, and it is open only because the one answering is the AI: a
human cannot be asked to forget his first answer, and the AI, asked again in a fresh
context, has not given it. What it buys is a shorter line, and a shorter line is one a turn
carries without loss — so the retreat that predicts a thread will run too long is a
compaction too, taken before the collision. It reaches past the thread: an answer in canon
is withdrawn the same way, and gives way at the merge that replaces it. What compaction is
not for is a conflict with the notebook alone. That is no aporia of the AI's; it is the
principal's, suspended, and every line and thread that could reach the point is drawn before
it is conceded as a dissent. `/principal:ask` looks for the collision before the question
goes and after the answer comes; which line it is, and what question would carry the
admission, is drafted here.

**Framing.** Open on what the answerer is already doing. Presuppose only what the act of asking
makes true; everything contested goes into the question. Minimise the hinges the other party is
not already standing on, rather than the count of them. One question per question — a second
clause loads the hinge and pre-empts the derivation. Never restate the term that raised it: it
is an implied gloss that leaks the principal's reading, and it makes the answering turn parse
the question for a prior instead of answering it. Leakage travels through a filename, a commit
title and a path, not only through wording. And nothing of the notebook may stand in the
answerer's context while the answer is given.

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
  introduces a word through an answer, or through the asker's parts of its hinge: the question
  half, what its asking stood on, which is how the root, with no ancestors, brings in "party" and
  "leak"; and the end and the method, what the asking is for and how that is read, which bring
  in the words the end needs. The answer's half records how the answer was drawn, in the
  encoding's own words, like the question's and the answer's metadata; it introduces nothing and
  does not use a word. Where a part that uses a word cannot reach it over the ancestors, either the line is missing
  an edge or the definition is on the wrong tab.
- A word comes in on a hinge only because the asking stood on it or the end needs it. Every question
  sits below the root, so the root's hinge is where any hard-to-reach word could be parked — and
  parking it there silences the one signal reach gives, a missing edge. The hinge must be true
  before it is useful.
- A hinge is what an act stands on without examining it. It is inherited down the lineage and
  stated only where it differs, and one repeated across siblings belongs to a question above
  them. The end and the method are inherited the same way: stated at the root, and below it only
  where a lineage's end is narrower than the one above it.
