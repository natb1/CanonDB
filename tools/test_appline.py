"""One application written in place: read off the page, checked, rebuilt."""

import hashlib
import json
import os
import subprocess
import sys
import unittest

from hypo import appline

HERE = os.path.dirname(os.path.abspath(__file__))

LINE_RUNS = ("<text id='.2'><code>tools/x.py</code></text>"
             "<text id='.3'>, a tool · ◆ A thesis · </text>"
             "<text id='.4'><link href='https://example.com/x.py'>tools/x.py</link></text>"
             "<text id='.5'> · postulate (while the principal answers this question)</text>")
LINE_TEXT = ("tools/x.py, a tool · ◆ A thesis · tools/x.py · postulate "
             "(while the principal answers this question)")
LINE_MD = ("`tools/x.py`, a tool · ◆ A thesis · [tools/x.py](https://example.com/x.py)"
           " · postulate (while the principal answers this question)")


def h(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]


def view(line_h=None, head_h=None, hit=False):
    runs = LINE_RUNS
    if hit:
        runs = runs.replace("> · ◆ A thesis", "><hit n='1'> · ◆ </hit>A thesis")
    return ("<doc rev='3'><paragraph id='abc.0' h='%s' heading='3'>"
            "<text id='.1'>⚙ the tool</text></paragraph>"
            "<paragraph id='.9' h='%s'>%s</paragraph></doc>"
            % (head_h or h("⚙ the tool"), line_h or h(LINE_TEXT), runs))


class ReadTest(unittest.TestCase):
    def test_a_line_reads_back_and_rebuilds_as_the_page_holds_it(self):
        fields = appline.read_line(view(), "abc.9")
        self.assertEqual(fields["h"], h(LINE_TEXT))
        self.assertEqual(appline.line(fields), LINE_MD)
        self.assertEqual(fields["clause"], "while the principal answers this question")

    def test_a_search_hit_is_folded_back_into_its_run(self):
        self.assertEqual(appline.line(appline.read_line(view(hit=True), "abc.9")), LINE_MD)

    def test_a_read_that_is_not_the_page_is_refused(self):
        with self.assertRaises(appline.Refused):
            appline.read_line(view(line_h="00000000"), "abc.9")

    def test_a_mention_contributes_nothing_to_the_hash(self):
        import xml.etree.ElementTree as ET
        node = ET.fromstring("<paragraph><text>see </text><mention label='x'/></paragraph>")
        self.assertEqual(appline.digest(node), h("see "))


class PageTest(unittest.TestCase):
    """A real read of a tab, as the document printed it."""

    def setUp(self):
        with open(os.path.join(HERE, "fixtures", "view-wording.xml"), encoding="utf-8") as fh:
            self.view = fh.read()

    def test_every_block_hashes_as_the_document_printed(self):
        """A dropdown's word is the enum's and not the block's letters: the
        question line and an answer's line hash without it."""
        for bid in appline.blocks(self.view):
            appline.block(self.view, bid)

    def test_the_session_is_taken_from_whatever_prints_it_first(self):
        """Here a retired block's ``gone`` prints it, and every id after is
        short."""
        self.assertIn("mg8a8pjx8b4.1421", appline.blocks(self.view))
        fields = appline.read_line(self.view, "mg8a8pjx8b4.1421")
        self.assertEqual((fields["h"], fields["rev"]), ("3b254abd", 6))


class OpsTest(unittest.TestCase):
    def test_replace_is_guarded_by_the_hash_read(self):
        fields = appline.read_line(view(), "abc.9")
        fields["what"] = "`tools/x.py`, a better tool"
        op = appline.replace_op(fields)
        self.assertEqual(op["ifHash"], h(LINE_TEXT))
        self.assertEqual(op["ifRev"], 3)  # the read's, which the document asks for too
        self.assertEqual(op["target"]["ids"], ["abc.9"])
        self.assertTrue(op["with"]["from"]["content"].startswith("`tools/x.py`, a better tool · ◆"))

    def test_insert_writes_a_heading_and_its_line(self):
        fields = {"what": "w", "thesis": "T", "link": "not yet written", "standing": "postulate"}
        op = appline.insert_op("abc.9", "new", fields)
        self.assertEqual(op["source"]["from"]["content"], "### ⚙ new\n\nw · ◆ T · not yet written · postulate")

    def test_a_standing_outside_the_vocabulary_is_refused(self):
        with self.assertRaises(appline.Refused):
            appline.line({"what": "w", "thesis": "T", "link": "", "standing": "built"})

    def test_delete_takes_the_heading_and_the_line_each_guarded(self):
        ops = appline.delete_ops(view(), "abc.0", "abc.9")
        self.assertEqual([o["target"]["ids"][0] for o in ops], ["abc.0", "abc.9"])
        self.assertEqual(ops[0]["ifHash"], h("⚙ the tool"))
        self.assertEqual([o["ifRev"] for o in ops], [3, 3])

    def test_a_read_with_no_rev_is_refused(self):
        with self.assertRaises(appline.Refused):
            appline.read_line(view().replace(" rev='3'", ""), "abc.9")

    def test_delete_refuses_a_heading_that_is_not_an_application(self):
        bad = view().replace("⚙ the tool", "Thesis").replace(h("⚙ the tool"), h("Thesis"))
        with self.assertRaises(appline.Refused):
            appline.delete_ops(bad, "abc.0", "abc.9")


