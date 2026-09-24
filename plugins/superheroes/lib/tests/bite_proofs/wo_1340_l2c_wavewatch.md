# WO-A (#1340 layer 2c) bite-proof — `wave_watch.py` membership read budget

Per-guard bite proof for `plugins/superheroes/lib/wave_watch.py` stack-resolution call site:
the `# bite-axis: READ-BUDGET` clause is neutralized in source, the proving test goes red alone,
then the clause is restored and the test goes green.

## BP1 — READ-BUDGET call site

**Guarded element:** `wave_watch.py` `_resolve_pr_stack_groups` membership_reader call — axis:
the whole membership read is bounded by the watcher's remaining budget; a read that outlives it
refuses rather than returning partial membership.

**Neutralization:** replaced `deadline=remaining` with `timeout=remaining` on the
`membership_reader` call (lines ~767).

**Proving test:** `test_pr_set_changed_whole_membership_read_bounded_by_watcher_remaining_budget`

**Red run:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_pr_set_changed_whole_membership_read_bounded_by_watcher_remaining_budget _

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-2655/test_pr_set_changed_whole_memb0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x1054f4190>

    def test_pr_set_changed_whole_membership_read_bounded_by_watcher_remaining_budget(
        tmp_path, monkeypatch,
    ):
        pr_sets = [{10}, {10, 99}]
        recorded = []
        mono = [500.0]
        watcher_deadline = 505.0
    
        def membership_reader(**kwargs):
            recorded.append(dict(kwargs))
            return {"ok": False, "reason": sc.REASON_NOT_LINKED}
    
        def monotonic():
            return mono[0]
    
        repo = _init_repo(tmp_path / "repo")
        _ledger_env(tmp_path, monkeypatch)
        result = ww.run(
            repo,
            "batch-982",
            max_seconds=5,
            interval_seconds=1,
            gh_run=_gh_pr_list_with_repo_view(pr_sets),
            membership_reader=membership_reader,
            monotonic=monotonic,
        )
    
        assert result["event"] == "pr-set-changed"
        assert len(recorded) == 1
        call = recorded[0]
        assert call["pr"] == 99
        assert call["repo"] == _TEST_REPO_SLUG
>       assert call["deadline"] > 0
E       KeyError: 'deadline'

plugins/superheroes/lib/tests/test_wave_watch.py:3706: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch.py::test_pr_set_changed_whole_membership_read_bounded_by_watcher_remaining_budget
1 failed in 1.32s
```

**Restore:** reverted to `deadline=remaining`

**Restore receipt:** `deadline=remaining`

**Green run:**
```
.                                                                        [100%]
1 passed in 1.28s
```
