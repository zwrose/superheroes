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
import ast

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
RP = _load("round_phases")

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
                        RD.P_FIXER: ["dispatch-fixer"],
                        RD.P_VERIFY: ["verify"]}
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

    def is_orchestrator_fulfilled(self, phase):
        return phase in (RD.P_VERIFY,)

    def orchestrator_payload_fault(self, phase, payload):
        if phase == RD.P_VERIFY:
            return RD.verify_result_fault(payload)
        return "orchestrator-payload-unknown-phase:%s" % phase

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
        if phase == RD.P_VERIFY:
            for env in (envelopes or []):
                if isinstance(env, dict) and env.get("schema") != RR.SEAT_MISSING_SCHEMA:
                    return dict(env.get("payload") or {"result": "pass"}), None
            return None, "missing-verify"
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


def _anchor_hashes(session_dir, rnd, phase, attempt, seat, occurrence=0):
    anchor = RD._orders_anchor(_state(session_dir), session_dir, rnd, phase, attempt)
    if anchor is None:
        return RR.NOT_EMITTED, RR.NOT_EMITTED
    skey = RR.storage_key(seat, occurrence)
    return anchor["manifestSha256"], (anchor.get("orders") or {}).get(skey, RR.NOT_EMITTED)


def _result_envelope(session_dir, seat, payload=None, pend=None, occurrence=0, **over):
    pend = pend or _pending(session_dir)
    # The default payload is SEAT-SPECIFIC on purpose: two seats sharing one payload would share a
    # payload hash, and the journal/store hash matching that `reconcile` runs on would silently
    # conflate them (a deleted record would still look "seen" through its twin's hash).
    payload = {"findings": [], "confidence": "high", "seat": seat,
               "verificationReceipt": {"ran": True}} if payload is None else payload
    manifest_sha, order_sha = _anchor_hashes(session_dir, pend["round"], pend["phase"],
                                             pend["attempt"], seat, occurrence=occurrence)
    env = {
        "schema": RR.SEAT_RESULT_SCHEMA,
        "session": _session_id(session_dir),
        "round": pend["round"],
        "phase": pend["phase"],
        "seat": seat,
        "attempt": pend["attempt"],
        "vendor": "claude",
        "model": "sonnet-5",
        "dispatchRef": manifest_sha,
        "orderSha256": order_sha,
        "manifestSha256": manifest_sha,
        "recordedAt": "2026-08-07T00:00:00",
        "payloadSha256": RR.payload_sha256(payload),
        "payload": payload,
    }
    if occurrence:
        env["occurrence"] = occurrence
    env.update(over)
    return env


def _land(session_dir, seat, payload=None, pend=None, occurrence=0, **over):
    """Write a seat's envelope into the LANDING area (what the host does)."""
    pend = pend or _pending(session_dir)
    env = _result_envelope(session_dir, seat, payload=payload, pend=pend, occurrence=occurrence,
                           **over)
    path = RR.landing_path(session_dir, pend["round"], pend["phase"],
                           RR.storage_key(seat, occurrence), pend["attempt"])
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


def _journal_events_claiming_policy_applied(session_dir):
    return [e for e in _journal(session_dir) if e.get("policyApplied")]


def _receipt_on_disk_policy_applied(session_dir):
    receipt_path = os.path.join(session_dir, RD.RECEIPT_FILE)
    if not os.path.isfile(receipt_path):
        return None
    with open(receipt_path, encoding="utf-8") as fh:
        return json.load(fh).get("policyApplied")


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
    by_phase = prov["byPhase"]
    assert by_phase[RD.P_PANEL]["vendorEchoMismatch"] == mismatch
    assert by_phase[RD.P_PANEL]["dispatchManifestUnavailable"] is True
    receipt = RD.build_receipt(_state(d), d)
    rd = next(r for r in receipt["rounds"] if r["round"] == 1)
    assert rd["adapterProvenance"] == prov
    degraded = "\n".join(receipt["degraded"])
    assert "adapter-provenance (round 1, %s): vendor echo mismatch" % RD.P_PANEL in degraded
    assert "adapter-provenance (round 1, %s): dispatch manifest unavailable" % RD.P_PANEL in degraded


def test_adapter_provenance_accumulates_per_phase_in_one_round(tmp_path, adapters):
    """Panel and verifiers disclosures in the same round must both survive under byPhase."""
    d = _session(tmp_path)
    panel_mismatch = [{"seat": "code-reviewer", "occurrence": 0, "echo": "cursor",
                       "manifest": "codex"}]
    verifier_omitted = [{"seat": "src/f.py:3", "occurrence": 0, "reason": "timeout"}]

    def assemble_with_provenance(phase, envelopes, state, config, dispatch_manifest=None,
                                 canary=None, session_dir=None):
        if phase == RD.P_PANEL:
            seats = {}
            for env in (envelopes or []):
                seat = env.get("seat")
                if env.get("schema") == RR.SEAT_MISSING_SCHEMA:
                    seats[seat] = {"findings": [], "missing": True}
                else:
                    seats[seat] = env.get("payload") or {"findings": []}
            return {"seats": seats,
                    "provenance": {"vendorEchoMismatch": panel_mismatch,
                                   "dispatchManifestUnavailable": True}}, None
        if phase == RD.P_VERIFIERS:
            return {"verdicts": [],
                    "provenance": {"unverifiedClusters": verifier_omitted}}, None
        return {}, None

    adapters.assemble = assemble_with_provenance
    _record_all_panel_seats(d)
    assert _advance(d, tmp_path)["ok"] is True
    # verifiers: empty roster folds immediately
    assert _advance(d, tmp_path)["ok"] is True
    prov = _state(d)["rounds"]["1"]["adapterProvenance"]
    by_phase = prov["byPhase"]
    assert by_phase[RD.P_PANEL]["vendorEchoMismatch"] == panel_mismatch
    assert by_phase[RD.P_PANEL]["dispatchManifestUnavailable"] is True
    assert by_phase[RD.P_VERIFIERS]["unverifiedClusters"] == verifier_omitted


def test_build_receipt_emits_mixed_old_flat_and_new_by_phase_adapter_provenance(tmp_path):
    """Round 1 legacy flat and round 2 per-phase shapes both ride the receipt and disclosures."""
    state = copy.deepcopy(V2_STATE)
    state["rounds"] = {
        "1": {"adapterProvenance": {"vendorEchoMismatch": [{"seat": "test-reviewer",
                                                            "echo": "cursor",
                                                            "manifest": "codex"}]}},
        "2": {"adapterProvenance": {"byPhase": {RD.P_VERIFIERS: {
            "dispatchManifestUnavailable": True}}}},
    }
    receipt = RD.build_receipt(state, str(tmp_path))
    rd1 = next(r for r in receipt["rounds"] if r["round"] == 1)
    rd2 = next(r for r in receipt["rounds"] if r["round"] == 2)
    assert rd1["adapterProvenance"] == state["rounds"]["1"]["adapterProvenance"]
    assert rd2["adapterProvenance"] == state["rounds"]["2"]["adapterProvenance"]
    degraded = "\n".join(receipt["degraded"])
    assert "adapter-provenance (round 1, unknown-phase): vendor echo mismatch" in degraded
    assert ("adapter-provenance (round 2, %s): dispatch manifest unavailable"
            % RD.P_VERIFIERS) in degraded


def test_adapter_provenance_migrates_legacy_flat_on_write(tmp_path):
    """A legacy flat value moves under unknown-phase when a new phase is folded."""
    state = copy.deepcopy(V2_STATE)
    state["round"] = 1
    state["rounds"] = {"1": {"adapterProvenance": {"dispatchManifestUnavailable": True}}}
    new_prov = {"unverifiedClusters": [{"seat": "cluster-a", "occurrence": 0, "reason": "killed"}]}
    RD._fold(state, state["config"], RD.P_VERIFIERS, {"provenance": new_prov})
    prov = state["rounds"]["1"]["adapterProvenance"]
    assert prov["byPhase"]["unknown-phase"]["dispatchManifestUnavailable"] is True
    assert prov["byPhase"][RD.P_VERIFIERS]["unverifiedClusters"] == new_prov["unverifiedClusters"]


def test_normalize_adapter_provenance_fail_closed_edges():
    """Corrupt stored values normalize to empty; empty phase disclosures are not recorded."""
    assert RD._normalize_adapter_provenance(None) == {}
    assert RD._normalize_adapter_provenance("bad") == {}
    assert RD._normalize_adapter_provenance({"byPhase": "not-a-dict"}) == {}
    assert RD._normalize_adapter_provenance({"vendorEchoMismatch": []}) == {"unknown-phase": {
        "vendorEchoMismatch": []}}
    state = copy.deepcopy(V2_STATE)
    state["round"] = 1
    state["rounds"] = {}
    RD._fold(state, state["config"], RD.P_PANEL, {"provenance": {}})
    assert "adapterProvenance" not in state["rounds"].get("1", {})


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


def test_record_result_refuses_bare_payload_fault(tmp_path, adapters):
    """Bare host landings get the same record-time payload validation as full envelopes."""
    d = _session(tmp_path)
    pend = _pending(d)
    skey = RR.storage_key("code-reviewer")
    stub_path = RR.envelope_stub_path(d, pend["round"], pend["phase"], skey, pend["attempt"])
    os.makedirs(os.path.dirname(stub_path), exist_ok=True)
    manifest_sha, order_sha = _anchor_hashes(d, pend["round"], pend["phase"], pend["attempt"],
                                             "code-reviewer")
    RR.atomic_write_json(stub_path, {
        "schema": RR.SEAT_RESULT_SCHEMA,
        "session": _session_id(d),
        "round": pend["round"],
        "phase": pend["phase"],
        "seat": "code-reviewer",
        "attempt": pend["attempt"],
        "vendor": "claude",
        "model": "sonnet-5",
        "dispatchRef": manifest_sha,
        "orderSha256": order_sha,
        "manifestSha256": manifest_sha,
    })
    RR.atomic_write_json(
        RR.bare_payload_path(d, pend["round"], pend["phase"], skey, pend["attempt"]),
        {"findings": "not-a-list"},
    )
    adapters.faults["code-reviewer"] = "findings must be a list"
    out = RD.cmd_record_result(d, "code-reviewer")
    assert out["ok"] is False and out["reason"] == "payload-fault"
    assert out["detail"] == "findings must be a list"
    spath = RR.store_path(d, pend["round"], pend["phase"], skey, pend["attempt"])
    assert not os.path.exists(spath)


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


def _pending_at_run_verify(session_dir):
    """Park a session on the advance path at run-verify with no orders manifest."""
    state = _state(session_dir)
    state["step"] = RD.P_VERIFY
    state["_advanceUsed"] = True
    state["pending"] = {"action": RD.P_VERIFY, "round": state["round"], "phase": RD.P_VERIFY,
                        "attempt": 0, "payload": {"command": "none"}}
    RD.save_state(session_dir, state)


def _write_verify_payload(session_dir, payload, attempt=None):
    pend = _pending(session_dir)
    attempt = pend["attempt"] if attempt is None else attempt
    skey = RR.storage_key("verify")
    path = RR.bare_payload_path(session_dir, pend["round"], pend["phase"], skey, attempt)
    RR.atomic_write_json(path, payload)
    return path


# --- orchestrator-fulfilled phases (#960) ------------------------------------


def test_orchestrator_fulfilled_phase_census():
    """Every ALL_PHASES member must be classified — new phases cannot fall through silently."""
    import round_adapters as RA

    seat_phases = {
        RP.P_PANEL, RP.P_VERIFIERS, RP.P_SYNTHESIS, RP.P_AUDITS, RP.P_SCOPED, RP.P_GAPSWEEP,
        RP.P_FIXER,
    }
    orchestrator_phases = {RP.P_VERIFY}
    owner_gate_phases = {RP.P_JUDGMENT, RP.P_STALL}
    terminal_phases = {RP.P_TERMINAL}
    for phase in RP.ALL_PHASES:
        if phase in owner_gate_phases:
            assert not RA.is_orchestrator_fulfilled(phase)
            continue
        if phase in terminal_phases:
            assert not RA.is_orchestrator_fulfilled(phase)
            continue
        if phase in orchestrator_phases:
            assert RA.is_orchestrator_fulfilled(phase)
            continue
        if phase in seat_phases:
            assert not RA.is_orchestrator_fulfilled(phase)
            continue
        raise AssertionError("unclassified phase %r — extend the census" % phase)
    assert len(RP.ALL_PHASES) == (len(seat_phases) + len(orchestrator_phases)
                                  + len(owner_gate_phases) + len(terminal_phases))


