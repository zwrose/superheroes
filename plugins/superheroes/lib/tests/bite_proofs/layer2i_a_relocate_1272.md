# Bite-proof record — #1272 layer 2i-a (the `relocate` verb)

Contract: `rubric/bite-proof.md`. Every proof below ran with the **detector unedited**; each
neutralization was a targeted, reversible edit to `plugins/superheroes/lib/round_driver.py`
applied with the Edit tool, restored by its exact inverse edit (never `git checkout`, never a
whole-file rewrite), with `git diff --quiet -- plugins/superheroes/lib/round_driver.py` exit 0
after every restore.

**Who ran these, and where.** Work order c13-2ia-r4-wo leg 2, cursor `composer-2.5`, in four
dedicated probe worktrees (`issue-1272-2ia-r4-bp1` … `bp4`) each at the layer's final head
`88c569d7`, no other session reading them.

Every command was run as
`/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest <node-id> -q -p no:randomly`
with EXIT the runner's own exit code, never a pipe's. Every detector was selected by its **exact
node id**, never `-k`.

**The guarded set.** 34 elements — G1a, G1b, G2–G10, G11, G12a, G12b, G13–G15, G15b, G16–G31 —
in `_cmd_relocate_locked`, `cmd_relocate`, `_relocate_claim_target_marker`, `_relocate_read_target_marker`,
`_relocate_recorded_head`, and `_retire_relocate_marker`. One proof per element, except G11 (unproven as placed,
disclosed in its entry) and G21 (removed: the code it guarded no longer exists).

The whole-file run at the final head and the orchestrator's independent re-run of every element
are recorded in the build record of PR #1372.

---

## G1a — `repoRoot` presence/type check

**Guarded element.** `_cmd_relocate_locked`, `if not isinstance(old_root, str) or not old_root or not os.path.isabs(old_root):` (the `not isinstance(old_root, str) or not old_root` half). **Axis:** repoRoot presence/type refusal when repoRoot is missing.

**Neutralization:** `if not isinstance(old_root, str) or not old_root or not os.path.isabs(old_root):` → `if (False and (not isinstance(old_root, str) or not old_root)) or not os.path.isabs(old_root):`

**Detector.** `plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_refusal_tokens[relocate-session-unreadable-no-repo-root]`.

**Red** (EXIT=1):

```
plugins/superheroes/lib/round_driver.py:6332: in _cmd_relocate_locked
    if (False and (not isinstance(old_root, str) or not old_root)) or not os.path.isabs(old_root):
E   TypeError: expected str, bytes or os.PathLike object, not NoneType
FAILED plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_refusal_tokens[relocate-session-unreadable-no-repo-root]
1 failed in 2.64s
```

**Restore.** Inverse edit. **Restore receipt:** `git diff --quiet -- plugins/superheroes/lib/round_driver.py; echo $?` → `0`.

**Green** (EXIT=0): `1 passed in 2.29s`.

## G1b — `repoRoot` absolute check

**Guarded element.** `_cmd_relocate_locked`, `if not isinstance(old_root, str) or not old_root or not os.path.isabs(old_root):` (the `not os.path.isabs(old_root)` half). **Axis:** repoRoot absolute-path refusal when repoRoot is relative.

**Neutralization:** `if not isinstance(old_root, str) or not old_root or not os.path.isabs(old_root):` → `if not isinstance(old_root, str) or not old_root or (False and not os.path.isabs(old_root)):`

**Detector.** `plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_refusal_tokens[relocate-session-unreadable-relative-repo-root]`.

**Red** (EXIT=1):

```
>       assert rc == 1
E       assert 0 == 1
FAILED plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_refusal_tokens[relocate-session-unreadable-relative-repo-root]
1 failed in 3.35s
```

**Restore.** Inverse edit. **Restore receipt:** `git diff --quiet -- plugins/superheroes/lib/round_driver.py; echo $?` → `0`.

**Green** (EXIT=0): `1 passed in 4.98s`.

## G2 — `sessionDir` presence/type check

**Guarded element.** `_cmd_relocate_locked`, `if (not isinstance(session_dir_meta, str) or not session_dir_meta or not session_dir_meta.strip()):`. **Axis:** sessionDir presence/type refusal when sessionDir is missing.

**Neutralization:** wrapped the full presence/type/strip condition in `False and (...)` (adapted from the prior record to include the `.strip()` term now in the guard).

