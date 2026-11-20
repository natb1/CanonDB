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

The arrangement is what this entry point is for and changes only by the principal's dictation:
one session speaks, one kind writes the notebook, the board holds the work, the kinds of helper
are fixed, and an act is one of four kinds. How it is carried out today is not the arrangement
and will change as the harness does: a coordinator started under the speaking session runs the
board, and the speaking session is started the confined way or the open way (**Before
anything**).

The notebook is the document `.principal/notebook.json` names at the project's root, read as
`/principal:dictate` says. The board is the page published from `web/board.html`, with its own
store, and it is named by `board` in the same file; the page the round is put on is named by
`page` there (**The page**). `tools/` is the plugin's own, at
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
names as the sitting's own, nor `speaker`. A local file an `ArtifactData` call of the speaker's
writes or sends, an `out_dir` or a `file_path`, is under `$SCRATCH/speaker/`, and the
coordinator's under `$SCRATCH/coordinator/`: the guard on the notebook refuses either kind any
other. The session's shell stays in the project: it never
changes its working directory into `$SCRATCH`, where the gates would read it as the project's
root. A file of this session's own
words is written with the Write tool, never through the shell; what a tool prints is kept by
sending its output to the file, never retyped. A file's fingerprint is its SHA-256 in
hexadecimal (`sha256sum`). A sitting's id is
`s` and the UTC time it opened in digits, `date -u +s%Y%m%d%H%M`. The kinds of helper are
defined under the plugin's `agents/`: `clean-reader`, `fetcher`, `recorder`, `reviewer`,
`grader`, `checker`, `comparer`, `ai-recorder` and `coordinator`, with `interviewer` the kind of
the speaking session. A clean turn is no helper and no kind: it is a run of its own, under
**The line in the AI's graph**. No
helper is started that is not one of them for work a kind carries: the guard on the notebook
knows these kinds and no other.

## What the sitting serves

This skill states no goal of its own. The sitting serves that portion of the principal's rule of
life that can be delegated to the AI, as the notebook states it. The AI's graph is built by a
line that arrives at the principle by which the delegated actions are carried out (**The line in
the AI's graph**). This skill is meant to be a projection of the AI's graph: each of its rules
following from an answer there, and citing it. Today it is not one. Most of it was built
straight from the principal's words, as a stopgap, before the AI's graph held answers that
cover it. A part of it is rebuilt when the AI's graph comes to cover that part and would build
it differently; until then the part stands as built, and is read as the principal's words and
not as the AI's answers. How the AI's graph realizes the user's is not fixed here.

**Observations.** What follows is mechanism, and may change. Three things are observed: a
prediction of the principal that fails; an override or a deferral of the action ranked first; and
an action or a sitting not taken up. Each is an observation and never a verdict. Every
observation leads to a tracked action, in *Opened*, a divergence note or a job, or to a stated
reason why none is owed. A count is read, and never driven.

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

Where `.principal/notebook.json` names no `board`, stop and say so: this session has no tool that
publishes one. Where it names no `page`, the sitting runs without one and says so (**The page**).

## Ground rules

1. **One session speaks.** It is the one running this entry point. Run the confined way, it is
   started in the background by name as the interviewer kind, and the principal attaches to it:

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
   recorder, the interviewer included; the tool list does not. Run the open way, nothing refuses
   it, and this text alone holds it (**Before anything**).
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
   principal as the next action, save an office item the Rule gives the session to run
   (procedure 3, rule 7), whose grant is the Rule written at the principal's word, in one of the four kinds the round names (procedure 3, rule 6):
   an act to ask is a `question`, an act to do or to observe a `work`, and a grant a `review`;
   an `office` is the Rule's and no act of the speaker's. Only a question of principle is
   counted: the principal sets how many the sitting may spend when it opens, and the number set
   and the number spent stand at the head of the line doc. An office item, a review and a work
   action are not counted. To observe is to collect what is the case, by the principal or by a
   helper,
   and what was observed is recorded where the project keeps such things, a divergence note
   (`/principal:dictate`, **No action is taken in a dictation**) or the project's own
   repository, and never on the board.
5. **A share is computed; an act's weight is judgment.** `tools/shares.py` computes the share of
   the root that a question carries, and with `--price` the sum over questions somebody named.
   Which questions an act serves or releases is the speaker's reading, and so is every order
   among acts beyond the shares of those questions, how likely an act is to help, and what it
   costs: each is said to be judgment where it is said. Before an act is put, what the
   principal is expected to choose is sealed (procedure 3), and compared after: a different
   choice is a failed prediction like any other, and an override of the action ranked first
   (procedure 3, rule 5).
6. **What is unsure in the ranking is a question.** A share that seems wrong, a pressure that
   seems missing, an act whose place in the lineage is unclear, is put to the principal like any
   other question, and is not settled by the speaker.
7. **Tiers.** Every helper the speaker starts is started with a model named for the job, never
   left to inherit: a kind's by its definition, any other by the speaker in the call that starts
   it. Lookups and mechanical checks go to the smallest tier that can do them. A helper is
   started at the setting its definition names. A job's `tier` is the
   board's word and names no model: it is the one the table below gives its kind, and at most two
   jobs of tier `full` are claimed at once. Nothing reads a tier but the cap, the brief and the
   reader of the table: two kinds of one tier may run at different settings, and the setting is
   always the definition's. A kind the board knows and the table does not name
   (`state`, `remedy`, `line`) has no helper defined for it, and no job of it
   is added: the work is said to the principal with the weighing of a helper for it, what it
   must read, what it must not, and whether a defined kind's tools would keep it clean, and it
   is carried as an open note of kind `change`.
8. **No sitting ends without residue, and none waits to.** A line of questions taken up opens
   further lines, and the sitting is an ongoing process: it takes up the lines the principal
   chooses from those proposed, and in doing so opens more, which are tracked and returned to.
   What an answer opens is a document of the page's collection `lines` at the step that opened
   it (**The open lines**), the one place it waits; it is also written in the line doc's
   *Opened* section, and at the batch point it goes to the notebook as a note opening with the
   word *open* on the tab it bears on, in a rows file like any other, and the item and the note
   each name the line's id. A line is never finished: it is in hand
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
| `turn` | `full` | none: the speaker, by `tools/clean_turn.py` | `line`: the question's directory, `$SCRATCH/lines/<line>/<n>` | `reply`: its `manifest.json`, `fingerprint` |
| `compare` | `full` | `comparer` | `notebook`, `index`: the line's index, `$SCRATCH/lines/<line>/index` | `reply`: the redraw signals and counts, `fingerprint` |
| `place` | `mid` | `ai-recorder` | `notebook`, `rows`: the rows file, `index`: the line's index, `$SCRATCH/lines/<line>/index` | `reply`: the recorder's report, `fingerprint` |

The coordinator runs every kind the table gives a helper, every `review` among them and every
`compare`, and passes over the rest; `probe`, `observe` and `turn` the speaker claims and marks done
itself.
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

## The page

The round is put on a page. Its address is the `page` key of `.principal/notebook.json`, beside
`board`. It is the plugin's `web/ordo.html`, published once as a private artifact with the `db`
and `user` capabilities and rules under which only its owner reads and writes,

```
{"db": {"rules": [{"path": "", "read": "owner", "write": "owner"}]}, "user": {}}
```

so that anyone else, or anyone signed out, sees it empty. It has three sections in a fixed
order, the action context, the next action and the helpers' action context, and above them a
bell notice while a rung bell's office has an item of the principal's unresolved; beside them
stands the context panel. The page is display only: it has no button and no input, its source
holds no data, and it writes nothing. It reads four documents of the collection `ordo` in its
store, and the speaker writes all four, the day's marks included.

On a wide screen the main column is on the left and the context panel on the right, kept in
view; on a phone the panel sits under the next action. The panel holds, in this order: "This
bell", the latest rung bell's name and time and its items still open or under way, the
principal's and those run by the session (marked so, and kept listed with their state once
resolved), "The office is complete." standing above them where no item is open or under way; "Next 48 hours", one timeline in time order under day
headings, of every bell still to ring in the next forty-eight hours and every event of
`ordo/agenda` not yet ended and starting within them, each tagged "Bell" or "Event", the next
bell the largest, tagged "Next bell", and an office item of a later bell never listed; and
last, when the calendar was read, or "No calendar has been read." where `ordo/agenda` is absent.
Below the panel, in the same column and kept in view with it, a second card holds only "Waiting,
in order (N)", the queue (rule 10), as a native details element closed by default, which the
page never opens or closes on a redraw.

