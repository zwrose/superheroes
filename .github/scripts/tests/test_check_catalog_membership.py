import importlib.util, os, subprocess, sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_M = os.path.join(_HERE, "..", "check_catalog_membership.py")
_spec = importlib.util.spec_from_file_location("check_catalog_membership", _M)
CM = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(CM)


def _cat(names, version):
    return {"metadata": {"version": version}, "plugins": [{"name": n} for n in names]}


def test_no_membership_change_passes():
    assert CM.compare_membership(_cat(["a", "b"], "0.4.0"), _cat(["a", "b"], "0.4.0")) == []

def test_reordered_same_set_passes():
    assert CM.compare_membership(_cat(["a", "b"], "0.4.0"), _cat(["b", "a"], "0.4.0")) == []

def test_add_without_bump_fails():
    assert CM.compare_membership(_cat(["a"], "0.4.0"), _cat(["a", "b"], "0.4.0")) != []

def test_add_with_bump_passes():
    assert CM.compare_membership(_cat(["a"], "0.4.0"), _cat(["a", "b"], "0.5.0")) == []

def test_remove_without_bump_fails():
    assert CM.compare_membership(_cat(["a", "b"], "0.4.0"), _cat(["a"], "0.4.0")) != []

def test_rename_same_cardinality_without_bump_fails():
    # add+remove in one change (same count, different set) must still be caught (FR-8)
    assert CM.compare_membership(_cat(["a", "b"], "0.4.0"), _cat(["a", "c"], "0.4.0")) != []

def test_fails_closed_on_unresolvable_base():
    # A base ref that cannot exist must NOT pass silently (plan R4). Run from repo root
    # (as CI does) so the head catalog reads successfully and only the base fails.
    repo_root = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
    r = subprocess.run(
        [sys.executable, _M, "definitely-not-a-ref-zzzzzz"],
        capture_output=True, text=True, cwd=repo_root,
    )
    assert r.returncode == 1
    assert "failing closed" in r.stderr
