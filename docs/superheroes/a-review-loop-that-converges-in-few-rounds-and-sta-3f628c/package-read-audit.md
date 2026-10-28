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
   "part": "children/C3.md",
   "status": "unreviewed"
  },
  {
   "part": "children/C1-L3.md",
   "status": "unreviewed"
  },
  {
   "part": "children/C1-L12.md",
   "status": "unreviewed"
  },
  {
   "part": "register.md",
   "status": "reviewed"
  },
  {
   "part": "coverage-map.md",
   "status": "reviewed"
  },
  {
   "part": "children/C4.md",
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
   "evidence": "C3 DoD now keeps every outside finding a reviewer returns, above the cap included, with the cap in reviewer instructions (FR-28 second acceptance); round 2 both seats clean",
   "finding": "F1-C3-outside-cap-retention",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "evidence": "C1-L3 search lists the removal notice, its fixtures and the vetting.md call site C1-L12 replaces; C1-L12 re-runs the search without that exception; round 2 both seats clean",
   "finding": "F2-L3-scan-vs-L12-vetting",
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

Run by the advisor on 2026-10-28 against the breakdown branch's head (commit 5ad894fcc, after the Canon append and bringing the branch current with main, plus this trail), before the package goes to the owner for the merge word. Every body the filing creates is a file in this folder: the epic body (#2185's, rewritten in place), the four child bodies, and the thirteen layer bodies of C1's stack. The two seam files are quote blocks appended to #2189's and #2190's bodies, which are their side's register home.

| Body | `issue_contract.py check-build-ready` | `register_check.py check` (`--register-copy worktree`) |
| --- | --- | --- |
| epic.md | `ok: true` | (epic body) |
| children/C1.md | `ok: true` | C1: pass |
| children/C1-L1.md to children/C1-L13.md | `ok: true`, each | C1: pass (a stack layer is checked on C1's body with token C1, per register-check.md § Stack layer inputs) |
| children/C2.md | `ok: true` | C2: pass |
| children/C3.md | `ok: true` | C3: pass |
| children/C4.md | `ok: true` | C4: pass |
| seams/2189.md | (appended quote block) | #2189: pass (R9, R10) |
| seams/2190.md | (appended quote block) | #2190: pass (R11) |

Coverage: `coverage.py check` finds 72 acceptance bullets, 3 NFR lines and 2 Definition of done bullets, 78 rows (one split), each owned exactly once; errors none.

Owner rulings the package says are drafted in, and where each sits:
- Canon 2026-10-28-5692f27d-1 (the core loop ships first in one release; three add-ons, copies of a bug with or after outside findings) is in register R1, the epic's sequencing, C1's stack and the C2, C3 and C4 dependency lines.
- Canon 2026-10-27-0b372f49-2 (review-loop changes are considered in the discovery's planning session) was held on the collector; it is committed to `docs/superheroes/canon.md` on this branch.
- The advisor's two readings (R1's interim sentence; C2's reading of FR-8 with FR-10) are craft calls for the owner's veto at the merge word, stated in R1's Status and C2's body.

No State line calls any of them open. Result: verified.
