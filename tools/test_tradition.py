"""The rows that record the readings of tradition given in a round: one
entry, one insert after the last block of a section of a saved read, the
notes joined in the file's order, and each fault in the readings, the ids or
the placement refused. Every party and position here is invented."""

import json
import os
import shutil
import tempfile
import unittest
import xml.etree.ElementTree as ET
from unittest import mock

from hypo import inplace, page, tradition
from hypo.appline import Refused
from support import load, run
from test_inplace import view_of

READINGS = [{"party": "Example Author", "position": "Example position."},
            {"party": "Another Author", "position": "Another position, held apart."}]
NOTE = ("> pending: a tradition reading given in the sitting of 2030-01-02, a lead, not "
        "verified against the source and owed to a tab of its party: %s: %s")


def last_of(source, section):
    """The last block of a section of a saved view, and the section's heading."""
    blocks = page.blocks(source)
    start = next(i for i, (_, md) in enumerate(blocks) if md == "## " + section)
    end = next((i for i in range(start + 1, len(blocks)) if blocks[i][1].startswith("## ")),
               len(blocks))
    return blocks[end - 1][0], blocks[start][0]


def view():
    """A saved view of a tab of the fixture graph, the last block of its
    Hinge section, and that section's heading."""
    source, _ = view_of(load(), "canon")
    return (source,) + last_of(source, "Hinge")


def without_hinge(source):
    """The same view with its Hinge section gone, as the renderer leaves a
    section with nothing in it."""
    root = ET.fromstring(source)
    kids = list(root)
    at = next(i for i, node in enumerate(kids)
              if node.get("heading") == "2" and "".join(node.itertext()).strip() == "Hinge")
    for node in kids[at:]:
        root.remove(node)
    return ET.tostring(root, encoding="unicode")


