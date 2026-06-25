import importlib.util
import os

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load():
    path = os.path.join(_HERE, "..", "loop_readout.py")
    spec = importlib.util.spec_from_file_location("loop_readout", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


LR = _load()


def _record(**kw):
    base = {"schemaVersion": LR.SCHEMA_VERSION, "terminal": "clean", "reason": "all clear"}
    base.update(kw)
    return base


def test_unknown_schema_version_surfaced_not_partial():
    out = LR.render({"schemaVersion": 99, "terminal": "clean"})
    assert "unknown record format" in out.lower()


def test_non_dict_record_is_safe():
    assert "unreadable" in LR.render(None).lower()


def test_names_fixes_drops_and_deferrals():
    out = LR.render(_record(
        terminal="clean-with-skips",
        fixes=["fixed the off-by-one in a.py"],
        deferred=[{"title": "rename var", "reason": "cosmetic"}],
        drops=[{"title": "phantom", "reason": "not in the diff", "was_blocking_tagged": False}]))
    assert "fixed the off-by-one in a.py" in out
    assert "rename var" in out and "cosmetic" in out
    assert "phantom" in out and "not in the diff" in out


def test_dropped_blocker_flagged_distinctly_ufr10():
    out = LR.render(_record(
        drops=[{"title": "real bug", "reason": "stale", "was_blocking_tagged": True},
               {"title": "nit", "reason": "n/a", "was_blocking_tagged": False}]))
    # the blocking-tagged drop is in its own scrutiny section, not the ordinary list
    scrutiny = out.split("tagged BLOCKING")[1]
    assert "real bug" in scrutiny and "nit" not in scrutiny


def test_parent_origin_named_fr21():
    out = LR.render(_record(terminal="halted", parentOrigin="plan"))
    assert "plan" in out and "upstream" in out.lower()


def test_record_missing_warned_ufr9():
    out = LR.render(_record(terminal="halted", recordMissing=True))
    assert "could not be written" in out.lower()


def test_parent_origin_multi_phase_names_every_phase_fr6():
    out = LR.render(_record(terminal="halted", parentOrigin="plan, tasks"))
    assert "plan" in out and "tasks" in out and "upstream" in out.lower()
