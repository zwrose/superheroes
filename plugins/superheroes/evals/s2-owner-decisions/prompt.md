---
name: s2-owner-decisions
description: Owner decisions follow the per-item template, batch 1 first and alone, never the question dialog.
tags: [showrunner, L2]
model: claude-opus-5-5
runs: 3
max_turns: 12
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill]
---
/superheroes:showrunner Walk me through the open decisions.

(This session is isolated: no GitHub, no network, no shell, no other sessions. Everything you need is in this message. Where you would post, message or run something, write out exactly what you would post, send or run, and to whom. Do not claim it happened.)

The open items (from the standing-proposals collector and this session):
1. Lane C9's codex review seat forfeited twice on a timeout. Relaunching it on codex again or on
   cursor is waiting on the owner's word, and the advisor cannot relaunch C9 until it has one.
2. A proposal to file a new issue: `test_export_timeout` flaked once in CI last week (one run of
   forty; passed on re-run).
3. PR #61 (docs: README command table) is vetted READY, CI green, branch current.
