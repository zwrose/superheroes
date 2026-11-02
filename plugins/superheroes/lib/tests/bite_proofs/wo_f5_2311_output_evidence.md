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

## A1: the arrow separator

Added by WO-F6 (#2311), after the scoped review of WO-F5 found that the Claude Code Read tool numbers lines as
`     1→# Core` (U+2192) and `_output_candidates` stripped only a tab, colon, pipe or hyphen. The capture rules
above hold: the `UV_NATIVE_TLS` warning line dropped, nothing else cut, no credential or private URL, no redaction.

- Guarded element: `_output_candidates`, the line-number prefix pattern `^\s*\d+[\t:|\-→]\s?`, the `→` in the
  separator class. Axis: a line-number prefix followed by U+2192 (the Claude Code Read tool's own form) is
  stripped before matching, so a Claude-engine reviewer that read its calibration grades `read`.
- Neutralization: `[\t:|\-→]` became `[\t:|\-]` (the arrow removed from the class).
- Detector node: `plugins/superheroes/lib/tests/test_calibration_read.py::test_claude_read_with_numbered_content_reads_and_with_empty_content_is_unknown`
  (its `grade(_numbered_arrow(CORE_TEXT)) == "read"` assertion).
- Raw red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_claude_read_with_numbered_content_reads_and_with_empty_content_is_unknown _
/home/user/sh-2311/plugins/superheroes/lib/tests/test_calibration_read.py:607: in test_claude_read_with_numbered_content_reads_and_with_empty_content_is_unknown
    assert grade(_numbered_arrow(CORE_TEXT)) == "read"
E   AssertionError: assert 'unknown' == 'read'
E     
E     - read
E     + unknown
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_calibration_read.py::test_claude_read_with_numbered_content_reads_and_with_empty_content_is_unknown
1 failed in 0.48s
```

- Restore: inverse Edit. Restore receipt (grep -n after): `547:    yield re.sub(r"^\s*\d+[\t:|\-→]\s?", "", line).strip()  # cat -n, nl, grep -n, the Claude Read tool (tab or U+2192 arrow)`
- Raw green:

```
.                                                                        [100%]
1 passed in 3.71s
```

## WO-F7 (#2311): a read is credited only when the stamped file is the one file the output can carry

Added by WO-F7. Same capture rules as above: every red ran the detector unedited by exact node id under
`scripts/pinned-python -B -m pytest <node ids> -q --tb=short`, the `UV_NATIVE_TLS` warning line dropped
(`grep -v UV_NATIVE_TLS`), nothing else cut; every green is the same node ids after the inverse Edit; no credential
or private URL, no redaction. Each neutralization is a targeted Edit undone by the inverse Edit; the restore receipt
is the restored line quoted back by `grep -n`.

Detectors, in `plugins/superheroes/lib/tests/test_calibration_read.py`:

- `S` = `test_codex_read_needs_the_stamped_file_to_be_the_one_file_the_output_can_carry` (explicit ids);
- `M` = `test_mcp_read_tool_credits_only_its_own_key_and_only_when_it_names_one_file` (explicit ids);
- `G` = `test_codex_gate_reads_each_calls_own_output_not_another_calls`.

Disclosed handling:

- Item 1b (grep/egrep/fgrep/rg naming more than one file operand is not a read) is the builder's addition inside the
  order's seam; B2 guards it.
- B1 and B2 neutralize the same line (`len(files) > 1` in `_file_operands`) on different programs: B1 drops `sed`
  from the program tuple, B2 drops the grep family from it. They are separate failure modes (a sed sibling and a grep
  sibling), each with its own red.
- The first B3 run used the single multi-assertion form of `M`, where the first assertion failed and hid the
  two-path assertion behind it. That run is not quoted; `M` was then split into one node per case and the B3 red
  below is the full one over the three named nodes. This cost one invocation more than the eight the order budgeted.
- `S[sed-core-alone]`, `S[grep-core-alone]`, `S[cat-sibling-and-core]` and `M[one-path-in-paths]` are the greens that
  keep the rule from over-refusing; they are green under every neutralization below (they guard no neutralization).
- Item 3 (the `<spelling>:` / `<spelling>:<n>:` prefix strip) and E2 (a sibling's prefix is not stripped) are
  detected by `test_codex_prefix_naming_the_stamped_files_own_spelling_is_stripped`,
  `test_codex_prefix_strip_holds_for_a_path_with_a_space_in_a_directory_name` and `S[sibling-path-prefix-kept]`; the
  order named no neutralization for them, so no red is claimed for them here.

## B1: sed names one file

- Guarded element: `_file_operands`, `if program in ("sed",) + _GREP_PROGRAMS and len(files) > 1: return None`, the
  `"sed"` member. Axis: a `sed` naming more than one file operand is not a read.
- Neutralization: `if program in ("sed",) + _GREP_PROGRAMS and len(files) > 1:` became
  `if program in _GREP_PROGRAMS and len(files) > 1:` (sed accepts several files).
- Detector node: `S[sed-sibling-and-core]`.
- Raw red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_codex_read_needs_the_stamped_file_to_be_the_one_file_the_output_can_carry[sed-sibling-and-core] _
/home/user/sh-2311/plugins/superheroes/lib/tests/test_calibration_read.py:462: in test_codex_read_needs_the_stamped_file_to_be_the_one_file_the_output_can_carry
    assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] == grade
E   AssertionError: assert 'read' == 'unknown'
E     
E     - unknown
E     + read
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_calibration_read.py::test_codex_read_needs_the_stamped_file_to_be_the_one_file_the_output_can_carry[sed-sibling-and-core]
1 failed in 0.39s
```

- Restore: inverse Edit. Restore receipt (grep -n after): `466:    if program in ("sed",) + _GREP_PROGRAMS and len(files) > 1:`
- Raw green:

```
.                                                                        [100%]
1 passed in 0.42s
```

## B2: the grep family names one file

- Guarded element: the same line, the `_GREP_PROGRAMS` member (item 1b). Axis: a `grep`/`egrep`/`fgrep`/`rg` naming
  more than one file operand is not a read (`-h` prints either file's matches with no prefix).
- Neutralization: `if program in ("sed",) + _GREP_PROGRAMS and len(files) > 1:` became
  `if program in ("sed",) and len(files) > 1:` (the grep family accepts several files).
- Detector nodes: `S[grep-h-sibling-and-core]`, `S[rg-h-sibling-and-core]`.
- Raw red:

```
FF                                                                       [100%]
=================================== FAILURES ===================================
_ test_codex_read_needs_the_stamped_file_to_be_the_one_file_the_output_can_carry[grep-h-sibling-and-core] _
/home/user/sh-2311/plugins/superheroes/lib/tests/test_calibration_read.py:462: in test_codex_read_needs_the_stamped_file_to_be_the_one_file_the_output_can_carry
    assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] == grade
E   AssertionError: assert 'read' == 'unknown'
E     
E     - unknown
E     + read
_ test_codex_read_needs_the_stamped_file_to_be_the_one_file_the_output_can_carry[rg-h-sibling-and-core] _
/home/user/sh-2311/plugins/superheroes/lib/tests/test_calibration_read.py:462: in test_codex_read_needs_the_stamped_file_to_be_the_one_file_the_output_can_carry
    assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] == grade
