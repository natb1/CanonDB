---
name: bootstrap
description: The principal reconciles application directly from the hypomnemata, ahead of canon. Review the notebook's applications against the checkout for gaps, plan the round for approval, build it on a branch of its own, record what was built as bootstrap, and publish a pull request the author merges. Invoke as /principal:bootstrap [dictation].
disable-model-invocation: true
allowed-tools: mcp__claude_ai_Claude_Docs__read, mcp__claude_ai_Claude_Docs__update, mcp__claude_ai_Claude_Docs__batch, mcp__Claude_Docs__read, mcp__Claude_Docs__update, mcp__Claude_Docs__batch
---

# /principal:bootstrap \[dictation\]

A principal entry point. It grants **notebook, canon and the checkout together**, which is
what makes it a principal entry point and not a canon one: never run it inside a turn that is
answering a canon question.

There are two ways application reaches `main`. The strict one runs `/principal:dictate` →
notebook → `/principal:ask` → thread → merge → canon → the asynchronous workflows that
reconcile application *from canon*. This is the other: `/principal:dictate` → notebook →
`/principal:bootstrap` → pull request → `main`. It implements what the notebook describes
before any answer has landed, because some application is wanted sooner than the elenchus
can supply it. What it builds is timelier and less strict, and it says so in two ways: every
bootstrap application is a **postulate** in the notebook, and every one is recorded in
`.principal/bootstrap.json`, the manifest of what bootstrap built and still owns.

`[dictation]`, when given, focuses the round on what the prose names — and it is a dictation
to the notebook first, applied exactly as `/principal:dictate` applies one, so that what is
built is what the notebook says and never more. Without it, the round reviews every
application in the notebook for a gap.

The author's feedback on a bootstrap pull request — a comment, a review, a message naming a
requirement the round missed — is read the same way: as a dictation to the notebook, and as
his authority for one more round on the same branch. Nothing is built from feedback that the
notebook has not first taken in.

The notebook is the document `.principal/notebook.json` names at the project's root. `tools/`
below is the plugin's own, at `${CLAUDE_PLUGIN_ROOT}/tools/`, and `$SCRATCH` is the session's
scratch directory. The document tools this run reads and writes the notebook with are granted
in its frontmatter under `allowed-tools`: invoking the entry point is the grant, and no other
turn holds one. Each tool is named in both spellings the surfaces give it,
`mcp__claude_ai_Claude_Docs__…` and `mcp__Claude_Docs__…`; a name the surface lacks grants
nothing.

## Ground rules

1. **The artifact is the source of truth.** Read it before anything else, as `/principal:dictate`
   does. An application is what the notebook says it is, and a gap is between that and the
   checkout — never between the checkout and what you would have built.
2. **What is built is what the notebook describes.** An application with no entry in the
   notebook is not bootstrapped; it is dictated first, in this run or a prior one, and built
   after. A round never invents an application to fill a gap it noticed.
3. **Bootstrap yields to canon.** An application whose standing is `derived` was reconciled
   from an answer that has landed, and this run never touches it, nor any file it owns. A
   bootstrap application is superseded the moment canon reconciles the same application: the
   reconciliation takes its files out of every manifest entry that lists them, drops an entry
   left with no files, and no later round takes them back. See **Supersession**.
4. **A file is bootstrap's to write only if it is new or already bootstrap's.** The manifest
   lists what bootstrap owns. A file that exists and is not listed there is canon's, or the
   principal's own hand's, and this run does not change it. Canon is what is under `canon/`,
   and nothing there is written here: a file enters it at promulgation and no other way.
5. **The author merges.** This run opens the pull request ready for review and stops. It never
   merges, never pushes to `main`, and never marks its own work as canon.

## Procedure

**1 — Read, in place.** The document is the reference, and it is read where it stands:
nothing is exported, transcribed to disk or built into a graph file. Read the artifact's tab
list. For each author tab — one whose top-level ancestor is the root, order `a0`, and not a
tab under a tradition's, order `b…`; a tradition's tabs carry no application — `search` its
body for `⚙` to find the application headings, then for ` · ◆ ` to get every application
line with its block id and `h`, and keep the tab's `rev` as its bookmark. That is every
application in the notebook, and all this entry point reads of it besides the blocks a
dictation bears on, which a `search` for their words finds. Then `git fetch origin main` and
start the round's branch from `origin/main` — `bootstrap/<what the round is for>` — or check
out the branch of the pull request the feedback came in on. Read `.principal/bootstrap.json`.

