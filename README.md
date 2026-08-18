# superheroes

**A discipline layer for building software with AI sessions.**

superheroes doesn't run your builds — your sessions do. It's the set of roles, artifacts,
and review structures that let a technical owner delegate real work to AI sessions and ship
the result on evidence instead of vibes. It's built for the moderately technical
builder — someone who can describe what they want, tell whether the result works, and read
code a little. The judgment lives in the structure (brief checks, cross-vendor review, an
advisor that vets with fresh eyes), not in the owner's own engineering taste — and every
claim traces to a receipt the owner's advisor session can check from the PR alone.

One plugin, one install:

```
/plugin marketplace add zwrose/superheroes
/plugin install superheroes@superheroes
```

**Compatibility.** superheroes is validated on **Claude Code ≥ 2.1.219**. Its SessionStart bootstrap relies on the
harness natively loading project context (project/user `CLAUDE.md`, memory) on every spawn path — plain chat,
headless `-p`, and slash-command spawn; on an older harness a slash-command-spawned session may silently miss that
layer. If you update the plugin on an older harness, run the plugin's `lib/harness_probe.py` tripwire to confirm the
dependency still holds.

**Why it exists and where it's going:** [PHILOSOPHY.md](PHILOSOPHY.md) — who superheroes
is for, what its owner may trust, and the bets behind it — and [ROADMAP.md](ROADMAP.md) —
the release train delivering those promises.

---

## Getting set up

**One command sets up, fixes, or shows & tunes any project's calibration:**

```
/superheroes:configure
```

Run it **first** in any project. It senses what the project needs and either sets it up,
repairs it, or lets you see the whole project's calibration on one screen and tune a
setting — models per role, review engines, test-pilot, storage (in-repo vs. out-of-repo),
and boundary rules — once, so every session that follows inherits it.

configure also carries the **preflight**: the checkout a builder session runs, with the
owner still present, before it goes autonomous — live-exercising the browser tool,
cross-vendor CLI, and `gh` access rather than trusting a config file, so a stalled approval
surfaces now instead of at 2am. See
[`skills/configure/reference/preflight.md`](plugins/superheroes/skills/configure/reference/preflight.md).

| Command | Use it to… |
| --- | --- |
| `/superheroes:configure` | Set up, fix, view, or tune a project's superheroes calibration (**run this first**). |

**Plugin update dialog — cache bookkeeping.** Claude Code may list `.in_use/` and `__pycache__/`
entries under the plugin install cache as locally modified files. Those are runtime bookkeeping
(session markers and Python bytecode from older installed versions); they are safe to overwrite,
and no user content lives in the plugin cache directory. SessionStart best-effort removes stale
`.in_use` markers from the active plugin install; set `SUPERHEROES_NO_CACHE_SWEEP` to any
non-empty value to disable that sweep. SessionStart also runs a read-only scan of **other**
installed version directories under the same cache parent: it never deletes those markers, but
may add a one-line bootstrap note asking the advisor to propose a manual cleanup with the owner.
`SUPERHEROES_NO_CACHE_SWEEP` suppresses that sibling scan as well.

---

## Three heroes run your sessions; four serve inside them

**Showrunner**, **Workhorse**, and **Detective** are the three session types you actually
launch — one long-lived advisor per project, one active builder per issue, and an
observe-only diagnostician when the cause matters more than the fix. **The Architect**,
**Review Crew**, **Test-Pilot**, and **Guardian** serve inside those sessions.

## Showrunner — the advisor session

**Keeps the project honest at project altitude.** One long-lived session per project:
it keeps the roadmap and issue board truthful, routes incoming work to one of four intake routes
(discovery, detective, build-ready, micro), decomposes big asks into small, independently mergeable
issues, drafts each builder's launch prompt as just the command and the issue pointer (everything
durable lives in the issue), vets
every PR from its artifacts — the diff, the issue/spec, the build brief — against what was
asked and what was proposed, diagnoses anomalies from artifacts, and coordinates releases. It
keeps **merge approval** with the owner and may **execute an approved merge** only where
a mechanical per-merge checkpoint exists.

