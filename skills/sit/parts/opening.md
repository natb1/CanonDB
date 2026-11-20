Read this part at the opening, once the board is exported as procedure 1 in `parts/board.md` gives it: the rest of procedure 1 and procedure 2.

Read the notebook where it stands. Every sitting opens with a `fetch` of every tab of the
project, its ancestors and the parties it cites, since the shares and the open lines are
computed over a graph that holds the root: `tools/page.py $SCRATCH/coordinator/views/<job
id>/*.json -o $SCRATCH/tabs --outlines $SCRATCH/outlines` over the lifted views, and `tools/read.py
$SCRATCH/coordinator/lists/<job id>/doc-<document id>.json $SCRATCH/tabs -o $SCRATCH/graph.json`,
with no `--scope`, as `/principal:dictate` step
1 gives them, then `tools/shares.py`, `tools/residue.py list $SCRATCH/graph.json --by-share` and
`tools/divergence.py list $SCRATCH/graph.json`; then the open lines are exported and checked,
`moved` and `orphans` run over them, and `order` over this graph (**The open lines**, **The
tool**). Then the brief is installed over this graph for the line in hand
(**The brief and the neighbourhood**). `residue.py list --by-share` is run over this
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
