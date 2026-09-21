# Bite-proof record — #1272 layer 2i-a (the `relocate` verb)

Contract: `rubric/bite-proof.md`. Every proof below ran with the **detector unedited**; each
neutralization was a targeted, reversible edit to the guarded site (`plugins/superheroes/lib/round_driver.py`)
applied with the Edit tool, restored by its exact inverse edit (never `git checkout`, never a
whole-file rewrite), with `git status --porcelain` **empty** after every restore.

**Who ran these, and where.** Work order c13-2ia-woC, in a dedicated detached probe worktree
(`issue-1272-2ia-probe`) cut at **`49df56e8`** — never in the build worktree, and with no other
session reading the probe tree during these runs.

Every command was run as
`/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest <node-id> -q -p no:randomly`
with EXIT the runner's own exit code, never a pipe's. Every detector was selected by its **exact
node id**, never `-k`.

**The guarded set.** 21 elements in `_cmd_relocate_locked` / `cmd_relocate` /
`_relocate_recorded_head` / `_retire_relocate_marker`, `round_driver.py`. One proof per element,
except G11 which is recorded **unproven** below.

**Whole-file baseline** (both trees, clean, before/after all neutralizations):

- Probe tree (`issue-1272-2ia-probe`), after the last restore: `33 passed in 115.14s`.
- Build tree (`issue-1272-efe41f96b59f20b3`), same file, unmodified: `33 passed in 127.81s`.

---

## G1a — `repoRoot` presence/type check

**Guarded element.** `_cmd_relocate_locked`, the `not isinstance(old_root, str) or not old_root`
half of the `repoRoot` guard.

**Neutralization** (one occurrence):
`if not isinstance(old_root, str) or not old_root or not os.path.isabs(old_root):` →
`if (False and (not isinstance(old_root, str) or not old_root)) or not os.path.isabs(old_root):`

**Detector.** `test_relocate_refusal_tokens[relocate-session-unreadable-no-repo-root]`.

**Red** (EXIT=1):

```
plugins/superheroes/lib/round_driver.py:6207: in _cmd_relocate_locked
    if (False and (not isinstance(old_root, str) or not old_root)) or not os.path.isabs(old_root):
E       TypeError: expected str, bytes or os.PathLike object, not NoneType
FAILED plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_refusal_tokens[relocate-session-unreadable-no-repo-root]
1 failed in 1.68s
```

**Restore.** Inverse edit (removed the `False and (...)` wrapper). **Restore receipt:**
`git status --porcelain` empty.

**Green** (EXIT=0): `1 passed in 1.60s`.

## G1b — `repoRoot` absolute check

**Guarded element.** Same guard, the `not os.path.isabs(old_root)` half.

**Neutralization:**
`if not isinstance(old_root, str) or not old_root or not os.path.isabs(old_root):` →
`if not isinstance(old_root, str) or not old_root or (False and not os.path.isabs(old_root)):`

**Detector.** `test_relocate_refusal_tokens[relocate-session-unreadable-relative-repo-root]`.

**Red** (EXIT=1):

```
>       assert rc == 1
E       assert 0 == 1
FAILED plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_refusal_tokens[relocate-session-unreadable-relative-repo-root]
1 failed in 1.56s
```

**Restore.** Inverse edit. **Restore receipt:** `git status --porcelain` empty.

**Green** (EXIT=0): `1 passed in 1.51s`.

## G2 — `sessionDir` presence/type check

**Guarded element.** `_cmd_relocate_locked`,
`if not isinstance(session_dir_meta, str) or not session_dir_meta:`.

**Neutralization:** wrapped the condition in `False and (...)`.

**Detector.** `test_relocate_refusal_tokens[relocate-session-unreadable-no-session-dir]`.

**Red** (EXIT=1):

