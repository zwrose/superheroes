# Redacted-field flag bite-proof — `test_review_record_redacted_2121.py`

**Provenance:** claude write channel (implementer, WO-1b of #2121).

Declared guarded-element set (from the order): E1 the `_flag_redactions` application in `render_plan`; E2 the
`Transit damage` summary line; E3 the `redacted text` why branch in `write`; E4 the merge in `_resolve_parts`.
Every run: `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-wo1 -m pytest <node> -q -p no:cacheprovider`,
the detector unedited. Each neutralization was one `Edit` and each restore the inverse `Edit`; no `git checkout`,
`restore`, `reset` or `stash`. Nothing in the captures is secret (the credential-shaped string is built from pieces
in the tests and never printed); no redaction was applied. The `UV_NATIVE_TLS` warning line that `uv` prints before
each run is dropped from the captures below.

## Summary

| Element | Axis | Proving test | Verdict |
|---|---|---|---|
| E1 `_flag_redactions` applied in `render_plan` | the posted record carries `transitDamage.redactedFields` | `test_pr2113_record_reads_flagged_and_its_summary_says_text_was_lost` (record assertion) | proven |
| E2 the `Transit damage` summary line | the summary says text was lost | the same test (summary assertion) | proven |
| E3 the `redacted text` why branch in `write` | a later record lists an earlier redacted-only record as `redacted text` | `test_a_later_record_lists_an_earlier_one_that_held_redacted_text` | proven |
| E4 the merge in `_resolve_parts` | the read's length/hash keys join, never replace, `redactedFields` | `test_parts_changed_in_transit_keep_the_redacted_fields_beside_the_length_and_hash_keys` | proven |

Unproven (no neutralization run): the compact `LISTED` form of the line (`_transit_line`, level >= 1) and the parts
head reading the flagged record; the `existing`-dict merge in `_flag_redactions`; the `changed in transit` branch
staying `changed in transit` when length/hash keys are present
(`test_an_earlier_record_changed_in_transit_still_reads_changed_in_transit`); the path-walk edges.

---

## E1 — `_flag_redactions` applied in `render_plan`

**guarded element:** `_flag_redactions` and its calls in `render_plan` (`single`, and the line before the parts
`text = _record_json(r)`). **axis:** a record holding `[REDACTED` text posts with `transitDamage.redactedFields`.

**neutralization:** in `plugins/superheroes/lib/review_record.py`, `_flag_redactions`: a first body line `return r`
inserted ahead of `paths = _redacted_paths(r)`.

**raw red:** (node `test_review_record_redacted_2121.py::test_pr2113_record_reads_flagged_and_its_summary_says_text_was_lost`)
```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_pr2113_record_reads_flagged_and_its_summary_says_text_was_lost ______

    def test_pr2113_record_reads_flagged_and_its_summary_says_text_was_lost():
        # axis: a record already holding [REDACTED FIELD] (PR #2113) posted with no flag and no summary line
        rec = json.loads(FIXTURE.read_text(encoding="utf-8"))
        assert "transitDamage" not in rec
        body = rr.render(rec)
>       assert rr._parse_body(body)["transitDamage"] == {"redactedFields": PR2113_FIELDS}
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       KeyError: 'transitDamage'

/home/user/wt-2121-wo1/plugins/superheroes/lib/tests/test_review_record_redacted_2121.py:35: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_redacted_2121.py::test_pr2113_record_reads_flagged_and_its_summary_says_text_was_lost
1 failed in 0.95s
```

**restore:** the inverse edit, deleting the inserted `return r`.

**restore receipt:** a grep of `paths = _redacted_paths(r)` with context printed
```
1620-def _flag_redactions(r):
1621-    """The record with `transitDamage.redactedFields` listing every recorded field whose text holds `[REDACTED`
1622-    (merged into an existing `transitDamage` dict), or the record itself when no field does."""
1623:    paths = _redacted_paths(r)
1624-    if not paths:
1625-        return r
1626-    existing = r.get("transitDamage")
1627-    return dict(r, transitDamage={**(existing if isinstance(existing, dict) else {}), "redactedFields": paths})
```

**raw green:**
```
.                                                                        [100%]
1 passed in 1.04s
```

## E2 — the `Transit damage` summary line

**guarded element:** `*([transit_line] if transit_line else []),` in `_summary`. **axis:** the summary carries the
line that tells a reader text was lost (checked on the summary assertion, line 36, not the record assertion).

**neutralization:** `*([transit_line] if transit_line else []),` became
`*([transit_line] if False and transit_line else []),`.

**raw red:** (node as for E1; the long `summary_of(...)` repr is cut by pytest itself, verbatim as printed)
```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_pr2113_record_reads_flagged_and_its_summary_says_text_was_lost ______

    def test_pr2113_record_reads_flagged_and_its_summary_says_text_was_lost():
        # axis: a record already holding [REDACTED FIELD] (PR #2113) posted with no flag and no summary line
        rec = json.loads(FIXTURE.read_text(encoding="utf-8"))
        assert "transitDamage" not in rec
        body = rr.render(rec)
        assert rr._parse_body(body)["transitDamage"] == {"redactedFields": PR2113_FIELDS}
>       assert PR2113_LINE in summary_of(body)
E       assert 'Transit damage: redacted text in 3 recorded fields, so that text is lost: findings[1].body, findings[2].body, findings[2].id.' in "<!-- superheroes:review-record -->\n**Review record: not reviewed.** Checked: CI on da7f67d: green; Reviewers that ra... the session\nNot run: grounding-seat, because no loop phase runs it, so no reviewer checked the PR body's claims.\n\n"
E        +  where "<!-- superheroes:review-record -->\n**Review record: not reviewed.** Checked: CI on da7f67d: green; Reviewers that ra... the session\nNot run: grounding-seat, because no loop phase runs it, so no reviewer checked the PR body's claims.\n\n" = summary_of('<!-- superheroes:review-record -->\n**Review record: not reviewed.** Checked: CI on da7f67d: green; Reviewers that ra...L119 waits for the owner\'s decision"],"withheldFromReviewers":[],"writtenAt":"2026-10-24T01:22:33Z"}\n```\n</details>')

/home/user/wt-2121-wo1/plugins/superheroes/lib/tests/test_review_record_redacted_2121.py:36: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_redacted_2121.py::test_pr2113_record_reads_flagged_and_its_summary_says_text_was_lost
1 failed in 1.92s
```

**restore:** the inverse edit, `if False and transit_line` back to `if transit_line`.

**restore receipt:** a grep of `transit_line` printed
```
1506:def _transit_line(damage, level):
1557:    transit_line = _transit_line(r.get("transitDamage"), level)
1568:        *([transit_line] if transit_line else []),
1589:                  and l is not transit_line and l not in wider_lines))
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.88s
```

## E3 — the `redacted text` why branch in `write`

**guarded element:** the `elif isinstance(damage, dict) and list(damage) == ["redactedFields"]:` branch in `write`'s
earlier-record loop. **axis:** an earlier record carrying only redacted fields is listed with why `redacted text`.

**neutralization:** the branch condition became `elif False and isinstance(damage, dict) and list(damage) == ["redactedFields"]:`,
so every damaged-but-readable record reads `changed in transit`.

**raw red:** (node `test_a_later_record_lists_an_earlier_one_that_held_redacted_text`)
```
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_a_later_record_lists_an_earlier_one_that_held_redacted_text _______

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-7/test_a_later_record_lists_an_e0')

    def test_a_later_record_lists_an_earlier_one_that_held_redacted_text(tmp_path):
        # axis: an earlier record with redacted text hidden from the vet by the next writes
        fake = Fake()
        send(tmp_path, fake, findings=[finding(body="see " + SECRET)])
        first = fake.marked()[0]
        send(tmp_path, fake, findings=[finding(body="plain text")])
        send(tmp_path, fake, findings=[finding(body="plain text")])
        third = posted(fake)[2]
        listed = [e for e in third["earlierRecordsNotChecked"] if e["id"] == first["id"]]
