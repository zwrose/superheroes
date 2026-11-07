# Bite-proof record — the kept break-it step reads the session head through one resolver (#2393)

Detector file: `plugins/superheroes/lib/tests/test_kept_head_resolver_2393.py`, unedited between each red and its green. Every neutralization is a targeted, reversible Edit-tool edit to one production file (`plugins/superheroes/lib/round_driver.py`), restored by the inverse edit (no `git checkout`, `restore`, `reset` or `stash`). Runs, from the worktree root: `GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-wo1 -m pytest '<exact node ids>' -q -p no:cacheprovider`, followed by the `exit=` line the command printed. The `UV_NATIVE_TLS` deprecation warning `uv` prints first is the only line left out of each capture. Each `old_string` occurred exactly once (the Edit tool refuses a non-unique match). No secrets, tokens, private URLs or PII appear in any capture; nothing was redacted (the pytest tmp path shown is a throwaway directory).

**Pinned condition:** the fixture's own git calls ignore user and system git config (`GIT_CONFIG_GLOBAL=os.devnull`, `GIT_CONFIG_NOSYSTEM=1`) and pass their commit identity inline. **Production shape the pin makes unobservable:** a host whose global git config rewrites hooks, signing or default branches; the code under test runs git with the caller's own environment, so the pin covers the fixture's commits only.

**Guarded-element set (the order declared two; none grouped):**

