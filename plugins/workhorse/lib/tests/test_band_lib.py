import os
import band_lib


def test_resolves_in_repo_target_first(tmp_path):
    # in-repo: <root>/plugins/the-architect/lib/escalation.py
    target = ("the-architect", "lib", "escalation.py")
    p = tmp_path / "plugins" / "the-architect" / "lib"
    p.mkdir(parents=True)
    f = p / "escalation.py"
    f.write_text("# stub\n")
    got = band_lib.resolve_target(target, root=str(tmp_path))
    assert got == os.path.abspath(str(f))


def test_resolves_installed_cache_highest_version(tmp_path):
    # marketplace cache: <marketplace>/the-architect/<ver>/lib/escalation.py
    target = ("the-architect", "lib", "escalation.py")
    marketplace = tmp_path / "cache" / "superheroes"
    for ver in ("0.9.0", "0.10.0"):
        d = marketplace / "the-architect" / ver / "lib"
        d.mkdir(parents=True)
        (d / "escalation.py").write_text(f"# {ver}\n")
    # plugin_root is <marketplace>/workhorse/<ver> => two levels under marketplace
    plugin_root = str(marketplace / "workhorse" / "0.1.0")
    got = band_lib.resolve_target(target, root=None, plugin_root=plugin_root)
    assert got.endswith("the-architect/0.10.0/lib/escalation.py")  # 0.10 > 0.9 numerically


def test_unresolvable_returns_none(tmp_path):
    got = band_lib.resolve_target(("nope", "lib", "x.py"), root=str(tmp_path))
    assert got is None


def test_empty_or_malformed_target_returns_none(tmp_path):
    # fail-closed must be TOTAL: a malformed target returns None, never raises —
    # even on the marketplace branch (plugin_root set, root unset).
    plugin_root = str(tmp_path / "cache" / "superheroes" / "workhorse" / "0.1.0")
    assert band_lib.resolve_target((), root=None, plugin_root=plugin_root) is None
    assert band_lib.resolve_target(None, root=str(tmp_path)) is None
    assert band_lib.resolve_target("not-a-tuple", root=None, plugin_root=plugin_root) is None
