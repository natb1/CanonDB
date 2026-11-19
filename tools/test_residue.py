"""An open note: what a line leaves open, tracked on the tab it bears on."""

import json
import os
import tempfile
import unittest

from hypo import model, project, residue, share, spec
from hypo.model import Note
from support import fixture, load, run

WHOLE = ("open: whether the rule holds in a month of travel · kind: question · "
         "whose: user · from: canon, the second step · returns: the next sitting · "
         "case: a month abroad · read 2030-01-02: unchanged · read 2030-02-03: still open")


class ParseTest(unittest.TestCase):
    def test_the_parts_of_a_note(self):
        parts = residue.parse(WHOLE)
        self.assertEqual(parts["words"], "whether the rule holds in a month of travel")
        self.assertEqual(parts["kind"], "question")
        self.assertEqual(parts["whose"], "user")
        self.assertEqual(parts["from"], "canon, the second step")
        self.assertEqual(parts["returns"], "the next sitting")
        self.assertEqual(parts["case"], "a month abroad")
        self.assertEqual(parts["readings"], [("2030-01-02", "unchanged"),
                                             ("2030-02-03", "still open")])
        self.assertEqual(residue.missing(parts), [])

    def test_another_note_is_not_one(self):
        for body in ("pending: something a run could not apply",
                     "divergence: d · action: a", "opens a further question",
                     "opening: a word that only begins with it",
                     "open the door when it rains", "Open questions remain here.",
                     "open question: is it so", "open-ended: a word it begins",
                     "open.", "open"):
            with self.subTest(body=body):
                self.assertIsNone(residue.parse(body))
        for body in ("Open: the word, whatever its case", "open : spaced",
                     "OPEN : loud", "open:tight"):
            with self.subTest(body=body):
                self.assertTrue(residue.is_one(body))

    def test_compose_and_parse_agree(self):
        words = residue.compose("w", "work", "ai", "f", "r", "c", [("2030-01-02", "x")])
        parts = residue.parse(words)
        self.assertEqual((parts["words"], parts["kind"], parts["whose"], parts["from"],
                          parts["returns"], parts["case"], parts["readings"]),
                         ("w", "work", "ai", "f", "r", "c", [("2030-01-02", "x")]))
        self.assertEqual(residue.missing(parts), [])

    def test_a_colon_inside_a_part_reads_back(self):
        given = ("w: a colon", "work", "ai", "canon: step 2", "r: at 10:30", "c: x",
                 [("2030-01-02", "kind: not a kind")])
        parts = residue.parse(residue.compose(*given))
        self.assertEqual((parts["words"], parts["kind"], parts["whose"], parts["from"],
                          parts["returns"], parts["case"], parts["readings"]), given)
        self.assertEqual(residue.missing(parts) + residue.strays(parts), [])

    def test_a_part_holding_the_separator_or_a_line_break_is_refused(self):
        base = dict(words="w", kind="work", whose="ai", raised="f", returns="r", case="c")
        for part in ("words", "raised", "returns", "case"):
            for bad in ("a · kind: case", "a\nb", "a ·", "· a", "a\r\n· b"):
                with self.subTest(part=part, bad=bad):
                    with self.assertRaises(ValueError):
                        residue.compose(**dict(base, **{part: bad}))
        with self.assertRaises(ValueError):
            residue.compose("w", "work", "ai", "f", "r", "",
                            [("2030-01-02", "a · whose: user")])

    def test_a_reading_not_dated_yyyy_mm_dd_is_refused(self):
        for when in ("notadate", "2030-1-02", "2030-01-2", "2030-13-01", "２０３０-01-02",
                     "2030-01-02x", "30-01-02"):
            with self.subTest(when=when):
                with self.assertRaises(ValueError):
                    residue.compose("w", "work", "ai", "f", "r", "", [(when, "x")])

    def test_an_unknown_or_repeated_part_is_reported(self):
        parts = residue.parse("open: w · kind: work · whose: ai · from: f · returns: r · "
                              "colour: red · trailing words · read 2030-01-02 no colon · "
                              "kind: case")
        self.assertEqual(parts["kind"], "work")
        self.assertEqual(residue.missing(parts), [])
        self.assertEqual(residue.strays(parts),
                         ["a part it does not know (colour: red)",
                          "a part it does not know (trailing words)",
                          "a part it does not know (read 2030-01-02 no colon)",
                          "kind given twice"])
        self.assertEqual(residue.strays(residue.parse(WHOLE)), [])

    def test_the_case_is_left_out_where_none_was_put(self):
        words = residue.compose("w", "change", "user", "f", "r")
        self.assertNotIn("case:", words)
        self.assertEqual(residue.missing(residue.parse(words)), [])

    def test_each_required_part_left_out_is_named(self):
        whole = residue.parse(WHOLE)
        for part in ("words", "kind", "whose", "from", "returns"):
            with self.subTest(part=part):
                parts = dict(whole, **{part: ""})
                self.assertEqual(residue.missing(parts), [part])
        self.assertEqual(residue.missing(residue.parse("open: only the words")),
                         ["kind", "whose", "from", "returns"])
        self.assertEqual(residue.missing(residue.parse("open:")),
                         ["words", "kind", "whose", "from", "returns"])

    def test_a_kind_or_whose_out_of_its_set_is_named(self):
        parts = residue.parse("open: w · kind: reading · whose: nobody · from: f · returns: r")
        self.assertEqual(residue.missing(parts),
                         ["kind (question, case, change, work)", "whose (user or ai)"])


