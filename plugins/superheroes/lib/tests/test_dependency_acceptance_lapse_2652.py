"""A dependency preflight accepted must still qualify at launch; without a recorded acceptance the old gate stands."""
import json

import pytest

from test_issue_contract import FEATURE, NOT_LINKED, _in_stack
from test_launcher import (
    L,
    _all_checks,
    _card_vet_body,
    _dependency_premise,
    _head_sha,
    _init_repo,
    _ledger_env,
    _membership_ok,
    _parked_vet_body,
    _pr_vet_state_ok,
    _ready_vet_body,
    _stack_premise,
)


def _gate(tmp_path, monkeypatch, body_at, accepted, base=None):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    head = _head_sha(repo)
    monkeypatch.setattr(L.stack_check, "resolve_repo_slug", lambda *args, **kwargs: ("acme/widgets", None))
    result = L._apply_dependency_gate(
        _dependency_premise(repo, 701, issue=7), base or head, repo, {},
        lambda pr, slug, **kwargs: (_pr_vet_state_ok(head, body_at(head), pr_number=pr), None),
        accepted=accepted, membership_reader=lambda **kwargs: dict(NOT_LINKED),
    )
    return result, head


def test_an_accepted_ready_dependency_whose_ready_line_stayed_behind_lapses(tmp_path, monkeypatch):
    # axis: an accepted READY dependency that advanced past its READY line refuses at launch
    stale = lambda head: _ready_vet_body(("1" if head[0] == "0" else "0") + head[1:])
    result, head = _gate(tmp_path, monkeypatch, stale, {"pr": 701, "form": "ready", "head": "h", "feature": FEATURE})
    assert result == {"ok": False, "reason": "dependency-acceptance-lapsed", "detail": head}


def test_without_a_recorded_acceptance_the_ungated_not_ready_pass_stands(tmp_path, monkeypatch):
    stale = lambda head: _ready_vet_body(("1" if head[0] == "0" else "0") + head[1:])
    result, _ = _gate(tmp_path, monkeypatch, stale, None)
    assert result["dependencyGate"] == {"applied": False, "reason": "dependency-not-ready"}


@pytest.mark.parametrize("card_feature, expected_ok", [(FEATURE, True), (77, False)])
def test_an_accepted_card_dependency_must_name_the_feature_it_was_accepted_for(
    tmp_path, monkeypatch, card_feature, expected_ok,
):
    # axis: a current-head card rewritten to name another feature lapses the acceptance
    body = lambda head: _card_vet_body(head, parent=card_feature)
    result, head = _gate(tmp_path, monkeypatch, body, {"pr": 701, "form": "stack-card", "head": "h", "feature": FEATURE})
    assert result["ok"] is expected_ok
    if not expected_ok:
        assert result == {"ok": False, "reason": "dependency-acceptance-lapsed", "detail": head}


def test_the_accepted_row_is_read_only_from_base_state_rows_naming_the_dependency():
    rows = [{"pr": 702, "form": "ready", "head": "h"}, {"pr": 701, "form": "stack-card", "head": "h"}]
    checks = lambda evidence, check="base-state": [{"id": check, "evidence": evidence}]
    assert L._preflight_accepted(checks(json.dumps(rows)), 701) == rows[1]
    assert L._preflight_accepted(checks(json.dumps(rows)), 703) is None
    assert L._preflight_accepted(checks("[]"), 701) is None
    assert L._preflight_accepted(checks(""), 701) is None
    assert L._preflight_accepted(checks("Accepted PR #701 at abc", "engine-auth"), 701) is None
    assert L._preflight_accepted(None, 701) is None
    # axis: base-state evidence that is not the accepted-rows array is unreadable, never "nothing accepted"
    for unreadable in ("Accepted PR #701 at abc", "{}", "[1]", "not json", json.dumps(rows[1]),
                       json.dumps([{"pr": "701", "form": "ready", "head": "h"}]), json.dumps([{"pr": 701}]),
                       json.dumps([{"pr": 701, "form": "ready"}]), json.dumps([{"pr": 701, "form": "ready", "head": 5}])):
        assert L._preflight_accepted(checks(unreadable), 701) is False, unreadable
    # axis: with no dependency named, every accepted row is returned (an empty list for empty evidence)
    assert L._preflight_accepted(checks(json.dumps(rows)), None) == rows
    assert L._preflight_accepted(checks(""), None) == []
    assert L._preflight_accepted(checks("{}"), None) is False


