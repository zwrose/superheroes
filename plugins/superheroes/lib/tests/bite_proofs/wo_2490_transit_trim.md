# #2490 bite-proof — the transit comparison trims the common prefix and suffix

**Provenance:** implementer work order WO3 (issue 2490) / `lib/cloud_builder.py` (`_transit_changes`, `transit_compare`), `lib/tests/test_transit_compare_trim_2490.py`. Worktree head `dd4e94c8e95fcf3f614b7d8cd80c15c1e707e9aa`, working tree uncommitted.

Declared guarded elements (from the order): G13 the shift by `p` of reported positions; G14 the cap on `s`; G15 the trim itself. Each was neutralized with one targeted Edit, run alone against its named detector by exact node id (unedited), restored with the inverse Edit (never `git checkout`, `restore`, `reset` or `stash`), and the same node then ran green. Every run was `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2490 -m pytest <node> -q -p no:cacheprovider` from the worktree root. The captures are unfiltered except that the launcher's one-line `UV_NATIVE_TLS` deprecation warning (the first line of every real run) was dropped. They hold no secrets, tokens, private URLs or PII; the only paths are repository paths; nothing was redacted. Each neutralized target was asserted to occur exactly once before the edit (a content search returned one match).

| ID | Guarded element | Axis | Detector (exact node id, in `test_transit_compare_trim_2490.py`) |
|---|---|---|---|
| G13 | `cloud_builder.py:702`, `_transit_changes`, the `+ p` shift of the reported positions | a change inside a trimmed body is reported at its position in the whole body, not in the middle | `test_trimmed_equals_untrimmed[middle]` |
| G14 | `cloud_builder.py:692`, `_transit_changes`, the cap `min(len(a), len(b)) - p` on the suffix length | the prefix and the suffix never overlap, so the middle is never negative and no edit is lost | `test_trimmed_equals_untrimmed[e7-aaa-aa]` |
| G15 | `cloud_builder.py:735`, `transit_compare`'s call `_transit_changes(a, b, trim=True)` | a full-size part with one changed character compares in seconds, not tens of seconds | `test_a_full_size_part_with_one_changed_character_compares_fast` |

Not separately neutralized, so unproven by this record: the `[a[::-1], b[::-1]]` reversal (the suffix computation other than its cap), the `TRANSIT_MAX_CHANGES` cap and `TRANSIT_EXCERPT_CHARS` (unchanged lines, asserted by `more-changes-than-the-cap` and the existing suite), the `+ p` on the end offsets `i2` and `j2` (G13 drops only the start offsets, as ordered; the excerpts a changed `i2`/`j2` would slice are not asserted by a separate node here), and the ambiguous-placement test (`test_trim_may_place_an_ambiguous_edit_elsewhere_but_counts_the_same`, which pins a known limit and was not run against a mutation).

---

## G13 — the shift by `p`

**neutralization** (`cloud_builder.py:702`, `_transit_changes`; the start offsets lose `+ p`, the end offsets keep it):
```python
-            i1, i2, j1, j2 = i1 + p, i2 + p, j1 + p, j2 + p
+            i1, i2, j1, j2 = i1, i2 + p, j1, j2 + p
```