- **K1** — the kept step's head read (`_break_it_kept_step`, `head = _session_head(session_dir, config)`). Detectors: T1 and T2.
- **K2** — the `session_dir` forwarding down the chain that reaches the kept step (all `session_dir=session_dir` forwards, plus the chain functions' `session_dir` parameters). Detector: T6 census, representative element: the forward at the `_after_findings_settled` call in `_fold_synthesis`. The T6 census walks every chain call from every top-level function that holds a `session_dir`, so any one dropped forward fails it by the same failure mode (a chain call that does not pass the session directory); this one forward stands for the class, and the other forwards were not each neutralized. (This was the first version of the census. K3 replaces it.)
- **K3**: the repaired census added after review round 1. It checks that every call into any function that takes a `session_dir`, made where one is held, passes that `session_dir` itself, never `None` and never omitted. Detectors: T6 (b) and the test role's break-it test `test_kept_head_forwarding_regression_2393.py`.

## K1. The kept step's head read

- **Axis:** a round-1 session whose head only `meta.json` records is never headless in the kept check (and a session with no head anywhere still withholds, T4).
- **Detectors:** `test_kept_head_resolver_2393.py::test_t1_a_round_one_session_whose_head_only_meta_json_records_is_not_headless` and `...::test_t2_the_converge_chokepoint_certifies_a_round_one_session_headed_only_by_meta_json`.
- **Neutralization:** `head = _session_head(session_dir, config)` became `head = config.get(FIX_FOLD_HEAD_KEY) or config.get("headSha")` (the base code's read).

**Raw red** (exit 1, T2's decisive line is the certification reason `unresolved: input-missing`, the axis):

```
FF                                                                       [100%]
=================================== FAILURES ===================================
_ test_t1_a_round_one_session_whose_head_only_meta_json_records_is_not_headless _

world = <test_kept_head_resolver_2393.World object at 0x7f6fcff5a1e0>

    def test_t1_a_round_one_session_whose_head_only_meta_json_records_is_not_headless(world):
        world.fixed_finding()
        world.write_meta(headSha=world.fix())
>       assert RD._break_it_kept_step(world.state, world.state["config"],
                                      session_dir=world.session_dir) is False
E       AssertionError: assert True is False
E        +  where True = <function _break_it_kept_step at 0x7f6fce326b60>({'schemaVersion': 5, 'sessionGeneration': 7, 'config': {'leg': 'code', 'panel': False, 'code': True, 'vendors': ['claude', 'codex'], ...}, 'round': 1, ...}, {'leg': 'code', 'panel': False, 'code': True, 'vendors': ['claude', 'codex'], ...}, session_dir='/tmp/claude-0/pytest-of-root/pytest-2/test_t1_a_round_one_session_wh0/session')
E        +    where <function _break_it_kept_step at 0x7f6fce326b60> = RD._break_it_kept_step
E        +    and   {'schemaVersion': 5, 'sessionGeneration': 7, 'config': {'leg': 'code', 'panel': False, 'code': True, 'vendors': ['claude', 'codex'], ...}, 'round': 1, ...} = <test_kept_head_resolver_2393.World object at 0x7f6fcff5a1e0>.state
E        +    and   '/tmp/claude-0/pytest-of-root/pytest-2/test_t1_a_round_one_session_wh0/session' = <test_kept_head_resolver_2393.World object at 0x7f6fcff5a1e0>.session_dir

/home/user/wt-2393/plugins/superheroes/lib/tests/test_kept_head_resolver_2393.py:164: AssertionError
_ test_t2_the_converge_chokepoint_certifies_a_round_one_session_headed_only_by_meta_json _

world = <test_kept_head_resolver_2393.World object at 0x7f6fcff5a3f0>

    def test_t2_the_converge_chokepoint_certifies_a_round_one_session_headed_only_by_meta_json(world):
        world.fixed_finding()
        world.write_meta(headSha=world.fix())
        RD._terminal_converged(world.state, world.state["config"], full_panel=True,
                               session_dir=world.session_dir)
>       assert world.state["terminal"] == "converged", world.state.get("certification")
E       AssertionError: {'shape': None, 'reason': 'break-it test not kept: tests/test_charge_once.py (unresolved: input-missing)'}
E       assert 'cannot-certify' == 'converged'
E         
E         - converged
E         + cannot-certify

/home/user/wt-2393/plugins/superheroes/lib/tests/test_kept_head_resolver_2393.py:175: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_kept_head_resolver_2393.py::test_t1_a_round_one_session_whose_head_only_meta_json_records_is_not_headless
FAILED plugins/superheroes/lib/tests/test_kept_head_resolver_2393.py::test_t2_the_converge_chokepoint_certifies_a_round_one_session_headed_only_by_meta_json
2 failed in 0.78s
exit=1
```

- **Restore:** inverse edit (`head = config.get(FIX_FOLD_HEAD_KEY) or config.get("headSha")` back to `head = _session_head(session_dir, config)`).
- **Restore receipt** (read back by the Grep tool over `head = _session_head(session_dir, config)|config.get\("headSha"\)`; no `config.get("headSha")` remains in the file):

```
10618-    # axis: the kept check reads the session head through the one resolver, meta.json first, so a round-1 session whose head only meta.json records is never headless — see bite-proof record wo_1_2393_kept_head
10619:    head = _session_head(session_dir, config)
```

**Raw green** (exit 0):

```
..                                                                       [100%]
2 passed in 1.38s
exit=0
```

## K2. The `session_dir` forward down the chain (representative: `_fold_synthesis` -> `_after_findings_settled`)

> **Superseded detector.** The census quoted in K2's red below is the implementer's first version, at head `3b1c8d94`. It checked only that a keyword named `session_dir` was present, over a hand-kept chain set that left out `_queue_fix_batch`. Review round 1 found that gap. The census was then rewritten to check the forwarded value across every function that takes a `session_dir`. K2's receipts stand as the record of that earlier detector, and K3 below is the record for the current one.

- **Axis:** every call to a chain function made where a `session_dir` is held passes it down, so the kept step receives the session directory from every route that reaches it.
- **Detector:** `test_kept_head_resolver_2393.py::test_t6_census_b_every_chain_call_made_where_a_session_dir_is_held_passes_it`.
- **Neutralization:** in `_fold_synthesis`, `_after_findings_settled(state, config, session_dir=session_dir)` became `_after_findings_settled(state, config)`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t6_census_b_every_chain_call_made_where_a_session_dir_is_held_passes_it _

    def test_t6_census_b_every_chain_call_made_where_a_session_dir_is_held_passes_it():
        tree = _round_driver_tree()
        missing, seen = [], 0
        for func in tree.body:
            if not isinstance(func, ast.FunctionDef) or "session_dir" not in _params(func):
                continue
            for node in ast.walk(func):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                        and node.func.id in CHAIN):
                    seen += 1
                    if "session_dir" not in [k.arg for k in node.keywords]:
                        missing.append("%s:%d calls %s without session_dir" % (func.name, node.lineno, node.func.id))
        assert seen >= len(CHAIN), "the census saw too few chain calls (%d): the walk is not reaching them" % seen
>       assert missing == []
E       AssertionError: assert ['_fold_synth... session_dir'] == []
E         
E         Left contains one more item: '_fold_synthesis:5435 calls _after_findings_settled without session_dir'
E         Use -v to get more diff

/home/user/wt-2393/plugins/superheroes/lib/tests/test_kept_head_resolver_2393.py:308: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_kept_head_resolver_2393.py::test_t6_census_b_every_chain_call_made_where_a_session_dir_is_held_passes_it
1 failed in 0.40s
exit=1
```

- **Restore:** inverse edit (`_after_findings_settled(state, config)` back to `_after_findings_settled(state, config, session_dir=session_dir)` at the `_fold_synthesis` call).
- **Restore receipt** (Grep over `_after_findings_settled\(state, config`; both calls carry the forward, the middle line is the definition):

```
5434-    _apply_repeat_marks(state, plan)
5435:    _after_findings_settled(state, config, session_dir=session_dir)
--
6165-
6166:def _after_findings_settled(state, config, session_dir=None):
--
10239-              "from there." % state["round"])
10240:    _after_findings_settled(state, config, session_dir=session_dir)
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.38s
exit=0
```

## K3. The repaired forwarding census (value-checked, every session-dir callee), after review round 1

Recorded by the builder at head `f8f0cd68`, in a detached probe worktree. Each neutralization is a targeted Edit-tool edit to `plugins/superheroes/lib/round_driver.py`, restored by the inverse edit. The probe tree read clean (`git status --short` empty) before the green run. Runs, from the probe root: `GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-probe -m pytest plugins/superheroes/lib/tests/test_kept_head_resolver_2393.py plugins/superheroes/lib/tests/test_kept_head_forwarding_regression_2393.py -q -p no:cacheprovider`. Captures are filtered to the decisive lines with `grep -E`. Nothing was redacted.

- **Axis:** every call into a function that takes a `session_dir`, made where one is held, passes that `session_dir` itself, never `None` and never omitted.
- **Detectors:** `test_kept_head_resolver_2393.py::test_t6_census_b_every_chain_call_made_where_a_session_dir_is_held_passes_it`, plus the test role's break-it test `test_kept_head_forwarding_regression_2393.py` (both of its tests).

**Neutralization 1, the omitted forward.** At the `_after_findings_settled` call into `_queue_fix_batch`, `session_dir=session_dir` was dropped. Raw red (exit 1):

```
E         Left contains one more item: '_after_findings_settled:6182 calls _queue_fix_batch without its session_dir (omitted)'
E       AssertionError: {'shape': None, 'reason': 'break-it test not kept: tests/test_charge_once.py (unresolved: input-missing)'}
E       assert 'cannot-certify' == 'converged'
E         + cannot-certify
FAILED plugins/superheroes/lib/tests/test_kept_head_resolver_2393.py::test_t6_census_b_every_chain_call_made_where_a_session_dir_is_held_passes_it
FAILED plugins/superheroes/lib/tests/test_kept_head_forwarding_regression_2393.py::test_discharge_exclusion_preserves_the_meta_only_head
2 failed, 8 passed in 4.46s
exit=1
```

**Neutralization 2, a `None`-valued forward.** At the `_fold_synthesis` call, `session_dir=session_dir` was changed to `session_dir=None`. Raw red (exit 1):

```
E         Left contains one more item: '_fold_synthesis:5435 calls _after_findings_settled without its session_dir (None)'
FAILED plugins/superheroes/lib/tests/test_kept_head_resolver_2393.py::test_t6_census_b_every_chain_call_made_where_a_session_dir_is_held_passes_it
1 failed, 9 passed in 20.29s
exit=1
```

**Raw green** after both inverse edits (exit 0):

```
10 passed in 2.73s
exit=0
```

## Not neutralized (named, so the record does not read broader than it is)

- T3, T4 and T5 and T6 (a) and (c) were each seen green on the final source (the whole-module run and the final file-set run below) but were not each driven red; the order named red-then-green for the kept step's head read (K1) and for the census (K2) only. T3 was not run against the base read, so this record does not claim it fails there.
- The other `session_dir=session_dir` forwards in the chain were not each dropped; the T6 (b) walk covers all of them by the same failure mode, with the `_fold_synthesis` forward as the one proven representative.

Implementer-head (`3b1c8d94`) file-set run (the new module, `test_break_it_loop.py`, the five updated-double files, `test_stall_decomposition.py`, `test_breaker_reason_census.py`):

```
........................................................................ [ 29%]
........................................................................ [ 59%]
........................................................................ [ 88%]
...........................                                              [100%]
243 passed in 28.61s
exit=0
```
