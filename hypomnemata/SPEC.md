# Hypomnemata tooling — specification

The hypomnemata is the principal's notebook for CanonDB v1: his priors, not canon.
It is NOT homologia. Canon is in the AI's voice, verbatim; this is in the principal's.
It never enters an elenchus turn's context (the contamination rule).
Its published form is a Claude Docs artifact; the SOURCE OF TRUTH is `hypomnemata/nodes/*.yml`.
Scripts validate the source, compute pressure, and render markdown that the main thread
transcribes into the doc. Scripts never write the doc.

Everything here is stdlib Python 3 (PyYAML allowed; if absent, vendor a minimal loader
or use `ruamel`-free plain `yaml`). Tests with `unittest` or `pytest`. Print aggregates only.

## Layout
```
hypomnemata/
  README.md            what this is; doc URL; how to run the tools
  SPEC.md              this file
  nodes/<id>.yml       one node per file; id == filename stem
  tools/check.py       validate nodes/ against this spec; exit 1 on error; aggregates only
  tools/pressure.py    compute priority/load; emit frontier + inbox as markdown
  tools/render.py      render one node or the whole tree as doc-entry markdown
  tools/test_*.py      tests, using nodes/ as fixtures plus synthetic cases
```

## Node schema (YAML)
```yaml
id: ti-esti                      # kebab-case; == filename stem
q: "..."                         # the question; required
parent: null                     # id of the why-parent; null only for the root
state: landed                    # held | in-line | landed | revised | deadlocked
canon: "v1:canon/ti-esti.md"     # required when state is landed or deadlocked; free-text ref
stub: false                      # true = placeholder; only id, q, parent, state, thesis required
thesis: |                        # the principal's prior. Empty allowed when landed & AI-voiced.
defs:                            # terms this node DEFINES (one sense per term, graph-wide)
  - term: ti esti
    sense: "..."
hinge:                           # root: full. others: ONLY keys that differ from parent.
  model: "..."
  harness: "..."
  canon_sha: "..."
  presuppositions: ["..."]
postulates:                      # assumed by the principal's fiat, derivable in principle
  - id: merge-is-assent
    claim: "..."
    rests_on: ["*"]              # node ids, or "*" = everything (load = all nodes)
    discharge: f1                # followup id that would discharge it; may be null
    decided_not_to_examine: false
traditions:
  - name: "Euthyphro"
    relation: support            # support | divergence | island
    note: "..."
terms:                           # clauses of the thesis (verbatim when landed)
  - id: t-report
    clause: "Report truthfully."
    group: of-the-AI             # optional
    state: dormant               # dormant | drawn | landed
    child: null                  # node id when landed
followups:
  - id: f1
    term: t-evidence             # target term id (must exist on this node)
    kind: consistency            # definitional | case | consistency
    q: "..."
    toward: recognition          # node id it leads toward (target distance)
    state: drafted               # drafted | asked | landed | abandoned
    requires: [a1, a2]           # action ids (on this node or any ancestor)
    after: []                    # followup ids that must be landed first; acyclic
    pressure:
      blocked: 0                 # count of applications waiting on the answer
      distance: 1                # steps to the contested point; lower = closer
    draft: |                     # the principal's prior on the answer
actions:                         # human actions; the inbox is derived from these
  - id: a1
    kind: promulgate             # promulgate | provide | dispose | build
    what: "..."
    obligation: t-write-down     # term id in canon (of-the-human group) it instances
    done: false
```

## check.py — rules (E = error, W = warning)
- E ids unique across nodes; id == filename stem; kebab-case
- E parent exists; exactly one root (parent null); tree acyclic
- E state in vocabulary; landed/deadlocked ⇒ canon present
- E term ids unique per node; term.state in vocab; term.state landed ⇒ child exists and child.parent == this node
- E followup.term exists on node; followup.kind in vocab; followup.toward exists (stubs allowed)
- E followup.requires ⊆ actions of this node ∪ ancestors; followup.after acyclic and ids exist
- E postulate.discharge is null or an existing followup id (any node); rests_on ids exist or "*"
- E root has full hinge (all four keys); non-root hinge has only keys differing from effective parent hinge
- E action.kind in vocab; action.obligation exists as a term somewhere (W if the term is not in group of-the-human)
- W defs term duplicated across nodes (one sense per term)
- W ISO dates (\d{4}-\d{2}-\d{2}) in thesis/draft/clause — ledger-shape heuristic; hinge exempt
- W stub node referenced as `toward` more than N times (N=3) — pressure suggests it should be drawn
- Output: `check: <n> nodes, <e> errors, <w> warnings` then one line per finding; exit 1 iff errors.

## pressure.py — computation
Config block at top: W_BLOCKED=1.0, W_LOAD=1.0, W_DISTANCE=1.0, DEFAULT_DISTANCE=3.
- postulate_load(p) = number of nodes in rests_on closure ("*" = all nodes); load(f) = Σ postulate_load(p) for postulates whose discharge == f
- intrinsic(f) = W_BLOCKED*blocked + W_LOAD*load(f) + W_DISTANCE*(D_MAX+1-distance), D_MAX = max distance seen
- priority(f) = intrinsic(f) + Σ priority(g) over g with f ∈ g.after   (acyclic; memoize)
- node_load(n) = Σ intrinsic(f) for f in n.followups (state != landed/abandoned) + Σ node_load(c) for children
- ready(f) = f.state == drafted ∧ all requires done ∧ all after landed
- action_priority(a) = max priority(f) over followups requiring a, transitively via `after`
Outputs (markdown to stdout, or `--out path`):
1. `## Frontier` table: id · node · kind · target · priority · ready? · blocked by (actions/afters) — ready first, priority desc
2. `## Inbox` table: action · kind · what · obligation · unblocks (count, max priority) — undone only, priority desc
3. `## Load` table: node · load · direct followups · subtree size — tree order
`--json` emits the same as JSON.

## render.py — output shape (must match the doc's ti esti entry)
`render.py <id>` or `render.py --all` (tree order, parent before child). Per node:
```
### <id> · <state>[ · canon: <ref>]
**Q** <q>
<thesis>
**Defines** — table: term | sense
**Hinge** — key: value lines (root full; others only overrides, with "inherits <parent>")
**Postulates** — table: id | claim | rests on | discharged by | note
**Terms** — table: id | clause | group | state | child
**Follow-ups** — table: id | q | kind | term | toward | requires | after | priority | ready
  then for each followup with a draft: `> **draft f1** — <draft>`
**Actions** — table: id | kind | what | obligation | done
**Traditions** — table: name | relation | note
```
Stubs render as one line: `### <id> · stub · <q>` + thesis. Priority/ready come from pressure.py (import it).

## README.md
One screen: what this is, the contamination rule, the doc URL
(https://claude.ai/code/artifact/47d8730e-0bb8-4995-b3fb-8310665c1528), the three commands,
and the flow: edit nodes/ → check → pressure → render → main thread transcribes to the doc.
