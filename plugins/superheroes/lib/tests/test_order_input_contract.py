"""Order-input contract guards (#1107 WO-A): guidance key sync, head-diff materialization,
readable-input registry census."""
import json
import os

import pytest

import round_orders as RO
import round_phases as RP
import round_records as RR

_HERE = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_ROOT = os.path.normpath(os.path.join(_HERE, "..", ".."))
_LIB = os.path.normpath(os.path.join(_HERE, ".."))

import round_driver as RD  # noqa: E402

_GUIDANCE_COPY_SURFACES = [
    "rubric/orders/dispatch-fixer.md",
    "lib/tests/fixtures/orders/golden/dispatch-fixer.txt",
    "skills/review-code/reference/auto-fix-loop.md",
]

_TRADEOFF = {"title": "widen the API", "severity": "Important",
             "file": "f.py", "line": 1, "tradeoff": True}
_TRADEOFF_ID = "f.py::widen the api@L1"


def _read(rel):
    path = os.path.join(_PLUGIN_ROOT, rel)
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _cfg(tmp_path):
    return {"repoRoot": str(tmp_path), "verifyCommand": "none"}


def _judgment_state():
    state = RD.new_state(_cfg(os.path.join("/tmp", "judgment-probe")))
    RD._route_judgment_blockers(state, [dict(_TRADEOFF)])
    return state


def _minimal_paths(session_dir):
    return {
        "storage_key": "probe.a0",
        "landing_path": os.path.join(session_dir, "landing.json"),
        "envelope_landing_path": os.path.join(session_dir, "env.json"),
        "bare_payload_path": os.path.join(session_dir, "bare.json"),
        "envelope_stub_path": os.path.join(session_dir, "stub.json"),
        "order_path": os.path.join(session_dir, "order.md"),
    }


def _template_placeholders(phase):
    path = RO.order_template_path(phase)
    with open(path, encoding="utf-8") as fh:
        return set(RO._PLACEHOLDER_RE.findall(fh.read()))


def _order_placeholder_keys(phase, session_dir, state, payload, seat_key):
    paths = _minimal_paths(session_dir)
    return set(
        RD._order_placeholders(
            phase, seat_key, 0, state, state.get("config") or {},
            payload, session_dir, 2, paths, RD.CHANNEL_FILE,
        ).keys()
    )


def _placeholder_partition():
    return (
        RD.ORDER_READABLE_FILE_INPUTS
        | RD.ORDER_SHIPPED_RESOURCE_INPUTS
        | RD.ORDER_OUTPUT_PLACEHOLDERS
        | RD.ORDER_DERIVED_PLACEHOLDERS
        | RO._AUX_PLACEHOLDER_INPUTS
    )


# --- guidance key drift pin (bite axis: constant ↔ copy surfaces) -------------------------


@pytest.mark.parametrize("rel", _GUIDANCE_COPY_SURFACES, ids=_GUIDANCE_COPY_SURFACES)
def test_fix_batch_guidance_key_present_on_copy_surface(rel):
    # axis: FIX_BATCH_GUIDANCE_KEY literal appears on every enumerated copy surface
    literal = RD.FIX_BATCH_GUIDANCE_KEY
    text = _read(rel)
    assert literal in text, (
        "expected %r on copy surface %s — rename must update all copies" % (literal, rel)
    )


# --- guidance emission (bite axis: fold writes FIX_BATCH_GUIDANCE_KEY) ---------------------


def test_fold_judgment_writes_user_guidance_key():
    # axis: fix-with-guidance folds owner text under FIX_BATCH_GUIDANCE_KEY
    state = _judgment_state()
    RD._fold_judgment(state, state["config"], {"dispositions": [
        {"id": _TRADEOFF_ID, "disposition": "fix-with-guidance",
         "guidance": "keep it backward compatible"}]})
    batch = state["_fixBatch"][0]
    assert batch[RD.FIX_BATCH_GUIDANCE_KEY] == "keep it backward compatible"
    assert "guidance" not in batch


# --- head diff materialization (bite axis: head.diff exists when cited) ---------------------


def test_ensure_round_head_diff_writes_when_cited(tmp_path):
    # axis: _ensure_round_head_diff materializes head.diff from state
    session_dir = str(tmp_path / "head-session")
    os.makedirs(session_dir)
    head = "diff --git a/x b/x\n"
    state = {"headDiff": head}
    path = RD._ensure_round_head_diff(session_dir, 2, state)
    assert path == os.path.join(session_dir, "round-2", "head.diff")
    with open(path, encoding="utf-8") as fh:
        assert fh.read() == head


