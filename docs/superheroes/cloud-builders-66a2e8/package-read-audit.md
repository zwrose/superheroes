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

<!-- package-read-audit:record -->
```json
{
 "controlProbe": "engaged",
 "declinedExtension": [],
 "findings": [
  {
   "finding": "F5-closure-no-real-wave",
   "lens": "spec-contradiction"
  },
  {
   "finding": "F6-renewal-stale-mentions",
   "lens": "collisions"
  },
  {
   "finding": "F7-closure-decide-by-list",
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
   "part": "C4",
   "status": "reviewed"
  }
 ],
 "round": 2
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
   "part": "coverage-map",
   "status": "unreviewed"
  },
  {
   "part": "epic",
   "status": "unreviewed"
  },
  {
   "part": "C2",
   "status": "unreviewed"
  },
  {
   "part": "C8",
   "status": "reviewed"
  },
  {
   "part": "C3",
   "status": "reviewed"
  },
  {
   "part": "C7",
   "status": "reviewed"
  },
  {
   "part": "register",
   "status": "reviewed"
  }
 ],
 "round": 3
}
```

<!-- package-read-audit:record -->
```json
{
 "findings": [
  {
   "disposition": "package-fix",
   "evidence": "epic.md and coverage-map.md run the closure validation at C8 vet against the stack head before the one stack merge; C8.md DoD names its handback as the closure handback",
   "finding": "F1-closure-before-merge",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "evidence": "register R3: the pass command alone never moves the lapse date; it moves only on a cloud session confirmation (decide-by C3)",
   "finding": "F2-renewal-confirmed-paste",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "evidence": "register R2 and C6: mismatch at intake ends refusal, never park; C7 relaunches on the owner machine via C5 routing with both versions named",
   "finding": "F3-intake-version-mismatch",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "evidence": "C1 What: wave watch reads pid and transcript age; heartbeat sweep reads heartbeat files (terminal, nonterminal, unknown)",
   "finding": "F4-C1-heartbeat-baseline",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "evidence": "epic.md and coverage-map.md: no real wave or full-size build before merge; recorded runs graded as far as they reach, rest left to learning in use (Canon ca3e7e0d-15)",
   "finding": "F5-closure-no-real-wave",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "evidence": "coverage-map FR-36 line and C2 sequencing line now read the lapse date as moved by confirmation only",
   "finding": "F6-renewal-stale-mentions",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "evidence": "epic DoD lists R2 by C1 and C5, R3 by C2 and C3",
   "finding": "F7-closure-decide-by-list",
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
  },
  {
   "child": "C5",
   "result": "pass"
  },
  {
   "child": "C6",
   "result": "pass"
  },
  {
   "child": "C7",
   "result": "pass"
  },
  {
   "child": "C8",
   "result": "pass"
  }
 ]
}
```

## Filing dry-run

Run by the advisor on 2026-10-10 against the breakdown branch's head (commit 504d0a65 plus this trail), before the package goes to the owner for the merge word. Every body the filing creates is a file in this folder. There is no separate layer body: each of the eight children is one layer of the epic's stack, and the epic is the stack's feature issue.

| Body | `issue_contract.py check-build-ready` | `register_check.py check` (`--register-copy worktree`, on the epic's body, per § Stack layer inputs) |
| --- | --- | --- |
| epic.md | `ok: true`, reason null | (feature body; quotes R1–R11) |
| children/C1.md | `ok: true` | C1: pass |
| children/C2.md | `ok: true` | C2: pass |
| children/C3.md | `ok: true` | C3: pass |
| children/C4.md | `ok: true` | C4: pass |
| children/C5.md | `ok: true` | C5: pass |
| children/C6.md | `ok: true` | C6: pass |
| children/C7.md | `ok: true` | C7: pass |
| children/C8.md | `ok: true` | C8: pass |

Owner rulings the package says are drafted in, and where each sits:
- Canon 2026-10-10-dcc2b5e5-8 (walk item 18 = c: build ahead with stacks, merge as one unit, never partly in #1708's release) is in register R8, the epic's Sequencing and its one-release paragraph, and every child's Order block. The Canon line is committed on this branch.
- Canon 2026-10-10-ca3e7e0d-21 (a parked cloud PR follows the review spec) is in register R7 and C6/C7.
- Canon 2026-10-10-ca3e7e0d-22 (Canon or specs outside the repo means a local build) is in register R5 and C5.

No State line calls any of them open. Result: verified.
