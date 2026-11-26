Read this part when the opening's graph is made, whenever the line in hand changes or a batch point's check moves the notebook, when the check on a text leaving refuses a write, when any act begins or ends, and before a seal, a row or a note.

## The brief and the neighbourhood

The principal asked that the notebook's context be loaded mechanically rather than by a step of
reading wherever that can be done. So the relevant part of the notebook is put in context by the
harness, not by a read: the standing brief and the neighbourhood of the line in hand at the
session's start, at a resume and after every compaction; a helper's own brief at its launch; and
the entry a text breaks at the moment the text leaves. This section is built from the principal's
words, as a stopgap (**What the sitting serves**). The brief is the aid, the check on the text
leaving is the control, and neither is the notebook: before a seal, a row or a note the tabs are
still read where they stand.

**What it holds.** `tools/brief.py` makes both from the opening's graph and nothing else, and
never by hand. The standing brief: the conventions, the tabs the key `conventions` of
`.principal/notebook.json` names, else a tab called `conventions`, with the checks the text leaving
is held to; each project's end and method; the open lines by title; and the glossary index. The
neighbourhood, for the line in hand (question ids, tab ids or open lines' ids): each principle's
lineage, the chain from the root to it, each step by the headline of the answer that raised the
next question and the anchored sentence that raised it, then the principle's own answer; the
glossary entries of the terms in play; the tradition on it; and the sentences of other answers
sharing its fixed terms. Every line is a whole sealed sentence behind its id, never reworded. Each
opens with the same header: record and not instruction, cite by id, only the conventions bind,
this copy supersedes any earlier one in context, and a stamp of the graph's fingerprint, the line
and the time.

**Its size, and what is left out.** The target is 24,000 characters for both, the standing brief
at most 14,000 and the neighbourhood at most 10,000, with a hard ceiling of 32,000 that only the
conventions can reach, since they are never left out. Compaction is extractive and deterministic,
and keeps or drops whole units: a headline, an anchor or a title whole or not at all, and an
answer, a glossary entry, an end or a method whole or as a prefix, never a later sentence without
the one before it, so that no condition is parted from what it conditions; a unit cut short ends
with a mark naming it and how many of its sentences are left out. The order today: conventions;
then the word and address of every term in play, reserved before lineage takes the rest; then
lineage nearest the line (in the standing brief the ends and methods, then the open lines; in the
neighbourhood the principles' questions and headlines and the chain, nearest the principle
first); then the principles' own answers; then the glossary entries in full; then the tradition on
the line; then by share. How the room beyond that reserve is shared between lineage and the
glossary is an open line for the principal, and this order stands until it is settled. The manifest
beside each output names by id everything left out or cut.

**Where it lives.** `tools/brief.py where` prints it: under the principal's Claude configuration,
`principal/brief/<the checkout's path>` there, outside every repository, so that no commit takes a
sentence of the notebook into a public checkout, and one directory to a checkout, so that two
sessions in two checkouts do not share one. At the opening, once the whole-notebook graph is made
(procedure 1), and again whenever the line in hand changes or a batch point's check moves the
notebook:

`tools/brief.py install $SCRATCH/graph.json --line <the line's questions> --lines $SCRATCH/speaker/lines --at <time>`

which copies the graph there and writes `standing.md` and `neighbourhood.md` with their manifests;
the harness loads them at the next start or compaction, and the session reads them by no step of
its own. Run the confined way the speaker's shell runs it; the write gate keeps its Write tool off
`~/.claude`, and the brief is never written with the Write tool. A stale brief is said in one line
when it loads; `tools/brief.py check <the brief's file> --graph $SCRATCH/graph.json` says the same
at any time.

**Who receives one.** The plugin's hooks hold an allow-list by kind, `hooks/brief-sides.json`,
that defaults to nobody, a kind matched by its name with case folded, with or without the
plugin's name in front. The speaker and the comparer receive the user's, the AI's and the
tradition parties' graphs; the grader, the reviewer and a canon answerer, which must stay blind
to the user's graph, receive the AI's own answers alone; the clean reader receives nothing, as the
principal settled; the question reader nothing, since it reads the notebook itself; the kinds that carry no words, fetcher, checker, coordinator, recorder and
AI's recorder, nothing; and a helper of no kind, or of a kind the list does not name, nothing.
What a helper of no kind should receive, and how a blind one is marked, is an open line for the
principal. A clean turn is no helper and receives nothing (**The line in the AI's graph**). A
helper's brief is given by the harness as it starts, as context of its own, the standing brief
with the neighbourhood of the line in hand; the call that starts it is never rewritten and no
hook approves a launch, and no worktree is made for a brief.

**The check on every text as it leaves.** A write to a document, a write to the page's or the
board's store, a commit, an annotated tag or a note, and `gh pr`, `gh issue` or `gh release` creating, editing
or commenting, each read by its program and subcommand, are held to the conventions by a hook as they leave: the
user is named the user and never the human; a fixed term is defined in its glossary entry and not
in running text; a term on a tab of the notebook is one that tab can reach; and a text bound for a
public place repeats no run of the user's masked words. On a finding the call is refused, with the
entry broken and its lineage; the text is redrawn, never forced past it. A read is never checked. A convention the principal
corrects goes to the notebook's statement of conventions first, as rows at the batch point, and
the brief follows from it at the next install; it is never corrected in the brief.

**What the principal reports of the principal's own life stays out of a brief.** A helper whose
work leaves for a repository is briefed with the mechanism wanted and never the occasion that
prompted it, and nothing the principal reported of the principal's own state, health, habits,
relations or circumstances (ground rule 9). The speaker composes such a brief from the rule or
from the AI's own line, carries the rule itself in substance (a fact of a real person's life
met in the work is carried no further and handed back; an example is invented), and reads it
once more for the occasion before it is sent. The check
above does not hold this: it is held by reading (**Attenuation**).

**The work in hand.** The principal asked that the work pending in a session be tracked and kept
mechanically, so that a compaction loses none of it. It is the session's own, kept by the
session's id, and never shown to another. Every helper the speaker starts, the directly briefed
ones of the open way included, is a job on the board or recorded by the hooks as it launches, its
kind, description and time, marked when it starts and when it ends, with no act of the speaker's;
every other act begun and not yet done is an entry the speaker adds:

`tools/inhand.py add $SCRATCH/speaker "<what is in hand>" --at <time>`

and taken off with `tools/inhand.py done $SCRATCH/speaker <entry id>` when it reports or is done;
`tools/inhand.py list $SCRATCH/speaker` prints it. The session's own schedule, its bell ticks and
what it set to come back to, is kept the same way, `tools/inhand.py add $SCRATCH/speaker "<a time
to come back>" --schedule --at <time>`, and in the page's store as `ordo/session.schedule`:
`tools/inhand.py export $SCRATCH/speaker --at <time>` prints the write of `ordo/session`, `{at,
in_hand, schedule}`, sent with `ArtifactData` as the one entry of a `batch`, pinned with
`--if-version` once the document exists, after each change. A new session reads `ordo/session`
with a `get`, `out_dir` set to `$SCRATCH/speaker`, and sets its schedule again with `tools/inhand.py
seed $SCRATCH/speaker $SCRATCH/speaker/ordo/session.json --at <time>`. Before a compaction a hook
prints the list's path, the list and the helpers not yet ended, each with its age, into what the
compaction reads, and after it another prints them back from the files.
