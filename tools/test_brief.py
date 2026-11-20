"""The brief and the neighbourhood, the convention checks on a text leaving,
and the work in hand: over an invented garden's graph."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from support import fixture
from hypo import brief, inhand, model, outgoing

HERE = os.path.dirname(os.path.abspath(__file__))
GRAPH = fixture("brief")
T = "2030-01-02T03:04:05Z"


def load():
    return model.load(GRAPH)


def sha():
    return brief.fingerprint(GRAPH)


def every_sentence(graph):
    """Every sentence and part the graph holds, as the tool may quote it."""
    out = set()
    for q in graph.questions:
        out.add(" ".join(q.question.split()))
        for t in q.theses:
            out.add(" ".join(t.title.split()))
            out.update(brief.sentences(t.text))
            for term in t.terms:
                out.update(" ".join(a.split()) for a in term.anchors)
            for e in t.traditions:
                out.add(" ".join((e.note + " " + e.counter).split()))
        for d in q.definitions:
            out.update(brief.sentences(d.body))
        if q.hinge:
            out.update(brief.sentences(q.hinge.end) + brief.sentences(q.hinge.method))
    return out


class SentencesTest(unittest.TestCase):
    def test_whole_sentences_in_order(self):
        self.assertEqual(brief.sentences("One. Two? \"Three.\" Four\nruns on.\n\n- An item.\n- Another."),
                         ["One.", "Two?", "\"Three.\"", "Four runs on.", "- An item.", "- Another."])

    def test_a_stop_before_a_small_letter_is_no_break(self):
        self.assertEqual(brief.sentences("Read e.g. the sheet. Then go."),
                         ["Read e.g. the sheet.", "Then go."])

    def test_an_abbreviation_or_an_initial_is_no_break(self):
        self.assertEqual(brief.sentences("See No. 5 here. Ask J. Smith. Done."),
                         ["See No. 5 here.", "Ask J. Smith.", "Done."])


class StandingTest(unittest.TestCase):
    def setUp(self):
        self.graph = load()

    def test_header_conventions_ends_glossary(self):
        out = brief.standing(self.graph, sha(), "all", T, None, ["wording"]).text
        lines = out.splitlines()
        self.assertEqual(lines[0], "# Brief: standing (side all)")
        self.assertEqual(lines[2], brief.RECORD)
        self.assertEqual(brief.stamp_of(out), {"graph": sha(), "line": [], "at": T,
                                               "tool": brief.TOOL})
        for want in ("## Conventions", "[wording/a1.s1] The one the record is kept for is named the user.",
                     "[check:user-named]", "[check:masked]", "## Ends and methods",
                     "[garden/end.s1] end: that the beds feed the house through the year",
                     "## Glossary index", "[rotation/≡fallow.s1] ≡ fallow:"):
            self.assertIn(want, out)
        self.assertLess(out.index("## Conventions"), out.index("## Ends and methods"))

    def test_the_same_inputs_give_the_same_bytes(self):
        a = brief.standing(self.graph, sha(), "all", T, None, ["wording"])
        b = brief.standing(load(), sha(), "all", T, None, ["wording"])
        self.assertEqual(a.text, b.text)
        self.assertEqual(a.manifest, b.manifest)

    def test_open_lines_by_rank(self):
        lines = {"l2": {"id": "l2", "title": "Second line", "state": "open", "rank": 2},
                 "l1": {"id": "l1", "title": "First line", "state": "open", "rank": 1},
                 "l3": {"id": "l3", "title": "Closed", "state": "closed"}}
        out = brief.standing(self.graph, sha(), "all", T, lines, []).text
        self.assertLess(out.index("[lines/l1] First line"), out.index("[lines/l2] Second line"))
        self.assertNotIn("Closed", out)

    def test_the_ai_side_holds_nothing_of_the_user(self):
        out = brief.standing(self.graph, sha(), "ai", T, {"l1": {"id": "l1", "title": "A line",
                                                                 "state": "open"}},
                             ["wording"]).text
        self.assertIn("[planting/a1.h] A bed takes what the kitchen asks for.", out)
        for user in ("named the user", "feed the house", "fallow", "A line", "almanac"):
            self.assertNotIn(user, out)
        self.assertIn("[check:user-named]", out)

    def test_compaction_keeps_conventions_and_names_what_is_left_out(self):
        whole = brief.standing(self.graph, sha(), "all", T, None, ["wording"])
        small = brief.standing(self.graph, sha(), "all", T, None, ["wording"], limit=1100)
        self.assertLessEqual(len(small.text), 1100)
        self.assertIn("[wording/a1.s2]", small.text)
        self.assertIn("[check:masked]", small.text)
        self.assertTrue(small.manifest["left_out"] or small.manifest["kept_as_word_and_address"])
        named = set(small.manifest["included"]) | set(small.manifest["left_out"])
        self.assertTrue(set(whole.manifest["included"]) <= named)
        self.assertIn("named by id in the manifest", small.text)

    def test_an_entry_that_does_not_fit_keeps_its_word_and_address(self):
        whole = brief.standing(self.graph, sha(), "all", T, None, [])
        for limit in range(len(whole.text) - 1, 900, -10):
            out = brief.standing(self.graph, sha(), "all", T, None, [], limit=limit)
            if out.manifest["kept_as_word_and_address"]:
                base = out.manifest["kept_as_word_and_address"][0]
                self.assertIn("[%s] \u2261" % base, out.text)
                self.assertIn(base + ".s1", out.manifest["left_out"])
                return
        self.fail("no limit stubbed an entry")

    def test_conventions_over_the_ceiling_are_refused(self):
        with self.assertRaises(brief.Refused):
            brief.standing(self.graph, sha(), "all", T, None, ["wording"], limit=100,
                           ceiling=200)

    def test_nothing_is_reworded(self):
        known = every_sentence(self.graph)
        out = brief.standing(self.graph, sha(), "all", T, None, ["wording"]).text
        for line in out.splitlines():
            if line.startswith("[") and not line.startswith("[check:"):
                body = line.split("] ", 1)[1]
                body = body.split(": ", 1)[1] if body.startswith(("≡", "end:", "method:")) \
                    else body
                self.assertIn(body.strip(), known, line)


class NeighbourhoodTest(unittest.TestCase):
    def setUp(self):
        self.graph = load()

    def test_lineage_from_the_root_each_step_by_its_anchor(self):
        out = brief.neighbourhood(self.graph, sha(), ["rotation"], "all", T).text
        order = ["[garden/a1.h]", "[garden/a1.t2.1] raises planting: \"Each bed is planted for "
                 "what the kitchen will use.\"", "[planting/a1.h]",
                 "[planting/a1.t1.1] raises rotation: \"The rotation is written down before "
                 "the seed goes in.\"", "[rotation/q]", "[rotation/a1.s1]", "[rotation/a1.s3]"]
        at = [out.index(w) for w in order]
        self.assertEqual(at, sorted(at))
        self.assertIn("## Glossary of the terms in play", out)
        self.assertIn("[rotation/≡fallow.s1]", out)
        self.assertIn("[planting/a1.s2] (bed)", out)
        self.assertIn("[planting/a1.s1] (bed)", out)
        self.assertEqual(brief.stamp_of(out)["line"], ["rotation"])

    def test_tradition_on_the_line(self):
        out = brief.neighbourhood(self.graph, sha(), ["garden"], "all", T).text
        self.assertIn("## Tradition on the line", out)
        self.assertIn("support almanac: The almanac plants by the season.", out)

    def test_the_ai_side_reads_the_ai_s_answers_alone(self):
        out = brief.neighbourhood(self.graph, sha(), ["rotation", "planting"], "ai", T).text
        self.assertIn("[planting/a1.s1]", out)
        for user in ("feed the house", "one sheet", "≡", "almanac", "Each bed is planted"):
            self.assertNotIn(user, out)

    def test_every_term_in_play_keeps_its_word_and_address(self):
        """The floor: at any size the conventions and lineage leave room
        for, each term in play stands at least as its word and address,
        reserved before lineage takes the rest."""
        whole = brief.neighbourhood(self.graph, sha(), ["rotation"], "all", T)
        for limit in range(len(whole.text), 700, -15):
            out = brief.neighbourhood(self.graph, sha(), ["rotation"], "all", T, limit=limit)
            self.assertLessEqual(len(out.text), limit)
            for base in ("rotation/\u2261fallow", "garden/\u2261bed"):
                self.assertIn("[%s" % base, out.text, limit)
            if any(i.startswith("rotation/a1.s") for i in out.manifest["left_out"]):
                return
        self.fail("no limit cut the principle's answer")

    def test_compaction_order(self):
        """Lineage before the principle's sentences, those before the full
        glossary entries, those before the answers that share a term."""
        whole = brief.neighbourhood(self.graph, sha(), ["rotation"], "all", T)
        first = {}
        for limit in range(len(whole.text), 600, -5):
            out = brief.neighbourhood(self.graph, sha(), ["rotation"], "all", T, limit=limit)
            left = out.manifest["left_out"]
            for key, test in (("sharing", lambda i: i.startswith("planting/a1.s")),
                              ("glossary", lambda i: "\u2261" in i),
                              ("own", lambda i: i.startswith("rotation/a1.s")),
                              ("chain", lambda i: i.startswith("garden/a1.t"))):
                if key not in first and any(test(i) for i in left):
                    first[key] = limit
        self.assertGreaterEqual(first["sharing"], first["glossary"])
        self.assertGreaterEqual(first["glossary"], first["own"])
        self.assertGreaterEqual(first["own"], first.get("chain", 0))

    def test_a_condition_is_never_kept_apart_from_its_allowance(self):
        """B3: an answer is kept whole or as a prefix, and a cut is marked
        where it falls, with the answer's address."""
        raw = json.load(open(GRAPH))
        for q in raw["questions"]:
            if q["id"] == "rotation":
                q["theses"][0]["text"] = ("A bed may be sown at any season. Only when the "
                                          "rotation sheet shows it rested for a season may it "
                                          "be sown again with the same crop. Sowing is quick.")
        path = os.path.join(tempfile.mkdtemp(), "g.json")
        self.addCleanup(shutil.rmtree, os.path.dirname(path), ignore_errors=True)
        with open(path, "w") as fh:
            json.dump(raw, fh)
        graph = model.load(path)
        whole = brief.neighbourhood(graph, "x", ["rotation"], "all", T)
        cut_seen = False
        for limit in range(len(whole.text), 500, -3):
            out = brief.neighbourhood(graph, "x", ["rotation"], "all", T, limit=limit)
            ids = set(out.manifest["included"])
            for unit_sentences in (["rotation/a1.s1", "rotation/a1.s2", "rotation/a1.s3"],
                                   ["garden/\u2261bed.s1", "garden/\u2261bed.s2"]):
                kept = [i in ids for i in unit_sentences]
                self.assertEqual(kept, sorted(kept, reverse=True), (limit, kept))
            if "rotation/a1.s1" in ids and "rotation/a1.s2" not in ids:
                cut_seen = True
                self.assertIn("[rotation/a1 \u2026] cut here: 2 more sentence(s)", out.text)
                self.assertIn("rotation/a1", out.manifest["cut"])
                self.assertNotIn("Sowing is quick.", out.text)
        self.assertTrue(cut_seen)

    def test_the_line_resolves_by_id_tab_and_open_line(self):
        lines = {"l9": {"id": "l9", "anchors": [{"tab": "g-04", "words": "x"}]}}
        self.assertEqual(brief.resolve(self.graph, ["planting", "G-01", "l9"], lines),
                         ["planting", "garden", "rotation"])
        with self.assertRaises(brief.Refused):
            brief.resolve(self.graph, ["nowhere"])

    def test_staleness(self):
        out = brief.neighbourhood(self.graph, sha(), ["rotation"], "all", T).text
        self.assertEqual(brief.stale(out, sha(), ["rotation"]), [])
        self.assertTrue(brief.stale(out, "0" * 64))
        self.assertTrue(brief.stale(out, sha(), ["garden"]))
        self.assertTrue(brief.stale("no stamp", sha()))


