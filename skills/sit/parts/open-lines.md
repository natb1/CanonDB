Read this part at the opening, after a compaction, when an answer comes in, when an answer or a job opens a line, when the notebook's revision moves, and at the first sitting of the Rule's week.

## The open lines

Every open line still to be put to the principal is one document of the page's database, in the
collection `lines`, beside `ordo`, and nothing waits anywhere else: not in the speaker's context,
not only in the line doc, not only as a note in the notebook. An item of the line doc's *Opened*
section and an open note on a tab each name the line's id and point to it; neither is where the
line waits. `ordo/current.queue` is a projection of the open documents of `lines`, in the order of
their `rank`, for the page to draw: the queue the tool's `order` writes, the open asks and never
the session's own work, which is ranked after them and never put; and `ordo/current.next` is
the one now put; the page reads
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
- `anchors`: the sentences of the user's record it bears on, each `{tab, block, h, words}`,
  `h` being the fingerprint the notebook prints for the block.
- `seal`: what was sealed for it and when, a fingerprint and a time, never the sealed text.
- `parent` and `children`: line ids.
- `answered_by`: what closed it: the answer's file and round, or the line a merged one is
  carried on by; a close by the principal's later sentence keeps the sentence in `closed_by`.
- `rank`: its place in the order; the queue is the open asks by `rank`, lowest first, the
  session's work ranked after them and never in it. A line no longer open or put carries none, and a reopened one none until the next order.
- `opened_at` and `touched_at`: ISO times, read from the clock.
- `review_count`: how many times the weekly chunk has shown it to the principal.
- `origin`: who opened it: `principal`, `speaker`, `ai` for a drawer turn, or a helper's kind.
- `blocks` and `waits_on`, where set: the ids of the lines it holds up, and of the lines it
  waits on.
- `cost`, where set: what the line asks of the principal, on the scale 1, 3 or 9; never set on
  the session's work.
- `owed_by`, on a line of work: `user`, the principal's to do, as where unset, or `session`,
  owed by the sitting and not by the principal.
- `project`, where set: the project the line belongs to, by its name or its root's id (no
  other question's id spells a project). It is
  read on every line, anchored or not, to place the line in its project, and gives the line
  its root's share where no anchor gives it one.
- `pressure`, where set: a number kept from an earlier order, which weighs nothing now.
- What the tool writes: `flags`, by kind, each `{at, …}`, the kinds `ground-moved`,
  `parent-withdrawn` and `touched`, each cleared alone; `gone` on an anchor read as withdrawn;
  `closed_by`, `{sentence, answer}`, and `reopenable`; `proposed`, `"drop"` where the weekly
  chunk proposes it; `reviewed_at`, `review_weight`, `review_since` and `review_method`, when
  it was last shown, where its count began and by which weight, a count begun by an earlier
  weight begun again at the next showing, never proposed for a drop by that change alone;
  and `decision`, `{choice, word, at}`, the user's keep, merge or drop. No mode writes `put` or `answered`: those two states are written by hand, as an
  `update` like the others.

```json
{"id": "l203001020304", "title": "Mornings before the post",
 "kind": "question", "state": "open",
 "ask": {"case": "A morning on which the post holds a bill due that day.",
         "prompt": "Is watering the plants still first?", "recommendation": null},
 "why": "The answer on mornings left the bill's day open; it returns at the next sitting.",
 "source": "s203001020300, round 2, answers/2.md",
 "anchors": [{"tab": "mornings", "block": "b12", "h": "<the block's h>",
              "words": "The plants are watered before the post is opened."}],
 "seal": null, "parent": null, "children": [], "answered_by": null, "rank": 3,
 "opened_at": "2030-01-02T03:04:00Z", "touched_at": "2030-01-02T03:04:00Z",
 "review_count": 0, "origin": "speaker"}
```

A line is closed only by the principal's answer to it; by the principal's own later sentence
settling it in terms, the line then closed with that sentence quoted in `closed_by` and listed
in the action context, so that the principal can reopen it; or by the principal dropping it.
Never because a reader predicts the answer, the speaker or a clean reader among them. The
collection is the principal's private data, like `ordo/rule`: it is never written into this
repository, a line doc's words, the board or anything published. No tool reads, orders or
sweeps it but `tools/lines.py`, which reads an export of it and prints the writes it needs, and
nothing else decides how a line closes (**Attenuation**).