E   AssertionError: assert 'read' == 'unknown'
E     
E     - unknown
E     + read
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_calibration_read.py::test_codex_read_needs_the_stamped_file_to_be_the_one_file_the_output_can_carry[grep-h-sibling-and-core]
FAILED plugins/superheroes/lib/tests/test_calibration_read.py::test_codex_read_needs_the_stamped_file_to_be_the_one_file_the_output_can_carry[rg-h-sibling-and-core]
2 failed in 0.49s
```

- Restore: inverse Edit. Restore receipt (grep -n after): `466:    if program in ("sed",) + _GREP_PROGRAMS and len(files) > 1:`
- Raw green:

```
..                                                                       [100%]
2 passed in 0.28s
```

## B3: an MCP read tool credits its own path argument, exactly one

- Guarded element: `_codex_item_call`, the `mcp_tool_call` branch, the own-key choice (`paths` for
  `read_multiple_files`, `path` otherwise) and the `named_total == 1 and len(own) == 1` test. Axis: a read-file tool
  credits only its own key and only when the call names exactly one file in all.
- Neutralization: the block from `if tool == "read_multiple_files":` through `values.remove(own[0])` was replaced by
  the pre-WO-F7 form: `listed = arguments.get("paths")`, `own = [v for v in [arguments.get("path")] + (listed if
  isinstance(listed, list) else []) if isinstance(v, str)]`, `if own: paths = own; for path in own: values.remove(path)`
  (every `path`/`paths` string is credited, whatever the key or the count).
- Detector nodes: `M[read_file-other-path-core-paths]`, `M[two-paths-core-first]`, `M[two-paths-core-second]`.
- Raw red:

```
FFF                                                                      [100%]
=================================== FAILURES ===================================
_ test_mcp_read_tool_credits_only_its_own_key_and_only_when_it_names_one_file[read_file-other-path-core-paths] _
/home/user/sh-2311/plugins/superheroes/lib/tests/test_calibration_read.py:501: in test_mcp_read_tool_credits_only_its_own_key_and_only_when_it_names_one_file
    assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] == grade