**Detector.** `plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_refusal_tokens[relocate-session-unreadable-no-session-dir]`.

**Red** (EXIT=1):

```
plugins/superheroes/lib/round_driver.py:6341: in _cmd_relocate_locked
    if not os.path.isabs(session_dir_meta):
E   TypeError: expected str, bytes or os.PathLike object, not NoneType
FAILED plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_refusal_tokens[relocate-session-unreadable-no-session-dir]
1 failed in 3.31s
```

**Restore.** Inverse edit. **Restore receipt:** `git diff --quiet -- plugins/superheroes/lib/round_driver.py; echo $?` → `0`.

**Green** (EXIT=0): `1 passed in 3.59s`.

## G3 — loop-state unreadable check

**Guarded element.** `_cmd_relocate_locked`, `if not ok_state or loaded is None:`. **Axis:** loop-state unreadable refusal when loop-state.json is missing.

**Neutralization:** `if not ok_state or loaded is None:` → `if False and (not ok_state or loaded is None):`

**Detector.** `plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_refusal_tokens[relocate-session-unreadable-state-missing]`.

**Red** (EXIT=1):

```
plugins/superheroes/lib/round_driver.py:6349: in _cmd_relocate_locked
    if state.get("terminal"):
E   AttributeError: 'NoneType' object has no attribute 'get'
FAILED plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_refusal_tokens[relocate-session-unreadable-state-missing]
1 failed in 2.90s
```

**Restore.** Inverse edit. **Restore receipt:** `git diff --quiet -- plugins/superheroes/lib/round_driver.py; echo $?` → `0`.

**Green** (EXIT=0): `1 passed in 3.18s`.

## G4 — terminal-session check

**Guarded element.** `_cmd_relocate_locked`, `if state.get("terminal"):`. **Axis:** terminal-session refusal when the session is terminal.

**Neutralization:** `if state.get("terminal"):` → `if False and state.get("terminal"):`

**Detector.** `plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_refusal_tokens[relocate-session-terminal]`.

**Red** (EXIT=1):

```
>       assert rc == 1
E       assert 0 == 1
FAILED plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_refusal_tokens[relocate-session-terminal]
1 failed in 2.91s
```

**Restore.** Inverse edit. **Restore receipt:** `git diff --quiet -- plugins/superheroes/lib/round_driver.py; echo $?` → `0`.

**Green** (EXIT=0): `1 passed in 11.46s`.

## G5 — target-not-toplevel realpath-equality check

**Guarded element.** `_cmd_relocate_locked`, `if target_toplevel != os.path.realpath(target_root):`. **Axis:** target-not-toplevel refusal when target_root is not a git toplevel.

**Neutralization:** `if target_toplevel != os.path.realpath(target_root):` → `if False and target_toplevel != os.path.realpath(target_root):`

**Detector.** `plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_refusal_tokens[relocate-target-not-toplevel]`.

**Red** (EXIT=1):

```
>       assert rc == 1
E       assert 0 == 1
FAILED plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_refusal_tokens[relocate-target-not-toplevel]
1 failed in 4.24s
```

**Restore.** Inverse edit. **Restore receipt:** `git diff --quiet -- plugins/superheroes/lib/round_driver.py; echo $?` → `0`.

**Green** (EXIT=0): `1 passed in 4.29s`.

## G6 — session-dir-moved check

**Guarded element.** `_cmd_relocate_locked`, `if os.path.realpath(meta["sessionDir"]) != os.path.realpath(session_dir):`. **Axis:** session-dir-moved refusal (and ordering before same-checkout).

**Neutralization:** `if os.path.realpath(meta["sessionDir"]) != os.path.realpath(session_dir):` → `if False and os.path.realpath(meta["sessionDir"]) != os.path.realpath(session_dir):`

**Detector.** `plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_refusal_tokens[relocate-session-dir-moved]` and `plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_session_dir_moved_refuses_before_same_checkout`.

**Red** (EXIT=1):

```
>       assert out["reason"] == "relocate-session-dir-moved"
E       AssertionError: assert 'relocate-same-checkout' == 'relocate-session-dir-moved'
FAILED plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_refusal_tokens[relocate-session-dir-moved]
FAILED plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_session_dir_moved_refuses_before_same_checkout
2 failed in 9.81s
```

