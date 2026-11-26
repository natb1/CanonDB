"""The public copy: Claude's graph shown whole, the user's masked unless
marked, and nothing shown that quotes what is masked."""

import json
import os
import tempfile
import unittest

from hypo import model, public
from support import fixture, load, run

SALT = "a salt long enough to keep"


def marked(qid, words):
    """The fixture with a note on ``qid``. ``public: thesis`` and the like
    are given their fingerprints as the tab reads now; ``public: all``
    names every section; anything else goes on as written."""
    graph = load("valid")
    q = graph.get(qid)
    if words.startswith("public: "):
        names = words[len("public: "):].split(", ")
        if names == ["all"]:
            names = list(model.SECTIONS)
        words = public.mark(q, names)
    q.notes.append(model.Note(section="thesis", body=words))
    return graph


class WhoseTest(unittest.TestCase):
    def test_a_question_with_an_answer_past_held_is_claudes(self):
        graph = load("valid")
        self.assertTrue(graph.get("ti-esti").claude)
        self.assertFalse(graph.get("canon").claude)

    def test_only_the_answers_past_held_are_claudes_own(self):
        root = load("valid").get("ti-esti")
        self.assertTrue(all(t.state != "held" for t in public.own(root)))
        self.assertTrue(public.own(root))


class CopyTest(unittest.TestCase):
    def test_a_node_of_claudes_is_shown_with_its_question_and_answer(self):
        graph = load("valid")
        made = public.copy(graph, SALT)
        node = next(n for n in made["nodes"] if n["id"] == "ti-esti")
        self.assertEqual(node["whose"], "claude")
        self.assertFalse(node["masked"])
        self.assertEqual(node["question"], graph.get("ti-esti").question)
        self.assertEqual(node["answers"][0]["text"], public.own(graph.get("ti-esti"))[0].text)

    def test_an_unmarked_node_of_the_users_gives_neither_name_nor_words(self):
        graph = load("valid")
        made = public.copy(graph, SALT)
        text = json.dumps(made)
        canon = graph.get("canon")
        self.assertNotIn('"canon"', text)
        self.assertNotIn(canon.theses[0].text[:40], text)
        node = next(n for n in made["nodes"] if n["id"] == public.stub("canon", SALT))
        self.assertEqual(node, {"id": public.stub("canon", SALT), "whose": "user",
                                "masked": True})

    def test_the_edges_stand_with_the_masked_end_under_its_fingerprint(self):
        made = public.copy(load("valid"), SALT)
        self.assertIn({"from": "ti-esti", "to": public.stub("canon", SALT),
                       "kind": "raises"}, made["edges"])

    def test_a_marked_section_is_shown_and_the_others_are_not(self):
        graph = marked("canon", "public: thesis")
        node = next(n for n in public.copy(graph, SALT)["nodes"] if n["id"] == "canon")
        self.assertFalse(node["masked"])
        self.assertEqual(node["answers"][0]["text"], graph.get("canon").theses[0].text)
        self.assertNotIn("glossary", node)
        self.assertNotIn("end", node)

    def test_all_marks_every_section(self):
        self.assertEqual(public.marks(marked("canon", "public: all").get("canon")),
                         set(model.SECTIONS))

    def test_a_mark_with_no_fingerprint_marks_nothing(self):
        graph = load("valid")
        graph.get("canon").notes.append(model.Note(section="thesis", body="public: thesis"))
        self.assertEqual(public.marks(graph.get("canon")), set())
        self.assertEqual(public.lapsed(graph.get("canon")), ["thesis"])

    def test_a_section_changed_after_its_mark_is_masked_again(self):
        graph = marked("canon", "public: thesis")
        canon = graph.get("canon")
        self.assertEqual(public.marks(canon), {"thesis"})
        canon.theses[0].text += " One paragraph more."
        self.assertEqual(public.marks(canon), set())
        self.assertEqual(public.lapsed(canon), ["thesis"])
        node = next(n for n in public.copy(graph, SALT)["nodes"]
                    if n["id"] == public.stub("canon", SALT))
        self.assertTrue(node["masked"])

    def test_a_mark_on_one_section_does_not_lapse_when_another_changes(self):
        graph = marked("canon", "public: thesis")
        canon = graph.get("canon")
        canon.definitions.append(model.Definition(word="newword", body="A new entry."))
        self.assertEqual(public.marks(canon), {"thesis"})

    def test_a_note_that_is_no_mark_marks_nothing(self):
        self.assertEqual(public.marks(marked("canon", "pending: thesis").get("canon")), set())

    def test_a_party_no_shown_answer_cites_is_masked(self):
        graph = load("valid")
        cited = {e.to for q in graph.questions if q.claude
                 for t in public.own(q) for e in t.traditions}
        made = public.copy(graph, SALT)
        for q in graph.questions:
            if q.tradition and q.id not in cited:
                self.assertIn(public.stub(q.id, SALT), [n["id"] for n in made["nodes"]])

    def test_a_fingerprint_holds_under_one_salt_and_moves_under_another(self):
        self.assertEqual(public.stub("canon", SALT), public.stub("canon", SALT))
        self.assertNotEqual(public.stub("canon", SALT), public.stub("canon", SALT + "x"))


