# Continuation-7 (#1107) — the 45 owed bite-proof elements, re-run on the final head

**Head:** `df39f8f8` (`feat/1107-review-driver-defects`; `origin/main` `4a9efbbf` is an ancestor).
**Who ran them:** the orchestrator, in its own detached worktree at that head — not inherited from
any implementer report.

This file is the **superseding fresh proof** for the 45 elements the continuation-6 park listed as
owed, across 11 records. Per the established convention the **original records are left
byte-for-byte**; where a recorded figure or quoted assertion has moved, the superseding capture is
below and the per-element note says what moved. The five `wo_c6A_1107.md` elements are not repeated
here — they were re-run in continuation-6 on this same head.

## Method (identical for every element)

- Neutralize **production**, never the detector, as a targeted revertible edit through the host's
  edit action — never a whole-file rewrite, never an ad-hoc shell edit, never a git discard.
- Select by **exact pytest node id** (never `-k`).
- Capture the **runner's own exit status** — output redirected to a file, never a pipe (a piped
  `tail` reports the tail's status, not pytest's).
- Restore with the **inverse edit**, then `git status --porcelain` — **empty after every restore**.
- Every run: `/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-c7 -m pytest … -q -p no:xdist`.

**Normalization, stated because it changes what the runs mean.** The `pycache_prefix` keeps Apple
Python's out-of-tree bytecode cache (`~/Library/Caches/com.apple.python/`) from serving stale
objects across the same-second edits every mutation here makes. Every run was **serial**
(`-p no:xdist`), never under `-n auto`.

## Results — 45 of 45, all red then green

