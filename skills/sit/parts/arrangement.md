Read this part at the opening, before `$SCRATCH` is made, before naming a path under `$SCRATCH`, an id or a fingerprint the core does not spell, and before starting any helper.

## The arrangement

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
