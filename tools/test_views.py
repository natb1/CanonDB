"""The whole-tab reads in a helper's transcript, lifted into a file each."""

import json
import os
import tempfile
import unittest

from hypo import views
from support import read_fixture, run

TOOL = "mcp__claude_ai_Claude_Docs__read"


def call(cid, ref, payload, name=TOOL, as_text=False):
    """An assistant message that calls the read tool once."""
    given = {"ref": ref, "payload": payload}
    if as_text:
        given = {"ref": json.dumps(ref), "payload": json.dumps(payload)}
    return json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [
        {"type": "text", "text": "reading"},
        {"type": "tool_use", "id": cid, "name": name, "input": given}]}})


def result(cid, *texts):
    """The message that answers a call, one text part each."""
    return json.dumps({"type": "user", "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": cid,
         "content": [{"type": "text", "text": t} for t in texts]}]}})


def view(xml, rev=3, complete=True):
    return {"verdict": "allow", "rev": rev, "data": {"rev": rev, "xml": xml, "complete": complete}}


def node(nid):
    return {"object": "node", "id": nid}


def by_name(lifted):
    """What a lift saved, by the name its file would have."""
    return {views.name_of(k): v for k, v in lifted.saved.items()}


def answered(cid, nid, obj, payload=None, trail="", **kw):
    """A view of a node and its answer, the object followed by ``trail``."""
    return [call(cid, node(nid), payload or {"kind": "view"}, **kw),
            result(cid, json.dumps(obj) + trail)]


class LiftTest(unittest.TestCase):
    def test_a_view_is_lifted_and_the_text_after_it_ignored(self):
        lifted = views.lift(answered("c1", "n1", view("<doc rev='3'><p/></doc>"),
                                     trail="\n\nNext: read the outline."))
        self.assertEqual(lifted.errors, [])
        self.assertEqual(by_name(lifted)["n1"]["data"]["xml"], "<doc rev='3'><p/></doc>")

    def test_arguments_as_json_text_are_read(self):
        lifted = views.lift(answered("c1", "n1", view("<doc/>"), as_text=True,
                                     name="mcp__Claude_Docs__read"))
        self.assertEqual(list(by_name(lifted)), ["n1"])

    def test_the_last_read_of_a_node_wins(self):
        lines = (answered("c1", "n1", view("<doc>old</doc>", rev=1))
                 + answered("c2", "n1", view("<doc>new</doc>", rev=2)))
        self.assertEqual(by_name(views.lift(lines))["n1"]["rev"], 2)

    def test_a_continued_read_is_joined_to_the_one_it_continues(self):
        lines = (answered("c1", "n1", view("<doc node='n1' rev='4'><p>a</p></doc>", rev=4,
                                           complete=False))
                 + answered("c2", "n1", view("<doc node='n1' rev='4'><p>b</p></doc>", rev=5),
                            payload={"kind": "view", "from": "cursor"}))
        lifted = views.lift(lines)
        self.assertEqual(lifted.errors, [])
        got = by_name(lifted)["n1"]
        self.assertEqual(got["data"]["xml"], "<doc node='n1' rev='4'><p>a</p><p>b</p></doc>")
        self.assertTrue(got["data"]["complete"])
        self.assertEqual(got["rev"], 4)

    def test_a_node_whose_last_piece_is_not_complete_is_refused(self):
        lines = (answered("c1", "n1", view("<doc><p>a</p></doc>", complete=False))
                 + answered("c2", "n2", view("<doc/>")))
        lifted = views.lift(lines)
        self.assertEqual(list(by_name(lifted)), ["n2"])
        self.assertEqual(len(lifted.errors), 1)
        self.assertIn("n1", lifted.errors[0])

    def test_a_continuation_with_nothing_to_continue_is_refused(self):
        lifted = views.lift(answered("c1", "n1", view("<doc><p>b</p></doc>"),
                                     payload={"kind": "view", "from": "cursor"}))
        self.assertEqual(lifted.saved, {})
        self.assertIn("n1", lifted.errors[0])

    def test_a_result_saved_to_a_side_file_is_read_from_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            side = os.path.join(tmp, "result.txt")
            with open(side, "w", encoding="utf-8") as fh:
                json.dump([{"type": "text", "text": json.dumps(view("<doc>big</doc>")) + " more"}],
                          fh)
            lines = [call("c1", node("n1"), {"kind": "view"}),
                     result("c1", "Error: result exceeds maximum allowed tokens. Output has "
                                  "been saved to %s.\nFormat: JSON array" % side)]
            lifted = views.lift(lines)
        self.assertEqual(by_name(lifted)["n1"]["data"]["xml"], "<doc>big</doc>")

    def test_a_side_file_that_is_gone_is_an_error(self):
        lines = [call("c1", node("n1"), {"kind": "view"}),
                 result("c1", "Output has been saved to /nonexistent/result.txt.")]
        lifted = views.lift(lines)
        self.assertEqual(lifted.saved, {})
        self.assertIn("n1", lifted.errors[0])

    def test_a_tab_list_is_kept_and_a_search_passed_over(self):
        lines = [call("c1", {"object": "project", "id": "p1"}, {"kind": "tabs"}),
                 result("c1", json.dumps({"rev": 1, "tabs": []})),
                 call("c2", node("n1"), {"kind": "search", "query": "x"}),
                 result("c2", json.dumps({"rev": 1, "data": {"xml": "<doc/>"}}))]
        self.assertEqual(list(by_name(views.lift(lines))), ["doc-p1"])

    def test_a_line_that_is_not_json_is_skipped(self):
        lines = ["not json {", ""] + answered("c1", "n1", view("<doc/>"))
        self.assertEqual(list(by_name(views.lift(lines))), ["n1"])

    def test_a_refused_read_leaves_the_one_before(self):
        lines = (answered("c1", "n1", view("<doc>kept</doc>"))
                 + [call("c2", node("n1"), {"kind": "view"}), result("c2", "refused: rate")])
        self.assertEqual(by_name(views.lift(lines))["n1"]["data"]["xml"], "<doc>kept</doc>")


