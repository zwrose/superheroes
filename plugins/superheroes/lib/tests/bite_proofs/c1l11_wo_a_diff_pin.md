# C1-L11 (WO-A) bite-proof — the review loop's diff is one pinned argv

**Provenance:** implementer WO-A / `lib/review_diff_bytes.py`, `lib/review_base_guard.py`, `skills/review-code/SKILL.md`, `lib/tests/test_review_diff_pin_c1l11.py`

Declared guarded elements (from the order): E1 `run_git_diff_three_dot` passing `REVIEW_DIFF_ARGS`; E2 `_numstat_z_output` passing `REVIEW_NUMSTAT_ARGS` (production branch); E4 the SKILL command's flags. Each was neutralized with one targeted edit and restored with the inverse edit; no `git checkout`, `restore`, `reset` or `stash` was used. Run from `/home/user/wt-2215` under `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest -q -p no:cacheprovider`. The captures are the runner's whole output for each run apart from the `UV_NATIVE_TLS` deprecation warning line, which is left out; nothing is redacted (no secrets, tokens or URLs appear).

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| E1 | `review_diff_bytes.py` `run_git_diff_three_dot`, the `*REVIEW_DIFF_ARGS` in its argv | a user's copy detection never reaches the review diff: a copy is a new file | `test_t1_a_copy_is_a_new_file_and_its_lines_are_counted` |
| E2 | `review_base_guard.py` `_numstat_z_output`, the `*review_diff_bytes.REVIEW_NUMSTAT_ARGS` in the production `_run_git_bytes` call | the numstat the base guard compares against has the same rename/copy shape as the pinned diff | `test_t5_the_numstat_check_agrees_with_the_pinned_producer` |
| E4 | `skills/review-code/SKILL.md` line 150, the `-M` in the fenced command | the shell command the build session runs carries exactly `REVIEW_DIFF_ARGS` | `test_t6_the_skill_command_is_the_constant` |

E3 was withdrawn with the counter's copy-section guard: the pin keeps copy sections out of the review loop's diff, and the counter's own copy rule is unchanged.

Not separately neutralized (the unproven part of this record): the T2 shape tests (2, 3, 4) and T4.

---

## E1 — the pinned producer

**axis:** a copy under `diff.renames=copies` is a new file in the diff the producer returns.

**neutralization** (`review_diff_bytes.py`, `run_git_diff_three_dot`: `*REVIEW_DIFF_ARGS` removed from the argv):
```python
-        ["git", "-C", repo_root, "diff", *REVIEW_DIFF_ARGS, "%s...%s" % (base_sha, head_sha)],
+        ["git", "-C", repo_root, "diff", "%s...%s" % (base_sha, head_sha)],
```

**raw red:** `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest -q -p no:cacheprovider "plugins/superheroes/lib/tests/test_review_diff_pin_c1l11.py::test_t1_a_copy_is_a_new_file_and_its_lines_are_counted"`
```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_t1_a_copy_is_a_new_file_and_its_lines_are_counted ____________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-1/test_t1_a_copy_is_a_new_file_a0')

    def test_t1_a_copy_is_a_new_file_and_its_lines_are_counted(tmp_path):
        root, base = _copy_of_a(tmp_path, extra="appended\n")
        # the hostile config does produce a copy section from a plain diff
        assert "copy from a.txt" in _plain_diff(root, base)
        diff = _pinned_diff(root, base)
>       assert "copy from" not in diff and "copy to" not in diff
E       AssertionError: assert ('copy from' not in 'diff --git ...n+appended\n'
E         
E         'copy from' is contained here:
E           index 95%
E           copy from a.txt
E           copy to b.txt
E           index 19339a3..830fd9b 100644
E           --- a.txt...
E         
E         ...Full output truncated, use '-vv' to show)

/home/user/wt-2215/plugins/superheroes/lib/tests/test_review_diff_pin_c1l11.py:93: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_diff_pin_c1l11.py::test_t1_a_copy_is_a_new_file_and_its_lines_are_counted
1 failed in 0.16s
```

**restore:** the inverse edit (`*REVIEW_DIFF_ARGS, ` put back between `"diff"` and the `base...head` argument).

**restore receipt:** a search of `review_diff_bytes.py` for `"diff", ` finds line 27, which reads again:
```python
        ["git", "-C", repo_root, "diff", *REVIEW_DIFF_ARGS, "%s...%s" % (base_sha, head_sha)],
```

**raw green:** same command
```
.                                                                        [100%]
1 passed in 0.15s
```

---

## E2 — the numstat check pin

**axis:** the base guard's expected per-file stats agree with the pinned diff's, so a copy is a new file on both sides.

**neutralization** (`review_base_guard.py`, `_numstat_z_output`, production branch: `*review_diff_bytes.REVIEW_NUMSTAT_ARGS` removed from the `_run_git_bytes` call):
```python
-            repo_root, "diff", *review_diff_bytes.REVIEW_NUMSTAT_ARGS, "--numstat", "-z", "%s...HEAD" % pin
+            repo_root, "diff", "--numstat", "-z", "%s...HEAD" % pin
```

