# Layer 2c (#1270) bite-proof — native-channel retirements and verifier reason contract

**Provenance:** produced by **WO-2c-A** (code, committed at `9cc1733e`) and **WO-2c-A2** (test migration +
this record), cursor / composer-2.5. **WO-2c-A3** (specimen stdout + BP-2c-1/2 proofs), cursor /
composer-2.5, head `6e2d665d` + uncommitted test edits. Code head for proofs: `6e2d665d`; working
tree dirty with test-only edits at record time (`git rev-parse HEAD` unchanged).

**Method.** Each guarded element is neutralized on its own — the thing the detector guards, never the
detector — by a targeted edit, reverted by the exact inverse edit. Tests are selected by **exact
node id**. Only one neutralization was live at a time. Green runs were made together on the clean
tree after every restore.

Common command prefix:

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-2c -m pytest <node ids> -q -p no:cacheprovider --tb=short
```

## Guarded elements

| ID | Guarded element | Neutralized thing | Proving test(s) |
|---|---|---|---|
| BP-2c-1 | gate 3: review terminal upgrade never runs on native | channel condition at `_supervise` call site | `test_native_review_terminal_forfeit_carries_no_salvage`, `test_native_vacuous_terminal_is_never_upgraded` |
| BP-2c-2 | gate 1: no salvage / classifier on a native write terminal | early return in `_finalize_write_forfeit_terminal` | `test_native_write_exhausted_forfeit_carries_no_salvage` |
| BP-2c-3 | gate 2: no stdout-cap forfeit on a native write | `!= CHANNEL_NATIVE` clause in `_supervise` | `test_native_write_over_cap_stdout_never_forfeits_stdout_capped` |
| BP-2c-4 | write runs record `echoNonce` | `echo_nonce = secrets.token_hex(16)` and `record["echoNonce"] = …` in `_open_write_run` | `test_write_run_execution_record_carries_runner_nonce` |
| BP-2c-5 | `reason` required non-empty in P_VERIFIERS | move `reason` back to `optional` | `test_verdict_reason_required_in_contract_and_schema` |
| BP-2c-6 | F1: marker-channel codex run never spawns | `marker-channel-retired` refusal branch in `_spawn_native_result_argv` | `test_codex_marker_channel_run_refuses_to_spawn` |
| BP-2c-7 | F2: blank strings fault as non-empty-string | `.strip()` checks in `_check_scalar_type`, required-member, and element checks | `test_payload_contracts_non_empty_string_rejects_blank` |
| BP-2c-8 | F3: hand submit validates through contract | `payload_fault` call in `verifier_results_fault` | `test_hand_submit_verifier_reasonless_verdict_refused` |

---

## BP-2c-1 — review terminal upgrade gated off native

- **axis:** a native review terminal is never upgraded to `forfeit-with-engaged-artifact`.
- **neutralization:** delete the `if _opened_channel(opened) != engine_result_channel.CHANNEL_NATIVE:` guard so `_maybe_upgrade_review_terminal_forfeit` always runs.
- **raw red** (exit 1):
```
FAILED …/test_engine_dispatch.py::test_native_review_terminal_forfeit_carries_no_salvage
E   AssertionError: assert 'forfeit-with-engaged-artifact' == 'forfeited'
FAILED …/test_engine_dispatch.py::test_native_vacuous_terminal_is_never_upgraded
E   AssertionError: assert 'forfeit-with-engaged-artifact' == 'vacuous'
```
- **restore:** inverse edit (re-insert guard); `git status --porcelain -- plugins/superheroes/lib/engine_dispatch.py` empty.

---

## BP-2c-2 — write forfeit salvage gated off native

- **axis:** native write terminal forfeit never attaches marker-channel salvage.
- **neutralization:** delete the early `return terminal` when `_opened_channel(...) == CHANNEL_NATIVE` in `_finalize_write_forfeit_terminal`.
- **raw red** (exit 1):
```
FAILED …/test_engine_dispatch_write.py::test_native_write_exhausted_forfeit_carries_no_salvage
E   assert 'salvage' not in {'argv': ['codex', 'exec', …], 'attempts': 2, 'detail': 'native-result-schema-invalid', …, 'salvage': {…}, …}
```
- **restore:** inverse edit (re-insert early return); `git status --porcelain -- plugins/superheroes/lib/engine_dispatch.py` empty.

---

## BP-2c-3 — stdout-cap forfeit gated off native write

- **axis:** native write never forfeits with `stdout-capped-by-attempt`.
- **neutralization:** `if run_kind == RUN_KIND_WRITE and _opened_channel(opened) != engine_result_channel.CHANNEL_NATIVE:` → `if run_kind == RUN_KIND_WRITE:`.
- **raw red** (exit 1):
```
FAILED …/test_engine_dispatch_write.py::test_native_write_over_cap_stdout_never_forfeits_stdout_capped
E   AssertionError: assert 'stdout-capped-by-attempt' not in 'stdout-capp...empt:8389120'
```
- **restore:** inverse edit; `git diff --stat plugins/superheroes/lib/engine_dispatch.py` empty.

---

## BP-2c-4 — write run records runner nonce

- **axis:** `run_execution_record` exposes `runnerNonce` matching `echoNonce` on `run-opened`.
- **neutralization:** remove `echo_nonce = secrets.token_hex(16)` and the `record["echoNonce"] = effective_nonce` block in `_open_write_run`.
- **raw red** (exit 1):
```
FAILED …/test_engine_dispatch_write.py::test_write_run_execution_record_carries_runner_nonce
E   assert False is True
```
- **restore:** inverse edit; `git diff --stat plugins/superheroes/lib/engine_dispatch.py` empty.

---

## BP-2c-5 — verdict `reason` required in contract

- **axis:** `P_VERIFIERS` lists `reason` under `required` with type `non-empty-string`.
- **neutralization:** `required: ["id", "verdict", "reason"]` → `required: ["id", "verdict"]` plus `optional: ["reason"]` on the verdicts element.
- **raw red** (exit 1):
```
FAILED …/test_engine_result_channel.py::test_verdict_reason_required_in_contract_and_schema
E   AssertionError: assert 'reason' in ['id', 'verdict']
```
- **restore:** inverse edit; `git diff --stat plugins/superheroes/lib/payload_contracts.py` empty.

---

## BP-2c-6 — marker-channel codex spawn refused

- **axis:** codex opened without native channel refuses with `marker-channel-retired` and never spawns.
- **neutralization:** delete the inner `return False, spawn_argv, None, "marker-channel-retired"` branch.
- **raw red** (exit 1):
```
FAILED …/test_engine_dispatch.py::test_codex_marker_channel_run_refuses_to_spawn
E   assert False is True
```
- **restore:** inverse edit; `git diff --stat plugins/superheroes/lib/engine_dispatch.py` empty.

---

## BP-2c-7 — blank strings refused as non-empty-string

- **axis:** whitespace-only `id` / `reason` members fault through `payload_fault`.
- **neutralization:** remove `or value.strip() == ""` from scalar and element checks and the required-member blank test in `payload_contracts.py`.
- **raw red** (exit 1):
```
FAILED …/test_payload_contracts.py::test_payload_contracts_non_empty_string_rejects_blank
E   assert None is not None
```
- **restore:** inverse edit; `git diff --stat plugins/superheroes/lib/payload_contracts.py` empty.

---

## BP-2c-8 — hand submit contract validation

- **axis:** `verifier_results_fault` refuses reason-less verdict members via `payload_fault`.
- **neutralization:** delete the `payload_fault` call in `verifier_results_fault`.
- **raw red** (exit 1):
```
FAILED …/test_round_driver.py::test_hand_submit_verifier_reasonless_verdict_refused
E   assert None is not None
```
- **restore:** inverse edit; `git diff --stat plugins/superheroes/lib/round_driver.py` empty.

---

## Green run (all detectors, clean tree)

Command: single run of every proving test listed above after all restores.

```
.........                                                                [100%]
9 passed in 2.65s
```

`git status --porcelain -- plugins/superheroes/lib/*.py` empty (code files committed and untouched).
