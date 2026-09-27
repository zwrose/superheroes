---
type: regex
pattern: '^\s*- FU1 \[(owner-call|defect|craft|flake|info)\][\s\S]*^\s*- FU2 \[(owner-call|defect|craft|flake|info)\]'
flags: m
target:
  source: file
  path: pr-body.md
---