**Restore.** Inverse edit. **Restore receipt:** `git diff --quiet -- plugins/superheroes/lib/round_driver.py; echo $?` → `0`.

**Green** (EXIT=0): `2 passed in 4.60s`.

## G7 — same-checkout check

**Guarded element.** `_cmd_relocate_locked`, `if target_toplevel == old_root_rp:` (including the repair sub-block). **Axis:** same-checkout refusal when target equals the recorded checkout.

**Neutralization:** `if target_toplevel == old_root_rp:` → `if False and target_toplevel == old_root_rp:` (adapted to wrap the repair block now nested under this guard).

**Detector.** `plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_refusal_tokens[relocate-same-checkout]` and `plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_same_checkout_refused_even_from_the_recorded_session_dir`.

**Red** (EXIT=1):

```
>       assert rc == 1
E       assert 0 == 1
FAILED plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_refusal_tokens[relocate-same-checkout]
FAILED plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_same_checkout_refused_even_from_the_recorded_session_dir
2 failed in 5.05s
```

**Restore.** Inverse edit. **Restore receipt:** `git diff --quiet -- plugins/superheroes/lib/round_driver.py; echo $?` → `0`.

**Green** (EXIT=0): `2 passed in 12.44s`.

## G8 — repo-unverifiable (`baseRepo` missing)

**Guarded element.** `_cmd_relocate_locked`, `if not isinstance(base_repo, str) or not base_repo:`. **Axis:** repo-unverifiable refusal when baseRepo is missing.

**Neutralization:** `if not isinstance(base_repo, str) or not base_repo:` → `if False and (not isinstance(base_repo, str) or not base_repo):`

**Detector.** `plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_refusal_tokens[relocate-repo-unverifiable]`.

**Red** (EXIT=1):

```
plugins/superheroes/lib/round_driver.py:6381: in _cmd_relocate_locked
    if live_origin is None or live_origin.casefold() != base_repo.casefold():
E   AttributeError: 'NoneType' object has no attribute 'casefold'
FAILED plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_refusal_tokens[relocate-repo-unverifiable]
1 failed in 13.46s
```

**Restore.** Inverse edit. **Restore receipt:** `git diff --quiet -- plugins/superheroes/lib/round_driver.py; echo $?` → `0`.

**Green** (EXIT=0): `1 passed in 12.83s`.

## G9 — repo-mismatch (origin vs `baseRepo`)

**Guarded element.** `_cmd_relocate_locked`, `if live_origin is None or live_origin.casefold() != base_repo.casefold():`. **Axis:** origin vs recorded baseRepo disagreeing.

**Neutralization:** `if live_origin is None or live_origin.casefold() != base_repo.casefold():` → `if False and (live_origin is None or live_origin.casefold() != base_repo.casefold()):`

**Detector.** `plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_refusal_tokens[relocate-repo-mismatch]`.

**Red** (EXIT=1):

```
>       assert rc == 1
E       assert 0 == 1
FAILED plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_refusal_tokens[relocate-repo-mismatch]
1 failed in 2.82s
```

**Restore.** Inverse edit. **Restore receipt:** `git diff --quiet -- plugins/superheroes/lib/round_driver.py; echo $?` → `0`.

**Green** (EXIT=0): `1 passed in 2.56s`.

---

## G10 — base-mismatch (`meta.baseRef` vs `config.baseRef`)

**Guarded element.** `_cmd_relocate_locked`, `if meta_base != cfg_base:`. **Axis:** meta.baseRef vs config.baseRef disagreeing.

**Neutralization:** `if meta_base != cfg_base:` → `if False and meta_base != cfg_base:`

**Detector.** `plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_refusal_tokens[relocate-base-mismatch]`.

**Red** (EXIT=1):

```
>       assert rc == 1
E       assert 0 == 1
FAILED plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_refusal_tokens[relocate-base-mismatch]
1 failed in 3.18s
```

**Restore.** Inverse edit. **Restore receipt:** `git diff --quiet -- plugins/superheroes/lib/round_driver.py; echo $?` → `0`.

**Green** (EXIT=0): `1 passed in 3.90s`.

---

## G11 — base pin unresolvable in target (`resolved_pin is None`)

**Guarded element.** `_cmd_relocate_locked`, `if resolved_pin is None:` (the branch that refuses with detail `"baseRef does not resolve in target"`). **Axis:** unresolvable base pin.

