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
SILENT = ("canon-answer", "checker", "clean-reader", "coordinator", "fetcher",
          "grader", "reviewer")
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


class HooksFileTest(unittest.TestCase):
    """The plugin installs the gate beside the canon agent's, which stands as
    it was."""

    def setUp(self):
        with open(HOOKS, encoding="utf-8") as fh:
            self.entries = json.load(fh)["hooks"]["PreToolUse"]

    def test_the_canon_gate_stands_as_it_was(self):
        self.assertEqual(self.entries[0], {
            "matcher": "Read",
            "hooks": [{"type": "command",
                       "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/canon-gate.py\""}]})

    def test_the_notebook_gate_fires_on_the_writing_tools_and_no_others(self):
        self.assertEqual(len(self.entries), 5)
        entry = self.entries[2]
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
