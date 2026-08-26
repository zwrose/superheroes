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
MR = _load("model_registry")

# Fail-closed edge (WO #1035 finding 2): the truth table below asserts on "cursor" and "codex" as
# external-engine vendors. Confirm both are vendors `model_registry` actually knows before building
# a table on the assumption — an unregistered vendor name would make every assertion about it
# vacuous rather than a real check.
assert "codex" in MR.vendors(), MR.vendors()
assert "cursor" in MR.vendors(), MR.vendors()

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
def test_driver_context_gives_both_consumers_the_same_channel(tmp_path, phase):
    """`host_seat` and the `CHANNEL` placeholder must never disagree for one seat.

    Bite axis: AGREEMENT between the two consumers, both derived from the ONE row the caller
    resolved and handed in — `_build_order_render_context` takes `row` as a required parameter and
    never resolves its own (review finding, #1035), so `host_seat` and `CHANNEL` structurally cannot
    diverge inside this function; the real divergence risk moved to whether a CALLER (e.g.
    `_emit_orders_manifest`) resolves the row twice and passes a different one to each consumer —
    that risk is covered separately by
    `test_emit_orders_manifest_reuses_the_same_row_for_manifest_and_render` below.
    """
    session_dir = str(tmp_path / "ctx")
    os.makedirs(session_dir, exist_ok=True)
    out = RD.cmd_next(session_dir, {"leg": "code", "vendors": ["claude", "codex"], "diff": DIFF,
                                    "fixerVendor": "claude", "verifyCommand": "none",
                                    "seatMap": _mixed_seat_map()})
    assert out["ok"], out
    ok, state = RD.load_state(session_dir)
    assert ok, state
    state["headDiff"] = DIFF

    cfg = state.get("config") or {}
    repo_root = cfg.get("repoRoot") or session_dir
    seat = _seat_for(phase)
    payload = _payload_for(phase)
    row = RD._seat_transport_row(state, phase, seat, 0, cfg, payload, repo_root)
    context, _paths = RD._build_order_render_context(
        session_dir, state, 1, phase, 1, seat, 0, payload, row)
    placeholder_channel = context["placeholders"].get("CHANNEL")
    host_seat_channel = RD.CHANNEL_FILE if context["host_seat"] else RD.CHANNEL_STDOUT
    assert placeholder_channel == host_seat_channel, (
        "phase=%s — host_seat says %s, CHANNEL says %s"
        % (phase, host_seat_channel, placeholder_channel))


def test_emit_orders_manifest_reuses_the_same_row_for_manifest_and_render(tmp_path):
    """The MANIFEST's recorded vendor and the RENDERED order's output contract must agree.

    Bite axis: DISAGREEMENT between `_emit_orders_manifest`'s manifest entry (`seats[skey].vendor`,
    written from the row it resolved once) and the channel actually baked into that seat's rendered
    order file. A fold that resolved the transport row once for the manifest and again
    (independently, e.g. without `seat_map=seat_map`) for `_build_order_render_context` would pass
    every isolated channel test above while still recording `codex` in the manifest and writing a
    landing-path WRITE instruction into the engine seat's order — the exact #1035 forfeit.
    """
    session_dir = str(tmp_path / "reuse")
    os.makedirs(session_dir, exist_ok=True)
    out = RD.cmd_next(session_dir, {"leg": "code", "vendors": ["claude", "codex"], "diff": DIFF,
                                    "fixerVendor": "claude", "verifyCommand": "none",
                                    "seatMap": _mixed_seat_map()})
    assert out["ok"], out
    ok, state = RD.load_state(session_dir)
    assert ok, state
    pend = state["pending"]
    assert pend["phase"] == RD.P_PANEL, pend

    manifest_path = RD._orders_manifest_path(session_dir, pend["round"], RD.P_PANEL, pend["attempt"])
    manifest, err = RR.read_json(manifest_path)
    assert err is None, err

    engine_entry = None
    for entry in manifest["seats"].values():
        if entry.get("seat") == ENGINE_SEAT:
            engine_entry = entry
            break
    assert engine_entry is not None, manifest["seats"]

    with open(engine_entry["orderPath"], encoding="utf-8") as fh:
        order_text = fh.read()

    manifest_says_engine = RD._vendor_is_external_engine(engine_entry["vendor"])
    order_says_stdout = "final stdout" in order_text and not _names_a_landing_path(order_text)
    assert manifest_says_engine == order_says_stdout, (
        "manifest vendor=%r (engine=%s) but rendered order says stdout=%s:\n%s"
        % (engine_entry["vendor"], manifest_says_engine, order_says_stdout, order_text[-1200:]))


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


