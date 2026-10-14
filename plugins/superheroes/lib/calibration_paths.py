#!/usr/bin/env python3
"""The one home of "which paths are calibration files" (C6 FU3). Stdlib only, so a low-level writer
(`store_core.atomic_write`) can import it without a cycle.

A calibration file is one the cloud-session guard refuses to write, move or remove
(`CLAUDE_CODE_REMOTE == "true"`):

  * a `*.md` directly in the in-repo calibration directory `.claude/superheroes/`;
  * under a project store dir `<root>/projects/<key>/`: `registry.json`, `meta.json`,
    `doc-policy.json`, `config/*.md` and `permission/rules.json`;
  * the review-crew profile's two legacy locations: `<repo>/.claude/review-profile.md` and
    `<review store root>/entries/<hash>/review-profile.md`.

The legacy names live here, once; the modules above this leaf (`mode_registry`, `review_store`,
`calibration_resolve`) import them, so the guard and the resolver share one definition.
"""
import os
import pathlib

IN_REPO_DIR = os.path.join(".claude", "superheroes")

# The calibration layout inside a project store dir `<store_root>/projects/<key>/`.
REGISTRY_FILENAME = "registry.json"
META_FILENAME = "meta.json"
POLICY_FILENAME = "doc-policy.json"
CONFIG_DIRNAME = "config"
PERMISSION_DIRNAME = "permission"
PERMISSION_RULES_FILENAME = "rules.json"
STORE_TOP_FILES = (REGISTRY_FILENAME, META_FILENAME, POLICY_FILENAME)

# The review-crew profile's two legacy locations.
LEGACY_INREPO_REVIEW_PROFILE = os.path.join(".claude", "review-profile.md")
LEGACY_STORE_ENTRIES_DIRNAME = "entries"
LEGACY_STORE_PROFILE_FILENAME = "review-profile.md"


def _classify(real):
    parent, name = os.path.split(real)
    parts = pathlib.PurePath(real).parts
    in_repo_dir = pathlib.PurePath(IN_REPO_DIR).parts
    if name.endswith(".md") and pathlib.PurePath(parent).parts[-len(in_repo_dir):] == in_repo_dir:
        return True
    legacy_inrepo = pathlib.PurePath(LEGACY_INREPO_REVIEW_PROFILE).parts
    if parts[-len(legacy_inrepo):] == legacy_inrepo:
        return True
    if (len(parts) >= 3 and parts[-3] == LEGACY_STORE_ENTRIES_DIRNAME
            and parts[-1] == LEGACY_STORE_PROFILE_FILENAME):
        return True
    if len(parts) >= 3 and parts[-3] == "projects" and parts[-1] in STORE_TOP_FILES:
        return True
    if len(parts) >= 4 and parts[-4] == "projects":
        return ((parts[-2] == CONFIG_DIRNAME and parts[-1].endswith(".md"))
                or (parts[-2] == PERMISSION_DIRNAME and parts[-1] == PERMISSION_RULES_FILENAME))
    return False


def is_calibration_path(path):
    """True when `path` is a calibration file (see the module docstring). The store root is not
    consulted: writers take an explicit root, so the layout alone decides. Pure.

    Classifies both the fully resolved path and the path as given, so a symlink standing where a
    calibration file belongs is caught, and so is a file reached through a symlinked directory. A
    path that cannot be resolved (an OSError or ValueError from the resolver) is classified as
    given."""
    given = os.path.abspath(path)
    try:
        real = os.path.realpath(given)
    except (OSError, ValueError):
        real = given
    return _classify(real) or _classify(given)