class LeakTest(unittest.TestCase):
    def leaking(self):
        graph = load("valid")
        secret = "the household keeps seven grey geese behind the old mill"
        graph.get("attenuation").theses[0].text += " " + secret
        public.own(graph.get("ti-esti"))[0].text += " And " + secret + "."
        return graph

    def test_the_fixture_shows_nothing_masked(self):
        self.assertEqual(public.leaks(load("valid")), [])

    def test_an_answer_of_claudes_like_a_masked_node_is_agreement_and_no_leak(self):
        graph = self.leaking()
        self.assertEqual(public.leaks(graph), [])
        self.assertEqual([(s.shown, s.masked) for s in public.similar(graph)],
                         [("ti-esti", "attenuation")])

    def test_a_question_put_to_claude_that_repeats_masked_words_is_a_leak(self):
        graph = load("valid")
        secret = "the household keeps seven grey geese behind the old mill"
        graph.get("attenuation").theses[0].text += " " + secret
        graph.get("ti-esti").question += " Given that " + secret + "?"
        self.assertEqual([(leak.shown, leak.masked) for leak in public.leaks(graph)],
                         [("ti-esti", "attenuation")])

    def test_a_marked_section_like_an_unmarked_tab_is_to_consider_and_no_leak(self):
        graph = load("valid")
        secret = "the household keeps seven grey geese behind the old mill"
        graph.get("party").theses[0].text += " " + secret
        canon = graph.get("canon")
        canon.theses[0].text += " " + secret
        canon.notes.append(model.Note(section="thesis", body=public.mark(canon, ["thesis"])))
        self.assertEqual(public.leaks(graph), [])
        self.assertIn(("canon", "party"),
                      [(leak.shown, leak.masked) for leak in public.consider(graph)])

    def test_an_unmarked_graph_has_nothing_to_consider(self):
        self.assertEqual(public.consider(load("valid")), [])

    def test_a_shorter_run_is_no_likeness(self):
        graph = load("valid")
        graph.get("attenuation").theses[0].text += " seven grey geese behind"
        public.own(graph.get("ti-esti"))[0].text += " seven grey geese behind"
        self.assertEqual(public.similar(graph), [])

    def test_a_node_quoting_the_clause_that_raises_it_is_not_listed(self):
        graph = load("valid")
        root = graph.get("ti-esti")
        child = root.theses[0].terms[0].to
        clause = "a clause of nine words that raises the child node"
        public.own(root)[0].text += " " + clause
        graph.get(child).theses[0].text += " " + clause
        self.assertEqual(public.similar(graph), [])

    def test_the_hinge_on_a_tab_of_claudes_is_the_users_and_is_not_shown(self):
        graph = load("valid")
        root = graph.get("ti-esti")
        node = next(n for n in public.copy(graph, SALT)["nodes"] if n["id"] == "ti-esti")
        self.assertNotIn("asking", node)
        self.assertIn(root.hinge.question, public.masked(root))

    def test_a_drafted_question_that_quotes_a_masked_node_is_caught(self):
        graph = self.leaking()
        found = public.question(graph, "Given that the household keeps seven grey geese, what follows?")
        self.assertEqual([leak.masked for leak in found], ["attenuation"])

    def test_a_drafted_question_that_links_into_a_masked_tab_is_caught(self):
        graph = load("valid")
        tab = graph.get("attenuation").tab
        found = public.question(graph, "See https://example.invalid/doc#%s.block for what is meant." % tab)
        self.assertEqual([(leak.masked, leak.words) for leak in found],
                         [("attenuation", "a link into its tab")])

    def test_an_answer_of_claudes_that_spells_a_masked_tabs_address_is_a_leak(self):
        graph = load("valid")
        public.own(graph.get("ti-esti"))[0].text += " (#%s.x)" % graph.get("attenuation").tab
        self.assertIn(("ti-esti", "attenuation"),
                      [(leak.shown, leak.masked) for leak in public.leaks(graph)])

    def test_a_drafted_question_in_new_words_passes(self):
        self.assertEqual(public.question(load("valid"), "What does working with a person need of you?"), [])


