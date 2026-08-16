"""The emitted order's output contract follows the seat's CHANNEL (#1035).

A codex/cursor seat dispatched through `dispatch-review` runs in a read-only sandbox and forfeits
on a forbidden write (#767 class). So an order may name a landing path to WRITE only when the
driver has positive evidence the seat can write.

These tests read the order files the driver actually RENDERS in a fixture session — not the
renderer in isolation — because the defect #1035 records was never in the renderer (that half
shipped in #942); it was that the transport row reaching the renderer was empty, so every seat,
engine ones included, was told to write.
"""
import importlib.util
import os

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
RO = _load("round_orders")

ENGINE_SEAT = RD.DIMENSIONS[0]
NATIVE_SEAT = RD.DIMENSIONS[1]


def _section(path, third):
    return ("diff --git a/%s b/%s\n" % (path, path)
            + "index 1111111..2222222 100644\n"
            + "--- a/%s\n" % path
            + "+++ b/%s\n" % path
            + "@@ -1,2 +1,4 @@\n alpha\n+beta\n+%s\n delta\n" % third)


DIFF = "".join(_section("src/f%02d.py" % i, "gamma") for i in range(3))

# --- the write-instruction census vocabulary -----------------------------------------------------
# Every phrase the shipped templates + `round_orders` use to tell a seat to WRITE its result. A new
# write phrasing that is not listed here would slip the census, so this list is asserted against the
# rendered NATIVE orders below (test_write_vocabulary_is_live): each phrase must actually appear in
# some native order, which keeps the census honest as the prose evolves.
# Matched case-insensitively: the same phrase appears sentence-initial in one branch and
# mid-sentence in another ("Write your payload artifact to X — write an empty findings list …").
WRITE_PHRASES = (
    "write **only**",
    "write your",
    "write an empty",
)


def _mixed_seat_map():
    """One engine seat, the rest native — the mixed map the DoD names."""
    seats = {}
    for dim in RD.DIMENSIONS:
        if dim == ENGINE_SEAT:
            seats[dim] = {"vendor": "codex", "model": "gpt-5.1-codex-max", "engine": "codex"}
        else:
            seats[dim] = {"vendor": "claude", "model": "sonnet-5", "engine": "claude"}
    return {"seats": seats}


def _emit(tmp_path, name, seat_map):
    """Run `next` so the driver RENDERS and writes the round's order files; return {seat: text}."""
    session_dir = str(tmp_path / name)
    os.makedirs(session_dir, exist_ok=True)
    cfg = {"leg": "code", "vendors": ["claude", "codex"], "diff": DIFF,
           "fixerVendor": "claude", "verifyCommand": "none"}
    if seat_map is not None:
        cfg["seatMap"] = seat_map
    out = RD.cmd_next(session_dir, cfg)
    assert out["ok"], out
    ok, state = RD.load_state(session_dir)
    assert ok, state
    pend = state["pending"]
    assert pend["phase"] == RD.P_PANEL, pend
    rdir = RR.round_dir(session_dir, pend["round"])
    orders = {}
    for root, _dirs, files in os.walk(rdir):
        for fn in sorted(files):
            if not fn.endswith(".md"):
                continue
            with open(os.path.join(root, fn), encoding="utf-8") as fh:
                text = fh.read()
            # order file stem is the storage key: "<seat>-<hash>.aK" — recover the seat by prefix
            for dim in RD.DIMENSIONS:
                if fn.startswith(dim + "-"):
                    orders[dim] = text
                    break
    assert set(orders) == set(RD.DIMENSIONS), sorted(orders)
    return orders


def _names_a_write(text):
    low = text.lower()
    return [p for p in WRITE_PHRASES if p in low]


def _names_a_landing_path(text):
    return "/landing/" in text


# =================================================================================================
# DoD 1 — mixed seat map: the engine seat's order carries the stdout contract and NO landing write
# =================================================================================================

def test_engine_seat_order_carries_the_stdout_contract(tmp_path):
    orders = _emit(tmp_path, "mixed", _mixed_seat_map())
    text = orders[ENGINE_SEAT]
    assert "final stdout" in text, text[-1200:]


