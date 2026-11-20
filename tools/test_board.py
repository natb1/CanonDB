"""The board's gate: every mode, every refusal, the cap, the address rule,
what each batch pins, and that a refusal leaves no batch to send."""

import importlib
import json
import os
import re
import shutil
import tempfile
import unittest

from hypo import board
from support import run

META = {"schema": 1, "cap_full": 2, "max_attempts": 3, "notebook": "doc:abc/project:p1",
        "claims": 4}
T0 = "2030-01-02T03:04:05Z"
T1 = "2030-01-02T03:10:00Z"


def job(sitting="s1", batch="b1", row="r1", kind="seal", tier="small", state="queued",
        waits_on=(), inputs=None, result=None, attempts=0, created=T0, updated=None, **more):
    out = {"id": "%s-%s-%s-%s" % (sitting, batch, row, kind), "sitting": sitting,
           "batch": batch, "row": row, "kind": kind, "tier": tier, "state": state,
           "waits_on": list(waits_on), "inputs": dict(inputs or {}),
           "result": dict(result or {}), "attempts": attempts, "created": created,
           "updated": updated or created}
    out.update(more)
    return out


def given(j):
    """A job as a jobs file gives it."""
    return {k: j[k] for k in board.GIVEN}


def tree(where):
    """Every file under a directory, with its text."""
    out = {}
    for root, _, files in os.walk(where):
        for name in files:
            with open(os.path.join(root, name), encoding="utf-8") as fh:
                out[os.path.join(root, name)] = fh.read()
    return out


def read_batch(path):
    """A batch as written, each entry's document read back from the file
    its ``file_path`` names into ``data``, as the store takes it."""
    with open(path, encoding="utf-8") as fh:
        entries = json.load(fh)
    out = []
    for w in entries:
        assert "data" not in w, w
        assert os.path.isabs(w["file_path"]), w
        with open(w["file_path"], encoding="utf-8") as fh:
            data = json.load(fh)
        out.append(dict({k: v for k, v in w.items() if k != "file_path"}, data=data))
    return out


class Export:
    """A store exported to a temporary directory, with its versions file.
    The meta document counts the jobs given unless ``meta`` says otherwise;
    meta/board is at version 1 and every job at version 5."""

    def __init__(self, test, meta=META, jobs=(), versions=None):
        self.dir = tempfile.mkdtemp()
        test.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.export = os.path.join(self.dir, "export")
        os.makedirs(self.export)
        self.versions = os.path.join(self.dir, "versions.json")
        known = {}
        if meta is not None:
            self.put("meta", "board", dict({"jobs": len(jobs)}, **meta))
            known["meta/board"] = 1
        for j in jobs:
            self.put("jobs", j["id"], j)
            known["jobs/" + j["id"]] = 5
        self.write_versions(known if versions is None else versions)

    def put(self, collection, doc_id, data):
        where = os.path.join(self.export, collection)
        os.makedirs(where, exist_ok=True)
        with open(os.path.join(where, doc_id + ".json"), "w", encoding="utf-8") as fh:
            json.dump(data, fh)

    def write_versions(self, versions):
        with open(self.versions, "w", encoding="utf-8") as fh:
            json.dump(versions, fh)

    def file(self, name, data):
        path = os.path.join(self.dir, name)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        return path

    @property
    def batch_path(self):
        return os.path.join(self.export, "batch.json")

    def run(self, mode, *args):
        """The tool over this export, as the usage line orders it: the mode,
        the export, then a job's id where the mode takes one."""
        return run("board.py", mode, self.export, *args, "--versions", self.versions)

    def batch(self, path=None):
        return read_batch(path or self.batch_path)

    def board(self):
        return board.load(self.export, self.versions)

    def apply(self, written):
        """A batch as the store would take it: each document set, its
        version one higher."""
        with open(self.versions, encoding="utf-8") as fh:
            versions = json.load(fh)
        for w in written:
            key = "%s/%s" % (w["collection"], w["doc_id"])
            self.assert_pin(versions, key, w)
            self.put(w["collection"], w["doc_id"], w["data"])
            versions[key] = versions.get(key, 0) + 1
        self.write_versions(versions)

    @staticmethod
    def assert_pin(versions, key, w):
        if "if_version" in w and versions.get(key) != w["if_version"]:
            raise AssertionError("the store would refuse %s: pinned %s, at %s"
                                 % (key, w["if_version"], versions.get(key)))
        if "if_version" not in w and key in versions:
            raise AssertionError("the store would refuse a create of %s" % key)


class AddressTest(unittest.TestCase):
    def test_an_address_is_short_and_has_no_space(self):
        for ok in ("a", "doc:abc/tab#s1.4", "x@y+z~w-v_u.t", "A" * 200, 0, 42, -1):
            self.assertTrue(board.is_address(ok), ok)
        for bad in ("", "two words", "tab\tid", "line\n", "A" * 201, "é", "a,b", "q?",
                    True, None, 1.5, float("nan"), [], {}):
            self.assertFalse(board.is_address(bad), bad)

    def test_a_sentence_run_together_is_an_address_all_the_same(self):
        """The rule is the specification's, and stops spaces, not words: the
        module says so, and this pins what it does."""
        self.assertTrue(board.is_address("the_user_said_that_the_thing_is_good"))
        self.assertIn("convention", board.__doc__)

    def test_a_fingerprint_is_lowercase_hex_of_sixteen_or_more(self):
        self.assertTrue(board.is_fingerprint("0123456789abcdef"))
        self.assertTrue(board.is_fingerprint("ab" * 200))
        self.assertFalse(board.is_fingerprint("0123456789abcde"))
        self.assertFalse(board.is_fingerprint("0123456789ABCDEF"))

    def test_inputs_take_addresses_and_nothing_else(self):
        self.assertEqual(board.inputs_problems({"tab": "doc:1/tab", "rev": 4}), [])
        self.assertEqual(len(board.inputs_problems({"case": "the user said so"})), 1)
        self.assertEqual(len(board.inputs_problems({"fp": "ab" * 120})), 1)
        self.assertEqual(len(board.inputs_problems({"nested": {"a": 1}})), 1)
        self.assertEqual(len(board.inputs_problems({"list": ["a"]})), 1)
        self.assertEqual(len(board.inputs_problems({"Bad": "a"})), 1)
        self.assertEqual(len(board.inputs_problems({"k" * 41: "a"})), 1)
        self.assertEqual(board.inputs_problems([]), ["inputs is not an object"])

    def test_a_result_also_takes_a_long_fingerprint(self):
        self.assertEqual(board.result_problems({"sealed": "ab" * 120, "rev": 9}), [])
        self.assertEqual(len(board.result_problems({"verdict": "yes, because"})), 1)

    def test_a_time_is_iso_utc(self):
        self.assertEqual(board.parse_time("2030-01-02T03:04:05Z").isoformat(),
                         "2030-01-02T03:04:05+00:00")
        for bad in ("2030-01-02", "2030-01-02T03:04:05", "2030-01-02T03:04:05+00:00Z",
                    "2030-01-02T03:04:05+01:00", "yesterday", "2030-01-02T03:04:05 Z", 5,
                    None):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                board.parse_time(bad)


