Read this part at the opening, before the first write to the page's store, and before any write to `ordo/current`.

## The page

The round is put on a page. Its address is the `page` key of `.principal/notebook.json`, beside
`board`. It is the plugin's `web/ordo.html`, published once as a private artifact with the `db`
and `user` capabilities and rules under which only its owner reads and writes,

```
{"db": {"rules": [{"path": "", "read": "owner", "write": "owner"}]}, "user": {}}
```

so that anyone else, or anyone signed out, sees it empty. It has three sections in a fixed
order, the action context, the next action and the helpers' action context, and above them a
bell notice while a rung bell's office has an item of the principal's unresolved; beside them
stands the context panel. The page is display only: it has no input and one button, at its
foot, that goes back to the top and does nothing else; its source holds no data, and it writes
nothing. It reads four documents of the collection `ordo` in its
store, and the speaker writes all four, the day's marks included. Anything that needs the
principal's attention is presented here, in the next action, the action context or its log,
and the session's printed text, a log of operations only, never repeats it (rule 10).

On a wide screen the main column is on the left and the context panel on the right, kept in
view; on a phone the panel sits under the next action. The panel holds, in this order: "This
bell", the latest rung bell's name and time and its items still open or under way, the
principal's and those run by the session (marked so, and kept listed with their state once
resolved), "The office is complete." standing above them where no item is open or under way,
and while a pending action carries bells (rule 7), each carried bell under its
own name and time, earliest first, with its items, so that the panel reads the same set as the
card and the notice; "Next 48 hours", one timeline in time order under day
headings, of every bell still to ring in the next forty-eight hours and every event of
`ordo/agenda` not yet ended and starting within them, each tagged "Bell" or "Event", the next
bell the largest, tagged "Next bell", and an office item of a later bell never listed; and
last, when the calendar was read, or "No calendar has been read." where `ordo/agenda` is absent.
Below the panel, in the same column and kept in view with it, a second card holds only "Waiting,
in order (N)", the queue (rule 10), as a native details element closed by default, which the
page never opens or closes on a redraw.

Before any private data is written to the page's store in a sitting, where `ordo/current` does
not yet exist, as at the first sitting on a page, the speaker first `set`s it with `updated`
alone, which holds nothing private; then the speaker reads `ordo/current` with `ArtifactData` at
`as_level` `interact` and again at `admin`; where either read returns a document, the owner-only rule does not hold, and the sitting runs without a page
and says so. What is published is the page's source, which holds no data; the store is read
under the owner's rule alone, and this read is what tests it.

