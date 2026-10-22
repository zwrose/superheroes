"""Unit tests for the JS/TS front of the break-it body match (#2053)."""
import os
import sys

import pytest

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import break_it_body  # noqa: E402
import break_it_body_js as front  # noqa: E402


def _keys(text):
    return [rec["key"] for rec in front.parse(text)]


def _tokens(text):
    return [tok for key in _keys(text) for tok in key]


def _assert_same(a, b):
    assert _keys(a) == _keys(b), (a, b)


def _assert_differ(a, b):
    assert _keys(a) != _keys(b), (a, b)


def _only(text):
    records = front.parse(text)
    assert len(records) == 1, records
    return records[0]


# --- the contract ---------------------------------------------------------------------------------------------

def test_contract_constants():
    assert front.EXTENSIONS == (".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts")
    assert front.TITLE == "\x00title"


def test_record_shape():
    rec = _only("const a = 1")
    assert set(rec) == {"kind", "key", "titles", "imports", "binds", "uses", "hook", "relative"}
    assert rec["kind"] == "stmt"
    assert isinstance(rec["key"], tuple) and isinstance(rec["titles"], tuple) and isinstance(rec["imports"], tuple)
    assert isinstance(rec["binds"], frozenset) and isinstance(rec["uses"], frozenset)
    assert rec["hook"] is False
    hash(rec["key"])


def test_empty_and_blank_text_have_no_statements():
    assert front.parse("") == []
    assert front.parse("  \n\t \n") == []


# --- equal keys: what a formatter changes ---------------------------------------------------------------------

_EQUAL_PAIRS = [
    pytest.param("const a = 'x'", 'const a = "x"', id="quote-style"),
    pytest.param("const a = 'it\\'s'", 'const a = "it\'s"', id="escaped-quote"),
    pytest.param('const a = "say \\"hi\\""', "const a = 'say \"hi\"'", id="escaped-double-quote"),
    pytest.param("const a = 1\nconst b = 2\n", "const a = 1;\nconst b = 2;\n", id="semicolons"),
    pytest.param("foo()\nbar()", "foo();\nbar();", id="semicolons-calls"),
    pytest.param("foo(a, b, {x: 1, y: [1, 2, 3]})",
                 "foo(\n  a,\n  b,\n  {\n    x: 1,\n    y: [\n      1,\n      2,\n      3,\n    ],\n  },\n)",
                 id="line-breaks-in-calls-arrays-objects"),
    pytest.param("f(a, b,)", "f(a, b)", id="trailing-comma-call"),
    pytest.param("const a = [1, 2,]", "const a = [1, 2]", id="trailing-comma-array"),
    pytest.param("const a = {b: 1,}", "const a = {b: 1}", id="trailing-comma-object"),
    pytest.param("const f = (x) => x", "const f = x => x", id="arrow-parens"),
    pytest.param("const f = (x,) => x", "const f = x => x", id="arrow-parens-trailing-comma"),
    pytest.param("const f = async (x) => x", "const f = async x => x", id="async-arrow-parens"),
    pytest.param("/**\n * Hello\n * world\n */\nfoo()", "/** Hello world */\nfoo()", id="rewrapped-jsdoc"),
    pytest.param("// note\nfoo()", "//   note  \nfoo()", id="line-comment-spacing"),
    pytest.param("function f() {\n    return 1\n}", "function f() {\nreturn 1\n}", id="indentation"),
    pytest.param("if (x)\n  foo()", "if (x) foo();", id="if-without-braces"),
    pytest.param("const total = items.map((x) => x.price).reduce((a, b) => a + b, 0);\n"
                 "export const config = {\n  retries: 3,\n  names: [\"a\", \"b\"],\n};\n",
                 "const total = items.map(x => x.price).reduce((a, b) => a + b, 0)\n"
                 "export const config = { retries: 3, names: ['a', 'b'] }",
                 id="prettier-style-module"),
]


@pytest.mark.parametrize("a, b", _EQUAL_PAIRS)
def test_formatter_pairs_read_equal(a, b):
    _assert_same(a, b)


