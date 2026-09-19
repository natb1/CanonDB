# Hypomnemata — specification

The hypomnemata is the principal's notebook for CanonDB v1: his priors, in his voice, never canon.
Two encodings share one graph model. This file is a derived artifact of the notebook itself
(the `docs-encoding` tab and its seven section tabs); where they disagree, the notebook wins.

## Source of truth — read before you write

**The document database is the source of truth.**
<https://claude.ai/code/artifact/47d8730e-0bb8-4995-b3fb-8310665c1528>

- The principal edits it directly and **asynchronously**, outside any AI session.
- An AI **reads the database before it writes**, and grounds every author-requested update in what it
  finds there — never in a local copy, never in what it remembers writing last session.
- An AI **never reverts or overwrites a prior it did not write**. A block it has not read is a block it
  does not touch; on a hash or find mismatch the human's words win and the AI says what it kept.
- An AI **writes only in the encoding specified below**. The encoding constrains what the AI may write;
  it does not constrain the human, and it is not the interface he uses.
- **Every file under `hypomnemata/` is a cache**, including `nodes/` and anything a tool renders.
  No file is ever authoritative over the database.

## Graph model

| element | from → to | meaning |
|---|---|---|
| **question** node | — | the unit of address; one tab. No incoming term edge ⇒ a hinge, asked by fiat. |
| **thesis** node | — | an articulated answer. Canon: the AI's verbatim words. Notebook: the principal's. |
| **answer** edge | question → thesis | **assent lives here** — the merge admits one thesis as the answer. Canon: exactly one assented answer, plus at most one deadlocked answer. Notebook: any number. |
| **term** edge | thesis clause → question | **deadlock lives here** — dissent from one clause without withholding the merge. Several clauses (anchors) of one thesis may share one term: one follow-up is one term. A clause raising no question is a null edge and stays as text. |
| **support / divergence** | thesis → tradition thesis | how a tradition bears. Traditions are roots of their own. |
| **application** | thesis → artifact | the only edge leaving the graph. Ahead of its landed source it is a **postulate**, owing a discharge (diff derived against postulated, never assume). |

Question metadata: state (held · in line · landed · revised · deadlocked), kind (definitional · case ·
consistency), priority, load, requires (inbox items). Thesis metadata: assent, provenance (model, harness,
canon commit). Pressure originates at leaves; priority sums a question's pressure with every question blocked
behind it; load sums its follow-ups with its children. An inbox item (promulgate · provide · dispose · build)
lives on the most descendant tab that is an ancestor of every question it blocks, and instances a clause of
canon's of-the-human list.

The model is not a file format. Which end of an edge records it is each encoding's business.

## Canon encoding (the v1 repo, branch `main`)

- **Term edges are recorded on the child node.** A question node lists the one or more terms that lead to it.
  The thesis node carries no terms: drawing a term is the principal's act, never the answering turn's.
- `/canon:answer <question node id>` — the entry point that answers a question. It (1) runs a script that
  materialises `CLAUDE.local.md` with the question node and its **entire lineage up to the root**, and
  (2) leaves the turn to write the thesis node and nothing else.
- The commit is the AI's; the merge is the principal's, and the merge is his assent.

## Context and loading (the clean-context rule)

An answer is evidence of the AI's own prior only so far as nothing in its context put the answer there.

- **Nothing loads globally.** No canon, no notebook, and no artifact projected from canon is loaded by
  `CLAUDE.md` or by a rules file.
- Canon and notebook context are scoped to `.claude/skills` and `.claude/agents` (not yet defined).
- The principal grants context by the entry point he invokes: **`/principal:*` grants notebook + canon**
  (selecting, asking, disposing); **`/canon:*` grants canon alone** (answering).
- `CLAUDE.local.md` is a worktree cache of what an entry point materialised. Never a source.
- A **mechanical guard** — a check refusing a turn whose context carries the notebook — is an eventuality,
  recorded so it is not forgotten. Not a blocker; until it exists the rule holds by discipline.

## Docs encoding — tab layout

One tab per question and every thesis answering it. Tabs nest by term edge; a question with several parents
is placed under one and lists the rest. Traditions are top-level roots. Section order is fixed; empty
sections are omitted.

```
# <short name>                                    title = the question's short name = the tab name
<term text, verbatim, linked to its term section in the parent's thesis tab>   one line per term edge in
*<the question>*                                  subtitle: ONLY the question, never a restatement of the
                                                  term (an implied gloss leaks the prior and burdens the
                                                  answering agent with parsing for it)
⌂ <mention> › <mention> › <this>                  lineage breadcrumb (root: "⌂ root")
question: <state> · <kind> · priority N · load N · requires: <linked inbox items>

## Thesis      ### ◆ <title summary>   metadata line first (assent · deadlock · provenance link), then the
               verbatim text with each clause anchored to its term section and a mention chip to the
               question it raises, then the tradition edges of THIS thesis, one line.
## Glossary    ### ≡ <word>            a term edge with no descendant and a body; may cite a tradition.
## Inbox       frontier table: question | term | kind | priority | requires   (no ready column: requires
               already shows it), then ### <title summary> per inbox item living on this tab.
## Terms       ### ▸ <title summary> → <mention>   anchors verbatim in italics, one line each; deadlock here.
               Flat: terms never nest, they recurse by following their question.
## Applications ### ⚙ <artifact>       what · source thesis · path · derived or postulate.
## Hinge       ### ⚓ question: presuppositions and leaks (the principal's reading, notebook only)
               ### ⚓ thesis: model · harness · canon commit link (factual; canon keeps this)
```

Rules across every section: **no identifiers in prose** (a question is named by its tab, an item by its
title); **no inline documentation** of the encoding on a tab that is not about the encoding; **one home per
datum**, linked from wherever else it bears. In-page links are applied after the write with the `format` op
(`add: [{type: "link", href: …}]`); a cross-tab link is
`https://claude.ai/artifact/<viewer id>#<tab file id>.<block id>`.

## Cache layout (not authoritative)

`hypomnemata/nodes/*.yml` and `hypomnemata/tools/{check,pressure,render}.py` target the superseded flat
schema and are to be re-cut to the model above. Until then they are stale caches; the database is the record.
