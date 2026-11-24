"""The notebook's write gate: the recorder writes the notebook, no other
helper does, and the main thread keeps what the harness gives it."""

import importlib.util
import itertools
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
GATE = os.path.join(ROOT, "hooks", "notebook-gate.py")
HOOKS = os.path.join(ROOT, "hooks", "hooks.json")

NOTEBOOK = "0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0"
OTHER = "11111111-2222-3333-4444-555555555555"
SITE = "https://example.invalid/code/artifact/"

#: the shapes a document's id is written in, the notebook's
SHAPES = {
    "bare": NOTEBOOK,
    "upper": NOTEBOOK.upper(),
    "link": SITE + NOTEBOOK,
    "titled": SITE + "My-Notebook-" + NOTEBOOK,
    "titled-query": SITE + "Notebook-" + NOTEBOOK + "?tab=1#top",
    "slash": SITE + NOTEBOOK + "/",
}
#: shapes only a call is seen to send
LOOSE = {
    "edit": SITE + NOTEBOOK + "/edit",
    "param": NOTEBOOK + ";x=1",
    "dot": NOTEBOOK + ".",
}

PREFIXES = ("mcp__claude_ai_Claude_Docs__", "mcp__Claude_Docs__")
WRITES = [p + v for p in PREFIXES for v in ("update", "batch", "create", "delete")]
UPDATE, BATCH, CREATE = (PREFIXES[0] + v for v in ("update", "batch", "create"))
#: the plugin's kinds that hold no writing tool
SILENT = ("checker", "clean-reader", "coordinator", "fetcher", "grader", "reviewer")
#: helpers this plugin does not define, or does not define under that name
FOREIGN = ("fork", "general-purpose", "Explore", "other:recorder", "x:y:recorder",
           ":recorder", "my-recorder", "recorder ", "Recorder", "other:interviewer", 7,
           ["recorder"], {"a": 1}, True)

NO_ENV = {}


def load_gate():
    spec = importlib.util.spec_from_file_location("notebook_gate", GATE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RECORDER = os.path.join(ROOT, "agents", "recorder.md")


def define(root, text=None, kind="recorder"):
    """The project's own `.claude/agents/<kind>.md`: this plugin's, byte
    for byte, or ``text``."""
    os.makedirs(os.path.join(root, ".claude", "agents"), exist_ok=True)
    with open(os.path.join(ROOT, "agents", kind + ".md"), "rb") as fh:
        mine = fh.read()
    with open(os.path.join(root, ".claude", "agents", kind + ".md"), "wb") as fh:
        fh.write(mine if text is None else text)


def project(named=None, raw=None, recorder=True):
    """A project directory, with `.principal/notebook.json` holding ``named``
    as JSON or ``raw`` as text; with neither, no such file. Unless
    ``recorder`` is false, it defines the bare recorder as this repository's
    checkout does."""
    tmp = tempfile.TemporaryDirectory()
    if recorder:
        define(tmp.name)
    if named is not None or raw is not None:
        os.mkdir(os.path.join(tmp.name, ".principal"))
        with open(os.path.join(tmp.name, ".principal", "notebook.json"), "w",
                  encoding="utf-8") as fh:
            fh.write(raw if raw is not None else json.dumps(named))
    return tmp


def call(cwd, agent="principal:interviewer", tool=UPDATE, tool_input=None,
         container=NOTEBOOK):
    c = {"cwd": cwd, "tool_name": tool,
         "tool_input": tool_input if tool_input is not None
         else {"container": {"kind": "project", "id": container},
               "ref": {"object": "node", "id": "b1"}, "payload": {}}}
    if agent is not None:
        c["agent_type"] = agent
    return c


class Base(unittest.TestCase):
    NAMED = {"artifact": SITE + NOTEBOOK, "project": "x"}

    def setUp(self):
        self.gate = load_gate()
        self.tmp = project(self.NAMED)
        self.root = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def decide(self, c, env=NO_ENV, plugin="principal"):
        return self.gate.decide(c, env=env, plugin=plugin)

    def decision(self, c, **kw):
        return self.decide(c, **kw)["hookSpecificOutput"]["permissionDecision"]

    def reason(self, c, **kw):
        return self.decide(c, **kw)["hookSpecificOutput"]["permissionDecisionReason"]

    def refused(self, c, **kw):
        self.assertEqual(self.reason(c, **kw), self.gate.REFUSED, c)

    def unclear(self, c, **kw):
        self.assertEqual(self.reason(c, **kw), self.gate.UNCLEAR, c)

    def silent(self, c, **kw):
        self.assertEqual(self.decide(c, **kw), {}, c)


class WhoTest(Base):
    def test_the_main_thread_keeps_what_it_had(self):
        # an entry point there among them
        self.silent(call(self.root, agent=None))
        self.silent(call(self.root, agent=""))

    def test_the_recorder_writes_it(self):
        for agent in ("recorder", "principal:recorder"):
            for tool in WRITES:
                if tool.endswith("delete"):
                    # round 1c's minor 13: no helper deletes the notebook
                    self.refused(call(self.root, agent, tool))
                else:
                    self.silent(call(self.root, agent, tool))

    def test_without_the_plugin_s_name_only_the_bare_recorder_writes(self):
        self.silent(call(self.root, "recorder"), plugin="")
        self.refused(call(self.root, "principal:recorder"), plugin="")

    def test_a_bare_recorder_the_project_does_not_define_as_ours_is_a_helper(self):
        """Review B's and round one's minor 13: elsewhere a bare `recorder`
        is a project's or a user's own agent."""
        with project(self.NAMED, recorder=False) as other:
            self.refused(call(other, "recorder"))
            self.silent(call(other, "principal:recorder"))
            define(other, b"---\nname: recorder\n---\nmine\n")
            self.refused(call(other, "recorder"))
            self.refused(call(os.path.join(other, ".principal"), "recorder"))
            # round 1c's S3: a helper's ref to a part of another document
            self.unclear(call(other, "recorder", container=OTHER))
            define(other)
            self.silent(call(os.path.join(other, ".principal"), "recorder"))

    def test_a_kind_with_no_writing_tool_is_refused_every_write(self):
        for agent in SILENT:
            define(self.root, kind=agent)
            for named in (agent, "principal:" + agent):
                for tool in WRITES:
                    self.refused(call(self.root, named, tool))
                    self.refused(call(self.root, named, tool, container=OTHER))
                    self.refused(call(self.root, named, tool, tool_input="junk"))
        with project() as bare:
            self.silent(call(bare, "fetcher"))
            self.refused(call(bare, "principal:fetcher"))
            define(bare, kind="fetcher")
            self.refused(call(bare, "fetcher"))

    def test_minor_6_a_project_s_own_kind_of_the_same_name_is_a_helper(self):
        """A bare `reviewer` or `coordinator` the project does not define as
        this plugin does is that project's own agent: refused the notebook,
        as any helper is, and no opinion on another document or where no
        notebook is."""
        for agent in SILENT:
            with self.subTest(agent=agent):
                self.refused(call(self.root, agent))
                # round 1c's S2: in a project that names a notebook a bare
                # name is the kind, its copy differing or missing
                self.refused(call(self.root, agent, container=OTHER))
                with tempfile.TemporaryDirectory() as elsewhere:
                    self.silent(call(elsewhere, agent))
                    define(elsewhere, b"---\nname: %s\n---\nmine\n" % agent.encode(),
                           kind=agent)
                    self.silent(call(elsewhere, agent))

    def test_minor_7_without_the_plugin_s_name_any_name_ending_in_a_kind_is_it(self):
        for agent in ("principal:checker", "x:reviewer", "y:coordinator"):
            self.refused(call(self.root, agent, container=OTHER), plugin="")
        self.unclear(call(self.root, "other:checker", container=OTHER))
        self.silent(call(self.root, "other:checker", tool_input={
            "container": {"kind": "project", "id": OTHER}, "payload": {}}))

    def test_the_interviewer_is_refused_the_notebook(self):
        for agent in ("interviewer", "principal:interviewer"):
            for tool in WRITES:
                self.refused(call(self.root, agent, tool))

    def test_the_interviewer_writes_its_own_record(self):
        for verb in ("update", "create", "batch"):
            for prefix in PREFIXES:
                tool = prefix + verb
                self.silent(call(self.root, "interviewer", tool, container=OTHER))
                self.refused(call(self.root, "interviewer", tool))

    def test_a_helper_the_plugin_does_not_define_is_refused_the_notebook(self):
        # a fork or a general helper of the interviewer's, or one under a
        # name that only ends in the writer's
        for agent in FOREIGN:
            self.refused(call(self.root, agent))
            # round 1c's S3: a part of another document by a node ref is unclear
            self.unclear(call(self.root, agent, container=OTHER))
            self.silent(call(self.root, agent, tool_input={
                "container": {"kind": "project", "id": OTHER},
                "ref": {"object": "project", "id": OTHER}, "payload": {}}))

    def test_a_tool_it_does_not_guard_is_not_the_gate_s(self):
        for tool in ("Read", PREFIXES[0] + "read", PREFIXES[1] + "guide",
                     PREFIXES[0] + "query"):
            for agent in ("fetcher", "interviewer", "fork"):
                self.silent(call(self.root, agent, tool))

    def test_the_plugin_s_name_is_read_from_its_manifest(self):
        self.assertEqual(self.gate.plugin_name(), "principal")
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "plugin.json")
            self.assertEqual(self.gate.plugin_name(path), "")
            for text in ("{not json", "[1]", '{"name": 7}', '{"x": 1}'):
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(text)
                self.assertEqual(self.gate.plugin_name(path), "", text)
            with open(path, "w", encoding="utf-8-sig") as fh:
                fh.write('{"name": "other"}')
            self.assertEqual(self.gate.plugin_name(path), "other")

    def test_not_a_call(self):
        for junk in (None, [], ["interviewer"], "interviewer", 7):
            self.silent(junk)
        self.silent({})


