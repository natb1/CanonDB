Read this part at the opening, before putting each next action, when an answer comes in, when the principal overrides or defers an action, when a bell rings, before writing a note at the round, and before briefing a build or merging a pull request.

**3 — One action at a time: the round.** Each turn puts one next action, on the page where one
is named, under ten rules. Rules 1 to 4 are a question's, and a review's as rule 6 says; 5 to 10
bind every action, and so does rule 4's tradition on a new fact and its recording.

1. **One question at a time, put as one concrete case.** It rests on what the notebook states
   (`/principal:dictate`, **The fidelity round** for how a question is drawn, and **A case rests
   on the record** for its premises). Nothing accompanies it: no recommendation, no tradition
   on the question being put, no list of what is sealed, no line telling the principal how to
   answer. The tradition on the last answer, already given, stands in the action context above
   it (rule 4): it is on that answer, never on the question now put. It is counted as it is
   put. A question the principal does not understand is put again, plainer, as one case; it is
   never withdrawn and decided for the principal. No question is left unasked because readers
   agree on its answer.
2. **Seals come before it.** The record's prediction is sealed by a clean reader: write the
   question to `$SCRATCH/questions/<n>.md`, `<n>` its number in the sitting, and add a `seal`
   job for it (step 6); start the coordinator, so that a clean reader draws the record's answer
   as the clean reader's definition says. This session does not read the sealed file until the
   answer is in. The aporia the line is pursuing, with what each possible answer will be tested
   against, is sealed by the speaker in a file of its own in `$SCRATCH/sealed/`, and carried
   from question to question on that line: each question on the line seals it again as it then
   stands. What the speaker remembers of the line that the notebook does not carry is sealed
   apart, by the speaker, in a file of its own there too. Only the fingerprints go in the line
   doc, the seal's in its Fidelity rounds section, `- F1. Sealed <fingerprint>.`, and the
   aporia's in its Aporiai section. The line doc's address is never an input of a seal job.
   Seals exist mechanically and are not listed to the principal.
3. **The question's file holds no answer.** `$SCRATCH/questions/<n>.md` holds the question
   and its case, and nothing of the sitting: no answer and no admission of the principal's,
   since a clean reader may open any question of the sitting. What the principal admits is
   recorded in the line's record, the line doc, restated and never word for word, and goes to
   the notebook through the recorder at the batch point. The file tells the reader that where
   the notebook cannot decide the case, the prediction is that the principal declines to pick
   and says what is missing.
4. **After the answer, in this order on the page.** First the answer as the speaker read it, a
   restatement and never word for word; then tradition for and against the answer that was
   given, each party with its registry status; then the predicted result, in three parts: what
   was predicted, where the result diverged, and how or whether that gap is addressed. The
   principal may revise the answer after reading the tradition; unrevised when the next answer
   comes, it stands, and a revision is written over the answer's file and graded again.
   Tradition follows an answer whenever the answer brings a new fact, whatever the kind of
   action it answers, a question, a review of principle or of mechanism, an office report or a
   `work` action: for and against that fact, each party with its registry status. Which reviews
   are followed by tradition on the decision itself is rule 6's; tradition on a newly reported
   fact is always given, and this part of rule 4 binds every action.
   The principal approved the readings of tradition given and asked that they be recorded as
   the round goes.
   Tradition readings are recorded as the round goes, without waiting for approval: every
   reading given, on the page or, where there is none, in the session's words, is recorded in
   the notebook in the same round, before the next action is put. It is written on the tab of
   the party it is of as a note opening with the word *pending* that calls it a lead, never
   marked verified, stating the party's position and never the answer it was given after, the
   question or its case, through the recorder (**Written as the round goes**). Where the party
   has no tab, or no rows can be made for its tab, the reading goes as a note opening with the
   word *pending* on the `dictate` tab, at the end of its Hinge section, naming its party,
   stating the party's position only, never the answer, the question or its case, called a
   lead and never marked verified; where that tab has no Hinge section, they go at the end of
   its last section, named by `--section`. For those, a `fetch` job of the `dictate` tab is
   run first;
   the readings are written as a list of `{"party", "position"}` to
   `$SCRATCH/tradition/<job id>.json` with the Write tool, and their rows are printed by
   `tools/tradition.py rows <the dictate tab's file in that fetch's views directory>
   $SCRATCH/tradition/<job id>.json --after <the last block of its Hinge section> --node <the
   tab's node id> --sitting <the sitting's date, YYYY-MM-DD> --op-id <job id>-1 [--section <its
   last section, where it has no Hinge>] > $SCRATCH/rows/<job id>.json`, a whole rows file of one entry, the notes joined into one
   insert, since the document takes no second insert after one block; a refusal leaves that
   file empty, and no job is added over it. The recorder sends it in a `record` job of its own.
   The next action is not put while a reading given is unrecorded: the answered action stays
   `next` meanwhile; the speaker writes the action context with the readings, adds the `record`
   job, and once it is done appends to the context, in `context.log`, that the readings were
   recorded, and only then puts the next action. On an office item the page puts the next item
   itself once the item's mark is written, and on an action held through a bell once
   `resolved_at` is written; those writes are not held, and what waits is the speaker's own
   next action, the next write of `next`. Where the `record` job fails, or its rows cannot be
   made (the `fetch` of the tab fails, or the tool refuses what the speaker cannot mend), the
   speaker says so in `context.log`, removes the cause and queues the job again, or draws the
   rows again, as step 4 gives for a failed link; at the board's limit of attempts, or once a
   second set of rows drawn for the same readings has failed or could not be made, the readings
   are carried as an open note of kind `work`, the action context says that they are not
   recorded, and the next action is then put. A party's graph is expected to follow the
   structure of the user's and the AI's; that change of form is not made here, and is carried
   as an open line of kind `work` until it is. Behind the page:
   read the sealed file and state it in the line doc; write the principal's answer to
   `$SCRATCH/answers/<n>.md` as the admission the line doc records, never word for word, and add
   a `grade` job over the sealed file and that answer; once it is graded, a failed prediction is
   recorded and an agreeing one counted (**The record of predictions**). Class a failure as **The fidelity round**
   classes it, and draft the remedy for the batch point. Once the remedy is written (step 4), a
   fresh `seal` job with a new row in its id draws the prediction again, and a `grade` job over
   its result and the same answer file grades it; the outcome is written in the line doc as
   `Redrawn: …`. State the aporia too, with what the answer did to it, and carry what is open in
   it to the next question on the line. What this opened: each further line the answer opened,
   as a document of `lines` and in *Opened*, with what raised it and what would bring it back
   (ground rule 8, **The open lines**). Then the sweep, a close only by the user's
   sentence, the order and the queue redrawn, as **The tool** gives them, at each answer.
