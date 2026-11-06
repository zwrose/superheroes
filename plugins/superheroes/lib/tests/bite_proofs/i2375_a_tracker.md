# Bite-proof record — the codex stream tracker never reads a line it cannot read as idle (#2375, order A)

Detector file: `plugins/superheroes/lib/tests/test_codex_silence.py`, unedited between each red and its green. Production file: `plugins/superheroes/lib/codex_silence.py`. Every neutralization is a targeted edit made and undone with the edit tool, at commit `67377500`. Runs: `scripts/pinned-python -B -m pytest plugins/superheroes/lib/tests/test_codex_silence.py -q`, the whole file each time; the captures below quote each run's `FAILED` lines and summary line (tracebacks elided, each under a few KB). No secret, token, URL or personal data appears in any capture, so nothing is redacted. The five guarded elements are the five the order declared. Proofs re-run by the builder after the implementer's own run; both sets agree.

## G1. Item not an object, or its type not a string (`StreamTracker._line`)

- **Axis:** an item event whose item or type cannot be read may hide a command, so the stream is sticky `unknown`.
- **Neutralization:** the `self._unknown = True` line under `# axis: an item event whose item or type cannot be read …` deleted.
- **Raw red:** `7 failed, 103 passed` — `test_tracker_item_event_with_a_bad_item_shape_is_sticky_unknown[E1-started-item-missing]`, `[E2-started-item-list]`, `[E3-type-missing]`, `[E4-type-number]`, `[E5-completed-item-not-object]`, `[E5b-completed-item-null]`, `[E3b-completed-type-missing]`.
- **Restore:** the line re-inserted by the inverse edit. **Restore receipt:** `git status --porcelain` empty after the last restore. **Raw green:** `110 passed`.

## G2. An action item whose id cannot be read (`StreamTracker._line`)

- **Axis:** an action item whose id is missing, a bool, or not a str/int can never be closed, so the stream is sticky `unknown`.
- **Neutralization:** the `self._unknown = True` line under `# axis: an action item whose id cannot be read …` deleted.
- **Raw red:** `6 failed, 104 passed` — `test_tracker_action_item_with_a_bad_id_is_sticky_unknown[E6-id-missing]`, `[E7-id-null]`, `[E8-id-list]`, `[E9-id-true]`, `[E6b-completed-id-missing]`, and `test_sampler_stream_with_an_action_start_without_an_id_is_stream_unknown`.
- **Restore:** inverse edit. **Raw green:** `110 passed`.

## G3. A start of an unnamed item type, short line (`StreamTracker._line`)

- **Axis:** an `item.started` of a type that is neither an action type nor in `NON_ACTION_ITEM_TYPES` may open a command, so `unknown`.
- **Neutralization:** `self._unknown = True` under `# axis: a started item of an unnamed type …` replaced by `pass`.
- **Raw red:** `1 failed, 109 passed` — `test_tracker_started_item_of_an_unnamed_type_is_sticky_unknown`.
- **Restore:** inverse edit. **Raw green:** `110 passed`.

## G4. A start of an unnamed item type, over-long line (`_classify_head`)

- **Axis:** the same rule on the over-long head path.
- **Neutralization:** `return None` under `# axis: an over-long start of an unnamed item type …` changed to `return _NO_EFFECT`.
- **Raw red:** `1 failed, 109 passed` — `test_tracker_overlong_started_item_of_an_unnamed_type_is_sticky_unknown`. G3's neutralization leaves this test green and G4's leaves G3's green: the two sites are proven separately.
- **Restore:** inverse edit. **Raw green:** `110 passed`.

## G5. Growth counts as "did not grow" only when exactly `False` (`silent_and_idle`)

- **Axis:** a growth that could not be read (`None`, a falsy non-bool) never counts as silence.
- **Neutralization:** `return stdout_grew is False and stderr_grew is False and tracker_state == STATE_IDLE` changed back to `return (not stdout_grew) and (not stderr_grew) and tracker_state == STATE_IDLE`.
- **Raw red:** `7 failed, 103 passed` — `test_silent_and_idle_unread_growth_is_never_silence[E12-stdout-none]`, `[E13-stderr-none]`, `[E14-falsy-ints]`, `[both-none]`, `[stdout-zero]`, `[stderr-zero]`, `[stdout-empty-string]`.
- **Restore:** inverse edit; `git status --porcelain` empty. **Raw green:** `110 passed in 1.87s`.
