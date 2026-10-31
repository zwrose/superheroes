# C1-L9b WO-C bite-proof: the re-run line tells a head change

**Provenance:** `plugins/superheroes/lib/review_record.py` (`_moved_heads`, `_rerun_line`) with `plugins/superheroes/lib/tests/test_review_record_rerun_heads.py`. The neutralization was applied as a targeted edit and undone by the inverse edit; no `git checkout`, `restore`, `reset` or `stash` was used. Runner command: `timeout 600 scripts/pinned-python -B -X pycache_prefix=/home/user/superheroes/.git/pyc-woC -m pytest <node> -q -p no:cacheprovider`. Captures are the runner's own output with the `UV_NATIVE_TLS` deprecation warning line dropped; nothing else was cut. No secrets, tokens or private URLs appear in them.

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| G1 | `review_record._moved_heads` (read by `_rerun_line`) | a re-run across two different known heads is never called unchanged code | `test_1_moved_heads_add_the_suffix_and_the_compact_lead_drops_unchanged_code` |

The fail-closed edges (unknown head, equal heads, a `runs` list that is not two dicts) are pinned by tests 2, 3, 3b and the helper tests in the same file; they have no neutralization of their own in this order's declared set and are not claimed as proven here.

### G1 — the moved-head helper

- **site:** `plugins/superheroes/lib/review_record.py`, `_moved_heads`
- **neutralization:** replace the helper's last line `    return first, second` with `    return None` (the helper then always returns `None`)
- **raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_1_moved_heads_add_the_suffix_and_the_compact_lead_drops_unchanged_code __

    def test_1_moved_heads_add_the_suffix_and_the_compact_lead_drops_unchanged_code():
        # axis: a re-run across two different heads is never called unchanged code
        full, compact = rerun_lines([verify_check(H1, H2)])
>       assert full == TODAY_FULL + SUFFIX
E       AssertionError: assert 'Re-run after...) then passed' == 'Re-run after...nchanged code'
E         
E         Skipping 92 identical leading characters in diff, use -v to show
E         - then passed — the second run was at a different head (111111111111 then 222222222222), not on unchanged code
E         + then passed

/home/user/wt-2260-woC/plugins/superheroes/lib/tests/test_review_record_rerun_heads.py:42: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_rerun_heads.py::test_1_moved_heads_add_the_suffix_and_the_compact_lead_drops_unchanged_code
1 failed in 1.33s
```

- **restore:** inverse edit. **restore receipt**, the restored lines (`grep -n` at lines 1817-1820):

```
1817-    first, second = runs[0].get("head"), runs[1].get("head")
1818-    if not (isinstance(first, str) and first and isinstance(second, str) and second and first != second):
1819-        return None
1820:    return first, second
```

- **raw green:** `.  [100%]` / `1 passed in 1.30s`
- **verdict:** RED->GREEN
