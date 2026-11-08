# #2383 (work order B) bite-proof — the review record, the vet slot writer and the PR-body publisher flag text changed in transit

**Provenance:** implementer, work order B / `lib/review_record.py`, `lib/vet_slot.py`, `lib/pr_body_stage.py`, `lib/round_driver.py`, `lib/tests/test_transit_record_2383.py`

Declared guarded elements (from the order): E1 the writer's stamp in `render_plan`; E2 the reader's whole-record check in `_parse_body`; E3 the reader's parts check in `_resolve_parts`; E4 the legacy pass-through in `_sent_hash_damage`; E5 `_create_comment`'s read-back; E6 `write`'s aggregation (`_transit_summary`); E7 `vet_slot`'s read-back comparison; E8 `pr_body_stage`'s post-PATCH comparison; E9 `record_line`'s transit rendering. Nine elements, nine neutralizations, nine reds, nine greens; no grouping into classes.

Method: each element was neutralized with one targeted Edit (marked `BITE-PROOF NEUTRALIZED` in the file while neutralized), run alone against its named detector node, and restored with the inverse Edit (never `git checkout`, `restore`, `reset` or `stash`); the same node then ran green. Every run was `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest "<node>" -q -p no:cacheprovider` from the worktree root, with the launcher's one-line `UV_NATIVE_TLS` deprecation warning dropped (`grep -v UV_NATIVE` on the output). Nothing else was filtered. The captures hold no secrets, tokens, private URLs or PII; the only paths are pytest's own temporary directories. (E7's neutralization reuses `vet_slot._normalize`, which no other code calls; it is left in place for that reason.)

Restore receipt shape: the restored lines are quoted below (the inverse Edit's text), and `git diff --stat -- <file>` was read before any neutralization (once, over the three source files) and again after each restore, before the green run. The baseline read before E1:

```
 plugins/superheroes/lib/pr_body_stage.py | 14 ++++--
 plugins/superheroes/lib/review_record.py | 80 +++++++++++++++++++++++++++++---
 plugins/superheroes/lib/vet_slot.py      |  8 +++-
 3 files changed, 89 insertions(+), 13 deletions(-)
```

Each "after restore" stat below shows the same line for its file (`review_record.py | 80 +++…`, `vet_slot.py | 8 ++++++--`, `pr_body_stage.py | 14 ++++++++++----` as `--stat` prints it alone).

| ID | Guarded element | Axis | Detector node (all in `test_transit_record_2383.py`) |
|---|---|---|---|
| E1 | `review_record.render_plan` → `single`, the `stamped = dict(r, sentSha256=_sent_sha(r))` line | the hash is taken of the object the JSON is built from, after the redaction flag and every shed step | `test_1c_a_record_holding_redacted_text_round_trips_with_only_its_redacted_field_flag` |
| E2 | `review_record._parse_body`, `return _sent_hash_damage(obj)` | a whole record whose stamp no longer matches reads flagged | `test_2_a_record_whose_stored_json_lost_a_bang_reads_flagged_and_is_listed_by_the_next_write` |
| E3 | `review_record._resolve_parts`, `rec = _sent_hash_damage(rec)` | a parts record whose stamp no longer matches reads flagged, beside the hash keys | `test_2b_a_parts_record_whose_parts_lost_a_bang_reads_flagged_beside_the_hash_keys` |
| E4 | `review_record._sent_hash_damage`, the `"sentSha256" not in rec` pass-through | a record written before the key existed reads unflagged | `test_4_a_record_without_sentsha256_is_read_unflagged` |
| E5 | `review_record._create_comment`, the read-back compare | every created comment is read back and compared with what was posted | `test_5_create_comment_matched_changed_and_not_checked` |
| E6 | `review_record._transit_summary`, the overall `transit` | any changed comment makes the write `changed`; matched only when every comment matched | `test_6_write_reports_a_changed_head_and_names_it` |
| E7 | `vet_slot._run_verb`, the `transit_compare` read-back comparison | one cloud footer is tolerated, a lost character is not | `test_8a_a_readback_with_one_cloud_footer_is_confirmed` |
| E8 | `pr_body_stage._publish`, the post-PATCH `transit_compare` | a lost leading indent is a change (`strip_cloud_footer` hid it) | `test_9d_a_readback_that_lost_the_leading_indent_is_refused` |
| E9 | `pr_body_stage.record_line`, the `transit` rendering | a refused publish whose read-back was compared says what the comparison found | `test_9b_a_readback_that_fails_is_not_checked_and_the_line_says_so` |

Coverage not separately neutralized, so unproven by this record: `_sent_sha`'s exclusion of its own key (every green round trip depends on it, but no run removed the exclusion); the `transitDamage` merge in `_sent_hash_damage` (pinned by `test_4c_…`, not run against a mutation); the `transitLine` text of `_transit_summary`; `round_driver`'s `reservationTransit` pass-through (pinned by the updated assertion in `test_c1l4b_extra_audit.py::_ordered`, not run against a mutation); the retried-publish recognition in `publish` (`test_9f_…`, not run against a mutation).

---

## E1 — the writer's stamp

**neutralization** (`review_record.py`, `render_plan` → `single`; the hash is taken of the pre-flag, pre-shed record):
```python
-        stamped = dict(r, sentSha256=_sent_sha(r))
+        stamped = dict(r, sentSha256=_sent_sha(_scrubbed(record)))  # BITE-PROOF NEUTRALIZED
```

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_1c_a_record_holding_redacted_text_round_trips_with_only_its_redacted_field_flag _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-27/test_1c_a_record_holding_redac0')

    def test_1c_a_record_holding_redacted_text_round_trips_with_only_its_redacted_field_flag(tmp_path):
        # axis: the writer's stamp covers the record after the redaction flag, so the flag is not read as damage
        secret = "pass" + "word = " + "x" * 8
        fake = Fake()
        send(tmp_path, fake, findings=[finding(body="see " + secret)])
        rec = read_record(fake)
>       assert rec["transitDamage"] == {"redactedFields": ["findings[0].body"]}
E       AssertionError: assert {'redactedFie...tches': False} == {'redactedFie...ngs[0].body']}
E         
E         Omitting 1 identical items, use -vv to show
E         Left contains 1 more item:
E         {'sentHashMatches': False}
E         Use -v to get more diff

/home/user/wt-2383/plugins/superheroes/lib/tests/test_transit_record_2383.py:88: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_transit_record_2383.py::test_1c_a_record_holding_redacted_text_round_trips_with_only_its_redacted_field_flag
1 failed in 3.43s
```

**restore** (inverse Edit); **restore receipt**, the restored line:
```python
        stamped = dict(r, sentSha256=_sent_sha(r))
```
`git diff --stat -- plugins/superheroes/lib/review_record.py` after the restore: ` plugins/superheroes/lib/review_record.py | 80 +++++++++++++++++++++++++++++---` / `1 file changed, 73 insertions(+), 7 deletions(-)` (equal to the baseline line).

**raw green:**
```
.                                                                        [100%]
1 passed in 4.16s
```

## E2 — the reader's whole-record check

**neutralization** (`review_record.py`, `_parse_body`):
```python
-        return _sent_hash_damage(obj)  # axis: a whole record …
+        return obj  # BITE-PROOF NEUTRALIZED  # axis: a whole record …
```

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_2_a_record_whose_stored_json_lost_a_bang_reads_flagged_and_is_listed_by_the_next_write _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-29/test_2_a_record_whose_stored_j0')

    def test_2_a_record_whose_stored_json_lost_a_bang_reads_flagged_and_is_listed_by_the_next_write(tmp_path):
        # axis: the reader's whole-record check; a record changed in transit read as clean
        fake = StoreFake(drop_bangs)
        send(tmp_path, fake, findings=cdata_findings())
        assert "<![CDATA[" in fake.sent[1] and "<[CDATA[" in fake.comments[0]["body"]
>       assert read_record(fake)["transitDamage"]["sentHashMatches"] is False
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       KeyError: 'transitDamage'

/home/user/wt-2383/plugins/superheroes/lib/tests/test_transit_record_2383.py:98: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_transit_record_2383.py::test_2_a_record_whose_stored_json_lost_a_bang_reads_flagged_and_is_listed_by_the_next_write
1 failed in 3.82s
```

**restore** (inverse Edit); **restore receipt**, the restored line:
```python
        return _sent_hash_damage(obj)  # axis: a whole record …
```
`git diff --stat` after the restore: ` plugins/superheroes/lib/review_record.py | 80 +++++++++++++++++++++++++++++---` / `1 file changed, 73 insertions(+), 7 deletions(-)` (equal to the baseline line).

**raw green:**
```
.                                                                        [100%]
1 passed in 2.65s
```

## E3 — the reader's parts check

**neutralization** (`review_record.py`, `_resolve_parts`):
```python
-    rec = _sent_hash_damage(rec)  # axis: a parts record …
+    rec = rec  # BITE-PROOF NEUTRALIZED  # axis: a parts record …
```

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_2b_a_parts_record_whose_parts_lost_a_bang_reads_flagged_beside_the_hash_keys _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-31/test_2b_a_parts_record_whose_p0')

    def test_2b_a_parts_record_whose_parts_lost_a_bang_reads_flagged_beside_the_hash_keys(tmp_path):
        # axis: the reader's parts check; a parts record changed in transit flagged only by its length and hash
        fake = StoreFake(drop_bangs)
        send(tmp_path, fake, findings=parts_findings())
        assert any("<[CDATA[" in c["body"] for c in parts_of(fake))
        damage = read_record(fake)["transitDamage"]
>       assert damage["sentHashMatches"] is False and damage["hashMatches"] is False
               ^^^^^^^^^^^^^^^^^^^^^^^^^
E       KeyError: 'sentHashMatches'

/home/user/wt-2383/plugins/superheroes/lib/tests/test_transit_record_2383.py:112: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_transit_record_2383.py::test_2b_a_parts_record_whose_parts_lost_a_bang_reads_flagged_beside_the_hash_keys
1 failed in 2.84s
```

**restore** (inverse Edit); **restore receipt**, the restored line:
```python
    rec = _sent_hash_damage(rec)  # axis: a parts record …
```
`git diff --stat` after the restore: ` plugins/superheroes/lib/review_record.py | 80 +++++++++++++++++++++++++++++---` / `1 file changed, 73 insertions(+), 7 deletions(-)` (equal to the baseline line).

**raw green:**
```
.                                                                        [100%]
1 passed in 2.75s
```

## E4 — the legacy pass-through

**neutralization** (`review_record.py`, `_sent_hash_damage`; a record with no key falls through to the damage branch):
```python
-    if "sentSha256" not in rec:
-        return rec  # axis: a record written before the key existed …
-    if isinstance(rec["sentSha256"], str) and rec["sentSha256"] == _sent_sha(rec):
+    if False:  # BITE-PROOF NEUTRALIZED
+        return rec  # axis: a record written before the key existed …
+    if isinstance(rec.get("sentSha256"), str) and rec.get("sentSha256") == _sent_sha(rec):
```

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_4_a_record_without_sentsha256_is_read_unflagged _____________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-33/test_4_a_record_without_sentsh0')

    def test_4_a_record_without_sentsha256_is_read_unflagged(tmp_path):
        # axis: the legacy pass-through; a record written before the key existed read as damaged
        obj = stored_record(tmp_path)
        del obj["sentSha256"]
        rec = rr._parse_body(body_of(obj))
>       assert "sentSha256" not in rec and "transitDamage" not in rec
E       AssertionError: assert ('sentSha256' not in {'carriedRechecks': [], 'checked': ['CI on bbbbbbb: green', 'Reviewers that ran: code-reviewer', 'read the diff'], 'ci...state': 'green', ...}, 'cost': {'minutes': 2.0, 'notCounted': [], 'source': 'engine records', 'tokens': 100, ...}, ...} and 'transitDamage' not in {'carriedRechecks': [], 'checked': ['CI on bbbbbbb: green', 'Reviewers that ran: code-reviewer', 'read the diff'], 'ci...state': 'green', ...}, 'cost': {'minutes': 2.0, 'notCounted': [], 'source': 'engine records', 'tokens': 100, ...}, ...})

/home/user/wt-2383/plugins/superheroes/lib/tests/test_transit_record_2383.py:143: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_transit_record_2383.py::test_4_a_record_without_sentsha256_is_read_unflagged
1 failed in 2.70s
```

**restore** (inverse Edit); **restore receipt**, the restored lines:
```python
    if "sentSha256" not in rec:
        return rec  # axis: a record written before the key existed is read unflagged, never damaged — see bite-proof record i2383_transit_record
    if isinstance(rec["sentSha256"], str) and rec["sentSha256"] == _sent_sha(rec):
```
`git diff --stat` after the restore: ` plugins/superheroes/lib/review_record.py | 80 +++++++++++++++++++++++++++++---` / `1 file changed, 73 insertions(+), 7 deletions(-)` (equal to the baseline line).

**raw green:**
```
.                                                                        [100%]
1 passed in 2.71s
```

## E5 — `_create_comment`'s read-back

**neutralization** (`review_record.py`, `_create_comment`; the body is compared with itself):
```python
-            "transit": cloud_builder.transit_compare(body, found)}
+            "transit": cloud_builder.transit_compare(body, body)}  # BITE-PROOF NEUTRALIZED
```

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_5_create_comment_matched_changed_and_not_checked _____________

patched = {'held': {'body': 'see [a](b) here'}, 'args': ('api', 'repos/o/r/issues/comments/41')}

    def test_5_create_comment_matched_changed_and_not_checked(patched):
        # axis: the read-back of a created comment; compared with itself, or a failed read-back read as matched
        body = "see ![a](b) here"
        patched["held"] = {"body": body}
        got = rr._create_comment(7, "o/r", body)
        assert got == {"id": 41, "url": "http://c/41", "transit": {"transit": "matched"}}
        assert patched["args"] == ("api", "repos/o/r/issues/comments/41")
        patched["held"] = {"body": "see [a](b) here"}
        changed = rr._create_comment(7, "o/r", body)["transit"]
>       assert changed["transit"] == "changed" and any("!" in c["sent"] for c in changed["changes"])
E       AssertionError: assert ('matched' == 'changed'
E         
E         - changed
E         + matched)

/home/user/wt-2383/plugins/superheroes/lib/tests/test_transit_record_2383.py:183: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_transit_record_2383.py::test_5_create_comment_matched_changed_and_not_checked
1 failed in 2.42s
```

**restore** (inverse Edit); **restore receipt**, the restored line:
```python
            "transit": cloud_builder.transit_compare(body, found)}
