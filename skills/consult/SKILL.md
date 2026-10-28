---
name: consult
description: The principal describes a situation in the principal's own words and gets back the clauses of the notebook that bear on it, each verbatim with where it stands, and nothing is drawn, written or recommended. Invoke as /principal:consult <situation>.
disable-model-invocation: true
allowed-tools: mcp__claude_ai_Claude_Docs__read, mcp__Claude_Docs__read
---

# /principal:consult \<situation\>

A principal entry point, and a read-only one. It grants the **notebook for reading** and
nothing for writing, and it draws no answer: the notebook may be in the room because nothing
here is a draw of anything. This is the occasion read, what a notebook kept for rereading is
reread for: the user is in a situation and asks what the user's own record says bears on it,
because no one can carry the list of situations each clause governs, and recognition at the
moment is what a list asks for and a review supplies.

`<situation>` is the user's words. The run never restates them as a principle, never names
which principle the user "should" have recognised, and never says what to do. It finds the
clauses, quotes them, and says where each stands.

The notebook is the document `.principal/notebook.json` names at the project's root, with
`project` naming the project this checkout keeps. The document tools this run reads with are
granted in its frontmatter under `allowed-tools`: invoking the entry point is the grant, and no
other turn holds one. Each tool is named in both spellings the surfaces give it; a name the
surface lacks grants nothing.

## Procedure

**1 — Read the tab list.** The author tabs of this project, and of every project earlier in
the order than it, since a later project's end reads an earlier one's and the earlier one's
clauses bear on everything below it. Never a party's tab, and never the reserved `lease` tab.

**2 — Read the clauses, in place.** Per author tab, a `search` for `▸ ` finds every term, the
clauses that raise questions; a `search` for `⚓ ` finds the hinge's parts, the end and the
method among them; the thesis headline (`◆`) is on the same read. Read a whole tab only where
a clause's words are not enough to tell whether it bears on the situation.

**3 — Match, by reading.** A clause bears on the situation when the situation is one the clause
governs: an offer of income on a clause about trading agency, a request for help on a clause
about what is owed, a new account or device on a clause about custody. The match is read, not
computed, and a doubtful match is reported as doubtful. Where a clause carries a cue, the
situation it governs written beside it, the cue decides.

**4 — Report.** For each clause that bears: the tab and the project it stands on, the clause
verbatim, the end it serves (the root's end, quoted in part where the clause does not say),
and what stands on the clause: a deadlock and its attenuation, a suspension and what it waits
on, a cue and the situation it governs, a pending note. Order by the project's order, earlier
first, then by the tab. Then stop.

**5 — Nothing is written.** No note, no claim, no transcript, no file. A situation no clause
bears on is said in one line: it is a candidate dictation, and the dictate entry point is
where it goes, when the user chooses.

## Attenuation

- **No recommendation.** The clauses are the user's own words or the AI's answers the user
  merged, and the run adds nothing to them. "What should I do" is answered by the clauses
  standing there, and by nothing the run composes.
- **No principle named for the situation.** The run says which clauses bear; it never says what
  the situation "is" in the notebook's terms. Naming it is the user's reading.
- **The user's words are not restated.** The situation is quoted as given where it is quoted
  at all; a paraphrase is where a reading leaks in.
- **An earlier project's clauses come first.** archai's clauses bear on every project below it,
  and the order of the projects is the order of the report.
- **Nothing is kept.** The run is the occasion's and ends with it; a situation worth keeping is
  a dictation the user runs, never a note this run leaves.
