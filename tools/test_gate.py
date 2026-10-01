"""The canon agent's read gate lets the packet through, and nothing else."""

import importlib.util
import os
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
GATE = os.path.join(ROOT, "hooks", "canon-gate.py")


def load_gate():
    spec = importlib.util.spec_from_file_location("canon_gate", GATE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def call(path, tool="Read", cwd=None, agent="canon-answer"):
    return {"cwd": cwd or ROOT, "tool_name": tool, "agent_type": agent,
            "tool_input": {"file_path": path}}


class GateTest(unittest.TestCase):
    def setUp(self):
        self.gate = load_gate()
        self.root = ROOT

    def decision(self, c):
        return self.gate.decide(c)["hookSpecificOutput"]["permissionDecision"]

    def test_canon_on_disk_is_not_read(self):
        # the turn carries canon above its question in the packet, and there
        # is no reading past it: not the root question, not a landed answer
        self.assertEqual(self.decision(call("canon/ti-esti.md", cwd=self.root)), "deny")
        self.assertEqual(self.decision(call(os.path.join(self.root, "canon", "ti-esti.md"),
                                            cwd=self.root)), "deny")
        self.assertEqual(self.decision(call("ti-esti.md", cwd=self.root)), "deny")

    def test_a_file_beside_it_at_the_root_is_not(self):
        for name in os.listdir(self.root):
            if os.path.isfile(os.path.join(self.root, name)):
                self.assertEqual(self.decision(call(name, cwd=self.root)), "deny", name)
        self.assertEqual(self.decision(call("notebook.json", cwd=self.root)), "deny")

    def test_the_notebook_s_tooling_and_the_entry_points_are_not(self):
        for rel in ("tools/hypo/model.py", "skills/dictate/SKILL.md",
                    "agents/canon-answer.md", "hooks/canon-gate.py",
                    ".principal/bootstrap.json", ".principal/notebook.json",
                    "transcripts/index.json"):
            self.assertEqual(self.decision(call(rel, cwd=self.root)), "deny", rel)

    def test_no_list_makes_a_file_readable(self):
        # a list of canon was once the project's to keep; one left behind
        # admits nothing now
        with tempfile.TemporaryDirectory() as tmp:
            os.mkdir(os.path.join(tmp, ".principal"))
            with open(os.path.join(tmp, ".principal", "canon"), "w") as fh:
                fh.write("canon/root.md\n")
            os.mkdir(os.path.join(tmp, "canon"))
            with open(os.path.join(tmp, "canon", "root.md"), "w") as fh:
                fh.write("x\n")
            self.assertEqual(self.decision(call("canon/root.md", cwd=tmp)), "deny")
            self.assertEqual(self.decision(call("canon", cwd=tmp)), "deny")

    def test_the_packet_is_the_one_file_outside(self):
        with tempfile.TemporaryDirectory() as tmp:
            packet = os.path.join(tmp, "packet")
            os.mkdir(packet)
            self.assertEqual(self.decision(call(os.path.join(packet, "lineage.md"))), "allow")
            self.assertEqual(self.decision(call(os.path.join(packet, "notes.md"))), "deny")
            self.assertEqual(self.decision(call(os.path.join(tmp, "lineage.md"))), "deny")

    def test_a_path_that_climbs_out_is_read_as_where_it_lands(self):
        self.assertEqual(self.decision(call("/tmp/packet/lineage.md/../../etc/passwd")), "deny")

    def test_nothing_but_read(self):
        self.assertEqual(self.decision({"cwd": self.root, "tool_name": "Bash",
                                        "agent_type": "canon-answer",
                                        "tool_input": {"command": "cat ti-esti.md"}}), "deny")
        self.assertEqual(self.decision({"agent_type": "canon-answer"}), "deny")

    def test_only_the_canon_agent_is_gated(self):
        for agent in ("", None, "Explore", "general-purpose", "principal:dictate"):
            c = call("tools/hypo/model.py", cwd=self.root, agent=agent)
            self.assertEqual(self.gate.decide(c), {}, agent)
        self.assertEqual(self.gate.decide({}), {})

    def test_the_plugin_s_name_may_stand_in_front(self):
        self.assertEqual(self.decision(call("/tmp/x/packet/lineage.md", agent="principal:canon-answer")), "allow")
        self.assertEqual(self.decision(call("tools/next.py", agent="principal:canon-answer")), "deny")
        self.assertEqual(self.gate.decide(call("ti-esti.md", agent="my-canon-answer")), {})

    def test_a_refusal_names_no_file(self):
        out = self.gate.decide(call("notebook.json", cwd=self.root))
        self.assertNotIn("json", out["hookSpecificOutput"]["permissionDecisionReason"])

    def test_the_output_is_the_hook_s_shape(self):
        out = self.gate.decide(call("/tmp/x/packet/lineage.md", cwd=self.root))
        self.assertEqual(out["hookSpecificOutput"]["hookEventName"], "PreToolUse")
        self.assertIn("permissionDecisionReason", out["hookSpecificOutput"])


if __name__ == "__main__":
    unittest.main()
