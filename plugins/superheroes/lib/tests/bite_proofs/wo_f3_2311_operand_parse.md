# Bite-proof record: WO-F3 (#2311), a calibration read is credited only for a file operand, parsed by position

Detector: the parametrized test `test_codex_read_is_credited_only_for_a_file_operand_of_a_content_printing_command`
in `plugins/superheroes/lib/tests/test_calibration_read.py`, run against
`plugins/superheroes/lib/calibration_read.py` (`_file_operands`, `_OPERAND_SPECS`, `_command_hit`).

Declared guarded-element set (from the order): F1 to F4, one neutralization and one red each.
Every neutralization is a targeted Edit undone by the inverse Edit. Every red ran the detector
unedited, by exact node id, under `scripts/pinned-python -B -m pytest <node ids> -q`. In every
node id below, `T` stands for
`plugins/superheroes/lib/tests/test_calibration_read.py::test_codex_read_is_credited_only_for_a_file_operand_of_a_content_printing_command`.
Captures are the tail of the pytest output as seen (the `UV_NATIVE_TLS` warning line is dropped, and
the echoed parametrize source block of the failing test is elided where marked). Nothing in them is
a credential or a private URL; no redaction was needed.

Disclosed handling: the F1 red was run twice (the first neutralization turned only one of the two
named cases red, see F1). The F1 and F2 red captures were filtered by a `grep -v` that dropped the
indented test-source lines only (the assertion, the `E` lines and the `FAILED` lines are intact); the
F3 and F4 red captures are unfiltered `tail` output.

## F1: grep pattern position

- Guarded element: `_file_operands`, the final grep-family slice `files = files[1:]` (the first
  positional is the pattern when no `-e`/`--regexp` was given) and the rule that the argument of
  `-e`/`--regexp` is a value, never a file operand. Axis: a pattern argument is not a file operand.
- Neutralization, attempt 1 (only the slice): `files = files[1:]` became `files = files[:]`.
  Result: one case red (`grep <core> /tmp/other.txt`), the other (`grep -F -e <core> /tmp/other.txt`) stayed green, because that case
  never reaches the slice (its pattern is the `-e` value). Raw tail of attempt 1:

```
F.                                                                       [100%]
>       assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] == grade
E       AssertionError: assert 'read' == 'unknown'
E         - unknown
E         + read
FAILED ...::test_codex_read_is_credited_only_for_a_file_operand_of_a_content_printing_command[grep <core> /tmp/other.txt-unknown]
1 failed, 1 passed in 0.77s
```

- Neutralization, attempt 2 (the one that covers both named cases): the two lines
  `if program in _GREP_PROGRAMS and not values and not any(f.startswith("--regexp=") for f in flags):` / `files = files[1:]`
  became `if program in _GREP_PROGRAMS:` / `files = files + [v for v in values if v]`
  (every grep-family positional and every `-e` argument is a file operand).
- Detector nodes: `T[grep <core> /tmp/other.txt-unknown]` and `T[grep -F -e <core> /tmp/other.txt-unknown]`.
- Raw red (attempt 2):

```
FF                                                                       [100%]
=================================== FAILURES ===================================
_ test_codex_read_is_credited_only_for_a_file_operand_of_a_content_printing_command[grep <core> /tmp/other.txt-unknown] _
calib = <test_calibration_read.Calib object at 0x7f3fc636a180>
command = 'grep <core> /tmp/other.txt', grade = 'unknown'
>       assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] == grade
E       AssertionError: assert 'read' == 'unknown'
E         
E         - unknown
E         + read
/home/user/sh-2311/plugins/superheroes/lib/tests/test_calibration_read.py:256: AssertionError
_ test_codex_read_is_credited_only_for_a_file_operand_of_a_content_printing_command[grep -F -e <core> /tmp/other.txt-unknown] _
calib = <test_calibration_read.Calib object at 0x7f3fc636a300>
command = 'grep -F -e <core> /tmp/other.txt', grade = 'unknown'
>       assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] == grade
E       AssertionError: assert 'read' == 'unknown'
E         
E         - unknown
E         + read
/home/user/sh-2311/plugins/superheroes/lib/tests/test_calibration_read.py:256: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_calibration_read.py::test_codex_read_is_credited_only_for_a_file_operand_of_a_content_printing_command[grep <core> /tmp/other.txt-unknown]
FAILED plugins/superheroes/lib/tests/test_calibration_read.py::test_codex_read_is_credited_only_for_a_file_operand_of_a_content_printing_command[grep -F -e <core> /tmp/other.txt-unknown]
2 failed in 2.14s
```

- Restore: inverse Edit. Restore receipt (Grep of the file after): `368:    if program in _GREP_PROGRAMS and not values and not any(f.startswith("--regexp=") for f in flags):` / `369:        files = files[1:]`
- Raw green:

```
..                                                                       [100%]
2 passed in 0.31s
```

## F2: the program allowlist

- Guarded element: `_file_operands`, `spec = _OPERAND_SPECS.get(program)` followed by `if spec is None: return None`.
  Axis: a program not on the allowlist can never credit a read.
- Neutralization: `spec = _OPERAND_SPECS.get(program)` became `spec = _OPERAND_SPECS.get(program) or _OPERAND_SPECS["cat"]`
  (any program with the target as an argument is parsed like `cat`).
