"""Ruling attribution respects both boundaries of a finding key."""

import session_contract
import verification


def test_code_refutation_at_a_longer_path_does_not_inherit_a_suffix_ruling():
    # axis: a different finding key with a longer path must not inherit a live ruling whose key is its suffix; naming the actual ruling still attributes it.
    earlier = {
        "file": "a.py",
        "line": 3,
        "title": "Unchecked index",
        "severity": "Important",
    }
    current = dict(earlier, file="src/a.py")
    ruled_key = session_contract.finding_identity_key(earlier)
    current_key = session_contract.finding_identity_key(current)
    reason = f"The check at {current_key} rejects the triggering index."
    staged = verification.stage_ids([current])
    result = verification.apply_verdicts(
        staged,
        [{"id": staged[0]["id"], "verdict": "REFUTED", "reason": reason}],
        [ruled_key],
    )
    (drop,) = result["drops"]
    assert drop["grade"] == {"verdict": "wrong", "reason": reason}

    named_reason = f"{ruled_key} excludes this finding."
    named = verification.apply_verdicts(
        staged,
        [{"id": staged[0]["id"], "verdict": "REFUTED", "reason": named_reason}],
        [ruled_key],
    )
    assert named["drops"][0]["grade"]["restsOnRuling"] == {
        "findingKey": ruled_key
    }