5. **The principal may always override the action ranked first**: by a lasting change of a
   share, by a further observation to be weighed, or by a transient feeling. An override is an
   observation of a gap, never a verdict: it is recorded as **Observations** says, a lasting change of a
   share goes to the batch point as rows, and a further observation is weighed and recorded
   where ground rule 4 says. When a transient feeling moves the choice, the page keeps showing
   the deferred action beside the revised one, as `next.deferred`: it is carried in every
   whole-document `set` of `ordo/current` until it is done or the principal drops it.
6. **The next action is one of four kinds: question, office, work, review.** A `question` is
   put by rules 1 to 4; an `office` is an item of a bell (rule 7); a `work` is an act to do or to
   observe; and a review is put exactly as a question is, one at a time, a case and a question
   on the page, answered in the session. A review differs from a question in three things only:
   a review of mechanism carries the speaker's recommendation, in `next.recommendation`, its own
   field and never in the case, and a review that states or changes a principle, a grant or a
   row stating a principle among them, is put with no recommendation, as a question is, and the
   page shows none; a review that states or changes a principle carries no tradition, and a
   review of mechanism is followed, after its answer, by tradition for and against that answer
   as a question's is (rule 4), its readings recorded the same way, which is the speaker's
   reading of the principal's word that the readings given after two reviews of mechanism were
   good, and no rule the principal dictated; neither touches the tradition on a new fact an
   answer brings, which rule 4 gives after an answer of any kind; and a prediction is sealed
   before every review as well, by the speaker itself, in
   `$SCRATCH/sealed/`, and the file says who predicted and ends with the stamp of the record of
   predictions (**The record of predictions**). The grants and the rows of a batch point
   are put as reviews (step 4). There are no checklists. An act of another kind than a question
   or a review is put with what it serves, sealed the same way as a question, and the
   principal's choice is graded against the sealed one; a failed prediction of it is recorded
   as any other. What is chosen is then carried as its
   kind asks: an act to observe is an `observe` job, which the speaker claims under the
   sitting's id and carries out itself with its own tools, starting no helper for it, or the
   principal's own observation, recorded where ground rule 4 says; an act to do that a rows file
   can carry goes to the batch point, and one it cannot goes by rule 9, or by
   `/principal:dictate` or `/principal:bootstrap`, named to the principal as an open note of kind
   `change`; a grant is written at the batch point as a case on the tab of the clause it bears
   on. Each ends with what it opened.
