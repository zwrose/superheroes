# Bite-proof record: WO-2159-2 (#2159) the scoped `reoutcome` dedupe

Detector under proof: `plugins/superheroes/lib/tests/test_launch_ledger_reoutcome_dedupe_2159.py` (9 tests).
Guarded code: `plugins/superheroes/lib/launch_ledger.py`, `amend()` (production edit committed at `6fe7b68d`,
base `ed3b7b34baf209dcc7e84b59b3b7d44e5bc2b2de`). Declared guarded-element set: E1, E2, E3, E4 (neutralized below);
E5 and E6 are pinned behaviour (see the end). Every neutralization was a targeted edit made with the Edit tool,
undone by the inverse Edit before the next element. No `git checkout`, `restore`, `reset` or `stash` was used.
Command prefix for every run below (worktree root):
`scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_launch_ledger_reoutcome_dedupe_2159.py -q -k <selector>`.
Nothing in the captures was redacted (temp paths only); each is under 32 KiB. The test file was not edited between
any red and its green. The red runs exit 1 by design (bite-proof reds, not failures).

## E1. Scope boundary: the fix-order filter on the dedupe (`amend`, `launch_ledger.py`)

- **Axis:** an identical `reoutcome` from before the lane's newest fix order does not count as a duplicate, so
  the repeat outcome that answers the fix order is recorded and closes the reopening.
- **Neutralization:** `if fix_order_ts is not None and not (` became `if False and fix_order_ts is not None and not (`
  (every identical amendment in the history counts).
- **Raw red** (`-k "test_t1 or test_t2"`). T1 reddens; T2 stays green under this neutralization, because the
  issue's literal row has no earlier identical `reoutcome` to dedupe against (so T2 pins the reader's close, not
  the filter):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F.                                                                       [100%]
=================================== FAILURES ===================================
_ test_t1_second_cycle_repeat_outcome_after_a_fix_order_is_recorded_and_closes_the_reopening _

repo = '/tmp/claude-0/pytest-of-root/pytest-1/test_t1_second_cycle_repeat_ou0/repo'

    def test_t1_second_cycle_repeat_outcome_after_a_fix_order_is_recorded_and_closes_the_reopening(repo):
        _handed_back(repo)
        assert _record(repo) == "amendment"
        _fix_order(repo)
>       assert _record(repo) == "amendment"
E       AssertionError: assert 'amendment-existing' == 'amendment'
E         
E         - amendment
E         + amendment-existing

