# Redacted-flag test strengthening bite-proof — `test_review_record_redacted_2121.py`

**Provenance:** claude write channel (implementer, WO-3 of #2121; review round 1 findings test-001 and test-002 on PR #2130).

Declared guarded-element set (from the order): E1 the compact (`level >= 1`) form of the `Transit damage` line, guarded
by the strengthened `test_a_parts_head_that_only_fits_compact_still_carries_the_line`; E2 the flag computed on the
record as posted (inside `single`, after each shed step), guarded by the strengthened
`test_edge_f_the_flag_matches_the_record_a_large_panel_posts`.
Every run: `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-wo3 -m pytest <node> -q -p no:cacheprovider`,
the detector unedited. Each neutralization was one `Edit` and each restore the inverse `Edit`; no `git checkout`,
`restore`, `reset` or `stash`. No `EXIT=` lines: the pytest output is quoted. Nothing in the captures is secret (the
credential-shaped string is built from pieces in the tests and never printed); no redaction was applied. The
`UV_NATIVE_TLS` warning line that `uv` prints before each run is dropped from the captures below.

## Summary

| Element | Axis | Proving test | Verdict |
|---|---|---|---|
| E1 `_transit_line` compact branch | the compact summary level counts the redacted fields and carries the line | `test_a_parts_head_that_only_fits_compact_still_carries_the_line` | proven |
| E2 `_flag_redactions` inside `single` | the flag is computed on the record as posted, after shedding | `test_edge_f_the_flag_matches_the_record_a_large_panel_posts` | proven |

## E1 — the compact form of the `Transit damage` line

**guarded element:** the `level >= 1` branch of `_transit_line` in `plugins/superheroes/lib/review_record.py`.
**axis:** a parts head that only fits at a compact summary level carries the counted line, not the path and not nothing.
The fixture is 78 findings with 900-character ids (outcome `left-for-owner`), so the head only fits compact; finding 40
holds the redacted body.

**neutralization:** the `level >= 1` branch's `return f"Transit damage: redacted text in {count} {LISTED}, so that text is lost."`
became `return None`.

**raw red:** (node `test_review_record_redacted_2121.py::test_a_parts_head_that_only_fits_compact_still_carries_the_line`;
the long `summary_of(...)` reprs are cut by pytest itself, verbatim as printed)
```
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_a_parts_head_that_only_fits_compact_still_carries_the_line ________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-14/test_a_parts_head_that_only_fi0')

    def test_a_parts_head_that_only_fits_compact_still_carries_the_line(tmp_path):
        # axis: the compact summary level (the parts head's) reading the unflagged record, or naming the path instead of counting
        fake = Fake()
        idx = 40
        ids = [f"{i:03d}" + "x" * 897 for i in range(78)]
        found = [finding(i, title=f"t{n}", outcome="left-for-owner", reason="waits") for n, i in enumerate(ids)]
        found[idx] = dict(found[idx], body="see " + SECRET)
        out = send(tmp_path, fake, findings=found)
        head = fake.marked()[0]["body"]
        assert out["parts"] >= 1
        assert "Waiting for the owner: 78 findings left for the owner (listed in the full record)" in head
>       assert ("Transit damage: redacted text in 1 recorded field (listed in the full record), so that text is lost."
                in summary_of(head))
E       assert 'Transit damage: redacted text in 1 recorded field (listed in the full record), so that text is lost.' in '<!-- superheroes:review-record -->\n**Review record: not reviewed.** Checked: CI on bbbbbbb: green; Reviewers that ra...d just before this one (comment ids 1, 2, 3, 4); the block below names them and carries the hash that checks them.\n\n'
E        +  where '<!-- superheroes:review-record -->\n**Review record: not reviewed.** Checked: CI on bbbbbbb: green; Reviewers that ra...d just before this one (comment ids 1, 2, 3, 4); the block below names them and carries the hash that checks them.\n\n' = summary_of('<!-- superheroes:review-record -->\n**Review record: not reviewed.** Checked: CI on bbbbbbb: green; Reviewers that ra...:"review-record-parts/1","sha256":"3cd6d609e1fdad55dbf955d1284f402ae1784169243b0531858bc101466b0f60"}\n```\n</details>')

/home/user/wt-2121/plugins/superheroes/lib/tests/test_review_record_redacted_2121.py:151: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_redacted_2121.py::test_a_parts_head_that_only_fits_compact_still_carries_the_line
1 failed in 7.07s
```
The red is on the axis: the earlier assertions (parts posted, the head carries the `Waiting for the owner: 78 findings
... (listed in the full record)` compact text) passed, so the head was compact, and the failing line is the counted
`Transit damage` line.

**restore:** the inverse edit, `return None` back to the count line.

**restore receipt:** a grep of `if level >= 1:` with one line of context printed
```
1501:    if level >= 1:
1502-        return f"{lead}{_plural(len(lst), 'path', 'paths')} {LISTED}."
--
1513:    if level >= 1:
1514-        return f"Transit damage: redacted text in {count} {LISTED}, so that text is lost."
```

**raw green:**
```
.                                                                        [100%]
1 passed in 1.28s
```

## E2 — the flag computed on the record as posted

**guarded element:** the `r = _flag_redactions(r)` line inside `single(r)` in `render_plan`. **axis:** the posted
record's `transitDamage.redactedFields` lists the fields of the record as posted (after the `observation` shed step), so
redacted text that was shed is not listed. The fixture is a 132-row panel whose first engine run holds
`telemetry: {"note": "[REDACTED FIELD]", "padding": "x" * 70000}` (the observation is the engine run's, read through
`Fake(runs=...)` at the first row's run directory), plus a redacted finding body; the record posts as one comment
(`out["parts"] == 0`) after the `observation` shed.

**neutralization:** one `Edit` that removed the `r = _flag_redactions(r)` line inside `single(r)` and added
`r = _flag_redactions(r)` directly after `r = _scrubbed(record)` (the flag computed once, before shedding). The
parts-path call `r = _flag_redactions(r)  # the parts text and the head's summary carry the flag too` was left as it is;
the record posts as one comment, so that call is not reached.

**raw red:** (node `test_review_record_redacted_2121.py::test_edge_f_the_flag_matches_the_record_a_large_panel_posts`)
```
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_edge_f_the_flag_matches_the_record_a_large_panel_posts __________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-16/test_edge_f_the_flag_matches_t0')

    def test_edge_f_the_flag_matches_the_record_a_large_panel_posts(tmp_path):
        # axis: the flag computed before shedding (here a 132-row panel whose first run's telemetry holds redacted text and is shed)
        rows = panel_rows(SEATS, 12)
        telemetry = {"note": "[REDACTED FIELD]", "padding": "x" * 70000}
        big_run = ({**GOOD_RUN, "observation": {**GOOD_RUN["observation"], "telemetry": telemetry}}, None)
        fake = Fake(runs={rows[0]["runDir"]: big_run})
        out = send(tmp_path, fake, findings=[finding(body="see " + SECRET)], reviewers=rows)
        assert out["parts"] == 0
        [comment] = fake.marked()
        rec = rr._parse_body(comment["body"], {c["id"]: c for c in fake.comments})
        assert "observation" in rec["reviewerShed"]
        assert not any("telemetry" in (v.get("observation") or {}) for v in rec["reviewers"])
>       assert rec["transitDamage"]["redactedFields"] == rr._redacted_paths(rec) == ["findings[0].body"]
E       AssertionError: assert ['reviewers[0...ings[0].body'] == ['findings[0].body']
E         
E         At index 0 diff: 'reviewers[0].observation.telemetry.note' != 'findings[0].body'
E         Left contains one more item: 'findings[0].body'
E         Use -v to get more diff

/home/user/wt-2121/plugins/superheroes/lib/tests/test_review_record_redacted_2121.py:212: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_redacted_2121.py::test_edge_f_the_flag_matches_the_record_a_large_panel_posts
1 failed in 1.82s
```
The red is on the axis: the posted record parsed, posted as one comment, shed `observation`, and carried no telemetry;
only the flag differs, listing the shed `reviewers[0].observation.telemetry.note` that the posted record no longer holds.

**restore:** the inverse edit, the `r = _flag_redactions(r)` line back inside `single(r)` and out from after
`r = _scrubbed(record)`.

**restore receipt:** a grep of `_flag_redactions\(r\)|r = _scrubbed\(record\)` with one line of context each side printed
```
1619-
1620:def _flag_redactions(r):
1621-    """The record with `transitDamage.redactedFields` listing every recorded field whose text holds `[REDACTED`
--
1668-def render_plan(record):
1669:    r = _scrubbed(record)
1670-
--
1672-        # axis: the redacted-field flag is computed on the record as posted, after each shed step — see bite-proof record wo1_2121_redacted
1673:        r = _flag_redactions(r)
1674-        return (f"{MARKER}\n{_summary(r, 0)}\n\n<details><summary>Full record</summary>\n\n```json\n"
--
1698-    # Still over the cap after every step: the JSON text goes to part comments, never cut and never refused.
1699:    r = _flag_redactions(r)  # the parts text and the head's summary carry the flag too
1700-    text = _record_json(r)
```

**raw green:**
```
.                                                                        [100%]
1 passed in 1.11s
```
