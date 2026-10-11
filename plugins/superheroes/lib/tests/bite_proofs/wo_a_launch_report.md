# Launch report WO-A bite-proof: the "Still on your machine" state's clearing legs

Bite-proof record for `plugins/superheroes/lib/launch_report.py` (G12, G13, G14), detectors in `plugins/superheroes/lib/tests/test_launch_report.py` (`TLR`). Every red, restore and green below was run in this dispatch on the worktree head, against `launch_report.py` and `test_launch_report.py`.

- **Run command.** `scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc-wo1 -m pytest -p no:cacheprovider -q "<T>::<node>"`.
- **Pinned condition.** `TLR` builds its stores, repositories, account files and records under `tmp_path`; the clock is a fixed `today` (`2026-10-11`) and readiness is injected. The pin makes unobservable: the real home directory, the process environment, the network and the real wall clock.

## Declared guarded-element set

G12 the still state's reported-fact clearing leg is a strictly later day.
G13 the still state's reported-fact clearing leg also requires the reader to read `ready` now.
G14 a build that went to the cloud clears the stored reason even when a local not-ready fallback sits beside it in the same batch.

## Per-element receipts

### G12: the reported-fact leg clears only on a strictly later day. Axis: boundary (>)

- **Neutralization applied.** In `launch_report._fixed`, `datetime.date.fromisoformat(checked) > datetime.date.fromisoformat(state["observedOn"])` replaced with `>=`.
- **Node.** `TLR::test_R_still_leg_d_a_reported_fact_clears_only_on_a_strictly_later_check`
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_R_still_leg_d_a_reported_fact_clears_only_on_a_strictly_later_check ___

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1213/test_R_still_leg_d_a_reported_0')

    def test_R_still_leg_d_a_reported_fact_clears_only_on_a_strictly_later_check(tmp_path):
        cases = [("no-pass", {"noPass": True}), ("unreachable", {"unreachable": True}),
                 ("version", {"pluginVersion": "0.41.0"})]
        for index, (code, reported) in enumerate(cases):
            repo, store = _still_with(_sub(tmp_path, str(index)), _call(reason=code, cloud="0.41.0", advisor="0.42.0",
                                                  reported=reported))
            ready = _now(ready=True)
            for checked in (None, "2026-10-10", "2026-10-11", "garbage"):
>               assert LR.still_line(repo, root=store, today=TODAY, readiness_fn=lambda *a, **k: dict(
                    ready, checkedAt=checked)) is not None, (code, checked)
E               AssertionError: ('no-pass', '2026-10-11')
E               assert None is not None
E                +  where None = <function still_line at 0x1077b6c00>('/private/tmp/claude-501/pytest-of-zwrose/pytest-1213/test_R_still_leg_d_a_reported_0/0/repo', root='/private/tmp/claude-501/pytest-of-zwrose/pytest-1213/test_R_still_leg_d_a_reported_0/0/store', today=datetime.date(2026, 10, 11), readiness_fn=<function test_R_still_leg_d_a_reported_fact_clears_only_on_a_strictly_later_check.<locals>.<lambda> at 0x10774f880>)
E                +    where <function still_line at 0x1077b6c00> = LR.still_line

