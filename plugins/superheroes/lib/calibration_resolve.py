#!/usr/bin/env python3
"""Resolve review-crew calibration from the unified layout (core.md + hero layer).

The unified layout is canonical after configure (#81). Legacy `.claude/review-profile.md` is
no longer a migration source; it remains resolvable as a calibration path, and its presence
produces the legacy-profile-unsupported refusal from core_md.resolve_shared. Consumers read
core.md + `.claude/superheroes/review-crew.md` (or their global equivalents in the
control-plane project store). The layer and the dispatch core follow the storage mode.
"""
import os
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import calibration_paths  # noqa: E402
import core_md          # noqa: E402
import mode_registry    # noqa: E402
import review_store     # noqa: E402
import store_core       # noqa: E402

REVIEW_CREW = "review-crew"

REFUSAL_UNRESOLVABLE_ROOT = "unresolvable-root"

REASON_UNRESOLVABLE_ROOT = "root-unresolvable-project-calibrated-elsewhere"

_REMEDY_UNRESOLVABLE_ROOT = (
    "--root is the control-plane STORE root, not the repository root; "
    "omit --root to resolve calibration for this project."
)


class UnresolvableRootError(Exception):
    def __init__(self, root, cwd, hero, default_location, default_layer_path):
        self.root = root
        self.cwd = cwd
        self.hero = hero
        self.reason = REASON_UNRESOLVABLE_ROOT
        self.default_location = default_location
        self.default_layer_path = default_layer_path
        super().__init__(self.reason)

    def __str__(self):
        return f"{self.reason}: {self.root}"

    def payload(self):
        return {
            "action": "refused",
            "refusal": REFUSAL_UNRESOLVABLE_ROOT,
            "reason": self.reason,
            "root": self.root,
            "cwd": self.cwd,
            "hero": self.hero,
            "default_location": self.default_location,
            "default_layer_path": self.default_layer_path,
            "remedy": _REMEDY_UNRESOLVABLE_ROOT,
        }


def _repo_root(cwd):
    return store_core.repo_root(cwd)


def layer_path(cwd, hero=REVIEW_CREW, root=None):
    """Mode-aware path to a hero layer file, co-located with core.md."""
    return core_md.layer_path(cwd, hero, root)


def _legacy_in_repo(cwd, hero=REVIEW_CREW):
    sub = mode_registry._HERO_LEGACY_INREPO.get(hero)
    if sub is None:
        return None
    return os.path.join(_repo_root(cwd), sub)


def _unified_in_repo_layer_path(cwd, hero=REVIEW_CREW):
    return os.path.join(_repo_root(cwd), ".claude", "superheroes", hero + ".md")


def _unified_in_repo_layer(cwd, hero=REVIEW_CREW):
    path = _unified_in_repo_layer_path(cwd, hero)
    return path if os.path.isfile(path) else None


def _unified_global_layer_path(cwd, hero=REVIEW_CREW, root=None):
    """Path to control-plane config/<hero>.md (matches review_store._unified_global)."""
    return os.path.join(mode_registry.project_store_dir(cwd, root), "config", hero + ".md")


def _unified_global_layer(cwd, hero=REVIEW_CREW, root=None):
    path = _unified_global_layer_path(cwd, hero, root)
    return path if os.path.isfile(path) else None


def _legacy_global_profile_path(cwd, legacy_root=None):
    legacy_root = legacy_root or review_store.store_root()
    g = store_core.resolve_global(cwd, legacy_root, heal=False, _consumer="review_store")
    if g is not None:
        return os.path.join(g["dir"], review_store.FILENAMES["profile"])
    ident = store_core.derive_identifiers(cwd)
    return os.path.join(
        legacy_root, calibration_paths.LEGACY_STORE_ENTRIES_DIRNAME, ident["gitdir_hash"], review_store.FILENAMES["profile"])