```
>       if os.path.realpath(meta["sessionDir"]) != os.path.realpath(session_dir):
E       KeyError: 'sessionDir'
plugins/superheroes/lib/round_driver.py:6234: KeyError
FAILED plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_refusal_tokens[relocate-session-unreadable-no-session-dir]
1 failed in 1.68s
```

**Restore.** Inverse edit. **Restore receipt:** `git status --porcelain` empty.

**Green** (EXIT=0): `1 passed in 1.55s`.

## G3 — loop-state unreadable check

**Guarded element.** `_cmd_relocate_locked`, `if not ok_state or loaded is None:` after
`load_state`.

**Neutralization:** wrapped the condition in `False and (...)`.

**Detector.** `test_relocate_refusal_tokens[relocate-session-unreadable-state-missing]`.

**Red** (EXIT=1):

```
>       if state.get("terminal"):
E       AttributeError: 'NoneType' object has no attribute 'get'
plugins/superheroes/lib/round_driver.py:6220: AttributeError
FAILED plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_refusal_tokens[relocate-session-unreadable-state-missing]
1 failed in 1.69s
```

**Restore.** Inverse edit. **Restore receipt:** `git status --porcelain` empty.

**Green** (EXIT=0): `1 passed in 1.67s`.

## G4 — terminal-session check

**Guarded element.** `_cmd_relocate_locked`, `if state.get("terminal"):`.

**Neutralization:** `if False and state.get("terminal"):`.

**Detector.** `test_relocate_refusal_tokens[relocate-session-terminal]`.

**Red** (EXIT=1):

```
>       assert rc == 1
E       assert 0 == 1
FAILED plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_refusal_tokens[relocate-session-terminal]
1 failed in 1.56s
```

**Restore.** Inverse edit. **Restore receipt:** `git status --porcelain` empty.

**Green** (EXIT=0): `1 passed in 1.50s`.

## G5 — target-not-toplevel realpath-equality check

**Guarded element.** `_cmd_relocate_locked`,
`if target_toplevel != os.path.realpath(target_root):`.

**Neutralization:** `if False and target_toplevel != os.path.realpath(target_root):`.

**Detector.** `test_relocate_refusal_tokens[relocate-target-not-toplevel]`.

**Red** (EXIT=1):

```
>       assert rc == 1
E       assert 0 == 1
FAILED plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_refusal_tokens[relocate-target-not-toplevel]
1 failed in 1.82s
```

**Restore.** Inverse edit. **Restore receipt:** `git status --porcelain` empty.

**Green** (EXIT=0): `1 passed in 1.51s`.

## G6 — session-dir-moved check

**Guarded element.** `_cmd_relocate_locked`,
`if os.path.realpath(meta["sessionDir"]) != os.path.realpath(session_dir):`.

**Neutralization:** `if False and os.path.realpath(meta["sessionDir"]) != os.path.realpath(session_dir):`.

**Detectors.** `test_relocate_refusal_tokens[relocate-session-dir-moved]` and
`test_relocate_session_dir_moved_refuses_before_same_checkout` (the ordering axis — moved wins
over same-checkout).

**Red** (EXIT=1):

```
>       assert out["reason"] == "relocate-session-dir-moved"
E       AssertionError: assert 'relocate-same-checkout' == 'relocate-session-dir-moved'
FAILED plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_refusal_tokens[relocate-session-dir-moved]
FAILED plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_session_dir_moved_refuses_before_same_checkout
2 failed in 3.00s
```

**Restore.** Inverse edit. **Restore receipt:** `git status --porcelain` empty.

**Green** (EXIT=0): `2 passed in 2.86s`.

## G7 — same-checkout check

**Guarded element.** `_cmd_relocate_locked`, `if target_toplevel == old_root_rp:`.

**Neutralization:** `if False and target_toplevel == old_root_rp:`.

**Detectors.** `test_relocate_refusal_tokens[relocate-same-checkout]` and
`test_relocate_same_checkout_refused_even_from_the_recorded_session_dir`.

**Red** (EXIT=1):

