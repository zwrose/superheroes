# Layer 4d part (ii) bite-proof record — the rulings channel (arm D shadow of #1419)

## Heads `a654971d` / `93dca400` / `3c3ff398`: the round-4 to round-6 fix legs (advisor rulings 13:26Z, 15:3xZ, 17:3xZ)

Re-run by the orchestrator in a detached probe worktree (Q1–Q4, R1–R2 at `93dca400`, S1 at
`3c3ff398`) that no review session was reading. Each neutralization was a targeted edit to
`plugins/superheroes/lib/round_driver.py`, reverted by the inverse edit; detectors unedited. After
each restore `git status --porcelain` printed nothing; green: `test_layer4d_rulings_1419.py` —
`27 passed` at `93dca400`, `29 passed` at `3c3ff398`.

| # | Neutralization | Red (test → raw) |
|---|---|---|
| Q1 | `_cmd_rule_locked`: `"receiptFault": str(fault) if fault else None` → `fault.detail if fault else None` | `test_a_terminal_rule_reports_a_receipt_fault_as_its_detail_text` → `AttributeError: 'ReceiptFault' object has no attribute 'detail'` |
| Q2 | `_cmd_rule_locked`: the post-commit `if state.get("terminal"):` → `if terminal:` (the entry snapshot) | `test_a_live_ruling_that_converges_the_session_runs_the_terminal_receipt_gate` → `AssertionError: terminal-receipt-gate-skipped` |
| Q3 | `_plan_rulings`: `wave_reach is _WAVE_REACH_ALL or key in wave_reach` → `wave_reach is not _WAVE_REACH_ALL and key in wave_reach` (the literal disjunct drop crashes on the bare sentinel instead) | `test_a_step_with_no_declared_wave_reach_refuses_every_closing_ruling` → `AssertionError: ('run-verify', None, None)` (the ruling planned at `run-verify`) |
| Q4 | `_finding_history`: `log = _gate_history_rows(round_entry)` → `_guidance_log_rows(round_entry)` | `test_a_later_closing_ruling_supersedes_earlier_guidance_in_fixer_history` → `assert 'fix-with-guidance' == 'refuted'` |
| R1 | `_merged_gate_rows`: dropped `rows.sort(key=_gate_seq_of)` (fixed channel order) | `test_a_later_owner_judgment_supersedes_an_earlier_same_round_closing_ruling` → `assert 'refuted' == 'fix-with-guidance'` |
| R2 | `_fold_rulings`: dropped `row[GATE_SEQ_FIELD] = _next_gate_seq(state)` | the same test → `KeyError: 'gateSeq'` |
| S1 | `_plan_rulings`: `if owner_class == …UNRECOGNIZED:` → `if False and …` | `test_a_live_ruling_on_a_ledgered_finding_refuses_an_unrecognized_ledger_owner` → `{…, 'ok': True, 'ruled': ['src/f00.py::unchecked index@L2'], …}` / `assert True is False`; the terminal twin → `assert 'ruling-target-unknown' == 'disposition-ledger-owner-unrecognized'` |

Guarded-element set (brief + dispositions, declared before code): the in-order guidance render
(B1), the widened fix-batch exclusion (B2), pending supersession (B3), the attempt allocator (B4),
required provenance (B5), unique ids (B6), no Critical out of scope (B7), no ruling over an answered
attempt (B8), no ruling at an owner gate (B9), no ruling on a certified terminal (B10), retiring the
stale refusal (B11), seeding an unledgered candidate (B12), guidance only for an unexecuted fixer
slice (B13), and the audits fold recording candidates (B14).

The DoD's own bite-proof — *route the ruling back through a prompt appendix and the binding goes
red with its token* — is `test_a_ruling_carried_as_a_prompt_appendix_breaks_the_binding`: the
emitted order plus an appended ruling is the runner's prompt, and `record-result` refuses with the
exact token `evidence-order-mismatch`. Its green twin is
`test_guidance_ruling_renders_in_the_order_and_the_fixer_evidence_binds` (the same ruling through
`rule`; `record-result` stores a `dispatch-observed` seat). B1 is the neutralization that turns the
channel back into "no ruling in the order".

Neutralizations were targeted edits to `plugins/superheroes/lib/round_driver.py` in a detached probe
worktree at `d07d07f0`, each reverted by the inverse edit; detectors unedited. B7+B8 and B9+B13 were
neutralized in pairs because each pair's tests exercise disjoint elements (each red names its own
test). Restore receipt: after the last restore `git diff --stat` in the probe tree listed only the
test-fixture fix below, no source file; green: `test_layer4d_rulings_1419.py` — `14 passed`.

