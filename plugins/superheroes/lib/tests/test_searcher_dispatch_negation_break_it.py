"""The searcher dispatch guard must reject an affirmative general-purpose instruction."""

import os

import pytest

import test_seat_tool_grants as grants


def test_searcher_dispatch_guard_rejects_unrelated_never(monkeypatch):
    # axis: removing the general-purpose prohibition must fail even when another clause in the same sentence still says never.
    path = os.path.join(
        grants.PLUGIN, "skills", "review-code", "reference", "auto-fix-loop.md"
    )
    original_read = grants._read_required
    source = original_read(path, "the searcher dispatch instructions")
    needle = "never as a `general-purpose` subagent and never on"
    assert source.count(needle) == 1
    unsafe = source.replace(
        needle, "as a `general-purpose` subagent and never on", 1
    )

    def read_with_unsafe_instruction(candidate, why):
        return unsafe if candidate == path else original_read(candidate, why)

    monkeypatch.setattr(grants, "_read_required", read_with_unsafe_instruction)
    with pytest.raises(AssertionError, match="searcher-dispatch"):
        grants.test_searcher_dispatch_names_the_plugin_agent_and_never_general_purpose()
