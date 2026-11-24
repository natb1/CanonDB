"""The tabs of the AI's own record: the batch that makes one, and the key
that names them (`tools/ai_tab.py`)."""

import contextlib
import io
import json
import os
import tempfile
import unittest

import ai_tab as cli_tool
from hypo import ai_tab

NOTEBOOK = "0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0"
UNSET = {"artifact": "https://example.invalid/code/artifact/Notebook-" + NOTEBOOK, "x": 1}


class BatchTest(unittest.TestCase):
    def test_the_root_is_the_connector_s_four_calls_at_the_top_level(self):
        out = ai_tab.root(UNSET, "ai-root", "z0")
        self.assertEqual(out["container"], {"kind": "project", "id": NOTEBOOK})
        self.assertEqual([m["verb"] for m in out["batch"]],
                         ["create", "create", "update", "update"])
        self.assertEqual(out["batch"][1]["payload"]["source"]["from"]["content"], "# ai-root")
        where = out["batch"][3]["payload"]["patch"][0]["value"]
        self.assertEqual(where, {"name": "ai-root", "order": "z0"})
        self.assertEqual(out["opId"], ai_tab.root(UNSET, "ai-root", "z0")["opId"])
        nested = ai_tab.root(UNSET, "ai-root", "a0", under="t-project")
        self.assertEqual(nested["batch"][3]["payload"]["patch"][0]["value"]["subtabOf"],
                         "t-project")

    def test_the_root_is_made_once(self):
        named = ai_tab.add(UNSET, "n-root", "t-root")
        with self.assertRaises(ai_tab.Refused):
            ai_tab.root(named, "ai-root", "a0")
        with self.assertRaises(ai_tab.Refused):
            ai_tab.root(dict(UNSET, ai_root="n-old"), "ai-root", "a0")

    def test_a_tab_under_a_tab_the_key_gives_with_its_tab_id(self):
        named = ai_tab.add(UNSET, "n-root", "t-root")
        entry = ai_tab.tab(named, "N-ROOT", "q-one", "a1", "# q-one\n\nbody")
        self.assertEqual(entry["node"], "N-ROOT")
        self.assertEqual(entry["batch"]["batch"][3]["payload"]["patch"][0]["value"],
                         {"name": "q-one", "order": "a1", "subtabOf": "t-root"})
        self.assertEqual(entry["batch"]["batch"][1]["payload"]["source"]["from"]["content"],
                         "# q-one\n\nbody")
        self.assertNotEqual(entry["op_id"], ai_tab.tab(named, "n-root", "q-two", "a1")["op_id"])
        for named_, parent in ((UNSET, "n-root"), (named, "n-other"),
                               (dict(UNSET, ai_root=["n-old"]), "n-old"), (named, "n root")):
            with self.subTest(parent=parent):
                with self.assertRaises(ai_tab.Refused):
                    ai_tab.tab(named_, parent, "q-one", "a0")

    def test_a_name_is_a_question_s_id(self):
        for name in ("lease", "Ai-Root", "ai root", "a/b", "", "-a", "a--b", "ai_root"):
            with self.subTest(name=name):
                with self.assertRaises(ai_tab.Refused):
                    ai_tab.root(UNSET, name, "a0")
        for order in ("", "0a", "A0", "a-0"):
            with self.assertRaises(ai_tab.Refused):
                ai_tab.root(UNSET, "ai-root", order)
        with self.assertRaises(ai_tab.Refused):
            ai_tab.root(UNSET, "ai-root", "a0", content="  \n")
        with self.assertRaises(ai_tab.Refused):
            ai_tab.root(UNSET, "ai-root", "a0", under="t​-x")


class KeyTest(unittest.TestCase):
    def test_the_root_first_then_tabs_under_listed_ones(self):
        named = ai_tab.add(UNSET, "n-root", "t-root")
        self.assertEqual(named["ai_root"], [{"node": "n-root", "tab": "t-root"}])
        self.assertEqual(named["x"], 1)
        self.assertNotIn("ai_root", UNSET)
        named = ai_tab.add(named, "n-a", "t-a", parent="n-root")
        named = ai_tab.add(named, "n-b", "t-b", parent="N-A")
        self.assertEqual([e["node"] for e in named["ai_root"]], ["n-root", "n-a", "n-b"])

    def test_what_is_refused(self):
        named = ai_tab.add(UNSET, "n-root", "t-root")
        for args in ((named, "n-x", "t-x"),  # a second root
                     (UNSET, "n-a", "t-a", "n-root"),  # a parent under no root
                     (named, "n-a", "t-a", "n-other"),  # a parent the key does not list
                     (named, "n-root", "t-new", "n-root"),  # twice
                     (named, "n-new", "T-ROOT", "n-root"),
                     (named, "n a", "t-a", "n-root"),
                     (dict(UNSET, ai_root=[{"node": "n"}]), "n-a", "t-a")):
            with self.subTest(args=args[1:]):
                with self.assertRaises(ai_tab.Refused):
                    ai_tab.add(*args)

    def test_an_old_bare_entry_is_kept(self):
        named = ai_tab.add(dict(UNSET, ai_root="n-old"), "n-a", "t-a", parent="n-old")
        self.assertEqual(named["ai_root"], ["n-old", {"node": "n-a", "tab": "t-a"}])


class CommandTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.mkdir(os.path.join(self.tmp.name, ".principal"))
        self.path = os.path.join(self.tmp.name, ".principal", "notebook.json")
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(UNSET, fh)

    def tearDown(self):
        self.tmp.cleanup()

    def run_tool(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli_tool.main(["--notebook", self.path] + list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_root_add_tab(self):
        code, out, _ = self.run_tool("root", "--name", "ai-root")
        self.assertEqual(code, 0)
        self.assertIn("opId", json.loads(out))
        self.assertEqual(self.run_tool("tab", "--parent", "n-root", "--name", "q")[0], 1)
        self.assertEqual(self.run_tool("add", "--node", "n-root", "--tab", "t-root")[0], 0)
        code, _, err = self.run_tool("root", "--name", "ai-root")
        self.assertEqual(code, 1)
        self.assertIn("REFUSED", err)
        content = os.path.join(self.tmp.name, "body.md")
        with open(content, "w", encoding="utf-8") as fh:
            fh.write("# q\n")
        code, out, _ = self.run_tool("tab", "--parent", "n-root", "--name", "q",
                                     "--content", content)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["node"], "n-root")
        self.assertEqual(self.run_tool("add", "--node", "n-q", "--tab", "t-q",
                                       "--parent", "n-root")[0], 0)
        with open(self.path, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["ai_root"],
                             [{"node": "n-root", "tab": "t-root"}, {"node": "n-q", "tab": "t-q"}])

    def test_the_nearest_notebook_file(self):
        here = os.path.join(self.tmp.name, "a", "b")
        os.makedirs(here)
        self.assertEqual(ai_tab.find(here), self.path)


if __name__ == "__main__":
    unittest.main()