def test_advance_folds_run_verify_from_host_payload_without_manifest(tmp_path, adapters):
    d = _session(tmp_path)
    _record_all_panel_seats(d)
    assert _advance(d, tmp_path)["ok"] is True
    _pending_at_run_verify(d)
    assert not os.path.exists(RD._orders_manifest_path(d, 1, RD.P_VERIFY, 0))
    _write_verify_payload(d, {"result": "pass"})
    out = _advance(d, tmp_path)
    assert out["ok"] is True, out
    assert out["folded"] == {"phase": RD.P_VERIFY, "round": 1, "attempt": 0}
    state = _state(d)
    assert state["rounds"]["1"]["verifyResult"] == "pass"
    assert state["pending"]["phase"] != RD.P_VERIFY


def test_advance_refuses_missing_orchestrator_payload(tmp_path, adapters):
    d = _session(tmp_path)
    _record_all_panel_seats(d)
    assert _advance(d, tmp_path)["ok"] is True
    _pending_at_run_verify(d)
    out = _advance(d, tmp_path)
    assert out["ok"] is False and out["reason"] == "orchestrator-payload-missing"
    assert _pending(d)["phase"] == RD.P_VERIFY


def test_advance_refuses_unreadable_orchestrator_payload(tmp_path, adapters):
    d = _session(tmp_path)
    _record_all_panel_seats(d)
    assert _advance(d, tmp_path)["ok"] is True
    _pending_at_run_verify(d)
    path = _write_verify_payload(d, {"result": "pass"})
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("{not json")
    out = _advance(d, tmp_path)
    assert out["ok"] is False and out["reason"] == "orchestrator-payload-unreadable"
    assert _pending(d)["phase"] == RD.P_VERIFY


def test_advance_refuses_malformed_verify_payload_shape(tmp_path, adapters):
    d = _session(tmp_path)
    _record_all_panel_seats(d)
    assert _advance(d, tmp_path)["ok"] is True
    _pending_at_run_verify(d)
    _write_verify_payload(d, {"passed": True})
    out = _advance(d, tmp_path)
    assert out["ok"] is False
    assert "`passed`" in out["reason"]
    assert _pending(d)["phase"] == RD.P_VERIFY


def test_advance_does_not_fold_stale_attempt_orchestrator_payload(tmp_path, adapters):
    d = _session(tmp_path)
    _record_all_panel_seats(d)
    assert _advance(d, tmp_path)["ok"] is True
    _pending_at_run_verify(d)
    _write_verify_payload(d, {"result": "pass"}, attempt=0)
    state = _state(d)
    state["pending"] = dict(state["pending"])
    state["pending"]["attempt"] = 1
    RD.save_state(d, state)
    out = _advance(d, tmp_path)
    assert out["ok"] is False and out["reason"] == "orchestrator-payload-missing"
    assert _pending(d)["attempt"] == 1


def test_advance_folds_run_verify_from_seat_record_without_bare_payload(tmp_path, adapters):
    """Absent bare payload with a durable seat record folds through the seat path."""
    d = _session(tmp_path)
    _record_all_panel_seats(d)
    assert _advance(d, tmp_path)["ok"] is True
    _pending_at_run_verify(d)
    _land_and_record(d, "verify", payload={"result": "pass", "command": "none", "exit": 0})
    out = _advance(d, tmp_path)
    assert out["ok"] is True, out
    assert out["folded"] == {"phase": RD.P_VERIFY, "round": 1, "attempt": 0}
    state = _state(d)
    assert state["rounds"]["1"]["verifyResult"] == "pass"
    assert state["pending"]["phase"] != RD.P_VERIFY


def test_advance_malformed_verify_payload_does_not_fallback_to_seat_record(tmp_path, adapters):
    """Malformed bare payload refuses on the shape guard — it does not fall back to the seat path."""
    d = _session(tmp_path)
    _record_all_panel_seats(d)
    assert _advance(d, tmp_path)["ok"] is True
    _pending_at_run_verify(d)
    _land_and_record(d, "verify", payload={"result": "pass", "command": "none", "exit": 0})
    _write_verify_payload(d, {"passed": True})
    out = _advance(d, tmp_path)
    assert out["ok"] is False
    assert "`passed`" in out["reason"]
    assert _pending(d)["phase"] == RD.P_VERIFY
    assert _state(d)["rounds"]["1"].get("verifyResult") is None


# --- orchestrator-fulfilled folds leave a durable record (#1037) --------------

def _verify_store_path(session_dir, rnd=1, attempt=0):
    return RR.store_path(session_dir, rnd, RD.P_VERIFY, RR.storage_key("verify"), attempt)


def _at_run_verify(tmp_path, session_dir):
    """Drive a fresh session to a pending `run-verify` with no orders manifest."""
    _record_all_panel_seats(session_dir)
    assert _advance(session_dir, tmp_path)["ok"] is True
    _pending_at_run_verify(session_dir)


def test_orchestrator_fulfilled_fold_writes_the_durable_seat_record(tmp_path, adapters):
    """The bare-payload fold stores a `seat-result/1` for the slot — #960's first residual.

    The reconstruction assertion is the point: the folded `verifyResult` is readable from the STORE
    RECORD alone, with no reference to the state it folded into and no bare payload in hand."""
    d = _session(tmp_path)
    _at_run_verify(tmp_path, d)
    assert not os.path.exists(_verify_store_path(d))                              # A/B
    _write_verify_payload(d, {"result": "pass"})
    out = _advance(d, tmp_path)
    assert out["ok"] is True, out
    assert _state(d)["rounds"]["1"]["verifyResult"] == "pass"

    record, err = RR.read_json(_verify_store_path(d))
    assert err is None, err
    assert record["schema"] == RR.SEAT_RESULT_SCHEMA
    assert record["phase"] == RD.P_VERIFY and record["seat"] == "verify"
    assert record["round"] == 1 and record["attempt"] == 0 and record["occurrence"] == 0
    assert record["payload"] == {"result": "pass"}
    assert record["payloadSha256"] == RR.payload_sha256({"result": "pass"})
    # No orders manifest and no anchor exist for an orchestrator-fulfilled phase, so the record may
    # only carry the `not-emitted` literal — the one claim `_anchor_check` accepts unanchored.
    assert record["orderSha256"] == RR.NOT_EMITTED
    assert record["manifestSha256"] == RR.NOT_EMITTED
    assert record["fulfilledBy"] == "orchestrator"
    # reconstructed from the record alone
    assert record["payload"]["result"] == "pass"


def test_orchestrator_fulfilled_fold_writes_record_and_receipt_on_a_terminal_verify(
        tmp_path, adapters):
    """A verify `fail` folds to a terminal halt: `round-receipt.json` AND the seat record land."""
    d = _session(tmp_path)
    _at_run_verify(tmp_path, d)
    _write_verify_payload(d, {"result": "fail"})
    out = _advance(d, tmp_path)
    assert out["ok"] is True, out
    assert out.get("terminal") == "halted", out
    assert os.path.exists(os.path.join(d, RD.RECEIPT_FILE))
    record, err = RR.read_json(_verify_store_path(d))
    assert err is None, err
    assert record["payload"] == {"result": "fail"}


def test_orchestrator_fulfilled_record_and_journal_reconcile_clean(tmp_path, adapters):
    """Record and journal identity agree after the fold — `reconcile` sees no two-commit remnant.

    SCOPE, stated because the name it used to carry over-claimed: a clean `reconcile` after a
    SUCCESSFUL run would also result from three separate sequential commits, so this proves
    consistency, not atomicity. The atomicity itself is asserted structurally by
    `test_durable_record_rides_the_folds_own_commit_intent` below, which inspects the single commit
    the fold builds rather than its aftermath."""
    d = _session(tmp_path)
    _at_run_verify(tmp_path, d)
    _write_verify_payload(d, {"result": "pass"})
    assert _advance(d, tmp_path)["ok"] is True
    rec = RR.reconcile(d, 1, RD.P_VERIFY, RD._journal_record_identities(d, 1, RD.P_VERIFY))
    assert rec["reappend"] == []
    assert rec["journalOrphan"] == []
    # Non-vacuity: both lists above are empty because the PAIR landed, not because neither half did.
    identities = RD._journal_record_identities(d, 1, RD.P_VERIFY)
    assert any(i.get("seat") == "verify" for i in identities), identities
    assert os.path.exists(_verify_store_path(d))


def test_durable_record_rides_the_folds_own_commit_intent(tmp_path, adapters, monkeypatch):
    """ONE sealed intent carries the state advance, the record, and the record's journal identity.

    axis: ATOMICITY — that the three writes share a single commit. Asserting their presence after a
    successful run cannot show this (three sequential commits leave the same aftermath), so this
    inspects the commit object the fold actually builds, before it runs.
    """
    seen = []
    real_begin = RD.round_commit.begin

    def spy(session_dir, kind, **kw):
        commit = real_begin(session_dir, kind, **kw)
        seen.append((kind, commit))
        return commit

    monkeypatch.setattr(RD.round_commit, "begin", spy)
    d = _session(tmp_path)
    _at_run_verify(tmp_path, d)
    _write_verify_payload(d, {"result": "pass"})
    seen.clear()          # drop setup's own commits — only the verify fold is under inspection
    assert _advance(d, tmp_path)["ok"] is True

    accepts = [c for kind, c in seen if kind == "submit-accept"]
    assert len(accepts) == 1, [k for k, _ in seen]
    parts = accepts[0]._parts
    targets = [p.get("target") for p in parts if p.get("type") == "replace-file"]
    journals = [p for p in parts if p.get("type") == "journal-append"]
    assert any(t.endswith(RD.STATE_FILE) for t in targets), targets
    assert any("run-verify" in (t or "") for t in targets), targets
    assert any((j.get("entry") or {}).get("outcome") == "recorded" for j in journals), journals


def test_orchestrator_fold_refuses_to_write_a_record_with_no_session_id(tmp_path, adapters):
    """A record whose `session` would be null reconstructs nothing — refuse, don't commit it.

    axis: that the fold REFUSES, not that the envelope merely ends up with a null field. The seat
    path enforces the same precondition as `bootstrap-required` inside `validate_landing`; this
    path does not route through that validation, so it owes its own check."""
    d = _session(tmp_path)
    _at_run_verify(tmp_path, d)
    _write_verify_payload(d, {"result": "pass"})
    meta = os.path.join(d, RR.META_FILE)
    with open(meta, encoding="utf-8") as fh:
        saved = fh.read()
    with open(meta, "w", encoding="utf-8") as fh:
        fh.write("{}")                                   # a meta.json carrying no session id
    out = _advance(d, tmp_path)
    assert out["ok"] is False and out["reason"] == "bootstrap-required", out
    assert not os.path.exists(_verify_store_path(d)), "a refusal must leave nothing behind"
    assert _state(d)["rounds"]["1"].get("verifyResult") is None

    with open(meta, "w", encoding="utf-8") as fh:        # A/B — the same setup with the id back
        fh.write(saved)
    assert _advance(d, tmp_path)["ok"] is True
    assert os.path.exists(_verify_store_path(d))


def test_landing_ambiguity_probe_fails_closed_on_a_dangling_record_symlink(tmp_path, adapters):
    """axis: the EXISTENCE probe's fail direction. `os.path.exists` follows symlinks and answers
    False for a dangling one, which would fold the bare payload over an unknown store state."""
    d = _session(tmp_path)
    _at_run_verify(tmp_path, d)
    _write_verify_payload(d, {"result": "pass"})
    record_path = _verify_store_path(d)
    os.makedirs(os.path.dirname(record_path), exist_ok=True)
    os.symlink(os.path.join(os.path.dirname(record_path), "no-such-record.json"), record_path)
    assert not os.path.exists(record_path), "fixture must be a DANGLING symlink"
    assert os.path.lexists(record_path)
    out = _advance(d, tmp_path)
    assert out["ok"] is False and out["reason"] == "landing-ambiguous", out
    assert _state(d)["rounds"]["1"].get("verifyResult") is None


def test_vendor_gap_rows_from_two_phases_do_not_collide(tmp_path, adapters):
    """axis: that no disclosure is DROPPED by deduplication once the collector spans phases.

    A panel dimension may be configured with any name, including a fixed reviewer seat's. While the
    collector was panel-only, `(seat, occurrence)` was unique within a round; spanning phases makes
    it collide, and a dropped row means a fallback folded with no receipt."""
    state = {"round": 1, "rounds": {}}
    RD._disclose_order_vendor_provenance_gaps(state, [
        {"seat": "gap-sweep", "occurrence": 0, "phase": RD.P_PANEL, "vendorSource": None},
    ])
    RD._disclose_order_vendor_provenance_gaps(state, [
        {"seat": "gap-sweep", "occurrence": 0, "phase": RD.P_GAPSWEEP,
         "vendorSource": RD.VENDOR_SOURCE_DEFAULTED},
    ])
    rows = state["rounds"]["1"]["orderVendorProvenanceGaps"]
    assert len(rows) == 2, rows
    assert {r["phase"] for r in rows} == {RD.P_PANEL, RD.P_GAPSWEEP}
    # A/B: a genuine repeat of the SAME phase+slot is still deduplicated.
    RD._disclose_order_vendor_provenance_gaps(state, [
        {"seat": "gap-sweep", "occurrence": 0, "phase": RD.P_GAPSWEEP,
         "vendorSource": RD.VENDOR_SOURCE_DEFAULTED},
    ])
    assert len(state["rounds"]["1"]["orderVendorProvenanceGaps"]) == 2