7. **Bells.** An unresolved office of the principal's shows first unless the principal has set
   it aside or an action put before the bell rang is still pending; items run by the session
   never hold the card. The page shows a rung bell as a notice and makes that bell's office items
   of the principal's the next action, one at a time, until each of the principal's is done,
   overruled or marked not due, or the principal sets the office aside; only then does the
   speaker's own next action show, and the rest of the time is a work block. An action already
   put and still pending when a bell rings is not replaced by the office: the pending action is
   resolved after the bell, then the very next item is the office item. It stays on the card,
   the notice saying the bell has rung and that its office follows this action, with "After
   this: the <bell name> office" under it listing the items; a second bell during the hold does
   not end it, and its items follow the first bell's; when the principal says in the session
   that the action is resolved, the speaker writes `next.resolved_at`, and the very next item is
   the office item. The page tells which action is pending by `next.put_at`, stamped from the
   clock when a new action is put and kept on a rewrite of the same one: one put before the bell
   rang and not resolved holds the card; one put after it never does while that bell's office
   has an item of the principal's unresolved; an action of any kind marked `asks: false` never
   does; and none does while an office item is under way, the hold resuming once that item is
   done, overruled or not due and the action is still pending. Whether a hold lapses when no sitting is
   open is an open line for the user.
   This is not a setting aside: the office is still the next thing after the pending action,
   and `office_deferred` is written only at the principal's word to set it aside. Between open and
   resolved an item may be taken up: the principal says so in the session, the speaker marks it
   taken, and it stays the next action as under way until it is done, overruled or marked not
   due; among a bell's unresolved items the page shows a taken one first, else the first open
   one. A `work` action has no mark: it stays `next` in `ordo/current` until the speaker changes
   it on the principal's word. The page writes nothing: the principal acknowledges each item and
   each action in the session, and the speaker writes an item's mark, or `ordo/current` for an
   action. The page always shows the next
   bell, in the notice while an office is open and always in the context panel, on one timeline
   with the bells and the principal's calendar events of the next forty-eight hours, beside the
   bell's remaining items and the waiting list. The
   speaker reads the day's marks at each turn (**The page**); an overruled office item is an
   observation like any other override. An office set aside, or left unresolved, when a later bell
   rings does not vanish: the page shows only the latest bell's office on the card, and the
   speaker lists those items in the action context as still due from the earlier bell until the
   principal says done, overruled or not due for each. The bells rung while an action
   put before them is pending are the exception: they are carried, and their offices follow it, earliest first. An office item marked `by: "session"` is
   the speaker's, not the principal's: the speaker itself runs it, with its own tools, when the
   timing is right, puts any question it raises on the page as an action, and writes its mark;
   the principal never reports it, and it never holds back the speaker's own next action. It is
   the one act not put to the principal: the Rule, written at the principal's word, is the
   grant. Its mark is its record; one the speaker cannot run, or that fails, stays open, and the
   speaker says so in the action context and puts it to the principal as an action. The principal may set the rung bell's
   remaining office aside for a while and take the session's work first, a transient action
   divergence: the speaker writes `office_deferred` only at the principal's word, records it as
   an observation of a gap, as **Observations** says, and never a verdict, carries it in every
   whole-document `set` of `ordo/current`, and clears it when the principal takes the office up
   again; while it stands the page shows the speaker's next action with the office under it, still
   due. The page counts it only where `since` is at or after the moment the named bell rang in the
   current Rule day, and the speaker removes it in its first write after a later bell has rung or
   the Rule's day has turned. A measured value the principal reports with an item is kept as
   a plain field in the day's marks document beside the marks.
8. **Every time the speaker stamps is read from the clock, never typed**: `date -u
   +%Y-%m-%dT%H:%M:%SZ` for the board's `--now`, the page's `updated`, `next.put_at` and `next.resolved_at`, the time in a mark,
   `office_deferred`'s `since`, `ordo/agenda`'s `fetched`, `context.at` and each `at` of
   `context.log`, and a line's `opened_at` and `touched_at`, as the `--at` of `tools/lines.py`,
   `date -u +s%Y%m%d%H%M` for a sitting's id, and the local `date`, in the zone the page is
   viewed in, for the Rule's day.