```
`git diff --stat` after the restore: ` plugins/superheroes/lib/review_record.py | 80 +++++++++++++++++++++++++++++---` / `1 file changed, 73 insertions(+), 7 deletions(-)` (equal to the baseline line).

**raw green:**
```
.                                                                        [100%]
1 passed in 2.61s
```

## E6 — `write`'s aggregation

**neutralization** (`review_record.py`, `_transit_summary`; the overall is always `matched`):
```python
-    out = {"transitChecks": checks, "transit": overall}
+    out = {"transitChecks": checks, "transit": cloud_builder.TRANSIT_MATCHED}  # BITE-PROOF NEUTRALIZED
```

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_______________ test_6_write_reports_a_changed_head_and_names_it _______________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-37/test_6_write_reports_a_changed0')

    def test_6_write_reports_a_changed_head_and_names_it(tmp_path):
        # axis: write's aggregation; a changed comment reported as matched
        out = write_with(tmp_path, Fake(), lambda kind, n: CHANGED if kind == "head" else MATCHED,
                         rawFindingsFiles=[raw_file(tmp_path)])
>       assert out["ok"] and out["transit"] == "changed"
E       AssertionError: assert (True and 'matched' == 'changed'
E         
E         - changed
E         + matched)

/home/user/wt-2383/plugins/superheroes/lib/tests/test_transit_record_2383.py:236: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_transit_record_2383.py::test_6_write_reports_a_changed_head_and_names_it
1 failed in 2.68s
```

