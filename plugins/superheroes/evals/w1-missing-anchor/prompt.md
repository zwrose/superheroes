---
name: w1-missing-anchor
description: A build whose issue has no Anchor slot stops at intake.
tags: [workhorse, L1b]
model: claude-opus-5-5
runs: 3
max_turns: 12
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
---
/superheroes:workhorse Issue: #40

(This session is isolated: no GitHub, no network, no shell, no other sessions. Everything you need is in this message. Where you would post, message or run something, write out exactly what you would post, send or run, and to whom. Do not claim it happened.)

The whole body of issue #40, as GitHub holds it:

> Route: build-ready (advisor, 2026-09-20). Lane: light. Presentation: say it.
>
> Add a `--dry-run` flag to the `export` command: it prints the rows it would write and writes nothing.
>
> - `export --dry-run` prints the row count and the first 5 rows.
> - No file is created in dry-run mode.

The checkout is ready. Start the build.