Before any private data is written to the page's store in a sitting, where `ordo/current` does
not yet exist, as at the first sitting on a page, the speaker first `set`s it with `updated`
alone, which holds nothing private; then the speaker reads `ordo/current` with `ArtifactData` at
`as_level` `interact` and again at `admin`; where either read returns a document, the owner-only rule does not hold, and the sitting runs without a page
and says so. What is published is the page's source, which holds no data; the store is read
under the owner's rule alone, and this read is what tests it.

The speaker changes it by one small data write to the document `ordo/current`, with
`ArtifactData`, and never by republishing: a `set` of the whole document, pinned with
`if_version` to the version last read (the first `set`, of a document not yet there, without
it), when the action changes, so that nothing of the last one lingers, `next.deferred` aside
(rule 5); an `update` when one field alone changes, nested objects merging and lists replaced
whole. Each write sets `updated`, and the clock is read before it is stamped (procedure 3, rule
8). A refusal is read and the document read again, never forced. The bells and their office
items live in `ordo/rule`, which is the principal's private data: it is written only at the
principal's word, and never into this repository, a line doc, the board or anything published.
The day's marks live in `ordo/ticks-<day>`, which the speaker writes when the principal says in
the session what became of an item. The principal's calendar lives in `ordo/agenda`, which the
speaker writes at each sync, after reading the principal's calendar. A sync is an office item of
the Rule's with `by: "session"` at which the speaker reads the principal's calendar for the next
forty-eight hours and writes `ordo/agenda`. A speaker that holds no tool that reads the
principal's calendar, as the confined way's does not, writes no agenda and says so in the action
context, and the panel then says "No calendar has been read.".

Where `.principal/notebook.json` names no `page`, the sitting runs without one and says so: the
round is put in the session's own words, in the order the page would show it, the action
context among them, and there are no bells.

**`ordo/current`**, an invented example:

```json
{
  "context": {
    "heading": "Your answer, as read",
    "paragraphs": ["The plants are watered before the post is opened, every day."],
    "for": [{"who": "One party", "text": "What that party says for the answer."}],
    "against": [{"who": "Another party", "text": "What that party says against it."}],
    "prediction": {
      "predicted": "Watering waits until the post is opened.",
      "diverged": ["The answer put watering first."],
      "addressed": "A case on the clause about mornings, at the next batch point."
    },
    "notes": ["A quiet note."],
    "at": "2030-01-02T03:00:00Z",
    "log": [{"at": "2030-01-02T03:04:00Z",
             "paragraphs": ["An addition made after the first writing, before the next answer."]}]
  },
  "next": {
    "kind": "question",
    "line": "Line: mornings",
    "case": "A morning on which the post holds a bill due that day.",
    "prompt": "Is watering the plants still first?",
    "deferred": {"prompt": "Water the plants.", "reason": "Set aside for now: a passing feeling.",
                 "kind": "work", "line": "Line: mornings"}
  },
  "queue": [
    {"kind": "work", "prompt": "Water the plants."},
    {"kind": "review", "title": "Review the next rows"}
  ],
  "background": ["A helper is building a fix to the page."],
  "office_deferred": {"reason": "The letter first, for an hour.",
                      "since": "2030-01-02T08:20:00Z", "bell": "0800"},
  "updated": "2030-01-02T03:04:05Z"
}
```

- `context`, the action context: the last answer as the speaker read it, or the speaker's
  explanation, its answer to a question of the principal's, or its report of what was done, the
  brief and the close among them (rule 10); `heading`; `paragraphs`, that answer, explanation or
  report;
  `for` and `against`, lists of objects with `who`, the party and its registry status, and
  `text`, shown under "Tradition on the result" after
  the paragraphs and hidden where both are empty; `prediction`, with `predicted`, `diverged` and
  `addressed`, each a string or a list of strings, shown after the tradition as "Predicted",
  "Where the result diverged" and "How the gap is addressed", an empty part left out and "No
  prediction was sealed for this action." where all three are; `notes`, quiet lines; `at`, the
  ISO time the context was first written, shown as a quiet line "Written HH:MM" under the
  heading; and `log`, the records appended to it before the principal's next answer (rule 10),
  each `{at, paragraphs}`, `paragraphs` a string or a list of strings, drawn last, in the list's
  order, each after a divider labelled "Added HH:MM", with the date where it is not today, a
  record without paragraphs skipped. The page keeps that order, heading, "Written", paragraphs,
  tradition, prediction, notes and the records, whatever the data's. Without `context` the
  section is hidden.
  `prediction` never holds the prediction of the action now put, which stays sealed until its
  answer is in.
- `next`, the next action: `kind`, one of `question`, `office`, `work` and `review`, any other
  shown as `work`, every kind shown alike but for its pill; `line`; `case`; `prompt`, the one
  field the card needs, without which it says "No action set yet."; `how`, a quiet last line,
  never set for a question or a review (rule 1); and `deferred`, an object with `prompt`, `reason`,
  `kind` and `line`, the action ranked first and set aside (rule 5), shown in the card under "Deferred,
  still first by the measure" beside the revised choice, also while an office is put, under
  "After the office", and not at all where its `prompt` is empty; its `kind` falls to `work` as
  `next`'s does; and `recommendation`, a string or a list of strings, the speaker's recommendation,
  shown under "Recommendation" after the prompt and only where set: every review
  of mechanism carries it here, its own field and never in the case, and a question, or a review
  that states or changes a principle, never carries one, the page showing none on a `question`.
  There is no checklist: a review is a `prompt` like a question's, answered in the
  session.