```
>       assert rc == 1
E       assert 0 == 1
FAILED plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_refusal_tokens[relocate-same-checkout]
FAILED plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_same_checkout_refused_even_from_the_recorded_session_dir
2 failed in 2.99s
```

**Restore.** Inverse edit. **Restore receipt:** `git status --porcelain` empty.

**Green** (EXIT=0): `2 passed in 2.85s`.

## G8 — repo-unverifiable (`baseRepo` missing)

**Guarded element.** `_cmd_relocate_locked`, `if not isinstance(base_repo, str) or not base_repo:`.

**Neutralization:** wrapped the condition in `False and (...)`.

**Detector.** `test_relocate_refusal_tokens[relocate-repo-unverifiable]`.

**Red** (EXIT=1):

```
>       if live_origin is None or live_origin.casefold() != base_repo.casefold():
E       AttributeError: 'NoneType' object has no attribute 'casefold'
plugins/superheroes/lib/round_driver.py:6245: AttributeError
FAILED plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_refusal_tokens[relocate-repo-unverifiable]
1 failed in 1.69s
```

**Restore.** Inverse edit. **Restore receipt:** `git status --porcelain` empty.

**Green** (EXIT=0): `1 passed in 1.66s`.

## G9 — repo-mismatch (origin vs `baseRepo`)

**Guarded element.** `_cmd_relocate_locked`,
`if live_origin is None or live_origin.casefold() != base_repo.casefold():`.

**Neutralization:** wrapped the condition in `False and (...)`.

**Detector.** `test_relocate_refusal_tokens[relocate-repo-mismatch]`.

**Red** (EXIT=1):

```
>       assert rc == 1
E       assert 0 == 1
FAILED plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_refusal_tokens[relocate-repo-mismatch]
1 failed in 1.61s
```

**Restore.** Inverse edit. **Restore receipt:** `git status --porcelain` empty.

**Green** (EXIT=0): `1 passed in 1.55s`.

## G10 — base-mismatch (`meta.baseRef` vs `config.baseRef`)

**Guarded element.** `_cmd_relocate_locked`, `if meta_base != cfg_base:`.

**Neutralization:** `if False and meta_base != cfg_base:`.

**Detector.** `test_relocate_refusal_tokens[relocate-base-mismatch]`.

**Red** (EXIT=1):

```
>       assert rc == 1
E       assert 0 == 1
FAILED plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_refusal_tokens[relocate-base-mismatch]
1 failed in 1.57s
```

**Restore.** Inverse edit. **Restore receipt:** `git status --porcelain` empty.

**Green** (EXIT=0): `1 passed in 1.73s`.

## G11 — base pin unresolvable in target (`resolved_pin is None`) — UNPROVEN

**Guarded element.** `_cmd_relocate_locked`, `if resolved_pin is None:` (the branch that refuses
with detail `"baseRef does not resolve in target"`).

**Neutralization attempted:** `if False and resolved_pin is None:`.

**Detector attempted.** `test_relocate_refuses_a_base_pin_that_does_not_resolve_in_the_target`.

**Result — stayed GREEN with the guard disabled** (EXIT=0): `1 passed in 2.43s`. No red was
producible through this detector.

**Why it cannot bite here.** Directly beneath this guard, line 6260
(`if not isinstance(meta_base, str) or resolved_pin != meta_base.lower():`) re-checks
`resolved_pin != meta_base.lower()`. Since `resolved_pin` is `None` whenever G11's own condition
is true, `None != meta_base.lower()` is always `True`, so the very next line refuses with the
**same externally visible reason** (`relocate-base-mismatch`) that G11 would have produced —
only the `detail` string differs (`"baseRef does not resolve in target: …"` vs `"resolved pin …
does not match meta.baseRef …"`), and no test in this file asserts `detail`. The distinction G11
makes is not observable at the black-box surface this detector reads.

