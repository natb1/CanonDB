"""Sealing parts the notebook from its document, and nothing else."""

import copy
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

import portable as cli
from hypo import model, portable, project, spec

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
VALID = os.path.join(FIXTURES, "valid.json")

#: what the tests wrote to disk, removed once the module is done with them
_TEMP = []


def graph_file(data):
    """Write a graph dict to a temp file and return its path."""
    handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                         encoding="utf-8")
    json.dump(data, handle)
    handle.close()
    _TEMP.append(handle.name)
    return handle.name


def scratch():
    """A temp directory that is removed once the module is done with it."""
    where = tempfile.mkdtemp()
    _TEMP.append(where)
    return where


def tearDownModule():
    for path in _TEMP:
        if os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)
        elif os.path.exists(path):
            os.unlink(path)


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


def as_v1(envelope):
    """The same envelope as `hypomnemata-export/1` sealed it.

    That format hung the glossary off the answer that used a word rather than
    off the question, so an old envelope is reconstructed by pushing every
    question's definitions back down onto its first thesis — which is where the
    reader had already filed them, and so where an old file has them.
    """
    old = copy.deepcopy(envelope)
    old["format"] = "hypomnemata-export/1"
    for q in old["questions"]:
        words = q.pop("definitions", [])
        if words:
            q["theses"][0]["definitions"] = words
    return old


class OlderFormatTest(unittest.TestCase):
    """An envelope outlives the tooling that sealed it, so it is read forward."""

    def setUp(self):
        self.graph = model.load(VALID)
        self.envelope = portable.seal(self.graph)
        self.old = as_v1(self.envelope)

    def test_the_old_shape_is_the_one_the_model_refuses(self):
        # the premise: without the forward step this is what the receiving
        # party would be handed, and it is a graph the checker will not take
        raw = copy.deepcopy(self.old)
        for q in raw["questions"]:
            q["tab"], q["body"] = "t", "b"
        held = [q for q in raw["questions"] if q["theses"][0].get("definitions")]
        self.assertTrue(held)
        with self.assertRaises(model.ShapeError):
            model.load(graph_file({"artifact": "a", "mode": raw["mode"],
                                   "state_enum": "e",
                                   "questions": raw["questions"]}))

    def test_an_older_envelope_opens(self):
        data, notes = portable.opened(self.old)
        self.assertEqual([q["id"] for q in data["questions"]],
                         [q["id"] for q in self.envelope["questions"]])
        self.assertTrue(notes)

    def test_it_opens_to_what_the_current_format_opens_to(self):
        self.assertEqual(portable.unseal(self.old),
                         portable.unseal(self.envelope))

    def test_the_words_come_up_whole_and_in_order(self):
        data = portable.unseal(self.old)
        for came, want in zip(data["questions"], self.envelope["questions"]):
            self.assertEqual(came.get("definitions", []),
                             want.get("definitions", []))
            for t in came["theses"]:
                self.assertNotIn("definitions", t)

    def test_the_current_format_says_nothing(self):
        self.assertEqual(portable.opened(self.envelope)[1], [])

    def test_every_format_read_is_one_the_current_one_or_has_a_step(self):
        for fmt in portable.READS:
            self.assertTrue(fmt == portable.FORMAT or fmt in portable.FORWARD)

    def test_an_older_envelope_is_found_where_it_is_committed(self):
        where = scratch()
        path = os.path.join(where, "carried.json")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(portable.dump(self.old))
        self.assertEqual(portable.committed(where), path)

    def test_an_older_envelope_is_stale_by_its_format(self):
        where = scratch()
        path = os.path.join(where, "carried.json")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(portable.dump(self.old))
        _, changed = portable.compare(self.graph, path)
        self.assertIn("~ format", changed)

    def test_resealing_brings_a_carried_copy_forward(self):
        where = scratch()
        path = os.path.join(where, "carried.json")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(portable.dump(self.old))
        portable.reseal(self.graph, path)
        with open(path, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["format"], portable.FORMAT)

    def test_open_says_what_it_read_forward(self):
        where = scratch()
        path = os.path.join(where, "carried.json")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(portable.dump(self.old))
        code, _, err = run(["open", path, "-o", os.path.join(where, "g.json")])
        self.assertEqual(code, 0)
        self.assertIn("read forward", err)
        self.assertIn("definition(s)", err)


class CommandTest(unittest.TestCase):
    def setUp(self):
        self.dir = scratch()

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

    def test_open_refuses_an_envelope_whose_questions_are_not_objects(self):
        """Refused in the same line every other malformed input gets, rather
        than a traceback out of the loop that empties the bindings."""
        bad = graph_file({"format": portable.FORMAT, "questions": [1]})
        code, _, err = run(["open", bad, "-o", self.path("g.json")])
        self.assertEqual(code, 1)
        self.assertIn("ERROR envelope", err)


