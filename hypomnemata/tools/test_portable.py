"""Sealing parts the notebook from its document, and nothing else."""

import copy
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

import portable as cli
from hypo import model, portable, project

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
VALID = os.path.join(FIXTURES, "valid.json")


def graph_file(data):
    """Write a graph dict to a temp file and return its path."""
    handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                         encoding="utf-8")
    json.dump(data, handle)
    handle.close()
    return handle.name


def run(argv):
    """The CLI, with its streams captured: (exit code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = cli.main(argv)
    return code, out.getvalue(), err.getvalue()


class SealTest(unittest.TestCase):
    def setUp(self):
        self.graph = model.load(VALID)
        self.envelope = portable.seal(self.graph, name="a notebook")
        with open(VALID, encoding="utf-8") as fh:
            self.data = json.load(fh)

    def test_the_envelope_says_what_it_is(self):
        self.assertEqual(self.envelope["format"], portable.FORMAT)
        self.assertEqual(self.envelope["name"], "a notebook")

    def test_no_document_local_value_survives(self):
        self.assertNotIn("artifact", self.envelope)
        self.assertNotIn("state_enum", self.envelope)
        for q in self.envelope["questions"]:
            self.assertEqual(q["tab"], "")
            self.assertEqual(q["body"], "")

    def test_every_question_and_its_content_survives(self):
        sealed = {q["id"]: q for q in self.envelope["questions"]}
        self.assertEqual(sorted(sealed), sorted(q.id for q in self.graph.questions))
        for original in self.data["questions"]:
            carried = dict(sealed[original["id"]])
            stripped = {k: v for k, v in original.items()
                        if k not in portable.QUESTION_KEYS}
            for key in portable.QUESTION_KEYS:
                carried.pop(key)
            self.assertEqual(carried, stripped)

    def test_the_states_travel_in_order(self):
        self.assertEqual(self.envelope["states"], list(model.STATES))

    def test_the_rebuild_rides_along(self):
        self.assertEqual(self.envelope["rebuild"], portable.STEPS)

    def test_the_tree_is_recorded_as_what_a_rebuild_must_match(self):
        self.assertEqual(self.envelope["expect"]["questions"],
                         len(self.graph.questions))
        self.assertEqual(self.envelope["expect"]["tree"], portable.tree(self.graph))

    def test_sealing_does_not_touch_the_graph_file(self):
        with open(VALID, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh), self.data)

    def test_bindings_name_what_will_be_dropped(self):
        found = portable.bindings(self.data)
        self.assertIn("artifact=%s" % self.data["artifact"], found)
        for q in self.data["questions"]:
            self.assertIn("%s.tab=%s" % (q["id"], q["tab"]), found)

    def test_bindings_of_an_unbound_graph_are_none(self):
        self.assertEqual(portable.bindings(portable.unseal(self.envelope)), [])


class OpenTest(unittest.TestCase):
    def setUp(self):
        self.graph = model.load(VALID)
        self.envelope = portable.seal(self.graph)
        self.data = portable.unseal(self.envelope)

    def test_what_comes_out_is_a_graph_file(self):
        graph = model.load(graph_file(self.data))
        self.assertEqual([q.id for q in graph.questions],
                         [q.id for q in self.graph.questions])

    def test_it_comes_out_unbound(self):
        self.assertEqual(self.data["artifact"], "")
        self.assertIsNone(self.data["state_enum"])
        for q in self.data["questions"]:
            self.assertEqual(q["tab"], "")
            self.assertEqual(q["body"], "")

    def test_the_mode_travels(self):
        self.assertEqual(self.data["mode"], self.graph.mode)

    def test_binding_the_tabs_gives_back_the_same_tree(self):
        # The tab tree is not carried, because project derives it. Bind the
        # tabs to any ids at all and the projection must come out the same.
        data = copy.deepcopy(self.data)
        for i, q in enumerate(data["questions"]):
            q["tab"], q["body"] = "t%d" % i, "b%d" % i
        rebuilt = model.load(graph_file(data))
        self.assertEqual(portable.tree(rebuilt), self.envelope["expect"]["tree"])
        self.assertEqual(len(project.tabs_patch(rebuilt)),
                         self.envelope["expect"]["questions"])

    def test_sealing_what_was_opened_seals_the_same(self):
        again = portable.seal(model.load(graph_file(self.data)))
        self.assertEqual(again["questions"], self.envelope["questions"])

    def test_a_foreign_envelope_is_refused(self):
        with self.assertRaises(ValueError):
            portable.unseal({"format": "something-else", "questions": []})


class CommandTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def path(self, name):
        return os.path.join(self.dir, name)

    def test_seal_then_open_round_trips_through_the_disk(self):
        env, out = self.path("e.json"), self.path("g.json")
        self.assertEqual(run(["seal", VALID, "-o", env])[0], 0)
        self.assertEqual(run(["open", env, "-o", out])[0], 0)
        graph = model.load(out)
        self.assertEqual([q.id for q in graph.questions],
                         [q.id for q in model.load(VALID).questions])

    def test_seal_reports_every_binding_it_dropped(self):
        env = self.path("e.json")
        code, _, err = run(["seal", VALID, "-o", env])
        self.assertEqual(code, 0)
        with open(VALID, encoding="utf-8") as fh:
            expected = portable.bindings(json.load(fh))
        for line in expected:
            self.assertIn("dropped %s" % line, err)

    def test_seal_writes_to_stdout_when_asked_for_no_file(self):
        code, out, _ = run(["seal", VALID])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["format"], portable.FORMAT)

    def test_seal_refuses_a_graph_the_checker_faults(self):
        code, _, err = run(["seal", os.path.join(FIXTURES, "invalid-one-root.json"),
                            "-o", self.path("e.json")])
        self.assertEqual(code, 1)
        self.assertIn("refusing to seal", err)
        self.assertFalse(os.path.exists(self.path("e.json")))

    def test_force_seals_a_faulted_graph_and_says_so(self):
        env = self.path("e.json")
        code, _, err = run(["seal", os.path.join(FIXTURES, "invalid-one-root.json"),
                            "-o", env, "--force"])
        self.assertEqual(code, 0)
        self.assertIn("--force", err)
        self.assertTrue(os.path.exists(env))

    def test_seal_refuses_a_misshapen_graph(self):
        bad = graph_file({"questions": [{"id": "x"}]})
        code, _, err = run(["seal", bad, "-o", self.path("e.json")])
        self.assertEqual(code, 1)
        self.assertIn("ERROR shape", err)

    def test_open_refuses_what_is_not_an_envelope(self):
        code, _, err = run(["open", VALID, "-o", self.path("g.json")])
        self.assertEqual(code, 1)
        self.assertIn("ERROR envelope", err)

    def test_open_refuses_a_file_that_is_not_there(self):
        code, _, err = run(["open", self.path("absent.json")])
        self.assertEqual(code, 1)
        self.assertIn("ERROR envelope", err)


if __name__ == "__main__":
    unittest.main()