class ForPromptTest(unittest.TestCase):
    def setUp(self):
        self.graph = load()

    def test_a_prompt_naming_a_tab(self):
        words, manifest = brief.for_prompt(self.graph, sha(), "Build the sheet for rotation.",
                                           "all", T)
        self.assertIn("# Brief: standing (side all)", words)
        self.assertIn("# Brief: neighbourhood of the prompt (side all)", words)
        self.assertEqual(manifest["neighbourhood"]["line"], ["rotation"])

    def test_a_prompt_using_a_fixed_term(self):
        _, manifest = brief.for_prompt(self.graph, sha(), "Mark every fallow plot.", "all", T)
        self.assertEqual(manifest["neighbourhood"]["line"], ["rotation"])

    def test_a_prompt_with_nothing_of_the_graph_gets_the_standing_brief(self):
        words, manifest = brief.for_prompt(self.graph, sha(), "Count to ten.", "all", T)
        self.assertNotIn("neighbourhood", manifest)
        self.assertIn("## Conventions", words)

    def test_the_whole_fits_the_target(self):
        words, _ = brief.for_prompt(self.graph, sha(), "rotation planting garden", "all", T)
        self.assertLessEqual(len(words), brief.TARGET)


class WhereTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_under_the_config_home_keyed_by_the_checkout(self):
        project = os.path.join(self.tmp, "work", "p")
        os.makedirs(os.path.join(project, ".principal"))
        with open(os.path.join(project, ".principal", "notebook.json"), "w") as fh:
            fh.write("{}")
        env = {"HOME": os.path.join(self.tmp, "home")}
        root = brief.project_root(os.path.join(project, "sub"), env)
        self.assertEqual(root, os.path.realpath(project))
        where = brief.brief_dir(root, env)
        self.assertTrue(where.startswith(os.path.realpath(os.path.join(self.tmp, "home",
                                                                       ".claude", "principal",
                                                                       "brief"))))
        self.assertTrue(where.endswith(brief.slug(root)))
        self.assertNotEqual(brief.slug("/x/CanonDB-sitting"), brief.slug("/x/CanonDB/sitting"))
        env["CLAUDE_CONFIG_DIR"] = os.path.join(self.tmp, "cfg")
        self.assertTrue(brief.brief_dir(root, env).startswith(os.path.realpath(env["CLAUDE_CONFIG_DIR"])))

    def test_never_in_a_checkout_or_the_project(self):
        project = os.path.join(self.tmp, "p")
        os.makedirs(os.path.join(project, ".git"))
        with self.assertRaises(brief.Refused):
            brief.brief_dir(project, {"CLAUDE_CONFIG_DIR": os.path.join(project, "cfg")})
        with self.assertRaises(brief.Refused):
            brief.brief_dir(os.path.join(self.tmp, "q"),
                            {"CLAUDE_CONFIG_DIR": os.path.join(self.tmp, "q", "c")})

    def test_no_notebook_no_project(self):
        self.assertIsNone(brief.project_root(self.tmp, {}))


