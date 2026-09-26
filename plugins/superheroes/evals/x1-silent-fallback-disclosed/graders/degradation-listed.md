---
type: regex
pattern: '<!-- superheroes:degradations -->\s*\n\s*### Disclosed degradations\s*\n[\s\S]{0,600}codex-deep'
target:
  source: file
  path: pr-body.md
---