def regular_core(cwd, root=None):
    """The regular-file core.md the dispatch reads, or None. Writes nothing; never raises.

    When both candidates are present, the one the storage mode picks; when exactly one is, that one. The
    pick is returned only when it is a regular file: a picked core.md that is a directory or a dangling
    link gives None, never its peer, so a broken active core is not replaced by a stale copy."""
    # axis: dispatch_core is the present core.md the storage mode picks, and only when it is a regular file
    try:
        in_repo, global_path = core_md._core_candidates(cwd, root)
        in_present, global_present = os.path.lexists(in_repo), os.path.lexists(global_path)
        if in_present and global_present:
            picked = mode_registry.resolve(cwd, root, persist_backfill=False)["mode"]
            chosen = in_repo if picked == mode_registry.IN_REPO else global_path
        elif in_present:
            chosen = in_repo
        elif global_present:
            chosen = global_path
        else:
            return None
        return chosen if os.path.isfile(chosen) else None
    except Exception:
        return None


def _mode_layer(cwd, hero, root):
    """The layer file configure writes (core_md.layer_path) when it is a regular file, else None. Writes nothing."""
    try:
        path = core_md.layer_path(cwd, hero, root, persist_backfill=False)
        return path if os.path.isfile(path) else None
    except Exception:
        return None


def candidate_profile_paths(cwd, hero=REVIEW_CREW, root=None):
    """The ordered profile-source candidates resolve() considers, EXISTING OR NOT.

    The layer the storage mode picks (when it is a file) comes first, except that a present candidate
    that is not a regular file and that today's order ranks ahead of it stays ahead of it, so the tier
    gate meets and refuses that unreadable candidate. A picked layer that is present but not a regular
    file comes first itself, for the same reason."""
    legacy_root = review_store.store_root()
    candidates = [
        _unified_in_repo_layer_path(cwd, hero),
        _legacy_in_repo(cwd, hero),
        _unified_global_layer_path(cwd, hero, root),
        _legacy_global_profile_path(cwd, legacy_root),
    ]
    candidates = [c for c in candidates if c is not None]
    try:
        picked = core_md.layer_path(cwd, hero, root, persist_backfill=False)
    except Exception:
        picked = None
    if picked and os.path.lexists(picked) and not os.path.isfile(picked):
        # axis: a picked layer that is present but not a regular file is listed first, so the tier gate refuses it instead of reading a stale copy
        return [picked] + [c for c in candidates if c != picked]
    mode_layer = _mode_layer(cwd, hero, root)
    if mode_layer is None:
        return candidates
    ahead = candidates[:candidates.index(mode_layer)] if mode_layer in candidates else []
    # axis: an unreadable candidate today's order ranks ahead of the mode layer is listed first, so the tier gate refuses it
    blockers = [c for c in ahead if os.path.lexists(c) and not os.path.isfile(c)]
    return blockers + [mode_layer] + [c for c in candidates if c != mode_layer and c not in blockers]


def _core_beside_layer(layer_p, cwd, root):
    """Read-only core.md probe co-located with the layer — no mode_registry side effects."""
    beside = os.path.join(os.path.dirname(layer_p), "core.md")
    if os.path.isfile(beside):
        return beside
    global_core = os.path.join(mode_registry.project_store_dir(cwd, root), "config", "core.md")
    return global_core if os.path.isfile(global_core) else None


def _with_dispatch_fields(out, cwd, root):
    """dispatch_core/dispatch_layer: unified paths when present, else legacy single-file."""
    legacy = out.get("legacy_path")
    layer = out.get("layer_path")
    leg_ok = legacy and os.path.isfile(legacy)
    layer_ok = layer and os.path.isfile(layer)
    out["dispatch_layer"] = layer or (legacy if leg_ok else None)
    out["dispatch_core"] = (
        regular_core(cwd, root)
        or out.get("core_path")
        or (legacy if leg_ok else None)
        or (layer if layer_ok else None)
    )
    return out