**Neutralization attempted:** `if resolved_pin is None:` → `if False and resolved_pin is None:`

**Detector attempted.** `plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_refuses_a_base_pin_that_does_not_resolve_in_the_target`.

**Unproven.** Neutralization applied; detector stayed **GREEN** (EXIT=0): `1 passed in 2.96s`. Directly beneath this guard, `if not isinstance(meta_base, str) or resolved_pin != meta_base.lower():` re-checks `resolved_pin != meta_base.lower()`. Since `resolved_pin` is `None` whenever G11's condition is true, the next line refuses with the same externally visible `reason` (`relocate-base-mismatch`); no test asserts the distinguishing `detail` string. **Disclosure — Unprovable as placed** (per `rubric/bite-proof.md`).

**Restore.** Inverse edit applied regardless. **Restore receipt:** `git diff --quiet -- plugins/superheroes/lib/round_driver.py; echo $?` → `0`.

---

## G12a — `_relocate_recorded_head` `meta_has != cfg_has`

**Guarded element.** `_relocate_recorded_head`, `if meta_has != cfg_has:`. **Axis:** only one FIX_FOLD_HEAD copy is set.

**Neutralization:** `if meta_has != cfg_has:` → `if False and meta_has != cfg_has:`

**Detector.** `plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_refusal_tokens[relocate-head-ambiguous]`.

**Red** (EXIT=1):

```
>       assert rc == 1
E       assert 0 == 1
FAILED plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_refusal_tokens[relocate-head-ambiguous]
1 failed in 3.65s
```

**Restore.** Inverse edit. **Restore receipt:** `git diff --quiet -- plugins/superheroes/lib/round_driver.py; echo $?` → `0`.

**Green** (EXIT=0): `1 passed in 3.28s`.

---

## G12b — `_relocate_recorded_head` `meta_key != cfg_key`

**Guarded element.** `_relocate_recorded_head`, `if meta_has and cfg_has and meta_key != cfg_key:`. **Axis:** both FIX_FOLD_HEAD copies are set and disagree.

**Neutralization:** `if meta_has and cfg_has and meta_key != cfg_key:` → `if False and (meta_has and cfg_has and meta_key != cfg_key):`

**Detector.** `plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_refuses_when_fix_fold_head_copies_disagree`.

**Red** (EXIT=1):

```
>       assert rc == 1
E       assert 0 == 1
FAILED plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_refuses_when_fix_fold_head_copies_disagree
1 failed in 2.70s
```

**Restore.** Inverse edit. **Restore receipt:** `git diff --quiet -- plugins/superheroes/lib/round_driver.py; echo $?` → `0`.

**Green** (EXIT=0): `1 passed in 3.18s`.

---

## G13 — target HEAD vs recorded head compare

**Guarded element.** `_cmd_relocate_locked`, `if head_res.out.lower() != recorded_head.lower():`. **Axis:** moved-ahead target.

**Neutralization:** `if head_res.out.lower() != recorded_head.lower():` → `if False and head_res.out.lower() != recorded_head.lower():`

**Detector.** `plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_refuses_target_ahead_of_recorded_head`.

**Red** (EXIT=1):

```
>       assert rc == 1
E       assert 0 == 1
FAILED plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_refuses_target_ahead_of_recorded_head
1 failed in 3.22s
```

**Restore.** Inverse edit. **Restore receipt:** `git diff --quiet -- plugins/superheroes/lib/round_driver.py; echo $?` → `0`.

**Green** (EXIT=0): `1 passed in 2.57s`.

---

## G14 — records-path-bound check

**Guarded element.** `_cmd_relocate_locked`, `if _relocate_path_inside(records_path, old_root_rp):`. **Axis:** recordsPath lies inside the old root.

**Neutralization:** `if _relocate_path_inside(records_path, old_root_rp):` → `if False and _relocate_path_inside(records_path, old_root_rp):`

**Detector.** `plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_refusal_tokens[relocate-records-path-bound]`.

**Red** (EXIT=1):

```
>       assert rc == 1
E       assert 0 == 1
FAILED plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_refusal_tokens[relocate-records-path-bound]
1 failed in 4.07s
```

**Restore.** Inverse edit. **Restore receipt:** `git diff --quiet -- plugins/superheroes/lib/round_driver.py; echo $?` → `0`.

**Green** (EXIT=0): `1 passed in 6.07s`.

---

