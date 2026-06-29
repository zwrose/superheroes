# plugins/superheroes/lib/base_ref.py
"""Resolve a caller-supplied build base branch name to a git-usable ref — the SINGLE source of
base-ref resolution shared by build_state_cli (the entry/per-task gather) and ship_phase (the
freshness gate). Extracted so the two sites CANNOT drift: they once disagreed (gather had a
local->origin fallback; freshness used origin/<base> only), so a base that exists locally but is
not pushed to origin gathered fine yet gated a genuinely-up-to-date branch (#115, C-I1).

Pure git IO, dependency-free. Fail-closed by contract: an unresolvable base returns None and the
caller MUST fail closed (never silently treat everything as unmapped / gate on an opaque error)."""
import subprocess


def _git(git_root, *args):
    return subprocess.run(["git", "-C", git_root, *args], capture_output=True, text=True)


def resolve_configured_base(git_root, branch_name):
    """Resolve a caller-supplied base branch name to a ref git can use.

    Tries <branch_name> first (a local ref like 'live-showrunner-102'), then 'origin/<branch_name>'
    (its remote-tracking counterpart). Returns the resolved ref string on success, or None on
    failure (caller must fail closed)."""
    for ref in (branch_name, "origin/" + branch_name):
        if _git(git_root, "rev-parse", "--verify", "--quiet", ref).returncode == 0:
            return ref
    return None


def unresolvable_reason(branch_name, git_root):
    """The canonical, specific fail-closed message for an unresolvable base. One string so both
    consumers (build_state_cli's stdout error sentinel, ship_phase's freshness gate reason) report
    the SAME reason to the owner."""
    return ("--base %r could not be resolved in %s "
            "(tried local and origin/<branch>) — failing closed" % (branch_name, git_root))
