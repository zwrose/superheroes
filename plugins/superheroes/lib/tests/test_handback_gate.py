"""Tests for lib/handback_gate.py — handback receipt gate (#624 §4).

Uses real git repositories in tmp_path for binding paths; parser/subject tests are pure.
"""
import hashlib
import json
import os
import subprocess

import pytest

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
    }
    obj.update(over)
    with open(os.path.join(d, hg.REVIEW_SESSION_FILE), "w", encoding="utf-8") as fh:
        json.dump(obj, fh)


def _diff_sha256(repo, base_sha):
    r = subprocess.run(
        ["git", "-C", repo, "-c", "core.quotepath=false",
         "diff", "--no-color", "--no-ext-diff", "%s...HEAD" % base_sha],
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
    assert state == {"inScope": False, "markers": [], "stale": []}


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
        ["git", "-C", repo, "-c", "core.quotepath=false",
         "diff", "--no-color", "--no-ext-diff", "%s...HEAD" % base_sha],
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


# --- bite-proof -------------------------------------------------------------------------------

def _neutralize(path, old, new):
    with open(path, encoding="utf-8") as fh:
        src = fh.read()
    patched = src.replace(old, new, 1)
    assert patched != src, "neutralization target not found"
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(patched)
    return src


def _restore(path, src):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(src)
    import importlib
    import handback_gate as mod
    importlib.reload(mod)
    return mod


def test_bite_scope_silence(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "f.txt", "x\n")
    red = hg.validate_handback("gh pr ready", repo)
    assert red["decision"] == "allow" and red["reason"] is None
    path = hg.__file__
    src = _neutralize(path,
                      '        return _allow()\n\n    for inv in guarded:',
                      '        return _refuse("handback-no-receipt", "scope silence broken", subject=_empty_subject())\n\n    for inv in guarded:')
    try:
        import importlib
        mod = importlib.reload(hg)
        green = mod.validate_handback("gh pr ready", repo)
        assert green["decision"] == "refuse"
        assert green["reason"] == "handback-no-receipt"
    finally:
        _restore(path, src)


def test_bite_no_receipt(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    _commit_file(repo, "f.txt", "x\n")
    _write_build_lane(repo)
    red = hg.validate_handback("gh pr ready", repo)
    assert red["reason"] == "handback-no-receipt"
    path = hg.__file__
    src = _neutralize(path,
                      'if not os.path.isfile(sidecar_path):',
                      'if False and not os.path.isfile(sidecar_path):')
    try:
        import importlib
        mod = importlib.reload(hg)
        green = mod.validate_handback("gh pr ready", repo)
        assert green["reason"] != "handback-no-receipt"
    finally:
        _restore(path, src)


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
    path = hg.__file__
    with open(path, encoding="utf-8") as fh:
        src = fh.read()
    patched = src.replace(
        '    if verdict not in HANDBACK_VERDICT_ALLOWLIST:\n'
        '        return False, "verdict-not-allowlisted"',
        '    if False and verdict not in HANDBACK_VERDICT_ALLOWLIST:\n'
        '        return False, "verdict-not-allowlisted"',
        1,
    )
    assert patched != src
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(patched)
    try:
        import importlib
        mod = importlib.reload(hg)
        green = mod.validate_handback("gh pr ready", repo)
        assert green["decision"] == "allow"
    finally:
        _restore(path, src)


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
    path = hg.__file__
    src = _neutralize(path,
                      'if head_sha != sidecar.get("headSha"):',
                      'if False and head_sha != sidecar.get("headSha"):')
    try:
        import importlib
        mod = importlib.reload(hg)
        green = mod.validate_handback("gh pr ready", repo)
        assert green["decision"] == "allow"
    finally:
        _restore(path, src)


def test_bite_repo_binding_inline_gh_repo(tmp_path):
    repo, _, _ = _scoped_repo(tmp_path)
    red = hg.validate_handback("GH_REPO=other/repo gh pr ready", repo)
    assert red["reason"] == "handback-repo-mismatch"
    path = hg.__file__
    src = _neutralize(path,
                      'if subject.get("repo") and subject["repo"] != sidecar.get("repoId"):',
                      'if False and subject.get("repo") and subject["repo"] != sidecar.get("repoId"):')
    try:
        import importlib
        mod = importlib.reload(hg)
        green = mod.validate_handback("GH_REPO=other/repo gh pr ready", repo)
        assert green["decision"] == "allow"
    finally:
        _restore(path, src)


def test_bite_subject_unresolvable_selector(tmp_path):
    repo, _, _ = _scoped_repo(tmp_path)
    red = hg.validate_handback("gh pr ready 42", repo)
    assert red["reason"] == "handback-subject-unresolvable"
    path = hg.__file__
    src = _neutralize(path,
                      'if action == "pr-ready" and pr.get("selector"):',
                      'if False and action == "pr-ready" and pr.get("selector"):')
    try:
        import importlib
        mod = importlib.reload(hg)
        green = mod.validate_handback("gh pr ready 42", repo)
        assert green["decision"] == "allow"
    finally:
        _restore(path, src)


def test_bite_draft_undo_passthrough(tmp_path):
    repo, _, _ = _scoped_repo(tmp_path)
    assert hg.validate_handback("gh pr create --draft", repo)["decision"] == "allow"
    assert hg.validate_handback("gh pr ready --undo", repo)["decision"] == "allow"
    path = hg.__file__
    src = _neutralize(path,
                      'and not (inv["action"] == "pr-create" and inv.get("draft"))]',
                      ']')
    try:
        import importlib
        mod = importlib.reload(hg)
        red = mod.validate_handback("gh pr create --draft", repo)
        assert red["decision"] == "refuse"
    finally:
        _restore(path, src)


def test_bite_unknown_flag_does_not_shift_tokens():
    red = hg.parse_gh_invocations("gh pr create --fill --draft")
    assert red[0]["draft"] is True
    path = hg.__file__
    src = _neutralize(path,
                      '            # unknown flag: invariant (a) — no state change, width already set\n\n        i += width',
                      '            # unknown flag: invariant (a) — no state change, width already set\n\n        i += width + (1 if tok == "--fill" else 0)')
    try:
        import importlib
        mod = importlib.reload(hg)
        green = mod.parse_gh_invocations("gh pr create --fill --draft")
        assert green[0]["draft"] is False
    finally:
        _restore(path, src)


def test_bite_explicit_false_boolean():
    assert hg.parse_gh_invocations("gh pr create --draft=false")[0]["draft"] is False
    path = hg.__file__
    src = _neutralize(path,
                      'def _parse_bool_value(raw):\n'
                      '    """Parse an explicit boolean flag value. None means unparseable."""\n'
                      '    if raw is None:',
                      'def _parse_bool_value(raw):\n'
                      '    """Parse an explicit boolean flag value. None means unparseable."""\n'
                      '    return True\n'
                      '    if raw is None:')
    try:
        import importlib
        mod = importlib.reload(hg)
        inv = mod.parse_gh_invocations("gh pr create --draft=false")
        assert inv[0]["draft"] is True
    finally:
        _restore(path, src)


def test_bite_inherited_repo_flag(tmp_path):
    repo, _, _ = _scoped_repo(tmp_path)
    red = hg.validate_handback("gh -R other/repo pr ready", repo)
    assert red["reason"] == "handback-repo-mismatch"
    path = hg.__file__
    src = _neutralize(path,
                      'def _parse_gh_globals(tokens):',
                      'def _parse_gh_globals(tokens):\n    return None, None, tokens[1:], False\n\ndef _parse_gh_globals_DISABLED(tokens):')
    try:
        import importlib
        mod = importlib.reload(hg)
        green = mod.validate_handback("gh -R other/repo pr ready", repo)
        assert green["decision"] == "allow"
    finally:
        _restore(path, src)


def test_bite_host_qualified_repo():
    inv = hg.parse_gh_invocations("gh --repo ghe.example.com/org/repo pr ready")[0]
    red = hg.command_subject(inv)["repo"]
    assert red == "ghe.example.com/org/repo"
    path = hg.__file__
    src = _neutralize(path,
                      'if _GH_HOST_REPO_SLUG.match(value):',
                      'if False and _GH_HOST_REPO_SLUG.match(value):')
    try:
        import importlib
        mod = importlib.reload(hg)
        green = mod.command_subject(inv)["repo"]
        assert green is None
    finally:
        _restore(path, src)


def test_bite_stale_marker_silence(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    _write_build_lane(repo, repoRoot="/stale")
    red = hg.validate_handback("gh pr ready", repo)
    assert red["decision"] == "allow"
    path = hg.__file__
    src = _neutralize(path,
                      '    if not scope["inScope"]:\n'
                      '        # §4.2: neither valid marker → silent allow; stale alone is out of scope too.\n'
                      '        return _allow()',
                      '    if not scope["inScope"]:\n'
                      '        return _refuse("handback-no-receipt", "stale silence broken")')
    try:
        import importlib
        mod = importlib.reload(hg)
        green = mod.validate_handback("gh pr ready", repo)
        assert green["decision"] == "refuse"
    finally:
        _restore(path, src)


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
    path = hg.__file__
    src = _neutralize(path,
                      '    ok, why = RD.validate_receipt(receipt)',
                      '    ok, why = True, None  # bite: skip validate_receipt')
    try:
        import importlib
        mod = importlib.reload(hg)
        green = mod.validate_handback("gh pr ready", repo)
        assert green["decision"] == "allow"
    finally:
        _restore(path, src)


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
    path = hg.__file__
    src = _neutralize(path,
                      '    if branch and branch != sidecar.get("branch"):',
                      '    if False and branch and branch != sidecar.get("branch"):')
    try:
        import importlib
        mod = importlib.reload(hg)
        green = mod.validate_handback("gh pr ready", repo)
        assert green["decision"] == "allow"
    finally:
        _restore(path, src)


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
    path = hg.__file__
    with open(path, encoding="utf-8") as fh:
        src = fh.read()
    patched = src.replace(
        '    if _LEGACY_BASE_SHA.match(sidecar.get("baseRef") or ""):',
        '    if False and _LEGACY_BASE_SHA.match(sidecar.get("baseRef") or ""):',
        1,
    ).replace(
        '        if cmd_base != sidecar_base:',
        '        if False and cmd_base != sidecar_base:',
        1,
    )
    assert patched != src
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(patched)
    try:
        import importlib
        mod = importlib.reload(hg)
        green = mod.validate_handback("gh pr create --base main", repo)
        assert green["decision"] == "allow"
    finally:
        _restore(path, src)
