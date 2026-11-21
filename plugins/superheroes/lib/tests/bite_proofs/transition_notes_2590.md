# Bite-proof record: transition_notes.py (issue 2590, work order A)

Detectors added: `parse_note` / `check_notes` (note-shape refusals), `compare_pr`, `release_problems`
in `plugins/superheroes/lib/transition_notes.py`, and the write-nothing-on-refusal edge of `assemble`.
Their tests are in `plugins/superheroes/lib/tests/test_transition_notes.py` (P below).
Axis lines: `transition_notes.py:87` (parse_note/check_notes), `:330` (compare_pr), `:355` (release_problems).

Declared guarded-element set (from the order): the 11 note-shape tokens; `compare_pr`'s four tokens;
`release_problems`' `note-unassembled-at-release`; `assemble`'s write-nothing-on-refusal edge.
That is 17 elements, 17 neutralizations, 17 reds, 17 greens. No equivalence classes are used.

Method, the same for every entry: the neutralization is an Edit that replaces the one statement that
raises the token (the `problems.append(_p(...))` call) with `pass`, so the branch's condition and the
rest of the flow stay intact. The Edit tool refuses a non-unique `old_string`, and each raising statement
(including the two `note-removed-unassembled` ones, whose details differ) occurs once in the module, so
the "exactly once" precondition holds. The test is run by its exact node
id, under `-X pycache_prefix=/tmp/wo-a-pyc`, as
`scripts/pinned-python -B -X pycache_prefix=/tmp/wo-a-pyc -m pytest P::<node> -q --tb=line`.
Restore is the inverse Edit (the `pass` replaced by the original statement, quoted below). The detector
test is not edited between the red and the green of an entry. Captures are short; nothing is elided
except the one `UV_NATIVE_TLS` deprecation warning line at the top of each run and, in the red runs, the
`-----` rule lines. No secrets or private URLs appear in any capture, so nothing was redacted.

Byte-clean receipt for the whole sequence: `sha256sum transition_notes.py` was
`6726fab54f5891321b15d407c1ed88faa80de0e309b2f3c261e250de30e836f8` before the first neutralization and
the same value after the last restore. `git status --porcelain -- plugins` after the sequence lists only
`?? plugins/superheroes/lib/tests/test_transition_notes.py` and `?? plugins/superheroes/lib/transition_notes.py`
(the third deliverable is this file, written after).

Every green run below ended `1 passed`. Every red run ended `1 failed`.

## Note-shape tokens (parse_note / check_notes)

### 1. note-empty (transition_notes.py:93) - axis: refusal of an empty note
- Neutralization: `problems.append(_p(name, "note-empty", "The note file is empty."))` -> `pass`
- Node: `P::test_token_note_empty`
- Red: `E   AssertionError: assert [] == ['note-empty']` / `FAILED ...::test_token_note_empty` / `1 failed`
- Restore: inverse Edit; restored line (under `if not text.strip():`):
  `problems.append(_p(name, "note-empty", "The note file is empty."))`
- Green: `1 passed in 0.34s`

### 2. note-name-invalid (:96) - axis: refusal of a file name that is not `<n>[-slug].md`
- Neutralization: the `problems.append(_p(name, "note-name-invalid", ...))` call -> `pass`
- Node: `P::test_token_note_name_invalid`
- Red: `E   AssertionError: notes.md` / `assert [] == ['note-name-invalid']` / `1 failed`
- Restore: inverse Edit; restored under `if not NOTE_NAME.match(name):` the original `problems.append(_p(name, "note-name-invalid", "The file name must be the issue number, optionally followed by a lowercase slug, ending in .md."))`
- Green: `1 passed in 0.38s`

### 3. note-fence-unbalanced (:106) - axis: refusal of a fence left open at end of file
- Neutralization: the append under `if fence:` -> `pass`
- Node: `P::test_token_note_fence_unbalanced`
- Red: `E   AssertionError: assert [] == ['note-fence-unbalanced']` / `1 failed`
- Restore: inverse Edit; restored `problems.append(_p(name, "note-fence-unbalanced", "A code fence is opened and never closed."))`
- Green: `1 passed in 0.29s`

### 4. note-heading-level (:109) - axis: refusal of a `#` or `##` heading outside a fence
- Neutralization: the append under `if not state[k] and _H12.match(ln):` -> `pass`
- Node: `P::test_token_note_heading_level`
- Red: `E   AssertionError: # Title` / `assert [] == ['note-heading-level']` / `1 failed`
- Restore: inverse Edit; restored `problems.append(_p(name, "note-heading-level", "A # or ## heading would break the version section: " + ln.strip()[:60]))`
- Green: `1 passed in 0.26s`