| Command | Use it to… |
| --- | --- |
| `/superheroes:showrunner` | Run the advisor session for this project — route work, vet PRs, coordinate releases. |
| `/superheroes:checkpoint` | Freshen live state and emit a ready-to-paste `/compact` command before compaction. |
| `/superheroes:discuss-open-decisions` | Walk the owner through open decisions that are theirs — standing proposals, open parks, anything pending — filtered to what is genuinely theirs, in two batches with the blocking ones first. |

## Workhorse — the builder session

**Takes one routed issue to a ready PR.** A disposable session, one active builder per issue:
it writes a short **build brief** (shape, contracts & state, reuse plan, hard seams, rejected
alternatives, consequential flags), gets it checked pre-code by a fresh reviewer at
comparable tier and from another vendor, then builds test-first with tiered subagents in small
diffs, verifies UI work in a real browser via test-pilot, runs multi-model review with every
finding dispositioned in the PR body, and hands back a **ready PR**. It **never merges**.

| Command | Use it to… |
| --- | --- |
| `/superheroes:workhorse` | Build a routed issue and take it to a ready-for-review PR. |
| `/superheroes:checkpoint` | Freshen live state and emit a ready-to-paste `/compact` command before compaction. |

## Detective — the diagnosis session

**Finds the demonstrated cause when the cause matters more than the fix.** A dedicated
observe-only session that fires when the cause is unknown, the blast radius is
cross-cutting, or a first fix already failed — an ordinary bug stays build-ready. It
demonstrates a cause by **reproduction or A/B comparison on a disposable copy**, never by
inference from error text alone. It delivers a **diagnosis receipt** on the incident issue
for the **advisor to vet**. It **never edits the surface under diagnosis and never produces
a fix**.

| Command | Use it to… |
| --- | --- |
| `/superheroes:detective` | Run an observe-only diagnosis when the cause is the valuable thing — demonstrate cause, deliver a diagnosis receipt, never fix. |

## The Architect

**Turns fuzzy intent into an owner-approved spec.** the-architect owns the *what*, in plain
language — never the *how*, which stays the builder's, spelled out in the build brief. It runs
Discovery (eliciting requirements with you, no jargon), which ends one of three ways: an
owner-approved spec; a findings record you ratify, when the investigation finds nothing worth
specifying; or a park note, when it stops before reaching an answer — never silence.

| Command | Use it to… |
| --- | --- |
| `/superheroes:architect-discovery` | Turn an idea into an owner-approved requirements **spec**. |
| `/superheroes:review-spec` | Red-team a draft spec before the owner gives final approval. |

## Review Crew

**The multi-model, cross-vendor review layer.** It checks the build brief before any code
is written, reviews code with an auto-fix loop (`review-code`), red-teams specs
(`review-spec`), and periodically sweeps a whole repo for accumulated debt (`audit-debt`).
Panels are composed to be vendor-complementary — models that didn't write the code (or the
brief, or the spec) are the ones reviewing it.

| Command | Use it to… |
| --- | --- |
| `/superheroes:review-code` | Review an open PR or local branch and auto-fix what it finds — commits locally, never pushes. |
| `/superheroes:review-spec` | Red-team a draft spec and report a readiness verdict. |
| `/superheroes:audit-debt` | Periodically sweep a whole repo for accumulated debt → a prioritized set of GitHub issues. |

## Test-Pilot

**Behavioral proof that a change actually works — not just that it compiles.** It seeds
realistic test data, posts a checkbox test plan to the PR, then drives the plan in a real
browser and posts a results comment. **Observe-only:** a bug it finds is a finding, never a
fix — fixes always route back to the session that called it in.

