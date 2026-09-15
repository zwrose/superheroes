# Package-read audit trail

<!-- package-read-audit:record -->
```json
{
 "cause": "first read before the children file (Spec A and Spec B stamped 2026-09-14)",
 "ceiling": 3,
 "invocation": "inv-1",
 "kind": "invocation",
 "measurables": {
  "children": 17,
  "registerEntries": 28
 },
 "override": "one dispatch per seat carrying all five lenses; two seats from two families, the maker's family (Claude) excluded",
 "seats": [
  "codex:gpt-5.6-sol@high",
  "cursor:cursor-grok-4.6@xhigh"
 ],
 "weight": "full"
}
```

<!-- round 1 notes (advisor, 2026-09-14): seats codex Sol high (18 findings) and cursor Grok xhigh (13 findings), both engaged; both named the planted C4 parity-sentence contradiction (cursor-pkg-06, codex-pkg-03), which is the control probe and not a package defect. Full seat results: package-read/round-1-*.json. Every other finding was accepted and fixed as a package fix (no spec amendment, no refutation): the map re-extracted (240 criteria), R1/R5/R7/R8/R15/R27/R28 rewritten, C1 as wave 0, C9 and C15 restated to FR-B6, C6 first state, C12 six cases, C16 retire-to-archive, DoD additions on C7/C10/C11/C13/C14/C17, the machinery definition to C2. Those fixes are new authorship and are re-read in round 2. -->

<!-- package-read-audit:record -->
```json
{
 "controlProbe": "engaged",
 "declinedExtension": [],
 "findings": [
  {
   "finding": "cursor-pkg-01",
   "lens": "coverage-exactly-once"
  },
  {
   "finding": "cursor-pkg-02",
   "lens": "coverage-exactly-once"
  },
  {
   "finding": "cursor-pkg-03",
   "lens": "spec-contradiction"
  },
  {
   "finding": "cursor-pkg-04",
   "lens": "spec-contradiction"
  },
  {
   "finding": "cursor-pkg-05",
   "lens": "spec-contradiction"
  },
  {
   "finding": "cursor-pkg-06",
   "lens": "spec-contradiction"
  },
  {
   "finding": "cursor-pkg-07",
   "lens": "register-drift"
  },
  {
   "finding": "cursor-pkg-08",
   "lens": "dod-adequacy"
  },
  {
   "finding": "cursor-pkg-09",
   "lens": "collisions"
  },
  {
   "finding": "cursor-pkg-10",
   "lens": "coverage-exactly-once"
  },
  {
   "finding": "cursor-pkg-11",
   "lens": "coverage-exactly-once"
  },
  {
   "finding": "cursor-pkg-12",
   "lens": "dod-adequacy"
  },
  {
   "finding": "cursor-pkg-13",
   "lens": "dod-adequacy"
  },
  {
   "finding": "codex-pkg-01",
   "lens": "coverage-exactly-once"
  },
  {
   "finding": "codex-pkg-02",
   "lens": "coverage-exactly-once"
  },
  {
   "finding": "codex-pkg-03",
   "lens": "spec-contradiction"
  },
  {
   "finding": "codex-pkg-04",
   "lens": "spec-contradiction"
  },
  {
   "finding": "codex-pkg-05",
   "lens": "spec-contradiction"
  },
  {
   "finding": "codex-pkg-06",
   "lens": "spec-contradiction"
  },
  {
   "finding": "codex-pkg-07",
   "lens": "spec-contradiction"
  },
  {
   "finding": "codex-pkg-08",
   "lens": "spec-contradiction"
  },
  {
   "finding": "codex-pkg-09",
   "lens": "spec-contradiction"
  },
  {
   "finding": "codex-pkg-10",
   "lens": "dod-adequacy"
  },
  {
   "finding": "codex-pkg-11",
   "lens": "register-drift"
  },
  {
   "finding": "codex-pkg-12",
   "lens": "collisions"
  },
  {
   "finding": "codex-pkg-13",
   "lens": "dod-adequacy"
  },
  {
   "finding": "codex-pkg-14",
   "lens": "dod-adequacy"
  },
  {
   "finding": "codex-pkg-15",
   "lens": "dod-adequacy"
  },
  {
   "finding": "codex-pkg-16",
   "lens": "dod-adequacy"
  },
  {
   "finding": "codex-pkg-17",
   "lens": "dod-adequacy"
  },
  {
   "finding": "codex-pkg-18",
   "lens": "dod-adequacy"
  }
 ],
 "invocation": "inv-1",
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
   "part": "children-C1-to-C17",
   "status": "unreviewed"
  }
 ],
 "round": 1
}
```