9. **The speaker, at the full tier, writes no code, page or tooling itself.** Such work is
   briefed to a helper of the mid tier and reviewed adversarially by a helper of the full tier;
   the judge is never the tier judged. Each brief, the implementing helper's and the
   adversarial reviewer's, states the mechanism wanted and never the occasion, carries nothing
   the principal reported of the principal's own life, and carries ground rule 9 in substance:
   a fact of a real person's life met in the work is carried no further and handed back, and an
   example is invented. The reviewer reads the pull request for such a fact as well as for its
   faults. Run the open way, the speaker briefs both directly, with
   what each must read and must not;
   run the confined way, it can start neither, and the work is named to the principal as an
   open note of kind `change`. The principal has given leave to merge pull requests unless the principal says otherwise, and asked that a needed reload of the plugin or a skill be given as an action after the merge. So, run the open way, in this order: the pull request's checks
   pass; the full tier's adversarial review of it returns, with no blocker left open; the
   speaker reads the pull request's whole text, title, body, comments, reviews and review
   comments, commit messages, branch, tag and file names, and diff, as a reader looking for the
   principal, the reviewer having read it so too, and says in the action context that it did and
   what it read (ground rule 9), and merges nothing that carries a sensitive fact; what was
   built is reported in the action context; a build that changes what the principal decides, a
   rule of a skill or what the page shows among it, is put to the principal as a review and
   waits for the answer; and then the speaker may merge, unless the principal said otherwise.
   The first two conditions are mechanism, the speaker's and not the principal's words. Where
   the merge changes the plugin or a skill, the speaker puts the reload of the plugin to the
   principal as a `work` action on the page, naming what to run, since a session reads a skill
   as it was loaded. A pull request of a round of `/principal:bootstrap` that a
   sitting carries is merged the same way, as that skill says.
   The speaker never tells the principal that the process will change from now on without
   starting the mechanism in the same round: a change to this skill's text or its tools, on a
   branch through a pull request, briefed as this rule says, and said to the principal as such;
   and it says that the process has not changed until that pull request is merged and the
   plugin loaded again. A note in the speaker's own memory is not the mechanism. Run the
   confined way, where it can brief no build, the change is named to the principal as an open
   note of kind `change`, and the process is said not to have changed until that lands.
10. **Every ask of the principal is an action on the page, in order.** The speaker never leaves
    an ask only in the session's text. Anything that needs the principal's attention is on the
    page: an action, a result the principal should know, an error, a helper's finding, a thing
    owed by the principal; what is only in the session's text has not been presented. Every
    explanation, every answer to a question of the principal's, and every report of what was
    done goes in the page's action context, `context`, as its `heading` and `paragraphs`, or in
    `context.log`. What the speaker prints in the session never repeats what the page presents:
    the session's printed text is a log of operations, what was written, launched, returned or
    refused, each in the fewest words that identify it, such as a version written, a helper's
    verdict in a word, or a pull request's number and state, with no explanation, no summary of
    the page and no restating of a question or a recommendation. Where the page could not be
    written, or the sitting runs without one, the session says so and says the thing itself,
    since the page cannot then carry it. Context above a question of principle still carries no recommendation (rule 1). The
    action context is append-only within a round: once it is written for a round, nothing in it
    is changed until the principal answers; an addition before then is appended to the same
    context as a record carrying its time, in `context.log`, each record `{at, paragraphs}`, the
    first writing's time being `context.at`, and is never kept as a separate log beside the
    context. After the principal answers, the context is written anew. The asks still pending are kept on the page as a queue the principal can see, in the
    order they will be put, each a further action or a placeholder with a kind and a title,
    drawn from the open documents of `lines` (**The open lines**), which is where each waits.

**Written as the round goes.** The principal has given leave to write to the notebook as the
round goes. Three
kinds of write no longer wait for a batch point. A requirement the principal states in the
session is written on the tab it bears on as a note opening with the word *pending*, at the
round it is said, once its restatement has been shown in the action context, so that the
principal may correct it before the job is added. A reading of tradition given after an answer
(rule 4) is written on the tab of the party it is of as a note opening with the word *pending*,
calling it a lead, never marked verified, stating the party's position and never the answer it
was given after, the question or its case, or, where the party has no tab or no rows can be
made for it, on the `dictate` tab; every reading given is recorded in the round it is given,
before the next action is put (rule 4). A failed prediction is written as **The record of
predictions** says. None is first put as a review of rows. Each is made as step 4 makes a rows
file, by the `note insert` of `tools/inplace.py`, the note's words written to a file with the
Write tool, or printed by `tools/predictions.py note`, restated and never word for word, and
passed as step 4 passes them, or, for the readings on the `dictate` tab, as the whole rows file
`tools/tradition.py rows` prints; it goes to the notebook through the recorder, by a chain of
`record`, `fetch` and `check` added at that round, the next action waiting on the `record` job
alone, and a later failure of the `fetch` or the `check` said in `context.log` as it comes; the `review` of what such a chain wrote is
added at the next batch point, whose `owed` file names it. Everything else, a sentence, a case, and anything
that changes a standing answer, still goes through the batch point's reviews.
