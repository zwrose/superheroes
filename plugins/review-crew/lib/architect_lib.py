#!/usr/bin/env python3
"""Resolve the-architect's definition_doc.py for review-crew's gate writes.

The review trio (review-spec/review-plan/review-tasks) records definition-doc review
gates via **the-architect's** lib — the single writer of the §3.1 frontmatter
(CONVENTIONS §3). But review-crew and the-architect install as **separate plugins**, so
review-crew must LOCATE the-architect's lib at runtime — the band's heroes install as
separate plugins (CONVENTIONS "Band posture"). This resolver closes that cross-plugin
lib-resolution gap so the certifying gate is reachable in a shipped band, not only in the
monorepo.

Resolution order (first hit wins):
  1. **In-repo** (monorepo / dogfooding): ``<root>/plugins/the-architect/lib/definition_doc.py``.
  2. **Installed sibling**: a sibling of review-crew under the same marketplace cache —
     ``<CLAUDE_PLUGIN_ROOT>/../../the-architect/*/lib/definition_doc.py`` (highest version).

Prints the resolved absolute path and exits 0; **fails closed** (exits 1, message on
stderr) when neither resolves — the caller then reports "gate not recorded" rather than
crashing or hand-editing YAML (the band's degrade-not-crash posture).

stdlib only (the band convention); no third-party version parsing.
"""
import argparse
import glob
import os
import sys

# the-architect's lib, relative to a plugins/ dir or a marketplace-cache dir.
_DOC = ("the-architect", "lib", "definition_doc.py")


def _version_key(path):
    """Sort key for ``.../the-architect/<ver>/lib/definition_doc.py`` by <ver>.

    Numeric segments compare numerically (so 0.10 > 0.9); non-numeric fall back to
    string. The version dir is two levels up from definition_doc.py.
    """
    ver = os.path.basename(os.path.dirname(os.path.dirname(path)))
    return [(0, int(p)) if p.isdigit() else (1, p) for p in ver.replace("-", ".").split(".")]


def resolve_target(target, root=None, plugin_root=None):
    """Return the absolute path to one of the-architect's files, or None.

    `target` is a path tuple relative to a plugins/ dir, e.g.
    ("the-architect", "lib", "escalation.py") or
    ("the-architect", "rubric", "escalation-base.md"). Resolution order matches the
    existing definition_doc.py logic: in-repo (root/plugins/...) first, then the
    installed sibling under the marketplace cache (highest version wins). Fail-closed.
    """
    if root:
        cand = os.path.join(root, "plugins", *target)
        if os.path.isfile(cand):
            return os.path.abspath(cand)
    plugin_root = plugin_root or os.environ.get("CLAUDE_PLUGIN_ROOT")
    if plugin_root:
        marketplace = os.path.abspath(os.path.join(plugin_root, os.pardir, os.pardir))
        matches = [p for p in glob.glob(os.path.join(marketplace, target[0], "*", *target[1:]))
                   if os.path.isfile(p)]
        if matches:
            return os.path.abspath(max(matches, key=_version_key))
    return None


def resolve(root=None, plugin_root=None):
    """Back-compat: resolve the-architect's definition_doc.py (the original behavior)."""
    return resolve_target(_DOC, root=root, plugin_root=plugin_root)


def main(argv):
    ap = argparse.ArgumentParser(description="resolve the-architect's definition_doc.py (CONVENTIONS §7)")
    ap.add_argument("--root", default=None, help="target-repo root (the in-repo case)")
    ap.add_argument("--plugin-root", default=None, help="override $CLAUDE_PLUGIN_ROOT (installed-sibling case)")
    args = ap.parse_args(argv[1:])
    path = resolve(args.root, args.plugin_root)
    if not path:
        sys.stderr.write(
            "architect_lib: the-architect's definition_doc.py not found "
            "(not in-repo under <root>/plugins/, not an installed sibling of review-crew)\n")
        return 1
    sys.stdout.write(path + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
