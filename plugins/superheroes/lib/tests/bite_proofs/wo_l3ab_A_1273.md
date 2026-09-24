# WO-L3AB-A (#1273) bite-proof — result completion contract seam

**Provenance:** cursor / composer-2.5 (implementer).

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-A1 | `completion_window` step 1 | missing/unusable completion stamp → `result-completion-unrecorded` | `test_completion_window_empty_dict_forfeits_unrecorded` |
| BP-A2 | `completion_window` step 2 | payload digest mismatch → `result-completion-payload-mismatch` | `test_completion_window_bad_payload_sha256_forfeits_mismatch` |
| BP-A3 | `completion_window` step 5 | completion after deadline → `result-completion-after-deadline` | `test_completion_window_after_deadline_forfeits` |
| BP-A4 | `completion_window` step 4 epoch leg | deadline epoch differs from completion epoch → `result-completion-unrecorded` | `test_completion_window_epoch_mismatch_forfeits_unrecorded` |

---

## BP-A1 — result-completion-unrecorded

- **axis:** missing or unusable completion stamp forfeits before admission

**neutralization** (`plugins/superheroes/lib/engine_result_channel.py`, `completion_window`):
```python
    if isinstance(complete_at, bool) or not isinstance(complete_at, (int, float)):
        return ("admit", None)  # bite-proof BP-A1 neutralization
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_result_channel.py::test_completion_window_empty_dict_forfeits_unrecorded -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_completion_window_empty_dict_forfeits_unrecorded _____________

    def test_completion_window_empty_dict_forfeits_unrecorded():
>       assert ERC.completion_window({}, _DIGEST_X) == (
            "forfeit", ERC.REFUSAL_RESULT_COMPLETION_UNRECORDED,
        )
E       AssertionError: assert ('admit', None) == ('forfeit', '...n-unrecorded')
E         
E         At index 0 diff: 'admit' != 'forfeit'
E         Use -v to get more diff

plugins/superheroes/lib/tests/test_engine_result_channel.py:923: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_result_channel.py::test_completion_window_empty_dict_forfeits_unrecorded
1 failed in 0.32s
```

**restore** (`plugins/superheroes/lib/engine_result_channel.py`, `completion_window`):
```python
    if isinstance(complete_at, bool) or not isinstance(complete_at, (int, float)):
        return ("forfeit", REFUSAL_RESULT_COMPLETION_UNRECORDED)
```

**restore receipt:** post-restore `git status --porcelain` shows only expected worktree edits (`M` on the two order files).

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.27s
```

---

## BP-A2 — result-completion-payload-mismatch

- **axis:** admitted bytes digest must match recorded completion digest

**neutralization** (`plugins/superheroes/lib/engine_result_channel.py`, `completion_window`):
```python
    if not _is_valid_sha256_hex(payload_sha256):
        return ("admit", None)  # bite-proof BP-A2 neutralization
    if not hmac.compare_digest(payload_sha256, recorded_digest):
        return ("admit", None)  # bite-proof BP-A2 neutralization
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest 'plugins/superheroes/lib/tests/test_engine_result_channel.py::test_completion_window_bad_payload_sha256_forfeits_mismatch[None]' -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
______ test_completion_window_bad_payload_sha256_forfeits_mismatch[None] _______

bad_payload = None

    @pytest.mark.parametrize("bad_payload", [
        None,
        "",
        "A" * 64,
        "a" * 63,
    ])
    def test_completion_window_bad_payload_sha256_forfeits_mismatch(bad_payload):
        ended = _completion_record(10.0)
>       assert ERC.completion_window(ended, bad_payload) == (
            "forfeit", ERC.REFUSAL_RESULT_COMPLETION_PAYLOAD_MISMATCH,
        )
E       AssertionError: assert ('admit', None) == ('forfeit', '...oad-mismatch')
E         
E         At index 0 diff: 'admit' != 'forfeit'
E         Use -v to get more diff

