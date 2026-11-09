# Bite-proof record — a break-it test on a finding never sent for fixing does not block the certificate (#2397)

Detector file: `plugins/superheroes/lib/tests/test_break_it_never_sent_2397.py` (T1-T6, 8 test nodes) plus, for G3, the existing unedited `plugins/superheroes/lib/tests/test_break_it_loop.py::test_a_failed_break_it_run_with_no_disposition_withholds_certification`. Both are unedited between each red and its green. Every entry is one targeted, reversible edit to one production file (`plugins/superheroes/lib/round_driver.py`, helper `_never_sent_outcome`), restored by the inverse edit through the Edit tool (no `git checkout`, `restore`, `reset`, `stash`, and no shell edit). Command for every red and green, from the worktree root: `timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest <exact node ids> -q -p no:randomly`. Captures are the whole pytest output, including the `UV_NATIVE_TLS` deprecation warning `uv` prints first; the red captures are shown with that warning, the tmp paths and the failing source lines left as printed. No secret, token or private URL appears in any capture, so nothing was redacted.

The guarded-element set is the three the order declared (G1-G3); none is grouped. Each target string occurred exactly once in the file (the Edit tool refuses a non-unique match).

Detectors with a `# bites on:` line that are outside G1-G3 (T4 the E2 queued-now leg, T5 the E6 bound-ruling leg, T6's Critical case, and the E4 merged, E5 no-content and ledger-fault edges) guard edges of the new branch that were not neutralized separately (see *Not proven*).

## G1. The waiver branch (`round_driver.py`, `_never_sent_outcome`; consumed in the `disposition is None` arm of `_break_it_kept_step`)

- **Axis:** a never-fix-bound, non-blocking, unruled finding with no disposition gets a `not-required` row naming its end-of-loop outcome (`craft` or `left-for-owner`) and does not withhold the certificate; the axis is the converge verdict and the row, not the helper's return alone.
- **Detectors (expected red):** T1, T2.
- **Neutralization** (helper always returns None, so the arm keeps today's `unresolved` / `no-disposition` row):
  `    if not isinstance(key, str) or not key or not isinstance(ledger_by_key, dict):` became `    if True or not isinstance(key, str) or not key or not isinstance(ledger_by_key, dict):`

**Raw red** (exit 1):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
FF                                                                       [100%]
=================================== FAILURES ===================================
______ test_t1_a_minor_code_quality_finding_never_sent_converges_as_craft ______

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-3/test_t1_a_minor_code_quality_f0')

    def test_t1_a_minor_code_quality_finding_never_sent_converges_as_craft(tmp_path):
        # bites on: G1 the waiver branch (helper returning None withholds), and the craft token (outcomes[2]) chosen by the code-quality kind
        world, key = _folded(tmp_path, severity="Minor", consequenceKind=CODE_QUALITY)
        (row,) = _converge(world)
>       assert world.state["terminal"] == "converged"
E       AssertionError: assert 'cannot-certify' == 'converged'
E         
E         - converged
E         + cannot-certify

/home/user/wt-2397/plugins/superheroes/lib/tests/test_break_it_never_sent_2397.py:72: AssertionError
_ test_t2_a_minor_owner_facing_finding_never_sent_converges_as_left_for_owner __

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-3/test_t2_a_minor_owner_facing_f0')

    def test_t2_a_minor_owner_facing_finding_never_sent_converges_as_left_for_owner(tmp_path):
        # bites on: G1 the waiver branch (helper returning None withholds), and the left-for-owner token (outcomes[3]) for a non-code-quality consequence
        world, key = _folded(tmp_path, severity="Minor")
        (row,) = _converge(world)
>       assert world.state["terminal"] == "converged"
E       AssertionError: assert 'cannot-certify' == 'converged'
E         
E         - converged
E         + cannot-certify

/home/user/wt-2397/plugins/superheroes/lib/tests/test_break_it_never_sent_2397.py:84: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_never_sent_2397.py::test_t1_a_minor_code_quality_finding_never_sent_converges_as_craft
FAILED plugins/superheroes/lib/tests/test_break_it_never_sent_2397.py::test_t2_a_minor_owner_facing_finding_never_sent_converges_as_left_for_owner
2 failed in 0.81s
```

The red is on the claimed axis: the certificate is withheld (`cannot-certify`) where `converged` is expected.

**Restore:** the inverse Edit, `if True or not isinstance(key, str) ...` back to `if not isinstance(key, str) ...`.

**Restore receipt** (restored line quoted from a Grep of the file, `round_driver.py:10564`):

```
10564:    if not isinstance(key, str) or not key or not isinstance(ledger_by_key, dict):
```

**Raw green** (exit 0):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
..                                                                       [100%]
2 passed in 0.74s
```

## G2. The E1 history leg (`round_driver.py`, `_never_sent_outcome`, the `sentUnderDecision` presence test)

- **Axis:** a finding whose lineage root is present as a key in `sentUnderDecision` (even at stored seq 0, no ruling) went to a fixer once and is fix-bound for good, so its absent disposition withholds.
- **Detectors (expected red):** T3 (both `[code-quality]` and `[real]`). The test builds the history by driving the real `RD._queue_fix_batch(state, config, [ledger row], session_dir=...)` (it returned `"queued"`), asserts `state["sentUnderDecision"][root] == 0`, then empties `_fixBatch`, `_fixQueue` and `fixBatch`, so only E1 remains to withhold.
- **Neutralization** (skip the `sentUnderDecision` check):
  `    if isinstance(sent, dict) and _lineage_root(_lineage_map(state), key) in sent:` became `    if False and isinstance(sent, dict) and _lineage_root(_lineage_map(state), key) in sent:`

**Raw red** (exit 1; the two failures are identical bar the parameter, the second is shown by its header and assertion):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
FF                                                                       [100%]
=================================== FAILURES ===================================
__ test_t3_a_minor_finding_sent_once_in_a_slice_still_withholds[code-quality] __

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-5/test_t3_a_minor_finding_sent_o0')
kind = 'code-quality'

    @pytest.mark.parametrize("kind", [CODE_QUALITY, "real"])
    def test_t3_a_minor_finding_sent_once_in_a_slice_still_withholds(tmp_path, kind):
        # bites on: G2 the E1 history leg (presence of the lineage root in sentUnderDecision, even at seq 0)
        world, key = _folded(tmp_path, severity="Minor", consequenceKind=kind)
        state = world.state
        row = _ledger_row(world, key)
        assert RD._queue_fix_batch(state, state["config"], [row], session_dir=str(world.session)) == "queued"
        root = RD._lineage_root(RD._lineage_map(state), key)
        assert state["sentUnderDecision"][root] == 0
        for field in ("_fixBatch", "_fixQueue", "fixBatch"):
            state[field] = []
        assert RD._disposition_ledger_by_key(state)[0].get(key, {}).get("disposition") is None
>       _withheld(world)

/home/user/wt-2397/plugins/superheroes/lib/tests/test_break_it_never_sent_2397.py:103: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

world = <test_break_it_loop.World object at 0x7f5f9699b650>

    def _withheld(world):
        (row,) = _converge(world)
>       assert world.state["terminal"] == "cannot-certify"
E       AssertionError: assert 'converged' == 'cannot-certify'
E         
E         - cannot-certify
E         + converged

/home/user/wt-2397/plugins/superheroes/lib/tests/test_break_it_never_sent_2397.py:64: AssertionError
______ test_t3_a_minor_finding_sent_once_in_a_slice_still_withholds[real] ______
  (same body as above with kind = 'real'; same final assertion)
E       AssertionError: assert 'converged' == 'cannot-certify'
E         
E         - cannot-certify
E         + converged

/home/user/wt-2397/plugins/superheroes/lib/tests/test_break_it_never_sent_2397.py:64: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_never_sent_2397.py::test_t3_a_minor_finding_sent_once_in_a_slice_still_withholds[code-quality]
FAILED plugins/superheroes/lib/tests/test_break_it_never_sent_2397.py::test_t3_a_minor_finding_sent_once_in_a_slice_still_withholds[real]
2 failed in 1.03s
```

(Elided from the second failure: its repeated 17-line source listing, identical to the first's. The pytest run printed it in full; the elision is this record's.)

The red is on the claimed axis: a finding sent once converges where it must withhold.

**Restore:** the inverse Edit, `if False and isinstance(sent, dict) ...` back to `if isinstance(sent, dict) ...`.

**Restore receipt** (restored line quoted from a Grep of the file, `round_driver.py:10568`):

```
10568:    if isinstance(sent, dict) and _lineage_root(_lineage_map(state), key) in sent:
```

**Raw green** (exit 0):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
..                                                                       [100%]
2 passed in 0.65s
```

## G3. The E3 severity leg (`round_driver.py`, `_never_sent_outcome`, the `circuit_breaker.is_blocking` test)

- **Axis:** a finding whose severity is blocking is fix-bound, so its absent disposition withholds whatever else is true of it.
- **Detector (expected red):** the existing, unedited `test_break_it_loop.py::test_a_failed_break_it_run_with_no_disposition_withholds_certification` (an Important finding, no disposition). The new T6 (Critical and Important) carries the same `# bites on:` leg but was not the detector run for this entry.
- **Neutralization** (skip the severity leg):
  `    if circuit_breaker.is_blocking(content.get("severity")):` became `    if False and circuit_breaker.is_blocking(content.get("severity")):`

**Raw red** (exit 1):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_a_failed_break_it_run_with_no_disposition_withholds_certification ____

world = <test_break_it_loop.World object at 0x7fcd711b21e0>

    def test_a_failed_break_it_run_with_no_disposition_withholds_certification(world):
        world.fold_panel(_break_it_finding())
        world.fix(None)
        RD._terminal_converged(world.state, world.state["config"], full_panel=True)
>       assert world.state["terminal"] == "cannot-certify"
E       AssertionError: assert 'converged' == 'cannot-certify'
E         
E         - cannot-certify
E         + converged

/home/user/wt-2397/plugins/superheroes/lib/tests/test_break_it_loop.py:462: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_loop.py::test_a_failed_break_it_run_with_no_disposition_withholds_certification
1 failed in 0.45s
```

The red is on the claimed axis: a blocking finding with no disposition certifies where it must withhold.

**Restore:** the inverse Edit, `if False and circuit_breaker.is_blocking(...)` back to `if circuit_breaker.is_blocking(...)`.

**Restore receipt** (restored line quoted from a Grep of the file, `round_driver.py:10584`):

```
10584:    if circuit_breaker.is_blocking(content.get("severity")):
```

**Raw green** (exit 0):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 0.45s
```

## Not proven

The order declared G1-G3 only. These edges of the new branch carry a test or a code path but were **not** neutralized, so their bite is unproven: E2 queued-now (T4 passes with the leg present; a neutralization would be expected to redden T4), E6 bound ruling (T5, likewise), the Critical case of T6 (G3's red was run on the Important case), E4 merged, E5 no content, and the fail-closed returns for an unreadable ledger and for a ledger row that already carries a disposition (the last two have no test at all).
