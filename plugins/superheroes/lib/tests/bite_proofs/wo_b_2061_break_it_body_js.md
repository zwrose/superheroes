# WO-B2 (#2061) bite-proof — a JavaScript or TypeScript break-it test counts as kept by its body at any path

**Provenance:** claude / sonnet-5.5 (implementer, work order B2, layer 2 of the #2053 stack), maker family anthropic. `plugins/superheroes/lib/break_it_body_js.py` (the JS/TS front, trimmed from 624 to 426 lines), `plugins/superheroes/lib/break_it_body.py` (`_FRONTS`); tests in `plugins/superheroes/lib/tests/test_break_it_body_js_2053.py` and `plugins/superheroes/lib/tests/test_break_it_body_js_e2e_2061.py`.

Declared guarded-element set (from the order): **J1**, **J2**, **J3**, **J4**, **J5**, **J6**, **J7**, **J8**, **J9**. Every element was neutralized on the post-trim code (commit `83c67ce3a`, `refactor(superheroes): route and trim the JS/TS break-it body front`) by one targeted edit (the Edit tool, exact-text match), only its proving nodes were run, by exact node id and never `-k`, the inverse edit was applied, `git diff --stat` over the file was read clean against that commit, and the same node ids were run again. No `git checkout`, `git restore`, `git reset` or `git stash` was used. Each command was `scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest <node ids> -q`, followed by `; echo "exit=$?"` to print the exit code.

## Guarded elements

| ID | Guarded element | Axis | Proving nodes | Red / green exit |
|---|---|---|---|---|
| J1 | `_Scanner._emit`, the restricted-production clause `prev[0] == "id" and prev[1] in _RESTRICTED` | after `return`, `throw`, `break`, `continue` or `yield` a line break is a statement end whatever follows | `test_break_it_body_js_2053.py::test_restricted_production_line_break_is_a_statement_end` (see disclosure) | 1 / 0 |
| J2 | `_Scanner._emit`, the `head` expression (`if`/`for`/`while`/`with`/`catch`, and `for await`) | the `)` closing such a head does not end an expression, so no automatic `;` follows it | `test_break_it_body_js_2053.py::test_head_paren_line_break_is_not_a_statement_end` | 1 / 0 |
| J3 | `_Scanner._drop_trailing_comma`, the `self.out[m] != _COMMA and self.out[m] not in _OPENERS` guard | a comma after an opener or another comma is an array hole and stays | `test_break_it_body_js_2053.py::test_array_hole_commas_are_kept` | 1 / 0 |
| J4 | `_Scanner.run`, the `self.out.append(("comment", ...))` | comments stay in the key as tokens, so an added or removed directive reads unequal | `test_break_it_body_js_2053.py::test_added_ts_ignore_reads_unequal`, `::test_removed_ts_expect_error_reads_unequal`, `::test_a_different_comment_text_reads_unequal` | 1 / 0 |
| J5 | `_keyed`, the `not prior or prior[-1] in _STATEMENT_START` condition | a title slot is a call at statement start, not an expression that happens to be named `it` | `test_break_it_body_js_2053.py::test_title_slot_needs_statement_start` | 1 / 0 |
| J6 | `_framework_names`, the `name not in bound and imported.get(name, set()) <= _FRAMEWORK_MODULES` condition | a callee the file binds or imports from a non-framework module is not a framework name | `test_break_it_body_js_2053.py::test_non_framework_callee_at_statement_start_is_not_a_title_slot`, `::test_a_non_framework_callee_leaves_no_title` (see disclosure) | 1 / 0 |
| J7 | `_Scanner._put_semi`, the `insert(self._sig_at() + 1, ...)` position | a semicolon, written or automatic, sits before the comments that precede it | `test_break_it_body_js_2053.py::test_semicolon_moves_before_preceding_comments` | 1 / 0 |
| J8 | `_read_string`, the `raise ValueError("unterminated string")` | an unterminated string, or one cut by a line break, raises instead of reading as text | `test_break_it_body_js_2053.py::test_unterminated_string_raises`, `test_break_it_body_js_e2e_2061.py::test_a_prefilter_passing_unparseable_candidate_is_unresolved_beside_a_match` | 1 / 0 |
| J9 | `break_it_body.py` `_FRONTS`, the `"break_it_body_js"` entry | a `.ts` break-it test is searched at all | `test_break_it_body_js_e2e_2061.py::test_a_ts_test_folded_into_a_host_with_merged_vitest_imports_is_kept_and_runs_the_host` (e2e row (a)) | 1 / 0 |

## Disclosures

- Every element went red under its neutralization (pytest exit 1) and green after the restore (exit 0). Every restore receipt is `git diff --stat -- <file>` printing nothing, read against `83c67ce3a`.
- **J1.** Two nodes were run in both halves. Under the neutralization only `test_restricted_production_line_break_is_a_statement_end` went red; `test_return_line_break_is_not_return_space` stayed green, because `return` is not in `_NOT_END_IDS` and the number `1` already starts an expression, so the automatic `;` comes from the generic rule. That node does not discriminate J1 and is not counted as its proof. The restricted node is red on the axis: its first pair `return⏎(1)` reads equal to `return (1)` once the clause is gone, because `(` does not start an expression.
- **J6.** Three nodes were run in both halves. `test_a_callee_bound_to_a_const_in_the_same_line_is_not_a_title_slot` stayed green under the neutralization, because its `test("bad")` is not at statement start, so J5 alone decides it. It does not discriminate J6 and is not counted as its proof.
- **J2.** The proving node asserts its pairs in order and stops at the first red one (`if (x)⏎foo()`); the other head forms are in the same node but were not individually neutralized. The `before not in _MEMBER` exception (`a.if (x)`) has no node of its own in the unit file and is therefore **unproven** inside J2.
- **J8.** The second node is the end-to-end view of the same raise: with it gone the broken candidate parses, the search finds two matches, and the row reads `match-ambiguous` instead of `body-unparseable`.
- All captures are well under 32 KiB, so none is written off-repo. Nothing in the captures is redacted.

---

## J1 — the restricted-production automatic `;`

- **axis:** after `return`, `throw`, `break`, `continue` or `yield` a line break is a statement end whatever follows

**neutralization** (`plugins/superheroes/lib/break_it_body_js.py`, `_Scanner._emit`):
```diff
-            if (prev[0] == "id" and prev[1] in _RESTRICTED) or (self.p_ends and starts):
+            if self.p_ends and starts:
```

**command:** `scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_break_it_body_js_2053.py::test_return_line_break_is_not_return_space plugins/superheroes/lib/tests/test_break_it_body_js_2053.py::test_restricted_production_line_break_is_a_statement_end -q`

**raw red** (exit 1):
```
.F                                                                       [100%]
=================================== FAILURES ===================================
___________ test_restricted_production_line_break_is_a_statement_end ___________

    def test_restricted_production_line_break_is_a_statement_end():
        pairs = [
            ("function f() {\n  return\n  (1)\n}", "function f() { return (1) }"),
            ("function f() {\n  return\n  [1]\n}", "function f() { return [1] }"),
            ("function f() {\n  return\n}", "function f() { return }"),
            ("function f() {\n  throw\n  (e)\n}", "function f() { throw (e) }"),
            ("function* g() {\n  yield\n  (1)\n}", "function* g() { yield (1) }"),
            ("while (1) {\n  break\n}", "while (1) { break }"),
            ("while (1) {\n  continue\n}", "while (1) { continue }"),
        ]
        for a, b in pairs:
>           _assert_differ(a, b)

/Users/zwrose/.superheroes-worktrees/superheroes/issue-2061-wo-b2/plugins/superheroes/lib/tests/test_break_it_body_js_2053.py:149: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

a = 'function f() {\n  return\n  (1)\n}', b = 'function f() { return (1) }'

    def _assert_differ(a, b):
>       assert _keys(a) != _keys(b), (a, b)
E       AssertionError: ('function f() {
E           return
E           (1)
E         }', 'function f() { return (1) }')
E       assert [(('id', 'function'), ('id', 'f'), ('punct', '('), ('punct', ')'), ('punct', '{'), ('id', 'return'), ...)] != [(('id', 'function'), ('id', 'f'), ('punct', '('), ('punct', ')'), ('punct', '{'), ('id', 'return'), ...)]
E        +  where [(('id', 'function'), ('id', 'f'), ('punct', '('), ('punct', ')'), ('punct', '{'), ('id', 'return'), ...)] = _keys('function f() {\n  return\n  (1)\n}')
E        +  and   [(('id', 'function'), ('id', 'f'), ('punct', '('), ('punct', ')'), ('punct', '{'), ('id', 'return'), ...)] = _keys('function f() { return (1) }')

/Users/zwrose/.superheroes-worktrees/superheroes/issue-2061-wo-b2/plugins/superheroes/lib/tests/test_break_it_body_js_2053.py:27: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_body_js_2053.py::test_restricted_production_line_break_is_a_statement_end
1 failed, 1 passed in 0.69s
exit=1
```

**restore:** the inverse edit put `if (prev[0] == "id" and prev[1] in _RESTRICTED) or (self.p_ends and starts):` back.

**restore receipt:** `git diff --stat -- plugins/superheroes/lib/break_it_body_js.py` printed nothing.

**raw green** (exit 0):
```
..                                                                       [100%]
2 passed in 0.64s
exit=0
```

## J2 — the `if`/`for`/`while`/`with`/`catch` head exception

- **axis:** the `)` closing such a head does not end an expression, so no automatic `;` follows it

**neutralization** (`break_it_body_js.py`, `_Scanner._emit`, the second line of the `head` expression):
```diff
-                (prev[1] in _HEAD_IDS and before not in _MEMBER) or (prev[1] == "await" and before == ("id", "for")))
+                False)
```

**command:** `scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_break_it_body_js_2053.py::test_head_paren_line_break_is_not_a_statement_end -q`

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
______________ test_head_paren_line_break_is_not_a_statement_end _______________

    def test_head_paren_line_break_is_not_a_statement_end():
        pairs = [
            ("if (x)\n  foo()", "if (x) foo()"),
            ("for (const a of b)\n  foo()", "for (const a of b) foo()"),
            ("for await (const a of b)\n  foo()", "for await (const a of b) foo()"),
            ("while (x)\n  foo()", "while (x) foo()"),
            ("with (o)\n  foo()", "with (o) foo()"),
            # not valid JS: the catch head is only reachable by scanner-level text, since a valid catch is followed by `{`
            ("try { a() } catch (e)\n  foo()", "try { a() } catch (e) foo()"),
        ]
        for a, b in pairs:
>           _assert_same(a, b)

/Users/zwrose/.superheroes-worktrees/superheroes/issue-2061-wo-b2/plugins/superheroes/lib/tests/test_break_it_body_js_2053.py:171: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

a = 'if (x)\n  foo()', b = 'if (x) foo()'

    def _assert_same(a, b):
>       assert _keys(a) == _keys(b), (a, b)
E       AssertionError: ('if (x)
E           foo()', 'if (x) foo()')
E       assert [(('id', 'if'...punct', ';'))] == [(('id', 'if'...', '('), ...)]
E         
E         At index 0 diff: (('id', 'if'), ('punct', '('), ('id', 'x'), ('punct', ')'), ('punct', ';')) != (('id', 'if'), ('punct', '('), ('id', 'x'), ('punct', ')'), ('id', 'foo'), ('punct', '('), ('punct', ')'), ('punct', ';'))
E         Left contains one more item: (('id', 'foo'), ('punct', '('), ('punct', ')'), ('punct', ';'))
E         Use -v to get more diff

/Users/zwrose/.superheroes-worktrees/superheroes/issue-2061-wo-b2/plugins/superheroes/lib/tests/test_break_it_body_js_2053.py:23: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_body_js_2053.py::test_head_paren_line_break_is_not_a_statement_end
1 failed in 1.86s
exit=1
```

**restore:** the inverse edit put the original second line of the `head` expression back.

**restore receipt:** `git diff --stat -- plugins/superheroes/lib/break_it_body_js.py` printed nothing.

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.26s
exit=0
```

## J3 — the array-hole comma keep

- **axis:** a comma after an opener or another comma is an array hole and stays

**neutralization** (`break_it_body_js.py`, `_Scanner._drop_trailing_comma`):
```diff
-        if k >= 0 and m >= 0 and self.out[k] == _COMMA and self.out[m] != _COMMA and self.out[m] not in _OPENERS:
+        if k >= 0 and m >= 0 and self.out[k] == _COMMA:
```

**command:** `scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_break_it_body_js_2053.py::test_array_hole_commas_are_kept -q`

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_______________________ test_array_hole_commas_are_kept ________________________

    def test_array_hole_commas_are_kept():
>       _assert_differ("const a = [,]", "const a = []")

/Users/zwrose/.superheroes-worktrees/superheroes/issue-2061-wo-b2/plugins/superheroes/lib/tests/test_break_it_body_js_2053.py:179: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

a = 'const a = [,]', b = 'const a = []'

    def _assert_differ(a, b):
>       assert _keys(a) != _keys(b), (a, b)
E       AssertionError: ('const a = [,]', 'const a = []')
E       assert [(('id', 'const'), ('id', 'a'), ('punct', '='), ('punct', '['), ('punct', ']'), ('punct', ';'))] != [(('id', 'const'), ('id', 'a'), ('punct', '='), ('punct', '['), ('punct', ']'), ('punct', ';'))]
E        +  where [(('id', 'const'), ('id', 'a'), ('punct', '='), ('punct', '['), ('punct', ']'), ('punct', ';'))] = _keys('const a = [,]')
E        +  and   [(('id', 'const'), ('id', 'a'), ('punct', '='), ('punct', '['), ('punct', ']'), ('punct', ';'))] = _keys('const a = []')

/Users/zwrose/.superheroes-worktrees/superheroes/issue-2061-wo-b2/plugins/superheroes/lib/tests/test_break_it_body_js_2053.py:27: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_body_js_2053.py::test_array_hole_commas_are_kept
1 failed in 0.19s
exit=1
```

**restore:** the inverse edit put `and self.out[m] != _COMMA and self.out[m] not in _OPENERS:` back.

**restore receipt:** `git diff --stat -- plugins/superheroes/lib/break_it_body_js.py` printed nothing.

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.15s
exit=0
```

## J4 — comments kept as tokens

- **axis:** comments stay in the key as tokens, so an added or removed directive reads unequal

**neutralization** (`break_it_body_js.py`, `_Scanner.run`):
```diff
-                self.out.append(("comment", _normalise_comment(body, block)))
+                pass
```

**command:** `scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_break_it_body_js_2053.py::test_added_ts_ignore_reads_unequal plugins/superheroes/lib/tests/test_break_it_body_js_2053.py::test_removed_ts_expect_error_reads_unequal plugins/superheroes/lib/tests/test_break_it_body_js_2053.py::test_a_different_comment_text_reads_unequal -q`

**raw red** (exit 1):
```
FFF                                                                      [100%]
=================================== FAILURES ===================================
______________________ test_added_ts_ignore_reads_unequal ______________________

    def test_added_ts_ignore_reads_unequal():
>       _assert_differ("// @ts-ignore\nconst x: number = 's'", "const x: number = 's'")

/Users/zwrose/.superheroes-worktrees/superheroes/issue-2061-wo-b2/plugins/superheroes/lib/tests/test_break_it_body_js_2053.py:185: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

a = "// @ts-ignore\nconst x: number = 's'", b = "const x: number = 's'"

    def _assert_differ(a, b):
>       assert _keys(a) != _keys(b), (a, b)
E       AssertionError: ("// @ts-ignore
E         const x: number = 's'", "const x: number = 's'")
E       assert [(('id', 'const'), ('id', 'x'), ('punct', ':'), ('id', 'number'), ('punct', '='), ('str', 's'), ...)] != [(('id', 'const'), ('id', 'x'), ('punct', ':'), ('id', 'number'), ('punct', '='), ('str', 's'), ...)]
E        +  where [(('id', 'const'), ('id', 'x'), ('punct', ':'), ('id', 'number'), ('punct', '='), ('str', 's'), ...)] = _keys("// @ts-ignore\nconst x: number = 's'")
E        +  and   [(('id', 'const'), ('id', 'x'), ('punct', ':'), ('id', 'number'), ('punct', '='), ('str', 's'), ...)] = _keys("const x: number = 's'")

/Users/zwrose/.superheroes-worktrees/superheroes/issue-2061-wo-b2/plugins/superheroes/lib/tests/test_break_it_body_js_2053.py:27: AssertionError
__________________ test_removed_ts_expect_error_reads_unequal __________________

    def test_removed_ts_expect_error_reads_unequal():
>       _assert_differ("const x: number = 's'", "// @ts-expect-error\nconst x: number = 's'")

/Users/zwrose/.superheroes-worktrees/superheroes/issue-2061-wo-b2/plugins/superheroes/lib/tests/test_break_it_body_js_2053.py:190: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

a = "const x: number = 's'", b = "// @ts-expect-error\nconst x: number = 's'"

    def _assert_differ(a, b):
>       assert _keys(a) != _keys(b), (a, b)
E       AssertionError: ("const x: number = 's'", "// @ts-expect-error
E         const x: number = 's'")
E       assert [(('id', 'const'), ('id', 'x'), ('punct', ':'), ('id', 'number'), ('punct', '='), ('str', 's'), ...)] != [(('id', 'const'), ('id', 'x'), ('punct', ':'), ('id', 'number'), ('punct', '='), ('str', 's'), ...)]
E        +  where [(('id', 'const'), ('id', 'x'), ('punct', ':'), ('id', 'number'), ('punct', '='), ('str', 's'), ...)] = _keys("const x: number = 's'")
E        +  and   [(('id', 'const'), ('id', 'x'), ('punct', ':'), ('id', 'number'), ('punct', '='), ('str', 's'), ...)] = _keys("// @ts-expect-error\nconst x: number = 's'")

/Users/zwrose/.superheroes-worktrees/superheroes/issue-2061-wo-b2/plugins/superheroes/lib/tests/test_break_it_body_js_2053.py:27: AssertionError
_________________ test_a_different_comment_text_reads_unequal __________________

    def test_a_different_comment_text_reads_unequal():
>       _assert_differ("// one\nfoo()", "// two\nfoo()")

/Users/zwrose/.superheroes-worktrees/superheroes/issue-2061-wo-b2/plugins/superheroes/lib/tests/test_break_it_body_js_2053.py:205: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

a = '// one\nfoo()', b = '// two\nfoo()'

    def _assert_differ(a, b):
>       assert _keys(a) != _keys(b), (a, b)
E       AssertionError: ('// one
E         foo()', '// two
E         foo()')
E       assert [(('id', 'foo'), ('punct', '('), ('punct', ')'), ('punct', ';'))] != [(('id', 'foo'), ('punct', '('), ('punct', ')'), ('punct', ';'))]
E        +  where [(('id', 'foo'), ('punct', '('), ('punct', ')'), ('punct', ';'))] = _keys('// one\nfoo()')
E        +  and   [(('id', 'foo'), ('punct', '('), ('punct', ')'), ('punct', ';'))] = _keys('// two\nfoo()')

/Users/zwrose/.superheroes-worktrees/superheroes/issue-2061-wo-b2/plugins/superheroes/lib/tests/test_break_it_body_js_2053.py:27: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_body_js_2053.py::test_added_ts_ignore_reads_unequal
FAILED plugins/superheroes/lib/tests/test_break_it_body_js_2053.py::test_removed_ts_expect_error_reads_unequal
FAILED plugins/superheroes/lib/tests/test_break_it_body_js_2053.py::test_a_different_comment_text_reads_unequal
3 failed in 0.22s
exit=1
```

**restore:** the inverse edit put `self.out.append(("comment", _normalise_comment(body, block)))` back.

**restore receipt:** `git diff --stat -- plugins/superheroes/lib/break_it_body_js.py` printed nothing.

**raw green** (exit 0):
```
...                                                                      [100%]
3 passed in 0.22s
exit=0
```

## J5 — the statement-start condition on title slots

- **axis:** a title slot is a call at statement start, not an expression that happens to be named `it`

**neutralization** (`break_it_body_js.py`, `_keyed`):
```diff
-        if not prior or prior[-1] in _STATEMENT_START:
+        if True:
```

**command:** `scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_break_it_body_js_2053.py::test_title_slot_needs_statement_start -q`

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
____________________ test_title_slot_needs_statement_start _____________________

    def test_title_slot_needs_statement_start():
        # `it` is the global framework name here, so only the statement-start condition decides
>       _assert_differ('const f = it("a")', 'const f = it("b")')

/Users/zwrose/.superheroes-worktrees/superheroes/issue-2061-wo-b2/plugins/superheroes/lib/tests/test_break_it_body_js_2053.py:215: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

a = 'const f = it("a")', b = 'const f = it("b")'

    def _assert_differ(a, b):
>       assert _keys(a) != _keys(b), (a, b)
E       AssertionError: ('const f = it("a")', 'const f = it("b")')
E       assert [(('id', 'const'), ('id', 'f'), ('punct', '='), ('id', 'it'), ('punct', '('), ('str', '\x00title'), ...)] != [(('id', 'const'), ('id', 'f'), ('punct', '='), ('id', 'it'), ('punct', '('), ('str', '\x00title'), ...)]
E        +  where [(('id', 'const'), ('id', 'f'), ('punct', '='), ('id', 'it'), ('punct', '('), ('str', '\x00title'), ...)] = _keys('const f = it("a")')
E        +  and   [(('id', 'const'), ('id', 'f'), ('punct', '='), ('id', 'it'), ('punct', '('), ('str', '\x00title'), ...)] = _keys('const f = it("b")')

/Users/zwrose/.superheroes-worktrees/superheroes/issue-2061-wo-b2/plugins/superheroes/lib/tests/test_break_it_body_js_2053.py:27: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_body_js_2053.py::test_title_slot_needs_statement_start
1 failed in 0.16s
exit=1
```

**restore:** the inverse edit put `if not prior or prior[-1] in _STATEMENT_START:` back.

**restore receipt:** `git diff --stat -- plugins/superheroes/lib/break_it_body_js.py` printed nothing.

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.17s
exit=0
```

## J6 — the framework-name condition on title slots

- **axis:** a callee the file binds or imports from a non-framework module is not a framework name

**neutralization** (`break_it_body_js.py`, `_framework_names`):
```diff
-        if name not in bound and imported.get(name, set()) <= _FRAMEWORK_MODULES)
+        if True)
```

**command:** `scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_break_it_body_js_2053.py::test_non_framework_callee_at_statement_start_is_not_a_title_slot plugins/superheroes/lib/tests/test_break_it_body_js_2053.py::test_a_non_framework_callee_leaves_no_title plugins/superheroes/lib/tests/test_break_it_body_js_2053.py::test_a_callee_bound_to_a_const_in_the_same_line_is_not_a_title_slot -q`

**raw red** (exit 1):
```
FF.                                                                      [100%]
=================================== FAILURES ===================================
_______ test_non_framework_callee_at_statement_start_is_not_a_title_slot _______

    def test_non_framework_callee_at_statement_start_is_not_a_title_slot():
        # the callee is at statement start, so only the framework-name condition decides
>       _assert_differ('import { it } from "./helpers"\nit("a", f)', 'import { it } from "./helpers"\nit("b", f)')

/Users/zwrose/.superheroes-worktrees/superheroes/issue-2061-wo-b2/plugins/superheroes/lib/tests/test_break_it_body_js_2053.py:224: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

a = 'import { it } from "./helpers"\nit("a", f)'
b = 'import { it } from "./helpers"\nit("b", f)'

    def _assert_differ(a, b):
>       assert _keys(a) != _keys(b), (a, b)
E       AssertionError: ('import { it } from "./helpers"
E         it("a", f)', 'import { it } from "./helpers"
E         it("b", f)')
E       assert [(('id', 'import'), ('punct', '{'), ('id', 'it'), ('punct', '}'), ('id', 'from'), ('str', './helpers'), ...), (('id', 'it'), ('punct', '('), ('str', '\x00title'), ('punct', ','), ('id', 'f'), ('punct', ')'), ...)] != [(('id', 'import'), ('punct', '{'), ('id', 'it'), ('punct', '}'), ('id', 'from'), ('str', './helpers'), ...), (('id', 'it'), ('punct', '('), ('str', '\x00title'), ('punct', ','), ('id', 'f'), ('punct', ')'), ...)]
E        +  where [(('id', 'import'), ('punct', '{'), ('id', 'it'), ('punct', '}'), ('id', 'from'), ('str', './helpers'), ...), (('id', 'it'), ('punct', '('), ('str', '\x00title'), ('punct', ','), ('id', 'f'), ('punct', ')'), ...)] = _keys('import { it } from "./helpers"\nit("a", f)')
E        +  and   [(('id', 'import'), ('punct', '{'), ('id', 'it'), ('punct', '}'), ('id', 'from'), ('str', './helpers'), ...), (('id', 'it'), ('punct', '('), ('str', '\x00title'), ('punct', ','), ('id', 'f'), ('punct', ')'), ...)] = _keys('import { it } from "./helpers"\nit("b", f)')

/Users/zwrose/.superheroes-worktrees/superheroes/issue-2061-wo-b2/plugins/superheroes/lib/tests/test_break_it_body_js_2053.py:27: AssertionError
_________________ test_a_non_framework_callee_leaves_no_title __________________

    def test_a_non_framework_callee_leaves_no_title():
        recs =front.parse('import { it } from "./helpers"\nit("a", f)')
>       assert recs[1]["titles"] == ()
E       AssertionError: assert ('a',) == ()
E         
E         Left contains one more item: 'a'
E         Use -v to get more diff

/Users/zwrose/.superheroes-worktrees/superheroes/issue-2061-wo-b2/plugins/superheroes/lib/tests/test_break_it_body_js_2053.py:236: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_body_js_2053.py::test_non_framework_callee_at_statement_start_is_not_a_title_slot
FAILED plugins/superheroes/lib/tests/test_break_it_body_js_2053.py::test_a_non_framework_callee_leaves_no_title
2 failed, 1 passed in 0.30s
exit=1
```

**restore:** the inverse edit put `if name not in bound and imported.get(name, set()) <= _FRAMEWORK_MODULES)` back.

**restore receipt:** `git diff --stat -- plugins/superheroes/lib/break_it_body_js.py` printed nothing.

**raw green** (exit 0):
```
...                                                                      [100%]
3 passed in 0.28s
exit=0
```

## J7 — the semicolon-before-comment move

- **axis:** a semicolon, written or automatic, sits before the comments that precede it

**neutralization** (`break_it_body_js.py`, `_Scanner._put_semi`):
```diff
-        self.out.insert(self._sig_at() + 1, _SEMI)
+        self.out.append(_SEMI)
```

**command:** `scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_break_it_body_js_2053.py::test_semicolon_moves_before_preceding_comments -q`

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
________________ test_semicolon_moves_before_preceding_comments ________________

    def test_semicolon_moves_before_preceding_comments():
>       _assert_same("a // c\nb", "a; // c\nb")

/Users/zwrose/.superheroes-worktrees/superheroes/issue-2061-wo-b2/plugins/superheroes/lib/tests/test_break_it_body_js_2053.py:262: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

a = 'a // c\nb', b = 'a; // c\nb'

    def _assert_same(a, b):
>       assert _keys(a) == _keys(b), (a, b)
E       AssertionError: ('a // c
E         b', 'a; // c
E         b')
E       assert [(('id', 'a')...punct', ';'))] == [(('id', 'a')...punct', ';'))]
E         
E         At index 0 diff: (('id', 'a'), ('comment', 'c'), ('punct', ';')) != (('id', 'a'), ('punct', ';'))
E         Use -v to get more diff

/Users/zwrose/.superheroes-worktrees/superheroes/issue-2061-wo-b2/plugins/superheroes/lib/tests/test_break_it_body_js_2053.py:23: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_body_js_2053.py::test_semicolon_moves_before_preceding_comments
1 failed in 0.18s
exit=1
```

**restore:** the inverse edit put `self.out.insert(self._sig_at() + 1, _SEMI)` back.

**restore receipt:** `git diff --stat -- plugins/superheroes/lib/break_it_body_js.py` printed nothing.

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.10s
exit=0
```

## J8 — the unterminated-string `ValueError`

- **axis:** an unterminated string, or one cut by a line break, raises instead of reading as text

**neutralization** (`break_it_body_js.py`, `_read_string`):
```diff
-        raise ValueError("unterminated string")
+        return len(text), text[i + 1:]
```

**command:** `scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_break_it_body_js_2053.py::test_unterminated_string_raises plugins/superheroes/lib/tests/test_break_it_body_js_e2e_2061.py::test_a_prefilter_passing_unparseable_candidate_is_unresolved_beside_a_match -q`

**raw red** (exit 1):
```
FF                                                                       [100%]
=================================== FAILURES ===================================
_______________________ test_unterminated_string_raises ________________________

    def test_unterminated_string_raises():
        for text in ['x = "abc', "x = 'abc\ndef'", 'x = "abc\\', "x = 'abc\r\n'"]:
>           with pytest.raises(ValueError):
                 ^^^^^^^^^^^^^^^^^^^^^^^^^
E           Failed: DID NOT RAISE ValueError

/Users/zwrose/.superheroes-worktrees/superheroes/issue-2061-wo-b2/plugins/superheroes/lib/tests/test_break_it_body_js_2053.py:468: Failed
_ test_a_prefilter_passing_unparseable_candidate_is_unresolved_beside_a_match __

repo = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-237/test_a_prefilter_passing_unpar0/repo')

    def test_a_prefilter_passing_unparseable_candidate_is_unresolved_beside_a_match(repo):
        broken = ORIG + '\nconst broken = "oops\n'
        base, head = _stage(repo, {HOST: _host(), "web/broken.test.ts": broken})
        calls = []
>       assert _got(_check(repo, base, head, _record(), _stub(calls))) == ("unresolved", "body-unparseable")
E       AssertionError: assert ('unresolved'...ch-ambiguous') == ('unresolved'...-unparseable')
E         
E         At index 1 diff: 'match-ambiguous' != 'body-unparseable'
E         Use -v to get more diff

/Users/zwrose/.superheroes-worktrees/superheroes/issue-2061-wo-b2/plugins/superheroes/lib/tests/test_break_it_body_js_e2e_2061.py:198: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_body_js_2053.py::test_unterminated_string_raises
FAILED plugins/superheroes/lib/tests/test_break_it_body_js_e2e_2061.py::test_a_prefilter_passing_unparseable_candidate_is_unresolved_beside_a_match
2 failed in 0.30s
exit=1
```

**restore:** the inverse edit put `raise ValueError("unterminated string")` back.

**restore receipt:** `git diff --stat -- plugins/superheroes/lib/break_it_body_js.py` printed nothing.

**raw green** (exit 0):
```
..                                                                       [100%]
2 passed in 0.31s
exit=0
```

## J9 — the `_FRONTS` routing entry

- **axis:** a `.ts` break-it test is searched at all (e2e row (a), the weekly-eats shape)

**neutralization** (`plugins/superheroes/lib/break_it_body.py`):
```diff
-_FRONTS = ("break_it_body_py", "break_it_body_js")
+_FRONTS = ("break_it_body_py",)
```

**command:** `scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_break_it_body_js_e2e_2061.py::test_a_ts_test_folded_into_a_host_with_merged_vitest_imports_is_kept_and_runs_the_host -q`

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_ts_test_folded_into_a_host_with_merged_vitest_imports_is_kept_and_runs_the_host _

repo = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-241/test_a_ts_test_folded_into_a_h0/repo')

    def test_a_ts_test_folded_into_a_host_with_merged_vitest_imports_is_kept_and_runs_the_host(repo):
        base, head = _stage(repo, {HOST: _host()})
        calls = []
        result = _check(repo, base, head, _record(), _stub(calls))
>       assert _got(result) == ("kept", "body-match")
E       AssertionError: assert ('missing', 'not-in-head') == ('kept', 'body-match')
E         
E         At index 0 diff: 'missing' != 'kept'
E         Use -v to get more diff

/Users/zwrose/.superheroes-worktrees/superheroes/issue-2061-wo-b2/plugins/superheroes/lib/tests/test_break_it_body_js_e2e_2061.py:143: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_body_js_e2e_2061.py::test_a_ts_test_folded_into_a_host_with_merged_vitest_imports_is_kept_and_runs_the_host
1 failed in 0.29s
exit=1
```

**restore:** the inverse edit put `_FRONTS = ("break_it_body_py", "break_it_body_js")` back.

**restore receipt:** `git diff --stat -- plugins/superheroes/lib/break_it_body.py` printed nothing.

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.27s
exit=0
```
