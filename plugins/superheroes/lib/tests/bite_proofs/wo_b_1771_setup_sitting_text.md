# #1771 WO-B bite-proof: the setup sitting's skill text

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

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1771-9596bd8e72803b62/plugins/superheroes/lib/tests/test_cloud_setup_sitting_text.py:63: AssertionError
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

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1771-9596bd8e72803b62/plugins/superheroes/lib/tests/test_cloud_setup_sitting_text.py:76: AssertionError
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

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1771-9596bd8e72803b62/plugins/superheroes/lib/tests/test_cloud_setup_sitting_text.py:90: AssertionError
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
