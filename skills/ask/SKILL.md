---
name: ask
description: The principal puts the next question to the AI. Read the notebook, select the question that waits heaviest with nothing left to wait on, write its lineage out of canon, launch the canon agent to answer it in a clean context, test the answer against canon and the notebook, and record it in thread. Invoke as /principal:ask [question].
disable-model-invocation: true
allowed-tools: mcp__claude_ai_Claude_Docs__read, mcp__claude_ai_Claude_Docs__update, mcp__Claude_Docs__read, mcp__Claude_Docs__update
---

# /principal:ask \[question\]

A principal entry point. It grants **notebook and canon together**, and it is the one place a
canon turn is opened from: the turn itself is a separate agent, `canon-answer`, whose
configuration is the grant. This run selects the question and composes nothing of what the
agent reads. Never answer a canon question in this run, and never launch the agent from any
other.

`[question]` names the question to put, by id. Without it, the run puts the question the
frontier puts first. With it, the run puts that question only if the frontier says it can be
put, and says what it waits on otherwise.

The notebook is the document `.principal/notebook.json` names at the project's root. `tools/`
below is the plugin's own, at `${CLAUDE_PLUGIN_ROOT}/tools/`, and `$SCRATCH` is the session's
scratch directory. The document tools this run reads the notebook with, and records the answer
with, are granted in its frontmatter under `allowed-tools`: invoking the entry point is the
grant, and no other turn holds one. Each tool is named in both spellings the surfaces give it,
`mcp__claude_ai_Claude_Docs__…` and `mcp__Claude_Docs__…`; a name the surface lacks grants
nothing.

## Ground rules

1. **The artifact is the source of truth.** Read it before anything else, as `/principal:dictate`
   does: the principal edits it asynchronously, and the question's wording is whatever it says
   now.
2. **The agent reads; this run composes nothing it reads.** The lineage is written out of the
   graph file by `tools/lineage.py`, the packet is that file, and the prompt is the question's
   wording and the packet's path. Nothing else goes in — not a summary, not a hint at where the
   answer should land, not the name of the tab.
3. **The answer is verbatim.** What the agent replies is recorded word for word, and never
   edited, trimmed or reflowed. An answer the notebook cannot hold as it stands is said so and
   left, not reworded.
4. **Every graph file is a cache**, and the packet is one more. Nothing is exported: the
   document is read in place, as `/principal:dictate` says. No file is
   committed: the record is the notebook's, as step 8 says.

## Procedure

**1 — Read.** Read the artifact's tab list and each tab's body whole, spell the reads with
`tools/page.py`, and build the graph file with `tools/read.py <document read> $SCRATCH/tabs -o
$SCRATCH/graph.json`, as `/principal:dictate` step 1 says. Run
`tools/check.py` over it: no ERROR may stand, since a lineage written out of a faulted graph
is not one anybody vouched for.

**2 — Select.** `tools/next.py $SCRATCH/graph.json` prints the question the frontier puts
first: the AI's, not yet put, and every question the AI answers above it carrying an answer
that has landed. `--all` lists every question not yet put
with what each still waits on, and `--thread <ids>` names the open thread being continued, so
that an answer earlier on it is carried without having landed. Which thread a question is on is
not recorded anywhere, so that argument is yours to give and yours to get right: a question put
with another open thread's answer in its lineage is what the rule against dependent threads
forbids.

When nothing can be put, stop and say what the frontier waits on. What it waits on is an
answer above that has not landed, which is his merge and not this run's to supply.

**3 — Test the question before it is put.** The wording is the notebook's and is not rewritten
here, but it is read against the drafting rules of `/principal:dictate` before it goes: it
restates no anchor, it is one question, it presupposes only what the asking makes true. Then
look past the question's own line. The answer will be checked against the lineage by the agent,
and against everything else by this run — so where an admission on another line, in canon or in
the notebook, would collide with the answer this question will draw, say so now: name the
admission, and propose the question that would carry it. That question is a compaction, and
putting it instead is the principal's act. Stop there; a dictation changes the question, and
this entry point is run again.