| # | Record | Element | Red | Green |
|---|---|---|---|---|
| 1 | `wo_rbA` | BP-rbA1 mode-owner routing | `1 failed in 0.12s`, exit 1 | `1 passed in 0.11s`, exit 0 |
| 2 | `wo_rbA` | BP-rbA2 `MODE_EVIDENCE` registry membership | `1 failed in 0.61s`, exit 1 | `1 passed in 0.60s`, exit 0 |
| 3 | `wo_rbB` | E1 `STATUSES` disposition census | `1 failed in 0.12s`, exit 1 | `1 passed in 0.11s`, exit 0 |
| 4 | `wo_rbB` | E2 `appends_degradation` fail-closed | `1 failed in 0.12s`, exit 1 | `1 passed in 0.11s`, exit 0 |
| 5 | `wo_rbB` | E3 skew chokepoint census | `1 failed in 0.18s`, exit 1 | `1 passed in 0.15s`, exit 0 |
| 6 | `wo_rbE` | BP-1 `unknown-seat` doc token | `1 failed in 0.17s`, exit 1 | `1 passed in 0.14s`, exit 0 |
| 7 | `wo_c4B` | E1 unencodable manifest version gate | `1 failed in 0.07s`, exit 1 | `1 passed in 0.06s`, exit 0 |
| 8 | `wo_c5A` | E1 derived-placeholder registry drift | `1 failed in 0.14s`, exit 1 | `1 passed in 0.12s`, exit 0 |
| 9 | `wo_c4A` | E1 receipt-class validation | `1 failed in 0.43s`, exit 1 | `1 passed in 0.37s`, exit 0 |
| 10 | `wo_c4A` | E2 receipt-declaration census | `1 failed in 0.12s`, exit 1 | `1 passed in 0.11s`, exit 0 |
| 11 | `wo_c4A` | E3 empty head diff materializes | `1 failed in 0.16s`, exit 1 | `1 passed in 0.11s`, exit 0 |
| 12 | `wo_c4A` | E4 empty head diff, audits placeholders | `1 failed in 0.25s`, exit 1 | `1 passed in 0.18s`, exit 0 |
| 13 | `wo_c5C` | E1 open-blocker dedupe identity census | `1 failed in 0.13s`, exit 1 | `1 passed in 0.12s`, exit 0 |
| 14 | `wo_c5C` | E2 unknown skew status certifies non-`absent` | `1 failed in 0.44s`, exit 1 | `1 passed in 0.37s`, exit 0 |
| 15 | `wo_c5C` | E3 fix-batch unconditional refusal | `1 failed in 0.12s`, exit 1 | `2 passed in 0.11s`, exit 0 |
| 16 | `wo_c5C` | E4 skew vocabulary doc census | `1 failed in 0.24s`, exit 1 | `1 passed in 0.21s`, exit 0 |
| 17 | `wo_rc1` | BP-rc1-1 meta-wins precedence | `1 failed in 0.05s`, exit 1 | `1 passed in 0.04s`, exit 0 |
| 18 | `wo_rc1` | BP-rc1-2 receipt-mode routing | `1 failed in 0.44s`, exit 1 | `5 passed in 0.38s`, exit 0 |
| 19 | `wo_rc1` | BP-rc1-3 guard single-sourcing | `1 failed in 0.16s`, exit 1 | `1 passed in 0.14s`, exit 0 |
| 20 | `wo_rc1` | BP-rc1-4 raw-mode-read census | `1 failed in 0.17s`, exit 1 | `1 passed in 0.14s`, exit 0 |
| 21 | `wo_stall` | BP1 guard owner | `1 failed in 0.15s`, exit 1 | `1 passed in 0.14s`, exit 0 |
| 22 | `wo_stall` | BP2 escalation owner | `1 failed in 0.17s`, exit 1 | `1 passed in 0.16s`, exit 0 |
| 23 | `wo_stall` | BP3 routing isolation | `1 failed in 0.13s`, exit 1 | `1 passed in 0.13s`, exit 0 |
| 24 | `wo_stall` | BP4 composition owner | `1 failed in 0.14s`, exit 1 | `1 passed in 0.13s`, exit 0 |
| 25 | `wo_stall` | BP5 routing totality | `1 failed in 0.14s`, exit 1 | `1 passed in 0.13s`, exit 0 |
| 26 | `wo_stall` | BP6 attempt allocator | `1 failed in 0.40s`, exit 1 | `1 passed in 0.39s`, exit 0 |
| 27 | `wo_stall` | BP7 empty-resolution converge | `1 failed in 0.11s`, exit 1 | `1 passed in 0.10s`, exit 0 |
| 28 | `wo_r2` | BP-A1 member validation at the open-set boundary | `2 failed, 2 passed in 0.37s`, exit 1 | `11 passed in 1.93s`, exit 0 |
| 29 | `wo_r2` | BP-A2 single-constructor census | `1 failed in 0.17s`, exit 1 | `11 passed in 1.93s`, exit 0 |
| 30 | `wo_r2` | BP-B structure pins are AST, not substring | `1 failed in 0.14s`, exit 1 | `6 passed in 0.18s`, exit 0 |
| 31 | `wo_r2` | BP-C1 containment at the materialization chokepoint | `1 failed in 0.12s`, exit 1 | `17 passed in 0.79s`, exit 0 |
| 32 | `wo_r2` | BP-C2 disclosure channel registration | `1 failed in 0.44s`, exit 1 | `2 passed in 0.37s`, exit 0 |
| 33 | `wo_r2` | BP-D1 doc drift, doc side | `1 failed in 0.12s`, exit 1 | `1 passed in 0.11s`, exit 0 |
| 34 | `wo_r2` | BP-D2 doc drift, code side | `1 failed in 0.12s`, exit 1 | `6 passed in 0.11s`, exit 0 |
| 35 | `wo_r2` | BP-E receipt consumer for `priorCommentsUnavailable` | `1 failed in 0.44s`, exit 1 | `2 passed in 0.37s`, exit 0 |
| 36 | `completion_round` | BP-CR-1 receipt key partition is total | `3 failed, 4 passed in 0.13s`, exit 1 | `7 passed in 0.11s`, exit 0 |
| 37 | `completion_round` | BP-CR-2 attested validator reads the declaration | `1 failed, 6 passed in 0.12s`, exit 1 | `7 passed in 0.11s`, exit 0 |
| 38 | `completion_round` | BP-CR-3 each builder strips exactly its forbidden set | `3 failed, 4 passed in 0.13s`, exit 1 | `7 passed in 0.11s`, exit 0 |
| 39 | `completion_round` | BP-CR-4 materializer census derives from the registry | `1 failed, 5 passed in 0.12s`, exit 1 | `6 passed in 0.11s`, exit 0 |
| 40 | `completion_round` | BP-CR-5 `fix-batch.json` round-trips a non-empty batch | `1 failed, 5 passed in 0.12s`, exit 1 | `6 passed in 0.11s`, exit 0 |
| 41 | `completion_round` | BP-CR-6 v2 certified receipts omit `verifyPasses` | `1 failed in 0.16s`, exit 1 | `29 passed in 20.58s`, exit 0 |
| 42 | `completion_round` | BP-CR-7 binding-failure token count pin | `1 failed in 0.15s`, exit 1 | `10 passed in 1.44s`, exit 0 |
| 43 | `completion_round` | BP-CR-8 every non-`receipt-invalid:` token closes to the allowlisted reason | `5 failed, 5 passed in 1.46s`, exit 1 | `10 passed in 1.44s`, exit 0 |
| 44 | `completion_round` | BP-CR-9 the interim receipt still surfaces its own token | `1 failed in 0.31s`, exit 1 | `1 passed in 0.35s`, exit 0 |
| 45 | `completion_round` | BP-CR-11 checkpoint stop-reason vocabulary ↔ doc (A **and** B) | A `1 failed in 0.16s`; B `1 failed in 0.16s`, exit 1 each | A `1 passed in 0.14s`; B `1 passed in 0.14s`, exit 0 each |

**`BP-CR-10` is not in the count** — it was retired as vacuous in `completion_round_1107.md` and
stays retired; nothing here revives it.

## What the re-run changed, per element

Nothing below changes a verdict: every element that was recorded as biting still bites. These are
the places where the **recorded capture** no longer matches what the detector emits today, plus two
places where the re-run used a **stronger** neutralization than the original record.

### Superseded — the detector was narrowed after the record was written

