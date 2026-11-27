# #2674 bite-proofs — recovery keeps a not-yet-linked stack layer's stack binding

Detector file: `plugins/superheroes/lib/tests/test_cloud_recover.py` (the `test_i2674_*` tests). Production file
neutralized: `plugins/superheroes/lib/cloud_recover.py`. Every neutralization is a targeted edit of one production
line, made after the fix was committed and undone by the inverse edit; `git status --porcelain` read empty after the
last restore. Command for every run below (`$W` is the build worktree root):

```
$W/scripts/pinned-python -B -X pycache_prefix=<scratch> -m pytest $W/plugins/superheroes/lib/tests/test_cloud_recover.py -q -k i2674 -p no:randomly
```

Captures are trimmed to the failing assertion and the summary; the tmp paths are the sandbox's. Nothing in them is
secret.

## (a) The old no-stack reading restored — axis: a pre-link layer is read as the layer, or the successor waits

**Guarded element:** `cloud_recover.py:788` `elif not got["ok"]:` in `successor`, the branch that reads a
`not-linked` stack membership answer through the issue's timeline.

**Neutralization:** `elif not got["ok"]:` became `elif False:`, which is the code before this fix: a `not-linked`
answer falls through, so the successor is composed with no `adopts` and the supersession is recorded.

**Detector:** `test_i2674_a_recovered_pre_link_layer_keeps_its_stack_binding` (the DoD's pre-link test), with the
unreadable-timeline and no-cross-reference tests.

**Red:**
```
>       assert (premise["stack"], premise["layerPosition"], premise["adopts"]) == (2, 2, 99)
E       KeyError: 'adopts'
...
>       assert (got["ok"], got["reason"], got["pr"], got["why"]) == (False, "layer-link-pending", 99, "timeline-unreadable")
E       KeyError: 'reason'
...
10 failed, 2 passed, 125 deselected in 4.19s
```

The two that pass are the plain-lane and linked-layer tests, which this branch never reaches.

**Restore:** inverse edit, `elif False:` back to `elif not got["ok"]:`.

## (b) Any cross-reference confirms the layer — axis: only this PR of this repository confirms it

**Guarded element:** `cloud_recover.py:648` `found = found or (number == pr and name.lower() == repo.lower())`.

**Neutralization:** the line became `found = found or True`.

**Red:**
```
FAILED ...::test_i2674_a_timeline_with_no_cross_reference_from_the_pull_request_holds_the_successor[timeline1]
FAILED ...::test_i2674_a_timeline_with_no_cross_reference_from_the_pull_request_holds_the_successor[timeline2]
2 failed, 10 passed, 125 deselected in 7.46s
```

`timeline1` is another pull request's cross-reference; `timeline2` is another repository's pull request 99.

**Restore:** inverse edit.

## (c) A row whose event cannot be read is skipped — axis: a malformed row is unreadable, never skipped

**Guarded element:** `cloud_recover.py:633` `return None` under `if not isinstance(event, str) or not event.strip():`.

**Neutralization:** `return None` became `continue`.

**Red:**
```
FAILED ...::test_i2674_an_unreadable_timeline_holds_the_successor_with_a_named_reason[timeline2]
FAILED ...::test_i2674_an_unreadable_timeline_holds_the_successor_with_a_named_reason[timeline3]
2 failed, 10 passed, 125 deselected in 7.45s
```

`timeline2` has a row with a blank event and `timeline3` a row that is not an object, each before a valid
cross-reference from the PR: skipped, they would confirm the layer from a partly unreadable timeline.

**Restore:** inverse edit.

## Green (after the last restore)

```
............                                                             [100%]
12 passed, 125 deselected in 4.42s
```
