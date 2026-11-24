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


def answer(f, n, **more):
    """The connector's answer to a batch, its aliases' ids under lids."""
    return dict({"ok": True, "lids": {"f": f, "n": n, "p": "x"}}, **more)


class BatchTest(unittest.TestCase):
    def test_the_root_is_the_connector_s_four_calls_at_the_top_level(self):
        entry = ai_tab.root(UNSET, "ai-root", "z0")
        # a rows entry for the ai-recorder, in the form `tab` prints, with no node above it
        self.assertEqual(sorted(entry), ["batch", "node", "op_id"])
        self.assertIsNone(entry["node"])
        out = entry["batch"]
        self.assertEqual(out["container"], {"kind": "project", "id": NOTEBOOK})
        self.assertEqual([m["verb"] for m in out["batch"]],
                         ["create", "create", "update", "update"])
        self.assertEqual(out["batch"][1]["payload"]["source"]["from"]["content"], "# ai-root")
        self.assertEqual(out["batch"][0]["payload"]["value"]["birthName"], "ai-root.ldoc")
        where = out["batch"][3]["payload"]["patch"][0]["value"]
        self.assertEqual(where, {"name": "ai-root", "order": "z0"})
        # one operation id for every root of the notebook, so a second lands as the first
        self.assertEqual(entry["op_id"], ai_tab.root(UNSET, "other", "a0")["op_id"])
        self.assertEqual(entry["op_id"], ai_tab.op_id("root", NOTEBOOK))

    def test_the_root_is_made_once(self):
        named, _ = ai_tab.add(UNSET, ai_tab.root(UNSET, "ai-root", "a0"),
                              answer("t-root", "n-root"))
        with self.assertRaises(ai_tab.Refused):
            ai_tab.root(named, "ai-root", "a0")
        with self.assertRaises(ai_tab.Refused):
            ai_tab.root(dict(UNSET, ai_root="n-old"), "ai-root", "a0")

    def test_a_tab_under_a_tab_the_key_gives_with_its_tab_id(self):
        named = dict(UNSET, ai_root=[{"node": "n-root", "tab": "t-root"}])
        entry = ai_tab.tab(named, "N-ROOT", "q-one", "a1")
        self.assertEqual(entry["node"], "N-ROOT")
        self.assertEqual(entry["batch"]["batch"][3]["payload"]["patch"][0]["value"],
                         {"name": "q-one", "order": "a1", "subtabOf": "t-root"})
        self.assertEqual(entry["batch"]["batch"][1]["payload"]["source"]["from"]["content"],
                         "# q-one")
        self.assertEqual(entry["op_id"], ai_tab.op_id("tab", "t-root", "q-one"))
        self.assertNotEqual(entry["op_id"], ai_tab.tab(named, "n-root", "q-two", "a1")["op_id"])
        for named_, parent in ((UNSET, "n-root"), (named, "n-other"),
                               (dict(UNSET, ai_root=["n-old"]), "n-old"), (named, "n root")):
            with self.subTest(parent=parent):
                with self.assertRaises(ai_tab.Refused):
                    ai_tab.tab(named_, parent, "q-one", "a0")

    def test_the_gate_derives_the_same_operation_ids(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "gate_for_ids", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                                         "hooks", "notebook-gate.py"))
        gate = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gate)
        self.assertEqual(gate.tab_op_id("root", NOTEBOOK), ai_tab.op_id("root", NOTEBOOK))
        self.assertEqual(gate.TAB_NAME.pattern, ai_tab.NAME.pattern)
        self.assertEqual(gate.TAB_ORDER.pattern, ai_tab.ORDER.pattern)
        self.assertEqual(gate.TAB_RESERVED, ai_tab.RESERVED)

    def test_a_name_is_a_question_s_id(self):
        for name in ("lease", "Ai-Root", "ai root", "a/b", "", "-a", "a--b", "ai_root",
                     "lease\n", "ai-root\n"):
            with self.subTest(name=name):
                with self.assertRaises(ai_tab.Refused):
                    ai_tab.root(UNSET, name, "a0")
        for order in ("", "0a", "A0", "a-0", "a0\n"):
            with self.assertRaises(ai_tab.Refused):
                ai_tab.root(UNSET, "ai-root", order)
        named = dict(UNSET, ai_root=[{"node": "n-root", "tab": "t-root"}])
        for name in ("lease\n", "q\n"):
            with self.assertRaises(ai_tab.Refused):
                ai_tab.tab(named, "n-root", name, "a0")
        with self.assertRaises(ai_tab.Refused):
            ai_tab.tab(named, "n-root\n", "q", "a0")
        with self.assertRaises(ai_tab.Refused):
            ai_tab.add(UNSET, ai_tab.root(UNSET, "ai-root", "a0"), answer("t-r\n", "n-r"))


