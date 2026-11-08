"""Regression checks for session-directory propagation to the kept-test gate."""
import ast

import pytest

import test_kept_head_resolver_2393 as T


def test_discharge_exclusion_preserves_the_meta_only_head(tmp_path):
    # axis: excluding an already-fixed batch must still certify its retained test using the session's meta-only head.
    world = T.World(tmp_path)
    world.fixed_finding()
    world.write_meta(headSha=world.fix())
    T.RD._set_findings(world.state, list(world.state["_toVerify"]))

    T.RD._after_findings_settled(
        world.state, world.state["config"], session_dir=world.session_dir)

    assert world.round_record["fixBatchExcludedByDischarge"] == 1
    assert world.state["terminal"] == "converged", world.state.get("certification")
    assert world.round_record["breakItKept"][0]["outcome"] == "kept"


def test_forwarding_census_rejects_a_null_session_directory(monkeypatch):
    # axis: a session_dir keyword carrying None must fail the forwarding detector; only an in-memory AST is modified.
    tree = T._round_driver_tree()
    synthesis = T._function(tree, "_fold_synthesis")
    calls = [node for node in ast.walk(synthesis)
             if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Name)
             and node.func.id == "_after_findings_settled"]
    (call,) = calls
    (keyword,) = [item for item in call.keywords if item.arg == "session_dir"]
    keyword.value = ast.Constant(value=None)
    monkeypatch.setattr(T, "_round_driver_tree", lambda: tree)

    with pytest.raises(AssertionError):
        T.test_t6_census_b_every_chain_call_made_where_a_session_dir_is_held_passes_it()
