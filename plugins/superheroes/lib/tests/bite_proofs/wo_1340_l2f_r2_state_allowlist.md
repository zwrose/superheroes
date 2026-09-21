# WO-G2 (#1340 layer 2f r2) bite-proof — PR vet state allowlist in stack_check.py

Per-guard bite proof for `_parse_pr_vet_state_payload` state allowlist added in layer 2f r2,
plus FIX-C vet-verdict-form load guards.

**Register:** 5 guards — G1 allowlist membership on GitHub `state`; G2 fail-closed
`FileNotFoundError` branch in `_load_vet_verdict_form`; G3/G4/G5 verdict-vocabulary branches
(unknown, duplicate, missing) in `_load_vet_verdict_form`.

**Provenance:** cursor / composer-2.5.

**Command** (referred to as *the command* below):

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_stack_check.py -q -k l2f
```

## Summary table

| ID | Guarded element (file:line) | Axis | Proving tests | Verdict |
|---|---|---|---|---|
| G1 | stack_check.py:702-705 | allowlist membership on state | `test_l2f_read_pr_vet_state_unrecognised_state`, `test_l2f_read_pr_vet_state_lowercase_open_refuses` | proven |
| G2 | stack_check.py `_load_vet_verdict_form` FileNotFoundError branch | missing form file refuses rather than embedded defaults | `test_l2f_v30_vet_form_missing_refuses` | proven |
| G3 | stack_check.py:122-126 | unknown verdict in loaded form | `test_l2f_v31_vet_form_unknown_verdict_refuses` | proven |
| G4 | stack_check.py:127-131 | duplicated verdict in loaded form | `test_l2f_v32_vet_form_duplicate_verdict_refuses` | proven |
| G5 | stack_check.py:133-138 | missing verdict in loaded form | `test_l2f_v33_vet_form_missing_verdict_refuses` | proven |

---

## G1 — allowlist membership on state

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
    if state not in PR_VET_STATE_VALUES:
        return None, _read_refusal(
            REASON_STACK_UNREADABLE,
            "state is not one of the enumerated values: %r" % state)
```
→
```python
    # allowlist neutralized for bite-proof
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_stack_check.py -q -k l2f
```

**raw red:**
```
......................................FF..                               [100%]
=================================== FAILURES ===================================
________________ test_l2f_read_pr_vet_state_unrecognised_state _________________

    def test_l2f_read_pr_vet_state_unrecognised_state():
        # axis: unrecognised state value refuses stack-unreadable
        run, _calls = _make_run(
            {_pr_vet_argv(): _pr_vet_ok(state="UNKNOWN")}
        )
        state, refusal = sc.read_pr_vet_state(DEP_PR, REPO, run=run)
>       assert state is None
E       AssertionError: assert {'body': '', 'headRefOid': 'abcdef0123456789abcdef0123456789abcdef01', 'isDraft': False, 'number': 701, ...} is None

plugins/superheroes/lib/tests/test_stack_check.py:1713: AssertionError
______________ test_l2f_read_pr_vet_state_lowercase_open_refuses _______________

    def test_l2f_read_pr_vet_state_lowercase_open_refuses():
        # axis: case-sensitive allowlist — lowercase open is not OPEN
        run, _calls = _make_run(
            {_pr_vet_argv(): _pr_vet_ok(state="open")}
        )
        state, refusal = sc.read_pr_vet_state(DEP_PR, REPO, run=run)
>       assert state is None
E       AssertionError: assert {'body': '', 'headRefOid': 'abcdef0123456789abcdef0123456789abcdef01', 'isDraft': False, 'number': 701, ...} is None

plugins/superheroes/lib/tests/test_stack_check.py:1725: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_l2f_read_pr_vet_state_unrecognised_state
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_l2f_read_pr_vet_state_lowercase_open_refuses
2 failed, 40 passed, 82 deselected in 0.16s
```

**raw green** after restore:
```
..........................................                               [100%]
42 passed, 82 deselected in 0.13s
```

**restored lines:**
```python
    if state not in PR_VET_STATE_VALUES:
        return None, _read_refusal(
            REASON_STACK_UNREADABLE,
            "state is not one of the enumerated values: %r" % state)
```

---

## G2 — fail-closed vet-verdict-form load (FIX-C)

**Guarded element:** `stack_check.py` `_load_vet_verdict_form` FileNotFoundError branch — must refuse `vet-unreadable`, never fall back to a built-in form.

**Axis:** missing form file refuses rather than silently using embedded defaults.

**Proving test:** `plugins/superheroes/lib/tests/test_stack_check.py::test_l2f_v30_vet_form_missing_refuses`

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
    except FileNotFoundError:
        _vet_verdict_form_error = "vet-verdict-form.json is missing"
        return None, _vet_verdict_form_error
