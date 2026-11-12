"""Regression: mention_guard wrapping must not expose an adjacent login."""
import pytest

import mention_guard


@pytest.mark.parametrize("text", ["@one-no-such-login-0000000000000000000000@two-no-such-login-0000000000000000000000", "<p>@one-no-such-login-0000000000000000000000@two-no-such-login-0000000000000000000000</p>\n"])
def test_wrapping_cannot_expose_an_adjacent_mention(text):
    # axis: inserting code delimiters must not expose the following at-sign in prose or raw HTML.
    wrapped = mention_guard.wrap(text)
    assert "@one-no-such-login-0000000000000000000000" in wrapped and "@two-no-such-login-0000000000000000000000" in wrapped
    assert mention_guard.bare_mentions(wrapped) == []
    assert mention_guard.wrap(wrapped) == wrapped
