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

---

## Two heroes run your sessions; four serve inside them

**Showrunner** and **Workhorse** are the two session types you actually launch — one
long-lived advisor per project, one disposable builder per issue. **The Architect**,
**Review Crew**, **Test-Pilot**, and **Guardian** serve inside those sessions.

## Showrunner — the advisor session

**Keeps the project honest at project altitude.** One long-lived session per project:
it keeps the roadmap and issue board truthful, sizes and routes incoming work (build-ready
vs. needs-discovery), decomposes big asks into small, independently mergeable issues, drafts each
builder's launch prompt as just the command and the issue pointer (everything durable lives in the
issue), vets
every PR from its artifacts — the diff, the issue/spec, the build brief — against what was
asked and what was proposed, diagnoses anomalies from artifacts, and coordinates releases. It
**never merges** — that's always the owner's act.

| Command | Use it to… |
| --- | --- |
| `/superheroes:showrunner` | Run the advisor session for this project — route work, vet PRs, coordinate releases. |

## Workhorse — the builder session

**Takes one routed issue to a ready PR.** A disposable session, one per issue: it writes a
short **build brief** (shape, contracts & state, reuse plan, hard seams, rejected
alternatives, consequential flags), gets it checked pre-code by a fresh reviewer at
comparable tier and from another vendor, then builds test-first with tiered subagents in small diffs,
verifies UI work in a real browser via test-pilot, runs multi-model review with every
finding dispositioned in the PR body, and hands back a **ready PR**. It **never merges**.

| Command | Use it to… |
| --- | --- |
| `/superheroes:workhorse` | Build a routed issue and take it to a ready-for-review PR. |

## The Architect

**Turns fuzzy intent into an owner-approved spec.** the-architect owns the *what*, in plain
language — never the *how*, which stays the builder's, spelled out in the build brief. It
runs Discovery (eliciting requirements with you, no jargon) through to an owner-approved
spec.

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
  the code review it; the advisor vets every PR with fresh context; the owner merges. Maker
  and checker are never the same mind.
- **configure calibrates once**, and every session inherits it.
- **The covenant rides every session.** A SessionStart hook injects a distilled operating
  discipline — never merge, never claim more than you verified, disclose every degradation,
  park rather than presume — into every session (see
  [`rubric/covenant.md`](plugins/superheroes/rubric/covenant.md)).
- **An owner-authority gate backs the covenant mechanically.** A hook intercepts
  merge, release, force-push, and workflow-run actions and routes them to the owner — not just a
  promise in a prompt.

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
