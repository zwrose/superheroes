"""Tests for the round driver's durable-record subcommands (#723): the schema matrix,
`record-result` / `record-missing`, `advance`, `attest`, and the handback sidecar.

Three disciplines run through every test here:

  - THE REFUSAL STRING IS THE CONTRACT. Each fail-closed edge gets its own test asserting the EXACT
    `reason`, because callers route on it — a test that only asserted `ok is False` would pass
    against any refusal, including the wrong one.
  - UN-PRE-SATISFIED A/B. Every refusal test first demonstrates the UN-refused path succeeding on
    the same setup, so the refusal cannot be an artifact of a precondition that was never
    satisfiable. A refusal test whose setup could never have succeeded proves nothing.
  - SESSION-DEATH REPLAY. A kill between every adjacent pair of {seat-writes-landing, ingest,
    journal-append, advance, terminal, sidecar} is simulated, and the successor `advance` must
    recover with nothing lost and nothing double-counted.

`round_adapters` (the phase-shape sibling) is substituted here through `sys.modules`: the driver
imports it at CALL time precisely so it can be, and so this module still imports when the sibling
is absent. That substitution scopes this file to the DRIVER LAYER — it can never show that the
driver and the adapter agree about the artifact they pass. `test_round_driver_integration.py` is
the real-path home for that, and
`test_this_module_stubs_the_adapter_and_the_real_path_home_does_not` holds the two files'
division of labour as an assertion rather than a convention.
"""
import copy
import hashlib
import importlib.util
import json
import os
import subprocess
import sys

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

DIFF = ("diff --git a/f.py b/f.py\nindex 1..2 100644\n--- a/f.py\n+++ b/f.py\n"
        "@@ -1 +1,2 @@\n-old\n+new\n+more\n")

# The v2 state whose hash the schema matrix must preserve. The expected hex below was computed with
# the PRE-#723 round_driver (`git show HEAD:...round_driver.py`) against this exact dict.
V2_STATE = {
    "schemaVersion": 2,
    "config": {"leg": "code", "panel": False, "code": True, "vendors": ["claude", "codex"],
               "fixerVendor": "claude", "verifyCommand": "none", "maxRounds": 7,
               "dimensions": ["architecture-reviewer", "code-reviewer", "security-reviewer",
                              "test-reviewer", "premortem-reviewer"],
               "recordsPath": None, "coveragePath": None, "priorComments": None},
    "round": 2, "step": "dispatch-fixer", "pending": None,
    "lastAccepted": {"phase": "run-verify", "attempt": 0, "round": 1, "artifactHash": "abc"},
    "rounds": {}, "findings": [], "decisions": [], "auditRounds": [], "confirmations": 1,
    "selfRecovered": False, "independenceDegraded": False, "seatMap": {},
    "reviewedDiff": "diff --git a/f.py b/f.py\n", "headDiff": None, "fixBatch": [],
    "fullPanelRan": True, "_incompletePanel": False, "_changedSubjectsSincePanel": [],
    "terminal": None, "certification": None, "_records": [], "_coverage": [],
    "_resumeCorrupt": None,
}
V2_STATE_HASH_BEFORE_723 = "e39a8e3163d24fb114d1ac95d8e7c9bfbea2d0baef1240a4f7c9c33e85ca780a"

SEAT_MAP = {"seats": {dim: {"vendor": "claude", "model": "sonnet-5", "engine": "claude"}
                      for dim in RD.DIMENSIONS}}


# =============================================================================================
# the substituted adapter sibling
# =============================================================================================

class FakeAdapters(object):
    """A stand-in for the parallel `round_adapters` module, exactly at the pinned interface."""

    ADAPTER_PHASES = (RD.P_PANEL, RD.P_VERIFIERS, RD.P_SYNTHESIS, RD.P_GAPSWEEP, RD.P_AUDITS,
                      RD.P_SCOPED, RD.P_VERIFY, RD.P_FIXER)

    def __init__(self):
        self.rosters = {RD.P_PANEL: list(RD.DIMENSIONS),
                        RD.P_VERIFIERS: [],
                        RD.P_SYNTHESIS: ["synthesis"],
                        RD.P_FIXER: ["dispatch-fixer"]}
        self.roster_reasons = {}
        self.faults = {}
        self.assemble_reason = None
        self.assembled = []
        self.policies = {}

    def roster_for(self, phase, state, config):
        if phase in self.roster_reasons:
            return [], self.roster_reasons[phase]
        return list(self.rosters.get(phase, [])), None

    def payload_fault(self, phase, payload, seat_key, record_boundary=False):
        return self.faults.get(seat_key)

    def missing_policy(self, phase):
        return self.policies.get(phase, "seat-status")

    def assemble(self, phase, envelopes, state, config, dispatch_manifest=None, canary=None,
                 session_dir=None):
        self.assembled.append({"phase": phase, "envelopes": envelopes,
                               "dispatch_manifest": dispatch_manifest, "canary": canary,
                               "session_dir": session_dir})
        if self.assemble_reason is not None:
            return None, self.assemble_reason
        if phase == RD.P_PANEL:
            # `envelopes` is a LIST, keyed by each envelope's own `seat` — the real
            # `round_adapters.assemble` contract (`_index_envelopes` refuses anything else with
            # `envelopes-not-a-list`). This stub consumed a {seat: envelope} MAPPING while the
            # driver handed one over, and the agreement of the two shapes is precisely what a
            # stubbed seam cannot check: see test_round_driver_integration.py.
            seats = {}
            for env in (envelopes or []):
                if not isinstance(env, dict):
                    continue
                seat = env.get("seat")
                if env.get("schema") == RR.SEAT_MISSING_SCHEMA:
                    seats[seat] = {"findings": [], "missing": True}
                else:
                    seats[seat] = env.get("payload") or {"findings": []}
            return {"seats": seats}, None
        if phase == RD.P_VERIFIERS:
            return {"verdicts": []}, None
        if phase == RD.P_SYNTHESIS:
            return {"grouping": None}, None
        return {}, None


@pytest.fixture
def adapters(monkeypatch):
    fake = FakeAdapters()
    monkeypatch.setitem(sys.modules, "round_adapters", fake)
    return fake


# The real-path sibling. Named here (not just in prose) because the division of labour between the
# two files is asserted below rather than assumed.
REAL_PATH_MODULE = "test_round_driver_integration.py"


def test_this_module_stubs_the_adapter_and_the_real_path_home_does_not(adapters):
    """THE DIVISION OF LABOUR, asserted.

    This module substitutes `round_adapters` so it can test the DRIVER LAYER in isolation — the
    roster/attempt/completeness/journal bookkeeping, every refusal string, the session-death
    replays. That is legitimate and stays.

    What a stub can NEVER test is whether the two modules AGREE. It did not: the driver handed
    `assemble` a {seat: envelope} mapping while the adapter's contract is a LIST, so every phase
    refused `assemble-refused` on the real path while this file was green. `%s` is the real-path
    home — REAL driver, REAL adapters, no substitution — and this test fails if that file ever
    starts stubbing the adapter back, which would re-open the exact hole.
    """ % REAL_PATH_MODULE
    # this module really is the stubbed one
    assert sys.modules["round_adapters"] is adapters
    assert isinstance(adapters, FakeAdapters)

    path = os.path.join(_HERE, REAL_PATH_MODULE)
    assert os.path.isfile(path), "the real-path home %s is missing" % REAL_PATH_MODULE
    with open(path, encoding="utf-8") as fh:
        source = fh.read()
    assert "import round_adapters" in source, "%s must drive the REAL adapter" % REAL_PATH_MODULE
    # every spelling that could put a stand-in back in the adapter's place (module substitution or
    # per-function patching). Prose cannot produce these — only a substitution can.
    for substitution in ("monkeypatch.setitem", "monkeypatch.setattr",
                         'sys.modules["round_adapters"] =', "sys.modules['round_adapters'] ="):
        assert substitution not in source, (
            "%s must not substitute the adapter (%s) — it is the module that proves the driver "
            "and the adapter agree" % (REAL_PATH_MODULE, substitution))
    # the EXACT def line, not a prefix of it: a rename that leaves the old name as a prefix
    # (`..._DISABLED`) must not read as the fence still being there.
    assert "def test_adapter_module_is_not_stubbed_in_this_module():" in source, (
        "%s must keep its own call-time no-stub fence" % REAL_PATH_MODULE)


# =============================================================================================
# session helpers
# =============================================================================================

def _cfg(**over):
    base = {"leg": "code", "vendors": ["claude", "codex"], "diff": DIFF, "fixerVendor": "claude",
            "seatMap": SEAT_MAP}
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


def _pending(session_dir):
    return _state(session_dir)["pending"]


def _session_id(session_dir):
    with open(os.path.join(session_dir, RR.META_FILE), encoding="utf-8") as fh:
        return json.load(fh)["sessionId"]


def _anchor_hashes(session_dir, rnd, phase, attempt):
    anchor = RD._orders_anchor(_state(session_dir), session_dir, rnd, phase, attempt)
    if anchor is None:
        return RR.NOT_EMITTED, RR.NOT_EMITTED
    return anchor["manifestSha256"], anchor["orders"].get("*", RR.NOT_EMITTED)


def _result_envelope(session_dir, seat, payload=None, pend=None, **over):
    pend = pend or _pending(session_dir)
    # The default payload is SEAT-SPECIFIC on purpose: two seats sharing one payload would share a
    # payload hash, and the journal/store hash matching that `reconcile` runs on would silently
    # conflate them (a deleted record would still look "seen" through its twin's hash).
    payload = {"findings": [], "confidence": "high", "seat": seat,
               "verificationReceipt": {"ran": True}} if payload is None else payload
    manifest_sha, _order = _anchor_hashes(session_dir, pend["round"], pend["phase"],
                                          pend["attempt"])
    env = {
        "schema": RR.SEAT_RESULT_SCHEMA,
        "session": _session_id(session_dir),
        "round": pend["round"],
        "phase": pend["phase"],
        "seat": seat,
        "attempt": pend["attempt"],
        "vendor": "claude",
        "model": "sonnet-5",
        "dispatchRef": "dispatch-1",
        "orderSha256": RR.NOT_EMITTED,
        "manifestSha256": manifest_sha,
        "recordedAt": "2026-08-07T00:00:00",
        "payloadSha256": RR.payload_sha256(payload),
        "payload": payload,
    }
    env.update(over)
    return env


