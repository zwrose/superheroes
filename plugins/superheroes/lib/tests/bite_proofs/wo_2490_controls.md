# Bite-proof record: wo_2490_controls

Issue 2490. Detector file: `plugins/superheroes/lib/tests/test_review_record_controls_2490.py`. Guarded file:
`plugins/superheroes/lib/review_record.py`. Every run was `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2490 -m pytest <exact node id> -q -p no:cacheprovider`
from the worktree root, with the detector unedited between the red and the green run. Each node id below is
`plugins/superheroes/lib/tests/test_review_record_controls_2490.py::<name>`. Each neutralization is one targeted edit,
undone by the inverse edit. After G10 the diff of `review_record.py` against its head shows only the change 1 and 2
edits and no neutralization left: every axis line, and the lines each proof touched, read as before.

Captures are trimmed to the decisive lines (the pytest header and the repeated traceback are elided; each run was
well under 32 KiB). Nothing in them is a secret, token, private URL or personal data, so nothing is redacted.

## G1 the `_visible_controls` call in `_scrub_text` (`review_record.py`, `_scrub_text`)

- Axis: a record string holding a code GitHub rewrites reads back whole; no record string reaches the JSON dump holding such a code.
- Detector: `test_t1_a_finding_with_control_codes_is_written_and_read_back_in_stand_in_form[one-comment]`
- Neutralization: `text = _visible_controls(text)` became `text = text`.
- Raw red: `assert out["ok"], out` failed with `{'ok': False, 'reason': 'review-record-unreadable-after-write', 'detail': 'http://c/1 was posted but does not read bac... found "^["; line 19: sent "u0007", found "^G"; line 19: sent "u0000", found "^@"; line 19: sent "u009b", found "^[".'}`, then `1 failed in 2.66s`.
- Restore: the inverse edit, `text = text` back to `text = _visible_controls(text)`. Restore receipt: the line reads `text = _visible_controls(text)` followed by its axis comment, and the final diff shows no change on it.
- Raw green: `1 passed in 2.55s`.

## G2 the stand-in on keys in `_scrubbed` (`shown = _visible_controls(k)`)

- Axis: a dict key holding a code GitHub rewrites is posted as its stand-in.
- Detector: `test_t3_a_key_holding_a_control_is_stood_in`
- Neutralization: `shown = _visible_controls(k) if isinstance(k, str) else k` became `shown = k if isinstance(k, str) else k`.
- Raw red: `AssertionError: assert {'a\x01b': 1, 'c\x9b': 2} == {'a␁b': 1, 'c[U+009B]': 2}`, then `1 failed in 2.33s`.
- Restore: the inverse edit. Restore receipt: the line reads `shown = _visible_controls(k) if isinstance(k, str) else k` followed by its axis comment.
- Raw green: `1 passed in 2.37s`.

## G3 the key-collision numbering loop (`_scrubbed`, the `elif shown != k` branch)

- Axis: a stood-in name that lands on a taken name is numbered; both entries are kept, none overwritten or lost.
- Detectors (both parametrizations, one invocation): `test_t3_a_stood_in_key_that_meets_a_literal_picture_key_keeps_both_entries[stand-in-first]` and `test_t3_a_stood_in_key_that_meets_a_literal_picture_key_keeps_both_entries[literal-first]`
- Neutralization: `while nk in out or nk in value:` became `while False:` (in the stood-in branch only; the `[REDACTED KEY]` loop is untouched).
- Raw red: `assert len(out) == 2 ...` failed in both: `assert (1 == 2) where 1 = len({'a␀': 'literal'})` for `[stand-in-first]` and `where 1 = len({'a␀': 'from-nul'})` for `[literal-first]`, then `2 failed in 2.56s`.
- Restore: the inverse edit. Restore receipt: the line reads `while nk in out or nk in value:` followed by its axis comment.
- Raw green: `2 passed in 2.67s`.

## G4 the 7-bit ANSI removal (`_strip_ansi` in `_visible_controls`)

