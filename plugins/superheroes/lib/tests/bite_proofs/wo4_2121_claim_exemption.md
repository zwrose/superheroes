# Claim-check exemption bite-proof — `test_review_record_redacted_2121.py`

**Provenance:** claude write channel (implementer, WO-4 of #2121).

Declared guarded-element set (from the order): E1 the exemption (`and l is not transit_line` in the claim-check
generator in `_summary`); E2 no broadening (the `_assert_no_bug_free_claim(...)` call in `_summary` is not skipped
when a transit line exists). Every run: `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-wo4 -m pytest <node> -q -p no:cacheprovider`,
the detector unedited. Each neutralization was one `Edit` and each restore the inverse `Edit`; no `git checkout`,
`restore`, `reset` or `stash`. Nothing in the captures is secret and no redaction was applied. The `UV_NATIVE_TLS`
warning line that `uv` prints before each run is dropped from the captures below. The built record's first reviewer
row already held a dict `observation`, so the tests add only the `telemetry` key. `bug-free` is one of
`FORBIDDEN_CLAIMS` (`("no bugs", "bug-free", "bug free")`, `review_record.py:66`), and the accept test asserts it.

## Summary

| Element | Axis | Proving test | Verdict |
|---|---|---|---|
| E1 the transit line exemption from the claim check | a forbidden phrase in a redacted field's path (carried by the transit line) is accepted | `test_a_forbidden_phrase_in_a_redacted_fields_path_is_accepted_in_the_transit_line` | proven |
| E2 the claim check is not skipped when a transit line exists | a forbidden phrase elsewhere in a summary that has a transit line is still refused | `test_a_forbidden_phrase_elsewhere_in_a_summary_with_a_transit_line_is_still_refused` | proven |

Unproven: none in the declared set.

---

## E1 — the exemption

**guarded element:** `and l is not transit_line` in the generator passed to `_assert_no_bug_free_claim(...)` in
`_summary` (`review_record.py:1589`). **axis:** the transit line's literal record paths are not checked for forbidden
claims.

**neutralization:** in `plugins/superheroes/lib/review_record.py`, `_summary`, the generator's last two lines
```
                  and l is not transit_line and l not in wider_lines))
```
became
```
                  and l not in wider_lines))
```

**raw red:** (node `test_review_record_redacted_2121.py::test_a_forbidden_phrase_in_a_redacted_fields_path_is_accepted_in_the_transit_line`;
the `text = ...` repr is cut by pytest itself, verbatim as printed)
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_forbidden_phrase_in_a_redacted_fields_path_is_accepted_in_the_transit_line _

    def test_a_forbidden_phrase_in_a_redacted_fields_path_is_accepted_in_the_transit_line():
        # axis: the transit line's literal record paths being checked for forbidden claims (the exemption removed)
        assert "bug-free" in rr.FORBIDDEN_CLAIMS
>       body = rr.render(with_forbidden_redacted_path())
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

/home/user/wt-2121/plugins/superheroes/lib/tests/test_review_record_redacted_2121.py:230: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/home/user/wt-2121/plugins/superheroes/lib/review_record.py:1726: in render
    plan = render_plan(record)
           ^^^^^^^^^^^^^^^^^^^
/home/user/wt-2121/plugins/superheroes/lib/review_record.py:1679: in render_plan
    body = single(r)
           ^^^^^^^^^
/home/user/wt-2121/plugins/superheroes/lib/review_record.py:1674: in single
    return (f"{MARKER}\n{_summary(r, 0)}\n\n<details><summary>Full record</summary>\n\n```json\n"
                         ^^^^^^^^^^^^^^
/home/user/wt-2121/plugins/superheroes/lib/review_record.py:1587: in _summary
    _assert_no_bug_free_claim(
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

text = '**Review record: reviewed.** Checked: CI on bbbbbbb: green; Reviewers that ran: code-reviewer. Left: nothing.\nNothin...ks).\nRounds: 1 of 3 (round cap).\nReviewers:\n- code-reviewer: ran (engine record); findings: reported by the session'

    def _assert_no_bug_free_claim(text):
        low = text.lower()
        for phrase in FORBIDDEN_CLAIMS:
            if phrase in low:
>               raise Refusal("review-record-forbidden-claim", phrase)
E               review_record.Refusal: ('review-record-forbidden-claim', 'bug-free')

/home/user/wt-2121/plugins/superheroes/lib/review_record.py:1151: Refusal
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_redacted_2121.py::test_a_forbidden_phrase_in_a_redacted_fields_path_is_accepted_in_the_transit_line
1 failed in 1.34s
```

**restore:** the inverse edit, putting `l is not transit_line and ` back before `l not in wider_lines))`.

**restore receipt:** a grep of `l is not transit_line` with context printed
```
1587-    _assert_no_bug_free_claim(
1588-        "\n".join(l for l in lines if l is not floor_line and l is not withheld_line and l is not refusals_line
1589:                  and l is not transit_line and l not in wider_lines))
1590-    return "\n".join(lines)
```

**raw green:**
```
.                                                                        [100%]
1 passed in 1.13s
```

## E2 — no broadening

**guarded element:** the unconditional `_assert_no_bug_free_claim(...)` call in `_summary` (`review_record.py:1587`).
**axis:** the claim check still runs on every other line when a transit line exists.

**neutralization:** the call was wrapped in `if not transit_line:`, re-indenting only the call:
```
    if not transit_line:
        _assert_no_bug_free_claim(
            "\n".join(l for l in lines if l is not floor_line and l is not withheld_line and l is not refusals_line
                      and l is not transit_line and l not in wider_lines))
```

**raw red:** (node `test_review_record_redacted_2121.py::test_a_forbidden_phrase_elsewhere_in_a_summary_with_a_transit_line_is_still_refused`)
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_forbidden_phrase_elsewhere_in_a_summary_with_a_transit_line_is_still_refused _

    def test_a_forbidden_phrase_elsewhere_in_a_summary_with_a_transit_line_is_still_refused():
        # axis: the claim check skipped for the whole summary whenever a transit line exists (the exemption broadened)
        rec = with_forbidden_redacted_path()
        rec["whatIsMissing"] = ["this change is bug-free"]
>       with pytest.raises(rr.Refusal) as refused:
             ^^^^^^^^^^^^^^^^^^^^^^^^^
E       Failed: DID NOT RAISE Refusal

/home/user/wt-2121/plugins/superheroes/lib/tests/test_review_record_redacted_2121.py:240: Failed
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_redacted_2121.py::test_a_forbidden_phrase_elsewhere_in_a_summary_with_a_transit_line_is_still_refused
1 failed in 1.64s
```

**restore:** the inverse edit, removing the `if not transit_line:` line and the extra four-space indent on the call.

**restore receipt:** a grep of `_assert_no_bug_free_claim\($` with context printed
```
1586-    # axis: the refusals line's literal command text is left out of the claim check — see bite-proof record wo3_2011_record
1587:    _assert_no_bug_free_claim(
1588-        "\n".join(l for l in lines if l is not floor_line and l is not withheld_line and l is not refusals_line
1589-                  and l is not transit_line and l not in wider_lines))
1590-    return "\n".join(lines)
```

**raw green:**
```
.                                                                        [100%]
1 passed in 1.16s
```
