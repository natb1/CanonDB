"""The open lines: the schema and its checks, the ground moved, the sweep,
what closes a line and what refuses to, the order, parents and children,
the weekly chunk and the user's decision, and the skill's own lines run as
written. Every record here is invented."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest

from hypo import lines
from support import fixture, run

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.join(HERE, "..", "skills", "sit", "SKILL.md")

#: an outline as ``page.py --outlines`` writes one: the tab's blocks, each
#: with its fingerprint, every id whole
OUTLINE = ("<doc node='n' rev='4' sinceRev='0'>"
           "<paragraph id='s1.6' h='h5' heading='2'><text id='s1.7'>Evenings</text></paragraph>"
           "<paragraph id='s1.15' h='h6'><text id='s1.16'>The lamp is lit.</text></paragraph>"
           "</doc>")

T = "2030-02-01T00:00:00Z"
T1 = "2030-02-08T00:00:00Z"


def rec(lid, state="open", kind="question", anchors=(), opened="2030-01-01T00:00:00Z",
        **more):
    out = {"id": lid, "title": "Line %s" % lid, "kind": kind, "state": state,
           "ask": {"case": "A case.", "prompt": "A prompt?", "recommendation": None},
           "why": "Invented.", "source": "s203001010000", "anchors": list(anchors),
           "seal": None, "parent": None, "children": [], "answered_by": None, "rank": None,
           "opened_at": opened, "touched_at": opened, "review_count": 0, "origin": "speaker"}
    out.update(more)
    return out


def anchor(tab, block=None, h=None):
    out = {"tab": tab, "words": "Words on %s." % tab}
    if block:
        out["block"] = block
    if h:
        out["h"] = h
    return out


def standard():
    """a and b share mornings/b1; c is a's child; d is put; e is closed; f
    rests on evenings with no block and no opening time."""
    return [
        rec("a", anchors=[anchor("mornings", "b1", "h1")], children=["c"], rank=2,
            opened="2030-01-01T00:00:00Z"),
        rec("b", anchors=[anchor("mornings", "b1", "h1"), anchor("mornings", "b2", "h2")],
            rank=3, opened="2030-01-02T00:00:00Z"),
        rec("c", anchors=[anchor("evenings", "b5", "h5")], parent="a", rank=4,
            opened="2030-01-03T00:00:00Z"),
        rec("d", state="put", kind="review", anchors=[anchor("evenings")], rank=1),
        rec("e", state="closed", anchors=[anchor("mornings", "b1", "h1")],
            closed_by={"sentence": "That is settled.", "answer": "answers/1.md"},
            answered_by="answers/1.md", reopenable=True, rank=5),
        rec("f", anchors=[anchor("evenings")], opened=None, rank=5),
    ]


class Dir:
    """An export: one file per record under ``lines/``, and its versions."""

    def __init__(self, test, records, nested=True, versions=None):
        self.root = tempfile.mkdtemp()
        test.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        base = os.path.join(self.root, "lines") if nested else self.root
        os.makedirs(base, exist_ok=True)
        for r in records:
            with open(os.path.join(base, r["id"] + ".json"), "w") as fh:
                json.dump(r, fh)
        self.versions = os.path.join(self.root, "versions.json")
        with open(self.versions, "w") as fh:
            json.dump(versions if versions is not None else
                      {"lines/%s" % r["id"]: i + 10 for i, r in enumerate(records)}, fh)

    def file(self, name, content):
        path = os.path.join(self.root, name)
        with open(path, "w") as fh:
            fh.write(content if isinstance(content, str) else json.dumps(content))
        return path

    def lines(self):
        with open(self.versions) as fh:
            return lines.read(self.root, json.load(fh))


def every(found):
    """All that ``check`` found, faults, mendable and warnings alike."""
    return found.faults + found.mendable + found.warnings


def ids(writes):
    return [w["doc_id"] for w in writes]


class Base(unittest.TestCase):
    def given(self, records=None, **kw):
        self.d = Dir(self, standard() if records is None else records, **kw)
        return self.d.lines()

    def refused(self, fn, *args, **kw):
        with self.assertRaises(lines.Refused) as caught:
            fn(*args, **kw)
        return " | ".join(caught.exception.reasons)


class CheckTest(Base):
    def test_the_standard_export_checks(self):
        self.assertEqual(self.given().problems, [])

    def test_an_export_flat_or_under_lines_reads_alike(self):
        self.assertEqual(sorted(self.given(nested=False).records), list("abcdef"))
        self.assertEqual(sorted(self.given().records), list("abcdef"))

    def test_each_field_is_held_to_its_shape(self):
        bad = rec("x", kind="chore", state="waiting", rank=-1, pressure=-2,
                  anchors=[{"words": "no tab"}, anchor("t", None, "h9")],
                  children="y", proposed="keep", flags={"other": {"at": T}})
        bad["title"] = " "
        found = lines.shape(bad)
        for words in ("title is missing", "kind is not one of", "state is not one of",
                      "rank is not a whole number", "pressure is not a number",
                      "anchors[0] has no tab", "anchors[1] has a fingerprint and no block",
                      "children is not a list", "proposed is not", "flags holds 'other'"):
            self.assertTrue(any(words in p for p in found), (words, found))

    def test_a_file_whose_id_is_not_its_name_is_found(self):
        self.given([rec("a")])
        self.d.file(os.path.join("lines", "c.json"), rec("b"))
        problems = self.d.lines().problems
        self.assertEqual(problems, ["c.json: its id 'b' is not its file's name"])
        self.d.file(os.path.join("lines", "c.json"), "[1]")
        self.assertEqual(self.d.lines().problems, ["c.json is not an object"])
        self.d.file(os.path.join("lines", "c.json"), "{")
        self.assertIn("c.json cannot be read", self.d.lines().problems[0])

    def test_the_states_that_need_the_user_s_words(self):
        found = every(lines.check({
            "c": rec("c", state="closed"),
            "m": rec("m", state="merged"),
            "x": rec("x", state="dropped"),
            "o": rec("o", closed_by={"sentence": "Settled.", "answer": "a"}),
            "q": rec("q", state="closed", closed_by={"sentence": " ", "answer": "a"}),
        }))
        text = "\n".join(found)
        self.assertIn("c: state is closed with neither the user's sentence nor an answer", text)
        self.assertIn("m: state is merged into no line", text)
        self.assertIn("x: state is dropped without the user's word", text)
        self.assertIn("o: state is open and the line still carries closed_by", text)
        self.assertIn("q: closed_by quotes no sentence of the user's", text)

    def test_parent_and_child_agree_on_both_sides(self):
        found = "\n".join(every(lines.check({
            "p": rec("p", children=["k", "z"]), "k": rec("k"),
            "j": rec("j", parent="p"), "n": rec("n", parent="nowhere", blocks=["gone"])})))
        self.assertIn("p: lists k as a child whose parent is None", found)
        self.assertIn("p: its child z is no line", found)
        self.assertIn("j: its parent p does not list it among its children", found)
        self.assertIn("n: its parent nowhere is no line", found)
        self.assertIn("n: blocks gone, which is no line", found)

    def test_no_line_is_its_own_ancestor(self):
        found = every(lines.check({"a": rec("a", parent="b", children=["b"]),
                             "b": rec("b", parent="a", children=["a"])}))
        self.assertTrue(any("a cycle" in p for p in found), found)

    def test_no_chain_of_blocks_returns_to_where_it_began(self):
        found = every(lines.check({"a": rec("a", blocks=["b"]), "b": rec("b", blocks=["c"]),
                             "c": rec("c", blocks=["a"]), "s": rec("s", blocks=["s"])}))
        self.assertIn("a cycle of blocks and waits_on: a -> b -> c -> a", found)
        self.assertIn("s: blocks itself", found)

    def test_one_line_put_and_no_rank_held_twice(self):
        found = every(lines.check({"a": rec("a", state="put", rank=1), "b": rec("b", state="put"),
                             "c": rec("c", rank=1), "d": rec("d", state="closed",
                                                              answered_by="x", rank=1)}))
        self.assertIn("more than one line is put: a, b", found)
        self.assertIn("rank 1 is held by a, c; order mends it", found)

    def test_what_order_and_orphans_mend_refuses_only_the_other_modes(self):
        records = standard()
        records[1]["rank"] = 2  # b now shares a's rank
        records.append(rec("g", parent="nowhere"))
        given = self.given(records)
        self.assertEqual(given.found.faults, [])
        self.assertEqual(len(given.found.mendable), 2)
        self.assertTrue(lines.order(given, {}, T).writes)
        self.assertEqual(ids(lines.orphans(given, T)[1]), ["g"])
        self.assertEqual(len(lines.queue(given)), 5)
        self.assertIn("do not check", self.refused(lines.close, given, "a", "Yes.", "x", T))

    def test_an_anchor_with_no_block_is_a_warning_and_refuses_nothing(self):
        found = lines.check({"a": rec("a", anchors=[anchor("t"), anchor("t", "b1", "h")]),
                             "b": rec("b", anchors=[anchor("u")])})
        self.assertEqual((found.faults, found.mendable), ([], []))
        self.assertEqual(len(found.warnings), 1)
        self.assertIn("2 anchor(s) on 2 open line(s) name no block", found.warnings[0])

    def test_the_cli_prints_each_problem_and_exits_one(self):
        self.given([rec("a", parent="b")])
        done = run("lines.py", "check", self.d.root)
        self.assertEqual(done.returncode, 1)
        self.assertIn("ERROR a: its parent b is no line", done.stdout)
        self.given()
        done = run("lines.py", "check", self.d.root)
        self.assertEqual(done.returncode, 0)
        self.assertEqual(done.stdout.splitlines()[0], "ok: 6 line(s), 5 open or put")
        self.assertIn("WARN 2 anchor(s) on 2 open line(s)", done.stdout)

    def test_every_writing_mode_refuses_over_records_that_do_not_check(self):
        self.given([rec("a", parent="b")])
        done = run("lines.py", "close", self.d.root, "a", "--sentence", "Settled.",
                   "--by-answer", "answers/1.md", "--at", T, "--versions", self.d.versions)
        self.assertEqual(done.returncode, 1)
        self.assertIn("REFUSED: the records do not check", done.stderr)
        self.assertEqual(done.stdout, "")


class MovedTest(Base):
    def blocks(self, change=None):
        now = {("mornings", "b1"): "h1", ("mornings", "b2"): "h2", ("evenings", "b5"): "h5"}
        now.update(change or {})
        return [{"tab": t, "block": b, "h": h} for (t, b), h in now.items() if h is not None]

    def test_a_changed_fingerprint_flags_every_open_line_on_it(self):
        found, writes, _ = lines.moved(self.given(), self.blocks({("mornings", "b1"): "h1x"}), T)
        self.assertEqual([f["id"] for f in found], ["a", "b"])
        self.assertEqual(ids(writes), ["a", "b"])
        self.assertEqual(writes[0], {
            "op": "update", "collection": "lines", "doc_id": "a", "if_version": 10,
            "data": {"flags": {"ground-moved": {"at": T, "anchors": [
                {"tab": "mornings", "block": "b1", "was": "h1", "now": "h1x"}]}},
                "touched_at": T}})

    def test_a_block_gone_from_a_tab_read_is_withdrawn(self):
        now = [b for b in self.blocks() if b["block"] != "b5"] + [{"tab": "evenings"}]
        found, writes, _ = lines.moved(self.given(), now, T)
        self.assertEqual(ids(writes), ["c"])
        self.assertEqual(found[0]["anchors"][0]["now"], None)

    def test_what_cannot_be_judged_is_counted_and_not_flagged(self):
        # d and f anchor evenings with no block; a, b (three anchors) stand on
        # mornings, which this read does not hold
        found, writes, blind = lines.moved(self.given(), [{"tab": "evenings"}], T)
        self.assertEqual((ids(writes), blind), (["c"], 5))
        found, writes, blind = lines.moved(self.given(), [], T)
        self.assertEqual((found, writes, blind), ([], [], 6))

    def test_a_tab_gone_from_a_whole_read_is_withdrawn(self):
        found, writes, blind = lines.moved(self.given(), [{"tab": "evenings"}], T, whole=True)
        self.assertEqual(ids(writes), ["a", "b", "c"])
        self.assertTrue(found[0]["anchors"][0]["tab_gone"])
        self.assertEqual(blind, 2)

    def test_a_closed_line_is_not_flagged_and_a_flag_is_not_written_twice(self):
        now = [b for b in self.blocks() if b["block"] != "b5"] + [{"tab": "evenings"}]
        records = standard()
        records[2]["flags"] = {"ground-moved": {"at": T, "anchors": [
            {"tab": "evenings", "block": "b5", "was": "h5", "now": None}]}}
        found, writes, _ = lines.moved(self.given(records), now, T1)
        self.assertEqual(([f["id"] for f in found], writes), (["c"], []))
        found, _, _ = lines.moved(self.given(), self.blocks({("mornings", "b1"): "zz"}), T)
        self.assertNotIn("e", [f["id"] for f in found])

    def test_the_time_is_handed_in_and_checked(self):
        self.assertIn("--at", self.refused(lines.moved, self.given(), [], "yesterday"))

    def test_a_document_the_versions_do_not_name_is_refused(self):
        self.given(versions={})
        done = run("lines.py", "moved", self.d.root, "--blocks",
                   self.d.file("b.json", [{"tab": "evenings"}]), "--at", T,
                   "--versions", self.d.versions)
        self.assertEqual(done.returncode, 1)
        self.assertIn("REFUSED: the versions file does not name lines/c", done.stderr)

    def test_the_cli_prints_what_moved_beside_the_writes(self):
        self.given()
        done = run("lines.py", "moved", self.d.root, "--blocks",
                   self.d.file("b.json", {"blocks": [{"tab": "evenings"}]}), "--at", T,
                   "--versions", self.d.versions)
        out = json.loads(done.stdout)
        self.assertEqual([m["id"] for m in out["moved"]], ["c"])
        self.assertEqual(ids(out["writes"]), ["c"])
        self.assertEqual(out["unjudged_anchors"], 5)

    def test_the_blocks_are_read_from_the_outlines_page_py_writes(self):
        self.given()
        where = os.path.join(self.d.root, "outlines")
        os.makedirs(where)
        with open(os.path.join(where, "evenings.xml"), "w") as fh:
            fh.write(OUTLINE)
        self.assertEqual(lines.blocks_of_outlines(where), [
            {"tab": "evenings"}, {"tab": "evenings", "block": "s1.6", "h": "h5"},
            {"tab": "evenings", "block": "s1.15", "h": "h6"}])
        done = run("lines.py", "moved", self.d.root, "--outlines", where, "--at", T,
                   "--versions", self.d.versions)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(ids(json.loads(done.stdout)["writes"]), ["c"])
        with open(os.path.join(where, "evenings.xml"), "w") as fh:
            fh.write("<doc rev='1' sinceRev='3'><gap/></doc>")
        self.assertRaises(lines.Refused, lines.blocks_of_outlines, where)

    def test_unflag_clears_one_kind_and_takes_the_fingerprints_now(self):
        records = standard()
        records[2]["flags"] = {"ground-moved": {"at": T, "anchors": []},
                               "touched": {"answer": "x", "at": T}}
        writes = lines.unflag(self.given(records), "c", "ground-moved", T1,
                              [{"tab": "evenings", "block": "b5", "h": "h5new"}])
        self.assertEqual(writes[0]["data"]["flags"], {"ground-moved": None})
        self.assertEqual(writes[0]["data"]["anchors"][0]["h"], "h5new")
        self.assertNotIn("anchors", lines.unflag(self.given(records), "c", "ground-moved",
                                                 T1)[0]["data"])
        self.assertIn("carries no touched flag",
                      self.refused(lines.unflag, self.given(), "a", "touched", T))
        self.assertIn("only in clearing a ground-moved flag",
                      self.refused(lines.unflag, self.given(records), "c", "touched", T, []))

    def test_a_flag_of_one_kind_never_overwrites_another(self):
        records = standard()
        records[2]["flags"] = {"ground-moved": {"at": T, "anchors": []}}
        writes = lines.touch(self.given(records), "c", "answers/2.md", T1)
        self.assertEqual(list(writes[0]["data"]["flags"]), ["touched"])

    def test_a_block_read_gone_is_kept_so_and_not_flagged_again(self):
        records = standard()
        records[2]["flags"] = {"ground-moved": {"at": T, "anchors": []}}
        now = [{"tab": "evenings"}]
        writes = lines.unflag(self.given(records), "c", "ground-moved", T1, now)
        anchors = writes[0]["data"]["anchors"]
        self.assertTrue(anchors[0]["gone"])
        records[2]["anchors"] = anchors
        records[2]["flags"] = {"ground-moved": None}
        self.assertEqual(lines.moved(self.given(records), now, T1)[1], [])


class OrphanTest(Base):
    def test_a_child_of_a_dropped_or_merged_parent_is_flagged(self):
        records = standard()
        records[0].update(state="dropped", decision={"choice": "drop", "word": "Drop it.",
                                                      "at": T})
        found, writes = lines.orphans(self.given(records), T1)
        self.assertEqual(ids(writes), ["c"])
        self.assertEqual(writes[0]["data"]["flags"],
                         {"parent-withdrawn": {"parent": "a", "at": T1}})
        records[2]["flags"] = writes[0]["data"]["flags"]
        self.assertEqual(lines.orphans(self.given(records), T1)[1], [])

    def test_a_standing_parent_flags_nothing(self):
        self.assertEqual(lines.orphans(self.given(), T), ([], []))


class SweepTest(Base):
    def test_children_first_then_siblings_then_shared_anchors(self):
        records = standard() + [rec("g", parent="a", rank=6, anchors=[anchor("x", "b9")])]
        records[0]["children"] = ["c", "g"]
        swept = lines.sweep(self.given(records), "a")
        self.assertEqual([s["id"] for s in swept], ["c", "g", "b"])
        self.assertEqual(swept[2]["why"], ["anchor mornings/b1"])
        swept = lines.sweep(self.given(records), "c")
        self.assertEqual([(s["id"], s["why"]) for s in swept],
                         [("g", ["sibling"]), ("d", ["anchor evenings/b5"]),
                          ("f", ["anchor evenings/b5"])])

    def test_an_anchor_of_the_whole_tab_shares_with_every_anchor_on_it(self):
        swept = lines.sweep(self.given(), "f")
        self.assertEqual([(s["id"], s["why"]) for s in swept],
                         [("d", ["anchor evenings"]), ("c", ["anchor evenings/b5"])])

    def test_a_closed_line_and_the_answered_one_are_never_swept(self):
        swept = lines.sweep(self.given(), "b")
        self.assertEqual([s["id"] for s in swept], ["a"])

    def test_an_unknown_line_is_refused(self):
        self.assertIn("no line zz", self.refused(lines.sweep, self.given(), "zz"))

    def test_the_cli_needs_no_versions(self):
        self.given()
        done = run("lines.py", "sweep", self.d.root, "--answered", "a")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual([s["id"] for s in json.loads(done.stdout)["lines"]], ["c", "b"])


class CloseTest(Base):
    def test_a_line_closes_by_the_user_s_sentence_quoted(self):
        writes = lines.close(self.given(), "b", "That one is settled.", "answers/3.md", T)
        self.assertEqual(writes, [{
            "op": "update", "collection": "lines", "doc_id": "b", "if_version": 11,
            "data": {"state": "closed", "answered_by": "answers/3.md", "reopenable": True,
                     "closed_by": {"sentence": "That one is settled.", "answer": "answers/3.md"},
                     "proposed": None, "rank": None, "touched_at": T}}])

    def test_no_close_without_the_sentence(self):
        for sentence in (None, "", "   "):
            self.assertIn("closed only by the user's sentence",
                          self.refused(lines.close, self.given(), "b", sentence, "a.md", T))
        self.assertIn("--by-answer", self.refused(lines.close, self.given(), "b", "Yes.",
                                                  None, T))

    def test_a_line_not_open_is_not_closed(self):
        self.assertIn("e is closed, not open",
                      self.refused(lines.close, self.given(), "e", "Yes.", "a.md", T))

    def test_the_cli_refuses_without_the_sentence_and_prints_no_write(self):
        self.given()
        done = run("lines.py", "close", self.d.root, "b", "--by-answer", "answers/3.md",
                   "--at", T, "--versions", self.d.versions)
        self.assertEqual(done.returncode, 1)
        self.assertEqual(done.stdout, "")
        self.assertIn("REFUSED: a line is closed only by the user's sentence", done.stderr)

    def test_no_mode_but_close_writes_a_closed_state(self):
        """A prediction has no path to a close: only ``close`` writes the
        state, and it takes the sentence."""
        with open(os.path.join(HERE, "hypo", "lines.py")) as fh:
            text = fh.read()
        self.assertEqual(text.count("state=CLOSED"), 1)
        start = text.index("def close(")
        self.assertGreater(text.index("state=CLOSED"), start)
        self.assertLess(text.index("state=CLOSED"), text.index("def reopen("))

    def test_reopen_reverses_a_close(self):
        writes = lines.reopen(self.given(), "e", T)
        self.assertEqual(writes[0]["data"], {"state": "open", "closed_by": None,
                                             "answered_by": None, "reopenable": None,
                                             "rank": None, "touched_at": T})
        self.assertIn("not closed", self.refused(lines.reopen, self.given(), "a", T))
        records = standard()
        records[4]["reopenable"] = False
        self.assertIn("not reopenable", self.refused(lines.reopen, self.given(records), "e", T))

    def test_a_line_only_touched_stays_open_and_is_flagged(self):
        writes = lines.touch(self.given(), "b", "answers/3.md", T)
        self.assertEqual(writes[0]["data"], {"flags": {"touched": {
            "answer": "answers/3.md", "at": T}}, "touched_at": T})
        self.assertNotIn("state", writes[0]["data"])
        self.assertIn("not open", self.refused(lines.touch, self.given(), "e", "x", T))


class OrderTest(Base):
    SHARES = {"mornings": 0.5, "mornings/b1": 0.25, "evenings": 0.1}

    def test_the_weight_is_share_times_unblocks_over_cost(self):
        given = self.given()
        r = given.records
        # a: mornings/b1 0.25, its child c waiting on it, a question
        t = lines.terms(given, r["a"], self.SHARES)
        self.assertEqual((t.share, t.unblocks, t.cost, t.provisional), (0.25, 2, 1, None))
        self.assertAlmostEqual(t.weight, 0.5)
        # b: mornings/b1 and mornings (b2 has no share of its own), summed, and
        # no more than the tab's 0.5
        self.assertAlmostEqual(lines.weight(given, r["b"], self.SHARES), 0.5)
        self.assertAlmostEqual(lines.weight(given, r["c"], self.SHARES), 0.1)

    def test_several_anchors_are_summed_each_key_once(self):
        r = rec("x", anchors=[anchor("mornings", "b1"), anchor("evenings"),
                              anchor("evenings", "b9")])
        self.assertAlmostEqual(lines.share_of(r, self.SHARES), 0.35)
        r = rec("x", anchors=[anchor("mornings", "b7"), anchor("mornings", "b8")])
        self.assertAlmostEqual(lines.share_of(r, self.SHARES), 0.5)

    def test_a_tab_counts_no_more_than_its_own_share(self):
        r = rec("x", anchors=[anchor("mornings", "b1"), anchor("mornings")])
        self.assertAlmostEqual(lines.share_of(r, {"mornings": 0.5, "mornings/b1": 0.4}), 0.5)

    def test_pressure_is_kept_and_weighs_nothing(self):
        records = standard()
        records[1]["pressure"] = 4
        given = self.given(records)
        self.assertEqual(given.problems, [])
        self.assertAlmostEqual(lines.weight(given, given.records["b"], self.SHARES), 0.5)

    def test_unblocks_counts_each_live_line_waiting_directly_once(self):
        records = [rec("p", anchors=[anchor("evenings")], children=["k"], blocks=["k", "q"]),
                   rec("k", anchors=[anchor("evenings")], parent="p", children=["g"],
                       waits_on=["p"]),
                   rec("g", anchors=[anchor("evenings")], parent="k"),
                   rec("q", anchors=[anchor("evenings")]),
                   rec("w", anchors=[anchor("evenings")], waits_on=["p"]),
                   rec("z", state="closed", answered_by="answers/1.md", waits_on=["p"])]
        given = self.given(records)
        self.assertEqual(given.problems, [])
        # k (child, blocked and waiting), q (blocked), w (waiting); g is k's,
        # not p's, and z is closed
        self.assertEqual(lines.blocked(given, given.records["p"]), ["k", "q", "w"])
        self.assertEqual(lines.terms(given, given.records["p"], self.SHARES).unblocks, 4)
        self.assertEqual(lines.terms(given, given.records["q"], self.SHARES).unblocks, 1)

    def test_the_cost_by_kind_and_the_stated_scale(self):
        cases = [(rec("q"), 1), (rec("r", kind="review"), 1), (rec("w", kind="work"), 3),
                 (rec("w9", kind="work", cost=9), 9), (rec("w1", kind="work", cost=1), 1),
                 (rec("q3", cost=3), 3), (rec("s", kind="work", owed_by="session"), 1),
                 (rec("u", kind="work", owed_by="user"), 3)]
        for r, want in cases:
            self.assertEqual(lines.cost_of(r), want, r["id"])
        given = self.given([rec("cheap", kind="work", cost=1, opened="2030-01-03T00:00:00Z"),
                            rec("dear", kind="work", cost=9, opened="2030-01-01T00:00:00Z"),
                            rec("plain", kind="work", opened="2030-01-02T00:00:00Z")])
        self.assertEqual([l for l, _ in lines.ordered(given, {"t": 1.0})],
                         ["cheap", "plain", "dear"])

    def test_the_cost_and_the_owner_are_checked(self):
        found = every(lines.check({
            "a": rec("a", cost=2), "b": rec("b", cost=True), "c": rec("c", owed_by="team"),
            "d": rec("d", owed_by="session"),
            "e": rec("e", kind="work", owed_by="session", cost=3),
            "f": rec("f", kind="work", owed_by="session", state="put"),
            "g": rec("g", project=""), "h": rec("h", waits_on=["nowhere"]),
            "i": rec("i", waits_on=["i"])}))
        for words in ("a: cost is not one of 1, 3, 9", "b: cost is not one of 1, 3, 9",
                      "c: owed_by is not one of user, session",
                      "d: owed_by names the session on a line that is not work",
                      "e: cost is set on the session's work",
                      "f: state is put on the session's work",
                      "g: project is not a project's name",
                      "h: waits on nowhere, which is no line", "i: waits on itself"):
            self.assertTrue(any(p.startswith(words) for p in found), (words, found))

    def test_a_cycle_through_waits_on_is_a_fault(self):
        found = every(lines.check({"a": rec("a", blocks=["b"]), "b": rec("b", waits_on=["c"]),
                                   "c": rec("c", waits_on=["a"])}))
        # a holds up b; c holds up b; a holds up c: no cycle yet
        self.assertFalse(any("cycle" in p for p in found), found)
        found = every(lines.check({"a": rec("a", blocks=["b"]), "b": rec("b"),
                                   "c": rec("c", waits_on=["b"]), "d": rec("d", blocks=["a"],
                                                                           waits_on=["c"])}))
        self.assertIn("a cycle of blocks and waits_on: a -> b -> c -> d -> a", found)

    def test_a_line_with_no_anchor_takes_half_its_project_s_root_provisionally(self):
        given = self.given([rec("x", project="north"), rec("y", project="south"),
                            rec("z"), rec("v", project="nowhere")])
        r = given.records
        roots = {"north": 1.0}
        shares = {"south": 0.6, "evenings": 0.1}
        t = lines.terms(given, r["x"], shares, roots)
        self.assertEqual((t.share, t.provisional), (0.5, "no anchor"))
        # a project the shares key by its root's question id
        t = lines.terms(given, r["y"], shares, roots)
        self.assertAlmostEqual(t.share, 0.3)
        self.assertEqual(t.provisional, "no anchor")
        for lid in ("z", "v"):
            t = lines.terms(given, r[lid], shares, roots)
            self.assertEqual(t.share, 0.5)
            self.assertEqual(t.provisional,
                             "no anchor; no project the shares know, the whole root")

    def test_anchors_the_shares_do_not_key_count_as_none(self):
        given = self.given([rec("x", anchors=[anchor("elsewhere", "b1")], project="north")])
        t = lines.terms(given, given.records["x"], {"evenings": 0.1}, {"north": 0.8})
        self.assertAlmostEqual(t.share, 0.4)
        self.assertEqual(t.provisional, "no anchor the shares key")

    def test_with_no_shares_every_line_is_provisional_and_weighs_a_share_of_one(self):
        given = self.given()
        for lid in ("a", "b", "c", "f"):
            t = lines.terms(given, given.records[lid], {})
            self.assertEqual((t.share, t.provisional), (1.0, "no shares given"))
        # d put; a holds up c; then b, c by age; f has no opening time
        self.assertEqual([l for l, _ in lines.ordered(given, {})], ["d", "a", "b", "c", "f"])

    def test_put_first_then_heaviest_then_oldest_then_id(self):
        records = standard() + [rec("g", anchors=[anchor("evenings")], opened=None),
                                rec("h", anchors=[anchor("evenings")],
                                    opened="2029-01-01T00:00:00Z"),
                                rec("i", anchors=[anchor("evenings")], opened=None, rank=1)]
        records[1]["rank"] = 9  # a stored rank breaks no tie
        given = self.given(records)
        done = lines.order(given, self.SHARES, T)
        order = [l for l, _ in lines.ordered(given, self.SHARES)]
        # a and b weigh 0.5, a the older; c, f, g, h, i 0.1: h, c by age, then
        # those with no opening time by id
        self.assertEqual(order, ["d", "a", "b", "h", "c", "f", "g", "i"])
        self.assertEqual(done.queue, [{"kind": "question", "title": "Line %s" % l}
                                      for l in order[1:]])
        self.assertEqual([r["id"] for r in done.asks], order)
        self.assertEqual([r["rank"] for r in done.asks], list(range(1, 9)))

    def test_the_session_s_work_is_ordered_apart_and_never_queued(self):
        records = standard() + [
            rec("s1", kind="work", owed_by="session", anchors=[anchor("mornings")],
                blocks=["a", "b"]),
            rec("s2", kind="work", owed_by="session", anchors=[anchor("evenings")]),
            rec("u", kind="work", owed_by="user", anchors=[anchor("evenings")])]
        given = self.given(records)
        done = lines.order(given, self.SHARES, T)
        # s1 weighs 1.5, more than any ask, and still stands after them all; u,
        # the user's work, costs 3
        self.assertEqual([r["id"] for r in done.asks], ["d", "a", "b", "c", "f", "u"])
        self.assertEqual([r["id"] for r in done.session], ["s1", "s2"])
        self.assertEqual([(r["rank"], r["weight"], r["cost"]) for r in done.session],
                         [(7, 1.5, 1), (8, 0.1, 1)])
        self.assertNotIn("Line s1", [q["title"] for q in done.queue])
        self.assertEqual(done.queue[-2:], [{"kind": "question", "title": "Line f"},
                                           {"kind": "work", "title": "Line u"}])
        for w in done.writes:
            given.records[w["doc_id"]].update(w["data"])
        self.assertEqual([q["title"] for q in lines.queue(given)],
                         [q["title"] for q in done.queue])
        shown, _ = lines.chunk(given, self.SHARES, 9, T)
        self.assertNotIn("s1", [s["id"] for s in shown])
        self.assertNotIn("s2", [s["id"] for s in shown])

    def test_each_row_carries_the_weight_its_terms_and_the_mark(self):
        given = self.given(standard() + [rec("g", kind="work", project="north")])
        done = lines.order(given, self.SHARES, T, {"north": 1.0})
        rows = {r["id"]: r for r in done.asks}
        self.assertEqual(rows["g"], {
            "rank": 4, "id": "g", "kind": "work", "title": "Line g", "state": "open",
            "weight": round(0.5 / 3, 6), "share": 0.5, "unblocks": 1, "cost": 3,
            "provisional": True, "provisional_why": "no anchor",
            "opened_at": "2030-01-01T00:00:00Z"})
        self.assertFalse(rows["a"]["provisional"])
        self.assertIsNone(rows["a"]["provisional_why"])

    def test_only_a_changed_rank_is_written(self):
        writes = lines.order(self.given(), self.SHARES, T).writes
        # d 1, a 2, b 3, c 4, f 5 as stored; e, closed, gives its rank up
        self.assertEqual({w["doc_id"]: w["data"]["rank"] for w in writes}, {"e": None})
        writes = lines.order(self.given(), {"mornings/b2": 2.0, "mornings/b1": 0.25,
                                            "evenings": 0.1}, T).writes
        self.assertEqual({w["doc_id"]: w["data"]["rank"] for w in writes},
                         {"b": 2, "a": 3, "e": None})

    def test_a_rank_held_twice_is_mended_and_the_order_converges_over_split_batches(self):
        records = [rec("l%02d" % i, rank=i + 1, anchors=[anchor("t%d" % (i % 3))],
                       opened="2030-01-%02dT00:00:00Z" % (i + 1)) for i in range(12)]
        records[5]["rank"] = 3  # a rank held twice
        shares = {"t0": 0.5, "t1": 0.3, "t2": 0.2}
        store = {r["id"]: dict(r) for r in records}

        def run_order(limit=None):
            writes = lines.order(self.given(list(store.values())), shares, T).writes
            for w in writes[:limit]:
                store[w["doc_id"]].update(w["data"])
            return writes

        self.assertTrue(run_order(limit=4))  # one batch lands, the rest do not
        run_order()
        self.assertEqual(run_order(), [])
        ranks = sorted(r["rank"] for r in store.values())
        self.assertEqual(ranks, list(range(1, 13)))

    def test_a_reopened_line_waits_unranked_and_last(self):
        records = standard()
        records[4].update(state="open", closed_by=None, answered_by=None, rank=None)
        self.assertEqual(lines.queue(self.given(records))[-1]["title"], "Line e")

    def test_opened_at_is_read_as_a_time(self):
        early = rec("x", opened="2030-01-02")
        late = rec("y", opened="2030-01-01T23:00:00-02:00")  # 01:00 on the 2nd, UTC
        self.assertLess(lines._age(early), lines._age(late))

    def test_the_shares_listing_is_read_as_shares_py_prints_it(self):
        listing = "mornings   0.5000\nevenings   0.1000  pressure 2\n\n"
        self.assertEqual(lines.read_shares(listing), {"mornings": 0.5, "evenings": 0.1})
        self.assertEqual(lines.read_shares('{"t/b": 1}'), {"t/b": 1.0})
        self.assertRaises(lines.Refused, lines.read_shares, "not a listing at all")
        self.assertRaises(lines.Refused, lines.read_shares, '{"t": "x"}')
        self.assertRaises(lines.Refused, lines.read_shares, "[1, 2]")

    def test_the_cli_takes_shares_or_a_graph_and_prints_the_order_and_the_queue(self):
        self.given(standard() + [rec("s", kind="work", owed_by="session"),
                                 rec("n", project="ti-esti")])
        shares = self.d.file("shares.txt", "mornings  0.5000\nevenings  0.1000\n")
        out_file = os.path.join(self.d.root, "queue.json")
        argv = ["lines.py", "order", self.d.root, "--shares", shares, "--at", T,
                "--versions", self.d.versions, "--queue-out", out_file]
        done = run(*argv)
        self.assertEqual(done.returncode, 0, done.stderr)
        out = json.loads(done.stdout)
        self.assertEqual(set(out), {"order", "session_work", "queue", "writes"})
        self.assertEqual(len(out["queue"]), 5)
        self.assertEqual([r["id"] for r in out["session_work"]], ["s"])
        for r in out["order"]:
            self.assertTrue({"weight", "share", "unblocks", "cost", "provisional"} <= set(r))
        with open(out_file) as fh:
            self.assertEqual(json.load(fh), out["queue"])
        self.assertEqual(run(*argv).stdout, done.stdout)  # deterministic
        done = run("lines.py", "order", self.d.root, "--graph", fixture("valid"), "--at", T,
                   "--versions", self.d.versions)
        self.assertEqual(done.returncode, 0, done.stderr)
        rows = {r["id"]: r for r in json.loads(done.stdout)["order"]}
        # n names the graph's one root by its question id: half of its one
        self.assertEqual((rows["n"]["share"], rows["n"]["provisional_why"]), (0.5, "no anchor"))

    def test_the_queue_as_the_ranks_stand(self):
        self.assertEqual([q["title"] for q in lines.queue(self.given())],
                         ["Line a", "Line b", "Line c", "Line f"])
        records = standard()
        records[5]["rank"] = 2  # f now shares a's rank: read as it stands
        self.assertEqual([q["title"] for q in lines.queue(self.given(records))],
                         ["Line a", "Line f", "Line b", "Line c"])


class OverrideTest(Base):
    SHARES = {"mornings": 0.5, "mornings/b1": 0.25, "evenings": 0.1}

    def test_an_override_records_the_line_taken_ahead_of_the_order_s_first(self):
        given = self.given()
        entry = lines.override(given, self.SHARES, "c", "  The evening  is near. ", T)
        self.assertEqual(entry, {
            "at": T, "head": "d", "ground": "The evening is near.",
            "taken": {"id": "c", "place": 4, "weight": 0.1, "share": 0.1, "unblocks": 1,
                      "cost": 1, "provisional": False},
            "over": {"id": "d", "place": 1, "weight": 0.1, "share": 0.1, "unblocks": 1,
                     "cost": 1, "provisional": False}})
        entry = lines.override(given, self.SHARES, "c", "Sooner.", T, over="b")
        self.assertEqual((entry["over"]["id"], entry["head"]), ("b", "d"))

    def test_the_refusals(self):
        given = self.given(standard() + [rec("s", kind="work", owed_by="session")])
        self.assertIn("give --ground", self.refused(lines.override, given, self.SHARES,
                                                    "c", " ", T))
        self.assertIn("a few words", self.refused(lines.override, given, self.SHARES, "c",
                                                  " ".join(["word"] * 26), T))
        self.assertIn("first by the order already",
                      self.refused(lines.override, given, self.SHARES, "d", "G.", T))
        self.assertIn("stands after c", self.refused(lines.override, given, self.SHARES,
                                                     "c", "G.", T, over="f"))
        self.assertIn("e is closed", self.refused(lines.override, given, self.SHARES,
                                                  "e", "G.", T))
        self.assertIn("never holds the user's card",
                      self.refused(lines.override, given, self.SHARES, "s", "G.", T))
        self.assertIn("not an ask", self.refused(lines.override, given, self.SHARES, "c",
                                                 "G.", T, over="s"))
        self.assertIn("no line zz", self.refused(lines.override, given, self.SHARES, "zz",
                                                 "G.", T))
        self.assertIn("--at", self.refused(lines.override, given, self.SHARES, "c", "G.",
                                           "yesterday"))

    def test_the_cli_appends_beside_the_records_and_writes_no_store(self):
        scratch = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, scratch, ignore_errors=True)
        d = Dir(self, standard())
        records = os.path.join(scratch, "lines")
        shutil.copytree(d.root, records)
        shares = d.file("shares.json", self.SHARES)
        log = os.path.join(scratch, "lines-overrides.jsonl")
        done = run("lines.py", "override", records, "--taken", "c", "--ground", "Sooner.",
                   "--shares", shares, "--at", T)
        self.assertEqual(done.returncode, 0, done.stderr)
        out = json.loads(done.stdout)
        self.assertEqual(out["log"], log)
        self.assertNotIn("writes", out)
        with open(log) as fh:
            first = fh.read()
        done = run("lines.py", "override", records, "--taken", "f", "--ground", "Later.",
                   "--shares", shares, "--at", T1)
        self.assertEqual(done.returncode, 0, done.stderr)
        with open(log) as fh:
            both = fh.read()
        self.assertTrue(both.startswith(first))
        self.assertEqual([json.loads(x)["taken"]["id"] for x in both.splitlines()], ["c", "f"])
        done = run("lines.py", "override", records, "--taken", "c", "--at", T)
        self.assertEqual(done.returncode, 1)
        self.assertIn("REFUSED: an override keeps the user's ground", done.stderr)
        with open(log) as fh:
            self.assertEqual(fh.read(), both)
        other = os.path.join(scratch, "elsewhere.jsonl")
        done = run("lines.py", "override", records, "--taken", "c", "--ground", "G.",
                   "--log", other, "--at", T)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertTrue(os.path.exists(other))

    def test_the_overrides_change_no_weight(self):
        given = self.given()
        before = lines.order(given, self.SHARES, T)
        log = os.path.join(self.d.root, "log.jsonl")
        lines.append_override(log, lines.override(given, self.SHARES, "c", "G.", T))
        self.assertEqual(lines.order(self.d.lines(), self.SHARES, T), before)


def side(lid, share, unblocks=1, cost=1, provisional=False):
    return {"id": lid, "share": share, "unblocks": unblocks, "cost": cost,
            "weight": share * unblocks / cost, "provisional": provisional}


class ReportTest(Base):
    def test_the_term_each_override_most_contradicts(self):
        self.assertEqual(lines.contradicted({"taken": side("x", 0.1), "over": side("y", 0.4)}),
                         ["share"])
        self.assertEqual(lines.contradicted({"taken": side("x", 0.4, cost=9),
                                             "over": side("y", 0.2)}), ["cost"])
        self.assertEqual(lines.contradicted({"taken": side("x", 0.2, unblocks=1),
                                             "over": side("y", 0.1, unblocks=3)}),
                         ["unblocks"])
        # the worst by ratio: share a half, cost a third
        self.assertEqual(lines.contradicted({"taken": side("x", 0.1, cost=3),
                                             "over": side("y", 0.2)}), ["cost"])
        self.assertEqual(lines.contradicted({"taken": side("x", 0.1, cost=3),
                                             "over": side("y", 0.3)}), ["share", "cost"])
        self.assertEqual(lines.contradicted({"taken": side("x", 0.2), "over": side("y", 0.2)}),
                         [])

    def test_the_report_reads_the_log_against_the_order(self):
        entries = [
            {"at": T, "taken": side("x", 0.1), "over": side("y", 0.4), "ground": "One."},
            {"at": T1, "taken": side("x", 0.1, provisional=True), "over": side("z", 0.3),
             "ground": "Two."},
            {"at": "2030-02-03T00:00:00Z", "taken": side("w", 0.4, cost=9),
             "over": side("y", 0.2), "ground": "Three."}]
        got = lines.report(entries)
        self.assertEqual(got["overrides"], 3)
        self.assertEqual((got["first"], got["last"]), (T, T1))
        self.assertEqual(got["taken"], {"x": 2, "w": 1})
        self.assertEqual(got["passed_over"], {"y": 2, "z": 1})
        self.assertEqual(got["contradicts"], {"share": 2, "unblocks": 0, "cost": 1, "none": 0})
        self.assertEqual(got["most_contradicted"], ["share"])
        self.assertEqual(got["on_a_provisional_share"], 1)
        self.assertEqual([e["contradicts"] for e in got["entries"]],
                         [["share"], ["share"], ["cost"]])
        empty = lines.report([])
        self.assertEqual((empty["overrides"], empty["most_contradicted"]), (0, []))

    def test_the_log_is_read_whole_or_refused(self):
        d = Dir(self, standard())
        self.assertEqual(lines.read_overrides(os.path.join(d.root, "none.jsonl")), [])
        bad = d.file("bad.jsonl", '{"taken": {"id": "x"}, "over": {"id": "y"}}\nnot json\n')
        self.assertRaises(lines.Refused, lines.read_overrides, bad)
        bad = d.file("odd.jsonl", '{"taken": 1}\n')
        self.assertRaises(lines.Refused, lines.read_overrides, bad)

    def test_the_cli_reports_what_the_cli_logged(self):
        self.given()
        shares = self.d.file("shares.json", OverrideTest.SHARES)
        log = os.path.join(self.d.root, "o.jsonl")
        for taken in ("c", "f"):
            done = run("lines.py", "override", self.d.root, "--taken", taken, "--over",
                       "a", "--ground", "G.", "--shares", shares, "--log", log, "--at", T)
            self.assertEqual(done.returncode, 0, done.stderr)
        done = run("lines.py", "report", self.d.root, "--log", log)
        self.assertEqual(done.returncode, 0, done.stderr)
        got = json.loads(done.stdout)
        self.assertEqual(got["overrides"], 2)
        self.assertEqual(got["passed_over"], {"a": 2})
        self.assertEqual(got["most_contradicted"], ["share"])


class LinkTest(Base):
    def test_both_sides_are_written(self):
        writes = lines.link(self.given(), "b", "f", T)
        self.assertEqual([(w["doc_id"], w["data"]) for w in writes],
                         [("b", {"children": ["f"], "touched_at": T}),
                          ("f", {"parent": "b", "touched_at": T})])

    def test_a_link_already_made_writes_nothing(self):
        self.assertEqual(lines.link(self.given(), "a", "c", T), [])

    def test_the_refusals(self):
        given = self.given()
        self.assertIn("not its own parent", self.refused(lines.link, given, "a", "a", T))
        self.assertIn("already has the parent a", self.refused(lines.link, given, "b", "c", T))
        self.assertIn("would close a cycle", self.refused(lines.link, given, "c", "a", T))
        self.assertIn("no line zz", self.refused(lines.link, given, "zz", "a", T))
        records = standard()
        records[1].update(state="dropped", decision={"word": "Drop.", "choice": "drop", "at": T})
        self.assertIn("stands for no children",
                      self.refused(lines.link, self.given(records), "b", "f", T))


class ChunkTest(Base):
    SHARES = {"mornings": 0.5, "evenings": 0.1}

    def test_the_far_end_of_the_queue_the_oldest_shown_first(self):
        shown, writes = lines.chunk(self.given(), self.SHARES, 2, T)
        # the queue a, b, c, f; its lower half c, f
        self.assertEqual([s["id"] for s in shown], ["c", "f"])
        self.assertEqual([w["data"]["review_count"] for w in writes], [1, 1])
        self.assertEqual({w["data"]["reviewed_at"] for w in writes}, {T})
        shown, _ = lines.chunk(self.given(), self.SHARES, 1, T)
        self.assertEqual([s["id"] for s in shown], ["f"])

    def test_never_from_the_head_of_the_queue(self):
        shown, _ = lines.chunk(self.given(), {}, 9, T)
        self.assertEqual(sorted(s["id"] for s in shown), ["c", "f"])

    def test_a_line_shown_enough_without_rising_is_proposed_for_dropping(self):
        records = standard()
        records[5].update(review_count=2, review_weight=0.1, review_since=0)
        shown, writes = lines.chunk(self.given(records), self.SHARES, 1, T)
        self.assertEqual(writes[0]["data"]["proposed"], "drop")
        self.assertEqual(writes[0]["data"]["review_count"], 3)

    def test_with_no_shares_nothing_is_proposed(self):
        records = standard()
        records[5].update(review_count=2, review_weight=1.0, review_since=0)
        _, writes = lines.chunk(self.given(records), {}, 1, T)
        self.assertNotIn("proposed", writes[0]["data"])

    def test_a_line_whose_weight_rose_counts_afresh(self):
        records = standard()
        records[5].update(review_count=2, review_weight=0.05, review_since=0)
        _, writes = lines.chunk(self.given(records), self.SHARES, 1, T)
        self.assertNotIn("proposed", writes[0]["data"])
        self.assertEqual(writes[0]["data"]["review_since"], 2)

    def test_a_line_shown_this_week_is_not_shown_again(self):
        records = standard()
        records[5]["reviewed_at"] = "2030-01-28T00:00:00Z"
        shown, _ = lines.chunk(self.given(records), self.SHARES, 1, T)
        self.assertEqual([s["id"] for s in shown], ["c"])
        shown, _ = lines.chunk(self.given(records), self.SHARES, 1, T, min_days=3)
        self.assertEqual([s["id"] for s in shown], ["f"])

    def test_the_threshold_is_given(self):
        _, writes = lines.chunk(self.given(), self.SHARES, 1, T, drop_after=1)
        self.assertEqual(writes[0]["data"]["proposed"], "drop")

    def test_a_proposed_line_waits_and_is_not_shown_again(self):
        records = standard()
        records[5]["proposed"] = "drop"
        shown, _ = lines.chunk(self.given(records), self.SHARES, 1, T)
        self.assertEqual([s["id"] for s in shown], ["c"])

    def test_nothing_is_shown_for_no_lines_asked(self):
        self.assertIn("--n", self.refused(lines.chunk, self.given(), self.SHARES, 0, T))
        self.assertIn("--drop-after", self.refused(lines.chunk, self.given(), self.SHARES,
                                                   1, T, drop_after=0))


class DecideTest(Base):
    def test_no_drop_and_no_merge_without_the_user_s_word(self):
        for choice in ("drop", "merge"):
            for word in (None, " "):
                self.assertIn("only at the user's word",
                              self.refused(lines.decide, self.given(), "b", choice, word, T,
                                           into="a"))

    def test_a_drop_records_the_word_and_flags_the_children_left(self):
        writes = lines.decide(self.given(), "a", "drop", "Let it go.", T)
        self.assertEqual(ids(writes), ["a", "c"])
        self.assertEqual(writes[0]["data"]["state"], "dropped")
        self.assertEqual(writes[0]["data"]["decision"],
                         {"choice": "drop", "word": "Let it go.", "at": T})
        self.assertEqual(writes[0]["data"]["rank"], None)
        self.assertEqual(list(writes[1]["data"]["flags"]), ["parent-withdrawn"])

    def test_a_merge_names_the_line_it_is_carried_on_by(self):
        writes = lines.decide(self.given(), "b", "merge", "Same as the other.", T, into="a")
        self.assertEqual(writes[0]["data"]["state"], "merged")
        self.assertEqual(writes[0]["data"]["answered_by"], "a")
        given = self.given()
        self.assertIn("--into", self.refused(lines.decide, given, "b", "merge", "W.", T))
        self.assertIn("not merged into itself",
                      self.refused(lines.decide, given, "b", "merge", "W.", T, into="b"))
        self.assertIn("e is closed",
                      self.refused(lines.decide, given, "b", "merge", "W.", T, into="e"))
        self.assertIn("for a merge only",
                      self.refused(lines.decide, given, "b", "drop", "W.", T, into="a"))

    def test_keep_clears_the_proposal_and_counts_afresh(self):
        records = standard()
        records[2].update(proposed="drop", review_count=3)
        writes = lines.decide(self.given(records), "c", "keep", None, T)
        self.assertEqual(writes[0]["data"], {
            "proposed": None, "decision": {"choice": "keep", "word": None, "at": T},
            "review_weight": None, "review_since": 3, "touched_at": T})

    def test_the_cli_refuses_a_drop_without_the_word(self):
        self.given()
        done = run("lines.py", "decide", self.d.root, "b", "drop", "--at", T,
                   "--versions", self.d.versions)
        self.assertEqual(done.returncode, 1)
        self.assertEqual(done.stdout, "")
        self.assertIn("REFUSED: a line is dropped only at the user's word", done.stderr)


class SkillLinesTest(Base):
    """Every ``tools/lines.py`` line the sitting's skill gives, its
    placeholders filled, run by the shell as written over an invented
    export."""

    def test_every_line_runs(self):
        import test_sit_skill as walk
        found = walk.lines(SKILL, "lines.py")
        modes = {each.split()[1] for each in found}
        self.assertEqual(modes, {"check", "moved", "sweep", "close", "touch-flag", "order",
                                 "queue", "link", "orphans", "chunk", "decide", "reopen",
                                 "unflag", "override", "report"})
        scratch = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, scratch, ignore_errors=True)
        speaker = os.path.join(scratch, "speaker")
        records = standard()
        records[2]["flags"] = {"ground-moved": {"anchors": [], "at": T}}
        records.append(rec("g"))
        d = Dir(self, records)
        shutil.copytree(d.root, os.path.join(speaker, "lines"))
        os.rename(os.path.join(speaker, "lines", "versions.json"),
                  os.path.join(speaker, "lines-versions.json"))
        os.makedirs(os.path.join(scratch, "outlines"))
        with open(os.path.join(scratch, "outlines", "evenings.xml"), "w") as fh:
            fh.write(OUTLINE)
        shutil.copy(fixture("valid"), os.path.join(scratch, "graph.json"))
        values = {"$SCRATCH": scratch, "<time>": T, "<line>": "b", "<answered line>": "a",
                  "<answer>": "answers/1.md", "<the user's sentence>": "That is settled.",
                  "<the user's word>": "Drop it.", "<parent>": "b", "<child>": "g",
                  "<closed line>": "e", "<flagged line>": "c",
                  "<keep|merge|drop>": "drop", "<other line>": "a",
                  "<taken line>": "c", "<the ground, in a few words>": "Sooner, for now."}
        for each in found:
            command = each.replace("tools/", HERE + "/", 1)
            for key, value in values.items():
                command = command.replace(key, value)
            left = walk.UNFILLED.search(command)
            self.assertIsNone(left, (left and left.group(0), command))
            done = subprocess.run(["bash", "-c", command], capture_output=True, text=True,
                                  timeout=60)
            self.assertEqual(done.returncode, 0, (command, done.stdout, done.stderr))
        with open(os.path.join(speaker, "queue.json")) as fh:
            self.assertTrue(json.load(fh))
        with open(os.path.join(speaker, "lines-overrides.jsonl")) as fh:
            self.assertEqual(json.loads(fh.readline())["taken"]["id"], "c")


if __name__ == "__main__":
    unittest.main()