_TRUTH_TABLE_VENDORS = ("claude", "codex", "cursor", None, "")


@pytest.mark.parametrize("phase", sorted(RD._READ_ONLY_CHANNEL_PHASES))
@pytest.mark.parametrize("vendor", _TRUTH_TABLE_VENDORS)
def test_seat_channel_folds_the_vendor_fact_on_every_read_only_phase(phase, vendor):
    """The resolver truth table, crossed over EVERY read-only-channel phase — not just P_PANEL.

    Bite axis: an implementation that got P_PANEL right (the only phase the prior truth table
    covered) but returned `CHANNEL_FILE` for an engine or unresolved vendor on verifiers, audits,
    synthesis, gap-sweep, or scoped would pass every previously-existing test here and still emit a
    forbidden write contract to a sandboxed engine seat dispatched through one of those phases
    (review finding, #1035 round 2).
    """
    expected = RD.CHANNEL_FILE if vendor == "claude" else RD.CHANNEL_STDOUT
    assert RD._seat_channel(phase, {"vendor": vendor}) == expected, (phase, vendor)


@pytest.mark.parametrize("phase", sorted(RD._READ_ONLY_CHANNEL_PHASES))
def test_a_defaulted_vendor_folds_to_stdout_on_every_read_only_phase(phase):
    """`vendorSource: "defaulted"` is NOT positive host evidence — the #1037 rider's census row.

    `_reviewer_engine_vendor` falls back to the literal `"claude"` when the engine-preference read
    raises, so by VALUE the row is indistinguishable from a configured claude seat. Read as host
    evidence it hands the seat the landing-path write contract — which a seat the orchestrator
    actually dispatched on an engine forfeits on (#1043 confirmation-round finding 11).

    Bite axis: the pair below is the whole point — same vendor string, opposite channel, decided
    only by the marker. An implementation that ignores `vendorSource` returns `CHANNEL_FILE` for
    both and fails the defaulted half.
    """
    defaulted = {"vendor": "claude", "vendorSource": RD.VENDOR_SOURCE_DEFAULTED}
    configured = {"vendor": "claude", "vendorSource": RD.VENDOR_SOURCE_CONFIGURED}
    assert RD._seat_channel(phase, defaulted) == RD.CHANNEL_STDOUT, phase
    assert RD._seat_channel(phase, configured) == RD.CHANNEL_FILE, phase   # A/B
    # An unmarked row keeps its pre-#1037 reading: absence of the marker is not a defaulted claim.
    assert RD._seat_channel(phase, {"vendor": "claude"}) == RD.CHANNEL_FILE, phase


def test_reviewer_engine_vendor_marks_a_refused_read_as_defaulted(monkeypatch, tmp_path):
    """The PRODUCTION failure path is a refusal RETURN, not an exception.

    `engine_pref.load_engine_prefs` documents "Never raises" — an unreadable/refused core.md comes
    back as `refusal_engine_prefs(readError=…)`. A marker keyed only on `except` would never fire
    here, leaving the whole rider inert while every test that monkeypatched a *raise* still passed.
    So this drives the real return shape, produced by `engine_pref` itself rather than hand-built.
    """
    refusal = RD.engine_pref.refusal_engine_prefs("core.md unreadable")
    assert refusal.get("readError"), "fixture must be the real refusal shape"
    monkeypatch.setattr(RD.engine_pref, "load_engine_prefs", lambda _root: refusal)
    assert RD._reviewer_engine_vendor(str(tmp_path)) == ("claude", RD.VENDOR_SOURCE_DEFAULTED)


def test_a_genuinely_absent_config_is_configured_not_defaulted(monkeypatch, tmp_path):
    """A/B on the distinction `readError` draws: absent config is not a failed read.

    `degenerate_engine_prefs()` is "nothing configured", whose documented defaults ARE the
    configuration. Marking it `defaulted` would push every greenfield reviewer seat onto the stdout
    channel and disclose a provenance gap that does not exist."""
    degenerate = RD.engine_pref.degenerate_engine_prefs()
    assert degenerate.get("readError") is None, "fixture must be the real absent-config shape"
    monkeypatch.setattr(RD.engine_pref, "load_engine_prefs", lambda _root: degenerate)
    vendor, source = RD._reviewer_engine_vendor(str(tmp_path))
    assert source == RD.VENDOR_SOURCE_CONFIGURED, (vendor, source)


