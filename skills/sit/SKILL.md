---
name: sit
description: The principal sits with the one session that speaks. It reads the board and the notebook, opens with a brief of what was done, observed, waits on the principal and stands open, then puts one action at a time on its page, each question put alone, sealed by a clean reader before it is put and graded after, and hands every write to the notebook to a job on the board that a recorder carries out; it writes its own line doc and never the notebook, and it ends with lines still open. Invoke as /principal:sit, confined in a session started in the background as the interviewer kind, or open in an ordinary session.
disable-model-invocation: true
allowed-tools: mcp__claude_ai_Claude_Docs__read, mcp__claude_ai_Claude_Docs__guide, mcp__claude_ai_Claude_Docs__update, mcp__claude_ai_Claude_Docs__create, mcp__claude_ai_Claude_Docs__batch, mcp__Claude_Docs__read, mcp__Claude_Docs__guide, mcp__Claude_Docs__update, mcp__Claude_Docs__create, mcp__Claude_Docs__batch, ArtifactData
---

# /principal:sit

A principal entry point. It grants the **notebook for reading, its own line doc for writing, and
the board**: the session running it speaks with the principal, and every other piece of work is a
job on the board done by a helper of a fixed kind. The method of the questions is the line of
`/principal:dictate` (its **The line** section), and this skill does not repeat it: where that
skill says how a thing is done, this one names the paragraph. `/principal:interview` is a
questioner that has read nothing of the notebook; the sitting's speaker holds the notebook and
the board, and, run the confined way, is started as the interviewer kind only because that kind
is the one that may prompt the principal (**Before anything**). A sitting here is any one session of this entry point, and is not the
annual sitting that `/principal:interview` speaks of.

## After a compaction

After a compaction the harness keeps only the head of this file, and nothing is done from what
survives of it. The plugin's hooks print, at the compaction, the brief, the neighbourhood of the
line in hand and the work in hand (**The brief and the neighbourhood**): that list stands over
the summary, each entry taken up again or marked done. Before the next write, ask or seal, the
speaker reads again, in this order:

1. This file, by its path, `${CLAUDE_PLUGIN_ROOT}/skills/sit/SKILL.md`, whole, then each part its
   index names for the act in hand (**The parts**), by its path under
   `${CLAUDE_PLUGIN_ROOT}/skills/sit/parts/`, with the Read tool in parts, by `offset` and
   `limit`, to its last line where one call cannot hold it.
2. `$SCRATCH`, found where it was made: the session's scratchpad named in its own instructions,
   or a job's `~/.claude/jobs/<id>/tmp`; then `ordo/current` and the open documents of `lines`,
   with `ArtifactData`, exported to `$SCRATCH/speaker/lines` (**The open lines**). The store
   stands over anything remembered, and a difference is said in the action context.
3. The record of predictions: `tools/predictions.py stamp $SCRATCH/graph.json --added
   $SCRATCH/predictions --at <time> > $SCRATCH/speaker/stamp.txt`, and what it printed read
   whole (**The record of predictions**). A sealed file in `$SCRATCH/sealed/` whose answer is
   not yet in `$SCRATCH/answers/` stands: it is not sealed again.
4. The board, as step 1 of the procedure exports it, with `status`, and the line doc the last
   `probe` names, whose head holds the questions set and spent.

Where `$SCRATCH` or the line doc cannot be found again, the speaker says so in the action context
and writes nothing more until the principal answers.

## Before anything

A sitting is run one of two ways, and the speaker says which to the principal when it opens. A
session whose own instructions are the interviewer kind's runs the confined way; any other runs
the open way.

- **The confined way.** The session was started as the interviewer kind, by ground rule 1's
  command line, and the guard on the notebook binds it as that kind. It starts no helper but the
  coordinator.
- **The open way.** An ordinary session may run a sitting too. It runs it as the confined way
  does, and in it the speaker may also brief helpers directly for work the kinds do not carry,
  building and research outside the notebook, by rule 9 of the round (procedure 3); it never
  briefs one for work a kind carries. What holds in the open way: the gates still bind every
  helper by its kind; a helper that is no kind of this plugin is refused any write aimed at the
  notebook; and nothing but this text keeps the speaker itself off the notebook, since the guard
  gives the session running this entry point no opinion.

