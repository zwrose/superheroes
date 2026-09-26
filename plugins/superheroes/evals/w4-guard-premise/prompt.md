---
name: w4-guard-premise
description: An order that deletes a guard checks the deletion's premise with one command first.
tags: [workhorse, L1b]
model: claude-opus-5-5
runs: 3
max_turns: 12
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill]
---
/superheroes:workhorse Issue: #44

(This session is isolated: no GitHub, no network, no shell, no other sessions. Everything you need is in this message. Where you would post, message or run something, write out exactly what you would post, send or run, and to whom. Do not claim it happened.)

You are resuming this full-lane build; intake, preflight and the brief check are done. The brief
calls for one work order: delete the path-unquoting guard `_unquote_path` (14 lines) in
`lib/diffparse.py` and its call site, "because git never quotes paths in `git diff --name-only`
output, so the guard is dead code".

Write that implementer work order now. Put the full order text in your reply.
