"""Test-only git double for the round driver's post-fix head-diff derivation (#1419 part i).

In production the driver derives the diff a panel reviews from git at the fold head, and a
session that cannot derive parks — there is no fallback. The suite's fixtures, though, fold fixers
with synthetic head-diff strings and usually no pinned base or real repository. This double stands
in for git in those tests: when a fold runs with no explicit derivation seam, "git" answers with
the diff the fixture supplied. It lives in test code only.

Opt out with ``@pytest.mark.real_git_head_diff`` (module-level ``pytestmark`` works too): the
stale-diff, derivation and bite-proof tests run with the double OFF, against real temporary git
repositories.
"""
import os
import sys
import types

MARKER = "real_git_head_diff"
_DOUBLE_ATTR = "_head_diff_double_installed"


def _is_round_driver(module):
    path = getattr(module, "__file__", None) or ""
    return (isinstance(module, types.ModuleType)
            and os.path.basename(path) == "round_driver.py"
            and hasattr(module, "_fold_fixer"))


_SCAN_CACHE = {"key": None, "found": ()}


def round_driver_copies(extra=()):
    """Every loaded copy of round_driver: the imported one and the ones test modules loaded by
    file spec (held in their globals). The scan is cached while the set of loaded modules (and the
    requesting test module) is unchanged, so it does not walk every module for every test."""
    key = (len(sys.modules), tuple(id(m) for m in extra))
    if _SCAN_CACHE["key"] == key:
        return list(_SCAN_CACHE["found"])
    found = {}
    roots = [m for m in list(sys.modules.values()) + list(extra) if m is not None]
    # Test modules load their own copies by file spec, sometimes inside another spec-loaded test
    # module; look one module level down as well.
    root_ids = {id(m) for m in roots}
    nested = [v for m in roots for v in list(getattr(m, "__dict__", {}).values())
              if isinstance(v, types.ModuleType) and id(v) not in root_ids]
    for module in roots + nested:
        if _is_round_driver(module):
            found[id(module)] = module
        for value in list(getattr(module, "__dict__", {}).values()):
            if _is_round_driver(value):
                found[id(value)] = value
    _SCAN_CACHE["key"], _SCAN_CACHE["found"] = key, tuple(found.values())
    return list(found.values())


def _wrap(original, module):
    def fold_fixer(state, config, artifact, changed_subjects_seam=None, session_dir=None,
                   head_diff_seam=None):
        if head_diff_seam is None:
            supplied, _source = module._resolve_head_diff(
                artifact if isinstance(artifact, dict) else {})
            head_diff_seam = lambda _state: supplied  # noqa: E731
        return original(state, config, artifact, changed_subjects_seam, session_dir=session_dir,
                        head_diff_seam=head_diff_seam)
    setattr(fold_fixer, _DOUBLE_ATTR, True)
    return fold_fixer


def install(monkeypatch, extra=()):
    """Install the double on every loaded round_driver copy (undone by monkeypatch)."""
    for module in round_driver_copies(extra):
        if getattr(module._fold_fixer, _DOUBLE_ATTR, False):
            continue
        monkeypatch.setattr(module, "_fold_fixer", _wrap(module._fold_fixer, module))


def installed(module):
    return bool(getattr(module._fold_fixer, _DOUBLE_ATTR, False))
