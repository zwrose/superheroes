# Review record transit bite-proof — `test_review_record_transit_1957.py`

**Provenance:** claude write channel.

## Summary

| Class | Representative element | Axis | Proving test | Verdict |
|---|---|---|---|---|
| E-offset | the offset in `_unreadable_detail`'s whole-record branch | the refusal names the real character offset of the damage | `test_pr1942_record_refusal_names_the_damaged_span` | proven |
| E-escape | the escape in `_record_json` | the record's JSON carries no bare `/`, so the URL-wrapping egress cannot change it | `test_one_comment_record_survives_the_url_wrapping_egress` | proven |

Unproven (no neutralization run, inside the order's seven-command budget): the offset in
`_unreadable_detail`'s parts-joined branch (`pos = min(e.pos, len(text) - 1) if text else 0` and what
follows it); the phrase branches (`the comment has no JSON block`, `the JSON is not a review record`,
`the parts index is malformed`, `part comment <id> is missing or malformed`, `the joined parts are not
a review record`, `the record could not be read`); the other tests in the file. The proving tests were
selected with `-k <name>` as the order's budget names them, not by exact node id; each selected one
test (`1 failed, 6 deselected` / `1 passed, 6 deselected`).

---

## E-offset — the offset in `_unreadable_detail`'s whole-record branch

**guarded element:** the two `start + e.pos` expressions in the `json.JSONDecodeError` branch of
`_unreadable_detail` (`review_record.py`, lines 1549–1550). **axis:** the refusal names the real
character offset of the damage in the comment body, and the excerpt is cut around that offset.

**neutralization:** in `plugins/superheroes/lib/review_record.py`, `_unreadable_detail`:
`character {start + e.pos} of comment` became `character {0} of comment`, and
`{_span(body, start + e.pos)}` became `{_span(body, 0)}`.

**raw red:** (run of
`test_review_record_transit_1957.py -k test_pr1942_record_refusal_names_the_damaged_span`; the pytest
source dump of the test body is elided here, the output lines are verbatim)
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
______________ test_pr1942_record_refusal_names_the_damaged_span _______________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-7/test_pr1942_record_refusal_nam0')

[... pytest source dump of the test body elided ...]
>       assert out["detail"].startswith(lead)
E       assert False
E        +  where False = <built-in method startswith of str object at 0x7fc4a8c44b30>("https://x/c: the record's JSON does not parse at character 10392 of comment 6244257429: ")
E        +    where <built-in method startswith of str object at 0x7fc4a8c44b30> = 'https://x/c: the record\'s JSON does not parse at character 0 of comment 6244257429: "<!-- superheroes:review-record -->\\n**Rev"'.startswith

/home/user/sh-1957/plugins/superheroes/lib/tests/test_review_record_transit_1957.py:133: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_transit_1957.py::test_pr1942_record_refusal_names_the_damaged_span
1 failed, 6 deselected in 0.92s
EXIT=1
```

**restore:** the inverse edit, `{0}` back to `{start + e.pos}` and `_span(body, 0)` back to
`_span(body, start + e.pos)`.

**restore receipt:** `grep -n 'e\.pos' plugins/superheroes/lib/review_record.py` printed
```
1549:        return f"{where}: the record's JSON does not parse at character {start + e.pos} of comment " \
1550:               f"{latest.get('id')}: {_span(body, start + e.pos)}"
1568:        pos = min(e.pos, len(text) - 1) if text else 0
```

**raw green:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed, 6 deselected in 0.83s
EXIT=0
```

## E-escape — the escape in `_record_json`

**guarded element:** `.replace("/", "\\/")` in `_record_json` (`review_record.py`, line 1341).
**axis:** the record's JSON carries no bare `/`, so the egress that wraps each bare `http(s)://` run
in backticks has nothing to wrap, and the comment reads back as written plus the footer.

**neutralization:** in `plugins/superheroes/lib/review_record.py`, `_record_json`:
`return json.dumps(r, sort_keys=True, separators=(",", ":")).replace("/", "\\/")` became
`return json.dumps(r, sort_keys=True, separators=(",", ":"))`.

**raw red:** (run of
`test_review_record_transit_1957.py -k test_one_comment_record_survives_the_url_wrapping_egress`; the
pytest source dump of the test body is elided here, the output lines are verbatim)
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
___________ test_one_comment_record_survives_the_url_wrapping_egress ___________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-9/test_one_comment_record_surviv0')

[... pytest source dump of the test body elided ...]
>       assert all(c["body"] == fake.sent[c["id"]] + CLOUD_FOOTER for c in fake.comments)
E       assert False
E        +  where False = all(<generator object test_one_comment_record_survives_the_url_wrapping_egress.<locals>.<genexpr> at 0x7f5100f9d8c0>)

/home/user/sh-1957/plugins/superheroes/lib/tests/test_review_record_transit_1957.py:80: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_transit_1957.py::test_one_comment_record_survives_the_url_wrapping_egress
1 failed, 6 deselected in 1.97s
EXIT=1
```

**restore:** the inverse edit, `.replace("/", "\\/")` appended back after
`separators=(",", ":"))` on the `return json.dumps(...)` line.

**restore receipt:** `grep -n 'replace("/"' plugins/superheroes/lib/review_record.py` printed
`1341:    return json.dumps(r, sort_keys=True, separators=(",", ":")).replace("/", "\\/")`.
After both elements, `git diff HEAD -- plugins/superheroes/lib/review_record.py` printed nothing.

**raw green:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed, 6 deselected in 1.13s
EXIT=0
```
