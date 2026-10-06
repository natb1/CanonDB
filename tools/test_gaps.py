"""The review's decidable half: links against the checkout, and the files
nothing accounts for."""

import unittest

from hypo import gaps

REPO = "natb1/CanonDB"
FILES = ["README.md", "canon/ti-esti.md", "tools/a.py", "tools/test_a.py",
         "skills/x/SKILL.md", ".gitignore"]
BLOB = "[a](https://github.com/natb1/CanonDB/blob/main/tools/a.py)"
TREE = "[tools](https://github.com/natb1/CanonDB/tree/main/tools)"
ROOT = "[plugin](https://github.com/natb1/CanonDB/tree/main)"


class StatusTest(unittest.TestCase):
    def test_link_kinds(self):
        self.assertEqual(gaps.status(BLOB, REPO, FILES), gaps.PRESENT)
        self.assertEqual(gaps.status(TREE, REPO, FILES), gaps.PRESENT)
        self.assertEqual(gaps.status(ROOT, REPO, FILES), gaps.EVERYTHING)
        self.assertEqual(gaps.status("not yet written", REPO, FILES), gaps.NONE)
        self.assertEqual(gaps.status("[x](https://github.com/other/r/blob/main/x)", REPO, FILES),
                         gaps.ELSEWHERE)
        self.assertEqual(gaps.status("[b](https://github.com/natb1/CanonDB/blob/main/b.py)",
                                     REPO, FILES), gaps.ABSENT)


class OrphanTest(unittest.TestCase):
    def test_what_accounts_for_a_file(self):
        manifest = {"applications": [{"application": "the entry points",
                                      "files": ["skills/x/SKILL.md"]}]}
        why = gaps.covered(FILES, [TREE, ROOT], REPO, manifest, ["canon/ti-esti.md"])
        self.assertEqual(why["canon/ti-esti.md"], "canon")
        self.assertEqual(why["skills/x/SKILL.md"], "manifest: the entry points")
        self.assertEqual(why["tools/test_a.py"], "link: tools/")
        # the root link justifies nothing
        self.assertEqual(gaps.orphans(FILES, why), ["README.md", ".gitignore"])

    def test_canon_list_and_remote(self):
        self.assertEqual(gaps.canon_files(["canon/ti-esti.md", "canonical.md", "tools/canon/x"]),
                         ["canon/ti-esti.md"])
        self.assertEqual(gaps.repo_of("git@github.com:natb1/CanonDB.git"), REPO)
        self.assertEqual(gaps.repo_of("https://github.com/natb1/CanonDB"), REPO)



class AddressTest(unittest.TestCase):
    """A link as GitHub spells one, in every spelling the checkout can answer for."""

    def test_an_anchor_or_a_query_is_not_the_path(self):
        for url in ("https://github.com/natb1/CanonDB/blob/main/tools/a.py#L10-L20",
                    "https://github.com/natb1/CanonDB/blob/main/tools/a.py?plain=1"):
            self.assertEqual(gaps.status("[a](%s)" % url, REPO, FILES), gaps.PRESENT, url)

    def test_a_space_in_the_path_is_percent_encoded(self):
        files = FILES + ["docs/with space/file one.md"]
        link = "[f](https://github.com/natb1/CanonDB/blob/main/docs/with%20space/file%20one.md)"
        self.assertEqual(gaps.status(link, REPO, files), gaps.PRESENT)

    def test_a_ref_may_carry_a_slash(self):
        self.assertEqual(gaps.status(
            "[a](https://github.com/natb1/CanonDB/blob/release/1.0/tools/a.py)", REPO, FILES),
            gaps.PRESENT)
        self.assertEqual(gaps.status(
            "[t](https://github.com/natb1/CanonDB/tree/feature/x/tools)", REPO, FILES),
            gaps.PRESENT)
        self.assertEqual(gaps.status(
            "[b](https://github.com/natb1/CanonDB/blob/feature/x/b.py)", REPO, FILES),
            gaps.ABSENT)

    def test_the_repository_from_its_remote(self):
        for remote in ("https://github.com/natb1/my.repo.git", "git@github.com:natb1/my.repo.git",
                       "https://github.com/natb1/my.repo/", "https://github.com/natb1/my.repo"):
            self.assertEqual(gaps.repo_of(remote), "natb1/my.repo", remote)
        self.assertEqual(gaps.repo_of("https://github.com/natb1/CanonDB"), "natb1/CanonDB")


if __name__ == "__main__":
    unittest.main()