class VerifyTest(unittest.TestCase):
    def verify(self, **kw):
        e = Export(self, **kw)
        return e, e.run("verify")

    def test_a_sound_board_verifies(self):
        a = job()
        b = job(row="r2", kind="grade", waits_on=[a["id"]])
        _, done = self.verify(jobs=[a, b])
        self.assertEqual(done.returncode, 0, done.stdout)
        self.assertEqual(done.stdout, "")
        self.assertIn("2 job(s)", done.stderr)

    def assert_problem(self, words, **kw):
        _, done = self.verify(**kw)
        self.assertEqual(done.returncode, 1)
        self.assertIn(words, done.stdout)
        return done

    def test_each_problem_of_a_job(self):
        cases = [
            (job(kind="poem"), "kind 'poem'"),
            (job(tier="huge"), "tier 'huge'"),
            (job(state="lost"), "state 'lost'"),
            (job(attempts=-1), "attempts"),
            (job(attempts=1.0), "attempts"),
            (job(created="2030-01-02 03:04"), "created is not an ISO 8601 UTC time"),
            (job(updated="yesterday"), "updated is not an ISO 8601 UTC time"),
            (job(inputs={"note": "a sentence here"}), "inputs.note is not an address"),
            (job(result={"why": "a sentence here"}), "result.why"),
            (job(colour="red"), "unknown field 'colour'"),
            (job(state="claimed"), "claimed by no one"),
            (job(state="failed"), "failed with no reason"),
            (job(reason="timeout"), "queued and carries a reason"),
            (job(state="failed", reason="bored"), "reason 'bored'"),
            (job(state="claimed", claimed_by="two words"), "claimed_by is not an address"),
            (job(waits_on=["nope"]), "which is not a job id"),
            (job(row="r" * 200), "longer than 200"),
        ]
        for j, words in cases:
            with self.subTest(words=words):
                self.assert_problem(words, jobs=[j])

    def test_one_wait_named_twice(self):
        a = job(row="r1")
        self.assert_problem("waits on s1-b1-r1-seal twice",
                            jobs=[a, job(row="r2", waits_on=[a["id"], a["id"]])])

    def test_a_job_that_is_not_an_object(self):
        e = Export(self)
        e.put("jobs", "s1-b1-r1-seal", ["a list"])
        e.write_versions({"meta/board": 1, "jobs/s1-b1-r1-seal": 1})
        done = e.run("verify")
        self.assertEqual(done.returncode, 1)
        self.assertIn("jobs/s1-b1-r1-seal is not an object", done.stdout)

    def test_a_missing_field(self):
        j = job()
        del j["updated"]
        self.assert_problem("has no updated", jobs=[j])

    def test_an_id_that_does_not_match_its_parts(self):
        j = job()
        j["row"] = "r9"
        self.assert_problem("does not match its sitting, batch, row and kind", jobs=[j])

    def test_a_file_that_holds_another_job(self):
        e = Export(self, meta=dict(META, jobs=1))
        e.put("jobs", "s1-b1-r2-seal", job())
        e.write_versions({"meta/board": 1, "jobs/s1-b1-r2-seal": 1})
        done = e.run("verify")
        self.assertEqual(done.returncode, 1)
        self.assertIn("holds the job 's1-b1-r1-seal'", done.stdout)

    def test_a_wait_on_a_job_not_on_the_board(self):
        self.assert_problem("waits on s1-b1-r0-seal, which is not on the board",
                            jobs=[job(waits_on=["s1-b1-r0-seal"])])

    def test_a_cycle(self):
        a = job(row="r1", waits_on=["s1-b1-r2-seal"])
        b = job(row="r2", waits_on=["s1-b1-r1-seal"])
        self.assert_problem("cycle", jobs=[a, b])
        self.assert_problem("cycle", jobs=[job(waits_on=["s1-b1-r1-seal"])])

    def test_the_versions_file_must_name_every_document(self):
        done = self.assert_problem("does not name jobs/s1-b1-r1-seal",
                                   jobs=[job()], versions={"meta/board": 1})
        self.assertEqual(done.stdout.count("\n"), 1)
        self.assert_problem("does not name meta/board", versions={})

    def test_a_version_with_no_document_is_a_partial_export(self):
        """The versions file names a job the export lost: the count it
        omits would undercount the cap."""
        a = job(row="r1", tier="full", state="claimed", claimed_by="x")
        e = Export(self, jobs=[a, job(row="r2")])
        os.unlink(os.path.join(e.export, "jobs", a["id"] + ".json"))
        done = e.run("verify")
        self.assertEqual(done.returncode, 1)
        self.assertIn("names jobs/s1-b1-r1-seal, which the export does not hold", done.stdout)
        self.assertIn("the export is partial", done.stdout)
        claim = e.run("claim", "s1-b1-r2-seal", "--by", "y", "--now", T1)
        self.assertEqual(claim.returncode, 1)

    def test_an_export_shorter_than_the_board_is_caught(self):
        """One page of a longer collection, its versions agreeing with it:
        only the board's own count can tell."""
        self.assert_problem("the board holds 3 job(s) and the export 1: the export is partial",
                            meta=dict(META, jobs=3), jobs=[job()])

    def test_a_version_that_is_not_a_whole_number_from_one(self):
        for bad in (0, "1", 1.5, True):
            with self.subTest(bad=bad):
                self.assert_problem("the version of meta/board",
                                    versions={"meta/board": bad})

    def test_a_bad_meta(self):
        self.assert_problem("cap_full", meta=dict(META, cap_full=0))
        self.assert_problem("schema", meta=dict(META, schema=2))
        self.assert_problem("notebook is not an address", meta=dict(META, notebook="a b"))
        self.assert_problem("unknown field 'x'", meta=dict(META, x=1))
        self.assert_problem("claims", meta=dict(META, claims=-1))
        self.assert_problem("jobs is not a whole number", meta=dict(META, jobs="1"))
        no_claims = dict(META)
        del no_claims["claims"]
        self.assert_problem("has no claims", meta=no_claims)

    def test_an_unknown_collection_or_document(self):
        e = Export(self)
        e.put("notes", "n1", {"a": 1})
        e.put("meta", "other", {})
        done = e.run("verify")
        self.assertIn("unknown collection notes", done.stdout)
        self.assertIn("unknown document meta/other", done.stdout)

    def test_unreadable_files_are_said_not_raised(self):
        e = Export(self)
        with open(os.path.join(e.export, "meta", "board.json"), "w") as fh:
            fh.write("{not json")
        os.unlink(e.versions)
        done = e.run("verify")
        self.assertEqual(done.returncode, 1)
        self.assertIn("meta/board cannot be read", done.stdout)
        self.assertIn("the versions file cannot be read", done.stdout)
        self.assertNotIn("Traceback", done.stdout + done.stderr)

    def test_no_export_directory(self):
        e = Export(self)
        shutil.rmtree(e.export)
        done = e.run("verify")
        self.assertEqual(done.returncode, 1)
        self.assertIn("no export directory", done.stdout)