def piece(text, rev=4, nid="n1", complete=True, outer=None):
    """One piece of a continued view of ``nid``, its tag at ``rev``."""
    return view("<doc node='%s' rev='%d'>%s</doc>" % (nid, rev, text),
                rev=outer or rev, complete=complete)


def chain(*pieces, cursors=None):
    """A view and the reads that continue it, one call each."""
    lines = answered("c0", "n1", pieces[0])
    for i, got in enumerate(pieces[1:], 1):
        cursor = cursors[i - 1] if cursors else "k%d" % i
        lines += answered("c%d" % i, "n1", got, payload={"kind": "view", "from": cursor})
    return lines


class JoinTest(unittest.TestCase):
    A = "<paragraph id='s.1'>a</paragraph>"
    B = "<paragraph id='.2'>b</paragraph>"
    C = "<paragraph id='.3'>c</paragraph>"

    def refused(self, lines, why):
        lifted = views.lift(lines)
        self.assertEqual(lifted.saved, {})
        self.assertEqual(lifted.refused, [("node", "n1")])
        self.assertEqual(len(lifted.errors), 1)
        self.assertTrue(lifted.errors[0].startswith("n1: "), lifted.errors)
        self.assertIn(why, lifted.errors[0])

    def test_three_pieces_in_a_chain_are_joined_in_order(self):
        lifted = views.lift(chain(piece(self.A, complete=False), piece(self.B, complete=False),
                                  piece(self.C)))
        self.assertEqual(lifted.errors, [])
        self.assertEqual(by_name(lifted)["n1"]["data"]["xml"],
                         "<doc node='n1' rev='4'>%s%s%s</doc>" % (self.A, self.B, self.C))

    def test_a_piece_read_twice_from_one_cursor_is_refused(self):
        self.refused(chain(piece(self.A, complete=False), piece(self.B, complete=False),
                           piece(self.B, complete=False), piece(self.C),
                           cursors=["k1", "k1", "k2"]), "cursor")

    def test_a_piece_that_repeats_one_before_it_is_refused(self):
        self.refused(chain(piece(self.A, complete=False), piece(self.B, complete=False),
                           piece(self.B), cursors=["k1", "k2"]), "repeats")

    def test_pieces_at_different_revs_are_refused(self):
        self.refused(chain(piece(self.A, complete=False), piece(self.B, rev=9)), "rev")

    def test_pieces_of_different_tabs_are_refused(self):
        self.refused(chain(piece(self.A, complete=False), piece(self.B, nid="n2")), "n2")

    def test_a_piece_whose_tag_names_no_rev_is_refused(self):
        self.refused(chain(piece(self.A, complete=False),
                           view("<doc node='n1'>%s</doc>" % self.B)), "no rev")

    def test_a_join_that_does_not_parse_is_refused(self):
        self.refused(chain(piece(self.A, complete=False),
                           view("<doc node='n1' rev='4'/>")), "do not parse")

    def test_a_join_that_holds_a_block_twice_is_refused(self):
        self.refused(chain(piece(self.A, complete=False),
                           piece("<paragraph id='s.1'>again</paragraph>")), "s.1")

    def test_a_later_piece_after_a_refusal_keeps_the_reason(self):
        self.refused(chain(piece(self.A, complete=False), piece(self.B, rev=9, complete=False),
                           piece(self.C)), "rev")