**The tool.** The speaker exports the collection with `ArtifactData`, a `list` of `lines` paged
with `query.cursor` until it ends, `out_dir` set to `$SCRATCH/speaker/lines` itself, and writes
the versions the reads returned to `$SCRATCH/speaker/lines-versions.json` as
`{"lines/<id>": <version>}`; then `tools/lines.py check $SCRATCH/speaker/lines --graph
$SCRATCH/graph.json`, which holds
every document to the fields above and the documents to each other: each parent, child,
blocked line and line waited on (`waits_on`) exists, no chain of `blocks` and `waits_on` returns
to where it began, a parent and its child agree on both sides, no line is its own ancestor,
one line at most is put. It does not fail on what a mode mends: a rank two lines hold, which
`order` mends, and a parent that is no line, which `orphans` flags; and it warns, refusing
nothing, of anchors that name no block, which no move of the notebook can be judged against,
of live anchored lines of no project: no `project`, and no anchor whose tab the graph places in
a project (with no `--graph`, every live anchored line with no `project`); and, with `--graph`,
of a `project` that is neither a project's name the graph knows nor a root's id of it, and,
where the graph's projects are named, of a live line with no anchor and no `project`.
The lines opened before this tool carry such anchors, `{tab, words}`, the tab named in words:
until each is given its tab's id, block and `h`, `moved` judges none of them, and says how many
it could not judge. Whether the `list` with `out_dir` returns each document's version is to be
verified at the first sitting that runs it; where it does not, each document's version is read
with a `get` before any writing mode. `tools/lines.py queue $SCRATCH/speaker/lines` prints the queue as the
stored ranks give it, against which `ordo/current.queue` is read at a resume. A writing mode
prints the writes, each an `update` of the fields that change, pinned with `if_version` and
stamped with `touched_at`; the speaker sends them with `ArtifactData` in batches of fifty at
most, in order, and exports again before the next mode. Where a batch is refused, the speaker
exports again and runs the mode again, which writes what is still owed: `order` run again over
a store that took only some of its batches mends what they left. A refusal is a `REFUSED:` line
and no write.

The order is the tool's, one weight over every open line, anchored or not: its share, times
what it unblocks, divided by what it costs the principal. The share is the share of the root its
anchored sentences carry, each anchor read by its tab and block where the shares give one, else
by its tab, each once, summed, no tab for more than its own share. A line with no anchor the
shares key takes half the least share held by any anchored live line, open or put, the
session's work among them, of its project, so that it sorts by share below every anchored line
of its project, and is marked provisional. A line may stand in several projects: the one its
`project` names, by the project's name, read first, or by its root's id where the graph names
that root; and, on any line, each project the graph places one of its anchors' tabs in. A line
in several projects counts as an anchored line of each, so one anchored in two projects sets
the least of both; an unanchored line in several takes the least over all of them. A line in
none is of no project: where the graph's projects are named, it is of the whole root and takes
half the least share of every anchored live line; in a notebook of one project the lines of no
project are one group. Under `--shares` alone no tab and no root's id is placed: a project is
then its `project` as written, a project named by its name on one line and by its root's id on
another is two projects, and an anchored line with no `project` is of no project, setting no
share for an unanchored line of a named project; `check` warns of each such line.
Where its project has no anchored live line, it takes half the share of its project's root
instead, or of the whole root where it names no project the shares know. That fallback is a
step: an unanchored line's share rises to half its root's when the last anchored line of its
project leaves the live states, and the unanchored lines of a project with no anchored line can
weigh above those of a project with one. An anchored line whose share is zero counts as no
anchored line: it takes the provisional share itself. Where no shares are given, every line
weighs a share of one and is provisional. What it unblocks is one and the number of open lines
that wait on it directly: its children, the lines its `blocks` names, and those whose
`waits_on` names it. What it costs is its `cost` where set; else 1 for a question or a review,
and 3 for the principal's work. The session's work, `owed_by: "session"`, is weighed by the same
measure at a cost of one and ordered apart, after every ask: it is never in
`ordo/current.queue` and never holds the principal's card. The line put comes first, then the
heaviest; ties by `opened_at`, oldest first, then id. `rank` is the place in that order, the
asks first. `order` prints every line with its weight, its three terms and the provisional
mark, the asks under `order` and the session's work under `session_work`, and writes the queue
to the file `--queue-out` names, which the speaker sends as `ordo/current.queue`. It is a
proposal like the brief's acts (rule 5 of the round), and the principal's override always
stands. Where the principal takes another line ahead of the order, `tools/lines.py override
$SCRATCH/speaker/lines --taken <taken line> --ground "<the ground, in a few words>" --graph
$SCRATCH/graph.json --at <time>` appends to `$SCRATCH/speaker/lines-overrides.jsonl`, beside the
export, the line taken and the line the order put first, each with its terms, the time, and the
principal's ground restated in a few words; `--over <line>` names another line passed over. The
same override run again is not appended twice, and the tool says so. It writes nothing to the
store and changes no weight. `tools/lines.py report
$SCRATCH/speaker/lines` reads that log against the order as it was computed: how many
overrides, which lines, and which term of the weight each most contradicts, none where the
line taken already weighed no less, as where the line passed over stood first by being put, and
the provisional rule counted apart from the share term. A change to the
method is proposed from the report, as a review of mechanism; the log never makes one.