class WhereTest(Base):
    """The notebook is the project's, wherever in it the shell stands."""

    def test_a_cd_does_not_move_the_guard(self):
        deep = os.path.join(self.root, "tools", "hypo")
        os.makedirs(deep)
        self.refused(call(os.path.join(self.root, "tools")))
        self.refused(call(deep))
        self.refused(call(os.path.join(self.root, "tools", "..", "tools")))

    def test_the_project_dir_comes_first(self):
        with tempfile.TemporaryDirectory() as elsewhere:
            env = {"CLAUDE_PROJECT_DIR": self.root}
            self.refused(call(elsewhere), env=env)
            self.silent(call(elsewhere))
        with project({"artifact": SITE + OTHER}) as there:
            # the harness's project names another notebook than where the shell is
            env = {"CLAUDE_PROJECT_DIR": there}
            self.silent(call(self.root), env=env)
            self.refused(call(self.root, container=OTHER), env=env)

    def test_a_project_dir_with_no_notebook_falls_to_the_cwd(self):
        with project() as bare:
            self.refused(call(self.root), env={"CLAUDE_PROJECT_DIR": bare})
        self.refused(call(self.root), env={"CLAUDE_PROJECT_DIR": ""})

    def test_the_nearest_notebook_file_wins(self):
        inner = os.path.join(self.root, "sub")
        os.makedirs(os.path.join(inner, ".principal"))
        with open(os.path.join(inner, ".principal", "notebook.json"), "w") as fh:
            json.dump({"artifact": OTHER}, fh)
        self.silent(call(inner))
        self.refused(call(inner, container=OTHER))

    def test_a_project_with_no_notebook_has_nothing_to_guard(self):
        with project() as bare:
            for agent in ("interviewer", "fork", "general-purpose"):
                self.silent(call(bare, agent))

    def test_a_byte_order_mark_is_read_past(self):
        with project(raw="﻿" + json.dumps({"artifact": NOTEBOOK})) as there:
            self.refused(call(there))
            self.silent(call(there, container=OTHER))


class IdTest(Base):
    """An id, bare or in a link, titled or not, on either side."""

    def fields(self, value):
        """The calls that name a document by ``value``, one per field."""
        return [
            call(self.root, container=value),
            call(self.root, tool_input={"ref": {"object": "project", "id": value},
                                        "payload": {}}),
            call(self.root, tool=CREATE, tool_input={"artifact": value, "object": "node",
                                                     "payload": {}}),
            call(self.root, tool=BATCH, tool_input={
                "container": {"kind": "project", "id": OTHER},
                "batch": [{"verb": "update", "ref": {"object": "project", "id": value}}]}),
            call(self.root, tool=BATCH, tool_input={
                "container": {"kind": "project", "id": OTHER},
                "batch": [{"verb": "update", "container": {"kind": "project", "id": value},
                           "ref": {"object": "node", "id": "b1"}}]}),
            call(self.root, tool=BATCH, tool_input={
                "container": {"kind": "project", "create": {"name": "n", "artifact": value}},
                "batch": []}),
        ]

    def write(self, artifact):
        with open(os.path.join(self.root, ".principal", "notebook.json"), "w") as fh:
            json.dump({"artifact": artifact}, fh)

    def test_every_shape_on_each_side_and_in_every_field(self):
        for (fname, filed), (cname, sent) in itertools.product(SHAPES.items(),
                                                               {**SHAPES, **LOOSE}.items()):
            self.write(filed)
            for c in self.fields(sent):
                self.assertEqual(self.reason(c), self.gate.REFUSED, (fname, cname, c))

    def test_another_document_in_every_shape_is_not_the_gate_s(self):
        for fname, filed in SHAPES.items():
            self.write(filed)
            for sent in (OTHER, SITE + OTHER, SITE + "Notebook-" + OTHER):
                for c in self.fields(sent):
                    self.silent(c)

    def test_an_id_that_is_not_a_uuid(self):
        self.write(SITE + "My-Notes-AbCdEfGhIjKlMnOpQrStUv")
        for sent in ("AbCdEfGhIjKlMnOpQrStUv", SITE + "AbCdEfGhIjKlMnOpQrStUv",
                     SITE + "Other-Title-abcdefghijklmnopqrstuv"):
            self.refused(call(self.root, container=sent))
        self.silent(call(self.root, container="ZyXwVuTsRqPoNmLkJiHgFe"))

    def test_the_trailing_id(self):
        doc_id = self.gate.doc_id
        self.assertEqual(doc_id(SHAPES["titled-query"]), NOTEBOOK)
        self.assertEqual(doc_id(" " + NOTEBOOK.upper() + " "), NOTEBOOK)
        self.assertEqual(doc_id(SITE + "Notes-abcdefghijklmnopqrstuv"), "abcdefghijklmnopqrstuv")
        self.assertEqual(doc_id("Notes-short"), "notes-short")
        self.assertEqual(doc_id(42), "42")

    def test_a_notebook_id_too_short_to_look_for(self):
        self.write("ab")
        self.unclear(call(self.root, container=OTHER))


class AimTest(Base):
    """Which fields address a document, and what a call that names none gets."""

    def test_artifact_is_read_on_create_only(self):
        self.unclear(call(self.root, tool=UPDATE, tool_input={
            "artifact": OTHER, "ref": {"object": "node", "id": "b1"}, "payload": {}}))
        self.silent(call(self.root, tool=CREATE, tool_input={
            "artifact": OTHER, "object": "node", "payload": {}}))

    def test_an_empty_artifact_is_absent(self):
        self.silent(call(self.root, tool=CREATE, tool_input={
            "artifact": "", "container": {"kind": "project", "id": OTHER},
            "object": "utterance", "payload": {}}))
        self.unclear(call(self.root, tool=CREATE, tool_input={"artifact": "", "payload": {}}))

    def test_a_new_document_is_not_the_notebook(self):
        for agent in ("interviewer", "general-purpose"):
            self.silent(call(self.root, agent, BATCH, tool_input={
                "container": {"kind": "project", "create": {"name": "n"}}, "batch": []}))
            self.silent(call(self.root, agent, BATCH, tool_input={
                "container": {"kind": "project", "create": None}}))

    def test_a_new_document_does_not_excuse_a_member_aimed_at_the_notebook(self):
        self.refused(call(self.root, tool=BATCH, tool_input={
            "container": {"kind": "project", "create": {"name": "n"}},
            "batch": [{"verb": "update", "ref": {"object": "project", "id": NOTEBOOK}}]}))

    def test_only_a_batch_creates(self):
        for tool in (UPDATE, CREATE, PREFIXES[0] + "delete"):
            self.unclear(call(self.root, tool=tool, tool_input={
                "container": {"kind": "project", "create": {}},
                "ref": {"object": "node", "id": "b1"}, "payload": {}}))

    def test_parts_given_as_text(self):
        text = json.dumps
        self.refused(call(self.root, tool_input={
            "container": text({"kind": "project", "id": NOTEBOOK})}))
        self.silent(call(self.root, tool_input={
            "container": text({"kind": "project", "id": OTHER})}))
        self.refused(call(self.root, tool_input={
            "ref": text({"object": "project", "id": NOTEBOOK})}))
        self.refused(call(self.root, tool=BATCH, tool_input={
            "container": {"kind": "project", "id": OTHER},
            "batch": text([{"ref": {"object": "project", "id": NOTEBOOK}}])}))
        self.refused(call(self.root, tool=BATCH, tool_input={
            "container": {"kind": "project", "id": OTHER},
            "batch": [text({"ref": {"object": "project", "id": NOTEBOOK}})]}))
        self.refused(call(self.root, tool=BATCH, tool_input={
            "container": {"kind": "project", "create": text({"artifact": NOTEBOOK})}}))

    def test_a_node_ref_names_no_document(self):
        self.unclear(call(self.root, tool_input={"ref": {"object": "node", "id": NOTEBOOK}}))
        self.unclear(call(self.root, "fork", tool_input={"ref": {"object": "node"}}))

    def test_the_payload_is_never_read(self):
        self.silent(call(self.root, tool_input={
            "container": {"kind": "project", "id": OTHER},
            "ref": {"object": "node", "id": "b1"},
            "payload": {"text": "see " + SITE + NOTEBOOK, "id": NOTEBOOK}}))


