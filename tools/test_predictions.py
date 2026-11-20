"""The failed predictions the notebook records: a note's words and what they
refuse, the tally over a graph and the notes graded since, the stamp and the
seal it binds, and the skill's own lines run as written. Every note here is
invented, about plants and post, and about no one."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest

from hypo import predictions
from support import fixture, run

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.join(HERE, "..", "skills", "sit", "SKILL.md")
T = "2030-01-02T03:04:05Z"
LESSON = "A rule about days is asked about weather too."


SEALS = iter("s1-review-%d" % i for i in range(1, 1000))


def note(by="speaker", kind="review", grade="diverges", direction="expected-more-limits",
         lesson=LESSON, text=None, seal=None):
    return predictions.compose(seal or next(SEALS), by, kind, grade, lesson,
                               "one more read of the mornings tab", direction, text)


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.added = os.path.join(self.dir, "predictions")
        os.makedirs(self.added)

    def graph(self, *bodies, recurring=()):
        """The fixture graph with these notes on one tab of the author's."""
        with open(fixture("valid"), encoding="utf-8") as fh:
            data = json.load(fh)
        q = next(x for x in data["questions"] if x["id"] == "canon")
        q["notes"] = [{"section": "hinge", "body": b} for b in bodies] + [
            {"section": "hinge", "body": "divergence: a lesson recurs across two predictions "
                                         "· action: %s · whose: ai · price: none" % r}
            for r in recurring]
        path = os.path.join(self.dir, "graph-%d.json" % len(os.listdir(self.dir)))
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        return path

    def add(self, name, body):
        with open(os.path.join(self.added, name), "w", encoding="utf-8") as fh:
            fh.write(body)


class NoteTest(Base):
    def test_the_words_hold_who_what_grade_and_direction_and_nothing_else(self):
        done = run("predictions.py", "note", "--seal", "s1-review-3", "--by", "speaker",
                   "--kind", "review", "--grade",
                   "diverges", "--direction", "expected-more-limits", "--lesson", LESSON,
                   "--price", "one more read")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout.strip(),
                         "divergence: prediction s1-review-3 by speaker of a review, graded "
                         "diverges, "
                         "direction expected-more-limits · action: %s · whose: ai · price: one "
                         "more read · budget: none" % LESSON)
        self.assertIsNotNone(predictions.parse(done.stdout, "x"))

    def test_short_of_the_edge_needs_no_direction_and_an_act_takes_an(self):
        words = note(kind="act", grade="short of the edge", direction=None)
        self.assertRegex(words, r"prediction \S+ by speaker of an act, graded short of the "
                                r"edge ·")
        self.assertEqual(predictions.parse(words, "x").direction, "")

    def refused(self, *args):
        done = run("predictions.py", "note", *args)
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertEqual(done.stdout, "")
        return done.stderr

    def test_refusals(self):
        base = ["--seal", "s1-review-1", "--by", "speaker", "--kind", "review", "--lesson", LESSON, "--price", "p"]
        self.assertIn("is not a failure the grader gives",
                      self.refused(*base, "--grade", "agrees"))
        self.assertIn("is not a failure the grader gives",
                      self.refused(*base, "--grade", "mostly", "--direction", "other",
                                   "--text", "t"))
        self.assertIn("says which way", self.refused(*base, "--grade", "verdict only"))
        self.assertIn("direction is not one of",
                      self.refused(*base, "--grade", "diverges", "--direction", "sideways"))
        self.assertIn("a direction of other says it in words",
                      self.refused(*base, "--grade", "diverges", "--direction", "other"))
        self.assertIn("the seal is not an id",
                      self.refused("--seal", "a seal with words", "--by", "speaker", "--kind",
                                   "review", "--grade", "short of the edge", "--lesson", "l",
                                   "--price", "p"))
        self.assertIn("by is not one of", self.refused("--seal", "x1", "--by", "principal", "--kind", "review",
                                                      "--grade", "diverges", "--direction",
                                                      "other", "--text", "t", "--lesson", "l",
                                                      "--price", "p"))
        self.assertIn("which parts a note",
                      self.refused("--seal", "x1", "--by", "speaker", "--kind", "review",
                                   "--grade",
                                   "short of the edge", "--lesson", "a · b", "--price", "p"))
        self.assertIn("the lesson is empty",
                      self.refused("--seal", "x1", "--by", "speaker", "--kind", "review",
                                   "--grade",
                                   "short of the edge", "--lesson", " ", "--price", "p"))

    def test_a_clean_reader_s_act_is_recorded_as_any(self):
        self.assertIn("by clean-reader of an act",
                      note(by="clean-reader", kind="act"))


