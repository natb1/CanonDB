"""The plain form of a marked-up anchor, and where it stands on the page."""

import unittest

from hypo.text import canonical, escape, forms, occurrences, plain


class PlainTest(unittest.TestCase):
    def test_text_without_markers_is_returned_whole(self):
        self.assertEqual(plain("a clause, plainly put."),
                         "a clause, plainly put.")

    def test_emphasis_is_unwrapped(self):
        self.assertEqual(plain("**Be predictable.** Keep going"),
                         "Be predictable. Keep going")
        self.assertEqual(plain("*italic* only"), "italic only")
        self.assertEqual(plain("the ***whole*** thing"), "the whole thing")

    def test_a_link_keeps_its_text_and_drops_its_target(self):
        self.assertEqual(plain("a [link](http://example.com) here"),
                         "a link here")

    def test_code_keeps_what_it_wraps(self):
        self.assertEqual(plain("run `check.py` first"), "run check.py first")

    def test_a_lone_asterisk_survives(self):
        self.assertEqual(plain("a * lone asterisk"), "a * lone asterisk")

    def test_an_intra_word_underscore_survives(self):
        """markdown honours `_` only at a word boundary, and an identifier in a
        clause must come back spelled the way the page holds it."""
        self.assertEqual(plain("the snake_case_word here"),
                         "the snake_case_word here")
        self.assertEqual(plain("_emphasis_ at a boundary"),
                         "emphasis at a boundary")

    def test_empty_and_none_are_empty(self):
        self.assertEqual(plain(""), "")
        self.assertEqual(plain(None), "")

    def test_an_escaped_mark_is_the_character(self):
        """The page holds a star where the markdown spells `\\*`; read as a
        marker it paired with the next one and took the words between."""
        self.assertEqual(plain("a \\* b and \\*not bold\\*"), "a * b and *not bold*")
        self.assertEqual(plain("\\[x\\](y) and a back\\\\slash"), "[x](y) and a back\\slash")

    def test_inside_code_a_backslash_is_a_character(self):
        self.assertEqual(plain("`a\\*b` and \\`c\\`"), "a\\*b and `c`")


class EscapeTest(unittest.TestCase):
    """What the page speller writes a backslash before, and what the reader
    keeps one before, is one rule, or a literal star went out bare and came
    back a mark."""

    def test_a_mark_the_page_holds_as_a_character_is_escaped(self):
        self.assertEqual(escape("a * b, [c] and `d` with \\ in it"),
                         "a \\* b, \\[c\\] and \\`d\\` with \\\\ in it")

    def test_an_underscore_is_escaped_only_at_a_word_boundary(self):
        self.assertEqual(escape("session_01 and _word_"), "session_01 and \\_word\\_")

    def test_words_without_a_mark_come_back_untouched(self):
        self.assertEqual(escape("a clause, plainly put."), "a clause, plainly put.")
        self.assertEqual(escape(""), "")

    def test_canonical_keeps_the_page_s_escapes_and_drops_the_exporter_s(self):
        self.assertEqual(canonical("session\\_01 \\. \\- \\* \\[x\\] \\_word\\_"),
                         "session_01 . - \\* \\[x\\] \\_word\\_")

    def test_canonical_leaves_code_as_it_stands(self):
        self.assertEqual(canonical("`a\\_b` and c\\_d"), "`a\\_b` and c_d")

    def test_escape_then_canonical_is_escape_and_plain_is_the_characters(self):
        for chars in ("a * b", "[x](y)", "back\\slash", "`not code`", "_edge_ a_b", "**not bold**"):
            with self.subTest(chars=chars):
                self.assertEqual(canonical(escape(chars)), escape(chars))
                self.assertEqual(plain(escape(chars)), chars)