def test_re_entry_after_its_own_fold_refuses_landing_ambiguous_unconditionally(tmp_path, adapters):
    """The refusal does not exempt the record this path itself wrote.

    axis: that the invariant is UNCONDITIONAL. An earlier revision carried a `replay` escape hatch
    so a post-fold re-entry would re-fold idempotently; it was removed because recognising "this
    record is mine" duplicates the already-folded judgment `cmd_submit`'s duplicate contract owns,
    and the two disagreed differently on every review round. The re-entry it protected could not
    make progress anyway — a duplicate `submit` returns before `pending` is cleared — so the loud
    refusal is both the ratified behaviour and the honest one.
    """
    d = _session(tmp_path)
    _at_run_verify(tmp_path, d)
    _write_verify_payload(d, {"result": "pass"})
    assert _advance(d, tmp_path)["ok"] is True                       # A/B: the fold itself works
    folded = _state(d)
    folded["step"] = RD.P_VERIFY
    folded["pending"] = {"action": RD.P_VERIFY, "round": 1, "phase": RD.P_VERIFY, "attempt": 0,
                         "payload": {"command": "none"}}
    RD.save_state(d, folded)
    out = _advance(d, tmp_path)
    assert out["ok"] is False and out["reason"] == "landing-ambiguous", out
    # exactly one durable record, and it still reconstructs the folded result.
    records = [e for e in RD.read_journal(d)
               if e.get("outcome") == "recorded" and e.get("phase") == RD.P_VERIFY]
    assert len(records) == 1, records
    stored, err = RR.read_json(_verify_store_path(d))
    assert err is None and stored["payload"] == {"result": "pass"}


def test_advance_refuses_landing_ambiguous_when_payload_and_record_both_present(tmp_path, adapters):
    """Two claims for one slot refuse — the seat path's invariant, on the bare-vs-record pair.

    A/B is the whole point of the fixture: the SAME setup minus one artifact folds either way, so
    the refusal cannot be an artifact of a precondition that was never satisfiable."""
    d = _session(tmp_path)
    _at_run_verify(tmp_path, d)
    _land_and_record(d, "verify", payload={"result": "pass", "command": "none", "exit": 0})
    _write_verify_payload(d, {"result": "pass"})
    before = RD.state_hash(_state(d))
    out = _advance(d, tmp_path)
    assert out["ok"] is False and out["reason"] == "landing-ambiguous", out
    assert RD.state_hash(_state(d)) == before, "a refusal must not move the state"
    assert _pending(d)["phase"] == RD.P_VERIFY
    assert _state(d)["rounds"]["1"].get("verifyResult") is None


def test_landing_ambiguous_ab_each_artifact_alone_still_folds(tmp_path, adapters):
    """The A/B halves of the refusal above: record alone folds; bare payload alone folds."""
    record_only = _session(tmp_path, name="record-only")
    _at_run_verify(tmp_path, record_only)
    _land_and_record(record_only, "verify",
                     payload={"result": "pass", "command": "none", "exit": 0})
    assert _advance(record_only, tmp_path)["ok"] is True
    assert _state(record_only)["rounds"]["1"]["verifyResult"] == "pass"

    payload_only = _session(tmp_path, name="payload-only")
    _at_run_verify(tmp_path, payload_only)
    _write_verify_payload(payload_only, {"result": "pass"})
    assert _advance(payload_only, tmp_path)["ok"] is True
    assert _state(payload_only)["rounds"]["1"]["verifyResult"] == "pass"


def test_emitted_order_resolves_host_seat_vendor_from_config_seat_map(tmp_path, adapters):
    """Config seatMap fallback when a submitted panel empties state seats (#723 + #960)."""
    seeded_vendor = "codex"
    partial = {"seats": {"architecture-reviewer": {"vendor": seeded_vendor, "model": "gpt-5",
                                                    "engine": "codex"}}}
    d = _session(tmp_path, seatMap=partial)
    initial_pend = _pending(d)
    initial_attempt = initial_pend["attempt"]

    pend = initial_pend
    seats = {dim: {"findings": []} for dim in RD.DIMENSIONS}
    submit_out = RD.cmd_submit(
        d, pend["phase"], pend["attempt"], RD.state_hash(_state(d)),
        {"seats": seats, "seatMap": {"seats": {}}},
    )
    assert submit_out["ok"] is True, submit_out

    state = _state(d)
    assert state["seatMap"]["seats"] == {}
    assert state["config"]["seatMap"]["seats"] == partial["seats"]

    # Reach the next panel dispatch through the SUPPORTED re-arm — the #174 confirmation re-arm,
    # which is how a fresh full panel is actually scheduled — rather than hand-setting
    # `step`/`pending`/`lastAccepted` (PR #1028 rework finding 24). A hand-set state can emit a
    # dispatch the driver would never have emitted, and the seat-map fallback assertion below would
    # then prove nothing about the live path.
    rnd = initial_pend["round"]
    state["confirmations"] = 0
    state["surfacedSinceLastPanel"] = ["Critical"]      # a Critical under budget owes one panel
    state["fullPanelRan"] = False
    state["findings"] = []
    state["auditRounds"] = [{"round": rnd, "outcomes": [{"identity": "x", "ruling": "discharged"}]}]
    state["_auditOutcome"] = {"notDischarged": [], "discharged": ["x"]}
    state["_changedSubjects"] = ["Code"]
    state["pending"] = None
    RD._settle_delta(state, state["config"])
    assert state.get("terminal") is None, "the re-arm must not certify"
    assert state["step"] == RD.P_PANEL
    assert any(dd["kind"] == "confirmation-rearm" for dd in state["decisions"])
    assert state["round"] == rnd + 1
    RD.save_state(d, state)

    next_out = RD.cmd_next(d)
    assert next_out["ok"] is True, next_out
    fresh_pend = _pending(d)
    assert fresh_pend["phase"].startswith("dispatch-"), fresh_pend
    assert (fresh_pend["round"], fresh_pend["attempt"]) != (rnd, initial_attempt), (
        "must emit a fresh dispatch, not re-read the pre-submit manifest")
    assert (fresh_pend["round"], fresh_pend["attempt"]) == (rnd + 1, 0), fresh_pend

    manifest_path = RD._orders_manifest_path(
        d, fresh_pend["round"], fresh_pend["phase"], fresh_pend["attempt"])
    manifest, err = RR.read_json(manifest_path)
    assert err is None, err
    skey = RR.storage_key("architecture-reviewer")
    assert manifest["seats"][skey]["vendor"] == seeded_vendor, (
        "config seat-map fallback must supply the seeded vendor for architecture-reviewer")


def test_emitted_order_discloses_vendor_gap_when_seat_map_absent(tmp_path, adapters):
    d = _session(tmp_path, name="no-map", seatMap=None)
    pend = _pending(d)
    gaps = _state(d)["rounds"][str(pend["round"])]["orderVendorProvenanceGaps"]
    assert isinstance(gaps, list) and gaps
    assert all(g.get("seat") in RD.DIMENSIONS for g in gaps)
    receipt = RD.build_receipt(_state(d), d)
    rd = next(r for r in receipt["rounds"] if r["round"] == pend["round"])
    assert rd.get("orderVendorProvenanceGaps") == gaps


def test_emitted_order_partial_seat_map_resolves_and_discloses(tmp_path, adapters):
    partial = {"seats": {"code-reviewer": {"vendor": "codex", "model": "gpt-5", "engine": "codex"}}}
    d = _session(tmp_path, seatMap=partial)
    pend = _pending(d)
    manifest_path = RD._orders_manifest_path(d, pend["round"], pend["phase"], pend["attempt"])
    manifest, err = RR.read_json(manifest_path)
    assert err is None
    resolved = RR.storage_key("code-reviewer")
    unresolved = RR.storage_key("architecture-reviewer")
    assert manifest["seats"][resolved]["vendor"] == "codex"
    assert manifest["seats"][unresolved]["vendor"] is None
    gaps = _state(d)["rounds"][str(pend["round"])]["orderVendorProvenanceGaps"]
    gap_seats = {g["seat"] for g in gaps}
    assert "architecture-reviewer" in gap_seats
    assert "code-reviewer" not in gap_seats


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


def _record_panel_with_verifier_cluster(session_dir, file="f.py", line=1):
    finding = {
        "file": file,
        "line": line,
        "severity": "Important",
        "title": "issue",
        "dimension": "Code",
    }
    for seat in RD.DIMENSIONS:
        payload = {"findings": [finding] if seat == "code-reviewer" else []}
        _land_and_record(session_dir, seat, payload=payload)


def test_advance_emits_the_orders_manifest_and_mirrors_its_hash_into_state(tmp_path, adapters):
    d = _session(tmp_path)
    verifier_seat = "verifier:f.py:0"
    adapters.rosters[RD.P_VERIFIERS] = [verifier_seat]
    _record_panel_with_verifier_cluster(d)
    out = _advance(d, tmp_path)
    assert out["ok"] is True
    manifest_path = RD._orders_manifest_path(d, 1, RD.P_VERIFIERS, 0)
    manifest, err = RR.read_json(manifest_path)
    assert err is None
    skey = RR.storage_key(verifier_seat)
    emitted = [e for e in _outcomes(d, "orders-emitted") if e.get("phase") == RD.P_VERIFIERS]
    assert len(emitted) == 1
    anchor = RD._orders_anchor(_state(d), d, 1, RD.P_VERIFIERS, 0)
    assert anchor["manifestSha256"] == emitted[0]["manifestSha256"]
    seat_entry = manifest["seats"][skey]
    assert seat_entry["storeKey"] == skey and seat_entry["seat"] == verifier_seat
    assert seat_entry["orderSha256"] == anchor["orders"][skey]
    assert anchor["orders"][skey] != RR.NOT_EMITTED
    # the anchor rides the state-hash chain, and the emitted hash is the one ingestion checks
    assert out["nextAction"]["expectedStateHash"] == RD.state_hash(_state(d))
    assert os.path.exists(seat_entry["orderPath"])
    assert os.path.exists(seat_entry["envelopeStubPath"])
    # an envelope claiming a DIFFERENT manifest hash is refused against the emission-time anchor
    pend = _pending(d)
    _land(d, verifier_seat, pend=pend, manifestSha256="deadbeef")
    assert RD.cmd_record_result(d, verifier_seat)["reason"] == "manifest-anchor-mismatch"
    # A/B: the envelope carrying the anchored hash records fine
    _land(d, verifier_seat, pend=pend)
    assert RD.cmd_record_result(d, verifier_seat)["ok"] is True


def test_advance_emits_synthesis_verified_json_sidecar(tmp_path, adapters):
    """Synthesis dispatch writes verified.json from the pending findings payload."""
    d = _session(tmp_path)
    _record_panel_with_verifier_cluster(d)
    assert _advance(d, tmp_path)["ok"] is True
    out = _advance(d, tmp_path)              # verifiers: empty roster → synthesis dispatch
    assert out["ok"] is True
    assert out["nextAction"]["phase"] == RD.P_SYNTHESIS
    verified_path = os.path.join(d, "round-1", "verified.json")
    assert os.path.isfile(verified_path)
    verified, err = RR.read_json(verified_path)
    assert err is None
    assert len(verified["findings"]) == 1
    assert verified["findings"][0]["file"] == "f.py"
    assert verified["findings"][0]["line"] == 1


def _drop_orders_anchor_mirror(session_dir):
    state = _state(session_dir)
    state.pop("_ordersAnchors", None)
    RD.save_state(session_dir, state)