**2 — Take the dictation in.** With `[dictation]`, or with the author's feedback, run the
`/principal:dictate` procedure over it first — plan, tool, attenuate, apply, re-check — so
that the notebook holds what is about to be built. Its plan rows cite the prose; this run's
rows, in step 4, cite the notebook. A dictation that changes nothing in the notebook but
names what to focus on is still recorded: as the pressure it bears on.
A dictation that bears only on applications, or on the words of a paragraph, is applied in
place — `tools/application.py` for an application, `tools/inplace.py` for the words of an
answer, its headline, a definition's body or an amendment to a hinge's provenance. One that
adds or drops a term or a glossary entry is `/principal:dictate`'s in-place path, with its
scoped check over the touched tabs and their ancestors; one that changes a question, a state
or the specification is `/principal:dictate`'s whole, with its graph and its checks, and until
that runs this round records the dictation verbatim as a note on the tab it bears on, opening
with the word *pending* (`tools/inplace.py note insert`, after the last block of the section it
concerns), which `tools/check.py` reports until a run takes it in.

**3 — Review for gaps.** For every application (⚙) read in step 1, read
what it says and look at the checkout. Its `link` is where it says the thing lives; its
`what` is what the thing is. Class each one:

| class | meaning |
|---|---|
| `derived` | reconciled from canon: not this run's, whatever the checkout holds |
| `built` | a postulate whose thing exists at the link and does what `what` says |
| `diverged` | a postulate whose thing exists but does not match `what`, or is not where the link says |
| `missing` | a postulate with nothing at the link, or a link of `not yet written` |

Without a dictation, every `diverged` and `missing` application is the round's. With one,
only those the prose bears on are, and the rest are listed and left. Whether a `built`
thing does what `what` says is read, not computed; say what you read.

Then the pending notes. A note on an author tab opening with *pending* — a `search` for the
word finds them — is a clause of a dictation no run could apply, left on the page by the run
that owed it. Each is listed with the gaps, and each is taken in as a dictation of this round
through step 2: applied where the tooling now can, and the note taken off; or left standing,
and said so, where it still cannot.

Then the other direction. Write the applications step 1 read as a JSON list, one
`{"tab", "name", "link"}` each with the link as the read spells it, and run
`tools/gaps.py <that file> --root <the project's root> --repo <owner/name>` (the root defaults
to the working directory and the repository to `origin`'s; run from elsewhere, or without an
`origin`, it would list every file as unaccounted for and say so of no link). It says per
application whether its link's path is in the checkout, or that the link is `not yet written`,
which is the `missing` class above and not a link gone wrong; and lists every tracked file that no
link and no manifest entry accounts for
and that is not under `canon/`. A link to the repository's root accounts for nothing. Read
each file it lists and class it:

| class | meaning | what the round does |
|---|---|---|
| `justified` | an application's `what` describes it, though no link or entry names it | the manifest takes it, or its link is corrected in place |
| `undocumented` | a requirement the notebook does not hold | proposes the dictation that would hold it; the file is not bootstrap's until that lands |
| `stale` | nothing the notebook says wants it | proposes pruning it; it is deleted only on approval |

**4 — Plan.** Enter plan mode and write the plan before any write. One row per edit:

| edit | application | motivated by | files | manifest |
|---|---|---|---|---|
| what changes | tab and application name | the clause of the application's `what` (or the dictation) that requires it, quoted | the files written, each new or already bootstrap's | add / keep / none |

A row whose file is neither new nor in the manifest does not belong in the plan: say why the
file is not bootstrap's, and what would make it so (a dictation that makes the application
bootstrap's, or the file's own application being reconciled). A row on a `derived`
application is never in the plan. Wait for approval. Where plan mode is not available,
present the table and stop until the principal says to go on.

**5 — Build.** Only the rows approved, only the files they name. A tool gets its tests, under
the plugin's `tools/`; a skill gets its attenuation; a rule the notebook states that a script
can decide is tooled, as `/principal:dictate` step 3 says. Run the plugin's tests
(`python3 -m unittest` in `tools/`) before anything is recorded.

**6 — Record.** Two records, and neither is a comment in a file.

- The manifest: one entry per application built, `{"question", "application", "files",
  "pull_request", "rounds"}`, added or updated in `.principal/bootstrap.json`. The files are
  the ones bootstrap now owns; a round that stops owning a file removes it.
