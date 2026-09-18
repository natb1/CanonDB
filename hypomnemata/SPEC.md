# Hypomnemata — specification

The hypomnemata is the principal's notebook for CanonDB v1: his priors, in his voice, never canon.
Canon is the AI's verbatim answers merged by the principal; this holds what the principal thinks before,
beside and after the elenchus. Nothing here enters an elenchus turn's context (the contamination rule):
a turn sees main, its line and its question; steering is by selection, case and the prior question,
never by showing the AI a thesis.

Two encodings share one graph model: the graph (below), and the Claude Docs artifact
(https://claude.ai/code/artifact/47d8730e-0bb8-4995-b3fb-8310665c1528), whose layout is the docs encoding.
The same model is meant to encode canon; the docs encoding is the hypomnemata's own.

## Graph model

Two node types, two edge types, plus two edge types with non-question targets.

| element | from → to | meaning |
|---|---|---|
| **question** node | — | the unit of address; one tab. A question with no incoming term edge is a hinge: asked by fiat. |
| **thesis** node | — | an articulated answer. In canon, the AI's verbatim answer; in the hypomnemata, the principal's prior. |
| **answer** edge | question → thesis | this thesis answers this question. Canon: exactly one *assented* answer per question, plus at most one **deadlock** answer (the principal's thesis, typed as such, attenuated). Hypomnemata: any number. **Assent lives here**: the merge admits the thesis. |
| **term** edge | thesis → question | a clause of the thesis (its *anchor* text) raises this question. Several anchors may share one term edge (one question). A clause with no descendant question is a null edge: no section, no metadata; it stays as text. **Deadlock may live here**: the principal dissents from one clause without withholding the merge; the dissent is recorded on the term, with the principal's counter-clause. |
| **support / divergence** edge | thesis → thesis (a tradition's thesis) | how a tradition bears on this thesis. Traditions are question/thesis nodes with their own roots. |
| **application** edge | thesis → artifact | a real-world projection derived from the thesis (a file, a tool, a page). Ahead of its landed source it is a postulate. |

Question metadata: `state` (held · in line · landed · revised · deadlocked), `kind` (definitional · case · consistency),
`priority`, `load`, `requires` (inbox items that must be done before the question can be asked), `lineage`.
Thesis metadata: `assent` (verbatim · merged · none · deadlock), `provenance` (model, harness, canon commit).
Postulates are theses with load: something already rests on them ahead of the elenchus reaching them.
Drafts are theses with no assent on questions not yet asked. Definitions are term edges with a null target and a body.

Pressure originates at leaves: blocked application, postulate load (what unravels if the thesis is false),
target distance, breadth. **priority(q)** = own pressure + priority of every question blocked behind q.
**load(q)** = pressure of q's follow-ups + load of its children. Step size gates the question; cost sets batch size.
An inbox item (a human action of kind promulgate · provide · dispose · build) lives on the most descendant tab
that is an ancestor of every question it blocks. Every inbox item instances a term the AI landed in canon
(the of-the-human clauses of ti-esti).

## Docs encoding (one tab per question, sub-tabs by term edges; tradition roots at top level)

```
# <short name>                                   title
*<the question, as it is put to the answerer>*    subtitle
⌂ <mention parent> › <mention …> › <this>         lineage breadcrumb (root: "⌂ root · a hinge")
question: <state chip> · <kind> · priority N · load N · requires: <mention/link inbox items>

## Thesis
### ◆ <title summary of the thesis>
assent: … · provenance: <link to ⚓ subsection>
<verbatim thesis; each term's anchor text is an in-page link to its ▸ section, immediately followed by a
 mention block to the question it descends to; glossary words are in-page links to their ≡ subsection>
Traditions: <mention> support|divergence — one line each      (edges of this thesis; never under Hinge)

## Glossary
### ≡ <word>            one per definition; may end with a tradition reference

## Inbox
| question | term | kind | priority | requires |                      (the frontier; questions, by priority)
### <title summary of the inbox item>                                   one per item living on this tab
kind · what · obligation (which of-the-human clause) · done?

## Terms
### ▸ <title summary> → <mention descendant question>
*<anchor text, verbatim>*  (one subtitle line per anchor that shares this term)
<deadlock, if any: the principal's counter-clause, attenuated>

## Applications
### ⚙ <artifact>   what · derived from which thesis · path/link · postulate or derived

## Hinge
### ⚓ question: what the asking presupposes
### ⚓ thesis: what the answer was drawn from     model · harness · canon commit (link)
```

Rendering rules: no inline documentation on tabs (it belongs on the hypomnemata tab); no ids in prose
(a question is named by its tab, an inbox item by its title); metadata of the answer is listed once, on the
thesis section; metadata of the question once, on the question line; a null-edge clause gets no section.
In-page links are applied after the write with the substrate's format op (`add: [{type: link, href: "#<block id>"}]`),
so link-bearing writes stay small.

## Source of truth and tools (on branch `hypomnemata`, never merged)

`hypomnemata/nodes/<id>.yml` — to be re-cut to this model: `questions/<id>.yml` (q, ask, kind, state, lineage,
requires, pressure) and `theses/<id>.yml` (answers, assent, provenance, text, terms[{anchors[], to, deadlock?}],
traditions[{to, relation, note}], definitions[], applications[]). `tools/check.py`, `tools/pressure.py`,
`tools/render.py` follow the model above; the current implementations target the superseded flat schema
and are kept until re-implemented. The main thread transcribes `render.py` output to the doc; scripts never write the doc.