### 5. note-byu-missing (:116) - axis: refusal of a note whose first content line is not `### Before you upgrade`
- Neutralization: the append under `if not byu_ok:` -> `pass`
- Node: `P::test_token_note_byu_missing`
- Red: `E   AssertionError: assert [] == ['note-byu-missing']` / `1 failed`
- Restore: inverse Edit; restored `problems.append(_p(name, "note-byu-missing", "The first content line must be the heading ### " + BYU + "."))`
- Green: `1 passed in 0.30s`

### 6. note-byu-repeated (:125) - axis: refusal of a second `### Before you upgrade`
- Neutralization: the append under `if byu_ok:` (inside `if title == BYU:`) -> `pass`
- Node: `P::test_token_note_byu_repeated`
- Red: `E   AssertionError: assert [] == ['note-byu-repeated']` / `1 failed`
- Restore: inverse Edit; restored `problems.append(_p(name, "note-byu-repeated", "The heading ### " + BYU + " appears more than once."))`
- Green: `1 passed in 0.25s`

### 7. note-byu-stray (:140) - axis: refusal of prose under `### Before you upgrade` that assembly would drop
- Neutralization: the append in the `else:` of the BYU-region walk -> `pass`
- Node: `P::test_token_note_byu_stray`
- Red: `E   AssertionError: assert [] == ['note-byu-stray']` / `1 failed`
- Restore: inverse Edit; restored `problems.append(_p(name, "note-byu-stray", "Only bullets may sit under ### " + BYU + ", and this line would be lost: " + ln.strip()[:60]))`
- Green: `1 passed in 0.24s`

### 8. note-byu-empty (:142) - axis: refusal of a BYU list with no bullet
- Neutralization: the append under `if byu_ok and not bullets:` -> `pass`
- Node: `P::test_token_note_byu_empty`
- Red: `E   AssertionError: assert [] == ['note-byu-empty']` / `1 failed`
- Restore: inverse Edit; restored `problems.append(_p(name, "note-byu-empty", "The ### " + BYU + " list has no bullet."))`
- Green: `1 passed in 0.27s`

### 9. note-bullet-unmarked (:151) - axis: refusal of a bullet that does not open with the strict marker
- Neutralization: the append under `if not MARKER.match(b[2:].lstrip()):` -> `pass`
- Node: `P::test_token_note_bullet_unmarked`
- Red: `E   AssertionError: assert [] == ['note-bullet-unmarked']` / `1 failed`
- Restore: inverse Edit; restored `problems.append(_p(name, "note-bullet-unmarked", "A bullet must open with **Before switching.** or **After switching.**: " + b[2:].strip()[:60]))`
- Green: `1 passed in 0.26s`

### 10. note-section-missing (:153) - axis: refusal of a note with no `###` section after its bullets
- Neutralization: the append under `if byu_ok and not sections:` -> `pass`
- Node: `P::test_token_note_section_missing`
- Red: `E   AssertionError: assert [] == ['note-section-missing']` / `1 failed`
- Restore: inverse Edit; restored `problems.append(_p(name, "note-section-missing", "The note has no ### section after its bullets."))`
- Green: `1 passed in 0.24s`

### 11. note-heading-duplicate (:165, in check_notes) - axis: refusal of a section heading used twice, across notes or in one
- Neutralization: the append under `if heading in seen:` -> `pass`
- Node: `P::test_token_note_heading_duplicate`
- Red: `E   AssertionError: assert [] == ['note-heading-duplicate']` / `1 failed`
- Restore: inverse Edit; restored `problems.append(_p(name, "note-heading-duplicate", "The section heading ### " + heading + " is already used in " + seen[heading] + "."))`
- Green: `1 passed in 0.27s`

## compare_pr (axis line :330)

### 12. transition-heading-added (:341) - axis: a heading added to TRANSITION.md beyond what removed notes cover
- Neutralization: the append in `for heading in sorted((added - removed_headings).elements()):` -> `pass`
- Node: `P::test_compare_direct_heading_is_refused`
- Red: `E   AssertionError: assert [] == ['transition-heading-added']` / `1 failed`
- Restore: inverse Edit; restored `problems.append(_p(_TRANSITION, "transition-heading-added", "The heading ### " + heading + " was added to TRANSITION.md; write the note as a file in the notes folder instead."))`
- Green: `1 passed in 0.22s`

### 13. note-removed-unassembled, missing heading (:345) - axis: a removed note's section did not reach TRANSITION.md
- Neutralization: the append under `if sec["heading"] not in head["headings"]:` -> `pass`
- Node: `P::test_compare_assembly_dropping_a_section_is_refused`
- Red: `E   AssertionError: assert [] == ['note-removed-unassembled']` / `1 failed`
- Restore: inverse Edit; restored `problems.append(_p(p["name"], "note-removed-unassembled", "The note was removed but its section ### " + sec["heading"] + " did not reach TRANSITION.md."))`
- Green: `1 passed in 0.35s`