def test_title_rename_with_it_imported_from_vitest_keeps_the_key():
    a = 'import { it } from "vitest"\nit("a", () => { expect(1).toBe(1) })'
    b = 'import { it } from "vitest"\nit("a (moved)", () => { expect(1).toBe(1) })'
    ra, rb = front.parse(a), front.parse(b)
    assert [r["key"] for r in ra] == [r["key"] for r in rb]
    assert ra[1]["titles"] == ("a",)
    assert rb[1]["titles"] == ("a (moved)",)
    assert ("str", front.TITLE) in ra[1]["key"]


def test_title_rename_with_global_it_keeps_the_key():
    ra, rb = front.parse('it("a", () => { expect(1).toBe(1) })'), front.parse('it("a (moved)", () => { expect(1).toBe(1) })')
    assert ra[0]["key"] == rb[0]["key"]
    assert ra[0]["titles"] == ("a",)
    assert rb[0]["titles"] == ("a (moved)",)


@pytest.mark.parametrize("module", ["vitest", "@jest/globals", "node:test", "bun:test"])
def test_every_framework_module_makes_a_title_slot(module):
    a = 'import { it } from "%s"\nit("a", f)' % module
    b = 'import { it } from "%s"\nit("b", f)' % module
    _assert_same(a, b)


def test_describe_and_nested_it_titles_are_collected_in_order():
    rec = _only('describe("outer", () => {\n  it("inner", () => {})\n  test(`third`, () => {})\n})')
    assert rec["titles"] == ("outer", "inner", "third")
    assert rec["key"].count(("str", front.TITLE)) == 3
    other = _only('describe("renamed", () => {\n  it("x", () => {})\n  test(`y`, () => {})\n})')
    assert other["key"] == rec["key"]


def test_a_title_slot_after_a_comment_at_statement_start():
    _assert_same('// the case\nit("a", f)', '// the case\nit("b", f)')


def test_a_title_slot_is_the_first_argument_only():
    _assert_differ('it("a", "p")', 'it("a", "q")')


# --- unequal keys: what changes the program -----------------------------------------------------------------

def test_return_line_break_is_not_return_space():
    _assert_differ("return\n1", "return 1")


def test_restricted_production_line_break_is_a_statement_end():
    pairs = [
        ("function f() {\n  return\n  (1)\n}", "function f() { return (1) }"),
        ("function f() {\n  return\n  [1]\n}", "function f() { return [1] }"),
        ("function f() {\n  throw\n  (e)\n}", "function f() { throw (e) }"),
        ("function* g() {\n  yield\n  (1)\n}", "function* g() { yield (1) }"),
    ]
    for a, b in pairs:
        _assert_differ(a, b)
    # a statement end directly before a closing brace ends nothing, so a bare jump at a block end reads equal
    for a, b in [("function f() {\n  return\n}", "function f() { return }"),
                 ("while (1) {\n  break\n}", "while (1) { break }"),
                 ("while (1) {\n  continue\n}", "while (1) { continue }")]:
        _assert_same(a, b)


def test_statement_end_before_a_parenthesis_is_not_a_call():
    _assert_differ("a;(b)", "a(b)")


def test_a_line_break_before_a_parenthesis_is_a_call():
    _assert_same("a\n(b)", "a(b)")


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
        _assert_same(a, b)


def test_a_call_paren_line_break_is_still_a_statement_end():
    _assert_differ("foo(x)\nbar()", "foo(x) bar()")


def test_array_hole_commas_are_kept():
    _assert_differ("const a = [,]", "const a = []")
    _assert_differ("const a = [a,,]", "const a = [a,]")
    _assert_differ("const a = [a,,]", "const a = [a]")


def test_added_ts_ignore_reads_unequal():
    _assert_differ("// @ts-ignore\nconst x: number = 's'", "const x: number = 's'")
    _assert_differ("const x: number = 's' // @ts-ignore", "const x: number = 's'")


