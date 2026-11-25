Read this part before a question for the AI's own record is drafted or put, before a clean turn or a `turn`, `compare` or `place` job, before any build is briefed, and before a constraint is treated as binding.

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
-name index | sort > $SCRATCH/lines/<line>/index`, before it adds a `compare` or a `place` job,
since the helpers of those kinds cannot list a directory. A question's directory holds its
packet, `tools/packet.py $SCRATCH/graph.json --under <id> --line $SCRATCH/lines/<line> -o
$SCRATCH/lines/<line>/<n>/packet.md`, with the fingerprint the tool writes beside it; its words,
`question.md`, written with the Write tool; its leak record and its origin; and its draws, in
`draws/`. The packet holds the AI's answers of the tab `<id>` it stands under and above it, then
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
   $SCRATCH/lines/<line>/<n>/leak.json`, which refuses a question that repeats masked words or
   breaks the notebook's rule for naming the user, saying what it found; its presuppositions
   are listed on the user's side, in the line doc and at the batch point on the tab it bears on.
   Each such question is then its own action on the page, a `review` whose prompt is the
   question word for word, for the principal to approve or revise; it is put to the AI only on
   that approval. A revision is written over `question.md` and checked again before it is shown
   again, and only the text the principal approved is put. On that approval the speaker writes
   `$SCRATCH/lines/<line>/<n>/approval.json` with the Write tool, `{"sha256": <the fingerprint
   of the question file as approved>, "approved": <the time, from the clock>}`, and the clean
   turn refuses any other text. A question the AI's own record raises comes verbatim from a
   drawer turn, `tools/clean_turn.py draw --packet $SCRATCH/lines/<line>/drawn-<n>/packet.md
   --out $SCRATCH/lines/<line>/drawn-<n>`, and needs no approval; it is still checked by
   `public.py question`, and the clean turn refuses it unless it stands as a line of that
   drawer's run. Case situations go to the AI's record as questions; verdicts and reasons stay
   on the user's side, with the comparing run. The clean turn refuses a question in which a
   token opens with `@`, which the harness would expand into a file of the machine, and one
   that opens with `/` or `!`; every prompt it sends opens with a line of its own.
4. **Draws.** Each question is drawn several times, `tools/clean_turn.py answer --packet
   $SCRATCH/lines/<line>/<n>/packet.md --question $SCRATCH/lines/<line>/<n>/question.md --out
   $SCRATCH/lines/<line>/<n>/draws --approval $SCRATCH/lines/<line>/<n>/approval.json --leak
   $SCRATCH/lines/<line>/<n>/leak.json`, three by default, or with `--drawn-from` the drawer's
   `draw-1.json` in place of `--approval`. All are kept, none is chosen by what it says, and
   the first kept is the answer of record (above). Where they part in what they would do, that
   is the finding, and the question is drawn higher. A question whose draws were all refused is
   put again under a new number, or dropped, before the line goes on: the packet refuses a gap.
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
   rows $SCRATCH/lines/<line>/<n>/place.json --node <node id> --kind <kind> >
   $SCRATCH/lines/<line>/<n>/rows.json` prints the rows entry that places them, `<node id>`
   the tab's body as the key lists it and `<kind>` the question's kind. The entry is one
   update of three inserts at the tab's end: the question and its question line, the answer
   word for word as an insert of its own, and the hinge, in the form of the notebook's own
   tabs, which `tools/read.py` reads back and `tools/packet.py` carries as an answer of the
   AI's past held, in thread; its operation id is fixed by the line, the question's number and
   the node, so that a second sending lands once. It refuses, saying why, an answer the page
   would not give back word for word, a line broken inside a paragraph among them, and never
   alters it; such an answer is not placed, and its place's file is carried as an open note
   of kind `change`. Placing on a new tab is two steps, in this order, and no one command
   prints both, since the new tab's body node id is known only once the batch that makes it
   has landed: first a `place` job whose rows file is a list of the one entry `tools/ai_tab.py
   tab` printed, after which the speaker runs `tools/ai_tab.py add` from the ids the
   `ai-recorder` hands back; then `rows` with the node id `add` put in the key, and a second
   `place` job whose rows file is a list of the one entry `rows` printed. A tab that already
   stands and holds its heading alone, the root's among them, takes the second step alone.
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
