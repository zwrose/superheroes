# Bite-proof record — the review record names each silence-watchdog end (#2375, order C)

Detector files: `plugins/superheroes/lib/tests/test_review_record.py` and `plugins/superheroes/lib/tests/test_review_record_session.py`, unedited between each red and its green. Production files: `plugins/superheroes/lib/review_record.py` and `plugins/superheroes/lib/review_record_session.py`. Every neutralization is a targeted edit made and undone with the edit tool, at commit `28c158c7`. Runs: `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_review_record.py plugins/superheroes/lib/tests/test_review_record_session.py -q -n auto`; the captures quote each run's `FAILED` lines and summary line, tracebacks elided. Nothing is redacted (no secret, token, URL or personal data appears). The five guarded elements are the five the order declared. Proofs re-run by the builder after the implementer's own run; both sets agree.

## K1. A run dir no reviewer row binds is still read (`review_record_session._watchdog_ends`)

- **Axis:** a forfeited seat's dir binds no row, and its ends must still reach the record.
- **Neutralization:** `if name is None: continue` inserted before `base = os.path.basename(...)`.
- **Raw red:** `2 failed, 496 passed` — `test_a_forfeited_seat_and_a_seat_that_answered_after_a_retry_are_both_named`, `test_r4_a_bound_dir_takes_the_row_name_an_unbound_dir_its_role_and_name_and_no_role_reads_unknown`.
- **Restore:** the inserted lines removed. **Raw green:** `498 passed`.

## K2. The account validation of `silenceWatchdogEnds` (`review_record._validate`)

- **Neutralization:** `chk(isinstance(ends, list) and all(` changed to `chk(True or isinstance(ends, list) and all(`.
- **Raw red:** `15 failed, 483 passed` — every `test_r5_a_malformed_part_is_refused_by_name[...]` case (`ends`, `ends0` … `ends13`).
- **Restore:** inverse edit. **Raw green:** `498 passed`.

## K3. The record carries the part (`review_record.build_record`)

- **Neutralization:** `if a.get("silenceWatchdogEnds") else {}` changed to `if False and a.get("silenceWatchdogEnds") else {}`.
- **Raw red:** `5 failed, 493 passed` — `test_a_well_formed_part_is_carried_whole_and_shown_in_the_summary`, `test_r6_level_zero_lists_every_end_and_the_compact_levels_give_only_the_count`, `test_r7_a_seat_the_scrubber_would_hide_reads_redacted_seat`, `test_a_seat_named_like_a_bug_free_claim_does_not_refuse_the_summary`, `test_a_forfeited_seat_and_a_seat_that_answered_after_a_retry_are_both_named`.
- **Restore:** inverse edit. **Raw green:** `498 passed`.

## K4. The full level names every end (`review_record._watchdog_line`)

- **Neutralization:** `if level >= 1:` (the compact branch) changed to `if level >= 0:`, so level 0 also gives only the count.
- **Raw red:** `5 failed, 493 passed` — the same five tests as K3, each reading the count form where the named list is asserted.
- **Restore:** inverse edit. **Raw green:** `498 passed`.

## K5. The compact levels give only the count (`review_record._watchdog_line`)

- **Neutralization:** `if level >= 1:` changed to `if level >= 99:`, so every level lists every end.
- **Raw red:** `1 failed, 497 passed` — `test_r6_level_zero_lists_every_end_and_the_compact_levels_give_only_the_count`.
- **Restore:** inverse edit; `git status --porcelain` empty. **Raw green:** `498 passed in 7.61s`.
