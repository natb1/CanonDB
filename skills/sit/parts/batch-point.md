Read this part at each batch point, before a note's rows file is made at the round, when a link of a chain fails, and at the close.

**4 — The batch point.** The rows are shown to the principal in words first, put as reviews
(rule 6 of procedure 3), one at a time: the sentences for
the tabs, the cases, what is expected to generalize, the questions for the AI's own record, the
open notes to add, the open notes to take off because what they held now stands on the tab, and
the lessons of the record of predictions that recur (**The record of predictions**); what was
written as the round goes is not put again. What the principal approves is then made into a **rows file**, `$SCRATCH/rows/<job id>.json` for
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
kind `change`. A new tab of the AI's own record is not of these: the `ai-recorder` makes it in a
`place` job, and the speaker makes the root (`ai-line.md`, **The line in the AI's graph**).

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
