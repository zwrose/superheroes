import pytest

import guardian_lens as gl
from guardian_fixtures import FixtureLens


def test_lens_contract_constants():
    assert gl.LENS_CONTRACT_PARTS == (
        "collector", "baseline-diff", "validation", "consequence", "cost")
    assert gl.FINDING_STATES == (
        "candidate", "surfaced", "triaged-out", "filed", "accepted", "declined",
        "verified-fixed", "reopened")
    assert gl.RED_LINE_THRESHOLDS == {"complexity": 100, "cloneLines": 100}
    assert gl.RED_LINE_KINDS == (
        "critical-vuln", "new-high-complexity", "large-fresh-clone")
    assert gl.FACTS == ("verify-command", "recorded-coverage", "stack-tags", "paths")


def test_validate_lens_passes_fixture():
    ok, reasons = gl.validate_lens(FixtureLens())
    assert ok is True
    assert reasons == []


@pytest.mark.parametrize("gap,attr", [
    ("name", "name"),
    ("collector_version", "collector_version"),
    ("cost", "cost"),
    ("required_facts", "required_facts"),
    ("validation_guidance", "validation_guidance"),
    ("consequence_template", "consequence_template"),
])
def test_validate_lens_fails_closed_on_missing_attr(gap, attr):
    lens = FixtureLens()
    if attr == "cost":
        setattr(lens, attr, "not-a-dict")
    elif attr == "required_facts":
        setattr(lens, attr, ("bogus-fact",))
    else:
        setattr(lens, attr, "")
    ok, reasons = gl.validate_lens(lens)
    assert ok is False
    assert reasons


def test_validate_lens_fails_on_missing_method():
    class BadLens(FixtureLens):
        collect = None
    ok, reasons = gl.validate_lens(BadLens())
    assert ok is False
    assert any("collect" in r for r in reasons)


def test_register_raises_on_invalid():
    lens = FixtureLens()
    lens.name = ""
    with pytest.raises(ValueError):
        gl.register(lens)


def test_registry_empty():
    assert gl.REGISTRY == []
    assert gl.registered_lenses() == []