def test_engine_seat_order_names_no_landing_path_write(tmp_path):
    """The bite of this change: a sandboxed seat is never told to write a file it cannot write.

    Bite axis: the PRESENCE of a write instruction in an engine seat's order — not the presence of
    the stdout contract (a fold that emitted both would satisfy that and still forfeit the seat).
    """
    orders = _emit(tmp_path, "mixed", _mixed_seat_map())
    text = orders[ENGINE_SEAT]
    assert _names_a_write(text) == [], _names_a_write(text)
    assert not _names_a_landing_path(text), \
        "engine order names a landing path:\n%s" % text[-1200:]


def test_native_seat_order_still_carries_the_landing_path_write(tmp_path):
    """The other direction — the fix must not collapse every seat onto stdout.

    Bite axis: the ABSENCE of the write instruction for a seat positively known to be native. This
    is the guard against "fix" that just deletes the write contract everywhere.
    """
    orders = _emit(tmp_path, "mixed", _mixed_seat_map())
    text = orders[NATIVE_SEAT]
    assert _names_a_write(text), text[-1200:]
    assert _names_a_landing_path(text), text[-1200:]


def test_write_vocabulary_is_live(tmp_path):
    """Every phrase the census greps for must really be emitted, or the census is vacuous."""
    orders = _emit(tmp_path, "mixed", _mixed_seat_map())
    native = "\n".join(t for d, t in orders.items() if d != ENGINE_SEAT).lower()
    unseen = [p for p in WRITE_PHRASES if p not in native]
    assert unseen == [], "census phrases never emitted by a native order: %s" % unseen


# =================================================================================================
# The fail-safe — an UNKNOWABLE vendor must not produce a write contract (the live #1035 cause)
# =================================================================================================

def test_absent_seat_map_never_emits_a_write_contract(tmp_path):
    """`--seat-map` is optional, so round 1 can have no vendor for any seat.

    Folding that unknown to "native" is what told real codex seats to write (10/10 lanes). The
    fold direction is asymmetric on purpose: a host seat handed the stdout contract still returns
    its payload for the orchestrator to land; an engine seat handed the write contract is lost.

    Bite axis: the FOLD DIRECTION for an unknowable vendor — that no write instruction is stated
    without positive evidence. Not seat-map parsing, which is a different failure.
    """
    orders = _emit(tmp_path, "nomap", None)
    for dim, text in sorted(orders.items()):
        assert _names_a_write(text) == [], (dim, _names_a_write(text))
        assert not _names_a_landing_path(text), dim
        assert "final stdout" in text, dim


def test_absent_vendor_is_still_disclosed_not_merely_made_safe(tmp_path):
    """Fail-safe must not silence the provenance gap — safe is not the same as silent."""
    session_dir = str(tmp_path / "disc")
    os.makedirs(session_dir, exist_ok=True)
    out = RD.cmd_next(session_dir, {"leg": "code", "vendors": ["claude", "codex"], "diff": DIFF,
                                    "fixerVendor": "claude", "verifyCommand": "none"})
    assert out["ok"], out
    ok, state = RD.load_state(session_dir)
    assert ok, state
    gaps = (state["rounds"].get("1") or {}).get("orderVendorProvenanceGaps")
    assert gaps, state["rounds"].get("1")


# =================================================================================================
# DoD — the census, both directions, over every seat kind x channel
# =================================================================================================

@pytest.mark.parametrize("phase", sorted(RD._READ_ONLY_CHANNEL_PHASES))
def test_engine_channel_renders_no_write_instruction_for_every_phase(phase):
    """Direction 1: on the engine channel, no phase's order tells the seat to write."""
    text = _render_phase(phase, host_seat=False)
    assert _names_a_write(text) == [], (phase, _names_a_write(text))
    assert LANDING not in text, phase


@pytest.mark.parametrize("phase", sorted(RD._READ_ONLY_CHANNEL_PHASES))
def test_every_phase_renders_exactly_one_output_contract(phase):
    """Direction 2: exactly one output contract per seat kind x channel — never two, never none.

    Bite axis: MUTUAL EXCLUSIVITY of the two concrete contracts. Counting the `## Return your
    result` heading would not do this — `render_order` appends that heading unconditionally, so an
    order carrying BOTH a stdout instruction and a landing-file write would still count 1.
    """
    for host_seat in (True, False):
        text = _render_phase(phase, host_seat=host_seat)
        writes = bool(_names_a_write(text))
        emits = "final stdout" in text
        assert writes != emits, (
            "phase=%s host_seat=%s must state exactly one contract (writes=%s emits_stdout=%s)"
            % (phase, host_seat, writes, emits))
        assert writes is host_seat, (phase, host_seat, writes)