def test_reviewer_engine_vendor_still_degrades_if_the_loader_violates_its_contract(monkeypatch,
                                                                                   tmp_path):
    """Belt-and-braces only: the `except` arms are not the primary signal (see the test above)."""
    def boom(_root):
        raise RuntimeError("engine prefs unreadable")

    monkeypatch.setattr(RD.engine_pref, "load_engine_prefs", boom)
    assert RD._reviewer_engine_vendor(str(tmp_path)) == ("claude", RD.VENDOR_SOURCE_DEFAULTED)


def test_a_configured_engine_vendor_keeps_the_configured_marker(monkeypatch, tmp_path):
    monkeypatch.setattr(RD.engine_pref, "load_engine_prefs", lambda _root: {"effort": {}})
    monkeypatch.setattr(RD.engine_pref, "resolve_engine", lambda _role, _prefs: "codex")
    assert RD._reviewer_engine_vendor(str(tmp_path)) == ("codex", RD.VENDOR_SOURCE_CONFIGURED)


@pytest.mark.parametrize("phase", [RD.P_VERIFIERS, RD.P_GAPSWEEP, RD.P_SCOPED])
def test_reviewer_phase_transport_row_carries_the_vendor_source(monkeypatch, phase, tmp_path):
    """The marker reaches the transport row — the seam `_seat_channel` and the gap collector read."""
    monkeypatch.setattr(RD.engine_pref, "load_engine_prefs",
                        lambda _root: RD.engine_pref.refusal_engine_prefs("core.md unreadable"))
    state = {"config": {}, "seatMap": {}, "pending": {}, "round": 1, "rounds": {}}
    row = RD._seat_transport_row(state, phase, "verifier", 0, {}, {}, str(tmp_path))
    assert row["vendor"] == "claude"
    assert row["vendorSource"] == RD.VENDOR_SOURCE_DEFAULTED
    assert RD._seat_channel(phase, row) == RD.CHANNEL_STDOUT


@pytest.mark.parametrize("phase", [RD.P_VERIFIERS, RD.P_GAPSWEEP, RD.P_SCOPED])
def test_a_defaulted_reviewer_vendor_is_disclosed_not_merely_made_safe(tmp_path, monkeypatch,
                                                                       phase):
    """Safe is not the same as silent — the defaulted fallback owes a receipt (#1037 rider).

    The collector used to be panel-scoped, so a reviewer-phase fallback folded safely to stdout and
    disclosed NOTHING. It now derives from the same predicate the channel folds on, so the
    disclosure cannot lag the fold."""
    session_dir = str(tmp_path / ("disc-" + phase))
    os.makedirs(session_dir, exist_ok=True)
    out = RD.cmd_next(session_dir, {"leg": "code", "vendors": ["claude", "codex"], "diff": DIFF,
                                    "fixerVendor": "claude", "verifyCommand": "none",
                                    "seatMap": _mixed_seat_map()})
    assert out["ok"], out
    ok, state = RD.load_state(session_dir)
    assert ok, state
    state["headDiff"] = DIFF
    rnd_key = str(state["round"])
    state["rounds"].setdefault(rnd_key, {}).pop("orderVendorProvenanceGaps", None)   # clear round-1

    monkeypatch.setattr(RD.engine_pref, "load_engine_prefs",
                        lambda _root: RD.engine_pref.refusal_engine_prefs("core.md unreadable"))
    seat = _seat_for(phase)
    RD._emit_orders_manifest(session_dir, state, state["round"], phase, 0, [seat],
                             journal_cmd="next", pending_payload=_payload_for(phase), seat_map={})
    gaps = (state["rounds"].get(rnd_key) or {}).get("orderVendorProvenanceGaps")
    assert gaps, "a defaulted reviewer vendor must be disclosed, not silently made safe"
    row = next(g for g in gaps if g.get("seat") == seat)
    assert row["vendorSource"] == RD.VENDOR_SOURCE_DEFAULTED, row