class CommandTest(unittest.TestCase):
    def test_check_passes_on_the_fixture(self):
        done = run("public", "check", fixture("valid"))
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_copy_writes_a_page_a_node_and_no_masked_word(self):
        graph = load("valid")
        with tempfile.TemporaryDirectory() as out:
            salt = os.path.join(out, "salt")
            with open(salt, "w", encoding="utf-8") as fh:
                fh.write(SALT)
            done = run("public", "copy", fixture("valid"), "-o", os.path.join(out, "copy"),
                       "--salt-file", salt)
            self.assertEqual(done.returncode, 0, done.stderr)
            pages = os.listdir(os.path.join(out, "copy", "nodes"))
            self.assertEqual(len(pages), len(graph.questions))
            everything = ""
            for name in pages:
                with open(os.path.join(out, "copy", "nodes", name), encoding="utf-8") as fh:
                    everything += fh.read()
            self.assertIn(public.own(graph.get("ti-esti"))[0].text.strip()[:60], everything)
            self.assertNotIn(graph.get("canon").theses[0].text.strip()[:60], everything)

    def test_copy_waits_until_a_likeness_of_a_marked_section_is_considered(self):
        import json as _json
        with open(fixture("valid"), encoding="utf-8") as fh:
            data = _json.load(fh)
        secret = "the household keeps seven grey geese behind the old mill"
        for q in data["questions"]:
            if q["id"] == "canon":
                q["theses"][0]["text"] += " " + secret
                q.setdefault("notes", []).append({"section": "thesis", "body": "MARK"})
            if q["id"] == "party":
                q["theses"][0]["text"] += " " + secret
        with tempfile.TemporaryDirectory() as out:
            graph, salt = os.path.join(out, "g.json"), os.path.join(out, "salt")
            with open(graph, "w", encoding="utf-8") as fh:
                _json.dump(data, fh)
            words = run("public", "mark", graph, "canon", "thesis").stdout.strip()
            for q in data["questions"]:
                for note in q.get("notes", []):
                    if note["body"] == "MARK":
                        note["body"] = words
            with open(graph, "w", encoding="utf-8") as fh:
                _json.dump(data, fh)
            with open(salt, "w", encoding="utf-8") as fh:
                fh.write(SALT)
            held = run("public", "copy", graph, "-o", os.path.join(out, "copy"), "--salt-file", salt)
            self.assertEqual(held.returncode, 2)
            self.assertFalse(os.path.exists(os.path.join(out, "copy")))
            done = run("public", "copy", graph, "-o", os.path.join(out, "copy"),
                       "--salt-file", salt, "--considered")
            self.assertEqual(done.returncode, 0, done.stderr)

    def test_a_short_salt_is_refused(self):
        with tempfile.TemporaryDirectory() as out:
            salt = os.path.join(out, "salt")
            with open(salt, "w", encoding="utf-8") as fh:
                fh.write("short")
            done = run("public", "copy", fixture("valid"), "-o", os.path.join(out, "copy"),
                       "--salt-file", salt)
            self.assertEqual(done.returncode, 1)
            self.assertFalse(os.path.exists(os.path.join(out, "copy")))


