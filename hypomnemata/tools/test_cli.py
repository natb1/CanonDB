"""The three command-line entry points: exit codes and output shape."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from hypo import model, project, render, spec

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(HERE, "fixtures")


def run(script, *args, cwd=None):
    """Run a tool from another directory: paths resolve beside the script."""
    return subprocess.run(
        [sys.executable, os.path.join(HERE, script)] + list(args),
        capture_output=True, text=True, cwd=cwd or os.path.dirname(HERE))


def fixture(name):
    return os.path.join(FIXTURES, name + ".json")


def slurp(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def document(where):
    """A document read plus its tab exports, built from fixtures/valid.json.

    read.py needs a manifest (a document read) and a directory of rendered
    tabs; nothing in the fixtures directory is that shape. Rather than commit
    a second, static copy of the fixture in manifest form, this derives one
    from fixtures/valid.json itself, so it can never drift out of step with
    it: the tab tree comes from `project.tabs_patch`, the same patch
    `project.py` would hand the document, and each tab's markdown is exactly
    what `render.py --all` would print for it. Returns `(manifest path, tabs
    dir)`, both under `dir`.
    """
    graph = model.load(fixture("valid"))
    findings = spec.run(graph)
    tabs = {op["path"][1]: op["value"] for op in project.tabs_patch(graph)}
    manifest = {
        "value": {"tabs": tabs},
        "files": [{"id": q.tab, "content": {"id": q.body}} for q in graph.questions],
        "frame": {"artifactUrl": graph.artifact},
    }
    manifest_path = os.path.join(where, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh)
    tabs_dir = os.path.join(where, "tabs")
    os.makedirs(tabs_dir)
    for q in graph.questions:
        with open(os.path.join(tabs_dir, q.id + ".md"), "w", encoding="utf-8") as fh:
            fh.write(render.render(graph, q.id, findings))
    return manifest_path, tabs_dir


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
        done = run("check.py", fixture("invalid-headline-not-identifier"))
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
        self.assertEqual(len(done.stdout.strip().splitlines()), len(spec.CHECKS))

    def test_a_missing_file_is_reported_not_raised(self):
        done = run("check.py", fixture("absent"))
        self.assertNotEqual(done.returncode, 0)
        # the traceback goes to stderr, so asserting on stdout alone proves nothing
        self.assertNotIn("Traceback", done.stdout + done.stderr)
        self.assertIn("absent.json", done.stdout + done.stderr)


class ProjectCliTest(unittest.TestCase):
    def test_a_cycle_refuses(self):
        done = run("project.py", fixture("invalid-acyclic"))
        self.assertEqual(done.returncode, 1)
        self.assertEqual(done.stdout, "")
        self.assertIn("cycle", done.stderr)

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
        # the lineage stands above the title
        self.assertTrue(done.stdout.startswith("⌂ "))
        self.assertIn("\n# canon\n", done.stdout)

    def test_all_tabs(self):
        done = run("render.py", fixture("valid"), "--all")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout.count("=== "), 5)

    def test_links_sidecar_follows_the_markdown(self):
        done = run("render.py", fixture("valid"), "ti-esti", "--links")
        head, _, tail = done.stdout.partition("=== links ===")
        self.assertIn("# ti-esti", head)
        # two term anchors, one definition, the answer's provenance, two inbox
        # table term titles and the item each of those rows waits on; the root
        # waits on nothing, so its own question line carries no link
        self.assertEqual(len(json.loads(tail)["links"]), 8)

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


class ReadCliTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.manifest, self.tabs = document(self.dir)
        self.envelope = os.path.join(self.dir, "envelope.json")
        sealed = run("portable.py", "seal", fixture("valid"), "-o", self.envelope,
                     "--name", "a notebook", "--tools", "somewhere/tools")
        self.assertEqual(sealed.returncode, 0, sealed.stderr)

    def read(self, tabs=None, envelope=None, no_seal=False):
        args = [self.manifest, tabs or self.tabs,
                "-o", os.path.join(self.dir, "graph.json")]
        if envelope is not None:
            args += ["--envelope", envelope]
        if no_seal:
            args.append("--no-seal")
        return run("read.py", *args)

    def test_a_complete_read_re_seals_a_named_envelope(self):
        before = json.loads(slurp(self.envelope))
        done = self.read(envelope=self.envelope)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertTrue("re-sealed" in done.stderr or "is current" in done.stderr,
                        done.stderr)
        after = json.loads(slurp(self.envelope))
        self.assertEqual(after["format"], before["format"])
        self.assertEqual(after["name"], before["name"])
        self.assertEqual(after["tools"], before["tools"])
        rebuilt = model.load(os.path.join(self.dir, "graph.json"))
        self.assertEqual([q["id"] for q in after["questions"]],
                         [q.id for q in rebuilt.questions])

    def test_what_the_re_seal_says_is_ids_and_not_the_notebook(self):
        done = self.read(envelope=self.envelope)
        self.assertEqual(done.returncode, 0, done.stderr)
        said = [line for line in done.stderr.splitlines()
                if "sealed" in line or "is current" in line]
        self.assertEqual(len(said), 1, done.stderr)  # one line, whatever moved
        graph = model.load(fixture("valid"))
        for q in graph.questions:
            for thesis in q.theses:
                self.assertNotIn(thesis.title, said[0])

    def test_no_seal_leaves_the_envelope_byte_identical(self):
        before = slurp(self.envelope)
        done = self.read(envelope=self.envelope, no_seal=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(slurp(self.envelope), before)

    def test_a_read_that_leaves_out_a_tab_does_not_seal(self):
        partial = os.path.join(self.dir, "partial")
        os.makedirs(partial)
        for entry in os.listdir(self.tabs):
            if entry != "attenuation.md":
                shutil.copy(os.path.join(self.tabs, entry), partial)
        before = slurp(self.envelope)
        done = self.read(tabs=partial, envelope=self.envelope)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("not sealed over", done.stderr)
        self.assertEqual(slurp(self.envelope), before)

    def test_re_sealing_is_idempotent(self):
        first = self.read(envelope=self.envelope)
        self.assertEqual(first.returncode, 0, first.stderr)
        after_first = slurp(self.envelope)

        second = self.read(envelope=self.envelope)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn("is current", second.stderr)
        self.assertEqual(slurp(self.envelope), after_first)


if __name__ == "__main__":
    unittest.main()
