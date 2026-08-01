"""Static AST census: dispatch outcome tokens live only in dispatch_outcome.py (#747)."""
import ast
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.realpath(os.path.join(_HERE, ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import dispatch_outcome  # noqa: E402

_BANNED_LITERALS = dispatch_outcome.ALL_REASONS | dispatch_outcome.ATTRIBUTIONS
# Live census scans outcome reasons only; ATTRIBUTION_UNKNOWN collides with unrelated
# "unknown" fallbacks across guardian/heartbeat/etc. — attribution literals are proven
# by test_matcher_catches_attribution_literal on synthetic source.
_LIVE_BANNED_LITERALS = dispatch_outcome.ALL_REASONS
_EXEMPT_MODULE = "dispatch_outcome.py"
_REQUIRED_BASENAMES = ("engine_dispatch.py", "round_driver.py", "seat_canary.py")


def _lineno(source_path, node):
    return "%s:%d" % (os.path.basename(source_path), node.lineno)


def _parse_source(source, source_path):
    try:
        return ast.parse(source, filename=source_path)
    except SyntaxError as exc:
        raise RuntimeError(
            "Census cannot parse %s: %s" % (source_path, exc)
        ) from exc


def _dict_key_constant_ids(tree):
    """Constants that are dictionary keys (result-contract field names, not outcome tokens)."""
    exempt = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for key in node.keys:
                if isinstance(key, ast.Constant):
                    exempt.add(id(key))
    return exempt


def _field_lookup_constant_ids(tree):
    """Constants naming a mapping field in .get('field') — not outcome token values."""
    exempt = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == "get"):
            continue
        if not node.args:
            continue
        first = node.args[0]
        if isinstance(first, ast.Constant):
            exempt.add(id(first))
        if len(node.args) > 1 and isinstance(node.args[0], ast.Constant):
            if node.args[0].value == "state" and isinstance(node.args[1], ast.Constant):
                exempt.add(id(node.args[1]))
    return exempt


def _supervisor_state_constant_ids(tree):
    """Constants in supervisor-state tuples (running/idle/abandon-requested), not reason tokens."""
    exempt = set()
    supervisor_markers = frozenset({"idle", "abandon-requested", "run-not-opened"})
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Tuple, ast.List)):
            continue
        elts = node.elts
        values = [
            e.value for e in elts
            if isinstance(e, ast.Constant) and isinstance(e.value, str)
        ]
        if supervisor_markers.intersection(values):
            for elt in elts:
                if isinstance(elt, ast.Constant):
                    exempt.add(id(elt))
    return exempt


def _state_keyword_constant_ids(tree):
    """Constants passed as state= in dict()/call keywords — supervisor state, not reason."""
    exempt = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for kw in node.keywords:
            if kw.arg != "state":
                continue
            val = kw.value
            if isinstance(val, ast.Constant):
                exempt.add(id(val))
            elif isinstance(val, ast.IfExp):
                if isinstance(val.body, ast.Constant):
                    exempt.add(id(val.body))
                if isinstance(val.orelse, ast.Constant):
                    exempt.add(id(val.orelse))
    return exempt


def _exempt_constant_ids(tree):
    exempt = set()
    exempt.update(_dict_key_constant_ids(tree))
    exempt.update(_field_lookup_constant_ids(tree))
    exempt.update(_supervisor_state_constant_ids(tree))
    exempt.update(_state_keyword_constant_ids(tree))
    return exempt


def census_violations_from_source(source, source_path, *, member_set=None):
    """Return violations for outcome/attribution string literals outside dict keys."""
    if member_set is None:
        member_set = _BANNED_LITERALS
    tree = _parse_source(source, source_path)
    exempt_ids = _exempt_constant_ids(tree)
    violations = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant):
            continue
        if not isinstance(node.value, str):
            continue
        if node.value not in member_set:
            continue
        if id(node) in exempt_ids:
            continue
        violations.append(
            "%s: literal '%s' (clause: outcome tokens live only in dispatch_outcome.py)"
            % (_lineno(source_path, node), node.value)
        )
    return violations


def census_violations(source_path, *, member_set=None):
    with open(source_path, encoding="utf-8") as fh:
        source = fh.read()
    return census_violations_from_source(source, source_path, member_set=member_set)


def _lib_python_modules(exclude_basenames=frozenset()):
    """Every .py under lib/, excluding tests/."""
    modules = []
    for root, dirs, files in os.walk(_LIB):
        dirs[:] = [d for d in dirs if d != "tests"]
        for name in files:
            if not name.endswith(".py"):
                continue
            if name in exclude_basenames:
                continue
            modules.append(os.path.join(root, name))
    modules.sort()
    return modules


def census_modules():
    return _lib_python_modules(exclude_basenames=frozenset({_EXEMPT_MODULE}))


def _path_under_tests(path):
    tests_dir = os.path.join(_LIB, "tests")
    try:
        return os.path.commonpath([os.path.realpath(path), tests_dir]) == tests_dir
    except ValueError:
        return False


def _validate_population(modules):
    if not modules:
        raise RuntimeError(
            "Dispatch-outcome census population collapsed: derived zero modules from %s "
            "(expected every .py under lib/ except %s and tests/)"
            % (_LIB, _EXEMPT_MODULE)
        )
    basenames = {os.path.basename(p) for p in modules}
    missing = [n for n in _REQUIRED_BASENAMES if n not in basenames]
    if missing:
        raise RuntimeError(
            "Dispatch-outcome census population collapsed: derived population missing "
            "required module(s): %s" % ", ".join(missing)
        )
    for path in modules:
        if _path_under_tests(path):
            raise RuntimeError(
                "Dispatch-outcome census population includes test module: %s" % path
            )


def run_census():
    modules = census_modules()
    _validate_population(modules)
    all_violations = []
    for path in modules:
        all_violations.extend(
            census_violations(path, member_set=_LIVE_BANNED_LITERALS))
    return all_violations


def test_dispatch_outcome_census_clean():
    violations = run_census()
    assert violations == [], (
        "INVARIANT: outcome tokens live only in dispatch_outcome.py; violations:\n  "
        + "\n  ".join(violations)
    )


def test_matcher_catches_reason_comparison_literal():
    source = (
        "def check(reason):\n"
        "    return reason == \"forfeited\"\n"
    )
    path = os.path.join(_LIB, "fake_consumer.py")
    violations = census_violations_from_source(source, path)
    assert violations, violations
    assert any("forfeited" in v for v in violations), violations


def test_matcher_exempts_forfeited_dict_key():
    source = (
        "def ok():\n"
        "    return {\"forfeited\": True}\n"
    )
    path = os.path.join(_LIB, "fake_consumer.py")
    violations = census_violations_from_source(source, path)
    assert violations == [], violations


def test_matcher_catches_attribution_literal():
    source = (
        "def bad():\n"
        "    return \"our-transport-contract\"\n"
    )
    path = os.path.join(_LIB, "fake_consumer.py")
    violations = census_violations_from_source(source, path)
    assert violations, violations
    assert any("our-transport-contract" in v for v in violations), violations
