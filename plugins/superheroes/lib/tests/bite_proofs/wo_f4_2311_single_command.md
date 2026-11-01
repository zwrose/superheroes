# Bite-proof record: WO-F4 (#2311), a calibration read is credited only for a structurally single command

Detectors, in `plugins/superheroes/lib/tests/test_calibration_read.py`, run against
`plugins/superheroes/lib/calibration_read.py` (`_simple_command`, `_command_hit`, `_file_operands`,
`_codex_item_call`, `stamp`):

- `T` = `test_codex_read_is_credited_only_for_one_structurally_single_command` (parametrized, S1 to S5);
- `M` = `test_mcp_read_tool_credits_only_its_path_arguments` (S6);
- `K` = `test_stamp_names_a_file_under_the_real_root_when_the_root_is_given_through_a_symlink` (S7).

Declared guarded-element set (from the order): S1 to S7, one neutralization and one red each.
Every neutralization is a targeted Edit undone by the inverse Edit. Every red ran the detector
unedited, by exact node id, under `scripts/pinned-python -B -m pytest <node id> -q`; every green is the
same node id after the inverse Edit. Captures are the tail of the pytest output as seen (the
`UV_NATIVE_TLS` warning line is dropped, and for the `T` reds the echoed parametrize source block of the
failing test is elided where marked; the assertion, the `E` lines and the `FAILED` line are intact). Nothing
in them is a credential or a private URL; no redaction was needed. The restore receipt for each element is
the restored line quoted back from the file by `grep -n` after the inverse Edit. Final state of the two
changed source paths after the last restore: `git status --porcelain -- plugins/` printed
` M plugins/superheroes/lib/calibration_read.py` and ` M plugins/superheroes/lib/tests/test_calibration_read.py`
(the record files are new or edited by this order too).

