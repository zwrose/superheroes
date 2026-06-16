#!/usr/bin/env python3
"""Resolve the-architect's definition_doc.py for review-crew's gate writes.

The review trio (review-spec/review-plan/review-tasks) records definition-doc review
gates via **the-architect's** lib — the single writer of the §3.1 frontmatter
(CONVENTIONS §3). But review-crew and the-architect install as **separate plugins**, so
review-crew must LOCATE the-architect's lib at runtime. This is the cross-plugin
lib-resolution concern deferred in CONVENTIONS §7 — resolved here so the certifying gate
is reachable in a shipped band, not only in the monorepo.

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


def resolve(root=None, plugin_root=None):
    """Return the absolute path to the-architect's definition_doc.py, or None.

    `root` is the target-repo root (the in-repo case); `plugin_root` overrides
    `$CLAUDE_PLUGIN_ROOT` (the installed-sibling case). Both are optional; whichever
    resolves first wins.
    """
    # 1. in-repo (the-architect vendored alongside review-crew under plugins/)
    if root:
        cand = os.path.join(root, "plugins", *_DOC)
        if os.path.isfile(cand):
            return os.path.abspath(cand)
    # 2. installed sibling under the marketplace cache
    plugin_root = plugin_root or os.environ.get("CLAUDE_PLUGIN_ROOT")
    if plugin_root:
        # <CLAUDE_PLUGIN_ROOT> = .../<marketplace>/review-crew/<ver>; the marketplace
        # dir (where the-architect installs as a sibling) is two levels up.
        marketplace = os.path.abspath(os.path.join(plugin_root, os.pardir, os.pardir))
        matches = [p for p in glob.glob(os.path.join(marketplace, _DOC[0], "*", *_DOC[1:]))
                   if os.path.isfile(p)]
        if matches:
            return os.path.abspath(max(matches, key=_version_key))
    return None


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
