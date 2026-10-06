"""The graph file loads into the model, and a malformed one is refused."""

import json
import os
import tempfile
import unittest

from hypo import model

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def fixture(name):
    return os.path.join(FIXTURES, name + ".json")


class ImportShapeTest(unittest.TestCase):
    def test_an_import_needs_no_body_key(self):
        """An entry with no body of its own is an import, as the model says;
        the key may be left out as well as left empty."""
        with open(fixture("valid"), encoding="utf-8") as fh:
            data = json.load(fh)
        canon = next(q for q in data["questions"] if q["id"] == "canon")
        canon["definitions"].append({"word": "homologia", "tradition": {"to": "plato"}})
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                         encoding="utf-8") as fh:
            json.dump(data, fh)
        try:
            graph = model.load(fh.name)
        finally:
            os.unlink(fh.name)
        entry = graph.get("canon").definitions[-1]
        self.assertTrue(entry.imported)
        self.assertEqual(entry.body, "")


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
        self.assertIsInstance(root.definitions[0], model.Definition)
        self.assertIsInstance(root.theses[0].traditions[0], model.TraditionEdge)
        self.assertIsInstance(list(root.applications())[0][1], model.Application)
        self.assertIsInstance(root.hinge, model.Hinge)

    def test_a_glossary_on_an_answer_is_refused(self):
        """The glossary moved to the question. Nothing else refuses a key it
        does not know, so an old file would lose its words without a word."""
        with open(fixture("valid"), encoding="utf-8") as fh:
            data = json.load(fh)
        root = data["questions"][0]
        root["theses"][0]["definitions"] = root.pop("definitions")
        with tempfile.TemporaryDirectory() as tmp:
            old = os.path.join(tmp, "old.json")
            with open(old, "w", encoding="utf-8") as fh:
                json.dump(data, fh)
            with self.assertRaises(model.ShapeError) as caught:
                model.load(old)
        self.assertIn("belongs to the question", "; ".join(caught.exception.problems))

    def test_a_definition_with_no_body_must_import_one(self):
        """An entry with no body says the word is a party's, in the party's
        sense. With no party named there is no sense anywhere."""
        with open(fixture("valid"), encoding="utf-8") as fh:
            data = json.load(fh)
        data["questions"][0]["definitions"].append({"word": "homologia", "body": ""})
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "bodiless.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh)
            with self.assertRaises(model.ShapeError) as caught:
                model.load(path)
        self.assertIn("unless it imports", "; ".join(caught.exception.problems))

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
        for key in ("'tab'", "'body'", "'question'", "'state'", "'kind'", "'pressure'"):
            self.assertIn(key, problems)

    def test_wrong_types_are_reported(self):
        with self.assertRaises(model.ShapeError) as caught:
            self._load({"questions": [
                {"id": "a", "tab": "t", "body": "b", "question": "?",
                 "state": "held", "kind": "case", "pressure": "high"}]})
        self.assertIn("must be an integer", " ".join(caught.exception.problems))

    def test_defaults(self):
        graph = self._load({"questions": [
            {"id": "a", "tab": "t", "body": "b", "question": "?",
             "state": "held", "kind": "case", "pressure": 0}]})
        q = graph.get("a")
        self.assertEqual((q.theses, q.definitions, q.notes), ([], [], []))
        self.assertEqual(list(q.applications()), [])
        self.assertFalse(q.tradition)
        self.assertIsNone(q.hinge)

    def test_a_graph_file_that_still_holds_an_inbox_is_refused(self):
        """Nothing else refuses a key it does not know, so a file written
        while a tab had an inbox would be read as though it never held one."""
        q = {"id": "a", "tab": "t", "body": "b", "question": "?",
             "state": "held", "kind": "case", "pressure": 0}
        for key, value in (("inbox", []), ("requires", ["an-item"])):
            with self.subTest(key=key), self.assertRaises(model.ShapeError) as caught:
                self._load({"questions": [dict(q, **{key: value})]})
            problems = " ".join(caught.exception.problems)
            self.assertIn("(a).%s" % key, problems)
            self.assertIn("the inbox was removed", problems)

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
