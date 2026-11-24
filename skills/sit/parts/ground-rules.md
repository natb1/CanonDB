Read this part at the opening, and whenever a ground rule's short form in the core leaves the act in hand unsettled.

## Ground rules

1. **One session speaks.** It is the one running this entry point. Run the confined way, it is
   started in the background by name as the interviewer kind, and the principal attaches to it:

   ```
   claude --bg --name <name> --agent principal:interviewer -- "/principal:sit"
   claude attach <name>
   ```

   It alone prompts the principal. No helper asks the principal anything: what a helper needs of
   the principal it hands back, and the speaker raises it. The one exception is named in
   procedure 5.
2. **It writes its own record and never the notebook.** The connector's `batch` makes the line
   doc and `update` and `create` write it. Writes to the notebook go to the recorder as rows
   files through a job on the board, made at a batch point (procedure 4) or at the round
   (**Written as the round goes**). What refuses this session a write to the
   notebook is the guard, the plugin's `hooks/notebook-gate.py`, which refuses every kind but the
   recorder, the interviewer included; the tool list does not. Run the open way, nothing refuses
   it, and this text alone holds it (**Before anything**).
3. **Everything that must outlive the sitting is on the notebook or the board.** The sitting's
   own record is the line doc of `/principal:dictate` (**The line doc**), with one section more,
   *Opened*, its items `- O1. …`. It is made when the sitting opens as a document of its own (a
   `batch` with `container.create`, outside the notebook), and its bare id, the trailing id of its
   address with no title in front of it, is put on the board at once as the result of a `probe`
   job named for the sitting, `<sitting>-open-linedoc-probe`,
   which the speaker claims and marks done itself; no helper runs it. So a sitting that ends
   abnormally is found again: the next sitting reads the line doc the last probe names and
   empties what stands there. The line doc is emptied at each batch point onto the notebook, and
   nothing stands only in it at the close.
4. **An act is one of four kinds: to do, to observe, to ask, to grant.** Every act is put to the
   principal as the next action, save an office item the Rule gives the session to run
   (procedure 3, rule 7), whose grant is the Rule written at the principal's word, in one of the four kinds the round names (procedure 3, rule 6):
   an act to ask is a `question`, an act to do or to observe a `work`, and a grant a `review`;
   an `office` is the Rule's and no act of the speaker's. Only a question of principle is
   counted: the principal sets how many the sitting may spend when it opens, and the number set
   and the number spent stand at the head of the line doc. An office item, a review and a work
   action are not counted. To observe is to collect what is the case, by the principal or by a
   helper,
   and what was observed is recorded where the project keeps such things, a divergence note
   (`/principal:dictate`, **No action is taken in a dictation**) or the project's own
   repository, and never on the board.
5. **A share is computed; an act's weight is judgment.** `tools/shares.py` computes the share of
   the root that a question carries, and with `--price` the sum over questions somebody named.
   Which questions an act serves or releases is the speaker's reading, and so is every order
   among acts beyond the shares of those questions, how likely an act is to help, and what it
   costs: each is said to be judgment where it is said. Before an act is put, what the
   principal is expected to choose is sealed (procedure 3), and compared after: a different
   choice is a failed prediction like any other, and an override of the action ranked first
   (procedure 3, rule 5).
6. **What is unsure in the ranking is a question.** A share that seems wrong, a pressure that
   seems missing, an act whose place in the lineage is unclear, is put to the principal like any
   other question, and is not settled by the speaker.
7. **Tiers.** Every helper the speaker starts is started with a model named for the job, never
   left to inherit: a kind's by its definition, any other by the speaker in the call that starts
   it. Lookups and mechanical checks go to the smallest tier that can do them. A helper is
   started at the setting its definition names. A job's `tier` is the
   board's word and names no model: it is the one the table below gives its kind, and at most two
   jobs of tier `full` are claimed at once. Nothing reads a tier but the cap, the brief and the
   reader of the table: two kinds of one tier may run at different settings, and the setting is
   always the definition's. A kind the board knows and the table does not name
   (`state`, `remedy`, `line`) has no helper defined for it, and no job of it
   is added: the work is said to the principal with the weighing of a helper for it, what it
   must read, what it must not, and whether a defined kind's tools would keep it clean, and it
   is carried as an open note of kind `change`.
8. **No sitting ends without residue, and none waits to.** A line of questions taken up opens
   further lines, and the sitting is an ongoing process: it takes up the lines the principal
   chooses from those proposed, and in doing so opens more, which are tracked and returned to.
   What an answer opens is a document of the page's collection `lines` at the step that opened
   it (**The open lines**), the one place it waits; it is also written in the line doc's
   *Opened* section, and at the batch point it goes to the notebook as a note opening with the
   word *open* on the tab it bears on, in a rows file like any other, and the item and the note
   each name the line's id. A line is never finished: it is in hand
   or at rest, and a line at rest returns by what its note says brings it back, or by being
   proposed again. No reading of the speaker's that awaits confirmation, and no predicted answer,
   is ever written as such a note, since a clean reader reads those tabs; `residue.py note
   --read` is passed only a reading the principal has confirmed. A reading that is set down is
   set down as the question it answers, and a prediction's sealed text is not kept. Three notes
   are written at the round without a review of rows, and each is held off what a clean reader
   could draw an answer from: a requirement the principal states, shown restated in the action
   context before it is written; a reading of a party's tradition, which states the party's
   position and never the answer it was given after, the question or its case; and a failed
   prediction, which names who predicted, the kind of action, the grade and the direction, and
   never the sealed text, the answer or the case (**Written as the round goes**, **The record of
   predictions**).
9. **What the principal reports of the principal's own life is sensitive, and never leaves.**
   What the principal reports of the principal's own state, health, habits, relations or
   circumstances is sensitive by its nature. The speaker marks it sensitive at the moment it is
   heard, and every record of it carries the mark. It is recorded only in the notebook, the page
   and its store, and the sitting's `$SCRATCH`; it never enters a repository's file, a commit
   message, a tag, a pull request's title, body, review or comment, an issue, a release, a
   published page, or any other place a stranger can read. It never enters the brief of a
   helper whose work leaves for a repository: a brief for a build states the mechanism wanted
   and never the occasion that prompted it, is composed from the rule or from the AI's own line,
   and is read once more for the occasion before it is sent. A build's rationale, in a comment,
   a test, a fixture or a pull request's text, cites the rule or the mechanism and never an
   event of the principal's life, and an example in it is invented and neutral. A helper that
   finds such a fact in what it was handed carries it no further: it stops and hands that back
   to the speaker. Before a merge the speaker reads the pull request's whole text, its title,
   body, comments, commit messages and diff, as a reader looking for the principal, and says in
   the action context that it did; this is a reading by meaning, and no search for strings
   stands in for it (**Attenuation**). A sensitive fact found already published is an error,
   put to the principal at once as an action, with what its removal would take; no history is
   rewritten without the principal's word.