**Disclosure — Unprovable as placed** (per `rubric/bite-proof.md`): what would make it provable —
a test that asserts the refusal `detail` string distinguishes "did not resolve" from "resolved but
disagrees", or restructuring so the two branches carry different `reason` tokens; until then this
line's protection specifically (as opposed to the guard immediately below it, which line 6260
supplies) is unverified. This disclosure is unadjudicated by the party that wrote it — it travels
to the next independent reader of this record.

**Restore.** Inverse edit applied regardless (targeted, reversible). **Restore receipt:**
`git status --porcelain` empty.

## G12a — `_relocate_recorded_head` `meta_has != cfg_has`

**Guarded element.** `_relocate_recorded_head`, `if meta_has != cfg_has: return None, True`.

**Neutralization:** `if False and meta_has != cfg_has:`.

**Detector.** `test_relocate_refusal_tokens[relocate-head-ambiguous]`.

**Red** (EXIT=1):

```
>       assert rc == 1
E       assert 0 == 1
FAILED plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_refusal_tokens[relocate-head-ambiguous]
1 failed in 2.05s
```

**Restore.** Inverse edit. **Restore receipt:** `git status --porcelain` empty.

**Green** (EXIT=0): `1 passed in 1.67s`.

## G12b — `_relocate_recorded_head` `meta_key != cfg_key`

**Guarded element.** `_relocate_recorded_head`,
`if meta_has and cfg_has and meta_key != cfg_key: return None, True`.

**Neutralization:** wrapped the condition in `False and (...)`.

**Detector.** `test_relocate_refuses_when_fix_fold_head_copies_disagree`.

**Red** (EXIT=1):

```
>       assert rc == 1
E       assert 0 == 1
FAILED plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_refuses_when_fix_fold_head_copies_disagree
1 failed in 1.79s
```

**Restore.** Inverse edit. **Restore receipt:** `git status --porcelain` empty.

**Green** (EXIT=0): `1 passed in 1.73s`.

## G13 — target HEAD vs recorded head compare

**Guarded element.** `_cmd_relocate_locked`,
`if head_res.out.lower() != recorded_head.lower():`.

**Neutralization:** `if False and head_res.out.lower() != recorded_head.lower():`.

**Detector.** `test_relocate_refuses_target_ahead_of_recorded_head`.

**Red** (EXIT=1):

```
>       assert rc == 1
E       assert 0 == 1
FAILED plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_refuses_target_ahead_of_recorded_head
1 failed in 1.78s
```

**Restore.** Inverse edit. **Restore receipt:** `git status --porcelain` empty.

**Green** (EXIT=0): `1 passed in 1.76s`.

## G14 — records-path-bound check

**Guarded element.** `_cmd_relocate_locked`,
`if _relocate_path_inside(records_path, old_root_rp):`.

**Neutralization:** `if False and _relocate_path_inside(records_path, old_root_rp):`.

**Detector.** `test_relocate_refusal_tokens[relocate-records-path-bound]`.

**Red** (EXIT=1):

```
>       assert rc == 1
E       assert 0 == 1
FAILED plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_refusal_tokens[relocate-records-path-bound]
1 failed in 2.02s
```

**Restore.** Inverse edit. **Restore receipt:** `git status --porcelain` empty.

**Green** (EXIT=0): `1 passed in 1.95s`.

## G15 — target marker foreign (sessionDir compare)

**Guarded element.** `_cmd_relocate_locked`,
`if (not isinstance(target_marker, dict) or target_marker.get("sessionDir") != session_rp):`.

**Neutralization:** wrapped the condition in `False and (...)`.

**Detector.** `test_relocate_refusal_tokens[relocate-target-marker-foreign]`.

**Red** (EXIT=1):

```
>       assert rc == 1
E       assert 0 == 1
FAILED plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_refusal_tokens[relocate-target-marker-foreign]
1 failed in 1.81s
```