**restore** (inverse Edit); **restore receipt**, the restored line:
```python
    out = {"transitChecks": checks, "transit": overall}
```
`git diff --stat` after the restore: ` plugins/superheroes/lib/review_record.py | 80 +++++++++++++++++++++++++++++---` / `1 file changed, 73 insertions(+), 7 deletions(-)` (equal to the baseline line).

**raw green:**
```
.                                                                        [100%]
1 passed in 2.42s
```

## E7 — `vet_slot`'s comparison

**neutralization** (`vet_slot.py`, `_run_verb`; back to `_normalize` equality):
```python
-    compared = cloud_builder.transit_compare(new_body, readback)
-    if compared["transit"] != cloud_builder.TRANSIT_MATCHED:
-        raise _Refusal("write-unconfirmed", "%s; readback differs from the pushed body: %s"
-                       % (pushed, cloud_builder.transit_line(compared)))
+    if _normalize(readback) != _normalize(new_body):  # BITE-PROOF NEUTRALIZED
+        raise _Refusal("write-unconfirmed", "%s; readback differs from the pushed body" % pushed)
```

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_8a_a_readback_with_one_cloud_footer_is_confirmed _____________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-39/test_8a_a_readback_with_one_cl0')

    def test_8a_a_readback_with_one_cloud_footer_is_confirmed(tmp_path):
        # axis: the vet slot's comparison tolerates the one footer the cloud egress appends
        result, fake = write_slot(tmp_path, lambda f: setattr(f, "bodies", [f.edited[-1] + CLOUD_FOOTER]))