- `queue`, the actions after `next`, in order (rule 10), a projection of the open documents of
  the collection `lines` by their `rank` (**The open lines**): each a whole action with the
  fields of `next`, or a placeholder with `kind` and `title`, listed by its kind and its `title`, or its
  `prompt` where it has no title, as "Waiting, in order (N)" in its own card below the context
  panel, a details element closed by default; an entry with neither is dropped, and an empty
  `queue` hides the card. The page never moves the queue: when `next` is
  answered or done, the speaker writes the first entry as `next`, a placeholder made a whole
  action, and the rest as `queue`.
- `office_deferred`, the office set aside (rule 7): an object with `reason`; `since`, an ISO
  time; and `bell`, the base `time` of the bell set aside without its colon, `HHMM`, a
  `time_by_day` move not changing it. While `bell` names the latest rung bell, `since` is at or
  after the moment that bell rang on the current Rule day, and that bell still has an item of the
  principal's unresolved, the card shows `next` exactly as when no
  office is unresolved, and under its prompt a quiet block, "Office set aside, still due",
  lists the items left, a taken one marked under way, with the bell, the time it was set aside
  and the `reason`; a deferred action, where one is set, shows under it too. The notice stays,
  saying the office is set aside, and the panel's "This bell" is unchanged. Once a later bell
  rings, or every item of the principal's in that bell is resolved, the field is ignored, and so
  it is where `since` does not parse or is before that bell rang today, as on a later day; the
  speaker removes it in its first write after a later bell has rung or the Rule's day has turned.
- `background`, the helpers' action context: strings, what the helpers are doing, hidden where
  empty.
- `updated`: the time of the write, ISO 8601 in UTC, shown as the hour and minute it was made.

**`ordo/rule`**, the principal's. An invented example:

```json
{
  "day_start": "05:00",
  "days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
  "bells": [
    {"time": "08:00", "name": "Morning",
     "office": ["Water the plants", {"label": "Feed the goldfish", "ask": true},
                {"label": "Copy out the seed list", "by": "session"}]},
    {"time": "21:00", "time_by_day": {"sat": "22:30"}, "name": "Evening",
     "office": [{"label": "Put out the recycling", "days": ["thu"]},
                {"label": "Cover the seedlings", "off_from": "11-01", "off_to": "02-28"},
                {"label": "Wind the clock", "except_days": ["sat"]}]}
  ]
}
```

- `day_start`, `HH:MM`, `00:00` where missing: the Rule's day begins then. Before it, the day
  is the calendar day before, for the bells, every weekday filter, the off ranges and the
  marks' date; a bell whose time is before `day_start` rings after midnight, at the end of the
  Rule's day.
- `days`: the weekdays the Rule rings on, each a name in any case read by its first three
  letters or a number from 0 to 6, Sunday 0; every day where missing or empty.
- `bells`, each with `time`, `HH:MM`, two digits each, on a 24-hour clock in the viewer's
  local time, without
  which the bell is ignored, and which names it in the marks' keys; `time_by_day`, a weekday to
  `HH:MM`, moving the bell that day and not its keys; `name`; and `office`, a list of items, each
  a label or an object with `label`, without which it is dropped, `days` and `except_days`,
  weekdays it rings on or not, `off_from` and `off_to`, `MM-DD`, both needed, an inclusive
  range of the year
  it is off, wrapping the new year where `off_from` is the later, and `ask`, `true` where the
  page cannot tell whether the item is due, so that the speaker asks, the question put on the page
  as an action (rule 10), and may mark it not due;
  and `by`, `"session"` where the item is the session's to run and not the principal's to
  report, any other value ignored. Such an item is never the principal's next action: it is
  left out of the notice, its counts, the card and "Then:", and shown only in the context
  panel, marked as run by the session with its state. The speaker itself runs
  it, with its own tools, when the timing is right, puts any question it raises on the page as an
  action (rule 10), and writes its mark, `taken` when it starts and the bare time when it is done;
  the principal never reports it.
  An item filtered out for the day is neither shown nor counted.
- The page finds the latest bell rung on the Rule's day. While that bell has an item of the
  principal's open or taken, the notice stands, saying the office is not yet taken up, is under
  way, or how many items are left, with the next bell under it; the next action is the first
  such item taken, else the first open one, "Under way since" the time it was taken where it
  was, the others after "Then:", those resolved listed as done, overruled or not due, a line
  asking the principal to tell the session when it is done, and the speaker's own `next` in a
  quiet "After the office" block, with its deferred action under it where one is set. While
  `office_deferred` names that bell and was set after it rang today, `next` shows instead, with
  the office under it as set aside.
  Once every item of the principal's is resolved the notice goes and `next` shows, even while
  items run by the session remain. An earlier bell's unresolved items are not shown. It reads
  the clock again every thirty seconds.

**`ordo/ticks-<day>`**, the marks: `<day>` the Rule's day as `YYYY-MM-DD`, the local date moved
back a day before `day_start`. It is a flat map from an office item's key to a value. The key is
`bell-<HHMM>-<slug>`, the bell's base `time` without its colon and the item's label as a slug:
the label in lower case, every run of characters but `a-z` and `0-9` made one `-`, trimmed of `-`
and cut to sixty characters, `item` where nothing is left; a label repeated in one bell's office
takes `-2`, `-3` and so on, counted over the whole list with the items filtered out, so that a
key does not shift from day to day. A label changed is a key changed. A value is `null`, or no
key, open; `taken <ISO time>`, under way since then and still unresolved; an ISO time alone,
done, any other value being read as open; `overruled <ISO time>`, overruled; and `notdue <ISO
time>`, not due today. An item is
unresolved while open or taken. The day's first mark is a `set` of the whole document, which
does not yet exist; each later one an `update` of its key. A measured value the principal
reports with an item, a weight for example, is kept as a plain field of the same document
beside the marks, under a key that does not begin with `bell-`; the page reads only the items'
keys and passes it by. An invented example:

```json
{"bell-0800-water-the-plants": "2030-01-02T08:10:00.000Z",
 "water_used": "2 l",
 "bell-2100-wind-the-clock": "overruled 2030-01-02T21:05:00.000Z",
 "bell-2100-cover-the-seedlings": "taken 2030-01-02T21:12:00.000Z"}
```

**`ordo/agenda`**, the principal's calendar for the panel, written whole by the speaker at each
sync after reading the principal's calendar, with the events of at least the next forty-eight
hours. It is the principal's private data like `ordo/rule`. An invented example:

```json
{"events": [{"start": "2030-01-02T14:00:00Z", "end": "2030-01-02T15:00:00Z",
             "title": "An example visit"},
            {"start": "2030-01-03", "end": "2030-01-04", "title": "An example fair",
             "all_day": true}],
 "fetched": "2030-01-02T09:12:00Z"}
```