### 14. transition-bullet-added (:348) - axis: upgrade-step bullets gained beyond what removed notes held
- Neutralization: the append under `if delta > removed_bullets:` -> `pass`
- Node: `P::test_compare_direct_bullet_is_refused`
- Red: `E   AssertionError: assert [] == ['transition-bullet-added']` / `1 failed`
- Restore: inverse Edit; restored `problems.append(_p(_TRANSITION, "transition-bullet-added", "TRANSITION.md gained " + str(delta - removed_bullets) + " upgrade-step bullet(s) that no removed note accounts for; write them in a note file."))`
- Green: `1 passed in 0.36s`

### 15. note-removed-unassembled, bullet shortfall (:350) - axis: fewer bullets reached TRANSITION.md than removed notes held
- Neutralization: the append under `if delta < removed_bullets:` -> `pass`
- Node: `P::test_compare_assembly_dropping_a_bullet_is_refused`
- Red: `E   AssertionError: assert [] == ['note-removed-unassembled']` / `1 failed`
- Restore: inverse Edit; restored `problems.append(_p(_TRANSITION, "note-removed-unassembled", "Removed notes held " + str(removed_bullets) + " bullet(s) but TRANSITION.md gained " + str(delta) + ", a shortfall of " + str(removed_bullets - delta) + "."))`
- Green: `1 passed in 0.22s`

Entries 13 and 15 share a token and differ in branch; each has its own test that reaches only its branch
(the drop-a-section fixture keeps the bullet count equal, the drop-a-bullet fixture keeps every heading).

## release_problems (axis line :355)

### 16. note-unassembled-at-release (:357) - axis: a note file still present when a release is cut
- Neutralization: the `return [_p(name, "note-unassembled-at-release", ...) for name, _text in head_notes]` -> `return []`
- Node: `P::test_release_problems_one_per_note`
- Red: `E   AssertionError: assert [] == ['note-unasse...d-at-release']` / `Right contains 2 more items` / `1 failed`
- Restore: inverse Edit; restored `return [_p(name, "note-unassembled-at-release", "The note file is still present at release; run the assemble step first.")` / `for name, _text in head_notes]`
- Green: `1 passed in 0.35s`

## assemble write-nothing-on-refusal (transition_notes.py:372-373)

### 17. assemble refuses a malformed note and writes and removes nothing - axis: no side effect on refusal
- Neutralization: line 373 `return {"ok": False, "reason": "notes-malformed", "problems": exc.problems}` -> `new_text = text`
  (the refusal no longer returns, so `assemble` falls through to the write step and the per-file `os.remove`).
- Node: `P::test_assemble_refuses_malformed_note_and_writes_nothing`
- First attempt: the test then checked `result["ok"]` first, and the red was `E   assert True is False`, which is
  the return value, not the side effect. Per the rubric's wrong-axis trap the test was reordered (my own new test,
  before any recorded green of this entry) so the byte-identical TRANSITION.md and the files-present assertions come
  before the `ok` assertions. The code was restored (a first restore left `path =os.path.join` without its space,
  fixed by a second Edit and confirmed by the sha256 match above), then the entry was re-run from green.
- Red (final): `E   AssertionError: assert ['README.md'] == ['12.md', '3-..., 'README.md']` /
  `At index 0 diff: 'README.md' != '12.md'` / `Right contains 3 more items, first extra item: '3-two.md'` /
  `...test_transition_notes.py:415: AssertionError` / `1 failed`. This is on the side-effect axis: the note files were removed.
- Restore: inverse Edit; restored lines 373-374:
  `return {"ok": False, "reason": "notes-malformed", "problems": exc.problems}` / `path = os.path.join(plugin_root, _TRANSITION)`
- Green: `1 passed in 0.28s`
- Disclosure (not a vacuity trap, a limit of the red): with this neutralization `new_text` equals the old text, so the
  TRANSITION.md write is skipped by the `if new_text != text` guard and the red shows the file-removal half only.
  The byte-identical assertion (line 414) is in the test and passes in the red run, so the red does not show the write
  half biting. A neutralization that makes the write observable would need `render` to succeed on malformed notes, which
  lies outside this module's refusal edge (render's own guard raises first). The write half of this edge is therefore
  guarded by the same return but is not separately proven red.

## Final-head re-run

After the last restore the full file ran green on the final tree: `54 passed in 0.90s`, and
`test_adopt_version.py` ran `27 passed in 3.63s` (that module is unchanged).