<!-- package-read-audit:record -->
```json
{
 "controlProbe": "not-engaged",
 "declinedExtension": [],
 "findings": [
  {
   "finding": "codex-R2PR-1",
   "lens": "spec-contradiction"
  },
  {
   "finding": "codex-R2PR-2",
   "lens": "coverage-exactly-once"
  },
  {
   "finding": "codex-R2PR-3",
   "lens": "spec-contradiction"
  },
  {
   "finding": "codex-R2PR-4",
   "lens": "coverage-exactly-once"
  },
  {
   "finding": "codex-R2PR-5",
   "lens": "coverage-exactly-once"
  },
  {
   "finding": "codex-R2PR-6",
   "lens": "coverage-exactly-once"
  },
  {
   "finding": "codex-R2PR-7",
   "lens": "dod-adequacy"
  },
  {
   "finding": "codex-R2PR-8",
   "lens": "dod-adequacy"
  },
  {
   "finding": "codex-R2PR-9",
   "lens": "dod-adequacy"
  },
  {
   "finding": "codex-R2PR-10",
   "lens": "dod-adequacy"
  },
  {
   "finding": "codex-R2PR-11",
   "lens": "dod-adequacy"
  },
  {
   "finding": "cursor-PR2-1",
   "lens": "collisions"
  },
  {
   "finding": "cursor-PR2-2",
   "lens": "coverage-exactly-once"
  },
  {
   "finding": "cursor-PR2-3",
   "lens": "coverage-exactly-once"
  },
  {
   "finding": "cursor-PR2-4",
   "lens": "spec-contradiction"
  },
  {
   "finding": "cursor-PR2-5",
   "lens": "spec-contradiction"
  },
  {
   "finding": "cursor-PR2-6",
   "lens": "collisions"
  },
  {
   "finding": "cursor-PR2-7",
   "lens": "spec-contradiction"
  },
  {
   "finding": "cursor-PR2-8",
   "lens": "dod-adequacy"
  },
  {
   "finding": "cursor-PR2-9",
   "lens": "dod-adequacy"
  },
  {
   "finding": "cursor-PR2-10",
   "lens": "dod-adequacy"
  },
  {
   "finding": "cursor-PR2-11",
   "lens": "dod-adequacy"
  }
 ],
 "invocation": "inv-1",
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
   "part": "children-C1-C2-C3-C6-C7-C9-C10-to-C17",
   "status": "unreviewed"
  },
  {
   "part": "children-C4-C5-C8",
   "status": "reviewed"
  },
  {
   "part": "register-R2-R3-R4-R6-R9-to-R14-R16-to-R26",
   "status": "reviewed"
  }
 ],
 "round": 2
}
```