class Refusals:
    """Asserting a refusal: exit 1, a REFUSED line, and no batch left."""

    def refused(self, e, done, words, out=None):
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        lines = done.stdout.splitlines()
        self.assertTrue(lines and all(l.startswith("REFUSED: ") for l in lines), lines)
        self.assertIn(words, done.stdout)
        self.assertFalse(os.path.exists(out or e.batch_path))

    def wrote(self, e, done):
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        return e.batch()

    def one(self, e, done):
        """The one write of a batch that changes one job, pinned to it."""
        written = self.wrote(e, done)
        self.assertEqual(len(written), 1, written)
        w = written[0]
        self.assertEqual((w["op"], w["collection"], w["if_version"]), ("set", "jobs", 5))
        return w["data"]


class InitTest(Refusals, unittest.TestCase):
    def test_it_creates_the_board(self):
        e = Export(self, meta=None)
        written = self.wrote(e, e.run("init", "--notebook", "doc:abc", "--cap", "1",
                                      "--max-attempts", "5"))
        self.assertEqual(written, [{"op": "set", "collection": "meta", "doc_id": "board",
                                    "data": {"schema": 1, "cap_full": 1, "max_attempts": 5,
                                             "notebook": "doc:abc", "claims": 0,
                                             "jobs": 0}}])

    def test_the_defaults(self):
        e = Export(self, meta=None)
        data = self.wrote(e, e.run("init", "--notebook", "doc:abc"))[0]["data"]
        self.assertEqual((data["cap_full"], data["max_attempts"]), (2, 3))

    def test_what_it_creates_verifies(self):
        e = Export(self, meta=None)
        e.apply(self.wrote(e, e.run("init", "--notebook", "doc:abc")))
        self.assertEqual(e.run("verify").returncode, 0)

    def test_it_is_refused_where_the_board_exists(self):
        e = Export(self)
        self.refused(e, e.run("init", "--notebook", "doc:abc"), "already exists")

    def test_it_is_refused_where_the_versions_name_a_board_the_export_lacks(self):
        e = Export(self, meta=None, versions={"meta/board": 3})
        done = e.run("init", "--notebook", "doc:abc")
        self.refused(e, done, "already exists")
        self.assertIn("which the export does not hold", done.stdout)

    def test_a_notebook_that_is_not_an_address_and_a_cap_of_none(self):
        e = Export(self, meta=None)
        self.refused(e, e.run("init", "--notebook", "my notebook"), "notebook")
        self.refused(e, e.run("init", "--notebook", "d", "--cap", "0"), "cap_full")
        self.refused(e, e.run("init", "--notebook", "d", "--max-attempts", "-1"),
                     "max_attempts")

    def test_out_names_where_the_batch_goes(self):
        e = Export(self, meta=None)
        out = os.path.join(e.dir, "new", "out")
        done = e.run("init", "--notebook", "d", "--out", out)
        self.assertEqual(done.returncode, 0, done.stdout)
        self.assertTrue(os.path.exists(os.path.join(out, "batch.json")))
        self.assertFalse(os.path.exists(e.batch_path))
        self.assertEqual(sorted(os.listdir(out)), ["batch.json", "write-1.json"])

    def test_each_entry_names_its_document_s_file_and_carries_no_words(self):
        """The session sends the entries as written; ArtifactData takes a
        ``file_path`` in a batch entry, so no document is retyped."""
        e = Export(self, meta=None)
        out = os.path.join(e.dir, "out")
        self.assertEqual(e.run("init", "--notebook", "d", "--out", out).returncode, 0)
        with open(os.path.join(out, "batch.json"), encoding="utf-8") as fh:
            raw = json.load(fh)
        self.assertEqual(raw, [{"op": "set", "collection": "meta", "doc_id": "board",
                                "file_path": os.path.join(out, "write-1.json")}])
        with open(raw[0]["file_path"], encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["notebook"], "d")

    def test_an_out_that_cannot_be_written_is_refused_not_raised(self):
        e = Export(self, meta=None)
        blocker = e.file("plain", {})
        done = e.run("init", "--notebook", "d", "--out", os.path.join(blocker, "out"))
        self.assertEqual(done.returncode, 1)
        self.assertIn("REFUSED: ", done.stdout)
        self.assertNotIn("Traceback", done.stdout + done.stderr)


