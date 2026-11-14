# WO-3 (#2459) bite-proof — the linearity gate of `stack_merge.py`

Per-element bite proof for the gate added to `plugins/superheroes/lib/stack_merge.py`: each new `# axis:` clause is neutralized by a targeted edit, its proving test(s) must go red alone (`-k`), the clause is restored by the inverse edit, and both stack_merge test files go green again. Line numbers are those of the restored file.

**Provenance:** claude (Claude Sonnet 5.5), implementer of WO-3.

**Commands.** *Red* (one per element, `<expr>` named in each entry; the `--tb` style used is named per entry):

```
scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-wo3 -m pytest plugins/superheroes/lib/tests/test_stack_merge.py plugins/superheroes/lib/tests/test_stack_merge_linear.py -q -p no:cacheprovider --tb=short -k "<expr>"
```

*Green* (after each restore, both files whole): the same command with no `-k`.

Every capture omits the one leading line `warning: The UV_NATIVE_TLS environment variable is deprecated ...`, which is uv's own notice. Nothing else is filtered or trimmed. No secret, token or private URL appears in any capture, so nothing was redacted. The restored green count is 169 passed until E18, whose proving test was added during this proof (disclosed under E18), after which it is 173 passed.

**Guarded-element set.** The order declared "every new `# axis:` clause in `stack_merge.py` (one per G1-G9 at least, plus queue-false-pass and the-gate-runs-before-the-PUT)". That is E1-E17 below, one entry each (no equivalence classes). E18 is one more element found during the proof. G5 has no clause of its own (see E18). Elements in no entry: none left unproven.

## Summary table

