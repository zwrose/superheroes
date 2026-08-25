"""Interim receipt at non-terminal stops — per-pass verdict totals (#1107 WO-C)."""
import hashlib
import importlib.util
import json
import os
import subprocess

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_LIB, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RD = _load("round_driver")
RR = _load("round_records")
HG = _load("handback_gate")
verification = _load("verification")

DIFF = ("diff --git a/f.py b/f.py\nindex 1..2 100644\n--- a/f.py\n+++ b/f.py\n"
        "@@ -1 +1,2 @@\n-old\n+new\n+more\n")


def _cfg(**over):
    base = {"leg": "code", "vendors": ["claude", "codex"], "diff": DIFF, "fixerVendor": "claude"}
    base.update(over)
    return base


def _session(tmp_path, name="s", **cfg_over):
    d = str(tmp_path / name)
    os.makedirs(d, exist_ok=True)
    out = RD.cmd_next(d, _cfg(**cfg_over))
    assert out["ok"], out
    return d


def _state(session_dir):
    ok, state = RD.load_state(session_dir)
    assert ok, state
    return state


def _finding(fid="v0", **over):
    base = {"file": "f.py", "line": 1, "title": "issue", "severity": "Important", "id": fid}
    base.update(over)
    return base


def _fold_verifiers(state, findings, verdicts):
    staged = verification.stage_ids(findings)
    state["_toVerify"] = staged
    RD._fold_verifiers(state, state["config"], {"verdicts": verdicts})


# --- per-pass append --------------------------------------------------------------------------

def test_verify_passes_records_two_waves_without_overwrite():
    # axis: each verifier fold appends one verifyPasses entry; a second wave must not overwrite.
    state = RD.new_state(_cfg())
    f0, f1 = _finding("v0"), _finding("v1", line=2)
    _fold_verifiers(state, [f0], [{"id": "v0", "verdict": "CONFIRMED", "evidence": "ran"}])
    _fold_verifiers(state, [f1], [{"id": "v0", "verdict": "REFUTED", "reason": "not real"}])
    passes = state["rounds"]["1"]["verifyPasses"]
    assert len(passes) == 2
    assert passes[0]["CONFIRMED"] == 1 and passes[0]["REFUTED"] == 0
    assert passes[1]["CONFIRMED"] == 0 and passes[1]["REFUTED"] == 1


def test_build_receipt_projects_verify_passes(tmp_path):
    state = RD.new_state(_cfg())
    _fold_verifiers(state, [_finding()], [{"id": "v0", "verdict": "PLAUSIBLE", "reason": "x"}])
    receipt = RD.build_receipt(state, str(tmp_path))
    assert receipt["rounds"][0]["verifyPasses"][0]["PLAUSIBLE"] == 1


def test_verify_passes_absent_from_certified_v2_with_truthy_list(tmp_path):
    """v2 certified receipts omit verifyPasses even when the round recorded a non-empty list."""
    state = RD.new_state(_cfg())
    state["schemaVersion"] = 2
    _fold_verifiers(state, [_finding()], [{"id": "v0", "verdict": "CONFIRMED", "evidence": "ran"}])
    assert state["rounds"]["1"]["verifyPasses"]
    receipt = RD.build_receipt(state, str(tmp_path))
    assert "verifyPasses" not in receipt["rounds"][0]
    interim = RD.build_interim_receipt(state, str(tmp_path), "park")
    assert interim["rounds"][0]["verifyPasses"][0]["CONFIRMED"] == 1


def test_records_path_resume_preserves_verify_passes_in_interim(tmp_path):
    """A recordsPath resume with verifyPasses disclosures must not read as unverified."""
    records = tmp_path / "round-records.json"
    vp = [{"CONFIRMED": 2, "PLAUSIBLE": 0, "REFUTED": 1, "drops": 1,
           "downgrades": 0, "unverified": 0, "ambiguous": 0}]
    rec = {"schemaVersion": 2, "round": 1, "kind": "baseline",
           "dimensions": {"test-reviewer": {"status": "run", "findings": []}},
           "findings": [], "coverageDecisions": [],
           "disclosures": {"verifyPasses": vp}}
    records.write_text(__import__("json").dumps([rec]))
    state = RD.new_state(_cfg(recordsPath=str(records)))
    interim = RD.build_interim_receipt(state, str(tmp_path / "s"), "tripwire")
    assert interim["rounds"][0]["verifyPasses"] == vp