/home/user/wt-2159/plugins/superheroes/lib/tests/test_launch_ledger_reoutcome_dedupe_2159.py:77: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launch_ledger_reoutcome_dedupe_2159.py::test_t1_second_cycle_repeat_outcome_after_a_fix_order_is_recorded_and_closes_the_reopening
1 failed, 1 passed, 7 deselected in 0.85s
```

- **Restore:** inverse Edit. **Restore receipt:** the restored line, `                    if fix_order_ts is not None and not (`
  (`launch_ledger.py:2692`, shown by the final `grep -n fix_order_ts`).
- **Raw green** (same selector):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
..                                                                       [100%]
2 passed, 7 deselected in 0.80s
```

## E2. Tie: a candidate at exactly the fix order's ts dedupes (`amend`, `launch_ledger.py`)

- **Axis:** a candidate with `ts == fix_order_ts` counts as after the fix order, matching the reader (a closer at the opener's ts closes it).
- **Neutralization:** `and math.isfinite(ets) and ets >= fix_order_ts):` became `and math.isfinite(ets) and ets > fix_order_ts):`.
- **Raw red** (`-k "test_t4"`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_t4_an_identical_reoutcome_at_the_fix_orders_ts_dedupes __________

repo = '/tmp/claude-0/pytest-of-root/pytest-3/test_t4_an_identical_reoutcome0/repo'

    def test_t4_an_identical_reoutcome_at_the_fix_orders_ts_dedupes(repo):
        _handed_back(repo)
        tie = time.time()
        _amend_at(repo, _LAUNCH, "reoutcome", "handback", tie, note=_EVIDENCE)
        _amend_at(repo, _LAUNCH, "vet", "not-ready", tie)
        assert ww._reopen_candidate(_info(repo), []) is None
        count = _record_count(repo)
>       assert _record(repo) == "amendment-existing"
E       AssertionError: assert 'amendment' == 'amendment-existing'
E         
E         - amendment-existing
E         + amendment

/home/user/wt-2159/plugins/superheroes/lib/tests/test_launch_ledger_reoutcome_dedupe_2159.py:122: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launch_ledger_reoutcome_dedupe_2159.py::test_t4_an_identical_reoutcome_at_the_fix_orders_ts_dedupes
1 failed, 8 deselected in 0.65s
```

- **Restore:** inverse Edit. **Restore receipt:** the restored text, `and math.isfinite(ets) and ets >= fix_order_ts):`
  (`launch_ledger.py:2694`).
- **Raw green** (same selector):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed, 8 deselected in 0.65s
```

## E3. Non-finite candidate does not dedupe (`amend`, `launch_ledger.py`)

- **Axis:** an identical `reoutcome` whose `ts` is non-finite is not after the fix order (the reader skips it), so it does not dedupe and a closer is written.
- **Neutralization:** `and math.isfinite(ets) and ets >= fix_order_ts):` became `and ets >= fix_order_ts):` (the candidate's finiteness check dropped; `inf >= T` is true).
- **Raw red** (`-k "test_t5"`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_t5_an_identical_reoutcome_with_a_non_finite_ts_does_not_dedupe ______

repo = '/tmp/claude-0/pytest-of-root/pytest-5/test_t5_an_identical_reoutcome0/repo'

    def test_t5_an_identical_reoutcome_with_a_non_finite_ts_does_not_dedupe(repo):
        _handed_back(repo)
        _amend_at(repo, _LAUNCH, "vet", "not-ready", time.time())
        _amend_at(repo, _LAUNCH, "reoutcome", "handback", float("inf"), note=_EVIDENCE)
        assert ww._reopen_candidate(_info(repo), []) is not None
>       assert _record(repo) == "amendment"
E       AssertionError: assert 'amendment-existing' == 'amendment'
E         
E         - amendment
E         + amendment-existing

/home/user/wt-2159/plugins/superheroes/lib/tests/test_launch_ledger_reoutcome_dedupe_2159.py:133: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launch_ledger_reoutcome_dedupe_2159.py::test_t5_an_identical_reoutcome_with_a_non_finite_ts_does_not_dedupe
1 failed, 8 deselected in 0.58s
```

- **Restore:** inverse Edit. **Restore receipt:** the restored text, `and math.isfinite(ets) and ets >= fix_order_ts):`
  (`launch_ledger.py:2694`).
- **Raw green** (same selector):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed, 8 deselected in 0.57s
```

## E4. The ts clamp (`amend`, `launch_ledger.py`)

- **Axis:** a backwards clock step cannot write a closer older than the lane's fix order.
- **Neutralization:** `"ts": time.time() if fix_order_ts is None else max(time.time(), fix_order_ts),` became `"ts": time.time(),`.
- **Raw red** (`-k "test_t6"`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t6_a_clock_stepped_back_still_writes_a_closer_no_older_than_the_fix_order _

repo = '/tmp/claude-0/pytest-of-root/pytest-7/test_t6_a_clock_stepped_back_s0/repo'
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f64c8740e00>

    def test_t6_a_clock_stepped_back_still_writes_a_closer_no_older_than_the_fix_order(repo, monkeypatch):
        _handed_back(repo)
        assert _record(repo) == "amendment"
        now = time.time()
        fix_order_ts = now + 1000
        _amend_at(repo, _LAUNCH, "vet", "not-ready", fix_order_ts)
        assert ww._reopen_candidate(_info(repo), []) is not None
        monkeypatch.setattr(ll, "time", _SteppedTime(now))
        assert _record(repo) == "amendment"
>       assert _reoutcomes(repo)[-1]["ts"] == fix_order_ts
E       assert 1792902352.135349 == 1792903352.135349

/home/user/wt-2159/plugins/superheroes/lib/tests/test_launch_ledger_reoutcome_dedupe_2159.py:147: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launch_ledger_reoutcome_dedupe_2159.py::test_t6_a_clock_stepped_back_still_writes_a_closer_no_older_than_the_fix_order
1 failed, 8 deselected in 0.68s
```

- **Restore:** inverse Edit. **Restore receipt:** the restored line, `                "ts": time.time() if fix_order_ts is None else max(time.time(), fix_order_ts),`
  (`launch_ledger.py:2709`); a post-restore `git status --porcelain` lists no modified tracked file, so
  `launch_ledger.py` equals `6fe7b68d`.
- **Raw green** (same selector):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed, 8 deselected in 0.73s
```

## E5 and E6: pinned behaviour, no neutralization owed

- **E5 (no fix order: whole-history dedupe; dedupe resumes after the fix order is answered)** is today's
  behaviour: the production edit leaves the loop unchanged when `fix_order_ts is None`, and the base code already
  dedupes after an answered fix order only because the answering `reoutcome` is itself after it. T3 (both tests)
  pins it and passes against the committed edit; no neutralization was run for it, and no run against the base
  revision of `launch_ledger.py` was made in this dispatch.
- **E6 (other kinds unchanged with `dedupe_identical=True`)** is today's behaviour: `fix_order_ts` is only set
  for `kind == "reoutcome"`, so other kinds never reach the filter. T7 pins it; no neutralization owed.
- T8 (non-finite opener ignored) is also not given its own neutralization by this order; it is pinned by the
  `math.isfinite(ets)` test in the opener loop (`launch_ledger.py:2686`), which this order did not list as a
  guarded element, so T8's bite is **unproven** here.
