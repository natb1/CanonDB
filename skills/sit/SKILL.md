---
name: sit
description: The principal sits with the one session that speaks. It reads the board and the notebook, opens with a brief of what was done, observed, waits on the principal and stands open, then puts one act at a time, each question sealed by a clean reader before it is put and graded after, and hands every write to the notebook to a job on the board that a recorder carries out; it writes its own line doc and never the notebook, and it ends with lines still open. Invoke as /principal:sit, in a session started in the background as the interviewer kind.
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
the board, and is started as the interviewer kind only because that kind is the one that may
prompt the principal. A sitting here is any one session of this entry point, and is not the
annual sitting that `/principal:interview` speaks of.

The arrangement is what this entry point is for and changes only by the principal's dictation:
one session speaks, one kind writes the notebook, the board holds the work, the kinds of helper
are fixed, and an act is one of four kinds. How it is carried out today is not the arrangement
and will change as the harness does: a coordinator started under the speaking session runs the
board, and the speaking session is started by the command line ground rule 1 gives.

The notebook is the document `.principal/notebook.json` names at the project's root, read as
`/principal:dictate` says. The board is the page published from `web/board.html`, with its own
store, and it is named by `board` in the same file. `tools/` is the plugin's own, at
`${CLAUDE_PLUGIN_ROOT}/tools/`. `$SCRATCH` is the sitting's scratch directory, the session's own
and outside the checkout: the questions, the sealed texts, the rows files and the board's exports
are kept there and nowhere else, and they go with the session. Each question is a file of its
own in `$SCRATCH/questions/`, the one directory the clean reader's read gate opens to it; the
principal's answers are in `$SCRATCH/answers/`, what the speaker seals of its own in
`$SCRATCH/sealed/`, the rows files in `$SCRATCH/rows/`, and nothing else is ever put in
`$SCRATCH/questions/`. Each party that reads and writes the board has its own export, versions
file and batch, `$SCRATCH/<party>/board`, `$SCRATCH/<party>/versions.json` and
`$SCRATCH/<party>/out`, the party being `speaker` or `coordinator`, so that one never sends or
removes a batch the other wrote; everything the coordinator writes is under
`$SCRATCH/coordinator/`, its replies, results, tab lists and views among them, and the plugin's
gates refuse it every other path. `$SCRATCH` is an absolute path spelled in letters, digits and
`_ . + -`, outside the project, outside the plugin's root, and outside `~/.claude` save a
session's own `~/.claude/jobs/<id>/tmp`: the session's scratchpad, `/tmp/claude-*/…/scratchpad/…`,
is one, a job's `~/.claude/jobs/<id>/tmp/…` another, and the gates recognise no other root. No directory on it is named `questions`, `answers`,
`replies`, `results`, `sealed`, `rows`, `check` or `coordinator`, since the gates read those
names as the sitting's own. A file of this session's own
words is written with the Write tool, never through the shell; what a tool prints is kept by
sending its output to the file, never retyped. A file's fingerprint is its SHA-256 in
hexadecimal (`sha256sum`). A sitting's id is
`s` and the UTC time it opened in digits, `date -u +s%Y%m%d%H%M`. The kinds of helper are
defined under the plugin's `agents/`: `clean-reader`, `fetcher`, `recorder`, `reviewer`,
`grader`, `checker` and `coordinator`, with `interviewer` the kind of the speaking session. No
helper is started that is not one of them: the guard on the notebook knows these kinds and no
other.

## Before anything

This session must have been started as the interviewer kind, since that is what the guard on the
notebook binds. A session whose own instructions are not that kind's stops here, and tells the
principal the command of ground rule 1. In an ordinary session the guard decides nothing, and
nothing but this instruction would keep the speaker off the notebook.

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

Where `.principal/notebook.json` names no `board`, stop and say so: this session has no tool that
publishes one.

## Ground rules

1. **One session speaks.** It is the one running this entry point, started in the background by
   name as the interviewer kind, and the principal attaches to it:

   ```
   claude --bg --name <name> --agent principal:interviewer -- "/principal:sit"
   claude attach <name>
   ```

   It alone prompts the principal. No helper asks the principal anything: what a helper needs of
   the principal it hands back, and the speaker raises it. The one exception is named in
   procedure 5.
