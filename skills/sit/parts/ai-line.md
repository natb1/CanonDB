Read this part before a question for the AI's own record is drafted or put, before a clean turn or a `lead`, `turn`, `compare` or `place` job, before any build is briefed, and before a constraint is treated as binding.

**5 — The AI's own turns.** A question for the AI's own record is a `turn` job, its `line` the
question's directory (**The line in the AI's graph**). One drafted on the user's side is held at
once with `wait`, `tools/board.py wait $SCRATCH/speaker/board <id> --versions
$SCRATCH/speaker/versions.json --now <time> --out $SCRATCH/speaker/out`, until the principal
approves it on the page, shown word for word as its own action (**The line in the AI's
graph**, rule 3); then it is queued again with `resume`, `tools/board.py resume
$SCRATCH/speaker/board <id> --versions $SCRATCH/speaker/versions.json --now <time> --out
$SCRATCH/speaker/out`. One a drawer turn raised needs no approval and is queued as it is added.
The speaker claims a `turn` job under the sitting's id and runs it itself with
`tools/clean_turn.py`, starting no helper for it, and marks it done with its manifest as the
`reply`. No other session puts a question to the AI's record.

## The line in the AI's graph

The AI's own record is a graph of the AI's answers, in its own words. Its tabs stand under a root
of their own in the notebook, and the key `ai_root` of `.principal/notebook.json` lists them, the
root's first, each as its body's node id and its own tab id; until the root is made the key is
unset, and the guard on the notebook refuses the `ai-recorder` every write but the root. The AI makes the
tabs under its own root, the root among them, and no dictation is needed for one; the speaker
makes none, and never writes the notebook. Every tab of the AI's is made by the `ai-recorder` in
a `place` job, holding its heading, `# <name>`, and nothing else, its name the id of a question of
the AI's record that names neither the user nor anything private; the question's words and what
answers it are inserted on it after, by a `place` job like any other. The root is such a
question: one the speaker drafted and the principal approved (rule 3), its id the root's name.
While the key is unset, `tools/ai_tab.py root --name <question id> > $SCRATCH/lines/<line>/root.json`
prints the rows entry that makes it, at the top level, in the form `tab` prints with `node` null,
sent with the one operation id every root of the notebook gets, so that a second lands as the
first; the guard admits the `ai-recorder` that batch while the key is unset and refuses it once the
key is set. A tab under the root is made from `tools/ai_tab.py tab --parent <node id> --name
<question id>`, which prints a rows entry that makes it under the tab of the AI's whose node id is
given, which the key must list with its tab id; the guard lets the `ai-recorder` that batch and no
other shape of it, under no other tab. A tab made is the AI's to the guard only once the speaker,
from the ids the `ai-recorder` hands back for the batch's aliases, written with the Write tool as
`{"lids": {"f": <the tab's id>, "n": <its body's node id>}}`, runs `tools/ai_tab.py add --made <the
entry> --answer <that file>`; until then nothing is inserted on it. `add` takes only an entry it
prints again, the same, from the key as it stands, and says what it could not check: that the ids
are the ones the connector made, which the tab read back shows. The key's change
reaches the repository's main only through a pull request. An answer of the AI's given before the root, past held on
a tab wherever it stands, is the AI's too. A line is a run of questions put to that record. Each
is put in a clean turn: a run of the harness of its own, started by `tools/clean_turn.py` in an
empty directory with no tools, settings, memory or rules file, whose context holds the AI's own
earlier answers, as `tools/packet.py` writes them, and one question, and nothing of the user's
record. A clean turn is never a helper of this session: a helper started from a session carries
that session's memory, rules file, git status and skills. Before the sitting's first clean turn
the speaker runs `tools/clean_turn.py probe`; where it exits other than 0 no line is drawn, and the
speaker says so in the action context.

