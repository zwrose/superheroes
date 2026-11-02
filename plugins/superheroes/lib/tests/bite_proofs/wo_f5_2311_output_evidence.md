# Bite-proof record: WO-F5 (#2311), a calibration read is credited only when the call's own output shows the file

Detectors, in `plugins/superheroes/lib/tests/test_calibration_read.py`, run against
`plugins/superheroes/lib/calibration_read.py` (`_file_state`, `_output_shows_file`, `_is_nontrivial`, `_simple_command`):

- `N` = `test_codex_read_needs_the_calls_own_output_to_show_the_file` (parametrized by explicit ids);
- `D` = `test_a_stamp_entry_without_line_digests_grades_unknown_for_an_otherwise_good_read`;
- `T` = `test_codex_read_is_credited_only_for_one_structurally_single_command` (FU9 case added to it).

Declared guarded-element set (from the order): O1, O2, O3, W1, one neutralization and one red each (O1 has one
red per named node). Every neutralization is a targeted Edit undone by the inverse Edit. Every red ran the
detector unedited, by exact node id, under `scripts/pinned-python -B -m pytest <node ids> -q --tb=short`; every
green is the same node ids after the inverse Edit. Captures are the pytest output as seen with the
`UV_NATIVE_TLS` warning line dropped (`grep -v UV_NATIVE_TLS`); nothing else was cut. Nothing in them is a
credential or a private URL; no redaction was needed. The restore receipt for each element is the restored line
quoted back from the file by `grep -n` after the inverse Edit.

Disclosed handling:

- **Order premise that did not hold for two named shapes.** The order lists `rg -h <core>` and `rg -nh <core>`
  as passing the structural rule. They do not: `rg` (like `grep`) takes the first non-option word as the
  PATTERN, so in `rg -h <core>` the core path is the pattern and no file operand is left; `_file_operands`
  returns `[]` and the rule already grades `unknown`. With O1 applied they stay green (an exploratory O1 run of
  the 8 nodes first listed in the order showed exactly those two passing and the other six red). The test keeps
  those two literal cases (they hold, by the structural rule alone) and ADDS `rg -h Policy <core>` and
  `rg -nh Policy <core>` (ids `rg-h-with-pattern-is-help`, `rg-nh-with-pattern-is-help`), which do pass the
  structural rule and are red under O1. The O1 red below includes both.
- The first-edit exploratory O1 run is not quoted; the run below is the full one.

## O1: the output gate

- Guarded element: `_file_state`, the rewrite of a successful `_HIT_READ` hit to `_HIT_AMBIGUOUS` unless
  `_output_shows_file(call["output"], digests, basename)`. Axis: a prefilter read counts only when the call's own
  output holds a non-trivial line of the file.
- Neutralization: `and not _output_shows_file(call["output"], digests, basename) else hit)` became
  `and False else hit)` (a prefilter read counts without the output check).
- Detector nodes (all under `N`, id in brackets): `rg-h-is-help`, `rg-nh-is-help`, `rg-h-with-pattern-is-help`,
  `rg-nh-with-pattern-is-help`, `rg-E-is-the-encoding-option`, `two-files-one-stream`, `tail-start-past-the-end`,
  `sed-line-past-the-end`, `shell-comment`, `cat-empty-output`, `cat-heading-and-blank-only`,
  `cat-no-aggregated-output-key`. Red on every one except the two literal `rg -h <core>` / `rg -nh <core>` nodes
  (see the disclosure above: the structural rule alone decides those).
- Raw red (one run over all twelve node ids):