2. **It writes its own record and never the notebook.** The connector's `batch` makes the line
   doc and `update` and `create` write it. Writes to the notebook go to the recorder as rows
   files (procedure 4) through a job on the board. What refuses this session a write to the
   notebook is the guard, the plugin's `hooks/notebook-gate.py`, which refuses every kind but the
   recorder, the interviewer included; the tool list does not.
3. **Everything that must outlive the sitting is on the notebook or the board.** The sitting's
   own record is the line doc of `/principal:dictate` (**The line doc**), with one section more,
   *Opened*, its items `- O1. …`. It is made when the sitting opens as a document of its own (a
   `batch` with `container.create`, outside the notebook), and its bare id, the trailing id of its
   address with no title in front of it, is put on the board at once as the result of a `probe`
   job named for the sitting, `<sitting>-open-linedoc-probe`,
   which the speaker claims and marks done itself; no helper runs it. So a sitting that ends
   abnormally is found again: the next sitting reads the line doc the last probe names and
   empties what stands there. The line doc is emptied at each batch point onto the notebook, and
   nothing stands only in it at the close.
4. **An act is one of four kinds: to do, to observe, to ask, to grant.** Every act is put to the
   principal, so every proposal is a question and is counted as one: the principal sets how many
   the sitting may spend when it opens, and the number set and the number spent stand at the head
   of the line doc. To observe is to collect what is the case, by the principal or by a helper,
   and what was observed is recorded where the project keeps such things, a divergence note
   (`/principal:dictate`, **No action is taken in a dictation**) or the project's own
   repository, and never on the board.
5. **A share is computed; an act's weight is judgment.** `tools/shares.py` computes the share of
   the root that a question carries, and with `--price` the sum over questions somebody named.
   Which questions an act serves or releases is the speaker's reading, and so is every order
   among acts beyond the shares of those questions, how likely an act is to help, and what it
   costs: each is said to be judgment where it is said. Before an act is proposed, what the
   principal is expected to choose is sealed (procedure 3), and compared after: a different
   choice is a failed prediction like any other.
6. **What is unsure in the ranking is a question.** A share that seems wrong, a pressure that
   seems missing, an act whose place in the lineage is unclear, is put to the principal like any
   other question, and is not settled by the speaker.
7. **Tiers.** A helper is started at the setting its definition names. A job's `tier` is the
   board's word and names no model: it is the one the table below gives its kind, and at most two
   jobs of tier `full` are claimed at once. Nothing reads a tier but the cap, the brief and the
   reader of the table: two kinds of one tier may run at different settings, and the setting is
   always the definition's. A kind the board knows and the table does not name
   (`state`, `remedy`, `compare`, `line`, `place`) has no helper defined for it, and no job of it
   is added: the work is said to the principal with the weighing of a helper for it, what it
   must read, what it must not, and whether a defined kind's tools would keep it clean, and it
   is carried as an open note of kind `change`.
8. **No sitting ends without residue, and none waits to.** A line of questions taken up opens
   further lines, and the sitting is an ongoing process: it takes up the lines the principal
   chooses from those proposed, and in doing so opens more, which are tracked and returned to.
   What an answer opens is written in the line doc's *Opened* section at the step that opened
   it, and at the batch point it goes to the notebook as a note opening with the word *open* on
   the tab it bears on, in a rows file like any other. A line is never finished: it is in hand
   or at rest, and a line at rest returns by what its note says brings it back, or by being
   proposed again. No reading of the speaker's that awaits confirmation, and no predicted answer,
   is ever written as such a note, since a clean reader reads those tabs; `residue.py note
   --read` is passed only a reading the principal has confirmed. A reading that is set down is
   set down as the question it answers, and a prediction is not kept.

## Which kind runs which job

The inputs are addresses: a path under `$SCRATCH`, the notebook's or the line doc's address, a
tab's name or a question's id. The board holds addresses, counts and fingerprints and never
words, and `tools/board.py` refuses a value with a space.

