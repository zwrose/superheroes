"""Invariant tests: one normalized severity vocabulary on the review driver's fold path (#1094)."""
import importlib.util
import itertools
import os
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import circuit_breaker as CB  # noqa: E402
import loop_synthesis as LS  # noqa: E402
import verification as V  # noqa: E402


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_LIB, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RD = _load("round_driver")
RM = _load("review_memory")

DIFF = ("diff --git a/f.py b/f.py\nindex 1..2 100644\n--- a/f.py\n+++ b/f.py\n"
        "@@ -1 +1,2 @@\n-old\n+new\n+more\n")

EDGE_VALUES = [
    None, "", " Critical ", "important", "CRITICAL",
    "Blocker", "High", 123, ["Critical"], {"a": 1},
]
ALL_VALUES = list(CB.SEVERITY_TIERS) + EDGE_VALUES
_TIER_RANK = {"Critical": 0, "Important": 1, "Minor": 2, "Nit": 3}
_FAIL_CLOSED_DEFAULT = "Important"
_BLOCKING_VALUES = [x for x in ALL_VALUES if CB.is_blocking(x)]
_NON_BLOCKING_VALUES = [x for x in ALL_VALUES if not CB.is_blocking(x)]

_TIER_VARIANTS = {
    "Critical": ["critical", "CRITICAL", "cRiTiCaL", "  Critical  "],
    "Important": ["important", "IMPORTANT", "iMpOrTaNt", "  Important  "],
    "Minor": ["minor", "MINOR", "mInOr", "  Minor  "],
    "Nit": ["nit", "NIT", "nIt", "  Nit  "],
}


def _cfg(**over):
    base = {"leg": "code", "vendors": ["claude", "codex"], "diff": DIFF, "fixerVendor": "claude"}
    base.update(over)
    return base


def _finding(title="null deref", severity="Important", file="f.py", line=1, **kw):
    base = {"title": title, "severity": severity, "file": file, "line": line}
    base.update(kw)
    return base


def _plausible_verdicts(findings):
    staged = V.stage_ids(findings)
    return [{"id": f["id"], "verdict": "PLAUSIBLE", "reason": "could not fully verify"}
            for f in staged]


def _drive_fold_path(seat_findings, verdicts=None, grouping=None):
    """Panel compile → verify → synthesis → fix batch, reusing round_driver folds.

    `seat_findings` maps dimension name → list of findings for that seat.
    """
    state = RD.new_state(_cfg())
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    for dim, flist in seat_findings.items():
        seats[dim] = {"findings": list(flist)}
    RD._fold_panel(state, state["config"], {"seats": seats})
    compiled = state.get("_toVerify") or []
    RD._fold_verifiers(state, state["config"],
                        {"verdicts": verdicts if verdicts is not None
                         else _plausible_verdicts(compiled)})
    artifact = {"grouping": grouping} if grouping is not None else {}
    RD._fold_synthesis(state, state["config"], artifact)
    return state


# --- census / invariant -------------------------------------------------------

@pytest.mark.parametrize("x", ALL_VALUES)
def test_effective_severity_always_valid_tier(x):
    assert CB.effective_severity(x) in CB.SEVERITY_TIERS


@pytest.mark.parametrize("x", ALL_VALUES)
def test_severity_rank_matches_tier_index(x):
    eff = CB.effective_severity(x)
    assert CB.severity_rank(x) == _TIER_RANK[eff]


def test_fail_closed_default_tier_rank_is_independently_pinned():
    off_vocab = "something-off-vocabulary"
    assert CB.effective_severity(off_vocab) == _FAIL_CLOSED_DEFAULT
    assert CB.severity_rank(off_vocab) == _TIER_RANK[_FAIL_CLOSED_DEFAULT]


@pytest.mark.parametrize("x", ALL_VALUES)
def test_blocking_agrees_with_effective_severity(x):
    assert CB.is_blocking(CB.effective_severity(x)) == CB.is_blocking(x)


@pytest.mark.parametrize("blocking,non_blocking",
                         itertools.product(_BLOCKING_VALUES, _NON_BLOCKING_VALUES))
def test_blocking_always_ranks_above_non_blocking(blocking, non_blocking):
    assert CB.severity_rank(blocking) < CB.severity_rank(non_blocking)