class AddTest(Refusals, unittest.TestCase):
    def add(self, e, jobs, now=T1, *more):
        return e.run("add", "--jobs", e.file("jobs.json", jobs), "--now", now, *more)

    def test_jobs_are_queued_with_no_attempts_and_the_time_handed_in(self):
        e = Export(self)
        a = given(job())
        b = given(job(row="r2", kind="grade", tier="full", waits_on=[a["id"]],
                      inputs={"tab": "doc:1/tab#s1.4", "rev": 12}))
        written = self.wrote(e, self.add(e, [b, a]))
        self.assertEqual([w["doc_id"] for w in written[1:]], [a["id"], b["id"]])
        for w in written[1:]:
            self.assertEqual((w["op"], w["collection"]), ("set", "jobs"))
            self.assertNotIn("if_version", w)
            self.assertEqual((w["data"]["state"], w["data"]["attempts"], w["data"]["result"],
                              w["data"]["created"], w["data"]["updated"]),
                             ("queued", 0, {}, T1, T1))
        self.assertEqual(written[2]["data"]["inputs"], {"tab": "doc:1/tab#s1.4", "rev": 12})
        self.assertEqual(set(written[1]["data"]), set(board.FIELDS) - {"claimed_by", "reason"})

    def test_the_batch_pins_the_board_and_raises_its_count(self):
        held = job(row="r0")
        e = Export(self, jobs=[held])
        written = self.wrote(e, self.add(e, [given(job(row="r1")), given(job(row="r2"))]))
        self.assertEqual((written[0]["collection"], written[0]["doc_id"],
                          written[0]["if_version"], written[0]["data"]["jobs"]),
                         ("meta", "board", 1, 3))
        self.assertEqual(written[0]["data"]["claims"], META["claims"])

    def test_what_is_waited_on_comes_first(self):
        """In id order r1 would land before the r9 it waits on; a batch
        stopped part way would leave it waiting on nothing."""
        e = Export(self)
        r9 = given(job(row="r9"))
        r5 = given(job(row="r5", waits_on=["s1-b1-r9-seal"]))
        r1 = given(job(row="r1", waits_on=["s1-b1-r5-seal", "s1-b1-r9-seal"]))
        r3 = given(job(row="r3"))
        written = self.wrote(e, self.add(e, [r1, r3, r5, r9]))
        order = [w["doc_id"] for w in written[1:]]
        self.assertEqual(order, ["s1-b1-r9-seal", "s1-b1-r5-seal", "s1-b1-r1-seal",
                                 "s1-b1-r3-seal"])
        for i, jid in enumerate(order):
            for w in written[1 + i]["data"]["waits_on"]:
                self.assertIn(w, order[:i])

    def test_a_batch_holds_at_most_fifty_writes(self):
        e = Export(self)
        jobs = [given(job(row="r%d" % i)) for i in range(49)]
        self.assertEqual(len(self.wrote(e, self.add(e, jobs))), 50)
        e2 = Export(self)
        self.refused(e2, self.add(e2, jobs + [given(job(row="r99"))]),
                     "51 writes, over the 50 one batch takes")

    def test_waits_and_inputs_may_be_left_out(self):
        e = Export(self)
        a = {k: v for k, v in given(job()).items() if k not in ("waits_on", "inputs")}
        data = self.wrote(e, self.add(e, [a]))[1]["data"]
        self.assertEqual((data["waits_on"], data["inputs"]), ([], {}))

    def test_what_was_added_verifies_and_a_second_send_would_be_refused(self):
        e = Export(self)
        written = self.wrote(e, self.add(e, [given(job())]))
        e.apply(written)
        self.assertEqual(e.run("verify").returncode, 0, e.run("verify").stdout)
        with self.assertRaises(AssertionError):
            e.apply(written)

    def test_an_identical_re_add_writes_nothing(self):
        held = job(state="done", attempts=2, result={"rev": 3})
        e = Export(self, jobs=[held])
        done = self.add(e, [given(held)])
        self.assertEqual(done.returncode, 0, done.stdout)
        self.assertIn("nothing to write", done.stdout)
        self.assertFalse(os.path.exists(e.batch_path))

    def test_a_re_add_with_the_waits_in_another_order_is_the_same_job(self):
        a, b = job(row="r1"), job(row="r2")
        c = job(row="r3", waits_on=[a["id"], b["id"]])
        e = Export(self, jobs=[a, b, c])
        done = self.add(e, [dict(given(c), waits_on=[b["id"], a["id"]])])
        self.assertIn("nothing to write", done.stdout)

    def test_a_re_add_with_a_new_job_writes_only_the_new(self):
        held = job()
        e = Export(self, jobs=[held])
        new = given(job(row="r2", waits_on=[held["id"]]))
        written = self.wrote(e, self.add(e, [given(held), new]))
        self.assertEqual([w["doc_id"] for w in written], ["board", new["id"]])

    def test_a_re_add_with_other_fields_is_refused(self):
        held = job()
        e = Export(self, jobs=[held])
        self.refused(e, self.add(e, [dict(given(held), tier="full")]),
                     "on the board with other tier")

    def test_one_job_given_twice_differently_is_refused(self):
        e = Export(self)
        a = given(job())
        self.refused(e, self.add(e, [a, dict(a, tier="mid")]), "given twice")
        self.assertEqual(len(self.wrote(e, self.add(e, [a, dict(a)]))), 2)

    def test_a_wait_on_a_job_nowhere_is_refused(self):
        e = Export(self)
        self.refused(e, self.add(e, [given(job(waits_on=["s1-b1-r0-seal"]))]),
                     "neither on the board nor in the file")

    def test_a_cycle_is_refused(self):
        held = job(row="r1")
        e = Export(self, jobs=[held])
        a = given(job(row="r2", waits_on=["s1-b1-r3-seal"]))
        b = given(job(row="r3", waits_on=["s1-b1-r2-seal"]))
        self.refused(e, self.add(e, [a, b]), "cycle")
        self.refused(e, self.add(e, [given(job(row="r4", waits_on=["s1-b1-r4-seal"]))]),
                     "cycle")

    def test_an_id_that_does_not_match_its_parts_is_refused(self):
        e = Export(self)
        self.refused(e, self.add(e, [dict(given(job()), id="s1-b1-r2-seal")]),
                     "does not match")
        self.refused(e, self.add(e, [dict(given(job()), sitting="S-1")]), "sitting")
        self.refused(e, self.add(e, [dict(given(job()), id="nonsense")]),
                     "is not <sitting>-<batch>-<row>-<kind>")

    def test_an_id_longer_than_the_store_takes_is_refused(self):
        e = Export(self)
        self.refused(e, self.add(e, [given(job(row="r" * 300))]), "longer than 200")

    def test_what_the_gate_sets_may_not_be_given(self):
        e = Export(self)
        for key, value in (("state", "done"), ("attempts", 0), ("created", T0),
                           ("updated", T0), ("result", {}), ("claimed_by", "x"),
                           ("note", "x")):
            with self.subTest(key=key):
                self.refused(e, self.add(e, [dict(given(job()), **{key: value})]), repr(key))

    def test_prose_in_the_inputs_is_refused(self):
        e = Export(self)
        self.refused(e, self.add(e, [given(job(inputs={"question": "what is good"}))]),
                     "inputs.question is not an address")

    def test_a_bad_kind_tier_or_missing_field_is_refused(self):
        e = Export(self)
        self.refused(e, self.add(e, [given(job(tier="huge"))]), "tier")
        j = given(job())
        del j["kind"]
        self.refused(e, self.add(e, [j]), "has no kind")
        self.refused(e, self.add(e, ["s1-b1-r1-seal"]), "is not an object")
        self.refused(e, self.add(e, {"jobs": []}), "not a list")

    def test_a_time_that_is_not_one_is_refused(self):
        e = Export(self)
        for now in ("next tuesday", "yesterday", "2030-01-02"):
            with self.subTest(now=now):
                self.refused(e, self.add(e, [given(job())], now), "--now")

    def test_an_unreadable_jobs_file_is_refused(self):
        e = Export(self)
        self.refused(e, e.run("add", "--jobs", os.path.join(e.dir, "absent.json"),
                              "--now", T1), "jobs file cannot be read")

    def test_no_board_no_add(self):
        e = Export(self, meta=None)
        self.refused(e, self.add(e, [given(job())]), "run init first")

    def test_a_board_that_does_not_verify_takes_nothing(self):
        e = Export(self, jobs=[job(kind="poem")])
        self.refused(e, self.add(e, [given(job(row="r2"))]), "does not verify")


