"""Every party's works, exported as the registry a repository's check reads."""

import json
import os
import tempfile
import unittest

from support import fixture, load, rewrite, run

from hypo import model, registry

#: what the tests wrote to disk, removed once the module is done with them
_TEMP = []


def tearDownModule():
    for path in _TEMP:
        if os.path.exists(path):
            os.unlink(path)


def with_works(data):
    """Two works on the party's tab, in the order a key would not sort them."""
    plato = next(q for q in data["questions"] if q["id"] == "plato")
    plato["works"] = [
        {"key": "RB-5", "verified": "yes"},
        {"key": "PLATO-EUTH", "work": "Euthyphro", "author": "Plato", "locus": "5d-6e",
         "date": "c. 399 BCE", "domain": "ethics", "verified": "2026-10-29",
         "status": "read", "url": "https://example.org/euthyphro",
         "note": "Read in the Grube translation."}]


def graph_file(mutate):
    """A fixture rewritten by ``mutate``, on disk: the CLI takes a path."""
    with open(fixture("valid"), encoding="utf-8") as fh:
        data = json.load(fh)
    mutate(data)
    handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                         encoding="utf-8")
    json.dump(data, handle)
    handle.close()
    _TEMP.append(handle.name)
    return handle.name


class ExportTest(unittest.TestCase):
    def test_every_key_with_its_party_and_its_filled_fields_sorted(self):
        found = registry.export(rewrite("valid", with_works))
        self.assertEqual(list(found), ["sources"])
        self.assertEqual(list(found["sources"]), ["PLATO-EUTH", "RB-5"])
        self.assertEqual(found["sources"]["RB-5"], {"party": "plato", "verified": "yes"})
        self.assertEqual(found["sources"]["PLATO-EUTH"], {
            "party": "plato", "work": "Euthyphro", "author": "Plato", "locus": "5d-6e",
            "date": "c. 399 BCE", "domain": "ethics", "verified": "2026-10-29",
            "status": "read", "url": "https://example.org/euthyphro",
            "note": "Read in the Grube translation."})

    def test_the_field_names_are_the_works_own(self):
        self.assertEqual(registry.FIELDS, ("work", "author", "locus", "date", "domain",
                                           "verified", "status", "url", "note"))

    def test_a_notebook_without_works_exports_no_source(self):
        self.assertEqual(registry.export(load("valid")), {"sources": {}})

    def test_a_key_defined_twice_is_refused(self):
        graph = rewrite("valid", with_works)
        graph.get("ti-esti").works = [model.Work(key="RB-5")]
        with self.assertRaises(registry.Doubled) as caught:
            registry.export(graph)
        self.assertIn("RB-5", str(caught.exception))


class CliTest(unittest.TestCase):
    def test_export_prints_the_registry(self):
        done = run("registry.py", "export", graph_file(with_works))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(sorted(json.loads(done.stdout)["sources"]), ["PLATO-EUTH", "RB-5"])

    def test_export_writes_a_file(self):
        out = tempfile.NamedTemporaryFile(suffix=".json", delete=False).name
        _TEMP.append(out)
        done = run("registry.py", "export", graph_file(with_works), "-o", out)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout, "")
        self.assertIn("2 source(s)", done.stderr)
        with open(out, encoding="utf-8") as fh:
            self.assertEqual(len(json.load(fh)["sources"]), 2)

    def test_an_error_on_the_works_refuses(self):
        def bad(data):
            with_works(data)
            data["questions"][0]["works"] = [{"key": "SHOSTACK-FOUR"}]
        done = run("registry.py", "export", graph_file(bad))
        self.assertEqual(done.returncode, 1)
        self.assertIn("works-on-party", done.stderr)
        self.assertEqual(done.stdout, "")

    def test_a_partial_graph_refuses(self):
        def scoped(data):
            with_works(data)
            data["scope"] = ["canon"]
        done = run("registry.py", "export", graph_file(scoped))
        self.assertEqual(done.returncode, 1)
        self.assertIn("every party's", done.stderr)


if __name__ == "__main__":
    unittest.main()