class OutgoingTest(unittest.TestCase):
    def setUp(self):
        self.graph = load()

    def checks(self, words, target=None, public=False, party=False):
        return [f.check for f in outgoing.findings(self.graph, words, target, public, party)]

    def test_the_user_is_never_the_human(self):
        self.assertEqual(self.checks("The human waters the beds."), ["user-named"])
        self.assertEqual(self.checks("The user waters the beds."), [])
        self.assertEqual(self.checks("The human waters the beds.", party=True), [])

    def test_a_fixed_term_defined_in_running_text(self):
        for words in ("Here \"fallow\" means a bed with weeds.", "Fallow is defined as idle.",
                      "By fallow we mean idle.", "This defines *fallow* as idle."):
            self.assertEqual(self.checks(words), ["definition-in-glossary"], words)
        self.assertEqual(self.checks("A fallow bed is marked with a cross."), [])
        self.assertEqual(self.checks("≡ fallow\n\nFallow means rested."), [])
        self.assertEqual(self.checks("\"Weeds\" means nothing fixed."), [])

    def test_a_term_out_of_reach_of_its_tab(self):
        self.assertEqual(self.checks("A fallow bed waits.", target="planting"), ["reach"])
        self.assertEqual(self.checks("A fallow bed waits.", target="rotation"), [])
        self.assertEqual(self.checks("A fallow bed waits."), [])

    def test_masked_words_bound_for_a_public_place(self):
        self.assertEqual(self.checks("The garden is kept to feed the house well.", public=True),
                         ["masked"])
        self.assertEqual(self.checks("The garden is kept to feed the house well."), [])
        self.assertEqual(self.checks("A bed takes the crop the kitchen asks for this season.",
                                     public=True), [])

    def test_the_refusal_hands_back_the_entry_and_its_lineage(self):
        found = outgoing.findings(self.graph, "Here \"fallow\" means weeds.")
        said = outgoing.refusal(self.graph, found, "all", ["wording"])
        for want in ("[check:definition-in-glossary]", "[rotation/≡fallow.s1] ≡ fallow:",
                     "[planting/a1.t1.1] raises rotation:", "[garden/a1.h]"):
            self.assertIn(want, said)
        named = outgoing.refusal(self.graph, outgoing.findings(self.graph, "The human digs."),
                                 "all", ["wording"])
        self.assertIn("[wording/a1.s1] The one the record is kept for is named the user.", named)

    def test_a_blind_context_is_told_the_check_alone(self):
        found = outgoing.findings(self.graph, "The garden is kept to feed the house well.",
                                  public_place=True)
        said = outgoing.refusal(self.graph, found, "ai", ["wording"])
        self.assertIn("[check:masked]", said)
        self.assertNotIn("garden", said)
        self.assertNotIn("feed the house", said)


class InhandTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)

    def test_add_done_list_export_seed(self):
        data = inhand.load(self.dir)
        self.assertEqual(inhand.add(data, "a reviewer   of the build", T), "w1")
        self.assertEqual(inhand.add(data, "the evening bell", T, schedule=True), "s2")
        inhand.save(self.dir, data)
        data = inhand.load(self.dir)
        said = inhand.listing(data, "/x")
        self.assertIn("- w1 (since %s, " % T, said)
        self.assertIn(" ago) a reviewer of the build", said)
        self.assertEqual(inhand.age("2030-01-01T00:00:00Z", "2030-01-02T03:05:00Z"), "1d03h")
        self.assertEqual(inhand.age("2030-01-01T00:00:00Z", "2030-01-01T02:05:00Z"), "2h05m")
        self.assertEqual(inhand.age("whenever"), "age unknown")
        self.assertIn("not an instruction", said)
        self.assertEqual(inhand.export(data, T, 3),
                         {"op": "set", "collection": "ordo", "doc_id": "session",
                          "data": {"at": T, "in_hand": ["a reviewer of the build"],
                                   "schedule": ["the evening bell"]}, "if_version": 3})
        inhand.done(data, "w1")
        with self.assertRaises(inhand.Refused):
            inhand.done(data, "w1")
        fresh = inhand.empty()
        self.assertEqual(inhand.seed(fresh, {"data": {"in_hand": [], "schedule":
                                                      ["the evening bell"]}}, T), ["s1"])
        self.assertEqual(inhand.seed(fresh, {"schedule": ["the evening bell"]}, T), [])


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.project = os.path.join(self.tmp, "project")
        os.makedirs(os.path.join(self.project, ".principal"))
        with open(os.path.join(self.project, ".principal", "notebook.json"), "w") as fh:
            json.dump({"artifact": "x", "conventions": "wording"}, fh)
        self.env = {k: v for k, v in os.environ.items()
                    if k not in ("CLAUDE_PROJECT_DIR", "CLAUDE_CONFIG_DIR")}
        self.env["HOME"] = os.path.join(self.tmp, "home")

    def run_tool(self, tool, *args, code=0):
        done = subprocess.run([sys.executable, "-B", os.path.join(HERE, tool)] + list(args),
                              cwd=self.project, capture_output=True, text=True, env=self.env,
                              timeout=60)
        self.assertEqual(done.returncode, code, done.stderr)
        return done

    def test_install_check_and_where(self):
        done = self.run_tool("brief.py", "install", GRAPH, "--line", "rotation", "--at", T)
        where = done.stdout.strip().splitlines()[-1]
        self.assertEqual(where, self.run_tool("brief.py", "where").stdout.strip())
        self.assertTrue(where.startswith(os.path.join(self.env["HOME"], ".claude")))
        for name in ("graph.json", "source.json", "standing.md", "standing.md.manifest.json",
                     "neighbourhood.md", "neighbourhood.md.manifest.json"):
            self.assertTrue(os.path.isfile(os.path.join(where, name)), name)
        with open(os.path.join(where, "standing.md")) as fh:
            standing = fh.read()
        self.assertIn("[wording/a1.s1]", standing)
        self.assertEqual(self.run_tool("brief.py", "check", os.path.join(where, "standing.md"),
                                       "--graph", GRAPH).stdout, "fresh\n")
        other = os.path.join(self.tmp, "g.json")
        with open(GRAPH) as src, open(other, "w") as dst:
            dst.write(src.read() + "\n")
        said = self.run_tool("brief.py", "check", os.path.join(where, "neighbourhood.md"),
                             "--graph", other, code=1).stdout
        self.assertTrue(said.startswith("stale: made from graph"))

    def test_for_prompt_and_refusal(self):
        prompt = os.path.join(self.tmp, "prompt.md")
        with open(prompt, "w") as fh:
            fh.write("Build the sheet for rotation.")
        out = self.run_tool("brief.py", "for-prompt", prompt, "--graph", GRAPH, "--side", "ai",
                            "--at", T).stdout
        self.assertIn("(side ai)", out)
        self.assertNotIn("one sheet", out)
        said = self.run_tool("brief.py", "neighbourhood", GRAPH, "--line", "nowhere", code=1)
        self.assertIn("REFUSED:", said.stderr)

    def test_inhand_registers_its_path(self):
        speaker = os.path.join(self.tmp, "scratch", "speaker")
        self.assertEqual(self.run_tool("inhand.py", "add", speaker, "a helper", "--at", T,
                                       "--session", "sess-1").stdout.strip(), "w1")
        where = self.run_tool("brief.py", "where").stdout.strip()
        self.assertFalse(os.path.exists(os.path.join(where, "sessions", "sess-2")))
        with open(os.path.join(where, "sessions", "sess-1", "inhand.path")) as fh:
            self.assertEqual(fh.read().strip(), os.path.realpath(os.path.join(speaker,
                                                                              "inhand.json")))
        out = json.loads(self.run_tool("inhand.py", "export", speaker, "--at", T).stdout)
        self.assertEqual(out["data"]["in_hand"], ["a helper"])
        self.run_tool("inhand.py", "add", "relative/dir", "x", "--at", T, code=1)


if __name__ == "__main__":
    unittest.main()