class RecordTest(unittest.TestCase):
    def graph(self, *bodies, on="canon"):
        graph = load("valid")
        for body in bodies:
            graph.get(on).notes.append(Note("thesis", body))
        return graph

    def test_a_whole_note_passes_the_check(self):
        self.assertEqual(spec.run(self.graph(WHOLE), only=["open-complete"]), [])

    def test_a_note_that_names_no_kind_fails_it(self):
        fired = spec.run(self.graph("open: only the words"), only=["open-complete"])
        self.assertEqual([f.question for f in fired], ["canon"])
        self.assertEqual(fired[0].severity, spec.ERROR)
        self.assertIn("an open note on thesis names no kind, whose, from, returns",
                      fired[0].message)

    def test_a_stray_part_fails_it(self):
        fired = spec.run(self.graph(WHOLE + " · colour: red"), only=["open-complete"])
        self.assertEqual(len(fired), 1)
        self.assertIn("holds a part it does not know (colour: red)", fired[0].message)

    def test_prose_opening_with_the_word_does_not_fire_it(self):
        self.assertEqual(spec.run(self.graph("Open questions remain here."),
                                  only=["open-complete"]), [])

    def test_the_check_holds_a_tradition_tab_the_listing_skips(self):
        graph = self.graph("open: only the words", on="plato")
        self.assertEqual(residue.found(graph), [])
        fired = spec.run(graph, only=["open-complete"])
        self.assertEqual([f.question for f in fired], ["plato"])

    def test_found_lists_each_with_its_gaps(self):
        found = residue.found(self.graph("open: only the words"))
        self.assertEqual(found[0].missing, ("kind", "whose", "from", "returns"))

    def test_found_skips_a_tradition_tab(self):
        graph = self.graph(WHOLE, on="plato")
        self.assertTrue(graph.get("plato").tradition)
        self.assertEqual(residue.found(graph), [])
        graph.get("canon").notes.append(Note("thesis", WHOLE))
        self.assertEqual([o.question for o in residue.found(graph)], ["canon"])

    def test_found_takes_one_project(self):
        graph = self.graph(WHOLE)
        self.assertEqual(len(residue.found(graph, "")), 1)
        self.assertEqual(residue.found(graph, "elsewhere"), [])


class CountTest(unittest.TestCase):
    def test_every_kind_and_whose_is_counted_and_none_open_is_a_count(self):
        self.assertEqual(residue.count([]),
                         "0 open · by kind: question 0, case 0, change 0, work 0 · "
                         "by whose: user 0, ai 0")

    def test_a_kind_out_of_its_set_is_counted_under_a_mark(self):
        graph = load("valid")
        graph.get("canon").notes.append(Note("thesis", "open: w"))
        graph.get("canon").notes.append(Note("thesis", WHOLE))
        self.assertEqual(residue.count(residue.found(graph)),
                         "2 open · by kind: question 1, case 0, change 0, work 0, ? 1 · "
                         "by whose: user 1, ai 0, ? 1")


