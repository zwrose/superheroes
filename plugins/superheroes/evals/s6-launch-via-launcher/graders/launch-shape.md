---
type: llm
focus:
  source: file
  path: launch-plan.md
---
Judge the launch plan.
PASS only if all of these hold:
- It launches through the launcher's steps (declare the batch, preflight, launch) and never
  composes a raw `claude -p` (or other hand-built) builder command.
- The launch prompt is the workhorse command plus the issue pointer only; anything the build must
  follow sits in the issue body, not in the prompt.
- The launch pins the advisor's own config dir (`/Users/dev/.claude-two`), not the previous seat's.
FAIL if any of these is missing.