Each line has a directory, `$SCRATCH/lines/<line>`, holding `requirement`, the names of the tabs
of the user's record the line is drawn for, one name a line; one directory for each question, in
the order they are put, `$SCRATCH/lines/<line>/<n>`, `<n>` counted from 1; one for each drawer
turn, `$SCRATCH/lines/<line>/drawn-<n>`; and `index`, every file of the line by its absolute
path, one a line, which the speaker writes again, with `find $SCRATCH/lines/<line> -type f !
-name index ! -path '*/held/*' | sort > $SCRATCH/lines/<line>/index`, which leaves out what the
line set aside (rule 4), before it adds a `compare` or a `place` job,
since the helpers of those kinds cannot list a directory. A question's directory holds its
packet, `tools/packet.py $SCRATCH/graph.json --under <id> --line $SCRATCH/lines/<line> -o
$SCRATCH/lines/<line>/<n>/packet.md`, with the fingerprint the tool writes beside it; its words,
`question.md`, written with the Write tool; its leak record, the record of its reading
(rule 3) and its origin; and its draws, in `draws/`. The packet holds the AI's answers of the tab `<id>` it stands under and above it, then
the line's own earlier questions and answers, in the order they were put, each answer under the
question it was given to, marked `<<< question >>>` and `<<< answer >>>`: a question of how
reaches the answer of why above it on the line, however many questions deep. Several draws are
kept for each question and none is chosen by what it says, so the rule is fixed in advance: the
first draw a question's manifest lists as kept is the answer of record, the one every later
packet carries; the others are the evidence of whether that answer is stable, read by the
comparing run, and never carried. Where the line stands under no tab of the AI's yet, the packet
is `tools/packet.py $SCRATCH/graph.json --line $SCRATCH/lines/<line> -o
$SCRATCH/lines/<line>/<n>/packet.md`, the line's alone, which is also the back-brief's. A drawer
turn's packet is cut by the same line as the question it draws under, into
`$SCRATCH/lines/<line>/drawn-<n>/packet.md`. The packet holds no hinge, glossary, note, case,
application line or anything else written on the user's side; the tool refuses a question of
the graph the AI does not answer, or that holds no answer past held, a graph on which
`only-ai-put` or `state-order` fails, a gap in the line, a draw that does not match its manifest
or its question, and a question or an answer holding `<<<` or `>>>`, which no text may forge.

1. **The order.** The principal's requirement is recorded on the user's side first, on the tab it
   bears on, at a batch point. Then a line is drawn in the AI's graph. Then the comparing run, a
   `compare` job, reads the line against the user's record. Then the build, whose brief cites the
   AI's answers by their opening words and never the principal's requirement. Then the build is
   checked against the record, by a `compare` job over the line with what was built. Nothing is
   built straight from the principal's words unless the principal asks for that explicitly, once,
   as an action on the page, for that one build.
2. **Intention is carried by the line.** Every line opens at the purpose: what the thing is for,
   and what it must never do. A question of how stands only beneath an answer of why. Each answer
   names the answers it rests on, on its `Rests on:` line. Before any build a back-brief is
   drawn: a clean turn over the line alone restates what the thing is for, what it must never do
   and what failing would look like, and the comparing run reads it against the user's record. A
   difference of intention is repaired by drawing again higher up, never by correcting the
   mechanism. Some cases are held back from every question, kept on the user's side, and used
   only to test that the design generalizes; one of them is a case where the letter of the
   mechanism and its purpose part.
