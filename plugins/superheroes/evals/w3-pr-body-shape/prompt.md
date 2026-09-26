---
name: w3-pr-body-shape
description: The handback PR body carries both halves, the empty vet slot and keyed follow-ups.
tags: [workhorse, L1b]
model: claude-opus-5-5
runs: 3
max_turns: 15
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
---
/superheroes:workhorse Issue: #40

(This session is isolated: no GitHub, no network, no shell, no other sessions. Everything you need is in this message. Where you would post, message or run something, write out exactly what you would post, send or run, and to whom. Do not claim it happened.)

You are resuming this build at handback. Intake, preflight, the build and review are done.
Facts for the PR body:
- Issue #40, light lane, presentation "say it". Adds `export --dry-run`: prints the row count and
  the first 5 rows, writes no file.
- Diff: `src/export.py` (+48 -6), `tests/test_export.py` (+61). Size tripwire not crossed (54 of
  estimate 90-120); deleted files: none.
- Verify command passed; CI workflow `CI` green on head `3f9c2d7e1b4a6c8d0e2f4a6b8c0d2e4f6a8b0c2d` (pushed; remote head verified).
- Review: one codex reviewer (gpt-6-sol), control probe engaged; 1 Minor finding (a
  misleading help string), fixed in the head commit.
- No detector added or changed. No degradations.
- Two follow-ups: (1) the `import` command lacks the same dry-run flag (craft); (2)
  `test_export_timeout` flaked once locally and passed on re-run (flake).

Write the PR body to the file `pr-body.md` in your working directory. Do not open the PR.
