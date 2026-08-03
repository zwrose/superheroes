"""Doc↔code census: C7 browser/context/provision refusal tokens in pilot-contract.md."""
import ast
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.realpath(os.path.join(_HERE, ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import pilot_journal  # noqa: E402

_PILOT_CONTRACT = os.path.join(
    os.path.dirname(_LIB), "reference", "pilot-contract.md"
)

_CENSUS_MODULES = (
    "pilot_browser.py",
    "pilot_context.py",
    "pilot_provision.py",
)

_EFFECT_KIND_HEADER = "| Kind | Scope |"
_BROWSER_EFFECT_KINDS = (
    "browser-server-provisioned",
    "browser-server-torn-down",
)


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


def _collect_census_refusal_tokens():
    all_tokens = set()
    for basename in _CENSUS_MODULES:
        path = os.path.join(_LIB, basename)
        tokens = _refusal_constants_from_module(path)
        if not tokens:
            raise RuntimeError(
                "Browser census collected zero REFUSAL_* constants from %s" % path
            )
        all_tokens.update(tokens)
    return all_tokens


def _load_contract():
    with open(_PILOT_CONTRACT, encoding="utf-8") as fh:
        return fh.read()


def _parse_effect_kind_table(doc):
    """Parse effect-kind table into a set of kind strings from the first column."""
    lines = doc.splitlines()
    try:
        start = lines.index(_EFFECT_KIND_HEADER)
    except ValueError:
        raise AssertionError(
            "effect-kind table header not found in pilot-contract.md (file: %s)"
            % _PILOT_CONTRACT
        )
    kinds = set()
    for line in lines[start + 2 :]:
        if not line.startswith("|"):
            break
        kind = line.strip().strip("|").split("|")[0].strip().strip("`")
        kinds.add(kind)
    return kinds


def test_pilot_contract_names_every_refusal_token():
    """axis: every REFUSAL_* constant value in C7 modules is named in pilot-contract.md."""
    if not os.path.isfile(_PILOT_CONTRACT):
        raise AssertionError(
            "pilot-contract.md missing (file: %s)" % _PILOT_CONTRACT
        )
    doc = _load_contract()
    tokens = _collect_census_refusal_tokens()
    missing = [token for token in sorted(tokens) if token not in doc]
    assert missing == [], (
        "pilot-contract.md missing refusal token(s): %s (file: %s)"
        % (", ".join(missing), _PILOT_CONTRACT)
    )


def test_browser_effect_kinds_in_contract():
    """axis: browser-server journal effect kinds appear in the effect-kind table."""
    doc = _load_contract()
    doc_kinds = _parse_effect_kind_table(doc)
    missing = [
        kind for kind in _BROWSER_EFFECT_KINDS if kind not in doc_kinds
    ]
    assert missing == [], (
        "pilot-contract.md missing browser effect kind(s): %s (file: %s)"
        % (", ".join(missing), _PILOT_CONTRACT)
    )
    for kind in _BROWSER_EFFECT_KINDS:
        assert pilot_journal.EFFECT_SCOPE[kind] == "slot", (
            "expected slot scope for %r, got %r"
            % (kind, pilot_journal.EFFECT_SCOPE[kind])
        )