The speaker changes it by one small data write to the document `ordo/current`, with
`ArtifactData`, and never by republishing: a `set` of the whole document, pinned with
`if_version` to the version last read (the first `set`, of a document not yet there, without
it), when the action changes, so that nothing of the last one lingers, `next.deferred` aside
(rule 5); an `update` when one field alone changes, nested objects merging and lists replaced
whole. Each write sets `updated`, and the clock is read before it is stamped (procedure 3, rule
8). Before every write of `ordo/current`, whole or an `update`, the object to be written is
written to a file with the Write tool and checked with `tools/card.py check <that file>`; it is
sent only once the check prints `ok`, and a refusal is mended in the file and checked again,
never sent as it stands. The check refuses the shapes the page would draw wrong or blank,
and no others: a reading of tradition in `context.for` or `context.against` that is not an
object with `who` and `text`; a `context.prediction` out of its three parts; `paragraphs`,
`notes`, `heading`, `queue` or `background` out of shape; a time that does not parse; a write
without `updated`; a `next` that writes a field the card draws without its `kind` and
`prompt`, or whose `kind`, or a queue entry's, is not one of the four; a recommendation not
a string or a list of strings; a `next.deferred` without its `prompt`; an `office_deferred`
whose `since` is not a time or whose `bell` is not `HHMM`; and a `question` carrying a
recommendation, or a `question` or
`review` carrying a `how`. It refuses one thing more, which is not a shape: a `review` that
shows a question for the AI's own record names the question's `lead.json` as `next.reading`,
and is refused unless that record was written by `lead.py record`, is of the `question.md`
beside it, says `does not lead`, and that question is the prompt word for word (**The line in
the AI's graph**, rule 3). An `update` of `next.resolved_at`, `asks` or `deferred` alone
needs no `kind` or `prompt`. A refusal of the store is read and the document read again, never forced; where the write
still cannot be made, the session says so and says the thing itself, since the page cannot
carry it (rule 10). The bells and their office
items live in `ordo/rule`, which is the principal's private data: it is written only at the
principal's word, and never into this repository, a line doc, the board or anything published.
The day's marks live in `ordo/ticks-<day>`, which the speaker writes when the principal says in
the session what became of an item. The principal's calendar lives in `ordo/agenda`, which the
speaker writes at each sync, after reading the principal's calendar. A sync is an office item of
the Rule's with `by: "session"` at which the speaker reads the principal's calendar for the next
forty-eight hours and writes `ordo/agenda`. A speaker that holds no tool that reads the
principal's calendar, as the confined way's does not, writes no agenda and says so in the action
context, and the panel then says "No calendar has been read.".

Where `.principal/notebook.json` names no `page`, the sitting runs without one and says so, and
tells the principal to publish `web/ordo.html` once as above and put its address there as
`page` (**Before anything** gives the words): the round is put in the session's own words, in the order the page would show it, the action
context among them, and there are no bells.

**`ordo/current`**, an invented example:

```json
{
  "context": {
    "heading": "Your answer, as read",
    "paragraphs": ["The plants are watered before the post is opened, every day."],
    "for": [{"who": "One party", "text": "What that party says for the answer."}],
    "against": [{"who": "Another party", "text": "What that party says against it."}],
    "prediction": {
      "predicted": "Watering waits until the post is opened.",
      "diverged": ["The answer put watering first."],
      "addressed": "A case on the clause about mornings, at the next batch point."
    },
    "notes": ["A quiet note."],
    "at": "2030-01-02T03:00:00Z",
    "log": [{"at": "2030-01-02T03:04:00Z",
             "paragraphs": ["An addition made after the first writing, before the next answer."]}]
  },
  "next": {
    "kind": "question",
    "line": "Line: mornings",
    "case": "A morning on which the post holds a bill due that day.",
    "prompt": "Is watering the plants still first?",
    "put_at": "2030-01-02T03:04:05Z",
    "deferred": {"prompt": "Water the plants.", "reason": "Set aside for now: a passing feeling.",
                 "kind": "work", "line": "Line: mornings"}
  },
  "queue": [
    {"kind": "work", "prompt": "Water the plants."},
    {"kind": "review", "title": "Review the next rows"}
  ],
  "background": ["A helper is building a fix to the page."],
  "office_deferred": {"reason": "The letter first, for an hour.",
                      "since": "2030-01-02T08:20:00Z", "bell": "0800"},
  "updated": "2030-01-02T03:04:05Z"
}
```

- `context`, the action context: the last answer as the speaker read it, or the speaker's
  explanation, its answer to a question of the principal's, or its report of what was done, the
  brief and the close among them, a result the principal should know, an error, a helper's
  finding and a thing owed by the principal included (rule 10); `heading`; `paragraphs`, that answer, explanation or
  report;
  `for` and `against`, lists of objects with `who`, the party and its registry status, and
  `text`, shown under "Tradition on the result" after
  the paragraphs and hidden where both are empty; `prediction`, with `predicted`, `diverged` and
  `addressed`, each a string or a list of strings, shown after the tradition as "Predicted",
  "Where the result diverged" and "How the gap is addressed", an empty part left out and "No
  prediction was sealed for this action." where all three are; `notes`, quiet lines; `at`, the
  ISO time the context was first written, shown as a quiet line "Written HH:MM" under the
  heading; and `log`, the records appended to it before the principal's next answer (rule 10),
  each `{at, paragraphs}`, `paragraphs` a string or a list of strings, drawn last, in the list's
  order, each after a divider labelled "Added HH:MM", with the date where it is not today, a
  record without paragraphs skipped. The page keeps that order, heading, "Written", paragraphs,
  tradition, prediction, notes and the records, whatever the data's. Without `context` the
  section is hidden.
  `prediction` never holds the prediction of the action now put, which stays sealed until its
  answer is in.
- `next`, the next action: `kind`, one of `question`, `office`, `work` and `review`, any other
  shown as `work`, every kind shown alike but for its pill; `line`; `case`; `prompt`, the one
  field the card needs, without which it says "No action set yet."; `how`, a quiet last line,
  never set for a question or a review (rule 1); and `deferred`, an object with `prompt`, `reason`,
  `kind` and `line`, the action ranked first and set aside (rule 5), shown in the card under "Deferred,
  still first by the measure" beside the revised choice, also while an office is put, under
  "After the office", and not at all where its `prompt` is empty; its `kind` falls to `work` as
  `next`'s does; and `recommendation`, a string or a list of strings, the speaker's recommendation,
  shown under "Recommendation" after the prompt and only where set: every review
  of mechanism carries it here, its own field and never in the case, and a question, or a review
  that states or changes a principle, never carries one, the page showing none on a `question`.
  `put_at`, an ISO time with its offset, when this action was put, read from the clock and
  written in the same write only when a new action is put; restating, rewording or adding to
  the same pending action, its case, recommendation, `how` or context, keeps its `put_at`;
  `resolved_at`, an ISO time with its offset, written when the principal says in the session that
  this action is resolved, and counted only where it is not earlier than `put_at`; and `asks`,
  `false` on an action that asks nothing of the principal, a `work` placeholder for one, of any
  kind, and left out otherwise. These three tell the page whether the action holds the card
  through a bell (rule 7): a `next` put before the latest bell rang, not resolved, and not
  `asks: false`, is the pending action, and holds it.
  There is no checklist: a review is a `prompt` like a question's, answered in the
  session.
- `queue`, the actions after `next`, in order (rule 10), a projection of the open documents of
  the collection `lines` by their `rank` (**The open lines**): each a whole action with the
  fields of `next`, or a placeholder with `kind` and `title`, listed by its kind and its `title`, or its
  `prompt` where it has no title, as "Waiting, in order (N)" in its own card below the context
  panel, a details element closed by default; an entry with neither is dropped, and an empty
  `queue` hides the card. The page never moves the queue: when `next` is
  answered or done, the speaker writes the first entry as `next`, a placeholder made a whole
  action, and the rest as `queue`.
- `office_deferred`, the office set aside (rule 7): an object with `reason`; `since`, an ISO
  time; and `bell`, the base `time` of the bell set aside without its colon, `HHMM`, a
  `time_by_day` move not changing it. While `bell` names the latest rung bell, `since` is at or
  after the moment that bell rang on the current Rule day, and that bell still has an item of the
  principal's unresolved, the card shows `next` exactly as when no
  office is unresolved, and under its prompt a quiet block, "Office set aside, still due",
  lists the items left, a taken one marked under way, with the bell, the time it was set aside
  and the `reason`; a deferred action, where one is set, shows under it too. The notice stays,
  saying the office is set aside, and the panel's "This bell" is unchanged. Once a later bell
  rings, or every item of the principal's in that bell is resolved, the field is ignored, and so
  it is where `since` does not parse or is before that bell rang today, as on a later day; the
  speaker removes it in its first write after a later bell has rung or the Rule's day has turned.
- `background`, the helpers' action context: strings, what the helpers are doing, hidden where
  empty.
- `updated`: the time of the write, ISO 8601 in UTC, shown as the hour and minute it was made.
