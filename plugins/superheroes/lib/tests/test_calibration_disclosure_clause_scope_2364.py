"""A disclosure's clauses retain their own seat and file scope (#2364)."""

import calibration_disclosure as cd


def _row(name, core, crew):
    return {
        "name": name,
        "ran": "engine-record",
        "calibrationRead": [
            {
                "label": label,
                "file": file,
                "sha256": None,
                "policyVersion": None,
                "read": state,
            }
            for label, file, state in (
                ("core", "core.md", core),
                ("review-crew", "review-crew.md", crew),
            )
        ],
    }


def _body(claim):
    return (
        "<!-- superheroes:degradations -->\n"
        "### Disclosed degradations\n\n"
        "- [costly] " + claim + "\n"
    )


def _names(record, claim):
    return {
        seat["name"]
        for hit in cd.contradicted(record, _body(claim))
        for seat in hit["seats"]
    }


def test_each_clause_is_checked_against_its_own_seat_and_files():
    # axis: combining two contradicted clauses must still report both seats;
    # an unknown grade for a file named only by the other clause cannot hide either contradiction.
    code = "code-reviewer (round 1)"
    security = "security-reviewer (round 1)"
    record = {
        "ok": True,
        "findings": [],
        "leftForOwner": [],
        "reviewers": [
            _row(code, "read", "unknown"),
            _row(security, "unknown", "read"),
        ],
    }
    first = code + " lacked core.md"
    second = security + " lacked review-crew.md"
    assert _names(record, first) == {code}
    assert _names(record, second) == {security}
    assert _names(record, first + "; " + second) == {code, security}
