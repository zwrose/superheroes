"""Refusal-token census for handback_gate._receipt_bindings_ok (#1107 WO-C1)."""
import ast
import hashlib
import json
import os

import pytest

import handback_gate as hg
import round_driver as RD
import test_handback_gate as thg

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_HANDBACK_GATE_PATH = os.path.join(_LIB, "handback_gate.py")

# If you added a failure token to _receipt_bindings_ok, give it a disposition in the
# mapping below and bump the count in test_receipt_bindings_ok_failure_token_count.
_BINDING_FAILURE_TOKENS = (
    ("receipt-invalid:receipt is not an object", "handback-receipt-unreadable"),
    ("receipt-invalid:receipt missing required key 'rounds'", "handback-receipt-unreadable"),
    ("receipt-interim-not-handback-evidence", "receipt-interim-not-handback-evidence"),
    ("verdict-mismatch", "handback-verdict-not-allowlisted"),
    ("verdict-not-allowlisted", "handback-verdict-not-allowlisted"),
    ("no-certification", "handback-verdict-not-allowlisted"),
    ("no-attestation", "handback-verdict-not-allowlisted"),
)


def _is_false_literal(node):
    if isinstance(node, ast.Constant):
        return node.value is False
    if isinstance(node, ast.NameConstant):
        return node.value is False
    return False


def _count_binding_failure_returns(tree):
    count = 0
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "_receipt_bindings_ok":
            for child in ast.walk(node):
                if not isinstance(child, ast.Return) or child.value is None:
                    continue
                val = child.value
                if isinstance(val, ast.Tuple) and len(val.elts) >= 2:
                    if _is_false_literal(val.elts[0]):
                        count += 1
            return count
    raise AssertionError("_receipt_bindings_ok not found in handback_gate.py")


def test_receipt_bindings_ok_failure_token_count():
    with open(_HANDBACK_GATE_PATH, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=_HANDBACK_GATE_PATH)
    assert _count_binding_failure_returns(tree) == 7


def _update_receipt_and_sidecar_hash(repo, session, receipt_obj):
    receipt_path = os.path.join(session, RD.RECEIPT_FILE)
    receipt_bytes = json.dumps(receipt_obj).encode("utf-8")
    with open(receipt_path, "wb") as fh:
        fh.write(receipt_bytes)
    sidecar_path = os.path.join(thg._superheroes_dir(repo), hg._SIDECAR_FILE)
    with open(sidecar_path, encoding="utf-8") as fh:
        sidecar = json.load(fh)
    sidecar["receiptSha256"] = hashlib.sha256(receipt_bytes).hexdigest()
    with open(sidecar_path, "w", encoding="utf-8") as fh:
        json.dump(sidecar, fh)


def _cfg():
    diff = ("diff --git a/f.py b/f.py\nindex 1..2 100644\n--- a/f.py\n+++ b/f.py\n"
            "@@ -1 +1,2 @@\n-old\n+new\n+more\n")
    return {"leg": "code", "vendors": ["claude", "codex"], "diff": diff, "fixerVendor": "claude"}


@pytest.mark.parametrize("token,expected_reason", _BINDING_FAILURE_TOKENS)
def test_binding_failure_token_surfaces_declared_reason(tmp_path, token, expected_reason):
    if token == "receipt-invalid:receipt is not an object":
        repo, _, _ = thg._scoped_repo(tmp_path)
        _update_receipt_and_sidecar_hash(repo, str(tmp_path / "session"), [1, 2, 3])
    elif token == "receipt-invalid:receipt missing required key 'rounds'":
        repo, _, _ = thg._scoped_repo(tmp_path)
        _update_receipt_and_sidecar_hash(repo, str(tmp_path / "session"), {})
    elif token == "receipt-interim-not-handback-evidence":
        interim = RD.build_interim_receipt(RD.new_state(_cfg()), None, "tripwire")
        repo = thg._init_repo(tmp_path / "repo")
        thg._commit_file(repo, "base.txt", "base\n", msg="base")
        base_sha = thg.sc.run_git(repo, "rev-parse", "HEAD")
        thg._commit_file(repo, "feature.txt", "feature\n", msg="feature")
        session = str(tmp_path / "session")
        thg._write_build_lane(repo)
        thg._write_sidecar(repo, session, interim, verdict="converged", base_ref="main", base_sha=base_sha)
    elif token == "verdict-mismatch":
        repo, session, _ = thg._scoped_repo(tmp_path)
        receipt_path = os.path.join(session, RD.RECEIPT_FILE)
        with open(receipt_path, encoding="utf-8") as fh:
            receipt = json.load(fh)
        receipt["verdict"] = "halted"
        _update_receipt_and_sidecar_hash(repo, session, receipt)
    elif token == "verdict-not-allowlisted":
        repo = thg._init_repo(tmp_path / "repo")
        thg._commit_file(repo, "f.txt", "x\n")
        base_sha = thg.sc.run_git(repo, "rev-parse", "HEAD")
        thg._commit_file(repo, "g.txt", "y\n")
        session = str(tmp_path / "session")
        thg._write_build_lane(repo)
        thg._write_sidecar(
            repo, session, thg._certified_receipt(verdict="halted"),
            verdict="halted", base_ref="main", base_sha=base_sha,
        )
    elif token in ("no-certification", "no-attestation"):
        repo, _, _ = thg._scoped_repo(tmp_path)
        original = hg._receipt_bindings_ok

        def _patched(sidecar, receipt):
            return False, token

        hg._receipt_bindings_ok = _patched
        try:
            result = hg.validate_handback("gh pr ready", repo)
        finally:
            hg._receipt_bindings_ok = original
        assert result["decision"] == "refuse"
        assert result["reason"] == expected_reason
        return
    else:
        pytest.fail("unhandled census token %r" % token)

    result = hg.validate_handback("gh pr ready", repo)
    assert result["decision"] == "refuse"
    assert result["reason"] == expected_reason


@pytest.mark.parametrize("bind_why", [None, ""])
def test_binding_failure_fail_closed_edges(tmp_path, bind_why, monkeypatch):
    repo, _, _ = thg._scoped_repo(tmp_path)
    monkeypatch.setattr(hg, "_receipt_bindings_ok", lambda _sidecar, _receipt: (False, bind_why))
    result = hg.validate_handback("gh pr ready", repo)
    assert result["decision"] == "refuse"
    assert result["reason"] == "handback-verdict-not-allowlisted"