E   AssertionError: assert 'read' == 'unknown'
E     
E     - unknown
E     + read
_ test_mcp_read_tool_credits_only_its_own_key_and_only_when_it_names_one_file[two-paths-core-first] _
/home/user/sh-2311/plugins/superheroes/lib/tests/test_calibration_read.py:501: in test_mcp_read_tool_credits_only_its_own_key_and_only_when_it_names_one_file
    assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] == grade
E   AssertionError: assert 'read' == 'unknown'
E     
E     - unknown
E     + read
_ test_mcp_read_tool_credits_only_its_own_key_and_only_when_it_names_one_file[two-paths-core-second] _
/home/user/sh-2311/plugins/superheroes/lib/tests/test_calibration_read.py:501: in test_mcp_read_tool_credits_only_its_own_key_and_only_when_it_names_one_file
    assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] == grade
E   AssertionError: assert 'read' == 'unknown'
E     
E     - unknown
E     + read
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_calibration_read.py::test_mcp_read_tool_credits_only_its_own_key_and_only_when_it_names_one_file[read_file-other-path-core-paths]
FAILED plugins/superheroes/lib/tests/test_calibration_read.py::test_mcp_read_tool_credits_only_its_own_key_and_only_when_it_names_one_file[two-paths-core-first]
FAILED plugins/superheroes/lib/tests/test_calibration_read.py::test_mcp_read_tool_credits_only_its_own_key_and_only_when_it_names_one_file[two-paths-core-second]
3 failed in 0.44s
```

- Restore: inverse Edit. Restore receipt (grep -n after):
  `240:            named_total = len(_string_values(arguments.get("path"))) + len(_string_values(arguments.get("paths")))` /
  `242:            if named_total == 1 and len(own) == 1:`
- Raw green:

```
...                                                                      [100%]
3 passed in 0.27s
```

## B4: each call's own output (test-002)

- Guarded element: `_file_state`, `_output_shows_file(call["output"], digests, basename, spellings)`, the `call["output"]`
  argument. Axis: the gate reads the call's own output, never another call's.
- Neutralization: `call["output"]` became `"\n".join(c["output"] for c in calls if isinstance(c["output"], str))`
  (the gate reads the concatenation of every call's output).
- Detector node: `G`.
- Raw red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
________ test_codex_gate_reads_each_calls_own_output_not_another_calls _________
/home/user/sh-2311/plugins/superheroes/lib/tests/test_calibration_read.py:510: in test_codex_gate_reads_each_calls_own_output_not_another_calls
    assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] == "unknown"
E   AssertionError: assert 'read' == 'unknown'
E     
E     - unknown
E     + read
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_calibration_read.py::test_codex_gate_reads_each_calls_own_output_not_another_calls
1 failed in 0.38s
```

- Restore: inverse Edit. Restore receipt (grep -n after): `597:             and not _output_shows_file(call["output"], digests, basename, spellings) else hit)`
- Raw green:

```
.                                                                        [100%]
1 passed in 0.39s
```

