"""The rule every gate of the plugin shares for which turn is one of its
kinds: spelled once, in `hooks/kinds.py`, and read the same by each gate.
Run as processes, as the harness runs them."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
HOOKS = os.path.join(ROOT, "hooks")

#: each gate, the tool it fires on, an input that tool takes, and the kinds
#: it decides for
GATES = {
    "kind-bash-gate.py": ("Bash", {"command": "curl https://example.invalid"},
                          ("checker", "coordinator", "fetcher", "reviewer")),
    "kind-write-gate.py": ("Write", {"file_path": "/etc/x"},
                           ("checker", "coordinator", "fetcher", "reviewer")),
    "reader-gate.py": ("Read", {"file_path": "/etc/passwd"}, ("clean-reader",)),
    "notebook-gate.py": ("mcp__claude_ai_Claude_Docs__update",
                         {"container": {"kind": "project", "id": "x" * 32},
                          "ref": {"object": "node", "id": "b"}, "payload": {}},
                         ("checker", "coordinator", "fetcher", "reviewer")),
}


class SharedRuleTest(unittest.TestCase):
    def setUp(self):
        self.project = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.project, ignore_errors=True)
        self.env = {k: v for k, v in os.environ.items()
                    if k not in ("CLAUDE_PROJECT_DIR", "CLAUDE_PLUGIN_ROOT")}

    def run_gate(self, gate, agent):
        tool, given, _ = GATES[gate]
        call = {"cwd": self.project, "tool_name": tool, "tool_input": given,
                "agent_type": agent}
        done = subprocess.run([sys.executable, "-B", os.path.join(HOOKS, gate)],
                              input=json.dumps(call).encode(), capture_output=True,
                              env=self.env, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout)

    def test_every_gate_loads_the_one_rule(self):
        for gate in GATES:
            with open(os.path.join(HOOKS, gate), encoding="utf-8") as fh:
                text = fh.read()
            self.assertIn('"kinds.py"', text, gate)
            self.assertNotIn("def defined_here", text, gate)
            self.assertNotIn("def places", text, gate)

    def test_a_project_s_own_kind_of_the_same_name_gets_no_opinion(self):
        """Minor 6: a bare `reviewer` or `coordinator` of a project that does
        not define it as the plugin does is that project's own agent."""
        for gate, (_, _, kinds) in GATES.items():
            for kind in kinds:
                with self.subTest(gate=gate, kind=kind):
                    self.assertEqual(self.run_gate(gate, kind), {})
                    got = self.run_gate(gate, "principal:" + kind)
                    self.assertEqual(got["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_where_the_project_defines_it_as_ours_the_bare_name_is_the_kind(self):
        os.makedirs(os.path.join(self.project, ".claude", "agents"))
        for gate, (_, _, kinds) in GATES.items():
            for kind in kinds:
                shutil.copy(os.path.join(ROOT, "agents", kind + ".md"),
                            os.path.join(self.project, ".claude", "agents", kind + ".md"))
                with self.subTest(gate=gate, kind=kind):
                    got = self.run_gate(gate, kind)
                    self.assertEqual(got["hookSpecificOutput"]["permissionDecision"], "deny")


def plugin_copy(dest):
    """A copy of the plugin's gates, definitions and manifest under ``dest``."""
    for part in ("hooks", "agents", ".claude-plugin"):
        shutil.copytree(os.path.join(ROOT, part), os.path.join(dest, part),
                        ignore=shutil.ignore_patterns("__pycache__"))
    return os.path.join(dest, "hooks")


class KindsFileTest(unittest.TestCase):
    """Round 1c's S1: a `kinds.py` that does not load blocks the call, in
    every gate, with one sentence; it never fails open."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.hooks = plugin_copy(os.path.join(self.tmp, "plugin"))
        self.project = os.path.join(self.tmp, "project")
        os.makedirs(self.project)
        self.env = {k: v for k, v in os.environ.items()
                    if k not in ("CLAUDE_PROJECT_DIR", "CLAUDE_PLUGIN_ROOT")}

    def run_all(self):
        for gate, (tool, given, _) in GATES.items():
            for agent in ("principal:checker", "principal:clean-reader", "fork", None):
                call = {"cwd": self.project, "tool_name": tool, "tool_input": given}
                if agent:
                    call["agent_type"] = agent
                done = subprocess.run([sys.executable, "-B", os.path.join(self.hooks, gate)],
                                      input=json.dumps(call).encode(), capture_output=True,
                                      env=self.env, timeout=60)
                yield gate, agent, done

    def blocks(self):
        for gate, agent, done in self.run_all():
            with self.subTest(gate=gate, agent=agent):
                self.assertEqual(done.returncode, 2, done)
                self.assertEqual(done.stdout, b"")
                said = done.stderr.decode().strip()
                self.assertEqual(len(said.splitlines()), 1, said)
                self.assertIn("kinds.py", said)

    def test_intact_it_decides(self):
        for gate, agent, done in self.run_all():
            self.assertEqual(done.returncode, 0, (gate, done.stderr))

    def test_absent(self):
        os.remove(os.path.join(self.hooks, "kinds.py"))
        self.blocks()

    def test_empty(self):
        open(os.path.join(self.hooks, "kinds.py"), "w").close()
        self.blocks()

    def test_not_compiling(self):
        with open(os.path.join(self.hooks, "kinds.py"), "w") as fh:
            fh.write("def (")
        self.blocks()

    def test_exiting_as_it_loads(self):
        with open(os.path.join(self.hooks, "kinds.py"), "w") as fh:
            fh.write("import sys\nsys.exit(0)\n")
        self.blocks()


class DifferingCopyTest(SharedRuleTest):
    """Round 1c's S2: in a project that uses this plugin (it names a
    notebook), a bare name of a kind whose project copy differs from the
    plugin's, or is missing, is confined as the kind all the same; in a
    project that does not, it is that project's own agent."""

    def consumer(self):
        os.makedirs(os.path.join(self.project, ".principal"), exist_ok=True)
        with open(os.path.join(self.project, ".principal", "notebook.json"), "w") as fh:
            json.dump({"artifact": "0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0"}, fh)

    def copy(self, kind, extra=b""):
        os.makedirs(os.path.join(self.project, ".claude", "agents"), exist_ok=True)
        with open(os.path.join(ROOT, "agents", kind + ".md"), "rb") as fh:
            body = fh.read()
        with open(os.path.join(self.project, ".claude", "agents", kind + ".md"), "wb") as fh:
            fh.write(body + extra)

    def test_a_differing_copy_in_a_consumer_is_confined(self):
        self.consumer()
        for gate, (_, _, kinds) in GATES.items():
            for kind in kinds:
                for extra in (b"\n", None):
                    if extra is None:
                        path = os.path.join(self.project, ".claude", "agents", kind + ".md")
                        if os.path.exists(path):
                            os.remove(path)
                    else:
                        self.copy(kind, extra)
                    with self.subTest(gate=gate, kind=kind, extra=extra):
                        got = self.run_gate(gate, kind)
                        self.assertEqual(got["hookSpecificOutput"]["permissionDecision"],
                                         "deny")

    def test_a_differing_copy_elsewhere_is_the_project_s_own(self):
        for gate, (_, _, kinds) in GATES.items():
            for kind in kinds:
                self.copy(kind, b"\r\n")
                with self.subTest(gate=gate, kind=kind):
                    self.assertEqual(self.run_gate(gate, kind), {})


class ProjectDirOnlyTest(SharedRuleTest):
    """Round 1c's minor 4: a bare kind is known from CLAUDE_PROJECT_DIR when
    the call carries no cwd."""

    def test_no_cwd(self):
        os.makedirs(os.path.join(self.project, ".claude", "agents"))
        env = dict(self.env, CLAUDE_PROJECT_DIR=self.project)
        for gate, (tool, given, kinds) in GATES.items():
            for kind in kinds:
                shutil.copy(os.path.join(ROOT, "agents", kind + ".md"),
                            os.path.join(self.project, ".claude", "agents", kind + ".md"))
                call = {"tool_name": tool, "tool_input": given, "agent_type": kind}
                done = subprocess.run([sys.executable, "-B", os.path.join(HOOKS, gate)],
                                      input=json.dumps(call).encode(), capture_output=True,
                                      env=env, timeout=60)
                with self.subTest(gate=gate, kind=kind):
                    self.assertEqual(done.returncode, 0, done.stderr)
                    got = json.loads(done.stdout)
                    self.assertEqual(got["hookSpecificOutput"]["permissionDecision"], "deny")


class EscapedNameTest(SharedRuleTest):
    """Round 1c's minor 9: input that does not parse, naming a kind in JSON
    escapes, is read as the name it spells."""

    def test_escapes(self):
        for gate, (_, _, kinds) in GATES.items():
            kind = kinds[0]
            name = "principal:" + "".join("\\u%04x" % ord(c) for c in kind)
            for raw in (('{"agent_type":"%s","x":' % name).encode(),
                        ('{"agent_type":"%s","x":' % name.split(":", 1)[1]).encode()):
                done = subprocess.run([sys.executable, "-B", os.path.join(HOOKS, gate)],
                                      input=raw, capture_output=True, env=self.env,
                                      timeout=60)
                with self.subTest(gate=gate, raw=raw):
                    got = json.loads(done.stdout)
                    self.assertEqual(got["hookSpecificOutput"]["permissionDecision"], "deny")


if __name__ == "__main__":
    unittest.main()
