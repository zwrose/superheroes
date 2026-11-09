# Bite-proof record: i2398_leftover_title_word_end (#2398 V856-3; vet 856 on PR #2391) a title word glued to inline markup does not count as that word

Detector under proof: `plugins/superheroes/lib/tests/test_leftover_title_word_end_2398.py` (unedited between the red and the green).
Guarded code: `plugins/superheroes/lib/leftover_accepting.py` (`_mark_glued_ends`, called by `_names` on the title and on the item). Base head `c72c4282`.
The neutralization was one targeted Edit with the Edit tool, undone by the inverse Edit. No `git checkout`, `restore`, `reset`, `stash` or `sed`.
Command for both halves (worktree root):
`timeout 300 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_leftover_title_word_end_2398.py -q -p no:cacheprovider`

Guarded-element set (declared by the order): G1, the glued-end mark (the helper's return). No others.

Disclosures:
- Captures are the runner's output with uv's one `UV_NATIVE_TLS` deprecation warning line dropped. Nothing was redacted; both are under the 32 KiB ceiling.
- The red capture is incomplete: the tool output elided 8681 characters from the middle of the failure listing (the failure bodies of the chokepoint tag row and the first
  `test_more_glued_forms_are_refused` rows). The head, the tail and the `FAILED` summary lines are quoted whole; the elided part repeated the same assertion
  (`assert [] == ['F-1']` or `assert True is False`).
- Unreachable through this entry point (the tag row, end to end): the row `test_a_title_word_glued_to_markup_is_not_that_word_end_to_end[tag_shows_offf_model_only]`
  stays green with G1 neutralized. The public path that strips the input is `_scan_line` in `leftover_accepting.py` (`_item_cut` calls it per text line; it cuts the item
  at an entry `<`, so the item counts as nothing before `_names` sees the tag). It bites at the seam below: the chokepoint test
  `test_a_title_word_glued_to_markup_is_not_that_word_at_the_chokepoint[tag_shows_offf_model_only]` in the same test file, which calls `la._names` directly and failed in the red.
- The healthy controls, the literal-text edge rows, the monotonicity row and the marker row are guards against over-refusal and pass under the neutralization by design.

## G1: the glued-end mark

- **Guarded element / axis:** `_mark_glued_ends`, the helper's return (`leftover_accepting.py:358`, `return "".join(out)`), read by `_names` on both the title and the item.
  Axis: a title word that GitHub runs into the next word through inline markup (emphasis, strikethrough, a code span, an inline link, a tag) carries a marker, so it is not that word.
- **Neutralization:** `return "".join(out)` became `return text` (the helper marks nothing).
- **Raw red** (head, tail and summary; the middle of the failure listing was elided by the tool, 8681 characters, see Disclosures):

```
FFF.FFFFFFFFFFF...................F.                                     [100%]
=================================== FAILURES ===================================
_ test_a_title_word_glued_to_markup_is_not_that_word_end_to_end[emphasis_shows_offf_github] _
E       AssertionError: assert [] == ['F-1']
_ test_a_title_word_glued_to_markup_is_not_that_word_end_to_end[code_span_shows_offf_github] _
E       AssertionError: assert [] == ['F-1']
_ test_a_title_word_glued_to_markup_is_not_that_word_end_to_end[link_shows_offf_github] _
E       AssertionError: assert [] == ['F-1']
_ test_a_title_word_glued_to_markup_is_not_that_word_at_the_chokepoint[emphasis_shows_offf_github] _
E       AssertionError: assert True is False
_ test_a_title_word_glued_to_markup_is_not_that_word_at_the_chokepoint[code_span_shows_offf_github] _
E       AssertionError: assert True is False
_ test_a_title_word_glued_to_markup_is_not_that_word_at_the_chokepoint[link_shows_offf_github] _
E       AssertionError: assert True is False
_ test_a_title_word_glued_to_markup_is_not_that_word_at_the_chokepoint[tag_shows_offf_model_only] _
... [8681 characters truncated by the tool] ...
_ test_more_glued_forms_are_refused[interior_emphasis_shows_neverbacks_model_only] _
E       AssertionError: assert [] == ['F-1']
_ test_a_title_written_with_glued_markup_matches_its_verbatim_copy_and_not_the_rendered_words _
>       assert gaps(record, "- F-1 The retry loop never backs off f: accepted.\n") == ["F-1"]
E       AssertionError: assert [] == ['F-1']
=========================== short test summary info ============================
FAILED ...::test_a_title_word_glued_to_markup_is_not_that_word_end_to_end[emphasis_shows_offf_github]
FAILED ...::test_a_title_word_glued_to_markup_is_not_that_word_end_to_end[code_span_shows_offf_github]
FAILED ...::test_a_title_word_glued_to_markup_is_not_that_word_end_to_end[link_shows_offf_github]
FAILED ...::test_a_title_word_glued_to_markup_is_not_that_word_at_the_chokepoint[emphasis_shows_offf_github]
FAILED ...::test_a_title_word_glued_to_markup_is_not_that_word_at_the_chokepoint[code_span_shows_offf_github]
FAILED ...::test_a_title_word_glued_to_markup_is_not_that_word_at_the_chokepoint[link_shows_offf_github]
FAILED ...::test_a_title_word_glued_to_markup_is_not_that_word_at_the_chokepoint[tag_shows_offf_model_only]
FAILED ...::test_more_glued_forms_are_refused[padded_code_span_shows_offf_model_only]
FAILED ...::test_more_glued_forms_are_refused[strikethrough_shows_offf_model_only]
FAILED ...::test_more_glued_forms_are_refused[strong_shows_offf_model_only]
FAILED ...::test_more_glued_forms_are_refused[closing_emphasis_shows_offf_model_only]
FAILED ...::test_more_glued_forms_are_refused[closing_code_span_shows_offf_model_only]
FAILED ...::test_more_glued_forms_are_refused[closing_link_shows_offf_model_only]
FAILED ...::test_more_glued_forms_are_refused[interior_emphasis_shows_neverbacks_model_only]
FAILED ...::test_a_title_written_with_glued_markup_matches_its_verbatim_copy_and_not_the_rendered_words
15 failed, 21 passed in 0.33s
```

  The dot pattern shows the one refusal row that stays green: the fourth test of the first group, the tag row end to end (`_scan_line` cuts it first; see Disclosures).
  The `FAILED ...::` prefix stands for `plugins/superheroes/lib/tests/test_leftover_title_word_end_2398.py::` (shortened in this record only).
- **Restore:** the inverse Edit, `return text` back to `return "".join(out)`.
- **Restore receipt:** a Grep-tool read of `^    return (text|"".join\(out\))$` in `leftover_accepting.py` printed `358:    return "".join(out)`.
- **Raw green** (same command, after the restore):

```
....................................                                     [100%]
36 passed in 0.30s
```

## Elements in no class

None. Unproven elements: none. (The tag row end to end is the disclosed unreachable-through-this-entry-point case; its bite is the chokepoint tag row.)
