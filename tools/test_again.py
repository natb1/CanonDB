"""The due-again read: which landed answers are dated, read off the record."""

from __future__ import annotations

import copy
import json
import os
import subprocess
import tempfile
import unittest

from support import fixture, run

from hypo import again, model


def _data(mutate=None):
    with open(fixture("valid"), encoding="utf-8") as fh:
        data = json.load(fh)
    if mutate:
        mutate(data)
    return data


def _graph(data):
    handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(data, handle)
    handle.close()
    try:
        return model.load(handle.name)
    finally:
        os.unlink(handle.name)


def by_id(data, qid):
    return next(q for q in data["questions"] if q["id"] == qid)


def land(data, qid):
    q = by_id(data, qid)
    q["state"] = "landed"
    for thesis in q["theses"]:
        thesis["state"] = "landed"


MODEL = "an unnamed assistant"  # what the fixture's hinges name


def nothing_moved(qid, canon, above):
    return []


class ProvenanceTest(unittest.TestCase):
    def test_the_three_the_renderer_writes_are_read_and_the_rest_left(self):
        prov = again.provenance("model: Opus 5 · harness: Claude Code, the run of 2026-09-22 · "
                                "canon: dba4d22 · the principal's prior · amended 2026-10-16 by x")
        self.assertEqual(prov, again.Provenance("Opus 5", "Claude Code, the run of 2026-09-22",
                                                "dba4d22"))

    def test_a_canon_the_page_links_is_read_as_its_words(self):
        prov = again.provenance("model: Fable 5.1 · harness: h · canon: "
                                "[dba4d22](https://github.com/x/commit/dba4d228) · the answer")
        self.assertEqual(prov.canon, "dba4d22")

    def test_a_half_that_names_none_of_them_is_none(self):
        self.assertIsNone(again.provenance("the principal's prior, drawn from the design session"))


class DueTest(unittest.TestCase):
    def test_a_landed_answer_from_the_same_model_over_unmoved_canon_is_not_due(self):
        graph = _graph(_data(lambda d: land(d, "ti-esti")))
        self.assertEqual(again.due(graph, MODEL, nothing_moved), [])

    def test_another_model_dates_it(self):
        graph = _graph(_data(lambda d: land(d, "ti-esti")))
        rows = again.due(graph, "Fable 5.1", nothing_moved)
        self.assertEqual([r.question for r in rows], ["ti-esti"])
        self.assertEqual(rows[0].model, MODEL)
        self.assertEqual(rows[0].canon, "empty")
        self.assertEqual(rows[0].reasons, ["model: an unnamed assistant, now Fable 5.1"])

    def test_canon_moved_above_dates_it_and_names_what_moved(self):
        def mutate(d):
            land(d, "ti-esti")
            land(d, "canon")
        graph = _graph(_data(mutate))
        asked = []

        def moved(qid, canon, above):
            asked.append((qid, canon, list(above)))
            return ["ti-esti"] if qid == "canon" else []
        rows = again.due(graph, MODEL, moved)
        self.assertEqual([r.question for r in rows], ["canon"])
        self.assertEqual(rows[0].reasons, ["canon above moved since the opening entry: ti-esti"])
        self.assertIn(("canon", "the opening entry", ["ti-esti"]), asked)
        self.assertIn(("ti-esti", "empty", []), asked)

    def test_a_commit_git_does_not_know_is_said_and_never_read_as_current(self):
        graph = _graph(_data(lambda d: land(d, "ti-esti")))
        rows = again.due(graph, MODEL, lambda qid, canon, above: None)
        self.assertEqual(len(rows), 1)
        self.assertIn("empty is not a commit here", rows[0].reasons[0])

    def test_an_answer_not_landed_and_a_question_the_principal_answers_are_never_due(self):
        def mutate(d):
            land(d, "attenuation")  # the principal's, landed by hand
        graph = _graph(_data(mutate))
        # party and canon are held; ti-esti's answer is in thread; plato is a tradition's
        self.assertEqual(again.due(graph, "Fable 5.1", nothing_moved), [])

    def test_a_hinge_that_names_no_provenance_is_listed_as_such(self):
        def mutate(d):
            land(d, "ti-esti")
            by_id(d, "ti-esti")["hinge"]["thesis"] = "the principal's prior"
        graph = _graph(_data(mutate))
        rows = again.due(graph, MODEL, nothing_moved)
        self.assertEqual(rows[0].question, "ti-esti")
        self.assertIn("names no model and canon", rows[0].reasons[0])


class GitTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()

        def git(*args):
            return subprocess.run(["git", "-C", self.root] + list(args),
                                  capture_output=True, text=True, check=True).stdout.strip()
        git("init", "-q")
        git("config", "user.email", "t@example.org")
        git("config", "user.name", "t")
        os.mkdir(os.path.join(self.root, "canon"))
        for name in ("a", "b"):
            with open(os.path.join(self.root, "canon", name + ".md"), "w") as fh:
                fh.write("one\n")
        git("add", ".")
        git("commit", "-q", "-m", "first")
        self.first = git("rev-parse", "--short", "HEAD")
        with open(os.path.join(self.root, "canon", "a.md"), "w") as fh:
            fh.write("two\n")
        git("commit", "-q", "-am", "second")
        self.second = git("rev-parse", "--short", "HEAD")

    def test_a_file_touched_after_the_commit_has_moved_and_one_untouched_has_not(self):
        moved = again.git_moved(self.root)
        self.assertEqual(moved("q", self.first, ["a", "b"]), ["a"])
        self.assertEqual(moved("q", self.second, ["a", "b"]), [])

    def test_a_commit_git_does_not_know_is_none(self):
        self.assertIsNone(again.git_moved(self.root)("q", "nonesuch", ["a"]))


class CliTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        subprocess.run(["git", "-C", self.root, "init", "-q"], check=True)
        data = _data(lambda d: land(d, "ti-esti"))
        self.path = os.path.join(self.root, "graph.json")
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(data, fh)

    def test_the_rows_print_as_ids_and_reasons_and_as_json(self):
        done = run("again.py", self.path, "--model", "Fable 5.1", "--root", self.root)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertTrue(done.stdout.startswith("ti-esti"))
        self.assertIn("now Fable 5.1", done.stdout)
        self.assertIn("empty is not a commit here", done.stdout)
        done = run("again.py", self.path, "--model", "Fable 5.1", "--root", self.root, "--json")
        rows = json.loads(done.stdout)
        self.assertEqual(rows[0]["question"], "ti-esti")
        self.assertEqual(len(rows[0]["reasons"]), 2)

    def test_nothing_due_is_said_on_stderr_and_exits_clean(self):
        data = _data()  # nothing landed
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        done = run("again.py", self.path, "--model", "x", "--root", self.root)
        self.assertEqual((done.returncode, done.stdout), (0, ""))
        self.assertIn("nothing is due again", done.stderr)


if __name__ == "__main__":
    unittest.main()