class NextTest(unittest.TestCase):
    def test_runnable_oldest_first_then_by_id(self):
        jobs = [job(row="r3", created="2030-01-01T00:00:00Z"),
                job(row="r2", created="2030-01-02T00:00:00Z"),
                job(row="r1", created="2030-01-02T00:00:00Z"),
                job(row="r4", state="done"),
                job(row="r5", waits_on=["s1-b1-r4-seal"], created="2030-01-03T00:00:00Z"),
                job(row="r6", waits_on=["s1-b1-r3-seal"]),
                job(row="r7", state="waiting"),
                job(row="r8", state="failed", reason="error"),
                job(row="r9", state="claimed", claimed_by="agent:x")]
        e = Export(self, jobs=jobs)
        done = e.run("next")
        self.assertEqual(done.returncode, 0, done.stdout)
        self.assertEqual(done.stdout.split(), ["s1-b1-r3-seal", "s1-b1-r1-seal",
                                               "s1-b1-r2-seal", "s1-b1-r5-seal"])
        self.assertEqual(done.stderr, "")
        self.assertFalse(os.path.exists(e.batch_path))

    def test_oldest_is_by_the_time_not_its_spelling(self):
        """A time with fractions spells later than one without and is not."""
        jobs = [job(row="r1", created="2030-01-02T00:00:00.500Z"),
                job(row="r2", created="2030-01-02T00:00:01Z")]
        self.assertEqual(Export(self, jobs=jobs).run("next").stdout.split(),
                         ["s1-b1-r1-seal", "s1-b1-r2-seal"])

    def test_the_cap_withholds_the_full_tier_and_says_so(self):
        jobs = [job(row="r1", tier="full", state="claimed", claimed_by="a"),
                job(row="r2", tier="full", state="claimed", claimed_by="b"),
                job(row="r3", tier="full"), job(row="r4", tier="mid")]
        e = Export(self, jobs=jobs)
        done = e.run("next")
        self.assertEqual(done.stdout.split(), ["s1-b1-r4-seal"])
        self.assertIn("withheld by the cap: s1-b1-r3-seal", done.stderr)
        payload = json.loads(e.run("next", "--json").stdout)
        self.assertEqual(payload, {"runnable": ["s1-b1-r4-seal"],
                                   "withheld": ["s1-b1-r3-seal"]})

    def test_under_the_cap_the_full_tier_runs(self):
        jobs = [job(row="r1", tier="full", state="claimed", claimed_by="a"),
                job(row="r2", tier="small", state="claimed", claimed_by="b"),
                job(row="r3", tier="full")]
        done = Export(self, jobs=jobs).run("next")
        self.assertEqual(done.stdout.split(), ["s1-b1-r3-seal"])
        self.assertEqual(done.stderr, "")

    def test_a_job_behind_a_failure_is_named(self):
        f = job(row="r1", state="failed", reason="error", attempts=3)
        b = job(row="r2", waits_on=[f["id"]])
        c = job(row="r3", waits_on=[b["id"]])
        done = Export(self, jobs=[f, b, c]).run("next")
        self.assertEqual(done.stdout, "")
        self.assertIn("blocked by a failed job: s1-b1-r2-seal", done.stderr)
        self.assertIn("blocked by a failed job: s1-b1-r3-seal", done.stderr)

    def test_no_board_or_one_that_does_not_verify_lists_nothing(self):
        done = Export(self, jobs=[job(waits_on=["s1-b1-r0-seal"])]).run("next")
        self.assertEqual(done.returncode, 1)
        self.assertIn("REFUSED: the export does not verify", done.stdout)
        done = Export(self, meta=None).run("next")
        self.assertEqual(done.returncode, 1)
        self.assertIn("run init first", done.stdout)