def test_resume_verify_passes_second_wave_appends(tmp_path):
    """Restored verifyPasses plus a new verifier fold must append, not replace."""
    records = tmp_path / "round-records.json"
    wave0 = [{"CONFIRMED": 1, "PLAUSIBLE": 0, "REFUTED": 0, "drops": 0,
              "downgrades": 0, "unverified": 0, "ambiguous": 0}]
    rec = {"schemaVersion": 2, "round": 1, "kind": "baseline",
           "dimensions": {"test-reviewer": {"status": "run", "findings": []}},
           "findings": [], "coverageDecisions": [],
           "disclosures": {"verifyPasses": wave0}}
    records.write_text(__import__("json").dumps([rec]))
    state = RD.new_state(_cfg(recordsPath=str(records)))
    state["round"] = 1
    _fold_verifiers(state, [_finding("v1", line=2)],
                    [{"id": "v0", "verdict": "REFUTED", "reason": "no"}])
    passes = state["rounds"]["1"]["verifyPasses"]
    assert len(passes) == 2
    assert passes[0]["CONFIRMED"] == 1 and passes[1]["REFUTED"] == 1


def test_interim_receipt_validates_with_empty_verify_passes(tmp_path):
    d = _session(tmp_path)
    out = RD.cmd_checkpoint(d, "tripwire")
    assert out["ok"] is True
    with open(os.path.join(d, RD.RECEIPT_INTERIM_FILE), encoding="utf-8") as fh:
        receipt = json.load(fh)
    ok, reason = RD.validate_receipt(receipt)
    assert ok is True, reason
    assert "verifyPasses" not in (receipt["rounds"][0] if receipt["rounds"] else {})


# --- interim schema / receipt_kind ------------------------------------------------------------

def test_receipt_kind_recognizes_interim_before_certified():
    # axis: interim schema must classify as receipt-interim/1, not receipt-certified/*.
    interim = RD.build_interim_receipt(RD.new_state(_cfg()), None, "park")
    assert RD.receipt_kind(interim) == RD.RECEIPT_INTERIM_SCHEMA
    assert RD.receipt_kind(interim) != RD.RECEIPT_CERTIFIED_SCHEMA % 3


def test_validate_interim_rejects_certification_keys():
    interim = RD.build_interim_receipt(RD.new_state(_cfg()), None, "held")
    interim["certification"] = {"shape": "smuggled"}
    ok, reason = RD.validate_receipt(interim)
    assert ok is False
    assert "certification" in reason


# --- terminal gate ---------------------------------------------------------------------------

def test_verify_terminal_receipt_rejects_interim_on_disk(tmp_path):
    # axis: _verify_terminal_receipt must fault on a legacy interim at the terminal path.
    d = _session(tmp_path)
    interim = RD.build_interim_receipt(_state(d), d, "tripwire")
    with open(os.path.join(d, RD.RECEIPT_FILE), "w", encoding="utf-8") as fh:
        json.dump(interim, fh)
    fault = RD._verify_terminal_receipt(d)
    assert fault is not None
    assert "interim" in fault


def test_terminal_receipt_written_over_interim(tmp_path):
    d = _session(tmp_path)
    assert RD.cmd_checkpoint(d, "park")["ok"] is True
    state = _state(d)
    state["terminal"] = "halted"
    state["certification"] = {"shape": None, "reason": "test halt"}
    RD.save_state(d, state)
    RD._journal_append(d, {"cmd": "submit", "phase": RD.P_PANEL, "round": 1, "attempt": 0})
    fault = RD._terminal_receipt_gate(d, state)
    assert fault is None
    with open(os.path.join(d, RD.RECEIPT_FILE), encoding="utf-8") as fh:
        on_disk = json.load(fh)
    assert RD.receipt_kind(on_disk) == RD.RECEIPT_CERTIFIED_SCHEMA % RD.STATE_SCHEMA_VERSION


