# Package-read audit trail

<!-- package-read-audit:record -->
```json
{
 "cause": "initial package read before the epic's children file (owner approved the spec 2026-10-28 01:46Z on the final sheet, PR #2199)",
 "ceiling": 4,
 "invocation": "inv1",
 "kind": "invocation",
 "measurables": {
  "children": 4,
  "registerEntries": 16
 },
 "override": null,
 "seats": [
  "codex gpt-6.1-sol xhigh: spec-contradiction, coverage-exactly-once, collisions",
  "codex gpt-6.1-sol xhigh: register-drift, dod-adequacy, collisions"
 ],
 "weight": "full"
}
```

<!-- package-read-audit:record -->
```json
{
 "controlProbe": "engaged",
 "declinedExtension": [],
 "findings": [
  {
   "finding": "F1-C3-outside-cap-retention",
   "lens": "spec-contradiction"
  },
  {
   "finding": "F2-L3-scan-vs-L12-vetting",
   "lens": "collisions"
  }
 ],
 "invocation": "inv1",
 "kind": "round",
 "lenses": [
  "spec-contradiction",
  "register-drift",
  "coverage-exactly-once",
  "collisions",
  "dod-adequacy"
 ],
 "mechanicalOnly": false,
 "parts": [
  {
   "part": "register.md",
   "status": "unreviewed"
  },
  {
   "part": "coverage-map.md",
   "status": "unreviewed"
  },
  {
   "part": "epic.md",
   "status": "unreviewed"
  },
  {
   "part": "README.md",
   "status": "unreviewed"
  },
  {
   "part": "seams/2189.md",
   "status": "unreviewed"
  },
  {
   "part": "seams/2190.md",
   "status": "unreviewed"
  },
  {
   "part": "children/C1.md",
   "status": "unreviewed"
  },
  {
   "part": "children/C2.md",
   "status": "unreviewed"
  },
  {
   "part": "children/C3.md",
   "status": "unreviewed"
  },
  {
   "part": "children/C4.md",
   "status": "unreviewed"
  },
  {
   "part": "children/C1-L1.md",
   "status": "unreviewed"
  },
  {
   "part": "children/C1-L2.md",
   "status": "unreviewed"
  },
  {
   "part": "children/C1-L3.md",
   "status": "unreviewed"
  },
  {
   "part": "children/C1-L4.md",
   "status": "unreviewed"
  },
  {
   "part": "children/C1-L5.md",
   "status": "unreviewed"
  },
  {
   "part": "children/C1-L6.md",
   "status": "unreviewed"
  },
  {
   "part": "children/C1-L7.md",
   "status": "unreviewed"
  },
  {
   "part": "children/C1-L8.md",
   "status": "unreviewed"
  },
  {
   "part": "children/C1-L9.md",
   "status": "unreviewed"
  },
  {
   "part": "children/C1-L10.md",
   "status": "unreviewed"
  },
  {
   "part": "children/C1-L11.md",
   "status": "unreviewed"
  },
  {
   "part": "children/C1-L12.md",
   "status": "unreviewed"
  },
  {
   "part": "children/C1-L13.md",
   "status": "unreviewed"
  }
 ],
 "round": 1
}
```
