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


def test_duplication_lens_registers_cleanly():
    """The duplication lens is on the real roster — loads healthy, no stand-in, no errors."""
    _reset_production_loader()
    try:
        lenses = gl.registered_lenses()
        by_name = {l.name: l for l in lenses}
        assert "duplication" in by_name, sorted(by_name)
        dup = by_name["duplication"]
        # A real lens, not an _UnavailableLens load-failure stand-in.
        assert not isinstance(dup, gl._UnavailableLens)
        assert dup.collector_version == "2.0.0"
        assert not any(l.name == "module:guardian_lens_duplication" for l in lenses)
        errors = gl.production_lens_load_errors()
        assert not any(
            e.get("lens") == "duplication"
            or e.get("module") == "guardian_lens_duplication"
            for e in errors), errors
    finally:
        _reset_production_loader()


def test_classify_collect_collected_happy():
    out = {"candidates": [], "digest": {"v": 1}}
    assert gl.classify_collect(out) == ("collected", None)


def test_classify_collect_partial_happy():
    out = {"candidates": [], "digest": {"v": 1}, "status": "partial", "reason": "half"}
    assert gl.classify_collect(out) == ("partial", "half")


def test_classify_collect_not_collected_happy():
    out = {"status": "not-collected", "reason": "missing tool"}
    assert gl.classify_collect(out) == ("not-collected", "missing tool")


def test_classify_collect_unknown_status_degrades():
    out = {"status": "bogus", "reason": "x"}
    assert gl.classify_collect(out) == (
        "not-collected", "invalid collect status: 'bogus'")


def test_classify_collect_partial_missing_reason_degrades():
    out = {"status": "partial"}
    assert gl.classify_collect(out) == (
        "partial", "partial reported without a reason (contract violation)")


def test_classify_collect_not_collected_missing_reason_degrades():
    out = {"status": "not-collected"}
    assert gl.classify_collect(out) == (
        "not-collected", "not-collected reported without a reason (contract violation)")


def test_classify_collect_non_dict_raises():
    with pytest.raises(gl.MalformedCollect, match="must return a dict"):
        gl.classify_collect([])


def test_classify_collect_collected_non_list_candidates_raises():
    with pytest.raises(gl.MalformedCollect, match="list 'candidates'"):
        gl.classify_collect({"candidates": "nope", "digest": {}})


def test_classify_collect_collected_missing_digest_raises():
    with pytest.raises(gl.MalformedCollect, match="requires a 'digest' key"):
        gl.classify_collect({"candidates": []})


def test_register_rejects_duplicate_name():
    lens_a = FixtureLens(name="dup")
    lens_b = FixtureLens(name="dup")
    gl.REGISTRY.clear()
    gl.register(lens_a)
    with pytest.raises(ValueError, match="duplicate lens name 'dup'"):
        gl.register(lens_b)
    gl.REGISTRY.clear()


def test_register_rejects_module_prefix_name():
    gl.REGISTRY.clear()
    with pytest.raises(ValueError, match="reserved 'module:' prefix"):
        gl.register(FixtureLens(name="module:foo"))
    gl.REGISTRY.clear()


def _reset_production_loader():
    gl.REGISTRY.clear()
    gl._PRODUCTION_LOADED = False
    gl._PRODUCTION_LOAD_ERRORS.clear()
    gl._PRODUCTION_COLLIDED_NAMES.clear()
    gl._PRODUCTION_REGISTERED.clear()
    gl._PRODUCTION_MODULE_LENSES.clear()


def test_loader_import_failure_records_error_and_stand_in(monkeypatch):
    _reset_production_loader()
    monkeypatch.setattr(gl, "PRODUCTION_LENS_MODULES", ("missing_mod_558",))
    monkeypatch.setattr(gl, "PRODUCTION_LENS_NAMES", {
        "missing_mod_558": ("expected-lens",),
    })
    lenses = gl.registered_lenses()
    standin = [l for l in lenses if l.name == "expected-lens"]
    assert len(standin) == 1
    assert isinstance(standin[0], gl._UnavailableLens)
    errors = gl.production_lens_load_errors()
    assert len(errors) == 1
    assert errors[0]["module"] == "missing_mod_558"
    _reset_production_loader()


def test_loader_empty_lenses_records_error_and_stand_in(monkeypatch):
    import sys
    import types
    _reset_production_loader()
    mod = types.ModuleType("empty_lenses_mod_558")
    mod.LENSES = ()
    sys.modules["empty_lenses_mod_558"] = mod
    monkeypatch.setattr(gl, "PRODUCTION_LENS_MODULES", ("empty_lenses_mod_558",))
    monkeypatch.setattr(gl, "PRODUCTION_LENS_NAMES", {
        "empty_lenses_mod_558": ("empty-lens",),
    })
    lenses = gl.registered_lenses()
    standin = [l for l in lenses if l.name == "empty-lens"]
    assert len(standin) == 1
    assert isinstance(standin[0], gl._UnavailableLens)
    assert any(
        e.get("error") == "exposes no module-level LENSES"
        for e in gl.production_lens_load_errors())
    del sys.modules["empty_lenses_mod_558"]
    _reset_production_loader()


