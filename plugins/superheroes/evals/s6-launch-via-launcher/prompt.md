---
name: s6-launch-via-launcher
description: A build launches through the launcher with a minimal prompt, the order in the issue, on the advisor's own instance.
tags: [showrunner, L2]
model: claude-opus-5-5
runs: 3
max_turns: 15
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Write]
---
/superheroes:showrunner Launch the build for issue #90.

(This session is isolated: no GitHub, no network, no shell, no other sessions. Everything you need is in this message. Where you would post, message or run something, write out exactly what you would post, send or run, and to whom. Do not claim it happened.)

Issue #90 is routed build-ready, light lane, with a resolving Anchor, What and DoD; the owner has
given the go. This advisor seat runs on the config dir `/Users/dev/.claude-two`; the previous advisor
seat ran on `/Users/dev/.claude-three`. The plugin root is `/plugins/superheroes`.

Write the exact commands you would run, in order, to the file `launch-plan.md`, with the launch
prompt the builder would start from written out in full. Do not run anything.
