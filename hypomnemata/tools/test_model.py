"""The graph file loads into the model, and a malformed one is refused."""

import json
import os
import tempfile
import unittest

from hypo import model

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def fixture(name):
    return os.path.join(FIXTURES, name + ".json")


class LoadTest(unittest.TestCase):
    def setUp(self):
        self.graph = model.load(fixture("valid"))

    def test_questions_load_in_file_order(self):
        self.assertEqual([q.id for q in self.graph.questions],
                         ["ti-esti", "canon", "party", "attenuation", "plato"])

    def test_artifact_is_carried(self):
        self.assertTrue(self.graph.artifact.startswith("https://claude.ai/"))

    def test_nested_shapes(self):
        root = self.graph.get("ti-esti")
        self.assertIsInstance(root, model.Question)
        self.assertIsInstance(root.theses[0], model.Thesis)
        self.assertIsInstance(root.theses[0].terms[0], model.Term)
        self.assertIsInstance(root.theses[0].definitions[0], model.Definition)
        self.assertIsInstance(root.theses[0].traditions[0], model.TraditionEdge)
        self.assertIsInstance(root.inbox[0], model.InboxItem)
        self.assertIsInstance(root.applications[0], model.Application)
        self.assertIsInstance(root.hinge, model.Hinge)

    def test_absent_hinge_is_none(self):
        without = model.load(fixture("invalid-hinge-present"))
        self.assertIsNone(without.get("canon").hinge)
        self.assertIsInstance(self.graph.get("canon").hinge, model.Hinge)

    def test_the_mode_defaults_to_notebook(self):
        self.assertEqual(self.graph.mode, model.NOTEBOOK)

    def test_a_canon_names_its_mode(self):
        self.assertEqual(model.load(fixture("invalid-answer-cardinality")).mode,
                         model.CANON)

    def test_edges(self):
        self.assertEqual(len(self.graph.term_edges()), 4)
        self.assertEqual(sorted(src.id for src, _ in self.graph.incoming("attenuation")),
                         ["canon", "party"])
        self.assertEqual(self.graph.tradition_ids(), ["plato"])

    def test_by_id_and_get(self):
        self.assertEqual(set(self.graph.by_id()), {"ti-esti", "canon", "party",
                                                   "attenuation", "plato"})
        self.assertIsNone(self.graph.get("absent"))


class ShapeTest(unittest.TestCase):
    def _load(self, payload):
        handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                             encoding="utf-8")
        try:
            json.dump(payload, handle)
            handle.close()
            return model.load(handle.name)
        finally:
            os.unlink(handle.name)

    def test_missing_keys_are_collected(self):
        with self.assertRaises(model.ShapeError) as caught:
            self._load({"artifact": "x", "questions": [{"id": "a"}]})
        problems = " ".join(caught.exception.problems)
        for key in ("'tab'", "'body'", "'question'", "'state'", "'kind'", "'priority'"):
            self.assertIn(key, problems)

    def test_wrong_types_are_reported(self):
        with self.assertRaises(model.ShapeError) as caught:
            self._load({"questions": [
                {"id": "a", "tab": "t", "body": "b", "question": "?",
                 "state": "held", "kind": "case", "priority": "high"}]})
        self.assertIn("must be an integer", " ".join(caught.exception.problems))

    def test_defaults(self):
        graph = self._load({"questions": [
            {"id": "a", "tab": "t", "body": "b", "question": "?",
             "state": "held", "kind": "case", "priority": 0}]})
        q = graph.get("a")
        self.assertEqual((q.requires, q.theses, q.inbox, q.applications), ([], [], [], []))
        self.assertFalse(q.tradition)
        self.assertIsNone(q.hinge)

    def test_invalid_json_is_a_shape_error(self):
        handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        handle.write("{not json")
        handle.close()
        try:
            with self.assertRaises(model.ShapeError):
                model.load(handle.name)
        finally:
            os.unlink(handle.name)


class FixtureTest(unittest.TestCase):
    def test_every_fixture_is_shape_valid(self):
        for name in sorted(os.listdir(FIXTURES)):
            if not name.endswith(".json"):
                continue
            with self.subTest(fixture=name):
                model.load(os.path.join(FIXTURES, name))


if __name__ == "__main__":
    unittest.main()
