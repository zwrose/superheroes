# Bite-proof record: i2342_vet_slot_no_build_record (#2342) `vet_slot.py write` and `check` accept a PR body with no build record

Detector under proof: `plugins/superheroes/lib/tests/test_vet_slot_no_build_record_2342.py`.
Guarded code: `plugins/superheroes/lib/vet_slot.py` (`no_build_record`, `analyze_no_build_record`,
`_compose_no_build_record`, `_unrendered_slot`, and the routing in `evaluate` and `_run_verb`).
Base: `bd8c4ced7fde55592a082375ecc23ed1b19458a1`. Every neutralization was a targeted edit made with the Edit tool,
undone by the inverse Edit before the next element. No `git checkout`, `restore`, `reset` or `stash` was used.
Command prefix for every run below (worktree root), with `-k` as named per entry:
`timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_vet_slot_no_build_record_2342.py -q -p no:cacheprovider --tb=line -k <selector>`
(G1 ran with `--tb=short`). Nothing in the captures was redacted; each is far under 32 KiB. The production sites
cite this record with `# axis:` comments. Restore receipts are the inverse edit's text, quoted.

Disclosures:
- The red captures below are **condensed by hand, not verbatim**: pytest's `where True = <function ...>(<body repr>)`
  introspection lines, repeated failure lines (shown with a count) and the path prefix on `FAILED` lines are dropped,
  and uv's one deprecation warning line is dropped. Every line shown is the runner's text; the pass/fail counts and
  the `FAILED` node ids are exact. The green captures are verbatim minus uv's warning line.
- Guarded-element set: the nine the order declared (G1 to G9). Elements outside it carry no neutralization run and
  are **unproven by a red run**: the `analyze_no_build_record` two-marker arm (E6 exercises it, nothing neutralized it);
  the `no_build_record(new_body)` post-compose check in `_compose_no_build_record` (E17 exercises it); the
  marker-found-once-at-the-expected-offset post-compose check (it is the backstop that still refuses the fenced E7 case
  when G7 is neutralized, see 7); the span-invariant check (`new_body.startswith(prefix)`, unreachable by
  construction); and the `_run_verb` and `evaluate` write-routing (G9 neutralizes the `check` half of both sites).
- Under G3 the E8 `markers-only` case stays green, because the `Build record` wrapper it keeps is caught by G5's
  sign: only `whole-record` bites G3. Under G4 the two cases built from `BUILD_RECORD_NO_MARKERS` (`slot-span`,
  `below-the-build-record`) stay green for the same reason; the four `bare-*` cases bite G4.
- Under G7 the fenced E7 case still refuses `write-failed` (the marker-found backstop), but with the detail
  `composed body moved or shadowed slot markers`, so it fails the test's `would not render` assertion; the two comment
  cases (E7 unclosed comment, E16) turn into a successful write.

## 1. G1: the allowance (`no_build_record`)

- **Axis:** a body with no builder sign takes the no-build-record path, so the bot body's READY write succeeds.
- **Neutralization:** the final `return True` of `no_build_record` became `return False`.
- **Raw red** (`-k test_e2_a_bot_body_takes_a_ready_slot`, `--tb=short`):

```
F                                                                        [100%]
E   assert {'ok': False,...ing the slot'} == {'ok': True, ...ttps://x/c/1'}
E     {'ok': False} != {'ok': True}
E     Left contains 2 more items: {'detail': 'PR body has no "What\'s changing, and why" heading; restore the builder\'s body from the PR\'s edit history before writing the slot', 'reason': 'body-emptied'}
FAILED test_e2_a_bot_body_takes_a_ready_slot_appended_under_a_new_advisor_vet_heading
1 failed, 103 deselected in 0.50s
```

- **Restore:** inverse Edit, `return False` back to `return True` (the line above `def analyze_no_build_record`).
- **Restore receipt:** the restored lines read `        offset += len(whole)` then `    return True`.
- **Raw green:**

```
.                                                                        [100%]
1 passed, 103 deselected in 0.51s
```

## 2. G2: builder sign 1, a superheroes marker other than advisor-vet

- **Axis:** a `<!-- superheroes:` marker that is not the advisor-vet line is a builder sign, fenced or not.
- **Neutralization:** `if _SUPERHEROES_OPEN_RE.search(line) and line.strip() != marker:` became
  `if False and _SUPERHEROES_OPEN_RE.search(line) and line.strip() != marker:`.
- **Raw red** (`-k "e10 and (fenced or dod-table)"`):

```
FFFF                                                                     [100%]
E   AssertionError: assert True is False   (x4, test_vet_slot_no_build_record_2342.py:309, on vs.no_build_record(body))
FAILED test_e10_a_markerless_remnant_alone_is_refused[fenced-followups-marker-no-marker]
FAILED test_e10_a_markerless_remnant_alone_is_refused[fenced-followups-marker-with-marker]
FAILED test_e10_a_markerless_remnant_alone_is_refused[dod-table-marker-no-marker]
FAILED test_e10_a_markerless_remnant_alone_is_refused[dod-table-marker-with-marker]
4 failed, 100 deselected in 0.54s
```

