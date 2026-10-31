"""The digest: a project's end, words, clauses and cases as one markdown page."""

import json
import os
import tempfile
import unittest

from hypo import digest
from support import load, rewrite, run


def with_case(data):
    data["questions"][1]["cases"] = [{
        "name": "the signed entry",
        "situation": "an entry nobody with standing has marked is acted on",
        "verdict": "it is not acted on",
        "reason": "authority is held down by the mark and by nothing else",
        "clause": "Authority held down",
    }]


class DigestTest(unittest.TestCase):
    def test_the_root_and_its_hinge_open_the_digest(self):
        text = digest.digest(load())
        self.assertTrue(text.startswith("# ti-esti\n"))
        self.assertIn("## The end and its method", text)
        self.assertIn("- **end:** that the two sides go on working together", text)
        self.assertIn("- **method:** read at each entry", text)

    def test_words_clauses_and_cases_are_the_tabs_own(self):
        text = digest.digest(rewrite("valid", with_case))
        self.assertIn("## The words", text)
        self.assertIn("- **assent (canon):**", text)
        self.assertIn("## The clauses", text)
        self.assertIn("- **Authority held down (canon):**", text)
        self.assertIn("· cue: an act is proposed on an entry", text)
        self.assertIn("## The cases", text)
        self.assertIn("- **the signed entry (canon):** case: an entry nobody with standing "
                      "has marked is acted on · verdict: it is not acted on · reason: "
                      "authority is held down by the mark and by nothing else · clause: "
                      "Authority held down", text)

    def test_a_party_is_never_in_the_digest(self):
        text = digest.digest(load())
        self.assertNotIn("plato", text)

    def test_no_such_project_is_empty(self):
        self.assertEqual(digest.digest(load(), "ordo"), "")


class CliTest(unittest.TestCase):
    def test_prints_the_digest_and_writes_it(self):
        done = run("digest.py", os.path.join(os.path.dirname(__file__), "fixtures", "valid.json"))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("## The clauses", done.stdout)
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "digest.md")
            done = run("digest.py", os.path.join(os.path.dirname(__file__), "fixtures",
                                                 "valid.json"), "-o", out)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertIn("line(s) ->", done.stderr)
            with open(out, encoding="utf-8") as fh:
                self.assertIn("# ti-esti", fh.read())

    def test_refuses_a_project_the_graph_lacks(self):
        done = run("digest.py", os.path.join(os.path.dirname(__file__), "fixtures", "valid.json"),
                   "--project", "ordo")
        self.assertEqual(done.returncode, 1)
        self.assertIn("holds no project ordo", done.stderr)


if __name__ == "__main__":
    unittest.main()