class TransitionTest(Refusals, unittest.TestCase):
    def test_claim_is_pinned_and_names_the_claimant(self):
        a = job()
        e = Export(self, jobs=[a])
        data = self.one(e, e.run("claim", a["id"], "--by", "agent:fetcher#3", "--now", T1))
        self.assertEqual((data["state"], data["claimed_by"], data["updated"], data["created"]),
                         ("claimed", "agent:fetcher#3", T1, T0))

    def test_a_full_claim_also_pins_the_board_and_moves_its_counter(self):
        a = job(tier="full")
        e = Export(self, jobs=[a])
        written = self.wrote(e, e.run("claim", a["id"], "--by", "x", "--now", T1))
        self.assertEqual([(w["collection"], w["doc_id"], w["if_version"]) for w in written],
                         [("meta", "board", 1), ("jobs", a["id"], 5)])
        self.assertEqual(written[0]["data"]["claims"], META["claims"] + 1)
        self.assertEqual({k: v for k, v in written[0]["data"].items() if k != "claims"},
                         {k: v for k, v in e.board().meta.items() if k != "claims"})

    def test_two_full_claims_from_one_export_cannot_both_land(self):
        """Each counted one claimed of a cap of two; the second pin fails
        on the board, and its batch with it."""
        jobs = [job(row="r1", tier="full", state="claimed", claimed_by="a"),
                job(row="r2", tier="full"), job(row="r3", tier="full")]
        e = Export(self, jobs=jobs)
        first = self.wrote(e, e.run("claim", "s1-b1-r2-seal", "--by", "b", "--now", T1))
        second = self.wrote(e, e.run("claim", "s1-b1-r3-seal", "--by", "c", "--now", T1))
        e.apply(first)
        with self.assertRaisesRegex(AssertionError, "meta/board"):
            e.apply(second)
        self.refused(e, e.run("claim", "s1-b1-r3-seal", "--by", "c", "--now", T1),
                     "the cap is reached")

    def test_a_claim_below_the_full_tier_leaves_the_board_alone(self):
        for tier in ("mid", "small"):
            with self.subTest(tier=tier):
                a = job(tier=tier)
                e = Export(self, jobs=[a])
                self.one(e, e.run("claim", a["id"], "--by", "x", "--now", T1))

    def test_claim_refuses_what_is_not_runnable(self):
        a = job(row="r1")
        b = job(row="r2", waits_on=[a["id"]])
        c = job(row="r3", state="done")
        w = job(row="r4", state="waiting")
        e = Export(self, jobs=[a, b, c, w])
        self.refused(e, e.run("claim", b["id"], "--by", "x", "--now", T1),
                     "waits on s1-b1-r1-seal, not done")
        self.refused(e, e.run("claim", c["id"], "--by", "x", "--now", T1), "done, not queued")
        self.refused(e, e.run("claim", w["id"], "--by", "x", "--now", T1),
                     "waiting, not queued")
        self.refused(e, e.run("claim", "s1-b1-r9-seal", "--by", "x", "--now", T1), "no job")
        self.refused(e, e.run("claim", a["id"], "--by", "two words", "--now", T1),
                     "not an address")
        self.refused(e, e.run("claim", a["id"], "--by", "x", "--now", "yesterday"), "--now")

    def test_claim_refuses_the_full_tier_at_the_cap(self):
        jobs = [job(row="r1", tier="full", state="claimed", claimed_by="a"),
                job(row="r2", tier="full", state="claimed", claimed_by="b"),
                job(row="r3", tier="full"), job(row="r4", tier="small")]
        e = Export(self, jobs=jobs)
        self.refused(e, e.run("claim", "s1-b1-r3-seal", "--by", "c", "--now", T1),
                     "the cap is reached: 2 of the full tier claimed, cap 2")
        self.one(e, e.run("claim", "s1-b1-r4-seal", "--by", "c", "--now", T1))

    def test_the_cap_is_the_board_s(self):
        jobs = [job(row="r1", tier="full", state="claimed", claimed_by="a"),
                job(row="r3", tier="full")]
        e = Export(self, meta=dict(META, cap_full=1), jobs=jobs)
        self.refused(e, e.run("claim", "s1-b1-r3-seal", "--by", "c", "--now", T1), "cap 1")

    def test_done_stores_the_result(self):
        a = job(state="claimed", claimed_by="x")
        e = Export(self, jobs=[a])
        result = {"sealed": "0123456789abcdef0123", "rev": 7, "tab": "doc:1/t#s1.2"}
        data = self.one(e, e.run("done", a["id"], "--by", "x", "--result",
                                 e.file("r.json", result), "--now", T1))
        self.assertEqual((data["state"], data["result"], data["claimed_by"]),
                         ("done", result, "x"))

    def test_done_and_fail_are_the_claimant_s(self):
        """A helper released for going quiet, whose job was claimed again,
        cannot finish it over the one now holding it."""
        a = job(state="claimed", claimed_by="helper2")
        e = Export(self, jobs=[a])
        self.refused(e, e.run("done", a["id"], "--by", "helper1", "--result",
                              e.file("r.json", {}), "--now", T1),
                     "claimed by helper2, not helper1")
        self.refused(e, e.run("fail", a["id"], "--by", "helper1", "--reason", "error",
                              "--now", T1), "claimed by helper2, not helper1")

    def test_done_refuses(self):
        a = job(state="claimed", claimed_by="x")
        q = job(row="r2")
        e = Export(self, jobs=[a, q])
        self.refused(e, e.run("done", a["id"], "--by", "x", "--result",
                              e.file("r.json", {"answer": "it is good"}), "--now", T1),
                     "result.answer")
        self.refused(e, e.run("done", q["id"], "--by", "x", "--result", e.file("r.json", {}),
                              "--now", T1), "queued, not claimed")
        self.refused(e, e.run("done", a["id"], "--by", "x", "--result",
                              e.file("r.json", ["a"]), "--now", T1), "result is not an object")
        self.refused(e, e.run("done", a["id"], "--by", "x", "--result",
                              os.path.join(e.dir, "none"), "--now", T1),
                     "result file cannot be read")

    def test_fail_names_a_reason(self):
        a = job(state="claimed", claimed_by="x")
        e = Export(self, jobs=[a])
        data = self.one(e, e.run("fail", a["id"], "--by", "x", "--reason", "refused",
                                 "--now", T1))
        self.assertEqual((data["state"], data["reason"]), ("failed", "refused"))

    def test_fail_refuses(self):
        a = job(state="claimed", claimed_by="x")
        q = job(row="r2")
        e = Export(self, jobs=[a, q])
        self.refused(e, e.run("fail", a["id"], "--by", "x", "--reason", "it broke",
                              "--now", T1), "reason 'it broke'")
        self.refused(e, e.run("fail", q["id"], "--by", "x", "--reason", "error",
                              "--now", T1), "not claimed")
        self.refused(e, e.run("fail", a["id"], "--by", "x", "--reason", "error",
                              "--now", "at noon"), "--now")

    def test_fail_takes_the_reason_helper(self):
        a = job(state="claimed", claimed_by="coordinator")
        e = Export(self, jobs=[a])
        data = self.one(e, e.run("fail", a["id"], "--by", "coordinator", "--reason",
                                 "helper", "--now", T1))
        self.assertEqual((data["state"], data["reason"]), ("failed", "helper"))

    def test_superseded_takes_a_queued_or_waiting_job_with_no_claim(self):
        """The close's reproduction: a seal and the grade that waits on it,
        both queued; the grade can never be claimed, and is failed all the
        same, attempts unchanged."""
        seal = job(row="r2", kind="seal", tier="full")
        grade = job(row="r2", kind="grade", tier="mid", waits_on=[seal["id"]])
        held = job(row="r3", kind="turn", tier="full", state="waiting")
        e = Export(self, jobs=[seal, grade, held])
        self.refused(e, e.run("claim", grade["id"], "--by", "s1", "--now", T1),
                     "not done")
        for j in (grade, seal, held):
            with self.subTest(job=j["id"]):
                data = self.one(e, e.run("fail", j["id"], "--by", "s1", "--reason",
                                         "superseded", "--now", T1))
                self.assertEqual((data["state"], data["reason"], data["attempts"]),
                                 ("failed", "superseded", 0))
                self.assertNotIn("claimed_by", data)
        e.apply(self.wrote(e, e.run("fail", grade["id"], "--by", "s1", "--reason",
                                    "superseded", "--now", T1)))
        self.assertEqual(e.run("verify").stdout, "")

    def test_superseded_does_not_pass_the_cap_or_a_claim(self):
        """With the cap reached a queued full job is still superseded; a job
        claimed by another is not."""
        busy = [job(row="r%d" % i, tier="full", state="claimed", claimed_by="x")
                for i in (1, 2)]
        q = job(row="r3", tier="full")
        e = Export(self, jobs=busy + [q])
        self.assertEqual(self.one(e, e.run("fail", q["id"], "--by", "s1", "--reason",
                                           "superseded", "--now", T1))["state"], "failed")
        self.refused(e, e.run("fail", busy[0]["id"], "--by", "s1", "--reason", "superseded",
                              "--now", T1), "claimed by x, not s1")

    def test_other_reasons_still_need_the_claim(self):
        q = job()
        w = job(row="r2", state="waiting")
        e = Export(self, jobs=[q, w])
        for reason in ("refused", "error", "timeout", "helper"):
            for j in (q, w):
                with self.subTest(reason=reason, job=j["id"]):
                    self.refused(e, e.run("fail", j["id"], "--by", "s1", "--reason", reason,
                                          "--now", T1), "not claimed")
        self.refused(e, e.run("fail", q["id"], "--by", "a b", "--reason", "superseded",
                              "--now", T1), "not an address")
        d = job(row="r3", state="done")
        e = Export(self, jobs=[d])
        self.refused(e, e.run("fail", d["id"], "--by", "s1", "--reason", "superseded",
                              "--now", T1), "done, not claimed")

    def test_retry_queues_again_with_one_more_attempt(self):
        a = job(state="failed", reason="error", claimed_by="x", attempts=1)
        e = Export(self, jobs=[a])
        data = self.one(e, e.run("retry", a["id"], "--now", T1))
        self.assertEqual((data["state"], data["attempts"]), ("queued", 2))
        self.assertNotIn("reason", data)
        self.assertNotIn("claimed_by", data)

    def test_retry_refuses_at_the_limit_and_off_failed(self):
        a = job(state="failed", reason="error", attempts=3)
        q = job(row="r2")
        e = Export(self, jobs=[a, q])
        self.refused(e, e.run("retry", a["id"], "--now", T1), "at the limit of 3 attempts")
        self.refused(e, e.run("retry", q["id"], "--now", T1), "queued, not failed")

    def test_wait_and_resume(self):
        q = job()
        w = job(row="r2", state="waiting")
        e = Export(self, jobs=[q, w])
        self.assertEqual(self.one(e, e.run("wait", q["id"], "--now", T1))["state"], "waiting")
        self.assertEqual(self.one(e, e.run("resume", w["id"], "--now", T1))["state"], "queued")
        self.refused(e, e.run("wait", w["id"], "--now", T1), "waiting, not queued")
        self.refused(e, e.run("resume", q["id"], "--now", T1), "queued, not waiting")

    def test_what_a_transition_writes_verifies(self):
        """Claim, fail, retry, release and done each leave a board the
        schema accepts, each pinned to what the step before left."""
        a = job(tier="full")
        e = Export(self, jobs=[a])
        steps = [("claim", a["id"], "--by", "x", "--now", T1),
                 ("fail", a["id"], "--by", "x", "--reason", "timeout", "--now", T1),
                 ("retry", a["id"], "--now", T1),
                 ("claim", a["id"], "--by", "x", "--now", T1),
                 ("release", "--older-than", "0", "--now", "2030-01-03T00:00:00Z"),
                 ("claim", a["id"], "--by", "y", "--now", T1),
                 ("done", a["id"], "--by", "y", "--result", e.file("r.json", {"rev": 2}),
                  "--now", T1)]
        for step in steps:
            with self.subTest(step=step[0]):
                e.apply(self.wrote(e, e.run(*step)))
                self.assertEqual(e.run("verify").stdout, "")
        final = e.board()
        self.assertEqual((final.jobs[a["id"]]["state"], final.jobs[a["id"]]["attempts"],
                          final.jobs[a["id"]]["claimed_by"]), ("done", 2, "y"))
        self.assertEqual(final.meta["claims"], META["claims"] + 3)


