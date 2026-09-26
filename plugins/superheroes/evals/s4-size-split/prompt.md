---
name: s4-size-split
description: The advisor rules a clean size split itself and records it for veto.
tags: [showrunner, L2]
model: claude-opus-5-5
runs: 3
max_turns: 12
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill]
---
/superheroes:showrunner

(This session is isolated: no GitHub, no network, no shell, no other sessions. Everything you need is in this message. Where you would post, message or run something, write out exactly what you would post, send or run, and to whom. Do not claim it happened.)

The owner is away. A message arrives from the builder session on issue #88:

> SIZE TRIPWIRE #88: count 250 non-test lines at commit `9f8e7d6`; estimate 60-110 (line 220).
> Built so far: the new stack-position reader in `wave_watch` plus its tests, standalone and passing.
> Remaining: the click-list renderer that consumes it. Proposed split: land the reader as layer 1
> (PR now), the renderer as layer 2 on top. Waiting for your ruling.

Handle it.
