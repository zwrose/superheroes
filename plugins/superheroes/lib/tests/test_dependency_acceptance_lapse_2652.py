"""A dependency preflight accepted must still hold at launch; without that acceptance the old gate stands."""
import json

import pytest

from test_launcher import (
    L,
    _all_checks,
    _dependency_premise,
    _head_sha,
    _init_repo,
    _ledger_env,
    _pr_vet_state_ok,
    _ready_vet_body,
)


@pytest.mark.parametrize("evidence, expected", [
    # axis: an accepted READY dependency whose READY line stayed at the old head refuses at launch
    ("accepted", {"ok": False, "reason": "dependency-acceptance-lapsed"}),
    # axis: base-state evidence that records no acceptance keeps the pre-existing ungated not-ready pass
    ("", {"ok": True}),
    ("not json", {"ok": True}),
])
def test_an_advanced_ready_dependency_lapses_only_a_recorded_acceptance(tmp_path, monkeypatch, evidence, expected):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    old_head = _head_sha(repo)
    new_head = ("1" if old_head[0] == "0" else "0") + old_head[1:]
    if evidence == "accepted":
        evidence = json.dumps([{"pr": 701, "head": old_head, "form": "ready", "stack": None}])
    monkeypatch.setattr(L.stack_check, "resolve_repo_slug", lambda *args, **kwargs: ("acme/widgets", None))
    result = L._apply_dependency_gate(
        _dependency_premise(repo, 701, issue=7), old_head, repo, {},
        lambda pr, slug, **kwargs: (_pr_vet_state_ok(new_head, _ready_vet_body(old_head), pr_number=pr), None),
        accepted_form=L._preflight_accepted_form(
            [{"id": "base-state", "state": "pass", "evidence": evidence}], 701),
    )
    assert {key: result[key] for key in expected} == expected
    if not expected["ok"]:
        assert result["detail"] == new_head
    else:
        assert result["dependencyGate"] == {"applied": False, "reason": "dependency-not-ready"}


def test_the_accepted_form_is_read_only_from_base_state_rows_naming_the_dependency():
    rows = json.dumps([{"pr": 702, "form": "ready"}, {"pr": 701, "form": "stack-card"}])
    assert L._preflight_accepted_form([{"id": "base-state", "evidence": rows}], 701) == "stack-card"
    assert L._preflight_accepted_form([{"id": "base-state", "evidence": rows}], 703) is None
    assert L._preflight_accepted_form([{"id": "engine-auth", "evidence": rows}], 701) is None
    assert L._preflight_accepted_form([{"id": "base-state", "evidence": "{}"}], 701) is None
    assert L._preflight_accepted_form(None, 701) is None
