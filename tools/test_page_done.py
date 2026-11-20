"""The page draws a session's action that is resolved and not yet replaced
as resolved, never as the action to come: under "After the office" while
the office it carried shows, and as the card's action once that office is
done. Run in node against the stubbed document of the page's behaviour
tests; skipped where node is not installed. The Rule, the labels and the
times are invented."""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

import test_sit_skill as sit

PUT = "2030-01-02T07:50:00Z"
RESOLVED = "2030-01-02T08:30:00Z"
NOW = [2030, 0, 2, 9, 0]
DONE = "2030-01-02T08:40:00.000Z"
RULE = {"bells": [{"time": "08:00", "name": "Morning",
                   "office": ["Water the plants", "Feed the goldfish"]}]}
KEYS = ("bell-0800-water-the-plants", "bell-0800-feed-the-goldfish")


def current(**more):
    return {"next": dict({"kind": "question", "prompt": "Is watering still first?",
                          "put_at": PUT}, **more),
            "updated": "2030-01-02T09:00:00Z"}


class ResolvedActionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        node = shutil.which("node")
        if not node:
            sys.stderr.write("\n*** ResolvedActionTest SKIPPED: node is not installed; run again "
                             "under `nix shell nixpkgs#nodejs` ***\n")
            raise unittest.SkipTest("node is not installed")
        with open(sit.PAGE, encoding="utf-8") as fh:
            page = fh.read()
        hidden = [m.group(1) for m in re.finditer(r"<[^>]*\bid=\"([^\"]+)\"[^>]*>", page)
                  if re.search(r"\shidden[\s>]", m.group(0))]
        script = page[page.index("<script>") + len("<script>"):page.index("</script>")]
        done = {k: DONE for k in KEYS}
        scenarios = {
            # resolved, its office still due: the office shows, the action after it as resolved
            "carried": {"now": NOW, "rule": RULE, "ticks": None,
                        "current": current(resolved_at=RESOLVED)},
            # resolved, the office done: the card's action is drawn as resolved
            "after": {"now": NOW, "rule": RULE, "ticks": done,
                      "current": current(resolved_at=RESOLVED)},
            # not resolved, or resolved before it was put: drawn as before
            "open": {"now": NOW, "rule": RULE, "ticks": done, "current": current()},
            "early": {"now": NOW, "rule": RULE, "ticks": done,
                      "current": current(resolved_at="2030-01-02T07:40:00Z")},
            # N4 of the small-debts review: a review with a recommendation, how and case,
            # its office unresolved: the office card shows none of the three
            "office_review": {"now": NOW, "rule": RULE, "ticks": None,
                              "current": {"next": {"kind": "review", "prompt": "Is the new wording right?",
                                                   "recommendation": ["Keep the shorter wording."],
                                                   "how": "Say keep or change.",
                                                   "case": "The beds were sown twice."},
                                          "updated": "2030-01-02T09:00:00Z"}},
            # N5: the office set aside, the action resolved: drawn as resolved, the office under it
            "aside_done": {"now": NOW, "rule": RULE, "ticks": None,
                           "current": dict(current(resolved_at=RESOLVED), office_deferred={
                               "reason": "The letter first.", "since": "2030-01-02T08:40:00Z",
                               "bell": "0800"})},
            "early_office": {"now": NOW, "rule": RULE, "ticks": None,
                             "current": current(put_at="2030-01-02T08:20:00Z",
                                                resolved_at="2030-01-02T07:40:00Z")},
        }
        with tempfile.TemporaryDirectory() as tmp:
            paths = []
            for name, data in (("page.js", script), ("hidden.json", json.dumps(hidden)),
                               ("scenarios.json", json.dumps(scenarios)),
                               ("harness.js", sit.HARNESS)):
                with open(os.path.join(tmp, name), "w", encoding="utf-8") as fh:
                    fh.write(data)
                paths.append(os.path.join(tmp, name))
            run = subprocess.run([node, paths[3]] + paths[:3], capture_output=True, text=True,
                                 timeout=60, env=dict(os.environ, TZ="UTC"))
        if run.returncode:
            raise AssertionError(run.stderr)
        cls.res = json.loads(run.stdout)

    def el(self, name, id_):
        return self.res[name]["els"].get(id_) or {"hidden": True, "text": ""}

    def test_under_the_office_a_resolved_action_is_not_the_action_to_come(self):
        self.assertEqual(self.el("carried", "next-kind")["text"], "office")
        self.assertEqual(self.el("carried", "office-after-prompt")["text"],
                         "Resolved: Is watering still first?")
        self.assertIn("not yet put the next action", self.el("carried", "office-after-meta")["text"])
        self.assertTrue(self.el("carried", "next-done")["hidden"])

    def test_the_office_done_the_card_says_its_action_is_resolved(self):
        self.assertEqual(self.el("after", "next-prompt")["text"], "Is watering still first?")
        self.assertFalse(self.el("after", "next-done")["hidden"])

    def test_an_office_card_never_shows_a_review_s_recommendation_how_or_case(self):
        self.assertEqual(self.el("office_review", "next-kind")["text"], "office")
        self.assertEqual(self.el("office_review", "next-prompt")["text"], "Water the plants")
        for id_ in ("next-rec", "next-rec-label", "next-how", "next-case", "next-case-label"):
            self.assertTrue(self.el("office_review", id_)["hidden"], id_)
        self.assertEqual(self.el("office_review", "office-after-prompt")["text"],
                         "Is the new wording right?")

    def test_a_set_aside_office_under_a_resolved_action(self):
        self.assertEqual(self.el("aside_done", "next-prompt")["text"], "Is watering still first?")
        self.assertFalse(self.el("aside_done", "next-done")["hidden"])
        self.assertFalse(self.el("aside_done", "office-aside")["hidden"])
        self.assertIn("Water the plants", self.el("aside_done", "office-aside-items")["text"])

    def test_an_action_not_resolved_reads_as_before(self):
        for name in ("open", "early"):
            self.assertTrue(self.el(name, "next-done")["hidden"], name)
        self.assertEqual(self.el("early_office", "office-after-prompt")["text"],
                         "Is watering still first?")


if __name__ == "__main__":
    unittest.main()
