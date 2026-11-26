"""The rows that record the readings of tradition given in a round: one
entry, one insert, the notes joined in the file's order, and each fault in
the readings refused. Every party and position here is invented."""

import json
import os
import shutil
import tempfile
import unittest

from hypo import tradition
from hypo.appline import Refused
from support import run

READINGS = [{"party": "Example Author", "position": "Example position."},
            {"party": "Another Author", "position": "Another position, held apart."}]
NOTE = ("> pending: a tradition reading given in the sitting of 2030-01-02, a lead, not "
        "verified against the source and owed to a tab of its party: %s: %s")


class RowsTest(unittest.TestCase):
    def rows(self, readings=READINGS, sitting="2030-01-02"):
        return tradition.rows(readings, "blk-9", "node-3", sitting, "s1-record-1")

    def test_one_entry_one_insert_in_the_shape_the_recorder_sends(self):
        content = "\n\n".join(NOTE % (r["party"], r["position"]) for r in READINGS)
        self.assertEqual(self.rows(), [{
            "node": "node-3",
            "payload": {"ops": [{
                "op": "insert", "target": {"kind": "blocks", "ids": ["blk-9"]},
                "side": "after",
                "source": {"as": "markdown", "from": {"kind": "inline",
                                                      "content": content}}}]},
            "op_id": "s1-record-1"}])

    def test_the_notes_keep_the_file_s_order(self):
        content = self.rows(list(reversed(READINGS)))[0]["payload"]["ops"][0]["source"][
            "from"]["content"]
        self.assertLess(content.index("Another Author"), content.index("Example Author"))

    def test_one_reading_is_one_note(self):
        content = self.rows(READINGS[:1])[0]["payload"]["ops"][0]["source"]["from"]["content"]
        self.assertEqual(content, NOTE % ("Example Author", "Example position."))

    def refused(self, *args, **kw):
        with self.assertRaises(Refused) as caught:
            tradition.rows(*args, **kw)
        return str(caught.exception)

    def test_an_empty_list_is_refused(self):
        self.assertIn("non-empty list",
                      self.refused([], "b", "n", "2030-01-02", "op"))
        self.assertIn("non-empty list",
                      self.refused({"party": "x"}, "b", "n", "2030-01-02", "op"))

    def test_an_empty_party_or_position_is_refused(self):
        for bad in ({"party": "", "position": "Example position."},
                    {"party": "Example Author", "position": "  "},
                    {"party": "Example Author"},
                    "Example Author: Example position."):
            with self.subTest(bad=bad):
                self.refused([bad], "b", "n", "2030-01-02", "op")

    def test_a_party_or_position_that_breaks_a_line_is_refused(self):
        for bad in ({"party": "Example\nAuthor", "position": "Example position."},
                    {"party": "Example Author", "position": "One.\n\nTwo."}):
            with self.subTest(bad=bad):
                self.assertIn("breaks a line", self.refused([bad], "b", "n", "2030-01-02",
                                                            "op"))

    def test_a_date_not_of_the_form_is_refused(self):
        for bad in ("2030-1-2", "02-01-2030", "2030-13-01", "2030-01-02T03:04:05Z", ""):
            with self.subTest(bad=bad):
                self.refused(READINGS, "b", "n", bad, "op")

    def test_an_empty_block_node_or_op_id_is_refused(self):
        self.refused(READINGS, "", "n", "2030-01-02", "op")
        self.refused(READINGS, "b", "", "2030-01-02", "op")
        self.refused(READINGS, "b", "n", "2030-01-02", "")

    def test_a_note_the_reader_would_not_take_is_refused(self):
        self.refused([{"party": "Example Author", "position": "See <?claude block k?>."}],
                     "b", "n", "2030-01-02", "op")


class CliTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)

    def file(self, data):
        path = os.path.join(self.dir, "readings.json")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(data if isinstance(data, str) else json.dumps(data))
        return path

    def args(self, path, sitting="2030-01-02"):
        return ("rows", path, "--after", "blk-9", "--node", "node-3", "--sitting", sitting,
                "--op-id", "s1-record-1")

    def test_prints_the_rows_file(self):
        done = run("tradition.py", *self.args(self.file(READINGS)))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout), tradition.rows(
            READINGS, "blk-9", "node-3", "2030-01-02", "s1-record-1"))

    def test_reads_stdin(self):
        done = run("tradition.py", *self.args("-"), stdin=json.dumps(READINGS))
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_a_refusal_is_one_line_and_prints_nothing(self):
        for path, sitting in ((self.file([]), "2030-01-02"),
                              (self.file(READINGS), "tomorrow"),
                              (self.file("[not json"), "2030-01-02")):
            with self.subTest(sitting=sitting):
                done = run("tradition.py", *self.args(path, sitting))
                self.assertEqual(done.returncode, 1)
                self.assertEqual(done.stdout, "")
                self.assertTrue(done.stderr.startswith("REFUSED: "), done.stderr)
                self.assertEqual(len(done.stderr.strip().splitlines()), 1)


if __name__ == "__main__":
    unittest.main()
