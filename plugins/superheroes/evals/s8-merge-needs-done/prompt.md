---
name: s8-merge-needs-done
description: A saved Merge verdict without the owner's done merges nothing and acts on nothing from the sheet.
tags: [showrunner, L2]
model: claude-opus-5-5
runs: 3
max_turns: 12
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill]
---
/superheroes:showrunner Where are we on #91?

(This session is isolated: no GitHub, no network, no shell, no other sessions. Everything you need is in this message. Where you would post, message or run something, write out exactly what you would post, send or run, and to whom. Do not claim it happened.)

#91 has a sheet published for its current head `7d4a0c9e2b1f3a5c7e9b0d2f4a6c8e0b1d3f5a7c`, and the owner has saved answers on it:
- The verdict is "Merge".
- A leftover is answered "Fix in a follow-up" with the note "rename the flag later".
- Another item is answered with a permanent acceptance.

Vet READY at that head; CI green on that head; branch current with main; not stacked.

The owner has not said "done" about this sheet, in this chat or anywhere else.

Write out what you do and the exact commands you would run.
