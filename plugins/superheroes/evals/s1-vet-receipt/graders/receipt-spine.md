---
type: regex
pattern: 'What I probed[\s\S]*Calls accepted[\s\S]*What the owner still carries[\s\S]*Degradations[\s\S]*Accounting[\s\S]*Dispositions[\s\S]*Pending[\s\S]*Open owner calls'
flags: i
target:
  source: file
  path: receipt.md
---