def test_tampered_manifest_rebuild_refuses_ingest(tmp_path, adapters):
    """A/B — journal rebuild re-verifies manifest bytes; tampering refuses ingestion."""
    seat = "verifier:f.py:0"

    def _emit_verifiers_orders(name):
        d = _session(tmp_path, name=name)
        adapters.rosters[RD.P_VERIFIERS] = [seat]
        _record_panel_with_verifier_cluster(d)
        assert _advance(d, tmp_path)["ok"] is True
        return d

    # A: untampered manifest — mirror dropped, rebuild succeeds, ingest accepts
    ok_session = _emit_verifiers_orders("untampered")
    _drop_orders_anchor_mirror(ok_session)
    assert RD._orders_anchor(_state(ok_session), ok_session, 1, RD.P_VERIFIERS, 0) is not None
    pend = _pending(ok_session)
    _land(ok_session, seat, pend=pend)
    assert RD.cmd_record_result(ok_session, seat)["ok"] is True

    # B: one orderSha256 edited — rebuild fails closed, ingest refuses
    bad_session = _emit_verifiers_orders("tampered")
    manifest_path = RD._orders_manifest_path(bad_session, 1, RD.P_VERIFIERS, 0)
    anchor_before = RD._orders_anchor(_state(bad_session), bad_session, 1, RD.P_VERIFIERS, 0)
    manifest_sha = anchor_before["manifestSha256"]
    order_sha = anchor_before["orders"][RR.storage_key(seat)]
    _drop_orders_anchor_mirror(bad_session)
    manifest, err = RR.read_json(manifest_path)
    assert err is None
    skey = RR.storage_key(seat)
    manifest["seats"][skey]["orderSha256"] = "f" * 64
    RR.atomic_write_json(manifest_path, manifest)
    assert RD._orders_anchor(_state(bad_session), bad_session, 1, RD.P_VERIFIERS, 0) is None
    pend = _pending(bad_session)
    _land(bad_session, seat, pend=pend, manifestSha256=manifest_sha, orderSha256=order_sha)
    assert RD.cmd_record_result(bad_session, seat)["reason"] == "manifest-anchor-unanchored"


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
    """A/B — the same `advance` on a dispatch phase folds; without a calibration overlay the two
    OWNER gates park because the shipped default pre-authorizes nothing."""
    ok_session = _session(tmp_path, name="folds-" + reason)
    _record_all_panel_seats(ok_session)
    assert _advance(ok_session, tmp_path)["ok"] is True

    d = _session(tmp_path, name="park-" + reason)
    state = _state(d)
    state["step"] = phase
    state["pending"] = {"action": phase, "round": 1, "phase": phase, "attempt": 0, "payload": {}}
    state["config"]["repoRoot"] = _repo_without_gate_policy(tmp_path)
    if phase == RD.P_JUDGMENT:
        state["_judgmentFindings"] = [
            {"title": "widen the API", "severity": "Important", "file": "f.py", "line": 1,
             "tradeoff": True}]
        state["_judgmentMechanical"] = []
    if phase == RD.P_STALL:
        state["_stallChoices"] = [c for c in RD.STALL_CHOICES if c != "accept-the-disclosed-risk"]
        state["_acceptRiskEligible"] = False
    RD.save_state(d, state)
    out = _advance(d, tmp_path)
    assert out["ok"] is False and out["reason"] == reason
    if phase == RD.P_JUDGMENT:
        assert out["detail"] == "gate-policy-unmatched-class:judgment:important"
    else:
        assert out["detail"] == "gate-policy-unmatched-class:stall:accept-risk-ineligible"
    parks = [e for e in _journal(d) if e.get("reason") == reason]
    assert parks and parks[-1]["fault"] == RD.FAULT_CALLER


def test_run_loop_judgment_default_is_unchanged(tmp_path):
    """The advance-path park is a change on the ADVANCE path only. `run_loop`'s library default —
    no judgment gate wired → fix every judgment finding as suggested — must still do exactly that."""
    payload = {"findings": [{"id": "f1"}, {"id": "f2"}]}
    assert RD._run_seam({"io": {}}, RD.P_JUDGMENT, payload, RD.new_state(_cfg()), _cfg()) == {
        "dispositions": [{"id": "f1", "disposition": "fix-as-suggested"},
                         {"id": "f2", "disposition": "fix-as-suggested"}]}


# =============================================================================================
# §4b gate-policy auto-advance (#723 WO-7)
# =============================================================================================