def test_removed_ts_expect_error_reads_unequal():
    _assert_differ("const x: number = 's'", "// @ts-expect-error\nconst x: number = 's'")
    _assert_differ("/* @ts-expect-error */\nconst x: number = 's'", "const x: number = 's'")


def test_changed_assertion_literal_reads_unequal():
    _assert_differ("expect(add(1, 2)).toBe(3)", "expect(add(1, 2)).toBe(4)")
    _assert_differ("expect(add(1, 2)).toBe(3)", "expect(add(1, 3)).toBe(3)")


def test_changed_expected_string_reads_unequal():
    _assert_differ("expect(greet()).toBe('hello')", "expect(greet()).toBe('goodbye')")
    _assert_differ("expect(greet()).toBe(`hello`)", "expect(greet()).toBe(`goodbye`)")


def test_a_different_comment_text_reads_unequal():
    _assert_differ("// one\nfoo()", "// two\nfoo()")


def test_quote_style_does_not_hide_a_different_string():
    _assert_differ("const a = 'x'", 'const a = "y"')
    _assert_differ("const a = 'a\"b'", "const a = 'a\\\\\"b'")


def test_title_slot_needs_statement_start():
    # `it` is the global framework name here, so only the statement-start condition decides
    _assert_differ('const f = it("a")', 'const f = it("b")')
    _assert_differ('foo(it("a"))', 'foo(it("b"))')
    _assert_differ('x = { run: it("a") }', 'x = { run: it("b") }')
    _assert_differ('obj.it("a")', 'obj.it("b")')
    _assert_differ('foo(/* c */ it("a"))', 'foo(/* c */ it("b"))')


def test_non_framework_callee_at_statement_start_is_not_a_title_slot():
    # the callee is at statement start, so only the framework-name condition decides
    _assert_differ('import { it } from "./helpers"\nit("a", f)', 'import { it } from "./helpers"\nit("b", f)')
    _assert_differ('import it from "ava"\nit("a", f)', 'import it from "ava"\nit("b", f)')
    _assert_differ('import * as it from "./it"\nit("a")', 'import * as it from "./it"\nit("b")')
    _assert_differ('const test = x => x\ntest("bad")', 'const test = x => x\ntest("good")')
    _assert_differ('function describe(n) {}\ndescribe("a")', 'function describe(n) {}\ndescribe("b")')
    _assert_differ('class test {}\ntest("a")', 'class test {}\ntest("b")')
    _assert_differ('export const it = wrap()\nit("a")', 'export const it = wrap()\nit("b")')
    _assert_differ('describe("x", () => { const it = h; it("a") })', 'describe("x", () => { const it = h; it("b") })')


def test_a_non_framework_callee_leaves_no_title():
    recs =front.parse('import { it } from "./helpers"\nit("a", f)')
    assert recs[1]["titles"] == ()
    assert ("str", "a") in recs[1]["key"]


def test_a_callee_bound_to_a_const_in_the_same_line_is_not_a_title_slot():
    _assert_differ('const test = x => x; const f = test("bad")', 'const test = x => x; const f = test("good")')


def test_it_skip_is_not_it():
    _assert_differ('it.skip("a", f)', 'it("a", f)')
    _assert_differ('it.skip("a", f)', 'it.skip("b", f)')
    _assert_differ('describe.only("a", f)', 'describe("a", f)')


def test_a_title_built_by_concatenation_is_not_a_slot():
    _assert_differ('it("a" + n, f)', 'it("b" + n, f)')


def test_everything_but_the_title_still_reads():
    _assert_differ('it("a", () => { expect(1).toBe(1) })', 'it("a", () => { expect(1).toBe(2) })')
    _assert_differ('it("a", f)', 'it("a", g)')


# --- semicolon placement relative to comments ---------------------------------------------------------------

def test_semicolon_moves_before_preceding_comments():
    _assert_same("a // c\nb", "a; // c\nb")
    _assert_same("a /* c */\nb", "a; /* c */\nb")
    _assert_same("a // c", "a; // c")


def test_comments_after_a_semicolon_belong_to_the_next_statement():
    first, second = front.parse("a(); // note\nb()")
    assert first["key"][-1] == ("punct", ";")
    assert second["key"][0] == ("comment", "note")