- `events`, each with `start` and `end`, ISO times with an offset, or for an `all_day` event a
  bare date read as local midnight, `end` exclusive; `title`, shown as written; and `all_day`,
  `true` for an event shown as "All day". An event without a valid `start` or a `title` is
  dropped, and a missing `end` counts as the start.
- `fetched`, when the calendar was read, shown as the panel's last line.

At each turn the speaker reads and writes (rule 7): the Rule's day from the local clock, then
`ordo/rule` and `ordo/ticks-<that day>` by `get`; the bells rung so far, each at its time for
that weekday; their items that apply that day, and each item's state from its key. While the
latest bell has an item of the principal's unresolved, the page is putting the office and not
`next`, an item taken before any open one, until each of the principal's is done, overruled or
not due, or the principal sets the office aside; items run by the session never hold the card. When the
principal says in the session that an item is under way, done, not now, not due, or open again,
the speaker reads the clock and writes `taken`, the bare time, `overruled`, `notdue` or `null`.
An item overruled or marked not due is the principal's word for the day, and is not put again.
An earlier bell's unresolved items, set aside or not, the page does not show on the card: the
speaker lists each in the action context as still due from that bell until the principal says
done, overruled or not due for it, and lets none lapse without that word. Items with `by:
"session"` the speaker runs itself, with its own tools, when the timing is right, and marks. When
the principal sets the office aside, the speaker writes `office_deferred`, only at the principal's
word; when the principal takes it up again, the speaker removes it, and it removes it too in its
first write after a later bell has rung or the Rule's day has turned. At each sync the speaker
reads the principal's calendar and `set`s `ordo/agenda` whole, with `fetched`.

## The open lines

Every open line still to be put to the principal is one document of the page's database, in the
collection `lines`, beside `ordo`, and nothing waits anywhere else: not in the speaker's context,
not only in the line doc, not only as a note in the notebook. An item of the line doc's *Opened*
section and an open note on a tab each name the line's id and point to it; neither is where the
line waits. `ordo/current.queue` is a projection of the open documents of `lines`, in the order of
their `rank`, for the page to draw, and `ordo/current.next` is the one now put; the page reads
`ordo` alone, and never `lines`. The speaker starts every sitting, and resumes after its context
is compacted, by reading `ordo/current` and the open documents of `lines` with `ArtifactData`,
and trusts them over anything it remembers: where they differ, the store stands, and the
difference is said in the action context. A sitting that ends abnormally leaves its lines where
the next one finds them.

A line's document is written with `ArtifactData` like `ordo/current`: a `set` when it is opened,
then an `update` of the fields that change, each pinned with `if_version` to the version last
read, and each stamping `touched_at` from the clock. Its fields, an invented example after them:

- `id`, the document's id: `l` and the UTC time it was opened in digits, as a sitting's id is
  made, with a number after a hyphen where two open in one minute.
- `title`, a few words the queue shows.
- `kind`: `question`, `review` or `work`, as the page's kinds.
- `state`: `open`, waiting to be put; `put`, now `ordo/current.next`; `answered`, answered by the
  principal, and what the answer opened made lines of their own; `closed`; `merged`, its ask
  carried on by another line, which `answered_by` names; `dropped`, by the principal.
- `ask`: `{case, prompt, recommendation}`, the action as the page would put it, `recommendation`
  only where rule 6 of the round gives one.
- `why`: what raised it, and what would bring it back if it rests.
- `source`: where it was opened: the sitting, the round, and the answer, job or note that
  opened it.
- `anchors`: the sentences of the user's record it bears on, each `{tab, block, fingerprint,
  words}`.
- `seal`: what was sealed for it and when, a fingerprint and a time, never the sealed text.
- `parent` and `children`: line ids.
- `answered_by`: what closed it: the answer's file and round, the principal's later sentence
  quoted, or the line a merged one is carried on by.
- `rank`: its place in the order; the queue is the open documents by `rank`, lowest first.
- `opened_at` and `touched_at`: ISO times, read from the clock.
- `review_count`: how many times it has been put to the principal.
- `origin`: who opened it: `principal`, `speaker`, `ai` for a drawer turn, or a helper's kind.

```json
{"id": "l203001020304", "title": "Mornings before the post",
 "kind": "question", "state": "open",
 "ask": {"case": "A morning on which the post holds a bill due that day.",
         "prompt": "Is watering the plants still first?", "recommendation": null},
 "why": "The answer on mornings left the bill's day open; it returns at the next sitting.",
 "source": "s203001020300, round 2, answers/2.md",
 "anchors": [{"tab": "mornings", "block": "b12", "fingerprint": "<the block's h>",
              "words": "The plants are watered before the post is opened."}],
 "seal": null, "parent": null, "children": [], "answered_by": null, "rank": 3,
 "opened_at": "2030-01-02T03:04:00Z", "touched_at": "2030-01-02T03:04:00Z",
 "review_count": 0, "origin": "speaker"}
