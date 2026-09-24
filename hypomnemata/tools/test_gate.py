"""The canon agent's read gate lets canon and the packet through, and nothing else."""

import importlib.util
import os
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
GATE = os.path.abspath(os.path.join(HERE, "..", "..", ".claude", "hooks", "canon-gate.py"))


def load_gate():
    spec = importlib.util.spec_from_file_location("canon_gate", GATE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def call(path, tool="Read", cwd=None):
    return {"cwd": cwd or os.path.join(HERE, "..", ".."), "tool_name": tool,
            "tool_input": {"file_path": path}}


class GateTest(unittest.TestCase):
    def setUp(self):
        self.gate = load_gate()
        self.root = os.path.abspath(os.path.join(HERE, "..", ".."))

    def decision(self, c):
        return self.gate.decide(c)["hookSpecificOutput"]["permissionDecision"]

    def test_the_root_question_is_canon(self):
        self.assertEqual(self.decision(call("ti-esti.md", cwd=self.root)), "allow")
        self.assertEqual(self.decision(call(os.path.join(self.root, "ti-esti.md"),
                                            cwd=self.root)), "allow")

    def test_the_envelope_is_not(self):
        for name in os.listdir(self.root):
            if name.endswith(".json"):
                self.assertEqual(self.decision(call(name, cwd=self.root)), "deny", name)

    def test_the_notebook_s_tooling_and_the_entry_points_are_not(self):
        for rel in ("hypomnemata/tools/hypo/model.py",
                    ".claude/skills/principal-dictate/SKILL.md",
                    ".claude/agents/canon-answer.md", "transcripts/index.json"):
            self.assertEqual(self.decision(call(rel, cwd=self.root)), "deny", rel)

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
                                        "tool_input": {"command": "cat ti-esti.md"}}), "deny")
        self.assertEqual(self.decision({}), "deny")

    def test_a_refusal_names_no_file(self):
        out = self.gate.decide(call("hypomnemata-canondb-v1.json", cwd=self.root))
        self.assertNotIn("json", out["hookSpecificOutput"]["permissionDecisionReason"])

    def test_the_output_is_the_hook_s_shape(self):
        out = self.gate.decide(call("ti-esti.md", cwd=self.root))
        self.assertEqual(out["hookSpecificOutput"]["hookEventName"], "PreToolUse")
        self.assertIn("permissionDecisionReason", out["hookSpecificOutput"])


if __name__ == "__main__":
    unittest.main()