- Detector nodes: `T[xxd <core>-unknown]` and `T[sort <core>-unknown]`.
- Raw red (the echoed parametrize source block elided; the two tracebacks are identical in shape):

```
FF                                                                       [100%]
=================================== FAILURES ===================================
_ test_codex_read_is_credited_only_for_a_file_operand_of_a_content_printing_command[xxd <core>-unknown] _
calib = <test_calibration_read.Calib object at 0x7faa3b922150>
command = 'xxd <core>', grade = 'unknown'
>       assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] == grade
E       AssertionError: assert 'read' == 'unknown'
E         - unknown
E         + read
/home/user/sh-2311/plugins/superheroes/lib/tests/test_calibration_read.py:256: AssertionError
_ test_codex_read_is_credited_only_for_a_file_operand_of_a_content_printing_command[sort <core>-unknown] _
calib = <test_calibration_read.Calib object at 0x7faa3b9221b0>
command = 'sort <core>', grade = 'unknown'
>       assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] == grade
E       AssertionError: assert 'read' == 'unknown'
E         - unknown
E         + read
FAILED plugins/superheroes/lib/tests/test_calibration_read.py::test_codex_read_is_credited_only_for_a_file_operand_of_a_content_printing_command[xxd <core>-unknown]
FAILED plugins/superheroes/lib/tests/test_calibration_read.py::test_codex_read_is_credited_only_for_a_file_operand_of_a_content_printing_command[sort <core>-unknown]
2 failed in 0.31s
```

- Restore: inverse Edit. Restore receipt (Grep after): `348:    spec = _OPERAND_SPECS.get(program)` / `349:    if spec is None:`
- Raw green:

```
..                                                                       [100%]
2 passed in 0.28s
```

## F3: the sed print-script gate

- Guarded element: `_OPERAND_SPECS["sed"]`, the third item (the script must match the print-script pattern).
  Axis: a sed script other than a bare print is never a read.
- Neutralization: `"sed": ("-n|-e", "-e", r"\s*(\d+|\$)?(\s*,\s*(\d+|\$))?\s*p\s*"),` became `"sed": ("-n|-e", "-e", r"(?s).*"),`.
- Detector node: `T[sed -n 's/a/b/p' <core>-unknown]`.
- Raw red (the echoed parametrize source block elided):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_codex_read_is_credited_only_for_a_file_operand_of_a_content_printing_command[sed -n 's/a/b/p' <core>-unknown] _
calib = <test_calibration_read.Calib object at 0x7f0a5c5b2180>
command = "sed -n 's/a/b/p' <core>", grade = 'unknown'
>       assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] == grade
E       AssertionError: assert 'read' == 'unknown'
E         
E         - unknown
E         + read

/home/user/sh-2311/plugins/superheroes/lib/tests/test_calibration_read.py:256: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_calibration_read.py::test_codex_read_is_credited_only_for_a_file_operand_of_a_content_printing_command[sed -n 's/a/b/p' <core>-unknown]
1 failed in 0.38s
```

- Restore: inverse Edit. Restore receipt (Grep after): `336:    "sed": ("-n|-e", "-e", r"\s*(\d+|\$)?(\s*,\s*(\d+|\$))?\s*p\s*"),`
- Raw green:

```
.                                                                        [100%]
1 passed in 0.23s
```

## F4: the awk program gate

- Guarded element: `_OPERAND_SPECS["awk"]`, the third item (the program must be `1` or a bare print program).
  Axis: an awk program that does anything but print is never a read.
- Neutralization: the awk third item `r"1|\s*(%s(\s*&&\s*%s)?\s*)?\{\s*print(\s+\$0)?\s*;?\s*\}\s*" % (_NR, _NR)` became `r"(?s).*"`.
- Detector node: `T[awk '{system("x")}' <core>-unknown]`.
- Raw red (the echoed parametrize source block elided):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_codex_read_is_credited_only_for_a_file_operand_of_a_content_printing_command[awk '{system("x")}' <core>-unknown] _
calib = <test_calibration_read.Calib object at 0x7f5c0f342180>
command = 'awk \'{system("x")}\' <core>', grade = 'unknown'
>       assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] == grade
E       AssertionError: assert 'read' == 'unknown'
E         
E         - unknown
E         + read

/home/user/sh-2311/plugins/superheroes/lib/tests/test_calibration_read.py:256: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_calibration_read.py::test_codex_read_is_credited_only_for_a_file_operand_of_a_content_printing_command[awk '{system("x")}' <core>-unknown]
1 failed in 0.25s
```

- Restore: inverse Edit. Restore receipt (Grep after): `337:    "awk": (_NO_OPTION, _NO_OPTION, r"1|\s*(%s(\s*&&\s*%s)?\s*)?\{\s*print(\s+\$0)?\s*;?\s*\}\s*" % (_NR, _NR)),`
- Raw green:

```
.                                                                        [100%]
1 passed in 0.21s
```

## Not neutralized (listed, not claimed)

The `head`/`tail` count gate, the `cat`-family no-option rule, the `sed` `-n` requirement and the
single-script rule, and the grep short-flag and long-flag lists are guarded by test cases
(`head -c 10`, `cat -A`, `less -N`, `sed -i -n p`, `sed 's/a/b/'`, `grep -- foo`, `grep -f`) but have
no neutralization of their own in this record; the order declared F1 to F4 only.