| Command | Use it to… |
| --- | --- |
| `/superheroes:test-pilot-plan` | Seed test data for a PR/branch and post a checkbox test plan to the PR. |
| `/superheroes:test-pilot-execute` | Drive the plan in a real browser, record what it observes at each step, and post a results comment before your spot-check. |

## Guardian — the maintainability guardian

**Guards the existential risk for a non-technical owner: unmaintainable AI-spaghetti.** A
periodic **read-only sweep of repo health** where deterministic tools detect and one model pass
validates each candidate against your project's own conventions, then writes it as a plain
consequence with a receipt. It reports **drift over a baseline** — only what changed since the
last sweep, never re-raising settled trades — reaching you through the advisor as consequences
to act on, not matrices to interpret. It **never edits code, never commits or pushes, never
files issues, and never runs or owns enforcement**: it recommends; you and the advisor decide.
The health lenses (duplication, complexity, coupling, dependency and doc freshness, dead code)
roll out across the guardian arc; this is the sweep it runs them in.

| Command | Use it to… |
| --- | --- |
| `/superheroes:guardian` | Run a read-only repo-health sweep → a drift report of plain-language consequences with receipts. Never edits, commits, or files. |

---

## What holds it together

- **Specs carry intent.** An owner-approved spec is the *what* — the contract a PR is held
  accountable to. The *how* stays the builder's: spelled out explicitly in the build brief,
  checked once before code, and vetted against at the PR. No plan documents, no doc-review
  treadmills.
- **Review is structurally independent.** Cross-vendor panels mean models that didn't write
  the code review it; the advisor vets every PR with fresh context; merge approval stays with
  the owner. Maker and checker are never the same mind.
- **configure calibrates once**, and every session inherits it.
- **The covenant rides every session.** A SessionStart hook injects a distilled operating
  discipline — never delegate merge approval; claim only what you verified; disclose every
  degradation; park rather than presume — into every session (see
  [`rubric/covenant.md`](plugins/superheroes/rubric/covenant.md)).
- **An owner-authority gate backs the covenant mechanically.** A hook intercepts
  merge, release, force-push, and workflow-run actions and routes them to the owner — not just a
  promise in a prompt. On a calibrated project an owner may pre-authorize an exactly-named
  workflow dispatch via `owner-authority-allow.json`; merge, release, and force-push are never
  allowlistable.
- **A worktree guard refuses silent destruction of uncommitted work — on Claude Code.** A
  second hook intercepts git commands that would irrecoverably discard uncommitted changes and
  points at recoverable alternatives — commit first, stash, or revert a probe edit with an
  inverse edit. Codex has no such hook wired yet.

## What this is not

superheroes does not execute your build as a fixed sequence of stages, and it is not an
orchestration engine — there is no intermediary layer routing sessions through steps on
their behalf. There are no gates between an approved issue and a ready PR beyond the ones
above. The platform runs the agents; superheroes supplies the judgment structure around
them.

---

## Multi-host harness

The marketplace runs on both **Claude Code** and **Codex**. The plugin is the same;
only the install command differs.

**Claude Code** (existing flow):

```
/plugin marketplace add zwrose/superheroes
/plugin install superheroes@superheroes
```

**Codex:**

```
codex plugin marketplace add zwrose/superheroes
codex plugin add superheroes@superheroes
```

Skills speak in host-neutral actions and resolve them per host via a thin tool-map
(`hosts/claude-tools.md` / `hosts/codex-tools.md` inside the plugin). No behavior
changes — the same methodology runs on both.

---

## Where this is going

See the [roadmap](ROADMAP.md) — now a live [GitHub Project](https://github.com/users/zwrose/projects/1) —
for what's planned and in flight, and [CONVENTIONS.md](CONVENTIONS.md) for the cross-plugin contracts.

## Contributing

Issues and pull requests are welcome. Fork the repo, open a PR, and we'll help get
it merged. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE) © Zach Rose