def _land(session_dir, seat, payload=None, pend=None, **over):
    """Write a seat's envelope into the LANDING area (what the host does)."""
    pend = pend or _pending(session_dir)
    env = _result_envelope(session_dir, seat, payload=payload, pend=pend, **over)
    path = RR.landing_path(session_dir, pend["round"], pend["phase"], RR.storage_key(seat),
                           pend["attempt"])
    RR.atomic_write_json(path, env)
    return path, env


def _land_and_record(session_dir, seat, payload=None):
    _land(session_dir, seat, payload=payload)
    out = RD.cmd_record_result(session_dir, seat)
    assert out["ok"], out
    return out


def _record_all_panel_seats(session_dir, seats=None):
    for seat in (seats if seats is not None else RD.DIMENSIONS):
        _land_and_record(session_dir, seat)


def _fake_git(gitdir, head="a" * 40, base_sha="b" * 40, remote="github.com/o/r"):
    """The ONE git seam `_publish_sidecar` reads through — injected so no test touches the
    developer's real checkout."""
    def run(cwd, *args):
        if args[:2] == ("rev-parse", "--absolute-git-dir"):
            return gitdir
        if args == ("rev-parse", "HEAD"):
            return head
        if args[:3] == ("rev-parse", "--abbrev-ref", "HEAD"):
            return "feature/x"
        if args[0] == "rev-parse" and "--verify" in args:
            return base_sha
        if args[:2] == ("remote", "get-url"):
            return remote
        return None
    return run


def _gitdir(tmp_path, name="_gitdir"):
    path = str(tmp_path / name)
    os.makedirs(path, exist_ok=True)
    return path


def _journal(session_dir):
    return RD.read_journal(session_dir)


def _outcomes(session_dir, outcome):
    return [e for e in _journal(session_dir) if e.get("outcome") == outcome]


# =============================================================================================
# §1 bootstrap: session id + seat map
# =============================================================================================

def test_fresh_next_mints_a_session_id_and_keeps_the_skill_written_meta_keys(tmp_path):
    """The SKILL owns meta.json; minting MERGES into it, so `baseRef` & co. survive."""
    d = str(tmp_path / "s")
    os.makedirs(d)
    RR.atomic_write_json(os.path.join(d, RR.META_FILE),
                         {"baseRef": "c" * 40, "repoRoot": "/repo", "mode": "branch"})
    out = RD.cmd_next(d, _cfg())
    assert out["ok"]
    with open(os.path.join(d, RR.META_FILE), encoding="utf-8") as fh:
        meta = json.load(fh)
    assert meta["baseRef"] == "c" * 40 and meta["repoRoot"] == "/repo" and meta["mode"] == "branch"
    assert isinstance(meta["sessionId"], str) and len(meta["sessionId"]) == 32


def test_next_refuses_session_id_unmintable(tmp_path):
    """A/B — the same call on a parseable meta.json SUCCEEDS; only an unparseable one refuses (and
    the file is never clobbered: it is the only record of what the session was)."""
    ok_dir = str(tmp_path / "ok")
    os.makedirs(ok_dir)
    RR.atomic_write_json(os.path.join(ok_dir, RR.META_FILE), {"baseRef": "c" * 40})
    assert RD.cmd_next(ok_dir, _cfg())["ok"] is True

    bad = str(tmp_path / "bad")
    os.makedirs(bad)
    with open(os.path.join(bad, RR.META_FILE), "w", encoding="utf-8") as fh:
        fh.write("{not json")
    out = RD.cmd_next(bad, _cfg())
    assert out["ok"] is False and out["reason"] == "session-id-unmintable"
    assert out["detail"] == "meta-unparseable"
    with open(os.path.join(bad, RR.META_FILE), encoding="utf-8") as fh:
        assert fh.read() == "{not json"
    assert not os.path.exists(os.path.join(bad, RD.STATE_FILE))


def test_seat_map_seeds_config_and_state(tmp_path):
    seat_map_path = str(tmp_path / "seatmap.json")
    with open(seat_map_path, "w", encoding="utf-8") as fh:
        json.dump(SEAT_MAP, fh)
    d = str(tmp_path / "s")
    os.makedirs(d)
    argv = ["next", "--session-dir", d, "--seat-map", seat_map_path] + _guard_argv(d)
    assert RD.main(argv) == 0
    state = _state(d)
    assert state["config"]["seatMap"] == SEAT_MAP
    assert state["seatMap"] == SEAT_MAP


def test_seat_map_unparseable_refuses_nonzero(tmp_path, capsys):
    """A/B — a VALID seat map on the same fresh session is accepted (test above); these three
    shapes each fail loud and nonzero with their own reason."""
    for name, content in (("garbage", "{nope"), ("list", "[]"), ("missing", None)):
        d = str(tmp_path / ("s-" + name))
        os.makedirs(d)
        path = str(tmp_path / (name + ".json"))
        if content is not None:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(content)
        rc = RD.main(["next", "--session-dir", d, "--seat-map", path] + _guard_argv(d))
        out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
        assert rc == 1
        assert out["reason"] == "seat-map-unparseable", (name, out)


def test_seat_map_on_non_fresh_state_refuses_nonzero(tmp_path, capsys):
    seat_map_path = str(tmp_path / "seatmap.json")
    with open(seat_map_path, "w", encoding="utf-8") as fh:
        json.dump(SEAT_MAP, fh)
    d = str(tmp_path / "s")
    os.makedirs(d)
    # A/B: fresh state accepts it.
    assert RD.main(["next", "--session-dir", d, "--seat-map", seat_map_path]
                   + _guard_argv(d)) == 0
    capsys.readouterr()
    rc = RD.main(["next", "--session-dir", d, "--seat-map", seat_map_path]
                 + _guard_argv(d, fresh=False))
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert rc == 1 and out["reason"] == "seat-map-not-fresh-state"


def _guard_argv(session_dir, fresh=True):
    """The extra argv a CLI `next` needs to satisfy the base guard (a real two-commit repo +
    meta.json + the real round diff). Mirrors test_round_driver's helper."""
    repo = os.path.join(session_dir, "_gitrepo")
    if not os.path.isdir(os.path.join(repo, ".git")):
        os.makedirs(repo, exist_ok=True)
        subprocess.check_call(["git", "init", "-q", "-b", "main"], cwd=repo)
        subprocess.check_call(["git", "config", "user.email", "t@t"], cwd=repo)
        subprocess.check_call(["git", "config", "user.name", "t"], cwd=repo)
        subprocess.check_call(["git", "commit", "-q", "--allow-empty", "-m", "init"], cwd=repo)
        pin = subprocess.check_output(["git", "-C", repo, "rev-parse", "HEAD"], text=True).strip()
        with open(os.path.join(repo, "f.py"), "w", encoding="utf-8") as fh:
            fh.write("a\n")
        subprocess.check_call(["git", "-C", repo, "add", "f.py"], cwd=repo)
        subprocess.check_call(["git", "-C", repo, "commit", "-q", "-m", "change"], cwd=repo)
    else:
        pin = subprocess.check_output(["git", "-C", repo, "rev-parse", "HEAD~1"],
                                      text=True).strip()
    toplevel = subprocess.check_output(["git", "-C", repo, "rev-parse", "--show-toplevel"],
                                       text=True).strip()
    meta_path = os.path.join(session_dir, RR.META_FILE)
    meta = {}
    if os.path.isfile(meta_path):
        with open(meta_path, encoding="utf-8") as fh:
            meta = json.load(fh)
        if meta.get("baseRef"):
            pin = meta["baseRef"]
    meta.update({"mode": "branch", "baseRef": pin, "baseBranch": "main", "baseFetch": "fetched",
                 "repoRoot": toplevel})
    with open(meta_path, "w", encoding="utf-8") as fh:
        json.dump(meta, fh)
    diffpath = os.path.join(session_dir, "round-1", "diff.txt")
    os.makedirs(os.path.dirname(diffpath), exist_ok=True)
    with open(diffpath, "w", encoding="utf-8") as fh:
        fh.write(subprocess.check_output(["git", "-C", repo, "diff", "%s...HEAD" % pin],
                                         text=True))
    argv = ["--repo-root", repo]
    if fresh:
        argv += ["--diff-path", diffpath]
    return argv


# =============================================================================================
# §2 the schema matrix
# =============================================================================================

def test_v2_state_hash_is_unchanged_by_this_change(tmp_path):
    """THE hash-preservation rule. `state_hash` hashes the WHOLE canonical state, so a v3 default
    injected on load would invalidate an already-emitted `expectedStateHash` and break every
    in-flight session's next `submit`. The expected hex was computed with the PRE-#723 module."""
    d = str(tmp_path / "v2")
    os.makedirs(d)
    with open(os.path.join(d, RD.STATE_FILE), "w", encoding="utf-8") as fh:
        json.dump(V2_STATE, fh)
    ok, loaded = RD.load_state(d)
    assert ok
    assert loaded["schemaVersion"] == 2
    assert RD.state_hash(loaded) == V2_STATE_HASH_BEFORE_723
    # and no v3 key was written into the dict on load
    assert set(loaded) == set(V2_STATE)


def test_new_state_is_v3_and_load_accepts_both(tmp_path):
    assert RD.new_state(_cfg())["schemaVersion"] == RD.STATE_SCHEMA_VERSION == 3
    assert RD.SUPPORTED_STATE_VERSIONS == (2, 3)
    d = str(tmp_path / "v1")
    os.makedirs(d)
    with open(os.path.join(d, RD.STATE_FILE), "w", encoding="utf-8") as fh:
        json.dump({"schemaVersion": 1, "rounds": {}}, fh)
    ok, reason = RD.load_state(d)
    assert ok is False and "fresh session dir" in reason


