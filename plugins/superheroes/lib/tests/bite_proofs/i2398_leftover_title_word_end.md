# Bite-proof record: i2398_leftover_title_word_end (#2398 V856-3; vet 856 on PR #2391) a title word glued to inline markup does not count as that word

Detector under proof: `plugins/superheroes/lib/tests/test_leftover_title_word_end_2398.py` (unedited between the red and the green).
Guarded code: `plugins/superheroes/lib/leftover_accepting.py` (`_mark_glued_ends`, called by `_names` on the title and on the item). Base head `bc3dacdd`.
The helper reads raw HTML and link tails through `md_hidden._inline_constructs` and `md_hidden._destination_end`; the emphasis, strikethrough and code-span scans are this module's own.
The neutralization was one targeted Edit with the Edit tool, undone by the inverse Edit. No `git checkout`, `restore`, `reset`, `stash` or `sed`.
Command for the green halves (worktree root):
`timeout 300 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_leftover_title_word_end_2398.py -q -p no:cacheprovider`
The red half ran the same command plus `--tb=line`, so the listing stays whole (no truncation by the tool).

Guarded-element set (declared by the order): G1, the glued-end mark (the helper's return). No others.

Disclosures:
- Captures are the runner's output with uv's one `UV_NATIVE_TLS` deprecation warning line dropped. Nothing was redacted; both are under the 32 KiB ceiling. The red capture is complete.
- Unreachable through this entry point (the tag row, end to end): the row `test_a_title_word_glued_to_markup_is_not_that_word_end_to_end[tag_shows_offf_model_only]`
  stays green with G1 neutralized (the dot in the fourth position of the red's progress line). The public path that strips the input is `_scan_line` in `leftover_accepting.py` (`_item_cut` calls it per text line; it cuts the item
  at an entry `<`, so the item counts as nothing before `_names` sees the tag). It bites at the seam below: the chokepoint test
  `test_a_title_word_glued_to_markup_is_not_that_word_at_the_chokepoint[tag_shows_offf_model_only]` in the same test file, which calls `la._names` directly and failed in the red.
- Unreachable through this entry point (the angle-destination link row, end to end): `test_more_glued_forms_are_refused[angle_destination_link_shows_offf_model_only]`
  also stays green with G1 neutralized (the red lists 16 failures, and this row is not among them). The line holds `<https://x.example>`, an entry `<`, and `_scan_line` cuts the item there, the same way as for the tag row.
  No test in the file reaches the angle destination at the chokepoint (the order allows no further row); the mark on it was read off a one-line `_mark_glued_ends` call, which is not a test:
  `off[f](<https://x.example>)` marks as `offꙮ[f](<https://x.example>)`. The wider link tail is covered by the test seam only through `parenthesised_destination_link_shows_offf_model_only`, which failed in the red.
- The healthy controls, the literal-text edge rows, the monotonicity row, the marker row and `test_a_link_with_a_title_is_not_glued_at_the_chokepoint` are guards against over-refusal and pass under the neutralization by design.

## G1: the glued-end mark

- **Guarded element / axis:** `_mark_glued_ends`, the helper's return (`leftover_accepting.py:365`, `return "".join(out)`), read by `_names` on both the title and the item.
  Axis: a title word that GitHub runs into the next word through inline markup (emphasis, strikethrough, a code span, an inline link, a tag) carries a marker, so it is not that word.
- **Neutralization:** `return "".join(out)` became `return text` (the helper marks nothing).
- **Raw red** (complete; `--tb=line`):

```
FFF.FFFF.FFFFFFF.F...................F.                                  [100%]
=================================== FAILURES ===================================
E   AssertionError: assert [] == ['F-1']
      
      Right contains one more item: 'F-1'
      Use -v to get more diff
/home/user/wt-2398/plugins/superheroes/lib/tests/test_leftover_title_word_end_2398.py:35: AssertionError: assert [] == ['F-1']
E   AssertionError: assert [] == ['F-1']
      
      Right contains one more item: 'F-1'
      Use -v to get more diff
/home/user/wt-2398/plugins/superheroes/lib/tests/test_leftover_title_word_end_2398.py:35: AssertionError: assert [] == ['F-1']
E   AssertionError: assert [] == ['F-1']
      
      Right contains one more item: 'F-1'
      Use -v to get more diff
/home/user/wt-2398/plugins/superheroes/lib/tests/test_leftover_title_word_end_2398.py:35: AssertionError: assert [] == ['F-1']
E   AssertionError: assert True is False
     +  where True = <function _names at 0x7f6312251f80>(('F-1 The retry loop never backs off%s: accepted.' % '*f*'), 'F-1', 'The retry loop never backs off')
     +    where <function _names at 0x7f6312251f80> = la._names
/home/user/wt-2398/plugins/superheroes/lib/tests/test_leftover_title_word_end_2398.py:41: AssertionError: assert True is False
E   AssertionError: assert True is False
     +  where True = <function _names at 0x7f6312251f80>(('F-1 The retry loop never backs off%s: accepted.' % '`f`'), 'F-1', 'The retry loop never backs off')
     +    where <function _names at 0x7f6312251f80> = la._names
/home/user/wt-2398/plugins/superheroes/lib/tests/test_leftover_title_word_end_2398.py:41: AssertionError: assert True is False
E   AssertionError: assert True is False
     +  where True = <function _names at 0x7f6312251f80>(('F-1 The retry loop never backs off%s: accepted.' % '[f](https://x.example)'), 'F-1', 'The retry loop never backs off')
     +    where <function _names at 0x7f6312251f80> = la._names
/home/user/wt-2398/plugins/superheroes/lib/tests/test_leftover_title_word_end_2398.py:41: AssertionError: assert True is False
E   AssertionError: assert True is False
     +  where True = <function _names at 0x7f6312251f80>(('F-1 The retry loop never backs off%s: accepted.' % '<b>f</b>'), 'F-1', 'The retry loop never backs off')
     +    where <function _names at 0x7f6312251f80> = la._names
/home/user/wt-2398/plugins/superheroes/lib/tests/test_leftover_title_word_end_2398.py:41: AssertionError: assert True is False
E   AssertionError: assert [] == ['F-1']
      
      Right contains one more item: 'F-1'
      Use -v to get more diff
/home/user/wt-2398/plugins/superheroes/lib/tests/test_leftover_title_word_end_2398.py:66: AssertionError: assert [] == ['F-1']
E   AssertionError: assert [] == ['F-1']
      
      Right contains one more item: 'F-1'
      Use -v to get more diff
/home/user/wt-2398/plugins/superheroes/lib/tests/test_leftover_title_word_end_2398.py:66: AssertionError: assert [] == ['F-1']
E   AssertionError: assert [] == ['F-1']
      
      Right contains one more item: 'F-1'
      Use -v to get more diff
/home/user/wt-2398/plugins/superheroes/lib/tests/test_leftover_title_word_end_2398.py:66: AssertionError: assert [] == ['F-1']
E   AssertionError: assert [] == ['F-1']
      
      Right contains one more item: 'F-1'
      Use -v to get more diff
/home/user/wt-2398/plugins/superheroes/lib/tests/test_leftover_title_word_end_2398.py:66: AssertionError: assert [] == ['F-1']
E   AssertionError: assert [] == ['F-1']
      
      Right contains one more item: 'F-1'
      Use -v to get more diff
/home/user/wt-2398/plugins/superheroes/lib/tests/test_leftover_title_word_end_2398.py:66: AssertionError: assert [] == ['F-1']
E   AssertionError: assert [] == ['F-1']
      
      Right contains one more item: 'F-1'
      Use -v to get more diff
/home/user/wt-2398/plugins/superheroes/lib/tests/test_leftover_title_word_end_2398.py:66: AssertionError: assert [] == ['F-1']
E   AssertionError: assert [] == ['F-1']
      
      Right contains one more item: 'F-1'
      Use -v to get more diff
/home/user/wt-2398/plugins/superheroes/lib/tests/test_leftover_title_word_end_2398.py:66: AssertionError: assert [] == ['F-1']
E   AssertionError: assert [] == ['F-1']
      
      Right contains one more item: 'F-1'
      Use -v to get more diff
/home/user/wt-2398/plugins/superheroes/lib/tests/test_leftover_title_word_end_2398.py:66: AssertionError: assert [] == ['F-1']
E   AssertionError: assert [] == ['F-1']
      
      Right contains one more item: 'F-1'
      Use -v to get more diff
/home/user/wt-2398/plugins/superheroes/lib/tests/test_leftover_title_word_end_2398.py:118: AssertionError: assert [] == ['F-1']
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_leftover_title_word_end_2398.py::test_a_title_word_glued_to_markup_is_not_that_word_end_to_end[emphasis_shows_offf_github]
FAILED plugins/superheroes/lib/tests/test_leftover_title_word_end_2398.py::test_a_title_word_glued_to_markup_is_not_that_word_end_to_end[code_span_shows_offf_github]
FAILED plugins/superheroes/lib/tests/test_leftover_title_word_end_2398.py::test_a_title_word_glued_to_markup_is_not_that_word_end_to_end[link_shows_offf_github]
FAILED plugins/superheroes/lib/tests/test_leftover_title_word_end_2398.py::test_a_title_word_glued_to_markup_is_not_that_word_at_the_chokepoint[emphasis_shows_offf_github]
FAILED plugins/superheroes/lib/tests/test_leftover_title_word_end_2398.py::test_a_title_word_glued_to_markup_is_not_that_word_at_the_chokepoint[code_span_shows_offf_github]
FAILED plugins/superheroes/lib/tests/test_leftover_title_word_end_2398.py::test_a_title_word_glued_to_markup_is_not_that_word_at_the_chokepoint[link_shows_offf_github]
FAILED plugins/superheroes/lib/tests/test_leftover_title_word_end_2398.py::test_a_title_word_glued_to_markup_is_not_that_word_at_the_chokepoint[tag_shows_offf_model_only]
FAILED plugins/superheroes/lib/tests/test_leftover_title_word_end_2398.py::test_more_glued_forms_are_refused[padded_code_span_shows_offf_model_only]
FAILED plugins/superheroes/lib/tests/test_leftover_title_word_end_2398.py::test_more_glued_forms_are_refused[strikethrough_shows_offf_model_only]
FAILED plugins/superheroes/lib/tests/test_leftover_title_word_end_2398.py::test_more_glued_forms_are_refused[strong_shows_offf_model_only]
FAILED plugins/superheroes/lib/tests/test_leftover_title_word_end_2398.py::test_more_glued_forms_are_refused[closing_emphasis_shows_offf_model_only]
FAILED plugins/superheroes/lib/tests/test_leftover_title_word_end_2398.py::test_more_glued_forms_are_refused[closing_code_span_shows_offf_model_only]
FAILED plugins/superheroes/lib/tests/test_leftover_title_word_end_2398.py::test_more_glued_forms_are_refused[closing_link_shows_offf_model_only]
FAILED plugins/superheroes/lib/tests/test_leftover_title_word_end_2398.py::test_more_glued_forms_are_refused[interior_emphasis_shows_neverbacks_model_only]
FAILED plugins/superheroes/lib/tests/test_leftover_title_word_end_2398.py::test_more_glued_forms_are_refused[parenthesised_destination_link_shows_offf_model_only]
FAILED plugins/superheroes/lib/tests/test_leftover_title_word_end_2398.py::test_a_title_written_with_glued_markup_matches_its_verbatim_copy_and_not_the_rendered_words
16 failed, 23 passed in 0.47s
```

- **Restore:** the inverse Edit, `return text` back to `return "".join(out)`.
- **Restore receipt:** a Grep-tool read of `^    return (text|"".join\(out\))$` in `leftover_accepting.py` printed `365:    return "".join(out)`.
- **Raw green** (same command without `--tb=line`, after the restore):

```
.......................................                                  [100%]
39 passed in 0.33s
```

## Elements in no class

None. Unproven elements: none. (The tag row and the angle-destination row end to end are the disclosed unreachable-through-this-entry-point cases; the tag row's bite is the chokepoint tag row, and the angle-destination row has no test-level bite, see Disclosures.)
