# Bite-proof record: i2389_vet_slot_md_hidden (#2389, layer 2 of #2366) `vet_slot.py` reads what GitHub hides

Detector under proof: `plugins/superheroes/lib/tests/test_vet_slot_md_hidden_2389.py` (unedited; the `test_g1_` to `test_g6_` tests).
Guarded code: `plugins/superheroes/lib/vet_slot.py` at head `3b78f809`. Every neutralization was one targeted edit made with
the Edit tool and undone by the inverse Edit before the next element. No `git checkout`, `restore`, `reset`, `stash`, `sed`
or shell edit was used. After G6, `git diff --stat plugins/superheroes/lib/vet_slot.py` printed nothing: `vet_slot.py` is
byte-identical to `3b78f809`. Line numbers below are the head's.
Command for every run (worktree root), `N` the guard's number:
`timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_vet_slot_md_hidden_2389.py -q -p no:cacheprovider -k test_gN_`

Guarded-element set (declared by the order): G1 to G6, no others.

Disclosures:
- Every capture is the runner's output **verbatim except uv's one `UV_NATIVE_TLS` deprecation warning line**, which begins
  every run and is dropped. Nothing was redacted.
- **Truncated captures.** The tool that ran the commands cut the middle (and, for G1 and G4, the end) of the long failure
  listings. Those captures are labelled *incomplete* below and are not reconstructed. Where a capture lost its summary lines,
  the entry says so. G1 was re-run once with `--tb=no` added (the order's one spare run) so the summary lines exist for it;
  **G5 and G6 reds were also run with `--tb=no` added** (a deviation from the order's exact command, to keep the summary
  inside the tool's output limit; the tests were not edited and `--tb` only drops the traceback text). The green halves all
  use the order's exact command. **G4's red summary lines were lost and there was no run left to recover them.**
- Each `-k` matched the expected tests (the summary's `deselected` count is never the whole file).
- G4 is one declared element covering three checks (marker line, slot line, appended heading). Its single neutralization
  removes the whole bot-path call, so this record does not show each of the three checks biting alone.

## G1: only a `VISIBLE` heading counts (`_live_heading_offsets` / `check_not_emptied`)

- **Guarded element / axis:** `vet_slot.py:229-231`, `if state == md_hidden.VISIBLE:` in `_live_heading_offsets` (consumed
  by `check_not_emptied`, `:262`). Axis: the owner-half heading must be one GitHub renders; a heading `md_hidden` reads
  `HIDDEN` or `UNSURE` never counts, so `check_not_emptied` refuses where GitHub hides the owner heading.
- **Neutralization:** `vet_slot.py:230` `        if state == md_hidden.VISIBLE:` became `        if True:` (every heading counts).
- **Raw red, the order's command (incomplete: the tool cut 20012 characters from the middle and the tail; the summary
  lines are in the next capture).** The visible head:

```
....FFFF........F..F..........FFFF......FF.F.F.FFFF.F.....F........FFFFF [ 94%]
F...                                                                     [100%]
=================================== FAILURES ===================================
_ test_g1_visible_headings_only_builder_form_oracle[pre_quoted_opener-builder] _
...
>           assert refusal is not None, "GitHub hides the owner heading but check_not_emptied passes: %r" % row["id"]
E           AssertionError: GitHub hides the owner heading but check_not_emptied passes: 'pre_quoted_opener'
E           assert None is not None

/home/user/sh-2389/plugins/superheroes/lib/tests/test_vet_slot_md_hidden_2389.py:143: AssertionError
```

- **Raw red, summary (same `-k`, `--tb=no` added, the spare run):**

```
....FFFF........F..F..........FFFF......FF.F.F.FFFF.F.....F........FFFFF [ 94%]
F...                                                                     [100%]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_vet_slot_md_hidden_2389.py::test_g1_visible_headings_only_builder_form_oracle[pre_quoted_opener-builder]
FAILED plugins/superheroes/lib/tests/test_vet_slot_md_hidden_2389.py::test_g1_visible_headings_only_builder_form_oracle[pre_raw_opener-builder]
FAILED plugins/superheroes/lib/tests/test_vet_slot_md_hidden_2389.py::test_g1_visible_headings_only_builder_form_oracle[div_plain_closer-builder]
FAILED plugins/superheroes/lib/tests/test_vet_slot_md_hidden_2389.py::test_g1_visible_headings_only_builder_form_oracle[div_escaped_closer-builder]
FAILED plugins/superheroes/lib/tests/test_vet_slot_md_hidden_2389.py::test_g1_visible_headings_only_builder_form_oracle[decl_block-builder]
FAILED plugins/superheroes/lib/tests/test_vet_slot_md_hidden_2389.py::test_g1_visible_headings_only_builder_form_oracle[div_then_quoted-builder]
FAILED plugins/superheroes/lib/tests/test_vet_slot_md_hidden_2389.py::test_g1_visible_headings_only_builder_form_oracle[quote_tab_div-builder]
FAILED plugins/superheroes/lib/tests/test_vet_slot_md_hidden_2389.py::test_g1_visible_headings_only_builder_form_oracle[crlf_div-builder]
FAILED plugins/superheroes/lib/tests/test_vet_slot_md_hidden_2389.py::test_g1_visible_headings_only_builder_form_oracle[cr_div-builder]
FAILED plugins/superheroes/lib/tests/test_vet_slot_md_hidden_2389.py::test_g1_visible_headings_only_builder_form_oracle[alert_div-builder]
FAILED plugins/superheroes/lib/tests/test_vet_slot_md_hidden_2389.py::test_g1_visible_headings_only_builder_form_oracle[script_attr_opener-builder]
FAILED plugins/superheroes/lib/tests/test_vet_slot_md_hidden_2389.py::test_g1_visible_headings_only_builder_form_oracle[unclosed_attr-builder]
FAILED plugins/superheroes/lib/tests/test_vet_slot_md_hidden_2389.py::test_g1_visible_headings_only_builder_form_oracle[list_div_opener-builder]
FAILED plugins/superheroes/lib/tests/test_vet_slot_md_hidden_2389.py::test_g1_visible_headings_only_builder_form_oracle[quote_opener_ends-builder]
FAILED plugins/superheroes/lib/tests/test_vet_slot_md_hidden_2389.py::test_g1_visible_headings_only_builder_form_oracle[source_tag-builder]
FAILED plugins/superheroes/lib/tests/test_vet_slot_md_hidden_2389.py::test_g1_visible_headings_only_builder_form_oracle[search_tag-builder]
FAILED plugins/superheroes/lib/tests/test_vet_slot_md_hidden_2389.py::test_g1_visible_headings_only_builder_form_oracle[noscript_tag-builder]
FAILED plugins/superheroes/lib/tests/test_vet_slot_md_hidden_2389.py::test_g1_visible_headings_only_builder_form_oracle[setext_then_opener-builder]
FAILED plugins/superheroes/lib/tests/test_vet_slot_md_hidden_2389.py::test_g1_visible_headings_only_builder_form_oracle[type7_alone-builder]
FAILED plugins/superheroes/lib/tests/test_vet_slot_md_hidden_2389.py::test_g1_visible_headings_only_builder_form_oracle[div_title_unclosed_mid-builder]
FAILED plugins/superheroes/lib/tests/test_vet_slot_md_hidden_2389.py::test_g1_visible_headings_only_model_only_builder_on_sent_bytes[div_u2028_then_quoted-builder]
FAILED plugins/superheroes/lib/tests/test_vet_slot_md_hidden_2389.py::test_g1_visible_headings_only_model_only_builder_on_sent_bytes[div_nel_then_quoted-builder]
FAILED plugins/superheroes/lib/tests/test_vet_slot_md_hidden_2389.py::test_g1_visible_headings_only_model_only_builder_on_sent_bytes[div_ff_then_quoted-builder]
FAILED plugins/superheroes/lib/tests/test_vet_slot_md_hidden_2389.py::test_g1_visible_headings_only_model_only_builder_on_sent_bytes[cdata_block-builder]
FAILED plugins/superheroes/lib/tests/test_vet_slot_md_hidden_2389.py::test_g1_visible_headings_only_model_only_builder_on_sent_bytes[crlf_div-builder]
FAILED plugins/superheroes/lib/tests/test_vet_slot_md_hidden_2389.py::test_g1_visible_headings_only_model_only_builder_on_sent_bytes[cr_div-builder]
26 failed, 50 passed, 204 deselected in 0.96s
```

  The red is on the owner-heading axis: `check_not_emptied` returns no refusal (`refusal is None`) where GitHub hides the owner heading.
- **Restore:** inverse Edit, `if True:` back to `if state == md_hidden.VISIBLE:`.
- **Restore receipt:** the file search returned `230:        if state == md_hidden.VISIBLE:`.
- **Raw green** (the order's command):

```
........................................................................ [ 94%]
....                                                                     [100%]
76 passed, 204 deselected in 0.98s
```

## G2: the `![` image exclusion in `check_not_emptied`

- **Guarded element / axis:** `vet_slot.py:263`, the `"![" not in text` condition of `held`. Axis: an image heading (its text
  holds `![`) is never the owner-half heading, so `check_not_emptied` still refuses `body-emptied` for it.
- **Neutralization:** `vet_slot.py:263` `if at < limit and "![" not in text and _heading_key(text)...` became
  `if at < limit and _heading_key(text)...` (the `"![" not in text and ` clause removed).
- **Raw red:**

```
FF.                                                                      [100%]
=================================== FAILURES ===================================
_______________ test_g2_image_heading_is_never_the_owner_heading _______________

    def test_g2_image_heading_is_never_the_owner_heading():
        refusal = _emptied(IMAGE_OWNER_BODY)
>       assert refusal is not None and "What's changing, and why" in refusal.detail
E       assert (None is not None)

/home/user/sh-2389/plugins/superheroes/lib/tests/test_vet_slot_md_hidden_2389.py:277: AssertionError
_____________ test_g2_image_heading_through_evaluate_and_run_verb ______________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-31/test_g2_image_heading_through_0')

    def test_g2_image_heading_through_evaluate_and_run_verb(tmp_path):
        result = _evaluate(IMAGE_OWNER_BODY, receipt=RECEIPT)
>       assert result["ok"] is False and result["reason"] == "body-emptied", result
E       AssertionError: {'ok': True, 'verb': 'write', 'followups': ['FU1', 'FU2'], 'receipt': 'https://x/c/1', ...}
E       assert (True is False)

/home/user/sh-2389/plugins/superheroes/lib/tests/test_vet_slot_md_hidden_2389.py:283: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_vet_slot_md_hidden_2389.py::test_g2_image_heading_is_never_the_owner_heading
FAILED plugins/superheroes/lib/tests/test_vet_slot_md_hidden_2389.py::test_g2_image_heading_through_evaluate_and_run_verb
2 failed, 1 passed, 277 deselected in 0.71s
```

- **Restore:** inverse Edit, the `"![" not in text and ` clause put back.
- **Restore receipt:** the file search returned `263:            if at < limit and "![" not in text and _heading_key(text).startswith("whats changing")]`.
- **Raw green:**

```
...                                                                      [100%]
3 passed, 277 deselected in 0.60s
```

## G3: the unsure detail in `check_not_emptied`

- **Guarded element / axis:** `vet_slot.py:266-271`, the `if unsure:` branch. Axis: when no heading is held and the parse
  holds an unsure point above the marker, the refusal says the render could not be decided and sends the advisor to move
  the text by hand; it does not give the edit-history remedy (wrong detail text, not a missing refusal).
- **Neutralization:** `vet_slot.py:268` `        if unsure:` became `        if False and unsure:` (the branch never fires; the
  generic edit-history refusal on the next lines does).
- **Raw red:**

```
FFF..F                                                                   [100%]
=================================== FAILURES ===================================
_ test_g3_unsure_detail_a_256_character_fence_above_the_owner_heading_says_so[fence_tick_256_cap] _

shape = 'fence_tick_256_cap'

    @pytest.mark.parametrize("shape", ["fence_tick_256_cap", "fence_tilde_256_cap"])
    def test_g3_unsure_detail_a_256_character_fence_above_the_owner_heading_says_so(shape):
        body = _row(shape)["stored"]
        unsure = md_hidden.scan(body).unsure
        assert unsure and unsure[0][0] < body.index(MARKER)
        refusal = _emptied(body)
        assert refusal is not None
>       assert "edit history" not in refusal.detail
E       AssertionError: assert 'edit history' not in 'PR body has...ing the slot'
E         
E         'edit history' is contained here:
E            the PR's edit history before writing the slot
E         ?           ++++++++++++

/home/user/sh-2389/plugins/superheroes/lib/tests/test_vet_slot_md_hidden_2389.py:307: AssertionError
_ test_g3_unsure_detail_a_256_character_fence_above_the_owner_heading_says_so[fence_tilde_256_cap] _

shape = 'fence_tilde_256_cap'

    @pytest.mark.parametrize("shape", ["fence_tick_256_cap", "fence_tilde_256_cap"])
    def test_g3_unsure_detail_a_256_character_fence_above_the_owner_heading_says_so(shape):
        body = _row(shape)["stored"]
        unsure = md_hidden.scan(body).unsure
        assert unsure and unsure[0][0] < body.index(MARKER)
        refusal = _emptied(body)
        assert refusal is not None
>       assert "edit history" not in refusal.detail
E       AssertionError: assert 'edit history' not in 'PR body has...ing the slot'
E         
E         'edit history' is contained here:
E            the PR's edit history before writing the slot
E         ?           ++++++++++++

/home/user/sh-2389/plugins/superheroes/lib/tests/test_vet_slot_md_hidden_2389.py:307: AssertionError
_________ test_g3_unsure_detail_through_evaluate_names_no_edit_history _________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-33/test_g3_unsure_detail_through_0')

    def test_g3_unsure_detail_through_evaluate_names_no_edit_history(tmp_path):
        body = _row("fence_tick_256_cap")["stored"]
        result = _evaluate(body, receipt=RECEIPT)
        assert result["ok"] is False and result["reason"] == "body-emptied", result
>       assert "edit history" not in result["detail"]
E       AssertionError: assert 'edit history' not in 'PR body has...ing the slot'
E         
E         'edit history' is contained here:
E            the PR's edit history before writing the slot
E         ?           ++++++++++++

/home/user/sh-2389/plugins/superheroes/lib/tests/test_vet_slot_md_hidden_2389.py:316: AssertionError
____ test_g3_unsure_detail_an_internal_md_hidden_error_refuses_never_passes ____

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7feee0bfbd10>

    def test_g3_unsure_detail_an_internal_md_hidden_error_refuses_never_passes(monkeypatch):
        def boom(_body):
            raise RuntimeError("boom")
    
        monkeypatch.setattr(md_hidden, "_scan", boom)
        refusal = _emptied(BODY)
>       assert refusal is not None and "could not be decided" in refusal.detail and "internal error" in refusal.detail
E       assert (_Refusal('body-emptied') is not None and 'could not be decided' in 'PR body has no "What\'s changing, and why" heading above the advisor-vet marker; restore the builder\'s body from the PR\'s edit history before writing the slot')
E        +  where 'PR body has no "What\'s changing, and why" heading above the advisor-vet marker; restore the builder\'s body from the PR\'s edit history before writing the slot' = _Refusal('body-emptied').detail

/home/user/sh-2389/plugins/superheroes/lib/tests/test_vet_slot_md_hidden_2389.py:341: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_vet_slot_md_hidden_2389.py::test_g3_unsure_detail_a_256_character_fence_above_the_owner_heading_says_so[fence_tick_256_cap]
FAILED plugins/superheroes/lib/tests/test_vet_slot_md_hidden_2389.py::test_g3_unsure_detail_a_256_character_fence_above_the_owner_heading_says_so[fence_tilde_256_cap]
FAILED plugins/superheroes/lib/tests/test_vet_slot_md_hidden_2389.py::test_g3_unsure_detail_through_evaluate_names_no_edit_history
FAILED plugins/superheroes/lib/tests/test_vet_slot_md_hidden_2389.py::test_g3_unsure_detail_an_internal_md_hidden_error_refuses_never_passes
4 failed, 2 passed, 274 deselected in 0.70s
```

  The refusal token stays `body-emptied` throughout; the red is on the detail text (the axis), not on a missing refusal.
- **Restore:** inverse Edit, `if False and unsure:` back to `if unsure:`.
- **Restore receipt:** the file search returned `268:        if unsure:`.
- **Raw green:**

```
......                                                                   [100%]
6 passed, 274 deselected in 0.62s
```

## G4: `_visibility_problem` on the bot path (`_unrendered_slot`): marker line, slot line, appended heading

- **Guarded element / axis:** `vet_slot.py:499-502`, `_unrendered_slot`, which calls `_visibility_problem` for the bot
  path (`:464-467`). Axis: a composed body whose marker line, verdict line or appended `## Advisor vet` heading GitHub hides
  (or `md_hidden` is unsure of) refuses `write-failed`.
- **Neutralization:** `vet_slot.py:502` `    return _visibility_problem(md_hidden.scan(new_body), marker_at, slot_at, heading_at)`
  became `    return None` (the bot path sees no problem). `_visibility_problem` itself was left alone so the builder-path (G5)
  and `_line_state` (G6) were not touched.
- **Raw red (INCOMPLETE: the tool cut 19988 characters from the middle and the end; the summary lines were lost and there
  was no run left to recover them; nothing here is reconstructed).** What was shown:

```
..............................................................FFFFF..FFF [ 50%]
...F.FF..........FFFF.....FFF.FFF.FFFFFFF.F.FFFFFFFFFF.FFFF..........F   [100%]
=================================== FAILURES ===================================
___ test_g4_bot_path_visibility_fixture_oracle[control_unclosed_comment-bot] ___
...
>           assert problem is not None, "GitHub hides the Advisor vet heading but the check passes: %r" % row["id"]
E           AssertionError: GitHub hides the Advisor vet heading but the check passes: 'control_unclosed_comment'
E           assert None is not None

/home/user/sh-2389/plugins/superheroes/lib/tests/test_vet_slot_md_hidden_2389.py:177: AssertionError
```

  (other `test_g4_bot_path_visibility_fixture_oracle[...]` failures of the same assertion were visible for
  `pre_quoted_opener`, `pre_raw_opener`, `div_plain_closer`, `quote_opener_ends`, `source_tag`, `search_tag`, `noscript_tag`.)
  The detector went red on the right axis: `_unrendered_slot` returns no problem where GitHub hides the Advisor vet heading.
  The count of failed and passed tests is **not** in the shown output.
- **Restore:** inverse Edit, `return None` back to `return _visibility_problem(md_hidden.scan(new_body), marker_at, slot_at, heading_at)`.
- **Restore receipt:** the file search returned `502:    return _visibility_problem(md_hidden.scan(new_body), marker_at, slot_at, heading_at)`.
- **Raw green:**

```
........................................................................ [ 50%]
......................................................................   [100%]
142 passed, 138 deselected in 1.07s
```

## G5: the builder-path call of `_visibility_problem` in `evaluate`

- **Guarded element / axis:** `vet_slot.py:911`, `problem = _visibility_problem(md_hidden.scan(new_body), new_advisor_at, a + 1)`.
  Axis: the builder path refuses `write-failed` unless the marker line and the slot's first line both read `VISIBLE`.
- **Neutralization:** `vet_slot.py:911` became `    problem = None` (the builder path sees no problem).
- **Raw red** (`--tb=no` added, see Disclosures):

```
F.F..                                                                    [100%]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_vet_slot_md_hidden_2389.py::test_g5_builder_path_visibility_an_unclosed_div_title_before_the_slot_refuses_write_failed
FAILED plugins/superheroes/lib/tests/test_vet_slot_md_hidden_2389.py::test_g5_builder_path_visibility_a_hidden_marker_line_refuses_write_failed
2 failed, 3 passed, 275 deselected in 0.68s
```

  Two of five tests go red: the marker-line and the verdict-line tests. The other three pass with the call neutralized; this
  record does not say which of them are meant to discriminate the call (not read or run beyond this).
- **Restore:** inverse Edit, `problem = None` back to the `_visibility_problem(...)` call.
- **Restore receipt:** the file search returned `911:    problem = _visibility_problem(md_hidden.scan(new_body), new_advisor_at, a + 1)`.
- **Raw green:**

```
.....                                                                    [100%]
5 passed, 275 deselected in 0.68s
```

## G6: `_line_state` (the line-holding lookup; PRE2389-1)

- **Guarded element / axis:** `vet_slot.py:147-159`, `_line_state`, the lookup at `:156`. Axis: a visibility read at an
  offset inside a Markdown line (a marker offset that sits after leading U+2028, NBSP or U+3000) reads the state of the
  line holding it and never raises on a non-line-start.
- **Neutralization:** `vet_slot.py:156` `    index = bisect.bisect_right(starts, offset) - 1` became `    index = starts.index(offset)`
  (an exact line-start lookup, which raises `ValueError` for an offset inside a line, as `state_at` did).
- **Raw red** (`--tb=no` added, see Disclosures):

```
F.F.F.F.F.F.F.F.F.F.F.F.FFFFF                                            [100%]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_vet_slot_md_hidden_2389.py::test_g6_line_holding_a_marker_line_with_unicode_whitespace_through_evaluate[u2028-bot-leading]
FAILED plugins/superheroes/lib/tests/test_vet_slot_md_hidden_2389.py::test_g6_line_holding_a_marker_line_with_unicode_whitespace_through_evaluate[u2028-builder-leading]
FAILED plugins/superheroes/lib/tests/test_vet_slot_md_hidden_2389.py::test_g6_line_holding_a_marker_line_with_unicode_whitespace_through_evaluate[nbsp-bot-leading]
FAILED plugins/superheroes/lib/tests/test_vet_slot_md_hidden_2389.py::test_g6_line_holding_a_marker_line_with_unicode_whitespace_through_evaluate[nbsp-builder-leading]
FAILED plugins/superheroes/lib/tests/test_vet_slot_md_hidden_2389.py::test_g6_line_holding_a_marker_line_with_unicode_whitespace_through_evaluate[u3000-bot-leading]
FAILED plugins/superheroes/lib/tests/test_vet_slot_md_hidden_2389.py::test_g6_line_holding_a_marker_line_with_unicode_whitespace_through_evaluate[u3000-builder-leading]
FAILED plugins/superheroes/lib/tests/test_vet_slot_md_hidden_2389.py::test_g6_line_holding_a_marker_line_with_unicode_whitespace_through_run_verb[u2028-bot-leading]
FAILED plugins/superheroes/lib/tests/test_vet_slot_md_hidden_2389.py::test_g6_line_holding_a_marker_line_with_unicode_whitespace_through_run_verb[u2028-builder-leading]
FAILED plugins/superheroes/lib/tests/test_vet_slot_md_hidden_2389.py::test_g6_line_holding_a_marker_line_with_unicode_whitespace_through_run_verb[nbsp-bot-leading]
FAILED plugins/superheroes/lib/tests/test_vet_slot_md_hidden_2389.py::test_g6_line_holding_a_marker_line_with_unicode_whitespace_through_run_verb[nbsp-builder-leading]
FAILED plugins/superheroes/lib/tests/test_vet_slot_md_hidden_2389.py::test_g6_line_holding_a_marker_line_with_unicode_whitespace_through_run_verb[u3000-bot-leading]
FAILED plugins/superheroes/lib/tests/test_vet_slot_md_hidden_2389.py::test_g6_line_holding_a_marker_line_with_unicode_whitespace_through_run_verb[u3000-builder-leading]
FAILED plugins/superheroes/lib/tests/test_vet_slot_md_hidden_2389.py::test_g6_line_holding_a_leading_whitespace_marker_offset_sits_inside_its_line[u2028]
FAILED plugins/superheroes/lib/tests/test_vet_slot_md_hidden_2389.py::test_g6_line_holding_a_leading_whitespace_marker_offset_sits_inside_its_line[nbsp]
FAILED plugins/superheroes/lib/tests/test_vet_slot_md_hidden_2389.py::test_g6_line_holding_a_leading_whitespace_marker_offset_sits_inside_its_line[u3000]
FAILED plugins/superheroes/lib/tests/test_vet_slot_md_hidden_2389.py::test_g6_line_holding_returns_the_state_of_the_last_line_at_or_before_the_offset
FAILED plugins/superheroes/lib/tests/test_vet_slot_md_hidden_2389.py::test_g6_line_holding_no_line_at_or_before_the_offset_reads_unsure
17 failed, 12 passed, 251 deselected in 0.73s
```

- **Restore:** inverse Edit, `index = starts.index(offset)` back to `index = bisect.bisect_right(starts, offset) - 1`.
- **Restore receipt:** the file search returned `156:    index = bisect.bisect_right(starts, offset) - 1`.
- **Raw green:**

```
.............................                                            [100%]
29 passed, 251 deselected in 0.78s
```

## After the last restore

`git diff --stat plugins/superheroes/lib/vet_slot.py` printed nothing: `vet_slot.py` is byte-identical to `3b78f809`.

## Elements in no class

None: G1 to G6 each have their own neutralization and a red. Partially proven: G4 (red summary lines lost; the red is shown
by the progress lines and the failures that were visible, and the three bot-path checks are not shown biting one at a time).
