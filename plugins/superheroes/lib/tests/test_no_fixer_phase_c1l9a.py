"""The build session applies the fixes itself (C1-L9a): the fixer phase and what served it are gone.

A1 `round_phases` has no `P_FIXER` and no phase spelled `dispatch-fixer`.
A2 the fixer order template does not exist.
A3 `order_lint` takes one kind, `implementer`.
A4 `payload_contracts` has no `dispatch-fixer` contract, and its `apply-fixes` contract drops `escalated` and `refusals`.
A5 `round_orders.ORDER_PHASES` holds no fixer phase and the driver renders no fixer order.
A6 the string `dispatch-fixer` stands in no non-test file of the plugin beyond a measured allowlist, matched by path and
   count (an in-flight session carrying that step is moved to `apply-fixes`: `test_fix_step_migration_c1l9a.py`).

Bite-proof record: plugins/superheroes/lib/tests/bite_proofs/c1l9a_wo4a_migration.md
"""
import os

import order_lint
import payload_contracts
import round_adapters
import round_driver
import round_orders
import round_phases
from test_round_orders import _base_context

_PLUGIN_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_RETIRED = "dispatch-fixer"

# Measured: `grep -rn 'dispatch-fixer' plugins/superheroes --include=*.py --include=*.md --include=*.json | grep -v /tests/`.
# A path with `None` may hold any number of the string; the others hold exactly the count given.
_ALLOWED = {
    "CHANGELOG.md": None,
    "TRANSITION.md": None,
    os.path.join("skills", "review-code", "reference", "round-driver.md"): 2,
    os.path.join("lib", "round_driver.py"): 1,
}


def test_a1_round_phases_has_no_fixer_phase():
    assert not hasattr(round_phases, "P_FIXER")
    assert _RETIRED not in round_phases.ALL_PHASES
    assert _RETIRED not in [v for v in vars(round_phases).values() if isinstance(v, str)]
    assert round_phases.P_APPLY_FIXES == "apply-fixes" and round_phases.P_APPLY_FIXES in round_phases.ALL_PHASES
    assert not hasattr(round_driver, "P_FIXER")


def test_a2_the_fixer_order_template_does_not_exist():
    assert not os.path.exists(os.path.join(_PLUGIN_ROOT, "rubric", "orders", _RETIRED + ".md"))
    text, reason = round_orders.render_order(_RETIRED, "fixer", _base_context())
    assert text is None and reason == "no-template:%s" % _RETIRED


def test_a3_order_lint_takes_the_implementer_kind_alone():
    assert order_lint.KINDS == ("implementer",)
    assert not hasattr(order_lint, "TOKEN_RESULT_SHAPE_AUTHORED")
    assert order_lint.TOKEN_RESULT_SHAPE_AMBIGUOUS in order_lint.TOKENS


def test_a4_payload_contracts_has_no_fixer_contract_and_apply_fixes_drops_two_keys():
    contract, reason = round_adapters.payload_contract(_RETIRED)
    assert contract == {} and reason == "unknown-phase:%s" % _RETIRED
    assert _RETIRED not in payload_contracts.ADAPTER_PHASES
    assert _RETIRED not in payload_contracts._PAYLOAD_CHECKERS
    assert _RETIRED not in payload_contracts._PAYLOAD_FIELD_BINDINGS
    assert not hasattr(payload_contracts, "P_FIXER") and not hasattr(payload_contracts, "SEAT_FIXER")
    contract, reason = round_adapters.payload_contract(round_phases.P_APPLY_FIXES)
    assert reason is None, reason
    assert contract["required"] == ["fixes"]
    assert contract["optional"] == ["unfixed", "coverageDecisions", "headDiff", "headDiffPath"]
    assert "escalated" not in contract["types"] and "refusals" not in contract["types"]


def test_a5_round_orders_has_no_fixer_phase():
    assert not [p for p in round_orders.ORDER_PHASES if "fixer" in p]
    assert _RETIRED not in round_orders.ORDER_PHASES
    assert round_phases.P_APPLY_FIXES not in round_orders.ORDER_PHASES
    assert round_phases.P_APPLY_FIXES in round_adapters.ORCHESTRATOR_FULFILLED_PHASES
    assert not hasattr(round_orders, "FIXER_SEAT_RULE") and not hasattr(round_orders, "FIXER_NO_HEAD_DIFF_RULE")


def _non_test_files():
    for root, dirs, files in os.walk(_PLUGIN_ROOT):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git", "tests")]
        for name in files:
            if name.endswith((".py", ".md", ".json")):
                yield os.path.join(root, name)


def test_a6_the_retired_phase_name_stands_only_where_the_allowlist_says():
    found = {}
    for path in _non_test_files():
        with open(path, encoding="utf-8", errors="replace") as fh:
            count = fh.read().count(_RETIRED)
        if count:
            found[os.path.relpath(path, _PLUGIN_ROOT)] = count
    stray = sorted(rel for rel in found if rel not in _ALLOWED)
    assert not stray, "the retired phase name stands in %s" % stray
    for rel, want in _ALLOWED.items():
        if want is not None:
            assert found.get(rel) == want, "%s holds %s of the retired name, the allowlist says %s" % (
                rel, found.get(rel), want)
