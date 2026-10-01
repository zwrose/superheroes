# #1562 WO-2 bite-proof — `sandboxAccess` journaled at claude-write run open and mapped into the sandbox settings

Bite-proof record for the `access` journal field and its settings mapping (`plugins/superheroes/lib/engine_adapter.py`, `plugins/superheroes/lib/engine_dispatch.py`), detectors in `plugins/superheroes/lib/tests/test_sandbox_access_dispatch_1562.py` (`T`).

**Status: the orchestrator ran every proof below.** The implementer ran none: the harness refused every Python invocation the implementer issued (`This command requires approval`; the refusals are listed under "Why the orchestrator ran them"). The red captures are the orchestrator's, named `G9-red.txt` … `G18-red.txt`, in the `bp` subdirectory of the orchestrator's scratchpad directory. The green capture is `L2-green.txt` in the same directory (`546 passed`, which includes every node below). Each entry carries the neutralization applied (the planned one, which is what the orchestrator applied), the failing assertion line quoted from the red capture, the FAILED count, and the restore.

**G11 was vacuous as first written** (`1 passed` under its neutralization) and was fixed by WO-2b; its post-fix red and green are pending the orchestrator's re-run. See G11 below.

## Why the orchestrator ran them

The implementer's Python invocations were refused by the harness, none executed:

1. WO-2: `scripts/pinned-python -B -X pycache_prefix=/tmp/claude-501/superheroes-pyc-1562c -c "<multi-line script printing today's settings JSON>"`
2. WO-2: the same as a single-line `-c`
3. WO-2: the order's primary command, `scripts/pinned-python -B -X pycache_prefix=/tmp/claude-501/superheroes-pyc-1562c -m pytest plugins/superheroes/lib/tests/test_sandbox_access_dispatch_1562.py -q`
4. WO-2b: `scripts/pinned-python -B -X pycache_prefix=/tmp/claude-501/superheroes-pyc-1562e -m pytest plugins/superheroes/lib/tests/test_sandbox_access_dispatch_1562.py::test_continuation_uses_journaled_access_not_core_md -q` (the green half of the G11 fix; `This command requires approval`)

## Declared guarded-element set, neutralization applied, and receipts

Each neutralization was a targeted Edit in `engine_adapter.py` or `engine_dispatch.py`, restored by the inverse Edit; each restore is green in `L2-green.txt` (`546 passed`). `T` is `plugins/superheroes/lib/tests/test_sandbox_access_dispatch_1562.py`.

### G9 malformed refuses (refusal)

- Neutralization: in `_resolve_claude_write_sandbox`, the `reason == core_md.SANDBOX_ACCESS_REASON_MALFORMED` branch assigns `calibrated = core_md.sandbox_access_all_off()` instead of returning the malformed refusal, so the open proceeds all-off.
- Node: `T::test_malformed_calibration_refuses_before_open`
- Red (`G9-red.txt`, line 13): `E       KeyError: 'detail'`
- FAILED count: 1 (`1 failed in 1.30s`)
- Restored by the inverse Edit; green in `L2-green.txt`.

### G10 unreadable refuses (refusal)

- Neutralization: the final `return None, engine_adapter.REFUSAL_SANDBOX_ACCESS_UNREADABLE` under `if calibrated is None:` becomes `calibrated = core_md.sandbox_access_all_off()`.
- Node: `T::test_unreadable_calibration_refuses_before_open`
- Red (`G10-red.txt`, line 12): `E       KeyError: 'detail'`
- FAILED count: 1 (`1 failed in 3.88s`)
- Restored by the inverse Edit; green in `L2-green.txt`.

### G11 continuation reuse (journal reuse) — vacuous as first written

- Neutralization: at the continuation read, replace `claude_write_sandbox = opened.get("claudeWriteSandbox")` (about line 6317 of `engine_dispatch.py`) with `claude_write_sandbox, _ = _resolve_claude_write_sandbox(cwd_real, timeout=preflight_timeout)`.
- Node: `T::test_continuation_uses_journaled_access_not_core_md`
- Result as first written (`G11-red.txt`, line 2): `1 passed in 1.48s`. **The detector did not go red under its neutralization.** FAILED count: 0. The test asserted only on the returned and journaled argv, and that argv comes from the journal whether or not the calibration was re-read.
- Contrast: the sibling `test_continuation_uses_journaled_sandbox_not_environment` in `plugins/superheroes/lib/tests/test_claude_write_sandbox_1554.py` goes red under the same neutralization, because it spies on `ED._resolve_claude_write_sandbox` and asserts the call count stays 1 (`a continuation re-resolved the sandbox`, `assert 2 == 1`).
- Fix (WO-2b, order-authorized test change): the test now spies on `core_md.read_sandbox_access`, the calibration read itself, through `monkeypatch.setattr(ED.core_md, "read_sandbox_access", ...)`; the spy appends to a `calls` list and delegates to the real function. It asserts `len(calls) == 1` after the open and `len(calls) == 1, "a continuation re-read the sandboxAccess calibration"` after the continuation `_dispatch_write`. Every earlier assertion is kept.
- G11 post-fix: pending orchestrator re-run

### G12 domains (mapping)

- Neutralization: in `claude_write_sandbox_settings`, `domains = access.get("allowedDomains") or []` becomes `domains = []`.
- Node: `T::test_domains_drives_through_open`
- Red (`G12-red.txt`, line 17): `E       AssertionError: assert [] == ['pypi.org']`
- FAILED count: 1 (`1 failed in 1.69s`)
- Restored by the inverse Edit; green in `L2-green.txt`.