# --- statements -----------------------------------------------------------------------------------------------

def test_statements_split_at_depth_zero_semicolons_only():
    assert len(front.parse("a(); b()")) == 2
    assert len(front.parse("for (let i = 0; i < n; i++) {}")) == 1
    assert len(front.parse("class A { x = 1; y = 2; }")) == 1
    assert len(front.parse("function f() {}\nfunction g() {}")) == 2


def test_a_trailing_remainder_without_a_semicolon_is_a_final_statement():
    recs = front.parse("a();\n// the end")
    assert [r["key"] for r in recs] == [(("id", "a"), ("punct", "("), ("punct", ")"), ("punct", ";")), (("comment", "the end"),)]
    assert len(front.parse("x =")) == 1


# --- records: imports -----------------------------------------------------------------------------------------

_IMPORTS = [
    pytest.param('import "./setup"', ((None, ("./setup", None)),), set(), id="side-effect"),
    pytest.param("import './setup';", ((None, ("./setup", None)),), set(), id="side-effect-single-quote"),
    pytest.param('import foo from "m"', (("foo", ("m", "default")),), {"foo"}, id="default"),
    pytest.param('import { a, b as c } from "m"', (("a", ("m", "a")), ("c", ("m", "b"))), {"a", "c"}, id="named"),
    pytest.param('import foo, { a, b as c, type d } from "m"',
                 (("foo", ("m", "default")), ("a", ("m", "a")), ("c", ("m", "b")), ("d", ("m", "d", "type"))),
                 {"foo", "a", "c", "d"}, id="default-and-named"),
    pytest.param('import foo, * as ns from "m"', (("foo", ("m", "default")), ("ns", ("m", "*"))), {"foo", "ns"},
                 id="default-and-namespace"),
    pytest.param('import * as ns from "m"', (("ns", ("m", "*")),), {"ns"}, id="namespace"),
    pytest.param('import type { A, B as C } from "m"', (("A", ("m", "A", "type")), ("C", ("m", "B", "type"))), {"A", "C"},
                 id="type-named"),
    pytest.param('import type Def from "m"', (("Def", ("m", "default", "type")),), {"Def"}, id="type-default"),
    pytest.param('import type * as ns from "m"', (("ns", ("m", "*", "type")),), {"ns"}, id="type-namespace"),
    pytest.param('import type from "m"', (("type", ("m", "default")),), {"type"}, id="default-named-type"),
    pytest.param('import { type as x } from "m"', (("x", ("m", "type")),), {"x"}, id="named-type-renamed"),
    pytest.param('import { type a as b } from "m"', (("b", ("m", "a", "type")),), {"b"}, id="type-specifier-renamed"),
    pytest.param('import { default as x, "str-name" as y } from "m"', (("x", ("m", "default")), ("y", ("m", "str-name"))),
                 {"x", "y"}, id="default-and-string-names"),
    pytest.param('import {\n  a,\n  b,\n} from "m"', (("a", ("m", "a")), ("b", ("m", "b"))), {"a", "b"}, id="multi-line-trailing-comma"),
    pytest.param('import {} from "m"', ((None, ("m", None)),), set(), id="empty-braces"),
]


@pytest.mark.parametrize("text, imports, binds", _IMPORTS)
def test_import_forms(text, imports, binds):
    rec = _only(text)
    assert rec["kind"] == "import"
    assert rec["imports"] == imports
    assert rec["binds"] == frozenset(binds)
    assert rec["hook"] is (not binds)


def test_import_key_is_its_tokens():
    assert _only('import a from "m"')["key"] == (
        ("id", "import"), ("id", "a"), ("id", "from"), ("str", "m"), ("punct", ";"))


def test_import_quote_style_and_semicolon_read_equal():
    _assert_same("import { a } from 'm'", 'import { a } from "m";')


def test_dynamic_import_and_import_meta_are_statements():
    assert _only('import("x")')["kind"] == "stmt"
    assert _only("import.meta.url")["kind"] == "stmt"
    assert _only('const m = await import("x")')["imports"] == ()


