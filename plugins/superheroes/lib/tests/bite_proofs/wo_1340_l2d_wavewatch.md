# WO-C (#1340 layer 2d) bite-proof — `wave_watch.py` slug read de-duplication

Per-guard bite proof for `plugins/superheroes/lib/wave_watch.py` slug-resolution guards:
each guarded element is neutralized in source, the proving test goes red alone,
then the guard is restored and the test goes green.

## E1 — pre-call `_MIN_PR_POLL_SECONDS` budget guard

**Guarded element:** `wave_watch.py` `_resolve_repo_slug` — axis: return `None`
without calling gh when remaining budget is below `_MIN_PR_POLL_SECONDS`.

**Neutralization:** removed the `if remaining < _MIN_PR_POLL_SECONDS: return None`
block (lines ~702-704).

**Proving test:** `test_resolve_repo_slug_sub_min_budget_makes_no_gh_call`

**Red run:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_resolve_repo_slug_sub_min_budget_makes_no_gh_call ____________

    def test_resolve_repo_slug_sub_min_budget_makes_no_gh_call():
        gh_calls = []
        mono = [1000.0]

        def gh_run(argv, **kwargs):
            gh_calls.append(argv)
            return _gh_repo_view_proc()

        slug = ww._resolve_repo_slug(
            "/fake/repo",
            deadline=1000.5,
            monotonic=lambda: mono[0],
            gh_run=gh_run,
            env={},
        )

>       assert slug is None
E       AssertionError: assert 'owner/repo' is None

plugins/superheroes/lib/tests/test_wave_watch.py:3947: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch.py::test_resolve_repo_slug_sub_min_budget_makes_no_gh_call
1 failed in 0.25s
```

**Restore:** reinstated `if remaining < _MIN_PR_POLL_SECONDS: return None`

**Restore receipt:** `if remaining < _MIN_PR_POLL_SECONDS:\n        return None`

**Green run:**
```
.                                                                        [100%]
1 passed in 0.20s
```

## E2 — refusal-to-`None` funnel

**Guarded element:** `wave_watch.py` `_resolve_repo_slug` — axis: every
`resolve_repo_slug` refusal becomes `None` so the watcher degrades to ungrouped
rather than propagating the refusal.

**Neutralization:** replaced `if refusal is not None: return None` with
`if refusal is not None: raise RuntimeError("refusal propagated")` (lines ~713-714).

**Proving test:** `test_pr_set_changed_resolve_repo_slug_refusal_degrades_to_ungrouped`

**Red run:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_pr_set_changed_resolve_repo_slug_refusal_degrades_to_ungrouped ______

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-2922/test_pr_set_changed_resolve_re0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x101ad76d0>

    def test_pr_set_changed_resolve_repo_slug_refusal_degrades_to_ungrouped(
        tmp_path, monkeypatch,
    ):
        pr_sets = [{10}, {10, 99}]

        def membership_reader(*, pr, repo, **kwargs):
            raise AssertionError("membership_reader must not run when slug read refused")

        def refusing_resolve(*args, **kwargs):
            return None, {
                "ok": False,
                "reason": sc.REASON_STACK_UNREADABLE,
                "detail": "test refusal",
            }

        monkeypatch.setattr(sc, "resolve_repo_slug", refusing_resolve)
        result = _run_pr_set_changed(
            tmp_path, monkeypatch, pr_sets, membership_reader,
        )

>       assert result["event"] == "pr-set-changed"
E       KeyError: 'event'

plugins/superheroes/lib/tests/test_wave_watch.py:3899: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch.py::test_pr_set_changed_resolve_repo_slug_refusal_degrades_to_ungrouped
1 failed in 1.33s
```

**Restore:** reinstated `if refusal is not None: return None`

**Restore receipt:** `if refusal is not None:\n        return None`

**Green run:**
```
.                                                                        [100%]
1 passed in 1.28s
```