@pytest.mark.parametrize("cmd", ["advance", "record-result", "record-missing", "attest"])
def test_v2_session_is_refused_by_every_new_subcommand(tmp_path, adapters, cmd):
    """A/B — the SAME call against a v3 session gets past this gate (it fails later, on its own
    merits, or succeeds); only the v2 session is refused `legacy-session-use-next-submit`."""
    v3 = _session(tmp_path, name="v3")
    v2 = str(tmp_path / "v2")
    os.makedirs(v2)
    state = copy.deepcopy(_state(v3))
    state["schemaVersion"] = 2
    with open(os.path.join(v2, RD.STATE_FILE), "w", encoding="utf-8") as fh:
        json.dump(state, fh)
    RR.atomic_write_json(os.path.join(v2, RR.META_FILE), {"sessionId": _session_id(v3)})

    def call(session_dir):
        if cmd == "advance":
            return RD.cmd_advance(session_dir, git=_fake_git(_gitdir(tmp_path)))
        if cmd == "record-result":
            return RD.cmd_record_result(session_dir, "code-reviewer")
        if cmd == "record-missing":
            return RD.cmd_record_missing(session_dir, "code-reviewer", 0, "forfeit")
        return RD.cmd_attest(session_dir, "1", "note")

    assert call(v2)["reason"] == RD.LEGACY_SESSION_REFUSAL
    assert call(v3).get("reason") != RD.LEGACY_SESSION_REFUSAL
    assert any(e.get("reason") == RD.LEGACY_SESSION_REFUSAL for e in _journal(v2))


def test_next_and_submit_still_finish_a_v2_session_unchanged(tmp_path):
    """`next`/`submit` are NOT gated on v3 — an in-flight v2 session finishes exactly as before,
    and its receipt is `receipt-certified/2` (today's shape)."""
    d = _session(tmp_path)
    state = _state(d)
    state["schemaVersion"] = 2
    with open(os.path.join(d, RD.STATE_FILE), "w", encoding="utf-8") as fh:
        json.dump(state, fh)
    pend = RD.cmd_next(d)
    assert pend["ok"] and pend["phase"] == RD.P_PANEL
    seats = {dim: {"findings": []} for dim in RD.DIMENSIONS}
    out = RD.cmd_submit(d, pend["phase"], pend["attempt"], pend["expectedStateHash"],
                        {"seats": seats})
    assert out["ok"] is True
    assert _state(d)["schemaVersion"] == 2


def test_receipt_version_derives_from_the_state_version():
    v3 = RD.new_state(_cfg())
    v3["terminal"] = "converged"
    v3["certification"] = {"shape": "audited-chain"}
    r3 = RD.build_receipt(v3)
    assert r3["schemaVersion"] == 3 and RD.receipt_kind(r3) == "receipt-certified/3"
    assert RD.validate_receipt(r3) == (True, None)

    v2 = copy.deepcopy(v3)
    v2["schemaVersion"] = 2
    r2 = RD.build_receipt(v2)
    assert r2["schemaVersion"] == 2 and RD.receipt_kind(r2) == "receipt-certified/2"
    assert RD.validate_receipt(r2) == (True, None)
    # today's shape, unchanged: no key was added to the v2 receipt
    assert set(r2) == set(r3)


def test_validate_receipt_certified_requires_certification_and_an_allowlisted_verdict():
    state = RD.new_state(_cfg())
    state["terminal"] = "converged"
    state["certification"] = {"shape": "audited-chain"}
    receipt = RD.build_receipt(state)
    assert RD.validate_receipt(receipt)[0] is True           # A/B: the un-refused shape

    no_cert = dict(receipt)
    no_cert.pop("certification")
    ok, why = RD.validate_receipt(no_cert)
    assert ok is False and "certification" in why

    null_cert = dict(receipt, certification=None)
    ok, why = RD.validate_receipt(null_cert)
    assert ok is False and "certification" in why

    bad_verdict = dict(receipt, verdict="looks-fine")
    ok, why = RD.validate_receipt(bad_verdict)
    assert ok is False and "not one of" in why

    smuggled = dict(receipt)
    smuggled["schemaVersion"] = 4
    ok, why = RD.validate_receipt(smuggled)
    assert ok is False and "schemaVersion" in why


def test_validate_receipt_attested_shape_forbids_a_certification_block(tmp_path, adapters):
    d, receipt = _attested_session(tmp_path, adapters)
    assert RD.receipt_kind(receipt) == "receipt-attested/1"
    assert RD.validate_receipt(receipt) == (True, None)      # A/B: the un-refused shape
    assert "certification" not in receipt and "certificationShape" not in receipt

    with_cert = dict(receipt, certification={"shape": "audited-chain"})
    ok, why = RD.validate_receipt(with_cert)
    assert ok is False and "attestation is NOT a certification" in why

    no_attestation = dict(receipt)
    no_attestation.pop("attestation")
    ok, why = RD.validate_receipt(no_attestation)
    assert ok is False and "attestation" in why

    wrong_verdict = dict(receipt, verdict="converged")
    ok, why = RD.validate_receipt(wrong_verdict)
    assert ok is False and RD.ATTESTED_VERDICT in why


# =============================================================================================
# §3 record-result / record-missing
# =============================================================================================

def test_record_result_stores_the_envelope_and_journals_the_payload_hash(tmp_path, adapters):
    d = _session(tmp_path)
    _land(d, "code-reviewer")
    out = RD.cmd_record_result(d, "code-reviewer")
    assert out["ok"] is True and out["seat"] == "code-reviewer"
    stored, err = RR.read_json(out["storePath"])
    assert err is None and stored["seat"] == "code-reviewer"
    assert out["payloadSha256"] == stored["payloadSha256"]
    events = _outcomes(d, "recorded")
    assert len(events) == 1
    assert events[0]["payloadSha256"] == out["payloadSha256"]
    assert events[0]["seat"] == "code-reviewer" and events[0]["phase"] == RD.P_PANEL


def test_record_result_refuses_an_unknown_seat(tmp_path, adapters):
    d = _session(tmp_path)
    _land(d, "code-reviewer")
    assert RD.cmd_record_result(d, "code-reviewer")["ok"] is True     # A/B
    out = RD.cmd_record_result(d, "not-a-seat")
    assert out["ok"] is False and out["reason"] == "unknown-seat"


def test_record_result_refuses_a_seat_landed_for_another_phase(tmp_path, adapters):
    """The enumerated edge 'ingestion of a seat for a phase that is not the pending one' — the
    envelope's own phase is checked against the pending one."""
    d = _session(tmp_path)
    _land(d, "code-reviewer")
    assert RD.cmd_record_result(d, "code-reviewer")["ok"] is True     # A/B
    _land(d, "test-reviewer", phase=RD.P_AUDITS)
    out = RD.cmd_record_result(d, "test-reviewer")
    assert out["ok"] is False and out["reason"] == "phase-mismatch"


def test_record_result_refuses_an_attempt_that_is_not_the_pending_one(tmp_path, adapters):
    d = _session(tmp_path)
    _land(d, "code-reviewer")
    assert RD.cmd_record_result(d, "code-reviewer", attempt=0)["ok"] is True   # A/B
    _land(d, "test-reviewer")
    out = RD.cmd_record_result(d, "test-reviewer", attempt=3)
    assert out["ok"] is False and out["reason"] == "attempt-not-pending"
    assert out["pendingAttempt"] == 0


def test_record_result_refuses_bootstrap_required_on_a_fresh_dir(tmp_path, adapters):
    d = str(tmp_path / "fresh")
    os.makedirs(d)
    out = RD.cmd_record_result(d, "code-reviewer")
    assert out["ok"] is False and out["reason"] == "bootstrap-required"
    # A/B: after `next` the same call gets past bootstrap (it now refuses landing-missing).
    RD.cmd_next(d, _cfg())
    assert RD.cmd_record_result(d, "code-reviewer")["reason"] == "landing-missing"


def test_record_result_refuses_when_no_phase_is_pending(tmp_path, adapters):
    d = _session(tmp_path)
    _land(d, "code-reviewer")
    assert RD.cmd_record_result(d, "code-reviewer")["ok"] is True      # A/B
    state = _state(d)
    state["pending"] = None
    RD.save_state(d, state)
    out = RD.cmd_record_result(d, "code-reviewer")
    assert out["ok"] is False and out["reason"] == "no-pending-phase"


def test_record_result_supersede_is_a_compare_and_swap(tmp_path, adapters):
    d = _session(tmp_path)
    first = _land_and_record(d, "code-reviewer")
    # a second ingest without --supersede is refused: the record is immutable
    _land(d, "code-reviewer", payload={"findings": ["x"]})
    assert RD.cmd_record_result(d, "code-reviewer")["reason"] == "store-exists"
    assert RD.cmd_record_result(d, "code-reviewer", supersede=True)["reason"] \
        == "cas-expect-required"
    assert RD.cmd_record_result(d, "code-reviewer", supersede=True,
                                expect_sha256="dead")["reason"] == "cas-mismatch"
    # A/B: the CAS with the RIGHT expectation succeeds
    out = RD.cmd_record_result(d, "code-reviewer", supersede=True,
                               expect_sha256=first["payloadSha256"])
    assert out["ok"] is True and out["superseded"] is True


def test_advance_after_supersede_does_not_journal_orphan(tmp_path, adapters):
    """Reproduction for finding 3: supersede journals both payload hashes, but reconcile keys on
    slot identity — the same pending phase must advance cleanly."""
    d = _session(tmp_path)
    first = _land_and_record(d, "code-reviewer")
    replacement = {"findings": ["replaced"], "confidence": "high", "seat": "code-reviewer",
                   "verificationReceipt": {"ran": True}}
    _land(d, "code-reviewer", payload=replacement)
    out = RD.cmd_record_result(d, "code-reviewer", supersede=True,
                               expect_sha256=first["payloadSha256"])
    assert out["ok"] is True and out["superseded"] is True
    for seat in RD.DIMENSIONS:
        if seat == "code-reviewer":
            continue
        _land_and_record(d, seat)
    assert _advance(d, tmp_path)["ok"] is True