```

A line is closed only by the principal's answer to it; by the principal's own later sentence
settling it in terms, the line then closed with that sentence quoted in `answered_by` and listed
in the action context, so that the principal can reopen it; or by the principal dropping it.
Never because a reader predicts the answer, the speaker or a clean reader among them. The
collection is the principal's private data, like `ordo/rule`: it is never written into this
repository, a line doc's words, the board or anything published. No tool yet reads, orders or
sweeps it (**Attenuation**).

## Procedure

**1 — Read.** Read `ordo/current` and the open documents of `lines` first (**The open
lines**). Then export the board with `ArtifactData`: a `list` of `jobs`, paged with
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

**2 — The brief.** The brief is a report, written on the page, in the action context (rule 10),
and not in the session's text. In this order: what was done and what failed since the last sitting, by job
and kind, from `status`; what was observed, from the divergence listing; what waits on the
principal, each `waiting` job with what it releases; three numbers, how many open notes the last
sitting took off because their line stands on the tab, how many it added, and how many stand
open now, the first two from the count its line doc kept at its close and the third from this
opening's listing, the third said plainly to be a count that is not driven to nothing; the acts
that come first by the shares of what they serve, each with its reason, the reading marked as
judgment, as an order and not yet a proposal; and the question of how many questions of
principle the principal will spend this sitting, put on the page as the sitting's first action,
a `review`, like any other. Nothing else is asked until that number is set; the choice of a line
from the acts that come first is then put on the page as the next action.

**3 — One action at a time: the round.** Each turn puts one next action, on the page where one
is named, under ten rules. Rules 1 to 4 are a question's, and a review's as rule 6 says; 5 to 10
bind every action.

1. **One question at a time, put as one concrete case.** It rests on what the notebook states
   (`/principal:dictate`, **The fidelity round** for how a question is drawn, and **A case rests
   on the record** for its premises). Nothing accompanies it: no recommendation, no tradition
   on the question being put, no list of what is sealed, no line telling the principal how to
   answer. The tradition on the last answer, already given, stands in the action context above
   it (rule 4): it is on that answer, never on the question now put. It is counted as it is
   put. A question the principal does not understand is put again, plainer, as one case; it is
   never withdrawn and decided for the principal. No question is left unasked because readers
   agree on its answer.
2. **Seals come before it.** The record's prediction is sealed by a clean reader: write the
   question to `$SCRATCH/questions/<n>.md`, `<n>` its number in the sitting, and add a `seal`
   job for it (step 6); start the coordinator, so that a clean reader draws the record's answer
   as the clean reader's definition says. This session does not read the sealed file until the
   answer is in. The aporia the line is pursuing, with what each possible answer will be tested
   against, is sealed by the speaker in a file of its own in `$SCRATCH/sealed/`, and carried
   from question to question on that line: each question on the line seals it again as it then
   stands. What the speaker remembers of the line that the notebook does not carry is sealed
   apart, by the speaker, in a file of its own there too. Only the fingerprints go in the line
   doc, the seal's in its Fidelity rounds section, `- F1. Sealed <fingerprint>.`, and the
   aporia's in its Aporiai section. The line doc's address is never an input of a seal job.
   Seals exist mechanically and are not listed to the principal.
3. **The question's file holds no answer.** `$SCRATCH/questions/<n>.md` holds the question
   and its case, and nothing of the sitting: no answer and no admission of the principal's,
   since a clean reader may open any question of the sitting. What the principal admits is
   recorded in the line's record, the line doc, restated and never word for word, and goes to
   the notebook through the recorder at the batch point. The file tells the reader that where
   the notebook cannot decide the case, the prediction is that the principal declines to pick
   and says what is missing.
4. **After the answer, in this order on the page.** First the answer as the speaker read it, a
   restatement and never word for word; then tradition for and against the answer that was
   given, each party with its registry status; then the predicted result, in three parts: what
   was predicted, where the result diverged, and how or whether that gap is addressed. The
   principal may revise the answer after reading the tradition; unrevised when the next answer
   comes, it stands, and a revision is written over the answer's file and graded again.
   Tradition readings go to the notebook only with the principal's approval. Behind the page:
   read the sealed file and state it in the line doc; write the principal's answer to
   `$SCRATCH/answers/<n>.md` as the admission the line doc records, never word for word, and add
   a `grade` job over the sealed file and that answer. Class a failure as **The fidelity round**
   classes it, and draft the remedy for the batch point. Once the remedy is written (step 4), a
   fresh `seal` job with a new row in its id draws the prediction again, and a `grade` job over
   its result and the same answer file grades it; the outcome is written in the line doc as
   `Redrawn: …`. State the aporia too, with what the answer did to it, and carry what is open in
   it to the next question on the line. What this opened: each further line the answer opened,
   as a document of `lines` and in *Opened*, with what raised it and what would bring it back
   (ground rule 8, **The open lines**).
5. **The principal may always override the action ranked first**: by a lasting change of a
   share, by a further observation to be weighed, or by a transient feeling. An override is an
   observation of a gap, never a verdict: it is recorded as **Observations** says, a lasting change of a
   share goes to the batch point as rows, and a further observation is weighed and recorded
   where ground rule 4 says. When a transient feeling moves the choice, the page keeps showing
   the deferred action beside the revised one, as `next.deferred`: it is carried in every
   whole-document `set` of `ordo/current` until it is done or the principal drops it.
6. **The next action is one of four kinds: question, office, work, review.** A `question` is
   put by rules 1 to 4; an `office` is an item of a bell (rule 7); a `work` is an act to do or to
   observe; and a review is put exactly as a question is, one at a time, a case and a question
   on the page, answered in the session. A review differs from a question in three things only:
   a review of mechanism carries the speaker's recommendation, in `next.recommendation`, its own
   field and never in the case, and a review that states or changes a principle, a grant or a
   row stating a principle among them, is put with no recommendation, as a question is, and the
   page shows none; it carries no tradition; and a prediction is sealed
   before every review as well, by the speaker itself, in
   `$SCRATCH/sealed/`, and the file says who predicted. The grants and the rows of a batch point
   are put as reviews (step 4). There are no checklists. An act of another kind than a question
   or a review is put with what it serves, sealed the same way as a question, and the
   principal's choice is graded against the sealed one. What is chosen is then carried as its
   kind asks: an act to observe is an `observe` job, which the speaker claims under the
   sitting's id and carries out itself with its own tools, starting no helper for it, or the
   principal's own observation, recorded where ground rule 4 says; an act to do that a rows file
   can carry goes to the batch point, and one it cannot goes by rule 9, or by
   `/principal:dictate` or `/principal:bootstrap`, named to the principal as an open note of kind
   `change`; a grant is written at the batch point as a case on the tab of the clause it bears
   on. Each ends with what it opened.
7. **Bells.** An unresolved office of the principal's shows first unless the principal has set
   it aside; items run by the session never hold the card. The page shows a rung bell as a notice
   and makes that bell's office items of the principal's the next action, one at a time, until
   each of the principal's is done, overruled or marked not due, or the principal sets the
   office aside; only then does the speaker's own next action show, and the rest of the time is
   a work block. Between open and
   resolved an item may be taken up: the principal says so in the session, the speaker marks it
   taken, and it stays the next action as under way until it is done, overruled or marked not
   due; among a bell's unresolved items the page shows a taken one first, else the first open
   one. A `work` action has no mark: it stays `next` in `ordo/current` until the speaker changes
   it on the principal's word. The page writes nothing: the principal acknowledges each item and
   each action in the session, and the speaker writes an item's mark, or `ordo/current` for an
   action. The page always shows the next
   bell, in the notice while an office is open and always in the context panel, on one timeline
   with the bells and the principal's calendar events of the next forty-eight hours, beside the
   bell's remaining items and the waiting list. The
   speaker reads the day's marks at each turn (**The page**); an overruled office item is an
   observation like any other override. An office set aside, or left unresolved, when a later bell
   rings does not vanish: the page shows only the latest bell's office on the card, and the
   speaker lists those items in the action context as still due from the earlier bell until the
   principal says done, overruled or not due for each. An office item marked `by: "session"` is
   the speaker's, not the principal's: the speaker itself runs it, with its own tools, when the
   timing is right, puts any question it raises on the page as an action, and writes its mark;
   the principal never reports it, and it never holds back the speaker's own next action. It is
   the one act not put to the principal: the Rule, written at the principal's word, is the
   grant. Its mark is its record; one the speaker cannot run, or that fails, stays open, and the
   speaker says so in the action context and puts it to the principal as an action. The principal may set the rung bell's
   remaining office aside for a while and take the session's work first, a transient action
   divergence: the speaker writes `office_deferred` only at the principal's word, records it as
   an observation of a gap, as **Observations** says, and never a verdict, carries it in every
   whole-document `set` of `ordo/current`, and clears it when the principal takes the office up
   again; while it stands the page shows the speaker's next action with the office under it, still
   due. The page counts it only where `since` is at or after the moment the named bell rang in the
   current Rule day, and the speaker removes it in its first write after a later bell has rung or
   the Rule's day has turned. A measured value the principal reports with an item is kept as
   a plain field in the day's marks document beside the marks.
8. **Every time the speaker stamps is read from the clock, never typed**: `date -u
   +%Y-%m-%dT%H:%M:%SZ` for the board's `--now`, the page's `updated`, the time in a mark,
   `office_deferred`'s `since`, `ordo/agenda`'s `fetched`, `context.at` and each `at` of
   `context.log`, and a line's `opened_at` and `touched_at`,
   `date -u +s%Y%m%d%H%M` for a sitting's id, and the local `date`, in the zone the page is
   viewed in, for the Rule's day.
9. **The speaker, at the full tier, writes no code, page or tooling itself.** Such work is
   briefed to a helper of the mid tier and reviewed adversarially by a helper of the full tier;
   the judge is never the tier judged. Run the open way, the speaker briefs both directly, with
   what each must read and must not, and puts what they hand back to the principal as a review;
   run the confined way, it can start neither, and the work is named to the principal as an
   open note of kind `change`.
10. **Every ask of the principal is an action on the page, in order.** The speaker never leaves
    an ask only in the session's text: what it writes in the session is short and points to the
    page. Every explanation, every answer to a question of the principal's, and every report of
    what was done goes in the page's action context, `context`, as its `heading` and
    `paragraphs`; the session's own text is one or two lines saying the page changed, and never
    repeats what the page says; nothing the principal must decide appears only in the session's
    text. Context above a question of principle still carries no recommendation (rule 1). The
    action context is append-only within a round: once it is written for a round, nothing in it
    is changed until the principal answers; an addition before then is appended to the same
    context as a record carrying its time, in `context.log`, each record `{at, paragraphs}`, the
    first writing's time being `context.at`, and is never kept as a separate log beside the
    context. After the principal answers, the context is written anew. The asks still pending are kept on the page as a queue the principal can see, in the
    order they will be put, each a further action or a placeholder with a kind and a title,
    drawn from the open documents of `lines` (**The open lines**), which is where each waits.

**4 — The batch point.** The rows are shown to the principal in words first, put as reviews
(rule 6 of procedure 3), one at a time: the sentences for
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
`$SCRATCH/coordinator/replies/<job id>`, since a failed job carries no result, tells the principal on the page, in the action context, which link failed and why in a sentence, and
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

**5 — The AI's own turns.** A question for the AI's own record is a `turn` job, its `line` the
question's directory (**The line in the AI's graph**). One drafted on the user's side is held at
once with `wait`, `tools/board.py wait $SCRATCH/speaker/board <id> --versions
$SCRATCH/speaker/versions.json --now <time> --out $SCRATCH/speaker/out`, until the principal
approves it on the page, shown word for word as its own action (**The line in the AI's
graph**, rule 3); then it is queued again with `resume`, `tools/board.py resume
$SCRATCH/speaker/board <id> --versions $SCRATCH/speaker/versions.json --now <time> --out
$SCRATCH/speaker/out`. One a drawer turn raised needs no approval and is queued as it is added.
The speaker claims a `turn` job under the sitting's id and runs it itself with
`tools/clean_turn.py`, starting no helper for it, and marks it done with its manifest as the
`reply`. No other session puts a question to the AI's record.

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
`$SCRATCH/coordinator/` export. The coordinator is the only helper this session starts for work
a kind carries; every such piece of work is a job on the board, every `review` included. Work no
kind carries is rule 9's (procedure 3), and only the open way starts a helper for it.

**7 — Closing.** The close is a batch point like the others. Run `status` again and say on the page, in the action
context, what stands open: jobs not done, failures by kind, what waits on the principal, the questions spent
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

## The line in the AI's graph

The AI's own record is a graph of the AI's answers, in its own words. Its tabs stand under a root
of their own in the notebook, and the key `ai_root` of `.principal/notebook.json` lists their node
ids, the root's first; until the root is made the key is unset, and the guard on the notebook
refuses the `ai-recorder` every write. An answer of the AI's given before the root, past held on
a tab wherever it stands, is the AI's too. A line is a run of questions put to that record. Each
is put in a clean turn: a run of the harness of its own, started by `tools/clean_turn.py` in an
empty directory with no tools, settings, memory or rules file, whose context holds the AI's own
earlier answers, as `tools/packet.py` writes them, and one question, and nothing of the user's
record. A clean turn is never a helper of this session: a helper started from a session carries
that session's memory, rules file, git status and skills. Before the sitting's first clean turn
the speaker runs `tools/clean_turn.py probe`; where it exits other than 0 no line is drawn, and the
speaker says so in the action context.

Each line has a directory, `$SCRATCH/lines/<line>`, holding `requirement`, the names of the tabs
of the user's record the line is drawn for, one name a line; one directory for each question, in
the order they are put, `$SCRATCH/lines/<line>/<n>`, `<n>` counted from 1; one for each drawer
turn, `$SCRATCH/lines/<line>/drawn-<n>`; and `index`, every file of the line by its absolute
path, one a line, which the speaker writes again, with `find $SCRATCH/lines/<line> -type f !
-name index | sort > $SCRATCH/lines/<line>/index`, before it adds a `compare` or a `place` job,
since the helpers of those kinds cannot list a directory. A question's directory holds its
packet, `tools/packet.py $SCRATCH/graph.json --under <id> --line $SCRATCH/lines/<line> -o
$SCRATCH/lines/<line>/<n>/packet.md`, with the fingerprint the tool writes beside it; its words,
`question.md`, written with the Write tool; its leak record and its origin; and its draws, in
`draws/`. The packet holds the AI's answers of the tab `<id>` it stands under and above it, then
the line's own earlier questions and answers, in the order they were put, each answer under the
question it was given to, marked `<<< question >>>` and `<<< answer >>>`: a question of how
reaches the answer of why above it on the line, however many questions deep. Several draws are
kept for each question and none is chosen by what it says, so the rule is fixed in advance: the
first draw a question's manifest lists as kept is the answer of record, the one every later
packet carries; the others are the evidence of whether that answer is stable, read by the
comparing run, and never carried. Where the line stands under no tab of the AI's yet, the packet
is `tools/packet.py $SCRATCH/graph.json --line $SCRATCH/lines/<line> -o
$SCRATCH/lines/<line>/<n>/packet.md`, the line's alone, which is also the back-brief's. A drawer
turn's packet is cut by the same line as the question it draws under, into
`$SCRATCH/lines/<line>/drawn-<n>/packet.md`. The packet holds no hinge, glossary, note, case,
application line or anything else written on the user's side; the tool refuses a question of
the graph the AI does not answer, or that holds no answer past held, a graph on which
`only-ai-put` or `state-order` fails, a gap in the line, a draw that does not match its manifest
or its question, and a question or an answer holding `<<<` or `>>>`, which no text may forge.

1. **The order.** The principal's requirement is recorded on the user's side first, on the tab it
   bears on, at a batch point. Then a line is drawn in the AI's graph. Then the comparing run, a
   `compare` job, reads the line against the user's record. Then the build, whose brief cites the
   AI's answers by their opening words and never the principal's requirement. Then the build is
   checked against the record, by a `compare` job over the line with what was built. Nothing is
   built straight from the principal's words unless the principal asks for that explicitly, once,
   as an action on the page, for that one build.
2. **Intention is carried by the line.** Every line opens at the purpose: what the thing is for,
   and what it must never do. A question of how stands only beneath an answer of why. Each answer
   names the answers it rests on, on its `Rests on:` line. Before any build a back-brief is
   drawn: a clean turn over the line alone restates what the thing is for, what it must never do
   and what failing would look like, and the comparing run reads it against the user's record. A
   difference of intention is repaired by drawing again higher up, never by correcting the
   mechanism. Some cases are held back from every question, kept on the user's side, and used
   only to test that the design generalizes; one of them is a case where the letter of the
   mechanism and its purpose part.
3. **Two kinds of question.** A question drafted on the user's side, the opening question, a
   case's situation or a statement of the principal's position, is checked first, with
   `tools/public.py question $SCRATCH/graph.json $SCRATCH/lines/<line>/<n>/question.md --record
   $SCRATCH/lines/<line>/<n>/leak.json`, which refuses a question that repeats masked words or
   breaks the notebook's rule for naming the user, saying what it found; its presuppositions
   are listed on the user's side, in the line doc and at the batch point on the tab it bears on.
   Each such question is then its own action on the page, a `review` whose prompt is the
   question word for word, for the principal to approve or revise; it is put to the AI only on
   that approval. A revision is written over `question.md` and checked again before it is shown
   again, and only the text the principal approved is put. On that approval the speaker writes
   `$SCRATCH/lines/<line>/<n>/approval.json` with the Write tool, `{"sha256": <the fingerprint
   of the question file as approved>, "approved": <the time, from the clock>}`, and the clean
   turn refuses any other text. A question the AI's own record raises comes verbatim from a
   drawer turn, `tools/clean_turn.py draw --packet $SCRATCH/lines/<line>/drawn-<n>/packet.md
   --out $SCRATCH/lines/<line>/drawn-<n>`, and needs no approval; it is still checked by
   `public.py question`, and the clean turn refuses it unless it stands as a line of that
   drawer's run. Case situations go to the AI's record as questions; verdicts and reasons stay
   on the user's side, with the comparing run. The clean turn refuses a question in which a
   token opens with `@`, which the harness would expand into a file of the machine, and one
   that opens with `/` or `!`; every prompt it sends opens with a line of its own.
4. **Draws.** Each question is drawn several times, `tools/clean_turn.py answer --packet
   $SCRATCH/lines/<line>/<n>/packet.md --question $SCRATCH/lines/<line>/<n>/question.md --out
   $SCRATCH/lines/<line>/<n>/draws --approval $SCRATCH/lines/<line>/<n>/approval.json --leak
   $SCRATCH/lines/<line>/<n>/leak.json`, three by default, or with `--drawn-from` the drawer's
   `draw-1.json` in place of `--approval`. All are kept, none is chosen by what it says, and
   the first kept is the answer of record (above). Where they part in what they would do, that
   is the finding, and the question is drawn higher. A question whose draws were all refused is
   put again under a new number, or dropped, before the line goes on: the packet refuses a gap.
5. **On a divergence.** The comparing run hands back only the redraw signal, the opening words of
   the AI's answer under which the divergence sits, and the speaker passes those words and
   nothing else of its reply to the drawer, `--from "<opening words>"`, over a packet that
   holds that answer, the graph's or the line's; the drawer refuses words that do not open
   exactly one answer of the packet, or hold fewer than four words. After two redraws of one
   divergence, the default, either the principal states a position, which stands in the AI's
   record in the principal's words by way of a further approved question, or the line cannot be
   built, and that is put to the principal as one action: the case, what the AI's record
   reached, where it parts, and four choices, a further question, a stated position, a build
   straight from the notebook as a stopgap, or the principal does it.
6. **A budget of clean turns.** A line spends at most twenty-four clean turns, the default, each
   draw, drawer turn and back-brief one; the principal may set another number when the line
   opens. The speaker reports in the action context, at each batch point and when the line rests,
   the turns spent against the budget and the cost the draws recorded. A line that reaches its
   budget stops there, and is put to the principal as the one action of rule 5.
7. **What is acted on is the AI's action.** What is acted on from the AI's record is recorded on
   the page, in the action context, as the AI's action, naming the answers it rests on by their
   opening words, so that the principal is prompted to review it.
8. **Four signals before a constraint binds.** Before the speaker treats any constraint as
   binding it tests four signals and says which apply: marked stale by a later note; a mechanism
   standing as a principle, its source an application line, a skill or a helper's definition,
   this one among them; its price, the divergences recorded on it, beside the share it carries;
   and unjustified, no edge to a principle nearer the root.
9. **What is recorded.** The draws are placed in the AI's record by a `place` job, the
   `ai-recorder` sending a rows file of inserts whose texts are the draws' answers word for word,
   only once a tool prints such rows; the comparing run's lines go on the user's side. Until a
   tool prints the insert of an answer, the draws stay in the line's directory and the place is
   carried as an open note of kind `change`.

## Attenuation

What no tool decides. Hold these by reading.

- **The speaker is not a clean context.** It has heard the principal, so the record's answer it
  would draw is not the record's, and agreement between readers is no evidence the record is
  right: two clean readers that draw the same answer have read the same words. The principal's
  answer is the test. A prediction the speaker seals before a review is the speaker's own, and
  its file says so.
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
- **In the open way this text alone keeps the speaker off the notebook.** The gates still bind
  every helper by its kind, and a helper that is no kind of this plugin is refused any write
  aimed at the notebook; but the session running this entry point is the main thread, and the
  guard gives it no opinion. A helper the speaker briefs by rule 9 is held off the notebook's
  connector by the guard and off nothing else, and a shell line of its that starts a session of
  its own starts a main thread no gate binds: its brief, and the review of its work by the full tier, are
  what hold it to the work.
- **A recorder's write may be refused by a permission check.** The harness may ask a permission
  for a helper's call that cannot see the principal's approval at the batch point, and refuse
  it. This is untested. Then the speaker puts it to the principal as an action on the page
  (rule 10), and the principal either allows the tool by a permission rule or has the rows
  written by `/principal:dictate`. The speaker never writes the notebook. Never work around a
  refusal.
- **The page shows what its documents hold, and was read as code.** Whether a rule of `owner`
  for reading is accepted at publishing is untested, and no viewer has yet shown the page drawn;
  whether a read comes back to its owner alone is read at each sitting before any private data
  is written (**The page**). The page writes nothing, so a mark the
  speaker does not write is never made; it re-reads the clock every thirty seconds, so a bell
  rings on it up to that late.

- **What holds a clean turn, and what only reading holds.** `tools/clean_turn.py` refuses a
  packet with no matching fingerprint file, a question whose leak record or origin is of
  another text, a leak record made over another graph than the packet's, a question, packet or
  redraw signal holding a token that opens with `@`, a question opening with `/` or `!` or
  holding a packet's mark, a run whose `init` shows more than the stated residue, a run that
  made other than one model turn, an answer holding the account's email address, its local part
  or the run's directory, a redraw signal that opens no one answer of the packet, and an out
  directory that already holds draws or is claimed; `tools/packet.py` refuses a question of the
  graph the AI does not answer or that holds no answer past held, a graph on which the checks of
  whose an answer is fail, a gap in the line and a draw that does not match its record. The
  records these checks read, the packet's fingerprint, the leak record, the approval and a
  drawer's record, are plain files: each binds a check to an exact text and catches drift, and
  none is a signature, so one written by hand with the right hash passes; what holds them is
  that only the tools write them, and the speaker writes an approval only at the principal's
  word. What no tool holds: what a question presupposes, and a fact of the user's life said in
  new words, are read; and the stated residue, the lines the harness adds to every run's system
  prompt and first message (a billing and an identity line, the account's email address, the
  run's directory and whether it is a repository, the platform, the shell, the OS version, the
  model's name and id, the knowledge cutoff and the date), is in every turn, since no documented
  way drops them without an API key.
- **"None chosen" is per directory.** The tool keeps every draw it writes into one out directory
  and chooses none; a second `answer` of the same question into another directory, or a
  directory removed, is seen by no tool, and the answer of record is the first kept draw of the
  directory the line holds. The speaker draws each question once, into its own `draws/`.
- **The sides of the notebook are held by node, not by block.** The guard holds the
  `ai-recorder` to the tabs `ai_root` lists, and refuses it every write while the key is unset,
  and holds the `comparer` to every other tab, the tab given by a plain id and compared in lower
  case; each only by inserts of markdown beside one block named by id, or at the tab's end, in a
  call that names nothing else. While the key is unset the guard lets the comparer insert on any
  tab, and its definition alone keeps it off a tab that holds an answer of the AI's. A tab under
  the root that the key does not list is the user's to the guard; a block id inside a list or a
  table is read, not checked; and on a tab of the user's that still holds an answer of the AI's
  from before the root, where the comparer's insert lands is read. That the `ai-recorder`'s
  texts are the draws word for word is its definition's check, and no gate's. No tool yet
  prints the insert of an answer, so no draw is placed (**The line in the AI's graph**, rule 9).
- **The open lines are held by reading.** That every open line is a document of `lines` and
  waits nowhere else, that `ordo/current.queue` is drawn from it in order, that the speaker
  trusts it over its memory, and that a line is closed only by the principal's word: no tool
  reads, orders, sweeps or checks the collection, and the page does not read it.
- **The comparer's reply is read for its signals alone.** The speaker takes the `redraw:` lines
  of the reply and nothing else to the drawer; the drawer's refusal of words that do not open
  exactly one answer of the packet is what keeps anything of the user's from reaching a clean
  turn by that road.
- **The line's rules are held by reading.** The order of requirement, line, comparison, build
  and check; the opening at the purpose; the back-brief; the cases held back; the budget; the
  build's brief citing the AI's answers and never the principal's requirement; the four signals
  before a constraint binds; and the action context's being appended to and not changed within
  a round: no tool checks any of them.

## Where this entry point departs from the others

- An act is put and carried out, where `/principal:dictate` **No action is taken in a
  dictation** takes none.
- Rows are written at each batch point while the sitting goes on, where `/principal:dictate`
  **The line** writes nothing while the line runs.
- The rows are shown to the principal in words and made by the tools, with no plan table and no
  `line.py check`, where `/principal:dictate` step 2 enters plan mode first and **The
  compaction** has `line.py check` pass before the plan runs; this session has no export to give
  `line.py` its markdown.
- The record's answer to a question is drawn by a `seal` job and never by the questioner, where
  `/principal:dictate` **Every interviewing phase is the line** has the questioner seal it;
  before a review the speaker seals its own, and its file says who predicted.
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
- A question is put alone, with nothing beside it, where `/principal:dictate` **The four-part
  step** puts tradition, digressions and references with each next step and **Principles are
  asked, mechanisms decided** lists options with their consequences: tradition on an answer
  comes after it (rule 4 of the round), and digressions and references stay in the line doc.
- The line of aporia is sealed before every question on it and carried from one to the next,
  where `/principal:dictate` **The answer is explored, not taken** seals one before a critical
  question.
- Readings of tradition go to the notebook only with the principal's approval, where
  `/principal:dictate` **The adversarial review** finds every reading cited that is not on its
  tab or a *pending* note.
- The round is put on a page whose data the speaker writes, where `/principal:dictate` puts each
  step in the conversation.
- Building is briefed to a helper of the mid tier and reviewed by one of the full tier, where
  `/principal:bootstrap` builds in its own session.

What this entry point says now that reverses what it said before:

- An ordinary session may run a sitting, the open way, where before a session not started as
  the interviewer kind stopped at **Before anything**.
- A helper not of the plugin's kinds may be started for work no kind carries, in the open way,
  where before no helper was started that was not one of them and the coordinator was the only
  helper the session started.
- The guard is said to hold the speaker only in the confined way, where ground rule 2 said it
  held the speaker without condition.
- A question is put alone, where before it was put with the four parts of the step.
- The aporia is sealed for every question on a line and carried along it, where before only
  what the speaker remembers of the line was sealed apart.
- The reader is told to predict that the principal declines to pick where the notebook cannot
  decide, where before the file held the question alone.
- Every act is put as the next action, in one of four kinds of the page, where before an act
  was proposed as a question; the four kinds of act of ground rule 4 stand.
- A different choice is also an override, an observation and never a verdict, where before it
  was called a failed prediction alone.
- The rows of a batch point are put as reviews, one at a time on the page as a question is,
  where before they were shown in words whole.
- Every ask of the principal is an action on the page, the pending ones a queue the principal
  sees, where before the speaker put its acts in the session's text.
- An office item the Rule gives the session to run is run by the speaker itself and is not put
  to the principal, the Rule being its grant, where before every act was put as the next
  action; it is run by the speaker and by no helper.
- Every explanation and report, the brief and the close among them, is written in the page's
  action context, where before the brief and the close were said in the session's text.
- The AI's own turns are put by this session, in clean turns run by `tools/clean_turn.py`, where
  before the principal ran `/principal:ask` in a second session that prompted, the one exception
  to ground rule 1; that entry point is removed and there is no exception.
- A build follows a line in the AI's graph and is briefed from the AI's answers, where before
  the speaker briefed it from the notebook.
- Every open line waits as one document of the page's collection `lines`, and the queue is drawn
  from it, where before a line at rest waited in the line doc's *Opened* section and in an open
  note on its tab.
