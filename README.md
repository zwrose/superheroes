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

## Where this is going

superheroes is growing into a band that runs much of a project's development loop for
you. See the [roadmap](ROADMAP.md) for the phases, and [CONVENTIONS.md](CONVENTIONS.md)
for the cross-plugin contracts.

## Contributing

Issues and pull requests are welcome. Fork the repo, open a PR, and we'll help get
it merged. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE) © Zach Rose
