# WO-E (#2314) bite-proofs — no delete rides a compound command in review-code's own recipes

Guarded-element set (declared by the order): five elements, (a) to (e), one per distinct failure
mode, so no grouping is used and no element is unproven.

| | Element | Axis | Detector |
|---|---|---|---|
| a | the diff fence's `mv` line, `SKILL.md` | a delete in a compound command inside a fenced bash block is reported | `test_no_review_code_recipe_puts_a_delete_inside_a_compound_command` |
| b | the inline `find … -delete 2>/dev/null` span, `reference/verification-pass.md:37` | a delete in a compound command inside an inline span under `reference/` is reported | the same census test |
| c | the `|| { echo …; exit 1; }` on the diff fence's `mv` line | a failed `mv` halts with exit 1 and the `FAILED` message | `test_the_diff_recipe_halts_on_each_failure` |
| d | the empty-diff guard, the `[ -s … diff.txt ]` line right after the `mv` line | an empty diff halts with exit 1 and the `is EMPTY` message | `test_the_diff_recipe_halts_on_each_failure` |
| e | the `|| { … }` on the `meta.json` fence's `mv` line | a failed `mv` halts with exit 1 and the `could not write meta.json` message | `test_the_meta_json_recipe_halts_on_each_failure` |

All runs: `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-e -m pytest <node> -q -p no:cacheprovider`
from the worktree root. Every neutralization was made with the Edit tool and undone by the inverse
Edit. No receipt below holds a secret, token, or private URL; nothing was redacted. The single green
run after all five reverts (`... test_review_code_recipes_no_compound_delete.py -q`) is the green half
for every element:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
...                                                                      [100%]
3 passed in 0.44s
```

Line numbers are those of the head after this change: the new diff fence has the producer on
`SKILL.md:152`, the `mv` on `:153`, the empty guard on `:154`; the `meta.json` `mv` is on `:177`.
(The order's "line 153" for the guard names the line before the two-line replacement.)

---

## (a) Census, fence

**Neutralization:** appended ` && rm -f "$SESSION_DIR/round-<round>/diff.txt.tmp"` to the end of the
diff fence's `mv` line (`SKILL.md:153`).

**Raw red** (node `...::test_no_review_code_recipe_puts_a_delete_inside_a_compound_command`; the echoed
test source above the failing `assert` is elided, 12 lines, identical to the test file):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
______ test_no_review_code_recipe_puts_a_delete_inside_a_compound_command ______
>       assert not hits, "a delete rides a compound command:\n" + "\n".join(
            "%s:%d: %s" % hit for hit in hits
        )
E       AssertionError: a delete rides a compound command:
E         SKILL.md:153: mv "$SESSION_DIR/round-<round>/diff.txt.tmp" "$SESSION_DIR/round-<round>/diff.txt" || { echo "review-code: git diff against $BASE_REF FAILED — refusing to review the artifact it left behind (#637)" >&2; exit 1; } && rm -f "$SESSION_DIR/round-<round>/diff.txt.tmp"
E       assert not [('SKILL.md', 153, 'mv "$SESSION_DIR/round-<round>/diff.txt.tmp" "$SESSION_DIR/round-<round>/diff.txt" || { echo "review-code: git diff against $BASE_REF FAILED — refusing to review the artifact it left behind (#637)" >&2; exit 1; } && rm -f "$SESSION_DIR/round-<round>/diff.txt.tmp"')]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_code_recipes_no_compound_delete.py::test_no_review_code_recipe_puts_a_delete_inside_a_compound_command
1 failed in 0.40s
```
The red is on the claimed axis: the census reports `SKILL.md` and line 153.

**Restore:** by the inverse Edit, removed ` && rm -f "$SESSION_DIR/round-<round>/diff.txt.tmp"` from the end of that line.

**Restore receipt:** the line again reads (quoted from the file after the restore)
```
mv "$SESSION_DIR/round-<round>/diff.txt.tmp" "$SESSION_DIR/round-<round>/diff.txt" || { echo "review-code: git diff against $BASE_REF FAILED — refusing to review the artifact it left behind (#637)" >&2; exit 1; }
```

**Raw green:** the single green run above.

---

## (b) Census, inline span