plugins/superheroes/lib/tests/test_engine_result_channel.py:988: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_result_channel.py::test_completion_window_bad_payload_sha256_forfeits_mismatch[None]
1 failed in 0.27s
```

**restore** (`plugins/superheroes/lib/engine_result_channel.py`, `completion_window`):
```python
    if not _is_valid_sha256_hex(payload_sha256):
        return ("forfeit", REFUSAL_RESULT_COMPLETION_PAYLOAD_MISMATCH)
    if not hmac.compare_digest(payload_sha256, recorded_digest):
        return ("forfeit", REFUSAL_RESULT_COMPLETION_PAYLOAD_MISMATCH)
```

**restore receipt:** inverse edit applied; production branch restored.

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.25s
```

---

## BP-A3 — result-completion-after-deadline

- **axis:** completion instant strictly after deadline mono cap forfeits

**neutralization** (`plugins/superheroes/lib/engine_result_channel.py`, `completion_window`):
```python
    return ("admit", None)  # bite-proof BP-A3 neutralization
```
(replaces the final `return ("forfeit", REFUSAL_RESULT_COMPLETION_AFTER_DEADLINE)`)

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_result_channel.py::test_completion_window_after_deadline_forfeits -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
________________ test_completion_window_after_deadline_forfeits ________________

    def test_completion_window_after_deadline_forfeits():
        ended = _completion_record(25.0)
        ended.update(ERC.deadline_stamp(20.0))
>       assert ERC.completion_window(ended, _DIGEST_X) == (
            "forfeit", ERC.REFUSAL_RESULT_COMPLETION_AFTER_DEADLINE,
        )
E       AssertionError: assert ('admit', None) == ('forfeit', '...ter-deadline')
E         
E         At index 0 diff: 'admit' != 'forfeit'
E         Use -v to get more diff

plugins/superheroes/lib/tests/test_engine_result_channel.py:1007: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_result_channel.py::test_completion_window_after_deadline_forfeits
1 failed in 0.27s
```

**restore** (`plugins/superheroes/lib/engine_result_channel.py`, `completion_window`):
```python
    return ("forfeit", REFUSAL_RESULT_COMPLETION_AFTER_DEADLINE)
```

**restore receipt:** inverse edit applied; production branch restored.

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.25s
```

---

## BP-A4 — epoch-mismatch leg of step 4

- **axis:** deadline epoch must match completion epoch or forfeit as unrecorded

**neutralization** (`plugins/superheroes/lib/engine_result_channel.py`, `completion_window`):
```python
    if (
        not isinstance(deadline_epoch, str)
        or not deadline_epoch
        or deadline_epoch != complete_epoch
    ):
        return ("admit", None)  # bite-proof BP-A4 neutralization
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_result_channel.py::test_completion_window_epoch_mismatch_forfeits_unrecorded -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_completion_window_epoch_mismatch_forfeits_unrecorded ___________

    def test_completion_window_epoch_mismatch_forfeits_unrecorded():
        ended = _completion_record(10.0)
        ended.update(ERC.deadline_stamp(20.0))
        ended[ERC.FIELD_DEADLINE_EPOCH] = ended[ERC.FIELD_DEADLINE_EPOCH] + "-other"
>       assert ERC.completion_window(ended, _DIGEST_X) == (
            "forfeit", ERC.REFUSAL_RESULT_COMPLETION_UNRECORDED,
        )
E       AssertionError: assert ('admit', None) == ('forfeit', '...n-unrecorded')
E         
E         At index 0 diff: 'admit' != 'forfeit'
E         Use -v to get more diff

plugins/superheroes/lib/tests/test_engine_result_channel.py:940: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_result_channel.py::test_completion_window_epoch_mismatch_forfeits_unrecorded
1 failed in 0.26s
```

**restore** (`plugins/superheroes/lib/engine_result_channel.py`, `completion_window`):
```python
    if (
        not isinstance(deadline_epoch, str)
        or not deadline_epoch
        or deadline_epoch != complete_epoch
    ):
        return ("forfeit", REFUSAL_RESULT_COMPLETION_UNRECORDED)
```

**restore receipt:** inverse edit applied; production branch restored.

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.25s
```