# --- checkpoint command ----------------------------------------------------------------------

def test_checkpoint_refuses_session_already_terminal(tmp_path):
    d = _session(tmp_path)
    state = _state(d)
    state["terminal"] = "halted"
    RD.save_state(d, state)
    out = RD.cmd_checkpoint(d, "tripwire")
    assert out["ok"] is False and out["reason"] == "checkpoint-session-terminal"


def test_checkpoint_refuses_when_terminal_receipt_on_disk(tmp_path):
    # axis: checkpoint must refuse once a terminal receipt exists on disk.
    d = _session(tmp_path)
    state = _state(d)
    state["terminal"] = "halted"
    state["certification"] = {"shape": None, "reason": "halt"}
    RD._journal_append(d, {"cmd": "submit", "phase": RD.P_PANEL, "round": 1, "attempt": 0})
    RD._write_receipt(d, state)
    out = RD.cmd_checkpoint(d, "park")
    assert out["ok"] is False and out["reason"] == "checkpoint-terminal-receipt-exists"


def test_checkpoint_supersedes_prior_interim(tmp_path):
    d = _session(tmp_path)
    assert RD.cmd_checkpoint(d, "tripwire")["ok"] is True
    out = RD.cmd_checkpoint(d, "park")
    assert out["ok"] is True and out["stop"]["reason"] == "park"
    with open(os.path.join(d, RD.RECEIPT_INTERIM_FILE), encoding="utf-8") as fh:
        receipt = json.load(fh)
    assert receipt["stop"]["reason"] == "park"


def test_checkpoint_refuses_unknown_stop_reason(tmp_path):
    # axis: unknown stop reasons must refuse with an enumerated token, never accept free text.
    d = _session(tmp_path)
    out = RD.cmd_checkpoint(d, "owner-bailout")
    assert out["ok"] is False and out["reason"] == "checkpoint-stop-reason-unknown"


def test_checkpoint_journals_event(tmp_path):
    d = _session(tmp_path)
    assert RD.cmd_checkpoint(d, "held")["ok"] is True
    entries = list(RD.read_journal(d))
    assert any(e.get("cmd") == "checkpoint" and e.get("outcome") == "checkpointed"
               for e in entries)


def test_checkpoint_stop_reason_held_succeeds_non_terminal(tmp_path):
    # axis: held is reachable at the stall menu before the hold fold sets terminal.
    d = _session(tmp_path)
    out = RD.cmd_checkpoint(d, "held")
    assert out["ok"] is True
    with open(os.path.join(d, RD.RECEIPT_INTERIM_FILE), encoding="utf-8") as fh:
        receipt = json.load(fh)
    assert receipt["stop"]["reason"] == "held"


def test_checkpoint_stop_reason_held_refuses_terminal(tmp_path):
    d = _session(tmp_path)
    state = _state(d)
    state["terminal"] = "held"
    RD.save_state(d, state)
    out = RD.cmd_checkpoint(d, "held")
    assert out["ok"] is False and out["reason"] == "checkpoint-session-terminal"


def test_checkpoint_stop_reasons_census_non_terminal(tmp_path):
    # axis: every CHECKPOINT_STOP_REASONS member must succeed on a non-terminal session.
    for reason in RD.CHECKPOINT_STOP_REASONS:
        d = _session(tmp_path, name="s-%s" % reason)
        out = RD.cmd_checkpoint(d, reason)
        assert out["ok"] is True, (reason, out)


