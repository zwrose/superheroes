"""#1271 WO-G — disposition ledger, fix-fold head, and fix-content receipt guards."""
import ast
import hashlib
import importlib.util
import json
import os
import subprocess
import sys

import pytest

_TESTS = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_TESTS)


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_LIB, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RD = _load("round_driver")
RC = _load("round_certification")
round_records = _load("round_records")

_ROUND_DRIVER_PY = os.path.join(_LIB, "round_driver.py")


def _cfg(**over):
    base = {"fixerVendor": "claude", "reviewerVendor": "codex", "verifyCommand": None}
    base.update(over)
    return base


def _new_state(**cfg_over):
    state = RD.new_state(_cfg(**cfg_over))
    state["reviewedDiff"] = (
        "diff --git a/src/a.py b/src/a.py\n--- a/src/a.py\n+++ b/src/a.py\n@@ -1 +1 @@\n-x\n+y\n"
    )
    return state


def _is_state_findings_subscript(node):
    if not isinstance(node, ast.Subscript):
        return False
    if not isinstance(node.value, ast.Name) or node.value.id != "state":
        return False
    sl = node.slice
    if isinstance(sl, ast.Constant) and sl.value == "findings":
        return True
    if isinstance(sl, ast.Index) and isinstance(sl.value, ast.Str) and sl.value.s == "findings":
        return True
    return False


def _function_name_for_node(tree, lineno):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end = getattr(node, "end_lineno", node.lineno)
            if node.lineno <= lineno <= end:
                return node.name
    return None


def census_findings_assignment_violations():
    """Return (line, enclosing_function) for state['findings'] = outside _set_findings."""
    with open(_ROUND_DRIVER_PY, encoding="utf-8") as fh:
        source = fh.read()
    tree = ast.parse(source, filename=_ROUND_DRIVER_PY)
    violations = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not _is_state_findings_subscript(target):
                continue
            func = _function_name_for_node(tree, node.lineno)
            if func != "_set_findings":
                violations.append((node.lineno, func))
    return violations


def _git_head(repo):
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip()


def _init_repo(tmp_path, files):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(
        ["git", "init", "-q", "-b", "main", str(repo)],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "t@example.com"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "test"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    for rel, content in files.items():
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content if isinstance(content, bytes) else content.encode("utf-8"))
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "init"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    return repo, _git_head(repo)


def _session_dir(tmp_path, repo, setup_head):
    session_dir = tmp_path / "session"
    session_dir.mkdir()
    meta = {
        "sessionId": "wo-g-head",
        "headSha": setup_head,
        "repoRoot": str(repo),
    }
    with open(session_dir / round_records.META_FILE, "w", encoding="utf-8") as fh:
        json.dump(meta, fh)
        fh.write("\n")
    return session_dir


def test_findings_assignment_chokepoint_census():
    violations = census_findings_assignment_violations()
    assert not violations, (
        "state['findings'] assigned outside _set_findings: %r" % violations
    )


def test_cleared_disposition_findings_remain_in_certification_view():
    fixed = {
        "id": "F-fixed",
        "title": "bounds guard",
        "severity": "Important",
        "file": "src/guard.py",
        "line": 12,
        "disposition": "fixed",
        "dispositionReceipt": {"headSha": "a" * 40, "verifyResult": "pass"},
    }
    open_issue = {
        "id": "F-open",
        "title": "open nit",
        "severity": "Minor",
        "file": "src/other.py",
        "line": 3,
    }
    state = _new_state()
    state["round"] = 2
    state["findings"] = [fixed, open_issue]
    state["_newIssues"] = []
    RD._fold_scoped(state, state["config"], {"findings": []})
    assert state.get("findings") == []
    assert any(
        isinstance(entry, dict) and entry.get("id") == "F-fixed"
        for entry in (state.get("dispositionLedger") or [])
    )
    certified = RC._certification_findings(state)
    ids = {f.get("id") for f in certified if isinstance(f, dict)}
    assert "F-fixed" in ids