@pytest.mark.parametrize("membership, expected_ok", [
    (dict(NOT_LINKED), True), (_in_stack(900, 1), False),
    ({"ok": False, "reason": "stack-unreadable", "detail": "x"}, False),
])
def test_an_accepted_unstacked_dependency_is_reread_for_stack_membership(tmp_path, monkeypatch, membership, expected_ok):
    # axis: an accepted dependency that joined a stack, or whose membership cannot be read, refuses at launch
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    head = _head_sha(repo)
    monkeypatch.setattr(L.stack_check, "resolve_repo_slug", lambda *args, **kwargs: ("acme/widgets", None))
    reads = []
    result = L._apply_dependency_gate(
        _dependency_premise(repo, 701, issue=7), head, repo, {},
        lambda pr, slug, **kwargs: (_pr_vet_state_ok(head, _ready_vet_body(head), pr_number=pr), None),
        accepted={"pr": 701, "form": "ready", "head": head, "stack": None, "feature": FEATURE},
        membership_reader=lambda **kwargs: reads.append(kwargs["pr"]) or membership,
    )
    assert reads == [701]
    assert result["ok"] is expected_ok, result
    if membership is not NOT_LINKED and not expected_ok:
        assert result["reason"] in ("dependency-acceptance-lapsed", "dependency-read-unavailable")


def test_an_unaccepted_draft_keeps_the_ungated_pass_even_with_a_stale_card(tmp_path, monkeypatch):
    # axis: with no recorded acceptance a draft dependency stays work in flight, as before this change
    stale_card = lambda head: _card_vet_body(("1" if head[0] == "0" else "0") + head[1:], parent=FEATURE)
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    head = _head_sha(repo)
    monkeypatch.setattr(L.stack_check, "resolve_repo_slug", lambda *args, **kwargs: ("acme/widgets", None))
    result = L._apply_dependency_gate(
        _dependency_premise(repo, 701, issue=7), head, repo, {},
        lambda pr, slug, **kwargs: (_pr_vet_state_ok(head, stale_card(head), pr_number=pr, is_draft=True), None),
    )
    assert result == {"ok": True, "dependencyGate": {"applied": False, "reason": "dependency-not-ready"}}


@pytest.mark.parametrize("evidence", [[{"pr": 701, "form": "ready"}], {"pr": 701, "form": "ready"}, None])
def test_walk_preflight_keeps_base_state_json_evidence_as_its_json_text(tmp_path, evidence):
    # axis: base-state evidence given as JSON (array or not) is kept for the acceptance reader, never dropped
    repo = _init_repo(tmp_path / "repo")
    out = L.walk_preflight(_all_checks(**{"base-state": {"state": "pass", "reason": "", "evidence": evidence}}), repo)
    assert out["ok"] is True, out
    entry = next(check for check in out["checks"] if check["id"] == "base-state")
    assert json.loads(entry["evidence"]) == evidence


class _StackGateReached(Exception):
    pass


@pytest.mark.parametrize("withdrawn", [True, False], ids=["card-withdrawn", "card-intact"])
def test_a_stack_premise_rechecks_every_accepted_lower_layer_before_the_stack_gate(tmp_path, monkeypatch, withdrawn):
    # axis: on a stack premise an accepted lower layer whose card was withdrawn at the same head refuses; an intact one
    # passes on to the stack gate
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    head = _head_sha(repo)
    monkeypatch.setattr(L.stack_check, "resolve_repo_slug", lambda *args, **kwargs: ("acme/widgets", None))
    body = _parked_vet_body(head) if withdrawn else _card_vet_body(head, parent=FEATURE)
    row = {"pr": 701, "form": "stack-card", "head": head, "stack": 1, "feature": FEATURE}
    checks = _all_checks(**{"base-state": {"state": "pass", "reason": "", "evidence": json.dumps([row])}})

    def pr_lookup(*args, **kwargs):
        raise _StackGateReached()

    def launch():
        return L.launch_build(
            repo, 7, _stack_premise(repo, stack=1, layerPosition=2, issue=7), checks, str(tmp_path / "logs"),
            pr_vet_reader=lambda pr, slug, **kwargs: (_pr_vet_state_ok(head, body, pr_number=pr), None),
            membership_reader=lambda **kwargs: _membership_ok(1, head, pr_number=701) | {"stack": {"number": 1}},
            pr_lookup=pr_lookup,
        )

    if withdrawn:
        result = launch()
        assert result["ok"] is False
        assert result["reason"] == "dependency-acceptance-lapsed"
    else:
        with pytest.raises(_StackGateReached):
            launch()