## WO-F8 (#2311): head and tail naming several files are not reads; a failed multi-file call is unknown

Detectors, in `plugins/superheroes/lib/tests/test_calibration_read.py`:

- `S` = `test_codex_read_needs_the_stamped_file_to_be_the_one_file_the_output_can_carry` (ids `tail-sibling-and-core`,
  `head-sibling-and-core`);
- `X` = `test_codex_failed_call_naming_another_file_beside_the_core_is_unknown` (id `failed-cat-missing-then-core`);
- `M` = `test_mcp_read_tool_credits_only_its_own_key_and_only_when_it_names_one_file` (id `failed-two-paths`).

Declared guarded-element set (from the order): H1, F1. Each is a targeted Edit undone by the inverse Edit; each red
ran the detector unedited by exact node id under `scripts/pinned-python -B -X pycache_prefix=/tmp/claude-0/shpyc -m
pytest <node ids> -q` (F1 also `--tb=short`); each green is the same node ids after the inverse Edit. Captures are
the pytest output with the `UV_NATIVE_TLS` warning line dropped. The H1 red below is its tail only (the
`short test summary info` block and the result line); the failure bodies above it repeat the parametrize table and
the same `assert 'read' == 'unknown'` for each node, and are elided (about 90 lines). No credential or private URL
is in them; no redaction was needed.

### H1: head and tail name one file

- Guarded element: `_file_operands`, the program tuple in `if program in ("sed", "head", "tail") + _GREP_PROGRAMS
  and len(files) > 1:`. Axis: a call naming several files is a read only when its program prints every file it
  names in full; `head` and `tail` print a slice of each.
- Neutralization: `("sed", "head", "tail") + _GREP_PROGRAMS` became `("sed",) + _GREP_PROGRAMS`.
- Detector nodes: `S[tail-sibling-and-core]`, `S[head-sibling-and-core]`.
- Raw red (tail of the output; failure bodies elided):

```
E       AssertionError: assert 'read' == 'unknown'
E         
E         - unknown
E         + read

/home/user/sh-2311/plugins/superheroes/lib/tests/test_calibration_read.py:468: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_calibration_read.py::test_codex_read_needs_the_stamped_file_to_be_the_one_file_the_output_can_carry[tail-sibling-and-core]
FAILED plugins/superheroes/lib/tests/test_calibration_read.py::test_codex_read_needs_the_stamped_file_to_be_the_one_file_the_output_can_carry[head-sibling-and-core]
2 failed in 0.43s
```

- Restore: inverse Edit. Restore receipt (grep -n after):
  `466:    if program in ("sed", "head", "tail") + _GREP_PROGRAMS and len(files) > 1:`
- Raw green:

```
..                                                                       [100%]
2 passed in 12.82s
```

### F1: a failed multi-file call is indeterminate

- Guarded element: `_names_other_file` (called from `_file_state`, the `_FAILED` branch). Axis: a failed call that
  names the stamped file beside another file grades unknown, not not-read.
- Neutralization: a `return False` inserted as the first statement of `_names_other_file`'s body, so it always
  says "names only the target".
- Detector nodes: `X[failed-cat-missing-then-core]`, `M[failed-two-paths]`.
- Raw red:

```
FF                                                                       [100%]
=================================== FAILURES ===================================
_ test_codex_failed_call_naming_another_file_beside_the_core_is_unknown[failed-cat-missing-then-core] _
/home/user/sh-2311/plugins/superheroes/lib/tests/test_calibration_read.py:483: in test_codex_failed_call_naming_another_file_beside_the_core_is_unknown
    assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] == grade
E   AssertionError: assert 'not-read' == 'unknown'
E     
E     - unknown
E     + not-read
_ test_mcp_read_tool_credits_only_its_own_key_and_only_when_it_names_one_file[failed-two-paths] _
/home/user/sh-2311/plugins/superheroes/lib/tests/test_calibration_read.py:522: in test_mcp_read_tool_credits_only_its_own_key_and_only_when_it_names_one_file
    assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] == grade
E   AssertionError: assert 'not-read' == 'unknown'
E     
E     - unknown
E     + not-read
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_calibration_read.py::test_codex_failed_call_naming_another_file_beside_the_core_is_unknown[failed-cat-missing-then-core]
FAILED plugins/superheroes/lib/tests/test_calibration_read.py::test_mcp_read_tool_credits_only_its_own_key_and_only_when_it_names_one_file[failed-two-paths]
2 failed in 0.61s
```