class CursorKeyTest(unittest.TestCase):
    """A continuation is known by what comes before it, whatever its
    cursor's key is called."""

    def test_a_cursor_under_another_key_continues_an_incomplete_read(self):
        lines = (answered("c1", "n1", piece("<p id='a'>a</p>", complete=False),
                          payload={"kind": "view", "sinceRev": 0})
                 + answered("c2", "n1", piece("<p id='b'>b</p>"),
                            payload={"kind": "view", "sinceRev": 0, "after": "a.1"}))
        lifted = views.lift(lines)
        self.assertEqual(lifted.errors, [])
        self.assertIn("<p id='a'>a</p><p id='b'>b</p>", by_name(lifted)["n1"]["data"]["xml"])

    def test_the_review_s_half_tab_is_no_longer_saved_whole(self):
        """First read not complete, then a piece by another key that repeats
        nothing and parses: joined, never saved alone as the whole tab."""
        lines = (answered("c1", "n1", piece("<p id='a'>a</p>", complete=False))
                 + answered("c2", "n1", piece("<p id='z'>z</p>"),
                            payload={"kind": "view", "after": "a.1"}))
        got = by_name(views.lift(lines))["n1"]["data"]["xml"]
        self.assertIn("<p id='a'>a</p>", got)

    def test_another_key_with_nothing_incomplete_before_is_a_read_of_its_own(self):
        lines = (answered("c1", "n1", piece("<p id='a'>a</p>"))
                 + answered("c2", "n1", piece("<p id='b'>b</p>"),
                            payload={"kind": "view", "depth": 2}))
        lifted = views.lift(lines)
        self.assertEqual(lifted.errors, [])
        self.assertNotIn("<p id='a'>", by_name(lifted)["n1"]["data"]["xml"])

    def test_since_rev_alone_is_no_cursor(self):
        lines = (answered("c1", "n1", piece("<p id='a'>a</p>", complete=False))
                 + answered("c2", "n1", piece("<p id='b'>b</p>"),
                            payload={"kind": "view", "sinceRev": 0}))
        lifted = views.lift(lines)
        self.assertEqual(lifted.errors, [])
        self.assertNotIn("<p id='a'>", by_name(lifted)["n1"]["data"]["xml"])


class ReadKindTest(unittest.TestCase):
    def test_a_node_named_like_a_tab_list_is_still_held_whole(self):
        lifted = views.lift(answered("c1", "doc-x", view("<doc/>", complete=False)))
        self.assertEqual(lifted.saved, {})
        self.assertEqual(lifted.refused, [("node", "doc-x")])

    def test_a_tab_list_and_a_node_of_its_name_are_kept_apart(self):
        lines = ([call("c1", {"object": "project", "id": "p1"}, {"kind": "tabs"}),
                  result("c1", json.dumps({"rev": 1, "tabs": []}))]
                 + answered("c2", "doc-p1", view("<doc/>")))
        self.assertEqual(sorted(views.lift(lines).saved),
                         [("node", "doc-p1"), ("project", "p1")])


