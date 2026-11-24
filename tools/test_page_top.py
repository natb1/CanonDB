"""The page's one button: at its foot, after the last section, a real button
with a plain label that goes back to the top (smoothly, at once under reduced
motion) and moves focus to the main landmark. It reads no data, so it is wired
while the store is absent, slow or empty. The behaviour runs in node against a
stubbed document and window; skipped where node is not installed."""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

import test_sit_skill as sit

HARNESS = r"""
const fs = require("fs"), vm = require("vm");
const [script, scenarios] = process.argv.slice(2).map((a, i) =>
  i === 0 ? fs.readFileSync(a, "utf8") : JSON.parse(fs.readFileSync(a, "utf8")));
function run(sc) {
  const out = { scrolls: [], focus: [], media: [], writes: [] };
  const els = {};
  function node(id) {
    return { id, children: [], hidden: false, attrs: {}, className: "", _text: "",
      appendChild(c) { this.children.push(c); return c; },
      removeChild(c) { this.children.splice(this.children.indexOf(c), 1); },
      setAttribute(k, v) { this.attrs[k] = String(v); },
      get firstChild() { return this.children[0] || null; },
      get textContent() { return this._text + this.children.map(c => c.textContent).join(""); },
      set textContent(t) { this._text = String(t); this.children = []; },
      focus(o) { out.focus.push({ id: this.id, preventScroll: !!(o && o.preventScroll) }); } };
  }
  const document = {
    getElementById(id) { return els[id] || (els[id] = node(id)); },
    createElement() { return node(null); },
    createTextNode(t) { const n = node(null); n._text = String(t); return n; },
  };
  const window = {
    scrollTo(o) { out.scrolls.push(o); },
    matchMedia(q) { out.media.push(q); return { matches: !!sc.reduce && q === "(prefers-reduced-motion: reduce)" }; },
  };
  const subs = {};
  const db = { doc(path) { return { onSnapshot(cb) { subs[path] = cb; return () => {}; } }; } };
  if (sc.store === "slow") window.claude = { use: () => new Promise(() => {}) };
  if (sc.store === "empty") window.claude = { use: async () => db };
  const sandbox = { document, window, Date, JSON, Math, Object, Array, String, Number, isNaN,
    console, setTimeout: () => 0, clearTimeout: () => {}, setInterval: () => 0, Promise };
  vm.createContext(sandbox);
  vm.runInContext(script, sandbox);
  return new Promise(r => setImmediate(r)).then(() => {
    const none = { exists: false, data: () => undefined, metadata: { fromCache: false } };
    if (sc.store === "empty") Object.values(subs).forEach(cb => cb(none));
    const top = els.top;
    out.wired = !!(top && typeof top.onclick === "function");
    if (out.wired) top.onclick();
    return out;
  });
}
(async () => { const res = {}; for (const [k, sc] of Object.entries(scenarios)) res[k] = await run(sc);
  process.stdout.write(JSON.stringify(res)); })();
"""


class TopButtonMarkupTest(unittest.TestCase):
    """The button as the source gives it."""

    @classmethod
    def setUpClass(cls):
        with open(sit.PAGE, encoding="utf-8") as fh:
            cls.page = fh.read()
        cls.style = cls.page[cls.page.index("<style>"):cls.page.index("</style>")]

    def test_it_is_one_real_button_with_a_plain_label(self):
        buttons = re.findall(r"<button\b[^>]*>(.*?)</button>", self.page, re.S)
        self.assertEqual(buttons, ["Back to top"])
        self.assertIn('<button type="button" class="top" id="top">', self.page)

    def test_it_sits_after_the_last_section_in_the_flow(self):
        at = self.page.index('id="top"')
        self.assertGreater(at, self.page.index("</main>"))
        self.assertLess(at, self.page.index("<script>"))
        rule = re.search(r"\.top \{([^}]*)\}", self.style).group(1)
        self.assertNotIn("position", rule)
        self.assertNotIn("position", re.search(r"\.foot \{([^}]*)\}", self.style).group(1))

    def test_it_is_styled_by_the_page_s_tokens_with_a_comfortable_target(self):
        rule = re.search(r"\.top \{([^}]*)\}", self.style).group(1)
        for words in ("min-height: 44px", "var(--surface)", "var(--line)", "var(--accent)",
                      "var(--display)"):
            self.assertIn(words, rule)
        self.assertNotRegex(rule, r"#[0-9a-fA-F]{3,6}\b")
        self.assertIn(".top:focus-visible", self.style)

    def test_its_focus_target_is_the_main_landmark(self):
        self.assertIn('<main id="main" tabindex="-1">', self.page)


class TopButtonBehaviourTest(unittest.TestCase):
    """The button's click, run in node, with the store absent, slow or empty."""

    @classmethod
    def setUpClass(cls):
        node = shutil.which("node")
        if not node:
            sys.stderr.write("\n*** TopButtonBehaviourTest SKIPPED: node is not installed; run "
                             "again under `nix shell nixpkgs#nodejs` ***\n")
            raise unittest.SkipTest("node is not installed")
        with open(sit.PAGE, encoding="utf-8") as fh:
            page = fh.read()
        script = page[page.index("<script>") + len("<script>"):page.index("</script>")]
        scenarios = {"none": {}, "slow": {"store": "slow"}, "empty": {"store": "empty"},
                     "still": {"reduce": True}}
        with tempfile.TemporaryDirectory() as tmp:
            paths = []
            for name, data in (("page.js", script), ("scenarios.json", json.dumps(scenarios)),
                               ("harness.js", HARNESS)):
                with open(os.path.join(tmp, name), "w", encoding="utf-8") as fh:
                    fh.write(data)
                paths.append(os.path.join(tmp, name))
            run = subprocess.run([node, paths[2]] + paths[:2], capture_output=True, text=True,
                                 timeout=60, env=dict(os.environ, TZ="UTC"))
        if run.returncode:
            raise AssertionError(run.stderr)
        cls.res = json.loads(run.stdout)

    def test_it_is_wired_whatever_the_store(self):
        for name in ("none", "slow", "empty"):
            self.assertTrue(self.res[name]["wired"], name)

    def test_it_scrolls_to_the_top_smoothly(self):
        for name in ("none", "slow", "empty"):
            self.assertEqual(self.res[name]["scrolls"], [{"top": 0, "behavior": "smooth"}], name)

    def test_under_reduced_motion_it_goes_at_once(self):
        self.assertIn("(prefers-reduced-motion: reduce)", self.res["still"]["media"])
        self.assertEqual(self.res["still"]["scrolls"], [{"top": 0, "behavior": "auto"}])

    def test_it_moves_focus_to_the_main_landmark(self):
        for name in ("none", "slow", "empty", "still"):
            self.assertEqual(self.res[name]["focus"], [{"id": "main", "preventScroll": True}], name)


if __name__ == "__main__":
    unittest.main()