# =================================================================================================
# The channel is resolved ONCE and both consumers get that value (review finding, #1035)
# =================================================================================================

@pytest.mark.parametrize("phase", sorted(RD._READ_ONLY_CHANNEL_PHASES))
def test_driver_context_gives_both_consumers_the_same_channel(tmp_path, phase, monkeypatch):
    """`host_seat` and the `CHANNEL` placeholder must never disagree for one seat.

    Bite axis: AGREEMENT between the two consumers, resolved through the REAL context builder — not
    a hand-built context, which cannot expose a disagreement because the test would be choosing
    both values itself. `_seat_transport_row` is not pure for the reviewer-engine phases (it
    re-reads engine prefs from disk behind a fallback), so a second resolution is a real divergence
    path; this pins that only one resolution happens.
    """
    session_dir = str(tmp_path / "ctx")
    os.makedirs(session_dir, exist_ok=True)
    out = RD.cmd_next(session_dir, {"leg": "code", "vendors": ["claude", "codex"], "diff": DIFF,
                                    "fixerVendor": "claude", "verifyCommand": "none",
                                    "seatMap": _mixed_seat_map()})
    assert out["ok"], out
    ok, state = RD.load_state(session_dir)
    assert ok, state

    # Every resolution after the first returns a DIFFERENT vendor. With one resolution the context
    # is self-consistent; with two, `host_seat` and `CHANNEL` come from different rows and disagree.
    calls = {"n": 0}
    real_row = RD._seat_transport_row

    def flipping_row(*args, **kwargs):
        row = dict(real_row(*args, **kwargs))
        calls["n"] += 1
        if calls["n"] > 1:
            row["vendor"] = "codex" if row.get("vendor") == "claude" else "claude"
        return row

    monkeypatch.setattr(RD, "_seat_transport_row", flipping_row)
    context, _paths = RD._build_order_render_context(
        session_dir, state, 1, phase, 1, _seat_for(phase), 0, _payload_for(phase))
    placeholder_channel = context["placeholders"].get("CHANNEL")
    host_seat_channel = RD.CHANNEL_FILE if context["host_seat"] else RD.CHANNEL_STDOUT
    assert placeholder_channel == host_seat_channel, (
        "phase=%s resolved the transport row %d times — host_seat says %s, CHANNEL says %s"
        % (phase, calls["n"], host_seat_channel, placeholder_channel))


def _seat_for(phase):
    if phase == RD.P_PANEL:
        return ENGINE_SEAT
    if phase == RD.P_VERIFIERS:
        return "verifier:c1"
    if phase == RD.P_AUDITS:
        return "t1"
    return phase


def _payload_for(phase):
    if phase == RD.P_VERIFIERS:
        return {"clusters": [{"key": "c1", "issues": []}]}
    if phase == RD.P_AUDITS:
        return {"targets": [{"id": "t1", "auditorVendor": "claude"}]}
    return {}


def test_the_fixer_is_not_swept_into_the_read_only_fold():
    """`dispatch-fixer` writes in place and its vendor is UNKNOWN by default (#608).

    Folding its absent vendor to stdout would rewrite a deliberate default rather than close a
    forfeit, so it is excluded by name — pinned here so a later edit cannot quietly add it.
    """
    assert RD.P_FIXER not in RD._READ_ONLY_CHANNEL_PHASES
    row = {"vendor": None, "model": None, "engine": None}
    assert RD._seat_channel(RD.P_FIXER, row) == RD.CHANNEL_FILE


# =================================================================================================
# the channel switch itself — one home for both `host_seat` and the CHANNEL placeholder
# =================================================================================================