**raw red** (axis check: the red is on the reported position — the trimmed `at` is 0 and `line` is 1 where the whole-body run says `at` 2065, `line` 46 — not on a count; both counts are 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
____________________ test_trimmed_equals_untrimmed[middle] _____________________

a = 'line 0000 rec value 0 of the record, ref 00\nline 0001 rec value 856 of the record, ref 31\nline 0002 rec value 703 o...15 of the record, ref 78\nline 0088 rec value 662 of the record, ref 12\nline 0089 rec value 509 of the record, ref 43'
b = 'line 0000 rec value 0 of the record, ref 00\nline 0001 rec value 856 of the record, ref 31\nline 0002 rec value 703 o...15 of the record, ref 78\nline 0088 rec value 662 of the record, ref 12\nline 0089 rec value 509 of the record, ref 43'

    @pytest.mark.parametrize("a, b", [(a, b) for _, a, b in DIFFERING], ids=[i for i, _, _ in DIFFERING])
    def test_trimmed_equals_untrimmed(a, b):
        assert a != b
        trimmed = cb._transit_changes(a, b, trim=True)
>       assert trimmed == cb._transit_changes(a, b, trim=False)
E       AssertionError: assert (1, [{'line':...001 rec va'}]) == (1, [{'line':...found': '#'}])
E         
E         At index 1 diff: [{'line': 1, 'at': 0, 'sent': 'line 0000 rec value 0 of the record, ref 00\nline 0001 rec va', 'found': 'line 0000 rec value 0 of the record, ref 00\nline 0001 rec va'}] != [{'line': 46, 'at': 2065, 'sent': 'l', 'found': '#'}]
E         Use -v to get more diff

/home/user/wt-2490/plugins/superheroes/lib/tests/test_transit_compare_trim_2490.py:93: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_transit_compare_trim_2490.py::test_trimmed_equals_untrimmed[middle]
1 failed in 2.48s
```

**restore:** the inverse Edit put `+ p` back on `i1` and `j1`.

**restore receipt** (restored content, `cloud_builder.py:702`):
```python
            i1, i2, j1, j2 = i1 + p, i2 + p, j1 + p, j2 + p
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.34s
```

---

## G14 — the cap on `s`

**neutralization** (`cloud_builder.py:692`, `_transit_changes`; the cap is removed):
```python
-        s = min(len(os.path.commonprefix([a[::-1], b[::-1]])), min(len(a), len(b)) - p)
+        s = len(os.path.commonprefix([a[::-1], b[::-1]]))
```

**raw red** (axis check: for `a = "aaa"`, `b = "aa"` the prefix is 2 and the uncapped suffix is 2, so the middle is empty on both sides and the trimmed run loses the edit — count 0 where the whole-body run says 1; the red is on the overlap, not on a position):
```
F                                                                        [100%]
=================================== FAILURES ===================================
___________________ test_trimmed_equals_untrimmed[e7-aaa-aa] ___________________

a = 'aaa', b = 'aa'

    @pytest.mark.parametrize("a, b", [(a, b) for _, a, b in DIFFERING], ids=[i for i, _, _ in DIFFERING])
    def test_trimmed_equals_untrimmed(a, b):
        assert a != b
        trimmed = cb._transit_changes(a, b, trim=True)
>       assert trimmed == cb._transit_changes(a, b, trim=False)
E       AssertionError: assert (0, []) == (1, [{'line':...'found': ''}])
E         
E         At index 0 diff: 0 != 1
E         Use -v to get more diff

/home/user/wt-2490/plugins/superheroes/lib/tests/test_transit_compare_trim_2490.py:93: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_transit_compare_trim_2490.py::test_trimmed_equals_untrimmed[e7-aaa-aa]
1 failed in 0.22s
```

**restore:** the inverse Edit put `min(..., min(len(a), len(b)) - p)` back.

**restore receipt** (restored content, `cloud_builder.py:692`):
```python
        s = min(len(os.path.commonprefix([a[::-1], b[::-1]])), min(len(a), len(b)) - p)
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.20s
```

The swapped case `e7-aa-aaa` was not separately neutralized or run alone; only `e7-aaa-aa` is the recorded detector for G14.

---

## G15 — the trim itself

**neutralization** (`cloud_builder.py:735`, `transit_compare`; the helper is called untrimmed):
```python
-        count, changes = _transit_changes(a, b, trim=True)
+        count, changes = _transit_changes(a, b, trim=False)
```

**raw red** (axis check: the red is the elapsed assertion, `31.0s`; every earlier assertion in the test — `changed`, `changeCount == 1`, `at`, `line`, `sent` — passed, so the untrimmed result was correct and only slow. The order expected minutes; on this 64,852-character part and this machine the untrimmed run took 31.0 s, still six times the 5 s bound):
```
F                                                                        [100%]
=================================== FAILURES ===================================
________ test_a_full_size_part_with_one_changed_character_compares_fast ________

    def test_a_full_size_part_with_one_changed_character_compares_fast():
        text = _long_json_text()
        part = rr._part_bodies(text)[0]
        assert len(part) >= 60000
        assert len(part) <= rr.MAX_BODY_CHARS
        at = len(part) // 2
        changed = _swap(part, at, "#" if part[at] != "#" else "%")
        started = time.monotonic()
        result = cb.transit_compare(part, changed)
        elapsed = time.monotonic() - started
        assert result["transit"] == cb.TRANSIT_CHANGED
        assert result["changeCount"] == 1
        change = result["changes"][0]
        assert change["at"] == at
        assert change["line"] == part.count("\n", 0, at) + 1
        assert change["line"] > 1
        assert change["sent"] == part[at]
        # axis: the elapsed bound is what fails when the trim is gone, because the untrimmed matcher takes minutes at this size — see bite-proof record wo_2490_transit_trim
>       assert elapsed < 5, f"transit_compare took {elapsed:.1f}s on a {len(part)}-character part"
E       AssertionError: transit_compare took 31.0s on a 64852-character part
E       assert 30.97153714899997 < 5

/home/user/wt-2490/plugins/superheroes/lib/tests/test_transit_compare_trim_2490.py:209: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_transit_compare_trim_2490.py::test_a_full_size_part_with_one_changed_character_compares_fast
1 failed in 31.17s
```

The red capture shows the axis comment as it read at the red run ("takes minutes"). After the red run, the comment was reworded to "takes far longer" (a comment-only edit, before the green run, because the measured time was 31 s and not minutes); nothing else in the test changed.

**restore:** the inverse Edit put `trim=True` back.

**restore receipt** (restored content, `cloud_builder.py:735`):
```python
        count, changes = _transit_changes(a, b, trim=True)
```

**raw green** (run on the final test text):
```
.                                                                        [100%]
1 passed in 0.21s
```
