"""The plain form of a marked-up anchor, and where it stands on the page."""

import unittest

from hypo.text import occurrences, plain


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


if __name__ == "__main__":
    unittest.main()
