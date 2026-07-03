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


def _unified_in_repo_layer(cwd, hero=REVIEW_CREW):
    path = os.path.join(_repo_root(cwd), ".claude", "superheroes", hero + ".md")
    return path if os.path.isfile(path) else None


def _unified_global_layer(cwd, hero=REVIEW_CREW, root=None):
    """Direct probe of control-plane config/<hero>.md (matches review_store._unified_global)."""
    path = os.path.join(mode_registry.project_store_dir(cwd, root), "config", hero + ".md")
    return path if os.path.isfile(path) else None


def _core_beside_layer(layer_p, cwd, root):
    """Read-only core.md probe co-located with the layer — no mode_registry side effects."""
    beside = os.path.join(os.path.dirname(layer_p), "core.md")
    if os.path.isfile(beside):
        return beside
    global_core = os.path.join(mode_registry.project_store_dir(cwd, root), "config", "core.md")
    return global_core if os.path.isfile(global_core) else None


def _with_dispatch_fields(out):
    """dispatch_core/dispatch_layer: unified paths when present, else legacy single-file."""
    legacy = out.get("legacy_path")
    layer = out.get("layer_path")
    leg_ok = legacy and os.path.isfile(legacy)
    layer_ok = layer and os.path.isfile(layer)
    out["dispatch_layer"] = layer or (legacy if leg_ok else None)
    out["dispatch_core"] = (
        out.get("core_path")
        or (legacy if leg_ok else None)
        or (layer if layer_ok else None)
    )
    return out


def resolve(cwd, root=None, hero=REVIEW_CREW, legacy_root=None, heal=False):
    """Resolve unified + legacy calibration locations for review-crew consumers.

    Precedence: unified-in-repo → legacy-in-repo → unified-global → legacy-global.
    Returns location, exists, layout, core_path, layer_path, legacy_path, plus
    dispatch_core and dispatch_layer (paths specialists should read — legacy
    single-file fills both when no unified split exists yet). healed/entry_id
    are set only when the legacy-global branch runs (heal controls pointer repair).
    """
    legacy_root = legacy_root or review_store.store_root()
    legacy_in = _legacy_in_repo(cwd, hero)

    layer_p = _unified_in_repo_layer(cwd, hero)
    if layer_p:
        return _with_dispatch_fields({
            "location": mode_registry.IN_REPO, "exists": True, "layout": "unified",
            "core_path": _core_beside_layer(layer_p, cwd, root),
            "layer_path": layer_p,
            "legacy_path": legacy_in if legacy_in and os.path.isfile(legacy_in) else None,
            "healed": False, "entry_id": None,
        })

    if legacy_in and os.path.isfile(legacy_in):
        return _with_dispatch_fields({
            "location": mode_registry.IN_REPO, "exists": True, "layout": "legacy",
            "core_path": None, "layer_path": None, "legacy_path": legacy_in,
            "healed": False, "entry_id": None,
        })

    layer_p = _unified_global_layer(cwd, hero, root)
    if layer_p:
        return _with_dispatch_fields({
            "location": mode_registry.GLOBAL, "exists": True, "layout": "unified",
            "core_path": _core_beside_layer(layer_p, cwd, root),
            "layer_path": layer_p, "legacy_path": None,
            "healed": False, "entry_id": None,
        })

    g = store_core.resolve_global(cwd, legacy_root, heal=heal, _consumer="review_store")
    if g is not None:
        legacy_p = os.path.join(g["dir"], review_store.FILENAMES["profile"])
        if os.path.isfile(legacy_p):
            return _with_dispatch_fields({
                "location": mode_registry.GLOBAL, "exists": True, "layout": "legacy",
                "core_path": None, "layer_path": None, "legacy_path": legacy_p,
                "healed": g["healed"], "entry_id": g["entry_id"],
            })

    return _with_dispatch_fields({
        "location": "none", "exists": False, "layout": None,
        "core_path": None, "layer_path": None, "legacy_path": None,
        "healed": g["healed"] if g else False,
        "entry_id": g["entry_id"] if g else None,
    })


def resolve_profile_path(cwd=None, root=None):
    """Hero-specific calibration path: unified layer first, else legacy profile."""
    info = resolve(cwd or os.getcwd(), root=root)
    return info.get("dispatch_layer") or info.get("legacy_path")


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
