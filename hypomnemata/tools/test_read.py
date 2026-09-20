"""render then read is the identity on everything the markdown carries."""

import os
import unittest

from hypo import model, read, render

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def load(name):
    return model.load(os.path.join(FIXTURES, name + ".json"))


def chip_ids(graph):
    """The map the document's file list supplies: chip key back to question."""
    return {render.chip_key(q.id): q.id for q in graph.questions}


def shed(value):
    """A model object as plain data, dropping what the markdown never carries."""
    if isinstance(value, list):
        return [shed(v) for v in value]
    if hasattr(value, "__dataclass_fields__"):
        out = {}
        for name in value.__dataclass_fields__:
            if name in ("tab", "body", "tradition", "requires", "path",
                        "questions", "artifact", "mode", "state_enum"):
                continue
            field = shed(getattr(value, name))
            if field in ([], "", None, False):
                continue
            out[name] = field
        return out
    return value


class RoundTripTest(unittest.TestCase):
    """The hand-written step in the middle of the loop, removed.

    Until this existed the renderer produced a correct tab, the checker
    validated a correct graph, and nothing at all compared the two with what
    was on the page.
    """

    def assert_round_trips(self, name):
        graph = load(name)
        ids = chip_ids(graph)
        for q in graph.questions:
            with self.subTest(fixture=name, question=q.id):
                parsed = read.parse_tab(render.body(graph, q.id), ids)
                # back through the model, so the comparison is of objects and
                # not of the shape this particular parser happens to emit
                again = model.Question.read(model._Reader(), dict(
                    parsed, tab=q.tab, body=q.body), "round-trip")
                self.assertEqual(shed(again), shed(q))

    def test_the_valid_graph(self):
        self.assert_round_trips("valid")

    def test_every_invalid_fixture_too(self):
        """They are whole graphs with one mutation, so they exercise shapes the
        valid one does not — a term deadlock, a second thesis, a bad target."""
        for name in sorted(os.listdir(FIXTURES)):
            if name.startswith("invalid-") and name.endswith(".json"):
                self.assert_round_trips(name[:-5])


class DetailTest(unittest.TestCase):
    def setUp(self):
        self.graph = load("valid")
        self.ids = chip_ids(self.graph)

    def parse(self, qid):
        return read.parse_tab(render.body(self.graph, qid), self.ids)

    def test_the_breadcrumb_is_not_stored(self):
        """It is projected from the edges at every render, so reading it back
        would be storing a second copy of the tree."""
        self.assertNotIn("lineage", self.parse("attenuation"))

    def test_the_incoming_anchors_come_back_with_their_source(self):
        incoming = self.parse("attenuation")["incoming"]
        self.assertEqual([src for _, src in incoming], ["canon", "party"])

    def test_requires_comes_back_as_the_rendered_title(self):
        """The page shows titles; ids are resolved against the inbox items of
        every tab, which is why assembling a graph needs all of them."""
        self.assertEqual(self.parse("ti-esti")["requires"],
                         ["promulgate the root answer"])

    def test_a_tab_that_is_not_a_tab_is_refused(self):
        with self.assertRaises(read.ParseError):
            read.parse_tab("just some prose", self.ids)

    def test_an_exported_chip_reads_the_same_as_a_token(self):
        """The document flattens a chip to a link when it exports markdown."""
        body = render.body(self.graph, "ti-esti")
        exported = body.replace("<?claude block m_canon?>", "[canon](file/tab-02)")
        self.assertEqual(read.parse_tab(exported, self.ids),
                         read.parse_tab(body, self.ids))


if __name__ == "__main__":
    unittest.main()
