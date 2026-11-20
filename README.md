# principal

A Claude Code plugin: the principal's entry points over a hypomnemata notebook and the canon it
feeds. Canon is the source of truth: the root question, [`canon/ti-esti.md`](canon/ti-esti.md),
and every answer merged since. Failing canon, the notebook is the `canondb` project of
[Hypomnemata — merged v1](https://claude.ai/code/artifact/b700cd97-fc03-4060-836e-e2557e2dcfd3),
the one notebook every project is kept in, whose applications name every file here. This README is a projection of the two. It says what the
plugin is for, as the root states it, and how the plugin is installed, which neither says.

## What it is for

The end, as the root's hinge states it: that what the AI does on the user's behalf is what the
user would have it do, across sessions, because the AI would do it with nothing in its context
pushing it there; that the conditions on which the two work can be read in the record they keep;
and that the condition on which the user keeps the AI can be tested there, off what was agreed
and off what comes back when a question is put again, never off either party's report.

The method: the record is read whenever an answer is admitted and whenever a model or the
answers above a question change. The readings are counts: how many answers the AI has drawn to
each question and whether they agree, which clauses were settled by the user's word rather than
reached by the AI and whether later draws hold them, and which answers are due to be drawn
again. Each is read against the last reading and never as a verdict on either party, and one
thing changes at a time.

What it depends on: the user keeps an AI as a vendor, kept as a means and on condition. Its terms
are stated and can be read, the user pays for it rather than being sold by it to a third party,
its reasoning is not captured by an interest that is not the user's, and it can be left while
others compete to supply the same. That condition is set in a notebook of the user's own, which
is private, and this record is where it is tested.

## The entry points and the readings

Six entry points, each a grant of what a turn may carry. `/principal:dictate` changes the notebook, and may draw the change with the principal first as
a line of questions whose admissions are compacted into the plan. `/principal:bootstrap` builds
what the notebook describes ahead of canon. `/principal:consult` takes a situation in the user's
words and returns the clauses and cases that bear on it, reading only and drawing nothing.
`/principal:anticipate` drafts the user's own answer to a question from the record, each source
quoted, for the user to confirm or correct. `/principal:interview` puts a question the principal
answers, or the project's end, to the user through a questioner that has read nothing of the
notebook, keeps a line doc of admissions, and hands over to a comparing run the user runs.
`/principal:sit` is the one session that speaks with the principal. It states no goal of its
own: it serves that portion of the principal's rule of life that can be delegated to the AI, and
is meant to be a projection of the AI's graph, which a line of questions builds; most of it is a
stopgap built from the principal's words until that graph covers it. It puts questions to the
AI's own record in clean turns, each a run of the harness of its own that `tools/clean_turn.py`
starts in an empty directory with no tools, settings, memory or rules file, holding the AI's own
earlier answers, each under the question it was given to, written by `tools/packet.py`, and one
question. It
puts one action at a time on its page, each question alone and sealed by a clean reader before it
is put and graded after, writes its own line doc and never the notebook, and hands every write to
the notebook to a job on the board. It runs confined, in a session started as the interviewer
kind, or open, in an ordinary session that may also brief helpers for building.

The sitting's work is done by helpers of fixed kinds, defined under `agents/`: `clean-reader`
(seals the notebook's answer to a question before it is put), `grader`, `fetcher`, `recorder`
(writes the notebook from rows files), `reviewer`, `checker`, `comparer` (holds both records and
writes the user's side only), `ai-recorder` (writes the AI's own record only) and `coordinator`
(runs the board), with `interviewer` the kind of the speaking session. The clean turns' system
prompts are under `clean/`, outside `agents/`, so that no session starts one as a helper. Four gates under `hooks/`, sharing
`hooks/kinds.py`, hold each kind to its work and decide nothing for any other turn:
`notebook-gate.py` refuses every helper but the recorder a write to the notebook, the comparer
and the AI's recorder aside, each held to inserts on its own side of it,
`reader-gate.py` confines the clean reader's reads to the sitting's questions, `kind-bash-gate.py`
confines each kind's shell to the tools its work needs, and `kind-write-gate.py` confines each
kind's file writes to its own scratch. `tools/board.py` is the gate on the board of jobs, a
writing mode printing a batch for the session to send, and `tools/views.py` lifts the whole-tab
reads out of a helper's transcript, one file each. `tools/lines.py` reads an export of the
page's open lines: it checks them, flags those whose anchored sentences moved, sweeps the few an
answer may bear on, orders them by the share they carry, their pressure and what they hold up,
picks the week's lines of least weight, and prints the writes for the session to send; it closes
a line only by the user's sentence quoted, and merges or drops one only at the user's word.
`tools/predictions.py` prints the words of a failed prediction's divergence note, refusing a
grade or a direction outside its lists, and reads those notes back from a graph and the notes
graded since: it tallies them by kind, grade and direction with the lessons that recur, and
stamps the tally with a fingerprint that a seal of the speaker's own must end with.
`tools/hinges.py` places a line's answer of record with its presuppositions as hinges, each
unjustified until a later answer of the AI's is linked to it, and lists every unjustified hinge
of the AI's graph with the builds that rest on it.

The readings are projections over the record, computed and stored nowhere: `tools/frontier.py`
(the frontier, and with `--principal` the questions only the user can answer whose lineage has
landed), `tools/again.py` (the answers due again), `tools/drift.py` (the drift count),
`tools/due.py` (what is due and why: an answer due again, a deadlocked clause a later draw gave
way on, a pending or suspended clause, a question past its backstop, and an upstream that moved
past the rev the hinge's provenance records it read at, or whose rev is not recorded), and
`tools/project.py --pressure` (the pressure stored beside the one the record derives where none
is). `tools/registry.py export` is one more, written to a file: every party's works, each
under the key prose cites it by, which a repository's check reads in place of a registry of its
own. `tools/digest.py --project <p>` is another: a project's end and method, its words, its
clauses with their cues and its cases, as the instructions a Claude Project's sessions open
with. `tools/line.py check` reads a line doc's export against the graph: every admission cited
by a row of its plan, every row citing one, every tab a row names present. The notebook is its source: the file is exported again, never edited, and never committed by
the notebook's tooling. `tools/residue.py` lists what a line leaves open, the open notes the
graph holds, each with its kind and whose move it is, and counts them without driving the count
to nothing. `tools/shares.py` gives each principle the share of the root it carries, in equal parts unless pressure corrects them, and proposes arrangements that need less pressure; `tools/divergence.py` lists the data that contradicts a principle, each with the action that would resolve it; and `tools/crossing.py` reads the edges that run from one project to the entry of a later one, which is the derivation reading. `tools/public.py` writes the copy of the notebook that may be shown, Claude's graph whole and the user's as nodes and edges without words unless the user has marked a section as it now reads, and fails where a question put to Claude quotes what is masked; a likeness between an answer of Claude's and a masked one is agreement and fails nothing, and one between a tab the user marked and a masked tab is listed for the user to consider before the copy is made.

## Installing the plugin

The plugin is a marketplace named `canondb`, hosted in this repository, listing one plugin,
`principal`, by a relative path. Where a session runs decides how the plugin reaches it. The
manifest pins no `version`, so every install below tracks commits on `main`: a new commit is a
new version, and whatever refreshes the marketplace picks it up.

### Local sessions, including Remote Control

A Remote Control session runs on your machine with your machine's configuration, so it needs
nothing beyond the local setup. Two ways, either of which is enough:

- **User scope**, so the plugin is on in every project on the machine. Register the marketplace
  and install once:

  ```
  claude plugin marketplace add natb1/CanonDB
  claude plugin install principal@canondb
  ```

  Then turn on auto-update for `canondb` under **Marketplaces** in `/plugin`, or set it in
  `~/.claude/settings.json` directly — this is also the declarative form, the whole of what
  the two commands write:

  ```json
  {
    "extraKnownMarketplaces": {
      "canondb": {
        "source": { "source": "github", "repo": "natb1/CanonDB" },
        "autoUpdate": true
      }
    },
    "enabledPlugins": { "principal@canondb": true }
  }
  ```

  Claude Code clones a declared marketplace it has not seen and installs the enabled plugins
  from it at the next start, so a configuration manager may write this block instead of
  running the commands. Keep the file writable: Claude Code writes to it too.

- **Project scope**, so every collaborator who trusts the folder gets it: the same block in the
  project's `.claude/settings.json`. Claude Code applies a
  repository's marketplaces only after the workspace trust dialog, so this route is for
  interactive terminal sessions; `-p` runs need the folder trusted beforehand, and cloud
  sessions never show the dialog and ignore the block.

Either way the marketplace is a clone under `~/.claude/plugins/marketplaces/`, and with
`autoUpdate` on it is refreshed in the background after a session starts. A refresh that finds
new commits updates the plugin on disk; the next session loads it, or `/reload-plugins` does.

### Cloud sessions

A cloud session clones the repository fresh and never shows the trust dialog, so it does not
install plugins from `.claude/settings.json`, and nothing installed on your machine reaches it.
What it can load comes from the cloud environment: its setup script, which runs before Claude
Code starts and whose result is snapshotted, and its environment variables. The setup goes in
the environment, once, and serves every repository the environment is used with. Edit the
environment from the cloud environment menu in a session's title bar.

Claude Code clones a marketplace its user settings declare but the machine has not fetched at
session start, installs the enabled plugins from it, and loads them. So the setup script
declares the marketplace, and every new session clones `main` as it is that day: there is no
lag to manage. Two facts about the environment shape the rest of the script:

- **Environment variables are not set while the setup script runs**, so anything the script
  needs must be in the script itself.
- **Claude Code's own `git` does not use the session proxy** that authenticates the shells'
  GitHub traffic. The repository is public, so the clone needs no credentials.

```sh
# Declare the marketplace and the plugin; Claude Code clones main at every session start.
mkdir -p ~/.claude
[ -f ~/.claude/settings.json ] || echo '{}' > ~/.claude/settings.json
tmp=$(mktemp)
jq '.extraKnownMarketplaces.canondb = {"source": {"source": "github", "repo": "natb1/CanonDB"}, "autoUpdate": true}
    | .enabledPlugins["principal@canondb"] = true' ~/.claude/settings.json > "$tmp"
mv "$tmp" ~/.claude/settings.json
```

A private fork needs more: a read-only token scoped to the fork alone, written into the system
git config by the same script, since Claude Code's own `git` finds no credentials otherwise.
Under the environment's variables, set

```
CLAUDE_CODE_SYNC_PLUGIN_INSTALL=1
```

so the first turn waits for the install rather than racing it. A new session then lists
`principal@canondb`, at the commit `main` was at when it started, with the `principal:`
skills and the plugin's agents available.

If the install fails, the reason is in the session's debug log at `/tmp/claude-code.log`, on the
line beginning `[reconcile] failed to install marketplace`.

Two other routes exist and are recorded here for completeness. An environment used only with
this repository can load the checkout in place with the environment variable
`CLAUDE_CODE_PLUGIN_DIRS=/home/user/CanonDB`, where the path is where the cloud runner clones the
session's repository; it fails on any other repository, and the path's casing follows the
runner, so confirm it with `pwd` in a session before setting the variable. And cloud sessions
load the plugins enabled on the claude.ai account they run under, as `principal@synced`, via
**Customize > Plugins**, **Add > Add marketplace**; in testing, a marketplace added that way did
not reach the account's enabled plugins.

### Working on the plugin itself

`claude --plugin-dir /path/to/CanonDB` loads a checkout for one session and takes precedence
over an installed copy of the same name. In a cloud session on this repository, the checkout is
at `/home/user/CanonDB` (as `pwd` shows it: the casing follows the runner), and the environment
variable `CLAUDE_CODE_PLUGIN_DIRS=/home/user/CanonDB`, set on the cloud environment, does the
same at startup.

## Using it in another project

[natb1/ordo](https://github.com/natb1/ordo) is one: a rule of life kept this way, whose notebook
is read and written through these entry points.

1. Install the plugin for the sessions you use, as above.

2. Create the project's configuration under `.principal/` at its root:

   - `notebook.json` — `{"artifact": "<Claude Docs artifact id>", "state_enum": "<enum id>"}`,
     the notebook the skills read and write. Make the document first; the enum holds the
     states `held · in thread · landed`, in that order, and its id is the document's. Where
     the document holds several projects, add `"project": "<its root's name>"`, the one this
     repository keeps, and, where that root was renamed after its canon landed,
     `"canon": {"<question id>": "<canon file name>"}`. Such a document keeps a `lease` tab at
     the top level, ordered last, with `## Leases` and `## Tooling` sections, which the skills
     read and write and the reader never takes for a question. For `/principal:sit`, add
     `"board": "<artifact address>"`: publish `web/board.html` once as a private artifact
     with the db capability and rules that let only its owner read and write, and put its
     address in this key; and `"page": "<artifact address>"`: publish `web/ordo.html` once the
     same way, with the db and user capabilities, and put its address in this key. Without a
     `page` a sitting runs with no page and says so. Once the AI's own record has a root tab,
     add `"ai_root": ["<its node id>", "<the node id of each tab under it>", …]`; until then the
     AI's recorder is refused every write.
   - `bootstrap.json` — `{"applications": []}`, the manifest `/principal:bootstrap` keeps.

3. Write the root question under `canon/`. Canon is what is under that directory, and nothing
   lists it; a clean turn reads none of it, only the packet it is handed.

4. Open a session and run `/principal:dictate` with the first dictation. The skills call the
   plugin's tools by `${CLAUDE_PLUGIN_ROOT}/tools/…`; Python 3 is the requirement, and `/principal:sit` needs `jq`
   as well.

## Tests

```
cd tools && python3 -m unittest
```
