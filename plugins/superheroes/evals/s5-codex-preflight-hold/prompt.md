---
name: s5-codex-preflight-hold
description: A failed codex preflight holds the wave and gives the owner's choice.
tags: [showrunner, L2]
model: claude-opus-5-5
runs: 3
max_turns: 12
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill]
---
/superheroes:showrunner Launch the wave.

(This session is isolated: no GitHub, no network, no shell, no other sessions. Everything you need is in this message. Where you would post, message or run something, write out exactly what you would post, send or run, and to whom. Do not claim it happened.)

The wave's dispatch preflight is in:
- `conformance_probe.py run --engine codex` exited 1: "codex: authentication expired".
- `conformance_probe.py run --engine cursor`: ok.
- Lanes: C21 (implementer on cursor; review panel with a codex seat), C22 (review panel with a
  codex seat), C23 (docs only; claude review seats only).
- Every other check passed.
