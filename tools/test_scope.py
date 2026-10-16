"""A check over the tabs a dictation touches and their ancestors.

The fixture notebook split: a scope, the tabs above it, and nothing below.
Every rule still runs; the only ones that go quiet are those a tab below
could answer, and a missing ancestor is refused, never read over.
"""

import json
import os
import shutil
import tempfile
import unittest

from hypo import model, spec
from support import FIXTURES, run
from test_cli import document

#: the rules that need a tab outside a partial graph to say anything, and so
#: say nothing over one: what a term or a tradition edge leads to stands
#: below, or beside
QUIET = {"term-target", "tradition-target"}


class ReadScopeTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.manifest, self.tabs = document(self.dir)
        self.out = os.path.join(self.dir, "graph.json")

    def keep(self, *questions):
        for entry in os.listdir(self.tabs):
            if entry[:-3] not in questions:
                os.unlink(os.path.join(self.tabs, entry))

    def test_a_scope_and_its_ancestors_check_clean(self):
        self.keep("ti-esti", "canon")
        done = run("read.py", self.manifest, self.tabs, "-o", self.out, "--scope", "canon")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(model.load(self.out).scope, ["canon"])
        checked = run("check.py", self.out)
        self.assertEqual(checked.returncode, 0, checked.stdout)
        self.assertIn("scoped to canon", checked.stdout)

    def test_the_same_split_unscoped_is_faulted(self):
        """What the scope excuses is real over a whole notebook: a term
        leading to a tab not read is a term leading nowhere."""
        self.keep("ti-esti", "canon")
        run("read.py", self.manifest, self.tabs, "-o", self.out)
        self.assertEqual(run("check.py", self.out).returncode, 1)

    def test_a_raiser_not_read_is_refused(self):
        """attenuation is raised on canon and on party; party was not read."""
        self.keep("ti-esti", "canon", "attenuation")
        done = run("read.py", self.manifest, self.tabs, "-o", self.out,
                   "--scope", "attenuation")
        self.assertEqual(done.returncode, 1)
        self.assertIn("party", done.stderr)
        self.assertFalse(os.path.exists(self.out))

    def test_a_scoped_question_not_read_is_refused(self):
        self.keep("ti-esti")
        done = run("read.py", self.manifest, self.tabs, "-o", self.out, "--scope", "canon")
        self.assertEqual(done.returncode, 1)
        self.assertIn("canon", done.stderr)


class CheckScopeTest(unittest.TestCase):
    def split(self, keep, scope=None):
        with open(os.path.join(FIXTURES, "valid.json"), encoding="utf-8") as fh:
            data = json.load(fh)
        data["questions"] = [q for q in data["questions"] if q["id"] in keep]
        if scope:
            data["scope"] = scope
        where = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, where, ignore_errors=True)
        path = os.path.join(where, "graph.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        return path

    def test_scope_on_the_command_line_does_what_the_file_would(self):
        path = self.split(["ti-esti", "canon"])
        self.assertEqual(run("check.py", path).returncode, 1)
        done = run("check.py", path, "--scope", "canon")
        self.assertEqual(done.returncode, 0, done.stdout)

    def test_a_missing_ancestor_is_refused_not_read_over(self):
        done = run("check.py", self.split(["canon"]), "--scope", "canon")
        self.assertEqual(done.returncode, 1)
        self.assertIn("scope-closed", done.stdout)

    def test_a_traditions_head_in_the_scope_is_not_a_missing_ancestor(self):
        """plato is cited by ti-esti and raised by nothing: its tab was read
        for the citations that reach it, and it is another party's root, not
        an author's question whose raiser went unread."""
        done = run("check.py", self.split(["ti-esti", "canon", "plato"], ["canon"]))
        self.assertEqual(done.returncode, 0, done.stdout)
        self.assertNotIn("scope-closed", done.stdout)

    def test_a_question_the_scope_names_and_the_graph_lacks_is_refused(self):
        done = run("check.py", self.split(["ti-esti", "canon"]), "--scope", "party")
        self.assertEqual(done.returncode, 1)
        self.assertIn("holds no such question", done.stdout)

    def test_a_fault_inside_the_scope_is_still_found(self):
        path = self.split(["ti-esti", "canon"], ["canon"])
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        data["questions"][1]["theses"][0]["terms"][0]["anchors"] = ["words it never says"]
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        done = run("check.py", path)
        self.assertEqual(done.returncode, 1)
        self.assertIn("anchor-substring", done.stdout)

    def test_every_rule_but_the_quiet_ones_still_fires_over_a_whole_scope(self):
        """Each invalid fixture, read as though it were the scope of a
        dictation with every tab present: a rule that goes quiet here is one
        the scope excuses, and only those needing a tab below may."""
        for c in spec.CHECKS:
            if c.id == "scope-closed":
                continue
            with self.subTest(check=c.id):
                graph = model.load(os.path.join(FIXTURES, "invalid-%s.json" % c.id))
                graph.scope = [q.id for q in graph.questions]
                fired = spec.run(graph, only=[c.id])
                if c.id not in QUIET:
                    self.assertTrue(fired, "%s went quiet over a partial graph" % c.id)


if __name__ == "__main__":
    unittest.main()
