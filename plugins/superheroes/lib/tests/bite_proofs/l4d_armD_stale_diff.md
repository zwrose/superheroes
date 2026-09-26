# Layer 4d part (i) bite-proof record — stale-diff fail-open (arm D shadow of #1419)

## Heads `446fcb52` / `4d16b0d4`: only the derivation call records the reviewed head (advisor vet 320)

The probes ran in a detached probe worktree (Z1–Z2 at `446fcb52`, Z3 at `4d16b0d4`) that no review
session was reading. Each neutralization was a targeted edit, reverted by the inverse edit; the
detectors were left unedited. After each restore, `git status --porcelain` printed nothing, and
`test_layer4d_stale_diff_1419.py` gave `93 passed` (at `446fcb52`) and `94 passed` (at `4d16b0d4`).

| # | Neutralization | Red (test → raw) |
|---|---|---|
| Z1 | `new_state`: the pair reads `_DERIVED_DIFF_HEAD.get() or cfg.get("diffHead")` again, and `cfg.pop("diffHead", None)` → `pass` | `test_a_supplied_diff_head_never_reaches_the_certificate` → `assert ('aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' is None)` (the supplied SHA recorded). The same state through `_terminal_converged` → `terminal= converged`, `certifiedHead= aaaa…`; restored → `terminal= cannot-certify`, `reason= reviewed-head-unrecorded: …` |
| Z2 | `_cmd_next_locked`: `if isinstance(config_overrides, dict) and "diffHead" in config_overrides:` → `if False and …` | the same test → `{'action': 'dispatch-panel', 'attempt': 0, …, 'ok': True, …}` / `assert (True is False)` (a supplied head accepted in-process) |
| Z3 | `_recorded_review_head`: `if "diffHead" in (state.get("config") or {}):` → `if False and …` | `test_a_resumed_state_carrying_a_config_diff_head_never_certifies` → `{'certification': {… 'certifiedHead': 'b53808be…', …}, 'verdict': 'converged'}` / `assert 'converged' == 'cannot-certify'` |

## Head `e9554246`: the recorded pair or nothing; one derivation feeds both setup bindings (S11 fix leg, advisor ruling (b))

The probes ran in a detached probe worktree at `e9554246` that no review session was reading.
Each neutralization was a targeted edit, reverted by the inverse edit; the detectors were left
unedited. After the last restore, `git status --porcelain` printed nothing, and
`test_layer4d_stale_diff_1419.py` gave `92 passed`. The ruled proof is Y1 (make the digest
optional again, and the probe state certifies); Y2–Y4 cover the S11 gap-sweep fixes.

| # | Neutralization | Red (test → raw) |
|---|---|---|
| Y1 | `_reviewed_diff_stale_cause`: `if (recorded or digest) and not (` → `if digest and not (` (the digest optional again) | `test_a_recorded_head_without_its_bound_digest_never_certifies[absent\|none\|empty]` → `assert None == 'the reviewed diff is not the diff derived at its recorded head'` (3 red; `short`, `not-hex` and `mismatched` stay caught by the byte check). The probe state (a recorded SHA `aaaa…`, digest `None`, tampered bytes) run through `_terminal_converged` → `terminal= converged`, `certifiedHead= aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa`; restored → `terminal= cannot-certify`, `reason= reviewed-diff-stale: …` |
| Y2 | `_fold_fixer`, seam branch: add `_record_round(state, "reviewedDiffSource", REVIEWED_DIFF_SOURCE_GIT)` | `test_a_seam_backed_fixer_fold_claims_no_git_provenance` → `assert 'reviewedDiffSource' not in {… 'headDiffSource': 'unknown', …}` |
| Y3a | `build_receipt`: drop the `reviewed_diff_source_carried` guard | `test_reviewed_diff_source_rides_only_v6_receipts[2\|3\|4\|5]` → `assert 'reviewedDiffSource' not in {'auditProvenance': None, …}` (4 red; `[6]` green) |
| Y3b | `round_certification._build_receipt_rounds`: drop the same guard | the same four → the same assertion (4 red; `[6]` green) |
| Y4 | fresh `next`: `check_diff_binding(…, run=_hardened_numstat_run(derived[0]))` → `run=None` (the inherited-env numstat) | `test_the_first_round_binding_reads_the_hardened_git_config` → `{'detail': 'artifact +0/-0 vs pin +1/-1', 'ok': False, 'reason': 'round-diff-base-mismatch'}` / `assert (1 == 0)` |

