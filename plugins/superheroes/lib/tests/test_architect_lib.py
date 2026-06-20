"""Tests for review-crew's cross-plugin resolver (`architect_lib`).

It must locate the-architect's `definition_doc.py` both **in-repo** (monorepo /
dogfooding) and as an **installed marketplace sibling**, prefer in-repo, prefer the
highest installed version, and **fail closed** (None / exit 1) when neither resolves —
the gate-write degrade-not-crash contract depends on this (CONVENTIONS §7).
"""
import importlib.util
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.join(_HERE, "..", "architect_lib.py")
_REPO_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", "..", ".."))


def _load():
    spec = importlib.util.spec_from_file_location("architect_lib", _LIB)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


AL = _load()
_SUFFIX = os.path.join("plugins", "the-architect", "lib", "definition_doc.py")


def test_resolves_in_repo():
    p = AL.resolve(root=_REPO_ROOT)
    assert p and p.endswith(_SUFFIX) and os.path.isfile(p)


def _fake_cache(tmp_path, versions):
    """Build .../<marketplace>/{review-crew/<v>, the-architect/<v>/lib/definition_doc.py}
    and return the review-crew plugin root (the `$CLAUDE_PLUGIN_ROOT` analogue)."""
    mk = tmp_path / "cache" / "zwr-agent-skills"
    plugin_root = mk / "review-crew" / "0.3.0"
    plugin_root.mkdir(parents=True)
    for v in versions:
        d = mk / "the-architect" / v / "lib"
        d.mkdir(parents=True)
        (d / "definition_doc.py").write_text("# fake\n", encoding="utf-8")
    return str(plugin_root)


def test_resolves_installed_sibling(tmp_path):
    plugin_root = _fake_cache(tmp_path, ["0.2.0"])
    p = AL.resolve(root=None, plugin_root=plugin_root)
    assert p and p.endswith(os.path.join("the-architect", "0.2.0", "lib", "definition_doc.py"))


def test_prefers_highest_installed_version(tmp_path):
    # 0.10.0 must beat 0.9.0 — numeric, not lexicographic.
    plugin_root = _fake_cache(tmp_path, ["0.2.0", "0.10.0", "0.9.0"])
    p = AL.resolve(root=None, plugin_root=plugin_root)
    assert p.endswith(os.path.join("the-architect", "0.10.0", "lib", "definition_doc.py")), p


def test_non_numeric_version_does_not_crash(tmp_path):
    # `0.10.0` vs `0.10.x` differ at the SAME index with a numeric-vs-non-numeric segment,
    # so the comparison actually reaches the int-vs-str case _version_key guards. Without
    # the (0,int)/(1,str) tag this raises TypeError — so this kills a tag-removal mutant
    # (whereas a shared-prefix fixture would route around it). Exact ordering of the odd
    # version is not a contract; we only assert no-crash + a valid resolved path.
    plugin_root = _fake_cache(tmp_path, ["0.10.0", "0.10.x"])
    p = AL.resolve(root=None, plugin_root=plugin_root)
    assert p and p.endswith(os.path.join("lib", "definition_doc.py")) and os.path.isfile(p)


def test_in_repo_precedence_over_sibling(tmp_path):
    plugin_root = _fake_cache(tmp_path, ["9.9.9"])
    p = AL.resolve(root=_REPO_ROOT, plugin_root=plugin_root)
    assert p.endswith(_SUFFIX)  # in-repo wins over an installed sibling


def test_fails_closed_when_absent(tmp_path):
    assert AL.resolve(root=str(tmp_path), plugin_root=str(tmp_path)) is None


def test_cli_resolves_in_repo_and_fails_closed(tmp_path, capsys):
    assert AL.main(["architect_lib.py", "--root", _REPO_ROOT]) == 0
    assert capsys.readouterr().out.strip().endswith(_SUFFIX)
    assert AL.main(["architect_lib.py", "--root", str(tmp_path), "--plugin-root", str(tmp_path)]) == 1


def test_resolves_escalation_lib_in_repo():
    p = AL.resolve_target(("the-architect", "lib", "escalation.py"), root=_REPO_ROOT)
    assert p and p.endswith(os.path.join("the-architect", "lib", "escalation.py")) and os.path.isfile(p)

def test_resolves_escalation_rubric_in_repo():
    p = AL.resolve_target(("the-architect", "rubric", "escalation-base.md"), root=_REPO_ROOT)
    assert p and p.endswith(os.path.join("the-architect", "rubric", "escalation-base.md")) and os.path.isfile(p)

def test_default_resolve_still_targets_definition_doc():
    # back-compat: the existing resolve() keeps resolving definition_doc.py
    p = AL.resolve(root=_REPO_ROOT)
    assert p and p.endswith(os.path.join("the-architect", "lib", "definition_doc.py"))

def test_resolve_target_fails_closed_when_absent(tmp_path):
    assert AL.resolve_target(("the-architect", "lib", "escalation.py"),
                             root=str(tmp_path), plugin_root=str(tmp_path)) is None
