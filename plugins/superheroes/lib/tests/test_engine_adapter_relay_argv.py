"""Tests for the two relay argv builders in engine_adapter (#1748 C7r-1)."""
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.join(_HERE, "..")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import engine_adapter  # noqa: E402


def test_agents_list_argv():
    assert engine_adapter.claude_agents_list_argv() == {
        "argv": ["claude", "agents", "--json"], "reason": None}


def test_version_argv():
    # axis: the version argv is exactly `claude --version` — the call the contract gate reads the installed claude with
    assert engine_adapter.claude_version_argv() == {"argv": ["claude", "--version"], "reason": None}


def test_stop_argv_names_the_agent_by_its_id():
    # axis: the stop argv targets the listed short id and nothing else
    assert engine_adapter.claude_stop_argv("d1") == {"argv": ["claude", "stop", "d1"], "reason": None}


@pytest.mark.parametrize("agent_id", [None, 7, "", "-rf", "a b", "a/b", "x" * 65])
def test_stop_argv_refuses_an_id_that_is_not_a_short_agent_id(agent_id):
    # axis: a malformed id yields a refusal and no executable argv
    out = engine_adapter.claude_stop_argv(agent_id)
    assert out["argv"] == [] and out["reason"] == engine_adapter.REFUSAL_RELAY_STOP_ID_INVALID
    assert out["detail"]


def test_relay_argv_is_the_named_haiku_background_session():
    out = engine_adapter.claude_relay_argv("superheroes-relay-claude-two", "forward things")
    assert out == {"argv": ["claude", "--bg", "-n", "superheroes-relay-claude-two", "--model",
                            "haiku", "--effort", "low", "forward things"], "reason": None}


@pytest.mark.parametrize("prompt", ["", "  \n", None, 3])
def test_relay_argv_refuses_an_empty_prompt(prompt):
    out = engine_adapter.claude_relay_argv("relay", prompt)
    assert out["argv"] == [] and out["reason"] == engine_adapter.REFUSAL_BUILDER_PROMPT_MISSING
    assert out["detail"]


@pytest.mark.parametrize("name", ["", "has space", "a/b", "x" * 65, None, 7])
def test_relay_argv_refuses_a_bad_session_name(name):
    out = engine_adapter.claude_relay_argv(name, "forward things")
    assert out["argv"] == [] and out["reason"] == engine_adapter.REFUSAL_CLOUD_SESSION_NAME_INVALID
    assert out["detail"]
