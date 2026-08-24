"""Drift pin: order-input ownership docs bound to round_driver materialization (#1107 WO-R2-D)."""
import os
import re
import tempfile

import round_driver as RD
import round_records as RR

_HERE = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_ROOT = os.path.normpath(os.path.join(_HERE, "..", ".."))

_ROUND_DRIVER_DOC = "skills/review-code/reference/round-driver.md"
_SETUP_DOC = "skills/review-code/reference/setup.md"

_PROBE_SESSION = None  # set per derivation call — see _probe_session_dir
_PROBE_RND = 1
_PROBE_STATE = {
    "reviewedDiff": "diff --git a/f b/f\n",
    "headDiff": "diff --git a/f b/f\n",
    "_fixBatch": [],
}

# Mutation hook for red-on-old proof only — leave empty in committed code.
_PROBE_EXTRA_ARTIFACT = ""


def _probe_session_dir():
    global _PROBE_SESSION
    if _PROBE_SESSION is None:
        _PROBE_SESSION = tempfile.mkdtemp(prefix="ownership-doc-drift-")
    return _PROBE_SESSION


def _derive_driver_materialized_round_paths():
    """Round-relative paths the driver materializes — derived from round_driver, not hand lists."""
    session_dir = _probe_session_dir()
    rdir = RR.round_dir(session_dir, _PROBE_RND)
    paths = set()
    for fn in (RD._ensure_round_diff, RD._ensure_round_head_diff, RD._ensure_fix_batch_file):
        rel = os.path.relpath(fn(session_dir, _PROBE_RND, _PROBE_STATE), rdir)
        paths.add(rel.replace("\\", "/"))
    roster = ["verifier:c0", "finding::auth.py::12"]
    payloads = {
        RD.P_VERIFIERS: {"clusters": [{"key": "c0"}]},
        RD.P_AUDITS: {"targets": [{"id": "finding::auth.py::12"}]},
        RD.P_SCOPED: {"hunks": {}},
        RD.P_SYNTHESIS: {"findings": []},
    }
    for phase, payload in payloads.items():
        for path, _ in RD._order_sidecar_writes(session_dir, _PROBE_RND, phase, roster, payload):
            rel = os.path.relpath(path, rdir).replace("\\", "/")
            paths.add(rel)
    if _PROBE_EXTRA_ARTIFACT:
        paths.add(_PROBE_EXTRA_ARTIFACT)
    return frozenset(paths)


def _normalize_for_line_wrap(text):
    return re.sub(r"\s+", " ", text).strip()


def _forbidden_claim_present(text, claim):
    return _normalize_for_line_wrap(claim) in _normalize_for_line_wrap(text)


_FORBIDDEN_STALE_CLAIMS = (
    "The driver never creates `head.diff` or `fix-batch.json`",
    "is **not** produced by the driver",
    "orchestrator must write these **before** dispatching a fixer",
)


def _read_plugin(rel):
    path = os.path.join(_PLUGIN_ROOT, rel)
    if not os.path.isfile(path):
        raise AssertionError("doc surface missing or unreadable: %s" % rel)
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _ownership_section(text):
    match = re.search(
        r"\*\*Order-input ownership\.\*\*(.*?)(?=\n## |\Z)",
        text,
        re.DOTALL,
    )
    if not match:
        raise AssertionError(
            "round-driver.md missing **Order-input ownership.** section anchor"
        )
    return match.group(0)


def _doc_needle_for_artifact(rel_path):
    """Ownership-section substring that must appear for one code-derived artifact path."""
    if rel_path == "diff.txt":
        return rel_path
    if rel_path == "head.diff":
        return rel_path
    if rel_path == "fix-batch.json":
        return rel_path
    if rel_path.startswith(RD.ORDER_SIDECAR_CLUSTERS_DIR + "/"):
        return "round-<N>/%s/" % RD.ORDER_SIDECAR_CLUSTERS_DIR
    if rel_path.startswith(RD.ORDER_SIDECAR_AUDIT_TARGETS_DIR + "/"):
        return "round-<N>/%s/" % RD.ORDER_SIDECAR_AUDIT_TARGETS_DIR
    if rel_path == RD.ORDER_SIDECAR_SCOPED_HUNKS_FILE:
        return rel_path
    if rel_path == RD.ORDER_SIDECAR_VERIFIED_FILE:
        return rel_path
    return rel_path


def _setup_written_by(path_token):
    text = _read_plugin(_SETUP_DOC)
    pattern = (
        r"\|\s*`[^`]*%s[^`]*`\s*\|\s*([^|]+?)\s*\|"
        % re.escape(path_token)
    )
    match = re.search(pattern, text)
    if not match:
        raise AssertionError(
            "setup.md session-artifact table missing row for %r" % path_token
        )
    return match.group(1).strip().lower()


def test_forbidden_stale_ownership_claims_absent():
    text = _read_plugin(_ROUND_DRIVER_DOC)
    for claim in _FORBIDDEN_STALE_CLAIMS:
        assert not _forbidden_claim_present(text, claim), (
            "round-driver.md reverted to stale ownership claim: %r" % claim
        )


def test_setup_fix_batch_owned_by_driver():
    written_by = _setup_written_by("fix-batch.json")
    assert written_by == "round driver", (
        "setup.md fix-batch.json row must assign round driver ownership, found %r"
        % written_by
    )


def test_round_driver_ownership_covers_code_derived_artifacts():
    derived = _derive_driver_materialized_round_paths()
    section = _ownership_section(_read_plugin(_ROUND_DRIVER_DOC))
    for rel_path in sorted(derived):
        needle = _doc_needle_for_artifact(rel_path)
        assert needle in section, (
            "round-driver.md Order-input ownership missing code-derived artifact "
            "%r (expected needle %r in section)" % (rel_path, needle)
        )


def test_round_driver_assigns_driver_ownership_for_head_diff_and_fix_batch():
    section = _ownership_section(_read_plugin(_ROUND_DRIVER_DOC))
    for artifact, fn_name in (
        ("head.diff", "_ensure_round_head_diff"),
        ("fix-batch.json", "_ensure_fix_batch_file"),
    ):
        assert artifact in section, (
            "round-driver.md Order-input ownership must name driver-materialized %r"
            % artifact
        )
        assert fn_name in section, (
            "round-driver.md must cite driver function %r for %r" % (fn_name, artifact)
        )
    assert "orchestrator still owns the real round diff" in section.lower(), (
        "round-driver.md must preserve orchestrator ownership of diff content"
    )
    assert "replaces" in section.lower() and "fix-batch.json" in section, (
        "round-driver.md must document orchestrator-supplied fix-batch.json replacement"
    )