>       assert listed == [{"id": first["id"], "url": first["url"], "why": "redacted text"}]
E       AssertionError: assert [{'id': 1, 'u... in transit'}] == [{'id': 1, 'u...dacted text'}]
E         
E         At index 0 diff: {'id': 1, 'url': 'http://c/1', 'why': 'changed in transit'} != {'id': 1, 'url': 'http://c/1', 'why': 'redacted text'}
E         Use -v to get more diff

/home/user/wt-2121-wo1/plugins/superheroes/lib/tests/test_review_record_redacted_2121.py:109: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_redacted_2121.py::test_a_later_record_lists_an_earlier_one_that_held_redacted_text
1 failed in 1.09s
```

**restore:** the inverse edit, dropping `False and`.

**restore receipt:** a grep of `list\(damage\) == ` with context printed
```
1941-                if usable is None:
1942-                    why = "unreadable"
1943:                elif isinstance(damage, dict) and list(damage) == ["redactedFields"]:
1944-                    why = "redacted text"
1945-                else:
1946-                    why = "changed in transit"
```

**raw green:**
```
.                                                                        [100%]
1 passed in 1.08s
```

## E4 — the merge in `_resolve_parts`

**guarded element:** the `**(damage if isinstance(damage, dict) else {})` spread in `_resolve_parts`. **axis:** a
parts record changed in transit keeps the writer's `redactedFields` beside `recordedChars`/`foundChars`/`hashMatches`.

**neutralization:** `**(damage if isinstance(damage, dict) else {})` became `**({} if isinstance(damage, dict) else {})`,
so the read's keys replace the object.

**raw red:** (node `test_parts_changed_in_transit_keep_the_redacted_fields_beside_the_length_and_hash_keys`)
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_parts_changed_in_transit_keep_the_redacted_fields_beside_the_length_and_hash_keys _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-9/test_parts_changed_in_transit_0')

    def test_parts_changed_in_transit_keep_the_redacted_fields_beside_the_length_and_hash_keys(tmp_path):
        # axis: the read's length/hash report replacing the writer's redactedFields instead of joining them
        fake = Fake()
        found = many_findings(40, 4000)
        found[0] = finding("f-000", body="see " + SECRET)
        send(tmp_path, fake, findings=found)
        assert len(parts_of(fake)) >= 2
        assert "Transit damage: redacted text in 1 recorded field" in summary_of(fake.marked()[0]["body"])
        part = parts_of(fake)[0]
        assert "reads the saved" in part["body"]
        part["body"] = part["body"].replace("reads the saved", "reads the SAVED", 1)
        out = rr.read(7, readers=fake.readers())
        idx = [f["body"] for f in out["findings"]].index("[REDACTED FIELD]")
        damage = out["transitDamage"]
>       assert damage["redactedFields"] == [f"findings[{idx}].body"]
               ^^^^^^^^^^^^^^^^^^^^^^^^
E       KeyError: 'redactedFields'

/home/user/wt-2121-wo1/plugins/superheroes/lib/tests/test_review_record_redacted_2121.py:93: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_redacted_2121.py::test_parts_changed_in_transit_keep_the_redacted_fields_beside_the_length_and_hash_keys
1 failed in 1.42s
```

**restore:** the inverse edit, `{} if` back to `damage if`.

**restore receipt:** a grep of `damage = rec.get\("transitDamage"\)` with context printed
```
1812-        # merged into a `transitDamage` the writer already put there (its redacted fields), never replacing it
1813:        damage = rec.get("transitDamage")
1814-        rec = dict(rec, transitDamage={**(damage if isinstance(damage, dict) else {}), "recordedChars": chars,
1815-                                       "foundChars": len(text), "hashMatches": hash_matches})
1816-    return rec
```

**raw green:**
```
.                                                                        [100%]
1 passed in 1.26s
```