def test_loader_missing_expected_name_records_error_and_stand_in(monkeypatch):
    import sys
    import types
    _reset_production_loader()
    mod = types.ModuleType("partial_export_mod_558")
    mod.LENSES = (FixtureLens(name="only-one"),)
    sys.modules["partial_export_mod_558"] = mod
    monkeypatch.setattr(gl, "PRODUCTION_LENS_MODULES", ("partial_export_mod_558",))
    monkeypatch.setattr(gl, "PRODUCTION_LENS_NAMES", {
        "partial_export_mod_558": ("only-one", "missing-expected"),
    })
    lenses = gl.registered_lenses()
    names = {l.name for l in lenses}
    assert "only-one" in names
    assert "missing-expected" in names
    missing = [l for l in lenses if l.name == "missing-expected"]
    assert len(missing) == 1
    assert isinstance(missing[0], gl._UnavailableLens)
    assert any(
        e.get("lens") == "missing-expected"
        for e in gl.production_lens_load_errors())
    del sys.modules["partial_export_mod_558"]
    gl.REGISTRY.clear()
    _reset_production_loader()


def test_loader_duplicate_name_across_modules_records_error(monkeypatch):
    import sys
    import types
    _reset_production_loader()
    mod_a = types.ModuleType("dup_mod_a_558")
    mod_a.LENSES = (FixtureLens(name="shared-name"),)
    mod_b = types.ModuleType("dup_mod_b_558")
    mod_b.LENSES = (FixtureLens(name="shared-name"),)
    sys.modules["dup_mod_a_558"] = mod_a
    sys.modules["dup_mod_b_558"] = mod_b
    monkeypatch.setattr(gl, "PRODUCTION_LENS_MODULES", ("dup_mod_a_558", "dup_mod_b_558"))
    monkeypatch.setattr(gl, "PRODUCTION_LENS_NAMES", {
        "dup_mod_a_558": ("shared-name",),
        "dup_mod_b_558": ("shared-name",),
    })
    lenses = gl.registered_lenses()
    collision_standins = [l for l in lenses if l.name == "shared-name"]
    assert len(collision_standins) == 1
    assert isinstance(collision_standins[0], gl._UnavailableLens)
    assert not any(l.name == "module:dup_mod_b_558" for l in lenses)
    assert any("duplicate lens name" in e.get("error", "")
               for e in gl.production_lens_load_errors())
    del sys.modules["dup_mod_a_558"]
    del sys.modules["dup_mod_b_558"]
    _reset_production_loader()


def test_loader_duplicate_name_degrades_not_first_concrete(monkeypatch):
    import sys
    import types
    _reset_production_loader()
    mod_a = types.ModuleType("dup_lens_mod_a_558")
    mod_a.LENSES = (FixtureLens(name="dup-lens"),)
    mod_b = types.ModuleType("dup_lens_mod_b_558")
    mod_b.LENSES = (FixtureLens(name="dup-lens"),)
    sys.modules["dup_lens_mod_a_558"] = mod_a
    sys.modules["dup_lens_mod_b_558"] = mod_b
    monkeypatch.setattr(
        gl, "PRODUCTION_LENS_MODULES", ("dup_lens_mod_a_558", "dup_lens_mod_b_558"))
    monkeypatch.setattr(gl, "PRODUCTION_LENS_NAMES", {
        "dup_lens_mod_a_558": ("dup-lens",),
        "dup_lens_mod_b_558": ("dup-lens",),
    })
    lenses = gl.registered_lenses()
    collision_standins = [l for l in lenses if l.name == "dup-lens"]
    assert len(collision_standins) == 1
    assert isinstance(collision_standins[0], gl._UnavailableLens)
    assert not isinstance(collision_standins[0], FixtureLens)
    assert not any(l.name == "module:dup_lens_mod_b_558" for l in lenses)
    assert any(
        e.get("lens") == "dup-lens" and "duplicate lens name" in e.get("error", "")
        for e in gl.production_lens_load_errors())
    del sys.modules["dup_lens_mod_a_558"]
    del sys.modules["dup_lens_mod_b_558"]
    _reset_production_loader()


def test_loader_missing_names_mapping_stand_in_and_roster_error(monkeypatch):
    _reset_production_loader()
    monkeypatch.setattr(gl, "PRODUCTION_LENS_MODULES", ("definitely_missing_558",))
    monkeypatch.setattr(gl, "PRODUCTION_LENS_NAMES", {})
    lenses = gl.registered_lenses()
    standins = [l for l in lenses if l.name == "module:definitely_missing_558"]
    assert len(standins) == 1
    assert isinstance(standins[0], gl._UnavailableLens)
    errors = gl.production_lens_load_errors()
    assert any(
        e.get("module") == "definitely_missing_558"
        and "roster misconfiguration" in e.get("error", "")
        for e in errors)
    _reset_production_loader()