def test_interim_checkpoint_not_at_terminal_path(tmp_path):
    # axis: interim checkpoint receipt must not occupy the terminal receipt path.
    d = _session(tmp_path)
    assert RD.cmd_checkpoint(d, "park")["ok"] is True
    assert not os.path.exists(os.path.join(d, RD.RECEIPT_FILE))
    assert os.path.exists(os.path.join(d, RD.RECEIPT_INTERIM_FILE))


def test_legacy_interim_at_terminal_path_classified_as_interim(tmp_path):
    # axis: legacy interim at round-receipt.json is interim, not terminal.
    d = _session(tmp_path)
    interim = RD.build_interim_receipt(_state(d), d, "tripwire")
    with open(os.path.join(d, RD.RECEIPT_FILE), "w", encoding="utf-8") as fh:
        json.dump(interim, fh)
    assert RD._on_disk_receipt_class(d) == "interim"
    assert RD._terminal_receipt_on_disk(d) is False


def test_checkpoint_oserror_surfaces_as_refusal(tmp_path, monkeypatch):
    d = _session(tmp_path)

    def boom(*_a, **_k):
        raise OSError("disk full")

    monkeypatch.setattr(RD.round_commit, "begin", boom)
    out = RD.cmd_checkpoint(d, "tripwire")
    assert out["ok"] is False and out["reason"] == "interim-receipt-unwritable"


# --- cmd_attest re-key -----------------------------------------------------------------------

def test_attest_allowed_when_only_interim_on_disk(tmp_path, monkeypatch):
    # axis: attest must not refuse merely because the receipt path exists when the receipt is interim.
    d = _session(tmp_path)
    assert RD.cmd_checkpoint(d, "tripwire")["ok"] is True
    assert RD._terminal_receipt_on_disk(d) is False
    calls = []

    def track_resolve(_sd, ref):
        calls.append(ref)
        return None, "attest-failure-unknown"

    monkeypatch.setattr(RD, "_resolve_failure_ref", track_resolve)
    out = RD.cmd_attest(d, "1", "orphaned record; handing back uncertified")
    assert out["ok"] is False
    assert out["reason"] != "terminal-receipt-exists"
    assert out["reason"] != "terminal-receipt-unreadable"
    assert calls == ["1"]


def test_attest_refuses_unreadable_on_disk_receipt(tmp_path):
    # axis: unreadable on-disk receipt is never permission to overwrite
    d = _session(tmp_path)
    path = os.path.join(d, RD.RECEIPT_FILE)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("not-json{{")
    out = RD.cmd_attest(d, "1", "orphaned record; handing back uncertified")
    assert out["ok"] is False
    assert out["reason"] == "terminal-receipt-unreadable"


def test_checkpoint_calls_commit_recover_before_write(tmp_path, monkeypatch):
    # axis: checkpoint must replay a sealed-unapplied commit before opening its own
    d = _session(tmp_path)
    calls = []
    orig = RD._commit_recover_or_refuse

    def track(sd, cmd, **kw):
        calls.append(cmd)
        return orig(sd, cmd, **kw)

    monkeypatch.setattr(RD, "_commit_recover_or_refuse", track)
    assert RD.cmd_checkpoint(d, "tripwire")["ok"] is True
    assert calls == ["checkpoint"]


# --- handback_gate ---------------------------------------------------------------------------

_REMOTE = "git@github.com:org/repo.git"
_REPO_ID = "github.com/org/repo"