@pytest.mark.parametrize("phase", [RD.P_VERIFIERS, RD.P_GAPSWEEP, RD.P_SCOPED])
def test_a_configured_reviewer_vendor_is_not_disclosed_as_a_gap(tmp_path, monkeypatch, phase):
    """A/B for the disclosure above: a vendor the driver really RESOLVED is not a gap.

    Without this the test above would pass against a collector that discloses every reviewer seat
    unconditionally — which would make the channel say one thing and the receipt another."""
    session_dir = str(tmp_path / ("ok-" + phase))
    os.makedirs(session_dir, exist_ok=True)
    out = RD.cmd_next(session_dir, {"leg": "code", "vendors": ["claude", "codex"], "diff": DIFF,
                                    "fixerVendor": "claude", "verifyCommand": "none",
                                    "seatMap": _mixed_seat_map()})
    assert out["ok"], out
    ok, state = RD.load_state(session_dir)
    assert ok, state
    state["headDiff"] = DIFF
    rnd_key = str(state["round"])
    state["rounds"].setdefault(rnd_key, {}).pop("orderVendorProvenanceGaps", None)

    monkeypatch.setattr(RD.engine_pref, "load_engine_prefs", lambda _root: {})
    monkeypatch.setattr(RD.engine_pref, "resolve_engine", lambda _role, _prefs: "claude")
    seat = _seat_for(phase)
    RD._emit_orders_manifest(session_dir, state, state["round"], phase, 0, [seat],
                             journal_cmd="next", pending_payload=_payload_for(phase), seat_map={})
    gaps = (state["rounds"].get(rnd_key) or {}).get("orderVendorProvenanceGaps") or []
    assert not any(g.get("seat") == seat for g in gaps), gaps


@pytest.mark.parametrize("vendor", _TRUTH_TABLE_VENDORS)
def test_seat_channel_fixer_folds_on_the_same_table_but_never_via_the_read_only_exclusion(vendor):
    """`P_FIXER` is deliberately excluded from the READ-ONLY fold — pinned across the same vendor
    sweep as the read-only phases above, so the exclusion is checked on the SAME table.

    An engine vendor (`codex`/`cursor`) still folds to `CHANNEL_STDOUT` on the fixer phase — that is
    the vendor-is-an-engine check (`_seat_is_engine`), which fires for every phase and is correct: a
    genuine codex/cursor fixer really is sandboxed and needs the stdout contract (pinned separately
    in `test_round_orders.py::test_engine_fixer_order_landing_block_uses_fixes_stdout_contract`).
    What `P_FIXER`'s exclusion from `_READ_ONLY_CHANNEL_PHASES` protects is narrower: an UNRESOLVED
    vendor (`None`/empty) must stay `CHANNEL_FILE` — the fixer's deliberate default-to-write (#608)
    — rather than falling to stdout the way an unresolved read-only-phase seat would.

    Bite axis: `P_FIXER` collapsing an UNRESOLVED vendor onto `CHANNEL_STDOUT`, which would silently
    drop the fixer's deliberate default-to-write behaviour — the one fold this exclusion must never
    let happen. (An engine vendor going to stdout is the correct, unrelated branch, asserted too so
    the table stays honest rather than only testing the branch the bite axis cares about.)
    """
    if vendor in ("codex", "cursor"):
        expected = RD.CHANNEL_STDOUT
    else:
        expected = RD.CHANNEL_FILE
    assert RD._seat_channel(RD.P_FIXER, {"vendor": vendor}) == expected, vendor


# --- rendering helper (isolated renderer, for the phase census) ----------------------------------

SESSION = "/tmp/rd1035-census"
LANDING = SESSION + "/round-1/landing/p/skey.a1.payload.json"
BARE = SESSION + "/round-1/landing/p/skey.a1.bare.json"
_DIFF = SESSION + "/round-1/diff.txt"

# Populated by `round_orders._panel_derived_placeholders` / `_channel_derived_placeholders`.
_DERIVED_PLACEHOLDER_NAMES = frozenset({
    "OUTPUT_CHANNEL_BLOCK",
    "PR_CHECKOUT_CONTEXT_LINE",
    "PRIOR_COMMENTS_CONTEXT_LINE",
    "FOCUS_CONTEXT_LINE",
    "PR_CHECKOUT_INSTRUCTION_BLOCK",
})