# --- site-reachability arms ---------------------------------------------------

def test_default_blocking_severity_agrees_across_homes():
    """Fail-closed blocking default must not drift across circuit_breaker, verification, loop_synthesis."""
    assert V._DEFAULT_BLOCKING_SEVERITY == LS._DEFAULT_BLOCKING_SEVERITY
    assert CB.effective_severity("something-off-vocabulary") == V._DEFAULT_BLOCKING_SEVERITY


def test_review_memory_imports_first_in_fresh_process():
    """Cycle-safe: review_memory must not top-level-import circuit_breaker (#1104)."""
    code = "import sys; sys.path.insert(0, %r); import review_memory" % _LIB
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout


@pytest.mark.parametrize("tier", CB.SEVERITY_TIERS)
@pytest.mark.parametrize("variant_idx", range(4))
def test_mechanical_compile_canonicalizes_tier_variants(tier, variant_idx):
    variant = _TIER_VARIANTS[tier][variant_idx]
    finding = _finding(severity=variant)
    compiled, drops = RD.mechanical_compile([finding], DIFF)
    assert drops == []
    assert len(compiled) == 1
    assert compiled[0]["severity"] == tier


@pytest.mark.parametrize("bad", ["blocker", "high", "Bananas", None, 123, ["Critical"], {"a": 1}])
def test_mechanical_compile_off_vocabulary_to_important(bad):
    finding = _finding(severity=bad)
    compiled, drops = RD.mechanical_compile([finding], DIFF)
    assert drops == []
    assert len(compiled) == 1
    assert compiled[0]["severity"] == "Important"


def test_mechanical_compile_stamps_before_dedupe_merge():
    """Severity must be canonical before _compile_by_anchor runs (ingest chokepoint)."""
    pre_dedupe = []
    real_compile_by_anchor = RD._compile_by_anchor

    def spy_compile_by_anchor(findings):
        pre_dedupe.extend(list(findings))
        return real_compile_by_anchor(findings)

    RD._compile_by_anchor = spy_compile_by_anchor
    try:
        findings = [
            _finding(severity="important", taxonomy="winner-important"),
            _finding(severity="Minor", taxonomy="winner-minor", title="NULL DEREF"),
        ]
        compiled, drops = RD.mechanical_compile(findings, DIFF)
    finally:
        RD._compile_by_anchor = real_compile_by_anchor

    assert drops == []
    assert len(compiled) == 1
    assert all(f.get("severity") in CB.SEVERITY_TIERS for f in pre_dedupe)
    assert compiled[0]["taxonomy"] == "winner-important"


def test_mechanical_compile_nit_cap_overflow_stays_nit():
    findings = [{"title": "nit%d" % i, "severity": "nit", "file": "f.py", "line": i + 1}
                for i in range(9)]
    compiled, _ = RD.mechanical_compile(findings, None)
    summary = [f for f in compiled if f.get("summaryEntry")]
    assert len(summary) == 1
    assert summary[0]["severity"] == "Nit"


def test_ingested_important_retains_blocking_in_review_memory():
    """DoD regression: lowercase important survives ingest and counts blocking cross-round."""
    raw = _finding(severity="important")
    compiled, _ = RD.mechanical_compile([raw], DIFF)
    assert compiled[0]["severity"] == "Important"
    records = [
        {"round": 1, "findings": [compiled[0]]},
        {"round": 2, "findings": [dict(compiled[0])]},
    ]
    assert len(RM.recurrent_classes(records)) == 1
    summary = RM._summarize_dimension({"findings": [compiled[0]]})
    assert summary["blockingCount"] == 1


def test_review_memory_blocking_reads_survive_raw_mis_cased_severity():
    """Edge 7: recordsPath resume may carry raw severity mechanical_compile never saw."""
    raw = _finding(severity="important")
    records = [
        {"round": 1, "findings": [raw]},
        {"round": 2, "findings": [dict(raw)]},
    ]
    assert len(RM.recurrent_classes(records)) == 1
    summary = RM._summarize_dimension({"findings": [raw]})
    assert summary["blockingCount"] == 1