# --- records: binds -------------------------------------------------------------------------------------------

_BINDS = [
    ("function foo() {}", {"foo"}),
    ("export function* gen() {}", {"gen"}),
    ("async function a() {}", {"a"}),
    ("export default async function b() {}", {"b"}),
    ("export default function () {}", set()),
    ("class C {}", {"C"}),
    ("export default class D {}", {"D"}),
    ("export abstract class E {}", {"E"}),
    ("class extends Base {}", set()),
    ("enum En { A, B }", {"En"}),
    ("const enum CE { A }", {"CE"}),
    ("export interface I {}", {"I"}),
    ("type T = number", {"T"}),
    ("export type U = { a: 1 }", {"U"}),
    ("namespace N {}", {"N"}),
    ("declare module M {}", {"M"}),
    ('declare module "x" {}', set()),
    ("const a = 1, b = 2", {"a", "b"}),
    ("const f = (x, y) => x + y, g = 1", {"f", "g"}),
    ("export const e = f(1, 2), g = 3;", {"e", "g"}),
    ("var v", {"v"}),
    ("let l = 1", {"l"}),
    ("const é = 1", {"é"}),
    ('export { a, b } from "m"', set()),
    ('export * from "m"', set()),
    ("export { a, b }", set()),
    ("foo(a, b)", set()),
    ("module.exports = { a }", set()),
    ("type = 5", set()),
]


@pytest.mark.parametrize("text, names", _BINDS)
def test_binds_by_declaration_form(text, names):
    rec = _only(text)
    assert rec["kind"] == "stmt"
    assert rec["binds"] == frozenset(names)


def test_binds_of_a_destructuring_declaration_cover_every_bound_name():
    rec = _only("let { x, y: z } = obj, [p, q] = arr")
    assert {"x", "z", "p", "q"} <= rec["binds"]
    assert "obj" not in rec["binds"] and "arr" not in rec["binds"]


def test_binds_of_an_annotated_declaration_include_the_name():
    assert "x" in _only("const x: Map<string, number> = new Map()")["binds"]


# --- records: hook and uses -----------------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "beforeEach(() => {})", "beforeAll(setup)", "afterEach(() => {})", "afterAll(teardown)",
    'vi.mock("x")', 'jest.mock("x")', "vi.useFakeTimers()", "jest.setTimeout(5000)",
    'it("a", f)', "beforeEach.each", "vi(x)", 'import "./setup"',
])
def test_hook_true_for_module_level_setup(text):
    assert _only(text)["hook"] is True


@pytest.mark.parametrize("text", [
    'describe("a", () => {})', "const beforeEach = 1", "const vi = 1", 'import { vi } from "vitest"',
])
def test_hook_false_otherwise(text):
    assert _only(text)["hook"] is False


def test_hook_ignores_a_leading_comment():
    assert _only("// reset\nbeforeEach(() => {})")["hook"] is True


def test_a_comment_only_record_is_not_a_hook():
    assert [rec["hook"] for rec in front.parse("const a = 1\n// the end")] == [False, False]


def test_a_registration_needs_its_callee_to_be_a_framework_name():
    assert [rec["hook"] for rec in front.parse('import { it } from "vitest"\nit("a", () => {})')] == [False, False]
    recs = front.parse('import { it } from "./helpers"\nit("a", () => {})')
    assert [rec["hook"] for rec in recs] == [False, True]


# --- the allowlist for a host statement outside the moved test ------------------------------------------------

_FRAMEWORKS = frozenset(("it", "test", "describe"))


def _allowed(text, frameworks=_FRAMEWORKS):
    stmts = front._split(front._Scanner(text).run())
    assert len(stmts) == 1, stmts
    return front._allowed_host([tok for tok in stmts[0] if tok[0] != "comment"], frameworks)