def _load_core_md():
    path = os.path.join(_LIB, "core_md.py")
    spec = importlib.util.spec_from_file_location("core_md_advance", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _repo_with_gate_policy(tmp_path, rules):
    cm = _load_core_md()
    repo = str(tmp_path / "repo")
    os.makedirs(repo)
    subprocess.check_call(["git", "init", "-q", "-b", "main"], cwd=repo)
    subprocess.check_call(["git", "config", "user.email", "t@t"], cwd=repo)
    subprocess.check_call(["git", "config", "user.name", "t"], cwd=repo)
    subprocess.check_call(["git", "commit", "-q", "--allow-empty", "-m", "init"], cwd=repo)
    facts = {"verifyCommand": "none", "stackTags": [], "threatModel": "", "patterns": ""}
    in_repo = os.path.join(repo, ".claude", "superheroes", "core.md")
    os.makedirs(os.path.dirname(in_repo), exist_ok=True)
    with open(in_repo, "w", encoding="utf-8") as fh:
        fh.write(cm.render_core(facts, "confirmed", "2026-01-01", "2026-01-01"))
    policy = {"schema": "gate-policy/1", "default": "park", "rules": rules}
    assert cm.write_review_gate_policy(repo, policy, root=None)["action"] == "written"
    return repo


def _repo_without_gate_policy(tmp_path):
    cm = _load_core_md()
    repo = str(tmp_path / "repo-no-policy")
    os.makedirs(repo)
    subprocess.check_call(["git", "init", "-q", "-b", "main"], cwd=repo)
    subprocess.check_call(["git", "config", "user.email", "t@t"], cwd=repo)
    subprocess.check_call(["git", "config", "user.name", "t"], cwd=repo)
    subprocess.check_call(["git", "commit", "-q", "--allow-empty", "-m", "init"], cwd=repo)
    facts = {"verifyCommand": "none", "stackTags": [], "threatModel": "", "patterns": ""}
    in_repo = os.path.join(repo, ".claude", "superheroes", "core.md")
    os.makedirs(os.path.dirname(in_repo), exist_ok=True)
    with open(in_repo, "w", encoding="utf-8") as fh:
        fh.write(cm.render_core(facts, "confirmed", "2026-01-01", "2026-01-01"))
    return repo


def _parked_at_owner_gate(tmp_path, adapters, phase, name=None):
    label = name or ("park-" + phase)
    d = _session(tmp_path, name=label)
    state = _state(d)
    state["step"] = phase
    state["pending"] = {"action": phase, "round": 1, "phase": phase, "attempt": 0, "payload": {}}
    if phase == RD.P_JUDGMENT:
        state["_judgmentFindings"] = [
            {"title": "widen the API", "severity": "Important", "file": "f.py", "line": 1,
             "tradeoff": True}]
        state["_judgmentMechanical"] = []
    if phase == RD.P_STALL:
        state["_stallChoices"] = list(RD.STALL_CHOICES)
        state["_acceptRiskEligible"] = False
    RD.save_state(d, state)
    return d


def _judgment_session_with_repo(tmp_path, adapters, repo, severity="Important", name="judgment"):
    d = _parked_at_owner_gate(tmp_path, adapters, RD.P_JUDGMENT, name=name)
    state = _state(d)
    state["config"]["repoRoot"] = repo
    state["_judgmentFindings"] = [
        {"title": "widen the API", "severity": severity, "file": "f.py", "line": 1, "tradeoff": True}]
    RD.save_state(d, state)
    return d


def test_advance_judgment_auto_applies_calibration_overlay(tmp_path, adapters):
    repo = _repo_with_gate_policy(tmp_path, [{
        "gate": "present-judgment",
        "findingClass": "judgment:important",
        "disposition": "skip",
    }])
    d = _judgment_session_with_repo(tmp_path, adapters, repo)
    out = _advance(d, tmp_path)
    assert out["ok"] is True, out
    assert out.get("policyApplied") is not None
    assert out["policyApplied"]["source"] == RD.POLICY_APPLIED_SOURCE_GATE_POLICY
    assert out["policyApplied"]["action"] == {"dispositions": [
        {"findingClass": "judgment:important", "disposition": "skip"}]}
    assert _state(d)["terminal"] == "converged"
    found = [p for p in os.listdir(os.path.join(d, "round-1")) if p.startswith("gate-policy.")]
    assert found, "expected gate-policy archive under round-1"
    receipt = RD.build_receipt(_state(d), d)
    assert receipt.get("policyApplied")


def test_advance_judgment_colliding_identity_severity_policy_dispositions_not_collapse(
        tmp_path, adapters):
    """Policy advance must not collapse dispositions when two same-location findings differ in severity."""
    repo = _repo_with_gate_policy(tmp_path, [
        {"gate": "present-judgment", "findingClass": "judgment:critical",
         "disposition": "fix-as-suggested"},
        {"gate": "present-judgment", "findingClass": "judgment:important",
         "disposition": "skip"},
    ])
    d = _parked_at_owner_gate(tmp_path, adapters, RD.P_JUDGMENT, name="judgment-collide")
    state = _state(d)
    state["config"]["repoRoot"] = repo
    state["_judgmentFindings"] = [
        {"title": "widen the API", "severity": "Critical", "file": "f.py", "line": 1, "tradeoff": True},
        {"title": "widen the API", "severity": "Important", "file": "f.py", "line": 1, "tradeoff": True},
    ]
    RD.save_state(d, state)
    out = _advance(d, tmp_path)
    assert out["ok"] is True, out
    after = _state(d)
    assert after["step"] == RD.P_FIXER
    assert [f["severity"] for f in after["_fixBatch"]] == ["Critical"]
    assert [s["severity"] for s in after.get("_skippedBlockers") or []] == ["Important"]


def test_advance_judgment_partial_match_parks(tmp_path, adapters):
    """Fail-closed edge 1: some rows match and some do not → park with advance-judgment-park."""
    repo = _repo_with_gate_policy(tmp_path, [{
        "gate": "present-judgment",
        "findingClass": "judgment:important",
        "disposition": "skip",
    }])
    d = _judgment_session_with_repo(tmp_path, adapters, repo)
    state = _state(d)
    state["_judgmentFindings"].append(
        {"title": "other", "severity": "Minor", "file": "g.py", "line": 2, "tradeoff": True})
    RD.save_state(d, state)
    out = _advance(d, tmp_path)
    assert out["ok"] is False and out["reason"] == "advance-judgment-park"
    assert out["detail"] == "gate-policy-unmatched-class:judgment:minor"


def test_advance_judgment_unreadable_overlay_parks(tmp_path, adapters):
    """Fail-closed edge 3: unreadable calibration overlay → park."""
    repo = _repo_with_gate_policy(tmp_path, [{
        "gate": "present-judgment",
        "findingClass": "judgment:important",
        "disposition": "skip",
    }])
    core_path = os.path.join(repo, ".claude", "superheroes", "core.md")
    with open(core_path, "w", encoding="utf-8") as fh:
        fh.write("{{{corrupt core\n")
    d = _judgment_session_with_repo(tmp_path, adapters, repo)
    out = _advance(d, tmp_path)
    assert out["ok"] is False and out["reason"] == "advance-judgment-park"
    assert out["detail"].startswith("gate-policy-calibration-unreadable")


def test_advance_judgment_calibration_absent_parks(tmp_path, adapters):
    """Calibration absent (no core.md) → park with gate-policy-calibration-absent."""
    repo = str(tmp_path / "repo-no-core")
    os.makedirs(repo)
    subprocess.check_call(["git", "init", "-q", "-b", "main"], cwd=repo)
    subprocess.check_call(["git", "config", "user.email", "t@t"], cwd=repo)
    subprocess.check_call(["git", "config", "user.name", "t"], cwd=repo)
    subprocess.check_call(["git", "commit", "-q", "--allow-empty", "-m", "init"], cwd=repo)
    d = _judgment_session_with_repo(tmp_path, adapters, repo, name="judgment-absent")
    out = _advance(d, tmp_path)
    assert out["ok"] is False and out["reason"] == "advance-judgment-park"
    assert out["detail"] == "gate-policy-calibration-absent"


def test_advance_judgment_calibration_refused_parks(tmp_path, adapters, monkeypatch):
    """Unregistered calibration refusal status → park with gate-policy-calibration-refused."""
    repo = _repo_with_gate_policy(tmp_path, [{
        "gate": "present-judgment",
        "findingClass": "judgment:important",
        "disposition": "skip",
    }])
    d = _judgment_session_with_repo(tmp_path, adapters, repo, name="judgment-refused")
    cm = _load_core_md()
    unknown_status = "unregistered-calibration-refusal"
    with pytest.raises(KeyError):
        cm.gate_refusal_reason_for_status(unknown_status)

    def fake_overlay(_config):
        return cm.ReviewGatePolicyGate(unknown_status, None, None)

    monkeypatch.setattr(RD, "_gate_policy_overlay_from_config", fake_overlay)
    out = _advance(d, tmp_path)
    assert out["ok"] is False and out["reason"] == "advance-judgment-park"
    assert out["detail"] == "gate-policy-calibration-refused"


def test_advance_judgment_shipped_policy_missing_parks(tmp_path, adapters, monkeypatch):
    """Fail-closed edge 4: shipped policy file missing with no overlay → park."""
    repo = _repo_without_gate_policy(tmp_path)
    d = _judgment_session_with_repo(tmp_path, adapters, repo)
    import review_gate_policy as rgp

    def missing_layer(path=None):
        return {"ok": False, "reason": "gate-policy-shipped-missing", "layer": None}

    monkeypatch.setattr(rgp, "load_shipped_layer", missing_layer)
    out = _advance(d, tmp_path)
    assert out["ok"] is False and out["reason"] == "advance-judgment-park"
    assert out["detail"] == "gate-policy-no-valid-layer"


_CONFIRMED_STALL_TARGET = {"id": "v0", "title": "bug", "severity": "Important", "file": "f.py",
                           "line": 1, "verdict": "CONFIRMED", "evidence": "tests pass"}


def test_advance_stall_accept_risk_authorized(tmp_path, adapters):
    """Stall gate authorized advance via accept-the-disclosed-risk when eligible."""
    repo = _repo_with_gate_policy(tmp_path, [{
        "gate": "present-stall-menu",
        "findingClass": "stall:accept-risk-eligible",
        "disposition": "accept-the-disclosed-risk",
    }])
    d = _parked_at_owner_gate(tmp_path, adapters, RD.P_STALL)
    state = _state(d)
    state["config"]["repoRoot"] = repo
    state["_acceptRiskEligible"] = True
    state["_stallTargets"] = [dict(_CONFIRMED_STALL_TARGET)]
    RD.save_state(d, state)
    out = _advance(d, tmp_path)
    assert out["ok"] is True, out
    assert out.get("policyApplied") is not None
    assert out["policyApplied"]["source"] == RD.POLICY_APPLIED_SOURCE_GATE_POLICY
    assert out["policyApplied"]["action"] == {"choice": "accept-the-disclosed-risk"}
    assert _state(d)["terminal"] == "converged"
    receipt_path = os.path.join(d, RD.RECEIPT_FILE)
    with open(receipt_path, encoding="utf-8") as fh:
        on_disk = json.load(fh)
    assert on_disk.get("policyApplied")
    assert on_disk["policyApplied"][-1]["action"] == {"choice": "accept-the-disclosed-risk"}


def test_advance_stall_ineligible_accept_risk_rule_parks(tmp_path, adapters):
    """Fail-closed edge 2: accept-the-disclosed-risk is not offerable for ineligible stall class."""
    cm = _load_core_md()
    repo = _repo_with_gate_policy(tmp_path, [])
    invalid = {
        "schema": "gate-policy/1",
        "default": "park",
        "rules": [{
            "gate": "present-stall-menu",
            "findingClass": "stall:accept-risk-ineligible",
            "disposition": "accept-the-disclosed-risk",
        }],
    }
    assert cm.write_review_gate_policy(repo, invalid, root=None)["action"] == "refused"
    d = _parked_at_owner_gate(tmp_path, adapters, RD.P_STALL)
    state = _state(d)
    state["config"]["repoRoot"] = repo
    RD.save_state(d, state)
    out = _advance(d, tmp_path)
    assert out["ok"] is False and out["reason"] == "advance-stall-park"
    assert out["detail"] == "gate-policy-unmatched-class:stall:accept-risk-ineligible"


def _allowed_gate_policy_layer_sources(repo):
    cm = _load_core_md()
    import review_gate_policy as rgp
    return {cm.core_path(repo, root=None), rgp.gate_policy_path()}


def test_advance_has_no_caller_supplied_policy_route(tmp_path, adapters):
    """Gate policy is calibration-only — no advance flag may inject rules."""
    parser = RD.build_parser()
    for _path, action in __import__("cli_contract").iter_caller_supplied_actions(parser):
        assert "policy" not in action.dest
        for opt in action.option_strings:
            assert "policy" not in opt.lower()
    repo = _repo_with_gate_policy(tmp_path, [{
        "gate": "present-judgment",
        "findingClass": "judgment:important",
        "disposition": "skip",
    }])
    d = _judgment_session_with_repo(tmp_path, adapters, repo, name="policy-sources")
    out = _advance(d, tmp_path)
    assert out["ok"] is True, out
    allowed = _allowed_gate_policy_layer_sources(repo)
    for layer in out["policyApplied"]["layers"]:
        assert layer.get("source") in allowed, layer


def test_advance_owner_gate_policy_applied_commits_state_and_journal(tmp_path, adapters, monkeypatch):
    """Policy-applied durable record bundles state + journal in one commit."""
    repo = _repo_with_gate_policy(tmp_path, [{
        "gate": "present-judgment",
        "findingClass": "judgment:important",
        "disposition": "skip",
    }])
    d = _judgment_session_with_repo(tmp_path, adapters, repo, name="policy-commit")
    seen = []
    real_begin = RD.round_commit.begin

    def track_begin(session_dir, kind, **kw):
        commit = real_begin(session_dir, kind, **kw)
        seen.append((kind, commit))
        return commit

    monkeypatch.setattr(RD.round_commit, "begin", track_begin)
    out = _advance(d, tmp_path)
    assert out["ok"] is True, out
    commit_kinds = [kind for kind, _commit in seen]
    assert "advance-policy-applied" not in commit_kinds
    accepts = [c for kind, c in seen if kind == "submit-accept"]
    assert len(accepts) == 1, commit_kinds
    journals = [p for p in accepts[0]._parts if p.get("type") == "journal-append"]
    assert any((j.get("entry") or {}).get("outcome") == "accepted" for j in journals), journals
    assert any((j.get("entry") or {}).get("outcome") == "advanced"
               and (j.get("entry") or {}).get("policyApplied") for j in journals), journals


def test_policy_applied_records_match_and_action_not_identities_only(tmp_path, adapters):
    repo = _repo_with_gate_policy(tmp_path, [{
        "gate": "present-judgment",
        "findingClass": "judgment:important",
        "disposition": "fix-as-suggested",
    }])
    d = _judgment_session_with_repo(tmp_path, adapters, repo)
    out = _advance(d, tmp_path)
    assert out["ok"] is True
    applied = out["policyApplied"]
    assert applied["matches"]
    assert applied["matches"][0].get("rule")
    assert applied["action"]
    assert _state(d)["step"] == RD.P_FIXER


def test_advance_owner_gate_fold_refused_leaves_session_unblocked(tmp_path, adapters, monkeypatch):
    """Policy staging is durable only after a successful fold — refused folds keep submit open."""
    repo = _repo_with_gate_policy(tmp_path, [{
        "gate": "present-judgment",
        "findingClass": "judgment:important",
        "disposition": "fix-as-suggested",
    }])
    d = _judgment_session_with_repo(tmp_path, adapters, repo, name="fold-refused")
    real_submit = RD.cmd_submit

    def refuse_once(session_dir, phase, attempt, state_hash_arg, artifact, _via_advance=False,
                    _pending_policy_applied=None, _policy_journal_entry=None, _durable_record=None):
        if _via_advance:
            return {"ok": False, "reason": "test-fold-refused"}
        return real_submit(session_dir, phase, attempt, state_hash_arg, artifact,
                           _via_advance=_via_advance,
                           _pending_policy_applied=_pending_policy_applied,
                           _policy_journal_entry=_policy_journal_entry,
                           _durable_record=_durable_record)

    monkeypatch.setattr(RD, "cmd_submit", refuse_once)
    out = _advance(d, tmp_path)
    assert out["ok"] is False and out["reason"] == "fold-refused"
    assert out["detail"] == "test-fold-refused"
    state = _state(d)
    assert state.get("_advanceUsed") is not True
    assert not state.get("_policyApplied")
    receipt = RD.build_receipt(state, d)
    assert not receipt.get("policyApplied")
    pend = RD.cmd_next(d)
    hand = RD.cmd_submit(d, pend["phase"], pend["attempt"], pend["expectedStateHash"],
                         {"dispositions": [
                             {"id": RD._location_id(state["_judgmentFindings"][0]),
                              "disposition": "fix-as-suggested"},
                         ]})
    assert hand["ok"] is True, hand


def test_stall_accept_risk_terminal_receipt_on_disk_carries_policy_applied(tmp_path, adapters):
    """FX-4B-4 detector 1: stall accept-the-disclosed-risk converges inside the fold and the
    write-once terminal receipt must carry policyApplied — assert against the on-disk file, not
    in-memory state."""
    repo = _repo_with_gate_policy(tmp_path, [{
        "gate": "present-stall-menu",
        "findingClass": "stall:accept-risk-eligible",
        "disposition": "accept-the-disclosed-risk",
    }])
    d = _parked_at_owner_gate(tmp_path, adapters, RD.P_STALL, name="stall-receipt-provenance")
    state = _state(d)
    state["config"]["repoRoot"] = repo
    state["_acceptRiskEligible"] = True
    state["_stallTargets"] = [dict(_CONFIRMED_STALL_TARGET)]
    RD.save_state(d, state)
    out = _advance(d, tmp_path)
    assert out["ok"] is True, out
    assert _state(d)["terminal"] == "converged"
    receipt_path = os.path.join(d, RD.RECEIPT_FILE)
    assert os.path.isfile(receipt_path), "terminal receipt must be on disk"
    with open(receipt_path, encoding="utf-8") as fh:
        on_disk = json.load(fh)
    policy = on_disk.get("policyApplied")
    assert policy, "on-disk round-receipt.json must carry policyApplied"
    assert policy[-1]["phase"] == RD.P_STALL
    assert policy[-1]["action"] == {"choice": "accept-the-disclosed-risk"}


def test_owner_gate_fold_refused_leaves_no_policy_applied_durable_record(tmp_path, adapters,
                                                                         monkeypatch):
    """FX-4B-4 detector 2: a fold-refused owner-gate advance must leave no durable record claiming
    policy was applied — not in state, not in any receipt, not in the journal."""
    repo = _repo_with_gate_policy(tmp_path, [{
        "gate": "present-judgment",
        "findingClass": "judgment:important",
        "disposition": "fix-as-suggested",
    }])
    d = _judgment_session_with_repo(tmp_path, adapters, repo, name="fold-refused-no-claim")
    real_submit = RD.cmd_submit

    def refuse_once(session_dir, phase, attempt, state_hash_arg, artifact, _via_advance=False,
                    _pending_policy_applied=None, _policy_journal_entry=None, _durable_record=None):
        if _via_advance:
            return {"ok": False, "reason": "test-fold-refused"}
        return real_submit(session_dir, phase, attempt, state_hash_arg, artifact,
                           _via_advance=_via_advance,
                           _pending_policy_applied=_pending_policy_applied,
                           _policy_journal_entry=_policy_journal_entry,
                           _durable_record=_durable_record)

    monkeypatch.setattr(RD, "cmd_submit", refuse_once)
    out = _advance(d, tmp_path)
    assert out["ok"] is False and out["reason"] == "fold-refused"
    state = _state(d)
    assert not state.get("_policyApplied")
    assert not RD.build_receipt(state, d).get("policyApplied")
    assert not _receipt_on_disk_policy_applied(d)
    assert not _journal_events_claiming_policy_applied(d)


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
# §4c advance --owner-artifact (#1061 WO-B)
# =============================================================================================

def _write_owner_artifact(tmp_path, artifact, name="owner-artifact.json"):
    path = str(tmp_path / name)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(artifact, fh)
    return path


def _judgment_dispositions_artifact(state):
    finding = state["_judgmentFindings"][0]
    return {"dispositions": [{"id": RD._location_id(finding),
                              "disposition": "fix-as-suggested"}]}


def _set_advance_used(session_dir):
    state = _state(session_dir)
    state["_advanceUsed"] = True
    RD.save_state(session_dir, state)


def test_advance_owner_artifact_judgment_closes_dead_end(tmp_path, adapters):
    repo = _repo_without_gate_policy(tmp_path)
    d = _judgment_session_with_repo(tmp_path, adapters, repo, name="owner-artifact-judgment")
    _set_advance_used(d)
    out = _advance(d, tmp_path)
    assert out["ok"] is False and out["reason"] == "advance-judgment-park"
    artifact = _judgment_dispositions_artifact(_state(d))
    out = _advance(d, tmp_path, owner_artifact_path=_write_owner_artifact(tmp_path, artifact))
    assert out["ok"] is True, out
    assert out["policyApplied"]["source"] == RD.POLICY_APPLIED_SOURCE_OWNER_SUPPLIED
    assert out["policyApplied"]["artifactSha256"] == hashlib.sha256(
        RD._canonical(artifact).encode("utf-8")).hexdigest()
    assert _state(d)["step"] == RD.P_FIXER
    advanced = [e for e in _journal(d) if e.get("outcome") == "advanced" and e.get("policyApplied")]
    assert advanced[-1]["policyApplied"]["source"] == RD.POLICY_APPLIED_SOURCE_OWNER_SUPPLIED


def test_advance_owner_artifact_stall_closes_dead_end(tmp_path, adapters):
    d = _parked_at_owner_gate(tmp_path, adapters, RD.P_STALL, name="owner-artifact-stall")
    _set_advance_used(d)
    artifact = {"choice": RD.HOLD_CHOICE}
    out = _advance(d, tmp_path, owner_artifact_path=_write_owner_artifact(tmp_path, artifact))
    assert out["ok"] is True, out
    assert out["policyApplied"]["source"] == RD.POLICY_APPLIED_SOURCE_OWNER_SUPPLIED
    assert _state(d)["terminal"] == "held"


def test_advance_owner_artifact_runs_stall_chokepoint(tmp_path, adapters):
    d = _parked_at_owner_gate(tmp_path, adapters, RD.P_STALL, name="owner-artifact-stall-guard")
    _set_advance_used(d)
    bad = {"choice": "not-on-menu"}
    out = _advance(d, tmp_path, owner_artifact_path=_write_owner_artifact(tmp_path, bad, "bad.json"))
    assert out["ok"] is False and out["reason"] == "fold-refused"
    assert out["detail"] == "%snot-on-menu" % RD.STALL_CHOICE_NOT_OFFERED_PREFIX
    assert _state(d)["pending"]["phase"] == RD.P_STALL
    good = {"choice": RD.HOLD_CHOICE}
    out = _advance(d, tmp_path, owner_artifact_path=_write_owner_artifact(tmp_path, good, "good.json"))
    assert out["ok"] is True, out


def test_advance_owner_artifact_terminal_refusal(tmp_path, adapters):
    gitdir = _gitdir(tmp_path, "owner-artifact-terminal")
    d = _session(tmp_path, name="owner-artifact-terminal")
    _drive_to_terminal(d, tmp_path, adapters, gitdir=gitdir)
    path = _write_owner_artifact(tmp_path, {"choice": RD.HOLD_CHOICE})
    out = _advance(d, tmp_path, owner_artifact_path=path)
    assert out["ok"] is False and out["reason"] == RD.OWNER_ARTIFACT_TERMINAL_REFUSAL
    out = _advance(d, tmp_path)
    assert out["ok"] is True and out.get("idempotent") is True


def test_advance_owner_artifact_submit_used_refuses_before_io(tmp_path, adapters):
    d = _session(tmp_path, name="owner-artifact-submit-used")
    state = _state(d)
    state["_submitUsed"] = True
    state["step"] = RD.P_STALL
    state["pending"] = {"action": RD.P_STALL, "round": 1, "phase": RD.P_STALL, "attempt": 0,
                        "payload": {}}
    state["_stallChoices"] = list(RD.STALL_CHOICES)
    RD.save_state(d, state)
    missing = str(tmp_path / "does-not-exist.json")
    assert not os.path.exists(missing)
    out = _advance(d, tmp_path, owner_artifact_path=missing)
    assert out["ok"] is False and out["reason"] == "advance-submit-interleaved"
    assert not os.path.exists(missing)


def test_advance_owner_artifact_seat_phase_refuses_before_io(tmp_path, adapters):
    d = _session(tmp_path, name="owner-artifact-seat")
    _set_advance_used(d)
    missing = str(tmp_path / "does-not-exist-seat.json")
    assert not os.path.exists(missing)
    out = _advance(d, tmp_path, owner_artifact_path=missing)
    assert out["ok"] is False and out["reason"] == "advance-submit-interleaved"
    assert not os.path.exists(missing)


def test_advance_owner_artifact_unreadable_missing_file(tmp_path, adapters):
    d = _parked_at_owner_gate(tmp_path, adapters, RD.P_STALL, name="owner-artifact-missing")
    missing = str(tmp_path / "missing-owner-artifact.json")
    out = _advance(d, tmp_path, owner_artifact_path=missing)
    assert out["ok"] is False and out["reason"] == RD.OWNER_ARTIFACT_UNREADABLE_REFUSAL


def test_advance_owner_artifact_unreadable_invalid_json(tmp_path, adapters):
    d = _parked_at_owner_gate(tmp_path, adapters, RD.P_STALL, name="owner-artifact-bad-json")
    path = str(tmp_path / "bad.json")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("{not json")
    out = _advance(d, tmp_path, owner_artifact_path=path)
    assert out["ok"] is False and out["reason"] == RD.OWNER_ARTIFACT_UNREADABLE_REFUSAL


def test_advance_owner_artifact_shape_refusal_json_list(tmp_path, adapters):
    d = _parked_at_owner_gate(tmp_path, adapters, RD.P_STALL, name="owner-artifact-list")
    path = _write_owner_artifact(tmp_path, [1, 2, 3], "list.json")
    out = _advance(d, tmp_path, owner_artifact_path=path)
    assert out["ok"] is False and out["reason"] == RD.OWNER_ARTIFACT_SHAPE_REFUSAL


def test_advance_calibration_path_policy_applied_source_gate_policy(tmp_path, adapters):
    repo = _repo_with_gate_policy(tmp_path, [{
        "gate": "present-judgment",
        "findingClass": "judgment:important",
        "disposition": "skip",
    }])
    d = _judgment_session_with_repo(tmp_path, adapters, repo, name="gate-policy-source")
    out = _advance(d, tmp_path)
    assert out["ok"] is True, out
    assert out["policyApplied"]["source"] == RD.POLICY_APPLIED_SOURCE_GATE_POLICY
    advanced = [e for e in _journal(d) if e.get("outcome") == "advanced" and e.get("policyApplied")]
    assert advanced[-1]["policyApplied"]["source"] == RD.POLICY_APPLIED_SOURCE_GATE_POLICY
    on_disk = _receipt_on_disk_policy_applied(d)
    assert on_disk[-1]["source"] == RD.POLICY_APPLIED_SOURCE_GATE_POLICY


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


# --- FB-12: _ensure_round_diff atomic write + content guard -------------------------------


def _fb12_round_dir(session_dir, rnd=1):
    rdir = RR.round_dir(session_dir, rnd)
    os.makedirs(rdir, exist_ok=True)
    return rdir


def test_ensure_round_diff_writes_when_absent(tmp_path):
    d = str(tmp_path / "fb12-absent")
    state = {"reviewedDiff": DIFF}
    path = RD._ensure_round_diff(d, 1, state)
    assert path == os.path.join(_fb12_round_dir(d), "diff.txt")
    with open(path, encoding="utf-8") as fh:
        assert fh.read() == DIFF


def test_ensure_round_diff_returns_existing_when_correct(tmp_path):
    d = str(tmp_path / "fb12-correct")
    rdir = _fb12_round_dir(d)
    diff_path = os.path.join(rdir, "diff.txt")
    with open(diff_path, "w", encoding="utf-8") as fh:
        fh.write(DIFF)
    mtime_before = os.path.getmtime(diff_path)
    path = RD._ensure_round_diff(d, 1, {"reviewedDiff": DIFF})
    assert path == diff_path
    assert os.path.getmtime(diff_path) == mtime_before


def test_ensure_round_diff_repairs_zero_byte(tmp_path):
    d = str(tmp_path / "fb12-zero")
    diff_path = os.path.join(_fb12_round_dir(d), "diff.txt")
    with open(diff_path, "wb"):
        pass
    path = RD._ensure_round_diff(d, 1, {"reviewedDiff": DIFF})
    assert path == diff_path
    with open(diff_path, encoding="utf-8") as fh:
        assert fh.read() == DIFF


def test_ensure_round_diff_repairs_mismatch(tmp_path):
    d = str(tmp_path / "fb12-mismatch")
    diff_path = os.path.join(_fb12_round_dir(d), "diff.txt")
    with open(diff_path, "w", encoding="utf-8") as fh:
        fh.write("stale diff\n")
    path = RD._ensure_round_diff(d, 1, {"reviewedDiff": DIFF})
    assert path == diff_path
    with open(diff_path, encoding="utf-8") as fh:
        assert fh.read() == DIFF


@pytest.mark.parametrize("reviewed_diff", [pytest.param(None, id="none"),
                                           pytest.param({"x": 1}, id="dict")])
def test_ensure_round_diff_refuses_non_string_reviewed_diff(tmp_path, reviewed_diff):
    d = str(tmp_path / "fb12-non-string")
    with pytest.raises(ValueError, match="reviewed-diff-unavailable"):
        RD._ensure_round_diff(d, 1, {"reviewedDiff": reviewed_diff})


def test_ensure_round_diff_refuses_missing_reviewed_diff(tmp_path):
    d = str(tmp_path / "fb12-missing")
    with pytest.raises(ValueError, match="reviewed-diff-unavailable"):
        RD._ensure_round_diff(d, 1, {})


# --- receipt write-order census (FX-4B-R3) ---------------------------------
#
# Blind spots (honest narrower guard — see module docstring in test below):
# - Nested config reads such as ``(state.get("config") or {}).get("baseDegraded")`` are not
#   expanded; only one-hop helpers whose body reads ``state`` literally are followed.
# - Dynamic or computed state keys are invisible.
# - Writers inside nested functions or lambdas are not attributed.

_ROUND_DRIVER_PATH = os.path.join(_LIB, "round_driver.py")
_RECEIPT_CENSUS_BOOTSTRAP_KEYS = frozenset({"_scriptRan"})


def _round_driver_ast():
    with open(_ROUND_DRIVER_PATH, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    return tree, ast


def _fn_node(tree, ast_mod, name):
    node = next((n for n in ast_mod.walk(tree)
                 if isinstance(n, ast_mod.FunctionDef) and n.name == name), None)
    assert node is not None, "round_driver has no function %r — census parse is inert" % name
    return node


def _function_index(tree, ast_mod):
    return {node.name: node for node in tree.body if isinstance(node, ast_mod.FunctionDef)}


def _literal_state_keys_read_in_function(fn_node, ast_mod, func_index=None, _visiting=None):
    keys = set()
    for node in ast_mod.walk(fn_node):
        if isinstance(node, ast_mod.Call):
            func = node.func
            if (isinstance(func, ast_mod.Attribute) and func.attr == "get"
                    and isinstance(func.value, ast_mod.Name) and func.value.id == "state"
                    and node.args and isinstance(node.args[0], ast_mod.Constant)
                    and isinstance(node.args[0].value, str)):
                keys.add(node.args[0].value)
            elif (isinstance(func, ast_mod.Name) and func_index is not None
                  and func.id in func_index and node.args
                  and isinstance(node.args[0], ast_mod.Name) and node.args[0].id == "state"):
                callee = func.id
                if _visiting is None:
                    _visiting = set()
                if callee in _visiting:
                    continue
                _visiting.add(callee)
                keys |= _literal_state_keys_read_in_function(
                    func_index[callee], ast_mod, func_index, _visiting)
        elif isinstance(node, ast_mod.Subscript):
            if (isinstance(node.value, ast_mod.Name) and node.value.id == "state"
                    and isinstance(node.slice, ast_mod.Constant)
                    and isinstance(node.slice.value, str)):
                keys.add(node.slice.value)
    return keys


def _post_fold_advance_callers(tree, ast_mod):
    """Functions that fold through ``cmd_submit`` with ``_via_advance=True``."""
    callers = set()
    for node in tree.body:
        if not isinstance(node, ast_mod.FunctionDef):
            continue
        for sub in ast_mod.walk(node):
            if not isinstance(sub, ast_mod.Call):
                continue
            func = sub.func
            if not (isinstance(func, ast_mod.Name) and func.id == "cmd_submit"):
                continue
            for kw in sub.keywords:
                if (kw.arg == "_via_advance"
                        and isinstance(kw.value, ast_mod.Constant)
                        and kw.value.value is True):
                    callers.add(node.name)
    return callers


def _functions_assigning_state_key(tree, ast_mod, key):
    writers = set()
    for node in tree.body:
        if not isinstance(node, ast_mod.FunctionDef):
            continue
        for sub in ast_mod.walk(node):
            targets = []
            if isinstance(sub, ast_mod.Assign):
                targets = sub.targets
            elif isinstance(sub, ast_mod.AugAssign):
                targets = [sub.target]
            for target in targets:
                if (isinstance(target, ast_mod.Subscript)
                        and isinstance(target.value, ast_mod.Name)
                        and target.value.id == "state"
                        and isinstance(target.slice, ast_mod.Constant)
                        and target.slice.value == key):
                    writers.add(node.name)
    return writers


def test_receipt_state_writes_census_no_post_fold_receipt_relevant_writes():
    """Census — receipt-relevant state must not be written by post-fold advance callers.

    Derives post-fold callers from ``cmd_submit(..., _via_advance=True)`` call sites and expands
    receipt-relevant keys one hop into same-module ``state`` helpers (e.g. ``_degraded`` →
    ``independenceDegraded``). See module comment above for blind spots."""
    tree, ast_mod = _round_driver_ast()
    func_index = _function_index(tree, ast_mod)
    post_fold_callers = _post_fold_advance_callers(tree, ast_mod)
    assert post_fold_callers, "no post-fold advance callers found — census parse is inert"
    receipt_keys = _literal_state_keys_read_in_function(
        _fn_node(tree, ast_mod, "build_receipt"), ast_mod, func_index)
    assert len(receipt_keys) >= 9, (
        "build_receipt reads %d state keys — census parse looks inert" % len(receipt_keys))

    post_fold_violations = {}
    for key in sorted(receipt_keys):
        if key in _RECEIPT_CENSUS_BOOTSTRAP_KEYS:
            continue
        bad = _functions_assigning_state_key(tree, ast_mod, key) & post_fold_callers
        if bad:
            post_fold_violations[key] = sorted(bad)
    assert post_fold_violations == {}, (
        "receipt-relevant state written by post-fold callers: %s" % post_fold_violations)


def test_receipt_state_writes_census_red_on_post_fold_probe_write():
    """Bite-axis: a receipt-relevant key written only post-fold must fail the census."""
    tree, ast_mod = _round_driver_ast()
    func_index = _function_index(tree, ast_mod)
    post_fold_callers = _post_fold_advance_callers(tree, ast_mod)
    probe_key = "_censusReceiptProbe"
    with open(_ROUND_DRIVER_PATH, encoding="utf-8") as fh:
        source = fh.read()
    marker = "    ok_after, after = load_state(session_dir)\n"
    assert marker in source
    probe_line = '    state["%s"] = True\n' % probe_key
    probed = source.replace(marker, probe_line + marker, 1)
    probed_tree = ast.parse(probed)
    build_receipt = next(n for n in ast_mod.walk(probed_tree)
                         if isinstance(n, ast_mod.FunctionDef) and n.name == "build_receipt")
    # Inject a read of the probe key so the census considers it receipt-relevant.
    build_receipt.body.insert(0, ast.parse('state.get("%s")' % probe_key).body[0])
    receipt_keys = _literal_state_keys_read_in_function(build_receipt, ast_mod, func_index)
    assert probe_key in receipt_keys
    bad = _functions_assigning_state_key(probed_tree, ast_mod, probe_key) & post_fold_callers
    assert bad == {"_advance_owner_gate"}, bad


# =============================================================================================
# round-ceiling advance park — honest notFolded receipts (#1030, ruling 23-b)
# =============================================================================================

_CEILING_FIXTURE_CEILING = 10
_CEILING_FIXTURE_REACHED = 11


def _above_ceiling_state_baseline(state, reached_round):
    state["round"] = reached_round
    state["findings"] = []
    state["fullPanelRan"] = True
    state["_advanceUsed"] = True
    return state


def _above_ceiling_orchestrator_session(tmp_path, adapters,
                                        ceiling=_CEILING_FIXTURE_CEILING,
                                        reached_round=_CEILING_FIXTURE_REACHED):
    d = _session(tmp_path, name="ceil-orch",
                 maxRoundsAbsolute=ceiling, maxRounds=7)
    state = _state(d)
    _above_ceiling_state_baseline(state, reached_round)
    state["step"] = RD.P_VERIFY
    state["pending"] = {"action": RD.P_VERIFY, "round": reached_round, "phase": RD.P_VERIFY,
                        "attempt": 0, "payload": {"command": "none"}}
    RD.save_state(d, state)
    _write_verify_payload(d, {"result": "pass"})
    return d


def _above_ceiling_owner_gate_session(tmp_path, adapters, phase=RD.P_JUDGMENT,
                                      ceiling=_CEILING_FIXTURE_CEILING,
                                      reached_round=_CEILING_FIXTURE_REACHED):
    repo = _repo_with_gate_policy(tmp_path, [{
        "gate": "present-judgment",
        "findingClass": "judgment:important",
        "disposition": "skip",
    }])
    d = _judgment_session_with_repo(tmp_path, adapters, repo, name="ceil-owner")
    state = _state(d)
    state["round"] = reached_round
    state["pending"]["round"] = reached_round
    RD.save_state(d, state)
    return d


def _above_ceiling_panel_session(tmp_path, adapters,
                                 ceiling=_CEILING_FIXTURE_CEILING,
                                 reached_round=_CEILING_FIXTURE_REACHED):
    d = _session(tmp_path, name="ceil-panel",
                 maxRoundsAbsolute=ceiling, maxRounds=7)
    state = _state(d)
    _above_ceiling_state_baseline(state, reached_round)
    state["step"] = RD.P_PANEL
    state["pending"] = {"action": RD.P_PANEL, "round": reached_round, "phase": RD.P_PANEL,
                        "attempt": 0, "payload": {}}
    RD.save_state(d, state)
    _record_all_panel_seats(d)
    return d


def _advance_rows_for_step(session_dir, phase, rnd, attempt):
    return [e for e in _journal(session_dir)
            if e.get("cmd") == "advance" and e.get("phase") == phase
            and e.get("round") == rnd and e.get("attempt") == attempt]


def test_orchestrator_fulfilled_locked_parks_honestly_above_round_ceiling(tmp_path, adapters):
    """Loaded state above the ceiling parks through _advance_orchestrator_fulfilled_locked honestly."""
    ceiling = _CEILING_FIXTURE_CEILING
    reached_round = _CEILING_FIXTURE_REACHED
    assert reached_round == ceiling + 1, "fixture must distinguish ceiling from round reached"
    d = _above_ceiling_orchestrator_session(tmp_path, adapters, ceiling=ceiling,
                                            reached_round=reached_round)
    state = _state(d)
    pend = state["pending"]
    phase, rnd, attempt = pend["phase"], pend["round"], pend["attempt"]
    last_accepted_before = copy.deepcopy(state.get("lastAccepted"))
    config = state.get("config") or {}
    assert config["maxRoundsAbsolute"] == ceiling
    assert rnd == reached_round
    out = RD._advance_orchestrator_fulfilled_locked(
        d, state, phase, rnd, attempt, config, git=_fake_git(_gitdir(tmp_path)))
    assert out["ok"] is True
    assert "folded" not in out
    assert out["notFolded"]["reason"] == "round-ceiling"
    assert out["notFolded"]["phase"] == phase
    assert out["notFolded"]["round"] == rnd
    assert out["notFolded"]["attempt"] == attempt
    assert out["terminal"] == "halted"
    reloaded = _state(d)
    assert reloaded["certification"]["shape"] is None
    rows = _advance_rows_for_step(d, phase, rnd, attempt)
    assert not any(r.get("outcome") == "advanced" for r in rows)
    assert any(r.get("outcome") == "not-folded" for r in rows)
    assert reloaded.get("lastAccepted") == last_accepted_before
    assert out["durableRecord"]["written"] is False
    assert out["durableRecord"]["reason"].strip()
    assert not os.path.exists(_verify_store_path(d, rnd=rnd))


def test_advance_owner_gate_parks_honestly_above_round_ceiling(tmp_path, adapters):
    """Loaded state above the ceiling parks through _advance_owner_gate without a folded receipt."""
    d = _above_ceiling_owner_gate_session(tmp_path, adapters)
    state = _state(d)
    pend = state["pending"]
    phase, rnd, attempt = pend["phase"], pend["round"], pend["attempt"]
    config = state.get("config") or {}
    out = RD._advance_owner_gate(d, state, phase, rnd, attempt, config,
                                 git=_fake_git(_gitdir(tmp_path)))
    assert out["ok"] is True
    assert "folded" not in out
    assert out["notFolded"]["reason"] == "round-ceiling"
    assert out["terminal"] == "halted"
    assert "durableRecord" not in out
    rows = _advance_rows_for_step(d, phase, rnd, attempt)
    assert not any(r.get("outcome") == "advanced" for r in rows)


def test_advance_locked_parks_honestly_above_round_ceiling(tmp_path, adapters):
    """Loaded state above the ceiling parks through _advance_locked without a folded receipt."""
    d = _above_ceiling_panel_session(tmp_path, adapters)
    state = _state(d)
    pend = state["pending"]
    phase, rnd, attempt = pend["phase"], pend["round"], pend["attempt"]
    out = RD._advance_locked(d, state, git=_fake_git(_gitdir(tmp_path)))
    assert out["ok"] is True
    assert "folded" not in out
    assert out["notFolded"]["reason"] == "round-ceiling"
    assert out["terminal"] == "halted"
    assert "durableRecord" not in out
    rows = _advance_rows_for_step(d, phase, rnd, attempt)
    assert not any(r.get("outcome") == "advanced" for r in rows)


# --- #1061 advance/submit refusal contract -------------------------------------


def _patch_submit_accept_run(monkeypatch, reason, detail="simulated"):
    real_begin = RD.round_commit.begin

    def hooked_begin(session_dir, kind, **kw):
        commit = real_begin(session_dir, kind, **kw)
        if kind == "submit-accept":
            def run():
                raise RD.round_commit.CommitRefused(reason, detail)
            commit.run = run
        return commit

    monkeypatch.setattr(RD.round_commit, "begin", hooked_begin)


def _judgment_submit_artifact(session_dir):
    state = _state(session_dir)
    return {"dispositions": [
        {"id": RD._location_id(state["_judgmentFindings"][0]), "disposition": "skip"},
    ]}


def test_cmd_submit_cleanup_failure_carries_foldLanded(tmp_path, adapters, monkeypatch):
    repo = _repo_with_gate_policy(tmp_path, [{
        "gate": "present-judgment",
        "findingClass": "judgment:important",
        "disposition": "skip",
    }])
    d = _judgment_session_with_repo(tmp_path, adapters, repo, name="cleanup-fold")
    pend = _pending(d)
    _patch_submit_accept_run(monkeypatch, "commit-cleanup-failed")
    out = RD.cmd_submit(d, pend["phase"], pend["attempt"], RD.state_hash(_state(d)),
                        _judgment_submit_artifact(d), _via_advance=True)
    assert out == {"ok": False, "reason": "commit-cleanup-failed", "detail": "simulated",
                   "foldLanded": True}


def test_cmd_submit_apply_failure_does_not_carry_foldLanded(tmp_path, adapters, monkeypatch):
    repo = _repo_with_gate_policy(tmp_path, [{
        "gate": "present-judgment",
        "findingClass": "judgment:important",
        "disposition": "skip",
    }])
    d = _judgment_session_with_repo(tmp_path, adapters, repo, name="apply-fold")
    pend = _pending(d)
    _patch_submit_accept_run(monkeypatch, "commit-apply-failed")
    out = RD.cmd_submit(d, pend["phase"], pend["attempt"], RD.state_hash(_state(d)),
                        _judgment_submit_artifact(d), _via_advance=True)
    assert out["ok"] is False and out["reason"] == "commit-apply-failed"
    assert "foldLanded" not in out


def test_advance_owner_gate_propagates_receipt_fault_and_exits_nonzero(tmp_path, adapters,
                                                                       monkeypatch):
    repo = _repo_with_gate_policy(tmp_path, [{
        "gate": "present-judgment",
        "findingClass": "judgment:important",
        "disposition": "skip",
    }])
    d = _judgment_session_with_repo(tmp_path, adapters, repo, name="receipt-fault-owner")
    real_submit = RD.cmd_submit

    def submit_receipt_fault(session_dir, phase, attempt, state_hash_arg, artifact,
                             _via_advance=False, **_kw):
        if _via_advance:
            return {"ok": False, "reason": "receipt-fault", "detail": "simulated fault",
                    "foldLanded": True}
        return real_submit(session_dir, phase, attempt, state_hash_arg, artifact,
                           _via_advance=_via_advance, **_kw)

    monkeypatch.setattr(RD, "cmd_submit", submit_receipt_fault)
    out = _advance(d, tmp_path)
    assert out["ok"] is False and out["reason"] == "receipt-fault"
    assert out["reason"] != "fold-refused"
    rc = RD.main(["advance", "--session-dir", d])
    assert rc == 1


def test_advance_locked_propagates_receipt_fault_and_exits_nonzero(tmp_path, adapters,
                                                                   monkeypatch):
    d = _session(tmp_path, name="receipt-fault-seat")
    _record_all_panel_seats(d)
    real_submit = RD.cmd_submit

    def submit_receipt_fault(session_dir, phase, attempt, state_hash_arg, artifact,
                             _via_advance=False, **_kw):
        if _via_advance:
            return {"ok": False, "reason": "receipt-fault", "detail": "simulated fault",
                    "foldLanded": True}
        return real_submit(session_dir, phase, attempt, state_hash_arg, artifact,
                           _via_advance=_via_advance, **_kw)

    monkeypatch.setattr(RD, "cmd_submit", submit_receipt_fault)
    out = _advance(d, tmp_path)
    assert out["ok"] is False and out["reason"] == "receipt-fault"
    rc = RD.main(["advance", "--session-dir", d])
    assert rc == 1


def test_advance_fold_refused_still_wraps_non_receipt_fault(tmp_path, adapters, monkeypatch):
    repo = _repo_with_gate_policy(tmp_path, [{
        "gate": "present-judgment",
        "findingClass": "judgment:important",
        "disposition": "skip",
    }])
    d = _judgment_session_with_repo(tmp_path, adapters, repo, name="ordinary-refusal")
    real_submit = RD.cmd_submit

    def submit_refused(session_dir, phase, attempt, state_hash_arg, artifact,
                       _via_advance=False, **_kw):
        if _via_advance:
            return {"ok": False, "reason": "commit-apply-failed", "detail": "simulated"}
        return real_submit(session_dir, phase, attempt, state_hash_arg, artifact,
                           _via_advance=_via_advance, **_kw)

    monkeypatch.setattr(RD, "cmd_submit", submit_refused)
    out = _advance(d, tmp_path)
    assert out["ok"] is False and out["reason"] == "fold-refused"
    assert out["detail"] == "commit-apply-failed"


def test_advance_fold_refused_carries_foldLanded_from_submit(tmp_path, adapters, monkeypatch):
    repo = _repo_with_gate_policy(tmp_path, [{
        "gate": "present-judgment",
        "findingClass": "judgment:important",
        "disposition": "skip",
    }])
    d = _judgment_session_with_repo(tmp_path, adapters, repo, name="cleanup-advance")
    real_submit = RD.cmd_submit

    def submit_cleanup_failed(session_dir, phase, attempt, state_hash_arg, artifact,
                              _via_advance=False, **_kw):
        if _via_advance:
            return {"ok": False, "reason": "commit-cleanup-failed", "detail": "simulated",
                    "foldLanded": True}
        return real_submit(session_dir, phase, attempt, state_hash_arg, artifact,
                           _via_advance=_via_advance, **_kw)

    monkeypatch.setattr(RD, "cmd_submit", submit_cleanup_failed)
    out = _advance(d, tmp_path)
    assert out["ok"] is False and out["reason"] == "fold-refused"
    assert out["detail"] == "commit-cleanup-failed"
    assert out.get("foldLanded") is True


def test_owner_gate_policy_applied_rides_the_folds_own_commit_intent(tmp_path, adapters,
                                                                     monkeypatch):
    """ONE submit-accept carries state advance, policyApplied state, and advanced journal row.

    axis: ATOMICITY — the `advanced` row bearing `policyApplied` must share the fold's commit, not
    a second `advance-policy-applied` commit whose journal row could be lost after the fold lands.
    """
    repo = _repo_with_gate_policy(tmp_path, [{
        "gate": "present-judgment",
        "findingClass": "judgment:important",
        "disposition": "skip",
    }])
    d = _judgment_session_with_repo(tmp_path, adapters, repo, name="policy-atomicity")
    seen = []
    real_begin = RD.round_commit.begin

    def spy(session_dir, kind, **kw):
        commit = real_begin(session_dir, kind, **kw)
        seen.append((kind, commit))
        return commit

    monkeypatch.setattr(RD.round_commit, "begin", spy)
    assert _advance(d, tmp_path)["ok"] is True
    commit_kinds = [kind for kind, _commit in seen]
    assert "advance-policy-applied" not in commit_kinds
    accepts = [c for kind, c in seen if kind == "submit-accept"]
    assert len(accepts) == 1, commit_kinds
    parts = accepts[0]._parts
    targets = [p.get("target") for p in parts if p.get("type") == "replace-file"]
    journals = [p for p in parts if p.get("type") == "journal-append"]
    assert any(t.endswith(RD.STATE_FILE) for t in targets), targets
    assert any((j.get("entry") or {}).get("outcome") == "accepted" for j in journals), journals
    assert any((j.get("entry") or {}).get("outcome") == "advanced"
               and (j.get("entry") or {}).get("policyApplied") for j in journals), journals


# --- cmd_submit foldLanded caller census ---------------------------------------

_CMD_SUBMIT_FOLD_GUARD_ALLOWLIST = {
    "_dispatch": "CLI hand path returns the answer verbatim without interpreting fold semantics",
}


class _CmdSubmitCallVisitor(ast.NodeVisitor):
    def __init__(self):
        self.current_fn = None
        self.sites = []

    def visit_FunctionDef(self, node):
        prev = self.current_fn
        self.current_fn = node.name
        self.generic_visit(node)
        self.current_fn = prev

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name) and node.func.id == "cmd_submit":
            self.sites.append((self.current_fn, node))
        self.generic_visit(node)


def _submit_assign_name(fn_node, ast_mod, call_node):
    for node in ast_mod.walk(fn_node):
        if isinstance(node, ast_mod.Assign) and node.value is call_node:
            if len(node.targets) == 1 and isinstance(node.targets[0], ast_mod.Name):
                return node.targets[0].id
    return None


def _walk_own_scope(node, ast_mod):
    """Walk *node* and descendants without entering nested function or lambda bodies."""
    yield node
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast_mod.FunctionDef, ast_mod.AsyncFunctionDef, ast_mod.Lambda)):
            continue
        yield from _walk_own_scope(child, ast_mod)