| job | tier | helper | inputs | what reaches the board |
|---|---|---|---|---|
| `probe` | `mid` | none: the speaker | none | `line_doc`: the line doc's address |
| `observe` | `mid` | none: the speaker | `subject`: the address of what is observed | `recorded`: the address it is recorded at |
| `seal` | `full` | `clean-reader` | `notebook`, `question`: the question's file, `$SCRATCH/questions/<n>.md` | `reply`: the sealed file, `fingerprint` |
| `grade` | `mid` | `grader` | `sealed`: the seal's `reply`, `answer`: the answer's file | `reply`: the grade, `fingerprint` |
| `fetch` | `small` | `fetcher` | `notebook`, `tabs`: a file of tab names, one name a line | `reply`, `fingerprint`, `views`: `$SCRATCH/coordinator/views/<job id>`, `list`: `$SCRATCH/coordinator/lists/<job id>/doc-<document id>.json` |
| `record` | `mid` | `recorder` | `notebook`, `rows`: the rows file | `reply`: the recorder's report, `fingerprint` |
| `check` | `small` | `checker` | `views` and `list`: the fetch's `$SCRATCH/coordinator/views/<job id>` and `$SCRATCH/coordinator/lists/<job id>/doc-<document id>.json` | `reply`: what the tools printed, `fingerprint` |
| `review` | `full` | `reviewer` | `notebook`, `rows`, `owed`: what the rows were to carry | `reply`: the findings, `fingerprint` |
| `turn` | `full` | none yet | `question`: the question's id | nothing: it waits |

The coordinator runs every kind the table gives a helper, every `review` among them, and passes
over the rest; `probe` and `observe` the speaker claims and marks done itself, and `turn` waits.
The coordinator is handed the board's address, the path of `$SCRATCH` and the path of the
plugin's `tools/`, and nothing else; every address it puts on the board is under `$SCRATCH`. It
hands a clean reader the path of the question's file, which that reader may read, and the
notebook's address; a fetcher the notebook's address and the names in the `tabs` file; a checker
the tools directory, the `views` directory, the `list` file and `$SCRATCH/check/<job id>` to
work in. What a helper hands back in words the coordinator writes to
`$SCRATCH/coordinator/replies/<job id>`, and only that file's address and fingerprint go on the board, as `reply` and
`fingerprint`. After sending a claim, the coordinator exports the board again and starts the
helper only where the job stands `claimed` by `coordinator`; where it does not, it starts
nothing for that job and moves on. Every helper ends its reply with one last line, `status: ok` or `status: failed`,
by a rule its definition gives, and the coordinator reads that line and nothing else of the
reply: `done` on `status: ok`, `fail` with the reason `helper` on `status: failed` or where the
line is missing. The fetcher reads the document's tab list before the tabs; for a `fetch` the
coordinator takes the transcript path the harness gives for the fetcher it started, runs
`tools/views.py <that transcript> $SCRATCH/coordinator/lists/<job id> --list-only`, which saves
the tab list as `doc-<document id>.json` in the shape `tools/read.py` takes, and then
`tools/views.py <that transcript> $SCRATCH/coordinator/views/<job id> --doc
$SCRATCH/coordinator/lists/<job id>/doc-<document id>.json`, so
that each file is named for its tab and the views directory holds the tabs and nothing else.
Where the harness gives no transcript path, the coordinator fails the `fetch` with the reason
`helper` (see **Attenuation**).

## Procedure

**1 — Read.** Export the board with `ArtifactData`: a `list` of `jobs`, paged with
`query.cursor` until it ends, and a `get` of `meta/board`, each with `out_dir` set to
`$SCRATCH/speaker/board` itself; write the versions the reads returned to
`$SCRATCH/speaker/versions.json` as `{"<collection>/<doc_id>": <version>}`. A board not yet
begun has no `meta/board`, and the export finds none: make the directory, write `{}` as the
versions, and run `tools/board.py init $SCRATCH/speaker/board --versions
$SCRATCH/speaker/versions.json --notebook <the notebook's address> --out $SCRATCH/speaker/out`,
sent as step 6 sends a batch, and export again. Then `tools/board.py status
$SCRATCH/speaker/board --versions $SCRATCH/speaker/versions.json` and `tools/board.py verify
$SCRATCH/speaker/board --versions $SCRATCH/speaker/versions.json`. Every writing mode takes
`--out $SCRATCH/speaker/out`, never a directory inside the export, which the gate would read as
a collection.