class KeyTest(unittest.TestCase):
    """S6: what goes into the key is tied to the batch printed from the key
    as it stands, and to the connector's answer to it."""

    def setUp(self):
        self.made = ai_tab.root(UNSET, "ai-root", "a0")
        self.named, self.said = ai_tab.add(UNSET, self.made, answer("t-root", "n-root"))

    def test_the_root_first_then_tabs_under_listed_ones(self):
        self.assertEqual(self.named["ai_root"], [{"node": "n-root", "tab": "t-root"}])
        self.assertEqual(self.named["x"], 1)
        self.assertNotIn("ai_root", UNSET)
        self.assertIn("not checked", self.said)
        self.assertIn("t-root", self.said)
        named, _ = ai_tab.add(self.named, ai_tab.tab(self.named, "n-root", "q-a", "a0"),
                              {"result": [answer("t-a", "n-a")]})
        named, _ = ai_tab.add(named, ai_tab.tab(named, "N-A", "q-b", "a0"),
                              answer("t-b", "n-b"))
        self.assertEqual([e["node"] for e in named["ai_root"]], ["n-root", "n-a", "n-b"])

    def test_an_entry_not_printed_from_the_key_is_refused(self):
        entry = ai_tab.tab(self.named, "n-root", "q-a", "a0")
        # under a user's tab, claimed to stand under the root
        moved = json.loads(json.dumps(entry))
        moved["batch"]["batch"][3]["payload"]["patch"][0]["value"]["subtabOf"] = "t-user"
        # under a parent the key does not list
        other = dict(entry, node="n-user")
        # a body that says more
        said = json.loads(json.dumps(entry))
        said["batch"]["batch"][1]["payload"]["source"]["from"]["content"] = "# q-a\n\nmore"
        for made in (moved, other, said, dict(entry, op_id="x"), {}, [], {"node": "n-root"}):
            with self.subTest(made=made):
                with self.assertRaises(ai_tab.Refused):
                    ai_tab.add(self.named, made, answer("t-a", "n-a"))
        # a root's batch once the key names one, or one nested
        with self.assertRaises(ai_tab.Refused):
            ai_tab.add(self.named, self.made, answer("t-x", "n-x"))
        nested = json.loads(json.dumps(self.made))
        nested["batch"]["batch"][3]["payload"]["patch"][0]["value"]["subtabOf"] = "t-user"
        with self.assertRaises(ai_tab.Refused):
            ai_tab.add(UNSET, nested, answer("t-x", "n-x"))

    def test_an_answer_that_does_not_give_new_ids_is_refused(self):
        entry = ai_tab.tab(self.named, "n-root", "q-a", "a0")
        for got in ({}, {"lids": {"f": "t-a"}}, {"lids": {"f": 7, "n": "n-a"}},
                    answer("t-a", "t-a"), answer("t-root", "n-a"), answer("t-a", "N-ROOT"),
                    answer("t a", "n-a"), "lids"):
            with self.subTest(got=got):
                with self.assertRaises(ai_tab.Refused):
                    ai_tab.add(self.named, entry, got)

    def test_an_old_bare_entry_is_kept(self):
        named = dict(UNSET, ai_root=["n-old", {"node": "n-r", "tab": "t-r"}])
        out, _ = ai_tab.add(named, ai_tab.tab(named, "n-r", "q-a", "a0"), answer("t-a", "n-a"))
        self.assertEqual(out["ai_root"], ["n-old", {"node": "n-r", "tab": "t-r"},
                                          {"node": "n-a", "tab": "t-a"}])


class CommandTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.mkdir(os.path.join(self.tmp.name, ".principal"))
        self.path = os.path.join(self.tmp.name, ".principal", "notebook.json")
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(UNSET, fh)

    def tearDown(self):
        self.tmp.cleanup()

    def file(self, name, value):
        path = os.path.join(self.tmp.name, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(value if isinstance(value, str) else json.dumps(value))
        return path

    def run_tool(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli_tool.main(["--notebook", self.path] + list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_root_add_tab_add(self):
        code, out, _ = self.run_tool("root", "--name", "ai-root")
        self.assertEqual(code, 0)
        made = self.file("root.json", out)
        self.assertEqual(self.run_tool("tab", "--parent", "n-root", "--name", "q")[0], 1)
        bad = self.file("bad.json", "{")
        self.assertEqual(self.run_tool("add", "--made", made, "--answer", bad)[0], 1)
        code, out, _ = self.run_tool("add", "--made", made,
                                     "--answer", self.file("a1.json", answer("t-root", "n-root")))
        self.assertEqual(code, 0)
        self.assertIn("not checked", out)
        code, _, err = self.run_tool("root", "--name", "ai-root")
        self.assertEqual(code, 1)
        self.assertIn("REFUSED", err)
        code, out, _ = self.run_tool("tab", "--parent", "n-root", "--name", "q")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["node"], "n-root")
        entry = self.file("tab.json", out)
        self.assertEqual(self.run_tool("add", "--made", entry, "--answer",
                                       self.file("a2.json", answer("t-q", "n-q")))[0], 0)
        with open(self.path, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["ai_root"],
                             [{"node": "n-root", "tab": "t-root"}, {"node": "n-q", "tab": "t-q"}])

    def test_the_notebook_file_the_guard_reads(self):
        here = os.path.join(self.tmp.name, "a", "b")
        os.makedirs(here)
        self.assertEqual(ai_tab.find(here, {}), self.path)
        # N4: under CLAUDE_PROJECT_DIR first, as the guard reads it
        with tempfile.TemporaryDirectory() as other:
            os.mkdir(os.path.join(other, ".principal"))
            theirs = os.path.join(other, ".principal", "notebook.json")
            with open(theirs, "w", encoding="utf-8") as fh:
                json.dump(UNSET, fh)
            self.assertEqual(ai_tab.find(here, {"CLAUDE_PROJECT_DIR": other}), theirs)
            self.assertEqual(ai_tab.find(here, {"CLAUDE_PROJECT_DIR": here}), self.path)


if __name__ == "__main__":
    unittest.main()