class CliTest(unittest.TestCase):
    def test_replace_prints_the_ops_of_one_update(self):
        out = subprocess.run([sys.executable, os.path.join(HERE, "application.py"),
                              "replace", "-", "--block", "abc.9", "--note", "n"],
                             input=view(), capture_output=True, text=True, check=True)
        ops = json.loads(out.stdout)["ops"]
        self.assertTrue(ops[0]["with"]["from"]["content"].endswith(" · n"))



class LineTest(unittest.TestCase):
    FIELDS = {"what": "a tool", "thesis": "A thesis", "link": "tools/x.py", "standing": "postulate"}

    def test_a_field_carrying_the_separator_is_refused(self):
        for field in ("what", "thesis", "link"):
            with self.subTest(field=field), self.assertRaises(appline.Refused):
                appline.line(dict(self.FIELDS, **{field: "a · b"}))

    def test_the_note_may_carry_the_separator(self):
        self.assertTrue(appline.line(dict(self.FIELDS, note="a · b")).endswith(" · a · b"))

    def test_a_clause_with_a_bracket_does_not_read_back(self):
        with self.assertRaises(appline.Refused):
            appline.line(dict(self.FIELDS, clause="a) b"))

    def test_a_note_breaking_a_line_is_refused(self):
        with self.assertRaises(appline.Refused):
            appline.line(dict(self.FIELDS, note="one\ntwo"))


def two_applications():
    return ("<doc rev='3'>"
            "<paragraph id='abc.0' h='%s' heading='3'><text id='.1'>⚙ one</text></paragraph>"
            "<paragraph id='.10' h='%s'>%s</paragraph>"
            "<paragraph id='.11' h='%s' heading='3'><text id='.12'>⚙ two</text></paragraph>"
            "<paragraph id='.13' h='%s'>%s</paragraph></doc>"
            % (h("⚙ one"), h(LINE_TEXT), LINE_RUNS, h("⚙ two"), h(LINE_TEXT), LINE_RUNS))


class DeleteTest(unittest.TestCase):
    def test_the_line_deleted_is_the_heading_s_own(self):
        self.assertEqual(len(appline.delete_ops(two_applications(), "abc.0", "abc.10")), 2)
        with self.assertRaises(appline.Refused):
            appline.delete_ops(two_applications(), "abc.0", "abc.13")

    def test_a_read_that_is_not_one_is_refused(self):
        with self.assertRaises(appline.Refused):
            appline.blocks("<doc rev='1'><paragraph id='a.1'>unclosed</doc>")
        with self.assertRaises(appline.Refused):
            appline.blocks(json.dumps({"data": {"rev": 1}}))



class ReadErrorTest(unittest.TestCase):
    def test_a_read_that_is_not_there_is_said_not_tracebacked(self):
        done = subprocess.run([sys.executable, os.path.join(HERE, "application.py"), "replace",
                               os.path.join(HERE, "nope.xml"), "--block", "a.1"],
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 1)
        self.assertIn("ERROR read", done.stderr)
        self.assertNotIn("Traceback", done.stderr)
        done = subprocess.run([sys.executable, os.path.join(HERE, "application.py"), "replace",
                               "-", "--block", "a.1"],
                              input="<doc rev='1'><paragraph id='a.1'>unclosed</doc>",
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 1)
        self.assertIn("REFUSED", done.stderr)


if __name__ == "__main__":
    unittest.main()