def _own_scope_nodes(fn_node, ast_mod):
    for stmt in fn_node.body:
        if isinstance(stmt, (ast_mod.FunctionDef, ast_mod.AsyncFunctionDef, ast_mod.Lambda)):
            continue
        yield from _walk_own_scope(stmt, ast_mod)


def _is_fold_landed_get_call(node, ast_mod, var_name):
    if not isinstance(node, ast_mod.Call):
        return False
    func = node.func
    return (isinstance(func, ast_mod.Attribute) and func.attr == "get"
            and isinstance(func.value, ast_mod.Name) and func.value.id == var_name
            and len(node.args) == 1
            and not node.keywords
            and isinstance(node.args[0], ast_mod.Constant)
            and node.args[0].value == "foldLanded")


def _is_fold_landed_guard_test(test, ast_mod, var_name):
    if isinstance(test, ast_mod.UnaryOp) and isinstance(test.op, ast_mod.Not):
        if _is_fold_landed_get_call(test.operand, ast_mod, var_name):
            return True
    if (isinstance(test, ast_mod.Compare) and len(test.ops) == 1
            and isinstance(test.ops[0], ast_mod.IsNot)
            and _is_fold_landed_get_call(test.left, ast_mod, var_name)
            and len(test.comparators) == 1
            and isinstance(test.comparators[0], ast_mod.Constant)
            and test.comparators[0].value is True):
        return True
    return False