def test_advance_records_adapter_provenance_on_the_round_entry_and_receipt(tmp_path, adapters):
    """Adapter trust disclosures must survive advance into durable state and the terminal receipt."""
    d = _session(tmp_path)
    _record_all_panel_seats(d)
    mismatch = [{"seat": "code-reviewer", "occurrence": 0, "echo": "cursor", "manifest": "codex"}]

    def assemble_with_provenance(phase, envelopes, state, config, dispatch_manifest=None,
                                 canary=None, session_dir=None):
        seats = {}
        for env in (envelopes or []):
            seat = env.get("seat")
            if env.get("schema") == RR.SEAT_MISSING_SCHEMA:
                seats[seat] = {"findings": [], "missing": True}
            else:
                seats[seat] = env.get("payload") or {"findings": []}
        return {"seats": seats,
                "provenance": {"vendorEchoMismatch": mismatch,
                               "dispatchManifestUnavailable": True}}, None

    adapters.assemble = assemble_with_provenance
    assert _advance(d, tmp_path)["ok"] is True
    prov = _state(d)["rounds"]["1"]["adapterProvenance"]
    assert prov["vendorEchoMismatch"] == mismatch
    assert prov["dispatchManifestUnavailable"] is True
    receipt = RD.build_receipt(_state(d), d)
    rd = next(r for r in receipt["rounds"] if r["round"] == 1)
    assert rd["adapterProvenance"] == prov
    degraded = "\n".join(receipt["degraded"])
    assert "adapter-provenance (round 1): vendor echo mismatch" in degraded
    assert "adapter-provenance (round 1): dispatch manifest unavailable" in degraded


def test_record_result_refuses_a_payload_fault(tmp_path, adapters):
    d = _session(tmp_path)
    _land(d, "code-reviewer")
    assert RD.cmd_record_result(d, "code-reviewer")["ok"] is True      # A/B
    adapters.faults["test-reviewer"] = "findings must be a list"
    _land(d, "test-reviewer")
    pend = _pending(d)
    out = RD.cmd_record_result(d, "test-reviewer")
    assert out["ok"] is False and out["reason"] == "payload-fault"
    assert out["detail"] == "findings must be a list"
    spath = RR.store_path(d, pend["round"], pend["phase"], RR.storage_key("test-reviewer"),
                          pend["attempt"])
    assert not os.path.exists(spath), "payload-fault must leave no store file"
    adapters.faults.pop("test-reviewer")
    _land(d, "test-reviewer")
    assert RD.cmd_record_result(d, "test-reviewer")["ok"] is True


def _fixer_session(tmp_path, adapters, name="fx"):
    """A session parked at the dispatch-fixer phase with a one-seat roster."""
    d = _session(tmp_path, name=name)
    state = _state(d)
    state["step"] = RD.P_FIXER
    state["pending"] = {"action": RD.P_FIXER, "round": 1, "phase": RD.P_FIXER, "attempt": 0,
                        "payload": {}}
    RD.save_state(d, state)
    return d


def test_fixer_head_diff_is_copied_into_the_store_at_record_time(tmp_path, adapters):
    d = _fixer_session(tmp_path, adapters)
    head_path = str(tmp_path / "head.diff")
    with open(head_path, "w", encoding="utf-8") as fh:
        fh.write("diff --git a/f.py b/f.py\n+fixed\n")
    _land(d, "dispatch-fixer", payload={"fixes": [], "headDiffPath": head_path})
    out = RD.cmd_record_result(d, "dispatch-fixer")
    assert out["ok"] is True
    store_copy = out["headDiffStorePath"]
    assert os.path.isabs(store_copy) and store_copy.startswith(d)
    with open(store_copy, encoding="utf-8") as fh:
        assert fh.read() == "diff --git a/f.py b/f.py\n+fixed\n"
    stored, _err = RR.read_json(out["storePath"])
    assert stored["payload"]["headDiffStorePath"] == store_copy
    # the stored envelope stays self-consistent, and the seat's landed hash is preserved
    assert stored["payloadSha256"] == RR.payload_sha256(stored["payload"])
    assert stored["landedPayloadSha256"] != stored["payloadSha256"]
    # a later mutation of the caller's own path cannot change what the record attests
    with open(head_path, "w", encoding="utf-8") as fh:
        fh.write("TAMPERED\n")
    with open(store_copy, encoding="utf-8") as fh:
        assert fh.read() == "diff --git a/f.py b/f.py\n+fixed\n"


@pytest.mark.parametrize("head_path,label", [
    ("relative/head.diff", "not-absolute"),
    ("/nonexistent/absolutely/head.diff", "unreadable"),
], ids=["not-absolute", "unreadable"])
def test_fixer_head_diff_refuses_at_record_time(tmp_path, adapters, head_path, label):
    """A/B — a READABLE absolute path on the same session records fine (test above); these two
    refuse at RECORD time rather than degrading silently at fold time."""
    d = _fixer_session(tmp_path, adapters, name="fx-" + label)
    _land(d, "dispatch-fixer", payload={"fixes": [], "headDiffPath": head_path})
    out = RD.cmd_record_result(d, "dispatch-fixer")
    assert out["ok"] is False and out["reason"] == "head-diff-unreadable"
    # fail-closed: nothing was stored
    pend = _pending(d)
    spath = RR.store_path(d, pend["round"], pend["phase"], RR.storage_key("dispatch-fixer"),
                          pend["attempt"])
    assert not os.path.exists(spath)


def test_record_result_without_a_seat_refuses_unless_sweeping(tmp_path, adapters):
    d = _session(tmp_path)
    _land(d, "code-reviewer")
    out = RD.cmd_record_result(d)
    assert out["ok"] is False and out["reason"] == "seat-required"
    # A/B: the same call WITH a seat records, and a seat-less --sweep is legitimate
    assert RD.cmd_record_result(d, "code-reviewer")["ok"] is True
    assert RD.cmd_record_result(d, sweep=True)["ok"] is True


def test_record_result_sweep_ingests_every_unclaimed_landing(tmp_path, adapters):
    d = _session(tmp_path)
    for seat in RD.DIMENSIONS:
        _land(d, seat)
    out = RD.cmd_record_result(d, sweep=True)
    assert out["ok"] is True and sorted(out["recorded"]) == sorted(RD.DIMENSIONS)
    # idempotent: a second sweep records nothing new and does not manufacture an error
    again = RD.cmd_record_result(d, sweep=True)
    assert again["ok"] is True and again["recorded"] == []
    assert len(_outcomes(d, "recorded")) == len(RD.DIMENSIONS)


def test_record_missing_writes_and_ingests_a_seat_missing_envelope(tmp_path, adapters):
    d = _session(tmp_path)
    out = RD.cmd_record_missing(d, "security-reviewer", 0, "forfeit")
    assert out["ok"] is True
    stored, err = RR.read_json(out["storePath"])
    assert err is None
    assert stored["schema"] == RR.SEAT_MISSING_SCHEMA and stored["reason"] == "forfeit"
    assert stored["seat"] == "security-reviewer"
    assert [e["seat"] for e in _outcomes(d, "recorded")] == ["security-reviewer"]


def test_record_missing_refuses_an_unreadable_evidence_path(tmp_path, adapters):
    d = _session(tmp_path)
    evidence = str(tmp_path / "ev.txt")
    with open(evidence, "w", encoding="utf-8") as fh:
        fh.write("the seat forfeited at 12:01")
    assert RD.cmd_record_missing(d, "code-reviewer", 0, "forfeit",
                                 evidence_path=evidence)["ok"] is True      # A/B
    out = RD.cmd_record_missing(d, "test-reviewer", 0, "forfeit",
                                evidence_path=str(tmp_path / "nope.txt"))
    assert out["ok"] is False and out["reason"] == "evidence-unreadable"


def test_record_missing_refuses_an_unknown_reason_and_an_unknown_seat(tmp_path, adapters):
    d = _session(tmp_path)
    assert RD.cmd_record_missing(d, "code-reviewer", 0, "timeout")["ok"] is True   # A/B
    bad_reason = RD.cmd_record_missing(d, "test-reviewer", 0, "because")
    assert bad_reason["ok"] is False and bad_reason["reason"] == "missing-reason"
    unknown = RD.cmd_record_missing(d, "not-a-seat", 0, "timeout")
    assert unknown["ok"] is False and unknown["reason"] == "unknown-seat"


def test_record_missing_refuses_an_attempt_that_is_not_pending(tmp_path, adapters):
    d = _session(tmp_path)
    assert RD.cmd_record_missing(d, "code-reviewer", 0, "killed")["ok"] is True    # A/B
    out = RD.cmd_record_missing(d, "test-reviewer", 7, "killed")
    assert out["ok"] is False and out["reason"] == "attempt-not-pending"


# =============================================================================================
# §4 advance
# =============================================================================================

def _advance(d, tmp_path, **kw):
    return RD.cmd_advance(d, git=_fake_git(_gitdir(tmp_path)), **kw)


def test_next_emits_orders_manifest_for_bootstrap_dispatch(tmp_path, adapters):
    """Round-1 panel dispatch is created by `next` before any `advance` — it still needs an anchor."""
    d = _session(tmp_path)
    pend = _pending(d)
    assert pend["phase"] == RD.P_PANEL
    manifest_path = RD._orders_manifest_path(d, pend["round"], pend["phase"], pend["attempt"])
    assert os.path.exists(manifest_path)
    anchor = RD._orders_anchor(_state(d), d, pend["round"], pend["phase"], pend["attempt"])
    assert anchor is not None and anchor["manifestSha256"]