## G15 — target marker foreign (sessionDir compare)

The old record cited `_cmd_relocate_locked`; at this head the foreign-marker check lives in `_relocate_claim_target_marker` (lexists branch).

**Guarded element.** `_relocate_claim_target_marker`, `if not isinstance(marker, dict) or marker.get("sessionDir") != session_rp:`. **Axis:** target marker names another session.

**Neutralization:** wrapped the condition in `False and (...)` at the lexists branch (adapted from the old `_cmd_relocate_locked` site).

**Detector.** `plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_refusal_tokens[relocate-target-marker-foreign]`.

**Red** (EXIT=1):

```
>       assert rc == 1
E       assert 0 == 1
FAILED plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_refusal_tokens[relocate-target-marker-foreign]
1 failed in 2.07s
```

**Restore.** Inverse edit. **Restore receipt:** `git diff --quiet -- plugins/superheroes/lib/round_driver.py; echo $?` → `0`.

**Green** (EXIT=0): `1 passed in 7.03s`.

---

## G15b — a claimed target refuses a second session (sequential)

**Guarded element.** `_relocate_claim_target_marker`, `if not isinstance(marker, dict) or marker.get("sessionDir") != session_rp:` (lexists branch). **Axis:** sequential claim-then-claim — second session refused.

**Neutralization:** wrapped the condition in `False and (...)` at the lexists branch.

**Detector.** `plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_second_claimant_refused_after_first_claims_the_target`.

**Red** (EXIT=1):

```
>       assert rc2 == 1
E       assert 0 == 1
FAILED plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_second_claimant_refused_after_first_claims_the_target
1 failed in 21.73s
```

**Restore.** Inverse edit. **Restore receipt:** `git diff --quiet -- plugins/superheroes/lib/round_driver.py; echo $?` → `0`.

**Green** (EXIT=0): `1 passed in 21.91s`.

## G16 — target marker unparseable (the `except` around `json.load`)

**Guarded element.** `_relocate_read_target_marker`, `except Exception:` (around `json.load(fh)`). **Axis:** target marker unparseable bites on non-JSON marker content (refusal-shape: malformed marker must not propagate as an uncaught exception).

**Neutralization:** `except Exception:` → `except KeyError:` (site moved from `_cmd_relocate_locked` into `_relocate_read_target_marker`; intent unchanged).

**Detector.** `plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_refusal_tokens[relocate-target-marker-not-json]`.

**Red** (EXIT=1):

```
E           json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)
FAILED plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_refusal_tokens[relocate-target-marker-not-json]
1 failed in 5.40s
```

**Restore.** Inverse edit. **Restore receipt:** `git diff --quiet -- plugins/superheroes/lib/round_driver.py; echo $?` → `0`.

**Green** (EXIT=0): `1 passed in 3.22s`.

## G17 — the session lock in `cmd_relocate`

**Guarded element.** `cmd_relocate`, `except round_records.SessionLockHeld as held:` (around `_cmd_relocate_locked`). **Axis:** the session lock bites on a held lock refusing relocate.

**Neutralization:** `except round_records.SessionLockHeld as held:` → `except KeyError as held:`.

**Detector.** `plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_refusal_tokens[relocate-locked]`.

**Red** (EXIT=1):

```
E           round_records.SessionLockHeld: session lock held by pid 424242 since '2026-08-07T00:00:00'
FAILED plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_refusal_tokens[relocate-locked]
1 failed in 2.80s
```

**Restore.** Inverse edit. **Restore receipt:** `git diff --quiet -- plugins/superheroes/lib/round_driver.py; echo $?` → `0`.

**Green** (EXIT=0): `1 passed in 4.15s`.

## G18 — rewritten-only mutation

**Guarded element.** `_cmd_relocate_locked`, the contract that `relocated.rewritten` names exactly the checkout keys the commit touches — no more, no less (via `rewritten.append(...)` after `new_meta["branch"] = new_branch`). **Axis:** rewritten-only mutation bites on any extra non-checkout key rewrite.

**Neutralization:** inserted after `rewritten.append("meta.branch")`: `new_meta["headSha"] = "0" * 40` then `rewritten.append("meta.headSha")`.

**Detector.** `plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_rewritten_keys_are_exactly_the_checkout_keys`.

**Red** (EXIT=1):

