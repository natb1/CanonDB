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
        self.envelope = portable.seal(self.graph, name="a notebook",
                                      tools="somewhere/tools")
        with open(VALID, encoding="utf-8") as fh:
            self.data = json.load(fh)

    def test_the_envelope_says_what_it_is(self):
        self.assertEqual(self.envelope["format"], portable.FORMAT)
        self.assertEqual(self.envelope["name"], "a notebook")
        self.assertEqual(self.envelope["tools"], "somewhere/tools")

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


class SelfLinkTest(unittest.TestCase):
    """An application whose link is the document is a binding in content's clothes."""

    def setUp(self):
        with open(VALID, encoding="utf-8") as fh:
            self.data = json.load(fh)
        thesis = self.data["questions"][0]["theses"][0]
        thesis.setdefault("applications", []).append({
            "name": "the notebook itself",
            "what": "this notebook",
            "link": "[it](%s)" % self.data["artifact"],
            "standing": "postulate",
        })
        self.path = graph_file(self.data)
        self.envelope = portable.seal(model.load(self.path))

    def applications(self, envelope):
        return [a for q in envelope["questions"] for t in q["theses"]
                for a in t.get("applications", [])]

    def test_the_self_link_is_found(self):
        found = portable.self_links(self.data)
        self.assertEqual(found, [{"question": self.data["questions"][0]["id"],
                                  "thesis": self.data["questions"][0]["theses"][0]["title"],
                                  "application": "the notebook itself"}])

    def test_a_link_to_somewhere_else_is_not_a_binding(self):
        data = copy.deepcopy(self.data)
        for t in data["questions"][0]["theses"]:
            for a in t["applications"]:
                a["link"] = "[elsewhere](https://example.invalid/x)"
        self.assertEqual(portable.self_links(data), [])

    def test_a_graph_with_no_artifact_has_no_self_links(self):
        data = copy.deepcopy(self.data)
        data["artifact"] = ""
        self.assertEqual(portable.self_links(data), [])

    def test_the_envelope_carries_no_link_to_the_old_document(self):
        self.assertNotIn(self.data["artifact"], json.dumps(self.envelope))

    def test_the_application_itself_survives(self):
        carried = [a for a in self.applications(self.envelope)
                   if a["name"] == "the notebook itself"]
        self.assertEqual(len(carried), 1)
        self.assertEqual(carried[0]["what"], "this notebook")
        self.assertEqual(carried[0]["link"], "")

    def test_where_it_stood_is_recorded_for_rebinding(self):
        self.assertEqual(self.envelope["rebind"], portable.self_links(self.data))

    def test_an_unbound_graph_has_nothing_left_to_rebind(self):
        reopened = graph_file(portable.unseal(self.envelope))
        self.assertEqual(portable.seal(model.load(reopened))["rebind"], [])

    def test_the_drop_report_names_it(self):
        code, _, err = run(["seal", self.path, "-o", graph_file({}), "--verbose"])
        self.assertEqual(code, 0)
        self.assertIn("the notebook itself.link=the document itself", err)

    def test_sealing_does_not_touch_the_graph_file(self):
        with open(self.path, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh), self.data)


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
        code, _, err = run(["seal", VALID, "-o", env, "--verbose"])
        self.assertEqual(code, 0)
        with open(VALID, encoding="utf-8") as fh:
            expected = portable.bindings(json.load(fh))
        for line in expected:
            self.assertIn("dropped %s" % line, err)

    def test_seal_counts_the_bindings_rather_than_naming_them(self):
        env = self.path("e.json")
        code, _, err = run(["seal", VALID, "-o", env])
        self.assertEqual(code, 0)
        with open(VALID, encoding="utf-8") as fh:
            expected = portable.bindings(json.load(fh))
        self.assertIn("%d binding(s) dropped" % len(expected), err)
        self.assertNotIn("dropped %s" % expected[0], err)

    def test_seal_writes_to_stdout_when_asked_for_no_file(self):
        code, out, _ = run(["seal", VALID])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["format"], portable.FORMAT)

    def test_seal_records_where_the_tooling_is_kept(self):
        code, out, _ = run(["seal", VALID, "--tools", "repo/tools"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["tools"], "repo/tools")

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


class ResealTest(unittest.TestCase):
    """The envelope brought up to date, rather than sealed again from scratch."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.graph = model.load(VALID)
        self.envelope = os.path.join(self.dir, "notebook.json")
        with open(self.envelope, "w", encoding="utf-8") as fh:
            fh.write(portable.dump(portable.seal(
                self.graph, name="a notebook", tools="somewhere/tools")))

    def moved(self, change):
        """A graph like VALID with `change(data)` applied, on disk."""
        with open(VALID, encoding="utf-8") as fh:
            data = json.load(fh)
        change(data)
        return model.load(graph_file(data))

    def shrink(self):
        """Put a question in the envelope that the graph does not have.

        A question is added to the envelope rather than cut from the fixture,
        because cutting one leaves a graph the checker faults for other
        reasons, and this is a test about dropping and not about those.
        """
        with open(self.envelope, encoding="utf-8") as fh:
            data = json.load(fh)
        data["questions"].append(dict(data["questions"][0], id="gone"))
        with open(self.envelope, "w", encoding="utf-8") as fh:
            fh.write(portable.dump(data))

    def test_a_reseal_carries_the_name_and_tools_forward(self):
        graph = self.moved(lambda d: d["questions"][0].update(pressure=3))
        portable.reseal(graph, self.envelope)
        with open(self.envelope, encoding="utf-8") as fh:
            after = json.load(fh)
        self.assertEqual(after["name"], "a notebook")
        self.assertEqual(after["tools"], "somewhere/tools")

    def test_carried_is_what_the_replaced_file_said(self):
        with open(self.envelope, encoding="utf-8") as fh:
            self.assertEqual(portable.carried(json.load(fh)),
                             {"name": "a notebook", "tools": "somewhere/tools"})

    def test_a_reseal_that_changes_nothing_leaves_the_file_alone(self):
        with open(self.envelope, "rb") as fh:
            before = fh.read()
        self.assertEqual(portable.reseal(self.graph, self.envelope), [])
        with open(self.envelope, "rb") as fh:
            self.assertEqual(fh.read(), before)

    def test_drift_names_the_question_that_moved(self):
        graph = self.moved(lambda d: d["questions"][0].update(pressure=3))
        changed = portable.reseal(graph, self.envelope)
        self.assertIn("~ 1 question(s): ti-esti", changed)

    def test_drift_says_the_shape_and_never_the_notebook(self):
        graph = self.moved(lambda d: d["questions"][0].update(pressure=3))
        _, changed = portable.compare(graph, self.envelope)
        said = " ".join(changed)
        for q in self.graph.questions:
            for thesis in q.theses:
                self.assertNotIn(thesis.title, said)

    def test_drift_stops_naming_ids_at_a_bound(self):
        many = [str(n) for n in range(portable.NAMED * 3)]
        phrase = portable.named(many)
        self.assertIn("and %d more" % (len(many) - portable.NAMED), phrase)
        self.assertLessEqual(phrase.count(","), portable.NAMED)

    def test_drift_names_them_all_while_they_are_few(self):
        self.assertEqual(portable.named(["b", "a"]), "a, b")

    def test_a_header_value_that_moved_is_named_by_key(self):
        current = portable.seal(self.graph, name="another notebook",
                                tools="somewhere/tools")
        with open(self.envelope, encoding="utf-8") as fh:
            self.assertEqual(portable.drift(json.load(fh), current), ["~ name"])

    def test_dropped_names_what_the_envelope_has_and_the_graph_does_not(self):
        self.shrink()
        self.assertEqual(portable.dropped(self.graph, self.envelope), ["gone"])

    def test_nothing_is_dropped_by_a_graph_that_still_holds_them(self):
        self.assertEqual(portable.dropped(self.graph, self.envelope), [])

    def test_a_file_that_is_not_an_envelope_is_told_apart_from_a_stale_one(self):
        with self.assertRaises(ValueError):
            portable.compare(self.graph, VALID)

    def test_committed_finds_the_envelope_by_its_own_format(self):
        self.assertEqual(portable.committed(self.dir), self.envelope)

    def test_committed_passes_over_json_that_is_not_one(self):
        with open(os.path.join(self.dir, "a-decoy.json"), "w",
                  encoding="utf-8") as fh:
            json.dump({"format": "something-else"}, fh)
        self.assertEqual(portable.committed(self.dir), self.envelope)

    def test_committed_says_so_where_there_is_none(self):
        self.assertEqual(portable.committed(tempfile.mkdtemp()), "")


class ResealCommandTest(ResealTest):
    def test_reseal_brings_a_stale_envelope_up_to_date(self):
        graph = self.moved(lambda d: d["questions"][0].update(pressure=3))
        code, _, err = run(["reseal", graph.path, self.envelope])
        self.assertEqual(code, 0, err)
        self.assertIn("re-sealed", err)
        self.assertIn("~ 1 question(s): ti-esti", err)

    def test_reseal_says_when_there_is_nothing_to_do(self):
        code, _, err = run(["reseal", VALID, self.envelope])
        self.assertEqual(code, 0, err)
        self.assertIn("is current", err)

    def test_reseal_refuses_a_shrink_and_leaves_the_file(self):
        self.shrink()
        with open(self.envelope, "rb") as fh:
            before = fh.read()
        code, _, err = run(["reseal", VALID, self.envelope])
        self.assertEqual(code, 1)
        self.assertIn("would drop 1 question(s): gone", err)
        with open(self.envelope, "rb") as fh:
            self.assertEqual(fh.read(), before)

    def test_force_seals_a_shrink_that_is_meant(self):
        self.shrink()
        code, _, err = run(["reseal", VALID, self.envelope, "--force"])
        self.assertEqual(code, 0, err)
        with open(self.envelope, encoding="utf-8") as fh:
            self.assertNotIn("gone", [q["id"] for q in json.load(fh)["questions"]])

    def test_reseal_refuses_a_graph_the_checker_faults(self):
        bad = os.path.join(FIXTURES, "invalid-one-root.json")
        code, _, err = run(["reseal", bad, self.envelope])
        self.assertEqual(code, 1)
        self.assertIn("refusing to re-seal", err)

    def test_stale_exits_one_and_says_what_moved(self):
        graph = self.moved(lambda d: d["questions"][0].update(pressure=3))
        code, out, _ = run(["stale", graph.path, self.envelope])
        self.assertEqual(code, 1)
        self.assertIn("is stale", out)
        self.assertIn("~ 1 question(s): ti-esti", out)

    def test_stale_exits_zero_on_a_current_envelope(self):
        code, out, _ = run(["stale", VALID, self.envelope])
        self.assertEqual(code, 0)
        self.assertIn("is current", out)

    def test_stale_writes_nothing(self):
        graph = self.moved(lambda d: d["questions"][0].update(pressure=3))
        with open(self.envelope, "rb") as fh:
            before = fh.read()
        run(["stale", graph.path, self.envelope])
        with open(self.envelope, "rb") as fh:
            self.assertEqual(fh.read(), before)

    def test_a_named_file_that_is_not_an_envelope_is_reported(self):
        code, _, err = run(["reseal", VALID, VALID])
        self.assertEqual(code, 1)
        self.assertIn("ERROR envelope", err)


if __name__ == "__main__":
    unittest.main()