3. **Two kinds of question.** A question drafted on the user's side, the opening question, a
   case's situation or a statement of the principal's position, is checked first, with
   `tools/public.py question $SCRATCH/graph.json $SCRATCH/lines/<line>/<n>/question.md --record
   $SCRATCH/lines/<line>/<n>/leak.json`, which refuses a question that spells a masked tab's
   address or breaks the notebook's rule for naming the user, saying what it found, and looks
   for no run of the user's words; its presuppositions are listed on the user's side, in the
   line doc and at the batch point on the tab it bears on. Then, before it is shown to the
   principal, it is read for whether it leads the answerer, in a `lead` job (**Which kind runs
   which job**) whose inputs are `notebook`, `question`, the path of `question.md`, and
   `question_fingerprint`, its SHA-256 as it stands: `tools/lead.py job --question
   $SCRATCH/lines/<line>/<n>/question.md --id <job id> --notebook <the notebook's address> >
   $SCRATCH/speaker/jobs.json` prints the jobs file the board's `add` takes (**How jobs reach the board**), and refuses a text
   already read, since one text is read once. The coordinator hands the path and the
   notebook's address to a `question-reader`, which holds that file and the notebook and
   nothing else and judges by meaning whether the question hands over an answer, a design or a
   position of the user's record, so that the reply would echo that record instead of being the
   AI's own. Stating a problem and the ends to be served is not leading; sharing words with the
   record is not leading. It hands back a verdict, `leads` or `does not lead`, and one reason
   that neither quotes nor paraphrases the notebook, and proposes no rewording. Once the job is
   done and the board exported again, `tools/lead.py record --question
   $SCRATCH/lines/<line>/<n>/question.md --board $SCRATCH/speaker/board --versions
   $SCRATCH/speaker/versions.json --job <job id> -o $SCRATCH/lines/<line>/<n>/lead.json` writes
   the record of the reading, which the clean turn demands; a refusal leaves whatever record
   stood there as it stood. Where the hooks attest no run of the reader for the job, or the job
   failed, the job is never retried under its id: a new `lead` job, under a new id, is added for
   the question, and a launch left from the old one cannot answer for the new. A question read as
   `leads` is never shown, and its record is final for its number: the speaker sets it aside
   with `tools/lead.py aside` (rule 4), reads the reason, drafts the question again itself at the
   same number, and checks it and reads it again in a new `lead` job. Once three drafts of one
   question have been read as leading, no draft is read again (`lead.py` refuses it): the speaker
   puts it to the principal as one action, saying that the question could not be drafted without
   leading. Only a question read as `does not lead` becomes its own action on the page, a
   `review` whose prompt is the question word for word, its `next.reading` the path of its
   `lead.json`, for the principal to approve or revise; `tools/card.py check` refuses such a
   card unless that record is of exactly the question the prompt shows and says `does not lead`,
   and the question is put to the AI only on that approval. A revision is written over
   `question.md`, checked and read again before it is shown again, and only the text the
   principal approved is put. On that approval the speaker writes
   `$SCRATCH/lines/<line>/<n>/approval.json` with the Write tool, `{"sha256": <the fingerprint
   of the question file as approved>, "approved": <the time, from the clock>}`, and the clean
   turn refuses any other text, a reading of any other text and a reading that it leads. It does
   not compare the approval's time with the reading's: a question approved before a reading
   existed, as on a line drawn before readings were recorded, is put once a reading of exactly its
   text says it does not lead. A question the AI's own record raises comes verbatim from
   a drawer turn, `tools/clean_turn.py draw --packet $SCRATCH/lines/<line>/drawn-<n>/packet.md
   --out $SCRATCH/lines/<line>/drawn-<n>`, and needs no approval and no reading, being the AI's
   own words over a packet that held nothing of the user's; it is still checked by `public.py
   question`, and the clean turn refuses it unless it stands as a line of that drawer's run. Case situations go to the AI's record as questions; verdicts and reasons stay
   on the user's side, with the comparing run. The clean turn refuses a question in which a
   token opens with `@`, which the harness would expand into a file of the machine, and one
   that opens with `/` or `!`; every prompt it sends opens with a line of its own.
4. **Draws.** Each question is drawn several times, `tools/clean_turn.py answer --packet
   $SCRATCH/lines/<line>/<n>/packet.md --question $SCRATCH/lines/<line>/<n>/question.md --out
   $SCRATCH/lines/<line>/<n>/draws --approval $SCRATCH/lines/<line>/<n>/approval.json --lead
   $SCRATCH/lines/<line>/<n>/lead.json --leak $SCRATCH/lines/<line>/<n>/leak.json`, three by
   default, or with `--drawn-from` the drawer's `draw-1.json` in place of `--approval` and
   `--lead`. All are kept, none is chosen by what it says, and
   the first kept is the answer of record (above). Where they part in what they would do, that
   is the finding, and the question is drawn higher. A question whose draws were all refused is
   put again under a new number, or dropped, before the line goes on: the packet refuses a gap.
   A question found later to have led all the same, on a later reading or at the principal's
   word, cuts the line there. The speaker records it with `tools/lead.py led --question
   $SCRATCH/lines/<line>/<n>/question.md -o $SCRATCH/lines/<line>/<n>/lead.json`; the packet
   then refuses the line at that question, and refuses too a question put on a reading whose
   record is gone. Then `tools/lead.py aside --line $SCRATCH/lines/<line> --from <n>` sets
   aside together the led question and every later question of the line, whose packets carried
   its answer, and every drawer turn whose packet carried any of them: their directories are
   moved under the line's `held/`, nothing renumbered by hand and nothing deleted, and the tool
   prints what it set aside and which of it was placed. The line goes on from that number with a
   newly drafted question, read like any other; the packet, `hinges.py` and the index read the
   line without what was set aside, and without a gap. A question read as `leads` before it was
   shown is set aside the same way, alone. An answer already placed in the AI's record from a
   question set aside stays on its tab, carried by the graph's part of every packet, until it is
   taken off, which no tool here does: each is carried as an open note of kind `change`.
   A draw whose answer holds a packet's mark or a token opening with `@` is refused and not
   kept, like one that gives the account away, since no later packet or turn could carry it; the
   next kept draw is then of record by the same rule. A packet cut into
   `$SCRATCH/lines/<line>/<n>/` is for question `<n>`: the clean turn takes it only with that
   question's `question.md` and `draws/`, and only while the line, read again, carries what the
   packet's fingerprint says it carried; otherwise the packet is cut again.
5. **On a divergence.** The comparing run hands back only the redraw signal, the opening words of
   the AI's answer under which the divergence sits, and the speaker passes those words and
   nothing else of its reply to the drawer, `--from "<opening words>"`, over a packet that
   holds that answer, the graph's or the line's; the drawer refuses words that do not open
   exactly one answer of the packet, or hold fewer than four words. After two redraws of one
   divergence, the default, either the principal states a position, which stands in the AI's
   record in the principal's words by way of a further approved question, or the line cannot be
   built, and that is put to the principal as one action: the case, what the AI's record
   reached, where it parts, and four choices, a further question, a stated position, a build
   straight from the notebook as a stopgap, or the principal does it.
6. **A budget of clean turns.** A line spends at most twenty-four clean turns, the default, each
   draw, drawer turn and back-brief one; the principal may set another number when the line
   opens. The speaker reports in the action context, at each batch point and when the line rests,
   the turns spent against the budget and the cost the draws recorded. A line that reaches its
   budget stops there, and is put to the principal as the one action of rule 5.
7. **What is acted on is the AI's action.** What is acted on from the AI's record is recorded on
   the page, in the action context, as the AI's action, naming the answers it rests on by their
   opening words, so that the principal is prompted to review it.
8. **Four signals before a constraint binds.** Before the speaker treats any constraint as
   binding it tests four signals and says which apply: marked stale by a later note; a mechanism
   standing as a principle, its source an application line, a skill or a helper's definition,
   this one among them; its price, the divergences recorded on it, beside the share it carries;
   and unjustified, no edge to a principle nearer the root, which for a hinge of the AI's graph
   `tools/hinges.py unjustified` lists (rule 10).
9. **What is recorded.** The answer of record of each question on a line is placed in the AI's
   record with its question, its answer word for word and its presuppositions: `tools/hinges.py
   place $SCRATCH/lines/<line> --n <n> --under <id> > $SCRATCH/lines/<line>/<n>/place.json`
   prints them in the notebook's own form, the question, its one answer, and the hinge's two
   parts: what the asking presupposes, each presupposition on a line of its own ending
   `(unjustified; came in by <line>/<n>)`, and what the answer was drawn from, from the draw.
   `--line-name` names the line where its directory is not named for it. A draw made before
   the answerer gave its presuppositions one a line gives them on the label's own line, and
   the tool parts them there; nothing is redrawn for it. It reads the line's directory alone, and nothing of
   the user's record. A placed question is a tab of its own under the tab the line stands
   under, made by the `ai-recorder` in a `place` job from the entry `tools/ai_tab.py tab
   --parent <id> --name <question id>` prints, and put in the key by the speaker after
   (above); a new tab of the AI's own record needs no dictation. The answer, its question
   and its hinge are then inserts on that tab, which holds its heading alone: `tools/hinges.py
   rows $SCRATCH/lines/<line>/<n>/place.json --line $SCRATCH/lines/<line> --line-name <line>
   --node <node id> --kind <kind> --read <the tab's read> > $SCRATCH/rows/<job id>.json`
   writes the rows file of the `place` job that places them, a list of one entry: `<node id>`
   the tab's body as the key lists it, `<kind>` the question's kind, and `<the tab's read>` a
   whole read of that tab a `fetch` job saved just before, which must name the tab's node and
   show its heading alone. It opens the line's directory and refuses a place that is not what
   `place` prints from it for that question under that line's name, and what a packet would
   refuse to carry. Which tab a place goes to is the speaker's: `rows` holds it only to a
   blank tab of the AI's. Before the `place` job is added the index is written again, so that
   it lists `<n>/place.json`, which the `ai-recorder` checks the entry against. The entry is one update of three inserts at the
   tab's end, guarded by that read's rev, so that a tab written since refuses it: the
   question and its question line, the answer as an insert of its own, and the hinge, each
   text of the line in a code block of its own, which the document gives back word for word
   whatever marks, lists and spacing it holds, so that `tools/read.py` reads the answer back
   and `tools/packet.py` carries it as one of the AI's past held, in thread; its operation id
   is fixed by the line, the question's number, the node, the read's rev and every word
   inserted, so that a second sending lands once. A code block holds any text but an empty
   one and one holding a carriage return or a character XML cannot carry; such a text is
   refused, saying why, never altered, and its place's file is carried as an open note of kind
   `change`. Where the notebook refuses the entry because the tab moved since its read, the
   `ai-recorder` hands that back and sends nothing more; the speaker reads the tab again by a
   `fetch` job and prints the rows anew, which gives the entry a new operation id. Placing on a new tab is two steps, in this order, and no one
   command prints both, since the new tab's body node id is known only once the batch that
   makes it has landed: first a `place` job whose rows file is a list of the one entry
   `tools/ai_tab.py tab` printed, after which the speaker runs `tools/ai_tab.py add` from the
   ids the `ai-recorder` hands back; then a `fetch` job that reads the new tab, `rows` with
   the node id `add` put in the key and that read, and a second `place` job with the rows file
   `rows` wrote. A tab that already stands and holds its heading alone, the root's among
   them, takes the second step alone.
   The comparing run's lines go on the user's side.
