import importlib.util, json, os
_HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name):
    path = os.path.join(_HERE, "..", name + ".py")
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RD = _load("record_deferred")


def test_records_deferred_set_and_extras(tmp_path):
    report = {"fixed": ["fixed a.py off-by-one"],
              "deferred": [{"id": "a.py::bug", "severity": "Important", "parentOrigin": "plan"},
                           {"id": "b.py::x", "severity": "Critical", "parentOrigin": "tasks"}]}
    RD.record(str(tmp_path), report)
    assert json.loads((tmp_path / "deferred-set.json").read_text()) == {
        "a.py::bug": "Important", "b.py::x": "Critical"}
    extras = json.loads((tmp_path / "extras.json").read_text())
    assert extras["fixes"] == ["fixed a.py off-by-one"]
    phases = extras["parentOrigin"].split(", ")
    assert sorted(phases) == ["plan", "tasks"]  # FR-6: every distinct phase named


def test_parent_origin_merges_cumulatively_and_dedupes(tmp_path):
    RD.record(str(tmp_path), {"deferred": [{"id": "a::b", "severity": "Important", "parentOrigin": "plan"}]})
    RD.record(str(tmp_path), {"deferred": [{"id": "a::b", "severity": "Important", "parentOrigin": "plan"},
                                            {"id": "c::d", "severity": "Important", "parentOrigin": "build"}]})
    extras = json.loads((tmp_path / "extras.json").read_text())
    assert sorted(extras["parentOrigin"].split(", ")) == ["build", "plan"]  # run-scoped, deduped


def test_no_parent_origin_omits_key_and_is_failsafe(tmp_path):
    RD.record(str(tmp_path), {"fixed": [], "deferred": [{"id": "x::y", "severity": "Important"}]})
    extras = json.loads((tmp_path / "extras.json").read_text())
    assert "parentOrigin" not in extras
    assert RD.record(str(tmp_path), "not a dict")["ok"] is True  # never raises
