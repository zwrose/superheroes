"""Tests for lib/handback_gate.py — handback receipt gate (#624 §4).

Uses real git repositories in tmp_path for binding paths; parser/subject tests are pure.
"""
import hashlib
import json
import os
import subprocess

import pytest

from bite_support import patched_module

import handback_gate as hg
import round_driver as RD
import round_records as RR
import store_core as sc

REMOTE = "git@github.com:org/repo.git"
REPO_ID = "github.com/org/repo"


def _git(cwd, *args):
    subprocess.run(
        ["git", "-C", cwd, *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _init_repo(path, remote=REMOTE):
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
    with open(p, "w") as f:
        f.write(content)
    _git(repo, "add", name)
    _git(repo, "commit", "-q", "-m", msg)
    return p


def _gitdir(repo):
    return sc.get_worktree_gitdir(repo)


def _superheroes_dir(repo):
    d = os.path.join(_gitdir(repo), hg._SIDECAR_DIR)
    os.makedirs(d, exist_ok=True)
    return d


def _write_build_lane(repo, **over):
    d = _superheroes_dir(repo)
    obj = {
        "schema": hg.BUILD_LANE_SCHEMA,
        "lane": "full",
        "issue": "#624",
        "declaredAt": "2026-08-09T00:00:00Z",
        "repoRoot": os.path.realpath(repo),
        "branch": sc.run_git(repo, "rev-parse", "--abbrev-ref", "HEAD") or "main",
    }
    obj.update(over)
    with open(os.path.join(d, hg.BUILD_LANE_FILE), "w", encoding="utf-8") as fh:
        json.dump(obj, fh)


def _write_review_session(repo, **over):
    d = _superheroes_dir(repo)
    obj = {
        "schema": hg.REVIEW_SESSION_SCHEMA,
        "sessionDir": str(repo / "session") if hasattr(repo, "__truediv__") else "/tmp/session",
        "startedAt": "2026-08-09T00:00:00Z",
        "repoRoot": os.path.realpath(repo),
        "branch": sc.run_git(repo, "rev-parse", "--abbrev-ref", "HEAD") or "main",
    }
    obj.update(over)
    with open(os.path.join(d, hg.REVIEW_SESSION_FILE), "w", encoding="utf-8") as fh:
        json.dump(obj, fh)
    return obj


def _write_loop_state(session_dir, **over):
    os.makedirs(session_dir, exist_ok=True)
    obj = {"terminal": "converged"}
    obj.update(over)
    with open(os.path.join(session_dir, RD.STATE_FILE), "w", encoding="utf-8") as fh:
        json.dump(obj, fh)
    return obj


def _write_driver_journal(session_dir, rows):
    os.makedirs(session_dir, exist_ok=True)
    path = os.path.join(session_dir, RD.JOURNAL_FILE)
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
    return path


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


def _attested_receipt():
    return {
        "schema": RD.RECEIPT_ATTESTED_SCHEMA,
        "verdict": RD.ATTESTED_VERDICT,
        "attestation": {"by": "owner", "reason": "manual", "class": "test"},
        "rounds": [],
        "findings": [],
        "decisions": [],
        "seatMap": {},
        "scriptRan": {"byPhase": {}},
        "degraded": [],
        "skippedBlockers": [],
        "artifacts": {"meta.json": "a" * 64},
        "roster": {seat: "absent" for seat in RD.DIMENSIONS},
    }


def _write_sidecar(repo, session_dir, receipt_obj, *, verdict="converged", base_ref="main",
                   base_sha=None):
    head_sha = sc.run_git(repo, "rev-parse", "HEAD")
    if base_sha is None:
        base_sha = sc.run_git(repo, "rev-parse", "--verify", "--quiet", "%s^{commit}" % base_ref)
    diff_sha = _diff_sha256(repo, base_sha)
    receipt_path = os.path.join(session_dir, RD.RECEIPT_FILE)
    os.makedirs(session_dir, exist_ok=True)
    receipt_bytes = json.dumps(receipt_obj).encode("utf-8")
    with open(receipt_path, "wb") as fh:
        fh.write(receipt_bytes)
    sidecar = RR.build_sidecar(
        repoId=REPO_ID,
        branch=sc.run_git(repo, "rev-parse", "--abbrev-ref", "HEAD") or "main",
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
    path = os.path.join(_superheroes_dir(repo), hg._SIDECAR_FILE)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(sidecar, fh)
    return sidecar


def _scoped_repo(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "base.txt", "base\n", msg="base")
    base_sha = sc.run_git(repo, "rev-parse", "HEAD")
    _commit_file(repo, "feature.txt", "feature\n", msg="feature")
    session = str(tmp_path / "session")
    _write_build_lane(repo)
    _write_sidecar(repo, session, _certified_receipt(), base_ref="main", base_sha=base_sha)
    return repo, session, base_sha


# --- parser -----------------------------------------------------------------------------------

@pytest.mark.parametrize("command,action", [
    ("gh pr ready", "pr-ready"),
    ("/usr/local/bin/gh pr ready", "pr-ready"),
    ("gh pr create", "pr-create"),
    ("foo && gh pr ready", "pr-ready"),
    ("gh pr ready; gh pr create", "pr-ready"),
])
def test_parse_gh_invocations_recognises_guarded_actions(command, action):
    invs = hg.parse_gh_invocations(command)
    assert any(i["action"] == action for i in invs)


def test_parse_captures_inline_gh_repo():
    invs = hg.parse_gh_invocations("GH_REPO=other/repo gh pr ready")
    assert invs[0]["env"]["GH_REPO"] == "other/repo"


def test_parse_draft_and_undo_flags():
    invs = hg.parse_gh_invocations("gh pr create --draft")
    assert invs[0]["draft"] is True
    invs2 = hg.parse_gh_invocations("gh pr ready --undo")
    assert invs2[0]["undo"] is True


def test_parse_graphql_ready():
    invs = hg.parse_gh_invocations(
        'gh api graphql -f query=mutation{markPullRequestReadyForReview}')
    assert invs[0]["action"] == "graphql-ready"


def test_parse_ignores_gh_in_quotes():
    assert hg.parse_gh_invocations('echo "gh pr ready"') == []


def test_parse_ignores_non_guarded_gh():
    assert hg.parse_gh_invocations("gh pr list") == []


def test_chained_segment_each_scanned():
    invs = hg.parse_gh_invocations("gh pr list && gh pr ready")
    assert len(invs) == 1 and invs[0]["action"] == "pr-ready"


# --- command_subject --------------------------------------------------------------------------

def test_command_subject_repo_flag():
    inv = hg.parse_gh_invocations("gh pr ready -R org/repo")[0]
    subj = hg.command_subject(inv)
    assert subj["repo"] == "github.com/org/repo"
    assert subj["repoSource"] == "flag"


def test_command_subject_inline_and_inherited_env():
    inv = hg.parse_gh_invocations("GH_REPO=inline/repo gh pr ready")[0]
    subj = hg.command_subject(inv, {"GH_REPO": "inherited/repo"})
    assert subj["repo"] == "github.com/inline/repo"
    assert subj["repoSource"] == "env-inline"

    inv2 = hg.parse_gh_invocations("gh pr ready")[0]
    subj2 = hg.command_subject(inv2, {"GH_REPO": "inherited/repo"})
    assert subj2["repo"] == "github.com/inherited/repo"
    assert subj2["repoSource"] == "env-inherited"


def test_command_subject_pr_url():
    inv = hg.parse_gh_invocations(
        "gh pr ready https://github.com/org/repo/pull/42")[0]
    subj = hg.command_subject(inv)
    assert subj["repo"] == REPO_ID
    assert subj["selector"] == "https://github.com/org/repo/pull/42"
    assert subj["repoSource"] == "url"


# --- marker_state -----------------------------------------------------------------------------

def test_marker_state_neither_present(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    state = hg.marker_state(_gitdir(repo), repo)
    assert state == {"inScope": False, "markers": [], "stale": [], "reviewSession": None}


def test_marker_state_valid_build_lane(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    _write_build_lane(repo)
    state = hg.marker_state(_gitdir(repo), repo)
    assert state["inScope"] is True
    assert len(state["markers"]) == 1


def test_marker_state_stale_repo_root(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    _write_build_lane(repo, repoRoot="/elsewhere")
    state = hg.marker_state(_gitdir(repo), repo)
    assert state["inScope"] is False
    assert len(state["stale"]) == 1


# --- validate_handback: scope silence ---------------------------------------------------------

def test_out_of_scope_allows_silently(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "f.txt", "x\n")
    result = hg.validate_handback("gh pr ready", repo)
    assert result["decision"] == "allow"
    assert result["reason"] is None


def test_light_lane_marker_not_in_scope(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    d = _superheroes_dir(repo)
    with open(os.path.join(d, hg.BUILD_LANE_FILE), "w", encoding="utf-8") as fh:
        json.dump({
            "schema": hg.BUILD_LANE_SCHEMA,
            "lane": "light",
            "issue": "#1",
            "declaredAt": "2026-08-09T00:00:00Z",
            "repoRoot": os.path.realpath(repo),
        }, fh)
    result = hg.validate_handback("gh pr ready", repo)
    assert result["decision"] == "allow"
    assert result["reason"] is None


def test_only_stale_marker_allows_silently(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    _write_build_lane(repo, repoRoot="/stale")
    result = hg.validate_handback("gh pr ready", repo)
    assert result["decision"] == "allow"
    assert result["reason"] is None


# --- validate_handback: pass-through ----------------------------------------------------------

def test_draft_create_allowed_in_scope(tmp_path):
    repo, _, _ = _scoped_repo(tmp_path)
    result = hg.validate_handback("gh pr create --draft", repo)
    assert result["decision"] == "allow"


def test_ready_undo_allowed_in_scope(tmp_path):
    repo, _, _ = _scoped_repo(tmp_path)
    result = hg.validate_handback("gh pr ready --undo", repo)
    assert result["decision"] == "allow"


def test_non_guarded_gh_allowed_in_scope(tmp_path):
    repo, _, _ = _scoped_repo(tmp_path)
    result = hg.validate_handback("gh pr list", repo)
    assert result["decision"] == "allow"


# --- validate_handback: refusals --------------------------------------------------------------

def test_no_sidecar_refuses(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "f.txt", "x\n")
    _write_build_lane(repo)
    result = hg.validate_handback("gh pr ready", repo)
    assert result["reason"] == "handback-no-receipt"


def test_verdict_halted_refuses(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "f.txt", "x\n")
    base_sha = sc.run_git(repo, "rev-parse", "HEAD")
    _commit_file(repo, "g.txt", "y\n")
    session = str(tmp_path / "session")
    _write_build_lane(repo)
    _write_sidecar(repo, session, _certified_receipt(verdict="halted"), verdict="halted", base_ref="main", base_sha=base_sha)
    result = hg.validate_handback("gh pr ready", repo)
    assert result["reason"] == "handback-verdict-not-allowlisted"


def test_converged_without_certification_refuses(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "f.txt", "x\n")
    base_sha = sc.run_git(repo, "rev-parse", "HEAD")
    _commit_file(repo, "g.txt", "y\n")
    session = str(tmp_path / "session")
    receipt = _certified_receipt()
    del receipt["certification"]
    _write_build_lane(repo)
    _write_sidecar(repo, session, receipt, verdict="converged", base_ref="main", base_sha=base_sha)
    result = hg.validate_handback("gh pr ready", repo)
    assert result["reason"] == "handback-receipt-unreadable"


def test_attested_without_block_refuses(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "f.txt", "x\n")
    base_sha = sc.run_git(repo, "rev-parse", "HEAD")
    _commit_file(repo, "g.txt", "y\n")
    session = str(tmp_path / "session")
    receipt = _attested_receipt()
    del receipt["attestation"]
    _write_build_lane(repo)
    _write_sidecar(repo, session, receipt, verdict=RD.ATTESTED_VERDICT, base_ref="main", base_sha=base_sha)
    result = hg.validate_handback("gh pr ready", repo)
    assert result["reason"] == "handback-receipt-unreadable"


def test_head_mismatch_refuses(tmp_path):
    repo, session, base_sha = _scoped_repo(tmp_path)
    _commit_file(repo, "moved.txt", "m\n", msg="move head")
    result = hg.validate_handback("gh pr ready", repo)
    assert result["reason"] == "handback-head-mismatch"


def test_inline_gh_repo_mismatch_refuses(tmp_path):
    repo, _, _ = _scoped_repo(tmp_path)
    result = hg.validate_handback("GH_REPO=other/repo gh pr ready", repo)
    assert result["reason"] == "handback-repo-mismatch"


def test_inherited_gh_repo_mismatch_refuses(tmp_path):
    repo, _, _ = _scoped_repo(tmp_path)
    result = hg.validate_handback("gh pr ready", repo, environ={"GH_REPO": "other/repo"})
    assert result["reason"] == "handback-repo-mismatch"


def test_short_repo_flag_mismatch_refuses(tmp_path):
    repo, _, _ = _scoped_repo(tmp_path)
    result = hg.validate_handback("gh pr ready -R other/repo", repo)
    assert result["reason"] == "handback-repo-mismatch"


def test_explicit_selector_refuses(tmp_path):
    repo, _, _ = _scoped_repo(tmp_path)
    result = hg.validate_handback("gh pr ready 42", repo)
    assert result["reason"] == "handback-subject-unresolvable"


def test_head_flag_other_branch_refuses(tmp_path):
    repo, _, _ = _scoped_repo(tmp_path)
    result = hg.validate_handback("gh pr create --head other-branch --base main", repo)
    assert result["reason"] == "handback-subject-unresolvable"


def test_create_base_mismatch_refuses(tmp_path):
    repo, _, _ = _scoped_repo(tmp_path)
    head = sc.run_git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    result = hg.validate_handback("gh pr create --head %s --base develop" % head, repo)
    assert result["reason"] == "handback-base-mismatch"


def test_create_without_base_refuses(tmp_path):
    repo, _, _ = _scoped_repo(tmp_path)
    result = hg.validate_handback("gh pr create", repo)
    assert result["reason"] == "handback-subject-unresolvable"


def test_diff_mismatch_refuses(tmp_path):
    repo, session, base_sha = _scoped_repo(tmp_path)
    sidecar_path = os.path.join(_superheroes_dir(repo), hg._SIDECAR_FILE)
    with open(sidecar_path, encoding="utf-8") as fh:
        sidecar = json.load(fh)
    sidecar["diffSha256"] = "0" * 64
    with open(sidecar_path, "w", encoding="utf-8") as fh:
        json.dump(sidecar, fh)
    result = hg.validate_handback("gh pr ready", repo)
    assert result["reason"] == "handback-diff-mismatch"


def test_receipt_hash_mismatch_refuses(tmp_path):
    repo, session, base_sha = _scoped_repo(tmp_path)
    sidecar_path = os.path.join(_superheroes_dir(repo), hg._SIDECAR_FILE)
    with open(sidecar_path, encoding="utf-8") as fh:
        sidecar = json.load(fh)
    sidecar["receiptSha256"] = "0" * 64
    with open(sidecar_path, "w", encoding="utf-8") as fh:
        json.dump(sidecar, fh)
    result = hg.validate_handback("gh pr ready", repo)
    assert result["reason"] == "handback-receipt-unreadable"


def test_graphql_ready_refuses_in_scope(tmp_path):
    repo, _, _ = _scoped_repo(tmp_path)
    result = hg.validate_handback(
        "gh api graphql -f query=markPullRequestReadyForReview", repo)
    assert result["decision"] == "refuse"


def test_unparseable_pr_flags_refuse(tmp_path):
    repo, _, _ = _scoped_repo(tmp_path)
    result = hg.validate_handback("gh pr create --base", repo)
    assert result["reason"] == "handback-inspection-failed"


def test_valid_converged_allows(tmp_path):
    repo, _, _ = _scoped_repo(tmp_path)
    result = hg.validate_handback("gh pr ready", repo)
    assert result["decision"] == "allow"


def test_valid_attested_allows(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "f.txt", "x\n")
    base_sha = sc.run_git(repo, "rev-parse", "HEAD")
    _commit_file(repo, "g.txt", "y\n")
    session = str(tmp_path / "session")
    _write_build_lane(repo)
    _write_sidecar(repo, session, _attested_receipt(), verdict=RD.ATTESTED_VERDICT, base_ref="main", base_sha=base_sha)
    result = hg.validate_handback("gh pr ready", repo)
    assert result["decision"] == "allow"


def test_review_session_marker_alone_in_scope(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "f.txt", "x\n")
    base_sha = sc.run_git(repo, "rev-parse", "HEAD")
    _commit_file(repo, "g.txt", "y\n")
    session = str(tmp_path / "session")
    _write_review_session(repo, sessionDir=session)
    _write_loop_state(session, terminal="converged")
    _write_sidecar(repo, session, _certified_receipt(), base_ref="main", base_sha=base_sha)
    result = hg.validate_handback("gh pr ready", repo)
    assert result["decision"] == "allow"


def test_refusal_detail_includes_remedies(tmp_path):
    repo, _, _ = _scoped_repo(tmp_path)
    os.remove(os.path.join(_superheroes_dir(repo), hg._SIDECAR_FILE))
    result = hg.validate_handback("gh pr ready", repo)
    assert "round_driver.py attest" in result["detail"]
    assert "park to the advisor" in result["detail"]


# --- parser re-grounding (WO-7) ---------------------------------------------------------------

def test_parse_fill_and_draft_both_set():
    invs = hg.parse_gh_invocations("gh pr create --fill --draft")
    assert len(invs) == 1
    assert invs[0]["draft"] is True
    assert invs[0]["pr"]["base"] is None


def test_parse_fill_and_base():
    invs = hg.parse_gh_invocations("gh pr create --fill --base main")
    assert invs[0]["pr"]["base"] == "main"
    assert invs[0]["pr"]["selector"] is None


def test_parse_draft_false_not_guarded():
    invs = hg.parse_gh_invocations("gh pr create --draft=false")
    assert invs[0]["draft"] is False


def test_parse_undo_false_not_guarded():
    invs = hg.parse_gh_invocations("gh pr ready --undo=false")
    assert invs[0]["undo"] is False


def test_parse_inherited_repo_flag_before_subcommand():
    invs = hg.parse_gh_invocations("gh -R org/repo pr ready")
    assert invs[0]["action"] == "pr-ready"
    assert invs[0]["pr"]["repo"] == "org/repo"


def test_parse_inherited_repo_between_pr_and_subcommand():
    invs = hg.parse_gh_invocations("gh pr -R org/repo ready")
    assert invs[0]["action"] == "pr-ready"
    assert invs[0]["pr"]["repo"] == "org/repo"


def test_parse_host_qualified_repo_flag():
    invs = hg.parse_gh_invocations("gh --repo ghe.example.com/org/repo pr create --base main")
    subj = hg.command_subject(invs[0])
    assert subj["repo"] == "ghe.example.com/org/repo"


def test_command_subject_gh_host_with_bare_repo():
    inv = hg.parse_gh_invocations("GH_HOST=ghe.example.com GH_REPO=org/repo gh pr ready")[0]
    subj = hg.command_subject(inv)
    assert subj["repo"] == "ghe.example.com/org/repo"


def test_command_subject_inherited_gh_host_with_bare_repo():
    inv = hg.parse_gh_invocations("gh pr ready")[0]
    subj = hg.command_subject(inv, {"GH_HOST": "ghe.example.com", "GH_REPO": "org/repo"})
    assert subj["repo"] == "ghe.example.com/org/repo"


def test_cd_before_gh_refuses_in_scope(tmp_path):
    repo, _, _ = _scoped_repo(tmp_path)
    result = hg.validate_handback("cd /other && gh pr ready", repo)
    assert result["reason"] == "handback-inspection-failed"


def test_heredoc_body_gh_not_guarded(tmp_path):
    repo, _, _ = _scoped_repo(tmp_path)
    cmd = "cat > /tmp/note.md <<'EOF'\ngh pr ready\nEOF"
    assert hg.parse_gh_invocations(cmd) == []
    result = hg.validate_handback(cmd, repo)
    assert result["decision"] == "allow"


def test_if_gh_pr_ready_detected():
    invs = hg.parse_gh_invocations("if gh pr ready; then echo ok; fi")
    assert any(i["action"] == "pr-ready" for i in invs)


def test_command_substitution_gh_pr_create_detected():
    invs = hg.parse_gh_invocations('url="$(gh pr create --base main)"')
    assert any(i["action"] == "pr-create" for i in invs)
    assert invs[0]["pr"]["base"] == "main"


def test_create_with_explicit_base_allows(tmp_path):
    repo, _, _ = _scoped_repo(tmp_path)
    result = hg.validate_handback("gh pr create --base main", repo)
    assert result["decision"] == "allow"


def test_legacy_base_ref_sha_refuses(tmp_path):
    repo, session, base_sha = _scoped_repo(tmp_path)
    sidecar_path = os.path.join(_superheroes_dir(repo), hg._SIDECAR_FILE)
    with open(sidecar_path, encoding="utf-8") as fh:
        sidecar = json.load(fh)
    sidecar["baseRef"] = base_sha
    with open(sidecar_path, "w", encoding="utf-8") as fh:
        json.dump(sidecar, fh)
    result = hg.validate_handback("gh pr ready", repo)
    assert result["reason"] == "handback-receipt-unreadable"


def test_receipt_verdict_mismatch_refuses(tmp_path):
    repo, session, base_sha = _scoped_repo(tmp_path)
    receipt_path = os.path.join(session, RD.RECEIPT_FILE)
    with open(receipt_path, encoding="utf-8") as fh:
        receipt = json.load(fh)
    receipt["verdict"] = "halted"
    receipt_bytes = json.dumps(receipt).encode("utf-8")
    with open(receipt_path, "wb") as fh:
        fh.write(receipt_bytes)
    sidecar_path = os.path.join(_superheroes_dir(repo), hg._SIDECAR_FILE)
    with open(sidecar_path, encoding="utf-8") as fh:
        sidecar = json.load(fh)
    sidecar["receiptSha256"] = hashlib.sha256(receipt_bytes).hexdigest()
    with open(sidecar_path, "w", encoding="utf-8") as fh:
        json.dump(sidecar, fh)
    result = hg.validate_handback("gh pr ready", repo)
    assert result["reason"] == "handback-verdict-not-allowlisted"


def test_branch_mismatch_at_equal_head_refuses(tmp_path):
    repo, session, base_sha = _scoped_repo(tmp_path)
    sidecar_path = os.path.join(_superheroes_dir(repo), hg._SIDECAR_FILE)
    with open(sidecar_path, encoding="utf-8") as fh:
        sidecar = json.load(fh)
    sidecar["branch"] = "other-branch"
    with open(sidecar_path, "w", encoding="utf-8") as fh:
        json.dump(sidecar, fh)
    result = hg.validate_handback("gh pr ready", repo)
    assert result["reason"] == "handback-branch-mismatch"


def _git_diff_text(repo, base_sha):
    r = subprocess.run(
        ["git", "-C", repo, "diff", "%s...HEAD" % base_sha],
        capture_output=True,
        timeout=10,
    )
    assert r.returncode == 0, r.stderr
    return r.stdout.decode("utf-8")


def test_base_ref_round_trip_from_prepare_sidecar(tmp_path):
    """Producer sidecar via ``_prepare_sidecar`` must allow ``gh pr create --base <name>``."""
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "base.txt", "base\n", msg="base")
    base_sha = sc.run_git(repo, "rev-parse", "HEAD")
    _commit_file(repo, "feature.txt", "feature\n", msg="feature")
    session = str(tmp_path / "session")
    os.makedirs(session, exist_ok=True)
    receipt = _certified_receipt()
    receipt_path = os.path.join(session, RD.RECEIPT_FILE)
    with open(receipt_path, "w", encoding="utf-8") as fh:
        json.dump(receipt, fh)
    _write_build_lane(repo)
    state = {
        "config": {
            "repoRoot": repo,
            "baseRef": base_sha,
            "baseBranch": "main",
        },
        "terminal": "converged",
        "certification": {"shape": "audited-chain"},
        "reviewedDiff": _git_diff_text(repo, base_sha),
    }
    prepared = RD._prepare_sidecar(session, state)
    assert prepared.get("ok"), prepared
    assert json.loads(prepared["sidecar_bytes"])["baseRef"] == "main"
    assert json.loads(prepared["sidecar_bytes"])["baseSha"] == base_sha
    os.makedirs(os.path.dirname(prepared["path"]), exist_ok=True)
    with open(prepared["path"], "wb") as fh:
        fh.write(prepared["sidecar_bytes"])
    result = hg.validate_handback("gh pr create --base main", repo)
    assert result["decision"] == "allow"


# --- WO-8 exact-shape recognizer --------------------------------------------------------------

@pytest.mark.parametrize("command", [
    "gh pr create --unknown-flag --base main",
    "gh pr create --foo=bar --base main",
])
def test_unknown_option_refuses_in_family(tmp_path, command):
    repo, _, _ = _scoped_repo(tmp_path)
    result = hg.validate_handback(command, repo)
    assert result["reason"] == "handback-inspection-failed"
    assert "unrecognized gh option" in result["detail"]


def test_attached_short_repo_flag_parsed(tmp_path):
    repo, _, _ = _scoped_repo(tmp_path)
    result = hg.validate_handback("gh pr ready -Rother/repo", repo)
    assert result["reason"] == "handback-repo-mismatch"


def test_attached_short_title_not_draft(tmp_path):
    repo, _, _ = _scoped_repo(tmp_path)
    result = hg.validate_handback("gh pr create -tupdate --base main", repo)
    assert result["decision"] == "allow"


def test_body_pr_url_does_not_hijack_repo(tmp_path):
    repo, _, _ = _scoped_repo(tmp_path)
    url = "https://github.com/other/repo/pull/1"
    result = hg.validate_handback("gh pr create --body %s --base main" % url, repo)
    assert result["decision"] == "allow"


def test_head_owner_branch_same_owner_allows(tmp_path):
    repo, _, _ = _scoped_repo(tmp_path)
    branch = sc.run_git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    result = hg.validate_handback("gh pr create --head org:%s --base main" % branch, repo)
    assert result["decision"] == "allow"


def test_head_owner_branch_cross_repo_refuses(tmp_path):
    repo, _, _ = _scoped_repo(tmp_path)
    result = hg.validate_handback("gh pr create --head alice:feature --base main", repo)
    assert result["reason"] == "handback-subject-unresolvable"


def test_head_branch_only_allows(tmp_path):
    repo, _, _ = _scoped_repo(tmp_path)
    branch = sc.run_git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    result = hg.validate_handback("gh pr create --head %s --base main" % branch, repo)
    assert result["decision"] == "allow"


def test_unexpanded_repo_var_refuses(tmp_path):
    repo, _, _ = _scoped_repo(tmp_path)
    result = hg.validate_handback('gh pr ready --repo="$TARGET"', repo)
    assert result["reason"] == "handback-inspection-failed"


def test_quoted_gh_repo_env_parsed(tmp_path):
    repo, _, _ = _scoped_repo(tmp_path)
    result = hg.validate_handback("GH_REPO='other/repo' gh pr ready", repo)
    assert result["reason"] == "handback-repo-mismatch"


def test_help_leaves_family(tmp_path):
    repo, _, _ = _scoped_repo(tmp_path)
    assert hg.validate_handback("gh pr ready --help", repo)["decision"] == "allow"
    assert hg.validate_handback("gh pr create --dry-run --base main", repo)["decision"] == "allow"


def test_marker_branch_mismatch_stale_silence(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "f.txt", "x\n")
    _write_build_lane(repo, branch="other-branch")
    result = hg.validate_handback("gh pr ready", repo)
    assert result["decision"] == "allow"
    assert result["reason"] is None


def test_marker_missing_branch_stale(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "f.txt", "x\n")
    d = _superheroes_dir(repo)
    obj = {
        "schema": hg.BUILD_LANE_SCHEMA,
        "lane": "full",
        "issue": "#624",
        "declaredAt": "2026-08-09T00:00:00Z",
        "repoRoot": os.path.realpath(repo),
    }
    with open(os.path.join(d, hg.BUILD_LANE_FILE), "w", encoding="utf-8") as fh:
        json.dump(obj, fh)
    state = hg.marker_state(_gitdir(repo), repo)
    assert state["inScope"] is False
    assert len(state["stale"]) == 1


def test_review_session_gone_stale(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "f.txt", "x\n")
    session = str(tmp_path / "session")
    os.makedirs(session)
    _write_review_session(repo, sessionDir=session, branch="other-branch")
    state = hg.marker_state(_gitdir(repo), repo)
    assert state["inScope"] is False
    assert len(state["stale"]) == 1


def test_review_session_only_invalid_marker_in_scope(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "f.txt", "x\n")
    _write_review_session(repo, sessionDir="/nonexistent/session")
    state = hg.marker_state(_gitdir(repo), repo)
    assert state["inScope"] is True
    assert state["markers"] == []
    assert len(state["stale"]) == 0


def test_review_session_only_invalid_schema_wrong_branch_in_scope(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "f.txt", "x\n")
    session = str(tmp_path / "session")
    os.makedirs(session)
    _write_review_session(
        repo, schema="wrong-schema", sessionDir=session, branch="other-branch",
    )
    state = hg.marker_state(_gitdir(repo), repo)
    assert state["inScope"] is True
    assert state["markers"] == []
    assert len(state["stale"]) == 0
    result = hg.validate_handback("gh pr ready", repo)
    assert result["decision"] == "refuse"
    assert result["reason"] == "handback-driver-abandoned"


def test_review_session_only_missing_field_wrong_branch_in_scope(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "f.txt", "x\n")
    session = str(tmp_path / "session")
    os.makedirs(session)
    d = _superheroes_dir(repo)
    obj = {
        "schema": hg.REVIEW_SESSION_SCHEMA,
        "sessionDir": session,
        "repoRoot": os.path.realpath(repo),
        "branch": "other-branch",
    }
    with open(os.path.join(d, hg.REVIEW_SESSION_FILE), "w", encoding="utf-8") as fh:
        json.dump(obj, fh)
    state = hg.marker_state(_gitdir(repo), repo)
    assert state["inScope"] is True
    assert state["markers"] == []
    assert len(state["stale"]) == 0
    result = hg.validate_handback("gh pr ready", repo)
    assert result["decision"] == "refuse"
    assert result["reason"] == "handback-driver-abandoned"


def test_review_session_only_missing_session_dir_wrong_branch_in_scope(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "f.txt", "x\n")
    _write_review_session(repo, sessionDir="/nonexistent/session", branch="other-branch")
    state = hg.marker_state(_gitdir(repo), repo)
    assert state["inScope"] is True
    assert state["markers"] == []
    assert len(state["stale"]) == 0
    result = hg.validate_handback("gh pr ready", repo)
    assert result["decision"] == "refuse"
    assert result["reason"] == "handback-driver-abandoned"


def test_review_session_only_branch_mismatch_stale_silent_allow(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "f.txt", "x\n")
    session = str(tmp_path / "session")
    os.makedirs(session)
    _write_review_session(repo, sessionDir=session, branch="other-branch")
    state = hg.marker_state(_gitdir(repo), repo)
    assert state["inScope"] is False
    assert state["markers"] == []
    assert len(state["stale"]) == 1
    result = hg.validate_handback("gh pr ready", repo)
    assert result["decision"] == "allow"
    assert result["reason"] is None


def test_driver_abandoned_review_session_only_malformed_json(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "f.txt", "x\n")
    path = os.path.join(_superheroes_dir(repo), hg.REVIEW_SESSION_FILE)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("{not json")
    result = hg.validate_handback("gh pr ready", repo)
    assert result["decision"] == "refuse"
    assert result["reason"] == "handback-driver-abandoned"
    assert path in result["detail"]


def test_driver_abandoned_review_session_only_missing_session_dir(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "f.txt", "x\n")
    _write_review_session(repo, sessionDir="/nonexistent/session")
    result = hg.validate_handback("gh pr ready", repo)
    assert result["decision"] == "refuse"
    assert result["reason"] == "handback-driver-abandoned"


def test_pr_inherited_repo_between_pr_and_ready(tmp_path):
    repo, _, _ = _scoped_repo(tmp_path)
    result = hg.validate_handback("gh pr -R other/repo ready", repo)
    assert result["reason"] == "handback-repo-mismatch"


# --- WO-A (#1248 leg a): driver-state gate ----------------------------------------------------

def _forensic_specimen(tmp_path, *, loop_state=None, sidecar=True):
    """Build-lane + review-session with driver journal; optional sidecar."""
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "f.txt", "x\n")
    base_sha = sc.run_git(repo, "rev-parse", "HEAD")
    _commit_file(repo, "g.txt", "y\n")
    session = str(tmp_path / "session")
    _write_build_lane(repo)
    _write_review_session(repo, sessionDir=session)
    _write_driver_journal(session, [
        {"cmd": "next", "phase": "compile", "round": "1", "attempt": "1",
         "outcome": "ok", "ts": "2026-08-09T00:00:01Z"},
        {"cmd": "submit", "phase": "compile", "round": "1", "attempt": "1",
         "outcome": "ok", "ts": "2026-08-09T00:00:02Z"},
    ])
    if loop_state is not False:
        _write_loop_state(session, **(loop_state or {"terminal": None}))
    if sidecar:
        _write_sidecar(repo, session, _certified_receipt(), base_ref="main", base_sha=base_sha)
    return repo, session, base_sha


def test_specimen_shape_refuses(tmp_path):
    repo, _, _ = _forensic_specimen(tmp_path)
    result = hg.validate_handback("gh pr ready", repo)
    assert result["decision"] == "refuse"
    assert result["reason"] == "handback-driver-abandoned"


def test_driver_abandoned_unreadable_review_session_marker(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "f.txt", "x\n")
    session = str(tmp_path / "session")
    _write_build_lane(repo)
    path = os.path.join(_superheroes_dir(repo), hg.REVIEW_SESSION_FILE)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("{not json")
    result = hg.validate_handback("gh pr ready", repo)
    assert result["reason"] == "handback-driver-abandoned"
    assert path in result["detail"]


def test_driver_abandoned_invalid_review_session_marker(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "f.txt", "x\n")
    session = str(tmp_path / "session")
    _write_build_lane(repo)
    _write_review_session(repo, sessionDir="/nonexistent/session")
    result = hg.validate_handback("gh pr ready", repo)
    assert result["reason"] == "handback-driver-abandoned"


def test_driver_abandoned_loop_state_missing(tmp_path):
    repo, _, _ = _forensic_specimen(tmp_path, loop_state=False, sidecar=False)
    result = hg.validate_handback("gh pr ready", repo)
    assert result["reason"] == "handback-driver-abandoned"
    assert "loop-state.json is missing" in result["detail"]


def test_driver_abandoned_loop_state_unparseable(tmp_path):
    repo, session, _ = _forensic_specimen(tmp_path, loop_state=False, sidecar=False)
    with open(os.path.join(session, RD.STATE_FILE), "w", encoding="utf-8") as fh:
        fh.write("not-json")
    result = hg.validate_handback("gh pr ready", repo)
    assert result["reason"] == "handback-driver-abandoned"
    assert "loop-state.json unreadable" in result["detail"]


def test_driver_abandoned_null_terminal(tmp_path):
    repo, _, _ = _forensic_specimen(tmp_path, loop_state={"terminal": None}, sidecar=False)
    result = hg.validate_handback("gh pr ready", repo)
    assert result["reason"] == "handback-driver-abandoned"
    assert "terminal is null" in result["detail"]


@pytest.mark.parametrize("terminal", [None, "", "missing-key"])
def test_driver_abandoned_empty_terminal_variants(tmp_path, terminal):
    repo, session, _ = _forensic_specimen(tmp_path, loop_state=False, sidecar=False)
    if terminal == "missing-key":
        _write_loop_state(session)
        with open(os.path.join(session, RD.STATE_FILE), encoding="utf-8") as fh:
            state = json.load(fh)
        del state["terminal"]
        with open(os.path.join(session, RD.STATE_FILE), "w", encoding="utf-8") as fh:
            json.dump(state, fh)
    else:
        _write_loop_state(session, terminal=terminal)
    result = hg.validate_handback("gh pr ready", repo)
    assert result["reason"] == "handback-driver-abandoned"


def test_session_mismatch_refuses(tmp_path):
    repo, session, base_sha = _forensic_specimen(
        tmp_path, loop_state={"terminal": "converged"})
    other = str(tmp_path / "other-session")
    _write_loop_state(other, terminal="converged")
    sidecar_path = os.path.join(_superheroes_dir(repo), hg._SIDECAR_FILE)
    with open(sidecar_path, encoding="utf-8") as fh:
        sidecar = json.load(fh)
    sidecar["sessionDir"] = other
    with open(sidecar_path, "w", encoding="utf-8") as fh:
        json.dump(sidecar, fh)
    result = hg.validate_handback("gh pr ready", repo)
    assert result["reason"] == "handback-session-mismatch"


def test_no_review_session_marker_unchanged_no_receipt(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "f.txt", "x\n")
    _write_build_lane(repo)
    result = hg.validate_handback("gh pr ready", repo)
    assert result["reason"] == "handback-no-receipt"


def test_non_null_terminal_passes_driver_check_to_receipt_path(tmp_path):
    repo, session, base_sha = _forensic_specimen(
        tmp_path, loop_state={"terminal": "converged"})
    result = hg.validate_handback("gh pr ready", repo)
    assert result["decision"] == "allow"


# --- bite-proof -------------------------------------------------------------------------------

def test_bite_scope_silence(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "f.txt", "x\n")
    red = hg.validate_handback("gh pr ready", repo)
    assert red["decision"] == "allow" and red["reason"] is None
    mod = patched_module(hg, [
        ('        return _allow()\n\n    for inv in guarded:',
         '        return _refuse("handback-no-receipt", "scope silence broken", subject=_empty_subject())\n\n    for inv in guarded:'),
    ])
    green = mod.validate_handback("gh pr ready", repo)
    assert green["decision"] == "refuse"
    assert green["reason"] == "handback-no-receipt"


def test_bite_no_receipt(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "f.txt", "x\n")
    _write_build_lane(repo)
    red = hg.validate_handback("gh pr ready", repo)
    assert red["reason"] == "handback-no-receipt"
    mod = patched_module(hg, [
        ('if not os.path.isfile(sidecar_path):',
         'if False and not os.path.isfile(sidecar_path):'),
    ])
    green = mod.validate_handback("gh pr ready", repo)
    assert green["reason"] != "handback-no-receipt"


def test_bite_verdict_allowlist(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "f.txt", "x\n")
    base_sha = sc.run_git(repo, "rev-parse", "HEAD")
    _commit_file(repo, "g.txt", "y\n")
    session = str(tmp_path / "session")
    _write_build_lane(repo)
    _write_sidecar(repo, session, _certified_receipt(verdict="halted"), verdict="halted",
                    base_ref="main", base_sha=base_sha)
    red = hg.validate_handback("gh pr ready", repo)
    assert red["reason"] == "handback-verdict-not-allowlisted"
    mod = patched_module(hg, [
        ('    if verdict not in HANDBACK_VERDICT_ALLOWLIST:\n'
         '        return False, "verdict-not-allowlisted"',
         '    if False and verdict not in HANDBACK_VERDICT_ALLOWLIST:\n'
         '        return False, "verdict-not-allowlisted"'),
    ])
    green = mod.validate_handback("gh pr ready", repo)
    assert green["decision"] == "allow"


def test_bite_head_binding(tmp_path):
    repo, session, base_sha = _scoped_repo(tmp_path)
    sidecar_path = os.path.join(_superheroes_dir(repo), hg._SIDECAR_FILE)
    with open(sidecar_path, encoding="utf-8") as fh:
        sidecar = json.load(fh)
    sidecar["headSha"] = "0" * 40
    with open(sidecar_path, "w", encoding="utf-8") as fh:
        json.dump(sidecar, fh)
    red = hg.validate_handback("gh pr ready", repo)
    assert red["reason"] == "handback-head-mismatch"
    mod = patched_module(hg, [
        ('if head_sha != sidecar.get("headSha"):',
         'if False and head_sha != sidecar.get("headSha"):'),
    ])
    green = mod.validate_handback("gh pr ready", repo)
    assert green["decision"] == "allow"


def test_bite_repo_binding_inline_gh_repo(tmp_path):
    repo, _, _ = _scoped_repo(tmp_path)
    red = hg.validate_handback("GH_REPO=other/repo gh pr ready", repo)
    assert red["reason"] == "handback-repo-mismatch"
    mod = patched_module(hg, [
        ('if subject.get("repo") and subject["repo"] != sidecar.get("repoId"):',
         'if False and subject.get("repo") and subject["repo"] != sidecar.get("repoId"):'),
    ])
    green = mod.validate_handback("GH_REPO=other/repo gh pr ready", repo)
    assert green["decision"] == "allow"


def test_bite_subject_unresolvable_selector(tmp_path):
    repo, _, _ = _scoped_repo(tmp_path)
    red = hg.validate_handback("gh pr ready 42", repo)
    assert red["reason"] == "handback-subject-unresolvable"
    mod = patched_module(hg, [
        ('if action == "pr-ready" and pr.get("selector"):',
         'if False and action == "pr-ready" and pr.get("selector"):'),
    ])
    green = mod.validate_handback("gh pr ready 42", repo)
    assert green["decision"] == "allow"


def test_bite_draft_undo_passthrough(tmp_path):
    repo, _, _ = _scoped_repo(tmp_path)
    assert hg.validate_handback("gh pr create --draft", repo)["decision"] == "allow"
    assert hg.validate_handback("gh pr ready --undo", repo)["decision"] == "allow"
    mod = patched_module(hg, [
        ('        if inv["action"] == "pr-create" and inv.get("draft"):\n            continue',
         '        if False and inv["action"] == "pr-create" and inv.get("draft"):\n            continue'),
    ])
    red = mod.validate_handback("gh pr create --draft", repo)
    assert red["decision"] == "refuse"


def test_bite_unknown_option_refuses(tmp_path):
    repo, _, _ = _scoped_repo(tmp_path)
    red = hg.validate_handback("gh pr create --totally-unknown --base main", repo)
    assert red["reason"] == "handback-inspection-failed"
    mod = patched_module(hg, [
        ('        if inv.get("unrecognized") or inv["action"] == "unrecognized":',
         '        if False and (inv.get("unrecognized") or inv["action"] == "unrecognized"):'),
    ])
    green = mod.validate_handback("gh pr create --totally-unknown --base main", repo)
    assert green["decision"] == "allow"


def test_bite_explicit_false_boolean():
    assert hg.parse_gh_invocations("gh pr create --draft=false")[0]["draft"] is False
    mod = patched_module(hg, [
        ('def _parse_bool_value(raw):\n'
         '    """Parse an explicit boolean flag value. None means unparseable."""\n'
         '    if raw is None:',
         'def _parse_bool_value(raw):\n'
         '    """Parse an explicit boolean flag value. None means unparseable."""\n'
         '    return True\n'
         '    if raw is None:'),
    ])
    inv = mod.parse_gh_invocations("gh pr create --draft=false")
    assert inv[0]["draft"] is True


def test_bite_inherited_repo_flag(tmp_path):
    repo, _, _ = _scoped_repo(tmp_path)
    red = hg.validate_handback("gh -R other/repo pr ready", repo)
    assert red["reason"] == "handback-repo-mismatch"
    mod = patched_module(hg, [
        ('    if global_repo and parsed.get("repo") is None:\n        parsed["repo"] = global_repo',
         '    if False and global_repo and parsed.get("repo") is None:\n        parsed["repo"] = global_repo'),
    ])
    green = mod.validate_handback("gh -R other/repo pr ready", repo)
    assert green["decision"] == "allow"


def test_bite_host_qualified_repo():
    inv = hg.parse_gh_invocations("gh --repo ghe.example.com/org/repo pr ready")[0]
    red = hg.command_subject(inv)["repo"]
    assert red == "ghe.example.com/org/repo"
    mod = patched_module(hg, [
        ('if _GH_HOST_REPO_SLUG.match(value):',
         'if False and _GH_HOST_REPO_SLUG.match(value):'),
    ])
    green = mod.command_subject(inv)["repo"]
    assert green is None


def test_bite_stale_marker_silence(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    _write_build_lane(repo, repoRoot="/stale")
    red = hg.validate_handback("gh pr ready", repo)
    assert red["decision"] == "allow"
    mod = patched_module(hg, [
        ('    if not scope["inScope"]:\n'
         '        # §4.2: neither valid marker → silent allow; stale alone is out of scope too.\n'
         '        return _allow()',
         '    if not scope["inScope"]:\n'
         '        return _refuse("handback-no-receipt", "stale silence broken")'),
    ])
    green = mod.validate_handback("gh pr ready", repo)
    assert green["decision"] == "refuse"


def test_bite_receipt_delegation(tmp_path):
    repo, session, base_sha = _scoped_repo(tmp_path)
    receipt_path = os.path.join(session, RD.RECEIPT_FILE)
    with open(receipt_path, encoding="utf-8") as fh:
        receipt = json.load(fh)
    del receipt["certificationShape"]
    receipt_bytes = json.dumps(receipt).encode("utf-8")
    with open(receipt_path, "wb") as fh:
        fh.write(receipt_bytes)
    sidecar_path = os.path.join(_superheroes_dir(repo), hg._SIDECAR_FILE)
    with open(sidecar_path, encoding="utf-8") as fh:
        sidecar = json.load(fh)
    sidecar["receiptSha256"] = hashlib.sha256(receipt_bytes).hexdigest()
    with open(sidecar_path, "w", encoding="utf-8") as fh:
        json.dump(sidecar, fh)
    red = hg.validate_handback("gh pr ready", repo)
    assert red["reason"] == "handback-receipt-unreadable"
    mod = patched_module(hg, [
        ('    ok, why = RD.validate_receipt(receipt)',
         '    ok, why = True, None  # bite: skip validate_receipt'),
    ])
    green = mod.validate_handback("gh pr ready", repo)
    assert green["decision"] == "allow"


def test_bite_branch_binding(tmp_path):
    repo, session, base_sha = _scoped_repo(tmp_path)
    sidecar_path = os.path.join(_superheroes_dir(repo), hg._SIDECAR_FILE)
    with open(sidecar_path, encoding="utf-8") as fh:
        sidecar = json.load(fh)
    sidecar["branch"] = "other-branch"
    with open(sidecar_path, "w", encoding="utf-8") as fh:
        json.dump(sidecar, fh)
    red = hg.validate_handback("gh pr ready", repo)
    assert red["reason"] == "handback-branch-mismatch"
    mod = patched_module(hg, [
        ('    if branch and branch != sidecar.get("branch"):',
         '    if False and branch and branch != sidecar.get("branch"):'),
    ])
    green = mod.validate_handback("gh pr ready", repo)
    assert green["decision"] == "allow"


def test_bite_attached_short_repo(tmp_path):
    repo, _, _ = _scoped_repo(tmp_path)
    red = hg.validate_handback("gh pr create -tupdate --base main", repo)
    assert red["decision"] == "allow"
    mod = patched_module(hg, [
        ('            rest = letters[i + 1:]\n'
         '            parts.append((flag, rest if rest else None))',
         '            rest = letters[i + 1:]\n'
         '            parts.append((flag, None))'),
    ])
    green = mod.validate_handback("gh pr create -tupdate --base main", repo)
    assert green["decision"] == "refuse"


def test_bite_url_only_from_operands(tmp_path):
    repo, _, _ = _scoped_repo(tmp_path)
    url = "https://github.com/other/repo/pull/1"
    red = hg.validate_handback("gh pr create --body %s --base main" % url, repo)
    assert red["decision"] == "allow"
    mod = patched_module(hg, [
        ('    for operand in pr.get("operands") or []:',
         '    for operand in ([pr.get("body")] if pr.get("body") else []) + (pr.get("operands") or []):'),
    ])
    green = mod.validate_handback("gh pr create --body %s --base main" % url, repo)
    assert green["reason"] == "handback-repo-mismatch"


def test_bite_non_mutating_leaves_family(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "f.txt", "x\n")
    _write_build_lane(repo)
    red = hg.validate_handback("gh pr ready --help", repo)
    assert red["decision"] == "allow"
    mod = patched_module(hg, [
        ('        if inv.get("non_mutating"):\n            continue',
         '        if False and inv.get("non_mutating"):\n            continue'),
    ])
    green = mod.validate_handback("gh pr ready --help", repo)
    assert green["reason"] == "handback-no-receipt"


def test_bite_branch_bound_marker_staleness(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "f.txt", "x\n")
    _write_build_lane(repo, branch="other-branch")
    red = hg.validate_handback("gh pr ready", repo)
    assert red["decision"] == "allow"
    mod = patched_module(hg, [
        ('    for key in ("issue", "declaredAt", "repoRoot", "branch"):\n'
         '        if not isinstance(obj.get(key), str) or not obj.get(key):\n'
         '            return False, "missing or empty field: %s" % key\n'
         '    ok, why = _marker_repo_matches(obj["repoRoot"], repo_root)\n'
         '    if not ok:\n'
         '        return False, why\n'
         '    ok, why = _marker_branch_matches(obj["branch"], repo_root)',
         '    for key in ("issue", "declaredAt", "repoRoot", "branch"):\n'
         '        if not isinstance(obj.get(key), str) or not obj.get(key):\n'
         '            return False, "missing or empty field: %s" % key\n'
         '    ok, why = _marker_repo_matches(obj["repoRoot"], repo_root)\n'
         '    if not ok:\n'
         '        return False, why\n'
         '    ok, why = True, None  # bite: skip branch staleness'),
    ])
    green = mod.validate_handback("gh pr ready", repo)
    assert green["decision"] == "refuse"


def test_bite_diff_invocation_matches_production(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "base.txt", "base\n", msg="base")
    base_sha = sc.run_git(repo, "rev-parse", "HEAD")
    _commit_file(repo, "café.txt", "feature\n", msg="feature")
    session = str(tmp_path / "session")
    _write_build_lane(repo)
    _write_sidecar(repo, session, _certified_receipt(), base_ref="main", base_sha=base_sha)
    red = hg.validate_handback("gh pr ready", repo)
    assert red["decision"] == "allow"
    mod = patched_module(hg, [
        ('            ["git", "-C", repo_root, "diff", "%s...HEAD" % base_sha],',
         '            ["git", "-C", repo_root, "-c", "core.quotepath=false", "diff", "--no-color", "--no-ext-diff", "%s...HEAD" % base_sha],'),
    ])
    green = mod.validate_handback("gh pr ready", repo)
    assert green["reason"] == "handback-diff-mismatch"


def test_bite_base_ref_round_trip(tmp_path):
    repo, session, base_sha = _scoped_repo(tmp_path)
    sidecar_path = os.path.join(_superheroes_dir(repo), hg._SIDECAR_FILE)
    with open(sidecar_path, encoding="utf-8") as fh:
        sidecar = json.load(fh)
    sidecar["baseRef"] = base_sha
    with open(sidecar_path, "w", encoding="utf-8") as fh:
        json.dump(sidecar, fh)
    red = hg.validate_handback("gh pr create --base main", repo)
    assert red["reason"] == "handback-receipt-unreadable"
    mod = patched_module(hg, [
        ('    if _LEGACY_BASE_SHA.match(sidecar.get("baseRef") or ""):',
         '    if False and _LEGACY_BASE_SHA.match(sidecar.get("baseRef") or ""):'),
        ('        if cmd_base != sidecar_base:',
         '        if False and cmd_base != sidecar_base:'),
    ])
    green = mod.validate_handback("gh pr create --base main", repo)
    assert green["decision"] == "allow"
