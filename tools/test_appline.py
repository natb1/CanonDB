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


if __name__ == "__main__":
    unittest.main()