class TallyTest(Base):
    def test_the_graph_and_the_notes_graded_since(self):
        graph = self.graph(note(seal="s1-review-1"), note(kind="question", by="clean-reader",
                                        grade="verdict only",
                                        direction="missed-recorded-sentence",
                                        lesson="Ask about the post as well as the plants."),
                           "an open note of somebody's, not a prediction's",
                           "divergence: the post came late · action: wait · whose: user · "
                           "price: none")
        self.add("r3.txt", note(lesson="a rule about days is asked about  weather too"))
        # the graph's own note again, the same seal: counted once
        self.add("s1-review-1.txt", note(seal="s1-review-1"))
        done = run("predictions.py", "tally", graph, "--added", self.added)
        self.assertEqual(done.returncode, 0, done.stderr)
        t = json.loads(done.stdout)
        self.assertEqual(t["failed"], 3)
        self.assertEqual(t["by_kind"], {"question": 1, "review": 2, "act": 0})
        self.assertEqual(t["by_who"], {"speaker": 2, "clean-reader": 1})
        self.assertEqual(t["by_grade"], {"verdict only": 1, "short of the edge": 0,
                                         "diverges": 2})
        self.assertEqual(t["by_direction"]["expected-more-limits"], 2)
        self.assertEqual(len(t["lessons"]), 1)
        self.assertEqual(t["lessons"][0]["count"], 2)
        self.assertFalse(t["lessons"][0]["written"])

    def test_b2_the_same_words_twice_are_two_predictions(self):
        """A second failure in the same words is a second note, by its seal:
        counted, its lesson recurring, and the old stamp refused."""
        one = note(seal="s1-review-1")
        two = one.replace("s1-review-1", "s1-review-2")
        self.add("s1-review-2.txt", two)
        t = json.loads(run("predictions.py", "tally", self.graph(one), "--added",
                           self.added).stdout)
        self.assertEqual(t["failed"], 2)
        self.assertEqual(t["lessons"][0]["count"], 2)
        # two notes of the graph in the same words, on two tabs or one, are two
        t = json.loads(run("predictions.py", "tally", self.graph(one, one)).stdout)
        self.assertEqual(t["failed"], 2)

    def test_a_recurring_lesson_already_written_is_said_so(self):
        graph = self.graph(note(), note(direction="expected-less-change"),
                           recurring=[LESSON])
        t = json.loads(run("predictions.py", "tally", graph).stdout)
        self.assertTrue(t["lessons"][0]["written"])
        self.assertEqual(t["failed"], 2)

    def test_a_note_that_opens_as_a_prediction_and_breaks_the_form_is_refused(self):
        graph = self.graph("divergence: prediction s1 by speaker of a review, graded mostly · "
                           "action: l · whose: ai · price: p")
        done = run("predictions.py", "tally", graph)
        self.assertEqual(done.returncode, 1)
        self.assertIn("does not hold the form", done.stderr)
        self.add("bad.txt", "an open note")
        done = run("predictions.py", "tally", self.graph(), "--added", self.added)
        self.assertIn("bad.txt is no prediction's note", done.stderr)

    def test_a_graph_or_directory_that_is_not_there_is_refused(self):
        self.assertIn("the graph cannot be read",
                      run("predictions.py", "tally", "/nonexistent.json").stderr)
        self.assertIn("the added directory cannot be read",
                      run("predictions.py", "tally", self.graph(), "--added",
                          "/nonexistent/dir").stderr)


class StampTest(Base):
    def test_the_stamp_ends_the_tally(self):
        done = run("predictions.py", "stamp", self.graph(note()), "--at", T)
        self.assertEqual(done.returncode, 0, done.stderr)
        out = done.stdout.splitlines()
        self.assertIn("failed predictions recorded: 1", out)
        self.assertIn("lessons carried by 2 or more: none", out)
        self.assertRegex(out[-1], r"^predictions-read: [0-9a-f]{64} %s$" % T)

    def test_a_lesson_not_yet_on_the_notebook_is_marked(self):
        self.add("r1.txt", note())
        done = run("predictions.py", "stamp", self.graph(note(direction="other",
                                                             text="the bell")),
                   "--added", self.added, "--at", T)
        self.assertIn("- (2) %s [not yet on the notebook]" % LESSON, done.stdout)

    def test_a_time_that_is_not_utc_is_refused(self):
        done = run("predictions.py", "stamp", self.graph(), "--at", "2030-01-02 03:04")
        self.assertEqual(done.returncode, 1)
        self.assertEqual(done.stdout, "")
        self.assertIn("REFUSED: --at:", done.stderr)