### G13 local ports (mapping)

- Neutralization: delete the `if access.get("localPorts"): network["allowLocalBinding"] = True` branch.
- Node: `T::test_local_ports_drives_through_open`
- Red (`G13-red.txt`, line 15): `E       KeyError: 'allowLocalBinding'`
- FAILED count: 1 (`1 failed in 1.68s`)
- Restored by the inverse Edit; green in `L2-green.txt`.

### G14 unix sockets (mapping)

- Neutralization: delete the `if socket_dirs: network["allowUnixSockets"] = list(socket_dirs)` branch.
- Node: `T::test_local_sockets_drives_through_open`
- Red (`G14-red.txt`, line 17): `E       KeyError: 'allowUnixSockets'`
- FAILED count: 1 (`1 failed in 1.86s`)
- Restored by the inverse Edit; green in `L2-green.txt`.

### G15 extra write paths (mapping)

- Neutralization: delete `allow_write.extend(extra_paths)`.
- Node: `T::test_extra_write_paths_drives_through_open`
- Red (`G15-red.txt`, line 18, as truncated in the capture): `E       AssertionError: assert '/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-9629/test_extra_write_paths_drives_0/real-cache' in ['/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-9629...hd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-9629/test_extra_write_paths_drives_0/main/.git']`
- FAILED count: 1 (`1 failed in 1.79s`)
- Restored by the inverse Edit; green in `L2-green.txt`.

### G16 byte identity (preservation)

- Neutralization: build `network` with `"allowLocalBinding": bool(access.get("localPorts"))` always present.
- Node: `T::test_all_off_settings_are_byte_identical`
- Red (`G16-red.txt`, line 7): `E       assert '{"env":{"UV_...list":true}}}' == '{"env":{"UV_...list":true}}}'`
- FAILED count: 1 (`1 failed in 0.79s`). The capture's diff lines (10 and 11) show the only difference is the added `"allowLocalBinding":false`, which also bears out the hand-derived `_TODAYS_SETTINGS` literal for the rest of the string.
- Restored by the inverse Edit; green in `L2-green.txt`.

### G17 journal validity (refusal)

- Neutralization: `claude_write_sandbox_valid` ends `return True` instead of `return _sandbox_access_valid(sandbox.get("access"))`.
- Node: `T::test_access_validity_rejects_malformed_and_refuses_roots_missing` (every parametrized id)
- Red (`G17-red.txt`): every one of the 11 ids fails with the same `E` line; the first, at line 23, is `E       AssertionError: assert True is False`
- FAILED count: 11 (`11 failed in 0.93s`): `not-a-dict`, `unknown-key`, `missing-key`, `relative-extra-path`, `ports-int`, `ports-str`, `socket-dirs-not-list`, `socket-dir-relative`, `domains-not-list`, `domain-empty`, `domain-not-str`.
- Restored by the inverse Edit; green in `L2-green.txt`.

### G18 deny wins (preservation)

- Neutralization: `"denyWrite": [d for d in sandbox["denyWrite"] if d not in extra_paths]`.
- Node: `T::test_deny_write_is_never_filtered_by_extra_write_paths`
- Red (`G18-red.txt`, line 19, as truncated in the capture): `E       AssertionError: assert '/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-9632/test_deny_write_is_never_filte0/main/.git/hooks' in ['/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-9632...apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-9632/test_deny_write_is_never_filte0/main/.git/worktrees/wt/gitdir']`
- FAILED count: 1 (`1 failed in 1.68s`)
- Restored by the inverse Edit; green in `L2-green.txt`.

Token and setting-name literals are spelled out as strings in the tests, not reached through the module constants. `test_refusal_tokens_registered` (T11) pins the two tokens and has no neutralization of its own.

## Notes the reader of the proof needs

- **The T1 literal was derived by hand, not pasted from a run.** The order says to compute it from the base function and paste it. The Python invocation that would have printed it was refused, so `_TODAYS_SETTINGS` was derived from the base source of `claude_write_sandbox_settings` (`json.dumps(obj, sort_keys=True, separators=(",", ":"))` over `env`, `permissions`, `sandbox`, with the sandbox keys in sorted order). It was not measured against the base function by the implementer. The orchestrator's `L2-green.txt` (`546 passed`) includes `test_all_off_settings_are_byte_identical`, and the G16 red diff differs only in the injected `allowLocalBinding` key.
- **G16 is a mutual check only if the literal is right.** If the hand-derived literal were wrong, G16 would be red before any neutralization, which the green half of the proof would show.
- **T8 asserts `allowedDomains == []`, not key absence.** An all-off run keeps `network.allowedDomains: []` (today's bytes), so "no `allowedDomains` entry" is checked as no `example.org` and an empty list.
- **Extra detectors beyond the declared set** have no proof of their own: `test_all_off_run_stays_offline` (T2 companion), `test_absent_core_md_opens_as_all_off` (E4), `test_read_raising_is_treated_as_unreadable` (E1), `test_no_getuid_with_local_sockets_is_unreadable` (E7), `test_local_socket_dir_defaults_to_tmp`.
- **Harness seam.** `_open_claude_write` creates its own linked worktree, so the tests write core.md by monkeypatching `test_claude_write_sandbox_1554._linked_worktree` with a wrapper that calls the original and then writes core.md. `_open_claude_write` itself is unchanged and reused.