Disclosed handling: S2, S3 and S5 are neutralized by a different line than the order's wording suggests,
because the obvious one-token neutralization does not turn the named case red. Removing `|` from
`_OPERATOR_CHARS` leaves `cat <core> | wc -l` unknown (the `-l` operand fails `cat`'s no-option spec), so S2
instead truncates the token list at the first `|`. S3 truncates it at the first token starting with `>` or
`<`. S5 widens the whole wrapper test (any single option word before the inner text), since
`bash -n -c '...'` has two option words and the exact-length test already refuses it.

## S1: single command

- Guarded element: `_simple_command`, `joined = tokens[:1] == ["cd"] and len(tokens) > 3 and tokens[2] in ("&&", ";")`.
  Axis: only `cd D` may precede a `;` or `&&` joiner; any other first command followed by one is not a single command.
- Neutralization: that line became `joined = len(tokens) > 3 and tokens[2] in ("&&", ";")` (any two-token
  first command may be joined).
- Detector node: `T[exit 0; cat <core>-unknown]`.
- Raw red (the echoed parametrize source block elided):

```
>       assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] == grade
E       AssertionError: assert 'read' == 'unknown'
E         
E         - unknown
E         + read

/home/user/sh-2311/plugins/superheroes/lib/tests/test_calibration_read.py:349: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_calibration_read.py::test_codex_read_is_credited_only_for_one_structurally_single_command[exit 0; cat <core>-unknown]
1 failed in 0.27s
```

- Restore: inverse Edit. Restore receipt (grep -n after): `433:    joined = tokens[:1] == ["cd"] and len(tokens) > 3 and tokens[2] in ("&&", ";")`
- Raw green:

```
.                                                                        [100%]
1 passed in 0.89s
```

## S2: no pipe

- Guarded element: `_simple_command`, the operator check `any(t and all(ch in _OPERATOR_CHARS for ch in t) for t in head + rest)`
  with `|` in `_OPERATOR_CHARS`. Axis: a pipe sends the output to another command, not to the reviewer.
- Neutralization: one line added after the `except ValueError: return None` of the lexer loop,
  `tokens = tokens[:tokens.index("|")] if "|" in tokens else tokens` (the text ends at the first pipe).
- Detector node: `T[cat <core> | wc -l-unknown]`.
- Raw red (the echoed parametrize source block elided):

```
>       assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] == grade
E       AssertionError: assert 'read' == 'unknown'
E         
E         - unknown
E         + read

/home/user/sh-2311/plugins/superheroes/lib/tests/test_calibration_read.py:349: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_calibration_read.py::test_codex_read_is_credited_only_for_one_structurally_single_command[cat <core> | wc -l-unknown]
1 failed in 0.53s
```

- Restore: inverse Edit (the added line removed). Restore receipt (grep -n after for `index("|")`): no match; the
  lines around the lexer loop read `except ValueError:` / `return None` / `if unwrap and len(tokens) == 3 ...`.
- Raw green:

```
.                                                                        [100%]
1 passed in 0.22s
```

## S3: no redirection or here-document

- Guarded element: the same operator check, with `<` and `>` in `_OPERATOR_CHARS`. Axis: a redirection sends
  the output to a file or reads input from elsewhere, not to the reviewer.
- Neutralization: one line added after the lexer loop,
  `tokens = tokens[:next((i for i, t in enumerate(tokens) if t.startswith((">", "<"))), len(tokens))]`
  (the text ends at the first redirection token).
- Detector node: `T[cat <core> > /dev/null-unknown]`.
- Raw red (the echoed parametrize source block elided):

```
>       assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] == grade
E       AssertionError: assert 'read' == 'unknown'
E         
E         - unknown
E         + read

/home/user/sh-2311/plugins/superheroes/lib/tests/test_calibration_read.py:349: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_calibration_read.py::test_codex_read_is_credited_only_for_one_structurally_single_command[cat <core> > /dev/null-unknown]
1 failed in 0.35s
```

- Restore: inverse Edit (the added line removed). Restore receipt (grep -n after for `startswith((">"`): no
  match (grep exit 1).
- Raw green:

```
.                                                                        [100%]
1 passed in 0.26s
```

## S4: positive count

- Guarded element: `_file_operands`, `if program in ("head", "tail", "sed") and any(int(n) < 1 for s in flags + values for n in re.findall(r"\d+", s)):`.
  Axis: a count or line number of 0 shows no content.
- Neutralization: `int(n) < 1` became `int(n) < 0` (0 passes).
- Detector node: `T[head -n 0 <core>-unknown]`.
- Raw red (the echoed parametrize source block elided):

```
>       assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] == grade
E       AssertionError: assert 'read' == 'unknown'
E         
E         - unknown
E         + read

/home/user/sh-2311/plugins/superheroes/lib/tests/test_calibration_read.py:349: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_calibration_read.py::test_codex_read_is_credited_only_for_one_structurally_single_command[head -n 0 <core>-unknown]
1 failed in 0.28s
```

- Restore: inverse Edit. Restore receipt (grep -n after): `395:    if program in ("head", "tail", "sed") and any(int(n) < 1 for s in flags + values for n in re.findall(r"\d+", s)):`
- Raw green:

```
.                                                                        [100%]
1 passed in 0.26s
```

## S5: wrapper option word

- Guarded element: `_simple_command`, `if unwrap and len(tokens) == 3 and tokens[1] in ("-c", "-lc") and _program(tokens[0]) in _SHELL_PROGRAMS:`.
  Axis: a shell wrapper is unwrapped only with exactly one option word, `-c` or `-lc` (`-n` runs nothing).
- Neutralization: the two lines
  `if unwrap and len(tokens) == 3 and tokens[1] in ("-c", "-lc") and ...:` / `return _simple_command(tokens[2], False)`
  became `if unwrap and len(tokens) > 2 and tokens[-2].startswith("-") and ...:` / `return _simple_command(tokens[-1], False)`
  (any option word before the inner text).
- Detector node: `T[bash -n -c 'cat <core>'-unknown]`.
- Raw red (the echoed parametrize source block elided):

```
>       assert _reads(CR.read_states("codex", stdout, calib.stamp))["core"] == grade
E       AssertionError: assert 'read' == 'unknown'
E         
E         - unknown
E         + read

/home/user/sh-2311/plugins/superheroes/lib/tests/test_calibration_read.py:349: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_calibration_read.py::test_codex_read_is_credited_only_for_one_structurally_single_command[bash -n -c 'cat <core>'-unknown]
1 failed in 0.26s
```

- Restore: inverse Edit. Restore receipt (grep -n after): `431:    if unwrap and len(tokens) == 3 and tokens[1] in ("-c", "-lc") and _program(tokens[0]) in _SHELL_PROGRAMS:`
- Raw green:

```
.                                                                        [100%]
1 passed in 0.27s
```

## S6: MCP path argument

- Guarded element: `_codex_item_call`, the `mcp_tool_call` branch (`paths` taken only from the `path` and `paths`
  arguments of a `_READ_FILE_TOOLS` tool). Axis: only a read tool's path arguments credit a read; any other
  argument value merely names the file.
- Neutralization: `return _call(outcome, paths=paths, named=values)` became
  `return _call(outcome, paths=paths + (values if item.get("tool") in _READ_FILE_TOOLS else []), named=values)`
  (every argument value of a read tool credits a read again).
- Detector node: `M` (the `note` case is its second assertion).
- Raw red:

```
        assert _reads(CR.read_states("codex", mcp("read_file", {"path": calib.core}), calib.stamp))["core"] == "read"
        other = {"path": "/tmp/notes.txt", "note": calib.core}
>       assert _reads(CR.read_states("codex", mcp("read_file", other), calib.stamp))["core"] == "unknown"
E       AssertionError: assert 'read' == 'unknown'
E         
E         - unknown
E         + read

/home/user/sh-2311/plugins/superheroes/lib/tests/test_calibration_read.py:209: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_calibration_read.py::test_mcp_read_tool_credits_only_its_path_arguments
1 failed in 0.25s
```

- Restore: inverse Edit. Restore receipt (grep -n after): `199:        return _call(outcome, paths=paths, named=values)`
- Raw green:

```
.                                                                        [100%]
1 passed in 0.39s
```

## S7: stamp real root

- Guarded element: `stamp`, `named = next((s for s in spellings if s in order_text), None)` over the given
  path, the path with the root replaced by `os.path.realpath(repo_root)`, and (core, review-crew) the file's own
  realpath. Axis: a file is named by the order under any spelling of its root, so a symlinked root keeps it.
- Neutralization: that line became `named = path if path in order_text else None` (only the given root matches).
- Detector node: `K`.
- Raw red:

```
calib = <test_calibration_read.Calib object at 0x7f5dcffb2150>
tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-31/test_stamp_names_a_file_under_0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f5dce9b8350>

    def test_stamp_names_a_file_under_the_real_root_when_the_root_is_given_through_a_symlink(calib, tmp_path, monkeypatch):
        link = str(tmp_path / "root-link")
        os.symlink(calib.root, link)
        # the order names CLAUDE.md by its real path; the root arrives through the symlink
        stamped = CR.stamp(link, "Read %s only.\n" % calib.claude)
>       assert [(e["label"], e["path"], e["sha256"]) for e in stamped] == [
            ("CLAUDE.md", calib.claude, _sha(calib.bytes[calib.claude]))]
E       AssertionError: assert [] == [('CLAUDE.md'...2abe48ecaf8')]
E         
E         Right contains one more item: ('CLAUDE.md', '/tmp/claude-0/pytest-of-root/pytest-31/test_stamp_names_a_file_under_0/repo/CLAUDE.md', 'a01704753f0da6437f796bd4f649af49d231d2dd05fb6e0f5019c2abe48ecaf8')
E         Use -v to get more diff

/home/user/sh-2311/plugins/superheroes/lib/tests/test_calibration_read.py:501: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_calibration_read.py::test_stamp_names_a_file_under_the_real_root_when_the_root_is_given_through_a_symlink
1 failed in 0.33s
```

- Restore: inverse Edit. Restore receipt (grep -n after): `117:            named = next((s for s in spellings if s in order_text), None)`
- Raw green:

```
.                                                                        [100%]
1 passed in 0.31s
```