| ID | Guarded element (file:line) | Edge / axis | Proving test(s) | Verdict |
|---|---|---|---|---|
| E1 | stack_merge.py:380 | G9: only layers at or below the top are checked | `test_g9_*` | proven |
| E2 | stack_merge.py:391 | G1: budget spent before the gate, no read made | `test_g1_*` | proven |
| E3 | stack_merge.py:399 | G2: a membership refusal is `linearity-unreadable` naming its reason | `test_g2_*` | proven (see note) |
| E4 | stack_merge.py:405 | G3: no layer at or below the top can be named | `test_g3_*` | proven |
| E5 | stack_merge.py:414 | G4: a queue read that is not ok never passes | `test_g4_*` | proven |
| E6 | stack_merge.py:418 | a base with no queue passes, commits unread | `test_no_queue_base_*` | proven |
| E7 | stack_merge.py:428 | G6: a merge commit on a queue base is `stack-not-linear` | `test_dod_*`, `test_g5_queue_true_from_a_failed_read_still_*`, `test_g6_*`, `test_end_to_end_a_merge_*` | proven |
| E8 | stack_merge.py:431 | G7: any other non-ok commit read is `linearity-unreadable` | `test_g7_*` | proven |
| E9 | stack_merge.py:425 | a complete linear read lets the merge go | `test_queue_base_with_linear_*`, `test_g5_queue_true_from_a_failed_read_with_linear_*`, `test_end_to_end_linear_*` | proven |
| E10 | stack_merge.py:459 | the gate runs before the PUT: a refusal sends no request | `test_dod_*` | proven |
| E11 | stack_merge.py:465 | G8: budget spent between the gate and the PUT | `test_g8_budget_*` | proven |
| E12 | stack_merge.py:507 (clause 451) | one budget start shared by the gate, the PUT and the polling | `test_a_slow_gate_shortens_*` | proven |
| E13 | stack_merge.py:396 | the membership call timeout is capped by the time left | `test_the_membership_read_is_capped_*` | proven |
| E14 | stack_merge.py:397 | the membership read carries the deadline | `test_every_read_of_the_gate_*` | proven |
| E15 | stack_merge.py:411 | the merge-queue read carries the invocation deadline | `test_every_read_of_the_gate_*` | proven |
| E16 | stack_merge.py:422 | the commit read carries the invocation deadline | `test_every_read_of_the_gate_*` | proven |
| E17 | stack_merge.py:471 | the PUT's call timeout is capped by the time left after the gate | `test_g8_a_slow_gate_*` | proven |
| E18 | stack_merge.py:418 | only an exact `False` queue answer passes unchecked (G5's strictness) | `test_g5_only_an_exact_false_*` | proven |

## The definition-of-done case: red against the base, green after

The DoD test (`test_dod_queue_base_with_a_merge_commit_is_refused_and_no_request_is_sent`) is a thin wrapper over `_run_dod(module, monkeypatch)`, which runs the scenario (a queue base, a layer with a merge commit) on any `stack_merge` module. A throwaway probe (`probe_dod_base.py`, in the session scratchpad, not in the repository) reads layer 1's unchanged file with `git show 41a46120:plugins/superheroes/lib/stack_merge.py`, compiles it into a fresh module named `stack_merge_base`, and runs the same scenario and the same assertions on it and on the worktree's module. Disclosed deviation from the order: the base source is executed straight from the `git show` text into the module, not written to a scratch file first, because the file-write rule bars writing a file by shell or interpreter; nothing was checked out in the worktree.

```
loaded as stack_merge_base has _linear_gate: False
BASE 41a46120 reason: None merged: True ok: True
BASE 41a46120 put argvs seen: [['gh', 'api', '-X', 'PUT', 'repos/owner/example/pulls/105/merge-async', '-f', 'merge_method=squash', '-f', 'sha=0123456789abcdef0123456789abcdef01234567']]
BASE 41a46120 DoD assertions: FAIL (AssertionError)
WORKTREE reason: stack-not-linear merged: False ok: False
WORKTREE put argvs seen: []
WORKTREE DoD assertions: PASS
```

On the base the merge request is sent and the stack merges; after the change it is refused `stack-not-linear` with no PUT.

---

## E1 — only layers at or below the top are checked (G9)

**neutralization:** `if member_position <= position:` → `if True:  # bite-proof`

**red** (`-k test_g9`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_g9_a_layer_above_the_top_carrying_a_merge_commit_is_ignored _______
/home/user/wt-2459-wo3/plugins/superheroes/lib/tests/test_stack_merge_linear.py:411: in test_g9_a_layer_above_the_top_carrying_a_merge_commit_is_ignored
    _assert_merged(result)
/home/user/wt-2459-wo3/plugins/superheroes/lib/tests/test_stack_merge_linear.py:129: in _assert_merged
    assert result["ok"] is True
E   assert False is True
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_merge_linear.py::test_g9_a_layer_above_the_top_carrying_a_merge_commit_is_ignored
1 failed, 168 deselected in 0.49s
```

**restore:** the inverse edit. **restored line:** `        if member_position <= position:`
**green:**
```
........................................................................ [ 42%]
........................................................................ [ 85%]
.........................                                                [100%]
169 passed in 1.02s
```

---

## E2 — the budget is already spent before the gate (G1)

**neutralization:** `if left <= 0:` (first line after the gate's `left = end - monotonic()`) → `if False:  # bite-proof`

**red** (`-k test_g1`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_g1_budget_already_spent_before_the_gate_reads_nothing_and_sends_nothing _
/home/user/wt-2459-wo3/plugins/superheroes/lib/tests/test_stack_merge_linear.py:280: in test_g1_budget_already_spent_before_the_gate_reads_nothing_and_sends_nothing
    assert env.calls["read_membership"] == []
E   AssertionError: assert [{'pr': 105, ...: -70.0, ...}] == []
E     
E     Left contains one more item: {'pr': 105, 'repo': 'owner/example', 'timeout': -70.0, 'deadline': -70.0, ...}
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_merge_linear.py::test_g1_budget_already_spent_before_the_gate_reads_nothing_and_sends_nothing
1 failed, 168 deselected in 0.55s
```
(The result's reason and detail assertions pass under this neutralization, because the later budget check before the PUT refuses with the same words; the proof is the read made with a negative timeout, which the clause exists to prevent.)

**restore:** the inverse edit. **restored line:** `    if left <= 0:`
**green:**
```
........................................................................ [ 42%]
........................................................................ [ 85%]
.........................                                                [100%]
169 passed in 0.93s
```

---

## E3 — a membership refusal is `linearity-unreadable` and names its reason (G2)

**neutralization:** `if not membership.get("ok"):` → `if False:  # bite-proof`

**red** (`-k test_g2`):
```
FF                                                                       [100%]
=================================== FAILURES ===================================
_ test_g2_membership_refusal_is_linearity_unreadable_and_names_the_reason[not-linked-pull request 105 is not in a native stack] _
/home/user/wt-2459-wo3/plugins/superheroes/lib/tests/test_stack_merge_linear.py:293: in test_g2_membership_refusal_is_linearity_unreadable_and_names_the_reason
    assert result["detail"] == "stack membership: %s: %s" % (reason, detail)
E   AssertionError: assert 'stack member...l request 105' == 'stack member... native stack'
E     
E     - stack membership: not-linked: pull request 105 is not in a native stack
E     + stack membership names no layer at or below pull request 105
_ test_g2_membership_refusal_is_linearity_unreadable_and_names_the_reason[stack-unreadable-graphql refused; rest: gh api exited 1] _
/home/user/wt-2459-wo3/plugins/superheroes/lib/tests/test_stack_merge_linear.py:293: in test_g2_membership_refusal_is_linearity_unreadable_and_names_the_reason
    assert result["detail"] == "stack membership: %s: %s" % (reason, detail)
E   AssertionError: assert 'stack member...l request 105' == 'stack member... native stack'
E     
E     - stack membership: stack-unreadable: graphql refused; rest: gh api exited 1
E     + stack membership names no layer at or below pull request 105
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_merge_linear.py::test_g2_membership_refusal_is_linearity_unreadable_and_names_the_reason[not-linked-pull request 105 is not in a native stack]
FAILED plugins/superheroes/lib/tests/test_stack_merge_linear.py::test_g2_membership_refusal_is_linearity_unreadable_and_names_the_reason[stack-unreadable-graphql refused; rest: gh api exited 1]
2 failed, 167 deselected in 0.56s
```
(The refusal token is the same under this neutralization, because a refusal answer has no stack and the no-layer clause (E4) refuses it; the proof is the detail naming the real membership reason, and what the operator reads.)

**restore:** the inverse edit. **restored line:** `    if not membership.get("ok"):`
**green:**
```
........................................................................ [ 42%]
........................................................................ [ 85%]
.........................                                                [100%]
169 passed in 1.21s
```

---

## E4 — no layer at or below the top can be named (G3)

**neutralization:** `if named is None or not named[1]:` → `if False:  # bite-proof`

**red** (`-k test_g3`):
```
FFFFF                                                                    [100%]
=================================== FAILURES ===================================
_ test_g3_membership_ok_but_no_layer_at_or_below_the_top_is_unreadable[no-members] _
/home/user/wt-2459-wo3/plugins/superheroes/lib/tests/test_stack_merge_linear.py:333: in test_g3_membership_ok_but_no_layer_at_or_below_the_top_is_unreadable
    _assert_refusal(result, "linearity-unreadable")
/home/user/wt-2459-wo3/plugins/superheroes/lib/tests/test_stack_merge_linear.py:121: in _assert_refusal
    assert result["ok"] is False
E   assert True is False
_ test_g3_membership_ok_but_no_layer_at_or_below_the_top_is_unreadable[every-member-above-the-top] _
/home/user/wt-2459-wo3/plugins/superheroes/lib/tests/test_stack_merge_linear.py:333: in test_g3_membership_ok_but_no_layer_at_or_below_the_top_is_unreadable
    _assert_refusal(result, "linearity-unreadable")
/home/user/wt-2459-wo3/plugins/superheroes/lib/tests/test_stack_merge_linear.py:121: in _assert_refusal
    assert result["ok"] is False
E   assert True is False
_ test_g3_membership_ok_but_no_layer_at_or_below_the_top_is_unreadable[member-number-not-an-int] _
/home/user/wt-2459-wo3/plugins/superheroes/lib/tests/test_stack_merge_linear.py:332: in test_g3_membership_ok_but_no_layer_at_or_below_the_top_is_unreadable
    result, calls, run = _go()
                         ^^^^^
/home/user/wt-2459-wo3/plugins/superheroes/lib/tests/test_stack_merge_linear.py:220: in _go
    result = sm.merge(repo=REPO, top=TOP, sha=SHA, run=run, sleep=clock.sleep,
/home/user/wt-2459-wo3/plugins/superheroes/lib/stack_merge.py:456: in merge
    refused = _linear_gate(repo=repo, top=top, end=end, timeout=timeout, run=run,
/home/user/wt-2459-wo3/plugins/superheroes/lib/stack_merge.py:408: in _linear_gate
    base, layers = named
    ^^^^^^^^^^^^
E   TypeError: cannot unpack non-iterable NoneType object
_ test_g3_membership_ok_but_no_layer_at_or_below_the_top_is_unreadable[stack-missing] _
/home/user/wt-2459-wo3/plugins/superheroes/lib/tests/test_stack_merge_linear.py:332: in test_g3_membership_ok_but_no_layer_at_or_below_the_top_is_unreadable
    result, calls, run = _go()
                         ^^^^^
/home/user/wt-2459-wo3/plugins/superheroes/lib/tests/test_stack_merge_linear.py:220: in _go
    result = sm.merge(repo=REPO, top=TOP, sha=SHA, run=run, sleep=clock.sleep,
/home/user/wt-2459-wo3/plugins/superheroes/lib/stack_merge.py:456: in merge
    refused = _linear_gate(repo=repo, top=top, end=end, timeout=timeout, run=run,
/home/user/wt-2459-wo3/plugins/superheroes/lib/stack_merge.py:408: in _linear_gate
    base, layers = named
    ^^^^^^^^^^^^
E   TypeError: cannot unpack non-iterable NoneType object
_ test_g3_membership_ok_but_no_layer_at_or_below_the_top_is_unreadable[base-missing] _
/home/user/wt-2459-wo3/plugins/superheroes/lib/tests/test_stack_merge_linear.py:332: in test_g3_membership_ok_but_no_layer_at_or_below_the_top_is_unreadable
    result, calls, run = _go()
                         ^^^^^
/home/user/wt-2459-wo3/plugins/superheroes/lib/tests/test_stack_merge_linear.py:220: in _go
    result = sm.merge(repo=REPO, top=TOP, sha=SHA, run=run, sleep=clock.sleep,
/home/user/wt-2459-wo3/plugins/superheroes/lib/stack_merge.py:456: in merge
    refused = _linear_gate(repo=repo, top=top, end=end, timeout=timeout, run=run,
/home/user/wt-2459-wo3/plugins/superheroes/lib/stack_merge.py:408: in _linear_gate
    base, layers = named
    ^^^^^^^^^^^^
E   TypeError: cannot unpack non-iterable NoneType object
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_merge_linear.py::test_g3_membership_ok_but_no_layer_at_or_below_the_top_is_unreadable[no-members]
FAILED plugins/superheroes/lib/tests/test_stack_merge_linear.py::test_g3_membership_ok_but_no_layer_at_or_below_the_top_is_unreadable[every-member-above-the-top]
FAILED plugins/superheroes/lib/tests/test_stack_merge_linear.py::test_g3_membership_ok_but_no_layer_at_or_below_the_top_is_unreadable[member-number-not-an-int]
FAILED plugins/superheroes/lib/tests/test_stack_merge_linear.py::test_g3_membership_ok_but_no_layer_at_or_below_the_top_is_unreadable[stack-missing]
FAILED plugins/superheroes/lib/tests/test_stack_merge_linear.py::test_g3_membership_ok_but_no_layer_at_or_below_the_top_is_unreadable[base-missing]
5 failed, 164 deselected in 0.77s
```
(`no-members` and `every-member-above-the-top` are the clean reds: with no layer named, the neutralized gate went on to merge.)

**restore:** the inverse edit. **restored line:** `    if named is None or not named[1]:`
**green:**
```
........................................................................ [ 42%]
........................................................................ [ 85%]
.........................                                                [100%]
169 passed in 1.30s
```

---

## E5 — a queue read that is not ok never passes (G4)

**neutralization:** `if not queue.get("ok"):` → `if False:  # bite-proof`

**red** (`-k test_g4`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
______ test_g4_queue_read_not_ok_is_linearity_unreadable_and_never_passes ______
/home/user/wt-2459-wo3/plugins/superheroes/lib/tests/test_stack_merge_linear.py:343: in test_g4_queue_read_not_ok_is_linearity_unreadable_and_never_passes
    _assert_refusal(result, "linearity-unreadable")
/home/user/wt-2459-wo3/plugins/superheroes/lib/tests/test_stack_merge_linear.py:121: in _assert_refusal
    assert result["ok"] is False
E   assert True is False
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_merge_linear.py::test_g4_queue_read_not_ok_is_linearity_unreadable_and_never_passes
1 failed, 168 deselected in 0.66s
```

**restore:** the inverse edit. **restored line:** `    if not queue.get("ok"):`
**green:**
```
........................................................................ [ 42%]
........................................................................ [ 85%]
.........................                                                [100%]
169 passed in 0.84s
```

---

## E6 — a base with no queue passes with its commits unread

**neutralization:** `if queue.get("queue") is False:` → `if False:  # bite-proof`

**red** (`-k test_no_queue_base`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_no_queue_base_merges_as_before_and_never_reads_commits __________
/home/user/wt-2459-wo3/plugins/superheroes/lib/tests/test_stack_merge_linear.py:261: in test_no_queue_base_merges_as_before_and_never_reads_commits
    _assert_merged(result)
/home/user/wt-2459-wo3/plugins/superheroes/lib/tests/test_stack_merge_linear.py:129: in _assert_merged
    assert result["ok"] is True
E   assert False is True
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_merge_linear.py::test_no_queue_base_merges_as_before_and_never_reads_commits
1 failed, 168 deselected in 0.56s
```

**restore:** the inverse edit. **restored line:** `    if queue.get("queue") is False:`
**green:**
```
........................................................................ [ 42%]
........................................................................ [ 85%]
.........................                                                [100%]
169 passed in 0.89s
```

---

## E7 — a merge commit on a queue base is `stack-not-linear` (G6)

**neutralization:** `if linear.get("reason") == stack_linear.REASON_STACK_NOT_LINEAR:` → `if False:  # bite-proof`

**red** (`-k "test_dod or test_g5_queue_true_from_a_failed_read_still or test_g6 or test_end_to_end_a_merge"`, run with `--tb=line`):
```
FFFFF                                                                    [100%]
=================================== FAILURES ===================================
E   AssertionError: assert 'linearity-unreadable' == 'stack-not-linear'
      
      - stack-not-linear
      + linearity-unreadable
/home/user/wt-2459-wo3/plugins/superheroes/lib/tests/test_stack_merge_linear.py:123: AssertionError: assert 'linearity-unreadable' == 'stack-not-linear'
E   AssertionError: assert 'linearity-unreadable' == 'stack-not-linear'
      
      - stack-not-linear
      + linearity-unreadable
/home/user/wt-2459-wo3/plugins/superheroes/lib/tests/test_stack_merge_linear.py:123: AssertionError: assert 'linearity-unreadable' == 'stack-not-linear'
E   AssertionError: assert 'linearity-unreadable' == 'stack-not-linear'
      
      - stack-not-linear
      + linearity-unreadable
/home/user/wt-2459-wo3/plugins/superheroes/lib/tests/test_stack_merge_linear.py:123: AssertionError: assert 'linearity-unreadable' == 'stack-not-linear'
E   AssertionError: assert 'linearity-unreadable' == 'stack-not-linear'
      
      - stack-not-linear
      + linearity-unreadable
/home/user/wt-2459-wo3/plugins/superheroes/lib/tests/test_stack_merge_linear.py:123: AssertionError: assert 'linearity-unreadable' == 'stack-not-linear'
E   AssertionError: assert 'linearity-unreadable' == 'stack-not-linear'
      
      - stack-not-linear
      + linearity-unreadable
/home/user/wt-2459-wo3/plugins/superheroes/lib/tests/test_stack_merge_linear.py:123: AssertionError: assert 'linearity-unreadable' == 'stack-not-linear'
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_merge_linear.py::test_dod_queue_base_with_a_merge_commit_is_refused_and_no_request_is_sent
FAILED plugins/superheroes/lib/tests/test_stack_merge_linear.py::test_g5_queue_true_from_a_failed_read_still_checks_the_commits
FAILED plugins/superheroes/lib/tests/test_stack_merge_linear.py::test_g6_a_merge_commit_on_a_queue_base_is_stack_not_linear_with_the_readers_detail
FAILED plugins/superheroes/lib/tests/test_stack_merge_linear.py::test_end_to_end_a_merge_commit_on_an_assumed_queue_base_sends_no_put[merge-commit-in-the-top]
FAILED plugins/superheroes/lib/tests/test_stack_merge_linear.py::test_end_to_end_a_merge_commit_on_an_assumed_queue_base_sends_no_put[merge-commit-in-the-lower]
5 failed, 164 deselected in 0.61s
```
(The end-to-end test, with only `run` faked, goes red here too, so the recorded REST fixtures and the real three readers reach this clause.)

**restore:** the inverse edit. **restored line:** `    if linear.get("reason") == stack_linear.REASON_STACK_NOT_LINEAR:`
**green:**
```
........................................................................ [ 42%]
........................................................................ [ 85%]
.........................                                                [100%]
169 passed in 0.76s
```

---

## E8 — any other non-ok commit read is `linearity-unreadable` (G7)

**neutralization:** the final `return (REASON_LINEARITY_UNREADABLE, "%s: %s" % (linear.get("reason"), linear.get("detail")))` → `return None  # bite-proof`

**red** (`-k test_g7`, run with `--tb=line`):
```
FF                                                                       [100%]
=================================== FAILURES ===================================
E   assert True is False
/home/user/wt-2459-wo3/plugins/superheroes/lib/tests/test_stack_merge_linear.py:121: assert True is False
E   assert True is False
/home/user/wt-2459-wo3/plugins/superheroes/lib/tests/test_stack_merge_linear.py:121: assert True is False
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_merge_linear.py::test_g7_a_commit_read_that_is_not_ok_and_not_a_merge_commit_is_unreadable[linearity-unreadable]
FAILED plugins/superheroes/lib/tests/test_stack_merge_linear.py::test_g7_a_commit_read_that_is_not_ok_and_not_a_merge_commit_is_unreadable[bad-argument]
2 failed, 167 deselected in 0.49s
```

**restore:** the inverse edit. **restored line:** `    return (REASON_LINEARITY_UNREADABLE, "%s: %s" % (linear.get("reason"), linear.get("detail")))`
**green:**
```
........................................................................ [ 42%]
........................................................................ [ 85%]
.........................                                                [100%]
169 passed in 0.80s
```

---

## E9 — a complete linear read lets the merge go

**neutralization:** `if linear.get("ok") is True:` → `if False:  # bite-proof`

**red** (`-k "test_queue_base_with_linear or test_g5_queue_true_from_a_failed_read_with_linear or test_end_to_end_linear"`, run with `--tb=line`):
```
FFF                                                                      [100%]
=================================== FAILURES ===================================
E   assert False is True
/home/user/wt-2459-wo3/plugins/superheroes/lib/tests/test_stack_merge_linear.py:129: assert False is True
E   assert False is True
/home/user/wt-2459-wo3/plugins/superheroes/lib/tests/test_stack_merge_linear.py:129: assert False is True
E   assert False is True
/home/user/wt-2459-wo3/plugins/superheroes/lib/tests/test_stack_merge_linear.py:129: assert False is True
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_merge_linear.py::test_queue_base_with_linear_layers_sends_the_put_and_merges
FAILED plugins/superheroes/lib/tests/test_stack_merge_linear.py::test_g5_queue_true_from_a_failed_read_with_linear_layers_merges
FAILED plugins/superheroes/lib/tests/test_stack_merge_linear.py::test_end_to_end_linear_layers_on_an_assumed_queue_base_send_the_put_and_merge
3 failed, 166 deselected in 0.56s
```

**restore:** the inverse edit. **restored line:** `    if linear.get("ok") is True:`
**green:**
```
........................................................................ [ 42%]
........................................................................ [ 85%]
.........................                                                [100%]
169 passed in 1.03s
```

---

## E10 — the gate runs before the PUT: a refusal sends no request

**neutralization:** `if refused is not None:` → `if False:  # bite-proof` (the gate's verdict is ignored)

**red** (`-k test_dod`, run with `--tb=line`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
E   assert True is False
/home/user/wt-2459-wo3/plugins/superheroes/lib/tests/test_stack_merge_linear.py:121: assert True is False
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_merge_linear.py::test_dod_queue_base_with_a_merge_commit_is_refused_and_no_request_is_sent
1 failed, 168 deselected in 0.57s
```

**restore:** the inverse edit. **restored line:** `    if refused is not None:`
**green:**
```
........................................................................ [ 42%]
........................................................................ [ 85%]
.........................                                                [100%]
169 passed in 0.88s
```

---

## E11 — the budget ran out between the gate and the PUT (G8)

**neutralization:** `if put_left <= 0:` → `if False:  # bite-proof`

**red** (`-k test_g8_budget`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_g8_budget_spent_between_the_gate_and_the_put_sends_nothing ________
/home/user/wt-2459-wo3/plugins/superheroes/lib/tests/test_stack_merge_linear.py:387: in test_g8_budget_spent_between_the_gate_and_the_put_sends_nothing
    _assert_refusal(result, "linearity-unreadable")
/home/user/wt-2459-wo3/plugins/superheroes/lib/tests/test_stack_merge_linear.py:121: in _assert_refusal
    assert result["ok"] is False
E   assert True is False
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_merge_linear.py::test_g8_budget_spent_between_the_gate_and_the_put_sends_nothing
1 failed, 168 deselected in 0.48s
```

**restore:** the inverse edit. **restored line:** `    if put_left <= 0:`
**green:**
```
........................................................................ [ 42%]
........................................................................ [ 85%]
.........................                                                [100%]
169 passed in 0.81s
```

---

## E12 — one budget start is shared by the gate, the PUT and the polling

**neutralization:** in the `_poll_loop` call at the end of `merge`, the `start` argument → `monotonic()` (the polling budget then starts after the gate and the PUT instead of before the gate): `return _poll_loop(repo, top, sha, read["uuid"], start, poll_timeout,` → `return _poll_loop(repo, top, sha, read["uuid"], monotonic(), poll_timeout,  # bite-proof`

**red** (`-k test_a_slow_gate_shortens`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_______________ test_a_slow_gate_shortens_the_polling_budget_too _______________
/home/user/wt-2459-wo3/plugins/superheroes/lib/tests/test_stack_merge_linear.py:453: in test_a_slow_gate_shortens_the_polling_budget_too
    assert clock.sleeps == [5, 5]
E   assert [5, 5, 5, 5, 5, 5] == [5, 5]
E     
E     Left contains 4 more items, first extra item: 5
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_merge_linear.py::test_a_slow_gate_shortens_the_polling_budget_too
1 failed, 168 deselected in 0.47s
```

**restore:** the inverse edit. **restored line:** `    return _poll_loop(repo, top, sha, read["uuid"], start, poll_timeout,`
**green:**
```
........................................................................ [ 42%]
........................................................................ [ 85%]
.........................                                                [100%]
169 passed in 0.88s
```

---

## E13 — the membership call timeout is capped by the time left

**neutralization:** `timeout=min(timeout, left),` (the `read_membership` call) → `timeout=timeout,  # bite-proof`

**red** (`-k test_the_membership_read_is_capped`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_the_membership_read_is_capped_by_the_time_left ______________
/home/user/wt-2459-wo3/plugins/superheroes/lib/tests/test_stack_merge_linear.py:443: in test_the_membership_read_is_capped_by_the_time_left
    assert env.calls["read_membership"][0]["timeout"] == 30
E   assert 120 == 30
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_merge_linear.py::test_the_membership_read_is_capped_by_the_time_left
1 failed, 168 deselected in 1.12s
```

**restore:** the inverse edit. **restored line:** `    membership = stack_check.read_membership(pr=top, repo=repo, timeout=min(timeout, left),`
**green:**
```
........................................................................ [ 42%]
........................................................................ [ 85%]
.........................                                                [100%]
169 passed in 1.08s
```

---

## E14 — the membership read carries the deadline

**neutralization:** `deadline=left, run=run)` (the `read_membership` call) → `deadline=None, run=run)  # bite-proof`

**red** (`-k test_every_read_of_the_gate`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_every_read_of_the_gate_shares_the_one_deadline_and_the_one_run ______
/home/user/wt-2459-wo3/plugins/superheroes/lib/tests/test_stack_merge_linear.py:424: in test_every_read_of_the_gate_shares_the_one_deadline_and_the_one_run
    assert membership_kw["deadline"] == 30
E   assert None == 30
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_merge_linear.py::test_every_read_of_the_gate_shares_the_one_deadline_and_the_one_run
1 failed, 168 deselected in 0.51s
```

**restore:** the inverse edit. **restored line:** `                                             deadline=left, run=run)`
**green:**
```
........................................................................ [ 42%]
........................................................................ [ 85%]
.........................                                                [100%]
169 passed in 0.93s
```

---

## E15 — the merge-queue read carries the invocation deadline

**neutralization:** `deadline_at=end,` (the `merge_queue.read` call) → `deadline_at=None,  # bite-proof`

**red** (`-k test_every_read_of_the_gate`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_every_read_of_the_gate_shares_the_one_deadline_and_the_one_run ______
/home/user/wt-2459-wo3/plugins/superheroes/lib/tests/test_stack_merge_linear.py:429: in test_every_read_of_the_gate_shares_the_one_deadline_and_the_one_run
    assert queue_kw["deadline_at"] == 30
E   assert None == 30
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_merge_linear.py::test_every_read_of_the_gate_shares_the_one_deadline_and_the_one_run
1 failed, 168 deselected in 0.55s
```

**restore:** the inverse edit. **restored line:** `    queue = merge_queue.read(repo=repo, branch=base, timeout=timeout, deadline_at=end,`
**green:**
```
........................................................................ [ 42%]
........................................................................ [ 85%]
.........................                                                [100%]
169 passed in 1.13s
```

---

## E16 — the commit read carries the invocation deadline

**neutralization:** `deadline_at=end,` (the `stack_linear.check_rest` call) → `deadline_at=None,  # bite-proof`

**red** (`-k test_every_read_of_the_gate`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_every_read_of_the_gate_shares_the_one_deadline_and_the_one_run ______
/home/user/wt-2459-wo3/plugins/superheroes/lib/tests/test_stack_merge_linear.py:435: in test_every_read_of_the_gate_shares_the_one_deadline_and_the_one_run
    assert linear_kw["deadline_at"] == 30
E   assert None == 30
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_merge_linear.py::test_every_read_of_the_gate_shares_the_one_deadline_and_the_one_run
1 failed, 168 deselected in 0.56s
```

**restore:** the inverse edit. **restored line:** `    linear = stack_linear.check_rest(repo=repo, prs=layers, timeout=timeout, deadline_at=end,`
**green:**
```
........................................................................ [ 42%]
........................................................................ [ 85%]
.........................                                                [100%]
169 passed in 0.96s
```

---

## E17 — the PUT's call timeout is capped by the time left after the gate

**neutralization:** `timeout=min(timeout, put_left))` (the PUT call) → `timeout=timeout)  # bite-proof`

**red** (`-k test_g8_a_slow_gate`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_g8_a_slow_gate_leaves_the_put_only_the_time_left _____________
/home/user/wt-2459-wo3/plugins/superheroes/lib/tests/test_stack_merge_linear.py:400: in test_g8_a_slow_gate_leaves_the_put_only_the_time_left
    assert run.kw_calls[0]["timeout"] == 5.0
E   assert 120 == 5.0
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_merge_linear.py::test_g8_a_slow_gate_leaves_the_put_only_the_time_left
1 failed, 168 deselected in 0.61s
```

**restore:** the inverse edit. **restored line:** `                   timeout=min(timeout, put_left))`
**green:**
```
........................................................................ [ 42%]
........................................................................ [ 85%]
.........................                                                [100%]
169 passed in 0.90s
```

---

## E18 — only an exact `False` queue answer passes unchecked (G5's strictness)

G5 ("`queue: true` from `read-failed` must still check") has no clause of its own: a `queue: true` answer reaches the commit read whatever its source, so the two G5 tests pass under any neutralization of E6's `is False`. What the code can get wrong is the looser test (`not queue`), under which an `ok` answer whose `queue` is `None`, `0` or empty would pass unchecked. **Disclosed addition:** the first full run found no test for that, so `test_g5_only_an_exact_false_queue_answer_passes_unchecked` (None, 0, "false", "") was added, and the full run after it is 173 passed.

**neutralization:** `if queue.get("queue") is False:` → `if not queue.get("queue"):  # bite-proof`

**red** (`-k test_g5_only_an_exact_false`):
```
FF.F                                                                     [100%]
=================================== FAILURES ===================================
_______ test_g5_only_an_exact_false_queue_answer_passes_unchecked[None] ________
/home/user/wt-2459-wo3/plugins/superheroes/lib/tests/test_stack_merge_linear.py:370: in test_g5_only_an_exact_false_queue_answer_passes_unchecked
    _assert_refusal(result, "stack-not-linear")
/home/user/wt-2459-wo3/plugins/superheroes/lib/tests/test_stack_merge_linear.py:121: in _assert_refusal
    assert result["ok"] is False
E   assert True is False
_________ test_g5_only_an_exact_false_queue_answer_passes_unchecked[0] _________
/home/user/wt-2459-wo3/plugins/superheroes/lib/tests/test_stack_merge_linear.py:370: in test_g5_only_an_exact_false_queue_answer_passes_unchecked
    _assert_refusal(result, "stack-not-linear")
/home/user/wt-2459-wo3/plugins/superheroes/lib/tests/test_stack_merge_linear.py:121: in _assert_refusal
    assert result["ok"] is False
E   assert True is False
_________ test_g5_only_an_exact_false_queue_answer_passes_unchecked[] __________
/home/user/wt-2459-wo3/plugins/superheroes/lib/tests/test_stack_merge_linear.py:370: in test_g5_only_an_exact_false_queue_answer_passes_unchecked
    _assert_refusal(result, "stack-not-linear")
/home/user/wt-2459-wo3/plugins/superheroes/lib/tests/test_stack_merge_linear.py:121: in _assert_refusal
    assert result["ok"] is False
E   assert True is False
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_merge_linear.py::test_g5_only_an_exact_false_queue_answer_passes_unchecked[None]
FAILED plugins/superheroes/lib/tests/test_stack_merge_linear.py::test_g5_only_an_exact_false_queue_answer_passes_unchecked[0]
FAILED plugins/superheroes/lib/tests/test_stack_merge_linear.py::test_g5_only_an_exact_false_queue_answer_passes_unchecked[]
3 failed, 1 passed, 169 deselected in 0.54s
```
(The one pass is the `"false"` string, which is truthy and so is checked either way.)

**restore:** the inverse edit. **restored line:** `    if queue.get("queue") is False:`
**green:**
```
........................................................................ [ 41%]
........................................................................ [ 83%]
.............................                                            [100%]
173 passed in 1.02s
```

---

## Restore receipt

A search for `bite-proof` over `plugins/superheroes/lib/stack_merge.py` after the last restore returns no matches, so no neutralization is left in the source. Every restore was the inverse edit through the Edit tool; no `git checkout`, `git restore`, `git reset` or `git stash` was used.
