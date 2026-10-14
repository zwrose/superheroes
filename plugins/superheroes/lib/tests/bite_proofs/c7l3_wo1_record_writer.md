# C7 L3 WO-1 bite-proof record: the review record writer

**Status: no bite-proof was run.** The implementer stopped at rung 2 of the command-precedence ladder, because the
development run over the four scoped test files ended with failures (see the return). Every entry below names the
guarded element, its axis and the neutralization and test chosen, and nothing else: there is no red, no restore and no
green here, and none is claimed. `Unrunnable here` for all five until an implementer re-runs them.

Declared guarded-element set (five): the axis lines in `plugins/superheroes/lib/review_record.py` cite this record.

| ID | Guarded element | Axis | Neutralization (to apply) | Test node (to run alone) |
|---|---|---|---|---|
| BP-1 | `_resolve_parts`, the sha256 comparison | the joined parts must hash to what the head recorded | in `_resolve_parts`, `if len(text) != chars or hashlib.sha256(text.encode("utf-8")).hexdigest() != digest:` becomes `if len(text) != chars:` | `test_review_record_fit_c7l3.py::test_edge2_a_corrupted_part_fails_the_hash_check` |
| BP-2 | `_marker_comments`, a part comment is not a record | a part comment never becomes the latest record | `startswith(MARKER)` becomes `startswith((MARKER, PART_MARKER))` | `test_review_record_fit_c7l3.py::test_edge4_a_part_comment_is_never_the_latest_record` |
| BP-3 | `_recheck_decisions`, the write-time Canon re-check | a ruling stands only while its cited decision is on record | `ok, text = finding_outcomes.on_record(by, sources())` becomes `ok, text = True, "x"` | `test_review_record_fit_c7l3.py::test_a_ruling_citing_an_entry_that_is_not_on_record_goes_to_the_owner` |
| BP-4 | `build_record`, the go-ahead's Canon check | a standing-ruling go-ahead counts only with its Canon entry on record | `good = next((g for g in complete if canon_on_record(g)), None)` becomes `good = next(iter(complete), None)` | `test_review_record_fit_c7l3.py::test_a_standing_ruling_go_ahead_counts_only_when_its_canon_entry_is_on_record` |
| BP-5 | `_lane_reason`, the leading-punctuation strip | punctuation joining the lane word to its reason is not the reason | `return _REASON_LEAD_RE.sub("", text or "").strip() or None` becomes `return (text or "").strip() or None` | `test_review_record_fit_c7l3.py::test_a_lane_reason_has_no_leading_punctuation[**Lane call:** full, inherited from #1814: why-inherited from #1814: why]` |

Raw red, restore, restore receipt and raw green: not produced.
