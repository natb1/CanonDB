Read this part at the opening, and before the board is exported or written: a job added, a claim, a mark, a fail, a release, a retry, a wait or a resume, and before the coordinator is started.

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
| `lead` | `full` | `question-reader` | `notebook`, `question`: the question's file, `$SCRATCH/lines/<line>/<n>/question.md`, `question_fingerprint`: its SHA-256 | `reply`: the verdict and the reason, `fingerprint` |

The coordinator runs every kind the table gives a helper, every `review` among them and every
`compare`, and passes over the rest; `probe`, `observe` and `turn` the speaker claims and marks done
itself.
Two words of the table name other things too. The `probe` job puts the line doc's address on the
board; it is not `tools/clean_turn.py probe`, the check of the harness run before a sitting's
first clean turn. A `turn` job's input `line` is a question's directory on a line, not the line. A
`lead` job that failed, or whose reading the hooks do not attest, is never retried under its
id: a new `lead` job is added for the question (**The line in the AI's graph**, rule 3).
The coordinator is handed the board's address, the path of `$SCRATCH` and the path of the
plugin's `tools/`, and nothing else; every address it puts on the board is under `$SCRATCH`. It
hands a clean reader the path of the question's file, which that reader may read, and the
notebook's address; a question reader the same, its file a question's `question.md` on a
line; a fetcher the notebook's address and the names in the `tabs` file; a checker
the tools directory, the `views` directory, the `list` file and `$SCRATCH/check/<job id>` to
work in. What a helper hands back in words the coordinator writes to
`$SCRATCH/coordinator/replies/<job id>`, and only that file's address and fingerprint go on the board, as `reply` and
`fingerprint`. After sending a claim, the coordinator exports the board again and starts the
helper only where the job stands `claimed` by `coordinator`; where it does not, it starts
nothing for that job and moves on. It starts each helper with the job's id as the call's description, by which the
hooks record the launch; `tools/lead.py record` reads a `lead` job's reading against that
record (**The line in the AI's graph**, rule 3). Every helper ends its reply with one last line, `status: ok` or `status: failed`,
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
Each start of a coordinator, and of any helper
rule 9 briefs, is recorded in the work in hand by the hooks as it launches, and marked ended when
it stops (**The brief and the neighbourhood**). One coordinator runs at a time: the next is started
only once the last has reported, since every coordinator works through the one
`$SCRATCH/coordinator/` export. The coordinator is the only helper this session starts for work
a kind carries; every such piece of work is a job on the board, every `review` included. Work no
kind carries is rule 9's (procedure 3), and only the open way starts a helper for it.