class SideFileTest(unittest.TestCase):
    def lifted(self, held, words="Error: result exceeds maximum allowed tokens. "
                                 "Output has been saved to %s.", before=()):
        with tempfile.TemporaryDirectory() as tmp:
            side = os.path.join(tmp, "result.txt")
            with open(side, "w", encoding="utf-8") as fh:
                fh.write(held)
            return views.lift(list(before) + [call("c1", node("n1"), {"kind": "view"}),
                                              result("c1", words.replace("%s", side))])

    def test_a_bare_object_is_the_read(self):
        lifted = self.lifted(json.dumps(view("<doc>bare</doc>")))
        self.assertEqual(by_name(lifted)["n1"]["data"]["xml"], "<doc>bare</doc>")

    def test_a_file_that_yields_no_object_is_an_error_by_node(self):
        for held in ("[]", json.dumps([{"type": "text", "text": "no object here"}]), "3"):
            with self.subTest(held=held):
                lifted = self.lifted(held, before=answered("c0", "n1", view("<doc>old</doc>")))
                self.assertEqual(lifted.saved, {})
                self.assertIn("n1", lifted.errors[0])
                self.assertIn("holds no object", lifted.errors[0])

    def test_other_words_naming_a_place_leave_the_read_before(self):
        lifted = self.lifted("[]", words="refused: the draft was saved to %s by hand",
                             before=answered("c0", "n1", view("<doc>kept</doc>")))
        self.assertEqual(lifted.errors, [])
        self.assertEqual(by_name(lifted)["n1"]["data"]["xml"], "<doc>kept</doc>")