class UnclearTest(Base):
    """A helper's call the gate cannot make sense of is refused, with the
    sentence that says what to supply; the main thread's and the recorder's
    are nobody's to decide here."""

    def both(self, c):
        self.unclear(c)
        self.unclear(dict(c, agent_type="general-purpose"))
        self.silent(dict(c, agent_type="principal:recorder"))
        without = dict(c)
        without.pop("agent_type", None)
        self.silent(without)

    def test_no_tool(self):
        c = call(self.root)
        del c["tool_name"]
        self.both(c)
        self.both(dict(call(self.root), tool_name=7))

    def test_no_project(self):
        c = call(self.root)
        del c["cwd"]
        self.both(c)
        self.both(dict(call(self.root), cwd=""))
        self.both(dict(call(self.root), cwd=7))

    def test_input_that_is_not_an_object(self):
        self.both(call(self.root, tool_input="container"))
        self.both(call(self.root, tool_input=[NOTEBOOK]))

    def test_a_part_that_is_not_an_object(self):
        for part in ({"container": "{not json"}, {"container": [NOTEBOOK]}, {"ref": 7},
                     {"ref": "[1]"}, {"container": {"kind": "project", "create": 7}}):
            self.both(call(self.root, tool_input=part))

    def test_a_container_the_gate_does_not_know(self):
        for kind in ("file", None, 7):
            self.both(call(self.root, tool_input={
                "container": {"kind": kind, "id": OTHER},
                "ref": {"object": "node", "id": "b1"}}))

    def test_a_project_ref_with_no_id(self):
        self.both(call(self.root, tool_input={"ref": {"object": "project"}}))

    def test_an_id_that_is_not_one(self):
        for bad in ({"x": 1}, True, "", "/", 1.5, ["x"]):
            self.both(call(self.root, container=bad))
        self.both(call(self.root, tool=CREATE, tool_input={"artifact": ["x"]}))

    def test_an_integer_id_is_an_id(self):
        self.silent(call(self.root, container=42))

    def test_naming_no_document(self):
        self.both(call(self.root, tool_input={}))
        self.both(call(self.root, tool_input={"container": {"kind": "project"}}))
        self.both(call(self.root, tool=BATCH, tool_input={
            "container": {"kind": "project"}, "batch": []}))

    def test_a_batch_the_gate_cannot_read(self):
        base = {"container": {"kind": "project", "id": OTHER}}
        for members in ("{not json", 7, {"a": 1}, [None], [7], ["{not json"],
                        [{"container": {"kind": "file", "id": OTHER}}]):
            self.both(call(self.root, tool=BATCH, tool_input=dict(base, batch=members)))

    def test_a_notebook_file_the_gate_cannot_read(self):
        for named, raw in ((None, "{not json"), ([SITE + NOTEBOOK], None), ({"project": "x"}, None),
                           ({"artifact": ""}, None), ({"artifact": ["x"]}, None),
                           ({"artifact": "   "}, None), (None, "\xff\xfe")):
            with project(named, raw) as there:
                self.both(call(there))

    def test_a_notebook_file_that_is_a_directory(self):
        with project() as there:
            os.makedirs(os.path.join(there, ".principal", "notebook.json"))
            self.both(call(there))


class RefusalTest(Base):
    def test_two_refusals_that_say_different_things(self):
        self.assertNotEqual(self.gate.REFUSED, self.gate.UNCLEAR)
        self.refused(call(self.root))
        self.unclear(call(self.root, tool_input={}))

    def test_a_refusal_names_no_document(self):
        for reason in (self.gate.REFUSED, self.gate.UNCLEAR):
            self.assertNotIn(NOTEBOOK, reason)
            self.assertNotIn("http", reason)
            self.assertNotIn("\n", reason)

    def test_input_that_does_not_parse(self):
        unparsed = self.gate.unparsed
        self.assertEqual(unparsed(b"{not json", "principal"), {})
        self.assertEqual(unparsed(b'{"agent_type": "principal:recorder", x', "principal"), {})
        self.assertEqual(unparsed(b'{"agent_type": "", x', "principal"), {})
        for agent in (b"fork", b"principal:fetcher", b'a\\"b', b"\xff"):
            out = unparsed(b'{"agent_type": "' + agent + b'", x', "principal")
            self.assertEqual(out["hookSpecificOutput"]["permissionDecisionReason"],
                             self.gate.UNCLEAR, agent)

    def test_the_output_is_the_hook_s_shape(self):
        out = self.decide(call(self.root))
        self.assertEqual(out["hookSpecificOutput"]["hookEventName"], "PreToolUse")
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")


class ProcessTest(unittest.TestCase):
    """The hook as the harness runs it: the call on stdin, one JSON value on
    stdout, nothing on stderr, exit 0."""

    def setUp(self):
        self.tmp = project({"artifact": SITE + NOTEBOOK})
        self.root = self.tmp.name
        self.env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PROJECT_DIR"}

    def tearDown(self):
        self.tmp.cleanup()

    def run_hook(self, data, env=None):
        done = subprocess.run([sys.executable, "-B", GATE], input=data,
                              capture_output=True, env=env or self.env, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stderr, b"")
        lines = done.stdout.decode("utf-8").splitlines()
        self.assertEqual(len(lines), 1, lines)
        return json.loads(lines[0])

    def decision(self, answer):
        return answer["hookSpecificOutput"]["permissionDecision"]

    def test_a_refusal(self):
        self.assertEqual(self.decision(self.run_hook(json.dumps(call(self.root)).encode())),
                         "deny")

    def test_no_opinion(self):
        self.assertEqual(self.run_hook(json.dumps(call(self.root, "recorder")).encode()), {})

    def test_the_project_dir_from_the_environment(self):
        with tempfile.TemporaryDirectory() as elsewhere:
            data = json.dumps(call(elsewhere)).encode()
            self.assertEqual(self.run_hook(data), {})
            env = dict(self.env, CLAUDE_PROJECT_DIR=self.root)
            self.assertEqual(self.decision(self.run_hook(data, env)), "deny")

    def test_what_is_not_json_is_refused_to_a_helper(self):
        self.assertEqual(self.run_hook(b"{not json"), {})
        self.assertEqual(self.run_hook(b'{"agent_type": "principal:recorder", oops'), {})
        self.assertEqual(self.decision(self.run_hook(b'{"agent_type": "recorder", oops')),
                         "deny")
        self.assertEqual(self.run_hook(b'{"agent_type": "", oops'), {})
        self.assertEqual(self.decision(self.run_hook(
            b'{"agent_type": "principal:interviewer", oops')), "deny")
        self.assertEqual(self.decision(self.run_hook(
            b'{"agent_type": "fork", "x": "\xff"}')), "deny")

    def test_input_too_deep_to_parse(self):
        deep = b'{"agent_type": "fork", "payload": ' + b"[" * 300000 + b"]" * 300000 + b"}"
        self.assertEqual(self.decision(self.run_hook(deep)), "deny")
        deep = b'{"payload": ' + b"[" * 300000 + b"]" * 300000 + b"}"
        self.assertEqual(self.run_hook(deep), {})

    def test_a_byte_order_mark_on_stdin(self):
        data = "﻿".encode() + json.dumps(call(self.root)).encode()
        self.assertEqual(self.decision(self.run_hook(data)), "deny")