class OccurrencesTest(unittest.TestCase):
    """Which run of characters a search means.

    The document counts every literal match and folds case while it counts, so
    a qualifying answer is a position in that counting and not a counting of
    its own.
    """

    def nths(self, *args, **kw):
        return [run.nth for run in occurrences(*args, **kw)]

    def test_merge_is_not_found_inside_merged(self):
        page = "a merged branch, then merge it"
        self.assertEqual(self.nths(page, "merge", True), [2])
        self.assertEqual(self.nths(page, "merge"), [1, 2])

    def test_prior_is_not_found_inside_priority(self):
        self.assertEqual(
            self.nths("priority is high, the prior is low", "prior", True), [2])

    def test_a_possessive_still_holds_the_word(self):
        """An apostrophe is not a letter, and `party's` is where a reader meets
        the word."""
        self.assertEqual(self.nths("the party's end", "party", True), [1])

    def test_a_word_that_only_hides_is_never_found(self):
        self.assertEqual(self.nths("priority only", "prior", True), [])

    def test_a_phrase_is_counted_as_it_stands(self):
        page = "one two three, and one two three again"
        self.assertEqual(self.nths(page, "one two three"), [1, 2])

    def test_overlapping_runs_are_all_counted(self):
        self.assertEqual(self.nths("aaaa", "aa"), [1, 2, 3])

    def test_nothing_to_find_is_no_occurrence(self):
        self.assertEqual(occurrences("abc", ""), [])
        self.assertEqual(occurrences("", "abc"), [])

    def test_a_capital_counts_and_is_found(self):
        """The document's find folds case, so an earlier run that differs only
        in case is still the run its numbering reaches first. Counting these
        out cost the notebook twenty-four links: every `nth` named a run
        earlier than the one meant, and that run already carried a link."""
        page = "## Thesis\n\na thesis answers a question"
        self.assertEqual(self.nths(page, "thesis", True), [1, 2])
        self.assertEqual(occurrences(page, "thesis", True)[0].at, page.index("Thesis"))

    def test_a_run_says_where_it_begins(self):
        page = "a merged branch, then merge it"
        self.assertEqual(occurrences(page, "merge", True)[0].at, page.index("merge it"))

    def test_an_offset_is_an_offset_into_what_was_given(self):
        """Folding is one character in and one out, or an offset would name
        characters that moved while the case came off."""
        page = "\u0130stanbul and the merge"
        self.assertEqual(occurrences(page, "merge")[0].at, page.index("merge"))


class FormsTest(unittest.TestCase):
    """A glossary entry is a headword; the prose uses what the sentence wants."""

    def test_the_headword_comes_back_with_its_regular_forms(self):
        self.assertEqual(set(forms("grant")),
                         {"grant", "grants", "granted", "granting"})

    def test_a_silent_e_is_not_doubled(self):
        self.assertEqual(set(forms("merge")),
                         {"merge", "merges", "merged", "merging"})

    def test_a_consonant_y_becomes_ies(self):
        self.assertEqual(set(forms("carry")),
                         {"carry", "carries", "carried", "carrying"})
        self.assertNotIn("carrys", forms("carry"))

    def test_a_sibilant_takes_es(self):
        self.assertIn("catches", forms("catch"))

    def test_a_phrase_inflects_on_its_last_word(self):
        self.assertIn("section types", forms("section type"))
        self.assertNotIn("sections type", forms("section type"))

    def test_a_phrase_before_a_noun_is_hyphenated(self):
        """A clean-context answer uses `clean context`, in the form a phrase
        takes in front of the noun it qualifies."""
        self.assertIn("clean-context", forms("clean context"))
        self.assertIn("clean-contexts", forms("clean context"))
        self.assertNotIn("grant", [f for f in forms("grant") if "-" in f])
        self.assertEqual([f for f in forms("merge") if "-" in f], [])

    def test_longest_first_so_a_caller_links_the_whole_word(self):
        """`grants` is linked whole rather than as the `grant` inside it."""
        self.assertEqual(forms("grant")[-1], "grant")
        self.assertTrue(all(len(a) >= len(b) for a, b in zip(forms("grant"),
                                                             forms("grant")[1:])))

    def test_nothing_is_no_form(self):
        self.assertEqual(forms(""), [])


if __name__ == "__main__":
    unittest.main()
