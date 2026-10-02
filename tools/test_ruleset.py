"""The rule on main, as the file that defines it: the default branch takes
the admin's merge of a pull request and no other write. The file is what the
author imports under Settings > Rules; nothing here can tell whether he has."""

import json
import os
import unittest

RULESET = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir,
                       ".github", "rulesets", "main.json")

#: GitHub's id for the repository admin role
ADMIN = 5


class RulesetTest(unittest.TestCase):
    def setUp(self):
        with open(RULESET, encoding="utf-8") as fh:
            self.ruleset = json.load(fh)

    def test_it_is_in_force_on_the_default_branch_alone(self):
        self.assertEqual(self.ruleset["target"], "branch")
        self.assertEqual(self.ruleset["enforcement"], "active")
        self.assertEqual(self.ruleset["conditions"]["ref_name"],
                         {"include": ["~DEFAULT_BRANCH"], "exclude": []})

    def test_no_write_lands(self):
        # update refuses every push and merge, the other two a deletion and
        # a rewrite of what was merged
        self.assertEqual(sorted(r["type"] for r in self.ruleset["rules"]),
                         ["deletion", "non_fast_forward", "update"])

    def test_but_the_admin_s_merge_of_a_pull_request(self):
        self.assertEqual(self.ruleset["bypass_actors"],
                         [{"actor_id": ADMIN, "actor_type": "RepositoryRole",
                           "bypass_mode": "pull_request"}])


if __name__ == "__main__":
    unittest.main()