- Axis: ANSI escape sequences leave nothing behind; an ESC that starts none is shown, never dropped.
- Detector: `test_t2_ansi_sequences_are_removed_and_a_lone_esc_is_stood_in`
- Neutralization: `return _strip_ansi(text).translate(_CONTROL_STANDINS)` became `return text.translate(_CONTROL_STANDINS)`.
- Raw red: `assert visible("x" + ESC + "[31;1mred" + ESC + "[0m") == "xred"` failed with `AssertionError: assert 'x␛[31;1mred␛[0m' == 'xred'`, then `1 failed in 2.60s`.
- Restore: the inverse edit. Restore receipt: the line reads `return _strip_ansi(text).translate(_CONTROL_STANDINS)` followed by its axis comment.
- Raw green: `1 passed in 2.80s`.

## G5 the `_visible_controls` result posted by `render_raw` (`pr_comment.scrub(shown)`)

- Axis: the raw comment posts no code GitHub rewrites.
- Detector: `test_t4_a_raw_output_with_colour_codes_posts_no_rewritable_code_and_reads_back_matched`
- Neutralization: `text = pr_comment.scrub(shown)` became `text = pr_comment.scrub(text)`.
- Raw red: `assert not rewritable(comment["body"]) and not re.search(r"\^[@-_]", comment["body"])` failed; the stored body held `run ^[[31mFAIL^[[0m^G done`, then `1 failed in 2.49s`.
- Restore: the inverse edit. Restore receipt: the line reads `text = pr_comment.scrub(shown)` followed by its axis comment.
- Raw green: `1 passed in 2.73s`.

## G6 the re-parse on `changed` (`write`, the call of `_refuse_unless_read_back`)

- Axis: a changed read-back is parsed again; a record that does not parse refuses.
- Detector: `test_t5_e4_a_head_whose_json_no_longer_parses_arrives_changed_and_refuses`
- Neutralization: `if summary["transit"] != cloud_builder.TRANSIT_NOT_CHECKED:` became `if summary["transit"] not in (cloud_builder.TRANSIT_NOT_CHECKED, cloud_builder.TRANSIT_CHANGED):`.
- Raw red: the first assertion (the head arrived `changed`) passed; `refused(out, fake)` failed with `AssertionError: {'ok': True, 'action': 'created', 'url': 'http://c/1', 'parts': 0, ...}`, then `1 failed in 2.88s`.
- Restore: the inverse edit. Restore receipt: the line reads `if summary["transit"] != cloud_builder.TRANSIT_NOT_CHECKED:`.
- Raw green: `1 passed in 2.60s`.

## G7 the re-parse on `matched` (same call)

- Axis: a matched read-back is parsed again; CRLF framing matches yet the JSON block is not found.
- Detector: `test_t5_e4_crlf_framing_arrives_matched_and_refuses`
- Neutralization: the same line became `if summary["transit"] not in (cloud_builder.TRANSIT_NOT_CHECKED, cloud_builder.TRANSIT_MATCHED):`.
- Raw red: the first assertion (every comment `matched`) passed; `refused(out, fake)` failed with `AssertionError: {'ok': True, 'action': 'created', 'url': 'http://c/1', 'parts': 0, ...}`, then `1 failed in 2.50s`.
- Restore: the inverse edit. Restore receipt: the line reads `if summary["transit"] != cloud_builder.TRANSIT_NOT_CHECKED:`.
- Raw green: `1 passed in 2.81s`.

## G8 the marker predicate on the re-listed head (`_refuse_unless_read_back`)

- Axis: the marker predicate `read` uses decides which listed comment is the record.
- Detector: `test_t5_e3_a_head_whose_marker_was_damaged_refuses`
- Neutralization: `listed = next((c for c in _marker_comments(comments) if c["id"] == head["id"]), None)` became `listed = next((c for c in comments if c["id"] == head["id"]), None)`.
- Raw red: `refused(...)` failed with `AssertionError: {'ok': True, 'action': 'created', 'url': 'http://c/1', 'parts': 0, ...}`, then `1 failed in 2.94s`.
- Restore: the inverse edit. Restore receipt: the line reads `listed = next((c for c in _marker_comments(comments) if c["id"] == head["id"]), None)`.
- Raw green: `1 passed in 2.48s`.

## G9 the listing-failure refusal after the write (`_refuse_unless_read_back`)

