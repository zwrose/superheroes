---
type: regex
pattern: '^\s*(<!-- superheroes:advisor-vet -->\s*\n\s*)?\*\*Verdict: (READY|NOT-READY|PARKED)\*\* · [0-9a-f]{40}'
target:
  source: file
  path: owner-half.md
---
