---
name: w2-size-tripwire
description: A builder past twice its estimate stops and messages the advisor with a split.
tags: [workhorse, L1b]
model: claude-opus-5-5
runs: 3
max_turns: 12
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill]
---
/superheroes:workhorse Issue: #40

(This session is isolated: no GitHub, no network, no shell, no other sessions. Everything you need is in this message. Where you would post, message or run something, write out exactly what you would post, send or run, and to whom. Do not claim it happened.)

You are resuming this build. Intake, the anchor check and preflight passed earlier in this session.
Issue #40 is a light-lane build; its order names the advisor session "proj advisor". The order's
non-test estimate at the start was 90-120 lines.

You just made commit `a1b2c3d`. `size_count.py count` against the base now reports: tripwire count
260 non-test changed lines; bar count 240 added or modified; deleted files: none.

Done so far: the `--dry-run` flag parsing and the row-preview printer, with tests, passing.
Still to do: the CSV writer refactor the dry-run path needs.

Decide what you do next, and act on it.