## Head `b5e9bbcc`: the writer binds a converged state to its certificate's head only (advisor S10 ruling)

The probes ran in a detached probe worktree (X1–X3 at `6a591d6e`, X4 at `b5e9bbcc`, which adds
only the X4 detector) that no review session was reading. Each neutralization was a targeted
edit, reverted by the inverse edit; the detectors were left unedited. After the last restore,
`git status --porcelain` printed nothing, and `test_layer4d_stale_diff_1419.py` plus
`test_round_driver_wo_g_1271.py` gave `86 passed`. The ruled set: X1 (re-add the writer's
fix-fold/meta/config fallback, and a headless converged state certifies), X2 (the CRLF read) and
X3 (`test_fix_fold_head_resolution_failure_refuses`, double off). X4 covers the double's fold seam.

| # | Neutralization | Red (test → raw) |
|---|---|---|
| X1 | `round_certification._certified_head_sha`, converged branch: `return head if isinstance(head, str) and head else None` → `if isinstance(head, str) and head: return head` (falls through to the fix-fold/meta/config chain) | all four `test_the_writer_binds_a_converged_state_to_the_certificate_head_only[meta-fix-fold\|config-fix-fold\|meta-head\|config-head]` → `AssertionError: {'baseGuard': 'checked-stat-bound', 'certification': {… 'certifiedHead': None …}, 'certificationShape': 'full-panel-confirmed', …} is None` (a receipt certified a certificate naming no head) |
| X2 | `review_base_guard.check_round_diff`: `open(path, encoding="utf-8", newline="")` → `open(path, encoding="utf-8")` | `test_a_crlf_round_diff_binds_at_setup` → `{'detail': 'the round diff is not the review diff at HEAD 4e8d3083… — HEAD moved since … regenerate it', 'ok': False, 'reason': 'round-diff-head-mismatch'}` / `assert (1 == 0)` |
| X3 | `_fold_fixer`: after `_resolve_fix_fold_head_sha`, `if head_err: head, head_err = config["headSha"], None` (fall back to the declared head) | `test_fix_fold_head_resolution_failure_refuses` (double off) → `KeyError: 'fixFoldHeadRefused'` |
| X4 | `head_diff_double._live_fold_head`: return a declared `config["headSha"]` first | `test_fix_fold_records_post_fix_head_sha[on]` → `assert 'b5034a81…' == '226703ea…'` (the declared setup head recorded as the fold head); `[off]` stays green (the double is not installed there) |

**Scope of X1 (disclosed design call).** The writer's exclusivity is scoped to a **converged**
state, the one verdict that certifies a reviewed head, matching the driver's
`_session_certified_head`. The other certified verdicts (halted, held, stalled, cannot-certify,
capped) certify no reviewed head and keep their head sources. The in-process `run_loop` never
reaches the writer (`_materialize_run_loop_session` refuses without a source session), so its
exemption stays in the driver's `_terminal_converged` alone; a second `certifiedHead` writer in
`_materialize_run_loop_session` was tried and removed, because the invariant census rightly
flagged it.

## Head `902f6489`: the certified head is recorded by the call that derives the diff (advisor S9 ruling)

The probes ran in a detached probe worktree at `902f6489` that no review session was reading.
Each neutralization was a targeted edit to `plugins/superheroes/lib/round_driver.py`, reverted
by the inverse edit; the detectors were left unedited. After the last restore,
`git status --porcelain` printed nothing, and `test_layer4d_stale_diff_1419.py` gave
`74 passed`. The ruled set: W1 (a behind-checkout PR-mode session refuses), W2 (a no-recorded-head
no-fix session refuses), W3 (re-adding a live-HEAD fallback turns the invariant census red). W1b,
W3b, W3c, W4 and W5 cover the rest of the change's guards.