- **Restore:** inverse Edit, `if False and _SUPERHEROES_OPEN_RE...` back to `if _SUPERHEROES_OPEN_RE...`.
- **Restore receipt:** the restored line reads `        if _SUPERHEROES_OPEN_RE.search(line) and line.strip() != marker:`.
- **Raw green** (same `-k`):

```
....                                                                     [100%]
4 passed, 100 deselected in 0.44s
```

## 3. G3: builder sign 3, a builder-section heading

- **Axis:** an ATX heading whose key starts with a builder key is a builder sign, so a builder body with its build
  record stripped is still refused as today (the issue's second Definition-of-Done test).
- **Neutralization:** `if key.startswith(_BUILDER_HEADING_KEYS):` became
  `if False and key.startswith(_BUILDER_HEADING_KEYS):`.
- **Raw red** (`-k test_e8_a_builder_body`):

```
F.                                                                       [100%]
E   assert True is False   (test_vet_slot_no_build_record_2342.py:246, on vs.no_build_record(STRIPPED_WHOLE))
FAILED test_e8_a_builder_body_with_its_build_record_stripped_is_refused_as_today[whole-record]
1 failed, 1 passed, 102 deselected in 0.40s
```

- **Restore:** inverse Edit, `if False and key.startswith(...)` back to `if key.startswith(...)`.
- **Restore receipt:** the restored line reads `            if key.startswith(_BUILDER_HEADING_KEYS):`.
- **Raw green** (same `-k`):

```
..                                                                       [100%]
2 passed, 102 deselected in 0.45s
```

## 4. G4: the whole-body heading scan (headings below the advisor-vet marker count)

- **Axis:** a builder heading below the live advisor-vet marker is still a builder sign; the scan is not cut at the
  marker.
- **Neutralization:** three lines inserted before `heading = _ANY_HEADING_RE.match(line)`:
  `if marker_at is not None and offset > marker_at:` / `offset += len(whole)` / `continue`.
- **Raw red** (`-k e9`):

```
..FFFF..FFFF                                                             [100%]
E   assert True is False   (x4, test_vet_slot_no_build_record_2342.py:276, run_verb cases)
E   assert (True is False) (x4, test_vet_slot_no_build_record_2342.py:284, evaluate cases)
FAILED test_e9_run_verb_refuses_body_emptied_and_makes_no_edit[bare-slot-span]
FAILED test_e9_run_verb_refuses_body_emptied_and_makes_no_edit[bare-below]
FAILED test_e9_run_verb_refuses_body_emptied_and_makes_no_edit[bare-how-to-see-it]
FAILED test_e9_run_verb_refuses_body_emptied_and_makes_no_edit[bare-definition-of-done]
FAILED test_e9_evaluate_agrees[bare-slot-span]
FAILED test_e9_evaluate_agrees[bare-below]
FAILED test_e9_evaluate_agrees[bare-how-to-see-it]
FAILED test_e9_evaluate_agrees[bare-definition-of-done]
8 failed, 4 passed, 92 deselected in 0.46s
```

- **Restore:** inverse Edit, the three inserted lines removed.
- **Restore receipt:** the restored lines read `        heading = _ANY_HEADING_RE.match(line)` directly under the
  `# axis: headings below the advisor-vet marker are scanned too` comment.
- **Raw green** (same `-k`):

```
............                                                             [100%]
12 passed, 92 deselected in 0.47s
```

## 5. G5: builder sign 2, the `<summary>Build record` wrapper

- **Axis:** the `Build record` wrapper is a builder sign, with a line break or attributes between tag and words.
- **Neutralization:** `if _BUILD_RECORD_WRAPPER_RE.search(body):` became `if False and _BUILD_RECORD_WRAPPER_RE.search(body):`.
- **Raw red** (`-k "e10 and wrapper"`):

```
FFFF                                                                     [100%]
E   AssertionError: assert True is False   (x4, test_vet_slot_no_build_record_2342.py:309)
FAILED test_e10_a_markerless_remnant_alone_is_refused[wrapper-no-marker]
FAILED test_e10_a_markerless_remnant_alone_is_refused[wrapper-with-marker]
FAILED test_e10_a_markerless_remnant_alone_is_refused[wrapper-split-across-lines-no-marker]
FAILED test_e10_a_markerless_remnant_alone_is_refused[wrapper-split-across-lines-with-marker]
4 failed, 100 deselected in 0.41s
```

- **Restore:** inverse Edit, `if False and _BUILD_RECORD_WRAPPER_RE...` back to `if _BUILD_RECORD_WRAPPER_RE...`.
- **Restore receipt:** the restored line reads `    if _BUILD_RECORD_WRAPPER_RE.search(body):`.
- **Raw green** (same `-k`):

```
....                                                                     [100%]
4 passed, 100 deselected in 0.44s
```

## 6. G6: the `What we're accepting` exemption

- **Axis:** a `What we're accepting` heading below the live advisor-vet marker is the advisor's slot, not a builder
  sign, so a READY slot naming a leftover writes, and a second write over it replaces the old slot.
- **Neutralization:** `exempt = key.startswith(_ACCEPTING_KEY) and marker_at ...` became
  `exempt = False and key.startswith(_ACCEPTING_KEY) and marker_at ...`.
- **Raw red** (`-k test_e5_a_slot_naming`):

```
FF                                                                       [100%]
E   AssertionError: {'ok': False, 'reason': 'write-failed', 'detail': 'the slot text carries a builder heading or build-record wrapper; the composed body would read as a builder body'}
    assert False is True   (x2, test_vet_slot_no_build_record_2342.py:201)
FAILED test_e5_a_slot_naming_the_leftover_under_what_were_accepting_writes_and_rewrites[']
FAILED test_e5_a_slot_naming_the_leftover_under_what_were_accepting_writes_and_rewrites[’]
2 failed, 102 deselected in 0.42s
```

- **Restore:** inverse Edit, `exempt = False and key...` back to `exempt = key...`.
- **Restore receipt:** the restored line reads `                exempt = key.startswith(_ACCEPTING_KEY) and marker_at is not None and offset > marker_at`.
- **Raw green** (same `-k`):

```
..                                                                       [100%]
2 passed, 102 deselected in 0.45s
```

## 7. G7: the post-compose live check (`_compose_no_build_record`)

- **Axis:** a composed body whose advisor-vet marker sits in an unclosed HTML comment, or whose appended heading sits
  inside an unclosed fence or comment, refuses `write-failed` ("would not render"), nothing pushed.
- **Neutralization:** `if problem:` (after `problem = _unrendered_slot(...)`) became `if False and problem:`.
- **Raw red** (`-k "e7 or e16"`):

```
FFF                                                                      [100%]
E   AssertionError: {'ok': False, 'reason': 'write-failed', 'detail': 'composed body moved or shadowed slot markers'}
    assert 'would not render' in 'composed body moved or shadowed slot markers'   (test_vet_slot_no_build_record_2342.py:61)
E   AssertionError: {'ok': True, 'verb': 'write', 'followups': [], 'receipt': 'https://x/c/1'}
    assert True is False   (x2, test_vet_slot_no_build_record_2342.py:58)
FAILED test_e7_a_body_ending_inside_a_fence_or_comment_refuses_write_failed[unclosed-fence]
FAILED test_e7_a_body_ending_inside_a_fence_or_comment_refuses_write_failed[unclosed-comment]
FAILED test_e16_text_before_a_present_marker_that_leaves_a_comment_open_refuses_write_failed
3 failed, 101 deselected in 0.40s
```

- **Restore:** inverse Edit, `if False and problem:` back to `if problem:`.
- **Restore receipt:** the restored lines read `    if problem:` then `        raise _Refusal("write-failed", problem)`.
- **Raw green** (same `-k`):

```
...                                                                      [100%]
3 passed, 101 deselected in 0.44s
```

## 8. G8: a blank body is never no-build-record

- **Axis:** an empty or whitespace body (and the REST `null` body) is not no-build-record, so `write` refuses it
  `body-emptied` (the builder branch's `check_not_emptied`), never `read-failed`.
- **Neutralization:** `if not isinstance(body, str) or not body.strip():` (the first line of `no_build_record`'s body)
  became `if not isinstance(body, str) or (False and not body.strip()):`.
- **Raw red** (`-k "e1 or blank"`):

```
FFF...FFFFF......................................                        [100%]
E   AssertionError: assert True is False   (x3, :86, on vs.no_build_record('') and two blank strings)
E   AssertionError: {'ok': False, 'reason': 'read-failed', 'detail': 'PR body is empty'} / assert 'read-failed' == 'body-emptied'   (x5, :59 and :136)
FAILED test_a_blank_or_non_string_body_is_never_no_build_record[]
FAILED test_a_blank_or_non_string_body_is_never_no_build_record[  \n\t\n]
FAILED test_a_blank_or_non_string_body_is_never_no_build_record[\n]
FAILED test_e1_blank_body_on_write_refuses_body_emptied[]
FAILED test_e1_blank_body_on_write_refuses_body_emptied[   \n\t\n]
FAILED test_e1_blank_body_on_write_refuses_body_emptied[\n]
FAILED test_e1_null_rest_body_on_write_refuses_body_emptied
FAILED test_e1_evaluate_keeps_the_blank_body_reasons[write]
8 failed, 41 passed, 55 deselected in 0.55s
```

- **Restore:** inverse Edit, `(False and not body.strip())` back to `not body.strip()`.
- **Restore receipt:** the restored line reads `    if not isinstance(body, str) or not body.strip():`.
- **Raw green** (same `-k`):

```
.................................................                        [100%]
49 passed, 55 deselected in 0.62s
```

## 9. G9: `check` accepts the shape (the routing)

- **Axis:** `check` on a bot body routes to the no-build-record path in `_run_verb` and in `evaluate`, so it returns
  `followups: []` and the receipt result instead of `markers-invalid`.
- **Neutralization:** two sites. In `_run_verb`, `if no_build_record(body):` became
  `if verb == "write" and no_build_record(body):`; in `evaluate`, `bare = no_build_record(body)` became
  `bare = verb == "write" and no_build_record(body)`.
- **Raw red** (`-k e12`):

```
FF.                                                                      [100%]
E   AssertionError: assert {'ok': False,...ears 0 times'} == {'ok': True, ...t': None, ...}   (x2, :333)
      {'detail': 'advisor-vet marker appears 0 times', 'reason': 'markers-invalid'}     (no-marker)
      {'detail': 'build-record marker appears 0 times', 'reason': 'markers-invalid'}    (with-marker)
FAILED test_e12_check_on_a_bot_body[no-marker]
FAILED test_e12_check_on_a_bot_body[with-marker]
2 failed, 1 passed, 101 deselected in 0.45s
```

- **Restore:** two inverse Edits, `verb == "write" and ` removed from both sites.
- **Restore receipt:** the restored lines read `    if no_build_record(body):` (in `_run_verb`) and
  `        bare = no_build_record(body)` (in `evaluate`).
- **Raw green** (same `-k`):

```
...                                                                      [100%]
3 passed, 101 deselected in 0.44s
```

## Vet-817: the slot starts after the marker's own line (H1–H2)

Detector under proof: the `F` section of `plugins/superheroes/lib/tests/test_vet_slot_no_build_record_2342.py`
(`test_f1_f2_*`, `test_f1_every_splitlines_separator_*`, `test_f3_*`, `test_f5_*`).
Guarded code: `_compose_no_build_record` in `plugins/superheroes/lib/vet_slot.py`, at base `519e2e7c`. Every
neutralization was a targeted Edit, undone by the inverse Edit. No `git checkout`, `restore`, `reset` or `stash` was used.
Command for every run below (worktree root): `timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_vet_slot_no_build_record_2342.py -q -p no:cacheprovider --tb=short -k "test_f1 or test_f3 or test_f5"`
unless a different `-k` or `--tb` is named. Nothing was redacted; each capture is under 32 KiB. Disclosures:
the red captures are condensed by hand (the `where`/repr lines, the long `FAILED` node ids shortened to the test name
plus its parameter id, and uv's deprecation warning line dropped); every line shown is the runner's text and the counts
are exact. A first H1+H2 run was cut in the middle by the tool display (5179 characters lost), so it is not quoted:
the H1+H2 red below is a second, narrowed run (`-k test_f1_f2`) made after the two verdict assertions were moved ahead
of the exact-body assertions, so the red names the READY read directly.

### Pre-change receipt (before any edit, head `519e2e7c`)

The vet 817 reproduction (`evaluate("write", ...)` of a NOT-READY slot with a `dispositions none` receipt, then
`stack_check.read_vet_verdict(body, HEAD)`), `HEAD = a1b2c3d4e5f60718293a4b5c6d7e8f9012345678`:

```
F1-cr before: READY
F1-cr write ok; after: READY
F2-u2028 before: READY
F2-u2028 write ok; after: READY
```

The write succeeded and the merge train still read READY: the inversion.

### H1. the slot starts after the marker's own `str.splitlines()` line

- **Axis:** the first line of the composed advisor-vet region is the slot's, whatever separator ended the marker line.
- **Neutralization:** one line inserted before the `if line_end is None:` check:
  `line_end = (body.find("\n", advisor_at) + 1) or -1  # H1-NEUTRALIZED` (the pre-change `body.find("\n", advisor_at)`
  rule; `-1` is the no-terminator case). H2 left in place.
- **Raw red** (H1 only, the same command):

```
FFFFFFFFFFFFF..........                                                  [100%]
E   AssertionError: {'ok': False, 'reason': 'write-failed', 'detail': "the advisor-vet region's first line as the merge train reads it is ...3a4b5c6d7e8f9012345678', not the new verdict line '**Verdict: NOT-READY** · a1b2c3d4e5f60718293a4b5c6d7e8f9012345678'"}   (x13, one per failed test below)
FAILED test_f1_f2_..._through_evaluate[f1-cr-only]
FAILED test_f1_f2_..._through_evaluate[f2-u2028]
FAILED test_f1_f2_..._through_run_verb[f1-cr-only]
FAILED test_f1_f2_..._through_run_verb[f2-u2028]
FAILED test_f3_..._through_evaluate_and_run_verb[f1-cr-only]
FAILED test_f3_..._through_evaluate_and_run_verb[f2-u2028]
FAILED test_f1_every_splitlines_separator_after_the_marker_writes_cleanly[\r]
FAILED test_f1_every_splitlines_separator_after_the_marker_writes_cleanly[ ]
FAILED test_f1_every_splitlines_separator_after_the_marker_writes_cleanly[ ]
FAILED test_f1_every_splitlines_separator_after_the_marker_writes_cleanly[\x85]
FAILED test_f1_every_splitlines_separator_after_the_marker_writes_cleanly[\x0b]
FAILED test_f1_every_splitlines_separator_after_the_marker_writes_cleanly[\x0c]
FAILED test_f1_every_splitlines_separator_after_the_marker_writes_cleanly[\x1c]
13 failed, 10 passed, 104 deselected in 0.77s
```

With H2 in place, H1 alone turns the F1/F2 write into a `write-failed` refusal (the old READY line stays first in the
region, H2 sees it), not into a READY read; the tests that expect a clean write go red on `ok is True`. The
`\r\n` and `\n` separator cases stay green (`body.find("\n")` already ends those lines).

### H2. the invariant check

- **Axis:** the first non-empty line of the composed region, read as `read_vet_verdict` reads it, is the slot's, else
  the write refuses `write-failed` and pushes nothing.
- **Neutralization (a), H1 also neutralized:** the guard `if region_refusal is not None or region is None or first_read != first_written:`
  became `if False and (...):  # H2-NEUTRALIZED`, with the H1 line above still in place.
- **Raw red (a)** (`-k test_f1_f2`, the narrowed run):

```
FFFF                                                                     [100%]
E   AssertionError: assert 'READY' == 'NOT-READY'
E     - NOT-READY
E     + READY
FAILED test_f1_f2_..._through_evaluate[f1-cr-only]      (:478  assert _vet(new_body) == VERDICT_NOT_READY)
FAILED test_f1_f2_..._through_evaluate[f2-u2028]        (:478)
FAILED test_f1_f2_..._through_run_verb[f1-cr-only]      (:494  assert _vet(pushed) == VERDICT_NOT_READY)
FAILED test_f1_f2_..._through_run_verb[f2-u2028]        (:494)
4 failed, 123 deselected in 0.43s
```

  This is the vet 817 inversion: both checks off, the NOT-READY write is pushed and the merge train reads READY.
- **Neutralization (b), H2 alone:** H1 restored (the inverse Edit removed the inserted line), H2 still `if False and (...)`.
- **Raw red (b)** (`--tb=line`):

```
...............FFFFFFFF                                                  [100%]
E   AssertionError: {'ok': True, 'verb': 'write', 'followups': [], 'receipt': 'https://x/c/1', ...}
    assert (True is False)   (x8, test_vet_slot_no_build_record_2342.py:532)
FAILED test_f5_..._[marker-present-first-line-is-the-old-verdict]
FAILED test_f5_..._[marker-present-no-region]
FAILED test_f5_..._[marker-present-region-refusal]
FAILED test_f5_..._[marker-present-blank-region]
FAILED test_f5_..._[marker-absent-first-line-is-the-old-verdict]
FAILED test_f5_..._[marker-absent-no-region]
FAILED test_f5_..._[marker-absent-region-refusal]
FAILED test_f5_..._[marker-absent-blank-region]
8 failed, 15 passed, 104 deselected in 0.45s
```

  F1 to F3 stay green under H2 alone (15 passed): with H1 in place the check never fires on those bodies, so only F5 bites H2.
- **Restore:** inverse Edit, `if False and (region_refusal ...):  # H2-NEUTRALIZED` back to the unguarded `if`.
- **Restore receipt:** the restored line reads
  `    if region_refusal is not None or region is None or first_read != first_written:`; `grep -n NEUTRALIZED plugins/superheroes/lib/vet_slot.py` matched nothing after both restores.
- **Raw green** (same command as the top, after both restores):

```
.......................                                                  [100%]
23 passed, 104 deselected in 0.49s
```

## Builder path: the slot starts after the marker's own line (H3–H4)

Detector under proof: `plugins/superheroes/lib/tests/test_vet_slot_builder_path_verdict_read_2342.py` (33 tests: B1 and B2,
each over seven separators through `evaluate` and through `run_verb`; B3; B4 over four region shapes).
Guarded code: `evaluate`'s builder-path composition in `plugins/superheroes/lib/vet_slot.py`, at base `c23216f9`, which now
calls the two shared helpers `_after_marker_line` (H3) and `_check_verdict_reads_first` (H4) that `_compose_no_build_record`
also calls. Every neutralization was a targeted Edit, undone by the inverse Edit. No `git checkout`, `restore`, `reset` or
`stash` was used. Command for every run below (worktree root):
`timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_vet_slot_builder_path_verdict_read_2342.py -q -p no:cacheprovider --tb=line`
with the `-k` named per run. Nothing was redacted; each capture is under 32 KiB. Disclosures: the red captures are
condensed by hand (the long `FAILED` node ids dropped, the `detail` text of the refusal dicts cut at the width shown,
uv's deprecation warning line dropped); the counts and the assertion lines are the runner's text.

### Pre-change receipt (new test file against the unedited `vet_slot.py`, head `c23216f9`)

The tests carry the orchestrator's measured vet 817 reproduction: the builder `BODY` with its
`<!-- superheroes:advisor-vet -->\nold slot text\n` replaced by the marker, one of the seven separators and
`**Verdict: READY** · <40-hex HEAD>\n`, then a NOT-READY write at HEAD through `evaluate`, then
`stack_check.read_vet_verdict(newBody, HEAD)`. Every one of the seven separators (`\r`, U+2028, U+2029, U+0085, `\x0b`,
`\x0c`, `\x1c`) reads READY after the write, through `evaluate` and through `run_verb`:

```
FFFFFFFFFFFFFFFFFFFFFFFFFFFF.FFFF                                        [100%]
E   AssertionError: assert 'READY' == 'NOT-READY'     (x14: test file lines 67 evaluate x7, 84 run_verb x7)
E   AssertionError: assert 'NOT-READY' == 'READY'     (x14: B2, lines 95 evaluate x7 and 105 run_verb x7; the old NOT-READY line stays first)
E   AssertionError: {'ok': True, 'verb': 'write', ...} assert (True is False)   (x4: B4, line 130)
32 failed, 1 passed in 0.67s
```

The one pass is B3 (the LF body). Disclosure: the tool display cut the middle of this `--tb=line` run (3865 characters
lost), so the block above is condensed from the part that did show (the first eight B1 failures at line 67 and line 84,
the B2 failures at line 95, the closing `32 failed, 1 passed`) and from a first `--tb=short | tail -80` run of the same
file that showed the B2 and B4 failures at their lines and the same `32 failed, 1 passed in 0.76s`. The per-case order of
the progress line (28 `F`, one `.`, 4 `F`) is B1 (14), B2 (14), B3 (1), B4 (4).

### H3: the builder path calls the shared marker-line helper (axis: the slot starts after the marker's own splitlines line)

- **Neutralization:** in `evaluate`'s builder path, `a = _after_marker_line(body, advisor_at)` became
  `a = body.index("\n", advisor_at) + 1  # H3-NEUTRALIZED` (H4 left in place).
- **Raw red** (full file, `--tb=line`):

```
FFFFFFFFFFFFFFFFFFFFFFFFFFFF.....                                        [100%]
E   AssertionError: {'ok': False, 'reason': 'write-failed', 'detail': "the advisor-vet region's first line as the merge train reads it is ...3a4b5c6d7e8f9012345678', not the new verdict line '**Verdict: NOT-READY** · a1b2c3d4e5f6...
    assert False is True        (x14: B1, test file lines 65 and 82)
E   AssertionError: {'ok': False, 'reason': 'write-failed', 'detail': "the advisor-vet region's first line as the merge train reads it is ...4b5c6d7e8f9012345678 (old)', not the new verdict line '**Verdict: READY** · a1b2c3d4e5f6...
    assert False is True        (x14: B2, test file lines 94 and 103)
28 failed, 5 passed in 0.45s
```

  With H4 in place the stale-first-line writes refuse `write-failed`, which B1 counts as a failure (B1 asserts `ok` is
  true). The 5 passes are B3 and the four B4 cases.
- **Restore:** inverse Edit.

### H4: the builder path calls the shared read-back check (axis: the region's first line, as the merge train reads it, is the slot's)

- **Neutralization:** the builder path's `_check_verdict_reads_first(new_body, slot_text)` became
  `pass  # H4-NEUTRALIZED` (H3 restored first).
- **Raw red** (`-k b4`, `--tb=line`):

```
FFFF                                                                     [100%]
E   AssertionError: {'ok': True, 'verb': 'write', 'followups': ['FU1', 'FU2'], 'receipt': 'https://x/c/1', ...}
    assert (True is False)      (x4: first-line-is-the-old-verdict, no-region, region-refusal, blank-region; line 130)
4 failed, 29 deselected in 0.36s
```

- **H3 and H4 both neutralized** (`-k b1`): the inversion, the write succeeds and the merge train reads READY:

```
FFFFFFFFFFFFFF                                                           [100%]
     14 E   AssertionError: assert 'READY' == 'NOT-READY'
14 failed, 19 deselected in 0.41s
```

  (The second line is `grep -E "^E  |passed|failed" | sort | uniq -c` over the run, so the 14 identical assertion lines
  are counted rather than repeated.)
- **Restore:** inverse Edits for both.
- **Restore receipt:** `grep -n NEUTRALIZED plugins/superheroes/lib/vet_slot.py` matched nothing (exit 1) after both
  restores; the builder path's restored calls read `        a = _after_marker_line(body, advisor_at)` (inside the `try`
  that turns a `_Refusal` into the refusal dict) and `        _check_verdict_reads_first(new_body, slot_text)`.
- **Raw green** (same file, after both restores):

```
.................................                                        [100%]
33 passed in 0.50s
```

### The bot path after the extraction

`_compose_no_build_record` now calls the same two helpers; its H1/H2 proofs above are unchanged. Re-run once after the
extraction, `-k "test_f"` over `test_vet_slot_no_build_record_2342.py`: `23 passed, 104 deselected in 0.44s`.

## Vet 823: the slot-span guard and the write share one line rule (H5–H6)

The invariant: every edge of the advisor-vet slot span is computed by the same line rule. Its start, in the write and in
`analyze_body`'s guard, is `_after_marker_line(body, <advisor-vet marker offset>)`; on the builder path its end is
`build_at`, the build-record marker's own line start. Before this change the guard started its span at
`body.index("\n", offsets["advisor-vet"]) + 1` and the write ended it at `body.rfind("\n", 0, build_at) + 1`, so a marker
line (or a line before the build record) ended by a lone CR, U+2028 or a form feed put lines inside what the write
replaced but outside what the guard checked (start), or kept old slot text below the new slot (end).

Tests: `I` section of `test_vet_slot_builder_path_verdict_read_2342.py` (I1/I2 through `evaluate` and `run_verb`, I3
through `analyze_body`, I4 the write's end). Head `13f2a5a4`.

### Pre-change receipt (the new tests against the unedited `vet_slot.py`)

The tests carry the orchestrator's measured reproduction (builder `BODY` with `<!-- superheroes:advisor-vet -->\nold slot text\n`
replaced by the marker, a separator, then `<!-- superheroes:dod-table -->\n| DoD | done |\n`; NOT-READY `SLOT`; `RECEIPT`).
The orchestrator's measurement was `lf refused: slot-span-foreign-content`, and `cr`, `u2028` and `ff` each `WROTE; dod-table
marker kept: False`. I did not re-run that throwaway script; I ran the new tests instead (the order allows "the new tests
run before the fix"), `-k "test_i1 or test_i3 or test_i4"`, `--tb=short`:

```
.FFF.FFF.FFFFFF                                                          [100%]
E   AssertionError: {'ok': True, 'verb': 'write', 'followups': ['FU1', 'FU2'], 'receipt': 'https://x/c/1', ...}
E   assert (True is False)      (x3: I1 evaluate [cr] [u2028] [ff], test file line 159)
E   AssertionError: {'ok': True, 'verb': 'write', 'followups': ['FU1', 'FU2'], 'receipt': 'https://x/c/1'}
E   assert (True is False)      (x3: I1 run_verb [cr] [u2028] [ff], line 167)
E   Failed: DID NOT RAISE _Refusal      (x3: I3 analyze_body [cr] [u2028] [ff], line 173)
E   assert 'old slot text' not in "## What's c...n\ntrailer\n"      (x3: I4 [cr] [u2028] [ff], line 186)
12 failed, 3 passed, 33 deselected in 0.60s
```

The 3 passes are the LF cases (I2: evaluate, run_verb and `analyze_body` on the LF body), the behaviour that was already
correct. The block condenses the per-failure traceback lines (the repeated test names and paths); nothing else was elided.
The write succeeding on `cr`, `u2028` and `ff` reproduces the measured `WROTE` result. The "dod-table marker kept" value
was not printed by these tests; the write succeeded and refused nothing, as the measurement says.

### H5: the guard's span start goes through the shared helper (axis: the guard's span starts where the write's slot does, after the marker's own splitlines line)

- **Guarded element:** `vet_slot.py:453`, `span_start = _after_marker_line(body, offsets["advisor-vet"])` in `analyze_body`.
- **Neutralization:** that line became `span_start = body.index("\n", offsets["advisor-vet"]) + 1  # H5-NEUTRALIZED`
  (the `-1` branch below it left in place, dead under the neutralization).
- **Raw red** (full new file, `--tb=line`; the tool output was cut to 260 columns per line with `cut -c1-260`, which
  shortened nothing that matters here: every `E` line fits and the closing summary is whole; the 9 repeated `FAILED`
  ids are condensed to the groups below):

```
..................................FFF.FFF.FFF...                         [100%]
E   AssertionError: {'ok': True, 'verb': 'write', 'followups': ['FU1', 'FU2'], 'receipt': 'https://x/c/1', ...}
    assert (True is False)      (x3: I1 evaluate [cr] [u2028] [ff], line 159)
E   AssertionError: {'ok': True, 'verb': 'write', 'followups': ['FU1', 'FU2'], 'receipt': 'https://x/c/1'}
    assert (True is False)      (x3: I1 run_verb [cr] [u2028] [ff], line 167)
E   Failed: DID NOT RAISE _Refusal      (x3: I3 [cr] [u2028] [ff], line 173)
9 failed, 39 passed in 0.79s
```

  The LF cases (I2) and I4 stay green under H5, as expected: they do not depend on the guard's start.
- **Restore:** inverse Edit, the `# H5-NEUTRALIZED` line back to `span_start = _after_marker_line(body, offsets["advisor-vet"])`.
- **Restore receipt:** `grep -n NEUTRALIZED plugins/superheroes/lib/vet_slot.py` after both restores matched nothing (exit 1);
  restored line quoted back, `453:    span_start = _after_marker_line(body, offsets["advisor-vet"])`. `git status --porcelain` over the path: ` M plugins/superheroes/lib/vet_slot.py`
  (the intended fix, no residue).
- **Raw green** (`-k "test_i1 or test_i3"`, after the restore):

```
............                                                             [100%]
12 passed, 36 deselected in 0.45s
```

### H5a: the guard's `-1` return and the helper's `write-failed` raise (axis: an unterminated marker line refuses markers-invalid)

**Unreachable through this entry point.** `analyze_body` cannot deliver the guarded input to this branch:

- The public path that strips it: `_find_live_standalone_markers` returns a zero-indent standalone line's start, and
  `analyze_body` has already refused `markers-invalid` unless the advisor-vet marker is above the build-record marker
  (`offsets["advisor-vet"] >= offsets["build-record"]`). The build-record marker sits on a later line, so the advisor-vet
  marker's `str.splitlines()` line always has a terminator and `_after_marker_line` never returns `-1`. The marker offset
  is the start of a line of the body, so the helper's `write-failed` raise ("the offset is not on any line") cannot
  happen either.
- The seam and `file:line` of the proof that does bite: none. No test exercises either branch, by the order's
  instruction. The branch is a defensive guard (`vet_slot.py:455-456`, `raise _Refusal("markers-invalid", ...)` on `-1`;
  the helper's `write-failed` propagates unchanged), carrying a one-line `Unreachable through this entry point` comment at
  the detector (`vet_slot.py:454`). Its protection is unverified, by construction.

### H6: the write's span end is the build-record marker's own line start (axis: the write's span ends at `build_at`, never after the previous "\n")

- **Guarded element:** `vet_slot.py:751`, `b = build_at` in the builder path of `evaluate`.
- **Neutralization:** that line became `b = body.rfind("\n", 0, build_at) + 1  # H6-NEUTRALIZED` (H5 restored first).
- **Raw red** (`-k test_i4`, `--tb=short`, `cut -c1-200`; the three failures are the same shape, the assertion text and its
  context lines are condensed to the first):

```
FFF                                                                      [100%]
test_vet_slot_builder_path_verdict_read_2342.py:186: in test_i4_the_old_slot_text_before_the_build_record_marker_is_replaced_not_kept
    new_body = result["newBody"]
E   assert 'old slot text' not in "## What's c...n\ntrailer\n"
E     'old slot text' is contained here:
E       er half.
E       
E       old slot text
E       <!-- superheroes:build-record -->
E       <details><summary>Build record</summary>...
3 failed, 45 deselected in 0.42s      ([cr] [u2028] [ff])
```

  (The failing assertion is `assert "old slot text" not in new_body` at test file line 186; the short traceback printed
  the source line above it, `new_body = result["newBody"]`, beside that line number.)
- **Restore:** inverse Edit, the `# H6-NEUTRALIZED` line back to `b = build_at`.
- **Restore receipt:** `grep -n NEUTRALIZED plugins/superheroes/lib/vet_slot.py` matched nothing (exit 1); restored line
  quoted back, `751:    b = build_at`. `git status --porcelain` over the path: ` M plugins/superheroes/lib/vet_slot.py` (the intended fix, no residue).
- **Raw green** (`-k test_i4`, after the restore):

```
...                                                                      [100%]
3 passed, 45 deselected in 0.36s
```

### After both restores

Full new file before the neutralizations: `48 passed in 0.58s`. I5, the seven named test files together, unedited:
`664 passed in 3.16s`. In an LF body the write's end offset is the same as before (`rfind("\n", 0, build_at) + 1 == build_at`
when the character before the marker is "\n"; B3 and the whole existing suite pass unedited).
