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

<!-- package-read-audit:record -->
```json
{
 "controlProbe": "engaged",
 "declinedExtension": [],
 "findings": [
  {
   "finding": "cursor3-2",
   "lens": "collisions"
  },
  {
   "finding": "cursor3-3",
   "lens": "collisions"
  },
  {
   "finding": "codex3-2",
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
 "mechanicalOnly": true,
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
   "part": "C3",
   "status": "unreviewed"
  },
  {
   "part": "C4",
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
   "part": "C8",
   "status": "unreviewed"
  },
  {
   "part": "C8-L1",
   "status": "unreviewed"
  },
  {
   "part": "C8-L3",
   "status": "unreviewed"
  },
  {
   "part": "README",
   "status": "reviewed"
  },
  {
   "part": "epic",
   "status": "reviewed"
  },
  {
   "part": "C4-L3",
   "status": "reviewed"
  },
  {
   "part": "C6",
   "status": "reviewed"
  },
  {
   "part": "C8-L2",
   "status": "reviewed"
  },
  {
   "part": "C8-L4",
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
   "evidence": "R11: unset seat uses an installed cross-family engine; quotes and C3/C5-L1 handback cases synced (6a0b42cd).",
   "finding": "codex-1",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "evidence": "R18 draft-verdict persistence; C8-L3 DoD requires restore on reopen (6a0b42cd).",
   "finding": "codex-2",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "evidence": "C1, C5-L2, C6 DoD bullets record the amendment stamp in TRANSITION (6a0b42cd).",
   "finding": "codex-5",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "evidence": "C4-L3 writing-pass records quoted in the PR body.",
   "finding": "cursor-ind-3",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "evidence": "C8-L2/L3/L4 44px bullets name recorded run and search.",
   "finding": "cursor-ind-4",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "evidence": "R11 treats a same-family seat like unset; same-family path only with no different-family engine (231dcb82).",
   "finding": "codex2-1",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "evidence": "C8/C8-L3 prose match R18 draft verdict (231dcb82).",
   "finding": "codex2-4",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "evidence": "Same fix as codex2-1.",
   "finding": "cursor2-ind-2",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "evidence": "C8-L1 44px bullet names recorded 375px run and theme search.",
   "finding": "cursor2-ind-3",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "evidence": "C4-L4 takeover bullet names a recorded second-session run.",
   "finding": "cursor2-ind-4",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "evidence": "C5 DoD mapping and layer line include the front-half amends item.",
   "finding": "cursor3-2",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "evidence": "README C5 count 17 to 18.",
   "finding": "cursor3-3",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "evidence": "Covered by cursor3-2/3; coverage-map heading no longer says non-child owner.",
   "finding": "codex3-2",
   "outcome": "verified"
  },
  {
   "disposition": "package-fix",
   "evidence": "Amends item 1 owned by C5; C5-L2 DoD confirms the 2026-10-04 front-half entry (231dcb82).",
   "finding": "codex-4",
   "outcome": "verified"
  },
  {
   "disposition": "declined-extension",
   "evidence": "Re-flag on unchanged text; fixed without extension (amends item 1 to C5).",
   "finding": "codex2-2",
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

Run by the advisor on 2026-10-05, against branch head `advisor/breakdown-1614` (the package as it will merge), with the plugin at 0.40.0.

- **`issue_contract.py check-build-ready`, every body the filing creates:** `ok: true` for all 21 bodies: the epic, C1–C8, and the twelve layers (C4-L1 to C4-L4, C5-L1, C5-L2, C7-L1, C7-L2, C8-L1 to C8-L4).
- **`register_check.py check --register-copy worktree`, register-consuming bodies:**
  - **Children, own body and token, all `pass`:** C1 (10 required entries), C2 (8), C3 (11), C4 (23), C5 (12), C6 (15), C7 (3), C8 (7).
  - **Layers, own body under the bare layer token, all `pass`:** C4-L1 (10), C4-L2 (1), C4-L3 (4), C4-L4 (7), C5-L1 (8), C5-L2 (2), C7-L1 (2), C7-L2 (1), C8-L1 (2), C8-L2 (3), C8-L3 (1), C8-L4 (3).
  - The layers' binding check (the feature body under the feature token) is covered by the children's passes above.
  - The epic quotes no register entry.
- **Owner rulings the package or the PR body says are drafted in, and where each sits:**
  - The approval of both specs: the specs' frontmatter (`status: approved`, `approved: "2026-10-04"`) and handoff ruling 62 (`docs/superheroes/discovery-notes/spec-alignment/HANDOFF.md`).
  - Ruling 26 (the breakdown in the same PR) and ruling 56 (the specs in `docs/superheroes/` through this PR): handoff rulings 26 and 56.
  - Ruling 57 (one setup sitting with #1472): handoff ruling 57, quoted in register R12.
  - The front-half-sdlc-core FR-16/FR-17 amendment: that spec's Amendments log, entry dated 2026-10-04.
  - None of these is called open anywhere in the files.
- **Result:** verified. No missing body, every build-ready result `ok`, every register check `pass`, every ruling found.
