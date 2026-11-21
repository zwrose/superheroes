# Bite-proof record — `read-all` names every record comment it does not return (#2528)

Detector file: `plugins/superheroes/lib/tests/test_review_record_read_all_2528.py`, unedited between each red and its green. Each entry is a targeted, reversible edit to `plugins/superheroes/lib/review_record.py` (`read_all`), made and undone with the edit tool (no `git checkout`, `restore`, `reset` or `stash`). Runs: `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2528 -m pytest "<file>::<node>" -q -p no:cacheprovider`, selecting the detector by its exact test node id (stricter than the `-k` the order named; a `-k` can select nothing and read green). Each capture is the whole output of the run (no filter, no `tail`); the `UV_NATIVE_TLS` deprecation warning that `uv` prints first is the only line left out. No secret, token, URL or personal data appears in any capture, so nothing is redacted. The two guarded elements are the two the order declared (R1, R2); none is grouped.

## R1. The `unreadable` append for a `None` parse (`lib/review_record.py:3886-3893`, `read_all`)

- **Axis:** a record comment that parses to `None` is named in `unreadable`, never silently dropped.
- **Detector:** `test_an_unparseable_record_is_named_never_dropped`.
- **Neutralization:** after the parse `try`/`except`, two lines were inserted so a comment that parsed without raising and was not a record is skipped instead of named:

  ```
  if failure is None:
      continue
  ```

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
______________ test_an_unparseable_record_is_named_never_dropped _______________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-2/test_an_unparseable_record_is_0')

    def test_an_unparseable_record_is_named_never_dropped(tmp_path):
        # axis: a record comment that parses to None is named in unreadable, never dropped, and the readable ones around it stay
        fake, bad = around(tmp_path, HAND_EDITED)
        first, _, last = [c for c in fake.comments if c["body"].startswith(rr.MARKER)]
        out = rr.read_all(7, readers=fake.readers())
        assert out["ok"] is True
        assert len(out["records"]) == 2
        assert [r["url"] for r in out["records"]] == [first["url"], last["url"]]
>       assert len(out["unreadable"]) == 1
E       assert 0 == 1
E        +  where 0 = len([])

/home/user/wt-2528/plugins/superheroes/lib/tests/test_review_record_read_all_2528.py:70: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_read_all_2528.py::test_an_unparseable_record_is_named_never_dropped
1 failed in 0.82s
```

**Restore:** the inverse edit removed the two inserted lines.
**Restore receipt** (the restored lines, read back from the file): `3885:                failure = e` then `3886:            try:` then `3887:                if failure is not None:` (no `continue` between the first two).

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.72s
```

## R2. The per-comment exception isolation (`lib/review_record.py:3879-3885`, `read_all`)

- **Axis:** a record comment whose parse raises (a deeply nested JSON body raises `RecursionError`) is named in `unreadable` and costs no other record; the exception never reaches `_guarded` to turn the whole answer into a refusal.
- **Detector:** `test_a_record_that_raises_while_parsing_costs_no_other_record`.
- **Neutralization:** the per-comment `try`/`except Exception as e: failure = e` was removed, leaving the parse and the `records.append` / `continue` unprotected at the loop's indent.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
________ test_a_record_that_raises_while_parsing_costs_no_other_record _________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-4/test_a_record_that_raises_whil0')

    def test_a_record_that_raises_while_parsing_costs_no_other_record(tmp_path):
        # axis: a record comment whose parse raises (RecursionError from a deeply nested JSON body) is named, and the other records are kept
        fake, bad = around(tmp_path, nested_body())
        with pytest.raises(RecursionError):
            rr._parse_body(bad["body"], {})
        out = rr.read_all(7, readers=fake.readers())
>       assert out["ok"] is True
E       assert False is True

/home/user/wt-2528/plugins/superheroes/lib/tests/test_review_record_read_all_2528.py:82: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_read_all_2528.py::test_a_record_that_raises_while_parsing_costs_no_other_record
1 failed in 0.76s
```

**Restore:** the inverse edit put the `try:` / `except Exception as e:  # noqa: BLE001 — a body that raises while parsing is unreadable, not fatal` / `failure = e` block back around the parse.
**Restore receipt** (the restored lines, read back from the file):

```
3879:            try:
3880:                rec = _parse_body(c["body"], by_id)
3881:                if isinstance(rec, dict):
3882:                    records.append({"url": c.get("url"), **rec})
3883:                    continue
3884:            except Exception as e:  # noqa: BLE001 — a body that raises while parsing is unreadable, not fatal
3885:                failure = e
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.71s
```

## Not proven (outside what the detectors can tell apart)

- The fallback detail when `_unreadable_detail` itself raises (the inner `try`/`except`) is covered by `test_a_parse_and_a_detail_that_both_raise_fall_back_to_the_named_detail`, `test_a_detail_that_raises_for_an_unparseable_record_falls_back_to_the_named_detail` and `test_a_comment_with_no_url_falls_back_to_the_stand_in`, but the order declared only R1 and R2, so no neutralization of that inner `try` was run and it is not proven here.
- R1 neutralizes the `None`-parse path only; a parse that raises is R2's, and the two reds are on different tests.