Before anything else, the jobs of an earlier sitting are closed, since their files went with
that session and none is ever run or retried: each one still `queued` or `waiting` is failed
at once, `tools/board.py fail $SCRATCH/speaker/board <id> --versions
$SCRATCH/speaker/versions.json --by <this sitting's id> --reason superseded --now <time> --out
$SCRATCH/speaker/out`, which needs no claim and leaves its attempts as they were; each one still
`claimed` is first put back by `release`, below, once its claimant is read as gone, and then
failed the same way. Each batch is sent, and the board exported again, before the next.

`tools/board.py release $SCRATCH/speaker/board --versions $SCRATCH/speaker/versions.json
--older-than N --now <time> --out $SCRATCH/speaker/out` puts back every claimed job quiet for
more than N seconds, and takes no id. It is run only when every job it would catch has a
claimant read as gone; otherwise wait. Read the line doc the last `probe` names; what stands
there is emptied in this sitting's first batch point.

Read the notebook where it stands. Every sitting opens with a `fetch` of every tab of the
project, its ancestors and the parties it cites, since the shares and the open lines are
computed over a graph that holds the root: `tools/page.py $SCRATCH/coordinator/views/<job
id>/*.json -o $SCRATCH/tabs` over the lifted views, and `tools/read.py
$SCRATCH/coordinator/lists/<job id>/doc-<document id>.json $SCRATCH/tabs -o $SCRATCH/graph.json`,
with no `--scope`, as `/principal:dictate` step
1 gives them, then `tools/shares.py`, `tools/residue.py list $SCRATCH/graph.json --by-share` and
`tools/divergence.py list $SCRATCH/graph.json`. `residue.py list --by-share` is run over this
graph, the opening's whole-notebook read, and no other: over a graph of some tabs and their
ancestors a share is wrong even where the root is among them, and the tool cannot always tell. The listing
orders open notes by the share of the tab each stands on; that is the tab's weight and not the
line's, and it is a first ordering for the speaker's reading, not a ranking. After the opening,
a few blocks are read in place, by `search` or a `view` of each, as `/principal:dictate` step 1
reads a dictation that touches only line-shaped parts; nothing of a tab is transcribed by this
session.

**2 — The brief.** In this order: what was done and what failed since the last sitting, by job
and kind, from `status`; what was observed, from the divergence listing; what waits on the
principal, each `waiting` job with what it releases; three numbers, how many open notes the last
sitting took off because their line stands on the tab, how many it added, and how many stand
open now, the first two from the count its line doc kept at its close and the third from this
opening's listing, the third said plainly to be a count that is not driven to nothing; the acts
that come first by the shares of what they serve, each with its reason, the reading marked as
judgment, as an order and not yet a proposal; and the question of how many questions the
principal will spend this sitting. Nothing else is asked until that number is set.

**3 — One act at a time.** For a question:

- Put it as one concrete case resting on what the notebook states (`/principal:dictate`,
  **The fidelity round** for how a question is drawn, and **A case rests on the record** for its
  premises).