def test_head_diff_unavailable_refuses_emit(tmp_path):
    # axis: missing headDiff refuses before citing HEAD_DIFF_PATH
    session_dir = str(tmp_path / "head-refuse")
    os.makedirs(session_dir)
    state = {
        "config": {"repoRoot": str(tmp_path)},
        "reviewedDiff": "diff --git a/f b/f\n",
        "headDiff": None,
    }
    paths = _minimal_paths(session_dir)
    payload = {"targets": [{"id": "finding::auth.py::12"}]}
    with pytest.raises(ValueError, match="order-render-refused:head-diff-unavailable"):
        RD._order_placeholders(
            RP.P_AUDITS, "finding::auth.py::12", 0, state, state["config"],
            payload, session_dir, 2, paths, RD.CHANNEL_FILE,
        )


def test_readable_input_refusal_when_registered_path_missing(tmp_path):
    # axis: unregistered readable input on disk refuses with order-input-missing
    ph = {
        "DIFF_PATH": "/nonexistent/diff.txt",
        "RUBRIC_PATH": RD._shipped_rubric_path(),
    }
    reason = RD._readable_file_input_refusal(ph)
    assert reason == "order-input-missing:DIFF_PATH"


def test_pre_emit_and_commit_sidecar_bytes_match(tmp_path):
    # axis: pre-emit materialization and orders-emit commit write identical sidecar bytes
    session_dir = str(tmp_path / "sidecar-session")
    os.makedirs(session_dir)
    rdir = os.path.join(session_dir, "round-2")
    os.makedirs(rdir)
    roster = ["finding::auth.py::12", "finding::other.py::3"]
    payload = {
        "targets": [
            {"id": "finding::other.py::3", "summary": "other target"},
            {"id": "finding::auth.py::12", "summary": "auth target"},
        ],
    }
    commit_writes = dict(RD._order_sidecar_writes(session_dir, 2, RP.P_AUDITS, roster, payload))
    paths = _minimal_paths(session_dir)
    state = {
        "config": {"repoRoot": str(tmp_path)},
        "reviewedDiff": "diff --git a/f b/f\n",
        "headDiff": "diff --git a/f b/f\n",
    }
    RD._order_placeholders(
        RP.P_AUDITS, "finding::auth.py::12", 0, state, state["config"],
        payload, session_dir, 2, paths, RD.CHANNEL_FILE, roster=roster,
    )
    for path, expected in commit_writes.items():
        with open(path, "rb") as fh:
            assert fh.read() == expected


# --- registry census (bite axis: every rendered placeholder is partitioned) ---------------


def test_order_placeholder_registry_partition_is_complete():
    # axis: template + driver placeholder keys partition into registry sets by construction
    partition = _placeholder_partition()
    session_dir = "/tmp/order-input-contract-census"
    state = {
        "config": {"repoRoot": "/tmp"},
        "reviewedDiff": "diff --git a/f b/f\n",
        "headDiff": "diff --git a/f b/f\n",
        "_fixBatch": [],
    }
    payloads = {
        RP.P_PANEL: {},
        RP.P_VERIFIERS: {"clusters": [{"key": "c0", "findings": []}]},
        RP.P_SYNTHESIS: {"findings": []},
        RP.P_GAPSWEEP: {},
        RP.P_AUDITS: {"targets": [{"id": "finding::auth.py::12"}]},
        RP.P_SCOPED: {"hunks": {}},
        RP.P_FIXER: {},
    }
    seat_keys = {
        RP.P_PANEL: "code-reviewer",
        RP.P_VERIFIERS: "verifier:c0",
        RP.P_SYNTHESIS: "synthesis",
        RP.P_GAPSWEEP: "gap-sweep",
        RP.P_AUDITS: "finding::auth.py::12",
        RP.P_SCOPED: "scoped-finder",
        RP.P_FIXER: "fixer",
    }
    missing = []
    for phase in RO.ORDER_PHASES:
        names = _template_placeholders(phase) | _order_placeholder_keys(
            phase, session_dir, state, payloads[phase], seat_keys[phase])
        for name in sorted(names):
            if name not in partition:
                missing.append("%s:%s" % (phase, name))
    assert not missing, "placeholders outside registry partition:\n" + "\n".join(missing)