- The notebook: the application's `link` points at the thing on `main` — the path it will
  have once the pull request is merged — and its standing is written `postulate`
  (`--standing postulate`), and stays so until a reconciliation writes `derived`; the discharge
  clause beside it is what the renderer reads off the answer's state. Write each change with
  `tools/application.py` over a saved read of the block — `replace` for a line, `insert` for
  a new application, `delete` for one withdrawn — and send the ops it prints as one prose
  `update` per tab. It refuses a read whose block does not hash to the `h` the document
  printed, so a read copied by hand is checked before anything is built from it. No body is
  written, so no other tab's links are retired and no relink is owed. Re-check by reading
  each touched tab back with `sinceRev` at its bookmark.

**7 — Publish.** Commit on the round's branch, push it, and open the pull request against
`main`, ready for review, or push to the one already open. The body lists the applications
built, by tab and name, the manifest's diff, and what step 3 listed and left. The author
merges; his merge is what makes the branch `main`, and nothing here counts as canon for it.

**8 — Report.** The pull request, the applications built, the gaps left, and what step 2
took into the notebook. Not the code: it is on the branch, where the author reads it.

## Supersession

Two things keep a bootstrap application from compromising one reconciled from canon, and make
the second replace the first without anyone's hand.

- **Standing decides who writes.** An application's standing is `derived` once the answer it
  rests on has landed and the artifact was reconciled from it, and `postulate` otherwise;
  `standing-honest` holds the half a script can. This run writes only `postulate`
  applications, and only the files the manifest gives it or that do not yet exist. So
  nothing canon reconciled is ever rewritten by a bootstrap round.
- **The manifest is the hand-over, file by file.** When canon reconciles an application the
  manifest lists, the reconciliation writes the files as canon says, takes each of them out
  of every entry that lists it, drops an entry left with no files, and the application's
  standing becomes `derived`. A file several applications shaped is listed under each —
  `skills/dictate/SKILL.md` under three — and canon's reconciling any one of them makes the
  file canon's for all: rule 4 refuses it to any later round, and rule 3 refuses the
  application. The bootstrap version is gone when the reconciliation lands, and it is gone
  because the file's listing is, not because anyone remembered it.

A bootstrap application that canon later contradicts is not a conflict to resolve: it is a
postulate that did not survive, which is what a postulate is. The notebook's answer on
discharge says the same of any artifact built ahead of the answer it rests on.

## Attenuation

Rules of this entry point that no tool decides. Hold these by reading.

- **A gap is read.** Whether a `built` thing does what its `what` says, and whether a
  `diverged` one drifted or was never right, is judgement. The table in step 3 is what you
  read, written down, so the principal can see the reading before he approves the plan.
- **The dictation is recorded before it is built.** Feedback that names a requirement is a
  clause of the notebook or it is nothing the notebook supports. Step 2 comes before step 3
  every round, and a round that built from prose the notebook does not hold has built a
  postulate no application names — which the manifest would list and the notebook would not.
- **A pending note is a dictation whose run is still owed.** The note says what a run could
  not apply, in the words that run had; whether the tooling of this round can apply it now,
  and whether the note's words still say what the principal meant, is read. A note taken off
  the page is one whose clause now stands on it, and nothing checks that but the reading.
- **Ownership is the manifest's, and it is kept honest by hand.** Nothing checks that every
  file bootstrap wrote is listed, or that a listed file is still bootstrap's. Read the diff
  against the manifest before the pull request goes: every file in one is in the other.
- **Focus is the prose's, scope is the notebook's.** `[dictation]` narrows which gaps the
  round takes; it never widens what an application is. Where the prose asks for more than
  the application says, the notebook is dictated first, and the plan cites the new clause.
- **The notebook is read in place, one block at a time.** A round reads application lines
  and the blocks a dictation bears on, never a whole tab, and builds no graph file of its
  own. What it writes by itself — an application, the words of a paragraph — changes no
  question, term, state or definition, so the checks a graph feeds have nothing to see; a
  round that finds it must change one has found a dictation for `/principal:dictate`, whose
  in-place path and scoped check take a term or an entry, and whose whole path the rest.
- **An orphan's class is read.** `gaps.py` lists what nothing accounts for, and a tree link
  covers a subtree by address alone. Whether a listed file is a requirement the notebook
  lacks or a thing nobody wants any more, and whether a covering link's `what` really
  describes a file under it, is judgement: the reverse table in step 3 is that reading,
  written down before the plan.
- **The link is the thing's address on `main`.** It is written before the merge, so it is a
  promise the merge keeps. A pull request the author closes leaves links at paths that do not
  exist, and the next round finds them as `missing`, which is right.
- **The principal approves, the author merges, canon supersedes.** Three acts, and this run
  does none of them: it waits on the first, publishes for the second, and yields to the third.
