import freshness


def test_ancestor_true_is_up_to_date():
    action, _ = freshness.decide(is_ancestor=True, attempt=1)
    assert action == "up_to_date"


def test_behind_under_cap_says_sync():
    action, _ = freshness.decide(is_ancestor=False, attempt=1)
    assert action == "sync"


def test_behind_at_cap_still_syncs():
    action, _ = freshness.decide(is_ancestor=False, attempt=3, max_attempts=3)
    assert action == "sync"


def test_behind_past_cap_gives_up_with_notify():
    action, reason = freshness.decide(is_ancestor=False, attempt=4, max_attempts=3)
    assert action == "give_up_notify" and "behind" in reason.lower()


def test_unknown_ancestor_read_fails_closed_to_gate():
    # An unreadable merge-base (None) must never be treated as up-to-date.
    action, _ = freshness.decide(is_ancestor=None, attempt=1)
    assert action == "gate"


def test_non_bool_ancestor_fails_closed():
    action, _ = freshness.decide(is_ancestor="yes", attempt=1)
    assert action == "gate"


def test_bad_attempt_fails_closed():
    action, _ = freshness.decide(is_ancestor=False, attempt=0)
    assert action == "gate"


def test_bool_attempt_fails_closed():
    # bool is an int subclass in Python; a True/False attempt count must be
    # rejected (not silently treated as 1/0), so the isinstance(attempt, bool)
    # guard is load-bearing — pin it so the mutant that drops it can't survive.
    assert freshness.decide(is_ancestor=False, attempt=True)[0] == "gate"
    assert freshness.decide(is_ancestor=False, attempt=False)[0] == "gate"