- Write the question to `$SCRATCH/questions/<n>.md`, `<n>` its number in the sitting, and add a
  `seal` job for it (step 6); start the coordinator,
  so that a clean reader draws the record's answer as the clean reader's definition says. This
  session does not read the sealed file until the answer is in. What the speaker remembers of
  the line that the notebook does not carry is sealed apart, by the speaker, in a file of its
  own in `$SCRATCH/sealed/`. Only the two fingerprints go in the line doc's Fidelity rounds section, `- F1. Sealed
  <fingerprint>.` The line doc's address is never an input of a seal job.
- Put the question, with the four parts of the step (**The four-part step**), and count it.
- After the answer, read the sealed file and state it in the line doc. Write the principal's
  answer to `$SCRATCH/answers/<n>.md` as the admission the line doc records, never word for word, and add a
  `grade` job over the sealed file and that answer. Class a failure as **The fidelity round**
  classes it, and draft the remedy for the batch point. Once the remedy is written (step 4), a
  fresh `seal` job with a new row in its id draws the prediction again, and a `grade` job over
  its result and the same answer file grades it; the outcome is written in the line doc as
  `Redrawn: …`.
- What this opened: each further line the answer opened, in *Opened*, with what raised it and
  what would bring it back (ground rule 8).

A question the principal does not understand is put again, plainer, as one case; it is never
withdrawn and decided for the principal. No question is left unasked because readers agree on
its answer.

An act of another kind is proposed with the shares of what it serves, sealed and put the same
way, and the principal's choice is graded against the sealed one. What is chosen is then carried
as its kind asks: an act to observe is an `observe` job, which the speaker claims under the
sitting's id and carries out itself with its own tools, starting no helper for it, or the
principal's own observation, recorded where ground rule 4 says; an act to do that a rows file can carry goes to the batch
point, and one it cannot goes by `/principal:dictate` or `/principal:bootstrap`, named to the
principal as an open note of kind `change`; a grant is written at the batch point as a case on
the tab of the clause it bears on. Each ends with what it opened.

**4 — The batch point.** The rows are shown to the principal in words first: the sentences for
the tabs, the cases, what is expected to generalize, the questions for the AI's own record, the
open notes to add, and the open notes to take off because what they held now stands on the tab.
What the principal approves is then made into a **rows file**, `$SCRATCH/rows/<job id>.json` for
the `record` job that carries it: a JSON list with one entry per run of a tool, in the order the
tools were run, a tab standing in as many entries as tools were run over it. Each entry holds
the node id of the tab the run was over under `node`; what the tool printed under `payload`,
exactly as it printed it, the `ops` and, where the tool prints one, the read's `ifRev` beside
them; and the operation id under `op_id`, which is the `record` job's id and the entry's number
counted from 1, `<job id>-<n>`. The speaker makes it by running the tools over saved reads of
those tabs, got by a `fetch` job just before, each run's output sent to a file of its own,
`$SCRATCH/rows/<job id>/<n>.json`, and never retyped; each is made an entry with `jq -c --arg node
<node id> --arg op <job id>-<n> '{node: $node, payload: ., op_id: $op}'
$SCRATCH/rows/<job id>/<n>.json > $SCRATCH/rows/<job id>/<n>.entry`, and the list is `jq -s .
<every .entry file, named in order> > $SCRATCH/rows/<job id>.json` (`jq` must be installed). The
tools are `tools/inplace.py`, `tools/application.py`, `tools/residue.py note` with
`tools/inplace.py note insert READ --after ID --text T` (after the last block of the section the
note bears on, or the tool refuses), the note's words being what `residue.py note` printed to a
file and passed as `--text "$(cat <that file>)"`, and `tools/inplace.py note delete READ --block
ID`. The recorder sends each entry as it stands, as one update, in the file's order, changes
nothing, and sends nothing after an entry not applied. Writes in place are
guarded block by block and need no lease (`/principal:dictate`, **Several sessions**). Whatever the tools cannot print as
operations, a body, a section, a new tab, the tab patch, or anything that needs a lease, is
outside a sitting: it goes by `/principal:dictate`, and the sitting leaves it as an open note of
kind `change`.

The approved rows become four jobs in a chain, each waiting on the one before: `record`;
`fetch` of the tabs the rows touched and their ancestors; `check`, its `views` and `list` that
fetch's `$SCRATCH/coordinator/views/<job id>` and `$SCRATCH/coordinator/lists/<job
id>/doc-<document id>.json`, the document id being the notebook's bare id, over which the checker
runs its one fixed sequence, `tools/page.py`, `tools/read.py` scoped to the tabs read and
`tools/check.py`, the check `/principal:dictate` step 5 runs after a write in place, and takes no
command. It does not run `tools/verify.py`, which `/principal:dictate` runs after a body write:
over a scoped graph the counts on a question line are of the tabs read, and it would fail a
correct page. So the check sees every rule over the tabs read, a missing ancestor among them,
and does not see a link the page lost or carries astray, or a fault between a tab read and one
not read (**Attenuation**); and `review`, handed the
rows file and a file of what the rows were drawn to carry from the line doc. The coordinator
runs each of them.

A link of the chain that fails stops the chain there: the jobs after it stay `queued`, blocked,
and `status` names them. The speaker reads the failed job's reply, the file
`$SCRATCH/coordinator/replies/<job id>`, since a failed job carries no result, tells the principal which link failed and why in a sentence, and
removes the cause where it is the sitting's to remove: a `fetch` or a `check` that failed on
something passing is run again as it stands; a `record` whose rows no longer hold is not: the
jobs after it are failed `superseded`, and new rows are drawn for a new chain. Once the cause is removed,
the board is exported again as step 1 does, and the failed job is queued again with `tools/board.py retry $SCRATCH/speaker/board <id> --versions
$SCRATCH/speaker/versions.json --now <time> --out $SCRATCH/speaker/out`, sent as any batch, and
the coordinator started again; `retry` refuses a job at the board's limit of attempts, and the
jobs after that one are then failed `superseded` and what the chain was for carried as an open
note of kind `work`.

Each finding of a review is resolved, by rows shown and approved as any rows, or carried as an
open note of kind `work`; the review is run again, as a new job with a new row, until it returns
nothing not so resolved or carried. Then the line doc is emptied of what is now on the notebook.

**5 — The AI's own turns.** A question for the AI's own record that the principal approves at a
batch point is added to the board as a `turn` job and held at once with `wait`, `tools/board.py
wait $SCRATCH/speaker/board <id> --versions $SCRATCH/speaker/versions.json --now <time> --out
$SCRATCH/speaker/out`, until the tooling for it is built; then it is queued again with `resume`,
`tools/board.py resume $SCRATCH/speaker/board <id> --versions $SCRATCH/speaker/versions.json
--now <time> --out $SCRATCH/speaker/out`. Until then the principal runs `/principal:ask` in a session of the principal's
own. That session is the one exception to the single speaker, and is named to the principal as
one.

**6 — How jobs reach the board.** Write the jobs to a file as a JSON list, at most 49 new jobs to
a file, since one batch takes 50 writes and the board's count of jobs is one of them; each with
`id` `<sitting>-<batch>-<row>-<kind>` and those four parts again as `sitting`, `batch`, `row`
and `kind`, its `tier` from the table, `waits_on` the ids of the jobs it waits on, and its
`inputs`; export the board again as step 1 does, and run `tools/board.py add
$SCRATCH/speaker/board --versions $SCRATCH/speaker/versions.json --jobs <file> --now <time>
--out $SCRATCH/speaker/out`, where `<time>` is `date -u +%Y-%m-%dT%H:%M:%SZ`. The tool writes
each document to be written as a file of its own in `$SCRATCH/speaker/out` and
`$SCRATCH/speaker/out/batch.json`, whose entries name those files by `file_path`: send the
entries as one `ArtifactData` `batch`, as written, each pinned to the version read. A refusal is
read and the board read again, never forced. The speaker's own marks, `claim`, `done` and `fail`
of a `probe` or an `observe`, and `fail` with `superseded`, take `--by <the sitting's id>`, and
every writing mode but `init` takes `--now <time>`: a claim is `tools/board.py claim
$SCRATCH/speaker/board <id> --versions $SCRATCH/speaker/versions.json --by <this sitting's id>
--now <time> --out $SCRATCH/speaker/out`, and a mark of done is `tools/board.py done
$SCRATCH/speaker/board <id> --versions $SCRATCH/speaker/versions.json --by <this sitting's id>
--result <the result file> --now <time> --out $SCRATCH/speaker/out`, the result file a JSON
object the speaker writes with the Write tool, `line_doc` for a `probe` and `recorded` for an
`observe`, as the table gives them. Each batch is sent, and the board exported again, before the
next mode. Then start the coordinator with the Agent
tool, as `principal:coordinator`, handed the board's address, `$SCRATCH` and the plugin's
`tools/`; it runs one job and reports how it ended, so start it again until its report names
the job awaited or says nothing is runnable, and export the board again, as step 1 does, before
this session's next mode, since the coordinator writes the board through an export of its own.
One coordinator runs at a time: the next is started
only once the last has reported, since every coordinator works through the one
`$SCRATCH/coordinator/` export. The coordinator is the only helper this session starts; every
other piece of work is a job on the board, every `review` included.