A sitting runs only on an installed copy of the plugin refreshed to the checkout: the gates that
fire are the installed copy's, and a copy older than the checkout binds the kinds by older rules
or not at all. Where the project keeps its own `.claude/agents/`, check it at the project's root
before anything else, with

```
for f in .claude/agents/*.md; do cmp -s "$f" "${CLAUDE_PLUGIN_ROOT}/agents/${f##*/}" || echo "differs: $f"; done
```

which prints nothing where each definition there is the installed copy's byte for byte. A line
printed means the installed plugin is not the checkout's: stop, and tell the principal to refresh
the plugin and start the sitting again. Helpers are started by the plugin's name in front of the
kind only, the one name the gates always bind; a bare name is bound only as a fallback, where the
project's copy is the plugin's or the project names a notebook.

Where `.principal/notebook.json` names no `board`, stop, and tell the principal what to do, in
these words: "The project names no board. Publish the plugin's `web/board.html` once as a
private artifact, with the db capability and rules that let only its owner read and write, and
put its address in `.principal/notebook.json` as `board`. Publish `web/ordo.html` once as a
private artifact, with the db and user capabilities and rules that let only its owner read and
write, and put its address there as `page`. Then start the sitting again." This session publishes neither. Where it names a `board` and no `page`, the
sitting runs without one and says so, with the same words for the page alone (**The page**).

## On every turn

This file is the core of the skill; its full text is in the parts under
`${CLAUDE_PLUGIN_ROOT}/skills/sit/parts/`, each read on the event **The parts** names. Each rule
below is the short form of one stated in full in the part named after it, and the short form
binds only as far as the full text does: where the two seem to differ, the part is read and it
stands. A section named in bold is found by **The parts**; "rule N" alone is a rule of the round
(procedure 3), "ground rule N" one of **Ground rules**, and "step N" or "procedure N" a step of
the procedure. In every part, `tools/` is the plugin's own, at `${CLAUDE_PLUGIN_ROOT}/tools/`.

**The arrangement** (`arrangement.md`). One session speaks, one kind writes the notebook, the
board holds the work, the kinds of helper are fixed, and an act is one of four kinds. Questions,
sealed texts, rows files and the board's exports are kept in `$SCRATCH` and nowhere else, and
nothing but questions is ever put in `$SCRATCH/questions/`; each party keeps its own export,
versions file and batch under `$SCRATCH/<party>/`. The shell never changes into `$SCRATCH`; a
file of this session's own words is written with the Write tool, never through the shell, and
what a tool prints is sent to its file, never retyped. No helper is started that is not one of
the plugin's kinds for work a kind carries.

**Ground rules** (`ground-rules.md`).

1. One session speaks, and it alone prompts the principal; no helper asks the principal
   anything: what a helper needs of the principal it hands back, and the speaker raises it.
2. It writes its own record and never the notebook: every write to the notebook goes to the
   recorder as a rows file through a job on the board, at a batch point or at the round.
3. Everything that must outlive the sitting is on the notebook or the board: the line doc is
   made at the opening, its bare id put on the board by the sitting's `probe` job, and emptied
   at each batch point, so that nothing stands only in it at the close.
4. An act is one of four kinds, to do, to observe, to ask, to grant, and every act is put to the
   principal as the next action, save an office item the Rule gives the session to run. Only a
   question of principle is counted, against the number the principal sets at the opening. What
   is observed is recorded in a divergence note or the project's own repository, never on the
   board.
5. A share is computed; an act's weight, order, likelihood and cost are judgment, and said to
   be judgment where they are said. What the principal is expected to choose is sealed before
   an act is put and compared after.
6. What is unsure in the ranking is a question put to the principal, never settled by the
   speaker.
7. Every helper is started with a model named for the job, never left to inherit, at the setting
   its definition names; lookups and mechanical checks go to the smallest tier that can do them;
   at most two jobs of tier `full` are claimed at once. No job is added of a kind no helper is
   defined for: the work is said to the principal and carried as an open note of kind `change`.
8. No sitting ends without residue, and none waits to: what an answer opens is a document of
   `lines` at once, an item of *Opened*, and at the batch point an open note. No reading awaiting
   confirmation and no predicted answer is ever written as such a note.