- **When the notebook's revision moves**, at the opening's fetch and after every batch point's
  check: `tools/lines.py moved $SCRATCH/speaker/lines --outlines $SCRATCH/outlines --versions
  $SCRATCH/speaker/lines-versions.json --at <time>` flags every open line with an anchor whose
  block's fingerprint changed or whose block is gone, `ground-moved`, and `tools/lines.py
  orphans $SCRATCH/speaker/lines --versions $SCRATCH/speaker/lines-versions.json --at <time>`
  flags every open line whose parent is merged, dropped or no line, `parent-withdrawn`. Where
  the outlines hold every tab, `--whole` flags too an anchor whose tab is gone. A flagged line
  is read against its sentences as they now stand; once read and still standing, `tools/lines.py
  unflag $SCRATCH/speaker/lines <flagged line> --kind ground-moved --outlines $SCRATCH/outlines
  --versions $SCRATCH/speaker/lines-versions.json --at <time>` clears that flag alone, takes
  the fingerprints now, and keeps an anchor whose block is gone as read gone; another kind is
  cleared by its own `--kind`, without the outlines.
- **At each answer**, in this order. The sweep: `tools/lines.py sweep $SCRATCH/speaker/lines
  --answered <answered line>` prints the open lines that are the answered line's children, that
  share its parent, or that share an anchor with it, children first; that set, and no more, is
  read against the answer. A line the answer settles is closed only by the user's sentence,
  quoted: `tools/lines.py close $SCRATCH/speaker/lines <line> --sentence "<the user's
  sentence>" --by-answer <answer> --versions $SCRATCH/speaker/lines-versions.json --at <time>`,
  which refuses without the sentence and keeps it in `closed_by` with `reopenable`; where the
  user has said no such sentence, the line stays open, however sure a reading is, and a
  line the answer only touches is flagged, `tools/lines.py touch-flag $SCRATCH/speaker/lines
  <line> --answer <answer> --versions $SCRATCH/speaker/lines-versions.json --at <time>`. A
  line the answer opens under another is linked on both sides, `tools/lines.py link
  $SCRATCH/speaker/lines --parent <parent> --child <child> --versions
  $SCRATCH/speaker/lines-versions.json --at <time>`. Then the order, `tools/lines.py order
  $SCRATCH/speaker/lines --graph $SCRATCH/graph.json --queue-out $SCRATCH/speaker/queue.json
  --versions $SCRATCH/speaker/lines-versions.json --at <time>`, over the opening's
  whole-notebook graph; and the queue redrawn: `ordo/current.queue` set to the queue it wrote. A line closed by a
  sentence is reopened at the user's word, `tools/lines.py reopen $SCRATCH/speaker/lines
  <closed line> --versions $SCRATCH/speaker/lines-versions.json --at <time>`.
- **Once a week**, at the first sitting of the Rule's week: `tools/lines.py chunk
  $SCRATCH/speaker/lines --graph $SCRATCH/graph.json --n 5 --versions
  $SCRATCH/speaker/lines-versions.json --at <time>` picks, from the lower half of the queue and
  never its head, the open lines at its far end, the oldest of them shown first, none shown in
  the six days before, and prints the writes adding one to each one's `review_count`; each is
  put to the user as a `review`. A line shown three times without its weight rising is
  marked `proposed: "drop"`, never where no shares were given, which is a proposal for the user and nothing more:
  `tools/lines.py decide $SCRATCH/speaker/lines <line> <keep|merge|drop> --by-user-word "<the
  user's word>" --versions $SCRATCH/speaker/lines-versions.json --at <time>` writes the
  user's choice, a merge with `--into <other line>`, and refuses a merge or a drop without
  the user's word; a drop or a merge flags the children it leaves.