**4 — Write the packet.** `tools/lineage.py $SCRATCH/graph.json <question> -o $SCRATCH/packet/lineage.md`,
with the same `--thread` as step 2. The directory must be named `packet` and the file
`lineage.md`, because that is the one path outside the checkout the agent's gate lets
through. The script refuses rather than write a lineage with a gap, and says what is owed.
Do not read the file back into this run; you have the graph it was written from.

**5 — Launch.** Launch `canon-answer` with the Agent tool and this prompt, and nothing more:

```
<the question's wording, from the notebook, verbatim>

Lineage: <absolute path of the packet>
```

Wait for the reply. The agent has Read and nothing else, no rules file, and a gate that
refuses every path but the packet; the harness loads its definition at session
start, so a session that began before it existed cannot launch it and says so.

**6 — Test the answer.** The agent checked it against its lineage. This run holds the rest.

- Against canon on other lines: an admission the answer conflicts with is aporia the answering
  turn could not see. Say which admission, and what the compaction is — withdraw the line to
  the admission it left and put the carrying question there — and record the answer as the
  disposition it awaits, a retreat, rather than as one that stands. The withdrawn answer is
  not deleted: it is on its thread until the merge that replaces it.
- Against the notebook: a conflict with the principal's own thesis on the tab, or with an
  admission of his on another line, is no aporia of the AI's. It is the principal's,
  suspended. Record the answer, name the conflict, and name every line and thread that could
  reach the point. A dissent is not recorded from this run.
- Against nothing: record it.

**7 — Record.** The answer goes on the question's tab as a thesis, beside the principal's own:
`assent: verbatim (AI)`, state `in thread`, provenance naming the model, this harness, the
session by its id, and the canon commit the lineage was written at. The question's state becomes
`in thread`. No term is drawn from it — the clauses that raise the next questions are the
principal's to draw, in a dictation. Edit the graph file, then apply exactly as
`/principal:dictate` steps 4 and 5 say: body, then links, then the tab patch, then the re-check
with `check.py` and `verify.py`. `text-unquoted` and `text-unwrapped` may refuse the answer as
it stands; an answer is verbatim, so the refusal is reported with the answer as the agent gave
it, and nothing is recorded until the reader can hold it.

**8 — The session, and no transcript.** The session an answer came from is recorded by its
id, in the provenance line step 7 writes, and that is the whole of what this run keeps of it:
no log of this session or of the agent's is copied into the project, and nothing is committed.
What the thread is on disk — the file the answer takes when it lands — is the `canon`
question's to answer, and it is held; until then a thread is the notebook's record.

**9 — Report.** The tab the answer is on, the disposition the answer awaits — assent, deadlock,
gloss, suspend, retreat — and what step 6 found. Not the answer: it is in the notebook, where
the principal reads it.

## Attenuation

What this run holds by reading, because no script decides it.

- **The prompt is the question and the reference.** Nothing checks what the Agent tool was
  handed. Read the prompt once more before sending it, against the rule that the question is
  only the question.
- **The thread is yours to name.** `--thread` is the half of the blocking relation no file
  records. Name every question of the open thread being continued, and nothing of any other.
- **Aporia across lines is this run's to see.** The agent sees its lineage and nothing else, so
  what an answer collides with elsewhere is found here or not at all. It is found before the
  question is put where it can be, which is the cheaper compaction, and after where it cannot.
- **The answer is the AI's.** Verbatim, and never reflowed to pass a check.
- **The agent reads its packet and nothing behind it.** The plugin's `hooks/canon-gate.py`
  admits the lineage this run wrote and refuses the rest, canon on disk included, and nothing
  lists what counts as canon: it is what is under `canon/`. So the lineage must be whole, and
  what the answer collides with outside it is this run's to find, as the entry above says.
