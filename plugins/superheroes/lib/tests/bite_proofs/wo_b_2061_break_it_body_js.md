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

---

## B3 — closed-world host check

**Provenance:** claude / sonnet-5.5 (implementer, work order B3, layer 2 of the #2053 stack, issue #2061), maker family anthropic. `plugins/superheroes/lib/break_it_body_js.py` (`_allowed_host` and its helpers replace `_is_hook`, `_HOOKS` and `_HOOK_OBJECTS`); tests in `plugins/superheroes/lib/tests/test_break_it_body_js_2053.py` and `plugins/superheroes/lib/tests/test_break_it_body_js_e2e_2061.py`.

Declared guarded-element set (from the order): **K1**, **K2**, **K3**, **K4**. Every element was neutralized on the implementation commit `887f5020a` (`fix(superheroes): a moved JS/TS break-it test's host may only add plain code and its own tests around it`) by one targeted edit (the Edit tool, exact-text match). Only its proving nodes were run, by exact node id and never `-k`; the inverse edit was applied; `git diff --stat -- plugins/superheroes/lib/break_it_body_js.py` was read empty against that commit; and the same node ids were run again. No `git checkout`, `git restore`, `git reset` or `git stash` was used. Each command was `scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest <node ids> -q -n auto`, followed by `; echo "exit=$?"` to print the exit code.

| ID | Guarded element | Axis | Proving nodes | Red / green exit |
|---|---|---|---|---|
| K1 | `_registration`, the `len(callee) != 1` clause | a test registration's callee is the bare framework name, so member access (`it.only`, `describe.skip`) is a hook | `test_break_it_body_js_2053.py::test_allowed_host_refuses[it-only]`, `::test_allowed_host_refuses[describe-skip]`, `test_break_it_body_js_e2e_2061.py::test_a_host_it_only_is_host_setup` | 1 / 0 |
| K2 | `_allowed_host`, the `any(local is not None for local, _ in imports)` return of the import branch | an import that binds no name runs its module for effects, so it is a hook | `test_break_it_body_js_2053.py::test_allowed_host_refuses[side-effect-import]`, `test_break_it_body_js_e2e_2061.py::test_a_host_side_effect_import_is_host_setup` | 1 / 0 |
| K3 | `_plain`, the `tok == _LPAREN and called` refusal | a call in an initialiser (a `(` after an identifier or a closing bracket) makes the declaration a hook | `test_break_it_body_js_2053.py::test_allowed_host_refuses[call-in-initializer]`, `::test_allowed_host_refuses[call-in-second-declarator]` | 1 / 0 |
| K4 | `_parse`, the `"hook": not _allowed_host(sig, frameworks)` wiring | every record's hook flag is the allowlist's refusal | `test_break_it_body_js_2053.py::test_hook_ignores_a_leading_comment`, `::test_a_registration_needs_its_callee_to_be_a_framework_name`, `test_break_it_body_js_e2e_2061.py::test_a_host_top_level_before_each_is_host_setup`, `::test_a_host_it_only_is_host_setup`, `::test_a_host_side_effect_import_is_host_setup` | 1 / 0 |

### Disclosures

- Every element went red under its neutralization (pytest exit 1) and green after the restore (exit 0). Every restore receipt is `git diff --stat -- plugins/superheroes/lib/break_it_body_js.py` printing nothing (its own exit 0), read against `887f5020a`, plus a `grep -n` quoting the restored line.
- **K2.** The first red run of K2 was piped through `grep -v` to drop pytest's echo of the parametrize list, which the order does not permit for a bite-proof capture. It was discarded and the red half re-run unfiltered; the capture below is the unfiltered one. That discarded run is one of the spare runs.
- The parametrized nodes' failure output includes pytest's full echo of the `@pytest.mark.parametrize` list; it is kept verbatim.
- All captures are well under 32 KiB, so none is written off-repo. Nothing in the captures is redacted.

### K1 — the bare-callee clause of a test registration

- **axis:** a registration's callee is the bare framework name, so `it.only` and `describe.skip` are hooks

**neutralization** (`plugins/superheroes/lib/break_it_body_js.py`, `_registration`):
```diff
-    if len(callee) != 1 or callee[0][0] != "id" or callee[0][1] not in frameworks:
+    if callee[0][0] != "id" or callee[0][1] not in frameworks:
```

**command:** `scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest "plugins/superheroes/lib/tests/test_break_it_body_js_2053.py::test_allowed_host_refuses[it-only]" "plugins/superheroes/lib/tests/test_break_it_body_js_2053.py::test_allowed_host_refuses[describe-skip]" "plugins/superheroes/lib/tests/test_break_it_body_js_e2e_2061.py::test_a_host_it_only_is_host_setup" -q -n auto`

**raw red** (exit 1):
```
bringing up nodes...
bringing up nodes...

FFF                                                                      [100%]
=================================== FAILURES ===================================
______________________ test_allowed_host_refuses[it-only] ______________________
[gw0] darwin -- Python 3.12.13 /Users/zwrose/.cache/uv/builds-v0/.tmpXpKC5q/bin/python

text = 'it.only("x", () => {})'

    @pytest.mark.parametrize("text", [
        pytest.param('import "./setup"', id="side-effect-import"),
        pytest.param('import {} from "m"', id="empty-import"),
        pytest.param('it.only("x", () => {})', id="it-only"),
        pytest.param('describe.skip("x", () => {})', id="describe-skip"),
        pytest.param('test.each([1])("x", () => {})', id="test-each"),
        pytest.param("globalThis.fetch = f;", id="global-write"),
        pytest.param("const x = load();", id="call-in-initializer"),
        pytest.param("const y = new Map();", id="new-in-initializer"),
        pytest.param("const z = await y;", id="await-in-initializer"),
        pytest.param("const t = tag`x`;", id="tagged-template"),
        pytest.param("const t = `${a}`;", id="template-substitution"),
        pytest.param("const w = (q = 1);", id="assignment-in-initializer"),
        pytest.param("const a = 1, b = load()", id="call-in-second-declarator"),
        pytest.param("const f = (() => 1)()", id="immediately-invoked-arrow"),
        pytest.param("@dec class C {}", id="decorated-class"),
        pytest.param("class C { @d m() {} }", id="decorated-member"),
        pytest.param("class C extends mk() {}", id="call-in-heritage"),
        pytest.param("class C extends tag`x` {}", id="template-in-heritage"),
        pytest.param("class C { static x = load(); }", id="static-field"),
        pytest.param("class C { static { load() } }", id="static-block"),
        pytest.param("class C { [load()] = 1 }", id="computed-key"),
        pytest.param("if (a) {}", id="if"),
        pytest.param("for (;;) {}", id="for"),
        pytest.param("try {} catch (e) {}", id="try"),
        pytest.param("{ load() }", id="bare-block"),
        pytest.param('export * from "m";', id="re-export-all"),
        pytest.param('export { a } from "m"', id="re-export"),
        pytest.param("export { a }", id="export-list"),
        pytest.param("export = x", id="export-equals"),
        pytest.param("export default foo", id="export-default-expression"),
        pytest.param("export default () => {}", id="export-default-arrow"),
        pytest.param("enum E { A }", id="enum"),
        pytest.param("const enum E { A }", id="const-enum"),
        pytest.param("function f() {} load()", id="function-then-call-on-one-line"),
        pytest.param("interface I {} load()", id="interface-then-call-on-one-line"),
        pytest.param("foo()", id="call"),
        pytest.param('describe("x", () => { globalThis.fetch = f; })', id="describe-global-write"),
        pytest.param('describe("x", () => { beforeEach(() => {}); it("y", () => {}); })', id="describe-before-each"),
        pytest.param('describe("x", () => { const k = load(); })', id="describe-call-in-initializer"),
        pytest.param('describe("x", () => { describe.skip("y", () => {}) })', id="describe-nested-skip"),
        pytest.param('describe("x", () => foo())', id="describe-expression-body"),
        pytest.param('it("x", f(), () => {})', id="call-as-argument"),
        pytest.param("it(`${load()}`, () => {})", id="substituted-title"),
        pytest.param('it("x", f)', id="identifier-callback"),
        pytest.param('it("x", () => {}, { timeout: 1 })', id="options-object"),
        pytest.param('it("x" + n, () => {})', id="concatenated-title"),
        pytest.param('it("x", () => {}, 1, 2)', id="extra-argument"),
        pytest.param('it("x", () => {})()', id="called-result"),
        pytest.param('export it("x", () => {})', id="exported-registration"),
    ])
    def test_allowed_host_refuses(text):
>       assert _allowed(text) is False
E       assert True is False
E        +  where True = _allowed('it.only("x", () => {})')

/Users/zwrose/.superheroes-worktrees/superheroes/issue-2061-wo-b2/plugins/superheroes/lib/tests/test_break_it_body_js_2053.py:519: AssertionError
___________________ test_allowed_host_refuses[describe-skip] ___________________
[gw3] darwin -- Python 3.12.13 /Users/zwrose/.cache/uv/builds-v0/.tmpXpKC5q/bin/python

text = 'describe.skip("x", () => {})'

    @pytest.mark.parametrize("text", [
        pytest.param('import "./setup"', id="side-effect-import"),
        pytest.param('import {} from "m"', id="empty-import"),
        pytest.param('it.only("x", () => {})', id="it-only"),
        pytest.param('describe.skip("x", () => {})', id="describe-skip"),
        pytest.param('test.each([1])("x", () => {})', id="test-each"),
        pytest.param("globalThis.fetch = f;", id="global-write"),
        pytest.param("const x = load();", id="call-in-initializer"),
        pytest.param("const y = new Map();", id="new-in-initializer"),
        pytest.param("const z = await y;", id="await-in-initializer"),
        pytest.param("const t = tag`x`;", id="tagged-template"),
        pytest.param("const t = `${a}`;", id="template-substitution"),
        pytest.param("const w = (q = 1);", id="assignment-in-initializer"),
        pytest.param("const a = 1, b = load()", id="call-in-second-declarator"),
        pytest.param("const f = (() => 1)()", id="immediately-invoked-arrow"),
        pytest.param("@dec class C {}", id="decorated-class"),
        pytest.param("class C { @d m() {} }", id="decorated-member"),
        pytest.param("class C extends mk() {}", id="call-in-heritage"),
        pytest.param("class C extends tag`x` {}", id="template-in-heritage"),
        pytest.param("class C { static x = load(); }", id="static-field"),
        pytest.param("class C { static { load() } }", id="static-block"),
        pytest.param("class C { [load()] = 1 }", id="computed-key"),
        pytest.param("if (a) {}", id="if"),
        pytest.param("for (;;) {}", id="for"),
        pytest.param("try {} catch (e) {}", id="try"),
        pytest.param("{ load() }", id="bare-block"),
        pytest.param('export * from "m";', id="re-export-all"),
        pytest.param('export { a } from "m"', id="re-export"),
        pytest.param("export { a }", id="export-list"),
        pytest.param("export = x", id="export-equals"),
        pytest.param("export default foo", id="export-default-expression"),
        pytest.param("export default () => {}", id="export-default-arrow"),
        pytest.param("enum E { A }", id="enum"),
        pytest.param("const enum E { A }", id="const-enum"),
        pytest.param("function f() {} load()", id="function-then-call-on-one-line"),
        pytest.param("interface I {} load()", id="interface-then-call-on-one-line"),
        pytest.param("foo()", id="call"),
        pytest.param('describe("x", () => { globalThis.fetch = f; })', id="describe-global-write"),
        pytest.param('describe("x", () => { beforeEach(() => {}); it("y", () => {}); })', id="describe-before-each"),
        pytest.param('describe("x", () => { const k = load(); })', id="describe-call-in-initializer"),
        pytest.param('describe("x", () => { describe.skip("y", () => {}) })', id="describe-nested-skip"),
        pytest.param('describe("x", () => foo())', id="describe-expression-body"),
        pytest.param('it("x", f(), () => {})', id="call-as-argument"),
        pytest.param("it(`${load()}`, () => {})", id="substituted-title"),
        pytest.param('it("x", f)', id="identifier-callback"),
        pytest.param('it("x", () => {}, { timeout: 1 })', id="options-object"),
        pytest.param('it("x" + n, () => {})', id="concatenated-title"),
        pytest.param('it("x", () => {}, 1, 2)', id="extra-argument"),
        pytest.param('it("x", () => {})()', id="called-result"),
        pytest.param('export it("x", () => {})', id="exported-registration"),
    ])
    def test_allowed_host_refuses(text):
>       assert _allowed(text) is False
E       assert True is False
E        +  where True = _allowed('describe.skip("x", () => {})')

/Users/zwrose/.superheroes-worktrees/superheroes/issue-2061-wo-b2/plugins/superheroes/lib/tests/test_break_it_body_js_2053.py:519: AssertionError
______________________ test_a_host_it_only_is_host_setup _______________________
[gw1] darwin -- Python 3.12.13 /Users/zwrose/.cache/uv/builds-v0/.tmpXpKC5q/bin/python

repo = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-388/popen-gw1/test_a_host_it_only_is_host_se0/repo')

    def test_a_host_it_only_is_host_setup(repo):
        base, head = _stage(repo, {HOST: _host(before='\nit.only("focused", () => {});\n')})
        calls = []
>       assert _got(_check(repo, base, head, _record(), _stub(calls))) == ("unresolved", "host-setup")
E       AssertionError: assert ('kept', 'body-match') == ('unresolved', 'host-setup')
E         
E         At index 0 diff: 'kept' != 'unresolved'
E         Use -v to get more diff

/Users/zwrose/.superheroes-worktrees/superheroes/issue-2061-wo-b2/plugins/superheroes/lib/tests/test_break_it_body_js_e2e_2061.py:228: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_body_js_2053.py::test_allowed_host_refuses[it-only]
FAILED plugins/superheroes/lib/tests/test_break_it_body_js_2053.py::test_allowed_host_refuses[describe-skip]
FAILED plugins/superheroes/lib/tests/test_break_it_body_js_e2e_2061.py::test_a_host_it_only_is_host_setup
3 failed in 7.06s
exit=1
```

**restore:** the inverse edit put `    if len(callee) != 1 or callee[0][0] != "id" or callee[0][1] not in frameworks:` back.

**restore receipt:** `git diff --stat -- plugins/superheroes/lib/break_it_body_js.py` printed nothing; `grep -n` found `532:    if len(callee) != 1 or callee[0][0] != "id" or callee[0][1] not in frameworks:`.

**raw green** (exit 0):
```
bringing up nodes...
bringing up nodes...

...                                                                      [100%]
3 passed in 8.99s
exit=0
```

### K2 — the side-effect-only import refusal

- **axis:** an import that binds no name runs its module for effects, so it is a hook

**neutralization** (`plugins/superheroes/lib/break_it_body_js.py`, `_allowed_host`):
```diff
-        return any(local is not None for local, _ in imports)
+        return True
```

**command:** `scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest "plugins/superheroes/lib/tests/test_break_it_body_js_2053.py::test_allowed_host_refuses[side-effect-import]" "plugins/superheroes/lib/tests/test_break_it_body_js_e2e_2061.py::test_a_host_side_effect_import_is_host_setup" -q -n auto`

**raw red** (exit 1):
```
bringing up nodes...
bringing up nodes...

FF                                                                       [100%]
=================================== FAILURES ===================================
________________ test_allowed_host_refuses[side-effect-import] _________________
[gw0] darwin -- Python 3.12.13 /Users/zwrose/.cache/uv/builds-v0/.tmpRsCGe1/bin/python

text = 'import "./setup"'

    @pytest.mark.parametrize("text", [
        pytest.param('import "./setup"', id="side-effect-import"),
        pytest.param('import {} from "m"', id="empty-import"),
        pytest.param('it.only("x", () => {})', id="it-only"),
        pytest.param('describe.skip("x", () => {})', id="describe-skip"),
        pytest.param('test.each([1])("x", () => {})', id="test-each"),
        pytest.param("globalThis.fetch = f;", id="global-write"),
        pytest.param("const x = load();", id="call-in-initializer"),
        pytest.param("const y = new Map();", id="new-in-initializer"),
        pytest.param("const z = await y;", id="await-in-initializer"),
        pytest.param("const t = tag`x`;", id="tagged-template"),
        pytest.param("const t = `${a}`;", id="template-substitution"),
        pytest.param("const w = (q = 1);", id="assignment-in-initializer"),
        pytest.param("const a = 1, b = load()", id="call-in-second-declarator"),
        pytest.param("const f = (() => 1)()", id="immediately-invoked-arrow"),
        pytest.param("@dec class C {}", id="decorated-class"),
        pytest.param("class C { @d m() {} }", id="decorated-member"),
        pytest.param("class C extends mk() {}", id="call-in-heritage"),
        pytest.param("class C extends tag`x` {}", id="template-in-heritage"),
        pytest.param("class C { static x = load(); }", id="static-field"),
        pytest.param("class C { static { load() } }", id="static-block"),
        pytest.param("class C { [load()] = 1 }", id="computed-key"),
        pytest.param("if (a) {}", id="if"),
        pytest.param("for (;;) {}", id="for"),
        pytest.param("try {} catch (e) {}", id="try"),
        pytest.param("{ load() }", id="bare-block"),
        pytest.param('export * from "m";', id="re-export-all"),
        pytest.param('export { a } from "m"', id="re-export"),
        pytest.param("export { a }", id="export-list"),
        pytest.param("export = x", id="export-equals"),
        pytest.param("export default foo", id="export-default-expression"),
        pytest.param("export default () => {}", id="export-default-arrow"),
        pytest.param("enum E { A }", id="enum"),
        pytest.param("const enum E { A }", id="const-enum"),
        pytest.param("function f() {} load()", id="function-then-call-on-one-line"),
        pytest.param("interface I {} load()", id="interface-then-call-on-one-line"),
        pytest.param("foo()", id="call"),
        pytest.param('describe("x", () => { globalThis.fetch = f; })', id="describe-global-write"),
        pytest.param('describe("x", () => { beforeEach(() => {}); it("y", () => {}); })', id="describe-before-each"),
        pytest.param('describe("x", () => { const k = load(); })', id="describe-call-in-initializer"),
        pytest.param('describe("x", () => { describe.skip("y", () => {}) })', id="describe-nested-skip"),
        pytest.param('describe("x", () => foo())', id="describe-expression-body"),
        pytest.param('it("x", f(), () => {})', id="call-as-argument"),
        pytest.param("it(`${load()}`, () => {})", id="substituted-title"),
        pytest.param('it("x", f)', id="identifier-callback"),
        pytest.param('it("x", () => {}, { timeout: 1 })', id="options-object"),
        pytest.param('it("x" + n, () => {})', id="concatenated-title"),
        pytest.param('it("x", () => {}, 1, 2)', id="extra-argument"),
        pytest.param('it("x", () => {})()', id="called-result"),
        pytest.param('export it("x", () => {})', id="exported-registration"),
    ])
    def test_allowed_host_refuses(text):
>       assert _allowed(text) is False
E       assert True is False
E        +  where True = _allowed('import "./setup"')

/Users/zwrose/.superheroes-worktrees/superheroes/issue-2061-wo-b2/plugins/superheroes/lib/tests/test_break_it_body_js_2053.py:519: AssertionError
_________________ test_a_host_side_effect_import_is_host_setup _________________
[gw1] darwin -- Python 3.12.13 /Users/zwrose/.cache/uv/builds-v0/.tmpRsCGe1/bin/python

repo = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-391/popen-gw1/test_a_host_side_effect_import0/repo')

    def test_a_host_side_effect_import_is_host_setup(repo):
        base, head = _stage(repo, {HOST: _host(imports=HOST_IMPORTS + 'import "./setup";\n')})
        calls = []
>       assert _got(_check(repo, base, head, _record(), _stub(calls))) == ("unresolved", "host-setup")
E       AssertionError: assert ('kept', 'body-match') == ('unresolved', 'host-setup')
E         
E         At index 0 diff: 'kept' != 'unresolved'
E         Use -v to get more diff

/Users/zwrose/.superheroes-worktrees/superheroes/issue-2061-wo-b2/plugins/superheroes/lib/tests/test_break_it_body_js_e2e_2061.py:235: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_body_js_2053.py::test_allowed_host_refuses[side-effect-import]
FAILED plugins/superheroes/lib/tests/test_break_it_body_js_e2e_2061.py::test_a_host_side_effect_import_is_host_setup
2 failed in 6.27s
exit=1
```

**restore:** the inverse edit put `        return any(local is not None for local, _ in imports)` back.

**restore receipt:** `git diff --stat -- plugins/superheroes/lib/break_it_body_js.py` printed nothing; `grep -n` found `561:        return any(local is not None for local, _ in imports)`.

**raw green** (exit 0):
```
bringing up nodes...
bringing up nodes...

..                                                                       [100%]
2 passed in 6.72s
exit=0
```

### K3 — the call-in-initializer refusal

- **axis:** a call in an initialiser (a `(` after an identifier or a closing bracket) makes the declaration a hook

**neutralization** (`plugins/superheroes/lib/break_it_body_js.py`, `_plain`):
```diff
-        if tok == _LPAREN and called:
+        if False and tok == _LPAREN and called:
```

**command:** `scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest "plugins/superheroes/lib/tests/test_break_it_body_js_2053.py::test_allowed_host_refuses[call-in-initializer]" "plugins/superheroes/lib/tests/test_break_it_body_js_2053.py::test_allowed_host_refuses[call-in-second-declarator]" -q -n auto`

**raw red** (exit 1):
```
bringing up nodes...
bringing up nodes...

FF                                                                       [100%]
=================================== FAILURES ===================================
________________ test_allowed_host_refuses[call-in-initializer] ________________
[gw0] darwin -- Python 3.12.13 /Users/zwrose/.cache/uv/builds-v0/.tmpFyoiX6/bin/python

text = 'const x = load();'

    @pytest.mark.parametrize("text", [
        pytest.param('import "./setup"', id="side-effect-import"),
        pytest.param('import {} from "m"', id="empty-import"),
        pytest.param('it.only("x", () => {})', id="it-only"),
        pytest.param('describe.skip("x", () => {})', id="describe-skip"),
        pytest.param('test.each([1])("x", () => {})', id="test-each"),
        pytest.param("globalThis.fetch = f;", id="global-write"),
        pytest.param("const x = load();", id="call-in-initializer"),
        pytest.param("const y = new Map();", id="new-in-initializer"),
        pytest.param("const z = await y;", id="await-in-initializer"),
        pytest.param("const t = tag`x`;", id="tagged-template"),
        pytest.param("const t = `${a}`;", id="template-substitution"),
        pytest.param("const w = (q = 1);", id="assignment-in-initializer"),
        pytest.param("const a = 1, b = load()", id="call-in-second-declarator"),
        pytest.param("const f = (() => 1)()", id="immediately-invoked-arrow"),
        pytest.param("@dec class C {}", id="decorated-class"),
        pytest.param("class C { @d m() {} }", id="decorated-member"),
        pytest.param("class C extends mk() {}", id="call-in-heritage"),
        pytest.param("class C extends tag`x` {}", id="template-in-heritage"),
        pytest.param("class C { static x = load(); }", id="static-field"),
        pytest.param("class C { static { load() } }", id="static-block"),
        pytest.param("class C { [load()] = 1 }", id="computed-key"),
        pytest.param("if (a) {}", id="if"),
        pytest.param("for (;;) {}", id="for"),
        pytest.param("try {} catch (e) {}", id="try"),
        pytest.param("{ load() }", id="bare-block"),
        pytest.param('export * from "m";', id="re-export-all"),
        pytest.param('export { a } from "m"', id="re-export"),
        pytest.param("export { a }", id="export-list"),
        pytest.param("export = x", id="export-equals"),
        pytest.param("export default foo", id="export-default-expression"),
        pytest.param("export default () => {}", id="export-default-arrow"),
        pytest.param("enum E { A }", id="enum"),
        pytest.param("const enum E { A }", id="const-enum"),
        pytest.param("function f() {} load()", id="function-then-call-on-one-line"),
        pytest.param("interface I {} load()", id="interface-then-call-on-one-line"),
        pytest.param("foo()", id="call"),
        pytest.param('describe("x", () => { globalThis.fetch = f; })', id="describe-global-write"),
        pytest.param('describe("x", () => { beforeEach(() => {}); it("y", () => {}); })', id="describe-before-each"),
        pytest.param('describe("x", () => { const k = load(); })', id="describe-call-in-initializer"),
        pytest.param('describe("x", () => { describe.skip("y", () => {}) })', id="describe-nested-skip"),
        pytest.param('describe("x", () => foo())', id="describe-expression-body"),
        pytest.param('it("x", f(), () => {})', id="call-as-argument"),
        pytest.param("it(`${load()}`, () => {})", id="substituted-title"),
        pytest.param('it("x", f)', id="identifier-callback"),
        pytest.param('it("x", () => {}, { timeout: 1 })', id="options-object"),
        pytest.param('it("x" + n, () => {})', id="concatenated-title"),
        pytest.param('it("x", () => {}, 1, 2)', id="extra-argument"),
        pytest.param('it("x", () => {})()', id="called-result"),
        pytest.param('export it("x", () => {})', id="exported-registration"),
    ])
    def test_allowed_host_refuses(text):
>       assert _allowed(text) is False
E       AssertionError: assert True is False
E        +  where True = _allowed('const x = load();')

/Users/zwrose/.superheroes-worktrees/superheroes/issue-2061-wo-b2/plugins/superheroes/lib/tests/test_break_it_body_js_2053.py:519: AssertionError
_____________ test_allowed_host_refuses[call-in-second-declarator] _____________
[gw2] darwin -- Python 3.12.13 /Users/zwrose/.cache/uv/builds-v0/.tmpFyoiX6/bin/python

text = 'const a = 1, b = load()'

    @pytest.mark.parametrize("text", [
        pytest.param('import "./setup"', id="side-effect-import"),
        pytest.param('import {} from "m"', id="empty-import"),
        pytest.param('it.only("x", () => {})', id="it-only"),
        pytest.param('describe.skip("x", () => {})', id="describe-skip"),
        pytest.param('test.each([1])("x", () => {})', id="test-each"),
        pytest.param("globalThis.fetch = f;", id="global-write"),
        pytest.param("const x = load();", id="call-in-initializer"),
        pytest.param("const y = new Map();", id="new-in-initializer"),
        pytest.param("const z = await y;", id="await-in-initializer"),
        pytest.param("const t = tag`x`;", id="tagged-template"),
        pytest.param("const t = `${a}`;", id="template-substitution"),
        pytest.param("const w = (q = 1);", id="assignment-in-initializer"),
        pytest.param("const a = 1, b = load()", id="call-in-second-declarator"),
        pytest.param("const f = (() => 1)()", id="immediately-invoked-arrow"),
        pytest.param("@dec class C {}", id="decorated-class"),
        pytest.param("class C { @d m() {} }", id="decorated-member"),
        pytest.param("class C extends mk() {}", id="call-in-heritage"),
        pytest.param("class C extends tag`x` {}", id="template-in-heritage"),
        pytest.param("class C { static x = load(); }", id="static-field"),
        pytest.param("class C { static { load() } }", id="static-block"),
        pytest.param("class C { [load()] = 1 }", id="computed-key"),
        pytest.param("if (a) {}", id="if"),
        pytest.param("for (;;) {}", id="for"),
        pytest.param("try {} catch (e) {}", id="try"),
        pytest.param("{ load() }", id="bare-block"),
        pytest.param('export * from "m";', id="re-export-all"),
        pytest.param('export { a } from "m"', id="re-export"),
        pytest.param("export { a }", id="export-list"),
        pytest.param("export = x", id="export-equals"),
        pytest.param("export default foo", id="export-default-expression"),
        pytest.param("export default () => {}", id="export-default-arrow"),
        pytest.param("enum E { A }", id="enum"),
        pytest.param("const enum E { A }", id="const-enum"),
        pytest.param("function f() {} load()", id="function-then-call-on-one-line"),
        pytest.param("interface I {} load()", id="interface-then-call-on-one-line"),
        pytest.param("foo()", id="call"),
        pytest.param('describe("x", () => { globalThis.fetch = f; })', id="describe-global-write"),
        pytest.param('describe("x", () => { beforeEach(() => {}); it("y", () => {}); })', id="describe-before-each"),
        pytest.param('describe("x", () => { const k = load(); })', id="describe-call-in-initializer"),
        pytest.param('describe("x", () => { describe.skip("y", () => {}) })', id="describe-nested-skip"),
        pytest.param('describe("x", () => foo())', id="describe-expression-body"),
        pytest.param('it("x", f(), () => {})', id="call-as-argument"),
        pytest.param("it(`${load()}`, () => {})", id="substituted-title"),
        pytest.param('it("x", f)', id="identifier-callback"),
        pytest.param('it("x", () => {}, { timeout: 1 })', id="options-object"),
        pytest.param('it("x" + n, () => {})', id="concatenated-title"),
        pytest.param('it("x", () => {}, 1, 2)', id="extra-argument"),
        pytest.param('it("x", () => {})()', id="called-result"),
        pytest.param('export it("x", () => {})', id="exported-registration"),
    ])
    def test_allowed_host_refuses(text):
>       assert _allowed(text) is False
E       AssertionError: assert True is False
E        +  where True = _allowed('const a = 1, b = load()')

/Users/zwrose/.superheroes-worktrees/superheroes/issue-2061-wo-b2/plugins/superheroes/lib/tests/test_break_it_body_js_2053.py:519: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_body_js_2053.py::test_allowed_host_refuses[call-in-initializer]
FAILED plugins/superheroes/lib/tests/test_break_it_body_js_2053.py::test_allowed_host_refuses[call-in-second-declarator]
2 failed in 5.36s
exit=1
```

**restore:** the inverse edit put `        if tok == _LPAREN and called:` back.

**restore receipt:** `git diff --stat -- plugins/superheroes/lib/break_it_body_js.py` printed nothing; `grep -n` found `454:        if tok == _LPAREN and called:`.

**raw green** (exit 0):
```
bringing up nodes...
bringing up nodes...

..                                                                       [100%]
2 passed in 5.68s
exit=0
```

### K4 — the `hook = not _allowed_host(…)` wiring

- **axis:** every record's hook flag is the allowlist's refusal

**neutralization** (`plugins/superheroes/lib/break_it_body_js.py`, `_parse`):
```diff
-                        "binds": binds, "uses": uses, "hook": not _allowed_host(sig, frameworks)})
+                        "binds": binds, "uses": uses, "hook": False})
```

**command:** `scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_break_it_body_js_2053.py::test_hook_ignores_a_leading_comment plugins/superheroes/lib/tests/test_break_it_body_js_2053.py::test_a_registration_needs_its_callee_to_be_a_framework_name plugins/superheroes/lib/tests/test_break_it_body_js_e2e_2061.py::test_a_host_top_level_before_each_is_host_setup plugins/superheroes/lib/tests/test_break_it_body_js_e2e_2061.py::test_a_host_it_only_is_host_setup plugins/superheroes/lib/tests/test_break_it_body_js_e2e_2061.py::test_a_host_side_effect_import_is_host_setup -q -n auto`

**raw red** (exit 1):
```
bringing up nodes...
bringing up nodes...

FFFFF                                                                    [100%]
=================================== FAILURES ===================================
_________ test_a_registration_needs_its_callee_to_be_a_framework_name __________
[gw2] darwin -- Python 3.12.13 /Users/zwrose/.cache/uv/builds-v0/.tmpb8VZOu/bin/python

    def test_a_registration_needs_its_callee_to_be_a_framework_name():
        assert [rec["hook"] for rec in front.parse('import { it } from "vitest"\nit("a", () => {})')] == [False, False]
        recs = front.parse('import { it } from "./helpers"\nit("a", () => {})')
>       assert [rec["hook"] for rec in recs] == [False, True]
E       assert [False, False] == [False, True]
E         
E         At index 1 diff: False != True
E         Use -v to get more diff

/Users/zwrose/.superheroes-worktrees/superheroes/issue-2061-wo-b2/plugins/superheroes/lib/tests/test_break_it_body_js_2053.py:420: AssertionError
_____________________ test_hook_ignores_a_leading_comment ______________________
[gw0] darwin -- Python 3.12.13 /Users/zwrose/.cache/uv/builds-v0/.tmpb8VZOu/bin/python

    def test_hook_ignores_a_leading_comment():
>       assert _only("// reset\nbeforeEach(() => {})")["hook"] is True
E       assert False is True

/Users/zwrose/.superheroes-worktrees/superheroes/issue-2061-wo-b2/plugins/superheroes/lib/tests/test_break_it_body_js_2053.py:410: AssertionError
______________________ test_a_host_it_only_is_host_setup _______________________
[gw3] darwin -- Python 3.12.13 /Users/zwrose/.cache/uv/builds-v0/.tmpb8VZOu/bin/python

repo = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-395/popen-gw3/test_a_host_it_only_is_host_se0/repo')

    def test_a_host_it_only_is_host_setup(repo):
        base, head = _stage(repo, {HOST: _host(before='\nit.only("focused", () => {});\n')})
        calls = []
>       assert _got(_check(repo, base, head, _record(), _stub(calls))) == ("unresolved", "host-setup")
E       AssertionError: assert ('kept', 'body-match') == ('unresolved', 'host-setup')
E         
E         At index 0 diff: 'kept' != 'unresolved'
E         Use -v to get more diff

/Users/zwrose/.superheroes-worktrees/superheroes/issue-2061-wo-b2/plugins/superheroes/lib/tests/test_break_it_body_js_e2e_2061.py:228: AssertionError
_______________ test_a_host_top_level_before_each_is_host_setup ________________
[gw1] darwin -- Python 3.12.13 /Users/zwrose/.cache/uv/builds-v0/.tmpb8VZOu/bin/python

repo = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-395/popen-gw1/test_a_host_top_level_before_e0/repo')

    def test_a_host_top_level_before_each_is_host_setup(repo):
        host = _host(imports=HOST_IMPORTS.replace("describe", "beforeEach, describe"),
                     before="\nbeforeEach(() => {\n  window.localStorage.clear();\n});\n")
        base, head = _stage(repo, {HOST: host})
        calls = []
>       assert _got(_check(repo, base, head, _record(), _stub(calls))) == ("unresolved", "host-setup")
E       AssertionError: assert ('kept', 'body-match') == ('unresolved', 'host-setup')
E         
E         At index 0 diff: 'kept' != 'unresolved'
E         Use -v to get more diff

/Users/zwrose/.superheroes-worktrees/superheroes/issue-2061-wo-b2/plugins/superheroes/lib/tests/test_break_it_body_js_e2e_2061.py:221: AssertionError
_________________ test_a_host_side_effect_import_is_host_setup _________________
[gw7] darwin -- Python 3.12.13 /Users/zwrose/.cache/uv/builds-v0/.tmpb8VZOu/bin/python

repo = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-395/popen-gw7/test_a_host_side_effect_import0/repo')

    def test_a_host_side_effect_import_is_host_setup(repo):
        base, head = _stage(repo, {HOST: _host(imports=HOST_IMPORTS + 'import "./setup";\n')})
        calls = []
>       assert _got(_check(repo, base, head, _record(), _stub(calls))) == ("unresolved", "host-setup")
E       AssertionError: assert ('kept', 'body-match') == ('unresolved', 'host-setup')
E         
E         At index 0 diff: 'kept' != 'unresolved'
E         Use -v to get more diff

/Users/zwrose/.superheroes-worktrees/superheroes/issue-2061-wo-b2/plugins/superheroes/lib/tests/test_break_it_body_js_e2e_2061.py:235: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_body_js_2053.py::test_a_registration_needs_its_callee_to_be_a_framework_name
FAILED plugins/superheroes/lib/tests/test_break_it_body_js_2053.py::test_hook_ignores_a_leading_comment
FAILED plugins/superheroes/lib/tests/test_break_it_body_js_e2e_2061.py::test_a_host_it_only_is_host_setup
FAILED plugins/superheroes/lib/tests/test_break_it_body_js_e2e_2061.py::test_a_host_top_level_before_each_is_host_setup
FAILED plugins/superheroes/lib/tests/test_break_it_body_js_e2e_2061.py::test_a_host_side_effect_import_is_host_setup
5 failed in 6.39s
exit=1
```

**restore:** the inverse edit put `"hook": not _allowed_host(sig, frameworks)})` back.

**restore receipt:** `git diff --stat -- plugins/superheroes/lib/break_it_body_js.py` printed nothing; `grep -n` found `628:                        "binds": binds, "uses": uses, "hook": not _allowed_host(sig, frameworks)})`.

**raw green** (exit 0):
```
bringing up nodes...
bringing up nodes...

.....                                                                    [100%]
5 passed in 6.35s
exit=0
```

## L2-fix — the pytest rename rules apply only to Python files

**Provenance:** claude / sonnet-5.5 (implementer, work order L2-fix, attempt 2, #2061 / PR #2069), maker family anthropic, on top of `ffe696cac`. Both guards were neutralized by one targeted Edit-tool edit, only the new tests were run by exact node id (never `-k`), the inverse edit was applied, `git diff --stat` over the file was read, and the same ids were run again. The production files had been staged with `git add` after the dev runs, so the diff stat is read against the unneutralized text for L2a (staged after its restore, so for L2a the receipt is the quoted line plus the green run) and for L2b. No `git checkout`, `git restore`, `git reset` or `git stash` was used. Each command was `scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest <node ids> -q`, redirected unfiltered with `echo "pytest exit: $?"` appended, to `/private/tmp/claude-501/-Users-zwrose--superheroes-worktrees-superheroes-issue-2053-b7af41d156396fa0/109398b2-b53a-4a76-90e5-2bf96c9a5df8/scratchpad/l2fix/` (`site1-red.txt`, `site1-green.txt`, `site2-red.txt`, `site2-green.txt`).

Declared guarded-element set: **L2a**, **L2b**.

| ID | Guarded element | Axis | Proving nodes | Red / green exit |
|---|---|---|---|---|
| L2a | `locate`'s `getattr(front, "PYTEST_COLLECTION", False) and` before the `test_` prefix rule | the `test_` prefix rule applies only to a front pytest collects | `test_break_it_body_js_e2e_2061.py::test_a_js_title_change_without_a_test_prefix_reads_found_and_is_not_pytest_collected`, `::test_a_ts_rename_in_a_repository_whose_pytest_ini_sets_addopts_is_still_kept` | 1 / 0 |
| L2b | `_body_search`'s `pytest_collected(record["path"]) and` before `_collection_overrides` | the pytest configuration gate applies only to a front pytest collects | `test_break_it_body_js_e2e_2061.py::test_a_ts_rename_in_a_repository_whose_pytest_ini_sets_addopts_is_still_kept` | 1 / 0 |

### L2a — the `test_` prefix rule is Python-only

- **axis:** a JS/TS title (an `it`/`test`/`describe` string) is not a pytest function name

**neutralization** (`plugins/superheroes/lib/break_it_body.py`, `locate`):
```diff
-    if getattr(front, "PYTEST_COLLECTION", False) and any(old != new and not new.startswith("test_") for old, new in zip(old_titles, new_titles)):
+    if any(old != new and not new.startswith("test_") for old, new in zip(old_titles, new_titles)):
```

**command:** `scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_break_it_body_js_e2e_2061.py::test_a_js_title_change_without_a_test_prefix_reads_found_and_is_not_pytest_collected plugins/superheroes/lib/tests/test_break_it_body_js_e2e_2061.py::test_a_ts_rename_in_a_repository_whose_pytest_ini_sets_addopts_is_still_kept -q`

**raw red** (exit 1):
```
FF                                                                       [100%]
=================================== FAILURES ===================================
_ test_a_js_title_change_without_a_test_prefix_reads_found_and_is_not_pytest_collected _

    def test_a_js_title_change_without_a_test_prefix_reads_found_and_is_not_pytest_collected():
        found = break_it_body.locate(ORIG, OWN, [(HOST, _host())])
>       assert found["status"] == "found" and found["reason"] is None and found["path"] == HOST
E       AssertionError: assert ('unresolved' == 'found'
E         
E         - found
E         + unresolved)

/Users/zwrose/.superheroes-worktrees/superheroes/issue-2053-b7af41d156396fa0-l2/plugins/superheroes/lib/tests/test_break_it_body_js_e2e_2061.py:158: AssertionError
_ test_a_ts_rename_in_a_repository_whose_pytest_ini_sets_addopts_is_still_kept _

repo = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-456/test_a_ts_rename_in_a_reposito0/repo')

    def test_a_ts_rename_in_a_repository_whose_pytest_ini_sets_addopts_is_still_kept(repo):
        base, head = _stage(repo, {"pytest.ini": "[pytest]\naddopts = -k test_x\n", HOST: _host()})
        calls = []
        result = _check(repo, base, head, _record(), _stub(calls))
>       assert _got(result) == ("kept", "body-match")
E       AssertionError: assert ('unresolved'...ing-conflict') == ('kept', 'body-match')
E         
E         At index 0 diff: 'unresolved' != 'kept'
E         Use -v to get more diff

/Users/zwrose/.superheroes-worktrees/superheroes/issue-2053-b7af41d156396fa0-l2/plugins/superheroes/lib/tests/test_break_it_body_js_e2e_2061.py:167: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_body_js_e2e_2061.py::test_a_js_title_change_without_a_test_prefix_reads_found_and_is_not_pytest_collected
FAILED plugins/superheroes/lib/tests/test_break_it_body_js_e2e_2061.py::test_a_ts_rename_in_a_repository_whose_pytest_ini_sets_addopts_is_still_kept
2 failed in 0.61s
pytest exit: 1
```

**restore:** the inverse edit put `getattr(front, "PYTEST_COLLECTION", False) and ` back in front of `any(`.

**restore receipt:** `grep -n PYTEST_COLLECTION plugins/superheroes/lib/break_it_body.py` found `255:    if getattr(front, "PYTEST_COLLECTION", False) and any(old != new and not new.startswith("test_") for old, new in zip(old_titles, new_titles)):`; `git diff --stat -- plugins/superheroes/lib/break_it_body.py` printed nothing, read after the restored file was staged.

**raw green** (exit 0):
```
..                                                                       [100%]
2 passed in 0.58s
pytest exit: 0
```

### L2b — the pytest configuration gate is Python-only

- **axis:** a `pytest.ini` that sets `addopts` or `python_functions` says nothing about a vitest or jest run

**neutralization** (`plugins/superheroes/lib/break_it.py`, `_body_search`):
```diff
-        if found["titles"] and pytest_collected(record["path"]) and _collection_overrides(repo_root, head):
+        if found["titles"] and _collection_overrides(repo_root, head):
```

**command:** `scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_break_it_body_js_e2e_2061.py::test_a_ts_rename_in_a_repository_whose_pytest_ini_sets_addopts_is_still_kept -q`

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_ts_rename_in_a_repository_whose_pytest_ini_sets_addopts_is_still_kept _

repo = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-458/test_a_ts_rename_in_a_reposito0/repo')

    def test_a_ts_rename_in_a_repository_whose_pytest_ini_sets_addopts_is_still_kept(repo):
        base, head = _stage(repo, {"pytest.ini": "[pytest]\naddopts = -k test_x\n", HOST: _host()})
        calls = []
        result = _check(repo, base, head, _record(), _stub(calls))
>       assert _got(result) == ("kept", "body-match")
E       AssertionError: assert ('unresolved'...ing-conflict') == ('kept', 'body-match')
E         
E         At index 0 diff: 'unresolved' != 'kept'
E         Use -v to get more diff

/Users/zwrose/.superheroes-worktrees/superheroes/issue-2053-b7af41d156396fa0-l2/plugins/superheroes/lib/tests/test_break_it_body_js_e2e_2061.py:167: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_body_js_e2e_2061.py::test_a_ts_rename_in_a_repository_whose_pytest_ini_sets_addopts_is_still_kept
1 failed in 0.63s
pytest exit: 1
```

**restore:** the inverse edit put `pytest_collected(record["path"]) and ` back before `_collection_overrides`.

**restore receipt:** `git diff --stat -- plugins/superheroes/lib/break_it.py` printed nothing (read against the staged unneutralized text).

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.24s
pytest exit: 0
```
