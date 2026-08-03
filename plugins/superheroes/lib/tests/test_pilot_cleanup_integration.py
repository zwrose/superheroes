"""Integration exercise for C9 resurrection — skipped until B4/B6/C7 land."""
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.realpath(os.path.join(_HERE, ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import pilot_cleanup as pc  # noqa: E402
import pilot_contract  # noqa: E402
import pilot_provision as pp  # noqa: E402

pytestmark = pytest.mark.skip(
    reason="C9 integration exercise: requires B4 (#826) capture artifacts, B6 (#828) mint client, "
           "and C7 (#829) browser-context creation + generation bump. Sequenced after those land "
           "per issue #831; the unit path against A1 fixtures runs in test_pilot_cleanup.py."
)


def test_resurrection_end_to_end(
    private_tmp,
    live_browser_context,
    capture_artifact,
    generation_broker,
):
    """Full resurrection: containment receipt, boundary verdict, reseed, generation bump, resume."""
    policy = live_browser_context["policy"]
    pilot_block = live_browser_context["pilot_block"]
    slot_ref = live_browser_context["slot_ref"]
    reach_roots = live_browser_context["reach_roots"]
    run_cwd = live_browser_context["run_cwd"]
    cleanup_root = live_browser_context["cleanup_root"]
    journal_path = os.path.join(private_tmp, "journal.jsonl")

    receipt = pc.cleanup_effect_receipt(
        policy,
        pilot_block,
        slot_ref,
        reach_roots=reach_roots,
        run_cwd=run_cwd,
        cleanup_root=cleanup_root,
        journal_path=journal_path,
        now=live_browser_context["now"],
        observed_identity=live_browser_context["observed_identity"],
        identity_provenance=live_browser_context["identity_provenance"],
        identity_strength=live_browser_context["identity_strength"],
    )
    assert receipt["result"] == pc.RESULT_PASS

    registry = {
        "schemaVersion": 1,
        "records": [
            {
                "kind": "effects-escape",
                "declarationDigest": pilot_contract.declaration_digest(
                    pilot_block["effectsEscape"]
                ),
                "exercisedAt": live_browser_context["now"],
                "receipt": {"result": "pass", "evidence": "effects do not escape"},
            },
            pc.registry_record(receipt, pilot_block["cleanup"]),
        ],
    }

    containment = pc.resolve_containment(
        policy,
        pilot_block,
        slot_ref,
        receipt=receipt,
        cleanup_root=cleanup_root,
        run_cwd=run_cwd,
        observed_identity=live_browser_context["observed_identity"],
        identity_provenance=live_browser_context["identity_provenance"],
        identity_strength=live_browser_context["identity_strength"],
    )
    assert containment["mode"] == pc.MODE_RECEIPT

    verdict = pp.verify_boundary(
        policy,
        slot_ref,
        live_browser_context["candidate_target"],
        reach_roots=reach_roots,
        run_cwd=run_cwd,
    )
    assert verdict["result"] == "pass"

    plan = pc.resurrection_plan(
        policy,
        pilot_block,
        slot_ref,
        registry=registry,
        containment=containment,
        journal_path=journal_path,
        verdict=verdict,
        account=capture_artifact["account"],
        artifact=capture_artifact["artifact"],
        now=live_browser_context["now"],
    )
    assert plan["action"] == pc.ACTION_RESURRECT

    generation_broker.execute_plan(plan, journal_path=journal_path)

    assert pilot_contract.is_exercised(registry, "cleanup-containment", pilot_block["cleanup"])
