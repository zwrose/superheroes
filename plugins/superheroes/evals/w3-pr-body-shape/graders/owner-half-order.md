---
type: regex
pattern: '## What.s changing, and why[\s\S]*## What we.re accepting[\s\S]*## How to see it[\s\S]*## Advisor vet'
target:
  source: file
  path: pr-body.md
---
