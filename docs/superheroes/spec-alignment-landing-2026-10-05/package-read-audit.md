# Package-read audit trail: spec-alignment-landing-2026-10-05

Recorded by `lib/package_read_audit.py`. The maker is the advisor (anthropic family), so the seats are other families only.


<!-- package-read-audit:record -->
```json
{
 "cause": "initial package read before the epic's children file (owner approved both specs 2026-10-04; ruling 26 / FR-39)",
 "ceiling": 4,
 "invocation": "inv1",
 "kind": "invocation",
 "measurables": {
  "children": 8,
  "registerEntries": 25
 },
 "override": null,
 "seats": [
  "codex gpt-6.1-sol xhigh: spec-contradiction, coverage-exactly-once, collisions",
  "cursor cursor-grok-4.6 xhigh: register-drift, dod-adequacy, collisions"
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
   "finding": "codex-1",
   "lens": "spec-contradiction"
  },
  {
   "finding": "codex-2",
   "lens": "spec-contradiction"
  },
  {
   "finding": "codex-4",
   "lens": "coverage-exactly-once"
  },
  {
   "finding": "codex-5",
   "lens": "spec-contradiction"
  },
  {
   "finding": "cursor-ind-3",
   "lens": "dod-adequacy"
  },
  {
   "finding": "cursor-ind-4",
   "lens": "dod-adequacy"
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
   "part": "C4-L1",
   "status": "unreviewed"
  },
  {
   "part": "C4-L2",
   "status": "unreviewed"
  },
  {
   "part": "C4-L3",
   "status": "unreviewed"
  },
  {
   "part": "C4-L4",
   "status": "unreviewed"
  },
  {
   "part": "C5",
   "status": "unreviewed"
  },
  {
   "part": "C5-L1",
   "status": "unreviewed"
  },
  {
   "part": "C5-L2",
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
   "part": "C7-L1",
   "status": "unreviewed"
  },
  {
   "part": "C7-L2",
   "status": "unreviewed"
  },
  {
   "part": "C8",
   "status": "unreviewed"
  },
  {
   "part": "C8-L1",
   "status": "unreviewed"
  },
  {
   "part": "C8-L2",
   "status": "unreviewed"
  },
  {
   "part": "C8-L3",
   "status": "unreviewed"
  },
  {
   "part": "C8-L4",
   "status": "unreviewed"
  }
 ],
 "round": 1
}
```

<!-- package-read-audit:record -->
```json
{
 "controlProbe": "engaged",
 "declinedExtension": [
  "codex2-2"
 ],
 "findings": [
  {
   "finding": "codex2-1",
   "lens": "spec-contradiction"
  },
  {
   "finding": "codex2-2",
   "lens": "coverage-exactly-once"
  },
  {
   "finding": "codex2-4",
   "lens": "collisions"
  },
  {
   "finding": "cursor2-ind-2",
   "lens": "collisions"
  },
  {
   "finding": "cursor2-ind-3",
   "lens": "dod-adequacy"
  },
  {
   "finding": "cursor2-ind-4",
   "lens": "dod-adequacy"
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
   "part": "C1",
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
   "part": "C4-L3",
   "status": "unreviewed"
  },
  {
   "part": "C4-L4",
   "status": "unreviewed"
  },
  {
   "part": "C5",
   "status": "unreviewed"
  },
  {
   "part": "C5-L1",
   "status": "unreviewed"
  },
  {
   "part": "C5-L2",
   "status": "unreviewed"
  },
  {
   "part": "C6",
   "status": "unreviewed"
  },
  {
   "part": "C8",
   "status": "unreviewed"
  },
  {
   "part": "C8-L1",
   "status": "unreviewed"
  },
  {
   "part": "C8-L2",
   "status": "unreviewed"
  },
  {
   "part": "C8-L3",
   "status": "unreviewed"
  },
  {
   "part": "C8-L4",
   "status": "unreviewed"
  },
  {
   "part": "C4-L1",
   "status": "reviewed"
  },
  {
   "part": "C4-L2",
   "status": "reviewed"
  },
  {
   "part": "C7-L2",
   "status": "reviewed"
  },
  {
   "part": "README",
   "status": "reviewed"
  },
  {
   "part": "epic",
   "status": "reviewed"
  }
 ],
 "round": 2
}
```