**raw red:** `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest -q -p no:cacheprovider "plugins/superheroes/lib/tests/test_review_diff_pin_c1l11.py::test_t5_the_numstat_check_agrees_with_the_pinned_producer"`
```
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_t5_the_numstat_check_agrees_with_the_pinned_producer ___________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-3/test_t5_the_numstat_check_agre0')

    def test_t5_the_numstat_check_agrees_with_the_pinned_producer(tmp_path):
        root, base = _copy_of_a(tmp_path, extra="appended\n")
        diff = _pinned_diff(root, base)
        stats, per_file_ok, added, deleted = rbg._expected_diff_stats(base, str(root), None)
        act_stats, headers_ok, act_added, act_deleted = rbg._artifact_diff_stats(diff)
        assert per_file_ok and headers_ok
>       assert stats == act_stats and set(stats) == {"a.txt", "b.txt"}
E       AssertionError: assert ({'a.txt': (1,....txt': (1, 0)} == {'a.txt': (1,...txt': (31, 0)}
E         
E         Omitting 1 identical items, use -vv to show
E         Differing items:
E         {'b.txt': (1, 0)} != {'b.txt': (31, 0)}
E         Use -v to get more diff)

/home/user/wt-2215/plugins/superheroes/lib/tests/test_review_diff_pin_c1l11.py:225: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_diff_pin_c1l11.py::test_t5_the_numstat_check_agrees_with_the_pinned_producer
1 failed in 0.32s
```

**restore:** the inverse edit (`*review_diff_bytes.REVIEW_NUMSTAT_ARGS, ` put back after `"diff"`).

**restore receipt:** a search of `review_base_guard.py` for `REVIEW_NUMSTAT_ARGS` finds both branches again:
```python
            repo_root, "diff", *review_diff_bytes.REVIEW_NUMSTAT_ARGS, "--numstat", "-z", "%s...HEAD" % pin
    out = run(repo_root, "diff", *review_diff_bytes.REVIEW_NUMSTAT_ARGS, "--numstat", "-z", "%s...HEAD" % pin)
```

**raw green:** same command
```
.                                                                        [100%]
1 passed in 0.16s
```

---

## E4 — the SKILL command's flags

**axis:** the fenced per-round command holds exactly `" ".join(REVIEW_DIFF_ARGS)` between `git diff ` and `"$BASE_REF"...HEAD`.

**neutralization** (`skills/review-code/SKILL.md` line 150: ` -M` deleted from the fenced command):
```
-git diff --no-ext-diff --no-textconv --no-color -M -U3 --src-prefix=a/ --dst-prefix=b/ "$BASE_REF"...HEAD > ...
+git diff --no-ext-diff --no-textconv --no-color -U3 --src-prefix=a/ --dst-prefix=b/ "$BASE_REF"...HEAD > ...
```

**raw red:** `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest -q -p no:cacheprovider "plugins/superheroes/lib/tests/test_review_diff_pin_c1l11.py::test_t6_the_skill_command_is_the_constant"`
```
F                                                                        [100%]
=================================== FAILURES ===================================
__________________ test_t6_the_skill_command_is_the_constant ___________________

    def test_t6_the_skill_command_is_the_constant():
        with open(_SKILL, encoding="utf-8") as handle:
            text = handle.read()
        fences = re.findall(r"```bash\n(.*?)```", text, flags=re.DOTALL)
        fence = next(block for block in fences if "diff.txt.tmp" in block)
        expected = 'git diff ' + " ".join(review_diff_bytes.REVIEW_DIFF_ARGS) + ' "$BASE_REF"...HEAD'
>       assert fence.startswith(expected + " > ")
E       assert False
E        +  where False = <built-in method startswith of str object at 0xa468440>(('git diff --no-ext-diff --no-textconv --no-color -M -U3 --src-prefix=a/ --dst-prefix=b/ "$BASE_REF"...HEAD' + ' > '))
E        +    where <built-in method startswith of str object at 0xa468440> = 'git diff --no-ext-diff --no-textconv --no-color -U3 --src-prefix=a/ --dst-prefix=b/ "$BASE_REF"...HEAD > "$SESSION_DI...$BASE_REF is EMPTY — an empty review surface is never certifiable-clean; halt and investigate (#637)" >&2; exit 1; }\n'.startswith

/home/user/wt-2215/plugins/superheroes/lib/tests/test_review_diff_pin_c1l11.py:237: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_diff_pin_c1l11.py::test_t6_the_skill_command_is_the_constant
1 failed in 0.13s
```

**restore:** the inverse edit (` -M` put back).

**restore receipt:** a search of `SKILL.md` for `^git diff --no-ext-diff` finds line 150, which reads again:
```
git diff --no-ext-diff --no-textconv --no-color -M -U3 --src-prefix=a/ --dst-prefix=b/ "$BASE_REF"...HEAD > "$SESSION_DIR/round-<round>/diff.txt.tmp" && mv ...
```

**raw green:** same command
```
.                                                                        [100%]
1 passed in 0.11s
```