def test_advance_reloads_state_after_acquiring_lock(tmp_path, adapters, monkeypatch):
    """`cmd_advance` must load state under the session lock, not reuse a pre-lock snapshot."""
    d = _session(tmp_path)
    _record_all_panel_seats(d)
    original = RD._load_driver_state
    load_count = [0]

    def counting_load(session_dir, cmd):
        load_count[0] += 1
        if cmd == "advance":
            lock_path = RR.session_lock_path(session_dir)
            assert os.path.exists(lock_path), (
                "state must load only after the session lock is held")
        state, refusal = original(session_dir, cmd)
        if cmd == "advance" and refusal is None:
            state = dict(state)
            state["_lockReloadMarker"] = "fresh-under-lock"
            RD.save_state(session_dir, state)
        return state, refusal

    monkeypatch.setattr(RD, "_load_driver_state", counting_load)
    seen = []
    real = RD._advance_locked

    def capture(session_dir, state, **kw):
        seen.append(state.get("_lockReloadMarker"))
        return real(session_dir, state, **kw)

    monkeypatch.setattr(RD, "_advance_locked", capture)
    assert _advance(d, tmp_path)["ok"] is True
    assert seen == ["fresh-under-lock"]
    assert load_count[0] >= 1


def test_advance_folds_a_complete_phase_and_emits_the_next_action(tmp_path, adapters):
    d = _session(tmp_path)
    _record_all_panel_seats(d)
    out = _advance(d, tmp_path)
    assert out["ok"] is True
    assert out["folded"] == {"phase": RD.P_PANEL, "round": 1, "attempt": 0}
    assert out["nextAction"]["phase"] == RD.P_VERIFIERS
    assert _state(d)["step"] == RD.P_VERIFIERS
    assert len(_outcomes(d, "advanced")) == 1
    # the adapter was asked to assemble from the DURABLE records — a LIST of envelopes, each
    # carrying its own seat and slot occurrence (the real adapter indexes on that pair)
    call = adapters.assembled[-1]
    assert call["phase"] == RD.P_PANEL
    assert isinstance(call["envelopes"], list)
    assert sorted(e["seat"] for e in call["envelopes"]) == sorted(RD.DIMENSIONS)
    assert {e["occurrence"] for e in call["envelopes"]} == {0}


def test_advance_emits_the_orders_manifest_and_mirrors_its_hash_into_state(tmp_path, adapters):
    d = _session(tmp_path)
    adapters.rosters[RD.P_VERIFIERS] = ["src/f.py:3"]
    _record_all_panel_seats(d)
    out = _advance(d, tmp_path)
    assert out["ok"] is True
    manifest_path = RD._orders_manifest_path(d, 1, RD.P_VERIFIERS, 0)
    manifest, err = RR.read_json(manifest_path)
    assert err is None
    assert manifest["seats"]["src/f.py:3"] == {
        "storeKey": RR.storage_key("src/f.py:3"), "vendor": None, "model": None, "engine": None,
        "resultContract": RR.SEAT_RESULT_SCHEMA}
    emitted = [e for e in _outcomes(d, "orders-emitted") if e.get("phase") == RD.P_VERIFIERS]
    assert len(emitted) == 1
    anchor = RD._orders_anchor(_state(d), d, 1, RD.P_VERIFIERS, 0)
    assert anchor["manifestSha256"] == emitted[0]["manifestSha256"]
    # the anchor rides the state-hash chain, and the emitted hash is the one ingestion checks
    assert out["nextAction"]["expectedStateHash"] == RD.state_hash(_state(d))
    assert anchor["orders"]["src/f.py:3"] == RR.NOT_EMITTED
    # an envelope claiming a DIFFERENT manifest hash is refused against the emission-time anchor
    pend = _pending(d)
    _land(d, "src/f.py:3", pend=pend, manifestSha256="deadbeef")
    assert RD.cmd_record_result(d, "src/f.py:3")["reason"] == "manifest-anchor-mismatch"
    # A/B: the envelope carrying the anchored hash records fine
    _land(d, "src/f.py:3", pend=pend)
    assert RD.cmd_record_result(d, "src/f.py:3")["ok"] is True


def test_advance_refuses_an_incomplete_roster_naming_every_missing_seat(tmp_path, adapters):
    """A/B — the SAME phase with every seat recorded folds (below); one seat short refuses and the
    refusal enumerates every absent seat BY NAME."""
    complete = _session(tmp_path, name="complete")
    _record_all_panel_seats(complete)
    assert _advance(complete, tmp_path)["ok"] is True

    d = _session(tmp_path, name="short")
    _record_all_panel_seats(d, seats=["code-reviewer", "test-reviewer"])
    out = _advance(d, tmp_path)
    assert out["ok"] is False and out["reason"] == "incomplete-roster"
    assert out["seats"] == sorted(["architecture-reviewer", "security-reviewer",
                                   "premortem-reviewer"])
    for seat in out["seats"]:
        assert seat in out["detail"]
    # nothing folded
    assert _state(d)["step"] == RD.P_PANEL
    assert _outcomes(d, "advanced") == []


def test_advance_completes_with_a_missing_envelope_for_the_absent_seat(tmp_path, adapters):
    """A seat with no artifact is COMPLETE once its absence is recorded — that is the difference
    between 'not yet' and 'never came'."""
    d = _session(tmp_path)
    _record_all_panel_seats(d, seats=["code-reviewer", "test-reviewer", "architecture-reviewer",
                                      "security-reviewer"])
    assert _advance(d, tmp_path)["reason"] == "incomplete-roster"
    assert RD.cmd_record_missing(d, "premortem-reviewer", 0, "forfeit")["ok"] is True
    assert _advance(d, tmp_path)["ok"] is True


def test_advance_refuses_a_held_lock_naming_the_holder(tmp_path, adapters):
    d = _session(tmp_path)
    _record_all_panel_seats(d)
    RR.atomic_write_json(RR.session_lock_path(d), {"pid": 4321, "createdAt": "2026-08-07T01:02:03"})
    out = _advance(d, tmp_path)
    assert out["ok"] is False and out["reason"] == "advance-locked"
    assert out["holder"] == {"pid": 4321, "createdAt": "2026-08-07T01:02:03"}
    # --break-lock breaks it, JOURNALS the broken holder, and is a caller-error (never eligible)
    broken = _advance(d, tmp_path, break_lock=True)
    assert broken["ok"] is True
    events = _outcomes(d, "lock-broken")
    assert len(events) == 1
    assert events[0]["holder"] == {"pid": 4321, "createdAt": "2026-08-07T01:02:03"}
    assert events[0]["fault"] == RD.FAULT_CALLER
    assert broken["brokeLock"]["pid"] == 4321


def test_advance_releases_the_lock_so_the_next_advance_can_take_it(tmp_path, adapters):
    d = _session(tmp_path)
    _record_all_panel_seats(d)
    assert _advance(d, tmp_path)["ok"] is True
    assert not os.path.exists(RR.session_lock_path(d))
    # the verifiers phase has an empty roster, so this second advance folds immediately
    assert _advance(d, tmp_path)["ok"] is True


def test_advance_refuses_a_journal_orphan_naming_the_seat(tmp_path, adapters):
    """The one machinery-failure class in reconcile: the LOG claims a record no store file carries.
    A/B — the same session without the orphan folds."""
    ok_session = _session(tmp_path, name="clean")
    _record_all_panel_seats(ok_session)
    assert _advance(ok_session, tmp_path)["ok"] is True

    d = _session(tmp_path, name="orphan")
    _record_all_panel_seats(d)
    pend = _pending(d)
    spath = RR.store_path(d, pend["round"], pend["phase"], RR.storage_key("security-reviewer"),
                          pend["attempt"])
    lpath = RR.landing_path(d, pend["round"], pend["phase"], RR.storage_key("security-reviewer"),
                            pend["attempt"])
    os.remove(spath)     # the journal still claims this seat's payload hash
    os.remove(lpath)     # ... and there is no landing to re-ingest from
    out = _advance(d, tmp_path)
    assert out["ok"] is False and out["reason"] == "journal-orphan"
    assert out["seats"] == ["security-reviewer"]
    assert "security-reviewer" in out["detail"]
    orphan_events = [e for e in _journal(d) if e.get("reason") == "journal-orphan"]
    assert orphan_events and orphan_events[-1]["fault"] == RD.FAULT_INTERNAL


def test_advance_refuses_when_the_roster_cannot_be_computed(tmp_path, adapters):
    d = _session(tmp_path)
    _record_all_panel_seats(d)
    adapters.roster_reasons[RD.P_PANEL] = "seat-map-unavailable"
    out = _advance(d, tmp_path)
    assert out["ok"] is False and out["reason"] == "roster-unavailable"
    assert out["detail"] == "seat-map-unavailable"
    # A/B: with the roster computable the same records fold
    del adapters.roster_reasons[RD.P_PANEL]
    assert _advance(d, tmp_path)["ok"] is True


def test_advance_refuses_when_assemble_refuses(tmp_path, adapters):
    d = _session(tmp_path)
    _record_all_panel_seats(d)
    adapters.assemble_reason = "seat payload missing a verification receipt"
    out = _advance(d, tmp_path)
    assert out["ok"] is False and out["reason"] == "assemble-refused"
    assert out["detail"] == "seat payload missing a verification receipt"
    assert _state(d)["step"] == RD.P_PANEL
    # A/B
    adapters.assemble_reason = None
    assert _advance(d, tmp_path)["ok"] is True


def test_advance_refuses_when_no_phase_is_pending(tmp_path, adapters):
    d = _session(tmp_path)
    _record_all_panel_seats(d)
    state = _state(d)
    state["pending"] = None
    RD.save_state(d, state)
    out = _advance(d, tmp_path)
    assert out["ok"] is False and out["reason"] == "no-pending-phase"
    # A/B: restore the pending step and the same records fold
    RD.cmd_next(d)
    assert _advance(d, tmp_path)["ok"] is True