```
→
```python
    except FileNotFoundError:
        _vet_verdict_form = (
            " · ",
            (
                ("**Verdict: READY**", VERDICT_READY),
                ("**Verdict: NOT-READY**", VERDICT_NOT_READY),
                ("**Verdict: PARKED**", VERDICT_PARKED),
            ),
        )
        return _vet_verdict_form, None
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_stack_check.py::test_l2f_v30_vet_form_missing_refuses -q
```

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
____________________ test_l2f_v30_vet_form_missing_refuses _____________________

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x106443370>

    def test_l2f_v30_vet_form_missing_refuses(monkeypatch):
        # axis: missing vet-verdict-form.json refuses vet-unreadable, never READY
        monkeypatch.setattr(sc, "_vet_verdict_form_path", lambda: "/nonexistent/vet-verdict-form.json")
        sc._reset_vet_verdict_form_cache()
>       _assert_vet_refusal(
            _vet_body("**Verdict: READY** · %s" % HEAD_SHA),
            HEAD_SHA,
            sc.REASON_VET_UNREADABLE,
        )

plugins/superheroes/lib/tests/test_stack_check.py:1565: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

body = '<!-- superheroes:advisor-vet -->\n**Verdict: READY** · abcdef0123456789abcdef0123456789abcdef01'
head_sha = 'abcdef0123456789abcdef0123456789abcdef01', reason = 'vet-unreadable'

    def _assert_vet_refusal(body, head_sha, reason):
        verdict, refusal = sc.read_vet_verdict(body, head_sha)
>       assert verdict is None
E       AssertionError: assert 'READY' is None

plugins/superheroes/lib/tests/test_stack_check.py:1373: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_l2f_v30_vet_form_missing_refuses
1 failed in 0.11s
```

**raw green** after restore:
```
.                                                                        [100%]
1 passed in 0.09s
```

**restored lines:**
```python
    except FileNotFoundError:
        _vet_verdict_form_error = "vet-verdict-form.json is missing"
        return None, _vet_verdict_form_error
```

---

## G3 — unknown verdict vocabulary branch (FIX-C2)

**Guarded element:** `stack_check.py:122-126` — `if verdict not in expected_verdicts` in `_load_vet_verdict_form`.

**Axis:** an unknown verdict value in the loaded form refuses `vet-unreadable`.

**Proving test:** `plugins/superheroes/lib/tests/test_stack_check.py::test_l2f_v31_vet_form_unknown_verdict_refuses`

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
        if verdict not in expected_verdicts:
            _vet_verdict_form_error = (
                "vet-verdict-form.json verdict %r is not recognised" % verdict
            )
            return None, _vet_verdict_form_error
```
→ (deleted)

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_stack_check.py::test_l2f_v31_vet_form_unknown_verdict_refuses -q
```

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
________________ test_l2f_v31_vet_form_unknown_verdict_refuses ___________________

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x106914e80>
tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-3662/test_l2f_v31_vet_form_unknown_0')

    def test_l2f_v31_vet_form_unknown_verdict_refuses(monkeypatch, tmp_path):
        # axis: unknown verdict value in the form refuses vet-unreadable
        tokens = list(_VALID_VET_FORM_TOKENS)
        tokens[0] = {"token": "**Verdict: READY**", "verdict": "SHIPPED"}
        _patch_vet_form(monkeypatch, tmp_path, tokens)
>       _assert_vet_refusal(
            _vet_body("**Verdict: READY** · %s" % HEAD_SHA),
            HEAD_SHA,
            sc.REASON_VET_UNREADABLE,
        )

plugins/superheroes/lib/tests/test_stack_check.py:1602: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

body = '<!-- superheroes:advisor-vet -->\n**Verdict: READY** · abcdef0123456789abcdef0123456789abcdef01'
head_sha = 'abcdef0123456789abcdef0123456789abcdef01', reason = 'vet-unreadable'

    def _assert_vet_refusal(body, head_sha, reason):
        verdict, refusal = sc.read_vet_verdict(body, head_sha)
>       assert verdict is None
E       AssertionError: assert 'SHIPPED' is None

plugins/superheroes/lib/tests/test_stack_check.py:1373: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_l2f_v31_vet_form_unknown_verdict_refuses
1 failed in 0.11s
```

**raw green** after restore:
```
.                                                                        [100%]
1 passed in 0.09s
```

**restored lines:**
```python
        if verdict not in expected_verdicts:
            _vet_verdict_form_error = (
                "vet-verdict-form.json verdict %r is not recognised" % verdict
            )
            return None, _vet_verdict_form_error
