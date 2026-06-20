"""Deterministic decision for the step-8 base-freshness gate — keep the branch
up to date with its PR base before handback, bounded so a hot base can't be
chased forever. Pure + fail-CLOSED: an unreadable ancestor read or a bad attempt
count GATES (never assume up-to-date on an unknown read).

The mechanical work (the merge, conflict resolution) is the orchestrator's; this
only decides 'are we up to date / should we sync / give up'. Mirrors
ci_loop.decide: a pure round-bounded gate.
"""

DEFAULT_MAX_SYNCS = 3


def decide(is_ancestor, attempt, max_attempts=DEFAULT_MAX_SYNCS):
    """('up_to_date' | 'sync' | 'give_up_notify' | 'gate', reason).

    is_ancestor: True  => origin/<base> is an ancestor of HEAD (branch already
                          contains base) => up to date.
                 False => branch is behind base => sync (or give up if past cap).
                 anything else (e.g. None from a failed `git merge-base` read) =>
                          GATE, fail-closed; an unknown read is never up-to-date.
    attempt: 1-based number of the sync we are about to make.
    max_attempts: bound on syncs so a continuously-advancing base does not loop.
    """
    if not isinstance(attempt, int) or isinstance(attempt, bool) or attempt < 1:
        return ("gate", "bad attempt count (fail-closed)")
    if is_ancestor is True:
        return ("up_to_date", "branch already contains base")
    if is_ancestor is not False:
        return ("gate", "freshness read undetermined — fail closed")
    if attempt > max_attempts:
        return ("give_up_notify",
                "still behind base after %d sync attempts" % max_attempts)
    return ("sync", "behind base — sync attempt %d" % attempt)