class CommandTest(unittest.TestCase):
    TAB_LIST = {"value": {"tabs": {"t1": {"name": "wording"}, "t2": {"name": "canon"}}},
                "files": [{"id": "t1", "content": {"id": "n1"}},
                          {"id": "t2", "content": {"id": "n2"}}]}

    def transcript(self, tmp, lines):
        path = os.path.join(tmp, "t.jsonl")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        return path

    def test_each_view_is_written_and_counted(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = self.transcript(tmp, answered("c1", "n1", view("<doc/>"))
                                  + answered("c2", "n2", view("<doc/>")))
            done = run("views.py", src, os.path.join(tmp, "out"))
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertEqual(done.stdout, "2 saved: n1 n2\n")
            with open(os.path.join(tmp, "out", "n1.json"), encoding="utf-8") as fh:
                self.assertEqual(json.load(fh)["rev"], 3)

    def test_names_give_the_files_their_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = self.transcript(tmp, answered("c1", "n1", view("<doc/>"))
                                  + answered("c2", "n2", view("<doc/>")))
            names = os.path.join(tmp, "names.tsv")
            with open(names, "w", encoding="utf-8") as fh:
                fh.write("tab\tname\tproject\trev\tnode\n1\twording\tcanondb\t3\tn1\n")
            done = run("views.py", src, os.path.join(tmp, "out"), "--names", names)
            self.assertEqual(done.stdout, "2 saved: n2 wording\n")
            self.assertEqual(sorted(os.listdir(os.path.join(tmp, "out"))),
                             ["n2.json", "wording.json"])

    def test_an_incomplete_node_fails_the_run_by_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = self.transcript(tmp, answered("c1", "n1", view("<doc/>", complete=False))
                                  + answered("c2", "n2", view("<doc/>")))
            done = run("views.py", src, os.path.join(tmp, "out"))
            self.assertEqual(done.returncode, 1)
            self.assertIn("ERROR n1", done.stderr)
            self.assertEqual(done.stdout, "1 saved: n2\n")

    def test_two_nodes_given_one_name_are_both_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = self.transcript(tmp, answered("c1", "n1", view("<doc/>"))
                                  + answered("c2", "n2", view("<doc/>")))
            names = os.path.join(tmp, "names.tsv")
            with open(names, "w", encoding="utf-8") as fh:
                fh.write("1\tsame\tp\t1\tn1\n2\tsame\tp\t1\tn2\n")
            done = run("views.py", src, os.path.join(tmp, "out"), "--names", names)
            self.assertEqual(done.returncode, 1)
            self.assertEqual(done.stdout, "0 saved\n")

    def test_a_tab_list_names_the_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = self.transcript(tmp, answered("c1", "n1", view("<doc/>"))
                                  + answered("c2", "n3", view("<doc/>")))
            doc = os.path.join(tmp, "doc.json")
            with open(doc, "w", encoding="utf-8") as fh:
                json.dump(self.TAB_LIST, fh)
            done = run("views.py", src, os.path.join(tmp, "out"), "--doc", doc)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertEqual(done.stdout, "2 saved: n3 wording\n")

    def test_the_tab_list_this_saved_names_the_next_run(self):
        """The tool's whole result held the list under ``data``; the file
        holds it at the top, and the run handed it writes the tabs alone."""
        with tempfile.TemporaryDirectory() as tmp:
            lines = ([call("c0", {"object": "project", "id": "p1"}, {"kind": "tabs"}),
                      result("c0", json.dumps({"verdict": "allow", "rev": 1,
                                               "data": self.TAB_LIST}))]
                     + answered("c1", "n2", view("<doc/>")))
            src = self.transcript(tmp, lines)
            first = run("views.py", src, os.path.join(tmp, "out"))
            self.assertEqual(first.stdout, "2 saved: doc-p1 n2\n")
            with open(os.path.join(tmp, "out", "doc-p1.json"), encoding="utf-8") as fh:
                saved = json.load(fh)
            self.assertEqual(saved, dict(self.TAB_LIST, verdict="allow", rev=1))
            done = run("views.py", src, os.path.join(tmp, "named"),
                       "--doc", os.path.join(tmp, "out", "doc-p1.json"))
            self.assertEqual(done.stdout, "1 saved: canon\n")
            self.assertEqual(os.listdir(os.path.join(tmp, "named")), ["canon.json"])

    def test_list_only_writes_the_tab_list_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            lines = ([call("c0", {"object": "project", "id": "p1"}, {"kind": "tabs"}),
                      result("c0", json.dumps({"rev": 1, "data": self.TAB_LIST}))]
                     + answered("c1", "n2", view("<doc/>"))
                     + answered("c2", "n3", view("<doc/>", complete=False)))
            done = run("views.py", self.transcript(tmp, lines), os.path.join(tmp, "out"),
                       "--list-only")
            self.assertEqual((done.returncode, done.stdout), (0, "1 saved: doc-p1\n"))
            self.assertEqual(os.listdir(os.path.join(tmp, "out")), ["doc-p1.json"])

    def test_a_tab_list_read_by_its_link_is_named_by_its_trailing_id(self):
        uuid = "0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0"
        for given in ("https://example.invalid/code/artifact/" + uuid,
                      "https://example.invalid/code/artifact/My-Notebook-" + uuid + "?t=1",
                      "https://example.invalid/artifact/Notes-AbCdEfGhIjKlMnOpQrStUv/",
                      uuid):
            with self.subTest(given=given), tempfile.TemporaryDirectory() as tmp:
                lines = [call("c0", {"object": "project", "id": given}, {}),
                         result("c0", json.dumps({"rev": 1, "data": self.TAB_LIST}))]
                done = run("views.py", self.transcript(tmp, lines), os.path.join(tmp, "o"))
                self.assertEqual(done.returncode, 0, done.stderr)
                want = "AbCdEfGhIjKlMnOpQrStUv" if "Notes-" in given else uuid
                self.assertEqual(done.stdout, "1 saved: doc-%s\n" % want)

    def test_a_wrapped_tab_list_is_not_taken_by_doc(self):
        """One shape: the one read.py takes. A list still under ``data`` names
        no body here, as it names no tab there."""
        with tempfile.TemporaryDirectory() as tmp:
            doc = os.path.join(tmp, "doc.json")
            with open(doc, "w", encoding="utf-8") as fh:
                json.dump({"verdict": "allow", "data": self.TAB_LIST}, fh)
            done = run("views.py", self.transcript(tmp, answered("c1", "n1", view("<doc/>"))),
                       os.path.join(tmp, "out"), "--doc", doc)
            self.assertEqual(done.returncode, 1)
            self.assertIn("names no tab's body", done.stderr)

    def test_list_only_and_doc_together_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = self.transcript(tmp, answered("c1", "n1", view("<doc/>")))
            done = run("views.py", src, os.path.join(tmp, "out"), "--doc", src, "--list-only")
            self.assertEqual(done.returncode, 2)

    def test_doc_and_names_together_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = self.transcript(tmp, answered("c1", "n1", view("<doc/>")))
            done = run("views.py", src, os.path.join(tmp, "out"), "--doc", src,
                       "--names", src)
            self.assertEqual(done.returncode, 2)
            self.assertIn("not allowed with", done.stderr)
            self.assertFalse(os.path.exists(os.path.join(tmp, "out")))

    def refuses_names(self, tmp, lines, *args, bad):
        src = self.transcript(tmp, lines)
        out = os.path.join(tmp, "deep", "out")
        done = run("views.py", src, out, *args)
        self.assertEqual(done.returncode, 1)
        self.assertIn("ERROR %r: not a file name" % bad, done.stderr)
        self.assertEqual(done.stdout, "")
        self.assertEqual(sorted(os.listdir(tmp)),
                         sorted(f for f in ("t.jsonl", "names.tsv", "doc.json")
                                if os.path.exists(os.path.join(tmp, f))))

    def test_a_node_id_that_is_a_path_writes_nothing(self):
        for bad in ("../../escaped", "/tmp/escaped", ".hidden", "a/b", ""):
            with self.subTest(bad=bad), tempfile.TemporaryDirectory() as tmp:
                self.refuses_names(tmp, answered("c1", "n1", view("<doc/>"))
                                   + answered("c2", bad, view("<doc/>")), bad=bad)

    def test_a_project_id_that_is_a_path_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            lines = [call("c1", {"object": "project", "id": "p e"}, {"kind": "tabs"}),
                     result("c1", json.dumps({"rev": 1}))]
            self.refuses_names(tmp, lines, bad="doc-p e")

    def test_a_project_id_with_a_path_is_named_by_its_last_segment_inside_out(self):
        with tempfile.TemporaryDirectory() as tmp:
            lines = [call("c1", {"object": "project", "id": "../pe"}, {"kind": "tabs"}),
                     result("c1", json.dumps({"rev": 1}))]
            out = os.path.join(tmp, "deep", "out")
            done = run("views.py", self.transcript(tmp, lines), out)
            self.assertEqual(done.stdout, "1 saved: doc-pe\n")
            self.assertEqual(os.listdir(out), ["doc-pe.json"])
            self.assertEqual(sorted(os.listdir(tmp)), ["deep", "t.jsonl"])

    def test_a_refused_node_with_a_bad_name_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.refuses_names(tmp, answered("c1", "../n", view("<doc/>", complete=False)),
                               bad="../n")

    def test_a_name_given_that_is_a_path_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            names = os.path.join(tmp, "names.tsv")
            with open(names, "w", encoding="utf-8") as fh:
                fh.write("1\t../up\tp\t1\tn1\n")
            self.refuses_names(tmp, answered("c1", "n1", view("<doc/>")), "--names", names,
                               bad="../up")

    def test_a_tab_name_that_is_a_path_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc = os.path.join(tmp, "doc.json")
            with open(doc, "w", encoding="utf-8") as fh:
                json.dump({"value": {"tabs": {"t1": {"name": "a/../../b"}}},
                           "files": [{"id": "t1", "content": {"id": "n1"}}]}, fh)
            self.refuses_names(tmp, answered("c1", "n1", view("<doc/>")), "--doc", doc,
                               bad="a/../../b")

    def test_a_refused_node_takes_the_earlier_file_away(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "out")
            first = run("views.py", self.transcript(tmp, answered("c1", "n1", view("<doc/>"))),
                        out)
            self.assertEqual(first.stdout, "1 saved: n1\n")
            src = self.transcript(tmp, answered("c1", "n1", view("<doc/>", complete=False))
                                  + answered("c2", "n2", view("<doc/>")))
            done = run("views.py", src, out)
            self.assertEqual(done.returncode, 1)
            self.assertEqual(sorted(os.listdir(out)), ["n2.json"])

    def test_two_nodes_given_one_name_take_the_earlier_file_away(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "out")
            os.makedirs(out)
            with open(os.path.join(out, "same.json"), "w", encoding="utf-8") as fh:
                fh.write("{}")
            src = self.transcript(tmp, answered("c1", "n1", view("<doc/>"))
                                  + answered("c2", "n2", view("<doc/>")))
            names = os.path.join(tmp, "names.tsv")
            with open(names, "w", encoding="utf-8") as fh:
                fh.write("1\tsame\tp\t1\tn1\n2\tsame\tp\t1\tn2\n")
            run("views.py", src, out, "--names", names)
            self.assertEqual(os.listdir(out), [])

    def test_a_missing_transcript_is_an_error_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            done = run("views.py", os.path.join(tmp, "gone.jsonl"), os.path.join(tmp, "out"))
            self.assertEqual(done.returncode, 1)
            self.assertTrue(done.stderr.startswith("ERROR transcript: "), done.stderr)
            self.assertNotIn("Traceback", done.stderr)
            self.assertFalse(os.path.exists(os.path.join(tmp, "out")))

    def test_a_doc_that_names_no_body_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = self.transcript(tmp, answered("c1", "n1", view("<doc/>")))
            doc = os.path.join(tmp, "doc.json")
            with open(doc, "w", encoding="utf-8") as fh:
                json.dump({"value": {"tabs": {}}}, fh)
            done = run("views.py", src, os.path.join(tmp, "out"), "--doc", doc)
            self.assertEqual(done.returncode, 1)
            self.assertIn("ERROR doc", done.stderr)


class ChainTest(unittest.TestCase):
    """What views.py writes is what page.py and read.py take, as the
    sitting runs them: the tab list by --list-only, the tabs by --doc, then
    page.py over every file of the views and read.py over the list."""

    def test_read_py_takes_the_tab_list_views_py_wrote(self):
        xml = read_fixture("view-wording.xml")
        node_id = "962b0362-16a8"
        tab_list = {"value": {"tabs": {"t1": {"name": "wording"}, "t2": {"name": "ti-esti"},
                                       "t3": {"name": "recognition"},
                                       "t4": {"name": "context"}}},
                    "files": [{"id": "t1", "content": {"id": node_id}}],
                    "frame": {"artifactUrl": "https://example.invalid/code/artifact/x"}}
        with tempfile.TemporaryDirectory() as tmp:
            lines = ([call("c0", {"object": "project", "id": "p1"}, {}),
                      result("c0", json.dumps({"verdict": "allow", "rev": 2,
                                               "data": tab_list}))]
                     + answered("c1", node_id, {"verdict": "allow", "rev": 6,
                                                "data": {"rev": 6, "xml": xml}},
                                payload={"kind": "view", "sinceRev": 0}))
            src = os.path.join(tmp, "t.jsonl")
            with open(src, "w", encoding="utf-8") as fh:
                fh.write("\n".join(lines) + "\n")
            lists, views_dir = os.path.join(tmp, "lists"), os.path.join(tmp, "views")
            self.assertEqual(run("views.py", src, lists, "--list-only").stdout,
                             "1 saved: doc-p1\n")
            listed = os.path.join(lists, "doc-p1.json")
            self.assertEqual(run("views.py", src, views_dir, "--doc", listed).stdout,
                             "1 saved: wording\n")
            every = sorted(os.path.join(views_dir, n) for n in os.listdir(views_dir))
            tabs = os.path.join(tmp, "tabs")
            done = run("page.py", *every, "-o", tabs)
            self.assertEqual(done.returncode, 0, done.stderr)
            graph = os.path.join(tmp, "graph.json")
            done = run("read.py", listed, tabs, "-o", graph)
            self.assertEqual(done.returncode, 0, done.stderr)
            with open(graph, encoding="utf-8") as fh:
                got = json.load(fh)
            self.assertEqual([q["id"] for q in got["questions"]], ["wording"])
            self.assertEqual(got["questions"][0]["body"], node_id)
            self.assertEqual(got["questions"][0]["rev"], 6)
            self.assertEqual(got["artifact"], "https://example.invalid/code/artifact/x")
            # the shape the round saved before: read.py names no tab of it
            wrapped = os.path.join(tmp, "wrapped.json")
            with open(wrapped, "w", encoding="utf-8") as fh:
                json.dump({"verdict": "allow", "rev": 2, "data": tab_list}, fh)
            done = run("read.py", wrapped, tabs, "-o", graph)
            self.assertEqual(done.returncode, 1)
            self.assertIn("names no tab of the document", done.stderr)


if __name__ == "__main__":
    unittest.main()
