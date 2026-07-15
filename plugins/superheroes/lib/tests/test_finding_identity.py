import importlib.util, os

LIB = os.path.join(os.path.dirname(__file__), "..")


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(LIB, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_identity_is_file_plus_normalized_clamped_title():
    fi = _load("finding_identity")
    got = fi.finding_identity({"file": "plan.md", "title": "Unauthenticated Access Path!!"})
    assert got == "plan.md::unauthenticated access path"


def test_identity_prefers_title_then_summary_then_empty():
    fi = _load("finding_identity")
    assert fi.finding_identity({"summary": "Data loss on retry"}) == "::data loss on retry"
    assert fi.finding_identity({}) == "::"


def test_circuit_breaker_delegates_to_shared_home():
    fi = _load("finding_identity")
    cb = _load("circuit_breaker")
    f = {"file": "plan.md", "title": "Some Finding — with dashes"}
    assert cb.finding_identity(f) == fi.finding_identity(f)
