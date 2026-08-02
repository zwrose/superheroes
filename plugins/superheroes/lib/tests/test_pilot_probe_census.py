"""Static AST census: pilot probe tokens live only in pilot_probe.py (A1)."""
import ast
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.realpath(os.path.join(_HERE, ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import pilot_probe  # noqa: E402

_BANNED_LITERALS = pilot_probe.ALL_PROBE_REASONS
_EXEMPT_MODULE = "pilot_probe.py"
_REQUIRED_BASENAMES = ("engine.py", "store.py")
_REFUSAL_MODULE_BASENAMES = ("pilot_contract.py", "pilot_seed.py", "pilot_slot.py")


def _lineno(source_path, node):
    return "%s:%d" % (os.path.basename(source_path), node.lineno)


def _parse_source(source, source_path):
    try:
        return ast.parse(source, filename=source_path)
    except SyntaxError as exc:
        raise RuntimeError(
            "Census cannot parse %s: %s" % (source_path, exc)
        ) from exc


def census_violations_from_source(source, source_path, *, member_set=None):
    """Return violations for probe-reason string literals outside pilot_probe.py."""
    if member_set is None:
        member_set = _BANNED_LITERALS
    tree = _parse_source(source, source_path)
    violations = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant):
            continue
        if not isinstance(node.value, str):
            continue
        if node.value not in member_set:
            continue
        violations.append(
            "%s: literal '%s' (clause: probe tokens live only in pilot_probe.py)"
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
            "Pilot-probe census population collapsed: derived zero modules from %s "
            "(expected every .py under lib/ except %s and tests/)"
            % (_LIB, _EXEMPT_MODULE)
        )
    basenames = {os.path.basename(p) for p in modules}
    missing = [n for n in _REQUIRED_BASENAMES if n not in basenames]
    if missing:
        raise RuntimeError(
            "Pilot-probe census population collapsed: derived population missing "
            "required module(s): %s" % ", ".join(missing)
        )
    for path in modules:
        if _path_under_tests(path):
            raise RuntimeError(
                "Pilot-probe census population includes test module: %s" % path
            )


def run_census():
    modules = census_modules()
    _validate_population(modules)
    all_violations = []
    for path in modules:
        all_violations.extend(census_violations(path, member_set=_BANNED_LITERALS))
    return all_violations


def _reason_constants_from_module_source():
    """Collect values of module-level REASON_* assignments in pilot_probe.py."""
    path = os.path.join(_LIB, _EXEMPT_MODULE)
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=path)
    values = set()
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue
            if not target.id.startswith("REASON_"):
                continue
            if not isinstance(node.value, ast.Constant):
                continue
            if not isinstance(node.value.value, str):
                continue
            values.add(node.value.value)
    return values


def _refusal_constants_from_module(path):
    """Collect values of module-level REFUSAL_* assignments via AST."""
    with open(path, encoding="utf-8") as fh:
        source = fh.read()
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as exc:
        raise RuntimeError("Cannot parse %s: %s" % (path, exc)) from exc
    values = set()
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue
            if not target.id.startswith("REFUSAL_"):
                continue
            if not isinstance(node.value, ast.Constant):
                continue
            if not isinstance(node.value.value, str):
                continue
            values.add(node.value.value)
    return values


def _collect_all_refusal_tokens():
    all_tokens = set()
    for basename in _REFUSAL_MODULE_BASENAMES:
        path = os.path.join(_LIB, basename)
        tokens = _refusal_constants_from_module(path)
        if not tokens:
            raise RuntimeError(
                "Refusal-token drift walk collected zero constants from %s" % path
            )
        all_tokens.update(tokens)
    return all_tokens


def test_pilot_probe_census_clean():
    violations = run_census()
    assert violations == [], (
        "INVARIANT: probe tokens live only in pilot_probe.py; violations:\n  "
        + "\n  ".join(violations)
    )


def test_reason_constants_match_all_probe_reasons():
    """Job B: every REASON_* constant must equal ALL_PROBE_REASONS exactly."""
    declared = _reason_constants_from_module_source()
    assert declared == pilot_probe.ALL_PROBE_REASONS
    assert len(declared) == pilot_probe.EXPECTED_TOKEN_COUNT


def test_matcher_catches_reason_comparison_literal():
    source = (
        "def check(reason):\n"
        "    return reason == \"no-session\"\n"
    )
    path = os.path.join(_LIB, "fake_consumer.py")
    violations = census_violations_from_source(source, path)
    assert violations, violations
    assert any("no-session" in v for v in violations), violations


def test_matcher_catches_no_session_dict_key_dispatch():
    source = (
        "def route():\n"
        "    return {\"no-session\": handler}\n"
    )
    path = os.path.join(_LIB, "fake_consumer.py")
    violations = census_violations_from_source(source, path)
    assert violations, violations
    assert any("no-session" in v for v in violations), violations


def test_matcher_catches_no_session_get_call():
    source = (
        "def lookup(handlers):\n"
        "    return handlers.get(\"no-session\")\n"
    )
    path = os.path.join(_LIB, "fake_consumer.py")
    violations = census_violations_from_source(source, path)
    assert violations, violations
    assert any("no-session" in v for v in violations), violations


_PILOT_CONTRACT = os.path.join(
    os.path.dirname(_LIB), "reference", "pilot-contract.md"
)
_PROFILE_TEMPLATE = os.path.join(
    os.path.dirname(_LIB), "templates", "profile.md"
)


def test_pilot_contract_names_every_probe_token():
    """axis: every probe member is actually named in pilot-contract.md — presence, not mere existence."""
    with open(_PILOT_CONTRACT, encoding="utf-8") as fh:
        doc = fh.read()
    missing = [
        reason for reason in sorted(pilot_probe.ALL_PROBE_REASONS)
        if reason not in doc
    ]
    assert missing == [], (
        "pilot-contract.md missing probe token(s): %s (file: %s)"
        % (", ".join(missing), _PILOT_CONTRACT)
    )


def test_pilot_contract_names_every_refusal_token():
    """axis: every REFUSAL_* constant value is named in pilot-contract.md."""
    if not os.path.isfile(_PILOT_CONTRACT):
        raise AssertionError(
            "pilot-contract.md missing (file: %s)" % _PILOT_CONTRACT
        )
    with open(_PILOT_CONTRACT, encoding="utf-8") as fh:
        doc = fh.read()
    tokens = _collect_all_refusal_tokens()
    missing = [token for token in sorted(tokens) if token not in doc]
    assert missing == [], (
        "pilot-contract.md missing refusal token(s): %s (file: %s)"
        % (", ".join(missing), _PILOT_CONTRACT)
    )


def test_profile_template_unseeded_expectation_is_probe_token():
    import re

    with open(_PROFILE_TEMPLATE, encoding="utf-8") as fh:
        doc = fh.read()
    match = re.search(r'"unseededExpectation"\s*:\s*"([^"]+)"', doc)
    if match is None:
        raise AssertionError(
            "profile.md has no unseededExpectation example (file: %s)" % _PROFILE_TEMPLATE
        )
    token = match.group(1)
    assert token in pilot_probe.ALL_PROBE_REASONS, (
        "profile.md unseededExpectation %r is not a probe token (file: %s)"
        % (token, _PROFILE_TEMPLATE)
    )