class ResealTest(unittest.TestCase):
    """The envelope brought up to date, rather than sealed again from scratch."""

    def setUp(self):
        self.dir = scratch()
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

    def test_an_unbound_graph_does_not_drift_on_what_is_owed_a_link(self):
        """Opened from an envelope, a graph names no document, so nothing in
        it links to one; the self-links the envelope recorded are waiting to
        be bound, and are not a drift."""
        def self_link(data):
            app = data["questions"][0]["theses"][0]["applications"][0]
            app["link"] = data["artifact"]
        bound = self.moved(self_link)
        sealed = portable.seal(bound, name="a notebook", tools="somewhere/tools")
        self.assertEqual(len(sealed["rebind"]), 1)
        with open(self.envelope, "w", encoding="utf-8") as fh:
            fh.write(portable.dump(sealed))

        def unbind(data):
            self_link(data)
            data["artifact"] = ""
            data["questions"][0]["theses"][0]["applications"][0]["link"] = ""
        unbound = self.moved(unbind)
        current, changed = portable.compare(unbound, self.envelope)
        self.assertEqual(changed, [])
        self.assertEqual(current["rebind"], sealed["rebind"])
        _, changed = portable.compare(bound, self.envelope)
        self.assertEqual(changed, [])

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
        self.assertEqual(portable.committed(scratch()), "")


class WhereTest(unittest.TestCase):
    """The committed envelope is found from where the run is made."""

    def setUp(self):
        self.cwd = os.getcwd()
        self.repo = scratch()
        os.mkdir(os.path.join(self.repo, ".git"))
        self.inside = os.path.join(self.repo, "deep", "er")
        os.makedirs(self.inside)

    def tearDown(self):
        os.chdir(self.cwd)

    def envelope_at(self, where, name="carried.json"):
        path = os.path.join(where, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(portable.dump(portable.seal(model.load(VALID), name="n",
                                                 tools="t")))
        return path

    def test_here_is_the_repository_the_run_is_made_from(self):
        os.chdir(self.inside)
        self.assertEqual(os.path.realpath(portable.here()),
                         os.path.realpath(self.repo))

    def test_here_is_nothing_where_no_repository_holds_the_run(self):
        outside = scratch()
        os.chdir(outside)
        self.assertNotEqual(os.path.realpath(portable.here() or "/"),
                            os.path.realpath(outside))

    def test_roots_put_the_run_s_repository_before_the_tooling_s(self):
        os.chdir(self.inside)
        found = [os.path.realpath(r) for r in portable.roots()]
        self.assertEqual(found[0], os.path.realpath(self.repo))
        self.assertIn(os.path.realpath(portable.root()), found)

    def test_roots_fall_back_to_the_tooling_s_branch_root(self):
        os.chdir(scratch())
        self.assertEqual(portable.roots()[-1], portable.root())

    def test_committed_takes_the_first_root_that_holds_an_envelope(self):
        other = scratch()
        mine = self.envelope_at(self.repo)
        self.envelope_at(other)
        self.assertEqual(portable.committed(scratch(), self.repo, other), mine)
        self.assertEqual(portable.committed(scratch(), scratch()), "")

    def test_a_run_from_another_notebook_s_checkout_reaches_its_envelope(self):
        """The tooling serves more than one notebook: the one kept beside
        it, and any raised from an envelope in a repository of its own."""
        mine = self.envelope_at(self.repo)
        os.chdir(self.inside)
        self.assertEqual(portable.committed(*portable.roots()), mine)


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


class CommittedEnvelopeTest(unittest.TestCase):
    """The envelope committed at the branch root, against the tooling beside it.

    It carries copies of what the tooling says — the format, the states, the
    rebuild steps — and a commit that moves only the tooling moves nothing of
    the notebook, so no read re-seals it. The suite runs on every commit, so
    this is where that drift is caught.
    """

    def setUp(self):
        self.path = portable.committed(portable.root())
        if not self.path:
            self.skipTest("no envelope is committed at the branch root")
        with open(self.path, encoding="utf-8") as fh:
            self.envelope = json.load(fh)

    def test_it_is_in_the_current_format(self):
        self.assertEqual(self.envelope["format"], portable.FORMAT)

    def test_it_carries_the_tooling_s_states_and_steps(self):
        self.assertEqual(self.envelope["states"], list(model.STATES))
        self.assertEqual(self.envelope["rebuild"], portable.STEPS)

    def test_it_is_written_as_a_re_seal_would_write_it(self):
        with open(self.path, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), portable.dump(self.envelope))

    def test_bound_it_stands_and_comes_out_to_what_it_expects(self):
        data = portable.unseal(self.envelope)
        data["artifact"] = "https://example.invalid/artifact/x"
        data["state_enum"] = "enum-x"
        for n, q in enumerate(data["questions"]):
            q["tab"], q["body"] = "t%d" % n, "b%d" % n
        graph = model.load(graph_file(data))
        self.assertEqual([f.line() for f in spec.errors(spec.run(graph))], [])
        expect = self.envelope["expect"]
        self.assertEqual(len(graph.questions), expect["questions"])
        self.assertEqual(portable.tree(graph), expect["tree"])


if __name__ == "__main__":
    unittest.main()
