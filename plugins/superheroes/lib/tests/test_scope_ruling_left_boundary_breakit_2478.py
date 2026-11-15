"""A longer file path must not inherit a suffix path's scope ruling."""

import session_contract as sc
import verification


def test_code_refutation_does_not_inherit_a_suffix_paths_ruling():
    # axis: a live key cited whole is marked; the same key embedded after another path component is not.
    root = {"file": "a.py", "line": 3, "title": "Unchecked index", "severity": "Important"}
    nested = dict(root, file="src/a.py")
    root_key = sc.finding_identity_key(root)
    nested_key = sc.finding_identity_key(nested)
    staged = verification.stage_ids([nested])

    exact_reason = f"see {root_key} for why"
    exact = verification.apply_verdicts(
        staged,
        [{"id": "v0", "verdict": "REFUTED", "reason": exact_reason}],
        [root_key],
    )
    assert exact["drops"][0]["grade"]["restsOnRuling"] == {"findingKey": root_key}

    reason = f"The index is checked at {nested_key}."
    result = verification.apply_verdicts(
        staged,
        [{"id": "v0", "verdict": "REFUTED", "reason": reason}],
        [root_key],
    )
    (drop,) = result["drops"]
    assert drop["grade"] == {"verdict": "wrong", "reason": reason}