9. What the principal reports of the principal's own state, health, habits, relations or
   circumstances is sensitive, noted so in words where the speaker records it, and kept only in
   the sitting's private places (the notebook, the page and its store, the line doc,
   `$SCRATCH`, the brief's directory, and a private repository only where a standing rule puts such a record): never
   where a stranger can read, nor in the brief of a helper whose work leaves for a repository or
   any published place, which states the mechanism, never the occasion, and carries this rule. A
   build's rationale cites the rule, its examples invented; a building helper that meets a fact
   of a real person's life hands it back, and a helper of the notebook handles it as its work.
   Before a merge the speaker and the full tier's reviewer read the pull request's whole text for
   the principal, by meaning, and the speaker says what it read; a fact found published is put
   to the principal at once. The rule binds a sitting and the publish steps of bootstrap and dictate, and no session
   outside those.

**The round** (`round.md`, procedure 3). One next action a turn, on the page.

1. One question at a time, put as one concrete case, with nothing beside it: no recommendation,
   no tradition on the question being put, no list of what is sealed, no line on how to answer.
   A question not understood is put again, plainer; no question is left unasked because
   readers agree on its answer.
2. The record's prediction is sealed by a clean reader before the question is put, and the
   aporia by the speaker; the sealed file is not read until the answer is in. Seals are not
   listed to the principal, and the line doc's address is never an input of a seal job.
3. The question's file holds the question and its case, and no answer and nothing of the
   sitting.
4. After the answer, on the page: the answer restated, never word for word; tradition for and
   against it; the prediction in three parts. Then it is graded, and what it opened is made lines.
   Tradition is given after every question's answer as above, and after any answer that
   brings a new fact, whatever the kind of action. Every reading given, on the page or in the
   session's words where there is none, is recorded in the notebook in the same round, the
   speaker's next action not put until its `record` job is done, or until the board's limit of
   attempts, or a second set of rows failed or not made, carries the readings as an open note of
   kind `work`.
5. The principal may always override the action ranked first; an override is an observation of
   a gap, never a verdict. Where a transient feeling moves the choice, the deferred action stays
   shown as `next.deferred`.
6. The next action is a `question`, an `office`, a `work` or a `review`. A review is put as a
   question is; one of mechanism carries the speaker's recommendation in `next.recommendation`,
   one that states or changes a principle carries none. A prediction is sealed before every
   review by the speaker itself (**The record of predictions**). Where one of the three cases of
   `ai-line.md` rule 1 holds, the speaker puts the request for a bootstrap unasked, as a review
   of mechanism.
7. An unresolved office of the principal's shows first unless the principal has set it aside or
   an action put before the bell rang is still pending; items run by the session never hold the
   card; `office_deferred` is written only at the principal's word.
8. Every time the speaker stamps is read from the clock, never typed.
9. The speaker writes no code, page or tooling itself, and merges a pull request only on the
   conditions the full rule gives, in the open way. It never tells the principal that the
   process will change from now on without starting the mechanism in the same round, a change
   to the skill's text or tools through a pull request, and it says the process has not
   changed until that is merged and loaded; a note in its own memory is not the mechanism.
10. Every ask of the principal is an action on the page, in order, and anything that needs the
    principal's attention, every explanation and report among it, is on the page; where the page
    is in use, what is only in the session's text has not been presented. The session's printed
    text is a log of operations in the fewest words that identify each, never repeating what the
    page presents; every write of the page is logged by its version, and says in a word where it
    holds an error, a refusal, a helper's finding or a thing owed. Where the page could not be
    written, where the sitting runs without one, and at every stop before the page's store is
    read at the opening, the session says so and says the thing itself. The
    action context is append-only within a round.

**Written as the round goes** (`round.md`). Three notes go to the notebook at the round, through
the recorder, each held off what a clean reader could draw an answer from: a requirement the
principal states, as a note opening with the word *pending*, once its restatement is shown in
the action context; a reading of tradition, as a note opening with the word *pending* that calls
it a lead, never marked verified, stating the party's position and never the answer it was given
after, the question or its case, on the `dictate` tab by `tools/tradition.py rows` where its
party has no tab or no rows can be made for its tab; and a failed prediction, naming who predicted, the kind of
action, the grade and the direction, and never the sealed text, the answer or the case. Each is
made as step 4 makes a rows file (`batch-point.md`). Everything else waits for the batch point's
reviews.

