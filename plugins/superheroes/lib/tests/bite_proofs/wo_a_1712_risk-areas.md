# #1712 bite-proof — risk areas (WO-A: storage, item 10, the reader, the view)

Per-element bite-proof for the risk-area detectors in `plugins/superheroes/lib/core_md.py`, `plugins/superheroes/lib/risk_areas.py` and `plugins/superheroes/lib/project_config.py`. Each element was neutralized with one targeted edit, its single test node ran alone and went red, the edit was undone by the inverse edit, the restored line was quoted back, and the same node ran green. No test file was edited between a red and its green.

Command for every run (never `-k`, never filtered):

```
scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest '<file>::<test>' -q
```

`T` = `plugins/superheroes/lib/tests/test_risk_areas.py`, `P` = `plugins/superheroes/lib/tests/test_project_config_risk_and_trust.py`.

Declared guarded-element set: G1–G10, as dispatched. Redaction: none needed; local temp paths are left as printed.

## Summary

| ID | Guarded element | Axis | Neutralization | Node | Red |
|---|---|---|---|---|---|
| G1 | `core_md.validate_risk_areas` duplicate-name refusal | names unique by stripped, case-folded text | `if folded in seen:` → `if False and folded in seen:` | `T::test_duplicate_names_refused` | `assert [] == [{... 'risk-area-duplicate-name'}]` |
| G2 | `core_md.risk_area_pattern_problem` leading-`./` refusal | a leading `./` is refused under its own token | `if pattern.startswith("./"):` → `if False and pattern.startswith("./"):` | `T::test_leading_dot_slash_pattern_refused` | `'pattern-dot-segment' == 'pattern-leading-dot-slash'` |
| G3 | `core_md.validate_risk_areas` exact key set | a missing key is malformed | `for field in RISK_AREA_FIELDS:` → `for field in ("name", "covers", "why"):` | `T::test_missing_undo_refused` | `assert [] == [{... 'risk-area-missing-field'}]` |
| G4 | `risk_areas.touched` missing leg | no core.md / no key is `not-set` `missing` | the leg returns `_result("set", None, None, [], [], [])` | `T::test_no_riskareas_key_is_not_set_missing` | `assert 'set' == 'not-set'` |
| G5 | `risk_areas.touched` empty leg | `[]` is `not-set` `empty`, never "touches none" | `if not areas:` → `if False and not areas:` | `T::test_empty_list_is_not_set_empty` | `assert 'set' == 'not-set'` |
| G6 | `core_md.read_risk_areas` non-dict `projectConfiguration` | reads unreadable, never as a missing key | the `if` → `if False and ...` | `T::test_project_configuration_not_an_object_is_not_set_unreadable` | `assert 'missing' == 'unreadable'` |
| G7 | `risk_areas.pattern_matches` | a path under a stored pattern is reported touched | body → `return False` | `T::test_payments_path_and_its_dot_slash_spelling_are_reported_touched` | `assert [] == [{'area': ...}]` |
| G8 | no-model-call guard | the reader starts no process | `import subprocess` and `subprocess.run(["true"])` as the first statements after the paths check in `touched` | `T::test_touched_makes_no_model_call` | `AssertionError: a process, a shell or a connection was started` |
| G9 | `project_config._set_risk_and_trust` half-aware read-back | only the written half is compared | `_values_equal(after.get(half), submitted)` → `_values_equal(after, value)` (today's whole-raw rule) | `P::test_set_risk_areas_writes_once_then_noops_and_leaves_the_threat_model_bytes` | `assert 'refused' == 'written'` |
| G10 | `project_config._set_risk_and_trust` other-half-unchanged check | a set that moves the other half is refused | `if before is not None and ...` → `if False and before is not None and ...` | `P::test_set_that_changes_the_other_half_is_a_mismatch_naming_that_half` | `assert ('written' == 'refused'` |

G10 is reachable through the public entry `set_item`: the test wraps `core_md.write_project_config_item` so the write also moves the threat model, which is the only way a set could change the other half. No disclosure shape is needed.

G2 disclosure: the dot-segment rule also refuses `./src/payments/*`, so dropping the leading-`./` condition does not make the pattern acceptable. The test therefore asserts the specific token `pattern-leading-dot-slash`, and the red is on that token, not on acceptance.

G8 note: the reader's one git lookup (the repo root, run through `store_core`) is answered by `store_core.repo_identity_memo()`, warmed by a first `touched` call in the test, so the raising stand-ins for `subprocess.run`, `subprocess.Popen`, `os.system` and `socket.socket.connect` only see anything the reader itself starts.

## G1 — duplicate-name refusal

Neutralization: `plugins/superheroes/lib/core_md.py` line 380, `if folded in seen:` → `if False and folded in seen:`.

Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_________________________ test_duplicate_names_refused _________________________

    def test_duplicate_names_refused():
        dup = dict(PAYMENTS, name=" payments ", covers=["lib/*"])
        got = CM.validate_risk_areas([PAYMENTS, dup])
>       assert got == [{"index": 1, "field": "name", "reason": "risk-area-duplicate-name"}]
E       AssertionError: assert [] == [{'index': 1,...licate-name'}]
E         
E         Right contains one more item: {'index': 1, 'field': 'name', 'reason': 'risk-area-duplicate-name'}
E         Use -v to get more diff

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1712-908b6c467f62dd01/plugins/superheroes/lib/tests/test_risk_areas.py:141: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_risk_areas.py::test_duplicate_names_refused
1 failed in 0.15s
```

Restore: the inverse edit. Restored line quoted back: `380:            if folded in seen:`

Green:

```
.                                                                        [100%]
1 passed in 0.30s
```

## G2 — leading-`./` refusal

Neutralization: `core_md.py`, `if pattern.startswith("./"):` → `if False and pattern.startswith("./"):`.

Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
____________________ test_leading_dot_slash_pattern_refused ____________________

    def test_leading_dot_slash_pattern_refused():
        # the token is asserted, not just "refused": the dot-segment rule would also catch this form
>       assert CM.risk_area_pattern_problem("./src/payments/*") == "pattern-leading-dot-slash"
E       AssertionError: assert 'pattern-dot-segment' == 'pattern-leading-dot-slash'
E         
E         - pattern-leading-dot-slash
E         + pattern-dot-segment

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1712-908b6c467f62dd01/plugins/superheroes/lib/tests/test_risk_areas.py:93: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_risk_areas.py::test_leading_dot_slash_pattern_refused
1 failed in 2.07s
```

Restore: the inverse edit. Restored line quoted back: `331:    if pattern.startswith("./"):`

Green:

```
.                                                                        [100%]
1 passed in 0.16s
```

## G3 — exact key set

Neutralization: `core_md.py`, `for field in RISK_AREA_FIELDS:` (the missing-field loop) → `for field in ("name", "covers", "why"):`.

Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
__________________________ test_missing_undo_refused ___________________________

    def test_missing_undo_refused():
        area = {k: v for k, v in PAYMENTS.items() if k != "undo"}
        got = CM.validate_risk_areas([area])
>       assert got == [{"index": 0, "field": "undo", "reason": "risk-area-missing-field"}]
E       AssertionError: assert [] == [{'index': 0,...ssing-field'}]
E         
E         Right contains one more item: {'index': 0, 'field': 'undo', 'reason': 'risk-area-missing-field'}
E         Use -v to get more diff

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1712-908b6c467f62dd01/plugins/superheroes/lib/tests/test_risk_areas.py:147: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_risk_areas.py::test_missing_undo_refused
1 failed in 0.17s
```

Restore: the inverse edit. Restored lines quoted back: `358:        for field in RISK_AREA_FIELDS:` / `359:            if field not in entry:`

Green:

```
.                                                                        [100%]
1 passed in 0.12s
```

## G4 — reader `missing` leg

Neutralization: `risk_areas.py`, the leg's `return _result("not-set", REASON_MISSING, reason)` → `return _result("set", None, None, [], [], [])`.

Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
___________________ test_no_riskareas_key_is_not_set_missing ___________________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1178/test_no_riskareas_key_is_not_s0')

    def test_no_riskareas_key_is_not_set_missing(tmp_path):
        repo, store = _repo(tmp_path, with_key=False)
>       _assert_not_set(R.touched(repo, ["src/payments/charge.py"], root=store), "missing")

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1712-908b6c467f62dd01/plugins/superheroes/lib/tests/test_risk_areas.py:288: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

got = {'riskAreas': 'set', 'reason': None, 'detail': None, 'areas': [], ...}
reason = 'missing'

    def _assert_not_set(got, reason):
>       assert got["riskAreas"] == "not-set"
E       AssertionError: assert 'set' == 'not-set'
E         
E         - not-set
E         + set

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1712-908b6c467f62dd01/plugins/superheroes/lib/tests/test_risk_areas.py:274: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_risk_areas.py::test_no_riskareas_key_is_not_set_missing
1 failed in 1.78s
```

Restore: the inverse edit. Restored lines quoted back: `77:    if reason == "core-md-absent" or not stored.get("declared"):` / `78:        return _result("not-set", REASON_MISSING, reason)`

Green:

```
.                                                                        [100%]
1 passed in 2.65s
```

## G5 — reader `empty` leg

Neutralization: `risk_areas.py`, `if not areas:` → `if False and not areas:`.

Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_______________________ test_empty_list_is_not_set_empty _______________________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1180/test_empty_list_is_not_set_emp0')

    def test_empty_list_is_not_set_empty(tmp_path):
        repo, store = _repo(tmp_path, [])
>       _assert_not_set(R.touched(repo, ["src/payments/charge.py"], root=store), "empty")

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1712-908b6c467f62dd01/plugins/superheroes/lib/tests/test_risk_areas.py:293: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

got = {'riskAreas': 'set', 'reason': None, 'detail': None, 'areas': [], ...}
reason = 'empty'

    def _assert_not_set(got, reason):
>       assert got["riskAreas"] == "not-set"
E       AssertionError: assert 'set' == 'not-set'
E         
E         - not-set
E         + set

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1712-908b6c467f62dd01/plugins/superheroes/lib/tests/test_risk_areas.py:274: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_risk_areas.py::test_empty_list_is_not_set_empty
1 failed in 2.05s
```

Restore: the inverse edit. Restored lines quoted back: `83:    if not areas:` / `84:        return _result("not-set", REASON_EMPTY)`

Green:

```
.                                                                        [100%]
1 passed in 2.17s
```

## G6 — reader `unreadable` leg for a non-dict `projectConfiguration`

Neutralization: `core_md.py` `read_risk_areas`, the `if PROJECT_CONFIGURATION_KEY in block and not isinstance(` check → `if False and PROJECT_CONFIGURATION_KEY in block and not isinstance(`. The fixture list is `["risk"]`, so the unguarded `RISK_AREAS_KEY not in mapping` reads it as an absent key, which is the failure this guards.

Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
________ test_project_configuration_not_an_object_is_not_set_unreadable ________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1182/test_project_configuration_not0')

    def test_project_configuration_not_an_object_is_not_set_unreadable(tmp_path):
        repo, store = _raw_core(tmp_path, _block(projectConfiguration=["risk"]))
        got = R.touched(repo, ["src/payments/charge.py"], root=store)
>       _assert_not_set(got, "unreadable")

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1712-908b6c467f62dd01/plugins/superheroes/lib/tests/test_risk_areas.py:306: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

got = {'riskAreas': 'not-set', 'reason': 'missing', 'detail': None, 'areas': [], ...}
reason = 'unreadable'

    def _assert_not_set(got, reason):
        assert got["riskAreas"] == "not-set"
>       assert got["reason"] == reason
E       AssertionError: assert 'missing' == 'unreadable'
E         
E         - unreadable
E         + missing

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1712-908b6c467f62dd01/plugins/superheroes/lib/tests/test_risk_areas.py:275: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_risk_areas.py::test_project_configuration_not_an_object_is_not_set_unreadable
1 failed in 0.26s
```

Restore: the inverse edit. Restored lines quoted back: `2472:        if PROJECT_CONFIGURATION_KEY in block and not isinstance(` / `2473:                block[PROJECT_CONFIGURATION_KEY], dict):`

Green:

```
.                                                                        [100%]
1 passed in 0.35s
```

## G7 — reader match

Neutralization: `risk_areas.py`, `return fnmatch.fnmatchcase(path, pattern)` → `return False`.

Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
______ test_payments_path_and_its_dot_slash_spelling_are_reported_touched ______

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1184/test_payments_path_and_its_dot0')

    def test_payments_path_and_its_dot_slash_spelling_are_reported_touched(tmp_path):
        repo, store = _repo(tmp_path, [PAYMENTS, CUSTOMER_DATA])
        for spelling in ("src/payments/charge.py", "./src/payments/charge.py",
                         "src\\payments\\charge.py", ".//src//payments/charge.py"):
            got = R.touched(repo, [spelling], root=store)
            assert got["riskAreas"] == "set" and got["reason"] is None
>           assert got["touched"] == [{"area": PAYMENTS, "matched": ["src/payments/charge.py"]}]
E           AssertionError: assert [] == [{'area': {'n.../charge.py']}]
E             
E             Right contains one more item: {'area': {'name': 'Payments', 'covers': ['src/payments/*'], 'why': 'Charges customers.', 'undo': 'Hard: a charge needs a refund.'}, 'matched': ['src/payments/charge.py']}
E             Use -v to get more diff

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1712-908b6c467f62dd01/plugins/superheroes/lib/tests/test_risk_areas.py:229: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_risk_areas.py::test_payments_path_and_its_dot_slash_spelling_are_reported_touched
1 failed in 2.07s
```

Restore: the inverse edit. Restored line quoted back: `49:    return fnmatch.fnmatchcase(path, pattern)`

Green:

```
.                                                                        [100%]
1 passed in 2.38s
```

## G8 — no model call

Neutralization: `risk_areas.py`, two lines inserted before `stored = core_md.read_risk_areas(cwd, root=root)` in `touched`: `import subprocess` and `subprocess.run(["true"])`.

Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_______________________ test_touched_makes_no_model_call _______________________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1186/test_touched_makes_no_model_ca0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x10b480ec0>

    def test_touched_makes_no_model_call(tmp_path, monkeypatch):
        repo, store = _repo(tmp_path, [PAYMENTS])
    
        def _refuse(*args, **kwargs):
            raise AssertionError("a process, a shell or a connection was started")
    
        # the reader's one git lookup (the repo root) is answered by the identity memo, which is
        # warmed first; anything else the reader started would reach the raising stand-ins below
        with CM.store_core.repo_identity_memo():
            assert R.touched(repo, [], root=store)["riskAreas"] == "set"
            monkeypatch.setattr(subprocess, "run", _refuse)
            monkeypatch.setattr(subprocess, "Popen", _refuse)
            monkeypatch.setattr(os, "system", _refuse)
            monkeypatch.setattr(socket.socket, "connect", _refuse)
>           got = R.touched(repo, ["src/payments/charge.py", "./src/payments/charge.py"], root=store)
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1712-908b6c467f62dd01/plugins/superheroes/lib/tests/test_risk_areas.py:366: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/Users/zwrose/.superheroes-worktrees/superheroes/issue-1712-908b6c467f62dd01/plugins/superheroes/lib/risk_areas.py:71: in touched
    subprocess.run(["true"])
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

args = (['true'],), kwargs = {}

    def _refuse(*args, **kwargs):
>       raise AssertionError("a process, a shell or a connection was started")
E       AssertionError: a process, a shell or a connection was started

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1712-908b6c467f62dd01/plugins/superheroes/lib/tests/test_risk_areas.py:356: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_risk_areas.py::test_touched_makes_no_model_call
1 failed in 2.60s
```

Restore: the inverse edit (both lines removed). Restored lines quoted back: `69:        return _result("not-set", REASON_UNREADABLE, "paths-not-a-list-of-strings")` / `70:    stored = core_md.read_risk_areas(cwd, root=root)`; a search of `risk_areas.py` for `subprocess` finds nothing.

Green:

```
.                                                                        [100%]
1 passed in 1.93s
```

## G9 — half-aware read-back

Neutralization: `project_config.py` `_set_risk_and_trust`, `if after is None or not _values_equal(after.get(half), submitted):` → `if after is None or not _values_equal(after, value):`.

Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_set_risk_areas_writes_once_then_noops_and_leaves_the_threat_model_bytes _

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1188/test_set_risk_areas_writes_onc0')

    def test_set_risk_areas_writes_once_then_noops_and_leaves_the_threat_model_bytes(tmp_path):
        repo, store = _setup_repo(tmp_path)
        before = _core_text(repo, store)
        section_before = CM._section(before, "Threat model")
        res = PC.set_item(repo, "riskAndTrust", {"riskAreas": [PAYMENTS]}, root=store)
>       assert res["action"] == "written"
E       AssertionError: assert 'refused' == 'written'
E         
E         - written
E         + refused

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1712-908b6c467f62dd01/plugins/superheroes/lib/tests/test_project_config_risk_and_trust.py:222: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_project_config_risk_and_trust.py::test_set_risk_areas_writes_once_then_noops_and_leaves_the_threat_model_bytes
1 failed in 1.51s
```

Restore: the inverse edit. Restored line quoted back: `687:    if after is None or not _values_equal(after.get(half), submitted):`

Green:

```
.                                                                        [100%]
1 passed in 2.00s
```

## G10 — other-half-unchanged check

Neutralization: `project_config.py` `_set_risk_and_trust`, `if before is not None and not _values_equal(after.get(other), before.get(other)):` → `if False and before is not None and not _values_equal(after.get(other), before.get(other)):`.

Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_set_that_changes_the_other_half_is_a_mismatch_naming_that_half ______

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1190/test_set_that_changes_the_othe0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x106d7c440>

    def test_set_that_changes_the_other_half_is_a_mismatch_naming_that_half(tmp_path, monkeypatch):
        repo, store = _setup_repo(tmp_path)
        real = PC.core_md.write_project_config_item
    
        def writes_and_also_moves_the_threat_model(*args, **kwargs):
            out = real(*args, **kwargs)
            PC.core_md.write_threat_model(repo, "changed behind the setter's back", root=store)
            return out
    
        monkeypatch.setattr(PC.core_md, "write_project_config_item",
                            writes_and_also_moves_the_threat_model)
        res = PC.set_item(repo, "riskAndTrust", {"riskAreas": [PAYMENTS]}, root=store)
>       assert res["action"] == "refused" and res["reason"] == PC.REASON_SET_MISMATCH
E       AssertionError: assert ('written' == 'refused'
E         
E         - refused
E         + written)

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1712-908b6c467f62dd01/plugins/superheroes/lib/tests/test_project_config_risk_and_trust.py:280: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_project_config_risk_and_trust.py::test_set_that_changes_the_other_half_is_a_mismatch_naming_that_half
1 failed in 1.83s
```

Restore: the inverse edit. Restored line quoted back: `695:    if before is not None and not _values_equal(after.get(other), before.get(other)):`

Green:

```
.                                                                        [100%]
1 passed in 1.72s
```

## WO-C

Item 10 reads its risk-areas half only through `core_md.read_risk_areas` (issue #1712, C4). Same command and shape as above; each element neutralized by one targeted edit, its single node run alone red, the inverse edit applied, the restored line quoted back, the same node run green. No test file was edited between a red and its green.

Declared guarded-element set: C1–C3, as dispatched. `P` = `plugins/superheroes/lib/tests/test_project_config_risk_and_trust.py`, `V` = `plugins/superheroes/lib/tests/test_configure_view_project_config.py`.

| ID | Guarded element | Axis | Neutralization | Node | Red |
|---|---|---|---|---|---|
| C1 | item 10 malformed for a stored `null` | `riskAreas: null` reads malformed, never a healthy empty list | in `_resolve_item_entry`'s `riskAndTrust` branch, after `areas_read = risk_areas_read or {}`, insert `if areas is None: areas_read = {"declared": False, "reason": None}` | `P::test_stored_null_areas_read_malformed_with_no_effective_list` | `assert False is True` on `got["malformed"]` |
| C2 | item 10 malformed for a non-object `projectConfiguration` | a `risk-areas-unreadable` reason makes item 10 malformed | `project_config.py` line 489 tuple `(MALFORMED, UNREADABLE)` → `(MALFORMED,)` | `P::test_project_configuration_that_is_a_list_reads_malformed_with_no_effective_list` | `assert False is True` on `got["malformed"]` |
| C3 | the `unset` row prefix | item 10 with nothing set says `unset` like every other item | `configure_view.py` `return "unset — " + shown` → `return shown` | `V::test_no_profile_renders_without_raising` | `assert False` on the `all("unset" in row or ...)` line |

### C1 red

```
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_stored_null_areas_read_malformed_with_no_effective_list _________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1268/test_stored_null_areas_read_ma0')

    def test_stored_null_areas_read_malformed_with_no_effective_list(tmp_path):
        repo, store = _setup_repo(tmp_path)
        _write_project_configuration(repo, store, {"riskAreas": None})
        got = PC.get_item(repo, "riskAndTrust", root=store)
>       assert got["malformed"] is True
E       assert False is True

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1712-908b6c467f62dd01/plugins/superheroes/lib/tests/test_project_config_risk_and_trust.py:424: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_project_config_risk_and_trust.py::test_stored_null_areas_read_malformed_with_no_effective_list
1 failed in 14.73s
```

Restore: the inverse edit (the two inserted lines removed). Restored lines quoted back: `487:        areas_read = risk_areas_read or {}` followed by `488:        areas_malformed = areas_read.get("reason") in (`.

C1 green:

```
.                                                                        [100%]
1 passed in 15.61s
```

### C2 red

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_project_configuration_that_is_a_list_reads_malformed_with_no_effective_list _

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1270/test_project_configuration_tha0')

    def test_project_configuration_that_is_a_list_reads_malformed_with_no_effective_list(tmp_path):
        repo, store = _setup_repo(tmp_path)
        _write_project_configuration(repo, store, ["riskAreas"])
        got = PC.get_item(repo, "riskAndTrust", root=store)
>       assert got["malformed"] is True
E       assert False is True

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1712-908b6c467f62dd01/plugins/superheroes/lib/tests/test_project_config_risk_and_trust.py:444: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_project_config_risk_and_trust.py::test_project_configuration_that_is_a_list_reads_malformed_with_no_effective_list
1 failed in 8.49s
```

Restore: the inverse edit. Restored line quoted back: `489:            core_md.RISK_AREAS_REASON_MALFORMED, core_md.RISK_AREAS_REASON_UNREADABLE)`

C2 green:

```
.                                                                        [100%]
1 passed in 15.77s
```

### C3 red

```
F                                                                        [100%]
=================================== FAILURES ===================================
___________________ test_no_profile_renders_without_raising ____________________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1272/test_no_profile_renders_withou0')

    def test_no_profile_renders_without_raising(tmp_path):
        repo = str(tmp_path)
        store = str(tmp_path / "store")
        _init_repo(tmp_path)
        screen = CV.render(repo, root=store)
        block = _project_config_section(screen)
        assert "profile: no core calibration yet" in block
        rows = _numbered_rows(block)
        assert len(rows) == 14
>       assert all("unset" in row or "plugin default" in row or "derived from dial" in row for row in rows)
E       assert False
E        +  where False = all(<generator object test_no_profile_renders_without_raising.<locals>.<genexpr> at 0x10b342f60>)

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1712-908b6c467f62dd01/plugins/superheroes/lib/tests/test_configure_view_project_config.py:137: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_configure_view_project_config.py::test_no_profile_renders_without_raising
1 failed in 23.04s
```

Restore: the inverse edit. Restored line quoted back: `257:            return "unset — " + shown`

C3 green:

```
.                                                                        [100%]
1 passed in 14.39s
```