```
E       AssertionError: assert ['meta.branch...fig.repoRoot'] == ['meta.branch...fig.repoRoot']
E         At index 1 diff: 'meta.headSha' != 'meta.repoRoot'
FAILED plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_rewritten_keys_are_exactly_the_checkout_keys
1 failed in 3.66s
```

**Restore.** Removed the two inserted lines. **Restore receipt:** `git diff --quiet -- plugins/superheroes/lib/round_driver.py; echo $?` → `0`.

**Green** (EXIT=0): `1 passed in 3.82s`.

## G19 — the `state.config.repoRoot` rewrite

**Guarded element.** `_cmd_relocate_locked`, `if "repoRoot" in new_cfg:` (block that rewrites `state.config.repoRoot` to the target checkout). **Axis:** the state.config.repoRoot rewrite bites on the new checkout's config.

**Neutralization:** `if "repoRoot" in new_cfg:` → `if False and "repoRoot" in new_cfg:`.

**Detector.** `plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_positive_and_next_from_new_checkout`.

**Red** (EXIT=1):

```
E       AssertionError: assert '/private/var...d_nex0/repo_a' == '/private/var...d_nex0/repo_b'
FAILED plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_positive_and_next_from_new_checkout
1 failed in 3.26s
```

**Restore.** Inverse edit. **Restore receipt:** `git diff --quiet -- plugins/superheroes/lib/round_driver.py; echo $?` → `0`.

**Green** (EXIT=0): `1 passed in 3.27s`.

## G20 — `_retire_relocate_marker` ownership check (not-ours)

**Guarded element.** `_retire_relocate_marker`, `if not isinstance(marker, dict) or marker.get("sessionDir") != session_rp:` (returns `"not-ours"`). **Axis:** the not-ours ownership check bites on a foreign marker's sessionDir.

**Neutralization:** `if not isinstance(marker, dict) or marker.get("sessionDir") != session_rp:` → `if False and (not isinstance(marker, dict) or marker.get("sessionDir") != session_rp):`.

**Detector.** `plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_marker_not_ours_left_alone`.

**Red** (EXIT=1):

```
E       AssertionError: assert 'retired' == 'not-ours'
FAILED plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_marker_not_ours_left_alone
1 failed in 0.49s
```

**Restore.** Inverse edit. **Restore receipt:** `git diff --quiet -- plugins/superheroes/lib/round_driver.py; echo $?` → `0`.

**Green** (EXIT=0): `1 passed in 1.46s`.

## G21 — marker retirement only when the target marker names this session

The prior record cited `test_relocate_marker_kept_when_target_detached` and a `kept-no-target-marker` branch; neither exists at this head (`kept-no-target-marker` appears only in the stale record).

**Removed.** The `kept-no-target-marker` outcome and its gated retirement path were dropped in the relocate refactor; detached targets are refused earlier via `if new_branch == "HEAD": return _refuse_cmd(..., "relocate-target-detached")`, and successful relocate always retires the old-checkout marker via `_retire_relocate_marker(old_root_rp, session_rp)` with no target-marker gate.

## G22 — an uncreatable marker directory is refused as JSON, never raised

**Guarded element.** `_relocate_claim_target_marker`, `except OSError:` (around `os.makedirs(parent, exist_ok=True)`). **Axis:** an uncreatable marker directory is refused as JSON, never raised (refusal-shape axis).

**Neutralization:** `except OSError:` → `except KeyError:` (in the `os.makedirs` block).

**Detector.** `plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_uncreatable_marker_directory_refuses_as_json`.

**Red** (EXIT=1):

```
E           FileExistsError: [Errno 17] File exists: '.../superheroes'
FAILED plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_uncreatable_marker_directory_refuses_as_json
1 failed in 3.88s
```

**Restore.** Inverse edit. **Restore receipt:** `git diff --quiet -- plugins/superheroes/lib/round_driver.py; echo $?` → `0`.

**Green** (EXIT=0): `1 passed in 2.72s`.

## G23 — an existing same-session marker is accepted idempotently

**Guarded element.** `_relocate_claim_target_marker`, `return True, False, None` (after `_relocate_refresh_target_marker` in the `os.path.lexists(marker_path)` branch). **Axis:** an existing same-session marker is accepted idempotently; refreshing a stale marker is G24's axis (idempotent-retry axis).