class ShortIdTest(Base):
    """Round one's finding 10: the notebook's id written short or without
    hyphens is the notebook's, run as the review ran it."""
    NAMED = {"artifact": "0123abcd-0000-4000-8000-00000000beef"}

    def test_the_review_s_reproduction_as_a_process(self):
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PROJECT_DIR"}
        for agent in ("principal:interviewer", "general-purpose"):
            for sent in ("0123abcd-0000-4000-8000-00000000beef", "0123abcd-0000", "0123abcd",
                         "0123abcd00004000800000000000beef", "0123ABCD-0000",
                         SITE + "Notebook-0123abcd-0000", SITE + "0123abcd"):
                with self.subTest(agent=agent, sent=sent):
                    data = json.dumps(call(self.root, agent, UPDATE, container=sent)).encode()
                    done = subprocess.run([sys.executable, "-B", GATE], input=data,
                                          capture_output=True, env=env, timeout=60)
                    got = json.loads(done.stdout)
                    self.assertEqual(got["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_minor_8_the_id_in_another_spelling(self):
        """Percent-encoding, Unicode hyphens, zero-width characters and
        full-width forms are read as the id they spell."""
        nb = "0123abcd-0000-4000-8000-00000000beef"
        full = "".join(chr(ord(c) + 0xFEE0) if c.isalnum() else c for c in nb)
        for sent in (nb.replace("-", "%2D"), nb.replace("-", "%2d"),
                     nb.replace("-", "\u2010"), nb.replace("-", "\u2011"),
                     nb.replace("-", "\u2212"), nb.replace("-", "\uff0d"),
                     nb[:4] + "\u200b" + nb[4:], nb[:4] + "\ufeff" + nb[4:],
                     nb[:4] + "\u00ad" + nb[4:], nb[:4] + "\u2060" + nb[4:], full,
                     "%30123abcd-0000", SITE + "Note-" + nb.replace("-", "%252D"),
                     "0123abcd\u20100000"):
            with self.subTest(sent=sent):
                self.refused(call(self.root, container=sent))

    def test_a_beginning_too_short_or_another_id_is_not_the_notebook(self):
        for sent in ("0123abc", "0123abcd-0001", "abcd0123", "ffff0123abcd",
                     OTHER, SITE + "Notes-11112222"):
            self.silent(call(self.root, container=sent))


class Round1cTest(Base):
    """The third review of the gates, on the notebook gate."""

    def test_s3_a_helper_s_ref_to_a_part_of_another_document(self):
        for agent in ("general-purpose", "fork", "other:reviewer", "recorder "):
            with self.subTest(agent=agent):
                self.unclear(call(self.root, agent, container=OTHER))
                self.unclear(call(self.root, agent, BATCH, tool_input={
                    "container": {"kind": "project", "create": {"name": "n"}},
                    "batch": [{"verb": "update", "ref": {"object": "node", "id": "b1"}}]}))
        # a ref of object project to another document is plain
        self.silent(call(self.root, "fork", tool_input={
            "ref": {"object": "project", "id": OTHER}, "payload": {}}))
        # the interviewer's own line doc is written by its nodes; its residue is said
        self.silent(call(self.root, "principal:interviewer", container=OTHER))
        self.silent(call(self.root, "principal:interviewer", BATCH, tool_input={
            "container": {"kind": "project", "create": {"name": "n"}},
            "batch": [{"verb": "update", "ref": {"object": "node", "id": "b1"}}]}))
        with open(GATE, encoding="utf-8") as fh:
            said = " ".join(fh.read().split())
        self.assertTrue("unchecked against the live connector" in said)

    def test_minor_13_the_artifact_tools_and_export_on_the_notebook(self):
        tools = ["Artifact", "ArtifactData", "ArtifactComments"] + \
            [p + v for p in PREFIXES for v in ("export", "delete")]
        for tool in tools:
            for named in ({"url": SITE + "Notebook-" + NOTEBOOK},
                          {"action": "read", "url": SITE + NOTEBOOK, "collection": "x"},
                          {"container": {"kind": "project", "id": NOTEBOOK}}):
                for agent in ("principal:recorder", "recorder", "principal:interviewer",
                              "general-purpose", "principal:coordinator"):
                    with self.subTest(tool=tool, named=named, agent=agent):
                        self.refused(call(self.root, agent, tool, tool_input=named))
                self.silent(call(self.root, None, tool, tool_input=named))
        for tool in ("Artifact", "ArtifactData", "ArtifactComments", PREFIXES[1] + "export"):
            self.silent(call(self.root, "general-purpose", tool,
                             tool_input={"url": SITE + OTHER}))
        entry = None
        with open(HOOKS, encoding="utf-8") as fh:
            for e in json.load(fh)["hooks"]["PreToolUse"]:
                if "notebook-gate.py" in e["hooks"][0]["command"]:
                    entry = e
        for tool in tools:
            self.assertIn(tool, entry["matcher"].split("|"))


class Round2Test(Base):
    """The fourth review of the gates, on the notebook gate."""

    BOARD = SITE + OTHER

    def setUp(self):
        super().setUp()
        base = tempfile.mkdtemp(prefix="claude-", dir=os.path.realpath("/tmp"))
        self.addCleanup(__import__("shutil").rmtree, base, ignore_errors=True)
        self.scratch = os.path.join(base, "claude-1000", "p", "s", "scratchpad", "sit")
        os.makedirs(self.scratch + "/coordinator/board")
        os.makedirs(self.scratch + "/speaker/board")

    def data(self, agent, **fields):
        tool_input = {"url": self.BOARD}
        tool_input.update(fields)
        return call(self.root, agent, "ArtifactData", tool_input=tool_input)

    def test_s1_the_reported_inputs_are_refused(self):
        plugin = ROOT
        for fields in ({"action": "get", "collection": ".principal", "doc_id": "notebook",
                        "out_dir": self.root},
                       {"action": "get", "collection": "hooks", "doc_id": "hooks",
                        "out_dir": plugin},
                       {"action": "set", "collection": "jobs", "doc_id": "x",
                        "file_path": os.path.expanduser("~/.claude.json")}):
            for agent in ("principal:coordinator", "principal:interviewer"):
                with self.subTest(fields=fields, agent=agent):
                    self.assertEqual(self.decision(self.data(agent, **fields)), "deny")

    def test_s1_a_member_s_file_and_a_climbing_collection(self):
        mine = self.scratch + "/coordinator/board"
        self.assertEqual(self.decision(self.data(
            "principal:coordinator", action="batch",
            writes=[{"collection": "jobs", "doc_id": "a", "file_path": mine + "/w.json"},
                    {"collection": "jobs", "doc_id": "b", "file_path": "/etc/passwd"}])),
            "deny")
        self.assertEqual(self.decision(self.data(
            "principal:coordinator", action="get", collection="../../x", doc_id="y",
            out_dir=mine)), "deny")
        # the speaker's export, its collection under it, lands in the project's setup
        self.assertEqual(self.decision(self.data(
            "principal:interviewer", action="list", collection=".principal",
            out_dir=self.root)), "deny")

    def test_s1_each_kind_s_own_directory_is_admitted(self):
        mine = self.scratch + "/coordinator/board"
        self.silent(self.data("principal:coordinator", action="get", collection="meta",
                              doc_id="board", out_dir=mine))
        self.silent(self.data("principal:coordinator", action="batch",
                              writes=[{"collection": "jobs", "doc_id": "a",
                                       "file_path": mine + "/w.json"}]))
        self.silent(self.data("principal:interviewer", action="list", collection="jobs",
                              out_dir=self.scratch + "/speaker/board"))
        # the coordinator, out of its own directory
        self.assertEqual(self.decision(self.data(
            "principal:coordinator", action="get", collection="meta", doc_id="board",
            out_dir=self.scratch + "/speaker/board")), "deny")
        # a kind that holds no such tool is refused any local file
        self.assertEqual(self.decision(self.data(
            "principal:fetcher", action="get", collection="meta", doc_id="board",
            out_dir=mine)), "deny")
        # with no local file, nothing changes
        self.silent(self.data("principal:coordinator", action="get", collection="meta",
                              doc_id="board"))
        # the main thread keeps what it had
        self.silent(self.data(None, action="get", collection=".principal", doc_id="n",
                              out_dir=self.root))

    def test_note_2_a_delete_by_a_ref_to_a_part(self):
        for agent in ("principal:recorder", "recorder", "general-purpose"):
            for container in (None, OTHER):
                tool_input = {"ref": {"object": "node", "id": "n1"}}
                if container:
                    tool_input["container"] = {"kind": "project", "id": container}
                for tool in (p + "delete" for p in PREFIXES):
                    with self.subTest(agent=agent, container=container, tool=tool):
                        self.unclear(call(self.root, agent, tool, tool_input=tool_input))


class Round3Test(Base):
    """The fifth review of the gates, on the notebook gate."""

    BOARD = SITE + OTHER

    def setUp(self):
        super().setUp()
        base = tempfile.mkdtemp(prefix="claude-", dir=os.path.realpath("/tmp"))
        self.addCleanup(__import__("shutil").rmtree, base, ignore_errors=True)
        self.scratch = os.path.join(base, "claude-1000", "p", "s", "scratchpad", "sit")
        os.makedirs(self.scratch + "/coordinator/board")
        os.makedirs(self.scratch + "/speaker/board")

    def data(self, agent, **fields):
        tool_input = {"url": self.BOARD}
        tool_input.update(fields)
        return call(self.root, agent, "ArtifactData", tool_input=tool_input)

    def test_s1_only_writes_is_read_as_a_list(self):
        for agent in ("principal:interviewer", "principal:coordinator"):
            for old, new in (("[ ] todo", "y"), ("x", "[draft] words"),
                             ("a", json.dumps([{"file_path": "/etc/passwd"}]))):
                with self.subTest(agent=agent, old=old, new=new):
                    self.silent(self.data(agent, action="str_replace", collection="ordo",
                                          doc_id="current", field="a", old_str=old,
                                          new_str=new))

    def test_note_1_writes_that_is_no_list_of_objects_is_unclear(self):
        mine = self.scratch + "/coordinator/board"
        bad = {"collection": "jobs", "doc_id": "a", "file_path": "/etc/passwd"}
        for writes in (bad, json.dumps(bad), [json.dumps(bad)], [[bad]], "\ufeff[]",
                       "not json", 3):
            with self.subTest(writes=writes):
                self.unclear(self.data("principal:coordinator", action="batch",
                                       writes=writes))
        # writes as the JSON text of a list of objects is read as that list
        self.silent(self.data("principal:coordinator", action="batch", writes=json.dumps(
            [{"collection": "jobs", "doc_id": "a", "file_path": mine + "/w.json"}])))
        self.assertEqual(self.decision(self.data(
            "principal:coordinator", action="batch", writes=json.dumps([bad]))), "deny")

    def test_note_3_the_coordinator_s_directory_under_the_speaker_s_is_not_its_own(self):
        os.makedirs(self.scratch + "/speaker/coordinator/board")
        self.assertEqual(self.decision(self.data(
            "principal:coordinator", action="get", collection="meta", doc_id="board",
            out_dir=self.scratch + "/speaker/coordinator/board")), "deny")
        self.silent(self.data("principal:interviewer", action="list", collection="jobs",
                              out_dir=self.scratch + "/speaker/board"))

    def test_note_4_a_delete_whose_ref_is_no_object(self):
        for agent in ("principal:recorder", "recorder", "principal:interviewer"):
            for ref in ("node:n1", [{"object": "node", "id": "n1"}]):
                for tool in (p + "delete" for p in PREFIXES):
                    with self.subTest(agent=agent, ref=ref, tool=tool):
                        self.unclear(call(self.root, agent, tool, tool_input={"ref": ref}))


def inserting(node, ops=None, container=NOTEBOOK, obj="node"):
    """An update of one node of a document by the given ops, inserts by
    default."""
    return {"container": {"kind": "project", "id": container},
            "ref": {"object": obj, "id": node},
            "payload": {"ifRev": 7, "ops": ops if ops is not None else [
                {"op": "insert", "target": {"kind": "blocks", "ids": ["b9"]},
                 "side": "after", "source": {"as": "markdown",
                                             "from": {"kind": "inline",
                                                      "content": "> a line"}}}]}}


def an_insert(**changes):
    """One insert as the tools print it, with ``changes`` made to it; a
    value of None removes the key."""
    op = {"op": "insert", "target": {"kind": "blocks", "ids": ["b9"]}, "side": "after",
          "source": {"as": "markdown", "from": {"kind": "inline", "content": "> a line"}}}
    for key, value in changes.items():
        if value is None:
            op.pop(key, None)
        else:
            op[key] = value
    return op


class SidedTest(Base):
    """The comparer writes the user's side and the AI's recorder the AI's
    own record, each only by inserting; the AI's recorder writes nothing
    until the notebook file names the AI's root."""

    AI = ["n-root", "n-tab"]
    NAMED = {"artifact": SITE + NOTEBOOK, "project": "x", "ai_root": AI}

    def update(self, agent, node, **kw):
        return call(self.root, agent, UPDATE, inserting(node, **kw))

    def deny(self, c, reason):
        self.assertEqual(self.reason(c), reason, c)

    def test_the_ai_recorder_inserts_on_the_ai_s_tabs_only(self):
        for agent in ("principal:ai-recorder", "ai-recorder"):
            if agent == "ai-recorder":
                define(self.root, kind="ai-recorder")
            for node in self.AI:
                self.silent(self.update(agent, node))
            self.deny(self.update(agent, "b1"), self.gate.AI_SIDE)

    def test_the_ai_recorder_never_edits_an_answer_already_there(self):
        agent = "principal:ai-recorder"
        for op in ("replace", "delete", "format"):
            self.deny(self.update(agent, "n-tab", ops=[{"op": op}]), self.gate.AI_SIDE)
        self.deny(self.update(agent, "n-tab", ops=[
            {"op": "insert"}, {"op": "replace"}]), self.gate.AI_SIDE)

    def test_the_ai_recorder_writes_nothing_while_the_root_is_unnamed(self):
        for named in ({"artifact": SITE + NOTEBOOK}, {"artifact": SITE + NOTEBOOK, "ai_root": ""},
                      {"artifact": SITE + NOTEBOOK, "ai_root": []}):
            with project(named) as root:
                c = call(root, "principal:ai-recorder", UPDATE, inserting("n-tab"))
                self.assertEqual(self.reason(c), self.gate.UNSET)

    def test_the_comparer_writes_off_the_ai_s_tabs(self):
        agent = "principal:comparer"
        self.silent(self.update(agent, "b1"))
        for node in self.AI:
            self.deny(self.update(agent, node), self.gate.USER_SIDE)
        self.deny(self.update(agent, "b1", ops=[{"op": "replace"}]), self.gate.USER_SIDE)
        with project({"artifact": SITE + NOTEBOOK}) as root:
            # no AI root yet: every tab is the user's
            self.silent(call(root, agent, UPDATE, inserting("n-tab")))

    def test_each_writes_the_notebook_alone_and_by_one_node(self):
        for agent, reason in (("principal:ai-recorder", self.gate.AI_SIDE),
                              ("principal:comparer", self.gate.USER_SIDE)):
            with self.subTest(agent=agent):
                self.deny(self.update(agent, "n-tab", container=OTHER), reason)
                self.deny(self.update(agent, "n-tab", obj="file"), reason)
                self.deny(self.update(agent, NOTEBOOK, obj="project"), reason)
                for tool in WRITES:
                    if not tool.endswith("update"):
                        # a delete naming the notebook is refused before
                        # the side is read, as it is to every helper
                        self.assertEqual(self.decision(call(self.root, agent, tool,
                                                            inserting("n-tab"))), "deny")

    def test_what_cannot_be_read_is_refused(self):
        for agent, node in (("principal:ai-recorder", "n-tab"), ("principal:comparer", "b1")):
            self.unclear(call(self.root, agent, UPDATE, dict(inserting(node), payload="{")))
            self.unclear(call(self.root, agent, UPDATE, dict(inserting(node), payload={})))
            for value in (7, [1], ["n-tab", ""], {"root": "n"}):
                with project({"artifact": SITE + NOTEBOOK, "ai_root": value}) as root:
                    self.unclear(call(root, agent, UPDATE, inserting("n-tab")))
            with project(None) as root:
                self.unclear(call(root, agent, UPDATE, inserting("n-tab")))

    def test_a_bare_name_not_defined_as_the_plugin_s_writes_nothing(self):
        for kind in ("comparer", "ai-recorder"):
            define(self.root, b"---\nname: %s\n---\nmine\n" % kind.encode(), kind=kind)
            self.refused(self.update(kind, "n-tab"))
            self.refused(self.update(kind, "b1"))

    def test_neither_exports_or_names_the_notebook_by_the_other_tools(self):
        for agent in ("principal:ai-recorder", "principal:comparer"):
            self.refused(call(self.root, agent, PREFIXES[0] + "export",
                              {"container": {"kind": "project", "id": NOTEBOOK}}))
            self.refused(call(self.root, agent, "Artifact", {"url": SITE + NOTEBOOK}))

    def test_only_an_insert_beside_a_block_or_at_the_end(self):
        # S7: no find target, no words put inside a paragraph, no each, no
        # other shape of source, no keys beside the ops
        markdown = {"as": "markdown", "from": {"kind": "inline", "content": "> a"}}
        bad = [an_insert(target={"kind": "find", "text": "is kept"}, side="before",
                         source={"as": "text", "from": {"kind": "inline", "content": "never "}}),
               an_insert(target={"kind": "find", "text": "is kept"}),
               an_insert(source={"as": "text", "from": {"kind": "inline", "content": "x"}}),
               an_insert(source="> a line"),
               an_insert(each={"kind": "rows"}),
               an_insert(target={"kind": "blocks", "ids": ["t1"]}, side="end"),
               an_insert(target={"kind": "blocks", "ids": ["b1", "b2"]}),
               an_insert(target={"kind": "blocks", "ids": []}),
               an_insert(target={"kind": "blocks", "ids": ["b1"], "nth": 2}),
               an_insert(target={"kind": "root"}, side="after"),
               an_insert(side=None), an_insert(target=None)]
        good = [an_insert(), an_insert(side="before"),
                an_insert(target={"kind": "root"}, side="end", source=markdown)]
        for agent, node, reason in (("principal:ai-recorder", "n-tab", self.gate.AI_SIDE),
                                    ("principal:comparer", "b1", self.gate.USER_SIDE)):
            for op in bad:
                with self.subTest(agent=agent, op=op):
                    self.deny(self.update(agent, node, ops=[op]), reason)
                    self.deny(self.update(agent, node, ops=[an_insert(), op]), reason)
            for op in good:
                with self.subTest(agent=agent, op=op):
                    self.silent(self.update(agent, node, ops=[op]))
            # a patch beside the inserts, a comment thread answered, another engine
            c = self.update(agent, node)
            c["tool_input"]["payload"]["kind"] = "patch"
            self.deny(c, reason)
            c = self.update(agent, node)
            c["tool_input"]["payload"]["patch"] = []
            self.deny(c, reason)
            c = self.update(agent, node)
            c["tool_input"]["answering"] = "u1"
            self.deny(c, reason)
            c = self.update(agent, node)
            c["tool_input"]["engine"] = "table"
            self.deny(c, reason)
            c = self.update(agent, node)
            c["tool_input"].update(engine="prose", opId="r-1", verbose=True)
            self.silent(c)

    def test_the_comparer_s_side_test_reads_the_id_as_the_connector_might(self):
        # S8: a spelling of an AI tab's id is the AI's tab, or no id at all
        agent = "principal:comparer"
        for node in ("N-TAB", "n-Tab", "n\u200b-tab", "n%2Dtab", "node/n-tab", "n\u2011tab",
                     " n-tab", "n-tab "):
            with self.subTest(node=node):
                self.deny(self.update(agent, node), self.gate.USER_SIDE)
        with project({"artifact": SITE + NOTEBOOK, "ai_root": ["N-Root", "N-TAB"]}) as root:
            self.assertEqual(self.reason(call(root, agent, UPDATE, inserting("n-tab"))),
                             self.gate.USER_SIDE)
            self.silent(call(root, "principal:ai-recorder", UPDATE, inserting("n-tab")))

    def test_the_ai_recorder_s_side_test_reads_the_id_the_same_way(self):
        agent = "principal:ai-recorder"
        self.silent(self.update(agent, "N-TAB"))
        for node in ("n\u200b-tab", "n%2Dtab", "node/n-tab"):
            with self.subTest(node=node):
                self.deny(self.update(agent, node), self.gate.AI_SIDE)

    def test_no_sided_grant_without_the_plugin_s_name(self):
        # N9: where the manifest's name cannot be read, `<any>:comparer`
        # is no comparer
        for agent in ("other:comparer", "x:ai-recorder", ":comparer"):
            with self.subTest(agent=agent):
                c = call(self.root, agent, UPDATE, inserting("b1"))
                self.assertEqual(self.decision(c), "deny")
                self.assertEqual(self.decision(c, plugin=""), "deny")
        # nor the plugin's own name where its manifest cannot be read
        self.assertEqual(self.decision(call(self.root, "principal:comparer", UPDATE,
                                            inserting("b1")), plugin=""), "deny")

    def test_input_that_does_not_parse_is_refused_to_them(self):
        for agent in ("principal:ai-recorder", "principal:comparer"):
            raw = b'{"agent_type": "%s", oops' % agent.encode()
            self.assertEqual(self.gate.unparsed(raw, "principal")["hookSpecificOutput"]
                             ["permissionDecision"], "deny")


class TabTest(Base):
    """The AI's recorder makes a tab under a tab of the AI's the key gives
    with its tab id, by the one batch `tools/ai_tab.py` prints, and nothing
    else; the speaker makes the AI's root once, at the top level, while the
    key is unset."""

    AI = [{"node": "n-root", "tab": "t-root"}, {"node": "n-tab", "tab": "t-tab"}, "n-old"]
    NAMED = {"artifact": SITE + NOTEBOOK, "project": "x", "ai_root": AI}
    UNSET = {"artifact": SITE + NOTEBOOK, "project": "x"}

    def setUp(self):
        super().setUp()
        sys.path.insert(0, HERE)
        from hypo import ai_tab
        self.tool = ai_tab

    def made(self, parent="n-tab", named=None, name="q-one"):
        """The batch the tool prints for a tab under ``parent``."""
        entry = self.tool.tab(named or self.NAMED, parent, name, "a0")
        self.assertEqual(entry["node"], parent)
        return dict(entry["batch"], opId=entry["op_id"])

    def named_tab(self, name, order="a0", under="t-tab"):
        """The batch made under ``under`` and named ``name`` by hand, its
        operation id the one the gate derives, so only the name is at
        fault."""
        c = self.made()
        where = c["batch"][3]["payload"]["patch"][0]["value"]
        where.update(name=name, order=order)
        c["batch"][0]["payload"]["value"]["birthName"] = "%s.ldoc" % name
        c["batch"][2]["payload"]["value"]["birthName"] = "%s.ldoc" % name
        c["batch"][1]["payload"]["source"]["from"]["content"] = "# %s" % name
        c["opId"] = self.gate.tab_op_id("tab", under, name)
        return c

    def deny(self, c, reason):
        self.assertEqual(self.reason(c), reason, c)

    def test_the_ai_recorder_makes_a_tab_under_a_tab_of_its_own(self):
        for agent in ("principal:ai-recorder", "ai-recorder"):
            if agent == "ai-recorder":
                define(self.root, kind="ai-recorder")
            for parent in ("n-root", "n-tab"):
                for tool in (p + "batch" for p in PREFIXES):
                    with self.subTest(agent=agent, parent=parent, tool=tool):
                        self.silent(call(self.root, agent, tool, self.made(parent)))
        self.silent(call(self.root, "principal:ai-recorder", BATCH,
                         self.named_tab("q-two", order="b07")))

    def test_s4_never_as_text_and_never_a_key_twice(self):
        agent = "principal:ai-recorder"
        c = self.made()
        text = dict(c, batch=json.dumps(c["batch"]))
        self.deny(call(self.root, agent, BATCH, text), self.gate.NEW_TAB)
        # the fourth member's payload twice, a delete of a user's tab hidden first
        members = json.dumps(c["batch"][:3])[:-1]
        fourth = json.dumps(c["batch"][3])
        hidden = fourth.replace('"payload": ', '"payload": {"kind": "patch", "patch": [{"op": '
                                '"delete", "path": ["tabs", "t-user"]}]}, "payload": ', 1)
        self.deny(call(self.root, agent, BATCH, dict(c, batch=members + ", " + hidden + "]")),
                  self.gate.NEW_TAB)
        self.deny(call(self.root, agent, BATCH, dict(c, container=json.dumps(c["container"]))),
                  self.gate.NEW_TAB)

    def test_nowhere_but_under_a_tab_the_key_gives_with_its_tab_id(self):
        agent = "principal:ai-recorder"
        for under in ("t-other", "T-TAB​", "t%2Dtab", "tab/t-tab", "n-tab", "n-old", "",
                      "t-tab\n"):
            c = self.made()
            c["batch"][3]["payload"]["patch"][0]["value"]["subtabOf"] = under
            with self.subTest(under=under):
                self.deny(call(self.root, agent, BATCH, c), self.gate.NEW_TAB)
        c = self.made()
        del c["batch"][3]["payload"]["patch"][0]["value"]["subtabOf"]
        self.deny(call(self.root, agent, BATCH, c), self.gate.NEW_TAB)
        # R1: the parent's tab id in another case is the same tab, with one operation id
        c = self.made()
        c["batch"][3]["payload"]["patch"][0]["value"]["subtabOf"] = "T-TAB"
        self.assertEqual(c["opId"], self.gate.tab_op_id("tab", "t-tab", "q-one"))
        self.silent(call(self.root, agent, BATCH, c))
        upper = dict(self.NAMED, ai_root=[{"node": "n-root", "tab": "T-ROOT"}])
        self.assertEqual(self.tool.tab(upper, "n-root", "q-one", "a0")["op_id"],
                         self.tool.tab(dict(self.NAMED), "n-root", "q-one", "a0")["op_id"])
        # the operation id is the one the tool derives, or none is admitted
        for op in (None, "other", self.gate.tab_op_id("tab", "t-root", "q-one"),
                   self.gate.tab_op_id("root", NOTEBOOK)):
            c = self.made()
            if op is None:
                del c["opId"]
            else:
                c["opId"] = op
            with self.subTest(op=op):
                self.deny(call(self.root, agent, BATCH, c), self.gate.NEW_TAB)
        # an entry that is a bare node id gives no tab to make one under
        with self.assertRaises(self.tool.Refused):
            self.tool.tab(self.NAMED, "n-old", "q-one", "a0")

    def test_s2_the_name_the_order_the_file_and_the_body_at_the_gate(self):
        agent = "principal:ai-recorder"
        for name in ("lease", "Q-one", "q one", "a/b", "q--one", "-q", "the user's rule", "",
                     "lease\n", "q-one\n"):
            with self.subTest(name=name):
                self.deny(call(self.root, agent, BATCH, self.named_tab(name)), self.gate.NEW_TAB)
        for order in ("!!", "", "A0", "0a", "a-0", "a0\n"):
            with self.subTest(order=order):
                self.deny(call(self.root, agent, BATCH, self.named_tab("q-one", order=order)),
                          self.gate.NEW_TAB)
        for birth in ("../x", "q-one", "q-two.ldoc", "Q-one.ldoc"):
            c = self.named_tab("q-one")
            c["batch"][0]["payload"]["value"]["birthName"] = birth
            c["batch"][2]["payload"]["value"]["birthName"] = birth
            with self.subTest(birth=birth):
                self.deny(call(self.root, agent, BATCH, c), self.gate.NEW_TAB)
        for body in ("# q-one\n\nany prose", "# Anything", "", "#  q-one", "# q-one\n", 7):
            c = self.named_tab("q-one")
            c["batch"][1]["payload"]["source"]["from"]["content"] = body
            with self.subTest(body=body):
                self.deny(call(self.root, agent, BATCH, c), self.gate.NEW_TAB)

    def test_s3_the_container_is_the_notebook_s_bare_id(self):
        agent = "principal:ai-recorder"
        for where in (SITE + OTHER + "?x=" + NOTEBOOK, OTHER + "#" + NOTEBOOK,
                      NOTEBOOK + "/../" + OTHER, NOTEBOOK[:8], SITE + NOTEBOOK,
                      NOTEBOOK.replace("-", ""), " " + NOTEBOOK, NOTEBOOK + "?a=1"):
            c = self.made()
            c["container"] = {"kind": "project", "id": where}
            c["batch"][3]["ref"]["id"] = where
            with self.subTest(where=where):
                self.assertEqual(self.decision(call(self.root, agent, BATCH, c)), "deny")
        c = self.made()
        c["container"] = {"kind": "project", "id": NOTEBOOK.upper()}
        c["batch"][3]["ref"]["id"] = NOTEBOOK.upper()
        self.silent(call(self.root, agent, BATCH, c))

    def test_nothing_while_the_key_is_unset(self):
        c = self.made()
        for named in (self.UNSET, {"artifact": SITE + NOTEBOOK, "ai_root": []}):
            with project(named) as root:
                self.assertEqual(self.reason(call(root, "principal:ai-recorder", BATCH, c)),
                                 self.gate.UNSET)

    def test_one_shape_alone(self):
        agent = "principal:ai-recorder"
        bad = []

        def change(fn):
            c = self.made()
            fn(c)
            bad.append(c)
        change(lambda c: c.update(answering="u1"))
        change(lambda c: c.update(container={"kind": "project", "id": OTHER}))
        change(lambda c: c["container"].update(create={}))
        change(lambda c: c["batch"].append(c["batch"][3]))
        change(lambda c: c["batch"].pop())
        change(lambda c: c["batch"].reverse())
        change(lambda c: c["batch"].__setitem__(3, {
            "verb": "update", "ref": {"object": "node", "id": "b1"}, "engine": "prose",
            "payload": {"ops": [{"op": "replace"}]}}))
        change(lambda c: c["batch"].__setitem__(0, dict(c["batch"][0], verb="delete")))
        change(lambda c: c["batch"][0].update(container={"kind": "project", "id": NOTEBOOK}))
        change(lambda c: c["batch"][1].update(engine="table"))
        change(lambda c: c["batch"][1]["payload"].update(parent={"object": "file", "id": "t-x"}))
        change(lambda c: c["batch"][1]["payload"]["source"].update(blocks={"b": {}}))
        change(lambda c: c["batch"][1]["payload"]["source"].update(**{"as": "text"}))
        change(lambda c: c["batch"][2]["payload"]["value"].update(birthName="other.ldoc"))
        change(lambda c: c["batch"][2]["payload"]["value"]["content"].update(id="b1"))
        change(lambda c: c["batch"][3]["ref"].update(id=OTHER))
        change(lambda c: c["batch"][3]["payload"]["patch"].append(
            {"op": "set", "path": ["tabs", "t-root", "subtabOf"], "value": "t-tab"}))
        change(lambda c: c["batch"][3]["payload"]["patch"][0].update(
            path=["tabs", "t-root"]))
        change(lambda c: c["batch"][3]["payload"]["patch"][0]["value"].update(extra=1))
        change(lambda c: c["batch"][3]["payload"]["patch"][0]["value"].update(name=""))
        change(lambda c: c.update(batch="["))
        change(lambda c: c.update(opId=7))
        # R1: an alias with a trailing newline
        change(lambda c: c["batch"][0].update(**{"$lid": "f\n"}))
        change(lambda c: c["batch"][1].update(**{"$lid": "n\n"}))
        for c in bad:
            with self.subTest(c=c):
                self.assertEqual(self.decision(call(self.root, agent, BATCH, c)), "deny")
        for tool in (p + v for p in PREFIXES for v in ("create", "delete")):
            self.assertEqual(self.decision(call(self.root, agent, tool, self.made())), "deny")

    def test_no_other_kind_makes_a_tab_by_it(self):
        c = self.made()
        self.deny(call(self.root, "principal:comparer", BATCH, c), self.gate.USER_SIDE)
        for agent in SILENT:
            self.refused(call(self.root, "principal:" + agent, BATCH, c))
        for agent in FOREIGN + ("other:ai-recorder", "x:interviewer"):
            with self.subTest(agent=agent):
                self.assertEqual(self.decision(call(self.root, agent, BATCH, c)), "deny")
        # a bare ai-recorder the project does not define as the plugin's
        define(self.root, b"---\nname: ai-recorder\n---\nmine\n", kind="ai-recorder")
        self.refused(call(self.root, "ai-recorder", BATCH, c))
        # the interviewer, once the key is set
        self.deny(call(self.root, "principal:interviewer", BATCH, c), self.gate.ROOT_MADE)

    def a_root(self, name="ai-root", order="z0"):
        return self.tool.root(self.UNSET, name, order)

    def test_s1_the_speaker_makes_the_root_at_the_top_level_with_its_heading_alone(self):
        made = self.a_root()
        with project(self.UNSET) as root:
            define(root, kind="interviewer")
            for agent in ("principal:interviewer", "interviewer"):
                with self.subTest(agent=agent):
                    self.silent(call(root, agent, BATCH, made))
            speaker = "principal:interviewer"
            # nested under any tab, the user's among them: refused
            nested = json.loads(json.dumps(made))
            nested["batch"][3]["payload"]["patch"][0]["value"]["subtabOf"] = "t-user"
            self.deny(call(root, speaker, BATCH, nested), self.gate.ROOT_SHAPE)
            # a body that says anything but its heading, a name no question
            # has, a file named otherwise: no tab's batch, so refused as the
            # notebook is
            for part, value in ((1, "# ai-root\n\nany prose"), (1, "# Anything")):
                c = json.loads(json.dumps(made))
                c["batch"][part]["payload"]["source"]["from"]["content"] = value
                self.refused(call(root, speaker, BATCH, c))
            for name in ("lease", "The user's rule", "a/b", "lease\n", "ai-root\n"):
                c = json.loads(json.dumps(made).replace("ai-root", json.dumps(name)[1:-1]))
                self.refused(call(root, speaker, BATCH, c))
            c = json.loads(json.dumps(made))
            c["batch"][3]["payload"]["patch"][0]["value"]["order"] = "z0\n"
            self.refused(call(root, speaker, BATCH, c))
            c = json.loads(json.dumps(made))
            c["batch"][0]["$lid"] = "f\n"
            self.refused(call(root, speaker, BATCH, c))
            c = json.loads(json.dumps(made))
            c["batch"][0]["payload"]["value"]["birthName"] = "../x"
            c["batch"][2]["payload"]["value"]["birthName"] = "../x"
            self.refused(call(root, speaker, BATCH, c))
            # every other write of the notebook is still refused
            self.refused(call(root, speaker, UPDATE))
            self.refused(call(root, speaker, BATCH, dict(made, batch=made["batch"][:3])))
            # its own document, in the same shape, is still its own
            mine = json.loads(json.dumps(made).replace(NOTEBOOK, OTHER))
            self.silent(call(root, speaker, BATCH, mine))
            half = dict(made, container={"kind": "project", "id": OTHER})
            self.refused(call(root, speaker, BATCH, half))
            # a bare interviewer the project does not define as the plugin's
            define(root, b"---\nname: interviewer\n---\nmine\n", kind="interviewer")
            self.refused(call(root, "interviewer", BATCH, made))
            # the AI's recorder makes no root
            self.assertEqual(self.reason(call(root, "principal:ai-recorder", BATCH, made)),
                             self.gate.UNSET)
        self.deny(call(self.root, "principal:interviewer", BATCH, made), self.gate.ROOT_MADE)
        with self.assertRaises(self.tool.Refused):
            self.tool.root(self.NAMED, "ai-root", "z0")
        with project({"artifact": SITE + NOTEBOOK, "ai_root": [{"node": 7}]}) as root:
            self.unclear(call(root, "principal:interviewer", BATCH, made))

    def test_a_second_root_while_the_key_is_unset(self):
        """The gate keeps no count: what makes the root once is the one
        operation id every root of the notebook is sent with, which the
        connector lands once. Another id is refused."""
        first, second = self.a_root(), self.a_root("other-root", "a0")
        self.assertEqual(first["opId"], second["opId"])
        self.assertEqual(first["opId"], self.gate.tab_op_id("root", NOTEBOOK))
        with project(self.UNSET) as root:
            speaker = "principal:interviewer"
            self.silent(call(root, speaker, BATCH, first))
            self.silent(call(root, speaker, BATCH, second))
            for op in ("ai-tab-0000000000000000", None, self.gate.tab_op_id("root", OTHER),
                       self.gate.tab_op_id("tab", NOTEBOOK, "other-root")):
                c = dict(second)
                if op is None:
                    del c["opId"]
                else:
                    c["opId"] = op
                with self.subTest(op=op):
                    self.deny(call(root, speaker, BATCH, c), self.gate.ROOT_SHAPE)

    def test_the_key_s_entries_hold_both_sides(self):
        self.silent(call(self.root, "principal:ai-recorder", UPDATE, inserting("n-root")))
        self.silent(call(self.root, "principal:ai-recorder", UPDATE, inserting("n-old")))
        for node in ("n-root", "n-old"):
            self.deny(call(self.root, "principal:comparer", UPDATE, inserting(node)),
                      self.gate.USER_SIDE)
        # R1: a node id with a trailing newline is no id of either side
        for agent in ("principal:ai-recorder", "principal:comparer"):
            self.assertEqual(self.decision(call(self.root, agent, UPDATE,
                                                inserting("n-root\n"))), "deny")
        # a tab id is no node to insert on
        self.deny(call(self.root, "principal:ai-recorder", UPDATE, inserting("t-root")),
                  self.gate.AI_SIDE)
        for value in ([{"node": "n"}], [{"node": "n", "tab": ""}], [{"node": "n", "tab": 7}],
                      [{"node": "n", "tab": "t", "x": 1}]):
            with project({"artifact": SITE + NOTEBOOK, "ai_root": value}) as root:
                for agent in ("principal:ai-recorder", "principal:comparer"):
                    with self.subTest(value=value, agent=agent):
                        self.unclear(call(root, agent, UPDATE, inserting("n")))
                self.unclear(call(root, "principal:ai-recorder", BATCH, self.made()))


class HooksFileTest(unittest.TestCase):
    """The plugin installs the gate beside the canon agent's, which stands as
    it was."""

    def setUp(self):
        with open(HOOKS, encoding="utf-8") as fh:
            self.entries = json.load(fh)["hooks"]["PreToolUse"]

    def test_the_canon_gate_is_gone(self):
        # the ask entry point and its canon agent were removed; a clean turn
        # is a process of its own (tools/clean_turn.py), and no gate is its
        self.assertFalse(any("canon-gate" in json.dumps(e) for e in self.entries))
        self.assertFalse(os.path.exists(os.path.join(ROOT, "hooks", "canon-gate.py")))

    def test_the_notebook_gate_fires_on_the_writing_tools_and_no_others(self):
        self.assertEqual(len(self.entries), 6)
        entry = self.entries[1]
        self.assertEqual(entry["hooks"], [{
            "type": "command",
            "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/notebook-gate.py\""}])
        naming = [p + "export" for p in PREFIXES] + ["Artifact", "ArtifactData",
                                                     "ArtifactComments"]
        self.assertEqual(sorted(entry["matcher"].split("|")), sorted(WRITES + naming))
        matcher = re.compile("^(?:%s)$" % entry["matcher"])
        for verb in ("read", "guide", "query"):
            for prefix in PREFIXES:
                self.assertIsNone(matcher.search(prefix + verb), verb)
        self.assertIsNone(matcher.search("Read"))

    def test_the_gate_guards_what_the_hook_fires_on(self):
        self.assertEqual(sorted(load_gate().GUARDED), sorted(WRITES))

    def test_the_gate_knows_every_kind_the_plugin_defines(self):
        agents = os.path.join(ROOT, "agents")
        defined = {n[:-3] for n in os.listdir(agents) if n.endswith(".md")}
        self.assertEqual(set(load_gate().KINDS), defined)


if __name__ == "__main__":
    unittest.main()