def test_advance_refuses_a_fold_the_submit_chokepoint_rejects(tmp_path, adapters):
    """The assembled artifact still passes through every `submit` fence — a mis-keyed seats map is
    refused at the chokepoint, and `advance` surfaces it rather than folding it."""
    d = _session(tmp_path)
    _record_all_panel_seats(d)

    def bad_assemble(phase, envelopes, state, config, dispatch_manifest=None, canary=None,
                     session_dir=None):
        return {"seats": {"architecture": {"findings": []}}}, None

    adapters.assemble = bad_assemble
    out = _advance(d, tmp_path)
    assert out["ok"] is False and out["reason"] == "fold-refused"
    assert "seat key" in out["detail"]


def test_advance_journals_an_unhandled_internal_exception_as_attestable(tmp_path, adapters):
    """An exception inside the adapter/fold internals is MACHINERY failure: it is journalled
    `driver-internal-error` with a traceback HASH (never the traceback text, which can carry paths
    and payload fragments) and `attest` can bind to it. A/B — the same phase folds when the
    internals do not raise."""
    d = _session(tmp_path)
    _record_all_panel_seats(d)

    def boom(phase, envelopes, state, config, dispatch_manifest=None, canary=None,
             session_dir=None):
        raise RuntimeError("adapter exploded")

    adapters.assemble = boom
    out = _advance(d, tmp_path)
    assert out["ok"] is False and out["reason"] == "driver-internal-exception"
    assert out["detail"] == "RuntimeError: adapter exploded"
    assert len(out["tracebackSha256"]) == 64
    seq = _seq_of(d, "driver-internal-exception")
    binding, why = RD._resolve_failure_ref(d, str(seq))
    assert why is None and binding["class"] == "driver-internal-exception"
    # the lock is released even on an unhandled exception
    assert not os.path.exists(RR.session_lock_path(d))
    # A/B
    adapters.assemble = FakeAdapters.assemble.__get__(adapters, FakeAdapters)
    assert _advance(d, tmp_path)["ok"] is True


@pytest.mark.parametrize("phase,reason", [
    (RD.P_JUDGMENT, "advance-judgment-park"),
    (RD.P_STALL, "advance-stall-park"),
], ids=["judgment", "stall"])
def test_advance_parks_unconditionally_on_the_owner_gates(tmp_path, adapters, phase, reason):
    """A/B — the same `advance` on a dispatch phase folds; the two OWNER gates park
    unconditionally, because the shipped default pre-authorizes nothing."""
    ok_session = _session(tmp_path, name="folds-" + reason)
    _record_all_panel_seats(ok_session)
    assert _advance(ok_session, tmp_path)["ok"] is True

    d = _session(tmp_path, name="park-" + reason)
    state = _state(d)
    state["step"] = phase
    state["pending"] = {"action": phase, "round": 1, "phase": phase, "attempt": 0, "payload": {}}
    RD.save_state(d, state)
    out = _advance(d, tmp_path)
    assert out["ok"] is False and out["reason"] == reason
    parks = [e for e in _journal(d) if e.get("reason") == reason]
    assert parks and parks[-1]["fault"] == RD.FAULT_CALLER


def test_run_loop_judgment_default_is_unchanged(tmp_path):
    """The advance-path park is a change on the ADVANCE path only. `run_loop`'s library default —
    no judgment gate wired → fix every judgment finding as suggested — must still do exactly that."""
    payload = {"findings": [{"id": "f1"}, {"id": "f2"}]}
    assert RD._run_seam({"io": {}}, RD.P_JUDGMENT, payload, RD.new_state(_cfg()), _cfg()) == {
        "dispositions": [{"id": "f1", "disposition": "fix-as-suggested"},
                         {"id": "f2", "disposition": "fix-as-suggested"}]}


def test_hand_submit_and_advance_may_not_interleave(tmp_path, adapters):
    """A/B — a pure-advance session advances, and a pure-submit session submits; MIXING the two
    within one session is refused loudly and journalled, in both directions."""
    advanced = _session(tmp_path, name="adv")
    _record_all_panel_seats(advanced)
    assert _advance(advanced, tmp_path)["ok"] is True
    pend = RD.cmd_next(advanced)
    hand = RD.cmd_submit(advanced, pend["phase"], pend["attempt"], pend["expectedStateHash"],
                         {"verdicts": []})
    assert hand["ok"] is False and hand["reason"] == "advance-submit-interleaved"
    assert _outcomes(advanced, "advance-submit-interleaved")

    submitted = _session(tmp_path, name="sub")
    p = _pending(submitted)
    seats = {dim: {"findings": []} for dim in RD.DIMENSIONS}
    assert RD.cmd_submit(submitted, p["phase"], p["attempt"], RD.state_hash(_state(submitted)),
                         {"seats": seats})["ok"] is True
    RD.cmd_next(submitted)
    out = _advance(submitted, tmp_path)
    assert out["ok"] is False and out["reason"] == "advance-submit-interleaved"


# =============================================================================================
# §6 the sidecar (+ the terminal path)
# =============================================================================================

def _drive_to_terminal(d, tmp_path, adapters, gitdir=None):
    """Panel → verifiers → synthesis → terminal, entirely on the advance path."""
    git = _fake_git(gitdir or _gitdir(tmp_path))
    _record_all_panel_seats(d)
    out = RD.cmd_advance(d, git=git)
    assert out["ok"], out
    out = RD.cmd_advance(d, git=git)              # verifiers: empty roster
    assert out["ok"], out
    _land_and_record(d, "synthesis", payload={"grouping": None})
    out = RD.cmd_advance(d, git=git)
    assert out["ok"], out
    return out


def test_terminal_advance_writes_the_receipt_and_publishes_the_sidecar(tmp_path, adapters):
    gitdir = _gitdir(tmp_path)
    d = _session(tmp_path)
    out = _drive_to_terminal(d, tmp_path, adapters, gitdir=gitdir)
    assert out["terminal"] == "converged"
    receipt_path = os.path.join(d, RD.RECEIPT_FILE)
    with open(receipt_path, "rb") as fh:
        receipt_bytes = fh.read()
    receipt = json.loads(receipt_bytes.decode("utf-8"))
    assert RD.receipt_kind(receipt) == "receipt-certified/3"
    assert RD.validate_receipt(receipt) == (True, None)

    sidecar_path = os.path.join(gitdir, "superheroes", "review-receipt.json")
    assert out["sidecar"] == sidecar_path
    sidecar, err = RR.read_json(sidecar_path)
    assert err is None
    assert RR.validate_sidecar(sidecar) == (True, None)
    assert sidecar["schema"] == RR.SIDECAR_SCHEMA
    assert sidecar["headSha"] == "a" * 40
    assert sidecar["sessionDir"] == d and sidecar["receiptPath"] == receipt_path
    assert sidecar["verdict"] == "converged"
    stale, _why = RR.sidecar_stale(sidecar, head_sha="a" * 40, receipt_bytes=receipt_bytes,
                                   session_dir=d)
    assert stale is False


def test_sidecar_journals_repair_begin_before_it_publishes(tmp_path, adapters):
    """ORDERING IS THE CONTRACT: a sidecar is never published that the journal could not record."""
    gitdir = _gitdir(tmp_path)
    d = _session(tmp_path)
    _drive_to_terminal(d, tmp_path, adapters, gitdir=gitdir)
    outcomes = [e["outcome"] for e in _journal(d)
                if e["outcome"] in ("sidecar-repair-begin", "sidecar-repaired")]
    assert outcomes == ["sidecar-repair-begin", "sidecar-repaired"]


def test_advance_on_an_existing_terminal_is_idempotent_and_repairs_the_sidecar(tmp_path,
                                                                              adapters):
    gitdir = _gitdir(tmp_path)
    d = _session(tmp_path)
    _drive_to_terminal(d, tmp_path, adapters, gitdir=gitdir)
    sidecar_path = os.path.join(gitdir, "superheroes", "review-receipt.json")
    before = _state(d)
    # a fresh sidecar is left exactly as it is
    again = RD.cmd_advance(d, git=_fake_git(gitdir))
    assert again["ok"] is True and again["idempotent"] is True
    assert again["sidecarRepaired"] is False
    assert _state(d)["terminal"] == before["terminal"]

    # a MISSING sidecar is republished
    os.remove(sidecar_path)
    repaired = RD.cmd_advance(d, git=_fake_git(gitdir))
    assert repaired["ok"] is True and repaired["sidecarRepaired"] is True
    assert os.path.exists(sidecar_path)

    # a STALE sidecar (the head moved) is republished with the new head
    moved = RD.cmd_advance(d, git=_fake_git(gitdir, head="f" * 40))
    assert moved["sidecarRepaired"] is True
    sidecar, _err = RR.read_json(sidecar_path)
    assert sidecar["headSha"] == "f" * 40


def test_sidecar_refuses_when_the_git_dir_cannot_be_resolved(tmp_path, adapters):
    d = _session(tmp_path)
    _record_all_panel_seats(d)
    assert RD.cmd_advance(d, git=_fake_git(_gitdir(tmp_path)))["ok"] is True   # A/B

    def no_git(cwd, *args):
        return None

    state = _state(d)
    state["terminal"] = "converged"
    state["certification"] = {"shape": "audited-chain"}
    state["_receiptFinalized"] = True
    RD.save_state(d, state)
    RD._write_receipt(d, state)
    out = RD.cmd_advance(d, git=no_git)
    assert out["ok"] is False and out["reason"] == "sidecar-gitdir-unresolvable"