```
..FFFFFFFFFF                                                             [100%]
=================================== FAILURES ===================================
_ test_codex_read_needs_the_calls_own_output_to_show_the_file[rg-h-with-pattern-is-help] _
/home/user/sh-2311/plugins/superheroes/lib/tests/test_calibration_read.py:439: in test_codex_read_needs_the_calls_own_output_to_show_the_file
    assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] == grade
E   AssertionError: assert 'read' == 'unknown'
E     
E     - unknown
E     + read
_ test_codex_read_needs_the_calls_own_output_to_show_the_file[rg-nh-with-pattern-is-help] _
/home/user/sh-2311/plugins/superheroes/lib/tests/test_calibration_read.py:439: in test_codex_read_needs_the_calls_own_output_to_show_the_file
    assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] == grade
E   AssertionError: assert 'read' == 'unknown'
E     
E     - unknown
E     + read
_ test_codex_read_needs_the_calls_own_output_to_show_the_file[rg-E-is-the-encoding-option] _
/home/user/sh-2311/plugins/superheroes/lib/tests/test_calibration_read.py:439: in test_codex_read_needs_the_calls_own_output_to_show_the_file
    assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] == grade
E   AssertionError: assert 'read' == 'unknown'
E     
E     - unknown
E     + read
_ test_codex_read_needs_the_calls_own_output_to_show_the_file[two-files-one-stream] _
/home/user/sh-2311/plugins/superheroes/lib/tests/test_calibration_read.py:439: in test_codex_read_needs_the_calls_own_output_to_show_the_file
    assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] == grade
E   AssertionError: assert 'read' == 'unknown'
E     
E     - unknown
E     + read
_ test_codex_read_needs_the_calls_own_output_to_show_the_file[tail-start-past-the-end] _
/home/user/sh-2311/plugins/superheroes/lib/tests/test_calibration_read.py:439: in test_codex_read_needs_the_calls_own_output_to_show_the_file
    assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] == grade
E   AssertionError: assert 'read' == 'unknown'
E     
E     - unknown
E     + read
_ test_codex_read_needs_the_calls_own_output_to_show_the_file[sed-line-past-the-end] _
/home/user/sh-2311/plugins/superheroes/lib/tests/test_calibration_read.py:439: in test_codex_read_needs_the_calls_own_output_to_show_the_file
    assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] == grade
E   AssertionError: assert 'read' == 'unknown'
E     
E     - unknown
E     + read
__ test_codex_read_needs_the_calls_own_output_to_show_the_file[shell-comment] __
/home/user/sh-2311/plugins/superheroes/lib/tests/test_calibration_read.py:439: in test_codex_read_needs_the_calls_own_output_to_show_the_file
    assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] == grade
E   AssertionError: assert 'read' == 'unknown'
E     
E     - unknown
E     + read
_ test_codex_read_needs_the_calls_own_output_to_show_the_file[cat-empty-output] _
/home/user/sh-2311/plugins/superheroes/lib/tests/test_calibration_read.py:439: in test_codex_read_needs_the_calls_own_output_to_show_the_file
    assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] == grade
E   AssertionError: assert 'read' == 'unknown'
E     
E     - unknown
E     + read
_ test_codex_read_needs_the_calls_own_output_to_show_the_file[cat-heading-and-blank-only] _
/home/user/sh-2311/plugins/superheroes/lib/tests/test_calibration_read.py:439: in test_codex_read_needs_the_calls_own_output_to_show_the_file
    assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] == grade
E   AssertionError: assert 'read' == 'unknown'
E     
E     - unknown
E     + read
_ test_codex_read_needs_the_calls_own_output_to_show_the_file[cat-no-aggregated-output-key] _
/home/user/sh-2311/plugins/superheroes/lib/tests/test_calibration_read.py:439: in test_codex_read_needs_the_calls_own_output_to_show_the_file
    assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] == grade
E   AssertionError: assert 'read' == 'unknown'
E     
E     - unknown
E     + read
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_calibration_read.py::test_codex_read_needs_the_calls_own_output_to_show_the_file[rg-h-with-pattern-is-help]
FAILED plugins/superheroes/lib/tests/test_calibration_read.py::test_codex_read_needs_the_calls_own_output_to_show_the_file[rg-nh-with-pattern-is-help]
FAILED plugins/superheroes/lib/tests/test_calibration_read.py::test_codex_read_needs_the_calls_own_output_to_show_the_file[rg-E-is-the-encoding-option]
FAILED plugins/superheroes/lib/tests/test_calibration_read.py::test_codex_read_needs_the_calls_own_output_to_show_the_file[two-files-one-stream]
FAILED plugins/superheroes/lib/tests/test_calibration_read.py::test_codex_read_needs_the_calls_own_output_to_show_the_file[tail-start-past-the-end]
FAILED plugins/superheroes/lib/tests/test_calibration_read.py::test_codex_read_needs_the_calls_own_output_to_show_the_file[sed-line-past-the-end]
FAILED plugins/superheroes/lib/tests/test_calibration_read.py::test_codex_read_needs_the_calls_own_output_to_show_the_file[shell-comment]
FAILED plugins/superheroes/lib/tests/test_calibration_read.py::test_codex_read_needs_the_calls_own_output_to_show_the_file[cat-empty-output]
FAILED plugins/superheroes/lib/tests/test_calibration_read.py::test_codex_read_needs_the_calls_own_output_to_show_the_file[cat-heading-and-blank-only]
FAILED plugins/superheroes/lib/tests/test_calibration_read.py::test_codex_read_needs_the_calls_own_output_to_show_the_file[cat-no-aggregated-output-key]
10 failed, 2 passed in 1.10s
```

  The two `.` at the head are `rg-h-is-help` and `rg-nh-is-help`, the literal order shapes the structural rule
  already refuses.