@pytest.mark.parametrize("vendor,expected", [
    ("claude", RD.CHANNEL_FILE),
    ("codex", RD.CHANNEL_STDOUT),
    ("cursor", RD.CHANNEL_STDOUT),
    (None, RD.CHANNEL_STDOUT),
    ("", RD.CHANNEL_STDOUT),
    ("   ", RD.CHANNEL_STDOUT),
])
def test_seat_channel_folds_the_vendor_fact(vendor, expected):
    assert RD._seat_channel(RD.P_PANEL, {"vendor": vendor}) == expected


# --- rendering helper (isolated renderer, for the phase census) ----------------------------------

SESSION = "/tmp/rd1035-census"
LANDING = SESSION + "/round-1/landing/p/skey.a1.payload.json"
BARE = SESSION + "/round-1/landing/p/skey.a1.bare.json"


def _phase_placeholders(phase, channel):
    common = {"RUBRIC_PATH": "/plugin/rubric/review-base.md", "CHANNEL": channel}
    diff = SESSION + "/round-1/diff.txt"
    if phase == RD.P_PANEL:
        return dict(common, MODE="branch", REPO="r", TARGET="t", DIFF_PATH=diff,
                    CORE_PATH="/proj/core.md", LAYER_PATH="/proj/layer.md",
                    PR_CHECKOUT_PATH="", PRIOR_COMMENTS_PATH=SESSION + "/prior-comments.json",
                    FOCUS_NOTES="", DIMENSION="correctness",
                    FINDINGS_OUTPUT_PATH=SESSION + "/round-1/findings-x.json")
    if phase == RD.P_VERIFIERS:
        return dict(common, CLUSTER_FINDINGS_PATH=SESSION + "/round-1/clusters/0.json",
                    DIFF_PATH=diff, VERIFICATION_ROOT="/proj")
    if phase == RD.P_SYNTHESIS:
        return dict(common, VERIFIED_FINDINGS_PATH=SESSION + "/round-1/verified.json",
                    DIFF_PATH=diff, VERIFICATION_ROOT="/proj",
                    GROUPING_OUTPUT_PATH=SESSION + "/round-1/grouping.json")
    if phase == RD.P_GAPSWEEP:
        return dict(common, DIFF_PATH=diff, CORE_PATH="/proj/core.md",
                    LAYER_PATH="/proj/layer.md", VERIFICATION_ROOT="/proj",
                    FINDINGS_OUTPUT_PATH=SESSION + "/round-1/gap-sweep-findings.json")
    if phase == RD.P_AUDITS:
        return dict(common, TARGET_SUMMARY_PATH=SESSION + "/round-1/audit-targets/x.json",
                    HEAD_DIFF_PATH=SESSION + "/round-1/head.diff",
                    VERIFICATION_ROOT="/proj", TARGET_ID="t1")
    if phase == RD.P_SCOPED:
        return dict(common, HUNKS_PATH=SESSION + "/round-1/scoped-hunks.json",
                    HEAD_DIFF_PATH=SESSION + "/round-1/head.diff",
                    CORE_PATH="/proj/core.md", LAYER_PATH="/proj/layer.md",
                    VERIFICATION_ROOT="/proj",
                    FINDINGS_OUTPUT_PATH=SESSION + "/round-1/scoped-findings.json")
    raise AssertionError("unmapped phase %r" % phase)


def _render_phase(phase, host_seat):
    channel = RD.CHANNEL_FILE if host_seat else RD.CHANNEL_STDOUT
    context = {
        "session_dir": SESSION,
        "round": 1,
        "attempt": 1,
        "diff_path": SESSION + "/round-1/diff.txt",
        "rubric_path": "/plugin/rubric/review-base.md",
        "core_path": "/proj/core.md",
        "layer_path": "/proj/layer.md",
        "repo_root": "/proj",
        "landing_path": BARE if host_seat else LANDING,
        "envelope_stub_path": SESSION + "/round-1/landing/p/skey.a1.stub.json",
        "ratified_residuals": "",
        "residuals_provenance": "prov",
        "residuals_read_failure": None,
        "payload": {},
        "host_seat": host_seat,
        "placeholders": _phase_placeholders(phase, channel),
    }
    text, reason = RO.render_order(phase, "seat", context)
    assert reason is None, (phase, host_seat, reason)
    return text
