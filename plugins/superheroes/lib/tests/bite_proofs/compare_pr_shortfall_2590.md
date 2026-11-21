# Bite-proof: the bullet-shortfall guard in `compare_pr` (issue 2590, PR 2599, work order F)

Detector changed: `plugins/superheroes/lib/transition_notes.py` `compare_pr`, the shortfall branch,
now `if removed and delta < removed_bullets:` (axis line in the code above it). Tests live in
`plugins/superheroes/lib/tests/test_transition_notes.py` (`P` below). Every run used
`scripts/pinned-python -B -X pycache_prefix=/tmp/wo-f-pyc -m pytest <exact node id> -q`. The
`UV_NATIVE_TLS` deprecation warning each run prints is omitted from the captures. No secrets, tokens or
private URLs appear in any capture, so nothing is redacted. Each capture is well under the 32 KiB ceiling.

Declared guarded-element set: (1) the `removed and` guard; (2) the shortfall refusal on an assembly.

## Element 1: the `removed and` guard

**Axis:** a bullet shortfall is refused only on a pull request that removes a note file.

**Neutralization:** the target line occurred once (grep count 1). Removed ` removed and`, giving the
old line `    if delta < removed_bullets:`.

**Raw red** (`P::test_compare_bullet_deletion_alone_passes`, exit 1):

```text
F                                                                        [100%]
=================================== FAILURES ===================================
__________________ test_compare_bullet_deletion_alone_passes ___________________

    def test_compare_bullet_deletion_alone_passes():
        extra = "- **After switching.** Second old step.\n"
        old = "- **After switching.** Old step.\n"
        base = TRANSITION.replace(old, old + extra)
        head = base.replace(extra, "")
        assert tn.structure(head)["bullets"] == tn.structure(base)["bullets"] - 1
        assert tn.structure(base)["bullets"] >= 1
>       assert tn.compare_pr(base, head, [], []) == []
E       AssertionError: assert [{'file': 'TR...tfall of 1.'}] == []
E
E         Left contains one more item: {'file': 'TRANSITION.md', 'token': 'note-removed-unassembled', 'detail': 'Removed notes held 0 bullet(s) but TRANSITION.md gained -1, a shortfall of 1.'}
E         Use -v to get more diff

/home/user/wt-2590/plugins/superheroes/lib/tests/test_transition_notes.py:632: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_transition_notes.py::test_compare_bullet_deletion_alone_passes
1 failed in 0.42s
```

The red is on the claimed axis: the bullet-count preconditions (head one less than base) passed, and the
final assertion failed on a `note-removed-unassembled` shortfall problem with no note removed.

**Restore:** the inverse edit, putting ` removed and` back.

**Restore receipt** (grep over the file after the edit, lines 360 to 361):

```text
360:    # axis: a bullet shortfall is refused only on a pull request that removes a note file
361:    if removed and delta < removed_bullets:
```

**Raw green** (same node id):

```text
.                                                                        [100%]
1 passed in 1.97s
```

## Element 2: the shortfall refusal on an assembly

**Axis:** the same: a pull request that removes a note file and drops its bullet is still refused.

**Neutralization:** the target line occurred once (grep count 1). Replaced it with
`    if False and removed and delta < removed_bullets:`.

**Raw red** (`P::test_compare_assembly_dropping_a_bullet_is_refused`, exit 1):

```text
F                                                                        [100%]
=================================== FAILURES ===================================
______________ test_compare_assembly_dropping_a_bullet_is_refused ______________

    def test_compare_assembly_dropping_a_bullet_is_refused():
        head = tn.render(TRANSITION, NOTES, "1.1.0")
        assert STEP_A in head
        short = head.replace(STEP_A, "")
        problems = tn.compare_pr(TRANSITION, short, NOTES, [])
>       assert tokens(problems) == ["note-removed-unassembled"]
E       AssertionError: assert [] == ['note-removed-unassembled']
E
E         Right contains one more item: 'note-removed-unassembled'
E         Use -v to get more diff

/home/user/wt-2590/plugins/superheroes/lib/tests/test_transition_notes.py:621: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_transition_notes.py::test_compare_assembly_dropping_a_bullet_is_refused
1 failed in 0.38s
```

The red is on the claimed axis: the expected refusal token `note-removed-unassembled` was missing.

**Restore:** the inverse edit, `if False and removed and delta < removed_bullets:` back to
`if removed and delta < removed_bullets:`.

**Restore receipt** (grep for either form over the file after the edit; only the restored form remains):

```text
361:    if removed and delta < removed_bullets:
```

**Raw green** (same node id):

```text
.                                                                        [100%]
1 passed in 0.26s
```

## Note on the replaced assertion

`test_compare_assembly_dropping_a_bullet_is_refused` now asserts `problems[0]["file"] == "TRANSITION.md"`
in place of the former `"shortfall" in problems[0]["detail"]`, as the work order specified.