<!-- round 2 notes (advisor, 2026-09-14): seats codex Sol high (11 findings, all Important or Minor) and cursor Grok xhigh (11 findings, all Important), both engaged by telemetry. The round-2 control probe (a one-word drift planted in C8's R6 quote) was NOT named by either seat, recorded as not-engaged; the register-quote check covers that lens mechanically and passes on every child, which is why the miss does not block. All 22 findings accepted as package fixes: R27's three birth duties; the plugin-root seam in R15/C15; C17's four declared dependencies and five shipped defaults; C1 owning all four promise-1 homes (merge-train.md and duty 6 moved from C2) with the tight-shell emphasis; the at-the-door rule to C2; C13's FR-D9 rules in the successor section; C7's document-layer rules; C6's foundational set at landing; C12's case 6 shape; C10's dropped-row echo; C11's failed-probe and scrub cases; C14's Astra pass criterion and scrub cases; C13's trigger and class-closure dry run; C15's scoped quota grep. Seat results: package-read/round-2-*.json. No round returned only mechanical items yet; round 3 (the ceiling) re-reads the changed parts. -->

<!-- package-read-audit:record -->
```json
{
 "controlProbe": "engaged",
 "declinedExtension": [],
 "findings": [
  {
   "finding": "codex-R3-01",
   "lens": "spec-contradiction"
  },
  {
   "finding": "codex-R3-02",
   "lens": "collisions"
  },
  {
   "finding": "codex-R3-03",
   "lens": "coverage-exactly-once"
  },
  {
   "finding": "codex-R3-04",
   "lens": "coverage-exactly-once"
  },
  {
   "finding": "cursor-R3-C1-01",
   "lens": "spec-contradiction"
  },
  {
   "finding": "cursor-R3-MAP-01",
   "lens": "coverage-exactly-once"
  },
  {
   "finding": "cursor-R3-C2-17-01",
   "lens": "collisions"
  },
  {
   "finding": "cursor-R3-C13-01",
   "lens": "dod-adequacy"
  },
  {
   "finding": "cursor-R3-C12-01",
   "lens": "coverage-exactly-once"
  },
  {
   "finding": "cursor-R3-C12-02",
   "lens": "dod-adequacy"
  },
  {
   "finding": "cursor-R3-C11-01",
   "lens": "coverage-exactly-once"
  },
  {
   "finding": "cursor-R3-C10-01",
   "lens": "dod-adequacy"
  },
  {
   "finding": "cursor-R3-C10-C6-01",
   "lens": "collisions"
  },
  {
   "finding": "cursor-R3-C12-C13-01",
   "lens": "collisions"
  }
 ],
 "invocation": "inv-1",
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
   "part": "register-R15-R19-R27",
   "status": "unreviewed"
  },
  {
   "part": "coverage-map.md",
   "status": "unreviewed"
  },
  {
   "part": "children-C1-C2-C6-C7-C10-to-C15-C17",
   "status": "unreviewed"
  },
  {
   "part": "children-C3-C4-C5-C8-C9-C16",
   "status": "reviewed"
  },
  {
   "part": "register-other-entries",
   "status": "reviewed"
  }
 ],
 "round": 3
}
```

<!-- round 3 notes (advisor, 2026-09-14): the ceiling round. Seats codex Sol high (4 findings: 3 Important, 1 Minor) and cursor Grok xhigh (10 findings, all Important), both engaged; both named the round-3 plant (the removed FR-A9 bullet-2 map row: codex-R3-04, cursor-R3-MAP-01), which is the control probe and not a package defect. The 12 real findings were applied as package fixes after the round (the receipt gates only the six pieces and the heartbeat; C7 after C15; the cache-served failure disclosure; C1's four homes graded together; the no-ladder rider on C2's carve-out; C13's stay-and-go list and coverage-replay rules; C12's misses-log duty, canary census, bump and transition-note bullets; C11's two-proposal tripwire; C10's transition-note and consumer-tell bullets; C6 consuming C10's three entries; the canary-census seam between C12 and C13). The round did not return only mechanical items, so the invocation reached its ceiling unconverged: PARKED to the owner with the children unfiled and the round-3 findings named. Those fixes are new authorship and have not been re-read. Seat results: package-read/round-3-*.json. -->

<!-- package-read-audit:record -->
```json
{
 "cause": "owner decision 2026-09-14 after inv-1 parked at its ceiling: re-read the round-3 fixes",
 "ceiling": 1,
 "invocation": "inv-2",
 "kind": "invocation",
 "measurables": {
  "children": 17,
  "registerEntries": 28
 },
 "override": "scoped to the round-3 changes; one dispatch per seat carrying all five lenses; the maker's family (Claude) excluded",
 "seats": [
  "codex:gpt-5.6-sol@high",
  "cursor:cursor-grok-4.6@xhigh"
 ],
 "weight": "full"
}
```

<!-- package-read-audit:record -->
```json
{
 "controlProbe": "not-engaged",
 "declinedExtension": [],
 "findings": [
  {
   "finding": "codex-REREAD-1",
   "lens": "spec-contradiction"
  },
  {
   "finding": "codex-REREAD-2",
   "lens": "spec-contradiction"
  },
  {
   "finding": "codex-REREAD-3",
   "lens": "dod-adequacy"
  },
  {
   "finding": "codex-REREAD-4",
   "lens": "coverage-exactly-once"
  },
  {
   "finding": "codex-REREAD-5",
   "lens": "register-drift"
  },
  {
   "finding": "codex-REREAD-6",
   "lens": "collisions"
  },
  {
   "finding": "codex-REREAD-7",
   "lens": "coverage-exactly-once"
  },
  {
   "finding": "codex-REREAD-8",
   "lens": "dod-adequacy"
  },
  {
   "finding": "cursor-UR2-1",
   "lens": "spec-contradiction"
  },
  {
   "finding": "cursor-UR2-2",
   "lens": "dod-adequacy"
  },
  {
   "finding": "cursor-UR2-3",
   "lens": "dod-adequacy"
  },
  {
   "finding": "cursor-UR2-4",
   "lens": "spec-contradiction"
  },
  {
   "finding": "cursor-UR2-5",
   "lens": "spec-contradiction"
  },
  {
   "finding": "cursor-UR2-6",
   "lens": "dod-adequacy"
  },
  {
   "finding": "cursor-UR2-7",
   "lens": "dod-adequacy"
  },
  {
   "finding": "cursor-UR2-8",
   "lens": "spec-contradiction"
  },
  {
   "finding": "cursor-UR2-9",
   "lens": "dod-adequacy"
  }
 ],
 "invocation": "inv-2",
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
   "part": "register-R15",
   "status": "unreviewed"
  },
  {
   "part": "children-C1-C2-C6-C7-C9-C10-to-C13-C15",
   "status": "unreviewed"
  },
  {
   "part": "coverage-map.md",
   "status": "reviewed"
  },
  {
   "part": "children-C3-C4-C5-C8-C14-C16-C17",
   "status": "reviewed"
  },
  {
   "part": "register-other-entries",
   "status": "reviewed"
  }
 ],
 "round": 1
}
```

<!-- invocation 2, round 1 notes (advisor, 2026-09-14): cause = the owner's ruling (a) after inv-1 parked; ceiling one. Seats codex Sol high (8 findings: 7 Important, 1 Minor) and cursor Grok xhigh (9 findings, all Important), both engaged by telemetry; NEITHER named this round's plant (C5 removing the worktree guard the spec keeps), recorded not-engaged. All 17 findings applied as package fixes: the six pieces retire as a set or not at all; the own-worktree prose stays; FR-D8's four checks named exactly; FR-D2's three counter-specimen shapes; the V-1 baseline with the weekly-eats corroboration and the fail-toward-alerting note; the class-closure negative case; C12's coverage re-run and closing notes; C6 moved to wave 1 with C12 after it (birth entries for the writer and checks); C6's consumer-report lifecycle and the bash-timeout log line (FR-F2.3 split C5/C6); C11's result-shape transition note and adapter check; C7's skill descriptions and what-remains bullets; C15's launch-ledger presence and narrowed quota grep. Not mechanical-only, so this invocation also reached its ceiling unconverged: PARKED to the owner a second time with the children unfiled. Seat results: package-read/inv2-*.json. Trend of findings per round: 31, 22, 14, 17; Critical: 13, 0, 0, 0. -->

<!-- package-read-audit:record -->
```json
{
 "findings": [
  {
   "disposition": "package-fix",
   "finding": "cursor-pkg-01",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "cursor-pkg-02",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "cursor-pkg-03",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "cursor-pkg-04",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "cursor-pkg-05",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "cursor-pkg-06",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "cursor-pkg-07",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "cursor-pkg-08",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "cursor-pkg-09",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "cursor-pkg-10",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "cursor-pkg-11",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "cursor-pkg-12",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "cursor-pkg-13",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "codex-pkg-01",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "codex-pkg-02",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "codex-pkg-03",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "codex-pkg-04",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "codex-pkg-05",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "codex-pkg-06",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "codex-pkg-07",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "codex-pkg-08",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "codex-pkg-09",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "codex-pkg-10",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "codex-pkg-11",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "codex-pkg-12",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "codex-pkg-13",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "codex-pkg-14",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "codex-pkg-15",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "codex-pkg-16",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "codex-pkg-17",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "codex-pkg-18",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "codex-R2PR-1",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "codex-R2PR-2",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "codex-R2PR-3",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "codex-R2PR-4",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "codex-R2PR-5",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "codex-R2PR-6",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "codex-R2PR-7",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "codex-R2PR-8",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "codex-R2PR-9",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "codex-R2PR-10",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "codex-R2PR-11",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "cursor-PR2-1",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "cursor-PR2-2",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "cursor-PR2-3",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "cursor-PR2-4",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "cursor-PR2-5",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "cursor-PR2-6",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "cursor-PR2-7",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "cursor-PR2-8",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "cursor-PR2-9",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "cursor-PR2-10",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "cursor-PR2-11",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "codex-R3-01",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "codex-R3-02",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "codex-R3-03",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "codex-R3-04",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "cursor-R3-C1-01",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "cursor-R3-MAP-01",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "cursor-R3-C2-17-01",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "cursor-R3-C13-01",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "cursor-R3-C12-01",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "cursor-R3-C12-02",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "cursor-R3-C11-01",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "cursor-R3-C10-01",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "cursor-R3-C10-C6-01",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "cursor-R3-C12-C13-01",
   "outcome": "verified"
  }
 ],
 "invocation": "inv-1",
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
  },
  {
   "child": "C9",
   "result": "pass"
  },
  {
   "child": "C10",
   "result": "pass"
  },
  {
   "child": "C11",
   "result": "pass"
  },
  {
   "child": "C12",
   "result": "pass"
  },
  {
   "child": "C13",
   "result": "pass"
  },
  {
   "child": "C14",
   "result": "pass"
  },
  {
   "child": "C15",
   "result": "pass"
  },
  {
   "child": "C16",
   "result": "pass"
  },
  {
   "child": "C17",
   "result": "pass"
  }
 ]
}
```

<!-- package-read-audit:record -->
```json
{
 "findings": [
  {
   "disposition": "package-fix",
   "finding": "codex-REREAD-1",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "codex-REREAD-2",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "codex-REREAD-3",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "codex-REREAD-4",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "codex-REREAD-5",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "codex-REREAD-6",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "codex-REREAD-7",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "codex-REREAD-8",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "cursor-UR2-1",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "cursor-UR2-2",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "cursor-UR2-3",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "cursor-UR2-4",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "cursor-UR2-5",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "cursor-UR2-6",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "cursor-UR2-7",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "cursor-UR2-8",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "finding": "cursor-UR2-9",
   "outcome": "verified"
  }
 ],
 "invocation": "inv-2",
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
  },
  {
   "child": "C9",
   "result": "pass"
  },
  {
   "child": "C10",
   "result": "pass"
  },
  {
   "child": "C11",
   "result": "pass"
  },
  {
   "child": "C12",
   "result": "pass"
  },
  {
   "child": "C13",
   "result": "pass"
  },
  {
   "child": "C14",
   "result": "pass"
  },
  {
   "child": "C15",
   "result": "pass"
  },
  {
   "child": "C16",
   "result": "pass"
  },
  {
   "child": "C17",
   "result": "pass"
  }
 ]
}
```

<!-- closing note (advisor, 2026-09-14): the owner ruled (a) at the second park: accept the package with the residual named (DoD completeness; second net = DoD sharpening at routing and the vet against the spec) and file. Every finding of both invocations was applied as a package fix and verified against its finding by the advisor; the mechanical sync check passes on all 17 children; the planted defects (rounds 1 and 3 caught by both seats, round 2 and inv-2 missed by both) are recorded as control probes, not defects. Filed on the owner's word of 2026-09-14. -->
