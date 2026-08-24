# Orchestrator-run bite-proof records — #1109 round 4

Every proof below was produced **by the orchestrator**, in the build worktree, against the
integrated head, using the discipline in `plugins/superheroes/rubric/bite-proof.md`: the guarded
behaviour is neutralized with the smallest edit that removes it, the test is shown **red with the
test itself unedited**, the mutation is reverted with an inverse edit, and the test is shown
**green**. `git status --porcelain` was confirmed empty after every restore.

Two groups:

- **Part 1 — the eight regenerated records.** The original build's implementers reported running
  these proofs, but their records were destroyed in transit by the very transport defect this PR
  repairs (PR body: *"Bite-proof records are missing for eight of nine detectors"*). They are
  **re-earned here from scratch**, not transcribed. BP9 (the resultKind drift gate) was already
  recorded by the round-1 orchestrator and is not repeated.
- **Part 2 — the six detectors this round added or changed.** The implementers produced their own
  records (`wo_r4_a.md`, `wo_r4_b.md`); these are the orchestrator's **independent re-runs**, which
  is what the receipt rests on.

---

## Part 1 — regenerated records for the original build's detectors

### 1. Multi-contract refusal — an object matching two result contracts is refused

**Guarded element:** `engine_adapter._recognised_review_kinds` returns **every** matching kind, so a
payload that satisfies two contracts at once can be refused rather than silently graded as one.

- **Mutation:** `return matched` → `return matched[:1]` (report only the first match).
- **Red:** `4 failed, 470 deselected in 0.31s` — `test_review_result_kind_census_refuses_multiple_contracts`.
- **Green after inverse edit:** `4 passed, 470 deselected in 0.22s`.

### 2. Grouping payload validation gate

**Guarded element:** an invalid `grouping` payload is `unreadable`, never `ok`.

- **Mutation:** in `_parse_review_grouping_object`, `if not _grouping_payload_valid(grouping):` → `if False:`.
- **Red:** `4 failed, 470 deselected in 0.32s` — `test_parse_result_review_grouping_invalid_unreadable`.
- **Green:** `4 passed, 470 deselected in 0.22s`.

### 3. Out-of-enum ruling rejection — **guarded twice; recorded honestly**

**Guarded element:** a `ruling` value outside `audits.AUDIT_RULINGS` is not recognised as a ruling.

This one is **redundantly guarded**, and the record says so rather than claiming a single clean bite:

- Neutralizing **only** the matcher's enum check (`ruling not in audits.AUDIT_RULINGS`) →
  `1 passed` — still protected, because `_parse_review_ruling_object` re-validates through the
  P_AUDITS contract.
- Neutralizing **only** the contract chokepoint (`_audit_ruling_payload_valid` → `return True`) →
  the out-of-enum test still passes — still protected by the matcher.
- Neutralizing **both** → `1 failed, 473 deselected in 0.25s`. **Red.**
- **Green after both inverse edits:** included in record 4's green run below.

A single-mutation proof here would have been **vacuous**, and reporting one would have been a false
receipt. Defense in depth is the finding, not a failure.

### 4. Ruling contract chokepoint — id validity and the `new-issue` → `newIssues` conditional

**Guarded element:** `_audit_ruling_payload_valid` delegating to `round_adapters.payload_fault(P_AUDITS, …)`.

