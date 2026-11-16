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
    graph = load("valid")
    graph.get(qid).notes.append(model.Note(section="thesis", body=words))
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

    def test_a_marked_section_that_repeats_an_unmarked_tabs_words_is_a_leak(self):
        graph = marked("canon", "public: thesis")
        secret = "the household keeps seven grey geese behind the old mill"
        graph.get("party").theses[0].text += " " + secret
        graph.get("canon").theses[0].text += " " + secret
        self.assertIn(("canon", "party"),
                      [(leak.shown, leak.masked) for leak in public.leaks(graph)])

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

    def test_a_short_salt_is_refused(self):
        with tempfile.TemporaryDirectory() as out:
            salt = os.path.join(out, "salt")
            with open(salt, "w", encoding="utf-8") as fh:
                fh.write("short")
            done = run("public", "copy", fixture("valid"), "-o", os.path.join(out, "copy"),
                       "--salt-file", salt)
            self.assertEqual(done.returncode, 1)
            self.assertFalse(os.path.exists(os.path.join(out, "copy")))


if __name__ == "__main__":
    unittest.main()