>       assert result["ok"] is True and len(fake.edit_calls()) == 1
E       assert (False is True)

/home/user/wt-2383/plugins/superheroes/lib/tests/test_transit_record_2383.py:325: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_transit_record_2383.py::test_8a_a_readback_with_one_cloud_footer_is_confirmed
1 failed in 2.57s
```

**restore** (inverse Edit); **restore receipt**, the restored lines:
```python
    compared = cloud_builder.transit_compare(new_body, readback)
    if compared["transit"] != cloud_builder.TRANSIT_MATCHED:
        raise _Refusal("write-unconfirmed", "%s; readback differs from the pushed body: %s"
                       % (pushed, cloud_builder.transit_line(compared)))
```
`git diff --stat -- plugins/superheroes/lib/vet_slot.py` after the restore: ` plugins/superheroes/lib/vet_slot.py | 8 ++++++--` / `1 file changed, 6 insertions(+), 2 deletions(-)` (equal to the baseline line).

**raw green:**
```
.                                                                        [100%]
1 passed in 2.83s
```

## E8 — `pr_body_stage`'s post-PATCH comparison

**neutralization** (`pr_body_stage.py`, `_publish`; back to the footer-strip comparison, `compared` still computed for the receipt):
```python
-    if compared["transit"] != cloud_builder.TRANSIT_MATCHED:
+    if after is None or not _same_body(cloud_builder.strip_cloud_footer(after), cloud_builder.strip_cloud_footer(staged)):  # BITE-PROOF NEUTRALIZED
```

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_9d_a_readback_that_lost_the_leading_indent_is_refused __________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-41/test_9d_a_readback_that_lost_t0')

    def test_9d_a_readback_that_lost_the_leading_indent_is_refused(tmp_path):
        # axis: only trailing whitespace is tolerated; a lost leading indent was hidden by strip_cloud_footer
        sd, out = publish_with(tmp_path, TPB.FIXED, fixed="    " + TPB.FIXED)
>       assert (out["ok"], out["reason"]) == (False, "pr-body-publish-unverified")
E       AssertionError: assert (True, None) == (False, 'pr-b...h-unverified')
E         
E         At index 0 diff: True != False
E         Use -v to get more diff

/home/user/wt-2383/plugins/superheroes/lib/tests/test_transit_record_2383.py:393: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_transit_record_2383.py::test_9d_a_readback_that_lost_the_leading_indent_is_refused
1 failed in 2.73s
```