class CheckSealTest(Base):
    def stamped(self, graph, prediction="by: speaker\nThe plants are watered first.\n"):
        stamp = os.path.join(self.dir, "stamp.txt")
        with open(stamp, "w") as fh:
            fh.write(run("predictions.py", "stamp", graph, "--added", self.added, "--at",
                         T).stdout)
        with open(stamp) as fh:
            last = fh.read().splitlines()[-1]
        sealed = os.path.join(self.dir, "review-1.md")
        with open(sealed, "w") as fh:
            fh.write(prediction + last + "\n")
        return sealed, stamp

    def check(self, sealed, stamp, graph):
        return run("predictions.py", "check-seal", sealed, "--graph", graph, "--stamp", stamp,
                   "--added", self.added)

    def test_a_seal_stamped_over_the_record_as_it_stands_passes(self):
        graph = self.graph(note())
        sealed, stamp = self.stamped(graph)
        done = self.check(sealed, stamp, graph)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertTrue(done.stdout.startswith("ok: predictions-read: "))

    def test_b2_a_note_graded_since_the_stamp_refuses_it(self):
        """The lesson just graded is the one the next seal must have read:
        its words in the sitting's directory kill the old stamp."""
        graph = self.graph()
        sealed, stamp = self.stamped(graph)
        self.add("r2.txt", note())
        done = self.check(sealed, stamp, graph)
        self.assertEqual(done.returncode, 1)
        self.assertIn("the stamp is not of the record as it stands", done.stderr)

    def test_a_stamp_file_written_by_hand_is_refused(self):
        graph = self.graph()
        sealed, stamp = self.stamped(graph)
        with open(stamp) as fh:
            last = fh.read().splitlines()[-1]
        with open(stamp, "w") as fh:
            fh.write(last + "\n")
        self.assertIn("is not what stamp prints", self.check(sealed, stamp, graph).stderr)

    def test_a_seal_whose_stamp_is_not_the_stamp_file_s_refuses(self):
        graph = self.graph()
        sealed, stamp = self.stamped(graph)
        with open(sealed, "w") as fh:
            fh.write("Kept.\npredictions-read: %s 1999-01-01T00:00:00Z\n" % ("0" * 64))
        self.assertIn("is not the stamp file's last line",
                      self.check(sealed, stamp, graph).stderr)

    def test_a_seal_without_the_stamp_refuses(self):
        graph = self.graph()
        _, stamp = self.stamped(graph)
        for text in ("Kept.\n", "",
                     "Kept. predictions-read: %s %s\n" % ("0" * 64, T),
                     "predictions-read: %s %s\nand after it\n" % ("0" * 64, T)):
            path = os.path.join(self.dir, "s.md")
            with open(path, "w") as fh:
                fh.write(text)
            done = self.check(path, stamp, graph)
            self.assertEqual(done.returncode, 1, text)
            self.assertIn("does not end with a line of its own", done.stderr)

    def test_a_seal_of_nothing_but_the_stamp_refuses(self):
        graph = self.graph()
        sealed, stamp = self.stamped(graph, prediction="\n")
        self.assertIn("holds nothing but the stamp", self.check(sealed, stamp, graph).stderr)

    def test_a_sealed_file_that_is_not_there_refuses(self):
        graph = self.graph()
        _, stamp = self.stamped(graph)
        done = self.check("/nonexistent/review-1.md", stamp, graph)
        self.assertEqual(done.returncode, 1)
        self.assertIn("the sealed file cannot be read", done.stderr)


class SkillLinesTest(Base):
    """The skill's own `predictions.py` and `tail` lines, run by the shell as
    written: a stamp, a seal stamped and checked, a failed prediction's note
    written to the sitting's directory, and the old stamp then refused, with
    no hand copy between."""

    def test_the_lines_run_in_order(self):
        import test_sit_skill as walk
        found = walk.lines(SKILL, "predictions.py")
        self.assertEqual({each.split()[1] for each in found}, {"stamp", "check-seal", "note"})
        tail = walk.lines(SKILL, "tail")
        self.assertEqual(len(tail), 1)
        scratch = os.path.join(self.dir, "s")
        for d in ("speaker", "sealed", "predictions"):
            os.makedirs(os.path.join(scratch, d))
        shutil.copy(self.graph(), os.path.join(scratch, "graph.json"))
        values = {"$SCRATCH": scratch, "<time>": T, "<seal id>": "s1-review-1",
                  "<seal>": "review-1",
                  "<who>": "speaker", "<question|review|act>": "review",
                  "<the grader's grade>": "diverges", "<direction>": "expected-more-limits",
                  "<the lesson>": LESSON, "<what applying it costs>": "one more read"}

        def sh(each, code=0):
            command = each.replace("tools/", HERE + "/", 1)
            for key, value in values.items():
                command = command.replace(key, value)
            left = walk.UNFILLED.search(command)
            self.assertIsNone(left, (left and left.group(0), command))
            done = subprocess.run(["bash", "-c", command], capture_output=True, text=True,
                                  timeout=60)
            self.assertEqual(done.returncode, code, (command, done.stdout, done.stderr))
            return done

        first = {each.split()[1]: each for each in reversed(found)}
        sh(first["stamp"])
        with open(os.path.join(scratch, "sealed", "review-1.md"), "w") as fh:
            fh.write("by: speaker\nThe plants are watered before the post.\n")
        sh(tail[0])
        sh(first["check-seal"])
        sh(first["note"])
        self.assertTrue(os.path.exists(os.path.join(scratch, "predictions",
                                                    "s1-review-1.txt")))
        self.assertIn("the stamp is not of the record as it stands",
                      sh(first["check-seal"], code=1).stderr)


if __name__ == "__main__":
    unittest.main()
