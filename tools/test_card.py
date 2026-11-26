"""The check on a write of the page's ordo/current: what the page draws as
meant passes, and each fault it would draw wrong, or a question carrying a
recommendation, is one refusal. Every value here is invented."""

import json
import os
import shutil
import tempfile
import unittest

from hypo import card
from support import run

T = "2030-01-02T03:04:05Z"
DELETE = {"__delete__": True}


def whole():
    """A whole write of ordo/current, as page.md's example gives it."""
    return {
        "context": {
            "heading": "Your answer, as read",
            "paragraphs": ["The plants are watered before the post is opened."],
            "for": [{"who": "Example Author (lead)", "text": "Example position."}],
            "against": [{"who": "Another Author (lead)", "text": "Another position."}],
            "prediction": {"predicted": "Watering waits.", "diverged": ["It came first."],
                           "addressed": "A case at the next batch point."},
            "notes": ["A quiet note."],
            "at": T,
            "log": [{"at": T, "paragraphs": "An addition."}],
        },
        "next": {"kind": "question", "case": "A morning with a bill due.",
                 "prompt": "Is watering still first?", "put_at": T},
        "queue": [{"kind": "work", "prompt": "Water the plants."}],
        "updated": T,
    }


class CheckTest(unittest.TestCase):
    def refused(self, update, *words):
        findings = card.check(update)
        self.assertTrue(findings, update)
        for w in words:
            self.assertTrue(any(w in f for f in findings), (w, findings))
        return findings

    def test_a_whole_write_passes(self):
        self.assertEqual(card.check(whole()), [])

    def test_a_partial_update_passes(self):
        self.assertEqual(card.check({"updated": T}), [])
        self.assertEqual(card.check({"queue": [], "updated": T}), [])
        self.assertEqual(card.check({"context": {"log": [{"at": T, "paragraphs": ["x"]}]}}),
                         [])

    def test_a_reading_as_a_plain_string_is_refused(self):
        u = whole()
        u["context"]["for"] = ["Example Author: Example position."]
        self.refused(u, "context.for[0] is not an object")
        u = whole()
        u["context"]["against"].append("Another position.")
        self.refused(u, "context.against[1] is not an object")

    def test_a_reading_without_who_or_text_is_refused(self):
        u = whole()
        u["context"]["for"] = [{"who": "Example Author"}, {"who": " ", "text": "x"}]
        findings = self.refused(u, "context.for[0] has no text", "context.for[1] has no who")
        self.assertEqual(len(findings), 2)

    def test_a_side_that_is_not_a_list_is_refused(self):
        u = whole()
        u["context"]["for"] = {"who": "Example Author", "text": "Example position."}
        self.refused(u, "context.for is not a list")

    def test_a_prediction_out_of_shape_is_refused(self):
        u = whole()
        u["context"]["prediction"] = "Watering waits."
        self.refused(u, "context.prediction is not an object")
        u = whole()
        u["context"]["prediction"]["guess"] = "x"
        self.refused(u, "holds 'guess'")
        u = whole()
        u["context"]["prediction"]["diverged"] = [1]
        self.refused(u, "context.prediction.diverged is not a string or a list of strings")

    def test_paragraphs_out_of_shape_are_refused(self):
        u = whole()
        u["context"]["paragraphs"] = "One paragraph."
        self.refused(u, "context.paragraphs is a string")
        u = whole()
        u["context"]["paragraphs"] = [{"text": "x"}]
        self.refused(u, "context.paragraphs is not a list of strings")
        u = whole()
        u["context"]["log"] = [{"at": T, "paragraphs": 3}]
        self.refused(u, "context.log[0].paragraphs is not a string or a list of strings")

    def test_a_log_record_without_its_time_is_refused(self):
        u = whole()
        u["context"]["log"] = [{"paragraphs": ["x"]}, "y"]
        self.refused(u, "context.log[0] has no at", "context.log[1] is not an object")

    def test_next_without_kind_or_prompt_is_refused(self):
        self.refused({"next": {"prompt": "Water the plants."}}, "next has no kind")
        self.refused({"next": {"kind": "work"}}, "next has no prompt")
        self.refused({"next": {"resolved_at": T}}, "next has no kind", "next has no prompt")
        self.refused({"next": "Water the plants."}, "next is not an object")

    def test_a_question_with_a_recommendation_is_refused(self):
        u = whole()
        u["next"]["recommendation"] = "Say yes."
        self.refused(u, "a question is put with none")
        u["next"]["recommendation"] = ["", "Say yes."]
        self.refused(u, "a question is put with none")

    def test_a_review_may_carry_a_recommendation_and_a_question_an_empty_one(self):
        u = whole()
        u["next"].update(kind="review", recommendation="Keep the order.")
        self.assertEqual(card.check(u), [])
        u["next"].update(kind="question", recommendation="")
        self.assertEqual(card.check(u), [])

    def test_the_deletion_marker_is_taken_wherever_a_field_may_go(self):
        self.assertEqual(card.check({"context": DELETE, "next": DELETE}), [])
        u = whole()
        u["context"].update({"for": DELETE, "against": DELETE, "prediction": DELETE,
                             "log": DELETE, "paragraphs": DELETE})
        u["next"]["recommendation"] = DELETE
        self.assertEqual(card.check(u), [])
        u = whole()
        u["context"]["prediction"]["addressed"] = DELETE
        self.assertEqual(card.check(u), [])

    def test_a_write_that_is_not_an_object_is_refused(self):
        self.refused([], "not a JSON object")
        self.refused({"context": "x"}, "context is not an object")


class CliTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)

    def file(self, data):
        path = os.path.join(self.dir, "update.json")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(data if isinstance(data, str) else json.dumps(data))
        return path

    def test_ok_and_exit_zero(self):
        done = run("card.py", "check", self.file(whole()))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout.strip(), "ok")
        self.assertEqual(done.stderr, "")

    def test_one_refused_line_per_finding(self):
        u = whole()
        u["context"]["for"] = ["a", "b"]
        u["next"]["recommendation"] = "Say yes."
        done = run("card.py", "check", self.file(u))
        self.assertEqual(done.returncode, 1)
        self.assertEqual(done.stdout, "")
        lines = done.stderr.strip().splitlines()
        self.assertEqual(len(lines), 3, lines)
        self.assertTrue(all(line.startswith("REFUSED: ") for line in lines), lines)

    def test_from_stdin_and_a_file_that_is_no_json(self):
        done = run("card.py", "check", "-", stdin=json.dumps({"updated": T}))
        self.assertEqual(done.returncode, 0, done.stderr)
        done = run("card.py", "check", self.file("{not json"))
        self.assertEqual(done.returncode, 1)
        self.assertIn("REFUSED: ", done.stderr)


if __name__ == "__main__":
    unittest.main()
