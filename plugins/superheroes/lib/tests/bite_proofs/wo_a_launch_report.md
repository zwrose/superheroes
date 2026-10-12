# Launch report WO-A bite-proof: the "Still on your machine" state's clearing legs

Bite-proof record for `plugins/superheroes/lib/launch_report.py` (G12, G13, G14, G15, G16, G17), detectors in `plugins/superheroes/lib/tests/test_launch_report.py` (`TLR`) and `plugins/superheroes/lib/tests/test_launch_report_verbs.py` (`TLV`); G15 and G17 neutralize `plugins/superheroes/lib/launcher.py`. Every red, restore and green below was run in this dispatch on the worktree head, against `launch_report.py` and `test_launch_report.py`.

- **Run command.** `scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc-wo1 -m pytest -p no:cacheprovider -q "<T>::<node>"`.
- **Pinned condition.** `TLR` builds its stores, repositories, account files and records under `tmp_path`; the clock is a fixed `today` (`2026-10-11`) and readiness is injected. The pin makes unobservable: the real home directory, the process environment, the network and the real wall clock.

## Declared guarded-element set

G12 the still state's reported-fact clearing leg is a strictly later day.
G13 the still state's reported-fact clearing leg also requires the reader to read `ready` now.
G14 a build that went to the cloud clears the stored reason even when a local not-ready fallback sits beside it in the same batch.
G15 the launch report orders issues by their first reservation, not their last.
G16 with no stored still state, the readiness function is never called.
G17 the reminder replays every batch's launches.

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

### G15: issues are ordered by first reservation. Axis: ordering (sort key)

- **Neutralization applied.** In `launcher.launch_report_for_batch`, the sort key `first_index[i]` replaced with `last_started[i][1]["reservedIndex"]`.
- **Node.** `TLV::test_I1_the_issue_order_is_its_first_reservation_not_its_last`
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
________ test_I1_the_issue_order_is_its_first_reservation_not_its_last _________

world = ('/private/tmp/claude-501/pytest-of-zwrose/pytest-1312/test_I1_the_issue_order_is_its0/repo', '/private/tmp/claude-501/pytest-of-zwrose/pytest-1312/test_I1_the_issue_order_is_its0/store')

    def test_I1_the_issue_order_is_its_first_reservation_not_its_last(world):
        repo, _store = world
        _launch(repo, "c1", 44, "cloud")
        _finish(repo, "c1")
        _launch(repo, "m1", 55, "local", _call(reason="needs", need=PHONE))
        _launch(repo, "l1", 44, "local", _call(reason="needs", need=PHONE))
        _folds(repo)
        got = _report(repo)
        assert got["lanes"] == 2
        # both issues land under "On your machine", so their relative order is observed: first reservation
        # puts 44 ahead of 55, last reservation would put 55 ahead of 44
        lines = got["report"].splitlines()
        assert lines[1] == "On your machine:"
>       assert lines[2].startswith("- #44 ") and lines[3].startswith("- #55 ")
E       AssertionError: assert (False)
E        +  where False = <built-in method startswith of str object at 0x105ce4130>('- #44 ')
E        +    where <built-in method startswith of str object at 0x105ce4130> = '- #55 Title 55. It needs the phone simulator, which only your machine has.'.startswith

plugins/superheroes/lib/tests/test_launch_report_verbs.py:168: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launch_report_verbs.py::test_I1_the_issue_order_is_its_first_reservation_not_its_last
1 failed in 5.81s
```

- **Restore.** The inverse Edit; quoted from `launcher.py:3311`: `    for issue in sorted(last_started, key=lambda i: first_index[i]):`.
- **Green:**

```
.                                                                        [100%]
1 passed in 12.75s
```

### G16: with no stored still state, the readiness function is never called. Axis: ordering (readiness read before the no-state return)

- **Neutralization applied.** In `launch_report.still_line`, a call `(readiness_fn or cloud_ready.readiness)(cwd, reported=None, root=root)` inserted before the `if state is None:` line.
- **Node.** `TLR::test_R_still_no_state_means_no_line`
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________________ test_R_still_no_state_means_no_line ______________________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1314/test_R_still_no_state_means_no0')

    def test_R_still_no_state_means_no_line(tmp_path):
        repo, store = _gitdir(tmp_path)
    
        asked = []
    
        def record_the_ask(*args, **kwargs):
            asked.append((args, kwargs))
            return _now()
    
        # still_line swallows an exception from the readiness read, so the callback records, not raises
        assert LR.still_line(repo, root=store, readiness_fn=record_the_ask) is None
>       assert asked == []
E       AssertionError: assert [(('/private/..._no0/store'})] == []
E         
E         Left contains one more item: (('/private/tmp/claude-501/pytest-of-zwrose/pytest-1314/test_R_still_no_state_means_no0/repo',), {'reported': None, 'root': '/private/tmp/claude-501/pytest-of-zwrose/pytest-1314/test_R_still_no_state_means_no0/store'})
E         Use -v to get more diff

plugins/superheroes/lib/tests/test_launch_report.py:471: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launch_report.py::test_R_still_no_state_means_no_line
1 failed in 2.90s
```

- **Restore.** The inverse Edit; quoted from `launch_report.py:256-258`:

```
        state = _read_still(path)
        if state is None:
            return None
```

- **Green:**

```
.                                                                        [100%]
1 passed in 1.75s
```

### G17: the reminder replays every batch's launches. Axis: scope (all launches in the ledger, not the reported batch's)

- **Neutralization applied.** At the one call site in `launch_report_for_batch`, `_record_batch_still` was passed `{lid: info for lid, info in folded["launches"].items() if info.get("batchId") == batch_id}` instead of `folded["launches"]`.
- **Node.** `TLV::test_reporting_an_older_batch_first_still_records_a_newer_batchs_launch`
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_reporting_an_older_batch_first_still_records_a_newer_batchs_launch ____

world = ('/private/tmp/claude-501/pytest-of-zwrose/pytest-1350/test_reporting_an_older_batch_0/repo', '/private/tmp/claude-501/pytest-of-zwrose/pytest-1350/test_reporting_an_older_batch_0/store')

    def test_reporting_an_older_batch_first_still_records_a_newer_batchs_launch(world):
        repo, store = world
        assert _declare(repo, "b-newer", 4)["ok"]
        _launch(repo, "a", 11, "local", _call(reason="unreachable"))
        _reserve(repo, "b", 22, "local", {"placeCall": _call(reason="no-setup")}, batch="b-newer")
        _start(repo, "b")
        # the newer batch has not reported; "no-setup" outranks "unreachable", so only its launch can supply it
>       assert _report(repo)["still"] == {"action": "written", "reason": "no-setup"}
E       AssertionError: assert {'action': 'w...'unreachable'} == {'action': 'w...': 'no-setup'}
E         
E         Omitting 1 identical items, use -vv to show
E         Differing items:
E         {'reason': 'unreachable'} != {'reason': 'no-setup'}
E         Use -v to get more diff

plugins/superheroes/lib/tests/test_launch_report_verbs.py:412: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launch_report_verbs.py::test_reporting_an_older_batch_first_still_records_a_newer_batchs_launch
1 failed in 7.42s
```

- **Restore.** The inverse Edit; quoted from `launcher.py:3411-3412`:

```
        "still": _record_batch_still(
            repo_root, folded["launches"], reserved, _started_indexes(read["records"])),
```

- **Green:**

```
.                                                                        [100%]
1 passed in 8.60s
```
