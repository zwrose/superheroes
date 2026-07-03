#!/usr/bin/env python3
"""Resolve review-crew calibration from the unified layout (core.md + hero layer).

The unified layout is canonical after configure (#81). Legacy `.claude/review-profile.md`
remains a migration source only — consumers read core.md + `.claude/superheroes/review-crew.md`
(or their global equivalents in the control-plane project store).
"""
import os
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import core_md          # noqa: E402
import mode_registry    # noqa: E402
import review_store     # noqa: E402
import store_core       # noqa: E402

REVIEW_CREW = "review-crew"


def _repo_root(cwd):
    out = store_core.run_git(cwd, "rev-parse", "--show-toplevel")
    return os.path.realpath(out) if out else os.path.realpath(cwd)


def layer_path(cwd, hero=REVIEW_CREW, root=None):
    """Mode-aware path to a hero layer file, co-located with core.md."""
    return core_md.layer_path(cwd, hero, root)


def _legacy_in_repo(cwd, hero=REVIEW_CREW):
    sub = mode_registry._HERO_LEGACY_INREPO.get(hero)
    if sub is None:
        return None
    return os.path.join(_repo_root(cwd), sub)


def _legacy_global_entry(cwd):
    """Legacy global entry dir when review-profile.md exists there, else None."""
    g = store_core.resolve_global(cwd, review_store.store_root(), heal=False)
    if g is None:
        return None
    legacy = os.path.join(g["dir"], review_store.FILENAMES["profile"])
    return g["dir"] if os.path.isfile(legacy) else None


def _in_repo_path(path, repo):
    try:
        return os.path.realpath(path).startswith(os.path.realpath(repo) + os.sep)
    except OSError:
        return False


def resolve(cwd, root=None, hero=REVIEW_CREW):
    """Resolve unified + legacy calibration locations for review-crew consumers.

    Returns:
      location: in-repo | global | none
      exists: True when unified layer OR legacy profile is present
      layout: unified | legacy | None
      core_path, layer_path, legacy_path (each str or None)
    """
    repo = _repo_root(cwd)
    core_p = core_md.core_path(cwd, root)
    layer_p = layer_path(cwd, hero, root)
    legacy_in = _legacy_in_repo(cwd, hero)

    if os.path.isfile(layer_p):
        loc = mode_registry.IN_REPO if _in_repo_path(layer_p, repo) else mode_registry.GLOBAL
        return {"location": loc, "exists": True, "layout": "unified",
                "core_path": core_p if os.path.isfile(core_p) else None,
                "layer_path": layer_p,
                "legacy_path": legacy_in if legacy_in and os.path.isfile(legacy_in) else None}

    if legacy_in and os.path.isfile(legacy_in):
        return {"location": mode_registry.IN_REPO, "exists": True, "layout": "legacy",
                "core_path": core_p if os.path.isfile(core_p) else None,
                "layer_path": None, "legacy_path": legacy_in}

    legacy_dir = _legacy_global_entry(cwd)
    if legacy_dir:
        legacy_p = os.path.join(legacy_dir, review_store.FILENAMES["profile"])
        return {"location": mode_registry.GLOBAL, "exists": True, "layout": "legacy",
                "core_path": core_p if os.path.isfile(core_p) else None,
                "layer_path": None, "legacy_path": legacy_p}

    return {"location": "none", "exists": False, "layout": None,
            "core_path": core_p if os.path.isfile(core_p) else None,
            "layer_path": None, "legacy_path": None}


def resolve_profile_path(cwd=None, root=None):
    """Hero-specific calibration path: unified layer first, else legacy profile."""
    info = resolve(cwd or os.getcwd(), root=root)
    if info["layer_path"] and os.path.isfile(info["layer_path"]):
        return info["layer_path"]
    if info["legacy_path"] and os.path.isfile(info["legacy_path"]):
        return info["legacy_path"]
    return None


def main(argv):
    import argparse
    import json
    ap = argparse.ArgumentParser(description="unified calibration path resolver")
    ap.add_argument("command", nargs="?", default="resolve", choices=("resolve",))
    ap.add_argument("--root", default=None)
    args = ap.parse_args(argv[1:])
    sys.stdout.write(json.dumps(resolve(os.getcwd(), root=args.root)) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
