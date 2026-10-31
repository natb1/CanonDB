---
name: interview
description: A questioner that has not read the notebook puts a question the principal answers, or the project's end, to the principal, in the principal's own words, one question at a time by the line, with tradition for and against each answer from the questioner's own knowledge, keeps a line doc of admissions and no transcript, and hands over to a comparing run in the checkout that reads the draw against the prior self and writes the plan. Invoke as /principal:interview [question|end] in a fresh session in the checkout.
disable-model-invocation: true
---

# /principal:interview [\<question\> | end]

A principal entry point that grants **nothing of the notebook**. It is the one place the
principal is the answerer and the AI the questioner, and it is the user's own version of the
clean context: a draw of what the user holds counts only so far as nothing in the room put it
there. So the questioner has not read the notebook, holds no graph or export of it, holds no
line doc of an earlier line, and holds the one question alone.

`<question>` is the id of a question the principal answers, `end` is the project's end, and
nothing is the root question. A second draw dates the first. Asked again from nothing, the
user may derive the same order again, and what comes back twice the same way is the position
rather than the draw; or may derive something else, and the difference is the finding, never a
reason to change the order in the moment. The order changes only by the user's own hand, by
dictation, after the reading and from level ground.

The run is one procedure with two parameters, who answers and whether the questioner holds the
notebook, shared with `/principal:dictate`'s line (its **The line** section) and with
`/principal:ask`. Here the principal answers and the questioner holds nothing; so the
comparing run that holds the notebook comes after, in the checkout, and is the dictate entry
point's.

## Before anything

- **A fresh session.** If this session has read the notebook document, a graph file, an export,
  a page of it, a line doc, or a transcript of an earlier interview, stop and say so. The draw
  would not be clean, and nothing can make it so in this session.
- **The right trigger.** The run is offered at the annual sitting, when a dependent's end was
  founded or changed, when the due reading lists a question of the principal's as due a draw
  again, and otherwise at a backstop that knows nothing of the moment. It is never run on the
  heels of a decision the question bears on: a draw taken right after a quarrel has the quarrel
  in the room. If the user says that is why they are here, say so, and offer the consult entry
  point instead, which reads the standing clauses and draws nothing.

## Procedure, the draw

**1 — The question.** `.principal/notebook.json` at the checkout's root names the project and
the canon file its root stands in (`canon`, a map from root to file under `canon/`). For the
root, read that file for the root question alone: the question's own paragraph, and nothing an
answer below it says. For `end`, read nothing: the question is what the project is for, put in
those words. For another question the principal answers, the user types the question, since
its tab is the notebook's and the run reads no tab; the run takes the words as typed. That is
all this run reads.

**2 — Put it.** Put the question to the user in its own words and wait. The user answers in the
user's own words; the run writes down admissions and nothing else.

**3 — Follow, by the line.** Each further question is drawn from what the user has just said
and from nothing else: a word the user used that could mean two things, a clause the user
stated that another of the user's clauses seems to cut against, an order the user named whose
members were not all placed, a case that would test a clause. From the second step on, each of
the questioner's turns has four parts in this order: what tradition says for and against the
previous answer, from the questioner's own knowledge and never from the notebook, each party
named and none given a registry status, since the registry is the notebook's; the digressions
pinned at this step, each with a brief response; references, if any; and the next step, a
question, a recognition of aporia, or a return from a digression. A contradiction between two
admissions is named where it stands. Never a question drawn from what the notebook says, which
the run has not read; never one that offers the user a formulation to accept. Stop when the
user says the answer is complete, or when a question would only restate what was already
said.

**4 — The line doc.** The record the run keeps is a line doc, as `/principal:dictate`'s line
keeps one: a document of admissions, never a transcript, each admission short, numbered, in the
user's words, with the sections that skill names, how the line is run, directives, admissions,
the line, held questions, aporiai, declarations, digressions, contradictions found, tradition
cited, decisions reached, and the plan, which this run leaves empty. Where the session grants
no document tool, the line doc is printed once at the end, in the same sections, for the user
to keep until the comparing run has read it. Nothing else is written.

**5 — Read back, and hand over.** Read back, in the user's words and in the user's order, what
the user said: the answer as a thesis, its clauses, the words it brought in, the cases and
their verdicts. Ask once whether that is what was said; correct it where the user says. Then
print the invocation the user runs in the checkout: `/principal:dictate` with the line doc as
its dictation, which asks for the comparing run below. Whether the draw agrees or diverges with
the standing answer is read in that run, which holds the notebook, and never here.

**6 — Keep nothing else.** No transcript, no summary in a file, no memory note. The line doc is
the one record, the user runs the comparing run over it, and that run retires it.

## The comparing run

Run by `/principal:dictate` over the line doc, in a session that holds the notebook. It reads
the question's standing answer and the draw beside each other and writes the plan as that
skill's compaction does, with these rows and no others:

- a further answer on the question, recorded with `assent: the principal's own prior, drawn
  again`, beside the one that stands, its clauses in the user's order;
- per clause of the draw, whether it agrees with the standing answer, diverges from it, or is
  new, read and said in the plan; a divergence is a finding and never a reason to change the
  standing answer in the same run;
- the traditions the prior pass lacked: each party the line doc cites that has no tab, or no
  edge to this question, as a tradition line and, for a party with no tab, a head to be born,
  every work `verified: unverified` until it is read against the text;
- each case the line put, with the user's verdict, the reason and the clause it tests, on the
  tab of the clause;
- for `end`, the end's words read against the hinge's end on the root: the same, narrower, or
  other, said in the plan and never written over the root without the user's dictation.

`tools/line.py check <doc.md> <graph.json>` passes before the plan runs: every admission is
cited by a row, every row cites an admission. The line doc is retired after the plan has run.

## Attenuation

- **The questioner holds nothing of the notebook.** A session that has read any of it cannot
  run this, and says so rather than proceeding. Nothing checks that but the session's own
  account of what it has read.
- **Questions come from the admissions.** The one leak that cannot be caught by a script is a
  question that carries the questioner's reading of the clause: cut every question that tells
  the user what was meant.
- **Tradition is the questioner's own, and is named as such.** What a party says for and
  against an answer comes from the questioner's knowledge, and is offered after the answer and
  never before it; whether the user takes it up is the user's. No registry status is given,
  since the registry is in the notebook and the notebook is not in the room.
- **The line doc is admissions, never a transcript.** No script tells a short admission in the
  user's words from a verbatim record; read every admission you write for length and voice.
- **The user's words stand.** The read-back is the user's words reordered, never improved. A
  word the user did not use is not in the line doc.
- **Agreement is not read here.** Whether the draw agrees with the standing answer is the
  comparing run's reading, with the notebook in the room; this run has no standing answer to
  read it against and does not guess.
- **No transcript, ever.** The interview is the user's and ends with the session; the line doc
  ends with the comparing run.