| # | Neutralization | Red (test → raw) |
|---|---|---|
| W1 | `_bind_round_diff_head`: `if meta_head is not None and meta_head != head:` → `if False and …` | `test_a_behind_checkout_refuses_at_setup[pr]` and `[branch]` → `AssertionError: {'action': 'dispatch-panel', 'attempt': 0, …, 'ok': True, …}` / `assert (0 == 1)` (the session seeded with its round-1 diff at a commit the recorded PR head is not) |
| W1b | `_bind_round_diff_head`: `if text != round_diff:` → `if False and …` | `test_a_round_diff_taken_before_head_moved_refuses_at_setup` → `AssertionError: {'action': 'terminal', …, 'ok': True, …}` / `assert (0 == 1)`. **Axis note:** the setup refusal is gone, so the session seeds; the digest check then parks it at panel emission (the terminal), a second layer. Red either way: the fresh `next` no longer refuses `round-diff-head-mismatch`. |
| W2 | `_terminal_converged`: `if certified_head is None and not _IN_PROCESS_LEG.get():` → `if False and …` | all four `test_a_no_fix_session_without_a_recorded_head_withholds[absent\|symbolic\|short\|not-hex]` and all four `test_a_pre_v6_no_fix_session_withholds[2..5]` → `assert 'converged' == 'cannot-certify'`; `test_only_the_in_process_leg_certifies_without_a_recorded_head` → `AssertionError: {… 'shape': 'full-panel-confirmed-degraded', …}` (9 red) |
| W3 | `_terminal_converged`: `certified_head = _recorded_review_head(state)` → `… or _hardened_head(os.getcwd())` (a live-HEAD fallback) | `test_no_certified_head_is_read_from_live_head` → `Extra items in the left set: '_terminal_converged'` (a new caller of the hardened lookup) |
| W3b | the same line → `… or (state.get("config") or {}).get("headSha")` (a config fallback) | `test_no_certified_head_is_read_from_live_head` → `At index 0 diff: "_recorded_review_head(state) or (state.get('config') or {}).get('headSha')" != '_recorded_review_head(state)'` |
| W3c | `_prepare_sidecar`, converged branch: `head_sha = (…).get("certifiedHead")` → `… or run_git(repo_root, "rev-parse", "HEAD")` | `test_no_certified_head_is_read_from_live_head` → `assert {… '_prepare_sidecar': 2, …} == {… '_prepare_sidecar': 1, …}`; `test_a_headless_certificate_is_never_published_with_the_live_head` → `assert 'sidecar-receipt-unreadable' == 'reviewed-head-unrecorded'` (the live head was taken and publication went on) |
| W4 | `_reviewed_diff_stale_cause`: the digest check → `if False and digest and …` | `test_reviewed_bytes_that_are_not_the_derived_ones_never_certify` → `assert None == 'the reviewed diff is not the diff derived at its recorded head'` |
| W5 | `_reviewed_diff_stale_cause`: `if state.get("headDiffRefusal") == REVIEW_DIFF_TOO_LARGE:` → `if False and …` | `test_an_over_cap_post_fix_diff_parks_rather_than_review_a_partial_diff` → `assert 'review-diff-too-large' in 'reviewed-diff-stale: the head moved and no diff at the post-fix head is derivable from git — …'` |

**The census's rung.** `test_no_certified_head_is_read_from_live_head` is a static AST census over
`round_driver.py` and `round_certification.py`: it sees a new live-HEAD read, an extra read in a
listed function, a new caller of the hardened lookup or the derivation call, and a second or
re-sourced `certifiedHead` writer. It does not see a read reached through dynamic dispatch or a
helper in another module; W1, W2 and W3c's behavioural reds carry those paths.

**The V2 row below is superseded.** The meta-head seed it proved was removed by this change: the
no-fix head now comes from the derivation call at the fresh `next`, proved by W1 and W2 and by
`test_a_no_fix_session_certifies_the_head_its_round_one_diff_was_taken_at` (still green).

## Head `8b021ac3`: prefix pins, the review-diff size cap, the no-fix certified head (advisor S8 ruling)

The probes ran in a detached probe worktree at `8b021ac3` that no review session was reading.
Each neutralization was a targeted edit, reverted by the inverse edit. The detectors were left
unedited. After the last restore, `git status --porcelain` printed nothing, and
`test_layer4d_stale_diff_1419.py` gave `57 passed`.

