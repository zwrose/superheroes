# #1562 WO-2 bite-proof — `sandboxAccess` journaled at claude-write run open and mapped into the sandbox settings

Bite-proof record for the `access` journal field and its settings mapping (`plugins/superheroes/lib/engine_adapter.py`, `plugins/superheroes/lib/engine_dispatch.py`), detectors in `plugins/superheroes/lib/tests/test_sandbox_access_dispatch_1562.py` (`T`).

**Status: no proof was produced. Every element below is `Unrunnable here`.** No neutralization was applied and no red or green was observed, so this record carries no raw captures and no restore receipts. Nothing in it is a claim that a run happened.

## Unrunnable here

- **What refused the run.** The harness returned `This command requires approval` for every Python invocation the implementer issued and none executed:
  1. `scripts/pinned-python -B -X pycache_prefix=/tmp/claude-501/superheroes-pyc-1562c -c "<multi-line script printing today's settings JSON>"`
  2. the same as a single-line `-c`
  3. the order's primary command, `scripts/pinned-python -B -X pycache_prefix=/tmp/claude-501/superheroes-pyc-1562c -m pytest plugins/superheroes/lib/tests/test_sandbox_access_dispatch_1562.py -q`
  The regression command was not issued, because the primary was the premise for it and a refused pytest is the same refusal. The ten red and ten green single-node runs were not issued either.
- **The exact command and environment that can run it.** From the worktree root, with approval for pytest granted:
  `scripts/pinned-python -B -X pycache_prefix=/tmp/claude-501/superheroes-pyc-1562c -m pytest <node id> -q`
  One node id per element, red then green, as the table names. `T` is `plugins/superheroes/lib/tests/test_sandbox_access_dispatch_1562.py`.
- **Substitute evidence actually produced.** Static only: a read of the import chain (no cycle, see below) and a whitespace grep. Neither discriminates any case below; neither is a bite-proof.
- **Who owns the outstanding receipt.** The orchestrator, at verification (it re-runs proofs itself). Until then the disclosure is unadjudicated.

## Declared guarded-element set and the planned neutralization per element

Neutralize by a targeted Edit in `engine_adapter.py` or `engine_dispatch.py`; restore by the inverse Edit only. None of these was applied.

| Element | Axis | Planned neutralization | Node to run alone (red, then green) |
|---|---|---|---|
| G9 malformed refuses | refusal | in `_resolve_claude_write_sandbox`, the `reason == core_md.SANDBOX_ACCESS_REASON_MALFORMED` branch assigns `calibrated = core_md.sandbox_access_all_off()` instead of returning the malformed refusal, so the open proceeds all-off | `T::test_malformed_calibration_refuses_before_open` |
| G10 unreadable refuses | refusal | the final `return None, engine_adapter.REFUSAL_SANDBOX_ACCESS_UNREADABLE` under `if calibrated is None:` becomes `calibrated = core_md.sandbox_access_all_off()` | `T::test_unreadable_calibration_refuses_before_open` |
| G11 continuation reuse | journal reuse | at the continuation read, replace `claude_write_sandbox = opened.get("claudeWriteSandbox")` with `claude_write_sandbox, _ = _resolve_claude_write_sandbox(cwd_real, timeout=preflight_timeout)` | `T::test_continuation_uses_journaled_access_not_core_md` |
| G12 domains | mapping | in `claude_write_sandbox_settings`, `domains = access.get("allowedDomains") or []` becomes `domains = []` | `T::test_domains_drives_through_open` |
| G13 local ports | mapping | delete the `if access.get("localPorts"): network["allowLocalBinding"] = True` branch | `T::test_local_ports_drives_through_open` |
| G14 unix sockets | mapping | delete the `if socket_dirs: network["allowUnixSockets"] = list(socket_dirs)` branch | `T::test_local_sockets_drives_through_open` |
| G15 extra write paths | mapping | delete `allow_write.extend(extra_paths)` | `T::test_extra_write_paths_drives_through_open` |
| G16 byte identity | preservation | build `network` with `"allowLocalBinding": bool(access.get("localPorts"))` always present | `T::test_all_off_settings_are_byte_identical` |
| G17 journal validity | refusal | `claude_write_sandbox_valid` ends `return True` instead of `return _sandbox_access_valid(sandbox.get("access"))` | `T::test_access_validity_rejects_malformed_and_refuses_roots_missing` (every parametrized id) |
| G18 deny wins | preservation | `"denyWrite": [d for d in sandbox["denyWrite"] if d not in extra_paths]` | `T::test_deny_write_is_never_filtered_by_extra_write_paths` |

Token and setting-name literals are spelled out as strings in the tests, not reached through the module constants. `test_refusal_tokens_registered` (T11) pins the two tokens and has no neutralization of its own.

## Notes the reader of the proof needs

- **The T1 literal was derived by hand, not pasted from a run.** The order says to compute it from the base function and paste it. The Python invocation that would have printed it was refused, so `_TODAYS_SETTINGS` was derived from the base source of `claude_write_sandbox_settings` (`json.dumps(obj, sort_keys=True, separators=(",", ":"))` over `env`, `permissions`, `sandbox`, with the sandbox keys in sorted order). It is unmeasured against the base function. The first thing a re-run should confirm is that `test_all_off_settings_are_byte_identical` is green against this branch and that the literal equals the base function's output for `_BYTE_SANDBOX`.
- **G16 is a mutual check only if the literal is right.** If the hand-derived literal were wrong, G16 would be red before any neutralization, which the green half of the proof would show.
- **T8 asserts `allowedDomains == []`, not key absence.** An all-off run keeps `network.allowedDomains: []` (today's bytes), so "no `allowedDomains` entry" is checked as no `example.org` and an empty list.
- **Extra detectors beyond the declared set** have no proof of their own: `test_all_off_run_stays_offline` (T2 companion), `test_absent_core_md_opens_as_all_off` (E4), `test_read_raising_is_treated_as_unreadable` (E1), `test_no_getuid_with_local_sockets_is_unreadable` (E7), `test_local_socket_dir_defaults_to_tmp`.
- **Harness seam.** `_open_claude_write` creates its own linked worktree, so the tests write core.md by monkeypatching `test_claude_write_sandbox_1554._linked_worktree` with a wrapper that calls the original and then writes core.md. `_open_claude_write` itself is unchanged and reused.