# Auxiliary inputs consumed by derivation but not declared in the template body.
_FIXTURE_AUX_INPUTS = {
    RD.P_PANEL: frozenset({"CHANNEL", "FOCUS_NOTES", "FINDINGS_OUTPUT_PATH", "PR_CHECKOUT_PATH"}),
    RD.P_VERIFIERS: frozenset({"CHANNEL"}),
    RD.P_SYNTHESIS: frozenset({"CHANNEL", "GROUPING_OUTPUT_PATH"}),
    RD.P_GAPSWEEP: frozenset({"CHANNEL", "FINDINGS_OUTPUT_PATH"}),
    RD.P_AUDITS: frozenset({"CHANNEL"}),
    RD.P_SCOPED: frozenset({"CHANNEL", "FINDINGS_OUTPUT_PATH"}),
}

# Realistic placeholder values preserved from the prior hand-typed fixture — keyed by phase then
# name. `CHANNEL` is always bound to the `channel` argument, never listed here.
_KNOWN_REALISTIC_VALUES = {
    RD.P_PANEL: {
        "MODE": "branch",
        "MODE_EVIDENCE": "Review session mode branch (from session metadata).",
        "REPO": "r",
        "TARGET": "t",
        "DIFF_PATH": _DIFF,
        "RUBRIC_PATH": "/plugin/rubric/review-base.md",
        "CORE_PATH": "/proj/core.md",
        "LAYER_PATH": "/proj/layer.md",
        "PR_CHECKOUT_PATH": "",
        "PRIOR_COMMENTS_PATH": SESSION + "/prior-comments.json",
        "FOCUS_NOTES": "",
        "DIMENSION": "correctness",
        "FINDINGS_OUTPUT_PATH": SESSION + "/round-1/findings-x.json",
    },
    RD.P_VERIFIERS: {
        "CLUSTER_FINDINGS_PATH": SESSION + "/round-1/clusters/0.json",
        "DIFF_PATH": _DIFF,
        "VERIFICATION_ROOT": "/proj",
        "RUBRIC_PATH": "/plugin/rubric/review-base.md",
    },
    RD.P_SYNTHESIS: {
        "VERIFIED_FINDINGS_PATH": SESSION + "/round-1/verified.json",
        "DIFF_PATH": _DIFF,
        "VERIFICATION_ROOT": "/proj",
        "RUBRIC_PATH": "/plugin/rubric/review-base.md",
        "GROUPING_OUTPUT_PATH": SESSION + "/round-1/grouping.json",
    },
    RD.P_GAPSWEEP: {
        "DIFF_PATH": _DIFF,
        "RUBRIC_PATH": "/plugin/rubric/review-base.md",
        "CORE_PATH": "/proj/core.md",
        "LAYER_PATH": "/proj/layer.md",
        "VERIFICATION_ROOT": "/proj",
        "FINDINGS_OUTPUT_PATH": SESSION + "/round-1/gap-sweep-findings.json",
    },
    RD.P_AUDITS: {
        "TARGET_SUMMARY_PATH": SESSION + "/round-1/audit-targets/x.json",
        "HEAD_DIFF_PATH": SESSION + "/round-1/head.diff",
        "VERIFICATION_ROOT": "/proj",
        "TARGET_ID": "t1",
        "RUBRIC_PATH": "/plugin/rubric/review-base.md",
    },
    RD.P_SCOPED: {
        "HUNKS_PATH": SESSION + "/round-1/scoped-hunks.json",
        "HEAD_DIFF_PATH": SESSION + "/round-1/head.diff",
        "CORE_PATH": "/proj/core.md",
        "LAYER_PATH": "/proj/layer.md",
        "VERIFICATION_ROOT": "/proj",
        "FINDINGS_OUTPUT_PATH": SESSION + "/round-1/scoped-findings.json",
        "RUBRIC_PATH": "/plugin/rubric/review-base.md",
    },
}


def _template_declared_placeholders(phase):
    template, reason = RO._read_template(phase)
    if reason:
        return None, reason
    return set(RO._PLACEHOLDER_RE.findall(template or "")), None


def _fixture_direct_placeholder_names(phase):
    declared, reason = _template_declared_placeholders(phase)
    if reason:
        return None, reason
    aux = _FIXTURE_AUX_INPUTS.get(phase, frozenset({"CHANNEL"}))
    return (declared - _DERIVED_PLACEHOLDER_NAMES) | aux, None


