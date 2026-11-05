"""An unrelated test runner does not select the test review seat (#2364)."""

import pytest

import calibration_disclosure as cd


def _row(name, state):
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
            for label, file in (
                ("core", "core.md"),
                ("review-crew", "review-crew.md"),
                ("CLAUDE.md", "CLAUDE.md"),
            )
        ],
    }


def _names(record, text):
    body = (
        "<!-- superheroes:degradations -->\n"
        "### Disclosed degradations\n\n"
        "- [costly] " + text + "\n"
    )
    return [
        seat["name"]
        for hit in cd.contradicted(record, body)
        for seat in hit["seats"]
    ]


@pytest.mark.parametrize("text", [
    "Calibration was stripped from the reviewers. The integration test runner was unavailable.",
    "Calibration was stripped from the reviewers because the integration test runner was unavailable.",
])
def test_runner_mention_does_not_narrow_a_calibration_claim(text):
    # axis: an unrelated test-runner noun cannot scope a calibration claim to the test-role row;
    # a code row graded read must remain a contradiction when the test row is unknown.
    code = "code-reviewer (round 1)"
    record = {
        "ok": True,
        "reviewers": [
            _row(code, "read"),
            _row("test-role (round 1)", "unknown"),
        ],
    }
    assert _names(record, "Calibration was stripped from the reviewers.") == [code]
    assert _names(record, text) == [code]