class QuestionCommandTest(unittest.TestCase):
    """`public.py question`: a masked tab's address and the notebook's rule
    for naming the user, and the record a pass leaves."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.question = os.path.join(self.tmp.name, "question.md")
        self.record = os.path.join(self.tmp.name, "leak.json")

    def check(self, words):
        with open(self.question, "w", encoding="utf-8") as fh:
            fh.write(words)
        return run("public", "question", fixture("valid"), self.question, "--record",
                   self.record)

    def test_a_pass_leaves_a_record_of_the_bytes_and_the_graph(self):
        import hashlib
        import json as _json
        done = self.check("What does working with a person need of you?\n")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        with open(self.record, encoding="utf-8") as fh:
            record = _json.load(fh)
        with open(self.question, "rb") as fh:
            self.assertEqual(record["sha256"], hashlib.sha256(fh.read()).hexdigest())
        with open(fixture("valid"), "rb") as fh:
            self.assertEqual(record["graph_sha256"], hashlib.sha256(fh.read()).hexdigest())

    def test_a_failing_check_leaves_no_record_an_earlier_one_included(self):
        # M13, S2: a record already at the path is taken away first
        self.assertEqual(self.check("What does working with a person need of you?\n")
                         .returncode, 0)
        self.assertTrue(os.path.exists(self.record))
        tab = load("valid").get("attenuation").tab
        done = self.check("See https://example.invalid/doc#%s.block for what is meant.\n" % tab)
        self.assertEqual(done.returncode, 2)
        self.assertFalse(os.path.exists(self.record))

    def test_a_run_of_masked_words_is_no_longer_what_refuses_a_question(self):
        # whether a question hands over the user's record is read by meaning
        # (the question-reader, lead.py); the mechanical check looks for no run
        graph = load("valid")
        words = None
        for q in graph.questions:
            for part in public.masked(q):
                run = public._words(part)
                if len(run) >= 8 and not q.claude:
                    words = " ".join(run[:8])
                    break
            if words:
                break
        self.assertIsNotNone(words)
        drafted = "Is it so that %s?\n" % words
        self.assertTrue(public.question(graph, drafted), "a run the outgoing check still sees")
        self.assertEqual(public.addresses(graph, drafted), [])
        done = self.check(drafted)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertTrue(os.path.exists(self.record))
        self.assertIn("whether it leads the answerer", done.stdout)

    def test_a_question_that_names_the_user_otherwise_is_refused(self):
        # the rule check.py holds the notebook's own words to, `user-named`
        for words in ("What does the human need before the post is opened?\n",
                      "Is THE HUMAN's word final on a kept record?\n"):
            with self.subTest(words=words):
                done = self.check(words)
                self.assertEqual(done.returncode, 2)
                self.assertIn("the human", done.stdout.lower())
                self.assertIn("user-named", done.stdout)
                self.assertFalse(os.path.exists(self.record))
        self.assertEqual(self.check("What does the user need before the post is opened?\n")
                         .returncode, 0)


if __name__ == "__main__":
    unittest.main()