@pytest.mark.parametrize("text", [
    pytest.param('import { a } from "m"', id="a-import-named"),
    pytest.param('import a from "m"', id="a-import-default"),
    pytest.param('import * as ns from "m"', id="a-import-namespace"),
    pytest.param('import type { T } from "m"', id="a-import-type"),
    pytest.param("function f(a, b) { return a }", id="b-function"),
    pytest.param("export default async function* g() {}", id="b-export-default-async-generator"),
    pytest.param("export async function h(): Promise<void> {}", id="b-return-type"),
    pytest.param("function f<T>(x: T): T { return x }", id="b-type-parameters"),
    pytest.param("class C {}", id="c-class"),
    pytest.param("export default class D extends Base { m() {} x = 1 }", id="c-extends-and-members"),
    pytest.param("export abstract class E<T> implements I {}", id="c-abstract-implements"),
    pytest.param("const a = 1", id="d-const"),
    pytest.param("export const f = x => load(x)", id="d-arrow"),
    pytest.param("let g = async function () { load() }", id="d-function-expression"),
    pytest.param("const o = { a: 1, b: [1, 2], c: `t` }", id="d-plain-expression"),
    pytest.param("var v", id="d-no-initializer"),
    pytest.param("const a = 1, b = x => x", id="d-two-declarators"),
    pytest.param("const m: Record<string, number> = {}", id="d-annotation-with-comma"),
    pytest.param("type T = number", id="e-type"),
    pytest.param("export interface I { a: string }", id="e-interface"),
    pytest.param("declare type U = string", id="e-declare"),
    pytest.param('it("x", () => {})', id="f-it"),
    pytest.param("test(`x`, function () {}, 5000)", id="f-test-with-timeout"),
    pytest.param('describe("x", () => { it("y", () => {}) })', id="f-describe"),
    pytest.param('describe("x", () => { it("y", () => {}); const k = 1; })', id="f-describe-with-plain-code"),
    pytest.param('describe("x", () => { describe("y", () => { test("z", () => {}) }) })', id="f-nested-describe"),
    pytest.param(";", id="lone-semicolon"),
])
def test_allowed_host_allows(text):
    assert _allowed(text) is True


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
    assert _allowed(text) is False


def test_allowed_host_needs_the_callee_to_be_a_framework_name():
    assert _allowed('it("x", () => {})', frozenset()) is False
    assert _allowed('describe("x", () => { it("y", () => {}) })', frozenset(("describe",))) is False


def test_uses_excludes_the_name_after_a_dot():
    assert _only("foo.bar(baz?.qux, a.b.c)")["uses"] == frozenset({"foo", "baz", "a"})


def test_uses_counts_keywords_and_private_names():
    uses = _only("class A { #p = 1; m() { return this.#p } }")["uses"]
    assert {"class", "A", "#p", "m", "return", "this"} <= uses


# --- the scanner ----------------------------------------------------------------------------------------------

def test_regex_literal_after_an_operator():
    toks = _tokens("x = /a\\/b[/]c/g.test(y)")
    assert ("re", "/a\\/b[/]c/g") in toks
    assert ("id", "test") in toks


def test_regex_literal_after_return_and_with_a_quote_inside():
    assert ("re", "/x/") in _tokens("function f() { return /x/.test(s) }")
    assert ("re", "/'/") in _tokens("x = /'/")


def test_slash_is_division_after_an_operand():
    toks = _tokens("a / b / c")
    assert toks.count(("punct", "/")) == 2
    assert not [t for t in toks if t[0] == "re"]
    assert [t for t in _tokens("f(x) / 2 / y") if t[0] == "re"] == []


def test_template_literal_nests_substitutions_strings_and_templates():
    toks = _tokens('x = `a ${ b + `c ${ d }` + "}" } e`')
    assert [t for t in toks if t[0] == "tpl"] == [("tpl", 'a ${ b + `c ${ d }` + "}" } e')]


def test_numbers_signs_and_leading_dot():
    assert [t[1] for t in _tokens("x = 1e+5 + 0xE+1 + .5 + 10n") if t[0] == "num"] == ["1e+5", "0xE", "1", ".5", "10n"]


