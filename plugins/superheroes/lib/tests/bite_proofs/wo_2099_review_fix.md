# Bite-proof — WO-C (#2099) review-fix batch, round 1

Declared guarded-element set (from the order): one element, G1. F2, F3 and F4 add axis comments
only and change no assertion, so they add no detector.

Redaction: none needed; the captures hold no secrets, tokens, private URLs or PII. The
`UV_NATIVE_TLS` deprecation warning line that `scripts/pinned-python` prints is left in.

## G1 — the strengthened `test_n2_without_a_note_ignore_the_key_is_absent`

**Guarded element:** `plugins/superheroes/lib/tests/test_wave_watch_builder_note.py`,
`test_n2_without_a_note_ignore_the_key_is_absent` (its `assert result["ok"] is True`, with the
`EVENT_TIMER` and `"ignoredNotes" not in result` assertions beside it).

**Axis:** valid inputs return a non-refusal result, and that result carries no `ignoredNotes`
without a note ignore. Both ignore inputs (`()` and the `("cloud-a", lane-stale)` class pair) are
valid. The fixture produced `event == timer` for both inputs and for both `run` and `watch_arm`, so
the order's `ww.EVENT_TIMER` assertion held as written and no other event was needed.

**Neutralization** (`plugins/superheroes/lib/wave_watch.py`, `_validate_ignore_events`, line 438;
a targeted Edit that makes a 2-tuple whose event is `lane-stale` return the refusal):

```
-        if event not in _SUPPRESSIBLE_EVENTS:
+        if event not in _SUPPRESSIBLE_EVENTS or event == EVENT_LANE_STALE:
             return _refusal(REFUSAL_IGNORE_EVENT_INVALID, batch_id, arms=arms)
```

**Raw red** (detector unedited; command
`scripts/pinned-python -B -X pycache_prefix=/tmp/claude-0/pyc-wo-c -m pytest "plugins/superheroes/lib/tests/test_wave_watch_builder_note.py::test_n2_without_a_note_ignore_the_key_is_absent" -q -p no:cacheprovider`;
exit 1). It is red on the declared axis, the non-refusal assertion `result["ok"] is True`:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_______________ test_n2_without_a_note_ignore_the_key_is_absent ________________

repo = '/tmp/claude-0/pytest-of-root/pytest-31/test_n2_without_a_note_ignore_0/repo'

    def test_n2_without_a_note_ignore_the_key_is_absent(repo):
        # axis: valid inputs return a non-refusal result — and that result carries no ignoredNotes without a note ignore
        _cloud_lane(repo, "cloud-a", 101)
        gh = _NoteGh([_comment(7, 101, "chatter")])
        pair = (("cloud-a", ww.EVENT_LANE_STALE),)
        for ignore in ((), pair):
            ran = ww.run(repo, _BATCH, gh_run=gh, ignore_events=ignore)
            armed = ww.watch_arm(
                repo, _BATCH, max_seconds=1, interval_seconds=1, gh_run=gh, ignore_events=ignore,
            )
            for result in (ran, armed):
>               assert result["ok"] is True
E               assert False is True

/home/user/wt-2099-c/plugins/superheroes/lib/tests/test_wave_watch_builder_note.py:739: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_builder_note.py::test_n2_without_a_note_ignore_the_key_is_absent
1 failed in 0.48s
```

**Restore:** the inverse Edit, putting the line back to
`        if event not in _SUPPRESSIBLE_EVENTS:` (no `or event == EVENT_LANE_STALE`).

**Restore receipt:** `git status --porcelain plugins/superheroes/lib/wave_watch.py` printed nothing
(empty output, so the file is byte-identical to the build head). The restored lines, read back:

```
438:        if event not in _SUPPRESSIBLE_EVENTS:
439:            return _refusal(REFUSAL_IGNORE_EVENT_INVALID, batch_id, arms=arms)
440:    return None
```

**Raw green** (same command, after the restore; exit 0):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 4.03s
```