```

---

## G4 — duplicate verdict vocabulary branch (FIX-C2)

**Guarded element:** `stack_check.py:127-131` — `if verdict in seen_verdicts` in `_load_vet_verdict_form`.

**Axis:** a duplicated verdict value in the loaded form refuses `vet-unreadable`.

**Proving test:** `plugins/superheroes/lib/tests/test_stack_check.py::test_l2f_v32_vet_form_duplicate_verdict_refuses`

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
        if verdict in seen_verdicts:
            _vet_verdict_form_error = (
                "vet-verdict-form.json verdict %r is duplicated" % verdict
            )
            return None, _vet_verdict_form_error
        seen_verdicts.add(verdict)
```
→
```python
        # duplicate-check neutralized for bite-proof
        seen_verdicts.add(verdict)
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_stack_check.py::test_l2f_v32_vet_form_duplicate_verdict_refuses -q
```

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_______________ test_l2f_v32_vet_form_duplicate_verdict_refuses ________________

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x105f5ea90>
tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-3677/test_l2f_v32_vet_form_duplicat0')

    def test_l2f_v32_vet_form_duplicate_verdict_refuses(monkeypatch, tmp_path):
        # axis: duplicated verdict value in the form refuses vet-unreadable
        tokens = list(_VALID_VET_FORM_TOKENS) + [
            {"token": "**Verdict: READY**", "verdict": sc.VERDICT_READY},
        ]
        _patch_vet_form(monkeypatch, tmp_path, tokens)
>       _assert_vet_refusal(
            _vet_body("**Verdict: READY** · %s" % HEAD_SHA),
            HEAD_SHA,
            sc.REASON_VET_UNREADABLE,
        )

plugins/superheroes/lib/tests/test_stack_check.py:1615: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

body = '<!-- superheroes:advisor-vet -->\n**Verdict: READY** · abcdef0123456789abcdef0123456789abcdef01'
head_sha = 'abcdef0123456789abcdef0123456789abcdef01', reason = 'vet-unreadable'

    def _assert_vet_refusal(body, head_sha, reason):
        verdict, refusal = sc.read_vet_verdict(body, head_sha)
>       assert verdict is None
E       AssertionError: assert 'READY' is None

plugins/superheroes/lib/tests/test_stack_check.py:1373: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_l2f_v32_vet_form_duplicate_verdict_refuses
1 failed in 0.20s
```

**raw green** after restore:
```
.                                                                        [100%]
1 passed in 0.15s
```

**restored lines:**
```python
        if verdict in seen_verdicts:
            _vet_verdict_form_error = (
                "vet-verdict-form.json verdict %r is duplicated" % verdict
            )
            return None, _vet_verdict_form_error
        seen_verdicts.add(verdict)
```

---

## G5 — missing verdict vocabulary branch (FIX-C2)

**Guarded element:** `stack_check.py:133-138` — `if seen_verdicts != expected_verdicts` in `_load_vet_verdict_form`.

**Axis:** a missing member of the verdict vocabulary in the loaded form refuses `vet-unreadable`.

**Proving test:** `plugins/superheroes/lib/tests/test_stack_check.py::test_l2f_v33_vet_form_missing_verdict_refuses`

**neutralization** (`plugins/superheroes/lib/stack_check.py`):
```python
    if seen_verdicts != expected_verdicts:
        for missing in expected_verdicts - seen_verdicts:
            _vet_verdict_form_error = (
                "vet-verdict-form.json verdict %r is missing" % missing
            )
            return None, _vet_verdict_form_error
```
→ (deleted)

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_stack_check.py::test_l2f_v33_vet_form_missing_verdict_refuses -q
```

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
________________ test_l2f_v33_vet_form_missing_verdict_refuses _________________

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x10435af10>
tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-3670/test_l2f_v33_vet_form_missing_0')

    def test_l2f_v33_vet_form_missing_verdict_refuses(monkeypatch, tmp_path):
        # axis: missing member of the verdict vocabulary refuses vet-unreadable
        tokens = _VALID_VET_FORM_TOKENS[:2]
        _patch_vet_form(monkeypatch, tmp_path, tokens)
>       _assert_vet_refusal(
            _vet_body("**Verdict: READY** · %s" % HEAD_SHA),
            HEAD_SHA,
            sc.REASON_VET_UNREADABLE,
        )

plugins/superheroes/lib/tests/test_stack_check.py:1625: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

body = '<!-- superheroes:advisor-vet -->\n**Verdict: READY** · abcdef0123456789abcdef0123456789abcdef01'
head_sha = 'abcdef0123456789abcdef0123456789abcdef01', reason = 'vet-unreadable'

    def _assert_vet_refusal(body, head_sha, reason):
        verdict, refusal = sc.read_vet_verdict(body, head_sha)
>       assert verdict is None
E       AssertionError: assert 'READY' is None

plugins/superheroes/lib/tests/test_stack_check.py:1373: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_l2f_v33_vet_form_missing_verdict_refuses
1 failed in 0.13s
```

**raw green** after restore:
```
.                                                                        [100%]
1 passed in 0.10s
```

**restored lines:**
```python
    if seen_verdicts != expected_verdicts:
        for missing in expected_verdicts - seen_verdicts:
            _vet_verdict_form_error = (
                "vet-verdict-form.json verdict %r is missing" % missing
            )
            return None, _vet_verdict_form_error
```

---

## Restore receipt

Bite-proof neutralizations applied and reverted by inverse edit in the FIX-D worktree.

**`git status --porcelain` after restore:**
```
 M plugins/superheroes/TRANSITION.md
 M plugins/superheroes/lib/tests/bite_proofs/wo_1340_l2f_r2_state_allowlist.md
```