class RowsTest(unittest.TestCase):
    def setUp(self):
        self.source, self.last, self.heading = view()

    def rows(self, readings=READINGS, sitting="2030-01-02", after=None, node="node-3",
             op_id="s1-record-1"):
        return tradition.rows(self.source, readings, after or self.last, node, sitting, op_id)

    def refused(self, **kw):
        with self.assertRaises(Refused) as caught:
            self.rows(**kw)
        return str(caught.exception)

    def test_one_entry_one_insert_in_the_shape_the_recorder_sends(self):
        content = "\n\n".join(NOTE % (r["party"], r["position"]) for r in READINGS)
        self.assertEqual(self.rows(), [{
            "node": "node-3",
            "payload": {"ops": [{
                "op": "insert", "target": {"kind": "blocks", "ids": [self.last]},
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

    def test_a_block_not_the_last_of_its_section_or_not_on_the_tab_is_refused(self):
        self.assertIn("last block", self.refused(after=self.heading))
        self.assertIn("holds no block", self.refused(after="no-such-block"))

    def test_the_section_is_held(self):
        thesis, _ = last_of(self.source, "Thesis")
        self.assertIn("not of Hinge", self.refused(after=thesis))
        self.assertEqual(len(tradition.rows(self.source, READINGS, thesis, "node-3",
                                            "2030-01-02", "op", section="Thesis")), 1)
        self.assertIn("not of Thesis", self.refused_section(self.last, "Thesis"))

    def refused_section(self, after, section, source=None):
        with self.assertRaises(Refused) as caught:
            tradition.rows(source or self.source, READINGS, after, "node-3", "2030-01-02",
                           "op", section=section)
        return str(caught.exception)

    def test_a_tab_without_the_section_is_refused(self):
        source = without_hinge(self.source)
        last = page.blocks(source)[-1][0]
        self.assertIn("not of Hinge", self.refused_section(last, "Hinge", source))

    def test_an_id_holding_whitespace_a_quote_or_a_newline_is_refused(self):
        for bad in (" blk", 'a","b', "a'b", "a\nb", "a\\b", "a\u200bb", "a\u2060b",
                    "a\u00a0b", "a\tb"):
            with self.subTest(bad=bad):
                self.assertIn("--after", self.refused(after=bad))
                self.assertIn("--node", self.refused(node=bad))
                self.assertIn("--op-id", self.refused(op_id=bad))
        self.assertIn("--node", self.refused(node=""))
        self.assertIn("--op-id", self.refused(op_id=""))

    def test_an_empty_list_is_refused(self):
        self.assertIn("non-empty list", self.refused(readings=[]))
        self.assertIn("non-empty list", self.refused(readings={"party": "x"}))

    def test_an_empty_party_or_position_is_refused(self):
        for bad in ({"party": "", "position": "Example position."},
                    {"party": "Example Author", "position": "  "},
                    {"party": "Example Author"},
                    "Example Author: Example position."):
            with self.subTest(bad=bad):
                self.refused(readings=[bad])

    def test_a_party_or_position_that_breaks_a_line_is_refused_by_name(self):
        for ch in ("\n", "\r", " ", " ", "\x85", "\v", "\f"):
            for bad in ({"party": "Example" + ch + "Author", "position": "Example position."},
                        {"party": "Example Author", "position": "One." + ch + "Two."}):
                with self.subTest(bad=bad):
                    self.assertIn("breaks a line", self.refused(readings=[bad]))

    def test_a_party_holding_the_separator_is_refused(self):
        self.assertIn('holds ": "', self.refused(
            readings=[{"party": "Example: Author", "position": "Example position."}]))
        self.rows([{"party": "Example Author", "position": "One: two."}])

    def test_the_size_is_bounded(self):
        self.refused(readings=READINGS[:1] * (tradition.MAX_READINGS + 1))
        self.assertIn("longer than", self.refused(
            readings=[{"party": "Example Author", "position": "x" * 2001}]))
        self.assertIn("longer than", self.refused(
            readings=[{"party": "A" * 201, "position": "Example position."}]))

    def test_a_date_not_of_the_form_is_refused(self):
        for bad in ("2030-1-2", "02-01-2030", "2030-13-01", "2030-01-02T03:04:05Z", ""):
            with self.subTest(bad=bad):
                self.refused(sitting=bad)

    def test_a_note_the_reader_would_not_take_is_refused(self):
        self.refused(readings=[{"party": "Example Author",
                                "position": "See <?claude block k?>."}])

    def test_the_read_back_refuses_notes_that_do_not_come_back_as_given(self):
        """Reached past every earlier check: the reader is made to take back
        one note fewer than the readings."""
        real = inplace._read_back

        def short(markdown, ids=None):
            got = real(markdown, ids)
            got["notes"] = got["notes"][:-1]
            return got

        with mock.patch.object(inplace, "_read_back", short):
            self.assertIn("1 note(s) read back for 2 reading(s)", self.refused())


class CliTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.source, self.last, _ = view()
        self.read = self.file("view.xml", self.source)

    def file(self, name, data):
        path = os.path.join(self.dir, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(data if isinstance(data, str) else json.dumps(data))
        return path

    def args(self, read, readings, sitting="2030-01-02"):
        return ("rows", read, readings, "--after", self.last, "--node", "node-3",
                "--sitting", sitting, "--op-id", "s1-record-1")

    def test_prints_the_rows_file(self):
        done = run("tradition.py", *self.args(self.read, self.file("r.json", READINGS)))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout), tradition.rows(
            self.source, READINGS, self.last, "node-3", "2030-01-02", "s1-record-1"))

    def test_reads_either_from_stdin_but_not_both(self):
        done = run("tradition.py", *self.args(self.read, "-"), stdin=json.dumps(READINGS))
        self.assertEqual(done.returncode, 0, done.stderr)
        done = run("tradition.py", *self.args("-", self.file("r.json", READINGS)),
                   stdin=self.source)
        self.assertEqual(done.returncode, 0, done.stderr)
        done = run("tradition.py", *self.args("-", "-"), stdin="")
        self.assertEqual(done.returncode, 1)
        self.assertIn("both be stdin", done.stderr)

    def test_a_refusal_is_one_line_and_prints_nothing(self):
        for readings, sitting in ((self.file("a.json", []), "2030-01-02"),
                                  (self.file("b.json", READINGS), "tomorrow"),
                                  (self.file("c.json", "[not json"), "2030-01-02")):
            with self.subTest(sitting=sitting):
                done = run("tradition.py", *self.args(self.read, readings, sitting))
                self.assertEqual(done.returncode, 1)
                self.assertEqual(done.stdout, "")
                self.assertTrue(done.stderr.startswith("REFUSED: "), done.stderr)
                self.assertEqual(len(done.stderr.strip().splitlines()), 1)


if __name__ == "__main__":
    unittest.main()