def resolve(cwd, root=None, hero=REVIEW_CREW, legacy_root=None, heal=False, *, _contradiction_check=True):
    """Resolve unified + legacy calibration locations for review-crew consumers.

    Precedence: unified-in-repo → legacy-in-repo → unified-global → legacy-global.
    Returns location, exists, layout, core_path, layer_path, legacy_path, plus
    dispatch_core and dispatch_layer (paths specialists should read — legacy
    single-file fills both when no unified split exists yet). healed/entry_id
    are set only when the legacy-global branch runs (heal controls pointer repair).
    Raises UnresolvableRootError when a supplied ``root`` resolves nothing while the
    default resolution finds calibration.
    """
    legacy_root = legacy_root or review_store.store_root()
    legacy_in = _legacy_in_repo(cwd, hero)

    mode_layer = _mode_layer(cwd, hero, root)
    if mode_layer is not None and mode_layer == _unified_global_layer_path(cwd, hero, root):
        # axis: the review reads the layer configure writes (core_md.layer_path), so a stale in-repo copy never beats the mode's layer
        return _with_dispatch_fields({
            "location": mode_registry.GLOBAL, "exists": True, "layout": "unified",
            "core_path": _core_beside_layer(mode_layer, cwd, root),
            "layer_path": mode_layer, "legacy_path": None,
            "healed": False, "entry_id": None,
        }, cwd, root)

    layer_p = _unified_in_repo_layer(cwd, hero)
    if layer_p:
        return _with_dispatch_fields({
            "location": mode_registry.IN_REPO, "exists": True, "layout": "unified",
            "core_path": _core_beside_layer(layer_p, cwd, root),
            "layer_path": layer_p,
            "legacy_path": legacy_in if legacy_in and os.path.isfile(legacy_in) else None,
            "healed": False, "entry_id": None,
        }, cwd, root)

    if legacy_in and os.path.isfile(legacy_in):
        return _with_dispatch_fields({
            "location": mode_registry.IN_REPO, "exists": True, "layout": "legacy",
            "core_path": None, "layer_path": None, "legacy_path": legacy_in,
            "healed": False, "entry_id": None,
        }, cwd, root)

    layer_p = _unified_global_layer(cwd, hero, root)
    if layer_p:
        return _with_dispatch_fields({
            "location": mode_registry.GLOBAL, "exists": True, "layout": "unified",
            "core_path": _core_beside_layer(layer_p, cwd, root),
            "layer_path": layer_p, "legacy_path": None,
            "healed": False, "entry_id": None,
        }, cwd, root)

    g = store_core.resolve_global(cwd, legacy_root, heal=heal, _consumer="review_store")
    if g is not None:
        legacy_p = os.path.join(g["dir"], review_store.FILENAMES["profile"])
        if os.path.isfile(legacy_p):
            return _with_dispatch_fields({
                "location": mode_registry.GLOBAL, "exists": True, "layout": "legacy",
                "core_path": None, "layer_path": None, "legacy_path": legacy_p,
                "healed": g["healed"], "entry_id": g["entry_id"],
            }, cwd, root)

    if root is not None and _contradiction_check:
        probe = resolve(
            cwd, root=None, hero=hero, legacy_root=legacy_root,
            heal=False, _contradiction_check=False,
        )
        if probe.get("exists"):
            raise UnresolvableRootError(
                root=root,
                cwd=cwd,
                hero=hero,
                default_location=probe["location"],
                default_layer_path=probe.get("dispatch_layer"),
            )

    return _with_dispatch_fields({
        "location": "none", "exists": False, "layout": None,
        "core_path": None, "layer_path": None, "legacy_path": None,
        "healed": g["healed"] if g else False,
        "entry_id": g["entry_id"] if g else None,
    }, cwd, root)


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
    try:
        result = resolve(os.getcwd(), root=args.root)
    except UnresolvableRootError as exc:
        sys.stderr.write(json.dumps(exc.payload()) + "\n")
        return 2
    sys.stdout.write(json.dumps(result) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
