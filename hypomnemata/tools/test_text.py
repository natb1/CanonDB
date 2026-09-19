"""The plain form of a marked-up anchor: characters kept, markers dropped."""

import unittest

from hypo.text import plain


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


if __name__ == "__main__":
    unittest.main()