class ReleaseTest(Refusals, unittest.TestCase):
    def test_a_quiet_claim_goes_back_to_the_queue(self):
        stale = job(row="r1", state="claimed", claimed_by="x", updated="2030-01-02T03:00:00Z")
        fresh = job(row="r2", state="claimed", claimed_by="y", updated="2030-01-02T03:09:00Z")
        e = Export(self, jobs=[stale, fresh])
        written = self.wrote(e, e.run("release", "--older-than", "300", "--now", T1))
        self.assertEqual([w["doc_id"] for w in written], [stale["id"]])
        data = written[0]["data"]
        self.assertEqual((data["state"], data["attempts"], data["updated"]), ("queued", 1, T1))
        self.assertNotIn("claimed_by", data)
        self.assertEqual(written[0]["if_version"], 5)

    def test_several_in_one_batch_longest_quiet_first(self):
        jobs = [job(row="r1", state="claimed", claimed_by="x", updated="2030-01-02T02:00:00Z"),
                job(row="r2", state="claimed", claimed_by="x", updated="2030-01-02T01:00:00Z",
                    attempts=3),
                job(row="r3", state="claimed", claimed_by="x", updated="2030-01-02T03:20:00Z")]
        e = Export(self, jobs=jobs)
        written = self.wrote(e, e.run("release", "--older-than", "60", "--now", T1))
        self.assertEqual([(w["doc_id"], w["data"]["state"]) for w in written],
                         [("s1-b1-r2-seal", "failed"), ("s1-b1-r1-seal", "queued")])

    def test_a_claim_updated_after_now_is_not_quiet(self):
        e = Export(self, jobs=[job(state="claimed", claimed_by="x",
                                   updated="2030-01-02T04:00:00Z")])
        self.assertIn("nothing to write",
                      e.run("release", "--older-than", "0", "--now", T1).stdout)

    def test_a_batch_takes_fifty_and_says_how_many_are_left(self):
        jobs = [job(row="r%d" % i, state="claimed", claimed_by="x") for i in range(53)]
        e = Export(self, jobs=jobs)
        done = e.run("release", "--older-than", "1", "--now", T1)
        self.assertEqual(len(self.wrote(e, done)), 50)
        self.assertIn("3 more quiet claim(s)", done.stderr)

    def test_at_the_limit_it_fails_with_timeout(self):
        stale = job(state="claimed", claimed_by="x", attempts=3,
                    updated="2030-01-02T03:00:00Z")
        e = Export(self, jobs=[stale])
        data = self.wrote(e, e.run("release", "--older-than", "60", "--now", T1))[0]["data"]
        self.assertEqual((data["state"], data["reason"], data["attempts"]),
                         ("failed", "timeout", 3))

    def test_exactly_the_limit_of_seconds_is_not_more(self):
        c = job(state="claimed", claimed_by="x", updated="2030-01-02T03:05:00Z")
        e = Export(self, jobs=[c])
        done = e.run("release", "--older-than", "300", "--now", T1)
        self.assertIn("nothing to write", done.stdout)
        self.assertFalse(os.path.exists(e.batch_path))
        self.assertEqual(len(self.wrote(e, e.run("release", "--older-than", "299",
                                                 "--now", T1))), 1)

    def test_only_claimed_jobs_are_released(self):
        e = Export(self, jobs=[job(row="r1"), job(row="r2", state="waiting"),
                               job(row="r3", state="done")])
        self.assertIn("nothing to write",
                      e.run("release", "--older-than", "0", "--now", T1).stdout)

    def test_what_it_cannot_take_is_refused(self):
        e = Export(self, jobs=[job(state="claimed", claimed_by="x")])
        self.refused(e, e.run("release", "--older-than", "1", "--now", "2030-01-02T03:04:05"),
                     "ending in Z")
        self.refused(e, e.run("release", "--older-than", "1", "--now", "tomorrow"), "--now")
        self.refused(e, e.run("release", "--older-than", "-1", "--now", T1), "--older-than")

    def test_a_stored_time_that_is_not_one_stops_the_board_not_just_release(self):
        """It can only come from a write past the gate; verify names it."""
        e = Export(self, jobs=[job(state="claimed", claimed_by="x", updated="yesterday")])
        self.refused(e, e.run("release", "--older-than", "1", "--now", T1),
                     "updated is not an ISO 8601 UTC time")


class StatusTest(unittest.TestCase):
    def jobs(self):
        return [job(row="r1", kind="seal"),
                job(row="r2", kind="seal", state="failed", reason="refused", attempts=1),
                job(row="r3", kind="grade", state="waiting"),
                job(row="r4", kind="grade", state="done", attempts=2),
                job(row="r5", kind="record", state="claimed", claimed_by="x"),
                job(row="r6", kind="check", waits_on=["s1-b1-r2-seal"])]

    def test_counts_waits_blocks_and_fit(self):
        e = Export(self, jobs=self.jobs())
        payload = json.loads(e.run("status", "--json").stdout)
        self.assertEqual(payload["states"], {"queued": 2, "claimed": 1, "done": 1,
                                             "failed": 1, "waiting": 1})
        self.assertEqual(payload["kinds"], {"seal": 2, "grade": 2, "record": 1, "check": 1})
        self.assertEqual(payload["waiting"], ["s1-b1-r3-grade"])
        self.assertEqual(payload["blocked"], ["s1-b1-r6-check"])
        self.assertEqual(payload["fit"], {"seal": {"failed": 1, "retried": 1},
                                          "grade": {"failed": 0, "retried": 1},
                                          "record": {"failed": 0, "retried": 0},
                                          "check": {"failed": 0, "retried": 0}})
        self.assertFalse(os.path.exists(e.batch_path))

    def test_a_superseded_job_is_no_measure_of_fit(self):
        """A close fails what is left superseded, a released claim among
        them with an attempt more; neither moves the fit."""
        jobs = [job(row="r1", kind="seal", state="failed", reason="superseded"),
                job(row="r2", kind="seal", state="failed", reason="superseded", attempts=1),
                job(row="r3", kind="seal", state="failed", reason="helper")]
        payload = json.loads(Export(self, jobs=jobs).run("status", "--json").stdout)
        self.assertEqual(payload["states"]["failed"], 3)
        self.assertEqual(payload["fit"], {"seal": {"failed": 1, "retried": 0}})

    def test_the_lines(self):
        done = Export(self, jobs=self.jobs()).run("status")
        self.assertEqual(done.returncode, 0, done.stdout)
        lines = done.stdout.splitlines()
        self.assertEqual(lines[0], "states: queued 2, claimed 1, done 1, failed 1, waiting 1")
        self.assertEqual(lines[1], "kinds: seal 2, grade 2, record 1, check 1")
        self.assertEqual(lines[2], "waiting on the principal: s1-b1-r3-grade")
        self.assertEqual(lines[3], "blocked by a failed job: s1-b1-r6-check")
        self.assertIn("fit seal: failed 1, retried 1", lines)

    def test_an_empty_board(self):
        done = Export(self).run("status")
        self.assertIn("kinds: none", done.stdout)
        self.assertIn("waiting on the principal: none", done.stdout)
        self.assertIn("blocked by a failed job: none", done.stdout)

    def test_no_board_or_one_that_does_not_verify(self):
        done = Export(self, meta=None).run("status")
        self.assertEqual(done.returncode, 1)
        self.assertIn("run init first", done.stdout)
        done = Export(self, jobs=[job(kind="poem")]).run("status")
        self.assertEqual(done.returncode, 1)
        self.assertIn("does not verify", done.stdout)


