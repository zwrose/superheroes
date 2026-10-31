# Launch report WO-A bite-proof: the "Still on your machine" line, read from the launch ledger

> Note (2026-10-31, #2296): owner-machine paths and the name of a consuming project in this record were replaced with neutral placeholders after capture; nothing else changed.

Bite-proof record for `plugins/superheroes/lib/launch_report.py` (G12, G13, G21, G22, G23, G24) and `plugins/superheroes/lib/launcher.py` (G15), detectors in `plugins/superheroes/lib/tests/test_launch_report_verbs.py` (`TLV`). Every red, restore and green below was run in the WO-8 dispatch on the worktree head `f0f362f37` plus that dispatch's changes, each as one pytest node.

- **Run command.** `scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc-wo8 -m pytest -p no:cacheprovider -q "<node>"`.
- **Pinned condition.** `TLV` builds its repository, ledger root and project store under `tmp_path`, and readiness is injected (`_fn`, or a lambda) and never read from a real home directory. The fixed start day `2026-10-11` (`DAY`) is written into the ledger's `ts` fields. The pin makes unobservable: the real home directory, the process environment, the network and the real wall clock.

## Declared guarded-element set

G12 the reported-fact clearing leg is a strictly later day than the launch's start day.
G13 the reported-fact clearing leg also requires the reader to read `ready` now.
G15 the launch report orders issues by their first reservation, not their last.
G21 one store: `report` and `still` write nothing and read no saved reminder.
G22 only the local fallbacks after the last confirmed cloud launch count.
G23 a fallback that reads fixed is skipped, so the next one still standing shows.
G24 an unconfirmed cloud launch does not clear the line.

## Per-element receipts

### G12: the reported-fact leg is a strictly later day. Axis: boundary (>)

- **Neutralization applied.** In `launch_report._fixed`, `datetime.date.fromisoformat(checked) > datetime.date.fromisoformat(observed)` replaced with `>=`.
- **Node.** `TLV::test_B6_a_reported_fact_clears_only_on_a_check_after_the_start_day_that_reads_ready[no-pass-reported0]` (B6's same-day case).
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_B6_a_reported_fact_clears_only_on_a_check_after_the_start_day_that_reads_ready[no-pass-reported0] _

world = ('/private/tmp/claude-501/pytest-of-zwrose/pytest-1371/test_B6_a_reported_fact_clears0/repo', '/private/tmp/claude-501/pytest-of-zwrose/pytest-1371/test_B6_a_reported_fact_clears0/store')
code = 'no-pass', reported = {'noPass': True}

    @pytest.mark.parametrize("code,reported", [
        ("no-pass", {"noPass": True}), ("unreachable", {"unreachable": True}),
        ("version", {"pluginVersion": "0.41.0"}),
    ])
    def test_B6_a_reported_fact_clears_only_on_a_check_after_the_start_day_that_reads_ready(
            world, code, reported):
        repo, _store = world
        _day_launch(repo, "a", 11, DAY, _call(reason=code, cloud="0.41.0", advisor="0.42.0",
                                              reported=reported))
        ready = _now(ready=True)
        for checked in (None, "garbage", "2026-10-10", "2026-10-11"):
>           assert LR.still_line(repo, readiness_fn=lambda *a, **k: dict(ready, checkedAt=checked)
                                 ) is not None, (code, checked)
E           AssertionError: ('no-pass', '2026-10-11')
E           assert None is not None
E            +  where None = <function still_line at 0x10b3dd760>('/private/tmp/claude-501/pytest-of-zwrose/pytest-1371/test_B6_a_reported_fact_clears0/repo', readiness_fn=<function test_B6_a_reported_fact_clears_only_on_a_check_after_the_start_day_that_reads_ready.<locals>.<lambda> at 0x10b797a60>)
E            +    where <function still_line at 0x10b3dd760> = LR.still_line

/path/to/home/.superheroes-worktrees/superheroes/issue-1775-73b0797ad1a5d29e/plugins/superheroes/lib/tests/test_launch_report_verbs.py:616: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launch_report_verbs.py::test_B6_a_reported_fact_clears_only_on_a_check_after_the_start_day_that_reads_ready[no-pass-reported0]
1 failed in 4.46s
```

- **Restore.** The inverse Edit; quoted from `launch_report.py:193`: `        later = datetime.date.fromisoformat(checked) > datetime.date.fromisoformat(observed)`.
- **Green:**

```
.                                                                        [100%]
1 passed in 5.75s
```

### G13: the reported-fact leg requires the reader to read ready now. Axis: conjunct (ready)

- **Neutralization applied.** In `launch_report._fixed`, `return later and now.get("ready") is True` replaced with `return later and True`.
- **Node.** `TLV::test_B6_a_reported_fact_clears_only_on_a_check_after_the_start_day_that_reads_ready[no-pass-reported0]` (B6's later-day, not-ready case).
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_B6_a_reported_fact_clears_only_on_a_check_after_the_start_day_that_reads_ready[no-pass-reported0] _

world = ('/private/tmp/claude-501/pytest-of-zwrose/pytest-1373/test_B6_a_reported_fact_clears0/repo', '/private/tmp/claude-501/pytest-of-zwrose/pytest-1373/test_B6_a_reported_fact_clears0/store')
code = 'no-pass', reported = {'noPass': True}

    @pytest.mark.parametrize("code,reported", [
        ("no-pass", {"noPass": True}), ("unreachable", {"unreachable": True}),
        ("version", {"pluginVersion": "0.41.0"}),
    ])
    def test_B6_a_reported_fact_clears_only_on_a_check_after_the_start_day_that_reads_ready(
            world, code, reported):
        repo, _store = world
        _day_launch(repo, "a", 11, DAY, _call(reason=code, cloud="0.41.0", advisor="0.42.0",
                                              reported=reported))
        ready = _now(ready=True)
        for checked in (None, "garbage", "2026-10-10", "2026-10-11"):
            assert LR.still_line(repo, readiness_fn=lambda *a, **k: dict(ready, checkedAt=checked)
                                 ) is not None, (code, checked)
        after = "2026-10-12"
        assert LR.still_line(repo, readiness_fn=lambda *a, **k: dict(ready, checkedAt=after)) is None
        not_ready = _now(ready=False, reason=code, checked=after)
>       assert LR.still_line(repo, readiness_fn=lambda *a, **k: dict(not_ready)) is not None
E       AssertionError: assert None is not None
E        +  where None = <function still_line at 0x109a5d760>('/private/tmp/claude-501/pytest-of-zwrose/pytest-1373/test_B6_a_reported_fact_clears0/repo', readiness_fn=<function test_B6_a_reported_fact_clears_only_on_a_check_after_the_start_day_that_reads_ready.<locals>.<lambda> at 0x10957ba60>)
E        +    where <function still_line at 0x109a5d760> = LR.still_line

/path/to/home/.superheroes-worktrees/superheroes/issue-1775-73b0797ad1a5d29e/plugins/superheroes/lib/tests/test_launch_report_verbs.py:621: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launch_report_verbs.py::test_B6_a_reported_fact_clears_only_on_a_check_after_the_start_day_that_reads_ready[no-pass-reported0]
1 failed in 5.53s
```

- **Restore.** The inverse Edit; quoted from `launch_report.py:195`: `        return later and now.get("ready") is True`.
- **Green:**

```
.                                                                        [100%]
1 passed in 4.63s
```

### G15: the report orders issues by their first reservation. Axis: ordering key

- **Neutralization applied.** In `launcher.launch_report_for_batch`, the sort key in `sorted(last_started, key=lambda i: first_index[i])` replaced with `last_started[i][1]["reservedIndex"]`.
- **Node.** `TLV::test_I1_the_issue_order_is_its_first_reservation_not_its_last`
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
________ test_I1_the_issue_order_is_its_first_reservation_not_its_last _________

world = ('/private/tmp/claude-501/pytest-of-zwrose/pytest-1375/test_I1_the_issue_order_is_its0/repo', '/private/tmp/claude-501/pytest-of-zwrose/pytest-1375/test_I1_the_issue_order_is_its0/store')

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
E        +  where False = <built-in method startswith of str object at 0x10d3f3530>('- #44 ')
E        +    where <built-in method startswith of str object at 0x10d3f3530> = '- #55 Title 55. It needs the phone simulator, which only your machine has.'.startswith

/path/to/home/.superheroes-worktrees/superheroes/issue-1775-73b0797ad1a5d29e/plugins/superheroes/lib/tests/test_launch_report_verbs.py:218: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launch_report_verbs.py::test_I1_the_issue_order_is_its_first_reservation_not_its_last
1 failed in 6.53s
```

- **Restore.** The inverse Edit; quoted from `launcher.py:3347`: `    for issue in sorted(last_started, key=lambda i: first_index[i]):`.
- **Green:**

```
.                                                                        [100%]
1 passed in 6.21s
```

### G21: one store. Axis: persistence (no write)

- **Neutralization applied.** In `launch_report.still_check`, as the first line inside the `try:`, added `open(os.path.join(__import__("mode_registry").project_store_dir(cwd, root), "state", "scratch.json"), "w").write("x")`.
- **Node.** `TLV::test_B10_one_store_report_and_still_write_nothing`
- **Red** (the capture was passed through `cut -c1-600`; no line in it is cut):

```
F                                                                        [100%]
=================================== FAILURES ===================================
______________ test_B10_one_store_report_and_still_write_nothing _______________

world = ('/private/tmp/claude-501/pytest-of-zwrose/pytest-1377/test_B10_one_store_report_and_0/repo', '/private/tmp/claude-501/pytest-of-zwrose/pytest-1377/test_B10_one_store_report_and_0/store')

    def test_B10_one_store_report_and_still_write_nothing(world):
        repo, _store = world
        state = os.path.join(mode_registry.project_store_dir(repo, None), "state")
        os.makedirs(state)
        with open(os.path.join(state, "stale-reminder.json"), "wb") as fh:
            fh.write(b"left behind by an older build")
        _launch(repo, "a", 11, "local", _call(reason="no-setup"))
        _launch(repo, "b", 22, "local", _call(reason="unreachable"))
        before = _snapshot(mode_registry.project_store_dir(repo, None), repo)
        assert _report(repo)["report"] is not None
        got = LR.still_check(repo, readiness_fn=_fn(ready=False, reason="no-setup"))
        assert got["line"].startswith("Still on your machine\n") and got["refused"] is None
>       assert _snapshot(mode_registry.project_store_dir(repo, None), repo) == before
E       AssertionError: assert {'/private/tm...t': None, ...} == {'/private/tm...: b'x\n', ...}
E         
E         Omitting 44 identical items, use -vv to show
E         Left contains 1 more item:
E         {'/private/tmp/claude-501/pytest-of-zwrose/pytest-1377/test_B10_one_store_report_and_0/store/projects/150aa8a113e50614/state/scratch.json': b'x'}
E         Use -v to get more diff

/path/to/home/.superheroes-worktrees/superheroes/issue-1775-73b0797ad1a5d29e/plugins/superheroes/lib/tests/test_launch_report_verbs.py:408: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launch_report_verbs.py::test_B10_one_store_report_and_still_write_nothing
1 failed in 5.60s
```

- **Restore.** The inverse Edit; quoted from `launch_report.py:254-255`: `    try:` then `        read = ll.read(cwd)`. A grep for `scratch` and `__import__` in the file found nothing after the restore.
- **Green:**

```
.                                                                        [100%]
1 passed in 5.02s
```

### G22: only the fallbacks after the last confirmed cloud launch count. Axis: ordering (cut at the last cloud launch)

- **Neutralization applied.** In `launch_report._fallbacks`, `deciding[last_cloud + 1:]` replaced with `deciding if call.get("place") != ll.PLACE_CLOUD`, so the cloud launch is ignored and every fallback counts.
- **Node.** `TLV::test_B3_a_confirmed_cloud_launch_after_a_fallback_clears_the_line`
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
______ test_B3_a_confirmed_cloud_launch_after_a_fallback_clears_the_line _______

world = ('/private/tmp/claude-501/pytest-of-zwrose/pytest-1379/test_B3_a_confirmed_cloud_laun0/repo', '/private/tmp/claude-501/pytest-of-zwrose/pytest-1379/test_B3_a_confirmed_cloud_laun0/store')

    def test_B3_a_confirmed_cloud_launch_after_a_fallback_clears_the_line(world):
        repo, _store = world
        _launch(repo, "a", 11, "local", _call(reason="no-setup"))
        assert _line(repo, ready=False, reason="no-setup") is not None
        _launch(repo, "b", 22, "cloud")
>       assert _line(repo, ready=False, reason="no-setup") is None
E       assert 'Still on your machine\nThis project has no cloud setup on this Claude account. Say "set up cloud builds" to fix it.' is None
E        +  where 'Still on your machine\nThis project has no cloud setup on this Claude account. Say "set up cloud builds" to fix it.' = _line('/private/tmp/claude-501/pytest-of-zwrose/pytest-1379/test_B3_a_confirmed_cloud_laun0/repo', ready=False, reason='no-setup')

/path/to/home/.superheroes-worktrees/superheroes/issue-1775-73b0797ad1a5d29e/plugins/superheroes/lib/tests/test_launch_report_verbs.py:479: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launch_report_verbs.py::test_B3_a_confirmed_cloud_launch_after_a_fallback_clears_the_line
1 failed in 7.03s
```

- **Restore.** The inverse Edit; quoted from `launch_report.py:237`: `    return [_candidate(call, info) for _pos, call, info in deciding[last_cloud + 1:]]`.
- **Green:**

```
.                                                                        [100%]
1 passed in 5.85s
```

### G23: a fixed candidate is skipped. Axis: filter (the `_fixed` test)

- **Neutralization applied.** In `launch_report.still_check`, `standing = [c for c in candidates if not _still_fixed(c, now, cwd, root)]` replaced with `standing = list(candidates)`, so the best-ranked candidate shows even when fixed.
- **Node.** `TLV::test_B7_a_higher_ranked_fallback_that_is_fixed_is_skipped` (B7's second case).
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_B7_a_higher_ranked_fallback_that_is_fixed_is_skipped ___________

world = ('/private/tmp/claude-501/pytest-of-zwrose/pytest-1381/test_B7_a_higher_ranked_fallba0/repo', '/private/tmp/claude-501/pytest-of-zwrose/pytest-1381/test_B7_a_higher_ranked_fallba0/store')

    def test_B7_a_higher_ranked_fallback_that_is_fixed_is_skipped(world):
        repo, _store = world
        _launch(repo, "a", 11, "local", _call(reason="no-setup"))
        _launch(repo, "b", 22, "local", _call(reason="version", cloud="0.41.0", advisor="0.42.0"))
        got = _line(repo, ready=False, reason="version")
>       assert got == ("Still on your machine\n"
                       "The cloud's plugin is 0.41.0 and mine is 0.42.0. Paste the new setup text to fix it.")
E       assert 'Still on you...s" to fix it.' == 'Still on you...xt to fix it.'
E         
E           Still on your machine
E         - The cloud's plugin is 0.41.0 and mine is 0.42.0. Paste the new setup text to fix it.
E         + This project has no cloud setup on this Claude account. Say "set up cloud builds" to fix it.

/path/to/home/.superheroes-worktrees/superheroes/issue-1775-73b0797ad1a5d29e/plugins/superheroes/lib/tests/test_launch_report_verbs.py:677: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launch_report_verbs.py::test_B7_a_higher_ranked_fallback_that_is_fixed_is_skipped
1 failed in 5.81s
```

- **Restore.** The inverse Edit; quoted from `launch_report.py:271`: `        standing = [c for c in candidates if not _still_fixed(c, now, cwd, root)]`.
- **Green:**

```
.                                                                        [100%]
1 passed in 5.48s
```

### G24: an unconfirmed cloud launch does not clear. Axis: filter (`cloudSessionUnconfirmed`)

- **Neutralization applied.** In `launch_report._fallbacks`, `if not info["started"] or info.get("cloudSessionUnconfirmed"):` replaced with `if not info["started"]:`.
- **Node.** `TLV::test_B3_an_unconfirmed_cloud_launch_after_a_fallback_leaves_the_line`
- **Red** (the line went missing, so the test's `.startswith` ran on `None`):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_B3_an_unconfirmed_cloud_launch_after_a_fallback_leaves_the_line _____

world = ('/private/tmp/claude-501/pytest-of-zwrose/pytest-1383/test_B3_an_unconfirmed_cloud_l0/repo', '/private/tmp/claude-501/pytest-of-zwrose/pytest-1383/test_B3_an_unconfirmed_cloud_l0/store')

    def test_B3_an_unconfirmed_cloud_launch_after_a_fallback_leaves_the_line(world):
        repo, _store = world
        _launch(repo, "a", 11, "local", _call(reason="no-setup"))
        _reserve(repo, "b", 22, "cloud", {"placeCall": _call("cloud", reason=None)})
        rec = _started("b")
        rec.update(cloudSessionName="lane-b", cloudSessionUnconfirmed=True)
        assert ll.append_under_lock(repo, rec)["ok"]
        _folds(repo)
        got = _report(repo)
        assert got["lanes"] == 1 and "#22" not in got["report"]
>       assert _line(repo, ready=False, reason="no-setup").startswith("Still on your machine\nThis project")
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: 'NoneType' object has no attribute 'startswith'

/path/to/home/.superheroes-worktrees/superheroes/issue-1775-73b0797ad1a5d29e/plugins/superheroes/lib/tests/test_launch_report_verbs.py:492: AttributeError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launch_report_verbs.py::test_B3_an_unconfirmed_cloud_launch_after_a_fallback_leaves_the_line
1 failed in 6.02s
```

- **Restore.** The inverse Edit; quoted from `launch_report.py:228`: `        if not info["started"] or info.get("cloudSessionUnconfirmed"):`.
- **Green:**

```
.                                                                        [100%]
1 passed in 4.67s
```