def _written(graph_of):
    """A graph file with open notes on it, its path, removed by the caller."""
    with open(fixture("valid"), encoding="utf-8") as fh:
        data = json.load(fh)
    graph_of(data)
    handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                         encoding="utf-8")
    json.dump(data, handle)
    handle.close()
    return handle.name


def _note_on(data, qid, body):
    q = next(q for q in data["questions"] if q["id"] == qid)
    q.setdefault("notes", []).append({"section": "thesis", "body": body})


class ListTest(unittest.TestCase):
    def setUp(self):
        def notes(data):
            # canon carries less of the root than ti-esti and more than party
            _note_on(data, "party", residue.compose("p", "work", "ai", "f", "r"))
            _note_on(data, "canon", residue.compose("c", "case", "user", "f", "r"))
            _note_on(data, "ti-esti", residue.compose("t", "question", "user", "f", "r"))
        self.path = _written(notes)
        self.addCleanup(os.unlink, self.path)

    def lines(self, *args):
        done = run("residue.py", "list", self.path, *args)
        self.assertEqual(done.returncode, 0, done.stderr)
        return done.stdout.splitlines(), done.stderr

    def test_listed_in_tab_order_with_the_count_last(self):
        lines, _ = self.lines()
        self.assertEqual([line.split()[0] for line in lines[:-1]],
                         ["canon", "party", "ti-esti"])
        self.assertIn("c · kind: case · whose: user · returns: r · from: f", lines[0])
        self.assertEqual(lines[-1], "3 open · by kind: question 1, case 1, change 0, "
                                    "work 1 · by whose: user 2, ai 1")

    def test_by_share_the_heaviest_comes_first(self):
        lines, err = self.lines("--by-share")
        self.assertEqual([line.split()[0] for line in lines[:-1]],
                         ["ti-esti", "canon", "party"])
        self.assertIn("share 1.0000", lines[0])
        self.assertTrue(lines[-1].startswith("3 open"))
        self.assertEqual(err, "")

    def test_a_scoped_graph_whose_entry_is_of_kind_root_has_no_share(self):
        """A graph of two projects scoped below the first: the second's entry,
        a question of kind root, stands alone at the top and is not the root."""
        def scoped(data):
            data["projects"] = ["main", "side"]
            by = {q["id"]: q for q in data["questions"]}
            for q in data["questions"]:
                if not q.get("tradition"):
                    q["project"] = "side"
            by["ti-esti"]["project"] = "main"
            by["canon"]["kind"] = "root"
            data["questions"] = [q for q in data["questions"]
                                 if q["id"] not in ("ti-esti", "party")]
            _note_on(data, "canon", residue.compose("c", "case", "user", "f", "r"))
            _note_on(data, "attenuation", residue.compose("a", "work", "ai", "f", "r"))
        path = _written(scoped)
        self.addCleanup(os.unlink, path)
        graph = model.load(path)
        self.assertEqual(project.roots(graph), ["canon", "plato"])
        self.assertEqual(graph.get("canon").kind, "root")
        self.assertIsNone(graph.get("ti-esti"))
        # the share the listing would print were it not refused
        self.assertEqual(share.shares(graph)["canon"], 1.0)
        done = run("residue.py", "list", path, "--by-share")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("shares cannot be read without the root", done.stderr)
        lines = done.stdout.splitlines()
        self.assertEqual([line.split()[0] for line in lines[:-1]], ["attenuation", "canon"])
        self.assertNotIn("share", done.stdout)
        got = json.loads(run("residue.py", "list", path, "--by-share", "--json").stdout)
        self.assertNotIn("share", got["open"][0])

    def test_a_graph_without_its_root_says_so_and_keeps_tab_order(self):
        def scoped(data):
            data["questions"] = [q for q in data["questions"] if q["id"] in ("canon", "party")]
            for q in data["questions"]:
                q.pop("incoming", None)
                for t in q.get("theses", []):
                    t["terms"] = []
            _note_on(data, "party", residue.compose("p", "work", "ai", "f", "r"))
            _note_on(data, "canon", residue.compose("c", "case", "user", "f", "r"))
        path = _written(scoped)
        self.addCleanup(os.unlink, path)
        done = run("residue.py", "list", path, "--by-share")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("shares cannot be read without the root", done.stderr)
        self.assertNotIn("share ", done.stdout)
        self.assertEqual([line.split()[0] for line in done.stdout.splitlines()[:-1]],
                         ["canon", "party"])

    def test_a_scoped_graph_that_holds_the_root_has_no_share(self):
        """The review's case: scoped to some tabs and their ancestors, the
        root among them, a share read 1.0 where the whole graph gives less.
        The scope the graph records is what refuses it."""
        def scoped(data):
            data["scope"] = ["party"]
        path = _written(scoped)
        self.addCleanup(os.unlink, path)
        done = run("residue.py", "list", path, "--by-share")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("shares cannot be read without the root", done.stderr)
        self.assertNotIn("share ", done.stdout)

    def test_the_help_says_a_share_is_right_only_over_the_whole_graph(self):
        done = run("residue.py", "list", "--help")
        self.assertIn("right only over the graph of the whole notebook", " ".join(done.stdout.split()))

    def test_json_holds_each_note_and_the_count(self):
        lines, _ = self.lines("--json", "--by-share")
        got = json.loads("\n".join(lines))
        self.assertEqual([o["question"] for o in got["open"]], ["ti-esti", "canon", "party"])
        self.assertEqual(got["open"][0]["kind"], "question")
        self.assertEqual(got["open"][0]["share"], 1.0)
        self.assertTrue(got["count"].startswith("3 open"))


