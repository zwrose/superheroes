# plugins/superheroes/lib/ship_ci.py
"""Pure CI-head decider for the ship phase. FR-5 stale-pass rejection: `gh pr checks` reports on the
PR's CURRENT remote head, so its rollup may only be judged when that head equals the integrated local
HEAD. A confirmed mismatch is 'stale' (the rollup belongs to an earlier commit). Unreadable heads are
NOT 'stale' here — the leaf's own fail-closed paths handle those."""


def is_stale(local, remote):
    """True iff local and remote are both known and DIFFER (the rollup is for an earlier commit)."""
    return bool(local and remote and local != remote)