- Restore: inverse Edit. Restore receipt (grep -n after): `576:             and not _output_shows_file(call["output"], digests, basename) else hit)`
- Raw green (the same twelve node ids):

```
............                                                             [100%]
12 passed in 0.57s
```

## O2: the non-trivial filter

- Guarded element: `_is_nontrivial`, the 24-character, 12-letter, not-`#` test (constants `MIN_LINE_CHARS = 24`,
  `MIN_LINE_LETTERS = 12`). Axis: short, blank and heading lines recur across files and prompts, so they never
  count as showing the file.
- Neutralization: the two-line `return (len(line) >= MIN_LINE_CHARS and not line.startswith("#") and sum(...) >= MIN_LINE_LETTERS)`
  became `return True` (every line counts, so the stamp digests the heading and blank lines too).
- Detector node: `N[cat-heading-and-blank-only]` (output `## Verify` and a blank line; `CORE_TEXT` holds both).
- Raw red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_codex_read_needs_the_calls_own_output_to_show_the_file[cat-heading-and-blank-only] _
/home/user/sh-2311/plugins/superheroes/lib/tests/test_calibration_read.py:439: in test_codex_read_needs_the_calls_own_output_to_show_the_file
    assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] == grade
E   AssertionError: assert 'read' == 'unknown'
E     
E     - unknown
E     + read
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_calibration_read.py::test_codex_read_needs_the_calls_own_output_to_show_the_file[cat-heading-and-blank-only]
1 failed in 0.32s
```

- Restore: inverse Edit. Restore receipt (grep -n -A1 after):
  `85:    return (len(line) >= MIN_LINE_CHARS and not line.startswith("#")` / `86:            and sum(1 for ch in line if ch.isalpha()) >= MIN_LINE_LETTERS)`
- Raw green:

```
.                                                                        [100%]
1 passed in 0.30s
```

## O3: the missing-digests rule

- Guarded element: `_output_shows_file`, `if digests is None or ...: return False`. Axis: a stamp without
  `lineDigests` (a run opened before this change) can never satisfy the output check, so its reads grade unknown.
- Neutralization: the guard was split so `if digests is None: return True` came first (a stamp without
  `lineDigests` matches).
- Detector node: `D`.
- Raw red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_stamp_entry_without_line_digests_grades_unknown_for_an_otherwise_good_read _
/home/user/sh-2311/plugins/superheroes/lib/tests/test_calibration_read.py:446: in test_a_stamp_entry_without_line_digests_grades_unknown_for_an_otherwise_good_read
    assert _reads(CR.read_states("codex", stdout, old))["core"] == "unknown"
E   AssertionError: assert 'read' == 'unknown'
E     
E     - unknown
E     + read
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_calibration_read.py::test_a_stamp_entry_without_line_digests_grades_unknown_for_an_otherwise_good_read
1 failed in 0.40s
```

- Restore: inverse Edit. Restore receipt (grep -n after): `557:    if digests is None or not isinstance(output, str) or not output:`
- Raw green:

```
.                                                                        [100%]
1 passed in 0.34s
```

## W1: the FU9 wrapper option guard

- Guarded element: `_simple_command`, `tokens[1] in ("-c", "-lc")` in the unwrap condition. Axis: a shell wrapper
  is unwrapped only with exactly one option word, `-c` or `-lc` (`bash -n` runs nothing); the three-token length
  check alone admits `bash -n 'cat <core>'`.
- Neutralization: `if unwrap and len(tokens) == 3 and tokens[1] in ("-c", "-lc") and _program(tokens[0]) in _SHELL_PROGRAMS:`
  became `if unwrap and len(tokens) == 3 and _program(tokens[0]) in _SHELL_PROGRAMS:` (that clause only).
- Detector node: `T[bash -n 'cat <core>'-unknown]` (output holds `CORE_TEXT`, so the output check cannot save it).
- Raw red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_codex_read_is_credited_only_for_one_structurally_single_command[bash -n 'cat <core>'-unknown] _
/home/user/sh-2311/plugins/superheroes/lib/tests/test_calibration_read.py:383: in test_codex_read_is_credited_only_for_one_structurally_single_command
    assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] == grade
E   AssertionError: assert 'read' == 'unknown'
E     
E     - unknown
E     + read
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_calibration_read.py::test_codex_read_is_credited_only_for_one_structurally_single_command[bash -n 'cat <core>'-unknown]
1 failed in 0.34s
```

- Restore: inverse Edit. Restore receipt (grep -n after): `487:    if unwrap and len(tokens) == 3 and tokens[1] in ("-c", "-lc") and _program(tokens[0]) in _SHELL_PROGRAMS:`
- Raw green:

```
.                                                                        [100%]
1 passed in 0.24s
```
