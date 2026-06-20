"""Resolve a band sibling's bundled file (the-architect / review-crew /
test-pilot), whether dogfooded in-repo or installed under the marketplace cache.
Fail-closed (None when unresolvable).

Modeled on review-crew/lib/architect_lib.py:resolve_target — the band's existing
cross-plugin resolution idiom — generalized to any target tuple.
"""
import glob
import os


def _version_key(path, depth):
    """Sort key for a versioned cache path: the version dir is `depth` levels
    above the target file. Numeric segments compare numerically (0.10 > 0.9)."""
    d = path
    for _ in range(depth):
        d = os.path.dirname(d)
    ver = os.path.basename(d)
    return [(0, int(p)) if p.isdigit() else (1, p)
            for p in ver.replace("-", ".").split(".")]


def resolve_target(target, root=None, plugin_root=None):
    """Absolute path to plugins/<target...>, or None.

    `target` is a path tuple under a plugins/ dir, e.g.
    ("the-architect", "lib", "escalation.py"). In-repo (root/plugins/...) wins;
    else the installed sibling under the marketplace cache (highest version).
    """
    if not isinstance(target, (list, tuple)) or not target:
        return None
    if root:
        cand = os.path.join(root, "plugins", *target)
        if os.path.isfile(cand):
            return os.path.abspath(cand)
    plugin_root = plugin_root or os.environ.get("CLAUDE_PLUGIN_ROOT")
    if plugin_root:
        marketplace = os.path.abspath(os.path.join(plugin_root, os.pardir, os.pardir))
        pattern = os.path.join(marketplace, target[0], "*", *target[1:])
        matches = [p for p in glob.glob(pattern) if os.path.isfile(p)]
        if matches:
            depth = len(target) - 1  # <ver> is len(target)-1 dirname hops above the file
            return os.path.abspath(max(matches, key=lambda p: _version_key(p, depth)))
    return None
