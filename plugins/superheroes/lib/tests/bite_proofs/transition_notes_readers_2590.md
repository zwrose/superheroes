# Bite-proof record: the census rule for transition_notes readers (#2590)

The detector added is the census rule in `plugins/superheroes/lib/tests/test_whole_tree_text_set.py`: a test file that imports
`transition_notes` is a candidate, so it must be listed in `whole-tree-text-tests.txt`. Three guarded elements were declared.
Each entry shows a targeted, reversible edit, the detector's own red output, the inverse-edit restore, the restored lines quoted back, and
the green output. No secret, token, private URL or personal detail appears in the captures; the only paths are temporary pytest directories under `/tmp`.
Elisions are labelled where they occur (entries 1 and 3).

## 1. The import rule (`_reads_transition_notes`, called in `scan`)

**Axis:** a test file that imports `transition_notes` is a candidate even with no enumeration line and no Markdown filter.

**Neutralization:** in `test_whole_tree_text_set.py`, the one line `    return "transition_notes" in _imported_modules(tree)`
(inside `_reads_transition_notes`) became `    return False`. The edit tool refused to apply unless the old text occurred once.

**Detector run alone:** `scripts/pinned-python -B -X pycache_prefix=/tmp/wo-c-pyc -m pytest "plugins/superheroes/lib/tests/test_whole_tree_text_set.py::test_a_test_importing_transition_notes_is_a_candidate" -q -p no:xdist`

**Raw red (all three parametrized cases fail the same way; the first is shown whole, the other two differ only in the `statement` value):**

```
FFF                                                                      [100%]
=================================== FAILURES ===================================
_ test_a_test_importing_transition_notes_is_a_candidate[import transition_notes] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-59/test_a_test_importing_transiti0')
statement = 'import transition_notes'

    def test_a_test_importing_transition_notes_is_a_candidate(tmp_path, statement):
        files = {
            "test_reads_notes.py": "%s\n\ndef test_a():\n    assert True\n" % statement,
            "test_other_import.py": "import transition_notes_other\n\ndef test_b():\n    assert True\n",
            "test_names_it_only.py": "def test_c():\n    assert \"transition_notes\"\n",
        }
        test_files, candidates = _scan_synthetic(tmp_path, files)
        assert sorted(test_files) == ["test_names_it_only.py", "test_other_import.py", "test_reads_notes.py"]
>       assert candidates == {"test_reads_notes.py": ()}
E       AssertionError: assert {} == {'test_reads_notes.py': ()}
E         
E         Right contains 1 more item:
E         {'test_reads_notes.py': ()}

plugins/superheroes/lib/tests/test_whole_tree_text_set.py:678: AssertionError
=========================== short test summary info ============================
FAILED ...::test_a_test_importing_transition_notes_is_a_candidate[import transition_notes]
FAILED ...::test_a_test_importing_transition_notes_is_a_candidate[from transition_notes import transition_text]
FAILED ...::test_a_test_importing_transition_notes_is_a_candidate[import transition_notes as tn]
3 failed in 0.86s
```

(The first-case traceback above is the run's own output with the pytest decorator echo, the `Use -v to get more diff` line and the two sibling cases' repeated tracebacks left out; the result lines are verbatim.)

**Restore:** the inverse edit, `    return False` back to `    return "transition_notes" in _imported_modules(tree)`.

**Restore receipt (the restored lines quoted back):**

```
def _reads_transition_notes(tree):
    """(d) the file imports `transition_notes`, the module a reader calls to read TRANSITION.md's
    wording with the unassembled upgrade notes rendered in, so it reads plugin Markdown."""
    return "transition_notes" in _imported_modules(tree)
```

**Raw green:**

```
...                                                                      [100%]
3 passed in 0.28s
```

## 2. The argument-file completeness for `test_transition_notes.py`

**Axis:** every candidate is a member of `whole-tree-text-tests.txt` or exempt.

**Neutralization:** the one line `plugins/superheroes/lib/tests/test_transition_notes.py` was deleted from `whole-tree-text-tests.txt`
(the edit tool refused unless it occurred once).

**Detector run alone:** `scripts/pinned-python -B -X pycache_prefix=/tmp/wo-c-pyc -m pytest "plugins/superheroes/lib/tests/test_whole_tree_text_set.py::test_every_candidate_is_a_member_or_exempt" -q -p no:xdist`

**Raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
__________________ test_every_candidate_is_a_member_or_exempt __________________
plugins/superheroes/lib/tests/test_transition_notes.py reads plugin Markdown by pattern (enumeration lines: ['assert sorted(os.listdir(folder)) == ["README.md"]', 'assert sorted(os.listdir(root)) == ["TRANSITION.md", "transition-notes"]', 'assert sorted(os.listdir(root / tn.NOTES_DIRNAME)) == ["12.md", "3-two.md", "7-bad.md", "README.md"]', 'assert sorted(os.listdir(root / tn.NOTES_DIRNAME)) == ["12.md", "3-two.md", "README.md"]', 'assert sorted(os.listdir(root / tn.NOTES_DIRNAME)) == ["12.md", "3-two.md", "README.md"]', 'assert sorted(os.listdir(root / tn.NOTES_DIRNAME)) == ["README.md"]']) and is in neither the set nor EXEMPT: add it to plugins/superheroes/lib/tests/whole-tree-text-tests.txt, or, if it does not read plugin Markdown by pattern, add it to EXEMPT with a reason and its enumeration lines.
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_whole_tree_text_set.py::test_every_candidate_is_a_member_or_exempt
1 failed in 12.49s
```

**Disclosure:** `test_transition_notes.py` also qualifies under the file's older rules (it has enumeration lines and a literal containing `TRANSITION`), so this red does not
discriminate the new import rule from the older rules; element 1 is the proof for the import rule, and this element proves only the file's listing.

**Restore:** the inverse edit, re-inserting the line after `test_test_role_seat.py` (its sorted place).

**Restore receipt (the restored lines quoted back):**

```
plugins/superheroes/lib/tests/test_test_role_seat.py
plugins/superheroes/lib/tests/test_transition_notes.py
plugins/superheroes/lib/tests/test_vet_record_checks.py
```

**Raw green:**

```
.                                                                        [100%]
1 passed in 12.11s
```

## 3. The `md_readers` mapping in `test_cloud_cleanup_doctrine.py`

**Axis:** a note file under `transition-notes/` counts as `TRANSITION.md`, so the set of Markdown files naming `cloud_setup.py gardening` reads the same before and after assembly.

**Setup:** a temporary note file `plugins/superheroes/transition-notes/9999-bite-proof-temp.md` mentioning `` `cloud_setup.py gardening` `` was created with the file-write tool.

**Neutralization:** in `test_cloud_cleanup_doctrine.py`, the one line `        _TRANSITION if rel.split("/")[0] == transition_notes.NOTES_DIRNAME else rel`
became `        rel` (the edit tool refused unless the surrounding text occurred once).

**Detector run alone:** `scripts/pinned-python -B -X pycache_prefix=/tmp/wo-c-pyc -m pytest "plugins/superheroes/lib/tests/test_cloud_cleanup_doctrine.py::test_reviewer_pass_gardening_line_has_no_new_reader" -q -p no:xdist`

**Raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_reviewer_pass_gardening_line_has_no_new_reader ______________
...
>       assert md_readers == sorted([_OWNER_DECISIONS, _TRANSITION]), md_readers
E       AssertionError: ['TRANSITION.md', 'skills/showrunner/reference/owner-decisions.md', 'transition-notes/9999-bite-proof-temp.md']
E       assert ['TRANSITION....roof-temp.md'] == ['TRANSITION....decisions.md']
E         
E         Left contains one more item: 'transition-notes/9999-bite-proof-temp.md'
E         Use -v to get more diff

plugins/superheroes/lib/tests/test_cloud_cleanup_doctrine.py:179: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_cleanup_doctrine.py::test_reviewer_pass_gardening_line_has_no_new_reader
1 failed in 0.43s
```

(The `...` stands for the function body the run echoed: the `py_readers` loop and the `md_readers` expression, which are in the file.)

**Restore:** the inverse edit, `        rel` back to the mapping line.

**Restore receipt (the restored lines quoted back):**

```
    md_readers = sorted({
        _TRANSITION if rel.split("/")[0] == transition_notes.NOTES_DIRNAME else rel
        for rel, path in _shipped((".md",))
        if re.search(r"cloud_setup\.py gardening", _collapsed(path))
    })
```

**Raw green (mapping restored, the temporary note still in place):**

```
.                                                                        [100%]
1 passed in 0.56s
```

**Cleanup:** the temporary note was removed with one plain `rm` of that one path; the post-restore `git status --porcelain` lists only this order's deliverables
(plus the untracked environment dotfiles that were in the worktree before this work), with `plugins/superheroes/transition-notes/` untracked and holding `README.md` and `2590.md`.