def test_sidecar_refuses_when_the_repo_root_is_not_a_repository(tmp_path, monkeypatch):
    """`store_core`'s shared classification answers `realpath(cwd)` for genuine greenfield — an
    IDENTITY, not a git dir. The sidecar must REFUSE and write nothing, never take that answer for
    a git dir and drop `superheroes/review-receipt.json` into a plain working directory. Real git
    seam (no injection): only a real decline reaches this branch."""
    plain = tmp_path / "plain"
    plain.mkdir()
    monkeypatch.delenv("GIT_DIR", raising=False)
    monkeypatch.delenv("GIT_WORK_TREE", raising=False)
    repo = str(tmp_path / "repo")                                             # A/B
    os.makedirs(repo)
    subprocess.check_call(["git", "init", "-q", "-b", "main"], cwd=repo)
    subprocess.check_call(["git", "config", "user.email", "t@t"], cwd=repo)
    subprocess.check_call(["git", "config", "user.name", "t"], cwd=repo)
    subprocess.check_call(["git", "commit", "-q", "--allow-empty", "-m", "init"], cwd=repo)
    d = _session(tmp_path)
    state = _state(d)
    state["terminal"] = "converged"
    state["certification"] = {"shape": "audited-chain"}
    state["_receiptFinalized"] = True
    RD.save_state(d, state)
    RD._write_receipt(d, state)          # a PUBLISHABLE session — the refusal is not a side effect
    # A/B on the SAME call: a real repository publishes; only the non-repository refuses.
    state["config"]["repoRoot"] = repo
    ok = RD._publish_sidecar(d, state)
    assert ok.get("ok") is True and os.path.exists(ok["path"]), ok

    state["config"]["repoRoot"] = str(plain)
    out = RD._publish_sidecar(d, state)
    assert out.get("ok") is not True
    assert out["reason"] == "sidecar-gitdir-unresolvable"
    assert not (plain / "superheroes").exists()


def test_sidecar_git_dir_is_per_worktree_never_the_shared_common_dir(tmp_path, monkeypatch):
    """Two sibling worktrees of ONE repository must not publish to the same receipt path — the
    common dir would collide them. Real git, real `git worktree add`."""
    monkeypatch.delenv("GIT_DIR", raising=False)
    monkeypatch.delenv("GIT_WORK_TREE", raising=False)
    repo = str(tmp_path / "repo")
    os.makedirs(repo)
    subprocess.check_call(["git", "init", "-q", "-b", "main"], cwd=repo)
    subprocess.check_call(["git", "config", "user.email", "t@t"], cwd=repo)
    subprocess.check_call(["git", "config", "user.name", "t"], cwd=repo)
    subprocess.check_call(["git", "commit", "-q", "--allow-empty", "-m", "init"], cwd=repo)
    wt_a, wt_b = str(tmp_path / "wt_a"), str(tmp_path / "wt_b")
    subprocess.check_call(["git", "-C", repo, "worktree", "add", "-q", wt_a], cwd=repo)
    subprocess.check_call(["git", "-C", repo, "worktree", "add", "-q", wt_b], cwd=repo)

    path_a = RD._sidecar_path(RD.store_core.get_worktree_gitdir(wt_a))
    path_b = RD._sidecar_path(RD.store_core.get_worktree_gitdir(wt_b))
    assert path_a != path_b
    assert path_a != RD._sidecar_path(RD.store_core.get_gitdir(wt_a))


def test_terminal_sidecar_lands_in_a_real_git_dir(tmp_path, adapters):
    """One end-to-end pass with the REAL git seam — a fake-git-only proof would never show that the
    seam's arguments resolve against a real repository."""
    d = _session(tmp_path)
    repo = str(tmp_path / "repo")
    os.makedirs(repo)
    subprocess.check_call(["git", "init", "-q", "-b", "main"], cwd=repo)
    subprocess.check_call(["git", "config", "user.email", "t@t"], cwd=repo)
    subprocess.check_call(["git", "config", "user.name", "t"], cwd=repo)
    subprocess.check_call(["git", "commit", "-q", "--allow-empty", "-m", "init"], cwd=repo)
    head = subprocess.check_output(["git", "-C", repo, "rev-parse", "HEAD"], text=True).strip()
    state = _state(d)
    state["config"]["repoRoot"] = repo
    RD.save_state(d, state)
    _record_all_panel_seats(d)
    assert RD.cmd_advance(d)["ok"] is True
    assert RD.cmd_advance(d)["ok"] is True
    _land_and_record(d, "synthesis", payload={"grouping": None})
    out = RD.cmd_advance(d)
    assert out["ok"] is True and out["terminal"] == "converged"
    sidecar_path = os.path.join(repo, ".git", "superheroes", "review-receipt.json")
    assert out["sidecar"] == sidecar_path
    sidecar, err = RR.read_json(sidecar_path)
    assert err is None and RR.validate_sidecar(sidecar) == (True, None)
    assert sidecar["headSha"] == head


# =============================================================================================
# §5 attest
# =============================================================================================

def _orphan_failure(tmp_path, adapters, name="att"):
    """A session carrying a REAL journalled `driver-internal-error` (a journal orphan)."""
    d = _session(tmp_path, name=name)
    _record_all_panel_seats(d)
    pend = _pending(d)
    os.remove(RR.store_path(d, pend["round"], pend["phase"], RR.storage_key("security-reviewer"),
                            pend["attempt"]))
    os.remove(RR.landing_path(d, pend["round"], pend["phase"],
                              RR.storage_key("security-reviewer"), pend["attempt"]))
    out = RD.cmd_advance(d, git=_fake_git(_gitdir(tmp_path, "_gd-" + name)))
    assert out["reason"] == "journal-orphan"
    seq = _seq_of(d, "journal-orphan")
    return d, seq


def _seq_of(session_dir, reason):
    for index, event in enumerate(_journal(session_dir), start=1):
        if event.get("reason") == reason:
            return index
    raise AssertionError("no journal event with reason %r" % reason)


def _attested_session(tmp_path, adapters, name="att"):
    d, seq = _orphan_failure(tmp_path, adapters, name=name)
    out = RD.cmd_attest(d, str(seq), "orphaned record; handing back uncertified",
                        git=_fake_git(_gitdir(tmp_path, "_gd-" + name)))
    assert out["ok"] is True, out
    with open(os.path.join(d, RD.RECEIPT_FILE), encoding="utf-8") as fh:
        return d, json.load(fh)


def test_attest_publishes_a_fresh_sidecar_against_the_final_receipt(tmp_path, adapters):
    """Regression: sidecar publication must hash the receipt that `cmd_attest` actually wrote."""
    gitdir = _gitdir(tmp_path, "_gd-attest-sidecar")
    d, seq = _orphan_failure(tmp_path, adapters, name="attest-sidecar")
    out = RD.cmd_attest(d, str(seq), "orphaned record; handing back uncertified",
                        git=_fake_git(gitdir))
    assert out["ok"] is True, out
    assert out["sidecar"] is not None
    assert out.get("sidecarReason") is None

    receipt_path = os.path.join(d, RD.RECEIPT_FILE)
    with open(receipt_path, "rb") as fh:
        receipt_bytes = fh.read()
    sidecar_path = os.path.join(gitdir, "superheroes", "review-receipt.json")
    assert out["sidecar"] == sidecar_path
    assert os.path.exists(sidecar_path)
    sidecar, err = RR.read_json(sidecar_path)
    assert err is None
    stale, _why = RR.sidecar_stale(sidecar, head_sha="a" * 40, receipt_bytes=receipt_bytes,
                                   session_dir=d)
    assert stale is False


def test_attest_refuses_when_sidecar_publication_fails(tmp_path, adapters):
    """A sidecar machinery failure must not ride home on `ok: True`."""
    d, seq = _orphan_failure(tmp_path, adapters, name="attest-sidecar-fail")

    def no_git(cwd, *args):
        return None

    out = RD.cmd_attest(d, str(seq), "orphaned record; handing back uncertified", git=no_git)
    assert out["ok"] is False and out["reason"] == "sidecar-gitdir-unresolvable"


def test_attest_writes_an_uncertified_receipt_with_its_evidence(tmp_path, adapters):
    d, receipt = _attested_session(tmp_path, adapters)
    assert receipt["verdict"] == RD.ATTESTED_VERDICT
    assert "certification" not in receipt
    assert receipt["attestation"]["class"] == "journal-orphan"
    assert receipt["attestation"]["note"] == "orphaned record; handing back uncertified"
    # sha256 of every artifact under the session dir except the receipt, loop-state, and live journal
    # (the receipt is written before sidecar publication, which appends sidecar-repair journal lines)
    assert receipt["artifacts"]
    assert RD.RECEIPT_FILE not in receipt["artifacts"]
    assert RD.STATE_FILE not in receipt["artifacts"]
    assert RD.JOURNAL_FILE not in receipt["artifacts"]
    for rel, digest in receipt["artifacts"].items():
        assert digest and len(digest) == 64
        with open(os.path.join(d, rel), "rb") as fh:
            assert hashlib.sha256(fh.read()).hexdigest() == digest
    assert RD.STATE_FILE not in receipt["artifacts"]
    # the FULL roster with each seat's disposition
    assert set(receipt["roster"]) == set(RD.DIMENSIONS)
    assert receipt["roster"]["security-reviewer"] == "absent"
    assert receipt["roster"]["code-reviewer"] == "recorded"
    assert _state(d)["terminal"] == RD.ATTESTED_VERDICT


def test_attest_refuses_a_caller_error_as_ineligible(tmp_path, adapters):
    """ELIGIBILITY IS ALLOWLIST-ONLY. A/B — the eligible `driver-internal-error` in the SAME journal
    attests; the caller-error event beside it does not."""
    d, seq = _orphan_failure(tmp_path, adapters)
    RD.cmd_record_result(d, "not-a-seat")                 # a caller error, journalled
    caller_seq = _seq_of(d, "unknown-seat")
    out = RD.cmd_attest(d, str(caller_seq), "please let me through")
    assert out["ok"] is False and out["reason"] == "attest-ineligible"
    assert not os.path.exists(os.path.join(d, RD.RECEIPT_FILE))
    # A/B: the eligible event in the same journal DOES attest
    assert RD.cmd_attest(d, str(seq), "orphan", git=_fake_git(_gitdir(tmp_path)))["ok"] is True


@pytest.mark.parametrize("ref", ["0", "9999", "issue:123", "marker:nope", "banana"],
                         ids=["zero", "past-end", "issue-ref", "unknown-marker", "not-a-number"])