**Restore.** Inverse edit. **Restore receipt:** `git status --porcelain` empty.

**Green** (EXIT=0): `1 passed in 1.79s`.

## G16 — target marker unparseable (the `except` around `json.load`)

**Guarded element.** `_cmd_relocate_locked`, the `except Exception as exc:` guarding
`json.load(fh)` on the target marker.

**Neutralization:** `except Exception as exc:` → `except KeyError as exc:` (won't catch
`json.JSONDecodeError`).

**Detector.** `test_relocate_refusal_tokens[relocate-target-marker-not-json]`.

**Red** (EXIT=1):

```
>           raise JSONDecodeError("Expecting value", s, err.value) from None
E           json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)
FAILED plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_refusal_tokens[relocate-target-marker-not-json]
1 failed in 1.95s
```

**Restore.** Inverse edit (`except KeyError as exc:` → `except Exception as exc:`). **Restore
receipt:** `git status --porcelain` empty.

**Green** (EXIT=0): `1 passed in 1.75s`.

## G17 — the session lock in `cmd_relocate`

**Guarded element.** `cmd_relocate`, `except round_records.SessionLockHeld as held:` around
`_cmd_relocate_locked`.

**Neutralization:** `except round_records.SessionLockHeld as held:` → `except KeyError as held:` —
the lock-held refusal path no longer catches the real exception, so a held lock now propagates
uncaught instead of being converted to a refusal.

**Detector.** `test_relocate_refusal_tokens[relocate-locked]`.

**Red** (EXIT=1):

```
>           raise SessionLockHeld(holder.get("pid"), holder.get("createdAt"))
E           round_records.SessionLockHeld: session lock held by pid 424242 since '2026-08-07T00:00:00'
FAILED plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_refusal_tokens[relocate-locked]
1 failed in 1.88s
```

**Restore.** Inverse edit (`except KeyError as held:` → `except round_records.SessionLockHeld as
held:`). **Restore receipt:** `git status --porcelain` empty.

**Green** (EXIT=0): `1 passed in 1.89s`.

## G18 — rewritten-only mutation

**Guarded element.** `_cmd_relocate_locked`, the contract that `relocated.rewritten` names exactly
the checkout keys the commit touches — no more, no less.

**Neutralization:** inserted one extra rewrite of a non-checkout key directly after
`rewritten.append("meta.branch")`:
`new_meta["headSha"] = "0" * 40` then `rewritten.append("meta.headSha")`.

**Detector.** `test_relocate_rewritten_keys_are_exactly_the_checkout_keys`.

**Red** (EXIT=1):

```
>       assert out["relocated"]["rewritten"] == sorted(
            ["meta.branch", "meta.repoRoot", "state.config.repoRoot"])
E       AssertionError: assert ['meta.branch...fig.repoRoot'] == ['meta.branch...fig.repoRoot']
E         At index 1 diff: 'meta.headSha' != 'meta.repoRoot'
E         Left contains one more item: 'state.config.repoRoot'
FAILED plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_rewritten_keys_are_exactly_the_checkout_keys
1 failed in 1.97s
```

**Restore.** Removed the two inserted lines. **Restore receipt:** `git status --porcelain` empty.

**Green** (EXIT=0): `1 passed in 1.85s`.

## G19 — the `state.config.repoRoot` rewrite

**Guarded element.** `_cmd_relocate_locked`, `if "repoRoot" in new_cfg:` block that rewrites
`state.config.repoRoot` to the target checkout.

**Neutralization:** `if "repoRoot" in new_cfg:` → `if False and "repoRoot" in new_cfg:` (removes
the rewrite).

**Detector.** `test_relocate_positive_and_next_from_new_checkout`.

**Red** (EXIT=1):

```
>       assert state["config"]["repoRoot"] == repo["root_b"]
E       AssertionError: assert '/private/var/.../repo_a' == '/private/var/.../repo_b'
FAILED plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_positive_and_next_from_new_checkout
1 failed in 3.12s
```