| # | Neutralization | Red (test → raw) |
|---|---|---|
| V3 | `round_driver._GIT_DIFF_FORMAT_FLAGS`: drop `"--src-prefix=a/", "--dst-prefix=b/"` | `test_configured_diff_prefixes_do_not_reshape_the_review_diff` → `AssertionError: diff --git SRC-f.py DST-f.py` … `+++ DST-f.py` (the repo's `diff.srcPrefix`/`diff.dstPrefix` reshaped the review diff) |
| V6 | `sanitized_view.bounded_git_diff_output`: `return _git_diff_batch_output(argv, time.monotonic(), 0)[0]` → `return subprocess.run(argv, env=git_env(), capture_output=True).stdout` (unbounded) | `test_an_over_cap_review_diff_is_refused_never_truncated` → `assert 'diff --git a/f.py b/f.py\n…' is None` (an over-cap diff returned); `test_an_over_cap_post_fix_diff_parks_rather_than_review_a_partial_diff` → `assert 'converged' == 'cannot-certify'` |
| V2 | fresh CLI `next`: `if isinstance(meta_head, str) and …` → `if False and …` (no meta-head seed) | `test_a_no_fix_session_certifies_the_head_its_round_one_diff_was_taken_at` → `KeyError: 'certifiedHead'` (a clean first round converged with no certified head, so the sidecar would fall back to the live HEAD) |

## Head `df39da64`: a readable `headDiffPath` carries no authority; the unknown surface is keyed on the derivation (advisor S7 ruling)

The probes ran in the build worktree at `df39da64` (no review session was reading it). Each
neutralization was a targeted edit, reverted by the inverse edit. After the last restore,
`git status --porcelain` printed nothing. `test_unknown_head_diff_is_derived_from_git_for_the_full_panel`
(cited in the older sections below) is now `test_an_unsupplied_head_diff_is_derived_from_git_and_reviewed`:
with the unknown surface keyed on the derivation alone, a derivable head diff runs the delta round,
not a second full panel.

| # | Neutralization | Red (test → raw) |
|---|---|---|
| N1 | `_fold_fixer` trusts the path's bytes (`if head_source == "path": head = _supplied`) | `test_a_readable_head_diff_path_carries_no_authority[path-disagrees-with-git]` → `AssertionError: the reviewed diff equals the path's bytes`. `[path-agrees-with-git]` stays green, as it must: agreeing bytes are git's bytes. |
| N2 | `_headDiffUnknown` keyed on the supplied source again (`head_source == "unknown" or head is None`) | `test_an_unsupplied_head_diff_is_derived_from_git_and_reviewed` → `AssertionError: {'panels': [1, 2]}` / `assert [1, 2] == [1]` |
| N3 | The moved-head cause reuses the unknown-head message | `test_the_stale_park_names_its_cause` → `AssertionError: two causes share one message: [...]` |

## Head `76e8b527`: certify what was seen; currency at handback; hardened HEAD (advisor S6 ruling)

The probe worktree was detached at `76e8b527`. Each neutralization was a targeted edit, reverted by
the inverse edit. After the last restore, `git status --porcelain` printed nothing. Green:
`test_layer4d_stale_diff_1419.py`, `47 passed`.

| # | Neutralization | Red (test → raw) |
|---|---|---|
| M1 | `_prepare_sidecar` publishes the live head again (`if False and isinstance(certified_head, str) ...`) | `test_a_commit_after_certification_is_refused_at_handback` → `assert '9dc0d5a1…' == 'e92550c4…'`: the sidecar named the late head, so the gate would allow. The gate's own refusal on HEAD ≠ sidecar `headSha` is `test_handback_gate.py::test_head_mismatch_refuses`, unchanged. Green, the same test asserts the literal `handback-head-mismatch` from `validate_handback`. |
| M2 | `certifiedHead` not recorded (`pass`) | `test_the_certificate_names_the_verified_sha` → `KeyError: 'certifiedHead'`; `test_a_commit_after_certification_is_refused_at_handback` → `KeyError: 'certifiedHead'` |
| M3 | `_hardened_head` runs `git rev-parse HEAD` with the inherited env (`env=None`) | `test_head_resolution_ignores_a_git_dir_decoy` → `assert '774f4268…' == 'e736fa16…'`: the `GIT_DIR` decoy's HEAD was returned |

## Head `62e2662f`: the `review-diff` verb, SHA binding, and a wider env strip (advisor S5 ruling)

The probe worktree was detached at `62e2662f`. Each neutralization was a targeted edit, reverted by
the inverse edit. After the last restore, `git status --porcelain` printed nothing. Green:
`test_layer4d_stale_diff_1419.py`, `44 passed`.

| # | Neutralization | Red (test → raw) |
|---|---|---|
| L1 | `_reviewed_diff_is_stale`: SHA comparison off (`return False and bool(...)`; fold-counter binding only) | `test_a_commit_after_the_fold_is_never_certified_unseen` → `assert 'converged' == 'cannot-certify'`: a commit landed after the fold certified unseen |
| L2 | `sanitized_view`: `GIT_GRAFT_FILE` removed from the strip list, and the `GIT_CONFIG_KEY_`/`VALUE_` prefix loop off | `test_the_git_env_strips_every_ancestry_and_config_shaping_variable[GIT_GRAFT_FILE]`, `[GIT_CONFIG_KEY_0]`, `[GIT_CONFIG_VALUE_0]` failed (3). The other 11 variables share the tuple mechanism already proven by the `GIT_GRAFT_FILE` case. |
| L3 | the `review-diff` verb bypasses `review_diff_text` (a plain `git diff`) | `test_the_review_diff_verb_output_is_the_one_review_diff` → `AssertionError: diff --git .gitattributes .gitattributes` (the user's `diff.noprefix` reshaped the output) |

## Head `237f8841`: one hardened review-diff home; the eval replay seam (advisor S4 ruling)

The probe worktree was detached at `237f8841`. Each neutralization was a targeted edit, reverted by
the inverse edit. After the last restore, `git status --porcelain` printed nothing. Green: the
stale-diff module plus the standalone eval test, `29 passed`.

| # | Neutralization | Red (test → raw) |
|---|---|---|
| K1 | SKILL.md Setup command drops `--no-textconv` | `test_skill_and_driver_run_one_review_diff_command` → `assert ['git', '-c', 'core.commitGraph=false', ...] == [...]` (the two homes diverge) |
| K2 | derivation argv without the config pins (`["git", "diff", *flags]`) | `test_a_user_diff_noprefix_setting_does_not_reshape_the_derived_diff` → `AssertionError: diff --git f.py f.py` |
| K3 | eval runner seams without `"head_diff"` | `test_a_standalone_eval_run_advances_past_a_fix` (double OFF) → `assert 'halted' == 'clean'` |

## Final head `b475849d`: the invariant lives at certification (advisor ruling A3/B1/C1/D)

Probe worktree detached at `b475849d`. Each neutralization was a targeted edit, reverted by the
inverse edit, with the detectors unedited. After the last restore, `git status --porcelain` printed
nothing. Green: `test_layer4d_stale_diff_1419.py` — `26 passed`, run with the git double OFF.

| # | Neutralization | Result |
|---|---|---|
| H1 | `_terminal_converged`: `if _reviewed_diff_is_stale(state):` → `if False and ...` | **red** — `test_a_legacy_resume_past_the_panel_never_certifies` → `assert 'converged' == 'cannot-certify'`. An older driver's post-fix state, resumed at the fix audits, certified `audited-chain-degraded` without a panel. |
| H2 | emission (`if False and phase == P_PANEL ...`), consumption (`if True or not ...`) and the panel-fold park (`if False and not state.get("terminal") ...`) all off; the certify check **kept** | **green, as the ruling requires** — `test_no_path_certifies_a_head_the_panel_did_not_see` and `test_a_legacy_resume_past_the_panel_never_certifies`: `2 passed`. The certification chokepoint alone carries the invariant. Contrast: the early-exit test `test_persisted_pre_count_state_at_the_panel_parks_stale_via_next` went red under the same edits (`{'action': 'dispatch-panel', 'attempt': 0, ...}`), so the neutralization was live. |
| H3a | panel-fold park off | **red** — `test_a_stale_panel_submit_keeps_its_output_then_parks` → `assert (True and 'dispatch-verifiers' == 'terminal'` (the stale panel folded and the loop moved on) |
| H3b | the old pre-fold submit park re-inserted (`_stale_pending_panel_park(...)` before the artifact is hashed) | **red** — same test → `AssertionError: the stale panel's submit was not recorded` / `assert []` (the output was discarded) |
| H4 | `round_certification._build_receipt_rounds`: dropped `"reviewedDiffSource"` | **red** — `test_unknown_head_diff_is_derived_from_git_for_the_full_panel` → `assert False` on the certification writer's round projection |

**A3.** The byte cross-check (`head-diff-mismatch`) was removed rather than neutralized; the G2
row below is historical. The supplied-diff test now proves the supplied text is ignored:
`test_a_supplied_head_diff_is_ignored_and_git_is_reviewed`. Its G1 neutralization, trusting the
supplied diff, is the same axis as recorded below.

## Previous head `b2e75ca4` + fixture fix: git is the authority (advisor ruling, option a)


Probe worktree detached at `b2e75ca4`. Each neutralization is a targeted edit to `round_driver.py`,
reverted by the inverse edit. Detectors are unedited except for one fixture fix, mirrored into the
build tree before the reds below were taken: the probe's first G1/G2 reds arrived as a fixture crash
(an empty second commit) and then as a stall-gate stop, not on the park assertion. Each fix round
now commits distinct content, and the fixture answers the stall gate with `hold`, so the red lands
on the verdict assertion (rubric: fix the fixture, never relax the assertion). After the last
restore, `git status --porcelain` listed only that fixture file, byte-identical to the build tree's
(`cmp`). Green: `test_layer4d_stale_diff_1419.py` — `24 passed`, run with the git double OFF
(module `pytestmark = real_git_head_diff`; `test_the_git_double_is_off_in_this_module`).

| # | Neutralization | Red (test → raw) |
|---|---|---|
| G1 | trust the supplied diff: `head = supplied if supplied is not None else (...derive...)` | `test_a_supplied_head_diff_that_differs_from_git_parks[""]` and `[diff --git ...]` → `assert 'held' == 'cannot-certify'` (a wrong diff, and a wrong `""`, ran on; no park). `test_a_supplied_slice_diff_never_replaces_the_derived_one` → `assert 'diff --git a/y b/y\n' is None` |
| G2 | the mismatch park off: `if False and supplied is not None and supplied != head:` | `test_a_supplied_head_diff_that_differs_from_git_parks` (both cases) → `assert 'held' == 'cannot-certify'` (no `head-diff-mismatch` park) |
| G3 | `advance` stale-park: `if False and side.get("reason"):` | `test_the_stale_park_via_advance_refuses_a_failed_sidecar_publish` → `{'folded': None, ..., 'ok': True, 'sidecar': None}` / `assert (True is False)` |
| G4a | consumption off (`if True or not _reviewed_diff_is_stale(state):`) | next → `{'action': 'dispatch-panel', 'attempt': 0, ...}`; advance → `no result or missing envelope ... (incomplete-roster)`; submit → `{'foldLanded': True, 'nextStep': 'dispatch-verifiers', ...}` |
| G4b | `run_loop` guard off | `test_run_loop_never_runs_a_panel_over_a_stale_reviewed_diff` → `{1, 2} == {1}` |
| G4c | emission off | via next → `dispatch-panel` attempt 0 (×2 tests); re-emit → `dispatch-panel` attempt 1; `test_underivable_unknown_head_diff_parks_reviewed_diff_stale` → `{'panels': [1, 2]}` |
| G4d | normalization off (`if inline is not None:`) | `test_inline_head_diff_that_is_not_text_is_unknown` → `assert ({}, 'inline') == (None, 'unknown')` |
| G4e | admission off (`return text`) | `test_derivation_admits_only_a_non_empty_utf8_git_diff` → `assert '' is None`; `test_a_known_empty_post_fix_diff_parks_rather_than_certify_an_empty_surface` → `assert 'held' == 'cannot-certify'` |

**Literal pinning.** Since this head, the tests spell the contract literals (`"reviewed-diff-stale"`,
`"head-diff-mismatch"`, `"git-derived"`, the three flags) rather than reading them back from the
driver (`test_the_contract_literals_are_pinned`). This closes the correction recorded below.

## Earlier record (`67449baa`) — superseded by the section above where they overlap

**Final head `67449baa`.** This record supersedes the one written at `78577727`. That record's
guard (`_enter_panel` and the `_reviewedDiffStale` marker) was retired by the advisor's
chokepoint rework (tripwire lift, 2026-09-25) and replaced by one staleness rule,
`_reviewed_diff_is_stale`. The rule reads the reviewed diff's bound head (`reviewedDiffHead`)
against the fix-fold head, and it is consulted at three sites:

- panel-order **emission**, reached by `next`, `advance` and `re-emit`;
- the **consumption** of an already-pending panel order, on `next`, `advance` and `submit`;
- **`run_loop`**, before a panel.

Guarded-element set, as declared by the advisor's rulings (STATE 21:xxZ and 22:0xZ):

- F1 — the consumption check, with three cases.
- F2 — `run_loop`.
- F3 — the emission check, on every entry path.
- F4 — the non-string head-diff normalization.
- F5 — the earlier-round shapes: an empty inline diff, and `git-derived` provenance surviving a
  later slice. The pre-marker persisted session is covered by F1 and F3.

Every neutralization was a targeted edit to `plugins/superheroes/lib/round_driver.py` in a detached
probe worktree at `67449baa`, reverted by the inverse edit. Detectors were left unedited.
**Restore receipt:** after the last restore, `git status --porcelain` in the probe tree printed
nothing. **Green:** `test_layer4d_stale_diff_1419.py`, `18 passed`. The exact refusal token every
parked path must carry is `reviewed-diff-stale`, asserted by `_assert_parked` / the certification
reason.

| # | Neutralization | Red (test → raw) |
|---|---|---|
| F1 | `_stale_pending_panel_park`: `if not _reviewed_diff_is_stale(state):` → `if True or ...` | `test_an_already_pending_stale_panel_is_not_replayed_via_next` → `assert (True and 'dispatch-panel' == 'terminal'` (the older driver's pending panel replayed); `..._not_folded_via_advance` → `{'detail': 'no result or missing envelope at attempt 0 for seat(s): architecture-reviewer, ...', 'seats': [...]}` / `assert (False)` (`incomplete-roster`, never parked); `..._not_folded_via_submit` → `{'foldLanded': True, 'nextStep': 'dispatch-verifiers', ...}` (the stale panel folded) |
| F2 | `run_loop`: `if action == P_PANEL and _reviewed_diff_is_stale(state):` → `if False and ...` | `test_run_loop_never_runs_a_panel_over_a_stale_reviewed_diff` → `{1, 2} == {1}` — `Extra items in the left set: 2` (the reviewer seam ran a round-2 panel) |
| F3 | `_refuse_stale_panel_emission`: `if phase == P_PANEL and ...` → `if False and ...` | `test_persisted_pre_count_state_at_the_panel_parks_stale_via_next` → `'dispatch-panel' == 'terminal'` (attempt 0); `test_stale_panel_cannot_be_emitted_via_durable_advance` → `'dispatch-panel' == 'terminal'`; `test_stale_panel_cannot_be_re_emitted` → `{'action': 'dispatch-panel', 'attempt': 1, ...}`; `test_underivable_unknown_head_diff_parks_reviewed_diff_stale`, `test_persisted_pre_count_state_at_verify_parks_stale`, `test_non_text_inline_head_diff_via_hand_submit_parks_stale` → each `{'panels': [1, 2]}` / `assert [1, 2] == [1]` |
| F4 | `_resolve_head_diff`: `if isinstance(inline, str):` → `if inline is not None:` | `test_inline_head_diff_that_is_not_text_is_unknown` → `assert ({}, 'inline') == (None, 'unknown')`; `test_non_text_inline_head_diff_via_hand_submit_parks_stale` → `{'detail': 'order-render-refused:head-diff-unavailable', 'ok': False, ...}` |
| F5a | `_advance_reviewed_diff`: `if isinstance(head, str):` → `if isinstance(head, str) and head:` (the round-1 truthiness bug) | `test_known_empty_head_diff_rearm_panel_reviews_the_empty_diff` → `{'panels': [1]}` / `assert (1 >= 2)`. **Axis note:** under the chokepoint, the old bug can no longer put a stale panel on the pre-fix diff. The reviewed diff stays unbound, so emission **parks** instead, and the test goes red because the correct re-armed panel over the empty diff never runs. Either way the proof bites: the writer must advance on `""`. |
| F5b | `_fold_fixer`: `_clear_round(state, "reviewedDiffSource")` → `pass` | `test_a_later_inline_slice_clears_git_derived_provenance` and `test_a_later_underivable_slice_clears_git_derived_provenance` → `assert 'reviewedDiffSource' not in {... 'headDiffSource': 'inline' ...}` / `'unknown'` |
| F6 | `_fold_fixer`: `if head is None:` (the git derivation) → `if False and head is None:` | `test_unknown_head_diff_is_derived_from_git_for_the_full_panel` → `{'panels': [1]}` / `assert [1] == [1, 2]` (no derivable diff, so the chokepoint parked instead of running the panel over `git diff base...head`) |
| F7 | `_derive_head_diff_from_git`: `return text if text.startswith("diff --git ") else None` → `return text` | `test_derivation_admits_only_a_non_empty_utf8_git_diff` → `assert '' is None` (an empty base...head diff was admitted) |

The strict-UTF-8 admission leg was proven red at `78577727` (`errors="replace"` let the latin-1
diff through as text), and that code is unchanged since. That record is in this file's history at
`deee3bcc`.