def _git(cwd, *args):
    subprocess.run(
        ["git", "-C", cwd, *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _init_repo(path, remote=_REMOTE):
    path = str(path)
    subprocess.run(["git", "init", "-q", "-b", "main", path], check=True,
                   capture_output=True, text=True)
    _git(path, "config", "user.email", "t@example.com")
    _git(path, "config", "user.name", "Test")
    if remote:
        _git(path, "remote", "add", "origin", remote)
    return path


def _commit_file(repo, name, content, msg="init"):
    p = os.path.join(repo, name)
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(content)
    _git(repo, "add", name)
    _git(repo, "commit", "-q", "-m", msg)
    return p


def _gitdir(repo):
    store = _load("store_core")
    return store.get_worktree_gitdir(repo)


def _superheroes_dir(repo):
    d = os.path.join(_gitdir(repo), HG._SIDECAR_DIR)
    os.makedirs(d, exist_ok=True)
    return d


def _diff_sha256(repo, base_sha):
    r = subprocess.run(
        ["git", "-C", repo, "diff", "%s...HEAD" % base_sha],
        capture_output=True,
        timeout=10,
    )
    assert r.returncode == 0, r.stderr
    return hashlib.sha256(r.stdout).hexdigest()


def _certified_receipt(verdict="converged"):
    return {
        "schema": RD.RECEIPT_CERTIFIED_SCHEMA % 3,
        "schemaVersion": 3,
        "verdict": verdict,
        "certificationShape": "audited-chain",
        "certification": {"shape": "audited-chain"},
        "scriptRan": {"byPhase": {}},
        "seatMap": {},
        "rounds": [],
        "findings": [],
        "decisions": [],
        "degraded": [],
        "skippedBlockers": [],
    }


def _write_build_lane(repo, **over):
    d = _superheroes_dir(repo)
    store = _load("store_core")
    obj = {
        "schema": HG.BUILD_LANE_SCHEMA,
        "lane": "full",
        "issue": "#1107",
        "declaredAt": "2026-08-09T00:00:00Z",
        "repoRoot": os.path.realpath(repo),
        "branch": store.run_git(repo, "rev-parse", "--abbrev-ref", "HEAD") or "main",
    }
    obj.update(over)
    with open(os.path.join(d, HG.BUILD_LANE_FILE), "w", encoding="utf-8") as fh:
        json.dump(obj, fh)


def _write_sidecar(repo, session_dir, receipt_obj, *, verdict="converged", base_ref="main",
                   base_sha=None):
    store = _load("store_core")
    head_sha = store.run_git(repo, "rev-parse", "HEAD")
    if base_sha is None:
        base_sha = store.run_git(repo, "rev-parse", "--verify", "--quiet",
                                 "%s^{commit}" % base_ref)
    diff_sha = _diff_sha256(repo, base_sha)
    receipt_path = os.path.join(session_dir, RD.RECEIPT_FILE)
    os.makedirs(session_dir, exist_ok=True)
    receipt_bytes = json.dumps(receipt_obj).encode("utf-8")
    with open(receipt_path, "wb") as fh:
        fh.write(receipt_bytes)
    sidecar = RR.build_sidecar(
        repoId=_REPO_ID,
        branch=store.run_git(repo, "rev-parse", "--abbrev-ref", "HEAD") or "main",
        headSha=head_sha,
        baseRef=base_ref,
        baseSha=base_sha,
        diffSha256=diff_sha,
        verdict=verdict,
        certificationShape="audited-chain" if verdict == "converged" else "attested",
        receiptPath=receipt_path,
        receiptSha256=hashlib.sha256(receipt_bytes).hexdigest(),
        policySha256="policy",
        sessionDir=session_dir,
    )
    path = os.path.join(_superheroes_dir(repo), HG._SIDECAR_FILE)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(sidecar, fh)
    return sidecar


def _scoped_handback_repo(tmp_path, receipt_obj, *, verdict="converged"):
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "base.txt", "base\n", msg="base")
    base_sha = _load("store_core").run_git(repo, "rev-parse", "HEAD")
    _commit_file(repo, "feature.txt", "feature\n", msg="feature")
    session = str(tmp_path / "session")
    _write_build_lane(repo)
    _write_sidecar(repo, session, receipt_obj, verdict=verdict, base_ref="main", base_sha=base_sha)
    return repo, session, base_sha


def _reload_handback_gate():
    return _load("handback_gate")


def test_handback_gate_rejects_interim_receipt():
    interim = RD.build_interim_receipt(RD.new_state(_cfg()), None, "tripwire")
    sidecar = {"verdict": "converged"}
    ok, why = HG._receipt_bindings_ok(sidecar, interim)
    assert ok is False
    assert why == "receipt-interim-not-handback-evidence"


def test_public_handback_rejects_interim_receipt(tmp_path):
    # axis: interim token must survive validate_handback — not collapse to verdict-not-allowlisted.
    interim = RD.build_interim_receipt(RD.new_state(_cfg()), None, "tripwire")
    repo, _, _ = _scoped_handback_repo(tmp_path, interim, verdict="converged")
    result = HG.validate_handback("gh pr ready", repo)
    assert result["decision"] == "refuse"
    assert result["reason"] == "receipt-interim-not-handback-evidence"


def test_public_handback_rejects_non_object_receipt(tmp_path):
    # axis: scalar/list JSON must refuse cleanly — never AttributeError on .get.
    repo, _, _ = _scoped_handback_repo(tmp_path, [1, 2, 3], verdict="converged")
    result = HG.validate_handback("gh pr ready", repo)
    assert result["decision"] == "refuse"
    assert result["reason"] == "handback-receipt-unreadable"
    assert "not an object" in result["detail"]


def test_public_handback_rejects_non_allowlisted_verdict(tmp_path):
    # axis: genuine verdict-not-allowlisted path stays accurate through validate_handback.
    repo, _, _ = _scoped_handback_repo(
        tmp_path, _certified_receipt(verdict="halted"), verdict="halted")
    result = HG.validate_handback("gh pr ready", repo)
    assert result["decision"] == "refuse"
    assert result["reason"] == "handback-verdict-not-allowlisted"


@pytest.mark.xdist_group(name="handback_gate_source_mutators")
def test_bite_public_handback_interim_token(tmp_path):
    interim = RD.build_interim_receipt(RD.new_state(_cfg()), None, "tripwire")
    repo, _, _ = _scoped_handback_repo(tmp_path, interim, verdict="converged")
    red = HG.validate_handback("gh pr ready", repo)
    assert red["reason"] == "receipt-interim-not-handback-evidence"
    path = os.path.join(_LIB, "handback_gate.py")
    with open(path, encoding="utf-8") as fh:
        src = fh.read()
    patched = src.replace(
        '        if bind_why == "receipt-interim-not-handback-evidence":\n'
        '            return _refuse("receipt-interim-not-handback-evidence", "",\n'
        '                            subject=subject, sidecar_path=sidecar_path, head_sha=head_sha)\n'
        '        return _refuse("handback-verdict-not-allowlisted", "",\n'
        '                        subject=subject, sidecar_path=sidecar_path, head_sha=head_sha)',
        '        return _refuse("handback-verdict-not-allowlisted", "",\n'
        '                        subject=subject, sidecar_path=sidecar_path, head_sha=head_sha)',
        1,
    )
    assert patched != src
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(patched)
    try:
        mod = _reload_handback_gate()
        green = mod.validate_handback("gh pr ready", repo)
        assert green["reason"] != "receipt-interim-not-handback-evidence"
        assert green["reason"] == "handback-verdict-not-allowlisted"
    finally:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(src)
        _reload_handback_gate()


@pytest.mark.xdist_group(name="handback_gate_source_mutators")
def test_bite_public_handback_non_object_receipt(tmp_path):
    repo, _, _ = _scoped_handback_repo(tmp_path, [1, 2, 3], verdict="converged")
    red = HG.validate_handback("gh pr ready", repo)
    assert red["reason"] == "handback-receipt-unreadable"
    path = os.path.join(_LIB, "handback_gate.py")
    with open(path, encoding="utf-8") as fh:
        src = fh.read()
    patched = src.replace(
        '    if not isinstance(receipt, dict):\n'
        '        return False, "receipt-invalid:receipt is not an object"\n',
        '',
        1,
    )
    assert patched != src
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(patched)
    try:
        mod = _reload_handback_gate()
        with pytest.raises(AttributeError):
            mod.validate_handback("gh pr ready", repo)
    finally:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(src)
        _reload_handback_gate()