- Restore: inverse Edit. Restore receipt (grep -n -A8 after, the body's first lines):
  `535:    if any(isinstance(p, str) and p not in targets for p in call["paths"] + call["named"]):`
  `536:        return True`
- Raw green:

```
..                                                                       [100%]
2 passed in 0.40s
```

## WO-F9 (#2311): a failed single-file call stays not-read when its pattern, script or count is not a file

Detector: `Y` = `test_codex_failed_single_file_call_with_a_pattern_or_count_stays_not_read` (explicit ids). Declared
guarded-element set (from the order): F1b. The neutralization is a targeted Edit undone by the inverse Edit; the red
and the green ran by exact node id under `scripts/pinned-python -B -X pycache_prefix=/tmp/claude-0/shpyc -m pytest
<node ids> -q --tb=short`. Captures are the pytest output with the `UV_NATIVE_TLS` warning line dropped; nothing else
was cut. No credential or private URL; no redaction.

### F1b: file operands, not raw arguments

- Guarded element: `_names_other_file`, the shell branch's `operands = _file_operands(_program(word), args)`. Axis: a
  failed single-file call whose pattern, sed script or count is not a file stays not-read; only a file operand found
  by position (or, when none can be found, a raw non-option argument) names another file.
- Neutralization: `operands = _file_operands(_program(word), args)` became `operands = None` (the shell branch always
  uses the raw non-option arguments, today's behaviour).
- Detector nodes: `Y[failed-grep-pattern-not-a-file]`, `Y[failed-sed-script-not-a-file]`,
  `Y[failed-head-count-not-a-file]`.
- Raw red:

```
FFF                                                                      [100%]
=================================== FAILURES ===================================
_ test_codex_failed_single_file_call_with_a_pattern_or_count_stays_not_read[failed-grep-pattern-not-a-file] _
/home/user/sh-2311/plugins/superheroes/lib/tests/test_calibration_read.py:502: in test_codex_failed_single_file_call_with_a_pattern_or_count_stays_not_read
    assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] == grade
E   AssertionError: assert 'unknown' == 'not-read'
E     
E     - not-read
E     + unknown
_ test_codex_failed_single_file_call_with_a_pattern_or_count_stays_not_read[failed-sed-script-not-a-file] _
/home/user/sh-2311/plugins/superheroes/lib/tests/test_calibration_read.py:502: in test_codex_failed_single_file_call_with_a_pattern_or_count_stays_not_read
    assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] == grade
E   AssertionError: assert 'unknown' == 'not-read'
E     
E     - not-read
E     + unknown
_ test_codex_failed_single_file_call_with_a_pattern_or_count_stays_not_read[failed-head-count-not-a-file] _
/home/user/sh-2311/plugins/superheroes/lib/tests/test_calibration_read.py:502: in test_codex_failed_single_file_call_with_a_pattern_or_count_stays_not_read
    assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] == grade
E   AssertionError: assert 'unknown' == 'not-read'
E     
E     - not-read
E     + unknown
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_calibration_read.py::test_codex_failed_single_file_call_with_a_pattern_or_count_stays_not_read[failed-grep-pattern-not-a-file]
FAILED plugins/superheroes/lib/tests/test_calibration_read.py::test_codex_failed_single_file_call_with_a_pattern_or_count_stays_not_read[failed-sed-script-not-a-file]
FAILED plugins/superheroes/lib/tests/test_calibration_read.py::test_codex_failed_single_file_call_with_a_pattern_or_count_stays_not_read[failed-head-count-not-a-file]
3 failed in 0.47s
```

- Restore: inverse Edit. Restore receipt (grep -n after): `547:        operands = _file_operands(_program(word), args)`
- Raw green:

```
...                                                                      [100%]
3 passed in 5.02s
```