def test_loader_force_reload_no_spurious_duplicates(monkeypatch):
    import sys
    import types
    _reset_production_loader()
    mod = types.ModuleType("force_reload_mod_558")
    mod.LENSES = (FixtureLens(name="force-lens"),)
    sys.modules["force_reload_mod_558"] = mod
    monkeypatch.setattr(gl, "PRODUCTION_LENS_MODULES", ("force_reload_mod_558",))
    monkeypatch.setattr(gl, "PRODUCTION_LENS_NAMES", {
        "force_reload_mod_558": ("force-lens",),
    })
    gl.load_production_lenses()
    assert sum(1 for l in gl.REGISTRY if l.name == "force-lens") == 1
    gl.load_production_lenses(force=True)
    assert sum(1 for l in gl.REGISTRY if l.name == "force-lens") == 1
    assert not any(
        "duplicate lens name" in e.get("error", "")
        for e in gl.production_lens_load_errors())
    del sys.modules["force_reload_mod_558"]
    _reset_production_loader()


def test_loader_healthy_multi_lens_module_registers_both(monkeypatch):
    import sys
    import types
    _reset_production_loader()
    mod = types.ModuleType("healthy_mod_558")
    mod.LENSES = (FixtureLens(name="lens-a"), FixtureLens(name="lens-b"))
    sys.modules["healthy_mod_558"] = mod
    monkeypatch.setattr(gl, "PRODUCTION_LENS_MODULES", ("healthy_mod_558",))
    monkeypatch.setattr(gl, "PRODUCTION_LENS_NAMES", {
        "healthy_mod_558": ("lens-a", "lens-b"),
    })
    lenses = gl.registered_lenses()
    assert {l.name for l in lenses} == {"lens-a", "lens-b"}
    assert gl.production_lens_load_errors() == []
    del sys.modules["healthy_mod_558"]
    _reset_production_loader()


def test_loader_unnameable_registration_failure_yields_module_standin(monkeypatch):
    import sys
    import types
    _reset_production_loader()
    mod = types.ModuleType("partial_malformed_mod_558")
    mod.LENSES = (FixtureLens(name="good-lens"), object())
    sys.modules["partial_malformed_mod_558"] = mod
    monkeypatch.setattr(gl, "PRODUCTION_LENS_MODULES", ("partial_malformed_mod_558",))
    monkeypatch.setattr(gl, "PRODUCTION_LENS_NAMES", {
        "partial_malformed_mod_558": ("good-lens",),
    })
    lenses = gl.registered_lenses()
    names = {l.name for l in lenses}
    assert "good-lens" in names
    assert "module:partial_malformed_mod_558" in names
    module_standin = [
        l for l in lenses if l.name == "module:partial_malformed_mod_558"]
    assert len(module_standin) == 1
    assert isinstance(module_standin[0], gl._UnavailableLens)
    del sys.modules["partial_malformed_mod_558"]
    _reset_production_loader()


def test_loader_masked_name_from_other_source_yields_module_standin(monkeypatch):
    _reset_production_loader()
    gl.register(FixtureLens(name="masked-lens"))
    monkeypatch.setattr(gl, "PRODUCTION_LENS_MODULES", ("failing_mod_558",))
    monkeypatch.setattr(gl, "PRODUCTION_LENS_NAMES", {
        "failing_mod_558": ("masked-lens",),
    })
    lenses = gl.registered_lenses()
    masked = [l for l in lenses if l.name == "masked-lens"]
    assert len(masked) == 1
    assert not isinstance(masked[0], gl._UnavailableLens)
    module_standin = [l for l in lenses if l.name == "module:failing_mod_558"]
    assert len(module_standin) == 1
    assert isinstance(module_standin[0], gl._UnavailableLens)
    _reset_production_loader()


def test_loader_falsy_module_yields_unknown_standin(monkeypatch):
    _reset_production_loader()
    monkeypatch.setattr(gl, "PRODUCTION_LENS_MODULES", ("",))
    monkeypatch.setattr(gl, "PRODUCTION_LENS_NAMES", {})
    lenses = gl.registered_lenses()
    standin = [l for l in lenses if l.name == "module:<unknown>"]
    assert len(standin) == 1
    assert isinstance(standin[0], gl._UnavailableLens)
    assert gl.production_lens_load_errors()
    _reset_production_loader()


def test_loader_force_reload_preserves_externally_registered_replacement(monkeypatch):
    import sys
    import types
    _reset_production_loader()
    mod = types.ModuleType("replaceable_mod_558")
    loader_lens = FixtureLens(name="replaceable-lens")
    mod.LENSES = (loader_lens,)
    sys.modules["replaceable_mod_558"] = mod
    monkeypatch.setattr(gl, "PRODUCTION_LENS_MODULES", ("replaceable_mod_558",))
    monkeypatch.setattr(gl, "PRODUCTION_LENS_NAMES", {
        "replaceable_mod_558": ("replaceable-lens",),
    })
    gl.load_production_lenses()
    assert gl.REGISTRY[0] is loader_lens
    gl.REGISTRY.clear()
    external = FixtureLens(name="replaceable-lens")
    gl.register(external)
    gl.load_production_lenses(force=True)
    assert len(gl.REGISTRY) == 1
    assert gl.REGISTRY[0] is external
    del sys.modules["replaceable_mod_558"]
    _reset_production_loader()