**7 — Closing.** The close is a batch point like the others. Run `status` again and say what
stands open: jobs not done, failures by kind, what waits on the principal, the questions spent
against the number set, and the three numbers of step 2 for this sitting. The count of open
notes now is not listed again over a fetch of what the sitting wrote, whose shares and count
would be of those tabs alone: it is the opening's listing, plus the notes this sitting added,
less those it took off, and it is again said to be a count not driven to nothing. Write that
count, with the numbers this sitting took off and added, at the head of the line doc, for the
next brief. Each job of this sitting still `queued` or `waiting` is failed `superseded` under
the sitting's id with `fail` as step 1 gives it, which needs no claim, since its files go with
the session; a job still `claimed` is first let end or, once its claimant is read as gone, put
back by `release` (step 1) and failed the same way; what it was for, if still owed, goes in an
open note of kind `work`.

The order is: the line doc is read for what would be lost, by the `review` of the last chain,
whose `owed` file is everything the line doc still holds; what it finds is resolved or carried
as an open note of kind `work` through one more rows file; and then the line doc is emptied onto
the notebook. A review that still finds something does not hold the sitting open: its findings
go onto the notebook as open notes of kind `work`, and the sitting closes. Where the principal
leaves before approving the last rows, the line doc stands with its address on the board, and
the next sitting opens by reading it.