- **Mutation:** function body → `return True`.
- **Red:** `6 failed, 1 passed, 467 deselected in 0.37s` — the malformed-id parametrizations and
  `test_parse_result_review_ruling_new_issue_without_usable_new_issues_unreadable`. (The 1 pass is
  record 3's out-of-enum case, still held by the matcher.)
- **Green:** `7 passed, 467 deselected in 0.22s`.

### 5. `investigated` path normalization

**Guarded element:** `_normalize_investigated_path_string` — surrounding whitespace and wrapping
backticks are stripped before a path is accepted into the investigation record.

- **Mutation:** body reduced to `return path_val` (no strip, no backtick unwrap).
- **Red:** `2 failed, 15 passed, 457 deselected in 0.29s` — `test_spot_check_investigated_entry_format_normalization`.
- **Green:** `17 passed, 457 deselected in 0.22s`.

### 6. Vacuous floor — an empty grouping does not clear the investigation-record floor

**Guarded element:** `engagement_read`'s grouping branch requires a **non-empty list**, so
`grouping: null` / `grouping: []` cannot certify a seat as engaged.

- **Mutation:** `if isinstance(payload, list) and payload:` → `if "grouping" in result:`.
- **Red:** `1 failed, 4 passed in 0.88s` — `test_engagement_read_empty_grouping_not_engaged`.
- **Green:** `5 passed in 0.81s`.

### 7. The stdout cap names itself — a truncated report is not blamed on the workspace

**Guarded element:** the `_attempt_stdout_truncated` → `_stdout_capped_forfeit` branch in
`_supervise`, which mints `stdout-capped-by-attempt` **before** the dirt check can mint
`worktree-dirtied-by-attempt`. This is defect 3, the one that cost WO-A its entire report on PR #1083.

- **Mutation:** `if truncated_bytes is not None:` → `if False:` (fall through to the dirt path).
- **Red:** `1 failed, 352 deselected in 1.16s` — `test_truncated_attempt1_stdout_capped_forfeit_not_dirtied`, `KeyError: 'forfeited'`.
- **Green:** `1 passed, 352 deselected in 2.95s`.

### 8. Foreign-leased sibling worktrees are excluded from this attempt's dirt

**Guarded element:** `_filter_porcelain_for_foreign_worktrees` applied to the filtered-mode snapshot.

- **Mutation:** `if mode == "filtered" and excluded_roots:` → `if False and …`.
- **Red:** `1 failed, 2 passed in 1.63s` — `test_nested_foreign_leased_sibling_no_dirt_forfeit`.
- **Green:** `3 passed in 1.59s`.

**Recorded limitation:** the *peer*-sibling test does **not** go red under this mutation, and that is
correct rather than a gap — a peer worktree lives outside the dispatching worktree and never enters
its porcelain, so only the **nested** case exercises the filter. This matches the round-1
orchestrator's own correction of defect 5's mechanism against the issue text.

---

## Part 2 — orchestrator re-runs of this round's six new/changed detectors

| Proof | Guarded element | Mutation | Red | Green |
| --- | --- | --- | --- | --- |
| A1 | bounded stdout-cap read | restore `fh.read()` whole-file | `2 failed`: `assert 32768 <= 4137`, `assert 12288 <= 2089` | `2 passed` |
| A2b | porcelain **mode replay** in `_worktree_dirt_verdict` | re-derive mode from live enumeration | `24 failed, 24 passed` | `48 passed` |
| B1 | malformed audit `id` rejection | `_audit_ruling_payload_valid` → `return True` | `5 failed` | `5 passed` |
| B2 | grouping contract **delegation** to `round_adapters` | restore the hand-written `member_ids` loop | `1 failed` (`round_adapters.P_SYNTHESIS` absent from source) | `2 passed` |
| B3 | envelope gate receives the real payload | restore hard-coded `[]` | `1 failed, 3 passed` (`[grouping]`) | `4 passed` |
| B4 | `grouping` passes the secret-scrub seam | return the payload unscrubbed | `1 failed, 3 passed` (`[grouping]`) | `4 passed` |

**On A2b — why the implementer's first proof did not count.** WO-R4-A's original A2 proof went red
on a *metadata* difference (a `mode` key appearing in a compared dict), not on the porcelain
asymmetry the fix exists to guard. I measured that directly: with the mode-replay removed and the
test's git stub as shipped, **all 48 parametrizations passed** — the test could not fail. Making the
stub mode-sensitive the way real git is (default collapses an untracked directory to one entry,
`-uall` enumerates its files) turned it into a real detector: **24 of 48 fail** with the defect,
**48 pass** with the fix. That correction was ordered as WO-R4-A2 and is the proof recorded above.

**On B3/B4 — the shape of the red matters.** In both, exactly the `[grouping]` parametrization fails
while `findings`, `verdicts` and `ruling` pass. That is the finding restated as a test: these were
never boundary-wide failures, they were one new kind skipping a rule the boundary already applied to
every other kind.