def test_fix_fold_records_post_fix_head_sha(tmp_path):
    repo, setup_head = _init_repo(tmp_path, {"src/a.py": b"before\n"})
    session_dir = _session_dir(tmp_path, repo, setup_head)
    path = repo / "src" / "a.py"
    path.write_bytes(b"after fix\n")
    subprocess.run(["git", "add", "src/a.py"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "fix"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    post_fix_head = _git_head(repo)
    assert post_fix_head != setup_head

    state = _new_state(repoRoot=str(repo), headSha=setup_head)
    state["round"] = 1
    state["_fixBatch"] = [{"id": "F1", "file": "src/a.py", "line": 1, "severity": "Important"}]
    state["findings"] = [
        {
            "id": "F1",
            "file": "src/a.py",
            "line": 1,
            "severity": "Important",
            "title": "issue",
            "disposition": "fixed",
            "dispositionReceipt": {"headSha": setup_head, "verifyResult": "pass"},
        }
    ]
    artifact = {"fixes": [{"file": "src/a.py"}], "headDiff": "diff"}
    RD._fold_fixer(state, state["config"], artifact, session_dir=str(session_dir))

    finding = state["findings"][0]
    receipt = finding["dispositionReceipt"]
    assert receipt["fixContentHeadSha"] == post_fix_head
    assert state["config"]["fixFoldHeadSha"] == post_fix_head
    blobs_path = os.path.join(session_dir, RD.HEAD_CONTENT_BLOBS_FILE)
    with open(blobs_path, encoding="utf-8") as fh:
        blobs = json.load(fh)
    assert blobs["headSha"] == post_fix_head
    row = next(r for r in blobs["reads"] if r.get("path") == "src/a.py")
    expected = subprocess.run(
        ["git", "show", "%s:src/a.py" % post_fix_head],
        cwd=repo,
        check=True,
        capture_output=True,
        text=False,
    ).stdout
    assert row["contentDigest"] == hashlib.sha256(expected).hexdigest()


def test_fix_fold_head_resolution_failure_refuses(tmp_path, monkeypatch):
    repo, setup_head = _init_repo(tmp_path, {"src/a.py": b"data\n"})
    session_dir = _session_dir(tmp_path, repo, setup_head)
    state = _new_state(repoRoot=str(repo), headSha=setup_head)
    state["round"] = 1
    state["_fixBatch"] = [{"id": "F1", "file": "src/a.py", "line": 1, "severity": "Important"}]
    state["findings"] = [
        {
            "id": "F1",
            "file": "src/a.py",
            "line": 1,
            "severity": "Important",
            "title": "issue",
            "disposition": "fixed",
            "dispositionReceipt": {"headSha": setup_head, "verifyResult": "pass"},
        }
    ]

    def _fail_rev_parse(_repo_root, *_args, **_kwargs):
        return None

    monkeypatch.setattr(RD.store_core, "run_git", _fail_rev_parse)
    RD._fold_fixer(
        state,
        state["config"],
        {"fixes": [{"file": "src/a.py"}], "headDiff": "diff"},
        session_dir=str(session_dir),
    )

    assert state["rounds"][str(state["round"])]["fixFoldHeadRefused"]
    assert "git rev-parse HEAD failed" in state["rounds"][str(state["round"])]["fixFoldHeadRefused"]
    assert "fixContentHeadSha" not in (state["findings"][0].get("dispositionReceipt") or {})
    assert not os.path.isfile(os.path.join(session_dir, RD.HEAD_CONTENT_BLOBS_FILE))


def test_fix_content_skips_refuted_finding_in_touched_file(tmp_path):
    repo, head = _init_repo(tmp_path, {"src/shared.py": b"original\n"})
    session_dir = _session_dir(tmp_path, repo, head)
    refuted = {
        "id": "R1",
        "file": "src/shared.py",
        "line": 1,
        "severity": "Minor",
        "title": "not a bug",
        "disposition": "refuted",
        "refutedReason": "false positive",
    }
    fixed = {
        "id": "F1",
        "file": "src/shared.py",
        "line": 2,
        "severity": "Important",
        "title": "real bug",
        "disposition": "fixed",
        "dispositionReceipt": {"headSha": head, "verifyResult": "pass"},
    }
    state = _new_state(repoRoot=str(repo), headSha=head)
    state["findings"] = [refuted, fixed]
    state["_fixBatch"] = [fixed]
    RD._record_fix_content_on_findings(
        state,
        str(session_dir),
        {"fixes": [{"file": "src/shared.py"}]},
        head,
    )
    assert "dispositionReceipt" not in refuted
    assert fixed["dispositionReceipt"]["fixContentHeadSha"] == head
    assert fixed["dispositionReceipt"]["fixContentDigest"]


def test_fix_content_requires_existing_receipt_on_fixed_finding(tmp_path):
    repo, head = _init_repo(tmp_path, {"src/a.py": b"content\n"})
    session_dir = _session_dir(tmp_path, repo, head)
    fixed_no_receipt = {
        "id": "F0",
        "file": "src/a.py",
        "line": 1,
        "severity": "Important",
        "title": "missing receipt",
        "disposition": "fixed",
    }
    state = _new_state(repoRoot=str(repo), headSha=head)
    state["findings"] = [fixed_no_receipt]
    RD._record_fix_content_on_findings(
        state,
        str(session_dir),
        {"fixes": [{"file": "src/a.py"}]},
        head,
    )
    assert "dispositionReceipt" not in fixed_no_receipt