## Attenuation

What no tool decides. Hold these by reading.

- **The speaker is not a clean context.** It has heard the principal, so the record's answer it
  would draw is not the record's, and agreement between readers is no evidence the record is
  right: two clean readers that draw the same answer have read the same words. The principal's
  answer is the test.
- **A clean reader is clean by instruction.** The connector's `read` reaches every document the
  account can read, the line doc among them. What keeps a clean reader to the notebook is its
  definition and that it was handed one address; a kind is tried before it is trusted, by
  starting one and asking what it was handed and what it can read. Its `Read` of files is
  bound by the plugin's read gate to `$SCRATCH/questions/`, so it cannot open an answer, a
  sealed reply, a grade or a rows file; it can open another question of the same sitting,
  which holds no answer. A file in a `questions` directory outside a scratch root the gates
  recognise gets no opinion from the gate, and the harness's own permissions decide it.
- **The shell and the files are bound for the helpers, not for the speaker.** The plugin's
  shell gate lets the checker run its three tools and its one listing, writing only under a
  `check` directory, and the coordinator the board's tools and a few plain programs over paths
  under its own `coordinator` directory, and refuses every other kind the shell. The plugin's
  write gate holds the coordinator's Write to its own `coordinator` directory, the
  interviewer's off the project's `.principal/` and `.claude/`, the plugin's root and
  `~/.claude`, and refuses every other kind a Write or an Edit. Each binds a kind by the
  plugin's name in front of it, or by its bare name in a project whose own definition is byte
  for byte the plugin's or that names a notebook. A kind's own directory counts only below a
  scratch root the gates recognise. The interviewer's shell is not confined, so for the speaker
  the rule that only the recorder writes the notebook is held by its definition and this entry
  point alone: one shell line reaches every file the gates stand on, and a session of its own.
- **The speaker's refs are not checked against the live connector.** The guard refuses every
  helper but the interviewer a write by a `ref` to a node, a file or an utterance, since the
  connector may follow such a ref into a document the call does not name. The speaker writes
  its line doc by such refs, and whether one could reach the notebook through a link is
  unchecked against the live connector: the speaker writes only by refs read from its own line
  doc.
- **The check after a record is scoped.** The checker runs `/principal:dictate`'s check after a
  write in place, `check.py` over the tabs read and their ancestors, and not `verify.py`. A link
  the page lost or carries astray, and a fault between a tab the rows touched and one the fetch
  did not read, are not seen by it; a write that could make one goes by `/principal:dictate`,
  which checks over the whole graph, and the `review` reads the rows against what they were to
  carry.
- **The guards have a blind spot outside the project.** A speaking session started outside the
  project, with no `CLAUDE_PROJECT_DIR` in its environment, finds no notebook file, and the
  guard on the notebook then gives no opinion, the interviewer included; the write gate and the
  shell gate then do not know the project either, and hold the interviewer only off any
  `.principal` or `.claude` directory and a coordinator only to its scratch. The speaker is
  started in the project by ground rule 1's command line, and that is what holds it.
- **The fetch stands on a transcript no tool promises.** The coordinator lifts the views from
  the fetcher's transcript at the path the harness reports with the fetcher's result. Nothing
  guarantees the harness reports one, and no live sitting has yet shown it does: this is
  untested. Where no path is reported the `fetch` fails with the reason `helper`, and every
  later link waits on it; the speaker says so to the principal, and nothing of the notebook is
  read by another road. The shell gate admits as a transcript only a `.jsonl` under
  `~/.claude/projects/<the session's project>/`, that directory named from `CLAUDE_PROJECT_DIR`
  with every character but a letter or a digit read as `-`; where the variable is not set, a
  `.jsonl` under any project's there. A harness that keeps it anywhere else stops the fetch.