def test_longest_punctuator_wins():
    puncts = [t[1] for t in _tokens("a >>>= b ?? c ?. d => e ... f") if t[0] == "punct"]
    assert ">>>=" in puncts and "??" in puncts and "?." in puncts and "=>" in puncts and "..." in puncts


def test_private_name_is_an_identifier():
    assert ("id", "#p") in _tokens("class A { #p = 1 }")


def test_a_line_break_in_a_block_comment_ends_a_statement():
    _assert_same("a /* x\ny */ b", "a; /* x y */ b")
    _assert_differ("a /* x y */ b", "a; /* x y */ b")


# --- fail closed: ValueError ----------------------------------------------------------------------------------

def test_unterminated_string_raises():
    for text in ['x = "abc', "x = 'abc\ndef'", 'x = "abc\\', "x = 'abc\r\n'"]:
        with pytest.raises(ValueError):
            front.parse(text)


def test_unterminated_template_raises():
    for text in ["x = `abc", "x = `a ${ b", "x = `a ${ b } c", "x = `a ${ '}' "]:
        with pytest.raises(ValueError):
            front.parse(text)


def test_unterminated_block_comment_raises():
    for text in ["/* abc", "a /* b *", "/*/"]:
        with pytest.raises(ValueError):
            front.parse(text)


def test_unterminated_regex_raises():
    for text in ["x = /abc", "x = /ab\nc/", "x = /[/", "x = /a\\"]:
        with pytest.raises(ValueError):
            front.parse(text)


def test_unbalanced_brackets_raise():
    for text in ["foo(", "foo)", "[1, 2)", "{", "}", "foo(a]", "function f() {", "(()"]:
        with pytest.raises(ValueError):
            front.parse(text)


def test_unknown_character_raises():
    for text in ["a = §", "a \\ b", "a = 1 \x00", "# x", "a = `ok` ¬"]:
        with pytest.raises(ValueError):
            front.parse(text)


@pytest.mark.parametrize("text", [
    "import",
    "import foo bar from 'm'",
    "import { a b } from 'm'",
    "import { a, , b } from 'm'",
    "import { a } 'm'",
    "import { a } from m",
    "import * ns from 'm'",
    "import * as from 'm'",
    "import a = require('x')",
    "import a, from 'm'",
    "import a, b from 'm'",
    "import 'm' with { type: 'json' }",
    "import 'm' 'n'",
    "import from 'm'",
    "import { type a b c d e } from 'm'",
    "import foo from 'm' extra",
    "import { a as 'b' } from 'm'",
])
def test_unparseable_import_form_raises(text):
    with pytest.raises(ValueError):
        front.parse(text)


def test_nothing_but_value_error_escapes():
    with pytest.raises(ValueError):
        front.parse("`${" * 2000)
    with pytest.raises(ValueError):
        front.parse(None)
    with pytest.raises(ValueError):
        front.parse(b"const a = 1")


# --- review round 1: relative imports, block-ending semicolons, template titles, lexical bindings ---------------

_RELATIVE_TEST = 'import { read } from "./subject";\nit("reads", () => { expect(read()).toBe(1); });\n'


def test_a_moved_test_with_a_relative_import_is_refused_but_a_same_directory_copy_is_found():
    moved = break_it_body.locate(_RELATIVE_TEST, "web/a.test.ts", [("other/b.test.ts", _RELATIVE_TEST)])
    assert (moved["status"], moved["reason"]) == ("unresolved", "binding-conflict")
    same = break_it_body.locate(_RELATIVE_TEST, "web/a.test.ts", [("web/b.test.ts", _RELATIVE_TEST)])
    assert same["status"] == "found"


@pytest.mark.parametrize("text, relative", [
    ('import { a } from "./m"', True),
    ('import { a } from "../m"', True),
    ('import "./m"', True),
    ('import { a } from "vitest"', False),
    ('const a = require("./m")', True),
    ('const a = require("m")', False),
    ('const a = await import("../m")', True),
    ('const a = await import("m")', False),
])
def test_relative_flag_marks_relative_module_paths(text, relative):
    assert _only(text)["relative"] is relative


