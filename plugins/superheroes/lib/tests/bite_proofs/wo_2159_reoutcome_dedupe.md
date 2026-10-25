# Bite-proof record: WO-2159-2 (#2159) the scoped `reoutcome` dedupe

Detector under proof: `plugins/superheroes/lib/tests/test_launch_ledger_reoutcome_dedupe_2159.py` (10 tests).
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
- T8 (non-finite opener ignored) was not in WO-2159-2's declared set; the orchestrator proved it as E7 below.

## E7. Non-finite opener ignored (`amend`, `launch_ledger.py`, the opener loop) — orchestrator-run

- **Axis:** a `vet not-ready` amendment with a non-finite ts is no fix order for the dedupe, so the dedupe stays
  whole-history (the reader skips the same amendment).
- **Neutralization** (orchestrator, Edit tool, in a detached probe worktree at `77c0cb67`):
  `and math.isfinite(ets) and (fix_order_ts is None or ets > fix_order_ts)):` became
  `and (fix_order_ts is None or ets > fix_order_ts)):`. Restored by the inverse Edit; `git status --porcelain`
  in the probe worktree was empty afterwards.
- **Raw red** (whole file, `-q -rf`, filtered by the orchestrator to the summary lines):

```
E       AssertionError: assert 'amendment' == 'amendment-existing'
FAILED plugins/superheroes/lib/tests/test_launch_ledger_reoutcome_dedupe_2159.py::test_t8_a_vet_not_ready_with_a_non_finite_ts_is_ignored_as_a_fix_order
1 failed, 8 passed in 2.69s
```

- **Raw green** after the restore: `9 passed in 2.78s`.

## E8. Newest of two fix orders (`amend`, `launch_ledger.py`, the opener loop)

- **Axis:** with two finite `vet not-ready` amendments and an identical `reoutcome` between them, the dedupe is
  scoped to the newer fix order: the repeat is written and closes the reopening the reader reports at the newer
  fix order's ts. Added by WO-2159-5 (review session 2 round 1), which found that no test laid two finite fix
  orders, so the newest-selection was not bitten (flipping it left the file at `9 passed`).
- **Neutralization** (Edit tool, at `11fcce2d`): `and math.isfinite(ets) and (fix_order_ts is None or ets > fix_order_ts)):`
  became `and math.isfinite(ets) and (fix_order_ts is None or ets < fix_order_ts)):` (the loop keeps the oldest
  fix order instead of the newest).
- **Raw red** (`-k test_t9`). T9 reddens: the oldest fix order scopes the dedupe, so the `reoutcome` between the
  two fix orders counts as a duplicate:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_t9_the_newest_of_two_fix_orders_scopes_the_dedupe ____________

repo = '/tmp/claude-0/pytest-of-root/pytest-12/test_t9_the_newest_of_two_fix_0/repo'

    def test_t9_the_newest_of_two_fix_orders_scopes_the_dedupe(repo):
        _handed_back(repo)
        now = time.time()
        _amend_at(repo, _LAUNCH, "vet", "not-ready", now - 300)
        _amend_at(repo, _LAUNCH, "reoutcome", "handback", now - 200, note=_EVIDENCE)
        _amend_at(repo, _LAUNCH, "vet", "not-ready", now - 100)
        assert ww._reopen_candidate(_info(repo), []) == (now - 100, "vet-not-ready")
>       assert _record(repo) == "amendment"
E       AssertionError: assert 'amendment-existing' == 'amendment'
E         
E         - amendment
E         + amendment-existing

/home/user/wt-2159/plugins/superheroes/lib/tests/test_launch_ledger_reoutcome_dedupe_2159.py:173: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launch_ledger_reoutcome_dedupe_2159.py::test_t9_the_newest_of_two_fix_orders_scopes_the_dedupe
1 failed, 9 deselected in 4.63s
```

- **Restore:** inverse Edit. **Restore receipt:** the restored text, `and math.isfinite(ets) and (fix_order_ts is None or ets > fix_order_ts)):`
  (`launch_ledger.py:2686`); `git diff --stat -- plugins/superheroes/lib/launch_ledger.py` prints nothing, so the
  file equals `11fcce2d`.
- **Raw green** (same selector):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed, 9 deselected in 0.82s
```

## Orchestrator re-run of E1–E4

The orchestrator re-ran every element above in its own detached probe worktree at `77c0cb67`, the same
neutralizations made by Edit and undone by the inverse Edit, whole test file each time (`-q -rf`):
E1 → 4 failed (T1, T3 "dedupe resumes", T5, T6), 5 passed; E2 → 2 failed (T4, T6), 7 passed; E3 → 1 failed (T5),
8 passed; E4 → 1 failed (T6, `assert 1792902665.0664358 == 1792903665.0664358`), 8 passed; restored → 9 passed.
Each red is on its element's axis; the extra reds under E1 and E2 are tests whose fixtures also lay a pre-fix
identical `reoutcome` or a tie through the stepped clock.
