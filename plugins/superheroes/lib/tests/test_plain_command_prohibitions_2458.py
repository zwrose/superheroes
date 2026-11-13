"""The plain-command content detector must reject reversed prohibitions."""

import pytest

import test_command_refusals as detector


@pytest.mark.parametrize(
    "original,replacement",
    [
        ("Never chain commands with", "You may chain commands with"),
        ("and never pipe into a loop", "and you may pipe into a loop"),
    ],
    ids=["chaining-permitted", "loop-pipe-permitted"],
)
def test_content_detector_rejects_reversed_prohibitions(monkeypatch, original, replacement):
    # axis: the content detector rejects explicit permission to chain commands or pipe into a loop.
    rule = detector.CR.PLAIN_COMMAND_RULE
    assert rule.count(original) == 1
    monkeypatch.setattr(
        detector.CR, "PLAIN_COMMAND_RULE", rule.replace(original, replacement, 1)
    )
    with pytest.raises(AssertionError):
        detector.test_plain_command_rule_content()