@pytest.mark.parametrize("a, b", [
    ("{ expect(1).toBe(1) }", "{ expect(1).toBe(1); }"),
    ("{\n  expect(1).toBe(1)\n}", "{\n  expect(1).toBe(1);\n}"),
    ("{\n  expect(1).toBe(1) // done\n}", "{\n  expect(1).toBe(1); // done\n}"),
    ('it("x", () => { expect(1).toBe(1) })', 'it("x", () => { expect(1).toBe(1); })'),
])
def test_a_semicolon_before_a_closing_brace_reads_equal(a, b):
    _assert_same(a, b)


def test_a_semicolon_before_a_closing_brace_does_not_hide_a_changed_statement():
    _assert_differ("{ expect(1).toBe(1) }", "{ expect(1).toBe(2); }")


def test_a_template_title_with_a_substitution_stays_in_the_key():
    a = "let fixture = [];\nit(`case ${fixture.push(1)}`, () => { expect(fixture).toHaveLength(1); });"
    _assert_differ(a, a.replace("push(1)", "push(2)"))
    plain = "it(`case one`, f)"
    _assert_same(plain, plain.replace("one", "two"))


def test_a_callee_name_used_as_a_parameter_is_no_framework_name():
    a = 'it("x", () => { [expect].forEach(test => { test("bad").toBe("good"); }); });'
    _assert_differ(a, a.replace('"bad"', '"good"'))
    _assert_same('it("a", f)', 'it("b", f)')


def test_a_callee_name_imported_under_a_rename_is_no_framework_name():
    a = 'import { expect as test, it } from "vitest";\nit("x", () => { test("bad").toBe("good"); });'
    _assert_differ(a, a.replace('"bad"', '"good"'))
    own = 'import { test } from "vitest";\ntest("a", f)'
    _assert_same(own, own.replace('"a"', '"b"'))


def test_an_own_name_framework_import_still_normalizes_the_title():
    for module in ("vitest", "@jest/globals", "node:test", "bun:test"):
        own = 'import { it } from "%s";\nit("a", () => { expect(1).toBe(1); });' % module
        _assert_same(own, own.replace('"a"', '"b"'))
    default = 'import test from "vitest";\ntest("a", f)'
    _assert_differ(default, default.replace('"a"', '"b"'))


# --- review round 1 (#2053 L2) -----------------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    'test("regex", () => { expect("(").toMatch(/\\(/); });',
    'test("comment", () => {\n  // f(\n  expect(1).toBe(1);\n});',
])
def test_valid_js_with_a_paren_in_a_regex_or_comment_locates_an_identical_candidate(text):
    found = break_it_body.locate(text, "a.test.js", [("moved.test.js", text)])
    assert (found["status"], found["path"]) == ("found", "moved.test.js"), found


@pytest.mark.parametrize("params, hook", [
    ("()", False),
    ("(a, b)", False),
    ("a", False),
    ("({ unused = (globalThis.disabled = true) } = {})", True),
    ("(a = globalThis.x())", True),
    ("({ a })", True),
    ("(...rest)", True),
])
def test_a_describe_callback_with_a_parameter_default_or_pattern_is_a_hook(params, hook):
    arrow = 'describe("extra", %s => {});' % params
    assert _only(arrow)["hook"] is hook
    func = 'describe("extra", function %s {});' % (params if params.startswith("(") else "(%s)" % params)
    assert _only(func)["hook"] is hook


def test_a_template_literal_module_load_counts_as_relative():
    assert _only("const subject = require(`./subject`);")["relative"] is True
    assert _only("const subject = require(`../x/${name}`);")["relative"] is True
    assert _only("const subject = require(`left-pad`);")["relative"] is False
    moved = break_it_body.locate("const subject = require(`./subject`);\ntest(\"a\", () => { expect(subject).toBe(1); });",
                                 "old/a.test.js",
                                 [("other/b.test.js", "const subject = require(`./subject`);\ntest(\"a\", () => { expect(subject).toBe(1); });")])
    assert moved["status"] == "unresolved", moved
