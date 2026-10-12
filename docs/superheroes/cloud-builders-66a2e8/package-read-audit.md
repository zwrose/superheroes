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

<!-- package-read-audit:record -->
```json
{
 "cause": "substantive amendments 1 and 2 (owner rulings 25 c and 27 a): touched-parts re-read before injection into C4",
 "ceiling": 2,
 "invocation": "inv2",
 "kind": "invocation",
 "measurables": {
  "children": 9,
  "registerEntries": 1
 },
 "override": "light despite nine children: one register entry (R3) and two child bodies (C2, C4) changed in substance; the other seven children are re-checked mechanically by the register check against the amended register",
 "seats": [
  "{\"vendor\":\"codex\",\"model\":\"gpt-6.1-sol\",\"role\":\"reviewer-deep\"}"
 ],
 "weight": "light"
}
```

<!-- package-read-audit:record -->
```json
{
 "controlProbe": "engaged",
 "declinedExtension": [],
 "findings": [
  {
   "finding": "A1-r3-environment-decide-by",
   "lens": "spec-contradiction"
  },
  {
   "finding": "A2-c4-dod-new-setup-steps",
   "lens": "dod-adequacy"
  }
 ],
 "invocation": "inv2",
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
   "status": "reviewed"
  },
  {
   "part": "coverage-map",
   "status": "reviewed"
  },
  {
   "part": "epic",
   "status": "reviewed"
  },
  {
   "part": "README",
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
   "part": "C4",
   "status": "reviewed"
  },
  {
   "part": "C5",
   "status": "reviewed"
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
 "invocation": "inv2",
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
   "part": "register",
   "status": "reviewed"
  },
  {
   "part": "coverage-map",
   "status": "reviewed"
  },
  {
   "part": "epic",
   "status": "reviewed"
  },
  {
   "part": "README",
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
   "part": "C4",
   "status": "reviewed"
  },
  {
   "part": "C5",
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
   "evidence": "register R3 and its epic quote: how the setup learns the environment is the owner's ruling 25 c (default environment, id read from the check session); C2 decides only how the id is stored; C2.md DoD wording matches",
   "finding": "A1-r3-environment-decide-by",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "evidence": "C4 DoD: a recorded setup sitting for a not-yet-signed-in fixture account shows the default-environment step, the one-time sign-in walked before the pass command, and no ask for the id, plus a test that fails on such an ask; the live run uses a default environment",
   "finding": "A2-c4-dod-new-setup-steps",
   "outcome": "verified"
  }
 ],
 "invocation": "inv2",
 "kind": "verification",
 "syncChecks": [
  {
   "child": "C1",
   "result": "pass"
  },
  {
   "child": "C1b",
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

<!-- package-read-audit:record -->
```json
{
 "cause": "substantive amendment 3 (owner's word a on the clarification of 25 c): touched-parts re-read before injection into C4",
 "ceiling": 2,
 "invocation": "inv3",
 "kind": "invocation",
 "measurables": {
  "children": 1,
  "registerEntries": 0
 },
 "override": null,
 "seats": [
  "{\"vendor\":\"codex\",\"model\":\"gpt-6.1-sol\",\"role\":\"reviewer-deep\"}"
 ],
 "weight": "light"
}
```

<!-- package-read-audit:record -->
```json
{
 "controlProbe": "engaged",
 "declinedExtension": [],
 "findings": [],
 "invocation": "inv3",
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
   "part": "C4",
   "status": "reviewed"
  },
  {
   "part": "C1b",
   "status": "reviewed"
  },
  {
   "part": "C5",
   "status": "reviewed"
  },
  {
   "part": "register",
   "status": "reviewed"
  },
  {
   "part": "coverage-map",
   "status": "reviewed"
  }
 ],
 "round": 1
}
```

<!-- package-read-audit:record -->
```json
{
 "findings": [],
 "invocation": "inv3",
 "kind": "verification",
 "syncChecks": [
  {
   "child": "C4",
   "result": "pass"
  }
 ]
}
```

<!-- package-read-audit:record -->
```json
{
 "cause": "substantive amendments 4 (35 a: the owner copies the environment's id) and 5 (33 a: relay on the builders' account): touched-parts re-read before injection into C4 and C7",
 "ceiling": 2,
 "invocation": "inv4",
 "kind": "invocation",
 "measurables": {
  "children": 2,
  "registerEntries": 2
 },
 "override": null,
 "seats": [
  "{\"vendor\":\"codex\",\"model\":\"gpt-6.1-sol\",\"role\":\"reviewer-deep\"}"
 ],
 "weight": "light"
}
```

<!-- package-read-audit:record -->
```json
{
 "controlProbe": "engaged",
 "declinedExtension": [],
 "findings": [],
 "invocation": "inv4",
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
   "part": "C4",
   "status": "reviewed"
  },
  {
   "part": "C7",
   "status": "reviewed"
  },
  {
   "part": "C1b",
   "status": "reviewed"
  },
  {
   "part": "C2",
   "status": "reviewed"
  },
  {
   "part": "C5",
   "status": "reviewed"
  },
  {
   "part": "register",
   "status": "reviewed"
  },
  {
   "part": "coverage-map",
   "status": "reviewed"
  },
  {
   "part": "spec",
   "status": "reviewed"
  },
  {
   "part": "board",
   "status": "reviewed"
  }
 ],
 "round": 1
}
```

<!-- package-read-audit:record -->
```json
{
 "findings": [],
 "invocation": "inv4",
 "kind": "verification",
 "syncChecks": [
  {
   "child": "C4",
   "result": "pass"
  },
  {
   "child": "C7",
   "result": "pass"
  }
 ]
}
```

<!-- package-read-audit:record -->
```json
{
 "cause": "ruling 37 b restates substantive amendment 4 (the owner picks the environment in Claude Code's picker; the plugin reads the id) and the C4/C4b split: touched-parts re-read before injection",
 "ceiling": 2,
 "invocation": "inv5",
 "kind": "invocation",
 "measurables": {
  "children": 2,
  "registerEntries": 2
 },
 "override": null,
 "seats": [
  "{\"vendor\":\"codex\",\"model\":\"gpt-6.1-sol\",\"role\":\"reviewer-deep\"}"
 ],
 "weight": "light"
}
```

<!-- package-read-audit:record -->
```json
{
 "controlProbe": "engaged",
 "declinedExtension": [],
 "findings": [
  {
   "finding": "code-001",
   "lens": "collisions"
  },
  {
   "finding": "code-002",
   "lens": "spec-contradiction"
  },
  {
   "finding": "code-003",
   "lens": "coverage-exactly-once"
  }
 ],
 "invocation": "inv5",
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
   "part": "C4",
   "status": "reviewed"
  },
  {
   "part": "C4b",
   "status": "reviewed"
  },
  {
   "part": "register",
   "status": "reviewed"
  },
  {
   "part": "coverage-map",
   "status": "reviewed"
  },
  {
   "part": "spec",
   "status": "reviewed"
  },
  {
   "part": "board",
   "status": "reviewed"
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
 "invocation": "inv5",
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
   "part": "C4",
   "status": "reviewed"
  },
  {
   "part": "C4b",
   "status": "reviewed"
  },
  {
   "part": "register",
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
   "evidence": "R11 now assigns the set-up path section and the showrunner pointer to C4b; epic quote regenerated; round 2 clean",
   "finding": "code-001",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "evidence": "C4 live-run DoD names the picked id passed to the start function (issue #1745 and C4.md); round 2 clean",
   "finding": "code-002",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "evidence": "C4 dry-run DoD claims FR-1's rule and names C4b as owner of the Given-When-Then; round 2 clean",
   "finding": "code-003",
   "outcome": "verified"
  }
 ],
 "invocation": "inv5",
 "kind": "verification",
 "syncChecks": [
  {
   "child": "C4",
   "result": "pass"
  },
  {
   "child": "C4b",
   "result": "pass"
  }
 ]
}
```

<!-- package-read-audit:record -->
```json
{
 "cause": "C5 size split into C5 and C5b (advisor craft call at the 600 bar): touched-parts re-read",
 "ceiling": 2,
 "invocation": "inv6",
 "kind": "invocation",
 "measurables": {
  "children": 3,
  "registerEntries": 7
 },
 "override": "seven consumer lines gain C5b but only R8's first paragraph changes; light weight is enough for a mechanical re-allocation. Corrected 2026-10-11 by the advisor: children is 3, not 2 (C6 is touched too: it now sits on C5b).",
 "seats": [
  "{\"vendor\":\"codex\",\"model\":\"gpt-6.1-sol\",\"role\":\"reviewer-deep\"}"
 ],
 "weight": "light"
}
```

<!-- package-read-audit:record -->
```json
{
 "controlProbe": "engaged",
 "declinedExtension": [],
 "findings": [
  {
   "finding": "architecture-001",
   "lens": "collisions"
  },
  {
   "finding": "architecture-002",
   "lens": "collisions"
  },
  {
   "finding": "architecture-003",
   "lens": "dod-adequacy"
  },
  {
   "finding": "architecture-004",
   "lens": "collisions"
  }
 ],
 "invocation": "inv6",
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
   "part": "C5",
   "status": "reviewed"
  },
  {
   "part": "C5b",
   "status": "reviewed"
  },
  {
   "part": "C6",
   "status": "reviewed"
  },
  {
   "part": "register",
   "status": "reviewed"
  },
  {
   "part": "coverage-map",
   "status": "reviewed"
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
 "invocation": "inv6",
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
   "part": "C5",
   "status": "reviewed"
  },
  {
   "part": "C5b",
   "status": "reviewed"
  },
  {
   "part": "C6",
   "status": "reviewed"
  },
  {
   "part": "register",
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
   "evidence": "C6.md sits on C5b in state, sequencing, DoD base and branching order; round 2 clean",
   "finding": "architecture-001",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "evidence": "R11 gives C5b the duty-9 place-call pointer, dispatch-preflight.md and the report/still verbs; epic quote equal; round 2 clean",
   "finding": "architecture-002",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "evidence": "C5 DoD grades routing-result fields; C5b DoD grades rendered wording; round 2 clean",
   "finding": "architecture-003",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "evidence": "R10 names C5b for the two glossary entries; epic quote equal; round 2 clean",
   "finding": "architecture-004",
   "outcome": "verified"
  }
 ],
 "invocation": "inv6",
 "kind": "verification",
 "syncChecks": [
  {
   "child": "C5",
   "result": "pass"
  },
  {
   "child": "C5b",
   "result": "pass"
  },
  {
   "child": "C6",
   "result": "pass"
  }
 ]
}
```

<!-- package-read-audit:record -->
```json
{
 "cause": "C6 size split into C6 and C6b (advisor craft call at the 600 bar): touched-parts re-read",
 "ceiling": 2,
 "invocation": "inv7",
 "kind": "invocation",
 "measurables": {
  "children": 3,
  "registerEntries": 7
 },
 "override": "seven consumer lines gain C6b but only R8's and R11's first paragraphs change; light weight is enough for a re-allocation. Children counts C6, C6b and C7 (C7 now sits on C6b); the other child copies change only their layer count.",
 "seats": [
  "{\"vendor\":\"codex\",\"model\":\"gpt-6.1-sol\",\"role\":\"reviewer-deep\"}"
 ],
 "weight": "light"
}
```

<!-- package-read-audit:record -->
```json
{
 "controlProbe": "engaged",
 "declinedExtension": [],
 "findings": [
  {
   "finding": "code-001",
   "lens": "dod-adequacy"
  },
  {
   "finding": "code-002",
   "lens": "collisions"
  },
  {
   "finding": "code-003",
   "lens": "collisions"
  }
 ],
 "invocation": "inv7",
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
   "part": "C6",
   "status": "reviewed"
  },
  {
   "part": "C6b",
   "status": "reviewed"
  },
  {
   "part": "C7",
   "status": "reviewed"
  },
  {
   "part": "register",
   "status": "reviewed"
  },
  {
   "part": "coverage-map",
   "status": "reviewed"
  },
  {
   "part": "spec",
   "status": "reviewed"
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
 "invocation": "inv7",
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
   "part": "C6",
   "status": "reviewed"
  },
  {
   "part": "C6b",
   "status": "reviewed"
  },
  {
   "part": "C7",
   "status": "reviewed"
  },
  {
   "part": "register",
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
   "evidence": "C6b live-run DoD grades FR-21's second acceptance (builder note public on the fixture issue in a public repository); #1777 synced; round 2 clean",
   "finding": "code-001",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "evidence": "R11's TRANSITION clause names the split layers carrying their parent's note (C4b, C5b, C6b); epic quote equal; round 2 clean",
   "finding": "code-002",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "evidence": "epic closure evidence cites C6b for the ready-PR run through the pass; round 2 clean",
   "finding": "code-003",
   "outcome": "verified"
  }
 ],
 "invocation": "inv7",
 "kind": "verification",
 "syncChecks": [
  {
   "child": "C6",
   "result": "pass"
  },
  {
   "child": "C6b",
   "result": "pass"
  },
  {
   "child": "C7",
   "result": "pass"
  }
 ]
}
```

**Owed: package read for the C7 size split (advisor, 2026-10-12; pending).** Cloud C7 (#1748) split at the 600 bar into C7 (answering a cloud builder) and C7b (recovering a cloud builder, #1784), on the docs PR that adds `children/C7b.md`. A touched-parts re-read is owed before the epic's body is re-injected with the new R8 and R11 quotes, in the shape of inv7: cause "C7 size split into C7 and C7b (advisor craft call at the 600 bar): touched-parts re-read"; parts C7, C7b and C8 (C8 now sits on C7b; the other child copies change only their layer count), the register (seven consumer lines gain C7b; R8's and R11's first paragraphs change) and the coverage map (six rows move from C7 to C7b). The advisor opens the invocation (inv8) with `package_read_audit.py open` when it runs the read and records its rounds and verification here; until then no inv8 record is written, so the trail stays conforming.

<!-- package-read-audit:record -->
```json
{
 "cause": "C7 size split into C7 and C7b (advisor craft call at the 600 bar): touched-parts re-read",
 "ceiling": 2,
 "invocation": "inv8",
 "kind": "invocation",
 "measurables": {
  "children": 3,
  "registerEntries": 7
 },
 "override": "seven consumer lines gain C7b, R8's order and R11's allocations change, six coverage rows move; C8 is touched only by renumbering; light weight is enough for a re-allocation",
 "seats": [
  "{\"vendor\":\"codex\",\"model\":\"gpt-6.1-sol\",\"role\":\"reviewer-deep\"}"
 ],
 "weight": "light"
}
```

<!-- package-read-audit:record -->
```json
{
 "controlProbe": "engaged",
 "declinedExtension": [],
 "findings": [
  {
   "finding": "code-001",
   "lens": "collisions"
  }
 ],
 "invocation": "inv8",
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
   "part": "C7",
   "status": "reviewed"
  },
  {
   "part": "C7b",
   "status": "reviewed"
  },
  {
   "part": "C8",
   "status": "reviewed"
  },
  {
   "part": "register",
   "status": "reviewed"
  },
  {
   "part": "coverage-map",
   "status": "reviewed"
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
 "invocation": "inv8",
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
   "part": "C7",
   "status": "reviewed"
  },
  {
   "part": "C7b",
   "status": "reviewed"
  },
  {
   "part": "register",
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
   "evidence": "R11's TRANSITION clause now gives C7 and C7b each their own note (C7 builder notes, C7b cloud recovery); epic quote equal; round 2 clean",
   "finding": "code-001",
   "outcome": "verified"
  }
 ],
 "invocation": "inv8",
 "kind": "verification",
 "syncChecks": [
  {
   "child": "C7",
   "result": "pass"
  },
  {
   "child": "C7b",
   "result": "pass"
  },
  {
   "child": "C8",
   "result": "pass"
  }
 ]
}
```

<!-- package-read-audit:record -->
```json
{
 "cause": "C7 second size split into C7, C7r and C7p (advisor craft call at the 450 stop line): touched-parts re-read",
 "ceiling": 2,
 "invocation": "inv9",
 "kind": "invocation",
 "measurables": {
  "children": 5,
  "registerEntries": 9
 },
 "override": "a re-allocation of already-read content across C7, C7r, C7p, C7b and C8, with no new requirement and no new register sentence beyond R8's order and R11's allocations; four consumer drops for C7 need checking; light weight with a 2-round ceiling is enough",
 "seats": [
  "{\"vendor\":\"codex\",\"model\":\"gpt-6.1-sol\",\"role\":\"reviewer-deep\"}"
 ],
 "weight": "light"
}
```
