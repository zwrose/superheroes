# Package-read audit trail

<!-- package-read-audit:record -->
```json
{
 "cause": "initial package read before the epic's children file (owner approved the spec 2026-10-08 in the discovery session for #1638)",
 "ceiling": 4,
 "invocation": "inv1",
 "kind": "invocation",
 "measurables": {
  "children": 4,
  "registerEntries": 7
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
   "finding": "seatA-2",
   "lens": "spec-contradiction"
  },
  {
   "finding": "seatB-2",
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
  }
 ],
 "round": 1
}
```

<!-- package-read-audit:record -->
```json
{
 "controlProbe": "engaged",
 "declinedExtension": [],
 "findings": [],
 "invocation": "inv1",
 "kind": "round",
 "lenses": [
  "spec-contradiction",
  "register-drift",
  "coverage-exactly-once",
  "collisions",
  "dod-adequacy"
 ],
 "mechanicalOnly": true,
 "parts": [
  {
   "part": "register-R4",
   "status": "unreviewed"
  },
  {
   "part": "C1",
   "status": "reviewed"
  },
  {
   "part": "C2",
   "status": "reviewed"
  },
  {
   "part": "C3",
   "status": "reviewed"
  },
  {
   "part": "coverage-map",
   "status": "reviewed"
  }
 ],
 "round": 2
}
```

<!-- package-read-audit:record -->
```json
{
 "findings": [
  {
   "disposition": "package-fix",
   "evidence": "R4 now ends 'unless the lane also holds no phone, in which case the results open with UFR-5's no-phone line instead and with no other did-not-run line', matching UFR-10's last sentence and UFR-5's second GWT; scoped round 2 re-read R4 and its three quotes and raised nothing beyond the planted probe.",
   "finding": "seatA-2",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "evidence": "R4 now ends 'unless the lane also holds no phone, in which case the results open with UFR-5's no-phone line instead and with no other did-not-run line', matching UFR-10's last sentence and UFR-5's second GWT; scoped round 2 re-read R4 and its three quotes and raised nothing beyond the planted probe.",
   "finding": "seatB-2",
   "outcome": "verified"
  }
 ],
 "invocation": "inv1",
 "kind": "verification",
 "syncChecks": [
  {
   "child": "C1",
   "result": "pass"
  },
  {
   "child": "C2",
   "result": "pass"
  },
  {
   "child": "C3",
   "result": "pass"
  },
  {
   "child": "C4",
   "result": "pass"
  }
 ]
}
```

## Filing dry-run

Run 2026-10-09T02:55Z by the advisor against the stored package (no spec PR; the stored spec stands in). Every body the filing creates, each saved as a file: the epic body and four child bodies; no child plans a stack, so there are no layer bodies.

| Body | check-build-ready | register-check (--register-copy worktree) |
| --- | --- | --- |
| epic.md | `{"ok":true,"anchorKind":"spec-section"}` | `n/a (the epic quotes no register entry)` |
| children/C1.md | `{"ok":true,"anchorKind":"spec-section"}` | `{"result":"pass","requiredEntries":["R1","R2","R3","R4"]}` |
| children/C2.md | `{"ok":true,"anchorKind":"spec-section"}` | `{"result":"pass","requiredEntries":["R2","R4","R5","R6","R7"]}` |
| children/C3.md | `{"ok":true,"anchorKind":"spec-section"}` | `{"result":"pass","requiredEntries":["R1","R3","R4","R5","R7"]}` |
| children/C4.md | `{"ok":true,"anchorKind":"spec-section"}` | `{"result":"pass","requiredEntries":["R6"]}` |

Owner rulings the package says are drafted in, and where each sits: the start-small ruling (2026-10-07) is quoted from the spec in R2's source and C1's What; the owner's 'Use claude-two for builders until further notice' (2026-10-08) is in each child's Order; the codex-only review panels ruling (2026-10-07) is in each child's Order. No STATE line calls any of them open.
