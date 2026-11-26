"""The check on a write of the page's ordo/current: what the page draws as
meant passes, and each fault it would draw wrong, or a question carrying a
recommendation or a how, is one refusal. The whole write is the invented
example page.md gives, read from the file."""

import copy
import json
import os
import re
import shutil
import tempfile
import unittest

from hypo import card
from support import run

HERE = os.path.dirname(os.path.abspath(__file__))
PAGE_MD = os.path.join(HERE, "..", "skills", "sit", "parts", "page.md")
T = "2030-01-02T03:04:05Z"
DELETE = {"__delete__": True}


def _example():
    with open(PAGE_MD, encoding="utf-8") as fh:
        text = fh.read()
    at = text.index("**`ordo/current`**")
    block = re.search(r"```json\n(.*?)\n```", text[at:], re.S)
    return json.loads(block.group(1))


EXAMPLE = _example()


def whole():
    """A whole write of ordo/current: page.md's example, fresh each time."""
    return copy.deepcopy(EXAMPLE)


class CheckTest(unittest.TestCase):
    def refused(self, update, *words):
        findings = card.check(update)
        self.assertTrue(findings, update)
        for w in words:
            self.assertTrue(any(w in f for f in findings), (w, findings))
        return findings

    def test_page_md_s_example_passes(self):
        self.assertEqual(card.check(whole()), [])

    def test_a_partial_update_passes(self):
        self.assertEqual(card.check({"updated": T}), [])
        self.assertEqual(card.check({"queue": [], "updated": T}), [])
        self.assertEqual(card.check({"context": {"log": [{"at": T, "paragraphs": ["x"]}]},
                                     "updated": T}), [])

    def test_every_write_sets_updated_as_a_time(self):
        self.refused({"queue": []}, "has no updated")
        self.refused({"updated": 5}, "updated is not an ISO time")
        self.refused({"updated": "03:04"}, "updated is not an ISO time")
        self.refused({"updated": "2030-01-02T03:04:05"}, "updated is not an ISO time")
        self.assertEqual(card.check({"updated": "2030-01-02T03:04:05+01:00"}), [])

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

    def test_paragraphs_notes_and_heading_out_of_shape_are_refused(self):
        u = whole()
        u["context"]["paragraphs"] = "One paragraph."
        self.refused(u, "context.paragraphs is a string")
        u = whole()
        u["context"]["paragraphs"] = [{"text": "x"}]
        self.refused(u, "context.paragraphs is not a list of strings")
        u = whole()
        u["context"]["notes"] = "A note."
        self.refused(u, "context.notes is a string")
        u = whole()
        u["context"]["notes"] = [3]
        self.refused(u, "context.notes is not a list of strings")
        u = whole()
        u["context"]["heading"] = 5
        self.refused(u, "context.heading is not a string")
        u = whole()
        u["context"]["log"] = [{"at": T, "paragraphs": 3}]
        self.refused(u, "context.log[0].paragraphs is not a string or a list of strings")

    def test_a_log_record_without_its_time_or_with_one_that_does_not_parse_is_refused(self):
        u = whole()
        u["context"]["log"] = [{"paragraphs": ["x"]}, "y", {"at": "not a time",
                                                             "paragraphs": ["x"]}]
        self.refused(u, "context.log[0] has no at", "context.log[1] is not an object",
                     "context.log[2].at is not an ISO time")
        u = whole()
        u["context"]["at"] = "2030-02-30T03:00:00Z"
        self.refused(u, "context.at is not an ISO time")

    def test_next_holding_a_drawn_field_without_kind_or_prompt_is_refused(self):
        self.refused({"next": {"prompt": "Water the plants."}, "updated": T},
                     "next has no kind")
        self.refused({"next": {"kind": "work"}, "updated": T}, "next has no prompt")
        self.refused({"next": {"case": "A morning."}, "updated": T},
                     "next has no kind", "next has no prompt")
        self.refused({"next": "Water the plants.", "updated": T}, "next is not an object")

    def test_next_holding_only_what_the_card_does_not_draw_passes(self):
        for n in ({"resolved_at": T}, {"asks": False}, {"deferred": DELETE},
                  {"recommendation": DELETE, "how": DELETE}):
            with self.subTest(next=n):
                self.assertEqual(card.check({"next": n, "updated": T}), [])
        self.refused({"next": {"resolved_at": "soon"}, "updated": T},
                     "next.resolved_at is not an ISO time")

    def test_a_kind_outside_the_four_is_refused(self):
        u = whole()
        u["next"].update(kind="Question", recommendation="Say yes.")
        self.refused(u, "next.kind 'Question' is not one of")
        u = whole()
        u["queue"][0]["kind"] = "quest"
        self.refused(u, "queue[0].kind 'quest' is not one of")

    def test_a_question_with_a_recommendation_or_a_how_is_refused(self):
        u = whole()
        u["next"]["recommendation"] = "Say yes."
        self.refused(u, "a question is put with none")
        u["next"]["recommendation"] = ["", "Say yes."]
        self.refused(u, "a question is put with none")
        for kind in ("question", "review"):
            u = whole()
            u["next"].update(kind=kind, how="Answer yes.")
            self.refused(u, "carries a how")

    def test_a_recommendation_of_the_wrong_type_is_refused(self):
        for bad in ({"a": 1}, [1, 2], 3):
            with self.subTest(bad=bad):
                u = whole()
                u["next"].update(kind="review", recommendation=bad)
                self.refused(u, "next.recommendation is not a string or a list of strings")

    def test_a_review_may_carry_a_recommendation_and_a_question_an_empty_one(self):
        u = whole()
        u["next"].update(kind="review", recommendation="Keep the order.")
        self.assertEqual(card.check(u), [])
        u["next"].update(kind="question", recommendation="")
        self.assertEqual(card.check(u), [])
        u["next"].update(kind="work", how="By hand.")
        self.assertEqual(card.check(u), [])

    def test_a_queue_out_of_shape_is_refused(self):
        self.refused({"queue": "x", "updated": T}, "queue is not a list")
        self.refused({"queue": ["a string"], "updated": T}, "queue[0] is not an object")
        self.refused({"queue": [{"kind": "work"}], "updated": T},
                     "queue[0] has neither title nor prompt")
        self.assertEqual(card.check({"queue": [{"kind": "review", "title": "Rows"}],
                                     "updated": T}), [])

    def test_background_out_of_shape_is_refused(self):
        self.refused({"background": "a string", "updated": T}, "background is not a list")
        self.assertEqual(card.check({"background": ["A helper."], "updated": T}), [])

    def test_the_deletion_marker_is_taken_wherever_a_field_may_go(self):
        self.assertEqual(card.check({"context": DELETE, "next": DELETE, "queue": DELETE,
                                     "background": DELETE, "updated": T}), [])
        u = whole()
        u["context"].update({"for": DELETE, "against": DELETE, "prediction": DELETE,
                             "log": DELETE, "paragraphs": DELETE, "notes": DELETE,
                             "heading": DELETE, "at": DELETE})
        u["next"]["recommendation"] = DELETE
        self.assertEqual(card.check(u), [])
        u = whole()
        u["context"]["prediction"]["addressed"] = DELETE
        self.assertEqual(card.check(u), [])

    def test_a_write_that_is_not_an_object_is_refused(self):
        self.refused([], "not a JSON object")
        self.refused({"context": "x", "updated": T}, "context is not an object")


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