def _branch_returns(branch_body, ast_mod):
    for stmt in branch_body:
        for node in _walk_own_scope(stmt, ast_mod):
            if isinstance(node, ast_mod.Return):
                return True
    return False


def _reads_fold_landed_guard(fn_node, ast_mod, var_name):
    for node in _own_scope_nodes(fn_node, ast_mod):
        if not isinstance(node, ast_mod.If):
            continue
        if not _is_fold_landed_guard_test(node.test, ast_mod, var_name):
            continue
        if _branch_returns(node.body, ast_mod):
            return True
    return False


def compute_cmd_submit_fold_guard_gaps(source=None, allowlist=None):
    if source is None:
        tree, ast_mod = _round_driver_ast()
    else:
        ast_mod = ast
        tree = ast.parse(source)
    if allowlist is None:
        allowlist = _CMD_SUBMIT_FOLD_GUARD_ALLOWLIST
    func_index = _function_index(tree, ast_mod)
    visitor = _CmdSubmitCallVisitor()
    visitor.visit(tree)
    callers = set()
    unguarded = []
    for fn_name, call in visitor.sites:
        if fn_name is None:
            unguarded.append("<module>")
            continue
        callers.add(fn_name)
        if fn_name in allowlist:
            continue
        fn_node = func_index[fn_name]
        var = _submit_assign_name(fn_node, ast_mod, call)
        if not var or not _reads_fold_landed_guard(fn_node, ast_mod, var):
            unguarded.append(fn_name)
    stale = sorted(name for name in allowlist if name not in callers)
    return sorted(set(unguarded)), stale


