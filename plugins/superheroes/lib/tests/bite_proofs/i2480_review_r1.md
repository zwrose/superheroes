# Review round 1 (#2480) bite-proof — the never-fits hold and the unmerged layer count

Per-guard bite proof for the guards the review's round-1 fixes added to
`plugins/superheroes/lib/merge_queue.py` and `plugins/superheroes/lib/stack_merge.py`, typed by the
build session at the review's fix step (maker family anthropic). Each guard was neutralized by a
one-line replacement in a detached, disposable probe worktree at commit `d2baa622`, the scoped
tests were run and showed red, the line was restored, the tests ran green again, and the probe
worktree's `git status --short` was empty at the end.

**Register:** 5 guarded elements.

| ID | Guarded element | Axis | Proving test(s) | Verdict |
|---|---|---|---|---|
| N1 | `merge_queue.py`, `if layers > limit:` | more layers than the build limit is `slots-never-fits` | `test_d5_limit_zero_can_never_fit_one_layer`, `test_more_layers_than_the_build_limit_can_never_fit_even_on_an_empty_queue`, `test_more_layers_than_the_limit_on_a_busy_queue_is_never_fits_not_short`, `test_the_slots_cli_exits_one_on_never_fits` | proven |
| N2 | `stack_merge.py`, `if member.get("state") != "MERGED":` | a merged layer needs no build slot | `test_a_merged_layer_needs_no_build_slot`, `test_a_stack_with_every_layer_merged_needs_no_slot_and_reads_none` | proven |
| N3 | `stack_merge.py`, `if unmerged == 0:` | an all-merged stack needs no slot and reads none | `test_a_stack_with_every_layer_merged_needs_no_slot_and_reads_none` | proven |
| N4 | `stack_merge.py`, the `slots-never-fits` mapping | `slots-never-fits` is `queue-slots-never-fits` | `test_slots_never_fits_is_queue_slots_never_fits_with_its_detail_and_no_request` | proven |
| N5 | `stack_merge.py`, `layers=unmerged` | the slot count is the unmerged count | `test_a_merged_layer_needs_no_build_slot` | proven |

**Command** (every red and every green):

```
scripts/pinned-python -B -m pytest plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py plugins/superheroes/lib/tests/test_stack_merge_linear.py plugins/superheroes/lib/tests/test_stack_merge.py -q -p no:cacheprovider --tb=no -rf
```

**Captures** (summary and failed-test lines, word for word; uv's `UV_NATIVE_TLS` notice omitted;
nothing needed redaction):

```
baseline green: exit 0: 425 passed in 1.69s
N1 more layers than the limit is slots-never-fits (merge_queue.py)
    neutralized: 'if layers > limit:' -> 'if False:'
    red: exit 1: 4 failed, 421 passed in 1.62s
      FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_d5_limit_zero_can_never_fit_one_layer
      FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_more_layers_than_the_build_limit_can_never_fit_even_on_an_empty_queue
      FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_more_layers_than_the_limit_on_a_busy_queue_is_never_fits_not_short
      FAILED plugins/superheroes/lib/tests/test_merge_queue_slots_2480.py::test_the_slots_cli_exits_one_on_never_fits
    green after restore: exit 0: 425 passed in 1.65s
N2 a merged layer needs no slot (stack_merge.py)
    neutralized: 'if member.get("state") != "MERGED":' -> 'if True:'
    red: exit 1: 2 failed, 423 passed in 1.81s
      FAILED plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py::test_a_merged_layer_needs_no_build_slot
      FAILED plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py::test_a_stack_with_every_layer_merged_needs_no_slot_and_reads_none
    green after restore: exit 0: 425 passed in 1.67s
N3 an all-merged stack needs no slot (stack_merge.py)
    neutralized: 'if unmerged == 0:' -> 'if False:'
    red: exit 1: 1 failed, 424 passed in 1.76s
      FAILED plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py::test_a_stack_with_every_layer_merged_needs_no_slot_and_reads_none
    green after restore: exit 0: 425 passed in 1.85s
N4 slots-never-fits maps to queue-slots-never-fits (stack_merge.py)
    neutralized: 'and slots.get("reason") == merge_queue.REASON_SLOTS_NEVER_FITS):' -> 'and False):'
    red: exit 1: 1 failed, 424 passed in 1.74s
      FAILED plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py::test_slots_never_fits_is_queue_slots_never_fits_with_its_detail_and_no_request
    green after restore: exit 0: 425 passed in 1.81s
N5 the slot count is the unmerged count (stack_merge.py)
    neutralized: 'layers=unmerged, timeout=timeout,' -> 'layers=len(layers), timeout=timeout,'
    red: exit 1: 1 failed, 424 passed in 1.89s
      FAILED plugins/superheroes/lib/tests/test_stack_merge_slots_2480.py::test_a_merged_layer_needs_no_build_slot
    green after restore: exit 0: 425 passed in 1.93s
git status after restore: ''
```

**Disclosure.** The probes were made by a script doing one-line replacements in the disposable
probe worktree rather than through the edit tool, so the five probes fit one call; each was
restored and the tree was checked clean.