class StaleBatchTest(Refusals, unittest.TestCase):
    """A batch an earlier run left is never there to be sent for a later one."""

    def setUp(self):
        self.a = job(row="r1")
        self.e = Export(self, jobs=[self.a, job(row="r2", state="done")])
        self.out = os.path.join(self.e.dir, "out")
        done = self.e.run("claim", self.a["id"], "--by", "x", "--now", T1, "--out", self.out)
        self.assertEqual(done.returncode, 0, done.stdout)
        self.path = os.path.join(self.out, "batch.json")
        self.assertTrue(os.path.exists(self.path))

    def test_a_refusal_removes_it(self):
        done = self.e.run("fail", "s1-b1-r2-seal", "--by", "x", "--reason", "error",
                          "--now", T1, "--out", self.out)
        self.refused(self.e, done, "not claimed", out=self.path)

    def test_nothing_to_write_removes_it(self):
        done = self.e.run("release", "--older-than", "0", "--now", T1, "--out", self.out)
        self.assertIn("nothing to write", done.stdout)
        self.assertFalse(os.path.exists(self.path))

    def test_a_refusal_over_a_bad_export_removes_it(self):
        os.unlink(self.e.versions)
        done = self.e.run("wait", self.a["id"], "--now", T1, "--out", self.out)
        self.refused(self.e, done, "versions file", out=self.path)

    def test_a_new_batch_replaces_it_whole(self):
        done = self.e.run("wait", self.a["id"], "--now", T1, "--out", self.out)
        self.assertEqual(done.returncode, 0, done.stdout)
        self.assertEqual(read_batch(self.path)[0]["data"]["state"], "waiting")
        self.assertEqual(sorted(os.listdir(self.out)), ["batch.json", "write-1.json"])

    def test_a_refusal_takes_the_earlier_documents_away_too(self):
        with open(os.path.join(self.out, "write-7.json"), "w", encoding="utf-8") as fh:
            fh.write("{}")
        done = self.e.run("fail", "s1-b1-r2-seal", "--by", "x", "--reason", "error",
                          "--now", T1, "--out", self.out)
        self.refused(self.e, done, "not claimed", out=self.path)
        self.assertEqual(os.listdir(self.out), [])

    def test_the_reading_modes_leave_it(self):
        """They write nothing, and take no --out to clear."""
        for mode in ("next", "status", "verify"):
            with self.subTest(mode=mode):
                self.assertIn(self.e.run(mode).returncode, (0, 1))
        self.assertTrue(os.path.exists(self.path))


class UsageTest(unittest.TestCase):
    def test_the_export_stands_before_the_id_as_the_usage_line_says(self):
        e = Export(self, jobs=[job()])
        done = run("board.py", "claim", e.export, "s1-b1-r1-seal", "--versions", e.versions,
                   "--by", "x", "--now", T1)
        self.assertEqual(done.returncode, 0, done.stdout)
        tool = importlib.import_module("board")
        self.assertIn("<export dir> [ID]", tool.__doc__.splitlines()[0])
        self.assertIn("claim <dir> ID", tool.__doc__)

    def test_the_mode_table_is_in_the_help(self):
        done = run("board.py", "--help")
        self.assertEqual(done.returncode, 0)
        self.assertIn("release <dir> --older-than SECONDS", done.stdout)
        done = run("board.py", "claim", "--help")
        self.assertIn("the job's id", done.stdout)


class NoWriteOnRefusalTest(Refusals, unittest.TestCase):
    def test_a_refusal_leaves_an_out_directory_unmade(self):
        e = Export(self)
        out = os.path.join(e.dir, "out")
        done = e.run("claim", "s1-b1-r1-seal", "--by", "x", "--now", T1, "--out", out)
        self.refused(e, done, "no job")
        self.assertFalse(os.path.exists(out))

    def test_the_export_is_left_as_it_was(self):
        a = job(state="failed", reason="error", attempts=3)
        e = Export(self, jobs=[a])
        before = tree(e.dir)
        self.refused(e, e.run("retry", a["id"], "--now", T1), "limit")
        self.assertEqual(before, tree(e.dir))


class PageTest(unittest.TestCase):
    """The page, read as text: there is no browser here, so this holds the
    lines that keep it to showing ids and codes and to saying what it knows."""

    @classmethod
    def setUpClass(cls):
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "web",
                            "board.html")
        with open(path, encoding="utf-8") as fh:
            cls.page = fh.read()
        cls.script = cls.page[cls.page.index("<script>"):cls.page.index("</script>")]

    def js_list(self, name):
        found = re.search(r"var %s = \[([^\]]*)\];" % name, self.script)
        return tuple(re.findall(r'"([^"]+)"', found.group(1)))

    def test_its_codes_are_the_gate_s(self):
        self.assertEqual(self.js_list("STATES"), board.STATES)
        self.assertEqual(self.js_list("KINDS"), board.KINDS)
        self.assertEqual(self.js_list("TIERS"), board.TIERS)

    def test_it_shows_an_address_or_a_question_mark(self):
        found = re.search(r"var ADDRESS = /\^(.*)\$/;", self.script).group(1)
        self.assertEqual(found.replace("\\/", "/"), board.ADDRESS.pattern)
        self.assertIn('ADDRESS.test(v) ? v : "?"', self.script)
        self.assertNotIn("innerHTML", self.page)

    def test_it_loads_nothing_from_elsewhere_and_writes_nothing(self):
        self.assertNotIn("https://", self.page)
        self.assertNotIn("<link", self.page)
        for call in (".set(", ".update(", ".delete(", ".add(", ".acquire("):
            self.assertNotIn(call, self.script)

    def test_a_dead_listener_is_not_called_live_again(self):
        settle = self.script[self.script.index("function settle()"):]
        self.assertIn("if (dead ||", settle.split("\n")[1])
        self.assertIn("dead = true;", self.script[self.script.index("function stopped("):])

    def test_nothing_is_stated_before_the_board_answers(self):
        self.assertIn('id="claimed-empty" hidden', self.page)
        self.assertIn('id="failed-empty" hidden', self.page)
        self.assertIn('loaded ? counts[s] : "–"', self.script)
        self.assertIn('"unknown state"', self.script)

    def test_its_title_is_a_name(self):
        title = re.search(r"<title>(.*)</title>", self.page).group(1)
        self.assertTrue(2 <= len(title.split()) <= 4, title)

if __name__ == "__main__":
    unittest.main()