def test_cmd_submit_fold_landed_caller_census():
    """Shape census: every non-exempt cmd_submit caller must guard foldLanded in its own scope.

    Catches (fail closed):
    - A caller with no foldLanded guard at all.
    - A guard hidden in a nested function or lambda rather than the caller's own scope.
    - A guard that does not return from the caller (noop body).
    - A .get("foldLanded") call must be the canonical one-argument spelling
      `<var>.get("foldLanded")`; any explicit default or keyword argument is not a guard by
      rule. The rule exists because `.get("foldLanded", True)` fails open at runtime — an absent
      key yields the truthy default and the guard never fires — and the census deliberately
      enforces the canonical spelling rather than trying to classify defaults by truthiness.
      This is stricter than runtime semantics: `.get("foldLanded", False)` is fail-closed and
      would be safe, and a keyword form raises TypeError rather than failing open; both are
      rejected anyway because the census enforces spelling, not semantics.
    - A caller that is neither exempt nor guarded fails the census.
    - An exemption entry naming a function that no longer calls cmd_submit fails the census
      (stale exemptions must not rot into a silent hole).

    Does not claim (deliberately out of scope; dominance analysis is separate routed work):
    - A guard placed after the work it should protect (late guard).
    - A conditional or elif bypass that skips the guard.
    - A try/except fallthrough past an unlanded fold.
    - Any deliberately mis-written guard — this is shape census, not control-flow dominance.
    """
    unguarded, stale = compute_cmd_submit_fold_guard_gaps()
    assert stale == [], "stale cmd_submit exemptions: %s" % stale
    assert unguarded == [], "unguarded cmd_submit callers: %s" % unguarded


def test_fold_guard_census_rejects_noop_guard():
    source = """
def bad_noop(session_dir):
    folded = cmd_submit(session_dir, "p", 0, "h", {})
    if not folded.get("foldLanded"):
        pass
    _journal_event(session_dir, "advanced")
"""
    unguarded, _stale = compute_cmd_submit_fold_guard_gaps(source=source, allowlist=set())
    assert "bad_noop" in unguarded


def test_fold_guard_census_rejects_get_with_default():
    source = """
def get_default_true(session_dir):
    folded = cmd_submit(session_dir, "p", 0, "h", {})
    if not folded.get("foldLanded", True):
        return {"ok": False}
    _journal_event(session_dir, "advanced")
"""
    unguarded, _stale = compute_cmd_submit_fold_guard_gaps(source=source, allowlist=set())
    assert "get_default_true" in unguarded


def test_fold_guard_census_rejects_nested_guard():
    source = """
def bad_nested(session_dir):
    folded = cmd_submit(session_dir, "p", 0, "h", {})
    def inner():
        if not folded.get("foldLanded"):
            return None
    _journal_event(session_dir, "advanced")
"""
    unguarded, _stale = compute_cmd_submit_fold_guard_gaps(source=source, allowlist=set())
    assert "bad_nested" in unguarded


def test_fold_guard_census_rejects_missing_guard():
    source = """
def unguarded_caller(session_dir):
    folded = cmd_submit(session_dir, "p", 0, "h", {})
    _journal_event(session_dir, "advanced")
"""
    unguarded, _stale = compute_cmd_submit_fold_guard_gaps(source=source, allowlist=set())
    assert "unguarded_caller" in unguarded


def test_fold_guard_census_accepts_not_get_guard_with_return():
    source = """
def good_not_get(session_dir):
    folded = cmd_submit(session_dir, "p", 0, "h", {})
    if not folded.get("foldLanded"):
        return {"ok": False}
    _journal_event(session_dir, "advanced")
"""
    unguarded, _stale = compute_cmd_submit_fold_guard_gaps(source=source, allowlist=set())
    assert unguarded == []


def test_fold_guard_census_accepts_is_not_true_guard_with_return():
    source = """
def good_is_not_true(session_dir):
    folded = cmd_submit(session_dir, "p", 0, "h", {})
    if folded.get("foldLanded") is not True:
        return {"ok": False}
    _journal_event(session_dir, "advanced")
"""
    unguarded, _stale = compute_cmd_submit_fold_guard_gaps(source=source, allowlist=set())
    assert unguarded == []