| # | Neutralization (in `round_driver.py`) | Red (test → raw) |
|---|---|---|
| B1 | `_guidance_log_rows`: `if isinstance(rulings, list):` → `if False and ...` | `test_guidance_ruling_renders_in_the_order_and_the_fixer_evidence_binds` → `assert 'use a sentinel value, not a second bounds check' in 'You are the fixer ...'` |
| B2 | `_excluded_discharged_fix_row`: `not in session_contract.DISPOSITIONS` → `!= "fixed"` | `test_out_of_scope_ruling_takes_a_mechanical_finding_out_of_the_fix_batch` → `Left contains one more item: 'src/f00.py::off by one@L3'`; `test_ruling_the_whole_batch_out_never_dispatches_a_fixer` → `{'action': 'dispatch-fixer', 'attempt': 1, ...}` |
| B3 | removed `state.pop("pending", None)` in `_cmd_rule_locked` | out-of-scope test → `assert (True, 'dispatch-fixer', 0) == (True, 'dispatch-fixer', 1)` |
| B4 | `_journal_max_attempt`: dropped the superseded-row leg | `test_a_superseded_attempt_is_never_reissued` → `assert 0 == 1` |
| B5 | `if not _owner_artifact_provenance_well_formed(...)` → `if False and ...` | `test_every_refusal_is_named_and_folds_nothing` → `KeyError: '_provenance'` (the `no-provenance` case reached the fold instead of refusing) |
| B6 | `if key in seen:` → `if False and ...` | same test → `('duplicate', {... 'ok': True ...})` / `assert (True is False)` |
| B7 | Critical out-of-scope check → `if False and ...` | `test_critical_may_not_be_ruled_out_of_scope` → `{'ok': True, 'ruled': [...]}` / `assert (True is False)` |
| B8 | `if names:` → `if False and names:` | `test_owner_gate_and_answered_attempts_refuse` → `{'ok': True, ... 'superseded': {'attempt': 0, ...}}` |
| B9 | `elif phase in OWNER_GATE_PHASES:` → `elif False and ...` | same test (B8 restored) → `{'ok': True, ... 'superseded': None}` |
| B10 | `_terminal_ruling_fault` certified check → `if False and ...` | `test_terminal_takes_only_closing_rulings_and_never_a_certified_session` → `{'ok': True, 'recertified': {... 'certified': True}}` / `assert (True is False)` |
| B11 | `_complete_ruling_recertify`: `os.remove(refusal)` → `pass` | `test_terminal_ruling_dispositions_an_unledgered_new_issue_and_recertifies` → `assert not True` on `certification-refusal.json` existing |
| B12 | `if seed_round is not None:` → `if False and ...` | same test → `'recertified': {... 'certified': False ...}` / `assert False is True` |
| B13 | `if key not in guidance_keys:` → `if False and ...` | `test_guidance_needs_an_unexecuted_fixer_slice` → `{'ok': True, ... 'phase': 'dispatch-audits' ...}` |
| B14 | `_fold_audits`: `if candidates:` → `if False and candidates:` | `test_the_audits_fold_records_each_new_issue_candidate_on_the_round` → `KeyError: 'auditNewIssues'` |
| B15 | `_plan_rulings` pending-wave refusal: `if entry.get("ruling") in RULING_CLOSING_KINDS and (` → `if False and ...` (fix round 2, in the build tree, reverted by the inverse edit) | `test_a_closing_ruling_during_a_pending_scoped_finder_wave_is_refused_not_lost` → `assert out["ok"] is False and out["reason"] == "ruling-target-in-pending-wave", out` / `{'ok': True, 'ruled': ['src/f00.py::a fresh defect the audit saw@L3'], 'superseded': {'attempt': 0, 'phase': 'dispatch-scoped-finder', 'round': 2}}`; a throwaway probe driving the scoped fold under the same neutralization read the ledger row back as `{'disposition': 'refuted', 'dispositionSeq': None, 'raisedSeq': 6}` — the ruling lost its sequence to the re-stage. Green after the inverse edit: `1 passed` |

**Fixture fix found by B10 (bite-proof rubric, vacuous-proof face 2).** The first B10 run stayed
**green** under neutralization: after a successful re-certification the refusal file is already
retired, so the "no refusal on disk" leg refused first and the certified leg never decided. The
fixture now also recreates the crash window (a receipt on disk beside a stale refusal) and asserts
the refusal detail names `certified`; with that fixture B10 goes red as recorded above. The
assertion was not relaxed.