**The brief and the work in hand** (`brief.md`). The brief is the aid and not the notebook:
before a seal, a row or a note the tabs are still read where they stand. Every act begun and not
yet done, save a helper the hooks record as it launches, is an entry the speaker adds to the work
in hand with `tools/inhand.py`, and takes off when it reports or is done; after each change the
work in hand is exported to `ordo/session`.

**The page and the board** (`page.md`, `bells.md`, `board.md`). The page changes only by data
writes with `ArtifactData`, never by republishing; a refusal is read and the document read
again, never forced. `ordo/rule`, `ordo/agenda` and the collection `lines` are the principal's
private data, never written into this repository, a line doc, the board or anything published.
The board holds addresses, counts and fingerprints and never words; it is written only by the
batches `tools/board.py` prints, and exported again before the next mode. One coordinator runs
at a time, and it is the only helper this session starts for work a kind carries.

## The parts

Each part opens with the line that says when it is read. Read a part, whole, on its event and
before the act it governs, and again on that event after a compaction. Parts in the order the
skill's text runs:

| part | what it holds | read it |
|---|---|---|
| `arrangement.md` | **The arrangement**: the notebook, the board, `$SCRATCH` and its directories, the parties' exports, the kinds | at the opening, before `$SCRATCH` is made; before naming a path, id or fingerprint the core does not spell; before starting any helper |
| `brief.md` | **The brief and the neighbourhood**: what the brief holds, its size, where it lives, who receives one, the check on a text leaving, the work in hand | when the opening's graph is made; when the line in hand changes or a batch point's check moves the notebook; when a text leaving is refused; when any act begins or ends; before a seal, a row or a note |
| `serves.md` | **What the sitting serves**, and **Observations** | when a prediction fails, the action ranked first is overridden or deferred, or an action or sitting is not taken up; before a rule here is rebuilt |
| `ground-rules.md` | **Ground rules** 1 to 9 in full | at the opening; when a ground rule's short form leaves the act unsettled |
| `page.md` | **The page**: its sections and panel, the owner-only read, the writes, `ordo/current` and its fields | at the opening, before the first write to the page's store; before any write to `ordo/current` |
| `bells.md` | **The page**, continued: `ordo/rule`, `ordo/ticks-<day>`, `ordo/agenda`, and what is read and written at each turn | at each turn, before the Rule and the marks are read; when a bell rings; when the principal reports an office item or sets an office aside; before running an item of the session's; at a sync |
| `open-lines.md` | **The open lines**, **The tool** | at the opening and after a compaction; when an answer comes in; when a line is opened; when the notebook's revision moves; at the first sitting of the Rule's week |
| `predictions.md` | **The record of predictions** | before every prediction of the speaker's own, that is before each review; when a grade comes back; before a failed prediction's note is written; at a batch point carrying a lesson that recurs; after a compaction |
| `board.md` | **Which kind runs which job**; the procedure's step 1, the board's export, and step 6, how jobs reach the board | at the opening; before the board is exported or written; before the coordinator is started |
| `opening.md` | Step 1's read of the notebook, and step 2, the brief | at the opening, after the board's export |
| `round.md` | Step 3, the round's ten rules in full, and **Written as the round goes** | at the opening; before putting each next action; when an answer comes in; when the principal overrides or defers; when a bell rings; before writing a note at the round; before briefing a build or merging |
| `batch-point.md` | Step 4, the batch point and its chain, and step 7, closing | at each batch point; before a note's rows file is made at the round; when a link of a chain fails; at the close |
| `ai-line.md` | Step 5, the AI's own turns, and **The line in the AI's graph** | before a question for the AI's record is drafted or put; before a clean turn or a `lead`, `turn`, `compare` or `place` job; before briefing any build; before a constraint is treated as binding |
| `attenuation.md` | **Attenuation**: what no tool decides | at the opening; before relying on a tool, gate or helper's reply to hold a rule; when a gate gives no opinion, a permission check refuses a write or a fetch finds no transcript |
| `departures.md` | **Where this entry point departs from the others**, and what it says now that reverses what it said before | when another entry point says otherwise than this one; when a rule here seems to reverse what it said before |
