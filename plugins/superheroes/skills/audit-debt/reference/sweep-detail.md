<!-- sweep-detail-version: 1 -->

## Severity Recalibration for Debt Context

Restated for this skill (the base rubric's table is calibrated for diff review; debt review needs slightly different anchors):

| Tier          | Definition (debt context)                                                                                                     | Examples                                                                                                                                    |
| ------------- | ----------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| **Critical**  | Active security risk in shipped code — exploitable today, not "theoretical if X."                                             | An API route returning owner-scoped data without an ownership filter; a mutation without an ownership check; a missing admin gate on an admin-only route |
| **Important** | Bug waiting to happen (will trigger under normal use) OR significant architecture violation that is making future work harder | A handler that throws on malformed input and surfaces as a 500; a 900-line unit with 8 responsibilities; an untested route handler          |
| **Minor**     | Real issue, small impact — consistency, missing test on a low-risk path, small refactor, minor abstraction creep              | A magic number; one route hardcodes error strings while others use the project's error constants; a util used by only one caller            |
| **Nit**       | Cleanup / naming / dead code that doesn't change behavior or risk                                                             | An unused export; inconsistent comment style; an outdated TODO that's no longer relevant                                                    |

Apply this rubric in §5 compile + prioritization. The diff-scope tier (`Pre-existing`) does **not** apply in debt mode — pre-existing IS the point.

## Effort Labels

Required on every finding. Subagents are told to emit this in §3; orchestrator-derived findings include it in §4.

| Label       | Range                | Examples                                                                                                                                             |
| ----------- | -------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Quick**   | <30 minutes          | Rename a misleading variable; replace a hardcoded string with an error constant; swap a hardcoded value for a shared token; a dependency-audit auto-fix |
| **Medium**  | 30 minutes – 4 hours | Refactor a unit to remove a duplicate pattern; write tests for an existing API route; fix an IDOR with a dual-filter; close a TODO with a small impl |
| **Big-job** | Multi-session        | Restructure a feature directory; migrate a data-store schema; replace a transitive dependency; rewrite a 900-line unit                              |

The `severity × inverse-effort` sort means an `Important + Quick` finding ranks above an `Important + Big-job`. Big-jobs aren't deprioritized because they don't matter — they're presented later because they need scheduling, not a same-day fix.

## Common Mistakes

| Mistake                                                            | Fix                                                                                                                                                                        |
| ------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Flagging pre-existing code as "debt" when it's working as designed | Debt = rotted, not just unfamiliar. If the pattern is intentional and consistent across the codebase, it's convention, not debt.                                           |
| Over-counting Nits and burying the real findings                   | Nit cap (5) applies the same as in `/review-crew:review-code`. A Nit avalanche in a debt audit is signal that the auditor is reaching — dedupe or drop.                    |
| Missing the difference between "could improve" and "is broken"     | `could improve` is Minor at best; only flag Important if you can name what will actually break. Critical is reserved for active security risk in shipped code.             |
| Citing files that don't exist                                      | `§5 step 2` (existence check) drops these at compile time. Subagents under sweep dispatch sometimes hallucinate paths — the orchestrator catches it.                       |
| Treating consistent patterns as drift                              | Consistency > novelty. If 12 of 13 routes use the same pattern, the 13th matching is **consistency**, not debt. If 6 use pattern A and 7 use pattern B, THAT is drift.     |
| Mapping every dependency-audit advisory to Critical                | Advisory severity is a hint, not a verdict — `moderate` maps to Minor in this skill. If the vulnerable code path isn't reachable in our usage, the advisory is even lower. |
| Running this before every PR                                       | This skill is slow and broad by design. Run it monthly. For PR review, use `/review-crew:review-code`.                                                                     |
| Filing noisy findings the owner won't action                       | Issue-filing is NOTIFY — findings are filed by default and reported back; use the **File** / **Drop** deselect pass to trim, and hard-floor trackers (public/shared/paid) still GATE.                           |
| Running a deps pass when no audit tool ran                         | The deps audit is ecosystem-aware and skips gracefully (no manifest, or tool absent). If §1 wrote no audit artifact, emit no deps findings — don't invent advisories.     |
| Dispatching reviewers by reading an agent file                     | The four reviewers are bundled plugin agents — dispatch the `<name>` reviewer with its methodology (resolve dispatch via the host tool map (`hosts/<host>-tools.md` at the plugin root)).                          |
| Skipping the profile bootstrap                                     | If `.claude/review-profile.md` is absent, run review-init's create procedure inline first. Headless runs get a provisional strict profile.                                 |

## Recording Decisions (Helper Reference)

audit-debt's resolution point is the §5 issue-gate (File / Drop, and the auto-included Fix/Defer). Append ONE record per decision to the **project-level** learning-loop store at the resolved `$DECISIONS` path (NOT the temp `$SESSION_DIR`). Use the bundled helper:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
python3 "$ROOT_DIR/lib/decisions.py" \
  append "$DECISIONS" '<record-json>'
```

`<record-json>` is `{"dimension": "<finding dimension>", "category": "<finding taxonomy/topic>", "action": "skip"|"guidance"|"fix"}`:
- `action` maps from the issue-gate decision: **filed** (auto-included `Fix`/`Defer`, or **File**) → `fix`; **Drop**/deselected → `skip`. `guidance` does not arise here (audit-debt files or drops; it never edits code).
- `dimension` is the finding's `dimension`; `category` is the finding's taxonomy/topic (its normalized title or topic tag). The store is append-only and atomic; it soft-fails on a bad/missing store, so this never blocks.
