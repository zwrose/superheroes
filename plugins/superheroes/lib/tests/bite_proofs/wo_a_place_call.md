# Place call WO-A bite-proof: the readiness reader, the routing decision, the launch report and the "Still on your machine" line

> Note (2026-10-31, #2296): owner-machine paths and the name of a consuming project in this record were replaced with neutral placeholders after capture; nothing else changed.

Bite-proof record for `plugins/superheroes/lib/cloud_ready.py` (G1 to G5, G13) and `plugins/superheroes/lib/launch_place.py` (G6 to G11), detectors in `plugins/superheroes/lib/tests/test_cloud_ready.py` (`TR`) and `plugins/superheroes/lib/tests/test_launch_place.py` (`TL`).

**Status.** The implementer ran every proof (G1 to G13): each neutralization is a targeted Edit in the source file, the red is the single named test function run alone, the restore is the inverse Edit, and the green is the same function. Reds and greens below are the pytest output of each run unless a line says otherwise; the absolute `tmp_path` prefixes and the worktree path are as printed. No fixture holds a real secret, so nothing is redacted.

- **Run command.** `scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest "<T>::<node>" -q -p no:cacheprovider`.
- **Restore receipt, every element.** The restored line is quoted back from the source after the inverse Edit, and a closing run of both test files (221 tests, no `-k`) passed with every neutralization undone.
- **One extra run, disclosed.** G13's first red run was piped through `tail -60` by the implementer, which cut its first lines. It was re-run with the neutralization still in place, written whole to a file outside the repository (`/private/tmp/claude-501/-Users-zwrose--superheroes-worktrees-superheroes-issue-1746-9ec121c90cfeb086/6705fc6a-c17f-4fec-897b-9af932525c63/scratchpad/g13_red.txt`, 8954 bytes). Only that complete run is quoted below, with the repeated failure blocks elided as the line says.
- **Function-level nodes.** G13's node is a parametrized function; its ten cases run together. The other twelve nodes are plain functions.
- **Pinned condition.** `TR` and `TL` build their stores, repositories, account files and records under `tmp_path`; readiness is given a fixed `today` (`2026-10-11`), a fixed advisor version and an injected stamp function wherever a test is not about those; the reviewer-pass command runs against a clipboard recorder with a fixed `now`. The pin makes unobservable: the real home directory, the process environment, the real clipboard, the network and the real wall clock.

## Declared guarded-element set

G1 `passLive` compares with `>= today`; G2 `version` with a reported plugin version ignores the record; G3 `calibration` compares the stamp the reader is given or the one the cloud check uses; G4 a false `setup` forces every later condition false; G5 the reason is the first false condition; G6 the strict policy read's visibility leg; G7 its mode leg; G8 its store-spec leg; G9 a Canon lookup that raises counts as outside the repository; G10 the local word is checked before a need; G11 a need is checked before the cloud word and readiness; G13 an invalid `reported` is not ready.

Not neutralized, and so unproven by a run in this record: the default stamp formula `_placed_stamp` (its test, `TR::test_real_stamp_formula_is_the_one_the_check_uses`, asserts equality with the cloud check's own `_placed_stamp` but has no neutralization here; G3's representative neutralizes the comparison, not the formula).

## Per-element receipts

### G1: a pass is live while its lapse date is not before today. Axis: boundary (>=)

- **Neutralization applied.** In `cloud_ready._lapses_ok`, `fromisoformat(lapses) >= today` replaced with `fromisoformat(lapses) > today`.
- **Node.** `TR::test_pass_that_lapses_today_is_still_live`
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
__________________ test_pass_that_lapses_today_is_still_live ___________________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1116/test_pass_that_lapses_today_is0')

    def test_pass_that_lapses_today_is_still_live(tmp_path):
        repo, store = _ready(tmp_path, pass_lapses=TODAY.isoformat())
>       assert _read(repo, store)["ready"] is True
E       assert False is True

/path/to/home/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_cloud_ready.py:220: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_ready.py::test_pass_that_lapses_today_is_still_live
1 failed in 9.75s
```

- **Restore.** The inverse Edit; quoted from `cloud_ready.py:54`: `        return datetime.date.fromisoformat(lapses) >= today`.
- **Green.**

```
.                                                                        [100%]
1 passed in 9.41s
```

### G2: a version the cloud reported stands in place of the record's. Axis: input precedence

- **Neutralization applied.** In `cloud_ready._readiness`, `if reported.get("pluginVersion") is not None:` replaced with `if False:`.
- **Node.** `TR::test_reported_version_ignores_the_record_and_its_pickup`
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
___________ test_reported_version_ignores_the_record_and_its_pickup ____________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1118/test_reported_version_ignores_0')

    def test_reported_version_ignores_the_record_and_its_pickup(tmp_path):
        repo, store = _ready(tmp_path, plugin_version="1.2.2", picks_up_version=False)
        got = _read(repo, store, reported={"pluginVersion": ADVISOR})
>       assert got["ready"] is True and got["cloudVersion"] == ADVISOR
E       assert (False is True)

/path/to/home/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_cloud_ready.py:274: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_ready.py::test_reported_version_ignores_the_record_and_its_pickup
1 failed in 7.02s
```

- **Restore.** The inverse Edit; quoted from `cloud_ready.py:123`: `    if reported.get("pluginVersion") is not None:`.
- **Green.**

```
.                                                                        [100%]
1 passed in 4.95s
```

### G3: the calibration condition compares the placed stamp with the recorded one. Axis: comparison

- **Neutralization applied.** In `cloud_ready._readiness`, the two-line `conditions["calibration"] = (stamp_fn or _placed_stamp)(cwd, root) == record.get("calibrationStamp")` replaced with `conditions["calibration"] = True`.
- **Node.** `TR::test_calibration_that_differs_is_not_ready`
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
__________________ test_calibration_that_differs_is_not_ready __________________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1120/test_calibration_that_differs_0')

    def test_calibration_that_differs_is_not_ready(tmp_path):
        repo, store = _ready(tmp_path)
>       _only_false(_read(repo, store, stamp_fn=lambda cwd, root: OTHER_STAMP), "calibration")

/path/to/home/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_cloud_ready.py:302: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

result = {'ready': True, 'reason': None, 'conditions': {'setup': True, 'passPresent': True, 'passLive': True, 'version': True, ...}, 'setting': False, ...}
name = 'calibration'

    def _only_false(result, name):
        expected = dict(ALL_TRUE, **{name: False})
>       assert result["conditions"] == expected
E       AssertionError: assert {'setup': Tru...n': True, ...} == {'setup': Tru...n': True, ...}
E         
E         Omitting 5 identical items, use -vv to show
E         Differing items:
E         {'calibration': True} != {'calibration': False}
E         Use -v to get more diff

/path/to/home/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_cloud_ready.py:84: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_ready.py::test_calibration_that_differs_is_not_ready
1 failed in 5.25s
```

- **Restore.** The inverse Edit; quoted from `cloud_ready.py:132-133`: `        conditions["calibration"] = (stamp_fn or _placed_stamp)(cwd, root) == record.get(` / `            "calibrationStamp")`.
- **Green.**

```
.                                                                        [100%]
1 passed in 5.21s
```

### G4: no setup forces every later condition false. Axis: short-circuit

- **Neutralization applied.** In `cloud_ready._readiness`, `if not setup:` (the early return) replaced with `if False:`.
- **Node.** `TR::test_E2_missing_record_forces_every_later_condition_false`
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_E2_missing_record_forces_every_later_condition_false ___________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1122/test_E2_missing_record_forces_0')

    def test_E2_missing_record_forces_every_later_condition_false(tmp_path):
        repo, store = _setup_repo(tmp_path)
        got = _read(repo, store, reported={})
>       assert got["conditions"] == ALL_FALSE
E       AssertionError: assert {'setup': Fal...': False, ...} == {'setup': Fal...': False, ...}
E         
E         Omitting 4 identical items, use -vv to show
E         Differing items:
E         {'platform': True} != {'platform': False}
E         {'passPresent': True} != {'passPresent': False}
E         Use -v to get more diff

/path/to/home/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_cloud_ready.py:184: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_ready.py::test_E2_missing_record_forces_every_later_condition_false
1 failed in 4.55s
```

- **Restore.** The inverse Edit; quoted from `cloud_ready.py:115-116`: `    if not setup:` / `        return _result(conditions, **fallback)`.
- **Green.**

```
.                                                                        [100%]
1 passed in 4.57s
```

### G5: the reason is the first false condition in the fixed order. Axis: ordering

- **Neutralization applied.** In `cloud_ready._result`, `for name in CONDITION_ORDER if not conditions[name]` replaced with `for name in reversed(CONDITION_ORDER) if not conditions[name]`, so the last false condition names the reason.
- **Node.** `TR::test_order_pass_present_before_pass_live`
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
___________________ test_order_pass_present_before_pass_live ___________________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1124/test_order_pass_present_before0')

    def test_order_pass_present_before_pass_live(tmp_path):
        repo, store = _ready(tmp_path, pass_lapses=PAST)
        got = _read(repo, store, reported={"noPass": True})
>       assert got["reason"] == "no-pass"
E       AssertionError: assert 'pass-lapsed' == 'no-pass'
E         
E         - no-pass
E         + pass-lapsed

/path/to/home/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_cloud_ready.py:360: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_ready.py::test_order_pass_present_before_pass_live
1 failed in 5.14s
```

- **Restore.** The inverse Edit; quoted from `cloud_ready.py:62`: `    reason = next((REASON_FOR[name] for name in CONDITION_ORDER if not conditions[name]), None)`.
- **Green.**

```
.                                                                        [100%]
1 passed in 5.19s
```

### G6: the strict policy read's visibility leg. Axis: strict equality with "committed"

- **Neutralization applied.** In `launch_place._specs_outside`, `if policy.get("visibility") != architect_config.COMMITTED:` replaced with `if False:`.
- **Node.** `TL::test_specs_leg_visibility_must_be_committed`
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_________________ test_specs_leg_visibility_must_be_committed __________________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1126/test_specs_leg_visibility_must0')

    def test_specs_leg_visibility_must_be_committed(tmp_path):
        # The Canon reader normalizes these to committed, so only the strict specs leg can name them.
        for index, visibility in enumerate((None, "Committed", "", 1, True)):
            policy = {k: v for k, v in POLICY_OK.items() if k != "visibility"}
            if visibility is not None:
                policy["visibility"] = visibility
            repo, store = _world(_sub(tmp_path, str(index)), policy=policy)
>           assert LP.machine_needs(repo, {}, root=store) == [SPECS], visibility
E           AssertionError: None
E           assert [] == ["this project's specs"]
E             
E             Right contains one more item: "this project's specs"
E             Use -v to get more diff

/path/to/home/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_launch_place.py:416: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launch_place.py::test_specs_leg_visibility_must_be_committed
1 failed in 1.81s
```

- **Restore.** The inverse Edit; quoted from `launch_place.py:127`: `        if policy.get("visibility") != architect_config.COMMITTED:`.
- **Green.**

```
.                                                                        [100%]
1 passed in 4.63s
```

### G7: the strict policy read's mode leg. Axis: mode must be in-repo

- **Neutralization applied.** In `launch_place._specs_outside`, `if mode_registry.resolve(cwd, root, persist_backfill=False)["mode"] != mode_registry.IN_REPO:` replaced with `if False:`.
- **Node.** `TL::test_specs_leg_mode_must_be_in_repo`
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________________ test_specs_leg_mode_must_be_in_repo ______________________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1128/test_specs_leg_mode_must_be_in0')

    def test_specs_leg_mode_must_be_in_repo(tmp_path):
        repo, store = _world(tmp_path, mode=mode_registry.GLOBAL)
>       assert LP.machine_needs(repo, {}, root=store) == [SPECS]
E       assert [] == ["this project's specs"]
E         
E         Right contains one more item: "this project's specs"
E         Use -v to get more diff

/path/to/home/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_launch_place.py:421: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launch_place.py::test_specs_leg_mode_must_be_in_repo
1 failed in 1.73s
```

- **Restore.** The inverse Edit; quoted from `launch_place.py:133`: `        if mode_registry.resolve(cwd, root, persist_backfill=False)["mode"] != mode_registry.IN_REPO:`.
- **Green.**

```
.                                                                        [100%]
1 passed in 1.54s
```

### G8: the strict policy read's store-spec leg. Axis: a spec in the project store means outside

- **Neutralization applied.** In `launch_place._specs_outside`, `if os.path.isfile(os.path.join(docs, name, "spec.md")):` replaced with `if False:`.
- **Node.** `TL::test_specs_leg_store_must_hold_no_spec`
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
____________________ test_specs_leg_store_must_hold_no_spec ____________________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1130/test_specs_leg_store_must_hold0')

    def test_specs_leg_store_must_hold_no_spec(tmp_path):
        repo, store = _world(tmp_path, spec=True)
>       assert LP.machine_needs(repo, {}, root=store) == [SPECS]
E       assert [] == ["this project's specs"]
E         
E         Right contains one more item: "this project's specs"
E         Use -v to get more diff

/path/to/home/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_launch_place.py:426: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launch_place.py::test_specs_leg_store_must_hold_no_spec
1 failed in 2.04s
```

- **Restore.** The inverse Edit; quoted from `launch_place.py:139`: `                if os.path.isfile(os.path.join(docs, name, "spec.md")):`.
- **Green.**

```
.                                                                        [100%]
1 passed in 1.56s
```

### G9: a Canon lookup that raises counts as outside the repository. Axis: fail toward the owner's machine

- **Neutralization applied.** In `launch_place._canon_outside`, the `except Exception:` branch's `return True` replaced with `return False`.
- **Node.** `TL::test_E9_a_canon_lookup_that_raises_counts_as_outside`
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_E9_a_canon_lookup_that_raises_counts_as_outside _____________

inrepo = ('/private/tmp/claude-501/pytest-of-zwrose/pytest-1132/inrepo0/repo', '/private/tmp/claude-501/pytest-of-zwrose/pytest-1132/inrepo0/store')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x1073816d0>

    def test_E9_a_canon_lookup_that_raises_counts_as_outside(inrepo, monkeypatch):
        repo, store = inrepo
    
        def boom(**kwargs):
            raise definition_doc.CanonLookupError("could not probe")
    
        monkeypatch.setattr(definition_doc, "resolve_canon", boom)
>       assert LP.machine_needs(repo, {}, root=store) == [CANON]
E       assert [] == ["this project's Canon"]
E         
E         Right contains one more item: "this project's Canon"
E         Use -v to get more diff

/path/to/home/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_launch_place.py:353: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launch_place.py::test_E9_a_canon_lookup_that_raises_counts_as_outside
1 failed in 1.42s
```

- **Restore.** The inverse Edit; quoted from `launch_place.py:108-110`: `    except Exception:` / the axis comment / `        return True`.
- **Green.**

```
.                                                                        [100%]
1 passed in 1.26s
```

### G10: the local word is checked before a need. Axis: precedence

- **Neutralization applied.** In `launch_place.route`, `if launch_word == LOCAL_WORD:` replaced with `if launch_word == LOCAL_WORD and not wants(cwd, premise, root=root):`, so a need beats the local word.
- **Node.** `TL::test_route_local_word_wins_over_a_need`
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
____________________ test_route_local_word_wins_over_a_need ____________________

    def test_route_local_word_wins_over_a_need():
        call = LP.route("cwd", {}, "local", readiness_fn=_fn(), needs_fn=_needs(PHONE))
>       assert call["place"] == "local" and call["reason"] == "local-word"
E       AssertionError: assert ('local' == 'local'
E         
E           local and None == 'local-word')

/path/to/home/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_launch_place.py:470: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launch_place.py::test_route_local_word_wins_over_a_need
1 failed in 0.65s
```

- **Restore.** The inverse Edit; quoted from `launch_place.py:223`: `        if launch_word == LOCAL_WORD:`.
- **Green.**

```
.                                                                        [100%]
1 passed in 0.33s
```

### G11: a need is checked before the cloud word and readiness. Axis: precedence

- **Neutralization applied.** In `launch_place.route`, `if needs:` replaced with `if needs and launch_word != CLOUD_WORD:`, so a cloud word overrides a need.
- **Node.** `TL::test_route_cloud_word_never_overrides_a_need`
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_________________ test_route_cloud_word_never_overrides_a_need _________________

    def test_route_cloud_word_never_overrides_a_need():
        call = LP.route("cwd", {}, "cloud", readiness_fn=_fn(setting=False), needs_fn=_needs(PHONE))
>       assert call["place"] == "local" and call["reason"] == "needs"
E       AssertionError: assert ('cloud' == 'local'
E         
E         - local
E         + cloud)

/path/to/home/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_launch_place.py:476: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launch_place.py::test_route_cloud_word_never_overrides_a_need
1 failed in 0.41s
```

- **Restore.** The inverse Edit; quoted from `launch_place.py:229`: `        if needs:`.
- **Green.**

```
.                                                                        [100%]
1 passed in 0.34s
```

### G13: an invalid `reported` is not ready. Axis: refusal of an unknown shape

- **Neutralization applied.** In `cloud_ready._readiness`, `if not valid_reported(reported):` replaced with `if False:`.
- **Node.** `TR::test_E8_invalid_reported_is_never_ready` (ten cases).
- **Red** (from the complete re-run; the first failure block in full, then the closing summary in full; the other seven failure blocks are the same assertion with `reported` set to each of the other failing cases, and the `"x"` and `1` cases pass under this neutralization because the reader's own exception guard still reads them as not ready):

```
F..FFFFFFF                                                               [100%]
=================================== FAILURES ===================================
______________ test_E8_invalid_reported_is_never_ready[reported0] ______________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1141/test_E8_invalid_reported_is_ne0')
reported = []

    @pytest.mark.parametrize("reported", [
        [], "x", 1, {"other": True}, {"noPass": False}, {"noPass": "true"}, {"unreachable": 1},
        {"pluginVersion": 41}, {"pluginVersion": "0.41"}, {"noPass": True, "extra": 1},
    ])
    def test_E8_invalid_reported_is_never_ready(tmp_path, reported):
        repo, store = _ready(tmp_path)
        PC.set_item(repo, "cloudBuilds", True, root=store, account=ACCOUNT)
        got = _read(repo, store, reported=reported)
>       assert got["ready"] is False and got["reason"] == "no-setup"
E       assert (True is False)

/path/to/home/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_cloud_ready.py:330: AssertionError
[... seven more failure blocks, same assertion, elided ...]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_ready.py::test_E8_invalid_reported_is_never_ready[reported0]
FAILED plugins/superheroes/lib/tests/test_cloud_ready.py::test_E8_invalid_reported_is_never_ready[reported3]
FAILED plugins/superheroes/lib/tests/test_cloud_ready.py::test_E8_invalid_reported_is_never_ready[reported4]
FAILED plugins/superheroes/lib/tests/test_cloud_ready.py::test_E8_invalid_reported_is_never_ready[reported5]
FAILED plugins/superheroes/lib/tests/test_cloud_ready.py::test_E8_invalid_reported_is_never_ready[reported6]
FAILED plugins/superheroes/lib/tests/test_cloud_ready.py::test_E8_invalid_reported_is_never_ready[reported7]
FAILED plugins/superheroes/lib/tests/test_cloud_ready.py::test_E8_invalid_reported_is_never_ready[reported8]
FAILED plugins/superheroes/lib/tests/test_cloud_ready.py::test_E8_invalid_reported_is_never_ready[reported9]
8 failed, 2 passed in 53.89s
```

- **Restore.** The inverse Edit; quoted from `cloud_ready.py:109`: `    if not valid_reported(reported):`.
- **Green.**

```
..........                                                               [100%]
10 passed in 65.62s (0:01:05)
```