def test_attest_refuses_an_unresolvable_failure_reference(tmp_path, adapters, ref):
    """There is deliberately NO `issue:<n>` path — a caller can file any open issue, which would
    make eligibility self-authorizing. A/B: a real journal sequence in the same session attests."""
    d, seq = _orphan_failure(tmp_path, adapters, name="ref-" + ref.replace(":", "-"))
    out = RD.cmd_attest(d, ref, "note")
    assert out["ok"] is False and out["reason"] == "attest-failure-unknown"
    assert RD.cmd_attest(d, str(seq), "note",
                         git=_fake_git(_gitdir(tmp_path, "_gd2")))["ok"] is True


def test_attest_refuses_a_failure_a_later_advance_recovered(tmp_path, adapters):
    d, seq = _orphan_failure(tmp_path, adapters, name="recovered")
    # A/B: before recovery the reference is attestable — prove it on a twin session.
    twin, twin_seq = _orphan_failure(tmp_path, adapters, name="twin")
    assert RD.cmd_attest(twin, str(twin_seq), "note",
                         git=_fake_git(_gitdir(tmp_path, "_gd3")))["ok"] is True
    # recover the orphan the only way it CAN be recovered: the seat's record comes back (the
    # journal's claim is true again), and the advance then succeeds.
    _land(d, "security-reviewer")
    assert RD.cmd_record_result(d, "security-reviewer")["ok"] is True
    assert RD.cmd_advance(d, git=_fake_git(_gitdir(tmp_path, "_gd4")))["ok"] is True
    out = RD.cmd_attest(d, str(seq), "note")
    assert out["ok"] is False and out["reason"] == "attest-failure-recovered"


def test_attest_refuses_an_event_from_another_session(tmp_path, adapters):
    d, seq = _orphan_failure(tmp_path, adapters, name="mine")
    # A/B: with this session's own id the reference binds (twin proves it).
    twin, twin_seq = _orphan_failure(tmp_path, adapters, name="twin2")
    assert RD.cmd_attest(twin, str(twin_seq), "note",
                         git=_fake_git(_gitdir(tmp_path, "_gd5")))["ok"] is True
    meta_path = os.path.join(d, RR.META_FILE)
    meta, _err = RR.read_json(meta_path)
    meta["sessionId"] = "z" * 32                     # the journal now belongs to another session
    RR.atomic_write_json(meta_path, meta)
    out = RD.cmd_attest(d, str(seq), "note")
    assert out["ok"] is False and out["reason"] == "attest-session-mismatch"


def test_attest_refuses_when_a_terminal_receipt_already_exists(tmp_path, adapters):
    d, seq = _orphan_failure(tmp_path, adapters, name="terminal")
    assert RD.cmd_attest(d, str(seq), "note",
                         git=_fake_git(_gitdir(tmp_path, "_gd6")))["ok"] is True   # A/B
    out = RD.cmd_attest(d, str(seq), "second attestation")
    assert out["ok"] is False and out["reason"] == "terminal-receipt-exists"


def test_attest_refuses_an_empty_note(tmp_path, adapters):
    d, seq = _orphan_failure(tmp_path, adapters, name="note")
    out = RD.cmd_attest(d, str(seq), "   ")
    assert out["ok"] is False and out["reason"] == "attest-note-required"
    assert RD.cmd_attest(d, str(seq), "a real note",
                         git=_fake_git(_gitdir(tmp_path, "_gd7")))["ok"] is True   # A/B


def test_journal_degraded_marker_is_attestable_and_unrecordable_is_not(tmp_path, adapters):
    """`JournalFaultUnrecordable` means journal AND marker both failed, so it can NEVER be its own
    evidence. Its recoverable neighbour — append failed, marker succeeded — IS referencable."""
    d = _session(tmp_path)
    os.remove(os.path.join(d, RD.JOURNAL_FILE))
    os.mkdir(os.path.join(d, RD.JOURNAL_FILE))       # every later append fails; markers succeed
    RD._journal_append(d, {"cmd": "record-result", "phase": RD.P_PANEL, "round": 1, "attempt": 0})
    markers = RD.read_fault_markers(d)
    assert len(markers) == 1
    row = markers[0]
    assert row["entryHash"] and row["sessionId"] == _session_id(d)
    assert row["round"] == 1 and row["attempt"] == 0 and row["phase"] == RD.P_PANEL
    assert row["seq"] >= 1
    binding, why = RD._resolve_failure_ref(d, "marker:" + row["entryHash"])
    assert why is None and binding["class"] == "journal-degraded"
    # the doubly-unwritable case records NOTHING, so nothing can bind to it
    os.remove(os.path.join(d, RD.JOURNAL_FAULT_FILE))
    os.mkdir(os.path.join(d, RD.JOURNAL_FAULT_FILE))
    with pytest.raises(RD.JournalFaultUnrecordable):
        RD._journal_append(d, {"cmd": "advance", "phase": RD.P_PANEL})
    assert RD._resolve_failure_ref(d, "marker:nothing-was-written")[1] == "attest-failure-unknown"


# =============================================================================================
# session-death replay matrix
# =============================================================================================
#
# A kill between every adjacent pair of {seat-writes-landing, ingest, journal-append, advance,
# terminal, sidecar}. The successor `advance` must recover with NOTHING LOST and NOTHING
# DOUBLE-COUNTED.

def test_death_between_seat_writes_landing_and_ingest(tmp_path, adapters):
    d = _session(tmp_path)
    _record_all_panel_seats(d, seats=[s for s in RD.DIMENSIONS if s != "test-reviewer"])
    _land(d, "test-reviewer")                       # landed, never ingested — the kill
    out = _advance(d, tmp_path)
    assert out["ok"] is True                        # reconcile ingested it
    pend_round, pend_phase = 1, RD.P_PANEL
    spath = RR.store_path(d, pend_round, pend_phase, RR.storage_key("test-reviewer"), 0)
    assert os.path.exists(spath)
    recorded = [e for e in _outcomes(d, "recorded") if e["seat"] == "test-reviewer"]
    assert len(recorded) == 1                       # not double-counted


def test_death_between_ingest_and_journal_append(tmp_path, adapters):
    d = _session(tmp_path)
    _record_all_panel_seats(d, seats=[s for s in RD.DIMENSIONS if s != "test-reviewer"])
    _land(d, "test-reviewer")
    # ingest WITHOUT the journal half — the kill lands between the two commits
    anchor = RD._orders_anchor(_state(d), d, 1, RD.P_PANEL, 0)
    ingested = RR.ingest_landing(d, 1, RD.P_PANEL, "test-reviewer", 0, current_attempt=0,
                                 roster=list(RD.DIMENSIONS), anchor=anchor)
    assert ingested["ok"] is True
    before = open(ingested["storePath"], "rb").read()
    assert not [e for e in _outcomes(d, "recorded") if e["seat"] == "test-reviewer"]
    out = _advance(d, tmp_path)
    assert out["ok"] is True
    # the journal caught up (the store file is authoritative — it was NOT rewritten)
    recorded = [e for e in _journal(d)
                if e.get("payloadSha256") == ingested["payloadSha256"]]
    assert len(recorded) == 1 and recorded[0].get("reappended") is True
    assert open(ingested["storePath"], "rb").read() == before


def test_death_between_journal_append_and_advance(tmp_path, adapters):
    d = _session(tmp_path)
    _record_all_panel_seats(d)                       # records + journal complete, no fold — kill
    assert _state(d)["step"] == RD.P_PANEL
    out = _advance(d, tmp_path)
    assert out["ok"] is True
    assert len(_outcomes(d, "advanced")) == 1
    assert len(_outcomes(d, "recorded")) == len(RD.DIMENSIONS)


def test_death_between_advance_and_terminal(tmp_path, adapters):
    d = _session(tmp_path)
    _record_all_panel_seats(d)
    assert _advance(d, tmp_path)["ok"] is True       # folded panel, next action emitted — kill
    state_after_fold = _state(d)
    # the successor advance works the NEW phase; it never re-folds the old one
    assert _advance(d, tmp_path)["ok"] is True
    assert len(_outcomes(d, "advanced")) == 2
    panel_folds = [e for e in _outcomes(d, "advanced") if e["phase"] == RD.P_PANEL]
    assert len(panel_folds) == 1
    assert state_after_fold["round"] == _state(d)["round"]


def test_death_between_terminal_and_sidecar(tmp_path, adapters):
    gitdir = _gitdir(tmp_path)
    d = _session(tmp_path)
    _drive_to_terminal(d, tmp_path, adapters, gitdir=gitdir)
    sidecar_path = os.path.join(gitdir, "superheroes", "review-receipt.json")
    os.remove(sidecar_path)                          # terminal reached, sidecar lost — the kill
    out = RD.cmd_advance(d, git=_fake_git(gitdir))
    assert out["ok"] is True and out["sidecarRepaired"] is True
    sidecar, err = RR.read_json(sidecar_path)
    assert err is None and RR.validate_sidecar(sidecar) == (True, None)
    # the terminal receipt was NOT re-written by the repair
    with open(os.path.join(d, RD.RECEIPT_FILE), "rb") as fh:
        assert sidecar["receiptSha256"] == hashlib.sha256(fh.read()).hexdigest()


def test_death_between_sidecar_begin_and_sidecar_complete(tmp_path, adapters):
    """A crash between the two journal halves leaves begin-without-complete; the next `advance`
    re-validates and republishes idempotently by content hash."""
    gitdir = _gitdir(tmp_path)
    d = _session(tmp_path)
    _drive_to_terminal(d, tmp_path, adapters, gitdir=gitdir)
    sidecar_path = os.path.join(gitdir, "superheroes", "review-receipt.json")
    os.remove(sidecar_path)
    RD._journal_event(d, "advance", "sidecar-repair-begin", sidecarPath=sidecar_path)
    begins = len(_outcomes(d, "sidecar-repair-begin"))
    completes = len(_outcomes(d, "sidecar-repaired"))
    assert begins == completes + 1                   # the crashed half is visible in the journal
    out = RD.cmd_advance(d, git=_fake_git(gitdir))
    assert out["ok"] is True
    assert os.path.exists(sidecar_path)
    assert len(_outcomes(d, "sidecar-repaired")) == completes + 1
