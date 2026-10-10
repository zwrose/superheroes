# Package-read audit trail

<!-- package-read-audit:record -->
```json
{
 "cause": "initial package read before the epic's children file (owner approved the spec 2026-10-10, PR #1740)",
 "ceiling": 4,
 "invocation": "inv1",
 "kind": "invocation",
 "measurables": {
  "children": 8,
  "registerEntries": 11
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
   "finding": "F1-closure-before-merge",
   "lens": "collisions"
  },
  {
   "finding": "F2-renewal-confirmed-paste",
   "lens": "collisions"
  },
  {
   "finding": "F3-intake-version-mismatch",
   "lens": "spec-contradiction"
  },
  {
   "finding": "F4-C1-heartbeat-baseline",
   "lens": "spec-contradiction"
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
   "part": "register",
   "status": "unreviewed"
  },
  {
   "part": "coverage-map",
   "status": "unreviewed"
  },
  {
   "part": "epic",
   "status": "unreviewed"
  },
  {
   "part": "README",
   "status": "unreviewed"
  },
  {
   "part": "C1",
   "status": "unreviewed"
  },
  {
   "part": "C2",
   "status": "unreviewed"
  },
  {
   "part": "C3",
   "status": "unreviewed"
  },
  {
   "part": "C4",
   "status": "unreviewed"
  },
  {
   "part": "C5",
   "status": "unreviewed"
  },
  {
   "part": "C6",
   "status": "unreviewed"
  },
  {
   "part": "C7",
   "status": "unreviewed"
  },
  {
   "part": "C8",
   "status": "unreviewed"
  },
  {
   "part": "dec0af-register-trailers",
   "status": "unreviewed"
  }
 ],
 "round": 1
}
```
