"""The three command-line entry points: exit codes and output shape."""

import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(HERE, "fixtures")


def run(script, *args, cwd=None):
    """Run a tool from another directory: paths resolve beside the script."""
    return subprocess.run(
        [sys.executable, os.path.join(HERE, script)] + list(args),
        capture_output=True, text=True, cwd=cwd or os.path.dirname(HERE))


def fixture(name):
    return os.path.join(FIXTURES, name + ".json")


class CheckCliTest(unittest.TestCase):
    def test_valid_exits_zero_with_a_summary(self):
        done = run("check.py", fixture("valid"))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("5 questions, 0 errors, 0 warnings", done.stdout)

    def test_an_error_fixture_exits_one(self):
        done = run("check.py", fixture("invalid-acyclic"))
        self.assertEqual(done.returncode, 1)
        self.assertIn("ERROR", done.stdout)
        self.assertIn("acyclic", done.stdout)

    def test_a_warning_fixture_exits_zero(self):
        done = run("check.py", fixture("invalid-priority-recompute"))
        self.assertEqual(done.returncode, 0)
        self.assertIn("WARN", done.stdout)

    def test_json_output(self):
        done = run("check.py", fixture("invalid-vocabulary"), "--json")
        payload = json.loads(done.stdout)
        self.assertEqual(payload["errors"], 1)
        self.assertEqual(payload["findings"][0]["check"], "vocabulary")

    def test_list_needs_no_graph(self):
        done = run("check.py", "--list")
        self.assertEqual(done.returncode, 0)
        self.assertEqual(len(done.stdout.strip().splitlines()), 21)

    def test_a_missing_file_is_reported_not_raised(self):
        done = run("check.py", fixture("absent"))
        self.assertNotEqual(done.returncode, 0)
        self.assertNotIn("Traceback", done.stdout)


class ProjectCliTest(unittest.TestCase):
    def test_tree_and_patch(self):
        done = run("project.py", fixture("valid"))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("a0 ti-esti", done.stdout)
        self.assertIn("b0 plato", done.stdout)
        patch = json.loads(done.stdout[done.stdout.index("["):])
        self.assertEqual(len(patch), 5)

    def test_json_carries_both(self):
        done = run("project.py", fixture("valid"), "--json")
        payload = json.loads(done.stdout)
        self.assertEqual(len(payload["tabs"]), 5)
        self.assertEqual(payload["tree"][0]["question"], "ti-esti")
        self.assertEqual(payload["tree"][0]["load"], 3)


class RenderCliTest(unittest.TestCase):
    def test_one_tab(self):
        done = run("render.py", fixture("valid"), "canon")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertTrue(done.stdout.startswith("# canon\n"))

    def test_all_tabs(self):
        done = run("render.py", fixture("valid"), "--all")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout.count("=== "), 5)

    def test_links_sidecar_follows_the_markdown(self):
        done = run("render.py", fixture("valid"), "ti-esti", "--links")
        head, _, tail = done.stdout.partition("=== links ===")
        self.assertIn("# ti-esti", head)
        self.assertEqual(len(json.loads(tail)["links"]), 3)

    def test_it_refuses_on_an_error(self):
        done = run("render.py", fixture("invalid-anchor-substring"), "ti-esti")
        self.assertEqual(done.returncode, 1)
        self.assertEqual(done.stdout, "")
        self.assertIn("refusing to render ti-esti", done.stderr)

    def test_an_unknown_question_is_refused(self):
        done = run("render.py", fixture("valid"), "absent")
        self.assertEqual(done.returncode, 1)
        self.assertIn("no question", done.stderr)

    def test_a_question_or_all_is_required(self):
        done = run("render.py", fixture("valid"))
        self.assertEqual(done.returncode, 2)


if __name__ == "__main__":
    unittest.main()
