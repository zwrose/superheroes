# #1590 WO-D bite-proof: the calibration read in `collect` ignores inherited git routing variables

Bite-proof record for `plugins/superheroes/lib/size_count.py` (`_git_routing_scrubbed_environ`, the `with` around `core_md.read_size_exclude` in `collect`). Detector: `plugins/superheroes/lib/tests/test_size_count_exclusions_1583.py` (`T`).

**Status.** The implementer ran the proof (D1): the neutralization is a targeted Edit, the red is the named node run alone, the restore is the inverse Edit, and the green is the same node.

- **Run command.** `scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest "<path>::<node>" -q`.

## Declared guarded-element set

D1 the scrub around the calibration read.

## Per-element receipts

### D1: the scrub around the calibration read (isolation)

- **Neutralization applied.** In `_git_routing_scrubbed_environ`, the line `    saved = {k: os.environ.pop(k) for k in _GIT_ROUTING_VARS if k in os.environ}` replaced by `    saved = {}`, so nothing is popped and the read sees repository B's `GIT_DIR` and `GIT_WORK_TREE`.
- **Node.** `T::test_calibration_read_ignores_inherited_routing_env`
- **Red** (the result carries B's `*` exclusion: `tripwireCount` 0 against 4, `pathsExcluded` naming `src/a-file` with glob `*`):

```
E       AssertionError: assert {'tripwireCou...ary': [], ...} == {'tripwireCou...ary': [], ...}
E         
E         Omitting 5 identical items, use -vv to show
E         Differing items:
E         {'tripwireCount': 0} != {'tripwireCount': 4}
E         {'barCount': 0} != {'barCount': 4}
E         Left contains 1 more item:
E         {'pathsExcluded': [{'glob': '*', 'lines': 4, 'path': 'src/a-file'}]}
E         Use -v to get more diff
FAILED plugins/superheroes/lib/tests/test_size_count_exclusions_1583.py::test_calibration_read_ignores_inherited_routing_env
1 failed in 1.55s
```

- **Restore.** The inverse Edit; quoted from `size_count.py:202`: `    saved = {k: os.environ.pop(k) for k in _GIT_ROUTING_VARS if k in os.environ}`.
- **Green.**

```
.                                                                        [100%]
1 passed in 3.31s
```
