# superheroes

**Your team of superheroes, powered by [superpowers](https://github.com/obra/superpowers) — agent tools for [Claude Code](https://code.claude.com).**

A marketplace of Claude Code plugins, each a character with a job to do. They team
up to take real development work off your plate — reviewing, testing, and (more and
more) running the loop themselves. Add the marketplace once, then install whichever
heroes you want:

```
/plugin marketplace add zwrose/superheroes
```

---

## the-architect

**Turns a fuzzy idea into a reviewed spec → plan → tasks.**

the-architect owns the front half of the loop. From a rough idea, feature request, or
bug it runs **Discovery** (eliciting plain-language requirements with you — the *what*,
no jargon), then autonomously drafts the technical **Plan** (the *how*) and the
bite-sized, test-first **Tasks** — each gated by review-crew. You live in the *what*; it
handles the *how*, pausing only to escalate genuinely consequential calls in
plain-language pros/cons.

### Commands

| Command | Use it to… |
| --- | --- |
| `/the-architect:discovery` | Turn an idea into an owner-approved requirements **spec**. |
| `/the-architect:plan` | Turn an approved spec into a technical **plan**. |
| `/the-architect:tasks` | Turn an approved plan into bite-sized, test-first **tasks**. |

### Install & first run

```
/plugin marketplace add zwrose/superheroes
/plugin install the-architect@superheroes
```

Then, in any project:

```
/the-architect:discovery      # turn an idea into a reviewed spec
```

---

## review-crew

**A standing review panel for your code, plans, and tech debt.**

Most AI review is one model skimming a diff for "anything wrong?" review-crew is
built differently: a panel of **five specialist reviewers** — architecture, code,
security, test, and failure-mode (premortem) — each with its own methodology, running in parallel under a
shared severity rubric. An orchestrator compiles their findings, triages each one,
and (for code) drives an **auto-fix loop** that applies the safe fixes and
re-reviews until nothing Critical or Important remains.

Two things make it more than a clever prompt:

- **Calibrated to your project.** `review-init` generates a
  `.claude/review-profile.md` — your threat model, verify command, scope, and
  canonical patterns — so reviews match *your* codebase instead of generic best
  practices. Severity rules, diff-scope discipline, and "cite `file:line` or drop
  the finding" are enforced when findings are compiled, not left to hope.
- **Measured, not vibes.** The reviewer agents ship with a frozen eval harness
  (planted findings + decoy traps, a deterministic scorer) and a non-regression
  gate: a change has to prove it catches real issues without inflating false
  positives before it lands. See [`plugins/review-crew/eval/`](plugins/review-crew/eval/).

It's also context-frugal — the orchestrator never loads the full diff or raw agent
output into its own conversation; subagents do the heavy reading and write
structured results to disk.

### Commands

| Command | Use it to… |
| --- | --- |
| `/review-crew:review-init` | Generate or refresh a project's review profile (**run this first**). |
| `/review-crew:review-code` | Review an open PR or local branch and auto-fix what it finds — commits locally, never pushes. |
| `/review-crew:review-plan` | Red-team a draft plan or design spec **before** any code is written. |
| `/review-crew:audit-debt` | Periodically sweep a whole repo for accumulated debt → a prioritized set of GitHub issues. |

### Install & first run

```
/plugin marketplace add zwrose/superheroes
/plugin install review-crew@superheroes
```

Then, in any project:

```
/review-crew:review-init      # calibrate to this repo
/review-crew:review-code      # review the current branch / PR
```

---

## test-pilot

**Behavioral proof that a change actually works — not just that it compiles.**

review-crew reads your code; test-pilot *drives your app*. It seeds realistic test
data, writes a manual test plan onto the PR as a checklist, then — when you ask —
pilots that plan in a real browser, fixes the bugs it trips over, and hands you a
results comment plus a short spot-check. The goal is a trustworthy "here's it
working" before a human ever clicks anything.

Like review-crew, it's **calibrated per project** (`test-pilot-init` sets up a
profile, seeding blocks, and browser tooling) so the plans and data fit *your* app.

### Commands

| Command | Use it to… |
| --- | --- |
| `/test-pilot:test-pilot-init` | Set up (or refresh) a project's testing profile, seed blocks, and browser tooling (**run this first**). |
| `/test-pilot:test-pilot-plan` | Seed test data for a PR/branch and post a checkbox test plan to the PR. |
| `/test-pilot:test-pilot-execute` | Drive the plan in a real browser, fix what breaks, and post a results comment before your spot-check. |

### Install & first run

```
/plugin marketplace add zwrose/superheroes
/plugin install test-pilot@superheroes
```

Then, in any project:

```
/test-pilot:test-pilot-init   # calibrate to this app
/test-pilot:test-pilot-plan   # seed data + post a plan to the PR
```

---

## workhorse

**The producer — builds an approved work-item and ships it to a ready-for-review PR.**

When a tasks doc is approved, workhorse runs the **back half** of the loop on its own: it
builds the change (subagent-driven, test-first), reviews it (review-crew's auto-fix loop),
opens a draft PR, exercises it (test-pilot), resets seeded data, gets CI green, and hands
you a live dev server + a plain-language readout. It **never merges** — that's always yours.

### Commands

| Command | Use it to… |
| --- | --- |
| `/workhorse:workhorse` | Build an approved work-item and take it to a ready-for-review PR. |

### Install & first run

```
/plugin marketplace add zwrose/superheroes
/plugin install workhorse@superheroes
```

Then, once a tasks doc is approved:

```
/workhorse:workhorse          # build it and take it to a PR
```

---

## Multi-host harness

The marketplace runs on both **Claude Code** and **Codex**. The plugins are the same;
only the install command differs.

**Claude Code** (existing flow):

```
/plugin marketplace add zwrose/superheroes
/plugin install review-crew@superheroes
```

**Codex:**

```
codex plugin marketplace add zwrose/superheroes
codex plugin add review-crew@superheroes
```

Skills speak in host-neutral actions and resolve them per host via a thin tool-map
(`hosts/claude-tools.md` / `hosts/codex-tools.md` inside each plugin). No behavior
changes — the same methodology runs on both.

---

## Where this is going

superheroes is growing into a band that runs much of a project's development loop for
you. See the [roadmap](ROADMAP.md) — now a live [GitHub Project](https://github.com/users/zwrose/projects/1) —
for what's planned and in flight, and [CONVENTIONS.md](CONVENTIONS.md) for the cross-plugin
contracts.

## Contributing

Issues and pull requests are welcome. Fork the repo, open a PR, and we'll help get
it merged. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE) © Zach Rose
