"""Layering invariants for payload_contracts — import closure and re-export identity."""
import ast
import importlib.util
import json
import os
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import payload_contracts  # noqa: E402
import round_adapters  # noqa: E402

# Adding a name here is a deliberate layering decision. The six names deleted in #1123 WO-A
# (`round_adapters`, `round_records`, `verification`, `circuit_breaker`, `panel_tally`,
# `loop_state`) plus `review_result` must never return.
# `dispatch_allowlist` loads because the allowlist is consulted at the entry chokepoint
# (`seat_bundle.resolve_entry`), so any dispatch entry imports it.
_ENGINE_ADAPTER_LIB_CLOSURE = frozenset({
    "audits",
    "claude_modes",
    "dispatch_allowlist",
    "dispatch_outcome",
    "engine_adapter",
    "finding_identity",
    "model_registry",
    "payload_contracts",
    "pr_comment",
    "readout",
    "resolved_inputs_vocab",
    "review_findings_schema",
    "review_memory",
    "round_phases",
    "round_panel_contract",  # stdlib-only panel-contract leaf round_phases re-exports from
    "seat_bundle",
})

_REEXPORT_NAMES = (
    "ADAPTER_PHASES",
    "SEAT_SYNTHESIS",
    "SEAT_GAPSWEEP",
    "SEAT_SCOPED",
    "SEAT_VERIFY",
    "SEAT_FIXER",
    "RULING_NEW_ISSUE",
    "VACUOUS_FIELD",
    "TYPE_TOKENS",
    "payload_contract",
    "payload_fault",
    "_label",
    "_type_name",
)

# finding_identity and review_memory arrive transitively through audits — not a layering slip.
_PAYLOAD_CONTRACTS_LIB_CLOSURE = frozenset({
    "audits",
    "dispatch_outcome",
    "finding_identity",
    "payload_contracts",
    "review_memory",
    "round_phases",
    "round_panel_contract",  # stdlib-only panel-contract leaf round_phases re-exports from
})


def _import_closure_modules(module_name):
    """Return lib/ modules loaded by importing module_name in a fresh interpreter."""
    program = (
        "import json, os, sys\n"
        "lib = %r\n"
        "sys.path.insert(0, lib)\n"
        "before = set(sys.modules)\n"
        "import %s  # noqa: F401\n"
        "loaded = []\n"
        "for name, mod in sys.modules.items():\n"
        "    if name in before:\n"
        "        continue\n"
        "    path = getattr(mod, '__file__', None)\n"
        "    if path and os.path.dirname(os.path.abspath(path)) == os.path.abspath(lib):\n"
        "        loaded.append(name)\n"
        "print(json.dumps(sorted(loaded)))\n"
    ) % (_LIB, module_name)
    proc = subprocess.run(
        [sys.executable, "-B", "-c", program],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    return frozenset(json.loads(proc.stdout.strip()))


def test_engine_adapter_import_closure_is_pinned():
    """Importing engine_adapter loads exactly the pinned lib/ closure — no round-layer modules."""
    loaded = _import_closure_modules("engine_adapter")
    expected = _ENGINE_ADAPTER_LIB_CLOSURE
    if loaded != expected:
        unexpected = sorted(loaded - expected)
        missing = sorted(expected - loaded)
        pytest.fail(
            "engine_adapter import closure mismatch: unexpected=%r missing=%r"
            % (unexpected, missing)
        )


_LIB_TOP_LEVEL_MODULE_NAMES = frozenset(
    entry[:-3]
    for entry in os.listdir(_LIB)
    if entry.endswith(".py") and not entry.startswith("_")
)


def _stdlib_prefix():
    spec = importlib.util.find_spec("json")
    assert spec is not None and spec.origin
    return os.path.dirname(os.path.abspath(spec.origin))


def _import_roots(tree):
    roots = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level:
                roots.append(("relative", node.lineno))
                continue
            if node.module:
                roots.append((node.module.split(".")[0], node.lineno))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                roots.append((alias.name.split(".")[0], node.lineno))
    return roots


def _is_stdlib_or_future(root):
    if root == "__future__":
        return True
    if root in sys.builtin_module_names:
        return True
    if root in _LIB_TOP_LEVEL_MODULE_NAMES:
        return False
    spec = importlib.util.find_spec(root)
    if spec is None or not spec.origin:
        return False
    return os.path.abspath(spec.origin).startswith(_stdlib_prefix())


def test_round_panel_contract_imports_no_lib_modules():
    """round_panel_contract is a stdlib-only leaf — no lib/ imports."""
    path = os.path.join(_LIB, "round_panel_contract.py")
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=path)
    violations = []
    for root, lineno in _import_roots(tree):
        if root == "relative":
            violations.append("%s:%s: relative import" % (path, lineno))
            continue
        if not _is_stdlib_or_future(root):
            violations.append("%s:%s: %r" % (path, lineno, root))
    assert not violations, "non-stdlib import in round_panel_contract: %s" % violations


def test_payload_contracts_import_closure_is_pinned():
    """Importing payload_contracts loads exactly the pinned lib/ closure."""
    loaded = _import_closure_modules("payload_contracts")
    expected = _PAYLOAD_CONTRACTS_LIB_CLOSURE
    if loaded != expected:
        unexpected = sorted(loaded - expected)
        missing = sorted(expected - loaded)
        pytest.fail(
            "payload_contracts import closure mismatch: unexpected=%r missing=%r"
            % (unexpected, missing)
        )


def test_round_adapters_reexports_are_the_same_objects():
    """round_adapters re-exports payload-contract names as identical objects, not copies."""
    for name in _REEXPORT_NAMES:
        assert hasattr(round_adapters, name), "round_adapters missing %r" % name
        assert hasattr(payload_contracts, name), "payload_contracts missing %r" % name
        assert getattr(round_adapters, name) is getattr(payload_contracts, name), (
            "%r is not the same object on both modules" % name
        )
    round_adapters_path = os.path.join(_LIB, "round_adapters.py")
    payload_contracts_path = os.path.join(_LIB, "payload_contracts.py")
    with open(round_adapters_path) as fh:
        round_text = fh.read()
    with open(payload_contracts_path) as fh:
        payload_text = fh.read()
    assert "member_ids-non-empty-strings" in payload_text
    assert "member_ids-non-empty-strings" not in round_text
