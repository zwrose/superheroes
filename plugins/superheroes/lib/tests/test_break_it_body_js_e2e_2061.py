"""#2061: a JavaScript or TypeScript break-it test counts as kept by its body at any path.

End to end through `break_it.check_kept` against real fixture git repos. No node or vitest runs: a fake runner
records the block it was handed and returns a passed or failed record built by `break_it._record`. The helpers
are copied from `test_break_it_body_2053.py`, never imported."""
import hashlib
import os
import subprocess
import sys

import pytest

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import break_it  # noqa: E402
import break_it_body  # noqa: E402
import break_it_body_js  # noqa: E402
import break_it_body_py  # noqa: E402

# The fixture repo's commits pass an inline identity (a CI runner has no configured one); the throwaway fixture repo also signs nothing.
_ID = ["-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false"]


def _git(repo, *args):
    done = subprocess.run(["git", "-C", str(repo)] + list(args), capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


def _commit(repo, message):
    _git(repo, "add", "-A")
    _git(repo, *_ID, "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


def _write(repo, rel, text):
    target = repo / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(text, bytes):
        target.write_bytes(text)
    else:
        target.write_text(text)


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _write(root, "README.md", "fixture\n")
    _write(root, "web/weekly.ts", "export const weeklyTotal = (kcal: number[]) => kcal.reduce((a, b) => a + b, 0);\n")
    _commit(root, "base")
    return root


OWN = "web/eats.test.ts"
HOST = "web/weekly.test.ts"
COMMAND = "npx vitest run %s" % OWN
# The test as the loop wrote it: single quotes, no trailing commas, and a semicolon only where a line break does not
# end the statement (a block-final statement followed by `}` gets no automatic one, so a formatter adding it reads unequal).
ORIG = """import { describe, it, expect } from 'vitest'
import { weeklyTotal } from './weekly'

const eats = [{ day: 'mon', kcal: 500 }, { day: 'tue', kcal: 700 }]
const kcal = eats.map(e => e.kcal)

describe('meal plan', () => {
  it('sums a week of eats', () => {
    expect(weeklyTotal(kcal)).toBe(1200);
  });
})
"""
# The same test after prettier: quotes, semicolons, trailing commas, wrapped lines, `(x) =>`.
FORMATTED = """import { describe, it, expect } from "vitest";
import { weeklyTotal } from "./weekly";

const eats = [
  { day: "mon", kcal: 500 },
  { day: "tue", kcal: 700 },
];
const kcal = eats.map((e) => e.kcal);

describe("meal plan", () => {
  it("sums a week of eats", () => {
    expect(
      weeklyTotal(kcal),
    ).toBe(
      1200,
    );
  });
});
"""
HOST_IMPORTS = 'import { describe, expect, it } from "vitest";\nimport { planWeek, weeklyTotal } from "./weekly";\n'
HOST_OWN = '\nit("plans seven days", () => {\n  expect(planWeek()).toHaveLength(7);\n});\n\n'
HOST_BODY = FORMATTED.split('import { weeklyTotal } from "./weekly";\n\n', 1)[1].replace(
    '"meal plan"', '"meal plan (folded)"').replace('"sums a week of eats"', '"sums a week of eats (folded)"')


def _host(imports=HOST_IMPORTS, before=""):
    return imports + before + HOST_OWN + HOST_BODY


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _record(content=ORIG, path=OWN, command=COMMAND, **extra):
    out = {"path": path, "command": command, "sha256": _sha(content), "content": content}
    out.update(extra)
    return out


def _stage(repo, files):
    """Commit ``files`` ({path: text or bytes}) on top of the fixture base; return (base, head)."""
    base = _git(repo, "rev-parse", "HEAD")
    for rel, text in files.items():
        _write(repo, rel, text)
    return base, _commit(repo, "head")


def _stub(calls, outcome="passed"):
    def runner(repo_root, head, block, **kwargs):
        calls.append(dict(block))
        return break_it._record(head, block, outcome, exit_code=0 if outcome == "passed" else 1)
    return runner


def _got(result):
    return result["outcome"], result["reason"]


def _check(repo, base, head, record, runner=None):
    kwargs = {"runner": runner} if runner else {}
    return break_it.check_kept(str(repo), base, head, record, **kwargs)


# ---- (a) the consuming project's shape: folded into a host that already has vitest imports and its own it() ----

def test_a_ts_test_folded_into_a_host_with_merged_vitest_imports_is_kept_and_runs_the_host(repo):
    base, head = _stage(repo, {HOST: _host()})
    calls = []
    result = _check(repo, base, head, _record(), _stub(calls))
    assert _got(result) == ("kept", "body-match")
    assert result["run"]["outcome"] == "passed"
    assert result["path"] == OWN
    assert [c["run"] for c in calls] == ["npx vitest run %s" % HOST]
    assert calls[0]["path"] == HOST
    assert break_it_body.locate(ORIG, OWN, [(HOST, _host())])["titles"] == [
        ("meal plan", "meal plan (folded)"), ("sums a week of eats", "sums a week of eats (folded)")]


# ---- (a2) the pytest rename rules are the Python front's alone ---------------------------------------------

def test_a_js_title_change_without_a_test_prefix_reads_found_and_is_not_pytest_collected():
    found = break_it_body.locate(ORIG, OWN, [(HOST, _host())])
    assert found["status"] == "found" and found["reason"] is None and found["path"] == HOST
    assert found["titles"] and all(not new.startswith("test_") for _, new in found["titles"])
    assert break_it_body.pytest_collected(OWN) is False and break_it_body.pytest_collected(HOST) is False


def test_a_ts_rename_in_a_repository_whose_pytest_ini_sets_addopts_is_still_kept(repo):
    base, head = _stage(repo, {"pytest.ini": "[pytest]\naddopts = -k test_x\n", HOST: _host()})
    calls = []
    result = _check(repo, base, head, _record(), _stub(calls))
    assert _got(result) == ("kept", "body-match")
    assert [c["run"] for c in calls] == ["npx vitest run %s" % HOST]


def test_the_python_front_declares_pytest_collection_and_the_js_front_does_not():
    assert break_it_body_py.PYTEST_COLLECTION is True
    assert getattr(break_it_body_js, "PYTEST_COLLECTION", False) is False
    assert break_it_body.pytest_collected("tests/test_a.py") is True
    assert break_it_body.pytest_collected("README.md") is False


def test_a_python_rename_keeps_the_pytest_rules():
    old = "def test_x():\n    assert 1 == 1\n"
    kept = break_it_body.locate(old, "tests/test_a.py", [("tests/test_b.py", old.replace("test_x", "test_y"))])
    assert kept["status"] == "found" and kept["titles"] == [("test_x", "test_y")]
    refused = break_it_body.locate(old, "tests/test_a.py", [("tests/test_b.py", old.replace("test_x", "testing_x"))])
    assert (refused["status"], refused["reason"]) == ("unresolved", "binding-conflict")


# ---- (b) a prettier-style reformat at the test's own path -----------------------------------------------

def test_a_prettier_reformat_at_its_own_path_is_kept_and_the_command_is_unchanged(repo):
    base, head = _stage(repo, {OWN: FORMATTED})
    # Doubled spaces and a quoted path: a command rebuilt from its tokens would not be these bytes.
    command = "npx  vitest run  '%s'" % OWN
    calls = []
    result = _check(repo, base, head, _record(command=command), _stub(calls))
    assert _got(result) == ("kept", "body-match")
    assert result["path"] == OWN
    assert [c["run"] for c in calls] == [command]
    assert calls[0]["path"] == OWN


# ---- (c) a changed test is not kept, at its own path or moved --------------------------------------------

CHANGES = {
    "assertion-value": lambda t: t.replace("1200", "1201"),
    "fixture-value": lambda t: t.replace("kcal: 700", "kcal: 701"),
}


@pytest.mark.parametrize("change", sorted(CHANGES))
def test_a_changed_ts_test_at_its_own_path_reads_changed(repo, change):
    assert CHANGES[change](ORIG) != ORIG and CHANGES[change](FORMATTED) != FORMATTED
    base, head = _stage(repo, {OWN: CHANGES[change](FORMATTED)})
    calls = []
    assert _got(_check(repo, base, head, _record(), _stub(calls))) == ("changed", "sha256-differs")
    assert calls == []


@pytest.mark.parametrize("change", sorted(CHANGES))
def test_a_changed_ts_test_in_a_moved_copy_reads_missing(repo, change):
    assert CHANGES[change](_host()) != _host()
    base, head = _stage(repo, {HOST: CHANGES[change](_host())})
    calls = []
    assert _got(_check(repo, base, head, _record(), _stub(calls))) == ("missing", "not-in-head")
    assert calls == []


# ---- (d) unreadable and ambiguous searches read unresolved ------------------------------------------------

def test_a_prefilter_passing_unparseable_candidate_is_unresolved_beside_a_match(repo):
    broken = ORIG + '\nconst broken = "oops\n'
    base, head = _stage(repo, {HOST: _host(), "web/broken.test.ts": broken})
    calls = []
    assert _got(_check(repo, base, head, _record(), _stub(calls))) == ("unresolved", "body-unparseable")
    assert calls == []


def test_a_prefilter_passing_unparseable_candidate_without_a_match_is_unresolved(repo):
    base, head = _stage(repo, {"web/broken.test.ts": ORIG + '\nconst broken = "oops\n'})
    assert _got(_check(repo, base, head, _record())) == ("unresolved", "body-unparseable")


def test_two_matching_copies_are_ambiguous(repo):
    base, head = _stage(repo, {"web/a.test.ts": ORIG.replace("meal plan", "copy a"), "web/b.test.ts": FORMATTED})
    calls = []
    assert _got(_check(repo, base, head, _record(), _stub(calls))) == ("unresolved", "match-ambiguous")
    assert calls == []


# ---- (e) module-level test setup the host adds ------------------------------------------------------------

def test_a_host_top_level_before_each_is_host_setup(repo):
    host = _host(imports=HOST_IMPORTS.replace("describe", "beforeEach, describe"),
                 before="\nbeforeEach(() => {\n  window.localStorage.clear();\n});\n")
    base, head = _stage(repo, {HOST: host})
    calls = []
    assert _got(_check(repo, base, head, _record(), _stub(calls))) == ("unresolved", "host-setup")
    assert calls == []


def test_a_host_it_only_is_host_setup(repo):
    base, head = _stage(repo, {HOST: _host(before='\nit.only("focused", () => {});\n')})
    calls = []
    assert _got(_check(repo, base, head, _record(), _stub(calls))) == ("unresolved", "host-setup")
    assert calls == []


def test_a_host_side_effect_import_is_host_setup(repo):
    base, head = _stage(repo, {HOST: _host(imports=HOST_IMPORTS + 'import "./setup";\n')})
    calls = []
    assert _got(_check(repo, base, head, _record(), _stub(calls))) == ("unresolved", "host-setup")
    assert calls == []


def test_a_host_import_from_a_module_named_from_is_not_host_setup(repo):
    base, head = _stage(repo, {HOST: _host(imports=HOST_IMPORTS + 'import stream from "from";\n')})
    found = break_it_body.locate(ORIG, OWN, [(HOST, (repo / HOST).read_text())])
    assert (found["status"], found["reason"]) == ("found", None)


def test_a_host_import_from_a_module_named_future_does_not_change_the_future_comparison(repo):
    host = _host(imports=HOST_IMPORTS + 'import { annotations } from "__future__";\n')
    found = break_it_body.locate(ORIG, OWN, [(HOST, host)])
    assert (found["status"], found["reason"]) == ("found", None)


def test_the_python_import_predicates_ignore_a_non_python_front():
    pair = ("x", ("from", 0, "other"))
    assert break_it_body._may_import_fixture(pair)
    assert not break_it_body._may_import_fixture(pair, python=False)
    rec = {"imports": (("annotations", ("from", 0, "__future__", "annotations")),)}
    assert break_it_body._futures([rec]) == {"annotations"}
    assert break_it_body._futures([rec], python=False) == set()


# ---- (f) moved but failing --------------------------------------------------------------------------------

def test_a_moved_ts_test_whose_runner_fails_reads_failing(repo):
    base, head = _stage(repo, {HOST: _host()})
    calls = []
    result = _check(repo, base, head, _record(), _stub(calls, "failed"))
    assert result["outcome"] == "failing"
    assert result["run"]["outcome"] == "failed"
    assert [c["run"] for c in calls] == ["npx vitest run %s" % HOST]


# ---- round 2: import order, runtime imports, type aliases -------------------------------------------------

SETUP_ORIG = 'import "./setup";\n' + ORIG


def _located(host, content=SETUP_ORIG):
    found = break_it_body.locate(content, OWN, [(HOST, host)])
    return found["status"], found["reason"]


SAME_IMPORTS = 'import { describe, expect, it } from "vitest";\nimport { weeklyTotal } from "./weekly";\n'


def test_a_setup_import_kept_before_the_named_imports_in_order_reads_found():
    host = 'import "./setup";\n' + SAME_IMPORTS + HOST_OWN + HOST_BODY
    assert _located(host) == ("found", None)


def test_an_extra_runtime_import_prepended_beside_a_setup_import_reads_host_setup():
    host = 'import { probe } from "./subject.mjs";\nimport "./setup";\n' + SAME_IMPORTS + HOST_OWN + HOST_BODY
    assert _located(host) == ("unresolved", "host-setup")


def test_an_extra_name_in_a_shared_module_import_beside_a_setup_import_reads_host_setup():
    assert _located('import "./setup";\n' + _host()) == ("unresolved", "host-setup")


def test_a_setup_import_moved_after_a_named_import_reads_host_setup():
    host = 'import { describe, expect, it } from "vitest";\nimport { weeklyTotal } from "./weekly";\nimport "./setup";\n' \
        + HOST_OWN + HOST_BODY
    assert _located(host) == ("unresolved", "host-setup")


def test_a_setup_import_added_to_a_host_whose_original_had_none_reads_host_setup():
    assert _located('import "./setup";\n' + _host(), ORIG) == ("unresolved", "host-setup")


def test_a_runtime_host_import_that_rebinds_a_name_the_test_uses_reads_binding_conflict():
    host = _host(imports=HOST_IMPORTS + 'import { eats } from "./fixtures";\n')
    assert _located(host, ORIG) == ("unresolved", "binding-conflict")


def test_a_runtime_host_import_that_rebinds_a_name_the_test_uses_reads_binding_conflict_beside_a_setup_import():
    host = 'import "./setup";\n' + _host(imports=HOST_IMPORTS + 'import { eats } from "./fixtures";\n')
    assert _located(host) == ("unresolved", "binding-conflict")


def test_a_type_only_import_does_not_make_a_same_named_value_declaration_a_rebinding():
    content = ORIG.replace("const eats", 'const Model = { id: 1 };\nconst eats', 1)
    content = 'import type { Model } from "./types";\n' + content
    host = HOST_IMPORTS + 'import type { Model } from "./types";\n' + HOST_OWN + "const Model = { id: 1 };\n" + HOST_BODY
    assert _located(host, content) == ("found", None)


def test_a_runtime_import_and_a_value_declaration_of_one_name_reads_binding_conflict():
    content = ORIG.replace("const eats", 'const Model = { id: 1 };\nconst eats', 1)
    content = 'import { Model } from "./types";\n' + content
    host = HOST_IMPORTS + 'import { Model } from "./types";\n' + HOST_OWN + "const Model = { id: 1 };\n" + HOST_BODY
    assert _located(host, content) == ("unresolved", "binding-conflict")


@pytest.mark.parametrize("alias, hook", [
    ("type T = { m(): void }", False),
    ("type T = { m(): void; n(x: number): string }", False),
    ("type T = number\n(test.only)('focused', () => {})", True),
    ("type T = number\n[test.only]", True),
    ("type T = Array<number>\nfoo()", True),
    ("type T = number\n`x${test.only('f', () => {})}`", True),
    ("type T = `focused${test.only('f', () => {})}`", True),
    ("type T = { a: number\n b: string }", False),
    ("type T =\n  | { a: 1 }\n  | { b: 2 }", False),
    ("type T = A\n  extends B ? 1 : 2", False),
])
def test_a_type_alias_is_harmless_only_when_nothing_executable_can_follow_it(alias, hook):
    records = break_it_body_js.parse(alias)
    assert [rec["hook"] for rec in records].count(True) == (1 if hook else 0), records


# ---- round 3: per-binding type-only imports, type-erased import order, JS rename configuration -------------

def _with_model(import_line, extra=""):
    """The original and a host that both carry ``import_line`` and a ``const Model`` value (plus ``extra``)."""
    content = import_line + ORIG.replace("const eats", "const Model = { id: 1 };\n" + extra + "const eats", 1)
    host = HOST_IMPORTS + import_line + HOST_OWN + "const Model = { id: 1 };\n" + extra + HOST_BODY
    return content, host


def test_a_mixed_import_whose_type_binding_shares_a_value_name_reads_found():
    content, host = _with_model('import { type Model, helper } from "types";\n')
    assert _located(host, content) == ("found", None)


def test_a_mixed_import_whose_runtime_binding_is_rebound_reads_binding_conflict():
    content, host = _with_model('import { type Model, helper } from "types";\n', "const helper = 2;\n")
    assert _located(host, content) == ("unresolved", "binding-conflict")


TYPED_SETUP = 'import type { Model } from "./subject";\n'


def test_a_setup_import_swapped_after_a_named_import_behind_a_type_import_reads_host_setup():
    content = TYPED_SETUP + 'import "./setup";\nimport { value } from "./subject";\n' + ORIG
    host = TYPED_SETUP + 'import { value } from "./subject";\nimport "./setup";\n' + _host()
    assert _located(host, content) == ("unresolved", "host-setup")


def test_a_setup_import_kept_in_order_behind_a_type_import_reads_found():
    content = TYPED_SETUP + 'import "./setup";\nimport { value } from "./subject";\n' + ORIG
    host = TYPED_SETUP + 'import "./setup";\nimport { value } from "./subject";\n' + SAME_IMPORTS + HOST_OWN + HOST_BODY
    assert _located(host, content) == ("found", None)


INLINE_TYPED = 'import { type Model } from "./subject";\n'


def test_an_inline_type_only_import_moved_across_a_setup_import_reads_host_setup():
    content = INLINE_TYPED + 'import "./setup";\n' + ORIG
    host = 'import "./setup";\n' + INLINE_TYPED + SAME_IMPORTS + HOST_OWN + HOST_BODY
    assert _located(host, content) == ("unresolved", "host-setup")


def test_an_inline_type_only_import_kept_in_order_beside_a_setup_import_reads_found():
    content = INLINE_TYPED + 'import "./setup";\n' + ORIG
    host = INLINE_TYPED + 'import "./setup";\n' + SAME_IMPORTS + HOST_OWN + HOST_BODY
    assert _located(host, content) == ("found", None)


def test_the_js_front_declares_its_own_rename_gate_and_the_python_front_does_not():
    assert break_it_body_js.JS_COLLECTION is True
    assert getattr(break_it_body_py, "JS_COLLECTION", False) is False
    assert break_it_body.js_collected(HOST) is True
    assert break_it_body.js_collected("tests/test_a.py") is False


@pytest.mark.parametrize("files", [
    pytest.param({"vitest.config.ts": "export default { test: { testNamePattern: /^regression/ } };\n"}, id="vitest-config"),
    pytest.param({"jest.config.js": "module.exports = {};\n"}, id="jest-config"),
    pytest.param({"vite.config.mts": "export default {};\n"}, id="vite-config"),
    pytest.param({"vitest.workspace.json": "[]\n"}, id="vitest-workspace"),
    pytest.param({"package.json": '{"name": "x", "jest": {"testNamePattern": "regression"}}\n'}, id="package-jest"),
    pytest.param({"package.json": '{"name": "x", "vitest": {}}\n'}, id="package-vitest"),
    pytest.param({"package.json": '{"name": "x",\n'}, id="package-unparseable"),
    pytest.param({"package.json": '["not", "an", "object"]\n'}, id="package-not-an-object"),
])
def test_a_ts_rename_in_a_repository_with_js_test_configuration_reads_unresolved(repo, files):
    base, head = _stage(repo, dict(files, **{HOST: _host()}))
    calls = []
    assert _got(_check(repo, base, head, _record(), _stub(calls))) == ("unresolved", "binding-conflict")
    assert calls == []


def test_a_ts_rename_with_a_plain_package_json_and_no_js_config_is_kept(repo):
    base, head = _stage(repo, {"package.json": '{"name": "x", "scripts": {"test": "vitest"}}\n', HOST: _host()})
    calls = []
    assert _got(_check(repo, base, head, _record(), _stub(calls))) == ("kept", "body-match")
    assert [c["run"] for c in calls] == ["npx vitest run %s" % HOST]


@pytest.mark.parametrize("command", [
    "npx vitest run --config web/vitest.config.ts %s" % OWN,
    "npx vitest run -c web/vitest.config.ts %s" % OWN,
    "npx vitest run --root web %s" % OWN,
    "npx vitest run --project unit %s" % OWN,
    "npx vitest run --config=web/vitest.config.ts %s" % OWN,
], ids=["config", "short-config", "root", "project", "config-equals"])
def test_a_ts_rename_whose_command_carries_an_option_reads_unresolved(repo, command):
    base, head = _stage(repo, {"web/vitest.config.ts": "export default { test: { testNamePattern: /^regression/ } };\n", HOST: _host()})
    calls = []
    assert _got(_check(repo, base, head, _record(command=command), _stub(calls))) == ("unresolved", "binding-conflict")
    assert calls == []


def test_a_ts_rename_whose_command_carries_only_env_pairs_and_runner_words_is_kept(repo):
    base, head = _stage(repo, {HOST: _host()})
    calls = []
    record = _record(command="CI=1 pnpm exec vitest run %s" % OWN)
    assert _got(_check(repo, base, head, record, _stub(calls))) == ("kept", "body-match")
    assert [c["run"] for c in calls] == ["CI=1 pnpm exec vitest run %s" % HOST]


MOVED = "web/eats-moved.test.ts"
RETITLED = FORMATTED.replace('"meal plan"', '"meal plan renamed"')
_SHAPES = {
    "move-same-title": lambda: {MOVED: FORMATTED},
    "retitle-same-path": lambda: {OWN: RETITLED},
}


@pytest.mark.parametrize("shape", sorted(_SHAPES))
@pytest.mark.parametrize("runner", [
    "pnpm vitest run", "pnpm test", "npm run test", "yarn test", "npm test", "yarn vitest run", "bun test",
    "node --test", "pnpm run vitest", "pnpm exec echo", "npx cowsay", "pnpm exec",
], ids=lambda r: r.replace(" ", "-"))
def test_a_moved_or_retitled_ts_test_whose_command_is_not_a_direct_runner_reads_unresolved(repo, runner, shape):
    base, head = _stage(repo, _SHAPES[shape]())
    calls = []
    record = _record(command="%s %s" % (runner, OWN))
    assert _got(_check(repo, base, head, record, _stub(calls))) == ("unresolved", "binding-conflict")
    assert calls == []


@pytest.mark.parametrize("shape", sorted(_SHAPES))
@pytest.mark.parametrize("runner", [
    "vitest run", "jest", "npx vitest run", "bunx vitest run", "pnpm exec vitest run", "yarn exec jest",
    "CI=1 pnpm exec vitest run",
], ids=lambda r: r.replace(" ", "-"))
def test_a_moved_or_retitled_ts_test_whose_command_calls_the_runner_directly_is_kept(repo, runner, shape):
    base, head = _stage(repo, _SHAPES[shape]())
    calls = []
    record = _record(command="%s %s" % (runner, OWN))
    assert _got(_check(repo, base, head, record, _stub(calls))) == ("kept", "body-match")
    assert len(calls) == 1


def test_a_ts_test_at_its_own_path_keeps_a_package_script_command_unchanged(repo):
    base, head = _stage(repo, {OWN: FORMATTED})
    calls = []
    record = _record(command="pnpm test %s" % OWN)
    assert _got(_check(repo, base, head, record, _stub(calls))) == ("kept", "body-match")
    assert [c["run"] for c in calls] == ["pnpm test %s" % OWN]


@pytest.mark.parametrize("import_line", [
    'import type { Model as ModelType } from "types";\n',
    'import { type Model as ModelType } from "types";\n',
], ids=["declaration-type", "inline-type"])
def test_a_type_only_aliased_import_does_not_make_its_source_name_a_runtime_use(import_line):
    content, host = _with_model(import_line)
    assert _located(host, content) == ("found", None)


def test_a_whitespace_change_inside_a_template_substitution_keeps_the_same_key():
    old = break_it_body_js.parse("const a = `x ${1+2} y ${f( b )}`;\n")
    new = break_it_body_js.parse("const a = `x ${1 + 2} y ${f(b)}`;\n")
    assert [r["key"] for r in old] == [r["key"] for r in new]


def test_a_change_to_the_literal_text_of_a_template_changes_the_key():
    old = break_it_body_js.parse("const a = `x ${1+2} y`;\n")
    new = break_it_body_js.parse("const a = `x ${1+2}  y`;\n")
    assert [r["key"] for r in old] != [r["key"] for r in new]


def test_a_change_to_a_template_substitution_expression_changes_the_key():
    old = break_it_body_js.parse("const a = `x ${1+2} y`;\n")
    new = break_it_body_js.parse("const a = `x ${1+3} y`;\n")
    assert [r["key"] for r in old] != [r["key"] for r in new]


def test_a_jsx_test_with_a_closing_tag_keeps_its_key_when_unchanged_and_changes_it_when_the_assertion_changes():
    same = "render(<p>Hello</p>);\nexpect(screen.getByText('Hello')).toBeTruthy();\n"
    other = "render(<p>Hello</p>);\nexpect(screen.getByText('Bye')).toBeTruthy();\n"
    keys = lambda text: [r["key"] for r in break_it_body_js.parse(text)]
    assert keys(same) == keys(same) and keys(same) != keys(other)


def test_a_jsx_closing_tag_reads_without_a_regular_expression_error():
    records = break_it_body_js.parse("render(<p>Hello</p>);\n")
    assert len(records) == 1


def test_an_unrenamed_moved_ts_test_with_an_option_is_not_refused_by_the_option_rule(repo):
    host = HOST_IMPORTS + HOST_OWN + FORMATTED.split('import { weeklyTotal } from "./weekly";\n\n', 1)[1]
    base, head = _stage(repo, {HOST: host})
    calls = []
    record = _record(command="npx vitest run --reporter=dot %s" % OWN)
    assert _got(_check(repo, base, head, record, _stub(calls))) == ("kept", "body-match")


def test_an_unrenamed_moved_ts_test_is_kept_beside_a_vitest_config(repo):
    host = HOST_IMPORTS + HOST_OWN + FORMATTED.split('import { weeklyTotal } from "./weekly";\n\n', 1)[1]
    base, head = _stage(repo, {"vitest.config.ts": "export default {};\n", HOST: host})
    calls = []
    assert _got(_check(repo, base, head, _record(), _stub(calls))) == ("kept", "body-match")
    assert [c["run"] for c in calls] == ["npx vitest run %s" % HOST]
