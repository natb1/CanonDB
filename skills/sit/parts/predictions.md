Read this part before every prediction of the speaker's own, that is before each review is put, when a grade comes back, before a failed prediction's note is written, at a batch point that carries a lesson that recurs, and after a compaction.

## The record of predictions

What is learned about predicting the principal must not be transient: so the principal has
said, and that no source of it be kept but the notebook. This section is built from those words,
as a stopgap (**What the sitting serves**). There is no store of predictions and no store of
lessons beside the notebook.

**A failed prediction is a divergence.** A prediction the grader grades `verdict only`, `short of
the edge`, `diverges in part` or `diverges`, the speaker's or a clean reader's, is recorded at the round as the
notebook records any divergence (`/principal:dictate`, `tools/divergence.py`): a note opening
with the word *divergence*, on the tab the notebook keeps for how the record predicts the user,
whose data names the seal graded by its id, who predicted, the kind of action, the grade and
the direction, and never the sealed text, the answer or the case, and whose `action` is the
lesson, what would have kept the prediction from failing. The seal's id is the `seal` job's id
for a clean reader's, and `<sitting>-<seal>` for the speaker's, so that two failures in the same
words are two notes and a lesson that recurs word for word is counted twice. Its words are
printed by `tools/predictions.py note --seal <seal id> --by <who> --kind <question|review|act>
--grade "<the grader's grade>" --direction <direction> --lesson "<the lesson>" --price "<what
applying it costs>" > $SCRATCH/predictions/<seal id>.txt`, one file a seal, a regrade of the
same seal written over it; the direction
one of `expected-more-limits`, `expected-fewer-limits`, `expected-less-change`,
`expected-more-change`, `missed-recorded-sentence` and `other`, with `--text` where it is
`other`, and needed for `verdict only`, `diverges in part` and `diverges`; and the note goes to the notebook through
the recorder, as **Written as the round goes** says. A lesson two or more failed predictions
carry, which the tally marks as not yet on the notebook, is written once more on that tab at
the next batch point, as a divergence whose data opens with `a lesson recurs` and whose `action`
is the lesson, put as a review like any row. An agreeing prediction, graded `agrees` or `silent`,
is counted where every grade already is, in the line doc's Fidelity rounds section (`- F1,
stated at S2. …` with its grade), which needs no new form; it is not written as a divergence,
since nothing diverged. Where the notebook has no tab for how the record predicts the user, the
speaker puts the making of one to the principal as an action on the page, and until it is made
the notes wait in `$SCRATCH/predictions/` and in the line doc.

**The lessons are record.** A clean reader reads the notebook, and so reads these notes and the
lessons in them: what is learned reaches its prediction by the notebook alone. It is never
handed the stamp or the tally, and nothing of either goes into `$SCRATCH/questions/` or a seal
job's inputs.

**Before every prediction of the speaker's own**, before each review: `tools/predictions.py
stamp $SCRATCH/graph.json --added $SCRATCH/predictions --at <time> > $SCRATCH/speaker/stamp.txt`,
over the opening's graph and the notes graded since, and read what it printed whole: the counts
by kind, by who predicted, by grade and by direction, and the lessons two or more predictions
carry. Then write the prediction with the Write tool to `$SCRATCH/sealed/<seal>.md`, `<seal>`
`review-<n>`, saying who predicted and ending with a newline; append the stamp's last line,
`tail -n 1 $SCRATCH/speaker/stamp.txt >> $SCRATCH/sealed/<seal>.md`; and run
`tools/predictions.py check-seal $SCRATCH/sealed/<seal>.md --graph $SCRATCH/graph.json --stamp
$SCRATCH/speaker/stamp.txt --added $SCRATCH/predictions`, which refuses a sealed file that does
not end with `predictions-read: <sha256> <time>` for the record as it stands, and a stamp file
that is not what `stamp` prints for it. Only then is its fingerprint taken. A note graded since
the stamp is in `$SCRATCH/predictions/`, so the old stamp no longer passes: stamp, read and seal
again. `$SCRATCH/predictions/` is made when the sitting opens, and holds note words and nothing
else.