@pytest.mark.parametrize("order", [
    ("important", "Minor"),
    ("Minor", "important"),
])
def test_compile_by_anchor_keeps_mis_cased_blocking(order):
    sev_a, sev_b = order
    findings = [
        _finding(severity=sev_a),
        _finding(severity=sev_b),
    ]
    compiled = RD._compile_by_anchor(findings)
    assert len(compiled) == 1
    assert CB.effective_severity(compiled[0]["severity"]) == "Important"


def test_apply_verdicts_honors_mis_cased_upgrade():
    findings = V.stage_ids([_finding(severity="Minor")])
    verdicts = [{"id": "v0", "verdict": "PLAUSIBLE", "severity": "critical",
                 "reason": "real blocker"}]
    out = V.apply_verdicts(findings, verdicts)
    assert out["findings"][0]["severity"] == "Critical"


def test_apply_verdicts_honors_mis_cased_demotion():
    findings = V.stage_ids([_finding(severity="Important")])
    verdicts = [{"id": "v0", "verdict": "PLAUSIBLE", "severity": "minor",
                 "reason": "cosmetic only"}]
    out = V.apply_verdicts(findings, verdicts)
    assert out["findings"][0]["severity"] == "Minor"
    assert len(out["downgrades"]) == 1
    assert out["downgrades"][0]["from"] == "Important"
    assert out["downgrades"][0]["to"] == "Minor"


def test_apply_verdicts_keeps_mis_cased_finding_severity_without_verdict():
    findings = V.stage_ids([_finding(severity="critical")])
    out = V.apply_verdicts(findings, [])
    assert out["findings"][0]["severity"] == "Critical"


@pytest.mark.parametrize("order", [
    ("important", "Minor"),
    ("Minor", "important"),
])
def test_merge_and_rank_keeps_mis_cased_blocking(order):
    sev_a, sev_b = order
    survivors = V.stage_ids([
        _finding(title="race", severity=sev_a, line=1),
        _finding(title="race", severity=sev_b, line=2),
    ])
    grouping = [{"group_id": "g0", "member_ids": ["v0", "v1"]}]
    out = V.merge_and_rank(survivors, grouping)
    assert len(out["findings"]) == 1
    assert out["findings"][0]["severity"] == "Important"


# --- end-to-end driver fixture (DoD row 1) ------------------------------------

@pytest.mark.parametrize("order", [
    ("important", "Minor"),
    ("Minor", "important"),
])
def test_e2e_same_anchor_blocker_reaches_fix_batch(order):
    """Two seats, same file+line+title: mis-cased blocking must survive to _fixBatch."""
    sev_a, sev_b = order
    seat_findings = {
        "code-reviewer": [_finding(severity=sev_a)],
        "security-reviewer": [_finding(severity=sev_b)],
    }
    raw = seat_findings["code-reviewer"] + seat_findings["security-reviewer"]
    compiled, _ = RD.mechanical_compile(raw, DIFF)
    assert len(compiled) == 1
    assert CB.effective_severity(compiled[0]["severity"]) == "Important"
    state = _drive_fold_path(seat_findings)
    assert state["step"] == RD.P_FIXER
    assert len(state["_fixBatch"]) == 1
    assert state["_fixBatch"][0]["severity"] == "Important"


@pytest.mark.parametrize("order", [
    ("important", "Minor"),
    ("Minor", "important"),
])
def test_e2e_cross_anchor_synthesis_blocker_reaches_fix_batch(order):
    """Different anchors merged by synthesis: mis-cased blocking must survive to _fixBatch."""
    sev_a, sev_b = order
    seat_findings = {
        "code-reviewer": [
            _finding(title="null deref", severity=sev_a, line=1),
            _finding(title="null deref elsewhere", severity=sev_b, line=2),
        ],
    }
    raw = seat_findings["code-reviewer"]
    compiled, _ = RD.mechanical_compile(raw, DIFF)
    assert len(compiled) == 2
    grouping = [{"group_id": "g0", "member_ids": ["v0", "v1"]}]
    state = _drive_fold_path(seat_findings, grouping=grouping)
    assert state["step"] == RD.P_FIXER
    assert len(state["_fixBatch"]) == 1
    assert state["_fixBatch"][0]["severity"] == "Important"