**Neutralization:** appended ` && true` inside the inline span on `reference/verification-pass.md:37`,
so it reads `` `find "$SESSION_DIR/round-<N>" -maxdepth 1 -name 'verdicts-*.json' -delete 2>/dev/null && true` ``.

**Raw red** (same node; echoed test source elided as in (a)):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
______ test_no_review_code_recipe_puts_a_delete_inside_a_compound_command ______
>       assert not hits, "a delete rides a compound command:\n" + "\n".join(
            "%s:%d: %s" % hit for hit in hits
        )
E       AssertionError: a delete rides a compound command:
E         reference/verification-pass.md:37: find "$SESSION_DIR/round-<N>" -maxdepth 1 -name 'verdicts-*.json' -delete 2>/dev/null && true
E       assert not [('reference/verification-pass.md', 37, 'find "$SESSION_DIR/round-<N>" -maxdepth 1 -name \'verdicts-*.json\' -delete 2>/dev/null && true')]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_code_recipes_no_compound_delete.py::test_no_review_code_recipe_puts_a_delete_inside_a_compound_command
1 failed in 0.31s
```
The red is on the claimed axis: the census reaches an inline span under `reference/` and reports the file and line.

**Restore:** by the inverse Edit, removed ` && true` from inside the span.

**Restore receipt:** the span reads `` `find "$SESSION_DIR/round-<N>" -maxdepth 1 -name 'verdicts-*.json' -delete 2>/dev/null` ``
again, and `git diff --stat HEAD -- plugins/superheroes/skills/review-code/reference/verification-pass.md`
shows nothing (the file is byte-clean against HEAD).

**Raw green:** the single green run above; its last assertions also require the plain `find … -delete`
span of that file to be counted as a non-compound delete.

---

## (c) Diff halt

**Neutralization:** removed ` || { echo "review-code: git diff against $BASE_REF FAILED — refusing to review the artifact it left behind (#637)" >&2; exit 1; }`
from the `mv` line (`SKILL.md:153`), leaving `mv "$SESSION_DIR/round-<round>/diff.txt.tmp" "$SESSION_DIR/round-<round>/diff.txt"`.

**Raw red** (node `...::test_the_diff_recipe_halts_on_each_failure`; the echoed test source above the
failing line is elided, 31 lines, identical to the test file; cases (a) and (b) passed, since the run
reached case (c)):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
__________________ test_the_diff_recipe_halts_on_each_failure __________________
        # (c) mv fails (a PATH shim whose mv only exits 1)
        moved = run(first, path=_failing_mv_path(tmp_path))
        assert moved.returncode == 1, (moved.returncode, moved.stderr)
>       assert "git diff against %s FAILED" % first in moved.stderr
E       AssertionError: assert ('git diff against %s FAILED' % '9ace56eee51e36d3eba221547a8b6307f59739e3') in 'review-code: round diff against 9ace56eee51e36d3eba221547a8b6307f59739e3 is EMPTY — an empty review surface is never certifiable-clean; halt and investigate (#637)\n'
E        +  where 'review-code: round diff against 9ace56eee51e36d3eba221547a8b6307f59739e3 is EMPTY — an empty review surface is never certifiable-clean; halt and investigate (#637)\n' = CompletedProcess(args=['bash', '-c', 'git diff --no-ext-diff --no-textconv --no-color -M -U3 --src-prefix=a/ --dst-pre...eba221547a8b6307f59739e3 is EMPTY — an empty review surface is never certifiable-clean; halt and investigate (#637)\n').stderr
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_code_recipes_no_compound_delete.py::test_the_diff_recipe_halts_on_each_failure
1 failed in 4.94s
```
The red is on the claimed axis and is the output the order predicted: exit 1 held (the unchanged
empty-diff guard stopped the script, so `REACHED-END` was not printed), but the message is `is EMPTY`
instead of the expected `FAILED`.

**Restore:** by the inverse Edit, re-appended the removed ` || { … }` to the `mv` line.

