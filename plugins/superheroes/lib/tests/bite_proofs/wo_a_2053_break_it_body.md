# Work order A (#2053, layer 1 of #2060) bite-proof: a Python break-it test counts as kept by its body at any path

> Note (2026-10-31, #2296): owner-machine paths and the name of a consuming project in this record were replaced with neutral placeholders after capture; nothing else changed.

**Provenance:** claude / sonnet-5.5 (implementer, work order A3), maker family anthropic. Production under proof: `plugins/superheroes/lib/break_it_body.py` (`locate`, `_outside`), `plugins/superheroes/lib/break_it_body_py.py` (`parse`, `_normalise`), `plugins/superheroes/lib/break_it.py` (`check_kept`, `_selects_tests`, `_rewrite_command`). Tests: `plugins/superheroes/lib/tests/test_break_it_body_2053.py`.

Declared guarded-element set (from the order): **E1**, **E2**, **E3**, **E4a**, **E4b**, **E5**, **E6**, **E7**, **E8**, **E9**, **E10**, **E11**. Each was neutralized by one targeted edit (the Edit tool, exact-text match), only its proving nodes run by exact node id (never `-k`; a bare function id selects every parametrization of that function), the inverse edit applied, `git diff --stat` taken over the file (empty: the file equals the last commit), and the same ids run again. No `git checkout`, `git restore`, `git reset` or `git stash` was used.

## Guarded elements

| ID | Guarded element | Axis | Proving nodes (all in `test_break_it_body_2053.py`) |
|---|---|---|---|
| E1 | the ambiguity refusal, `break_it_body.py` `locate` (`if len(matches) > 1:`) | a second copy of the test reads `match-ambiguous`, never kept | `::test_two_matching_copies_are_ambiguous`, `::test_a_copy_beside_the_changed_original_is_ambiguous` |
| E2 | the unparseable refusal for a prefilter-passing candidate, `locate` (`unparseable = True` in the `except ValueError` branch) | a candidate that passes the prefilter and cannot be read leaves the search undecided (`body-unparseable`), even beside a match | `::test_prefilter_passing_unparseable_candidate_is_unresolved_beside_a_match`, `::test_prefilter_passing_unparseable_candidate_without_a_match_is_unresolved` |
| E3 | the import-pair presence check, `_outside` (`if not orig_pairs <= {...}`) | every import the original bound is bound the same way in the host (`binding-conflict`) | `::test_host_that_lacks_an_import_the_test_binds_is_a_binding_conflict` |
| E4a | the outside-window import rebinding check, `_outside` (`if pair[0] == "*" or pair[0] in names:`) | an import outside the window that rebinds a used name, or star-imports over it, is `binding-conflict` | `::test_host_that_binds_an_imported_name_another_way_is_a_binding_conflict`, `::test_host_star_import_is_a_binding_conflict` |
| E4b | the outside-window statement-binds check, `_outside` (`if rec["kind"] == "stmt" and rec["binds"] & names:`) | a statement outside the window that rebinds a used name is `binding-conflict` | `::test_host_statement_that_rebinds_a_name_the_test_uses_is_a_binding_conflict[helper-def]`, `[assignment]`, `[loop-target]` |
| E5 | the `host-setup` check, `_outside` (`if rec["hook"] and rec["key"] not in orig_keys:`) | module-level test setup the host adds is refused (`host-setup`) | `::test_host_module_level_test_setup_is_host_setup[autouse-fixture]`, `[pytestmark]` |
| E6 | the Python front's directive-comment folding, `break_it_body_py.py` `parse` (`directives = _directives(text)`) | a directive comment inside a statement is part of its key, so an added `# type: ignore` is a different test | `::test_an_added_type_ignore_directive_is_not_kept`, `::test_front_unequal_keys_for_semantic_differences` |
| E7 | the title placeholder's `test` prefix condition, `break_it_body_py.py` `_normalise` (`if target.name.startswith("test"):`) | only a function named `test*` is a title; any other name is part of the compared tree | `::test_a_renamed_helper_is_not_a_title_and_reads_changed`, `::test_front_titles_are_test_prefixed_defs_only`, `::test_front_a_title_does_not_change_the_key_but_any_other_name_does` |
| E8 | `_rewrite_command`'s `command-selects-tests` refusal, `break_it.py` (`if titles and any(_selects_tests(...)...)`) | a renamed test's command that filters by flag, selector or old title is refused | `::test_a_renamed_moved_test_whose_command_carries_k_is_command_selects_tests`, `::test_a_renamed_test_at_its_own_path_with_a_selector_is_command_selects_tests`, `::test_rewrite_refuses_a_renamed_test_whose_command_selects_tests` |
| E9 | `_rewrite_command`'s same-path unchanged-command branch, `break_it.py` (`if new_path == old_path: return command, None`) | a test found at its own path runs the command exactly as the loop ran it (the original bytes) | `::test_formatter_case_is_kept_by_body_and_runs_the_original_command_byte_for_byte`, `::test_rewrite_same_path_returns_the_original_string` |
| E10 | the `content`-absent fallback, `break_it.py` `check_kept.searched` (`if not isinstance(record.get("content"), str): return today`) | a record without string content never searches, so it keeps the byte-exact check | `::test_a_record_without_content_keeps_the_byte_exact_check`, `::test_a_record_whose_content_is_not_a_string_keeps_the_byte_exact_check` |
| E11 | `_selects_tests`' path-token exemption, `break_it.py` (`if tok == old_path or tok.startswith(old_path + "::"): return "::" in tok`) | a path token is judged by the `::` rule alone, so a test file named after its own test still renames | `::test_rewrite_a_path_token_that_contains_an_old_title_is_no_filter`, `::test_a_test_file_named_after_its_own_test_is_kept_when_the_test_is_renamed_in_place` |

## Disclosures

- Every element went red under its neutralization (pytest exit 1) and green after the restore (exit 0). The red of each element is on the axis named in its row: a `kept`/`body-match` or a rewritten command where the axis expects a refusal or the original bytes (E10: a `KeyError` on `content` and a `body-unparseable` where the fallback expects `changed`).
- Every neutralization is a `False and ...` guard (E2: `unparseable = False`; E6: `directives = []`; E7: `if True:`), so the guarded branch is the production call site the detector reaches, never a helper the tests assert as a precondition.
- The restore receipt is `git diff --stat -- <file>` taken after the inverse edit, printed between `--- git diff --stat` and `--- end diff` markers: in every element it printed nothing, so the file equals its last commit. After E11 a `git status --porcelain` over the worktree also printed nothing.
- The command shape is `scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest <exact node ids> -q`, followed by `echo "pytest exit: $?"` to print the exit code. The `UV_NATIVE_TLS` deprecation warning line that `scripts/pinned-python` may print is not shown; everything else is verbatim (default `--tb`, no filter).
- Redaction: none needed; local `/path/to/home/...` and `/private/tmp/...` paths are kept as printed, no secret, token or private URL appears.
- All captures are under 32 KiB each and under 128 KiB together, so none is written off-repo.

---

## E1: the ambiguity refusal

- **axis:** a second copy of the test reads `match-ambiguous`, never kept

**neutralization** (`plugins/superheroes/lib/break_it_body.py`):
```diff
-    if len(matches) > 1:
+    if False and len(matches) > 1:
```

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_two_matching_copies_are_ambiguous plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_a_copy_beside_the_changed_original_is_ambiguous -q
```

**raw red** (exit 1):
```
FF                                                                       [100%]
=================================== FAILURES ===================================
____________________ test_two_matching_copies_are_ambiguous ____________________

repo = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-221/test_two_matching_copies_are_a0/repo')

    def test_two_matching_copies_are_ambiguous(repo):
        base, head = _stage(repo, {"tests/test_a.py": ORIG.replace("test_x", "test_a"),
                                   "tests/test_b.py": ORIG.replace("test_x", "test_b")})
        calls = []
>       assert _got(_check(repo, base, head, _record(), _stub(calls))) == ("unresolved", "match-ambiguous")
E       AssertionError: assert ('kept', 'body-match') == ('unresolved'...ch-ambiguous')
E         
E         At index 0 diff: 'kept' != 'unresolved'
E         Use -v to get more diff

/path/to/home/.superheroes-worktrees/superheroes/issue-2053-wo-a/plugins/superheroes/lib/tests/test_break_it_body_2053.py:259: AssertionError
_____________ test_a_copy_beside_the_changed_original_is_ambiguous _____________

repo = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-221/test_a_copy_beside_the_changed0/repo')

    def test_a_copy_beside_the_changed_original_is_ambiguous(repo):
        base, head = _stage(repo, {OWN: FORMATTED, "tests/test_b.py": ORIG.replace("test_x", "test_b")})
>       assert _got(_check(repo, base, head, _record())) == ("unresolved", "match-ambiguous")
E       AssertionError: assert ('kept', 'body-match') == ('unresolved'...ch-ambiguous')
E         
E         At index 0 diff: 'kept' != 'unresolved'
E         Use -v to get more diff

/path/to/home/.superheroes-worktrees/superheroes/issue-2053-wo-a/plugins/superheroes/lib/tests/test_break_it_body_2053.py:265: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_two_matching_copies_are_ambiguous
FAILED plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_a_copy_beside_the_changed_original_is_ambiguous
2 failed in 2.13s
pytest exit: 1
```

**restore:** the inverse edit on `plugins/superheroes/lib/break_it_body.py` (`if False and len(matches) > 1:` back to `if len(matches) > 1:`).

**restore receipt** (`git diff --stat` over the file, printed nothing):
```
--- git diff --stat (break_it_body.py):
--- end diff
```

**raw green** (exit 0), same command:
```
..                                                                       [100%]
2 passed in 0.84s
pytest exit: 0
```

---

## E2: the unparseable refusal for a prefilter-passing candidate

- **axis:** a candidate that passes the prefilter and cannot be read leaves the search undecided (`body-unparseable`), even beside a match

**neutralization** (`plugins/superheroes/lib/break_it_body.py`, in the `except ValueError` branch of `locate`; the edit's match text included the following `continue` and `stmts =` lines to be unique):
```diff
-            unparseable = True
+            unparseable = False
             continue
         stmts =
```

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_prefilter_passing_unparseable_candidate_is_unresolved_beside_a_match plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_prefilter_passing_unparseable_candidate_without_a_match_is_unresolved -q
```

**raw red** (exit 1):
```
FF                                                                       [100%]
=================================== FAILURES ===================================
__ test_prefilter_passing_unparseable_candidate_is_unresolved_beside_a_match ___

repo = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-226/test_prefilter_passing_unparse0/repo')

    def test_prefilter_passing_unparseable_candidate_is_unresolved_beside_a_match(repo):
        broken = ORIG + "\nbroken = (\n"
        base, head = _stage(repo, {"tests/test_weekly.py": ORIG.replace("test_x", "test_y"), "tests/broken.py": broken})
        calls = []
>       assert _got(_check(repo, base, head, _record(), _stub(calls))) == ("unresolved", "body-unparseable")
E       AssertionError: assert ('kept', 'body-match') == ('unresolved'...-unparseable')
E         
E         At index 0 diff: 'kept' != 'unresolved'
E         Use -v to get more diff

/path/to/home/.superheroes-worktrees/superheroes/issue-2053-wo-a/plugins/superheroes/lib/tests/test_break_it_body_2053.py:230: AssertionError
__ test_prefilter_passing_unparseable_candidate_without_a_match_is_unresolved __

repo = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-226/test_prefilter_passing_unparse1/repo')

    def test_prefilter_passing_unparseable_candidate_without_a_match_is_unresolved(repo):
        broken = ORIG + "\nbroken = (\n"
        base, head = _stage(repo, {"tests/broken.py": broken})
>       assert _got(_check(repo, base, head, _record())) == ("unresolved", "body-unparseable")
E       AssertionError: assert ('missing', 'not-in-head') == ('unresolved'...-unparseable')
E         
E         At index 0 diff: 'missing' != 'unresolved'
E         Use -v to get more diff

/path/to/home/.superheroes-worktrees/superheroes/issue-2053-wo-a/plugins/superheroes/lib/tests/test_break_it_body_2053.py:237: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_prefilter_passing_unparseable_candidate_is_unresolved_beside_a_match
FAILED plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_prefilter_passing_unparseable_candidate_without_a_match_is_unresolved
2 failed in 0.77s
pytest exit: 1
```

**restore:** the inverse edit on `plugins/superheroes/lib/break_it_body.py` (`unparseable = False` back to `unparseable = True`).

**restore receipt** (`git diff --stat` over the file, printed nothing):
```
--- git diff --stat (break_it_body.py):
--- end diff
```

**raw green** (exit 0), same command:
```
..                                                                       [100%]
2 passed in 0.73s
pytest exit: 0
```

---

## E3: the import-pair presence check

- **axis:** every import the original bound is bound the same way in the file that holds the test (`binding-conflict`)

**neutralization** (`plugins/superheroes/lib/break_it_body.py`, `_outside`):
```diff
-    if not orig_pairs <= {pair for rec in records for pair in rec["imports"]}:
+    if False and not orig_pairs <= {pair for rec in records for pair in rec["imports"]}:
```

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_host_that_lacks_an_import_the_test_binds_is_a_binding_conflict -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_host_that_lacks_an_import_the_test_binds_is_a_binding_conflict ______

repo = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-229/test_host_that_lacks_an_import0/repo')

    def test_host_that_lacks_an_import_the_test_binds_is_a_binding_conflict(repo):
        base, head = _stage(repo, {"tests/test_weekly.py": _host(imports="import pytest\n")})
        calls = []
>       assert _got(_check(repo, base, head, _record(), _stub(calls))) == ("unresolved", "binding-conflict")
E       AssertionError: assert ('kept', 'body-match') == ('unresolved'...ing-conflict')
E         
E         At index 0 diff: 'kept' != 'unresolved'
E         Use -v to get more diff

/path/to/home/.superheroes-worktrees/superheroes/issue-2053-wo-a/plugins/superheroes/lib/tests/test_break_it_body_2053.py:271: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_host_that_lacks_an_import_the_test_binds_is_a_binding_conflict
1 failed in 0.60s
pytest exit: 1
```

**restore:** the inverse edit on `plugins/superheroes/lib/break_it_body.py` (`if False and not orig_pairs <= {pair` back to `if not orig_pairs <= {pair`).

**restore receipt** (`git diff --stat` over the file, printed nothing):
```
--- git diff --stat (break_it_body.py):
--- end diff
```

**raw green** (exit 0), same command:
```
.                                                                        [100%]
1 passed in 1.03s
pytest exit: 0
```

---

## E4a: the outside-window import rebinding check

- **axis:** an import outside the window that rebinds a name the test uses, or star-imports over it, is refused (`binding-conflict`)

**neutralization** (`plugins/superheroes/lib/break_it_body.py`, `_outside`):
```diff
-            if pair[0] == "*" or pair[0] in names:
+            if False and (pair[0] == "*" or pair[0] in names):
```

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_host_that_binds_an_imported_name_another_way_is_a_binding_conflict plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_host_star_import_is_a_binding_conflict -q
```

**raw red** (exit 1):
```
FF                                                                       [100%]
=================================== FAILURES ===================================
___ test_host_that_binds_an_imported_name_another_way_is_a_binding_conflict ____

repo = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-234/test_host_that_binds_an_import0/repo')

    def test_host_that_binds_an_imported_name_another_way_is_a_binding_conflict(repo):
        imports = "from math import sqrt\nfrom math import isfinite as sqrt\n\nimport pytest\n"
        base, head = _stage(repo, {"tests/test_weekly.py": _host(imports=imports)})
        calls = []
>       assert _got(_check(repo, base, head, _record(), _stub(calls))) == ("unresolved", "binding-conflict")
E       AssertionError: assert ('kept', 'body-match') == ('unresolved'...ing-conflict')
E         
E         At index 0 diff: 'kept' != 'unresolved'
E         Use -v to get more diff

/path/to/home/.superheroes-worktrees/superheroes/issue-2053-wo-a/plugins/superheroes/lib/tests/test_break_it_body_2053.py:279: AssertionError
_________________ test_host_star_import_is_a_binding_conflict __________________

repo = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-234/test_host_star_import_is_a_bin0/repo')

    def test_host_star_import_is_a_binding_conflict(repo):
        base, head = _stage(repo, {"tests/test_weekly.py": _host(imports=IMPORTS + "from os.path import *\n")})
        calls = []
>       assert _got(_check(repo, base, head, _record(), _stub(calls))) == ("unresolved", "binding-conflict")
E       AssertionError: assert ('kept', 'body-match') == ('unresolved'...ing-conflict')
E         
E         At index 0 diff: 'kept' != 'unresolved'
E         Use -v to get more diff

/path/to/home/.superheroes-worktrees/superheroes/issue-2053-wo-a/plugins/superheroes/lib/tests/test_break_it_body_2053.py:286: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_host_that_binds_an_imported_name_another_way_is_a_binding_conflict
FAILED plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_host_star_import_is_a_binding_conflict
2 failed in 0.76s
pytest exit: 1
```

**restore:** the inverse edit on `plugins/superheroes/lib/break_it_body.py` (`if False and (pair[0] == "*" or pair[0] in names):` back to `if pair[0] == "*" or pair[0] in names:`).

**restore receipt** (`git diff --stat` over the file, printed nothing):
```
--- git diff --stat (break_it_body.py):
--- end diff
```

**raw green** (exit 0), same command:
```
..                                                                       [100%]
2 passed in 0.46s
pytest exit: 0
```

---

## E4b: the outside-window statement-binds check

- **axis:** a statement outside the window that rebinds a name the test uses is refused (`binding-conflict`)

**neutralization** (`plugins/superheroes/lib/break_it_body.py`, `_outside`):
```diff
-        if rec["kind"] == "stmt" and rec["binds"] & names:
+        if False and rec["kind"] == "stmt" and rec["binds"] & names:
```

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest "plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_host_statement_that_rebinds_a_name_the_test_uses_is_a_binding_conflict[helper-def]" "plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_host_statement_that_rebinds_a_name_the_test_uses_is_a_binding_conflict[assignment]" "plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_host_statement_that_rebinds_a_name_the_test_uses_is_a_binding_conflict[loop-target]" -q
```

**raw red** (exit 1):
```
FFF                                                                      [100%]
=================================== FAILURES ===================================
_ test_host_statement_that_rebinds_a_name_the_test_uses_is_a_binding_conflict[helper-def] _

repo = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-238/test_host_statement_that_rebin0/repo')
before = 'def sqrt(x):\n    return 3\n\n\n'

    @pytest.mark.parametrize("before", [
        "def sqrt(x):\n    return 3\n\n\n",
        "LABEL = 'ten'\n\n\n",
        "for side in (1, 2):\n    pass\n\n\n",
    ], ids=["helper-def", "assignment", "loop-target"])
    def test_host_statement_that_rebinds_a_name_the_test_uses_is_a_binding_conflict(repo, before):
        base, head = _stage(repo, {"tests/test_weekly.py": _host(before=before)})
        calls = []
>       assert _got(_check(repo, base, head, _record(), _stub(calls))) == ("unresolved", "binding-conflict")
E       AssertionError: assert ('kept', 'body-match') == ('unresolved'...ing-conflict')
E         
E         At index 0 diff: 'kept' != 'unresolved'
E         Use -v to get more diff

/path/to/home/.superheroes-worktrees/superheroes/issue-2053-wo-a/plugins/superheroes/lib/tests/test_break_it_body_2053.py:298: AssertionError
_ test_host_statement_that_rebinds_a_name_the_test_uses_is_a_binding_conflict[assignment] _

repo = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-238/test_host_statement_that_rebin1/repo')
before = "LABEL = 'ten'\n\n\n"

    @pytest.mark.parametrize("before", [
        "def sqrt(x):\n    return 3\n\n\n",
        "LABEL = 'ten'\n\n\n",
        "for side in (1, 2):\n    pass\n\n\n",
    ], ids=["helper-def", "assignment", "loop-target"])
    def test_host_statement_that_rebinds_a_name_the_test_uses_is_a_binding_conflict(repo, before):
        base, head = _stage(repo, {"tests/test_weekly.py": _host(before=before)})
        calls = []
>       assert _got(_check(repo, base, head, _record(), _stub(calls))) == ("unresolved", "binding-conflict")
E       AssertionError: assert ('kept', 'body-match') == ('unresolved'...ing-conflict')
E         
E         At index 0 diff: 'kept' != 'unresolved'
E         Use -v to get more diff

/path/to/home/.superheroes-worktrees/superheroes/issue-2053-wo-a/plugins/superheroes/lib/tests/test_break_it_body_2053.py:298: AssertionError
_ test_host_statement_that_rebinds_a_name_the_test_uses_is_a_binding_conflict[loop-target] _

repo = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-238/test_host_statement_that_rebin2/repo')
before = 'for side in (1, 2):\n    pass\n\n\n'

    @pytest.mark.parametrize("before", [
        "def sqrt(x):\n    return 3\n\n\n",
        "LABEL = 'ten'\n\n\n",
        "for side in (1, 2):\n    pass\n\n\n",
    ], ids=["helper-def", "assignment", "loop-target"])
    def test_host_statement_that_rebinds_a_name_the_test_uses_is_a_binding_conflict(repo, before):
        base, head = _stage(repo, {"tests/test_weekly.py": _host(before=before)})
        calls = []
>       assert _got(_check(repo, base, head, _record(), _stub(calls))) == ("unresolved", "binding-conflict")
E       AssertionError: assert ('kept', 'body-match') == ('unresolved'...ing-conflict')
E         
E         At index 0 diff: 'kept' != 'unresolved'
E         Use -v to get more diff

/path/to/home/.superheroes-worktrees/superheroes/issue-2053-wo-a/plugins/superheroes/lib/tests/test_break_it_body_2053.py:298: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_host_statement_that_rebinds_a_name_the_test_uses_is_a_binding_conflict[helper-def]
FAILED plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_host_statement_that_rebinds_a_name_the_test_uses_is_a_binding_conflict[assignment]
FAILED plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_host_statement_that_rebinds_a_name_the_test_uses_is_a_binding_conflict[loop-target]
3 failed in 0.67s
pytest exit: 1
```

**restore:** the inverse edit on `plugins/superheroes/lib/break_it_body.py` (`if False and rec["kind"] == "stmt" and rec["binds"] & names:` back to `if rec["kind"] == "stmt" and rec["binds"] & names:`).

**restore receipt** (`git diff --stat` over the file, printed nothing):
```
--- git diff --stat (break_it_body.py):
--- end diff
```

**raw green** (exit 0), same command:
```
...                                                                      [100%]
3 passed in 0.60s
pytest exit: 0
```

---

## E5: the `host-setup` check

- **axis:** module-level test setup the host adds is refused (`host-setup`)

**neutralization** (`plugins/superheroes/lib/break_it_body.py`, `_outside`):
```diff
-        if rec["hook"] and rec["key"] not in orig_keys:
+        if False and rec["hook"] and rec["key"] not in orig_keys:
```

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest "plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_host_module_level_test_setup_is_host_setup[autouse-fixture]" "plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_host_module_level_test_setup_is_host_setup[pytestmark]" -q
```

**raw red** (exit 1):
```
FF                                                                       [100%]
=================================== FAILURES ===================================
_______ test_host_module_level_test_setup_is_host_setup[autouse-fixture] _______

repo = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-242/test_host_module_level_test_se0/repo')
before = '@pytest.fixture(autouse=True)\ndef _env():\n    pass\n\n\n'

    @pytest.mark.parametrize("before", [
        "@pytest.fixture(autouse=True)\ndef _env():\n    pass\n\n\n",
        "pytestmark = pytest.mark.filterwarnings('ignore')\n\n\n",
    ], ids=["autouse-fixture", "pytestmark"])
    def test_host_module_level_test_setup_is_host_setup(repo, before):
        base, head = _stage(repo, {"tests/test_weekly.py": _host(before=before)})
        calls = []
>       assert _got(_check(repo, base, head, _record(), _stub(calls))) == ("unresolved", "host-setup")
E       AssertionError: assert ('kept', 'body-match') == ('unresolved', 'host-setup')
E         
E         At index 0 diff: 'kept' != 'unresolved'
E         Use -v to get more diff

/path/to/home/.superheroes-worktrees/superheroes/issue-2053-wo-a/plugins/superheroes/lib/tests/test_break_it_body_2053.py:309: AssertionError
_________ test_host_module_level_test_setup_is_host_setup[pytestmark] __________

repo = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-242/test_host_module_level_test_se1/repo')
before = "pytestmark = pytest.mark.filterwarnings('ignore')\n\n\n"

    @pytest.mark.parametrize("before", [
        "@pytest.fixture(autouse=True)\ndef _env():\n    pass\n\n\n",
        "pytestmark = pytest.mark.filterwarnings('ignore')\n\n\n",
    ], ids=["autouse-fixture", "pytestmark"])
    def test_host_module_level_test_setup_is_host_setup(repo, before):
        base, head = _stage(repo, {"tests/test_weekly.py": _host(before=before)})
        calls = []
>       assert _got(_check(repo, base, head, _record(), _stub(calls))) == ("unresolved", "host-setup")
E       AssertionError: assert ('kept', 'body-match') == ('unresolved', 'host-setup')
E         
E         At index 0 diff: 'kept' != 'unresolved'
E         Use -v to get more diff

/path/to/home/.superheroes-worktrees/superheroes/issue-2053-wo-a/plugins/superheroes/lib/tests/test_break_it_body_2053.py:309: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_host_module_level_test_setup_is_host_setup[autouse-fixture]
FAILED plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_host_module_level_test_setup_is_host_setup[pytestmark]
2 failed in 0.45s
pytest exit: 1
```

**restore:** the inverse edit on `plugins/superheroes/lib/break_it_body.py` (`if False and rec["hook"] and rec["key"] not in orig_keys:` back to `if rec["hook"] and rec["key"] not in orig_keys:`).

**restore receipt** (`git diff --stat` over the file, printed nothing):
```
--- git diff --stat (break_it_body.py):
--- end diff
```

**raw green** (exit 0), same command:
```
..                                                                       [100%]
2 passed in 0.47s
pytest exit: 0
```

---

## E6: the Python front's directive-comment folding

- **axis:** a directive comment inside a statement is part of its key, so an added `# type: ignore` is a different test

**neutralization** (`plugins/superheroes/lib/break_it_body_py.py`, `parse`):
```diff
-        directives = _directives(text)
+        directives = []
```

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_an_added_type_ignore_directive_is_not_kept plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_front_unequal_keys_for_semantic_differences -q
```

**raw red** (exit 1; the four directive rows of the parametrized test and the end-to-end test fail, the four non-directive rows pass):
```
F...FFFF.                                                                [100%]
=================================== FAILURES ===================================
_______________ test_an_added_type_ignore_directive_is_not_kept ________________

repo = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-245/test_an_added_type_ignore_dire0/repo')

    def test_an_added_type_ignore_directive_is_not_kept(repo):
        ignored = ORIG.replace("return 9", "return 9  # type: ignore")
        base, head = _stage(repo, {OWN: ignored})
>       assert _got(_check(repo, base, head, _record())) == ("changed", "sha256-differs")
E       AssertionError: assert ('kept', 'body-match') == ('changed', 'sha256-differs')
E         
E         At index 0 diff: 'kept' != 'changed'
E         Use -v to get more diff

/path/to/home/.superheroes-worktrees/superheroes/issue-2053-wo-a/plugins/superheroes/lib/tests/test_break_it_body_2053.py:329: AssertionError
_ test_front_unequal_keys_for_semantic_differences[x = 1\n-x = 1  # type: ignore\n] _

left = 'x = 1\n', right = 'x = 1  # type: ignore\n'

    @pytest.mark.parametrize("left, right", [
        ("x = (1,)\n", "x = (1)\n"),
        ("if c:\n    a = 1\nelse:\n    b = 2\n", "if c:\n    a = 1\n    b = 2\nelse:\n    pass\n"),
        ("def f(): pass\n", "@d\ndef f(): pass\n"),
        ("x = 1\n", "x = 1  # type: ignore\n"),
        ("x = 1  # type: ignore\n", "x = 1  # noqa\n"),
        ("x = foo(\n    1,  # type: ignore\n)\n", "x = foo(\n    1,\n)\n"),
        ("@d  # noqa\ndef f(): pass\n", "@d\ndef f(): pass\n"),
        ("x = 'a'\n", "x = 'b'\n"),
    ])
    def test_front_unequal_keys_for_semantic_differences(left, right):
>       assert _keys(left) != _keys(right)
E       assert [("Assign(targets=[Name(id='x', ctx=Store())], value=Constant(value=1))", ())] != [("Assign(targets=[Name(id='x', ctx=Store())], value=Constant(value=1))", ())]
E        +  where [("Assign(targets=[Name(id='x', ctx=Store())], value=Constant(value=1))", ())] = _keys('x = 1\n')
E        +  and   [("Assign(targets=[Name(id='x', ctx=Store())], value=Constant(value=1))", ())] = _keys('x = 1  # type: ignore\n')

/path/to/home/.superheroes-worktrees/superheroes/issue-2053-wo-a/plugins/superheroes/lib/tests/test_break_it_body_2053.py:600: AssertionError
_ test_front_unequal_keys_for_semantic_differences[x = 1  # type: ignore\n-x = 1  # noqa\n] _

left = 'x = 1  # type: ignore\n', right = 'x = 1  # noqa\n'

    @pytest.mark.parametrize("left, right", [
        ("x = (1,)\n", "x = (1)\n"),
        ("if c:\n    a = 1\nelse:\n    b = 2\n", "if c:\n    a = 1\n    b = 2\nelse:\n    pass\n"),
        ("def f(): pass\n", "@d\ndef f(): pass\n"),
        ("x = 1\n", "x = 1  # type: ignore\n"),
        ("x = 1  # type: ignore\n", "x = 1  # noqa\n"),
        ("x = foo(\n    1,  # type: ignore\n)\n", "x = foo(\n    1,\n)\n"),
        ("@d  # noqa\ndef f(): pass\n", "@d\ndef f(): pass\n"),
        ("x = 'a'\n", "x = 'b'\n"),
    ])
    def test_front_unequal_keys_for_semantic_differences(left, right):
>       assert _keys(left) != _keys(right)
E       assert [("Assign(targets=[Name(id='x', ctx=Store())], value=Constant(value=1))", ())] != [("Assign(targets=[Name(id='x', ctx=Store())], value=Constant(value=1))", ())]
E        +  where [("Assign(targets=[Name(id='x', ctx=Store())], value=Constant(value=1))", ())] = _keys('x = 1  # type: ignore\n')
E        +  and   [("Assign(targets=[Name(id='x', ctx=Store())], value=Constant(value=1))", ())] = _keys('x = 1  # noqa\n')

/path/to/home/.superheroes-worktrees/superheroes/issue-2053-wo-a/plugins/superheroes/lib/tests/test_break_it_body_2053.py:600: AssertionError
_ test_front_unequal_keys_for_semantic_differences[x = foo(\n    1,  # type: ignore\n)\n-x = foo(\n    1,\n)\n] _

left = 'x = foo(\n    1,  # type: ignore\n)\n', right = 'x = foo(\n    1,\n)\n'

    @pytest.mark.parametrize("left, right", [
        ("x = (1,)\n", "x = (1)\n"),
        ("if c:\n    a = 1\nelse:\n    b = 2\n", "if c:\n    a = 1\n    b = 2\nelse:\n    pass\n"),
        ("def f(): pass\n", "@d\ndef f(): pass\n"),
        ("x = 1\n", "x = 1  # type: ignore\n"),
        ("x = 1  # type: ignore\n", "x = 1  # noqa\n"),
        ("x = foo(\n    1,  # type: ignore\n)\n", "x = foo(\n    1,\n)\n"),
        ("@d  # noqa\ndef f(): pass\n", "@d\ndef f(): pass\n"),
        ("x = 'a'\n", "x = 'b'\n"),
    ])
    def test_front_unequal_keys_for_semantic_differences(left, right):
>       assert _keys(left) != _keys(right)
E       assert [("Assign(targets=[Name(id='x', ctx=Store())], value=Call(func=Name(id='foo', ctx=Load()), args=[Constant(value=1)], keywords=[]))", ())] != [("Assign(targets=[Name(id='x', ctx=Store())], value=Call(func=Name(id='foo', ctx=Load()), args=[Constant(value=1)], keywords=[]))", ())]
E        +  where [("Assign(targets=[Name(id='x', ctx=Store())], value=Call(func=Name(id='foo', ctx=Load()), args=[Constant(value=1)], keywords=[]))", ())] = _keys('x = foo(\n    1,  # type: ignore\n)\n')
E        +  and   [("Assign(targets=[Name(id='x', ctx=Store())], value=Call(func=Name(id='foo', ctx=Load()), args=[Constant(value=1)], keywords=[]))", ())] = _keys('x = foo(\n    1,\n)\n')

/path/to/home/.superheroes-worktrees/superheroes/issue-2053-wo-a/plugins/superheroes/lib/tests/test_break_it_body_2053.py:600: AssertionError
_ test_front_unequal_keys_for_semantic_differences[@d  # noqa\ndef f(): pass\n-@d\ndef f(): pass\n] _

left = '@d  # noqa\ndef f(): pass\n', right = '@d\ndef f(): pass\n'

    @pytest.mark.parametrize("left, right", [
        ("x = (1,)\n", "x = (1)\n"),
        ("if c:\n    a = 1\nelse:\n    b = 2\n", "if c:\n    a = 1\n    b = 2\nelse:\n    pass\n"),
        ("def f(): pass\n", "@d\ndef f(): pass\n"),
        ("x = 1\n", "x = 1  # type: ignore\n"),
        ("x = 1  # type: ignore\n", "x = 1  # noqa\n"),
        ("x = foo(\n    1,  # type: ignore\n)\n", "x = foo(\n    1,\n)\n"),
        ("@d  # noqa\ndef f(): pass\n", "@d\ndef f(): pass\n"),
        ("x = 'a'\n", "x = 'b'\n"),
    ])
    def test_front_unequal_keys_for_semantic_differences(left, right):
>       assert _keys(left) != _keys(right)
E       assert [("FunctionDef(name='f', args=arguments(posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]), body=[Pass()], decorator_list=[Name(id='d', ctx=Load())], type_params=[])", ())] != [("FunctionDef(name='f', args=arguments(posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]), body=[Pass()], decorator_list=[Name(id='d', ctx=Load())], type_params=[])", ())]
E        +  where [("FunctionDef(name='f', args=arguments(posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]), body=[Pass()], decorator_list=[Name(id='d', ctx=Load())], type_params=[])", ())] = _keys('@d  # noqa\ndef f(): pass\n')
E        +  and   [("FunctionDef(name='f', args=arguments(posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]), body=[Pass()], decorator_list=[Name(id='d', ctx=Load())], type_params=[])", ())] = _keys('@d\ndef f(): pass\n')

/path/to/home/.superheroes-worktrees/superheroes/issue-2053-wo-a/plugins/superheroes/lib/tests/test_break_it_body_2053.py:600: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_an_added_type_ignore_directive_is_not_kept
FAILED plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_front_unequal_keys_for_semantic_differences[x = 1\n-x = 1  # type: ignore\n]
FAILED plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_front_unequal_keys_for_semantic_differences[x = 1  # type: ignore\n-x = 1  # noqa\n]
FAILED plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_front_unequal_keys_for_semantic_differences[x = foo(\n    1,  # type: ignore\n)\n-x = foo(\n    1,\n)\n]
FAILED plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_front_unequal_keys_for_semantic_differences[@d  # noqa\ndef f(): pass\n-@d\ndef f(): pass\n]
5 failed, 4 passed in 1.19s
pytest exit: 1
```

**restore:** the inverse edit on `plugins/superheroes/lib/break_it_body_py.py` (`directives = []` back to `directives = _directives(text)`).

**restore receipt** (`git diff --stat` over the file, printed nothing):
```
--- git diff --stat (break_it_body_py.py):
--- end diff
```

**raw green** (exit 0), same command:
```
.........                                                                [100%]
9 passed in 0.33s
pytest exit: 0
```

---

## E7: the title placeholder's `test` prefix condition

- **axis:** only a function named `test*` is a title; any other name is part of the compared tree

**neutralization** (`plugins/superheroes/lib/break_it_body_py.py`, `_normalise`):
```diff
-        if target.name.startswith("test"):
+        if True:
```

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_a_renamed_helper_is_not_a_title_and_reads_changed plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_front_titles_are_test_prefixed_defs_only plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_front_a_title_does_not_change_the_key_but_any_other_name_does -q
```

**raw red** (exit 1):
```
FFF                                                                      [100%]
=================================== FAILURES ===================================
____________ test_a_renamed_helper_is_not_a_title_and_reads_changed ____________

repo = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-247/test_a_renamed_helper_is_not_a0/repo')

    def test_a_renamed_helper_is_not_a_title_and_reads_changed(repo):
        content = ORIG + "\n\ndef helper():\n    return 1\n"
        base, head = _stage(repo, {OWN: content.replace("def helper", "def helper2")})
>       assert _got(_check(repo, base, head, _record(content=content))) == ("changed", "sha256-differs")
E       AssertionError: assert ('kept', 'body-match') == ('changed', 'sha256-differs')
E         
E         At index 0 diff: 'kept' != 'changed'
E         Use -v to get more diff

/path/to/home/.superheroes-worktrees/superheroes/issue-2053-wo-a/plugins/superheroes/lib/tests/test_break_it_body_2053.py:335: AssertionError
________________ test_front_titles_are_test_prefixed_defs_only _________________

    def test_front_titles_are_test_prefixed_defs_only():
        assert front.parse("def test_a(): pass\n")[0]["titles"] == ("test_a",)
        assert front.parse("async def test_a(): pass\n")[0]["titles"] == ("test_a",)
>       assert front.parse("def helper(): pass\n")[0]["titles"] == ()
E       AssertionError: assert ('helper',) == ()
E         
E         Left contains one more item: 'helper'
E         Use -v to get more diff

/path/to/home/.superheroes-worktrees/superheroes/issue-2053-wo-a/plugins/superheroes/lib/tests/test_break_it_body_2053.py:613: AssertionError
______ test_front_a_title_does_not_change_the_key_but_any_other_name_does ______

    def test_front_a_title_does_not_change_the_key_but_any_other_name_does():
        assert _keys("def test_a(): pass\n") == _keys("def test_b(): pass\n")
        assert _keys("class T:\n    def test_m(self): pass\n") == _keys("class T:\n    def test_z(self): pass\n")
>       assert _keys("def check_a(): pass\n") != _keys("def check_b(): pass\n")
E       assert [("FunctionDef(name='\\x00title', args=arguments(posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]), body=[Pass()], decorator_list=[], type_params=[])", ())] != [("FunctionDef(name='\\x00title', args=arguments(posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]), body=[Pass()], decorator_list=[], type_params=[])", ())]
E        +  where [("FunctionDef(name='\\x00title', args=arguments(posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]), body=[Pass()], decorator_list=[], type_params=[])", ())] = _keys('def check_a(): pass\n')
E        +  and   [("FunctionDef(name='\\x00title', args=arguments(posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]), body=[Pass()], decorator_list=[], type_params=[])", ())] = _keys('def check_b(): pass\n')

/path/to/home/.superheroes-worktrees/superheroes/issue-2053-wo-a/plugins/superheroes/lib/tests/test_break_it_body_2053.py:623: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_a_renamed_helper_is_not_a_title_and_reads_changed
FAILED plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_front_titles_are_test_prefixed_defs_only
FAILED plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_front_a_title_does_not_change_the_key_but_any_other_name_does
3 failed in 1.20s
pytest exit: 1
```

**restore:** the inverse edit on `plugins/superheroes/lib/break_it_body_py.py` (`if True:` back to `if target.name.startswith("test"):`).

**restore receipt** (`git diff --stat` over the file, printed nothing):
```
--- git diff --stat (break_it_body_py.py):
--- end diff
```

**raw green** (exit 0), same command:
```
...                                                                      [100%]
3 passed in 0.30s
pytest exit: 0
```

---

## E8: `_rewrite_command`'s `command-selects-tests` refusal

- **axis:** a renamed test's command that filters by flag, selector or old title is refused, because the filter would select nothing in the moved copy

**neutralization** (`plugins/superheroes/lib/break_it.py`, `_rewrite_command`):
```diff
-    if titles and any(_selects_tests(tok, titles, old_path) for tok in argv):
+    if False and titles and any(_selects_tests(tok, titles, old_path) for tok in argv):
```

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_a_renamed_moved_test_whose_command_carries_k_is_command_selects_tests plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_a_renamed_test_at_its_own_path_with_a_selector_is_command_selects_tests plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_rewrite_refuses_a_renamed_test_whose_command_selects_tests -q
```

**raw red** (exit 1; all 18 fail, the 16 parametrized rows each print the same `@pytest.mark.parametrize("extra", [...])` decorator block above their assertion, shown in full as printed):
```
FFFFFFFFFFFFFFFFFF                                                       [100%]
=================================== FAILURES ===================================
__ test_a_renamed_moved_test_whose_command_carries_k_is_command_selects_tests __

repo = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-249/test_a_renamed_moved_test_whos0/repo')

    def test_a_renamed_moved_test_whose_command_carries_k_is_command_selects_tests(repo):
        base, head = _stage(repo, {"tests/test_weekly.py": _host(body=BODY.replace("test_x", "test_y"))})
        calls = []
        record = _record(command=_cmd(extra=" -k regression"))
>       assert _got(_check(repo, base, head, record, _stub(calls))) == ("unresolved", "command-selects-tests")
E       AssertionError: assert ('kept', 'body-match') == ('unresolved'...elects-tests')
E         
E         At index 0 diff: 'kept' != 'unresolved'
E         Use -v to get more diff

/path/to/home/.superheroes-worktrees/superheroes/issue-2053-wo-a/plugins/superheroes/lib/tests/test_break_it_body_2053.py:350: AssertionError
_ test_a_renamed_test_at_its_own_path_with_a_selector_is_command_selects_tests _

repo = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-249/test_a_renamed_test_at_its_own0/repo')

    def test_a_renamed_test_at_its_own_path_with_a_selector_is_command_selects_tests(repo):
        base, head = _stage(repo, {OWN: FORMATTED.replace("test_x", "test_y")})
        calls = []
        record = _record(command=_cmd(OWN + "::test_x"))
>       assert _got(_check(repo, base, head, record, _stub(calls))) == ("unresolved", "command-selects-tests")
E       AssertionError: assert ('kept', 'body-match') == ('unresolved'...elects-tests')
E         
E         At index 0 diff: 'kept' != 'unresolved'
E         Use -v to get more diff

/path/to/home/.superheroes-worktrees/superheroes/issue-2053-wo-a/plugins/superheroes/lib/tests/test_break_it_body_2053.py:358: AssertionError
___ test_rewrite_refuses_a_renamed_test_whose_command_selects_tests[-k foo] ____

extra = '-k foo'

    @pytest.mark.parametrize("extra", [
        "-k foo", "-t foo", "-g foo", "-kfoo", "-tfoo", "-gfoo", "--testNamePattern foo", "--grep foo", "--filter foo",
        "--match foo", "--testNamePattern=foo", "--grep=foo", "--filter=foo", "--match=foo", "a.py::test_old",
        "test_old",
    ])
    def test_rewrite_refuses_a_renamed_test_whose_command_selects_tests(extra):
        got = break_it._rewrite_command("python -m pytest a.py " + extra, "a.py", "b.py", [("test_old", "test_new")])
>       assert got == (None, "command-selects-tests")
E       AssertionError: assert ('python -m p...-k foo', None) == (None, 'comma...elects-tests')
E         
E         At index 0 diff: 'python -m pytest b.py -k foo' != None
E         Use -v to get more diff

/path/to/home/.superheroes-worktrees/superheroes/issue-2053-wo-a/plugins/superheroes/lib/tests/test_break_it_body_2053.py:564: AssertionError
___ test_rewrite_refuses_a_renamed_test_whose_command_selects_tests[-t foo] ____

extra = '-t foo'

    @pytest.mark.parametrize("extra", [
        "-k foo", "-t foo", "-g foo", "-kfoo", "-tfoo", "-gfoo", "--testNamePattern foo", "--grep foo", "--filter foo",
        "--match foo", "--testNamePattern=foo", "--grep=foo", "--filter=foo", "--match=foo", "a.py::test_old",
        "test_old",
    ])
    def test_rewrite_refuses_a_renamed_test_whose_command_selects_tests(extra):
        got = break_it._rewrite_command("python -m pytest a.py " + extra, "a.py", "b.py", [("test_old", "test_new")])
>       assert got == (None, "command-selects-tests")
E       AssertionError: assert ('python -m p...-t foo', None) == (None, 'comma...elects-tests')
E         
E         At index 0 diff: 'python -m pytest b.py -t foo' != None
E         Use -v to get more diff

/path/to/home/.superheroes-worktrees/superheroes/issue-2053-wo-a/plugins/superheroes/lib/tests/test_break_it_body_2053.py:564: AssertionError
___ test_rewrite_refuses_a_renamed_test_whose_command_selects_tests[-g foo] ____

extra = '-g foo'

    @pytest.mark.parametrize("extra", [
        "-k foo", "-t foo", "-g foo", "-kfoo", "-tfoo", "-gfoo", "--testNamePattern foo", "--grep foo", "--filter foo",
        "--match foo", "--testNamePattern=foo", "--grep=foo", "--filter=foo", "--match=foo", "a.py::test_old",
        "test_old",
    ])
    def test_rewrite_refuses_a_renamed_test_whose_command_selects_tests(extra):
        got = break_it._rewrite_command("python -m pytest a.py " + extra, "a.py", "b.py", [("test_old", "test_new")])
>       assert got == (None, "command-selects-tests")
E       AssertionError: assert ('python -m p...-g foo', None) == (None, 'comma...elects-tests')
E         
E         At index 0 diff: 'python -m pytest b.py -g foo' != None
E         Use -v to get more diff

/path/to/home/.superheroes-worktrees/superheroes/issue-2053-wo-a/plugins/superheroes/lib/tests/test_break_it_body_2053.py:564: AssertionError
____ test_rewrite_refuses_a_renamed_test_whose_command_selects_tests[-kfoo] ____

extra = '-kfoo'

    @pytest.mark.parametrize("extra", [
        "-k foo", "-t foo", "-g foo", "-kfoo", "-tfoo", "-gfoo", "--testNamePattern foo", "--grep foo", "--filter foo",
        "--match foo", "--testNamePattern=foo", "--grep=foo", "--filter=foo", "--match=foo", "a.py::test_old",
        "test_old",
    ])
    def test_rewrite_refuses_a_renamed_test_whose_command_selects_tests(extra):
        got = break_it._rewrite_command("python -m pytest a.py " + extra, "a.py", "b.py", [("test_old", "test_new")])
>       assert got == (None, "command-selects-tests")
E       AssertionError: assert ('python -m p... -kfoo', None) == (None, 'comma...elects-tests')
E         
E         At index 0 diff: 'python -m pytest b.py -kfoo' != None
E         Use -v to get more diff

/path/to/home/.superheroes-worktrees/superheroes/issue-2053-wo-a/plugins/superheroes/lib/tests/test_break_it_body_2053.py:564: AssertionError
____ test_rewrite_refuses_a_renamed_test_whose_command_selects_tests[-tfoo] ____

extra = '-tfoo'

    @pytest.mark.parametrize("extra", [
        "-k foo", "-t foo", "-g foo", "-kfoo", "-tfoo", "-gfoo", "--testNamePattern foo", "--grep foo", "--filter foo",
        "--match foo", "--testNamePattern=foo", "--grep=foo", "--filter=foo", "--match=foo", "a.py::test_old",
        "test_old",
    ])
    def test_rewrite_refuses_a_renamed_test_whose_command_selects_tests(extra):
        got = break_it._rewrite_command("python -m pytest a.py " + extra, "a.py", "b.py", [("test_old", "test_new")])
>       assert got == (None, "command-selects-tests")
E       AssertionError: assert ('python -m p... -tfoo', None) == (None, 'comma...elects-tests')
E         
E         At index 0 diff: 'python -m pytest b.py -tfoo' != None
E         Use -v to get more diff

/path/to/home/.superheroes-worktrees/superheroes/issue-2053-wo-a/plugins/superheroes/lib/tests/test_break_it_body_2053.py:564: AssertionError
____ test_rewrite_refuses_a_renamed_test_whose_command_selects_tests[-gfoo] ____

extra = '-gfoo'

    @pytest.mark.parametrize("extra", [
        "-k foo", "-t foo", "-g foo", "-kfoo", "-tfoo", "-gfoo", "--testNamePattern foo", "--grep foo", "--filter foo",
        "--match foo", "--testNamePattern=foo", "--grep=foo", "--filter=foo", "--match=foo", "a.py::test_old",
        "test_old",
    ])
    def test_rewrite_refuses_a_renamed_test_whose_command_selects_tests(extra):
        got = break_it._rewrite_command("python -m pytest a.py " + extra, "a.py", "b.py", [("test_old", "test_new")])
>       assert got == (None, "command-selects-tests")
E       AssertionError: assert ('python -m p... -gfoo', None) == (None, 'comma...elects-tests')
E         
E         At index 0 diff: 'python -m pytest b.py -gfoo' != None
E         Use -v to get more diff

/path/to/home/.superheroes-worktrees/superheroes/issue-2053-wo-a/plugins/superheroes/lib/tests/test_break_it_body_2053.py:564: AssertionError
_ test_rewrite_refuses_a_renamed_test_whose_command_selects_tests[--testNamePattern foo] _

extra = '--testNamePattern foo'

    @pytest.mark.parametrize("extra", [
        "-k foo", "-t foo", "-g foo", "-kfoo", "-tfoo", "-gfoo", "--testNamePattern foo", "--grep foo", "--filter foo",
        "--match foo", "--testNamePattern=foo", "--grep=foo", "--filter=foo", "--match=foo", "a.py::test_old",
        "test_old",
    ])
    def test_rewrite_refuses_a_renamed_test_whose_command_selects_tests(extra):
        got = break_it._rewrite_command("python -m pytest a.py " + extra, "a.py", "b.py", [("test_old", "test_new")])
>       assert got == (None, "command-selects-tests")
E       AssertionError: assert ('python -m p...rn foo', None) == (None, 'comma...elects-tests')
E         
E         At index 0 diff: 'python -m pytest b.py --testNamePattern foo' != None
E         Use -v to get more diff

/path/to/home/.superheroes-worktrees/superheroes/issue-2053-wo-a/plugins/superheroes/lib/tests/test_break_it_body_2053.py:564: AssertionError
_ test_rewrite_refuses_a_renamed_test_whose_command_selects_tests[--grep foo] __

extra = '--grep foo'

    @pytest.mark.parametrize("extra", [
        "-k foo", "-t foo", "-g foo", "-kfoo", "-tfoo", "-gfoo", "--testNamePattern foo", "--grep foo", "--filter foo",
        "--match foo", "--testNamePattern=foo", "--grep=foo", "--filter=foo", "--match=foo", "a.py::test_old",
        "test_old",
    ])
    def test_rewrite_refuses_a_renamed_test_whose_command_selects_tests(extra):
        got = break_it._rewrite_command("python -m pytest a.py " + extra, "a.py", "b.py", [("test_old", "test_new")])
>       assert got == (None, "command-selects-tests")
E       AssertionError: assert ('python -m p...ep foo', None) == (None, 'comma...elects-tests')
E         
E         At index 0 diff: 'python -m pytest b.py --grep foo' != None
E         Use -v to get more diff

/path/to/home/.superheroes-worktrees/superheroes/issue-2053-wo-a/plugins/superheroes/lib/tests/test_break_it_body_2053.py:564: AssertionError
_ test_rewrite_refuses_a_renamed_test_whose_command_selects_tests[--filter foo] _

extra = '--filter foo'

    @pytest.mark.parametrize("extra", [
        "-k foo", "-t foo", "-g foo", "-kfoo", "-tfoo", "-gfoo", "--testNamePattern foo", "--grep foo", "--filter foo",
        "--match foo", "--testNamePattern=foo", "--grep=foo", "--filter=foo", "--match=foo", "a.py::test_old",
        "test_old",
    ])
    def test_rewrite_refuses_a_renamed_test_whose_command_selects_tests(extra):
        got = break_it._rewrite_command("python -m pytest a.py " + extra, "a.py", "b.py", [("test_old", "test_new")])
>       assert got == (None, "command-selects-tests")
E       AssertionError: assert ('python -m p...er foo', None) == (None, 'comma...elects-tests')
E         
E         At index 0 diff: 'python -m pytest b.py --filter foo' != None
E         Use -v to get more diff

/path/to/home/.superheroes-worktrees/superheroes/issue-2053-wo-a/plugins/superheroes/lib/tests/test_break_it_body_2053.py:564: AssertionError
_ test_rewrite_refuses_a_renamed_test_whose_command_selects_tests[--match foo] _

extra = '--match foo'

    @pytest.mark.parametrize("extra", [
        "-k foo", "-t foo", "-g foo", "-kfoo", "-tfoo", "-gfoo", "--testNamePattern foo", "--grep foo", "--filter foo",
        "--match foo", "--testNamePattern=foo", "--grep=foo", "--filter=foo", "--match=foo", "a.py::test_old",
        "test_old",
    ])
    def test_rewrite_refuses_a_renamed_test_whose_command_selects_tests(extra):
        got = break_it._rewrite_command("python -m pytest a.py " + extra, "a.py", "b.py", [("test_old", "test_new")])
>       assert got == (None, "command-selects-tests")
E       AssertionError: assert ('python -m p...ch foo', None) == (None, 'comma...elects-tests')
E         
E         At index 0 diff: 'python -m pytest b.py --match foo' != None
E         Use -v to get more diff

/path/to/home/.superheroes-worktrees/superheroes/issue-2053-wo-a/plugins/superheroes/lib/tests/test_break_it_body_2053.py:564: AssertionError
_ test_rewrite_refuses_a_renamed_test_whose_command_selects_tests[--testNamePattern=foo] _

extra = '--testNamePattern=foo'

    @pytest.mark.parametrize("extra", [
        "-k foo", "-t foo", "-g foo", "-kfoo", "-tfoo", "-gfoo", "--testNamePattern foo", "--grep foo", "--filter foo",
        "--match foo", "--testNamePattern=foo", "--grep=foo", "--filter=foo", "--match=foo", "a.py::test_old",
        "test_old",
    ])
    def test_rewrite_refuses_a_renamed_test_whose_command_selects_tests(extra):
        got = break_it._rewrite_command("python -m pytest a.py " + extra, "a.py", "b.py", [("test_old", "test_new")])
>       assert got == (None, "command-selects-tests")
E       AssertionError: assert ('python -m p...rn=foo', None) == (None, 'comma...elects-tests')
E         
E         At index 0 diff: 'python -m pytest b.py --testNamePattern=foo' != None
E         Use -v to get more diff

/path/to/home/.superheroes-worktrees/superheroes/issue-2053-wo-a/plugins/superheroes/lib/tests/test_break_it_body_2053.py:564: AssertionError
_ test_rewrite_refuses_a_renamed_test_whose_command_selects_tests[--grep=foo] __

extra = '--grep=foo'

    @pytest.mark.parametrize("extra", [
        "-k foo", "-t foo", "-g foo", "-kfoo", "-tfoo", "-gfoo", "--testNamePattern foo", "--grep foo", "--filter foo",
        "--match foo", "--testNamePattern=foo", "--grep=foo", "--filter=foo", "--match=foo", "a.py::test_old",
        "test_old",
    ])
    def test_rewrite_refuses_a_renamed_test_whose_command_selects_tests(extra):
        got = break_it._rewrite_command("python -m pytest a.py " + extra, "a.py", "b.py", [("test_old", "test_new")])
>       assert got == (None, "command-selects-tests")
E       AssertionError: assert ('python -m p...ep=foo', None) == (None, 'comma...elects-tests')
E         
E         At index 0 diff: 'python -m pytest b.py --grep=foo' != None
E         Use -v to get more diff

/path/to/home/.superheroes-worktrees/superheroes/issue-2053-wo-a/plugins/superheroes/lib/tests/test_break_it_body_2053.py:564: AssertionError
_ test_rewrite_refuses_a_renamed_test_whose_command_selects_tests[--filter=foo] _

extra = '--filter=foo'

    @pytest.mark.parametrize("extra", [
        "-k foo", "-t foo", "-g foo", "-kfoo", "-tfoo", "-gfoo", "--testNamePattern foo", "--grep foo", "--filter foo",
        "--match foo", "--testNamePattern=foo", "--grep=foo", "--filter=foo", "--match=foo", "a.py::test_old",
        "test_old",
    ])
    def test_rewrite_refuses_a_renamed_test_whose_command_selects_tests(extra):
        got = break_it._rewrite_command("python -m pytest a.py " + extra, "a.py", "b.py", [("test_old", "test_new")])
>       assert got == (None, "command-selects-tests")
E       AssertionError: assert ('python -m p...er=foo', None) == (None, 'comma...elects-tests')
E         
E         At index 0 diff: 'python -m pytest b.py --filter=foo' != None
E         Use -v to get more diff

/path/to/home/.superheroes-worktrees/superheroes/issue-2053-wo-a/plugins/superheroes/lib/tests/test_break_it_body_2053.py:564: AssertionError
_ test_rewrite_refuses_a_renamed_test_whose_command_selects_tests[--match=foo] _

extra = '--match=foo'

    @pytest.mark.parametrize("extra", [
        "-k foo", "-t foo", "-g foo", "-kfoo", "-tfoo", "-gfoo", "--testNamePattern foo", "--grep foo", "--filter foo",
        "--match foo", "--testNamePattern=foo", "--grep=foo", "--filter=foo", "--match=foo", "a.py::test_old",
        "test_old",
    ])
    def test_rewrite_refuses_a_renamed_test_whose_command_selects_tests(extra):
        got = break_it._rewrite_command("python -m pytest a.py " + extra, "a.py", "b.py", [("test_old", "test_new")])
>       assert got == (None, "command-selects-tests")
E       AssertionError: assert ('python -m p...ch=foo', None) == (None, 'comma...elects-tests')
E         
E         At index 0 diff: 'python -m pytest b.py --match=foo' != None
E         Use -v to get more diff

/path/to/home/.superheroes-worktrees/superheroes/issue-2053-wo-a/plugins/superheroes/lib/tests/test_break_it_body_2053.py:564: AssertionError
_ test_rewrite_refuses_a_renamed_test_whose_command_selects_tests[a.py::test_old] _

extra = 'a.py::test_old'

    @pytest.mark.parametrize("extra", [
        "-k foo", "-t foo", "-g foo", "-kfoo", "-tfoo", "-gfoo", "--testNamePattern foo", "--grep foo", "--filter foo",
        "--match foo", "--testNamePattern=foo", "--grep=foo", "--filter=foo", "--match=foo", "a.py::test_old",
        "test_old",
    ])
    def test_rewrite_refuses_a_renamed_test_whose_command_selects_tests(extra):
        got = break_it._rewrite_command("python -m pytest a.py " + extra, "a.py", "b.py", [("test_old", "test_new")])
>       assert got == (None, "command-selects-tests")
E       AssertionError: assert ('python -m p...y b.py', None) == (None, 'comma...elects-tests')
E         
E         At index 0 diff: 'python -m pytest b.py b.py' != None
E         Use -v to get more diff

/path/to/home/.superheroes-worktrees/superheroes/issue-2053-wo-a/plugins/superheroes/lib/tests/test_break_it_body_2053.py:564: AssertionError
__ test_rewrite_refuses_a_renamed_test_whose_command_selects_tests[test_old] ___

extra = 'test_old'

    @pytest.mark.parametrize("extra", [
        "-k foo", "-t foo", "-g foo", "-kfoo", "-tfoo", "-gfoo", "--testNamePattern foo", "--grep foo", "--filter foo",
        "--match foo", "--testNamePattern=foo", "--grep=foo", "--filter=foo", "--match=foo", "a.py::test_old",
        "test_old",
    ])
    def test_rewrite_refuses_a_renamed_test_whose_command_selects_tests(extra):
        got = break_it._rewrite_command("python -m pytest a.py " + extra, "a.py", "b.py", [("test_old", "test_new")])
>       assert got == (None, "command-selects-tests")
E       AssertionError: assert ('python -m p...st_old', None) == (None, 'comma...elects-tests')
E         
E         At index 0 diff: 'python -m pytest b.py test_old' != None
E         Use -v to get more diff

/path/to/home/.superheroes-worktrees/superheroes/issue-2053-wo-a/plugins/superheroes/lib/tests/test_break_it_body_2053.py:564: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_a_renamed_moved_test_whose_command_carries_k_is_command_selects_tests
FAILED plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_a_renamed_test_at_its_own_path_with_a_selector_is_command_selects_tests
FAILED plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_rewrite_refuses_a_renamed_test_whose_command_selects_tests[-k foo]
FAILED plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_rewrite_refuses_a_renamed_test_whose_command_selects_tests[-t foo]
FAILED plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_rewrite_refuses_a_renamed_test_whose_command_selects_tests[-g foo]
FAILED plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_rewrite_refuses_a_renamed_test_whose_command_selects_tests[-kfoo]
FAILED plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_rewrite_refuses_a_renamed_test_whose_command_selects_tests[-tfoo]
FAILED plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_rewrite_refuses_a_renamed_test_whose_command_selects_tests[-gfoo]
FAILED plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_rewrite_refuses_a_renamed_test_whose_command_selects_tests[--testNamePattern foo]
FAILED plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_rewrite_refuses_a_renamed_test_whose_command_selects_tests[--grep foo]
FAILED plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_rewrite_refuses_a_renamed_test_whose_command_selects_tests[--filter foo]
FAILED plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_rewrite_refuses_a_renamed_test_whose_command_selects_tests[--match foo]
FAILED plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_rewrite_refuses_a_renamed_test_whose_command_selects_tests[--testNamePattern=foo]
FAILED plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_rewrite_refuses_a_renamed_test_whose_command_selects_tests[--grep=foo]
FAILED plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_rewrite_refuses_a_renamed_test_whose_command_selects_tests[--filter=foo]
FAILED plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_rewrite_refuses_a_renamed_test_whose_command_selects_tests[--match=foo]
FAILED plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_rewrite_refuses_a_renamed_test_whose_command_selects_tests[a.py::test_old]
FAILED plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_rewrite_refuses_a_renamed_test_whose_command_selects_tests[test_old]
18 failed in 0.52s
pytest exit: 1
```

**restore:** the inverse edit on `plugins/superheroes/lib/break_it.py` (`if False and titles and any(_selects_tests(` back to `if titles and any(_selects_tests(`).

**restore receipt** (`git diff --stat` over the file, printed nothing):
```
--- git diff --stat (break_it.py):
--- end diff
```

**raw green** (exit 0), same command:
```
..................                                                       [100%]
18 passed in 0.56s
pytest exit: 0
```

---

## E9: `_rewrite_command`'s same-path unchanged-command branch

- **axis:** a test found at its own path runs the command exactly as the loop ran it (the original bytes)

**neutralization** (`plugins/superheroes/lib/break_it.py`, `_rewrite_command`; the same-path case then falls through to the token-rebuilding path):
```diff
-    if new_path == old_path:
+    if False and new_path == old_path:
```

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_formatter_case_is_kept_by_body_and_runs_the_original_command_byte_for_byte plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_rewrite_same_path_returns_the_original_string -q
```

**raw red** (exit 1):
```
FF                                                                       [100%]
=================================== FAILURES ===================================
_ test_formatter_case_is_kept_by_body_and_runs_the_original_command_byte_for_byte _

repo = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-251/test_formatter_case_is_kept_by0/repo')

    def test_formatter_case_is_kept_by_body_and_runs_the_original_command_byte_for_byte(repo):
        base, head = _stage(repo, {OWN: FORMATTED})
        # Doubled spaces and a quoted path: a command rebuilt from its tokens would not be these bytes.
        command = "%s  -m pytest -p no:cacheprovider -q  '%s'" % (PY, OWN)
        calls = []
        result = _check(repo, base, head, _record(command=command), _spy(calls))
        assert _got(result) == ("kept", "body-match")
        assert result["run"]["outcome"] == "passed"
        assert result["path"] == OWN
>       assert [c["run"] for c in calls] == [command]
E       assert ['/path/to/...ts/test_k.py'] == ["/path/to/...s/test_k.py'"]
E         
E         At index 0 diff: '/path/to/home/.cache/uv/builds-v0/.tmpzF9R5D/bin/python -m pytest -p no:cacheprovider -q tests/test_k.py' != "/path/to/home/.cache/uv/builds-v0/.tmpzF9R5D/bin/python  -m pytest -p no:cacheprovider -q  'tests/test_k.py'"
E         Use -v to get more diff

/path/to/home/.superheroes-worktrees/superheroes/issue-2053-wo-a/plugins/superheroes/lib/tests/test_break_it_body_2053.py:160: AssertionError
______________ test_rewrite_same_path_returns_the_original_string ______________

    def test_rewrite_same_path_returns_the_original_string():
        command = "FOO=1   python  'a.py'"
>       assert break_it._rewrite_command(command, "a.py", "a.py", []) == (command, None)
E       assert ('FOO=1 python a.py', None) == ("FOO=1   pyt...'a.py'", None)
E         
E         At index 0 diff: 'FOO=1 python a.py' != "FOO=1   python  'a.py'"
E         Use -v to get more diff

/path/to/home/.superheroes-worktrees/superheroes/issue-2053-wo-a/plugins/superheroes/lib/tests/test_break_it_body_2053.py:504: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_formatter_case_is_kept_by_body_and_runs_the_original_command_byte_for_byte
FAILED plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_rewrite_same_path_returns_the_original_string
2 failed in 0.99s
pytest exit: 1
```

**restore:** the inverse edit on `plugins/superheroes/lib/break_it.py` (`if False and new_path == old_path:` back to `if new_path == old_path:`).

**restore receipt** (`git diff --stat` over the file, printed nothing):
```
--- git diff --stat (break_it.py):
--- end diff
```

**raw green** (exit 0), same command:
```
..                                                                       [100%]
2 passed in 0.85s
pytest exit: 0
```

---

## E10: the `content`-absent fallback

- **axis:** a record without string content never searches, so it keeps the byte-exact check

**neutralization** (`plugins/superheroes/lib/break_it.py`, `check_kept.searched`):
```diff
-        if not isinstance(record.get("content"), str):
+        if False and not isinstance(record.get("content"), str):
```

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_a_record_without_content_keeps_the_byte_exact_check plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_a_record_whose_content_is_not_a_string_keeps_the_byte_exact_check -q
```

**raw red** (exit 1; the absent-key record reaches `locate` and raises `KeyError: 'content'`, the `None` record is searched and reads `body-unparseable`):
```
FF                                                                       [100%]
=================================== FAILURES ===================================
___________ test_a_record_without_content_keeps_the_byte_exact_check ___________

repo = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-253/test_a_record_without_content_0/repo')

    def test_a_record_without_content_keeps_the_byte_exact_check(repo):
        base, head = _stage(repo, {OWN: FORMATTED})
        record = _record()
        del record["content"]
        calls = []
>       assert _got(_check(repo, base, head, record, _stub(calls))) == ("changed", "sha256-differs")
                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

/path/to/home/.superheroes-worktrees/superheroes/issue-2053-wo-a/plugins/superheroes/lib/tests/test_break_it_body_2053.py:443: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/path/to/home/.superheroes-worktrees/superheroes/issue-2053-wo-a/plugins/superheroes/lib/tests/test_break_it_body_2053.py:146: in _check
    return break_it.check_kept(str(repo), base, head, record, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/path/to/home/.superheroes-worktrees/superheroes/issue-2053-wo-a/plugins/superheroes/lib/break_it.py:1085: in check_kept
    return searched(res(KEPT_CHANGED, "sha256-differs"))
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/path/to/home/.superheroes-worktrees/superheroes/issue-2053-wo-a/plugins/superheroes/lib/break_it.py:1055: in searched
    return _body_search(repo_root, base, head, record, today, res, runner, interpreter)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

repo_root = '/private/tmp/claude-501/pytest-of-zwrose/pytest-253/test_a_record_without_content_0/repo'
base = 'ff40b23508a46fde3456ddf4a59d01ccc193028a'
head = 'f3b3af9e841c6f5a1a529f67cfd8576560efa7fc'
record = {'path': 'tests/test_k.py', 'command': '/path/to/home/.cache/uv/builds-v0/.tmpQpMNpL/bin/python -m pytest -p no:cacheprovider -q tests/test_k.py', 'sha256': 'fbc140aeb96b17c46a0bf5f3cdecc0f50efa4d27bf2145655f6210d9e829771f'}
today = {'path': 'tests/test_k.py', 'outcome': 'changed', 'reason': 'sha256-differs', 'run': None}
res = <function check_kept.<locals>.res at 0x1075b3420>
runner = <function _stub.<locals>.runner at 0x1075b31a0>
interpreter = <object object at 0x1066118f0>

    def _body_search(repo_root, base, head, record, today, res, runner, interpreter):
        """The body search behind the three rows that read the test missing or changed: ``today`` unless the test is
        found, unchanged up to formatting and its title, once among the files the final diff carries."""
        # imported late: break_it's import closure is pinned (test_payload_contracts_layering)
        from break_it_body import locate, supported_suffixes
        suffixes = supported_suffixes()
        if posixpath.splitext(record["path"].lower())[1] not in suffixes:
            return today
        try:
            diff = _git(repo_root, "diff", "--name-only", "-z", base + "..." + head)
            if diff.returncode != 0:
                return res(KEPT_UNRESOLVED, "diff-failed")
            candidates = []
            for name in diff.stdout.decode("utf-8", errors="surrogateescape").split("\0"):
                if not name or posixpath.splitext(name.lower())[1] not in suffixes or _path_unsafe(name):
                    continue
                tree = _git(repo_root, "ls-tree", "-z", head, "--", name)
                if tree.returncode != 0:
                    return res(KEPT_UNRESOLVED, "ls-tree-failed")
                meta = tree.stdout.decode("utf-8", errors="replace").split("\0", 1)[0].partition("\t")[0].split()
                if len(meta) != 3 or meta[0] not in _REGULAR_MODES or meta[1] != "blob":
                    continue
                blob = _git(repo_root, "cat-file", "blob", meta[2])
                if blob.returncode != 0:
                    return res(KEPT_UNRESOLVED, "cat-file-failed")
                try:
                    text = blob.stdout.decode("utf-8")
                except UnicodeDecodeError:
                    text = None
                candidates.append((name, text))
        except (OSError, subprocess.TimeoutExpired):
            return res(KEPT_UNRESOLVED, "git-failed")
>       found = locate(record["content"], record["path"], candidates)
                       ^^^^^^^^^^^^^^^^^
E       KeyError: 'content'

/path/to/home/.superheroes-worktrees/superheroes/issue-2053-wo-a/plugins/superheroes/lib/break_it.py:1026: KeyError
____ test_a_record_whose_content_is_not_a_string_keeps_the_byte_exact_check ____

repo = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-253/test_a_record_whose_content_is0/repo')

    def test_a_record_whose_content_is_not_a_string_keeps_the_byte_exact_check(repo):
        base, head = _stage(repo, {OWN: FORMATTED})
        record = _record()
        record["content"] = None
>       assert _got(_check(repo, base, head, record)) == ("changed", "sha256-differs")
E       AssertionError: assert ('unresolved'...-unparseable') == ('changed', 'sha256-differs')
E         
E         At index 0 diff: 'unresolved' != 'changed'
E         Use -v to get more diff

/path/to/home/.superheroes-worktrees/superheroes/issue-2053-wo-a/plugins/superheroes/lib/tests/test_break_it_body_2053.py:454: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_a_record_without_content_keeps_the_byte_exact_check
FAILED plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_a_record_whose_content_is_not_a_string_keeps_the_byte_exact_check
2 failed in 0.87s
pytest exit: 1
```

**restore:** the inverse edit on `plugins/superheroes/lib/break_it.py` (`if False and not isinstance(record.get("content"), str):` back to `if not isinstance(record.get("content"), str):`).

**restore receipt** (`git diff --stat` over the file, printed nothing):
```
--- git diff --stat (break_it.py):
--- end diff
```

**raw green** (exit 0), same command:
```
..                                                                       [100%]
2 passed in 1.01s
pytest exit: 0
```

---

## E11: `_selects_tests`' path-token exemption

- **axis:** a path token is judged by the `::` rule alone, so a test file named after its own test still renames

**neutralization** (`plugins/superheroes/lib/break_it.py`, `_selects_tests`; the path token then falls to the general title-substring rule):
```diff
-    if tok == old_path or tok.startswith(old_path + "::"):
+    if False and (tok == old_path or tok.startswith(old_path + "::")):
```

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_rewrite_a_path_token_that_contains_an_old_title_is_no_filter plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_a_test_file_named_after_its_own_test_is_kept_when_the_test_is_renamed_in_place -q
```

**raw red** (exit 1):
```
FF                                                                       [100%]
=================================== FAILURES ===================================
______ test_rewrite_a_path_token_that_contains_an_old_title_is_no_filter _______

    def test_rewrite_a_path_token_that_contains_an_old_title_is_no_filter():
        titles = [("test_x", "test_y")]
>       assert break_it._rewrite_command("python -m pytest t/test_x.py", "t/test_x.py", "t/test_y.py", titles) == (
            "python -m pytest t/test_y.py", None)
E       AssertionError: assert (None, 'comma...elects-tests') == ('python -m p...t_y.py', None)
E         
E         At index 0 diff: None != 'python -m pytest t/test_y.py'
E         Use -v to get more diff

/path/to/home/.superheroes-worktrees/superheroes/issue-2053-wo-a/plugins/superheroes/lib/tests/test_break_it_body_2053.py:522: AssertionError
_ test_a_test_file_named_after_its_own_test_is_kept_when_the_test_is_renamed_in_place _

repo = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-256/test_a_test_file_named_after_i0/repo')

    def test_a_test_file_named_after_its_own_test_is_kept_when_the_test_is_renamed_in_place(repo):
        path = "tests/test_x.py"
        base, head = _stage(repo, {path: FORMATTED.replace("test_x", "test_y")})
        calls = []
>       assert _got(_check(repo, base, head, _record(path=path), _spy(calls))) == ("kept", "body-match")
E       AssertionError: assert ('unresolved'...elects-tests') == ('kept', 'body-match')
E         
E         At index 0 diff: 'unresolved' != 'kept'
E         Use -v to get more diff

/path/to/home/.superheroes-worktrees/superheroes/issue-2053-wo-a/plugins/superheroes/lib/tests/test_break_it_body_2053.py:540: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_rewrite_a_path_token_that_contains_an_old_title_is_no_filter
FAILED plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_a_test_file_named_after_its_own_test_is_kept_when_the_test_is_renamed_in_place
2 failed in 0.57s
pytest exit: 1
```

**restore:** the inverse edit on `plugins/superheroes/lib/break_it.py` (`if False and (tok == old_path or tok.startswith(old_path + "::")):` back to `if tok == old_path or tok.startswith(old_path + "::"):`).

**restore receipt** (`git diff --stat` over the file, printed nothing; a worktree `git status --porcelain` before the green run printed nothing either):
```
--- git diff --stat (break_it.py):
--- end diff
--- end status
```

**raw green** (exit 0), same command:
```
..                                                                       [100%]
2 passed in 1.56s
pytest exit: 0
```

---

## A4 — closed-world host check

**Provenance:** claude / sonnet-5.5 (implementer, work order A4c), maker family anthropic. Refs #2060. Production under proof: `plugins/superheroes/lib/break_it_body_py.py` (`_allowed_host`, `_plain_assignment`, and the record dict in `_record`, which `parse` returns). Tests: `plugins/superheroes/lib/tests/test_break_it_body_2053.py` (the closed-world section, from `# ---- the closed-world host check (#2060)`).

Declared guarded-element set (from the order): **H1**, **H2**, **H3**, **H4**. Each was neutralized by one targeted edit (the Edit tool, exact-text match), only its proving nodes run by exact node id (never `-k`), the inverse edit applied, `git diff --stat` taken over the file (empty: the file equals the last commit), and the same ids run again. No `git checkout`, `git restore`, `git reset` or `git stash` was used.

### Guarded elements

| ID | Guarded element | Axis | Proving nodes (all in `test_break_it_body_2053.py`) |
|---|---|---|---|
| H1 | `_allowed_host`'s decorator refusal, `break_it_body_py.py:224` (`return not node.decorator_list and not _hook_name(node.name)`) | a decorated module-level def is a hook (a fixture under any spelling or alias), so a host that adds one is refused | `::test_allowed_host_refuses_each_forbidden_shape[decorated-def]`, `[decorated-async-def]`; `::test_core_a_host_that_adds_anything_but_plain_code_is_host_setup[decorated-helper]` |
| H2 | `_allowed_host`'s refusal of module-level control flow, `break_it_body_py.py:230` (`return _docstring(node)`, the fall-through for every statement kind not listed above it) | `if`, `try`, `for`, `while`, `with` and `match` at module level are hooks | `::test_allowed_host_refuses_each_forbidden_shape[if]`, `[try]`, `[for]`, `[while]`, `[with]`, `[match]`; `::test_core_a_host_that_adds_anything_but_plain_code_is_host_setup[if-holding-a-def]` |
| H3 | `_allowed_host`'s refusal of a call in an assigned value, `break_it_body_py.py:200` (`return all(_plain_value(part) for part in value)` in `_plain_assignment`) | an assignment or annotated assignment whose value calls something, at module level or in a class body, is a hook | `::test_allowed_host_refuses_each_forbidden_shape[call-value]`, `[annotated-call]`, `[class-call-assignment]`; `::test_core_a_host_that_adds_anything_but_plain_code_is_host_setup[call-in-assignment]` |
| H4 | the wiring, `break_it_body_py.py:261` (the `"hook": not _allowed_host(node),` entry of the record dict that `parse` returns) | `parse` records a statement as a hook exactly when `_allowed_host` refuses it, so `locate` reads `host-setup` | `::test_front_records_hook_is_the_negation_of_allowed_host`; `::test_core_a_host_that_adds_anything_but_plain_code_is_host_setup[call-statement]`, `[decorated-helper]` |

### Disclosures

- Every element went red under its neutralization (the harness reported `Exit code 1` for each red run) and green after the restore (each green run completed with no error code, exit 0). The command shape is `scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest <exact node ids> -q`, run as a single command, so there is no trailing `echo "pytest exit: $?"` line as in the entries above; the exit codes are the harness's. Everything else is verbatim (default `--tb`, no filter).
- H2's first red run was printed to the session by the harness with 11291 characters cut out of its middle. That output was not reconstructed. With the neutralization still applied, the same seven ids were run once more (a spare run) with the output redirected to a file outside the repository and read back whole; the H2 red below is that second run, and its summary (`7 failed`) matches the visible head and tail of the first. The H3 and H4 reds were captured the same way from the start, to a file outside the repository, read back whole, and pasted unedited. The H1 red is the harness's own printout, untruncated. The greens are the harness's printout.
- Scope of each neutralization: H1 drops only the decorator test on a def (a decorated class is `_plain_class`'s own check, outside this element). H2 lets only the six control-flow statement kinds through; every other forbidden shape stays refused. H3 returns `True` from `_plain_assignment` before the value test, which also lifts the lambda, walrus, comprehension, generator, await and yield refusals; the proving ids are limited to a call in the value, the axis claimed. H4 replaces the entry with a constant `False`, so no statement is ever a hook.
- The tests' parametrized forms print their full `@pytest.mark.parametrize` decorator block above each failing assertion; it is shown as printed, once per failing id.
- Redaction: none needed; local `/path/to/home/...` paths are kept as printed, no secret, token or private URL appears.
- Test commands: 10 of the 12 budgeted (H1: 2, H2: 3 including the one re-run, H3: 2, H4: 2, and the final run of the whole file). All captures are under 32 KiB each and under 128 KiB together, so none is written off-repo as an overflow. The final run of the file:

```
bringing up nodes...
bringing up nodes...

........................................................................ [ 34%]
........................................................................ [ 69%]
................................................................         [100%]
208 passed in 19.71s
```

---

### H1: the decorator refusal

- **axis:** a decorated module-level def is a hook (a fixture under any spelling or alias), so a host that adds one is refused

**neutralization** (`plugins/superheroes/lib/break_it_body_py.py`, `_allowed_host`):
```diff
-        return not node.decorator_list and not _hook_name(node.name)
+        return not _hook_name(node.name)
```

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest "plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_allowed_host_refuses_each_forbidden_shape[decorated-def]" "plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_allowed_host_refuses_each_forbidden_shape[decorated-async-def]" "plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_core_a_host_that_adds_anything_but_plain_code_is_host_setup[decorated-helper]" -q
```

**raw red** (exit 1):
```
FFF                                                                      [100%]
=================================== FAILURES ===================================
________ test_allowed_host_refuses_each_forbidden_shape[decorated-def] _________

text = '@pytest.fixture\ndef f():\n    pass\n'

    @pytest.mark.parametrize("text", [
        "@pytest.fixture\ndef f():\n    pass\n",
        "@fx(autouse=True)\nasync def f():\n    pass\n",
        "def pytest_generate_tests(metafunc):\n    pass\n",
        "def pytestmark():\n    pass\n",
        "def setup_module():\n    pass\n",
        "def setUpModule():\n    pass\n",
        "def tearDownModule():\n    pass\n",
        "def load_tests(loader, tests, pattern):\n    pass\n",
        "@register\nclass K:\n    pass\n",
        "class K:\n    global g\n    g = 1\n",
        "class K:\n    def f(self):\n        nonlocal_ = 1\n\n    class Inner:\n        @property\n        def p(self):\n            return 1\n",
        "class K(make()):\n    pass\n",
        "class K(metaclass=make()):\n    pass\n",
        "class K:\n    register()\n",
        "class K:\n    if c:\n        x = 1\n",
        "class K:\n    x = f()\n",
        "class K:\n    pytestmark = 1\n",
        "class K:\n    x += 1\n",
        "PYTESTMARK = 1\n",
        "pytestmark = 1\n",
        "pytest_plugins = ['x']\n",
        "setup_module = other\n",
        "__unittest_skip__ = True\n",
        "A.b = 1\n",
        "x, y = 1, 2\n",
        "x = f()\n",
        "x = lambda: 1\n",
        "x = (y := 1)\n",
        "x = [i for i in range(3)]\n",
        "x = {i for i in ()}\n",
        "x = (i for i in ())\n",
        "x: int = f()\n",
        "if c:\n    x = 1\n",
        "try:\n    x = 1\nexcept E:\n    pass\n",
        "for i in v:\n    pass\n",
        "while c:\n    pass\n",
        "with c:\n    pass\n",
        "match c:\n    case 1:\n        pass\n",
        "f()\n",
        "'a' + 'b'\n",
        "x += 1\n",
        "global g\n",
        "del x\n",
        "assert x\n",
        "raise E\n",
    ], ids=["decorated-def", "decorated-async-def", "pytest-hook-def", "pytestmark-def", "setup-def", "setUpModule-def", "tearDownModule-def",
            "load_tests-def", "decorated-class", "class-global", "class-nested-decorator", "class-call-base",
            "class-call-keyword", "class-call-statement", "class-if-body", "class-call-assignment",
            "class-pytest-assign", "class-augassign", "pytestmark-upper", "pytestmark", "pytest_plugins",
            "setup-assign", "dunder-assign", "attribute-target", "tuple-target", "call-value", "lambda-value",
            "walrus-value", "listcomp-value", "setcomp-value", "generator-value", "annotated-call", "if", "try", "for",
            "while", "with", "match", "call-statement", "non-docstring-expr", "augassign", "global", "del", "assert",
            "raise"])
    def test_allowed_host_refuses_each_forbidden_shape(text):
>       assert not front._allowed_host(ast.parse(text).body[0])
E       assert not True
E        +  where True = <function _allowed_host at 0x105de2480>(<ast.FunctionDef object at 0x104ead410>)
E        +    where <function _allowed_host at 0x105de2480> = front._allowed_host

/path/to/home/.superheroes-worktrees/superheroes/issue-2053-a5acd47bf4fc84b7/plugins/superheroes/lib/tests/test_break_it_body_2053.py:1007: AssertionError
_____ test_allowed_host_refuses_each_forbidden_shape[decorated-async-def] ______

text = '@fx(autouse=True)\nasync def f():\n    pass\n'

    @pytest.mark.parametrize("text", [
        "@pytest.fixture\ndef f():\n    pass\n",
        "@fx(autouse=True)\nasync def f():\n    pass\n",
        "def pytest_generate_tests(metafunc):\n    pass\n",
        "def pytestmark():\n    pass\n",
        "def setup_module():\n    pass\n",
        "def setUpModule():\n    pass\n",
        "def tearDownModule():\n    pass\n",
        "def load_tests(loader, tests, pattern):\n    pass\n",
        "@register\nclass K:\n    pass\n",
        "class K:\n    global g\n    g = 1\n",
        "class K:\n    def f(self):\n        nonlocal_ = 1\n\n    class Inner:\n        @property\n        def p(self):\n            return 1\n",
        "class K(make()):\n    pass\n",
        "class K(metaclass=make()):\n    pass\n",
        "class K:\n    register()\n",
        "class K:\n    if c:\n        x = 1\n",
        "class K:\n    x = f()\n",
        "class K:\n    pytestmark = 1\n",
        "class K:\n    x += 1\n",
        "PYTESTMARK = 1\n",
        "pytestmark = 1\n",
        "pytest_plugins = ['x']\n",
        "setup_module = other\n",
        "__unittest_skip__ = True\n",
        "A.b = 1\n",
        "x, y = 1, 2\n",
        "x = f()\n",
        "x = lambda: 1\n",
        "x = (y := 1)\n",
        "x = [i for i in range(3)]\n",
        "x = {i for i in ()}\n",
        "x = (i for i in ())\n",
        "x: int = f()\n",
        "if c:\n    x = 1\n",
        "try:\n    x = 1\nexcept E:\n    pass\n",
        "for i in v:\n    pass\n",
        "while c:\n    pass\n",
        "with c:\n    pass\n",
        "match c:\n    case 1:\n        pass\n",
        "f()\n",
        "'a' + 'b'\n",
        "x += 1\n",
        "global g\n",
        "del x\n",
        "assert x\n",
        "raise E\n",
    ], ids=["decorated-def", "decorated-async-def", "pytest-hook-def", "pytestmark-def", "setup-def", "setUpModule-def", "tearDownModule-def",
            "load_tests-def", "decorated-class", "class-global", "class-nested-decorator", "class-call-base",
            "class-call-keyword", "class-call-statement", "class-if-body", "class-call-assignment",
            "class-pytest-assign", "class-augassign", "pytestmark-upper", "pytestmark", "pytest_plugins",
            "setup-assign", "dunder-assign", "attribute-target", "tuple-target", "call-value", "lambda-value",
            "walrus-value", "listcomp-value", "setcomp-value", "generator-value", "annotated-call", "if", "try", "for",
            "while", "with", "match", "call-statement", "non-docstring-expr", "augassign", "global", "del", "assert",
            "raise"])
    def test_allowed_host_refuses_each_forbidden_shape(text):
>       assert not front._allowed_host(ast.parse(text).body[0])
E       assert not True
E        +  where True = <function _allowed_host at 0x105de2480>(<ast.AsyncFunctionDef object at 0x104c43490>)
E        +    where <function _allowed_host at 0x105de2480> = front._allowed_host

/path/to/home/.superheroes-worktrees/superheroes/issue-2053-a5acd47bf4fc84b7/plugins/superheroes/lib/tests/test_break_it_body_2053.py:1007: AssertionError
_ test_core_a_host_that_adds_anything_but_plain_code_is_host_setup[decorated-helper] _

extra = '@functools.lru_cache\ndef helper():\n    return 1\n'

    @pytest.mark.parametrize("extra", [
        "if True:\n    def helper():\n        return 1\n",
        "setup_things()\n",
        "@functools.lru_cache\ndef helper():\n    return 1\n",
        "COUNT += 1\n",
        "CONFIG = load()\n",
    ], ids=["if-holding-a-def", "call-statement", "decorated-helper", "augassign", "call-in-assignment"])
    def test_core_a_host_that_adds_anything_but_plain_code_is_host_setup(extra):
        got = break_it_body.locate(_V, "a.py", [("b.py", _V + "\n\n" + extra)])
>       assert (got["status"], got["reason"]) == ("unresolved", "host-setup")
E       AssertionError: assert ('found', None) == ('unresolved', 'host-setup')
E         
E         At index 0 diff: 'found' != 'unresolved'
E         Use -v to get more diff

/path/to/home/.superheroes-worktrees/superheroes/issue-2053-a5acd47bf4fc84b7/plugins/superheroes/lib/tests/test_break_it_body_2053.py:919: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_allowed_host_refuses_each_forbidden_shape[decorated-def]
FAILED plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_allowed_host_refuses_each_forbidden_shape[decorated-async-def]
FAILED plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_core_a_host_that_adds_anything_but_plain_code_is_host_setup[decorated-helper]
3 failed in 1.40s
```

**restore:** the inverse edit on `plugins/superheroes/lib/break_it_body_py.py` (`return not _hook_name(node.name)` back to `return not node.decorator_list and not _hook_name(node.name)`).

**restore receipt** (`git diff --stat -- plugins/superheroes/lib/break_it_body_py.py` printed nothing, so the file equals its last commit; the restored line, quoted back from `_allowed_host`):
```
        return not node.decorator_list and not _hook_name(node.name)
```

**raw green** (exit 0), same command:
```
...                                                                      [100%]
3 passed in 1.24s
```

---

### H2: the refusal of module-level control flow

- **axis:** `if`, `try`, `for`, `while`, `with` and `match` at module level are hooks, so a host that adds one is refused

**neutralization** (`plugins/superheroes/lib/break_it_body_py.py`, `_allowed_host`, the fall-through return; the edit's match text included the following blank lines and `def _normalise` to be unique):
```diff
-    return _docstring(node)
+    return _docstring(node) or isinstance(node, (ast.If, ast.For, ast.While, ast.With, ast.Try, ast.Match))
```

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest "plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_allowed_host_refuses_each_forbidden_shape[if]" "plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_allowed_host_refuses_each_forbidden_shape[try]" "plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_allowed_host_refuses_each_forbidden_shape[for]" "plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_allowed_host_refuses_each_forbidden_shape[while]" "plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_allowed_host_refuses_each_forbidden_shape[with]" "plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_allowed_host_refuses_each_forbidden_shape[match]" "plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_core_a_host_that_adds_anything_but_plain_code_is_host_setup[if-holding-a-def]" -q
```

**raw red** (exit 1; the second run of this command, see the disclosures):
```
FFFFFFF                                                                  [100%]
=================================== FAILURES ===================================
______________ test_allowed_host_refuses_each_forbidden_shape[if] ______________

text = 'if c:\n    x = 1\n'

    @pytest.mark.parametrize("text", [
        "@pytest.fixture\ndef f():\n    pass\n",
        "@fx(autouse=True)\nasync def f():\n    pass\n",
        "def pytest_generate_tests(metafunc):\n    pass\n",
        "def pytestmark():\n    pass\n",
        "def setup_module():\n    pass\n",
        "def setUpModule():\n    pass\n",
        "def tearDownModule():\n    pass\n",
        "def load_tests(loader, tests, pattern):\n    pass\n",
        "@register\nclass K:\n    pass\n",
        "class K:\n    global g\n    g = 1\n",
        "class K:\n    def f(self):\n        nonlocal_ = 1\n\n    class Inner:\n        @property\n        def p(self):\n            return 1\n",
        "class K(make()):\n    pass\n",
        "class K(metaclass=make()):\n    pass\n",
        "class K:\n    register()\n",
        "class K:\n    if c:\n        x = 1\n",
        "class K:\n    x = f()\n",
        "class K:\n    pytestmark = 1\n",
        "class K:\n    x += 1\n",
        "PYTESTMARK = 1\n",
        "pytestmark = 1\n",
        "pytest_plugins = ['x']\n",
        "setup_module = other\n",
        "__unittest_skip__ = True\n",
        "A.b = 1\n",
        "x, y = 1, 2\n",
        "x = f()\n",
        "x = lambda: 1\n",
        "x = (y := 1)\n",
        "x = [i for i in range(3)]\n",
        "x = {i for i in ()}\n",
        "x = (i for i in ())\n",
        "x: int = f()\n",
        "if c:\n    x = 1\n",
        "try:\n    x = 1\nexcept E:\n    pass\n",
        "for i in v:\n    pass\n",
        "while c:\n    pass\n",
        "with c:\n    pass\n",
        "match c:\n    case 1:\n        pass\n",
        "f()\n",
        "'a' + 'b'\n",
        "x += 1\n",
        "global g\n",
        "del x\n",
        "assert x\n",
        "raise E\n",
    ], ids=["decorated-def", "decorated-async-def", "pytest-hook-def", "pytestmark-def", "setup-def", "setUpModule-def", "tearDownModule-def",
            "load_tests-def", "decorated-class", "class-global", "class-nested-decorator", "class-call-base",
            "class-call-keyword", "class-call-statement", "class-if-body", "class-call-assignment",
            "class-pytest-assign", "class-augassign", "pytestmark-upper", "pytestmark", "pytest_plugins",
            "setup-assign", "dunder-assign", "attribute-target", "tuple-target", "call-value", "lambda-value",
            "walrus-value", "listcomp-value", "setcomp-value", "generator-value", "annotated-call", "if", "try", "for",
            "while", "with", "match", "call-statement", "non-docstring-expr", "augassign", "global", "del", "assert",
            "raise"])
    def test_allowed_host_refuses_each_forbidden_shape(text):
>       assert not front._allowed_host(ast.parse(text).body[0])
E       assert not True
E        +  where True = <function _allowed_host at 0x107d87560>(<ast.If object at 0x107cefb90>)
E        +    where <function _allowed_host at 0x107d87560> = front._allowed_host

/path/to/home/.superheroes-worktrees/superheroes/issue-2053-a5acd47bf4fc84b7/plugins/superheroes/lib/tests/test_break_it_body_2053.py:1007: AssertionError
_____________ test_allowed_host_refuses_each_forbidden_shape[try] ______________

text = 'try:\n    x = 1\nexcept E:\n    pass\n'

    @pytest.mark.parametrize("text", [
        "@pytest.fixture\ndef f():\n    pass\n",
        "@fx(autouse=True)\nasync def f():\n    pass\n",
        "def pytest_generate_tests(metafunc):\n    pass\n",
        "def pytestmark():\n    pass\n",
        "def setup_module():\n    pass\n",
        "def setUpModule():\n    pass\n",
        "def tearDownModule():\n    pass\n",
        "def load_tests(loader, tests, pattern):\n    pass\n",
        "@register\nclass K:\n    pass\n",
        "class K:\n    global g\n    g = 1\n",
        "class K:\n    def f(self):\n        nonlocal_ = 1\n\n    class Inner:\n        @property\n        def p(self):\n            return 1\n",
        "class K(make()):\n    pass\n",
        "class K(metaclass=make()):\n    pass\n",
        "class K:\n    register()\n",
        "class K:\n    if c:\n        x = 1\n",
        "class K:\n    x = f()\n",
        "class K:\n    pytestmark = 1\n",
        "class K:\n    x += 1\n",
        "PYTESTMARK = 1\n",
        "pytestmark = 1\n",
        "pytest_plugins = ['x']\n",
        "setup_module = other\n",
        "__unittest_skip__ = True\n",
        "A.b = 1\n",
        "x, y = 1, 2\n",
        "x = f()\n",
        "x = lambda: 1\n",
        "x = (y := 1)\n",
        "x = [i for i in range(3)]\n",
        "x = {i for i in ()}\n",
        "x = (i for i in ())\n",
        "x: int = f()\n",
        "if c:\n    x = 1\n",
        "try:\n    x = 1\nexcept E:\n    pass\n",
        "for i in v:\n    pass\n",
        "while c:\n    pass\n",
        "with c:\n    pass\n",
        "match c:\n    case 1:\n        pass\n",
        "f()\n",
        "'a' + 'b'\n",
        "x += 1\n",
        "global g\n",
        "del x\n",
        "assert x\n",
        "raise E\n",
    ], ids=["decorated-def", "decorated-async-def", "pytest-hook-def", "pytestmark-def", "setup-def", "setUpModule-def", "tearDownModule-def",
            "load_tests-def", "decorated-class", "class-global", "class-nested-decorator", "class-call-base",
            "class-call-keyword", "class-call-statement", "class-if-body", "class-call-assignment",
            "class-pytest-assign", "class-augassign", "pytestmark-upper", "pytestmark", "pytest_plugins",
            "setup-assign", "dunder-assign", "attribute-target", "tuple-target", "call-value", "lambda-value",
            "walrus-value", "listcomp-value", "setcomp-value", "generator-value", "annotated-call", "if", "try", "for",
            "while", "with", "match", "call-statement", "non-docstring-expr", "augassign", "global", "del", "assert",
            "raise"])
    def test_allowed_host_refuses_each_forbidden_shape(text):
>       assert not front._allowed_host(ast.parse(text).body[0])
E       assert not True
E        +  where True = <function _allowed_host at 0x107d87560>(<ast.Try object at 0x107c02910>)
E        +    where <function _allowed_host at 0x107d87560> = front._allowed_host

/path/to/home/.superheroes-worktrees/superheroes/issue-2053-a5acd47bf4fc84b7/plugins/superheroes/lib/tests/test_break_it_body_2053.py:1007: AssertionError
_____________ test_allowed_host_refuses_each_forbidden_shape[for] ______________

text = 'for i in v:\n    pass\n'

    @pytest.mark.parametrize("text", [
        "@pytest.fixture\ndef f():\n    pass\n",
        "@fx(autouse=True)\nasync def f():\n    pass\n",
        "def pytest_generate_tests(metafunc):\n    pass\n",
        "def pytestmark():\n    pass\n",
        "def setup_module():\n    pass\n",
        "def setUpModule():\n    pass\n",
        "def tearDownModule():\n    pass\n",
        "def load_tests(loader, tests, pattern):\n    pass\n",
        "@register\nclass K:\n    pass\n",
        "class K:\n    global g\n    g = 1\n",
        "class K:\n    def f(self):\n        nonlocal_ = 1\n\n    class Inner:\n        @property\n        def p(self):\n            return 1\n",
        "class K(make()):\n    pass\n",
        "class K(metaclass=make()):\n    pass\n",
        "class K:\n    register()\n",
        "class K:\n    if c:\n        x = 1\n",
        "class K:\n    x = f()\n",
        "class K:\n    pytestmark = 1\n",
        "class K:\n    x += 1\n",
        "PYTESTMARK = 1\n",
        "pytestmark = 1\n",
        "pytest_plugins = ['x']\n",
        "setup_module = other\n",
        "__unittest_skip__ = True\n",
        "A.b = 1\n",
        "x, y = 1, 2\n",
        "x = f()\n",
        "x = lambda: 1\n",
        "x = (y := 1)\n",
        "x = [i for i in range(3)]\n",
        "x = {i for i in ()}\n",
        "x = (i for i in ())\n",
        "x: int = f()\n",
        "if c:\n    x = 1\n",
        "try:\n    x = 1\nexcept E:\n    pass\n",
        "for i in v:\n    pass\n",
        "while c:\n    pass\n",
        "with c:\n    pass\n",
        "match c:\n    case 1:\n        pass\n",
        "f()\n",
        "'a' + 'b'\n",
        "x += 1\n",
        "global g\n",
        "del x\n",
        "assert x\n",
        "raise E\n",
    ], ids=["decorated-def", "decorated-async-def", "pytest-hook-def", "pytestmark-def", "setup-def", "setUpModule-def", "tearDownModule-def",
            "load_tests-def", "decorated-class", "class-global", "class-nested-decorator", "class-call-base",
            "class-call-keyword", "class-call-statement", "class-if-body", "class-call-assignment",
            "class-pytest-assign", "class-augassign", "pytestmark-upper", "pytestmark", "pytest_plugins",
            "setup-assign", "dunder-assign", "attribute-target", "tuple-target", "call-value", "lambda-value",
            "walrus-value", "listcomp-value", "setcomp-value", "generator-value", "annotated-call", "if", "try", "for",
            "while", "with", "match", "call-statement", "non-docstring-expr", "augassign", "global", "del", "assert",
            "raise"])
    def test_allowed_host_refuses_each_forbidden_shape(text):
>       assert not front._allowed_host(ast.parse(text).body[0])
E       assert not True
E        +  where True = <function _allowed_host at 0x107d87560>(<ast.For object at 0x107bc5610>)
E        +    where <function _allowed_host at 0x107d87560> = front._allowed_host

/path/to/home/.superheroes-worktrees/superheroes/issue-2053-a5acd47bf4fc84b7/plugins/superheroes/lib/tests/test_break_it_body_2053.py:1007: AssertionError
____________ test_allowed_host_refuses_each_forbidden_shape[while] _____________

text = 'while c:\n    pass\n'

    @pytest.mark.parametrize("text", [
        "@pytest.fixture\ndef f():\n    pass\n",
        "@fx(autouse=True)\nasync def f():\n    pass\n",
        "def pytest_generate_tests(metafunc):\n    pass\n",
        "def pytestmark():\n    pass\n",
        "def setup_module():\n    pass\n",
        "def setUpModule():\n    pass\n",
        "def tearDownModule():\n    pass\n",
        "def load_tests(loader, tests, pattern):\n    pass\n",
        "@register\nclass K:\n    pass\n",
        "class K:\n    global g\n    g = 1\n",
        "class K:\n    def f(self):\n        nonlocal_ = 1\n\n    class Inner:\n        @property\n        def p(self):\n            return 1\n",
        "class K(make()):\n    pass\n",
        "class K(metaclass=make()):\n    pass\n",
        "class K:\n    register()\n",
        "class K:\n    if c:\n        x = 1\n",
        "class K:\n    x = f()\n",
        "class K:\n    pytestmark = 1\n",
        "class K:\n    x += 1\n",
        "PYTESTMARK = 1\n",
        "pytestmark = 1\n",
        "pytest_plugins = ['x']\n",
        "setup_module = other\n",
        "__unittest_skip__ = True\n",
        "A.b = 1\n",
        "x, y = 1, 2\n",
        "x = f()\n",
        "x = lambda: 1\n",
        "x = (y := 1)\n",
        "x = [i for i in range(3)]\n",
        "x = {i for i in ()}\n",
        "x = (i for i in ())\n",
        "x: int = f()\n",
        "if c:\n    x = 1\n",
        "try:\n    x = 1\nexcept E:\n    pass\n",
        "for i in v:\n    pass\n",
        "while c:\n    pass\n",
        "with c:\n    pass\n",
        "match c:\n    case 1:\n        pass\n",
        "f()\n",
        "'a' + 'b'\n",
        "x += 1\n",
        "global g\n",
        "del x\n",
        "assert x\n",
        "raise E\n",
    ], ids=["decorated-def", "decorated-async-def", "pytest-hook-def", "pytestmark-def", "setup-def", "setUpModule-def", "tearDownModule-def",
            "load_tests-def", "decorated-class", "class-global", "class-nested-decorator", "class-call-base",
            "class-call-keyword", "class-call-statement", "class-if-body", "class-call-assignment",
            "class-pytest-assign", "class-augassign", "pytestmark-upper", "pytestmark", "pytest_plugins",
            "setup-assign", "dunder-assign", "attribute-target", "tuple-target", "call-value", "lambda-value",
            "walrus-value", "listcomp-value", "setcomp-value", "generator-value", "annotated-call", "if", "try", "for",
            "while", "with", "match", "call-statement", "non-docstring-expr", "augassign", "global", "del", "assert",
            "raise"])
    def test_allowed_host_refuses_each_forbidden_shape(text):
>       assert not front._allowed_host(ast.parse(text).body[0])
E       assert not True
E        +  where True = <function _allowed_host at 0x107d87560>(<ast.While object at 0x107cefa10>)
E        +    where <function _allowed_host at 0x107d87560> = front._allowed_host

/path/to/home/.superheroes-worktrees/superheroes/issue-2053-a5acd47bf4fc84b7/plugins/superheroes/lib/tests/test_break_it_body_2053.py:1007: AssertionError
_____________ test_allowed_host_refuses_each_forbidden_shape[with] _____________

text = 'with c:\n    pass\n'

    @pytest.mark.parametrize("text", [
        "@pytest.fixture\ndef f():\n    pass\n",
        "@fx(autouse=True)\nasync def f():\n    pass\n",
        "def pytest_generate_tests(metafunc):\n    pass\n",
        "def pytestmark():\n    pass\n",
        "def setup_module():\n    pass\n",
        "def setUpModule():\n    pass\n",
        "def tearDownModule():\n    pass\n",
        "def load_tests(loader, tests, pattern):\n    pass\n",
        "@register\nclass K:\n    pass\n",
        "class K:\n    global g\n    g = 1\n",
        "class K:\n    def f(self):\n        nonlocal_ = 1\n\n    class Inner:\n        @property\n        def p(self):\n            return 1\n",
        "class K(make()):\n    pass\n",
        "class K(metaclass=make()):\n    pass\n",
        "class K:\n    register()\n",
        "class K:\n    if c:\n        x = 1\n",
        "class K:\n    x = f()\n",
        "class K:\n    pytestmark = 1\n",
        "class K:\n    x += 1\n",
        "PYTESTMARK = 1\n",
        "pytestmark = 1\n",
        "pytest_plugins = ['x']\n",
        "setup_module = other\n",
        "__unittest_skip__ = True\n",
        "A.b = 1\n",
        "x, y = 1, 2\n",
        "x = f()\n",
        "x = lambda: 1\n",
        "x = (y := 1)\n",
        "x = [i for i in range(3)]\n",
        "x = {i for i in ()}\n",
        "x = (i for i in ())\n",
        "x: int = f()\n",
        "if c:\n    x = 1\n",
        "try:\n    x = 1\nexcept E:\n    pass\n",
        "for i in v:\n    pass\n",
        "while c:\n    pass\n",
        "with c:\n    pass\n",
        "match c:\n    case 1:\n        pass\n",
        "f()\n",
        "'a' + 'b'\n",
        "x += 1\n",
        "global g\n",
        "del x\n",
        "assert x\n",
        "raise E\n",
    ], ids=["decorated-def", "decorated-async-def", "pytest-hook-def", "pytestmark-def", "setup-def", "setUpModule-def", "tearDownModule-def",
            "load_tests-def", "decorated-class", "class-global", "class-nested-decorator", "class-call-base",
            "class-call-keyword", "class-call-statement", "class-if-body", "class-call-assignment",
            "class-pytest-assign", "class-augassign", "pytestmark-upper", "pytestmark", "pytest_plugins",
            "setup-assign", "dunder-assign", "attribute-target", "tuple-target", "call-value", "lambda-value",
            "walrus-value", "listcomp-value", "setcomp-value", "generator-value", "annotated-call", "if", "try", "for",
            "while", "with", "match", "call-statement", "non-docstring-expr", "augassign", "global", "del", "assert",
            "raise"])
    def test_allowed_host_refuses_each_forbidden_shape(text):
>       assert not front._allowed_host(ast.parse(text).body[0])
E       assert not True
E        +  where True = <function _allowed_host at 0x107d87560>(<ast.With object at 0x107c188d0>)
E        +    where <function _allowed_host at 0x107d87560> = front._allowed_host

/path/to/home/.superheroes-worktrees/superheroes/issue-2053-a5acd47bf4fc84b7/plugins/superheroes/lib/tests/test_break_it_body_2053.py:1007: AssertionError
____________ test_allowed_host_refuses_each_forbidden_shape[match] _____________

text = 'match c:\n    case 1:\n        pass\n'

    @pytest.mark.parametrize("text", [
        "@pytest.fixture\ndef f():\n    pass\n",
        "@fx(autouse=True)\nasync def f():\n    pass\n",
        "def pytest_generate_tests(metafunc):\n    pass\n",
        "def pytestmark():\n    pass\n",
        "def setup_module():\n    pass\n",
        "def setUpModule():\n    pass\n",
        "def tearDownModule():\n    pass\n",
        "def load_tests(loader, tests, pattern):\n    pass\n",
        "@register\nclass K:\n    pass\n",
        "class K:\n    global g\n    g = 1\n",
        "class K:\n    def f(self):\n        nonlocal_ = 1\n\n    class Inner:\n        @property\n        def p(self):\n            return 1\n",
        "class K(make()):\n    pass\n",
        "class K(metaclass=make()):\n    pass\n",
        "class K:\n    register()\n",
        "class K:\n    if c:\n        x = 1\n",
        "class K:\n    x = f()\n",
        "class K:\n    pytestmark = 1\n",
        "class K:\n    x += 1\n",
        "PYTESTMARK = 1\n",
        "pytestmark = 1\n",
        "pytest_plugins = ['x']\n",
        "setup_module = other\n",
        "__unittest_skip__ = True\n",
        "A.b = 1\n",
        "x, y = 1, 2\n",
        "x = f()\n",
        "x = lambda: 1\n",
        "x = (y := 1)\n",
        "x = [i for i in range(3)]\n",
        "x = {i for i in ()}\n",
        "x = (i for i in ())\n",
        "x: int = f()\n",
        "if c:\n    x = 1\n",
        "try:\n    x = 1\nexcept E:\n    pass\n",
        "for i in v:\n    pass\n",
        "while c:\n    pass\n",
        "with c:\n    pass\n",
        "match c:\n    case 1:\n        pass\n",
        "f()\n",
        "'a' + 'b'\n",
        "x += 1\n",
        "global g\n",
        "del x\n",
        "assert x\n",
        "raise E\n",
    ], ids=["decorated-def", "decorated-async-def", "pytest-hook-def", "pytestmark-def", "setup-def", "setUpModule-def", "tearDownModule-def",
            "load_tests-def", "decorated-class", "class-global", "class-nested-decorator", "class-call-base",
            "class-call-keyword", "class-call-statement", "class-if-body", "class-call-assignment",
            "class-pytest-assign", "class-augassign", "pytestmark-upper", "pytestmark", "pytest_plugins",
            "setup-assign", "dunder-assign", "attribute-target", "tuple-target", "call-value", "lambda-value",
            "walrus-value", "listcomp-value", "setcomp-value", "generator-value", "annotated-call", "if", "try", "for",
            "while", "with", "match", "call-statement", "non-docstring-expr", "augassign", "global", "del", "assert",
            "raise"])
    def test_allowed_host_refuses_each_forbidden_shape(text):
>       assert not front._allowed_host(ast.parse(text).body[0])
E       assert not True
E        +  where True = <function _allowed_host at 0x107d87560>(<ast.Match object at 0x107c78fd0>)
E        +    where <function _allowed_host at 0x107d87560> = front._allowed_host

/path/to/home/.superheroes-worktrees/superheroes/issue-2053-a5acd47bf4fc84b7/plugins/superheroes/lib/tests/test_break_it_body_2053.py:1007: AssertionError
_ test_core_a_host_that_adds_anything_but_plain_code_is_host_setup[if-holding-a-def] _

extra = 'if True:\n    def helper():\n        return 1\n'

    @pytest.mark.parametrize("extra", [
        "if True:\n    def helper():\n        return 1\n",
        "setup_things()\n",
        "@functools.lru_cache\ndef helper():\n    return 1\n",
        "COUNT += 1\n",
        "CONFIG = load()\n",
    ], ids=["if-holding-a-def", "call-statement", "decorated-helper", "augassign", "call-in-assignment"])
    def test_core_a_host_that_adds_anything_but_plain_code_is_host_setup(extra):
        got = break_it_body.locate(_V, "a.py", [("b.py", _V + "\n\n" + extra)])
>       assert (got["status"], got["reason"]) == ("unresolved", "host-setup")
E       AssertionError: assert ('found', None) == ('unresolved', 'host-setup')
E         
E         At index 0 diff: 'found' != 'unresolved'
E         Use -v to get more diff

/path/to/home/.superheroes-worktrees/superheroes/issue-2053-a5acd47bf4fc84b7/plugins/superheroes/lib/tests/test_break_it_body_2053.py:919: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_allowed_host_refuses_each_forbidden_shape[if]
FAILED plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_allowed_host_refuses_each_forbidden_shape[try]
FAILED plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_allowed_host_refuses_each_forbidden_shape[for]
FAILED plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_allowed_host_refuses_each_forbidden_shape[while]
FAILED plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_allowed_host_refuses_each_forbidden_shape[with]
FAILED plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_allowed_host_refuses_each_forbidden_shape[match]
FAILED plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_core_a_host_that_adds_anything_but_plain_code_is_host_setup[if-holding-a-def]
7 failed in 1.83s
```

**restore:** the inverse edit on `plugins/superheroes/lib/break_it_body_py.py` (`return _docstring(node) or isinstance(node, (ast.If, ...))` back to `return _docstring(node)`).

**restore receipt** (`git diff --stat -- plugins/superheroes/lib/break_it_body_py.py` printed nothing, so the file equals its last commit; the restored line, quoted back from `_allowed_host`):
```
    return _docstring(node)
```

**raw green** (exit 0), same command:
```
.......                                                                  [100%]
7 passed in 0.85s
```

---

### H3: the refusal of a call in an assigned value

- **axis:** an assignment or annotated assignment whose value calls something, at module level or in a class body, is a hook, so a host that adds one is refused

**neutralization** (`plugins/superheroes/lib/break_it_body_py.py`, `_plain_assignment`, its last line):
```diff
-    return all(_plain_value(part) for part in value)
+    return True
```

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest "plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_allowed_host_refuses_each_forbidden_shape[call-value]" "plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_allowed_host_refuses_each_forbidden_shape[annotated-call]" "plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_allowed_host_refuses_each_forbidden_shape[class-call-assignment]" "plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_core_a_host_that_adds_anything_but_plain_code_is_host_setup[call-in-assignment]" -q
```

**raw red** (exit 1):
```
FFFF                                                                     [100%]
=================================== FAILURES ===================================
__________ test_allowed_host_refuses_each_forbidden_shape[call-value] __________

text = 'x = f()\n'

    @pytest.mark.parametrize("text", [
        "@pytest.fixture\ndef f():\n    pass\n",
        "@fx(autouse=True)\nasync def f():\n    pass\n",
        "def pytest_generate_tests(metafunc):\n    pass\n",
        "def pytestmark():\n    pass\n",
        "def setup_module():\n    pass\n",
        "def setUpModule():\n    pass\n",
        "def tearDownModule():\n    pass\n",
        "def load_tests(loader, tests, pattern):\n    pass\n",
        "@register\nclass K:\n    pass\n",
        "class K:\n    global g\n    g = 1\n",
        "class K:\n    def f(self):\n        nonlocal_ = 1\n\n    class Inner:\n        @property\n        def p(self):\n            return 1\n",
        "class K(make()):\n    pass\n",
        "class K(metaclass=make()):\n    pass\n",
        "class K:\n    register()\n",
        "class K:\n    if c:\n        x = 1\n",
        "class K:\n    x = f()\n",
        "class K:\n    pytestmark = 1\n",
        "class K:\n    x += 1\n",
        "PYTESTMARK = 1\n",
        "pytestmark = 1\n",
        "pytest_plugins = ['x']\n",
        "setup_module = other\n",
        "__unittest_skip__ = True\n",
        "A.b = 1\n",
        "x, y = 1, 2\n",
        "x = f()\n",
        "x = lambda: 1\n",
        "x = (y := 1)\n",
        "x = [i for i in range(3)]\n",
        "x = {i for i in ()}\n",
        "x = (i for i in ())\n",
        "x: int = f()\n",
        "if c:\n    x = 1\n",
        "try:\n    x = 1\nexcept E:\n    pass\n",
        "for i in v:\n    pass\n",
        "while c:\n    pass\n",
        "with c:\n    pass\n",
        "match c:\n    case 1:\n        pass\n",
        "f()\n",
        "'a' + 'b'\n",
        "x += 1\n",
        "global g\n",
        "del x\n",
        "assert x\n",
        "raise E\n",
    ], ids=["decorated-def", "decorated-async-def", "pytest-hook-def", "pytestmark-def", "setup-def", "setUpModule-def", "tearDownModule-def",
            "load_tests-def", "decorated-class", "class-global", "class-nested-decorator", "class-call-base",
            "class-call-keyword", "class-call-statement", "class-if-body", "class-call-assignment",
            "class-pytest-assign", "class-augassign", "pytestmark-upper", "pytestmark", "pytest_plugins",
            "setup-assign", "dunder-assign", "attribute-target", "tuple-target", "call-value", "lambda-value",
            "walrus-value", "listcomp-value", "setcomp-value", "generator-value", "annotated-call", "if", "try", "for",
            "while", "with", "match", "call-statement", "non-docstring-expr", "augassign", "global", "del", "assert",
            "raise"])
    def test_allowed_host_refuses_each_forbidden_shape(text):
>       assert not front._allowed_host(ast.parse(text).body[0])
E       assert not True
E        +  where True = <function _allowed_host at 0x105f8e980>(<ast.Assign object at 0x105f2b510>)
E        +    where <function _allowed_host at 0x105f8e980> = front._allowed_host

/path/to/home/.superheroes-worktrees/superheroes/issue-2053-a5acd47bf4fc84b7/plugins/superheroes/lib/tests/test_break_it_body_2053.py:1007: AssertionError
________ test_allowed_host_refuses_each_forbidden_shape[annotated-call] ________

text = 'x: int = f()\n'

    @pytest.mark.parametrize("text", [
        "@pytest.fixture\ndef f():\n    pass\n",
        "@fx(autouse=True)\nasync def f():\n    pass\n",
        "def pytest_generate_tests(metafunc):\n    pass\n",
        "def pytestmark():\n    pass\n",
        "def setup_module():\n    pass\n",
        "def setUpModule():\n    pass\n",
        "def tearDownModule():\n    pass\n",
        "def load_tests(loader, tests, pattern):\n    pass\n",
        "@register\nclass K:\n    pass\n",
        "class K:\n    global g\n    g = 1\n",
        "class K:\n    def f(self):\n        nonlocal_ = 1\n\n    class Inner:\n        @property\n        def p(self):\n            return 1\n",
        "class K(make()):\n    pass\n",
        "class K(metaclass=make()):\n    pass\n",
        "class K:\n    register()\n",
        "class K:\n    if c:\n        x = 1\n",
        "class K:\n    x = f()\n",
        "class K:\n    pytestmark = 1\n",
        "class K:\n    x += 1\n",
        "PYTESTMARK = 1\n",
        "pytestmark = 1\n",
        "pytest_plugins = ['x']\n",
        "setup_module = other\n",
        "__unittest_skip__ = True\n",
        "A.b = 1\n",
        "x, y = 1, 2\n",
        "x = f()\n",
        "x = lambda: 1\n",
        "x = (y := 1)\n",
        "x = [i for i in range(3)]\n",
        "x = {i for i in ()}\n",
        "x = (i for i in ())\n",
        "x: int = f()\n",
        "if c:\n    x = 1\n",
        "try:\n    x = 1\nexcept E:\n    pass\n",
        "for i in v:\n    pass\n",
        "while c:\n    pass\n",
        "with c:\n    pass\n",
        "match c:\n    case 1:\n        pass\n",
        "f()\n",
        "'a' + 'b'\n",
        "x += 1\n",
        "global g\n",
        "del x\n",
        "assert x\n",
        "raise E\n",
    ], ids=["decorated-def", "decorated-async-def", "pytest-hook-def", "pytestmark-def", "setup-def", "setUpModule-def", "tearDownModule-def",
            "load_tests-def", "decorated-class", "class-global", "class-nested-decorator", "class-call-base",
            "class-call-keyword", "class-call-statement", "class-if-body", "class-call-assignment",
            "class-pytest-assign", "class-augassign", "pytestmark-upper", "pytestmark", "pytest_plugins",
            "setup-assign", "dunder-assign", "attribute-target", "tuple-target", "call-value", "lambda-value",
            "walrus-value", "listcomp-value", "setcomp-value", "generator-value", "annotated-call", "if", "try", "for",
            "while", "with", "match", "call-statement", "non-docstring-expr", "augassign", "global", "del", "assert",
            "raise"])
    def test_allowed_host_refuses_each_forbidden_shape(text):
>       assert not front._allowed_host(ast.parse(text).body[0])
E       assert not True
E        +  where True = <function _allowed_host at 0x105f8e980>(<ast.AnnAssign object at 0x105f15d90>)
E        +    where <function _allowed_host at 0x105f8e980> = front._allowed_host

/path/to/home/.superheroes-worktrees/superheroes/issue-2053-a5acd47bf4fc84b7/plugins/superheroes/lib/tests/test_break_it_body_2053.py:1007: AssertionError
____ test_allowed_host_refuses_each_forbidden_shape[class-call-assignment] _____

text = 'class K:\n    x = f()\n'

    @pytest.mark.parametrize("text", [
        "@pytest.fixture\ndef f():\n    pass\n",
        "@fx(autouse=True)\nasync def f():\n    pass\n",
        "def pytest_generate_tests(metafunc):\n    pass\n",
        "def pytestmark():\n    pass\n",
        "def setup_module():\n    pass\n",
        "def setUpModule():\n    pass\n",
        "def tearDownModule():\n    pass\n",
        "def load_tests(loader, tests, pattern):\n    pass\n",
        "@register\nclass K:\n    pass\n",
        "class K:\n    global g\n    g = 1\n",
        "class K:\n    def f(self):\n        nonlocal_ = 1\n\n    class Inner:\n        @property\n        def p(self):\n            return 1\n",
        "class K(make()):\n    pass\n",
        "class K(metaclass=make()):\n    pass\n",
        "class K:\n    register()\n",
        "class K:\n    if c:\n        x = 1\n",
        "class K:\n    x = f()\n",
        "class K:\n    pytestmark = 1\n",
        "class K:\n    x += 1\n",
        "PYTESTMARK = 1\n",
        "pytestmark = 1\n",
        "pytest_plugins = ['x']\n",
        "setup_module = other\n",
        "__unittest_skip__ = True\n",
        "A.b = 1\n",
        "x, y = 1, 2\n",
        "x = f()\n",
        "x = lambda: 1\n",
        "x = (y := 1)\n",
        "x = [i for i in range(3)]\n",
        "x = {i for i in ()}\n",
        "x = (i for i in ())\n",
        "x: int = f()\n",
        "if c:\n    x = 1\n",
        "try:\n    x = 1\nexcept E:\n    pass\n",
        "for i in v:\n    pass\n",
        "while c:\n    pass\n",
        "with c:\n    pass\n",
        "match c:\n    case 1:\n        pass\n",
        "f()\n",
        "'a' + 'b'\n",
        "x += 1\n",
        "global g\n",
        "del x\n",
        "assert x\n",
        "raise E\n",
    ], ids=["decorated-def", "decorated-async-def", "pytest-hook-def", "pytestmark-def", "setup-def", "setUpModule-def", "tearDownModule-def",
            "load_tests-def", "decorated-class", "class-global", "class-nested-decorator", "class-call-base",
            "class-call-keyword", "class-call-statement", "class-if-body", "class-call-assignment",
            "class-pytest-assign", "class-augassign", "pytestmark-upper", "pytestmark", "pytest_plugins",
            "setup-assign", "dunder-assign", "attribute-target", "tuple-target", "call-value", "lambda-value",
            "walrus-value", "listcomp-value", "setcomp-value", "generator-value", "annotated-call", "if", "try", "for",
            "while", "with", "match", "call-statement", "non-docstring-expr", "augassign", "global", "del", "assert",
            "raise"])
    def test_allowed_host_refuses_each_forbidden_shape(text):
>       assert not front._allowed_host(ast.parse(text).body[0])
E       assert not True
E        +  where True = <function _allowed_host at 0x105f8e980>(<ast.ClassDef object at 0x1050c7150>)
E        +    where <function _allowed_host at 0x105f8e980> = front._allowed_host

/path/to/home/.superheroes-worktrees/superheroes/issue-2053-a5acd47bf4fc84b7/plugins/superheroes/lib/tests/test_break_it_body_2053.py:1007: AssertionError
_ test_core_a_host_that_adds_anything_but_plain_code_is_host_setup[call-in-assignment] _

extra = 'CONFIG = load()\n'

    @pytest.mark.parametrize("extra", [
        "if True:\n    def helper():\n        return 1\n",
        "setup_things()\n",
        "@functools.lru_cache\ndef helper():\n    return 1\n",
        "COUNT += 1\n",
        "CONFIG = load()\n",
    ], ids=["if-holding-a-def", "call-statement", "decorated-helper", "augassign", "call-in-assignment"])
    def test_core_a_host_that_adds_anything_but_plain_code_is_host_setup(extra):
        got = break_it_body.locate(_V, "a.py", [("b.py", _V + "\n\n" + extra)])
>       assert (got["status"], got["reason"]) == ("unresolved", "host-setup")
E       AssertionError: assert ('found', None) == ('unresolved', 'host-setup')
E         
E         At index 0 diff: 'found' != 'unresolved'
E         Use -v to get more diff

/path/to/home/.superheroes-worktrees/superheroes/issue-2053-a5acd47bf4fc84b7/plugins/superheroes/lib/tests/test_break_it_body_2053.py:919: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_allowed_host_refuses_each_forbidden_shape[call-value]
FAILED plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_allowed_host_refuses_each_forbidden_shape[annotated-call]
FAILED plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_allowed_host_refuses_each_forbidden_shape[class-call-assignment]
FAILED plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_core_a_host_that_adds_anything_but_plain_code_is_host_setup[call-in-assignment]
4 failed in 1.89s
```

**restore:** the inverse edit on `plugins/superheroes/lib/break_it_body_py.py` (`return True` back to `return all(_plain_value(part) for part in value)`; the edit's match text included the following blank lines and `def _plain_class` to be unique).

**restore receipt** (`git diff --stat -- plugins/superheroes/lib/break_it_body_py.py` printed nothing, so the file equals its last commit; the restored line, quoted back from `_plain_assignment`):
```
    return all(_plain_value(part) for part in value)
```

**raw green** (exit 0), same command:
```
....                                                                     [100%]
4 passed in 1.25s
```

---

### H4: the wiring of `_allowed_host` into the record

- **axis:** `parse` records a statement as a hook exactly when `_allowed_host` refuses it, so `locate` reads `host-setup`

**neutralization** (`plugins/superheroes/lib/break_it_body_py.py`, the record dict in `_record`, which `parse` returns):
```diff
-            "hook": not _allowed_host(node),
+            "hook": False,
```

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_front_records_hook_is_the_negation_of_allowed_host "plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_core_a_host_that_adds_anything_but_plain_code_is_host_setup[call-statement]" "plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_core_a_host_that_adds_anything_but_plain_code_is_host_setup[decorated-helper]" -q
```

**raw red** (exit 1):
```
FFF                                                                      [100%]
=================================== FAILURES ===================================
___________ test_front_records_hook_is_the_negation_of_allowed_host ____________

    def test_front_records_hook_is_the_negation_of_allowed_host():
        for text in ("import os\n", "x = 1\n", "x = f()\n", "@d\ndef f(): pass\n", "if c:\n    pass\n"):
            node = ast.parse(text).body[0]
>           assert front.parse(text)[0]["hook"] is (not front._allowed_host(node))
E           assert False is not False
E            +  where False = <function _allowed_host at 0x103d7e980>(<ast.Assign object at 0x103ceddd0>)
E            +    where <function _allowed_host at 0x103d7e980> = front._allowed_host

/path/to/home/.superheroes-worktrees/superheroes/issue-2053-a5acd47bf4fc84b7/plugins/superheroes/lib/tests/test_break_it_body_2053.py:1013: AssertionError
_ test_core_a_host_that_adds_anything_but_plain_code_is_host_setup[call-statement] _

extra = 'setup_things()\n'

    @pytest.mark.parametrize("extra", [
        "if True:\n    def helper():\n        return 1\n",
        "setup_things()\n",
        "@functools.lru_cache\ndef helper():\n    return 1\n",
        "COUNT += 1\n",
        "CONFIG = load()\n",
    ], ids=["if-holding-a-def", "call-statement", "decorated-helper", "augassign", "call-in-assignment"])
    def test_core_a_host_that_adds_anything_but_plain_code_is_host_setup(extra):
        got = break_it_body.locate(_V, "a.py", [("b.py", _V + "\n\n" + extra)])
>       assert (got["status"], got["reason"]) == ("unresolved", "host-setup")
E       AssertionError: assert ('found', None) == ('unresolved', 'host-setup')
E         
E         At index 0 diff: 'found' != 'unresolved'
E         Use -v to get more diff

/path/to/home/.superheroes-worktrees/superheroes/issue-2053-a5acd47bf4fc84b7/plugins/superheroes/lib/tests/test_break_it_body_2053.py:919: AssertionError
_ test_core_a_host_that_adds_anything_but_plain_code_is_host_setup[decorated-helper] _

extra = '@functools.lru_cache\ndef helper():\n    return 1\n'

    @pytest.mark.parametrize("extra", [
        "if True:\n    def helper():\n        return 1\n",
        "setup_things()\n",
        "@functools.lru_cache\ndef helper():\n    return 1\n",
        "COUNT += 1\n",
        "CONFIG = load()\n",
    ], ids=["if-holding-a-def", "call-statement", "decorated-helper", "augassign", "call-in-assignment"])
    def test_core_a_host_that_adds_anything_but_plain_code_is_host_setup(extra):
        got = break_it_body.locate(_V, "a.py", [("b.py", _V + "\n\n" + extra)])
>       assert (got["status"], got["reason"]) == ("unresolved", "host-setup")
E       AssertionError: assert ('found', None) == ('unresolved', 'host-setup')
E         
E         At index 0 diff: 'found' != 'unresolved'
E         Use -v to get more diff

/path/to/home/.superheroes-worktrees/superheroes/issue-2053-a5acd47bf4fc84b7/plugins/superheroes/lib/tests/test_break_it_body_2053.py:919: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_front_records_hook_is_the_negation_of_allowed_host
FAILED plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_core_a_host_that_adds_anything_but_plain_code_is_host_setup[call-statement]
FAILED plugins/superheroes/lib/tests/test_break_it_body_2053.py::test_core_a_host_that_adds_anything_but_plain_code_is_host_setup[decorated-helper]
3 failed in 1.73s
```

**restore:** the inverse edit on `plugins/superheroes/lib/break_it_body_py.py` (`"hook": False,` back to `"hook": not _allowed_host(node),`).

**restore receipt** (`git diff --stat -- plugins/superheroes/lib/break_it_body_py.py` printed nothing, so the file equals its last commit; the restored line, quoted back from the record dict in `_record`):
```
            "hook": not _allowed_host(node),
```

**raw green** (exit 0), same command:
```
...                                                                      [100%]
3 passed in 1.27s
```

---

# C1-L12 addendum (build #2216, entries for C1-L11f's review-loop axis lines)

A2 (added by fixer commit `dd84d915`, `break_it.py:1818`; axis: "a renamed pytest test is accepted only when the repository at the reviewed head declares no pytest collection override, because a custom python_functions could leave the new name uncollected (or an addopts -k selector deselect it) while the host still passes; pytest configuration says nothing about a vitest or jest run, so only a test read by a pytest-collected front is gated — see bite-proof records wo_a_2053_break_it_body and wo_b_2061_break_it_body_js") has its entry, with the neutralization, raw red and raw green on `test_break_it_body_2053.py::test_a_rename_is_unresolved_when_pytest_ini_sets_python_functions`, in `wo_b_2061_break_it_body_js.md` under the same heading, section `## A2`.