/private/tmp/claude-501/-Users-zwrose--superheroes-worktrees-superheroes-issue-1775-73b0797ad1a5d29e/ba0c6594-07fc-485e-832d-f24f80bb0f89/scratchpad/wo1/plugins/superheroes/lib/tests/test_launch_report.py:496: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launch_report.py::test_R_still_leg_d_a_reported_fact_clears_only_on_a_strictly_later_check
1 failed in 13.92s
```

- **Restore.** The inverse Edit; quoted from `launch_report.py:217`: `        later = datetime.date.fromisoformat(checked) > datetime.date.fromisoformat(state["observedOn"])`.
- **Green:**

```
.                                                                        [100%]
1 passed in 7.15s
```

### G13: the reported-fact leg clears only when the reader reads ready now. Axis: conjunct (ready)

- **Neutralization applied.** In `launch_report._fixed`, `return later and now.get("ready") is True` replaced with `return later and True`.
- **Node.** `TLR::test_R_still_a_reported_fact_needs_the_reader_ready_as_well_as_a_later_check`
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_R_still_a_reported_fact_needs_the_reader_ready_as_well_as_a_later_check _

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1215/test_R_still_a_reported_fact_n0')

    def test_R_still_a_reported_fact_needs_the_reader_ready_as_well_as_a_later_check(tmp_path):
        repo, store = _still_with(tmp_path, _call(reason="version", cloud="0.41.0", advisor="0.42.0",
                                                  reported={"pluginVersion": "0.41.0"}))
        not_ready = _now(ready=False, reason="version", checked="2026-10-12")
        assert not_ready["conditions"]["version"] is False
>       assert LR.still_line(repo, root=store, today=TODAY,
                             readiness_fn=lambda *a, **k: dict(not_ready)) is not None
E       AssertionError: assert None is not None
E        +  where None = <function still_line at 0x10906ec00>('/private/tmp/claude-501/pytest-of-zwrose/pytest-1215/test_R_still_a_reported_fact_n0/repo', root='/private/tmp/claude-501/pytest-of-zwrose/pytest-1215/test_R_still_a_reported_fact_n0/store', today=datetime.date(2026, 10, 11), readiness_fn=<function test_R_still_a_reported_fact_needs_the_reader_ready_as_well_as_a_later_check.<locals>.<lambda> at 0x108fff880>)
E        +    where <function still_line at 0x10906ec00> = LR.still_line

/private/tmp/claude-501/-Users-zwrose--superheroes-worktrees-superheroes-issue-1775-73b0797ad1a5d29e/ba0c6594-07fc-485e-832d-f24f80bb0f89/scratchpad/wo1/plugins/superheroes/lib/tests/test_launch_report.py:647: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launch_report.py::test_R_still_a_reported_fact_needs_the_reader_ready_as_well_as_a_later_check
1 failed in 2.54s
```

- **Restore.** The inverse Edit; quoted from `launch_report.py:219`: `        return later and now.get("ready") is True`.
- **Green:**

```
.                                                                        [100%]
1 passed in 3.85s
```

### G14: a cloud build clears the stored reason even beside a local not-ready fallback. Axis: ordering (cloud check before the stuck/write branch)

- **Neutralization applied.** In `launch_report.record_still`, the `if any(c.get("place") == "cloud" ...)` clear branch moved after the `if stuck:` write branch (the old order).
- **Node.** `TLR::test_record_still_clears_when_a_cloud_build_sits_beside_a_local_not_ready_fallback`
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_record_still_clears_when_a_cloud_build_sits_beside_a_local_not_ready_fallback _

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1217/test_record_still_clears_when_0')

    def test_record_still_clears_when_a_cloud_build_sits_beside_a_local_not_ready_fallback(tmp_path):
        repo, store = _gitdir(tmp_path)
        mixed = [_call(reason="version", cloud="0.41.0", advisor="0.42.0"), _call("cloud")]
        LR.record_still(repo, [_call(reason="no-setup")], root=store, today=TODAY)
>       assert LR.record_still(repo, mixed, root=store, today=TODAY) == {
            "action": "cleared", "reason": None}
E       AssertionError: assert {'action': 'w...n': 'version'} == {'action': 'c...reason': None}
E         
E         Differing items:
E         {'reason': 'version'} != {'reason': None}
E         {'action': 'written'} != {'action': 'cleared'}
E         Use -v to get more diff

/private/tmp/claude-501/-Users-zwrose--superheroes-worktrees-superheroes-issue-1775-73b0797ad1a5d29e/ba0c6594-07fc-485e-832d-f24f80bb0f89/scratchpad/wo1/plugins/superheroes/lib/tests/test_launch_report.py:634: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launch_report.py::test_record_still_clears_when_a_cloud_build_sits_beside_a_local_not_ready_fallback
1 failed in 3.09s
```

- **Restore.** The inverse Edit; the cloud branch is back first in `record_still`, quoted from `launch_report.py:153-155`:

```
        if any(c.get("place") == "cloud" for c in place_calls):
            # axis: a build that went to the cloud clears the stored reason even beside a local not-ready fallback — see bite-proof record wo_a_launch_report
            return {"action": _remove(path)["action"], "reason": None}
```

- **Green:**

```
.                                                                        [100%]
1 passed in 3.47s
```