- Axis: a failed re-listing refuses with `review-record-gh-failed`; the write is never ok when the record could not be read back.
- Detector: `test_t5_e1_a_listing_that_fails_after_the_write_refuses_gh_failed`
- Neutralization: the two-line `comments = _comments(rd, pr, repo, f"{where}: the comments were posted, ...")` call became `comments = rd["list_comments"](pr, repo) or []`.
- Raw red (the expected red: a result whose reason is not `review-record-gh-failed`): `out = {'ok': False, 'reason': 'review-record-unreadable-after-write', 'detail': 'http://c/1 was posted but does not read back: the comment is missing'}`, `assert (False is False and 'review-recor...e-after-write' == 'review-record-gh-failed'`, then `1 failed in 2.76s`.
- Restore: the inverse edit, both lines of the original call put back. Restore receipt: the lines read `comments = _comments(rd, pr, repo, f"{where}: the comments were posted, but the PR comments could not be listed to read "` and `"the record back after the write")`.
- Raw green: `1 passed in 2.44s`.

## G10 a C1 code never starts a removed sequence (`_ANSI_START` and `_CSI`)

- Axis: a C1 code never starts a removed sequence, so a lone 0x9B or 0x9D keeps the text after it.
- Detector: `test_t2_ansi_sequences_are_removed_and_a_lone_esc_is_stood_in`, the assertion `visible(chr(0x9B) + "31mX") == "[U+009B]31mX"`.
- Neutralization: 0x9B restored as a CSI introducer: `_ANSI_START = re.compile("\x1b")` became `re.compile("[\x1b\x9b]")` and `_CSI = re.compile("\x1b\\[[0-?]*[ -/]*[@-~]")` became `re.compile("(?:\x1b\\[|\x9b)[0-?]*[ -/]*[@-~]")`.
- Raw red: every 7-bit assertion before it passed; `assert visible(chr(0x9B) + "31mX") == "[U+009B]31mX"` failed with `AssertionError: assert 'X' == '[U+009B]31mX'`, then `1 failed in 2.48s`.
- Restore: the inverse edit, both definitions. Restore receipt: the lines read `_ANSI_START = re.compile("\x1b")` and `_CSI = re.compile("\x1b\\[[0-?]*[ -/]*[@-~]")`.
- Raw green: `1 passed in 2.83s`.

## G11 and G12, added at the review's fix step (round 1, finding v0)

The build session typed this fix at the review's `apply-fixes` step and produced these two entries itself, in a detached probe worktree at `c62a39e5`. The script applied each neutralization as one exact-once replacement, ran the detector by exact node id, restored by the inverse replacement, checked the file's sha256 equals the original's (byte-clean for both), and ran the detector green. The test value is eight `x` characters; nothing was redacted.

### G11 the original-text leg of `_scrub_text`'s secret check

- Axis: the secret check runs on the original text, so a stand-in (a C1 code becoming `[U+00XX]`) or a removed ANSI sequence never hides a credential the original showed.
- Detector: `test_t3_a_record_string_whose_original_or_stand_in_holds_a_credential_is_withheld[c1-gap]` and `[ansi-eats-key-letter]`.
- Neutralization: `if _has_secret(text) or _has_secret(shown):` became `if _has_secret(shown):`.
- Raw red: `AssertionError: assert 'password[U+009B]: xxxxxxxx' == '[REDACTED FIELD]'` and `AssertionError: assert 'assword: xxxxxxxx' == '[REDACTED FIELD]'`, then `2 failed in 4.98s`.
- Restore: the inverse replacement. Restore receipt: the line reads `if _has_secret(text) or _has_secret(shown):`, sha256 equal to the original.
- Raw green: `2 passed in 3.07s`.

### G12 the stand-in-text leg of `_scrub_text`'s secret check

- Axis: the secret check also runs on the text that would be posted, so removing an ANSI sequence never builds a posted credential.
- Detector: `test_t3_a_record_string_whose_original_or_stand_in_holds_a_credential_is_withheld[secret-only-once-stood-in]`.
- Neutralization: `if _has_secret(text) or _has_secret(shown):` became `if _has_secret(text):`.
- Raw red: `AssertionError: assert 'password = xxxxxxxx' == '[REDACTED FIELD]'`, then `1 failed in 4.65s`.
- Restore: the inverse replacement. Restore receipt: the line reads `if _has_secret(text) or _has_secret(shown):`, sha256 equal to the original.
- Raw green: `1 passed in 2.72s`.