def _phase_placeholders(phase, channel):
    declared, reason = _template_declared_placeholders(phase)
    if reason:
        raise AssertionError("unmapped phase %r" % phase)
    direct_names, _ = _fixture_direct_placeholder_names(phase)
    known = _KNOWN_REALISTIC_VALUES.get(phase, {})
    result = {}
    for name in sorted(direct_names):
        if name == "CHANNEL":
            result[name] = channel
        elif name in known:
            result[name] = known[name]
        else:
            result[name] = "STUB:%s" % name
    return result


def test_read_only_channel_phases_is_derived_not_hand_typed():
    """`_READ_ONLY_CHANNEL_PHASES` must track `round_orders.ORDER_PHASES` minus the fixer exactly.

    Bite axis: set MEMBERSHIP drift between the two registries — a phase added to `ORDER_PHASES`
    and forgotten in the fold, or a phase named in the fold that `ORDER_PHASES` does not know about
    — not channel behaviour, which the tests above already cover.
    """
    order_phases = set(RO.ORDER_PHASES)
    fold = set(RD._READ_ONLY_CHANNEL_PHASES)
    expected = order_phases - {RD.P_FIXER}
    missing = expected - fold
    assert not missing, "phase(s) in ORDER_PHASES (minus the fixer) missing from the fold: %s" % sorted(missing)
    assert RD.P_FIXER not in fold, "the fixer must stay excluded from the fold"
    extra = fold - order_phases
    assert not extra, "fold names phase(s) ORDER_PHASES does not know about: %s" % sorted(extra)


def test_panel_fixture_supplies_realistic_values_and_exact_key_set():
    """Anti-vacuity: the derived fixture must not stub every value, and its key set must match the
    template's direct placeholders plus the auxiliary inputs this phase's derivation consumes.

    `render_order` refuses both directions (`unfilled-placeholder` and `unused-context-key`), so
    both halves of the key-set check are load-bearing.
    """
    ph = _phase_placeholders(RD.P_PANEL, RD.CHANNEL_FILE)
    for name in ("MODE", "DIFF_PATH", "FINDINGS_OUTPUT_PATH", "CHANNEL"):
        assert not ph[name].startswith("STUB:"), (name, ph[name])
    expected_keys, reason = _fixture_direct_placeholder_names(RD.P_PANEL)
    assert reason is None, reason
    assert set(ph.keys()) == expected_keys


def test_placeholder_fixture_known_table_covers_every_template_placeholder():
    """Drift pin (strong form): every placeholder declared in an order template must have a
    realistic (non-stub) value in `_KNOWN_REALISTIC_VALUES` for that phase, and every known-table
    key must still be declared in that phase's template or registered as an auxiliary input.

    Adding `{{NEW}}` to any template without extending the known-name table makes this test fail
    without touching the fixture builder — the mirror is derived from the template, not hand-typed.
    Deleting a placeholder from a template without removing its known-table entry fails the reverse
    half the same way.
    """
    phases = sorted(RD._READ_ONLY_CHANNEL_PHASES)
    assert phases, "read-only channel phases must be nonempty for fixture drift pin"
    gaps = []
    stub_values = []
    stale_keys = []
    for phase in phases:
        declared, reason = _template_declared_placeholders(phase)
        assert reason is None, (phase, reason)
        direct = declared - _DERIVED_PLACEHOLDER_NAMES
        direct_names, name_reason = _fixture_direct_placeholder_names(phase)
        assert name_reason is None, (phase, name_reason)
        known = _KNOWN_REALISTIC_VALUES.get(phase, {})
        ph = _phase_placeholders(phase, RD.CHANNEL_FILE)
        for name in sorted(direct):
            if name == "CHANNEL":
                continue
            if name not in known:
                gaps.append("%s:%s" % (phase, name))
                continue
            value = ph[name]
            if not isinstance(value, str) or not value or value.startswith("STUB:"):
                stub_values.append("%s:%s=%r" % (phase, name, value))
        for key in sorted(set(known) - direct_names):
            stale_keys.append("%s:%s" % (phase, key))
    assert not gaps, "template placeholder(s) missing realistic fixture value: %s" % gaps
    assert not stub_values, "template placeholder(s) with stub or empty fixture value: %s" % stub_values
    assert not stale_keys, "stale fixture key(s) not declared in template or aux inputs: %s" % stale_keys


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