**restore** (inverse Edit); **restore receipt**, the restored line:
```python
    if compared["transit"] != cloud_builder.TRANSIT_MATCHED:
```
`git diff --stat -- plugins/superheroes/lib/pr_body_stage.py` after the restore: ` plugins/superheroes/lib/pr_body_stage.py | 14 ++++++++++----` / `1 file changed, 10 insertions(+), 4 deletions(-)` (equal to the baseline line, which `--stat` printed as `14 ++++--` beside two other files).

**raw green:**
```
.                                                                        [100%]
1 passed in 2.73s
```

## E9 — `record_line`'s transit rendering

**neutralization** (`pr_body_stage.py`, `record_line`; the receipt's `transit` is ignored):
```python
-            transit = receipt.get("transit")
+            transit = None  # BITE-PROOF NEUTRALIZED
```

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
______ test_9b_a_readback_that_fails_is_not_checked_and_the_line_says_so _______

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-43/test_9b_a_readback_that_fails_0')

    def test_9b_a_readback_that_fails_is_not_checked_and_the_line_says_so(tmp_path):
        # axis: a read-back that cannot be made is not-checked, and the line says it was not checked
        sd = TPB._staged_fixed(tmp_path)
        views = iter([TPB._Done(0, json.dumps({"body": TPB.BODY})), TPB._Done(1)])

        def runner(argv):
            return next(views) if argv[2:4] != ["-X", "PATCH"] else TPB._Done(0)
        out = PBS.publish(sd, 7, runner=runner)
        assert (out["ok"], out["reason"]) == (False, "pr-body-publish-unverified")
        assert out["transit"]["transit"] == "not-checked"
>       assert "not checked" in PBS.record_line(sd)
E       AssertionError: assert 'not checked' in 'The review did not copy its PR-body fix onto the PR: the body read back from GitHub after the edit did not match.'
E        +  where 'The review did not copy its PR-body fix onto the PR: the body read back from GitHub after the edit did not match.' = <function record_line at 0x7f662846aac0>('/tmp/claude-0/pytest-of-root/pytest-43/test_9b_a_readback_that_fails_0/session')
E        +    where <function record_line at 0x7f662846aac0> = PBS.record_line

/home/user/wt-2383/plugins/superheroes/lib/tests/test_transit_record_2383.py:381: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_transit_record_2383.py::test_9b_a_readback_that_fails_is_not_checked_and_the_line_says_so
1 failed in 2.59s
```

**restore** (inverse Edit); **restore receipt**, the restored line:
```python
            transit = receipt.get("transit")
```
`git diff --stat` after the restore: ` plugins/superheroes/lib/pr_body_stage.py | 14 ++++++++++----` / `1 file changed, 10 insertions(+), 4 deletions(-)` (equal to the baseline line).

**raw green:**
```
.                                                                        [100%]
1 passed in 2.54s
```
