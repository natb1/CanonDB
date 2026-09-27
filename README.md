# principal

A Claude Code plugin: the principal's entry points over a **hypomnemata** notebook and the
**canon** it feeds. The notebook is a shared Claude Docs document, one tab per question, in
the layout `tools/hypo/render.py` writes and `tools/hypo/read.py` reads back. Canon is what
has landed on `main`: the root question, and every answer merged since.

The repository is the plugin. It is also the first project that uses it: `ti-esti.md` is this
project's root question, and `.principal/` is this project's configuration.

## What the plugin holds

| path | what |
|---|---|
| `skills/dictate/` | `/principal:dictate <dictation>` — change the notebook |
| `skills/ask/` | `/principal:ask [question]` — put the next question to the AI in a clean context |
| `skills/bootstrap/` | `/principal:bootstrap [dictation]` — reconcile application from the notebook ahead of canon |
| `agents/canon-answer.md` | the canon agent: Read and nothing else, launched only by `/principal:ask` |
| `hooks/canon-gate.py` | a PreToolUse gate on Read that fires for the canon agent alone and admits canon and the packet |
| `tools/` | the notebook tooling: model, spec, renderer, page read, reader, writer, page check, projections, frontier, lineage |

Two flows reach `main`:

- **strict** — `/principal:dictate` → notebook → `/principal:ask` → thread → merged pull request
  → canon → the asynchronous workflows that reconcile application from canon;
- **bootstrap** — `/principal:dictate` → notebook → `/principal:bootstrap` → pull request the
  author merges. Timelier and less strict: what it builds is a postulate, recorded in
  `.principal/bootstrap.json`, and canon supersedes it when it reconciles the same application.

There is one standing branch, `main`; every other branch is a pull request's. What a turn may
carry is decided by the entry point that runs it — a skill, an agent, a gate — never by a branch.

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
  project's `.claude/settings.json`, as this repository carries. Claude Code applies a
  repository's marketplaces only after the workspace trust dialog, so this route is for
  interactive terminal sessions; `-p` runs need the folder trusted beforehand, and cloud
  sessions never show the dialog and ignore the block.

Either way the marketplace is a clone under `~/.claude/plugins/marketplaces/`, and with
`autoUpdate` on it is refreshed in the background after a session starts. A refresh that finds
new commits updates the plugin on disk; the next session loads it, or `/reload-plugins` does.

### Cloud sessions

A cloud session clones the repository fresh and never shows the trust dialog, so it does not
install plugins from `.claude/settings.json`, and nothing installed on your machine reaches it.
It does read the user settings of the environment it runs in, and a marketplace those settings
declare but the machine has not fetched is cloned at session start, its enabled plugins
installed, and the plugin set reloaded. So the cloud environment's **setup script** declares
the marketplace and nothing more. Edit the environment from the cloud environment menu in a
session's title bar:

```sh
mkdir -p ~/.claude
[ -f ~/.claude/settings.json ] || echo '{}' > ~/.claude/settings.json
tmp=$(mktemp)
jq '.extraKnownMarketplaces.canondb = {"source": {"source": "github", "repo": "natb1/CanonDB"}, "autoUpdate": true}
    | .enabledPlugins["principal@canondb"] = true' ~/.claude/settings.json > "$tmp"
mv "$tmp" ~/.claude/settings.json
```

and, under the environment's variables, so the first turn waits for the install:

```
CLAUDE_CODE_SYNC_PLUGIN_INSTALL=1
```

The script must not run `claude plugin marketplace add` itself: the setup script runs before
the session's GitHub proxy is attached, so a private repository cannot be cloned there. Inside
the session the proxy authenticates the clone, and because the setup snapshot holds only the
declaration, every new session clones `main` as it is that day and installs the plugin at that
commit. There is no lag to manage.

For an environment used only with this repository, an environment variable loads the checkout
in place at startup instead, so the session runs the branch it checked out:

```
CLAUDE_CODE_PLUGIN_DIRS=/home/user/CanonDB
```

Do not set it on an environment used with other repositories: the path is absent there and
Claude Code reports a plugin that did not load at every start.

Cloud sessions also load the plugins enabled on the claude.ai account they run under, synced
at session start as `principal@synced`, which would make the setup unnecessary: **Customize >
Plugins**, then **Add > Add marketplace**, `natb1/CanonDB`, with **Sync automatically** on, then
add the `principal` plugin from the listing. In testing, a marketplace added that way did not
reach the account's enabled plugins, so this route is recorded but not relied on.

### Working on the plugin itself

`claude --plugin-dir /path/to/CanonDB` loads a checkout for one session and takes precedence
over an installed copy of the same name. In a cloud session on this repository, the checkout is
at `/home/user/CanonDB`, and the environment variable `CLAUDE_CODE_PLUGIN_DIRS=/home/user/CanonDB`,
set on the cloud environment, does the same at startup.

## Using it in another project

1. Install the plugin for the sessions you use, as above.

2. Create the project's configuration under `.principal/` at its root:

   - `notebook.json` — `{"artifact": "<Claude Docs artifact id>", "state_enum": "<enum id>"}`,
     the notebook the skills read and write. Make the document first; the enum holds the
     states `held · in thread · landed`, in that order, and its id is the document's.
   - `canon` — the paths that count as canon on disk, one per line relative to the root. Start
     with the root question's file alone; the list grows only when an answer is promulgated.
   - `bootstrap.json` — `{"applications": []}`, the manifest `/principal:bootstrap` keeps.

3. Write the root question at the root of the project and list it in `.principal/canon`. It
   is the only file a canon turn may read until an answer lands.

4. Open a session and run `/principal:dictate` with the first dictation. The skills call the
   plugin's tools by `${CLAUDE_PLUGIN_ROOT}/tools/…`; Python 3 is the only requirement.

## Migrating a project that used the patterns before the plugin

If a project carried its own copies under `.claude/` — skills named `principal-*`, a
`canon-answer` agent, a `canon-gate.py` hook, tooling under `hypomnemata/tools/` — the steps
are:

1. Install the plugin as above; remove the project's own copies of the skills, the agent and
   the hook, so that `/principal:dictate` resolves to the plugin's skill and not to a
   directory name. Remove the project's tooling too, unless it differs from the plugin's — a
   difference is a change to make in the plugin, by a pull request here.
2. Write `.principal/canon` from the hook's old `CANON` list, and `.principal/notebook.json`
   from whatever named the artifact before. Write `.principal/bootstrap.json` listing the
   applications already built from the notebook, with their files: those are postulates, and
   the manifest is what lets canon supersede them.
3. Keep `transcripts/` where it was: `tools/persist.py` writes to the project's root, and the
   notebook's provenance lines point there.
4. In the notebook, repoint every application link that named a branch to `main`, and every
   link into the old paths to the plugin's — a dictation, since the links are the notebook's.
5. Retire the old branch once its pull request is merged. Canon context is the agent's
   configuration, not a branch, so nothing is lost with it.

## Tests

```
cd tools && python3 -m unittest
```