- **A reply on disk is the coordinator's copy.** The coordinator writes a helper's reply with
  the Write tool, and the fingerprint sealed is of that copy; nothing checks the copy against
  what the helper handed back. The speaker reads a sealed reply as the coordinator wrote it.
- **The board's gate reads spaces, not sense.** A sentence spelled without spaces, or a file
  whose name says what it holds, passes it. Read every input and result as a reader of the
  board would.
- **Nothing reaches the principal but through the speaker.** A helper that seems to need the
  principal is a job held with `wait`, never a helper that asks; and a permission the harness
  asks of the principal on a helper's behalf is a second voice, said as such.
- **Whether a job's kind fits its helper is read.** `status` counts failures and retries by kind;
  what the count means, a helper too small for its work or a job badly drawn, is read, and a
  kind that keeps failing is said to the principal.
- **A sealed text lives for the sitting.** It is in `$SCRATCH` and goes with the session. A
  sitting that ends with one unstated carries its question to the notebook as an open note of
  kind `case`, with the case and without the prediction, so that the next sitting draws it again.
- **The count of open lines grows.** That is the pattern of the work and not a fault. What is
  watched is that nothing is lost and that the order the acts were proposed in is the one the
  shares give, never that the count falls; which line is in hand is the principal's choice, and
  a line closed to bring the number down is a line dropped.

## Where this entry point departs from the others

- An act is put and carried out, where `/principal:dictate` **No action is taken in a
  dictation** takes none.
- Rows are written at each batch point while the sitting goes on, where `/principal:dictate`
  **The line** writes nothing while the line runs.
- The rows are shown to the principal in words and made by the tools, with no plan table and no
  `line.py check`, where `/principal:dictate` step 2 enters plan mode first and **The
  compaction** has `line.py check` pass before the plan runs; this session has no export to give
  `line.py` its markdown.
- The record's answer is drawn by a `seal` job and never by the questioner, where
  `/principal:dictate` **Every interviewing phase is the line** has the questioner seal it.
- The sealed text holds what the clean reader's definition hands back, where
  `/principal:dictate` **The fidelity round** also seals what the principal is expected to add.
- The prediction is graded by a grader, where **The fidelity round** has the questioner grade
  it.
- A sealed text is kept in the session's `$SCRATCH`, where **The fidelity round** keeps it in
  the checkout's `.work/`.
- No question is left unasked because readers agree on its answer, where `/principal:dictate`
  **Read the notebook before asking what it answers** does not put a question the notebook
  already answers.
- The review is a `reviewer` handed the rows and what they were to carry, started by the
  coordinator for a `review` job, where
  `/principal:dictate` **The adversarial review** starts an agent with the line doc, the notebook
  and the checkout.
- An operation id is the `record` job's id and the entry's number, one entry to a run of a
  tool, where `/principal:dictate`
  **Several sessions** has `<session>-<step>-<n>`.
- The line doc has a section *Opened*, which `/principal:dictate` **The line doc** does not list.
- The line doc is emptied onto the notebook and nothing waits on there being nothing open, where
  `/principal:dictate` **Retirement** keeps the doc until the plan is executed, a review returns
  nothing and its fidelity round has passed.
- A sitting may end with a fidelity item failed, remedied or left as an open note, where **The
  fidelity round** goes on in rounds until one passes whole.
- A board claim is released by `release --older-than`, for every claim quiet that long, where
  `/principal:dictate` **A lease and a claim are released by reading** says nothing expires; here
  it is run only once every claimant it would catch is read as gone.
- The board's store is exported, where `/principal:dictate` **The document is read in place,
  and nothing is exported** speaks of the notebook, which is still read in place.
- The line is run by a fifth entry point, which `/principal:dictate` **Where the line is shared**
  does not list among its four.
- The principal's `/principal:ask` session is a second session that prompts, the one exception
  to ground rule 1; `/principal:ask` itself is unchanged.
