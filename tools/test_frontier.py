"""The frontier read off the page, from a few small searches per tab."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

from hypo import appline, frontier, model, page, project, turn
from test_cli import document
from test_inplace import SESSION, view_of

HERE = os.path.dirname(os.path.abspath(__file__))


def search(view, wanted):
    """A ``search`` of a view: only the blocks whose words hold ``wanted``,
    each printed with its full id, as a search prints what it found."""
    root = ET.fromstring(view)
    out = ET.Element("doc", rev=root.get("rev"))
    for node in list(root):
        bid = node.get("id")
        if node.tag == "paragraph" and wanted in page.inline(node):
            node.set("id", SESSION + bid if bid.startswith(".") else bid)
            out.append(node)
    return ET.tostring(out, encoding="unicode")


def reads(graph):
    """Per tab of the author's, the two searches the frontier asks for."""
    out = {}
    for q in graph.questions:
        if q.tradition:
            continue
        view, _ = view_of(graph, q.id)
        out[q.id] = [search(view, " · "), search(view, "▸ ")]
    return out


class FrontierTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        with open(document(self.dir)[0], encoding="utf-8") as fh:
            self.manifest = json.load(fh)
        self.graph = model.load(os.path.join(HERE, "fixtures", "valid.json"))
        self.graph.state_enum = "enum-1"  # the states as dropdowns, as the page has them

    def rows(self):
        return frontier.frontier(frontier.graph(self.manifest, reads(self.graph)))

    def test_the_searches_hold_no_body(self):
        view, by_id = view_of(self.graph, "canon")
        found = [b for r in reads(self.graph)["canon"] for b in appline.blocks(r)]
        self.assertLess(len(found), len(by_id) // 3)

    def test_a_question_under_an_answer_not_landed_is_not_on_it(self):
        """The root's answer is in thread: the root is on the frontier, and
        what it raises waits on it."""
        self.assertEqual(self.rows(), [("ti-esti", 27)])

    def test_a_landed_question_leaves_it_and_what_it_raised_comes_on(self):
        self.graph.get("ti-esti").theses[0].state = "landed"
        self.assertEqual(self.rows(), [("canon", 12), ("party", 9)])

    def test_it_agrees_with_the_graph_it_was_read_from(self):
        """The same relation over the whole graph file: the AI's questions not
        landed whose lineage has, by ``turn.above`` and ``project.landed``."""
        self.graph.get("ti-esti").theses[0].state = "landed"
        by_id = self.graph.by_id()
        whole = sorted(((q.id, q.pressure) for q in self.graph.questions
                        if not q.tradition and q.answerer == "ai"
                        and not project.landed(q)
                        and all(project.landed(by_id[a])
                                for a in turn.above(self.graph, q.id))),
                       key=lambda r: (-r[1], r[0]))
        self.assertEqual(self.rows(), whole)

    def test_a_tab_not_read_is_refused(self):
        partial = reads(self.graph)
        del partial["party"]
        with self.assertRaises(appline.Refused):
            frontier.graph(self.manifest, partial)

    def test_a_tab_with_no_question_line_is_refused(self):
        partial = reads(self.graph)
        partial["canon"] = partial["canon"][1:]
        with self.assertRaises(appline.Refused):
            frontier.graph(self.manifest, partial)

    def test_a_read_that_is_not_the_page_is_refused(self):
        partial = reads(self.graph)
        partial["canon"][0] = partial["canon"][0].replace("pressure 12", "pressure 99")
        with self.assertRaises(appline.Refused):
            frontier.graph(self.manifest, partial)


class CliTest(unittest.TestCase):
    def test_ids_and_numbers_only(self):
        where = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, where, ignore_errors=True)
        manifest, _ = document(where)
        graph = model.load(os.path.join(HERE, "fixtures", "valid.json"))
        folder = os.path.join(where, "reads")
        os.makedirs(folder)
        for qid, found in reads(graph).items():
            for n, xml in enumerate(found):
                with open(os.path.join(folder, "%s.search%d.xml" % (qid, n)), "w",
                          encoding="utf-8") as fh:
                    fh.write(xml)
        done = subprocess.run([sys.executable, os.path.join(HERE, "frontier.py"),
                               manifest, folder, "--json"],
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout),
                         {"frontier": [{"question": "ti-esti", "pressure": 27}]})
        plain = subprocess.run([sys.executable, os.path.join(HERE, "frontier.py"),
                                manifest, folder], capture_output=True, text=True)
        self.assertEqual(plain.stdout.split(), ["ti-esti", "27"])


if __name__ == "__main__":
    unittest.main()