class JsonTest(unittest.TestCase):
    def test_the_count_is_a_field_and_the_help_says_so(self):
        path = _written(lambda data: _note_on(data, "canon", "open: w · colour: red"))
        self.addCleanup(os.unlink, path)
        got = json.loads(run("residue.py", "list", path, "--json").stdout)
        self.assertTrue(got["count"].startswith("1 open"))
        self.assertEqual(got["open"][0]["strays"], ["a part it does not know (colour: red)"])
        self.assertNotIn("share", got["open"][0])
        self.assertIn("count field", run("residue.py", "list", "--help").stdout)

    def test_a_stray_part_is_listed(self):
        path = _written(lambda data: _note_on(data, "canon", WHOLE + " · colour: red"))
        self.addCleanup(os.unlink, path)
        first = run("residue.py", "list", path).stdout.splitlines()[0]
        self.assertIn("STRAY: a part it does not know (colour: red)", first)


class NoteTest(unittest.TestCase):
    ARGS = ("--words", "w", "--kind", "work", "--whose", "ai", "--from", "f",
            "--returns", "r")

    def test_the_words_of_a_note(self):
        done = run("residue.py", "note", *self.ARGS, "--case", "c")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout.strip(),
                         "open: w · kind: work · whose: ai · from: f · returns: r · case: c")

    def test_an_unknown_kind_or_whose_is_refused(self):
        for at, bad in ((3, "reading"), (5, "nobody")):
            args = list(self.ARGS)
            args[at] = bad
            with self.subTest(bad=bad):
                self.assertEqual(run("residue.py", "note", *args).returncode, 2)

    def test_a_separator_a_line_break_or_a_bad_date_is_refused(self):
        for at, bad in ((1, "a · kind: case"), (7, "x\ny"), (9, "r · whose: user")):
            args = list(self.ARGS)
            args[at] = bad
            with self.subTest(bad=bad):
                done = run("residue.py", "note", *args)
                self.assertEqual(done.returncode, 1)
                self.assertIn("REFUSED", done.stderr)
                self.assertEqual(done.stdout, "")
        done = run("residue.py", "note", *self.ARGS, "--read", "notadate", "x")
        self.assertEqual(done.returncode, 1)
        self.assertIn("YYYY-MM-DD", done.stderr)

    def test_a_colon_in_a_part_reads_back_from_the_command(self):
        args = list(self.ARGS)
        args[7] = "the line: step 2"
        done = run("residue.py", "note", *args, "--read", "2030-01-02", "said: yes")
        self.assertEqual(done.returncode, 0, done.stderr)
        parts = residue.parse(done.stdout.strip())
        self.assertEqual((parts["from"], parts["readings"]),
                         ("the line: step 2", [("2030-01-02", "said: yes")]))

    def test_an_empty_required_part_is_refused(self):
        for at in (1, 7, 9):
            args = list(self.ARGS)
            args[at] = "  "
            with self.subTest(part=self.ARGS[at - 1]):
                done = run("residue.py", "note", *args)
                self.assertEqual(done.returncode, 1)
                self.assertIn("REFUSED", done.stderr)


if __name__ == "__main__":
    unittest.main()