**Restore.** Inverse edit. **Restore receipt:** `git status --porcelain` empty.

**Green** (EXIT=0): `1 passed in 3.41s`.

## G20 — `_retire_relocate_marker` ownership check (not-ours)

**Guarded element.** `_retire_relocate_marker`,
`if marker.get("sessionDir") != os.path.realpath(session_dir): return "not-ours"`.

**Neutralization:** `if False and marker.get("sessionDir") != os.path.realpath(session_dir):`.

**Detector.** `test_relocate_marker_not_ours_left_alone` (direct call to
`RD._retire_relocate_marker`).

**Red** (EXIT=1):

```
>       assert outcome == "not-ours"
E       AssertionError: assert 'retired' == 'not-ours'
FAILED plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_marker_not_ours_left_alone
1 failed in 0.57s
```

**Restore.** Inverse edit. **Restore receipt:** `git status --porcelain` empty.

**Green** (EXIT=0): `1 passed in 0.55s`.

## G21 — marker retirement only when the target marker names this session

**Guarded element.** `_cmd_relocate_locked`, the post-commit block that leaves
`marker_outcome = "kept-no-target-marker"` unless the target checkout actually carries a marker
recorded for *this* session (the outer `os.path.isfile(target_marker_path)` plus inner
`target_marker.get("sessionDir") == session_rp` gate together).

**Neutralization:** bypassed the gate by unconditionally attempting retirement of the **old**
checkout's marker before the gated block runs — inserted
`marker_outcome = _retire_relocate_marker(old_root_rp, session_rp)` as the first statement inside
the `try:`, ahead of `if os.path.isfile(target_marker_path):`.

**Detector.** `test_relocate_marker_kept_when_target_detached` (target is a detached-HEAD
worktree, so no target marker exists; the guard should leave the source-checkout marker alone).

**Red** (EXIT=1):

```
>       assert out["markerRetirement"] == "kept-no-target-marker"
E       AssertionError: assert 'retired' == 'kept-no-target-marker'
FAILED plugins/superheroes/lib/tests/test_round_driver_session_mobility.py::test_relocate_marker_kept_when_target_detached
1 failed in 3.64s
```

**Restore.** Removed the inserted line. **Restore receipt:** `git status --porcelain` empty.

**Green** (EXIT=0): `1 passed in 1.82s`.

---

## Whole-file re-runs (after all elements restored)

**Probe tree** (`issue-1272-2ia-probe`, `49df56e8`), EXIT=0: `33 passed in 115.14s`.

**Build tree** (`issue-1272-efe41f96b59f20b3`), unmodified copy of the same file, EXIT=0:
`33 passed in 127.81s`.

**Final probe-tree restore receipt** — `git -C issue-1272-2ia-probe status --porcelain`: empty
(no output, exit 0).

---

## Disclosures

- **G11 is unprovable as placed** (see above) — the guard's own refusal branch is shadowed by the
  next line's independent check, which produces the same externally visible `reason` token. This
  disclosure is unadjudicated by the party that wrote it.
- No other element required disclosure; all remaining 20 declared elements produced a clean
  red/green pair.

---

## Orchestrator re-run (independent verification of every element)