**Restore receipt:** `SKILL.md:152-154` read back after the restore:
```
git diff --no-ext-diff --no-textconv --no-color -M -U3 --src-prefix=a/ --dst-prefix=b/ "$BASE_REF"...HEAD > "$SESSION_DIR/round-<round>/diff.txt.tmp" || { echo "review-code: git diff against $BASE_REF FAILED — refusing to review the artifact it left behind (#637)" >&2; exit 1; }
mv "$SESSION_DIR/round-<round>/diff.txt.tmp" "$SESSION_DIR/round-<round>/diff.txt" || { echo "review-code: git diff against $BASE_REF FAILED — refusing to review the artifact it left behind (#637)" >&2; exit 1; }
[ -s "$SESSION_DIR/round-<round>/diff.txt" ] || { echo "review-code: round diff against $BASE_REF is EMPTY — an empty review surface is never certifiable-clean; halt and investigate (#637)" >&2; exit 1; }
```

**Raw green:** the single green run above.

---

## (d) Empty guard

**Neutralization:** deleted the whole guard line `[ -s "$SESSION_DIR/round-<round>/diff.txt" ] || { echo "review-code: round diff against $BASE_REF is EMPTY — … (#637)" >&2; exit 1; }`
(`SKILL.md:154`).

**Raw red** (same node as (c); echoed test source elided, 36 lines; cases (a) to (c) passed):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
__________________ test_the_diff_recipe_halts_on_each_failure __________________
        # (d) an empty diff: the guard halts
        empty = run(head)
>       assert empty.returncode == 1, (empty.returncode, empty.stderr)
E       AssertionError: (0, '')
E       assert 0 == 1
E        +  where 0 = CompletedProcess(args=['bash', '-c', 'git diff --no-ext-diff --no-textconv --no-color -M -U3 --src-prefix=a/ --dst-pre...rtifact it left behind (#637)" >&2; exit 1; }\n\necho REACHED-END\n'], returncode=0, stdout='REACHED-END\n', stderr='').returncode
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_code_recipes_no_compound_delete.py::test_the_diff_recipe_halts_on_each_failure
1 failed in 0.31s
```
The red is on the claimed axis: with no guard an empty diff runs to the end (exit 0, `REACHED-END`).

**Restore:** by the inverse Edit, re-inserted the guard line directly after the `mv` line.

**Restore receipt:** the three-line quote under (c)'s restore receipt is the file as read back after
this restore too (the same text; (c)'s receipt was read before (d) was applied, and `SKILL.md`'s
`git diff HEAD` after all restores shows the guard line present and unchanged from HEAD).

**Raw green:** the single green run above.

---

## (e) meta.json halt

**Neutralization:** removed ` || { echo "review-code: could not write meta.json — halting rather than continuing without the session record (#637)" >&2; exit 1; }`
from the `mv "$SESSION_DIR/meta.json.tmp" "$SESSION_DIR/meta.json"` line (`SKILL.md:177`).

**Raw red** (node `...::test_the_meta_json_recipe_halts_on_each_failure`; echoed test source elided, 29
lines; cases (a) and (b) passed):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_______________ test_the_meta_json_recipe_halts_on_each_failure ________________
        # (c) mv fails (a PATH shim whose mv only exits 1)
        moved = run(session, path=_failing_mv_path(tmp_path))
>       assert moved.returncode == 1, (moved.returncode, moved.stderr)
E       AssertionError: (0, '')
E       assert 0 == 1
E        +  where 0 = CompletedProcess(args=['bash', '-c', '# The orchestrator sets FOCUS_JSON from the `--focus` argument (if any) before t...N_DIR/meta.json.tmp" "$SESSION_DIR/meta.json"\n\necho REACHED-END\n'], returncode=0, stdout='REACHED-END\n', stderr='').returncode
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_code_recipes_no_compound_delete.py::test_the_meta_json_recipe_halts_on_each_failure
1 failed in 0.36s
```
The red is on the claimed axis: with no `||` the failed `mv` is swallowed and the recipe runs on to the end.

**Restore:** by the inverse Edit, re-appended the removed ` || { … }` to the `mv` line.

**Restore receipt:** `SKILL.md:176-177` read back:
```
  > "$SESSION_DIR/meta.json.tmp" || { echo "review-code: could not write meta.json — halting rather than continuing without the session record (#637)" >&2; exit 1; }
mv "$SESSION_DIR/meta.json.tmp" "$SESSION_DIR/meta.json" || { echo "review-code: could not write meta.json — halting rather than continuing without the session record (#637)" >&2; exit 1; }
```

**Raw green:** the single green run above.