10. **Every presupposition is a hinge.** Every presupposition a question carries in, drafted on
   the user's side or drawn, as the AI's answer names it under `Presupposes:`, one a line, is
   recorded as a hinge at the place, unjustified. A hinge is justified only by a later answer of
   the AI's own that it is linked to: its line then ends `(justified by <question id>)`, naming a
   question of the AI's that answers past held, written by a words replace of the hinge's
   question part at a batch point. `tools/hinges.py unjustified $SCRATCH/graph.json` lists every
   unjustified hinge of the AI's graph with the builds that cite an answer resting on it: read
   for the fourth signal (rule 8), it is where a record that constrains a build unawares is
   looked for first.
11. **New ideas in the draws come back to the principal.** Once draws are kept, the speaker,
   which ran the clean turns and holds the draws, reads every kept draw for ideas new to the
   sitting: every kept draw of a question, a drawer turn's draw and the back-brief. An idea is
   new where neither the user's record, the page, a document of `lines` whatever its state, nor
   the AI's own record as the packet carried it already holds it, and it was not already
   returned in this sitting; what counts as one idea, and whether it is new, is the speaker's
   reading. Each such idea opens an open line of origin `ai-draw` (**The open lines**) in the
   same round, so that it is not lost: a `review`, put with no recommendation, since it states
   no position of the notebook's. The speaker makes no judgment of which are worth following,
   and the principal drops what is not wanted. In a drawer turn's draw, the questions it raises
   go on by rule 3 and are not `ai-draw` lines; anything else it says is read as any draw is.
   Each idea is named in the action context on the page as an idea from a draw of the AI's
   record, citing the line, the question's number, or the drawer turn or the back-brief, and the
   draw's index, and saying whether that draw is the answer of record. Where a context already
   stands for the round, the naming is a record in `context.log`. While a question or review of
   principle is put on the page, or another action is the next to be put and the idea bears on
   it, the naming is held and given after its answer, and the line's title names only the draw
   it came from until then; an `ai-draw` line is not put as the next action while its naming is
   held. For each question, drawer turn or back-brief read, the action context says that its
   draws yielded no new idea where they yielded none. A held naming, and an owed statement that
   no new idea was found, are kept in the work in hand, `tools/inhand.py add $SCRATCH/speaker
   "<the naming owed>" --at <time>`, until given. Until the principal has answered the idea's
   line, the speaker carries no idea of a draw not of record anywhere, a build's brief among
   them, and no idea of any draw in its own drafting of a question or a redraw signal, so the
   line stays drawn from the AI's answers alone. A build's brief cites the answers of record as
   rule 1 gives. What `tools/packet.py` carries of the answer of record, and a question a drawer
   turn raised, go on as rules 3 and 4 give. A line of origin `ai-draw` is never queued to a
   clean turn unasked. Once the principal takes the idea up, it is the principal's requirement
   or stated position, and it enters the AI's record only by rules 1, 3 and 5, in an approved
   question. An idea dropped, or closed without being taken up, stays out of the speaker's
   drafting of a question or a redraw signal, and, where it comes from a draw not of record, out
   of a build's brief, for good, unless the principal states it; a brief that cites an answer of
   record holding it cites it as rule 1 gives. Where ground rule 8 sends the line to the
   notebook as an *open* note, the note says it is an idea from the AI's draws and not a
   position of the user's; it goes on the tab the idea bears on, and where it bears on none, at
   the end of the `dictate` tab's Hinge section, or of its last section where it has none.
   Nothing of this changes which draw is the answer of record, the first kept (rule 4).
