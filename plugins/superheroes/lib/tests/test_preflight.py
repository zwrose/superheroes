import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import preflight

def _all_good():
    return {
        "spec_gate": "passed",
        "gh": {"ok": True},
        "active_run": "none",          # none | parked | stale | <other-live-work-item>
        "repo_ready": True,
        "verify_resolves": True,
        "config_resolves": True,
        "ci": {"provider": None, "required": False},
    }

def test_all_blocking_pass_is_ok():
    out = preflight.decide(_all_good(), "wi")
    assert out["ok"] is True
    # advisory present because no required CI gates the PR
    assert any(a["check"] == "ci-visibility" for a in out["advisory"])

def test_unapproved_spec_blocks():
    p = _all_good(); p["spec_gate"] = "pending"
    out = preflight.decide(p, "wi")
    assert out["ok"] is False
    f = [b for b in out["blocking"] if b["check"] == "spec-approved"][0]
    assert f["status"] == "fail" and f["remediation"]

def test_indeterminate_is_failclosed():
    p = _all_good(); p["gh"] = {"ok": False, "cause": "indeterminate", "remediation": "retry"}
    out = preflight.decide(p, "wi")
    assert out["ok"] is False
    assert [b for b in out["blocking"] if b["check"] == "github-access"][0]["status"] in ("fail", "indeterminate")

def test_active_live_run_blocks_but_parked_or_stale_passes():
    live = _all_good(); live["active_run"] = "live"
    assert preflight.decide(live, "wi")["ok"] is False
    for benign in ("none", "parked", "stale", "finished"):
        p = _all_good(); p["active_run"] = benign
        assert preflight.decide(p, "wi")["ok"] is True, benign


def test_unknown_readiness_probe_fails_closed_indeterminate():
    # None/unknown for repo_ready / verify_resolves / config_resolves must hit the fail-closed
    # `else` branch: block with that check's status == "indeterminate" (a probe that couldn't be
    # evaluated is treated as not-passing, never silently allowed through).
    for key, check in (("repo_ready", "repo-ready"), ("verify_resolves", "verify-resolves"),
                       ("config_resolves", "config-resolves")):
        p = _all_good(); p[key] = None
        out = preflight.decide(p, "wi")
        assert out["ok"] is False, key
        f = [b for b in out["blocking"] if b["check"] == check][0]
        assert f["status"] == "indeterminate" and f["remediation"], key

def test_required_ci_suppresses_advisory():
    p = _all_good(); p["ci"] = {"provider": "github-actions", "required": True}
    out = preflight.decide(p, "wi")
    assert out["ok"] is True
    assert not any(a["check"] == "ci-visibility" for a in out["advisory"])
