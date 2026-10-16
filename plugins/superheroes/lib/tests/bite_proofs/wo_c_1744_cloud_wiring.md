# #1744 WO-C bite-proof: the stamp view and the confirmation recorder

Bite-proof record for the stamp view in `plugins/superheroes/lib/cloud_setup_text.py` (`_without_setting`, used by `stamped_files` and `compose`) and for `record_confirmation` in `plugins/superheroes/lib/cloud_pass.py`. Detectors: `plugins/superheroes/lib/tests/test_cloud_setup_text.py` (`TS`) and `plugins/superheroes/lib/tests/test_cloud_pass.py` (`TP`).

**Status.** The implementer ran every proof (C1 to C3): each neutralization is a targeted Edit, the red is the single named node run alone, the restore is the inverse Edit, and the green is the same node. Reds and greens below are the full pytest output of each run; absolute `tmp_path` prefixes and the worktree path are as printed. No fixture holds a real secret, so nothing is redacted.

- **Run command.** `scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest "<file>::<node>" -q`.
- **Restore receipt, every element.** The restored line is quoted back, and a search of the edited file for the neutralized text (`pass` as the only body of the `isinstance` branch, `if False`) found none.

## Declared guarded-element set

C1 the setting's removal from the stamp view; C2 the recorder's reviewer-answered check (R2); C3 the recorder's lapsed-date check (R4).

## Per-element receipts

### C1: the setting's removal from the stamp view. Axis: the stamp is the same with the setting absent, off and on

- **Neutralization applied.** In `_without_setting`, the line `settings.pop(project_config.CLOUD_BUILDS_SLUG, None)` replaced with `pass`, so the key is not removed.
- **Node.** `TS::test_toggling_the_setting_leaves_the_stamp_unchanged`
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_toggling_the_setting_leaves_the_stamp_unchanged _____________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-683/test_toggling_the_setting_leav0')

    def test_toggling_the_setting_leaves_the_stamp_unchanged(tmp_path):
        w = _outside(tmp_path)
        results = {state: _real(w, _core(state)) for state in ("absent", False, True)}
        stamps = {r["calibration"]["stamp"] for r in results.values()}
>       assert len(stamps) == 1 and STAMP_SHAPE.fullmatch(stamps.pop())
E       AssertionError: assert (3 == 1)
E        +  where 3 = len({'sha256:1e38ffd42054c4199cd5d61108c2fdd744da6c09bd792361d648f91a8052d68e', 'sha256:76f421eb5368c7d8ed8f04846e44b532cb0ebcf02e8f4fbdd7be851f56f6e5d0', 'sha256:ddbb78d93fd9a41a605b7b04f7ba9c9ccb77d5837eba274cc758997f1f1fd3d6'})

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1744-9d9043901276fccf/plugins/superheroes/lib/tests/test_cloud_setup_text.py:666: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_setup_text.py::test_toggling_the_setting_leaves_the_stamp_unchanged
1 failed in 1.14s
```

- **Restore.** The inverse Edit; quoted from `cloud_setup_text.py:219`: `            settings.pop(project_config.CLOUD_BUILDS_SLUG, None)`.
- **Green.**

```
.                                                                        [100%]
1 passed in 1.67s
```

### C2: the recorder's reviewer-answered check (R2). Axis: refusal to write (a confirmation the reviewer did not answer moves nothing)

- **Neutralization applied.** In `record_confirmation`, `if not confirmation["reviewerAnswered"]:` replaced with `if False:`, so the check is skipped.
- **Node.** `TP::test_record_confirmation_r2_reviewer_did_not_answer_moves_nothing`
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
______ test_record_confirmation_r2_reviewer_did_not_answer_moves_nothing _______

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-685/test_record_confirmation_r2_re0')

    def test_record_confirmation_r2_reviewer_did_not_answer_moves_nothing(tmp_path):
        result, before, after = _record(tmp_path, _confirmation(answered=False))
>       assert result == {"action": "noop", "reason": "reviewer-did-not-answer"}
E       AssertionError: assert {'action': 'written'} == {'action': 'n...d-not-answer'}
E         
E         Differing items:
E         {'action': 'written'} != {'action': 'noop'}
E         Right contains 1 more item:
E         {'reason': 'reviewer-did-not-answer'}
E         Use -v to get more diff

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1744-9d9043901276fccf/plugins/superheroes/lib/tests/test_cloud_pass.py:869: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_pass.py::test_record_confirmation_r2_reviewer_did_not_answer_moves_nothing
1 failed in 0.83s
```

- **Restore.** The inverse Edit; quoted from `cloud_pass.py:368`: `    if not confirmation["reviewerAnswered"]:`.
- **Green.**

```
.                                                                        [100%]
1 passed in 1.23s
```

### C3: the recorder's lapsed-date check (R4). Axis: refusal to write (a pass whose date is before today moves nothing)

- **Neutralization applied.** In `record_confirmation`, `if day < datetime.fromtimestamp(time.time() if now is None else now, timezone.utc).date():` replaced with `if False:`, so the check is skipped.
- **Node.** `TP::test_record_confirmation_r4_lapsed_date_moves_nothing`
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_record_confirmation_r4_lapsed_date_moves_nothing _____________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-687/test_record_confirmation_r4_la0')

    def test_record_confirmation_r4_lapsed_date_moves_nothing(tmp_path):
        result, before, after = _record(tmp_path, _confirmation(lapses="2027-01-14"))
>       assert result == {"action": "noop", "reason": "pass-lapsed"}
E       AssertionError: assert {'action': 'written'} == {'action': 'n...'pass-lapsed'}
E         
E         Differing items:
E         {'action': 'written'} != {'action': 'noop'}
E         Right contains 1 more item:
E         {'reason': 'pass-lapsed'}
E         Use -v to get more diff

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1744-9d9043901276fccf/plugins/superheroes/lib/tests/test_cloud_pass.py:891: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_pass.py::test_record_confirmation_r4_lapsed_date_moves_nothing
1 failed in 1.32s
```

- **Restore.** The inverse Edit; quoted from `cloud_pass.py:377`: `    if day < datetime.fromtimestamp(time.time() if now is None else now, timezone.utc).date():`.
- **Green.**

```
.                                                                        [100%]
1 passed in 1.05s
```
