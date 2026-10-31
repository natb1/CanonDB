---
name: anticipate
description: The principal names a question, an ask or a situation, and gets back a draft of the principal's own answer drawn from the record, the end, the method, the clauses, the cases and the glossary, each source quoted with where it stands, marked a draft for the principal to confirm or correct; the correction becomes a case or a dictation the principal runs, and nothing is written. Invoke as /principal:anticipate <question>.
disable-model-invocation: true
allowed-tools: mcp__claude_ai_Claude_Docs__read, mcp__Claude_Docs__read
---

# /principal:anticipate \<question\>

A principal entry point, and a read-only one, as `/principal:consult` is. It grants the
**notebook for reading** and nothing for writing. Where consult returns the clauses that bear
on a situation and composes nothing, this run drafts what the principal would answer from
them, and says so: the draft is the record's and not the principal's until the principal
confirms it. It is the method's own reading. The canondb root's method reads whether the
record suffices to reproduce the user's answers off an answer drafted from the record and the
user's correction of it; this run is the draft, and what the principal says back is the
reading.

`<question>` is the principal's words: a question of the notebook's, an ask another tool put
to the principal, or a situation with the question it raises. The run never answers in its own
voice, never recommends, and never fills where the record runs out.

The notebook is the document `.principal/notebook.json` names at the project's root, with
`project` naming the project this checkout keeps. The document tools this run reads with are
granted in its frontmatter under `allowed-tools`: invoking the entry point is the grant, and no
other turn holds one. Each tool is named in both spellings the surfaces give it; a name the
surface lacks grants nothing.

## Procedure

**1 — Read the tab list.** The author tabs of this project, and of every project earlier in
the order than it, since a later project's end reads an earlier one's and the earlier one's
clauses bear on everything below it. Never a party's tab, and never the reserved `lease` tab.

**2 — Read the record, in place.** On the root, a `search` for `⚓ ` finds the hinge's parts,
the end and the method among them, which is where the order of appeal stands when clauses
conflict or run out. Per author tab, a `search` for `▸ ` finds every term, the clauses that
raise questions, with the cue beside one that carries it; a `search` for `⚖ ` finds every
case, a situation once put to the user with the user's verdict, the reason and the clause it
tests; a `search` for `≡ ` finds the words and their senses; the thesis headline (`◆`) is on
the same read. Read a whole tab where a clause's words are not enough.

**3 — Draft.** Write the answer the record gives, in the principal's words where the record has
them, the clauses verbatim and the cases' verdicts as they stand, and in plain words only where
a bridge is needed between two sources. After each sentence, its source: the tab and the part,
quoted where it is quoted at all. A case whose situation is like the question's brings its
verdict and reason, and the likeness is said. Where two clauses bear and conflict, the method's
order of appeal decides, and the draft says which clause gave way and why. Where the record
runs out, the draft stops at that point and says so in one line; a plausible continuation is a
leak, and is never written.

**4 — Mark it.** The output opens with the words *a draft from the record, not the principal's
answer*, and closes with the one ask: confirm, or correct.

**5 — The correction's home.** What the principal says back is not written here. A correction
that is a verdict on a situation is a case: print the invocation the principal runs through the
dictate entry point, `tools/inplace.py case insert` on the tab of the clause it tests, with the
case's name, the situation, the verdict, the reason and the clause. A correction that changes a
clause, a word or the order of appeal is a dictation: print it as the principal said it. A
confirmation adds nothing to the record: a draft the principal confirmed is evidence that the
record sufficed, which the method counts on its next reading, and the run says so in one line.

**6 — Nothing is written.** No note, no claim, no transcript, no file.

## Attenuation

- **The draft is the record's.** No word in it is the principal's until the principal confirms
  it, and the run never presents it as the answer. The opening words are not decoration: they
  are what keeps a draft from being read back later as a prior.
- **No filling.** Where the record runs out the draft stops. What makes a continuation
  plausible is the model's own prior, which is exactly what the notebook keeps out of the
  principal's answers; nothing checks it but the writer.
- **Sources verbatim.** A clause is quoted as it stands and a case as it stands; a paraphrase
  is where a reading leaks in.
- **The correction's home is read.** Whether what the principal says back is a case, a
  dictation or a confirmation, no script decides; and a case is only one whose situation is
  stated, so a correction with no situation is a dictation.
- **Sufficiency is the method's count, not this run's verdict.** One confirmed draft is one
  reading; the root's method says how the readings are counted, and never as a verdict on
  either party.
- **An earlier project's clauses come first.** archai's clauses bear on every project below
  it, and the order of the projects is the order the draft's sources are read in.
