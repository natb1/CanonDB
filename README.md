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
| `tools/` | the notebook tooling: model, spec, renderer, reader, writer, page check, projections, frontier, lineage |

Two flows reach `main`:

- **strict** — `/principal:dictate` → notebook → `/principal:ask` → thread → merged pull request
  → canon → the asynchronous workflows that reconcile application from canon;
- **bootstrap** — `/principal:dictate` → notebook → `/principal:bootstrap` → pull request the
  author merges. Timelier and less strict: what it builds is a postulate, recorded in
  `.principal/bootstrap.json`, and canon supersedes it when it reconciles the same application.

There is one standing branch, `main`; every other branch is a pull request's. What a turn may
carry is decided by the entry point that runs it — a skill, an agent, a gate — never by a branch.

## Using it in another project

1. Add the marketplace and install the plugin:

   ```
   claude plugin marketplace add natb1/CanonDB
   claude plugin install principal@canondb
   ```

   or, so every collaborator gets it, put in the project's `.claude/settings.json`:

   ```json
   {
     "extraKnownMarketplaces": {
       "canondb": { "source": { "source": "github", "repo": "natb1/CanonDB" } }
     },
     "enabledPlugins": { "principal@canondb": true }
   }
   ```

   To work on the plugin itself, `claude --plugin-dir /path/to/CanonDB` loads it from a checkout.

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
