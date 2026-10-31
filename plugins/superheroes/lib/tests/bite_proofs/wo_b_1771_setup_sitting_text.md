# #1771 WO-B bite-proof: the setup sitting's skill text

> Note (2026-10-31, #2296): owner-machine paths and the name of a consuming project in this record were replaced with neutral placeholders after capture; nothing else changed.

Bite-proof record for section 6 of `plugins/superheroes/skills/configure/reference/set-up.md`, detectors in `plugins/superheroes/lib/tests/test_cloud_setup_sitting_text.py` (`T`).

**Status.** The implementer ran every proof (D1 to D3): each neutralization is a targeted Edit to `set-up.md`, the red is the single named test function run alone, the restore is the inverse Edit, and the green is the same function. Reds and greens below are the pytest output of each run. The worktree path is as printed. No fixture holds a real secret, so nothing is redacted.

- **Run command.** `scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest "<T>::<node>" -q`.
- **Restore receipt, every element.** The restored line is quoted back, and a final search of `set-up.md` found none of the neutralizations present.
- **Pinned condition.** `T` reads the shipped files from the plugin root and holds no clock, environment or network input, so nothing is unobservable under the pin.
- **One ordering note, disclosed.** The D1 green run and the D2 neutralization Edit were issued in the same step. The D1 restore Edit had already been applied and the D1 test reads no line the D2 Edit touches, so the D1 green stands.

## Declared guarded-element set

D1 section 6 holds no instruction to ask for a typed, copied or pasted id; D2 the check session starts naming the picked id; D3 the pick is read after the owner makes it, before the pass and the check.

The census's other tests (`test_section_six_exists`, the two routing tests, the sign-in-before-pass ordering assertion, and the `judge` and `make` lines of `test_every_check_command_names_the_picked_id`) have no neutralization of their own here and are unproven by a run in this record. D2 is the representative for the three commands that must name the id (`start`, `judge`, `make`), which share one assertion.

## Per-element receipts

### D1: no instruction to ask for a typed or pasted id. Axis: absence of a forbidden instruction

- **Neutralization applied.** The sentence `If the pick cannot be read, ask the owner to paste the environment's id.` appended to the end of step 3's paragraph that begins `On \`picked\``.
- **Node.** `T::test_section_never_asks_for_a_typed_or_pasted_id`
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_______________ test_section_never_asks_for_a_typed_or_pasted_id _______________

    def test_section_never_asks_for_a_typed_or_pasted_id():
        section = _section_six()
        assert section, "section 6 of set-up.md was not found"
        ask = re.compile(r"\b(type|typed|paste|pasted|copy|copied)\b", re.IGNORECASE)
        ident = re.compile(r"\bids?\b", re.IGNORECASE)
        for sentence in _sentences(section):
            if ask.search(sentence) and ident.search(sentence) and "never" not in sentence.lower():
>               raise AssertionError("sentence asks for a typed, copied or pasted id without "
                                     "'never': %r" % sentence.strip())
E               AssertionError: sentence asks for a typed, copied or pasted id without 'never': "If the pick cannot be read, ask the owner to paste the environment's id"

/path/to/home/.superheroes-worktrees/superheroes/issue-1771-9596bd8e72803b62/plugins/superheroes/lib/tests/test_cloud_setup_sitting_text.py:63: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_setup_sitting_text.py::test_section_never_asks_for_a_typed_or_pasted_id
1 failed in 0.15s
```

- **Restore.** The inverse Edit; quoted from `set-up.md`, the last line of step 3: `   the pick is done: another account's pick in between would be read as this one.`
- **Green.**

```
.                                                                        [100%]
1 passed in 1.49s
```

### D2: the check starts naming the id. Axis: command content

- **Neutralization applied.** ` --environment <id>` deleted from the `cloud_check.py" start` command line.
- **Node.** `T::test_every_check_command_names_the_picked_id`
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_________________ test_every_check_command_names_the_picked_id _________________

    def test_every_check_command_names_the_picked_id():
        section = _section_six()
        assert section, "section 6 of set-up.md was not found"
        needles = ('cloud_check.py" start', 'cloud_check.py" judge', 'cloud_pass.py" make')
        seen = {needle: 0 for needle in needles}
        for line in section:
            for needle in needles:
                if needle in line:
                    seen[needle] += 1
>                   assert "--environment <id>" in line, (
                        "command line does not name '--environment <id>': %r" % line)
E                   AssertionError: command line does not name '--environment <id>': '   python3 -B "$ROOT_DIR/lib/cloud_check.py" start --cwd . [--issue <n>]'
E                   assert '--environment <id>' in '   python3 -B "$ROOT_DIR/lib/cloud_check.py" start --cwd . [--issue <n>]'

/path/to/home/.superheroes-worktrees/superheroes/issue-1771-9596bd8e72803b62/plugins/superheroes/lib/tests/test_cloud_setup_sitting_text.py:76: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_setup_sitting_text.py::test_every_check_command_names_the_picked_id
1 failed in 0.20s
```

- **Restore.** The inverse Edit; quoted from `set-up.md:469`: `   python3 -B "$ROOT_DIR/lib/cloud_check.py" start --cwd . --environment <id> [--issue <n>]`.
- **Green.**

```
.                                                                        [100%]
1 passed in 0.16s
```

### D3: the pick is read after the owner makes it. Axis: ordering and presence of the after-read

- **Neutralization applied.** The step-3 command's verb `pick` changed to `snapshot`, so the line reads `cloud_environment.py" snapshot --cwd . --before` and no after-read line exists.
- **Node.** `T::test_the_pick_is_read_before_and_after_and_before_the_check`
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_the_pick_is_read_before_and_after_and_before_the_check __________

    def test_the_pick_is_read_before_and_after_and_before_the_check():
        section = _section_six()
        assert section, "section 6 of set-up.md was not found"
        order = ['cloud_environment.py" snapshot', 'cloud_check.py" setup-message',
                 'cloud_environment.py" pick --cwd . --before', 'cloud_pass.py" make',
                 'cloud_check.py" start']
        found = [(needle, _first(section, needle)) for needle in order]
        for needle, index in found:
>           assert index is not None, "section 6 has no line containing %r" % needle
E           AssertionError: section 6 has no line containing 'cloud_environment.py" pick --cwd . --before'
E           assert None is not None

/path/to/home/.superheroes-worktrees/superheroes/issue-1771-9596bd8e72803b62/plugins/superheroes/lib/tests/test_cloud_setup_sitting_text.py:90: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_setup_sitting_text.py::test_the_pick_is_read_before_and_after_and_before_the_check
1 failed in 0.18s
```

- **Restore.** The inverse Edit; quoted from `set-up.md:440`: `   python3 -B "$ROOT_DIR/lib/cloud_environment.py" pick --cwd . --before <the value step 1 kept>`.
- **Green.**

```
.                                                                        [100%]
1 passed in 0.15s
```

## Final search

One search of `set-up.md` for `paste the environment's id`, `snapshot --cwd . --before` and `start --cwd . [--issue` found no match: no neutralization remains. A second search found the two restored lines, `set-up.md:440` and `set-up.md:469`.

# #1771 WO-D bite-proof: clause-level "never" and the exact recovery line

WO-D changes two detectors in `T`: `test_section_never_asks_for_a_typed_or_pasted_id` now checks each clause (a sentence split on `, and|but|or`, `;` and ` — `) and fails any clause that matches both the ask and id patterns without its own "never"; `test_the_pick_is_read_before_and_after_and_before_the_check` now asserts the exact recovery line, after the first `judge` line, in place of the loose `retry` list.

**Status.** The implementer ran both proofs (D6 and D7) with the same method and run command as D1 to D3 above: the neutralization is a targeted Edit to `set-up.md`, the red is the single named test function run alone, the restore is the inverse Edit, and the green is the same function. Before the probes, the whole file was run once on the unchanged section and passed (7 passed in 0.56s), so no existing section sentence fails under clause splitting. `set-up.md` is not changed by this order.

## Declared guarded-element set (WO-D)

D6 an unrelated "never" in another clause no longer lets a forbidden clause through; D7 step 8's recovery command must carry `--confirmed <the environment now in use>`, and only that line satisfies the assertion.

### D6: the unrelated-never bypass is caught. Axis: absence of a forbidden instruction, clause level

- **Neutralization applied.** The sentence `Never run it for them, and ask the owner to paste the environment's id.` appended to the end of step 5's paragraph that begins `Tell the owner to run it`.
- **Node.** `T::test_section_never_asks_for_a_typed_or_pasted_id`
- **Pre-WO-D detector, reasoned from its code (not a run).** The old check skipped any sentence for which `"never" in sentence.lower()` held. The appended sentence begins with "Never", so the old check would have passed it, although its second clause asks for a pasted id.
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_______________ test_section_never_asks_for_a_typed_or_pasted_id _______________

    def test_section_never_asks_for_a_typed_or_pasted_id():
        section = _section_six()
        assert section, "section 6 of set-up.md was not found"
        ask = re.compile(r"\b(type|typed|paste|pasted|copy|copied)\b", re.IGNORECASE)
        ident = re.compile(r"\bids?\b", re.IGNORECASE)
        split = re.compile(r",\s*(?:and|but|or)\s+|;\s*|\s+—\s+")
        for sentence in _sentences(section):
            for clause in split.split(sentence):
                if ask.search(clause) and ident.search(clause) and "never" not in clause.lower():
>                   raise AssertionError("clause asks for a typed, copied or pasted id without "
                                         "'never': %r" % clause.strip())
E                   AssertionError: clause asks for a typed, copied or pasted id without 'never': "ask the owner to paste the environment's id"

/path/to/home/.superheroes-worktrees/superheroes/issue-1771-9596bd8e72803b62/plugins/superheroes/lib/tests/test_cloud_setup_sitting_text.py:65: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_setup_sitting_text.py::test_section_never_asks_for_a_typed_or_pasted_id
1 failed in 1.04s
```

- **Restore.** The inverse Edit; quoted from `set-up.md:471`: `   the plugin root's absolute path written out in the quoted script path.`
- **Green.**

```
.                                                                        [100%]
1 passed in 0.68s
```

### D7: the recovery command must carry `--confirmed`. Axis: command content

- **Neutralization applied.** ` --confirmed <the environment now in use>` deleted from step 8's command line, which left `... pick --cwd . --before <the snapshot value>`. Step 3's confirm-by-name line, which carries `--confirmed`, was untouched.
- **Node.** `T::test_the_pick_is_read_before_and_after_and_before_the_check`
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_the_pick_is_read_before_and_after_and_before_the_check __________

    def test_the_pick_is_read_before_and_after_and_before_the_check():
        section = _section_six()
        assert section, "section 6 of set-up.md was not found"
        order = ['cloud_environment.py" snapshot', 'cloud_check.py" setup-message',
                 'cloud_environment.py" pick --cwd . --before', 'cloud_pass.py" make',
                 'cloud_check.py" start']
        found = [(needle, _first(section, needle)) for needle in order]
        for needle, index in found:
            assert index is not None, "section 6 has no line containing %r" % needle
        for (earlier, i), (later, j) in zip(found, found[1:]):
            assert i < j, "line %r (%d) does not come before line %r (%d)" % (earlier, i, later, j)
        recovery_needle = ('cloud_environment.py" pick --cwd . --before <the snapshot value> '
                           '--confirmed <the environment now in use>')
        recovery = _first(section, recovery_needle)
>       assert recovery is not None, "section 6 has no line containing %r" % recovery_needle
E       AssertionError: section 6 has no line containing 'cloud_environment.py" pick --cwd . --before <the snapshot value> --confirmed <the environment now in use>'
E       assert None is not None

/path/to/home/.superheroes-worktrees/superheroes/issue-1771-9596bd8e72803b62/plugins/superheroes/lib/tests/test_cloud_setup_sitting_text.py:98: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_setup_sitting_text.py::test_the_pick_is_read_before_and_after_and_before_the_check
1 failed in 0.68s
```

- **Restore.** The inverse Edit; quoted from `set-up.md:511`: `   python3 -B "$ROOT_DIR/lib/cloud_environment.py" pick --cwd . --before <the snapshot value> --confirmed <the environment now in use>`.
- **Green.**

```
.                                                                        [100%]
1 passed in 0.87s
```

## Final search (WO-D)

A search of `set-up.md` for `paste the environment's id` found no match, and found `set-up.md:471` and `set-up.md:511` in their restored form.

## WO-E: the plain after-read in step 3 is guarded on its own

Guarded elements, declared up front: D3b and D3c. Both are proofs of `T::test_the_pick_is_read_before_and_after_and_before_the_check`. Each neutralization is a targeted Edit to `set-up.md`, anchored on the plain line with the line after it (the closing fence), because the same `pick --cwd . --before <the value step 1 kept>` text also begins the confirm-by-name line. Each is reverted by the inverse Edit; the committed `set-up.md` is unchanged.

### D3b: the plain after-read is guarded by itself. Axis: command content

- **Neutralization applied.** Step 3's plain after-read verb changed from `pick` to `snapshot`: `cloud_environment.py" snapshot --cwd . --before <the value step 1 kept>`. The confirm-by-name line was untouched. Before this order, the old needle `cloud_environment.py" pick --cwd . --before` still matched the confirm-by-name line, so the test stayed green on this change (`1 passed`, seen by the orchestrator on head `e4db0e4d`).
- **Node.** `T::test_the_pick_is_read_before_and_after_and_before_the_check`
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_the_pick_is_read_before_and_after_and_before_the_check __________

    def test_the_pick_is_read_before_and_after_and_before_the_check():
        section = _section_six()
        assert section, "section 6 of set-up.md was not found"
        plain_end = 'pick --cwd . --before <the value step 1 kept>'
        plain_label = 'a plain after-read line ending %r' % plain_end
        plain = next((i for i, line in enumerate(section) if line.strip().endswith(plain_end)), None)
        found = [('cloud_environment.py" snapshot', _first(section, 'cloud_environment.py" snapshot')),
                 ('cloud_check.py" setup-message', _first(section, 'cloud_check.py" setup-message')),
                 (plain_label, plain),
                 ('cloud_pass.py" make', _first(section, 'cloud_pass.py" make')),
                 ('cloud_check.py" start', _first(section, 'cloud_check.py" start'))]
        for needle, index in found:
>           assert index is not None, "section 6 has no line containing %r" % needle
E           AssertionError: section 6 has no line containing "a plain after-read line ending 'pick --cwd . --before <the value step 1 kept>'"
E           assert None is not None

/path/to/home/.superheroes-worktrees/superheroes/issue-1771-9596bd8e72803b62/plugins/superheroes/lib/tests/test_cloud_setup_sitting_text.py:96: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_setup_sitting_text.py::test_the_pick_is_read_before_and_after_and_before_the_check
1 failed in 0.21s
```

- **Restore.** The inverse Edit; quoted from `set-up.md:442`: `   python3 -B "$ROOT_DIR/lib/cloud_environment.py" pick --cwd . --before <the value step 1 kept>`.
- **Green.**

```
.                                                                        [100%]
1 passed in 3.67s
```

### D3c: the plain after-read comes before the confirm-by-name read. Axis: command content

- **Neutralization applied.** ` --confirmed <the value step 1 kept>` appended to step 3's plain after-read line. That leaves two confirm-by-name lines and no plain read.
- **Node.** `T::test_the_pick_is_read_before_and_after_and_before_the_check`
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_the_pick_is_read_before_and_after_and_before_the_check __________

    def test_the_pick_is_read_before_and_after_and_before_the_check():
        section = _section_six()
        assert section, "section 6 of set-up.md was not found"
        plain_end = 'pick --cwd . --before <the value step 1 kept>'
        plain_label = 'a plain after-read line ending %r' % plain_end
        plain = next((i for i, line in enumerate(section) if line.strip().endswith(plain_end)), None)
        found = [('cloud_environment.py" snapshot', _first(section, 'cloud_environment.py" snapshot')),
                 ('cloud_check.py" setup-message', _first(section, 'cloud_check.py" setup-message')),
                 (plain_label, plain),
                 ('cloud_pass.py" make', _first(section, 'cloud_pass.py" make')),
                 ('cloud_check.py" start', _first(section, 'cloud_check.py" start'))]
        for needle, index in found:
>           assert index is not None, "section 6 has no line containing %r" % needle
E           AssertionError: section 6 has no line containing "a plain after-read line ending 'pick --cwd . --before <the value step 1 kept>'"
E           assert None is not None

/path/to/home/.superheroes-worktrees/superheroes/issue-1771-9596bd8e72803b62/plugins/superheroes/lib/tests/test_cloud_setup_sitting_text.py:96: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_setup_sitting_text.py::test_the_pick_is_read_before_and_after_and_before_the_check
1 failed in 3.32s
```

- **Restore.** The inverse Edit; quoted from `set-up.md:442`: `   python3 -B "$ROOT_DIR/lib/cloud_environment.py" pick --cwd . --before <the value step 1 kept>`, with `set-up.md:452` still `   python3 -B "$ROOT_DIR/lib/cloud_environment.py" pick --cwd . --before <the value step 1 kept> --confirmed <the value step 1 kept>`.
- **Green.**

```
.                                                                        [100%]
1 passed in 0.09s
```

## Fail-closed edges (WO-E)

1. The plain after-read is missing (renamed, deleted, or given `--confirmed`): the plain index is `None`, and the "has no line containing" assertion fails. D3b and D3c are the proofs of this edge.
2. The plain after-read comes after the pass command: the pairwise order assertion fails (`plain < make`). Reasoned from the code, not run.
3. The confirm-by-name line comes before the plain after-read: `plain < confirm` fails. Reasoned from the code, not run.

## C8a WO3 (C4b FU2): the plain after-read must name `cloud_environment.py`

The plain after-read match in `T::test_the_pick_is_read_before_and_after_and_before_the_check` now requires the line to contain `cloud_environment.py" pick` as well as end with `pick --cwd . --before <the value step 1 kept>`. Before, it matched on the line ending alone, so a plain after-read that ran another script passed. This is an authorized test strengthening. Same method and run command as above; the pytest captures omit the one `uv` deprecation warning line printed before pytest starts.

**Declared guarded element:** C4bFU2-a.

### C4bFU2-a: the plain after-read names `cloud_environment.py`. Axis: command content (the script the line runs)

- **Neutralization applied.** Whole of `set-up.md:443`, through its line end (a prefix of it also starts line 453): `   python3 -B "$ROOT_DIR/lib/cloud_environment.py" pick --cwd . --before <the value step 1 kept>` had `cloud_environment.py` changed to `cloud_setup.py`.
- **Node.** `T::test_the_pick_is_read_before_and_after_and_before_the_check`
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_the_pick_is_read_before_and_after_and_before_the_check __________

    def test_the_pick_is_read_before_and_after_and_before_the_check():
        section = _section_six()
        assert section, "section 6 of set-up.md was not found"
        # axis: the plain after-read line must name cloud_environment.py, not only end like the read — see bite-proof record wo_b_1771_setup_sitting_text.md
        plain_end = 'pick --cwd . --before <the value step 1 kept>'
        plain_name = 'cloud_environment.py" pick'
        plain_label = 'a plain after-read line naming %r and ending %r' % (plain_name, plain_end)
        plain = next((i for i, line in enumerate(section)
                      if plain_name in line and line.strip().endswith(plain_end)), None)
        found = [('cloud_environment.py" snapshot', _first(section, 'cloud_environment.py" snapshot')),
                 ('cloud_check.py" setup-message', _first(section, 'cloud_check.py" setup-message')),
                 (plain_label, plain),
                 ('cloud_pass.py" make', _first(section, 'cloud_pass.py" make')),
                 ('cloud_check.py" start', _first(section, 'cloud_check.py" start'))]
        for needle, index in found:
>           assert index is not None, "section 6 has no line containing %r" % needle
E           AssertionError: section 6 has no line containing 'a plain after-read line naming \'cloud_environment.py" pick\' and ending \'pick --cwd . --before <the value step 1 kept>\''
E           assert None is not None

/home/user/c8a-wo3/plugins/superheroes/lib/tests/test_cloud_setup_sitting_text.py:99: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_setup_sitting_text.py::test_the_pick_is_read_before_and_after_and_before_the_check
1 failed in 0.16s
EXIT=1
```

- **Restore.** The inverse Edit, `cloud_setup.py` back to `cloud_environment.py` on the same line.
- **Restore receipt.** `sed -n 443p set-up.md` printed `   python3 -B "$ROOT_DIR/lib/cloud_environment.py" pick --cwd . --before <the value step 1 kept>`.
- **Green.**

```
.                                                                        [100%]
1 passed in 0.12s
EXIT=0
```