Re-run by the build orchestrator in the probe tree `issue-1272-2ia-probe` (detached at `49df56e8`;
its `round_driver.py` is byte-identical to this record's commit — `git diff --quiet 49df56e8 HEAD --
plugins/superheroes/lib/round_driver.py` exit 0). Each neutralization applied alone with the host's
edit action, the detector run by exact node id, the inverse edit applied before the next element.

| Element | Neutralization re-applied | Red (decisive line) |
|---|---|---|
| G1a | `(False and (not isinstance(old_root, str) or not old_root)) or not os.path.isabs(old_root)` | `TypeError: expected str, bytes or os.PathLike object, not NoneType` — 1 failed |
| G1b | `… or (False and not os.path.isabs(old_root))` | `assert 0 == 1` — 1 failed |
| G2 | `if False and (not isinstance(session_dir_meta, str) or not session_dir_meta):` | `KeyError: 'sessionDir'`; `test_relocate_refuses_none_session_dir` `TypeError` — 2 failed |
| G3 | `if False and (not ok_state or loaded is None):` | `AttributeError: 'NoneType' object has no attribute 'get'` — 1 failed |
| G4 | `if False and state.get("terminal"):` | `assert 0 == 1` — 1 failed |
| G5 | `if False and target_toplevel != os.path.realpath(target_root):` | `assert 0 == 1` — 1 failed |
| G6 | `if False and os.path.realpath(meta["sessionDir"]) != …:` | `assert 0 == 1` and `assert 'relocate-same-checkout' == 'relocate-session-dir-moved'` — 2 failed |
| G7 | `if False and target_toplevel == old_root_rp:` | `assert 0 == 1` ×2 — 2 failed |
| G8 | `if False and (not isinstance(base_repo, str) or not base_repo):` | `AttributeError: 'NoneType' object has no attribute 'casefold'` — 1 failed |
| G9 | `if False and (live_origin is None or …):` | `assert 0 == 1` — 1 failed |
| G10 | `if False and meta_base != cfg_base:` | `assert 0 == 1` — 1 failed |
| G11 | `if False and resolved_pin is None:` | stayed green, `1 passed` — **disclosure accepted**: the check that confirmed it is the next line, `if not isinstance(meta_base, str) or resolved_pin != meta_base.lower():`, which refuses the same `relocate-base-mismatch` whenever `resolved_pin` is `None`; the unresolvable-pin invariant is therefore guarded, only the `detail` wording is unguarded |
| G12a | `if False and meta_has != cfg_has:` | `assert 0 == 1` — 1 failed |
| G12b | `if False and (meta_has and cfg_has and meta_key != cfg_key):` | `assert 0 == 1` — 1 failed |
| G13 | `if False and head_res.out.lower() != recorded_head.lower():` | `assert 0 == 1` on both `…target_ahead…` and `…mid_fix_head_mismatch…` — 2 failed |
| G14 | `if False and _relocate_path_inside(records_path, old_root_rp):` | `assert 0 == 1` — 1 failed |
| G15 | `if False and (not isinstance(target_marker, dict) or …):` | `assert 0 == 1` — 1 failed |
| G16 | `except Exception as exc:` → `except KeyError as exc:` | `json.decoder.JSONDecodeError: Expecting value` — 1 failed |
| G17 | `except round_records.SessionLockHeld as held:` → `except KeyError as held:` | `round_records.SessionLockHeld: session lock held by pid 424242` — 1 failed |
| G18 | **stricter than above**: an UNDECLARED extra rewrite, `new_meta["headSha"] = "0" * 40` with no `rewritten.append` | `test_relocate_invariant_no_old_paths_survive`: `'headSha': '9ce9…' != 'headSha': '0000…'` — failed (the snapshot-minus-rewritten comparison bites an undeclared rewrite, not only a declared one) |
| G19 | `if False and "repoRoot" in new_cfg:` | `assert '…/repo_a' == '…/repo_b'` — 1 failed |
| G20 | `if False and marker.get("sessionDir") != os.path.realpath(session_dir):` | `assert 'retired' == 'not-ours'` — 1 failed |
| G21 | inserted `marker_outcome = _retire_relocate_marker(old_root_rp, session_rp)` ahead of the gate | `assert 'retired' == 'kept-no-target-marker'` — 1 failed |

**Restore receipt:** probe tree `git status --porcelain` empty (exit 0) and `git diff --quiet HEAD
-- plugins/superheroes/lib/round_driver.py` exit 0 after the last inverse edit. **Green:** whole
file in the probe tree, `33 passed in 16.95s`. Nothing redacted (temporary paths only).