- **`wo_stall` BP3, BP4.** Both records quote a **substring** assertion
  (`assert '_park_cannot_certify' not in …`). The detector is now AST-based, and the fresh reds read
  `assert not True` / `where True = _subtree_has_bare_name_call(…)`. Same axis, stronger detector,
  different quoted text.
- **`wo_stall` BP5 — the important one.** That record does **not** carry a red at all: it states its
  own red was superseded because the substring pin did not bite (the comment still carried the token),
  i.e. it captured a **false green** and deferred to `wo_r2` BP-B. On this head the AST pin bites
  directly: deleting the `_settle_delta_converged(state, config)` call from the `else:` branch gives
  `1 failed in 0.14s`, exit 1, with
  `assert False +  where False = _subtree_has_bare_name_call(<ast.FunctionDef …>, '_settle_delta_converged')`.
  **`wo_stall` BP5 now has a genuine red of its own.**
- **`wo_r2` BP-B counter-factual re-verified.** With the call deleted and the explanatory comment
  left in place, the token `_settle_delta_converged` is still present inside the function (confirmed
  by grep: 1 occurrence). The old substring assertion would still have passed; the AST pin fails.

### Superseded — figures moved because sibling tests were added

- **`wo_rbA` BP-rbA1:** the record quotes the failing test at `test_prior_comments_mode.py:33`; it is
  line 221 on this head (file reorganized by later orders). Assertion and outcome unchanged.
- **`wo_rc1` BP-rc1-2 green:** record `5 passed, 377 deselected` (a `-k` selection). Re-run **by the
  five exact node ids** instead — `5 passed in 0.38s`. (`-k` was also run for comparison and gives
  `5 passed, 379 deselected in 0.40s`; the deselected count moved, the five selected did not.)
- **`wo_r2` BP-C1 green:** record `13 passed`; now `17 passed in 0.79s` (whole file).
- **`completion_round` BP-CR-1 / BP-CR-2 / BP-CR-3 green:** record `6 passed`; now `7 passed`
  (`test_receipt_schema_declaration.py` gained a test).
- **`completion_round` BP-CR-6 green:** record `26 passed`; now `29 passed in 20.58s`
  (`test_interim_receipt.py` gained tests).

### Strengthened — a production-side neutralization replaced a test-side one

- **`wo_r2` BP-D2.** The original record neutralizes by setting the test file's inert
  `_PROBE_EXTRA_ARTIFACT` hook, and discloses that as a residual (a proof affordance living in
  committed code). This re-run instead neutralized **production**: a materializer entry producing
  `brand-new-artifact.json` was added to `ROUND_MATERIALIZER_REGISTRY` in `round_driver.py`, so the
  code-derived set genuinely gains an artifact the docs do not name. Red:
  `assert 'brand-new-artifact.json' in '**Order-input ownership.** …'`, `1 failed in 0.12s`, exit 1.
  The detector was left unedited. **The `_PROBE_EXTRA_ARTIFACT` residual disclosed in `wo_r2_1107.md`
  still stands as a residual** — this re-run shows the axis can be proven without it, it does not
  remove the hook.
- **`completion_round` BP-CR-9.** The original record's neutralization lives **inside** the detector
  (it loads a `tmp_path` copy of `handback_gate.py` with the interim branch removed), so the proof
  has no external red. This re-run additionally neutralized the **shipped** chokepoint — deleting the
  `receipt-interim-not-handback-evidence` branch from `handback_gate.py` — which turns the detector's
  shipped-side assertion red:
  `assert 'handback-verdict-not-allowlisted' == 'receipt-interim-not-handback-evidence'`,
  `1 failed in 0.31s`, exit 1. Restored by the inverse edit; `grep -c 'if False'
  plugins/superheroes/lib/handback_gate.py` → **0** afterwards.

### Limitations re-confirmed, not smoothed over

- **`wo_r2` BP-A1** reproduces its recorded honest limitation exactly: of the four parametrized
  cases only the two using `{}` go red (`2 failed, 2 passed`), because `0` and `None` are hashable
  and still reach a park by another route. Read "4 cases" as one detector plus three siblings, not
  four independent detectors.
- **`completion_round` BP-CR-4** remains a **test-side** mutation (the guarded element is the
  test's derivation logic), so it shows the derivation axis is load-bearing but cannot show
  production behaviour changing. Its production-side counterpart is BP-CR-5.
- **`completion_round` BP-CR-8** re-confirms its recorded limitation: five cases bite — the three
  token-mapping cases **and both** fail-closed edges (`None` and `""`) — while the **interim** case
  stays green under this mutation, which is exactly why BP-CR-9 exists. The protected detector
  `test_handback_gate.py::test_receipt_verdict_mismatch_refuses` also goes red under the same
  mutation (`1 failed in 0.30s`, exit 1), so the pre-existing detector and the census agree.

## Tree integrity

`git status --porcelain` was checked **after every single restore** and was empty each time. After
all 45 elements: `git status --porcelain` empty, `git diff --stat` empty, `git diff HEAD --stat`
empty, `HEAD` still `df39f8f8`. No probe reached uncommitted work, because there was none — the
adopted head was clean before the first probe ran.
