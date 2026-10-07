"""A view read spells as the export did, so the reader takes it unchanged."""

import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from hypo import page, read  # noqa: E402

FIXTURES = os.path.join(HERE, "fixtures")


def fixture(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as fh:
        return fh.read()


class SpellingTest(unittest.TestCase):
    def test_a_real_tab_spells_as_its_export_did(self):
        self.assertEqual(page.markdown(fixture("view-wording.xml")), fixture("view-wording.md"))

    def test_the_tool_result_is_taken_as_well_as_its_xml(self):
        xml = fixture("view-wording.xml")
        wrapped = json.dumps({"verdict": "allow", "rev": 6, "data": {"rev": 6, "xml": xml}})
        self.assertEqual(page.markdown(wrapped), page.markdown(xml))
        self.assertEqual(page.markdown(json.loads(wrapped)), page.markdown(xml))

    def test_the_reader_parses_what_it_spells(self):
        tab = read.parse_tab(page.markdown(fixture("view-wording.xml")))
        self.assertEqual(tab["id"], "wording")
        self.assertEqual(tab["theses"][0]["applications"][0]["link"],
                         "[skills/dictate/SKILL.md](https://github.com/natb1/CanonDB/blob/main/skills/dictate/SKILL.md)")

    def test_a_mark_the_page_holds_as_a_character_is_spelled_behind_a_backslash(self):
        """The exporter escaped a literal star or bracket and the reader keeps
        the escape; spelled bare, the next render wrote a mark. Inside code
        nothing is a mark, so a code run is spelled as it stands."""
        xml = ("<doc><paragraph id='s.1'><text id='.2'>a * b, [c] and </text>"
               "<text id='.3'><code>x*y</code></text><text id='.4'> with \\ in it</text>"
               "</paragraph></doc>")
        self.assertEqual(page.markdown(xml), "a \\* b, \\[c\\] and `x*y` with \\\\ in it\n")
        self.assertEqual(read.parse_tab("⌂ root\n\n# q\n\n*%s*\n" % page.markdown(xml).strip())["question"],
                         "a \\* b, \\[c\\] and `x*y` with \\\\ in it")

    def test_a_split_link_is_one_link(self):
        xml = ("<doc><paragraph id='s.1'><text id='.2'><link href='u'>a/</link></text>"
               "<text id='.3'><link href='u'>b.md</link></text><text id='.4'> · x</text></paragraph></doc>")
        self.assertEqual(page.markdown(xml), "[a/b.md](u) · x\n")

    def test_nested_marks_spell_as_the_export_did(self):
        xml = ("<doc><paragraph id='s.1'><text id='.2'><italic><bold>Be predictable.</bold></italic></text>"
               "<text id='.3'><italic> Keep the same conventions.</italic></text></paragraph></doc>")
        self.assertEqual(page.markdown(xml), "***Be predictable.** Keep the same conventions.*\n")

    def test_table_note_list_and_headings(self):
        xml = ("<doc node='n' rev='3'><gone id='s.0' rev='1'/>"
               "<paragraph id='s.1' heading='2'><text id='.2'>Cited by</text></paragraph>"
               "<table id='.3'><row id='.4'><cell id='.5' header='true'><paragraph id='.6'><text id='.7'>question</text></paragraph></cell>"
               "<cell id='.8' header='true'><paragraph id='.9'><text id='.10'>waits on</text></paragraph></cell></row>"
               "<row id='.11'><cell id='.12'><paragraph id='.13'><mention id='.14' ref='file/x' label='canon'/></paragraph></cell>"
               "<cell id='.15'><paragraph id='.16'><text id='.17'><link href='#s.99'>Put it</link></text><text id='.18'>, </text>"
               "<text id='.19'><link href='#s.98'>Write it</link></text></paragraph></cell></row></table>"
               "<blockquote id='.20'><paragraph id='.21'><text id='.22'>Consider </text><text id='.23'><code>x</code></text>"
               "<text id='.24'> too.</text></paragraph></blockquote>"
               "<paragraph id='.25'><text id='.26'><bold>Support</bold></text></paragraph>"
               "<list id='.27' kind='bullet'><listItem id='.28'><paragraph id='.29'><text id='.30'>Polus concedes. </text>"
               "<mention id='.31' ref='file/p' label='Plato'/></paragraph></listItem></list>"
               "<paragraph id='.32'><text id='.33'>state: </text><dropdown id='.34' enum='e' index='1'>in thread</dropdown></paragraph>"
               "</doc>")
        self.assertEqual(page.markdown(xml), "\n\n".join([
            "## Cited by",
            "| question | waits on |\n| --- | --- |\n| canon | [Put it](#s.99), [Write it](#s.98) |",
            "> Consider `x` too.",
            "**Support**",
            "- Polus concedes. Plato",
            "state: in thread",
        ]) + "\n")

    def test_blocks_carry_their_ids_in_full(self):
        ids = [bid for bid, _ in page.blocks(fixture("view-wording.xml"))]
        self.assertEqual(ids[0], "mg8a8pjx8b4.9")
        self.assertIn("mg8a8pjx8b4.1421", ids)
        self.assertNotIn("mg8a8pjx8b4.0", ids)  # gone

    def test_the_cli_writes_one_md_per_view(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "wording.json")
            with open(src, "w", encoding="utf-8") as fh:
                json.dump({"data": {"xml": fixture("view-wording.xml")}}, fh)
            bad = os.path.join(tmp, "broken.xml")
            with open(bad, "w") as fh:
                fh.write("<doc><paragraph>")
            out = os.path.join(tmp, "tabs")
            proc = subprocess.run([sys.executable, os.path.join(HERE, "page.py"), src, "-o", out],
                                  capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            with open(os.path.join(out, "wording.md"), encoding="utf-8") as fh:
                self.assertEqual(fh.read(), fixture("view-wording.md"))
            proc = subprocess.run([sys.executable, os.path.join(HERE, "page.py"), bad, "-o", out],
                                  capture_output=True, text=True)
            self.assertEqual(proc.returncode, 1)
            self.assertIn("ERROR", proc.stderr)



class WalkTest(unittest.TestCase):
    def test_the_letters_of_an_element_the_walker_does_not_know_are_kept(self):
        import xml.etree.ElementTree as ET
        node = ET.fromstring("<paragraph><text>due </text><date value='2026-10-06'>6 Oct 2026"
                             "</date><text> sharp</text></paragraph>")
        self.assertEqual(page.inline(node), "due 6 Oct 2026 sharp")

    def test_a_partial_view_spells_no_tab(self):
        with self.assertRaises(ValueError):
            page.markdown("<doc rev='9' sinceRev='4'><paragraph id='a.1'><text>x</text>"
                          "</paragraph><gap blocks='7'/></doc>")

    def test_a_block_the_grammar_does_not_hold_is_said(self):
        with self.assertRaises(ValueError):
            page.markdown("<doc rev='1' sinceRev='0'><paragraph id='a.1'><text>x</text>"
                          "</paragraph><codeBlock id='.2'>print(1)</codeBlock></doc>")

    def test_a_read_without_xml_is_said(self):
        with self.assertRaises(ValueError):
            page.view_xml({"data": {"rev": 1}})


if __name__ == "__main__":
    unittest.main()