**Neutralization:** `return True, False, None` → `return False, False, "foreign"` (first attempt — wrapping refresh in `if False:` — stayed green because the pre-seeded marker already matched refreshed content; second attempt used the return-value neutralization).

**Detector.** `plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_target_marker_idempotent_retry`.

**Red** (EXIT=1):

```
E       assert 1 == 0
FAILED plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_target_marker_idempotent_retry
1 failed in 9.04s
```

**Restore.** Inverse edit (`return False, False, "foreign"` → `return True, False, None`). **Restore receipt:** `git diff --quiet -- plugins/superheroes/lib/round_driver.py; echo $?` → `0`.

**Green** (EXIT=0): `1 passed in 10.96s`.

## G24 — stale branch in target marker refreshed

**Guarded element.** `_relocate_claim_target_marker`, the existing-marker branch that calls `_relocate_refresh_target_marker(marker_path, marker_content)` when `marker.get("sessionDir") == session_rp`. **Axis:** a stale branch name in an already-claimed target marker is refreshed to the current target branch.

**Neutralization:** wrapped the refresh call: `if False: _relocate_refresh_target_marker(marker_path, marker_content)` (first occurrence, lines 6176–6177).

**Detector.** `plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_target_marker_stale_branch_refreshed`.

**Red** (EXIT=1):

```
>       assert marker["branch"] == "branch-b"
E       AssertionError: assert 'branch-a' == 'branch-b'
FAILED plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_target_marker_stale_branch_refreshed
1 failed in 3.93s
```

**Restore.** Inverse edit. **Restore receipt:** `git diff --quiet -- plugins/superheroes/lib/round_driver.py; echo $?` → `0`.

**Green** (EXIT=0): `1 passed in 3.75s`.

## G25 — claim write failure returns unwritable and leaves no marker

**Guarded element.** `_relocate_claim_target_marker`, `except OSError: return False, False, "unwritable"` on the new-marker `.claim.tmp` write path. **Axis:** a simulated write failure on claim creation is caught and returned as `unwritable` rather than propagating.

**Neutralization:** `except OSError:` → `except KeyError:` (new-marker path, line 6204).

**Detector.** `plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_claim_write_failure_leaves_no_marker`.

**Red** (EXIT=1):

```
>           raise OSError("simulated write failure")
E           OSError: simulated write failure
FAILED plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_claim_write_failure_leaves_no_marker
1 failed in 3.47s
```

**Restore.** Inverse edit. **Restore receipt:** `git diff --quiet -- plugins/superheroes/lib/round_driver.py; echo $?` → `0`.

**Green** (EXIT=0): `1 passed in 2.70s`.

## G26 — refused commit releases newly claimed marker

**Guarded element.** `_cmd_relocate_locked`, `if marker_created and exc.reason != "commit-cleanup-failed": _relocate_release_target_marker(target_marker_path, session_rp)` in the `CommitRefused` handler. **Axis:** when commit is refused after a newly created marker, the marker is released.

**Neutralization:** `if False and marker_created and exc.reason != "commit-cleanup-failed":`.

**Detector.** `plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_commit_refused_removes_claimed_marker`.

**Red** (EXIT=1):

```
>       assert not os.path.lexists(marker_path)
E       AssertionError: assert not True
FAILED plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_commit_refused_removes_claimed_marker
1 failed in 6.39s
```

**Restore.** Inverse edit. **Restore receipt:** `git diff --quiet -- plugins/superheroes/lib/round_driver.py; echo $?` → `0`.

**Green** (EXIT=0): `1 passed in 7.15s`.

## G27 — crash recovery leaves a retryable session

**Guarded element.** `_cmd_relocate_locked`, `c.add_replace_file(os.path.join(session_dir, STATE_FILE), _canonical(new_state).encode("utf-8"))` — the state file staged into the relocate commit for replay on sealed/partial crash recovery. **Axis:** crash recovery at sealed and partial stop points replays relocate state changes so the session agrees with the relocated journal row.

**Neutralization:** wrapped the state `add_replace_file` call: `if False: c.add_replace_file(... STATE_FILE ...)`. (Adapted from prior record: recovery discard lived in `round_commit.recover`, but restore receipt is scoped to `round_driver.py`; this neutralization blocks state replay through the relocate commit builder.)

**Detector.** `plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_crash_matrix`.

**Red** (EXIT=1):

