import os, subprocess, sys
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


# --- #25: route-aware input-artifact gate (spec on full, tasks on quick) --------------------

def test_full_route_default_echoes_route_and_gates_on_the_spec():
    # No `route` key => full (byte-identical for every existing caller): the spec gate is checked
    # and the verdict echoes the resolved route so the launcher reads a validated literal.
    out = preflight.decide(_all_good(), "wi")
    assert out["route"] == "full"
    assert any(b["check"] == "spec-approved" and b["status"] == "pass" for b in out["blocking"])
    assert not any(b["check"] == "tasks-approved" for b in out["blocking"])


def test_quick_route_gates_on_the_tasks_doc_not_the_absent_spec():
    # The whole point of quick discovery: a spec-less run must gate on the TASKS doc, not fail on
    # an absent spec. tasks passed + NO spec present => ok, route echoed 'quick'.
    p = _all_good(); p["route"] = "quick"; p.pop("spec_gate", None); p["tasks_gate"] = "passed"
    out = preflight.decide(p, "wi")
    assert out["ok"] is True and out["route"] == "quick"
    assert any(b["check"] == "tasks-approved" and b["status"] == "pass" for b in out["blocking"])
    assert not any(b["check"] == "spec-approved" for b in out["blocking"])


def test_quick_route_unapproved_tasks_blocks():
    p = _all_good(); p["route"] = "quick"; p.pop("spec_gate", None); p["tasks_gate"] = "pending"
    out = preflight.decide(p, "wi")
    assert out["ok"] is False
    f = [b for b in out["blocking"] if b["check"] == "tasks-approved"][0]
    assert f["status"] == "fail" and f["remediation"]


def test_derive_route_prefers_spec_then_tasks(tmp_path, monkeypatch):
    # The route is derived from which input artifact is on disk, through the SAME resolver the tasks
    # phase writes through: spec present => full; else tasks present => quick; neither => full.
    import definition_doc
    d = tmp_path / "wi"; d.mkdir()
    monkeypatch.setattr(definition_doc, "resolve_work_item_dir", lambda work_item, **kw: str(d))
    assert preflight._derive_route("wi", str(tmp_path)) == "full"          # neither artifact
    (d / "tasks.md").write_text("x")
    assert preflight._derive_route("wi", str(tmp_path)) == "quick"         # tasks only
    (d / "spec.md").write_text("x")
    assert preflight._derive_route("wi", str(tmp_path)) == "full"          # spec wins over tasks


def test_derive_route_failcloses_to_full_on_resolver_error(monkeypatch):
    import definition_doc
    def boom(*a, **k):
        raise RuntimeError("storage mode undeterminable")
    monkeypatch.setattr(definition_doc, "resolve_work_item_dir", boom)
    assert preflight._derive_route("wi", "/nope") == "full"

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


def test_live_run_remediation_names_the_holder():
    # #170: the block for an already-running work item names the lease holder so the owner can
    # find the run (threaded via the active_run_holder probe).
    p = _all_good(); p["active_run"] = "live"; p["active_run_holder"] = "pid 4242 on host-x"
    out = preflight.decide(p, "wi")
    f = [b for b in out["blocking"] if b["check"] == "no-active-run"][0]
    assert f["status"] == "fail" and "pid 4242 on host-x" in f["remediation"]


def test_lease_state_reads_target_work_item_lease(tmp_path):
    # #170: preflight's no-active-run reads the TARGET work item's lease directly from the
    # common-dir store. A live lease for the target => "live" (block) naming the holder; a
    # released/absent lease for the target => "stale" (pass).
    import control_plane
    import ref_lock
    subprocess.run(["git", "-C", str(tmp_path), "init", "-q"], check=True)
    root = str(tmp_path / "store")
    store = control_plane.ensure_store(str(tmp_path), root=root)
    assert store is not None
    # absent lease -> stale/pass
    state, holder = preflight._lease_state(str(tmp_path), "wi", root)
    assert state == "stale" and holder is None
    # a live lease for THIS work item -> live/block, holder named
    ok, gen, _r = ref_lock.acquire(store, "wi")
    assert ok
    # _lease_state resolves the store from os.getcwd() semantics via checkout_dir(cwd, root);
    # here cwd==tmp_path resolves the same store the lease was written to.
    state, holder = preflight._lease_state(str(tmp_path), "wi", root)
    assert state == "live" and holder and "pid" in holder
    # a DIFFERENT work item's lease does not block this target
    state_other, _ = preflight._lease_state(str(tmp_path), "other-wi", root)
    assert state_other == "stale"
    # releasing (park) frees it -> pass again
    ref_lock.release(store, "wi", gen)
    state_after, _ = preflight._lease_state(str(tmp_path), "wi", root)
    assert state_after == "stale"
