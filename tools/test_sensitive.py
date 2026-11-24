"""The sensitive-terms check: the convention gate's refusal of a
repository-bound text that matches the private list, its passes, a missing
list, and the audit of what already left (`sensitive.py`).

The list here is the neutral fixture `fixtures/sensitive.txt`: line 2 a
plain word, line 4 a regular expression, line 5 two words."""

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

from hypo import sensitive as listed
from support import fixture

HERE = os.path.dirname(os.path.abspath(__file__))
GATE = os.path.join(HERE, "..", "hooks", "convention-gate.py")
TOOL = os.path.join(HERE, "sensitive.py")
LIST = fixture("sensitive.txt")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.env = {k: v for k, v in os.environ.items()
                    if k not in ("CLAUDE_PROJECT_DIR", "CLAUDE_PLUGIN_ROOT", "CLAUDE_CONFIG_DIR",
                                 listed.ENV) and not k.startswith("GIT_")}
        self.env["HOME"] = os.path.join(self.tmp, "home")
        os.makedirs(self.env["HOME"])
        self.env.update(GIT_CONFIG_NOSYSTEM="1", GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@x",
                        GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@x")
        self.env[listed.ENV] = LIST
        self.repo = os.path.join(self.tmp, "repo")
        os.makedirs(self.repo)
        self.git("init", "-q", "-b", "main")

    def git(self, *args):
        done = subprocess.run(["git"] + list(args), cwd=self.repo, capture_output=True,
                              text=True, env=self.env, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        return done.stdout

    def put(self, name, words):
        with open(os.path.join(self.repo, name), "w", encoding="utf-8") as fh:
            fh.write(words)

    def gate(self, call, cwd=None):
        call = dict(call)
        call.setdefault("cwd", cwd or self.repo)
        done = subprocess.run([sys.executable, "-B", GATE], input=json.dumps(call).encode(),
                              capture_output=True, env=self.env, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout)

    def bash(self, command, cwd=None):
        return self.gate({"tool_name": "Bash", "tool_input": {"command": command}}, cwd)

    def denied(self, got):
        out = got.get("hookSpecificOutput", {})
        self.assertNotEqual(out.get("permissionDecision"), "allow")
        return out.get("permissionDecision") == "deny" and out["permissionDecisionReason"]

    def context(self, got):
        out = got.get("hookSpecificOutput", {})
        self.assertNotIn("permissionDecision", out)
        return out.get("additionalContext", "")


class ListTest(unittest.TestCase):
    def test_plain_words_and_expressions(self):
        p = listed.load({listed.ENV: LIST})
        self.assertEqual([x.line for x in p.patterns], [2, 4, 5])
        self.assertEqual(listed.matches(p, "An ALPHA-SECRET here"), [2])
        self.assertEqual(listed.matches(p, "xalpha-secret"), [])
        self.assertEqual(listed.matches(p, "beta-123 and beta-12"), [4])
        self.assertEqual(listed.matches(p, "beta-12"), [])
        self.assertEqual(listed.matches(p, "gamma\n  Delta"), [5])
        self.assertEqual(listed.matches(p, "# A neutral list"), [])

    def test_where_it_lives(self):
        self.assertEqual(listed.path({"HOME": "/h"}),
                         os.path.realpath("/h/.claude") + "/principal/sensitive.txt")
        self.assertEqual(listed.path({"HOME": "/h", "CLAUDE_CONFIG_DIR": "/c"}),
                         os.path.realpath("/c") + "/principal/sensitive.txt")
        self.assertEqual(listed.path({"HOME": "/h", listed.ENV: "/l"}), "/l")
        self.assertIsNone(listed.load({listed.ENV: "/nonexistent/list"}))

    def test_a_broken_expression_is_counted(self):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
            fh.write("re:([open\nalpha-secret\n")
        self.addCleanup(os.unlink, fh.name)
        p = listed.load({listed.ENV: fh.name})
        self.assertEqual(p.broken, [1])
        self.assertEqual([x.line for x in p.patterns], [2])

    def test_added_lines(self):
        diff = ("diff --git a/f b/f\n--- a/f\n+++ b/f\n@@ -1,0 +3,2 @@\n+one\n+two\n"
                "@@ -9 +11 @@\n-old\n+new\n")
        self.assertEqual([(a.file, a.line, a.text) for a in listed.added_lines(diff)],
                         [("f", 3, "one"), ("f", 4, "two"), ("f", 11, "new")])


class GateTest(Base):
    def test_every_message_bound_for_a_repository(self):
        for command in ("git commit -m 'Note the alpha-secret'",
                        "git commit -m 'one' -m 'Beta-123 two'",
                        "git commit -F - <<'EOF'\ngamma\ndelta\nEOF",
                        "git tag -a v1 -m 'alpha-secret'",
                        "git notes add -m 'alpha-secret'",
                        "git merge --no-ff -m 'alpha-secret' topic",
                        "gh pr create --title t --body 'alpha-secret'",
                        "gh pr edit 3 --title 'alpha-secret'",
                        "gh pr comment 3 -b 'alpha-secret'",
                        "gh pr review 3 --approve -b 'alpha-secret'",
                        "gh issue create -t 'alpha-secret' -b x",
                        "gh issue comment 3 -b 'alpha-secret'",
                        "gh release create v1 --notes 'alpha-secret'",
                        "cd sub && gh release edit v1 --notes 'alpha-secret'"):
            reason = self.denied(self.bash(command))
            self.assertTrue(reason, command)
            self.assertIn("pattern on line", reason)
            self.assertIn(LIST, reason)
            self.assertNotIn("alpha-secret", reason.lower(), command)
            self.assertNotIn("beta-", reason.lower(), command)
            self.assertIn("Restate it without", reason)

    def test_a_body_file_names_the_line(self):
        body = os.path.join(self.tmp, "body.md")
        with open(body, "w") as fh:
            fh.write("Clean words.\nThen beta-777.\n")
        reason = self.denied(self.bash("gh pr create --title t --body-file %s" % body))
        self.assertIn("pattern on line 4", reason)
        self.assertNotIn("777", reason)

    def test_a_staged_file(self):
        self.put("notes.txt", "one\ntwo alpha-secret\n")
        self.git("add", "notes.txt")
        reason = self.denied(self.bash("git commit -m 'Add notes'"))
        self.assertIn("notes.txt line 2 (staged): pattern on line 2", reason)
        self.assertNotIn("alpha-secret", reason)
        # from elsewhere, by -C and by a cd earlier in the line
        self.assertTrue(self.denied(self.bash("git -C %s commit -m x" % self.repo, cwd=self.tmp)))
        self.assertTrue(self.denied(self.bash("cd %s && git commit -m x" % self.repo,
                                              cwd=self.tmp)))

    def test_what_is_not_yet_staged(self):
        self.put("a.txt", "clean\n")
        self.git("add", "a.txt")
        self.git("commit", "-q", "-m", "first")
        self.put("a.txt", "clean\nalpha-secret\n")
        # not staged and not taken: the commit carries none of it
        self.assertEqual(self.bash("git commit -m 'Second'"), {})
        for command in ("git commit -am 'Second'", "git commit -a -m 'Second'",
                        "git commit --all -m 'Second'", "git commit -m 'Second' a.txt",
                        "git commit -m 'Second' -- a.txt"):
            reason = self.denied(self.bash(command))
            self.assertIn("a.txt line 2 (not yet staged)", reason, command)
        self.git("add", "a.txt")
        self.assertIn("(staged)", self.denied(self.bash("git commit --amend --no-edit")))

    def test_clean_writes_and_reads_pass(self):
        self.put("a.txt", "clean\n")
        self.git("add", "a.txt")
        self.assertEqual(self.bash("git commit -m 'Add a clean file'"), {})
        for read in ("git log --grep alpha-secret", "gh pr view 3 --comments",
                     "gh search issues alpha-secret", "echo alpha-secret",
                     "grep -r alpha-secret .", "git tag -l 'alpha-secret*'",
                     "git merge alpha-secret-branch", "gh api repos/x/y -q alpha-secret"):
            self.assertEqual(self.bash(read), {}, read)

    def test_the_private_notebook_and_page_are_not_held(self):
        for call in ({"tool_name": "mcp__claude_ai_Claude_Docs__update",
                      "tool_input": {"container": {"kind": "project", "id": "x"},
                                     "ref": {"object": "node", "id": "g-01"},
                                     "payload": "A row on the alpha-secret."}},
                     {"tool_name": "ArtifactData",
                      "tool_input": {"action": "set", "collection": "ordo", "doc_id": "c",
                                     "data": {"text": "alpha-secret"}}}):
            got = self.gate(call)
            self.assertFalse(self.denied(got))
            self.assertNotIn("sensitive", json.dumps(got))

    def test_a_missing_list_is_said_and_never_refuses(self):
        self.env[listed.ENV] = os.path.join(self.tmp, "none.txt")
        got = self.bash("git commit -m 'alpha-secret'")
        said = self.context(got)
        self.assertIn("had no list to read", said)
        self.assertIn(os.path.join(self.tmp, "none.txt"), said)
        # a read is still no business of the check
        self.assertEqual(self.bash("git log"), {})

    def test_the_default_place(self):
        del self.env[listed.ENV]
        self.assertIn(os.path.join(os.path.realpath(self.env["HOME"]), ".claude", "principal",
                                   "sensitive.txt"),
                      self.context(self.bash("git commit -m x")))
        where = os.path.join(self.env["HOME"], ".claude", "principal")
        os.makedirs(where)
        shutil.copyfile(LIST, os.path.join(where, "sensitive.txt"))
        self.assertTrue(self.denied(self.bash("git commit -m 'alpha-secret'")))

    def test_a_broken_line_is_said(self):
        broken = os.path.join(self.tmp, "broken.txt")
        with open(broken, "w") as fh:
            fh.write("alpha-secret\nre:([open\n")
        self.env[listed.ENV] = broken
        self.assertIn("Line(s) 2", self.context(self.bash("git commit -m clean")))
        self.assertIn("pattern on line 1", self.denied(self.bash("git commit -m alpha-secret")))

    def test_held_where_the_project_names_a_notebook(self):
        project = os.path.join(self.tmp, "project")
        os.makedirs(os.path.join(project, ".principal"))
        with open(os.path.join(project, ".principal", "notebook.json"), "w") as fh:
            json.dump({"artifact": "x"}, fh)
        got = self.bash("git commit -m 'alpha-secret'", cwd=project)
        self.assertIn("pattern on line 2", self.denied(got))
        # no brief installed: the convention check says so, and nothing else is refused
        self.assertIn("went unchecked", self.context(self.bash("git commit -m ok", cwd=project)))


class AuditTest(Base):
    def tool(self, *args, code):
        done = subprocess.run([sys.executable, "-B", TOOL] + list(args), cwd=self.repo,
                              capture_output=True, text=True, env=self.env, timeout=60)
        self.assertEqual(done.returncode, code, done.stdout + done.stderr)
        self.assertNotIn("alpha-secret", done.stdout + done.stderr)
        self.assertNotIn("beta-5", done.stdout + done.stderr)
        return done.stdout

    def test_a_commit_range(self):
        self.put("a.txt", "clean\n")
        self.git("add", "a.txt")
        self.git("commit", "-q", "-m", "first")
        base = self.git("rev-parse", "HEAD").strip()
        self.put("a.txt", "clean\nalpha-secret\n")
        self.git("commit", "-q", "-am", "second")
        self.put("a.txt", "clean\n")
        self.git("commit", "-q", "-am", "third, beta-555")
        out = self.tool("range", base + "..HEAD", code=1)
        second = self.git("rev-parse", "HEAD~1").strip()[:12]
        third = self.git("rev-parse", "HEAD").strip()[:12]
        self.assertIn("commit %s a.txt:2: pattern on line 2" % second, out)
        self.assertIn("commit %s message: pattern on line 4" % third, out)
        self.assertEqual(self.tool("range", "HEAD~2", "-C", self.repo, code=0), "")
        self.tool("range", "nonexistent..HEAD", code=2)

    def test_text_where_and_a_missing_list(self):
        self.put("x.md", "ok\nGamma delta\n")
        self.assertEqual(self.tool("text", "x.md", code=1), "x.md:2: pattern on line 5\n")
        self.assertEqual(self.tool("where", code=0).strip(), LIST)
        self.env[listed.ENV] = os.path.join(self.tmp, "none.txt")
        self.tool("text", "x.md", code=2)

    def test_a_pull_request(self):
        bin_dir = os.path.join(self.tmp, "bin")
        os.makedirs(bin_dir)
        view = {"title": "Clean title", "body": "Body with alpha-secret",
                "comments": [{"body": "fine"}, {"body": "beta-555"}],
                "reviews": [{"body": ""}],
                "commits": [{"oid": "abcdef1234567890", "messageHeadline": "Clean",
                             "messageBody": "gamma delta"}]}
        inline = [[{"path": "f.py", "body": "ALPHA-SECRET"}]]
        diff = "diff --git a/f.py b/f.py\n--- a/f.py\n+++ b/f.py\n@@ -0,0 +1,2 @@\n+ok\n+beta-555\n"
        script = os.path.join(bin_dir, "gh")
        with open(script, "w") as fh:
            fh.write("#!%s\nimport sys, json\na = sys.argv[1:]\n" % sys.executable
                     + "if a[:2] == ['pr', 'view']: print(json.dumps(%r))\n" % view
                     + "elif a[:2] == ['pr', 'diff']: sys.stdout.write(%r)\n" % diff
                     + "elif a[0] == 'api': print(json.dumps(%r))\n" % inline
                     + "else: sys.exit(3)\n")
        os.chmod(script, os.stat(script).st_mode | stat.S_IEXEC)
        self.env["PATH"] = bin_dir + os.pathsep + self.env.get("PATH", "")
        out = self.tool("pr", "7", "--repo", "o/n", code=1).splitlines()
        self.assertEqual(sorted(out), sorted([
            "body: pattern on line 2",
            "comment 2: pattern on line 4",
            "commit abcdef123456 message: pattern on line 5",
            "review comment 1 (f.py): pattern on line 2",
            "f.py:2 (diff): pattern on line 4"]))


if __name__ == "__main__":
    unittest.main()