```
>       assert snap["state"] != before["state"]
E       assert b'{"_changedSubjectsSincePanel":[]...' != b'{"_changedSubjectsSincePanel":[]...'
FAILED plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_crash_matrix[sealed]
FAILED plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_crash_matrix[part:0]
2 failed, 1 passed in 34.97s
```

**Restore.** Inverse edit. **Restore receipt:** `git diff --quiet -- plugins/superheroes/lib/round_driver.py; echo $?` → `0`.

**Green** (EXIT=0): `3 passed in 33.94s`.

## G28 — post-commit retirement removes old checkout marker

**Guarded element.** `_cmd_relocate_locked`, `marker_outcome = _retire_relocate_marker(old_root_rp, session_rp)` after successful commit. **Axis:** post-commit retirement of the old-checkout marker returns `retired` and removes the source marker file.

**Neutralization:** replaced the call with `if False: marker_outcome = _retire_relocate_marker(...)` / `else: marker_outcome = "absent"`.

**Detector.** `plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_marker_retirement`.

**Red** (EXIT=1):

```
>       assert out["markerRetirement"] == "retired"
E       AssertionError: assert 'absent' == 'retired'
FAILED plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_marker_retirement
1 failed in 11.06s
```

**Restore.** Inverse edit. **Restore receipt:** `git diff --quiet -- plugins/superheroes/lib/round_driver.py; echo $?` → `0`.

**Green** (EXIT=0): `1 passed in 10.44s`.

## G29 — retirement survives interleaved marker replacement

**Guarded element.** `_retire_relocate_marker`, the `retired` return path that calls only `os.unlink(tmp)` and does not remove `marker_path` after an interleaved replacement. **Axis:** TOCTOU — a marker replaced during retirement survives at `marker_path`.

**Neutralization:** after `os.unlink(tmp)`, inserted `if not False: os.remove(marker_path)` (with `OSError` pass).

**Detector.** `plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_marker_retirement_survives_interleaved_replacement`.

**Red** (EXIT=1):

```
>       surviving = json.load(open(marker_a, encoding="utf-8"))
E       FileNotFoundError: [Errno 2] No such file or directory: '.../review-session.json'
FAILED plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_marker_retirement_survives_interleaved_replacement
1 failed in 9.60s
```

**Restore.** Inverse edit. **Restore receipt:** `git diff --quiet -- plugins/superheroes/lib/round_driver.py; echo $?` → `0`.

**Green** (EXIT=0): `1 passed in 9.82s`.

## G30 — post-commit crash repaired by same-target retry

**Guarded element.** `_cmd_relocate_locked`, the same-checkout branch that calls `_relocate_try_repair_marker_retirement(session_dir, os.path.realpath(session_dir), target_toplevel)`. **Axis:** a post-commit crash before marker retirement is repaired when relocate is retried against the already-committed target.

**Neutralization:** `repaired = (_relocate_try_repair_marker_retirement(...) if False else None)`.

**Detector.** `plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_post_commit_crash_repaired_by_same_target_retry`.

**Red** (EXIT=1):

```
>       assert rc == 0
E       assert 1 == 0
FAILED plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_post_commit_crash_repaired_by_same_target_retry
1 failed in 10.46s
```

**Restore.** Inverse edit. **Restore receipt:** `git diff --quiet -- plugins/superheroes/lib/round_driver.py; echo $?` → `0`.

**Green** (EXIT=0): `1 passed in 12.14s`.

## G31 — relocate leaves non-checkout session state alone

**Guarded element.** `_cmd_relocate_locked`, the `new_state = json.loads(_canonical(state))` copy that must preserve `pending.payload.verify.landingPath` unchanged through the relocate commit. **Axis:** scope — relocate rewrites only checkout keys and does not mutate other session payload paths.

**Neutralization:** after building `new_state`, appended `.mutated` to `pending.payload.verify.landingPath` when present.

**Detector.** `plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_changes_nothing_else_in_the_session`.

**Red** (EXIT=1):

```
>       assert landing_after == landing_before
E       AssertionError: assert '...payload.json.mutated' == '...payload.json'
FAILED plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_changes_nothing_else_in_the_session
1 failed in 13.01s
```

**Restore.** Inverse edit. **Restore receipt:** `git diff --quiet -- plugins/superheroes/lib/round_driver.py; echo $?` → `0`.

**Green** (EXIT=0): `1 passed in 13.91s`.

---

Nothing redacted (temporary paths only).
