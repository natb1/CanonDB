import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import persist  # noqa: E402


def write_log(path, author_turns=0, tool_results=0):
    with open(path, "w") as fh:
        for _ in range(author_turns):
            fh.write(json.dumps({"type": "user", "message": {"content": "hello"}}) + "\n")
        for _ in range(tool_results):
            fh.write(
                json.dumps(
                    {"type": "user", "message": {"content": [{"type": "tool_result", "content": "x"}]}}
                )
                + "\n"
            )
        fh.write(json.dumps({"type": "assistant", "message": {"content": "hi"}}) + "\n")
        fh.write("\n")
        fh.write("not json\n")


class TestCountTurns(unittest.TestCase):
    def test_counts_author_turns_only(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "a.jsonl")
            write_log(p, author_turns=3, tool_results=5)
            self.assertEqual(persist.count_turns(p), 3)


class TestResolve(unittest.TestCase):
    def test_single_log_needs_no_id(self):
        # patch.dict puts the session id back once the test is done with it
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ):
            write_log(os.path.join(d, "abc.jsonl"), 1)
            os.environ.pop("CLAUDE_CODE_SESSION_ID", None)
            sid, path = persist.resolve(d, None)
            self.assertEqual(sid, "abc")
            self.assertTrue(path.endswith("abc.jsonl"))

    def test_several_logs_without_id_exits(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ):
            write_log(os.path.join(d, "abc.jsonl"), 1)
            write_log(os.path.join(d, "def.jsonl"), 1)
            os.environ.pop("CLAUDE_CODE_SESSION_ID", None)
            with self.assertRaises(SystemExit):
                persist.resolve(d, None)

    def test_missing_id_exits(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(SystemExit):
                persist.resolve(d, "nope")


class TestCopyIfChanged(unittest.TestCase):
    def test_created_then_unchanged_then_updated(self):
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "s.jsonl")
            dst = os.path.join(d, "out", "s.jsonl")
            write_log(src, 1)
            self.assertEqual(persist.copy_if_changed(src, dst, False)[0], "created")
            self.assertEqual(persist.copy_if_changed(src, dst, False)[0], "unchanged")
            write_log(src, 2)
            self.assertEqual(persist.copy_if_changed(src, dst, False)[0], "updated")

    def test_dry_run_writes_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "s.jsonl")
            dst = os.path.join(d, "out", "s.jsonl")
            write_log(src, 1)
            self.assertEqual(persist.copy_if_changed(src, dst, True)[0], "created")
            self.assertFalse(os.path.exists(dst))


class TestIdempotence(unittest.TestCase):
    def test_second_run_reports_unchanged_and_keeps_first_seen(self):
        with tempfile.TemporaryDirectory() as d:
            source, dest = os.path.join(d, "src"), os.path.join(d, "dest")
            os.makedirs(os.path.join(source, "sid", "subagents"))
            write_log(os.path.join(source, "sid.jsonl"), 2)
            write_log(os.path.join(source, "sid", "subagents", "agent-1.jsonl"), 1)
            with open(os.path.join(source, "sid", "subagents", "agent-1.meta.json"), "w") as fh:
                fh.write("{}\n")
            with open(os.path.join(source, "sid", "ignored.txt"), "w") as fh:
                fh.write("skip me\n")
            argv = sys.argv
            try:
                sys.argv = ["persist.py", "--session-id", "sid", "--source", source, "--dest", dest]
                persist.main()
                with open(os.path.join(dest, "index.json")) as fh:
                    first = json.load(fh)["sessions"]["sid"]["first_seen"]
                persist.main()
                with open(os.path.join(dest, "index.json")) as fh:
                    idx = json.load(fh)["sessions"]["sid"]
            finally:
                sys.argv = argv
            self.assertEqual(idx["first_seen"], first)
            self.assertEqual(idx["log"]["author_turns"], 2)
            self.assertIn(os.path.join("subagents", "agent-1.jsonl"), idx["agents"])
            self.assertIn(os.path.join("subagents", "agent-1.meta.json"), idx["agents"])
            self.assertNotIn("ignored.txt", idx["agents"])
            self.assertTrue(
                os.path.exists(os.path.join(dest, "sid-agents", "subagents", "agent-1.jsonl"))
            )


if __name__ == "__main__":
    unittest.main()
