"""A ruling reaches the next fix: the `withdraw` verb, `guidance` at every non-terminal step, and the
lift of undisposed real-consequence and guidance-named findings into a round's fix batch.

Drives the CLI-level functions over the real adapters the way `test_rulings_channel_1445.py` does,
reusing its helpers (and, through it, the shared integration harness)."""
import importlib.util
import json
import os
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import round_adapters  # noqa: E402
import round_driver as RD  # noqa: E402
import round_records as RR  # noqa: E402
import session_contract  # noqa: E402

_SPEC = importlib.util.spec_from_file_location(
    "test_rulings_channel_1445", os.path.join(_HERE, "test_rulings_channel_1445.py"))
_RC = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_RC)
_TRI = _RC._TRI

P_FIXER = RD.P_FIXER
_state = _RC._state
_state_bytes = _RC._state_bytes
_bootstrap = _RC._bootstrap
_drive_to_phase = _RC._drive_to_phase
_drive_one_phase = _RC._drive_one_phase
_write_ruling_file = _RC._write_ruling_file
_follow_up = _RC._follow_up
_rule = _RC._rule
_strip_fixer_orders_emitted = _RC._strip_fixer_orders_emitted


# --- fixtures and helpers ------------------------------------------------------------------------

@pytest.fixture
def keep_severity(monkeypatch):
    """The shared harness's verifier verdicts all say `Important`; wrap them (in this file only) so a
    verified finding keeps the severity the panel gave it."""
    original = _TRI._payload_for

    def wrapped(session_dir, state, pend, seat, panel_findings, head_diff_path):
        payload = original(session_dir, state, pend, seat, panel_findings, head_diff_path)
        if pend["phase"] == RD.P_VERIFIERS:
            cluster = _TRI._cluster_for(pend, seat)
            severity_of = {f.get("id"): f.get("severity") for f in cluster.get("findings") or []}
            for verdict in payload["verdicts"]:
                if severity_of.get(verdict["id"]):
                    verdict["severity"] = severity_of[verdict["id"]]
        return payload

    monkeypatch.setattr(_TRI, "_payload_for", wrapped)


def _finding(title, line, severity="Important", kind="real"):
    finding = _RC._blocking_finding(title, line)
    finding["severity"] = severity
    finding["consequenceKind"] = kind
    return finding


def _session(tmp_path, findings, to_phase=P_FIXER, name="c7", **cfg):
    """A session driven to `to_phase` pending: (session_dir, gitdir, head_diff_path)."""
    session_dir, gitdir, head_path = _bootstrap(tmp_path, name=name, **cfg)
    _drive_to_phase(session_dir, gitdir, findings, head_path, to_phase)
    return session_dir, gitdir, head_path


def _key(row):
    return RD._fix_batch_row_key(row)


def _batch_keys(state):
    return [_key(row) for row in state.get("_fixBatch") or []]


def _queue_keys(state):
    return [_key(row) for row in state.get("_fixQueue") or []]


def _rows_by_title(state):
    rows = list(state.get("_fixBatch") or []) + list(state.get("_fixQueue") or [])
    return {row.get("title"): row for row in rows}


def _finding_key_by_title(state, title):
    for finding in state.get("findings") or []:
        if finding.get("title") == title:
            return _key(finding)
    for entry in state.get(session_contract.DISPOSITION_LEDGER_KEY) or []:
        if entry.get("title") == title:
            return RD._finding_identity_key(entry)
    raise AssertionError("no finding titled %r" % title)


def _guidance_file(tmp_path, name, key, text):
    return _write_ruling_file(tmp_path / name, [
        {"id": key, "ruling": "guidance", "reason": "owner call", "guidance": text}])


def _order_path(session_dir, state):
    pend = state["pending"]
    roster, reason = round_adapters.roster_for(pend["phase"], state, state.get("config") or {})
    assert reason is None, reason
    seat, occurrence = RR.roster_slots(roster)[0]
    return RR.order_prompt_path(session_dir, pend["round"], pend["phase"],
                                RR.storage_key(seat, occurrence), pend["attempt"])


def _order_text(session_dir):
    with open(_order_path(session_dir, _state(session_dir)), encoding="utf-8") as fh:
        return fh.read()


def _fix_batch_file_bytes(session_dir, rnd=1):
    with open(os.path.join(RR.round_dir(session_dir, rnd), "fix-batch.json"), "rb") as fh:
        return fh.read()


def _git(cwd, *args):
    done = subprocess.run(
        ["git", "-C", str(cwd), "-c", "user.name=t", "-c", "user.email=t@t",
         "-c", "commit.gpgsign=false", *args],
        capture_output=True, text=True)
    assert done.returncode == 0, (args, done.stdout, done.stderr)
    return done.stdout.strip()


def _throwaway_repo(tmp_path, name="wt"):
    repo = tmp_path / name
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "a.txt").write_text("one\n", encoding="utf-8")
    _git(repo, "add", "a.txt")
    _git(repo, "commit", "-q", "-m", "first")
    return repo, _git(repo, "rev-parse", "HEAD")


def _bind_anchor_head(session_dir, head, repo=None):
    """Bind the pending fixer attempt's orders anchor to `head` (None drops the head) and, with
    `repo`, the session's recorded worktree to it."""
    state = _state(session_dir)
    if repo is not None:
        state["config"]["repoRoot"] = str(repo)
    pend = state["pending"]
    key = RD._anchor_key(pend["round"], pend["phase"], pend["attempt"])
    anchor = dict(state["_ordersAnchors"][key])
    if head is None:
        anchor.pop("headSha", None)
    else:
        anchor["headSha"] = head
    state["_ordersAnchors"][key] = anchor
    RD.save_state(session_dir, state)


def _two_important(tmp_path, name="c7-two"):
    """Fixer attempt emitted over a batch holding F only; G waits in the queue (cap 1)."""
    session_dir, gitdir, head_path = _session(
        tmp_path, [_finding("bounds F", 1), _finding("bounds G", 2)], name=name, fixBatchCap=1)
    state = _state(session_dir)
    assert len(state["_fixBatch"]) == 1 and len(state["_fixQueue"]) == 1, state
    return (session_dir, gitdir, head_path,
            _key(state["_fixBatch"][0]), _key(state["_fixQueue"][0]))


def _journal_refusals(session_dir, reason):
    return [row for row in RD.read_journal(session_dir)
            if row.get("outcome") == "refused" and row.get("reason") == reason]


# --- R1: the withdraw verb -----------------------------------------------------------------------

def test_t1_ruling_while_pending_reaches_the_fix(tmp_path, keep_severity):
    """axis: a ruling given while a fixer attempt is pending is refused with the recovery, and after
    `withdraw` it reaches the fix that follows; the withdrawn attempt can never fold.

    bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo1b_c7_ruling_window.md (elements 3, 5)
    """
    session_dir, _gitdir, _head, key_f, _key_g = _two_important(tmp_path)
    k = _state(session_dir)["pending"]["attempt"]
    ruling = _guidance_file(tmp_path, "r.json", key_f, "wrap it in the retry guard")
    before = _state_bytes(session_dir)
    out = _rule(session_dir, ruling)
    assert out.get("ok") is False and out.get("reason") == "ruling-attempt-pending", out
    assert "withdraw" in out.get("detail", ""), out
    assert _state_bytes(session_dir) == before
    assert _journal_refusals(session_dir, "ruling-attempt-pending")

    repo, head = _throwaway_repo(tmp_path)
    session_repo = _state(session_dir)["config"]["repoRoot"]
    _bind_anchor_head(session_dir, head, repo)
    withdrawn = RD.cmd_withdraw(session_dir, k, "owner ruled on F", repo_root=str(repo))
    assert withdrawn.get("ok") is True and withdrawn.get("restoreCheck") == "checked", withdrawn
    state = _state(session_dir)
    state["config"]["repoRoot"] = session_repo
    RD.save_state(session_dir, state)
    assert state["pending"] is None and state["step"] == P_FIXER
    assert state["withdrawnFixerAttempts"] == [
        {"round": 1, "attempt": k, "reason": "owner ruled on F", "restoreCheck": "checked"}]
    assert any(d["kind"] == "fixer-attempt-withdrawn" for d in state["decisions"])
    assert any(row.get("outcome") == "fixer-attempt-withdrawn" and row.get("attempt") == k
               for row in RD.read_journal(session_dir))

    assert _rule(session_dir, ruling).get("ok") is True
    nxt = RD.cmd_next(session_dir)
    assert nxt.get("ok") and nxt["phase"] == P_FIXER and nxt["attempt"] > k, nxt
    assert key_f in [_key(row) for row in nxt["payload"]["batch"]]
    assert "wrap it in the retry guard" in _order_text(session_dir)

    folded = RD.cmd_submit(session_dir, P_FIXER, k, "any-hash", {})
    assert folded.get("ok") is False and folded.get("reason") == "fixer-attempt-withdrawn", folded


def test_t2_replaced_guidance_never_renders_beside_the_new(tmp_path, keep_severity):
    """axis: guidance ruled before emission renders in attempt K; a later ruling replaces it, and after
    withdraw and re-emission only the new guidance renders and K can never fold."""
    session_dir, gitdir, head_path = _session(
        tmp_path, [_finding("bounds F", 1)], to_phase=RD.P_GAPSWEEP, name="c7-replace")
    key_f = _finding_key_by_title(_state(session_dir), "bounds F")
    assert _rule(session_dir, _guidance_file(tmp_path, "g1.json", key_f, "FIRST-GUIDANCE"))["ok"]
    _drive_to_phase(session_dir, gitdir, [], head_path, P_FIXER)
    k = _state(session_dir)["pending"]["attempt"]
    assert "FIRST-GUIDANCE" in _order_text(session_dir)

    g2 = _guidance_file(tmp_path, "g2.json", key_f, "SECOND-GUIDANCE")
    assert _rule(session_dir, g2).get("reason") == "ruling-attempt-pending"
    assert RD.cmd_withdraw(session_dir, k, "owner replaced the guidance")["ok"]
    assert _rule(session_dir, g2)["ok"]
    assert RD.cmd_next(session_dir)["ok"]
    text = _order_text(session_dir)
    assert "SECOND-GUIDANCE" in text and "FIRST-GUIDANCE" not in text
    assert RD.cmd_submit(session_dir, P_FIXER, k, "h", {}).get("reason") == "fixer-attempt-withdrawn"


def test_t3_ruling_outside_the_emitted_batch_is_recorded_at_once(tmp_path, keep_severity):
    """axis: a ruling whose target is in a later slice (not the emitted batch) is recorded with no
    refusal; the pending attempt, the emitted `_fixBatch` and the emitted `fix-batch.json` bytes stay
    exactly as they were."""
    session_dir, _g, _h, _key_f, key_g = _two_important(tmp_path, "c7-outside")
    before_state = _state(session_dir)
    before_file = _fix_batch_file_bytes(session_dir)
    log_before = len(before_state.get("rulingsLog") or [])
    out = _rule(session_dir, _guidance_file(tmp_path, "r.json", key_g, "for the next slice"))
    assert out.get("ok") is True, out
    after = _state(session_dir)
    assert len(after["rulingsLog"]) == log_before + 1
    assert after["pending"] == before_state["pending"]
    assert after["_fixBatch"] == before_state["_fixBatch"]
    assert _fix_batch_file_bytes(session_dir) == before_file


def test_ruling_on_a_queued_row_reconciles_the_queue_not_the_emitted_batch(tmp_path, keep_severity):
    """axis: with `fixBatchCap` 1 an out-of-scope ruling on a row in `_fixQueue` is accepted while the
    fixer is pending and drops the row from the queue; the emitted batch, the pending payload and the
    emitted batch file are untouched."""
    session_dir, _g, _h, _key_f, key_g = _two_important(tmp_path, "c7-queued")
    before = _state(session_dir)
    before_file = _fix_batch_file_bytes(session_dir)
    out = _rule(session_dir, _write_ruling_file(tmp_path / "r.json", [
        {"id": key_g, "ruling": "out-of-scope", "reason": "later", "followUp": _follow_up()}]))
    assert out.get("ok") is True, out
    after = _state(session_dir)
    assert after["_fixBatch"] == before["_fixBatch"]
    assert after["pending"] == before["pending"]
    assert key_g not in _queue_keys(after) and not after.get("_fixQueue")
    assert _fix_batch_file_bytes(session_dir) == before_file


def test_t4_guidance_at_a_non_fixer_step_binds_the_next_batch(tmp_path, keep_severity):
    """axis: `guidance` is accepted at a step that is not the fixer step and the fix batch that holds
    its finding renders it."""
    for phase in (RD.P_VERIFIERS, RD.P_GAPSWEEP):
        sub = tmp_path / phase
        sub.mkdir()
        session_dir, gitdir, head_path = _session(
            sub, [_finding("bounds F", 1)], to_phase=phase, name="c7-nonfixer")
        key_f = _finding_key_by_title(_state(session_dir), "bounds F")
        out = _rule(session_dir, _guidance_file(sub, "g.json", key_f, "GUIDED-%s" % phase))
        assert out.get("ok") is True, (phase, out)
        assert _state(session_dir)["rulingsLog"][-1]["ruling"] == "guidance"
        _drive_to_phase(session_dir, gitdir, [], head_path, P_FIXER)
        state = _state(session_dir)
        assert key_f in _batch_keys(state), phase
        assert "GUIDED-%s" % phase in _order_text(session_dir)


def test_t4_guidance_at_an_audit_step_is_accepted(tmp_path, keep_severity):
    """axis: a pending step that is neither the fixer nor a finding step (the audits) takes guidance."""
    session_dir, _g, _h, key_f, _key_g = _two_important(tmp_path, "c7-audits")
    state = _state(session_dir)
    pend = {"action": RD.P_AUDITS, "round": state["round"], "phase": RD.P_AUDITS, "attempt": 0,
            "payload": {"targets": state.get("_auditTargets") or []}}
    state["pending"] = pend
    state["step"] = RD.P_AUDITS
    RD.save_state(session_dir, state)
    out = _rule(session_dir, _guidance_file(tmp_path, "g.json", key_f, "g at the audits"))
    assert out.get("ok") is True, out
    assert _state(session_dir)["rulingsLog"][-1]["findingKey"] == key_f


# --- R4: the lift --------------------------------------------------------------------------------

def _minors_session(tmp_path, name, **cfg):
    findings = [_finding("blocker B", 1),
                _finding("real minor one", 2, "Minor", "real"),
                _finding("real minor two", 3, "Minor", "real"),
                _finding("quality minor", 4, "Minor", "code-quality")]
    return _session(tmp_path, findings, name=name, **cfg)


def test_t5_undisposed_real_minors_ride_the_first_fixer_order(tmp_path, keep_severity):
    """axis: a round that sends a fixer out offers its undisposed real-consequence Minors in that same
    batch, after the blocker, each marked; a code-quality Minor is not lifted.

    bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo1b_c7_ruling_window.md (element 6)
    """
    session_dir, _g, _h = _minors_session(tmp_path, "c7-lift")
    state = _state(session_dir)
    assert state["pending"]["phase"] == P_FIXER
    by_title = _rows_by_title(state)
    assert [row["title"] for row in state["_fixBatch"]] == [
        "blocker B", "real minor one", "real minor two"]
    assert "quality minor" not in by_title
    assert "lifted" not in by_title["blocker B"]
    assert by_title["real minor one"]["lifted"] == "real-consequence"
    assert by_title["real minor two"]["lifted"] == "real-consequence"
    with open(os.path.join(RR.round_dir(session_dir, 1), "fix-batch.json"), encoding="utf-8") as fh:
        emitted = json.load(fh)
    assert [row["title"] for row in emitted] == ["blocker B", "real minor one", "real minor two"]
    assert [row.get("lifted") for row in emitted] == [None, "real-consequence", "real-consequence"]
    rec = state["rounds"]["1"]
    assert rec["liftedIntoFixBatch"] == [_key(by_title["real minor one"]),
                                         _key(by_title["real minor two"])]
    assert any(d["kind"] == "fix-batch-lifted" for d in state["decisions"])


def test_t5b_lifted_row_waits_for_a_later_slice_of_the_same_round(tmp_path, keep_severity):
    """axis: with `fixBatchCap` 1 the blocker goes first and the lifted Minor waits in `_fixQueue` for
    the next slice of the same round."""
    session_dir, gitdir, head_path = _session(
        tmp_path, [_finding("blocker B", 1), _finding("real minor", 2, "Minor", "real")],
        name="c7-cap", fixBatchCap=1)
    state = _state(session_dir)
    assert [row["title"] for row in state["_fixBatch"]] == ["blocker B"]
    assert [row["title"] for row in state["_fixQueue"]] == ["real minor"]
    assert state["_fixQueue"][0]["lifted"] == "real-consequence"
    rnd = state["round"]
    phase, out = _drive_one_phase(session_dir, gitdir, [], head_path)
    assert phase == P_FIXER and out.get("ok"), out
    after = _state(session_dir)
    assert after["round"] == rnd and after["pending"]["phase"] == P_FIXER
    assert [row["title"] for row in after["_fixBatch"]] == ["real minor"]
    assert after["_fixBatchIndex"] == 1 and not after.get("_fixQueue")


def test_t6_guidance_lifts_a_code_quality_minor(tmp_path, keep_severity):
    """axis: a code-quality Minor an effective guidance decision names rides the next batch marked
    `guidance`, and its guidance renders."""
    session_dir, gitdir, head_path = _session(
        tmp_path, [_finding("blocker B", 1), _finding("quality minor", 2, "Minor", "code-quality")],
        to_phase=RD.P_VERIFIERS, name="c7-guided-minor")
    key_m = _finding_key_by_title(_state(session_dir), "quality minor")
    assert _rule(session_dir, _guidance_file(tmp_path, "g.json", key_m, "TIDY-THE-MINOR"))["ok"]
    _drive_to_phase(session_dir, gitdir, [], head_path, P_FIXER)
    state = _state(session_dir)
    by_title = _rows_by_title(state)
    assert by_title["quality minor"]["lifted"] == "guidance"
    assert "lifted" not in by_title["blocker B"]
    assert "TIDY-THE-MINOR" in _order_text(session_dir)


def test_guidance_ruled_at_the_fixer_step_lifts_a_finding_the_batch_lacks(tmp_path, keep_severity):
    """axis: before the fixer order is emitted, a guidance ruling on a finding the batch does not hold
    brings it in through the same marker."""
    session_dir, _g, _h = _minors_session(tmp_path, "c7-reconcile")
    state = _state(session_dir)
    key_q = _finding_key_by_title(state, "quality minor")
    assert key_q not in _batch_keys(state)
    _strip_fixer_orders_emitted(session_dir)
    assert _rule(session_dir, _guidance_file(tmp_path, "g.json", key_q, "pull it in"))["ok"]
    after = _state(session_dir)
    assert _rows_by_title(after)["quality minor"]["lifted"] == "guidance"


def test_lift_marker_decision_table():
    """axis: which findings the lift selects — a product choice rides only on an owner decision."""
    real = {"consequenceKind": "real"}
    choice = {"consequenceKind": "real", "tradeoff": True}
    quality = {"consequenceKind": "code-quality"}
    live = lambda ruling: {"ruling": ruling}  # noqa: E731
    fixed = {"disposition": "fixed", "dispositionSeq": 5, "raisedSeq": 1}
    assert RD._lift_marker_for(real, {}, None) == "real-consequence"
    assert RD._lift_marker_for(quality, {}, None) is None
    assert RD._lift_marker_for(real, {}, live("out-of-scope")) is None
    assert RD._lift_marker_for(real, {"disposition": "out-of-scope"}, None) is None
    assert RD._lift_marker_for(real, fixed, None) is None
    assert RD._lift_marker_for(quality, {}, live("guidance")) == "guidance"
    assert RD._lift_marker_for(quality, {"disposition": "out-of-scope"}, live("guidance")) == "guidance"
    assert RD._lift_marker_for(quality, fixed, live("guidance")) is None
    assert RD._lift_marker_for(choice, {}, None) is None
    assert RD._lift_marker_for(choice, {}, live("out-of-scope")) is None
    assert RD._lift_marker_for(choice, {}, live("guidance")) == "guidance"
    assert RD._lift_marker_for(choice, {}, live("fix")) == "guidance"
    assert RD._lift_marker_for(choice, fixed, live("fix")) is None
    assert RD._lift_marker_for({"consequenceKind": "real", "tradeoff": None}, {}, None) \
        == "real-consequence"


# --- fail-closed edges ---------------------------------------------------------------------------

@pytest.mark.parametrize("case,token", [
    ("terminal", "withdraw-session-terminal"),
    ("not-fixer", "withdraw-not-fixer"),
    ("wrong-attempt", "withdraw-attempt-mismatch"),
    ("not-emitted", "withdraw-not-emitted"),
    ("blank-reason", "withdraw-reason-missing"),
])
def test_edge1_withdraw_refusals_leave_state_bytes_alone(tmp_path, keep_severity, case, token):
    if case == "not-fixer":
        session_dir, _g, _h = _bootstrap(tmp_path, name="c7-e1")
        attempt = _state(session_dir)["pending"]["attempt"]
        assert _state(session_dir)["pending"]["phase"] != P_FIXER
    else:
        session_dir, _g, _h, _f, _g2 = _two_important(tmp_path, "c7-e1")
        attempt = _state(session_dir)["pending"]["attempt"]
    reason = "a reason"
    if case == "terminal":
        state = _state(session_dir)
        state["terminal"] = "converged"
        RD.save_state(session_dir, state)
    elif case == "wrong-attempt":
        attempt += 1
    elif case == "not-emitted":
        _strip_fixer_orders_emitted(session_dir)
    elif case == "blank-reason":
        reason = "   "
    before = _state_bytes(session_dir)
    out = RD.cmd_withdraw(session_dir, attempt, reason)
    assert out.get("ok") is False and out.get("reason") == token, out
    assert _state_bytes(session_dir) == before
    assert _journal_refusals(session_dir, token)


@pytest.mark.parametrize("case,token", [
    ("tracked-change", "withdraw-worktree-dirty"),
    ("untracked-file", "withdraw-worktree-dirty"),
    ("head-moved", "withdraw-head-moved"),
    ("no-anchor-head", "withdraw-head-unanchored"),
    ("git-unavailable", "withdraw-git-unavailable"),
])
def test_edge2_restore_check_refusals(tmp_path, keep_severity, case, token):
    """axis: the worktree must be back at the attempt's starting head with nothing left over.

    bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo1b_c7_ruling_window.md (elements 1, 2)
    """
    session_dir, _g, _h, _f, _g2 = _two_important(tmp_path, "c7-e2")
    k = _state(session_dir)["pending"]["attempt"]
    repo, head = _throwaway_repo(tmp_path)
    _bind_anchor_head(session_dir, None if case == "no-anchor-head" else head, repo)
    kwargs = {"repo_root": str(repo)}
    if case == "tracked-change":
        (repo / "a.txt").write_text("changed by the stopped fixer\n", encoding="utf-8")
    elif case == "untracked-file":
        (repo / "stray.txt").write_text("left behind\n", encoding="utf-8")
    elif case == "head-moved":
        (repo / "a.txt").write_text("two\n", encoding="utf-8")
        _git(repo, "commit", "-q", "-a", "-m", "second")
    elif case == "git-unavailable":
        kwargs = {"repo_root": str(repo), "git": lambda cwd, *args: None}
    before = _state_bytes(session_dir)
    out = RD.cmd_withdraw(session_dir, k, "owner ruled", **kwargs)
    assert out.get("ok") is False and out.get("reason") == token, out
    assert _state_bytes(session_dir) == before
    assert _journal_refusals(session_dir, token)


def test_untracked_files_inside_the_session_directory_are_not_a_dirty_worktree(tmp_path):
    inside = tmp_path / "session"
    assert RD._untracked_outside_session(str(inside), str(tmp_path), "?? session/round-1/x") is False
    assert RD._untracked_outside_session(str(inside), str(tmp_path), "?? other/x") is True
    assert RD._untracked_outside_session(str(inside), None, "?? session/x") is True


def test_library_withdraw_without_a_repo_records_not_checked(tmp_path, keep_severity):
    session_dir, _g, _h, _f, _g2 = _two_important(tmp_path, "c7-nc")
    k = _state(session_dir)["pending"]["attempt"]
    out = RD.cmd_withdraw(session_dir, k, "owner ruled")
    assert out.get("ok") is True and out["restoreCheck"] == "not-checked", out
    assert _state(session_dir)["withdrawnFixerAttempts"][0]["restoreCheck"] == "not-checked"


def test_withdraw_verb_runs_through_the_command_line(tmp_path, keep_severity, capsys):
    session_dir, _g, _h, _f, _g2 = _two_important(tmp_path, "c7-cli")
    k = _state(session_dir)["pending"]["attempt"]
    repo, head = _throwaway_repo(tmp_path)
    _bind_anchor_head(session_dir, head, repo)
    capsys.readouterr()
    code = RD.main(["withdraw", "--session-dir", session_dir, "--attempt", str(k),
                    "--reason", "owner ruled", "--repo-root", str(repo)])
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert code == 0 and out["ok"] is True and out["restoreCheck"] == "checked", out
    (repo / "a.txt").write_text("dirty\n", encoding="utf-8")
    code = RD.main(["withdraw", "--session-dir", session_dir, "--attempt", str(k + 1),
                    "--reason", "again", "--repo-root", str(repo)])
    assert code == 1


def test_edge3_fold_paths_refuse_a_withdrawn_attempt(tmp_path, keep_severity):
    """axis: submit, record-result and record-missing addressed to a withdrawn fixer attempt name the
    withdrawal, and leave the state alone."""
    session_dir, _g, _h, _f, _g2 = _two_important(tmp_path, "c7-e3")
    state = _state(session_dir)
    k = state["pending"]["attempt"]
    roster, _ = round_adapters.roster_for(P_FIXER, state, state.get("config") or {})
    seat = RR.roster_slots(roster)[0][0]
    assert RD.cmd_withdraw(session_dir, k, "owner ruled")["ok"]
    before = _state_bytes(session_dir)
    for out in (RD.cmd_submit(session_dir, P_FIXER, k, "h", {"fixes": []}),
                RD.cmd_record_result(session_dir, seat, attempt=k),
                RD.cmd_record_missing(session_dir, seat, k, "no-output")):
        assert out.get("ok") is False and out.get("reason") == "fixer-attempt-withdrawn", out
    assert _state_bytes(session_dir) == before
    assert len(_journal_refusals(session_dir, "fixer-attempt-withdrawn")) == 3


def test_edge4_fresh_attempt_is_above_the_withdrawn_one(tmp_path, keep_severity):
    """axis: the attempt allocated after a withdrawal is strictly greater, its orders are emitted at
    that attempt, and the withdrawn attempt's order files stay on disk untouched.

    bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo1b_c7_ruling_window.md (element 4)
    """
    session_dir, _g, _h, _f, _g2 = _two_important(tmp_path, "c7-e4")
    state = _state(session_dir)
    k = state["pending"]["attempt"]
    old_order = _order_path(session_dir, state)
    manifest = RD._orders_manifest_path(session_dir, state["round"], P_FIXER, k)
    with open(old_order, "rb") as fh:
        old_order_bytes = fh.read()
    with open(manifest, "rb") as fh:
        old_manifest_bytes = fh.read()
    assert RD.cmd_withdraw(session_dir, k, "owner ruled")["ok"]
    assert RD._next_dispatch_attempt(session_dir, state["round"], P_FIXER, _state(session_dir)) > k
    nxt = RD.cmd_next(session_dir)
    assert nxt.get("ok") and nxt["attempt"] > k, nxt
    assert RD._journal_has_orders_emitted(session_dir, state["round"], P_FIXER, nxt["attempt"])
    with open(old_order, "rb") as fh:
        assert fh.read() == old_order_bytes
    with open(manifest, "rb") as fh:
        assert fh.read() == old_manifest_bytes
    assert _order_path(session_dir, _state(session_dir)) != old_order


def test_a_landing_left_at_the_withdrawn_attempt_is_not_folded(tmp_path, keep_severity):
    """axis: `advance` folds only the fresh attempt; a seat result landed at the withdrawn attempt's
    path is never stored or folded."""
    session_dir, gitdir, head_path, _f, _g = _two_important(tmp_path, "c7-stale")
    state = _state(session_dir)
    k = state["pending"]["attempt"]
    pend_k = state["pending"]
    roster, _ = round_adapters.roster_for(P_FIXER, state, state.get("config") or {})
    seat, occurrence = RR.roster_slots(roster)[0]
    _TRI._write_dispatch_manifest(session_dir, pend_k, _TRI._slots_of(roster),
                                  _TRI._auditor_vendor_for(state))
    payload = _TRI._payload_for(session_dir, state, pend_k, seat, [], head_path)
    _TRI._land(session_dir, state, pend_k, seat, payload, occurrence=occurrence)
    assert RD.cmd_withdraw(session_dir, k, "owner ruled")["ok"]
    assert RD.cmd_next(session_dir)["ok"]
    fresh = _state(session_dir)["pending"]["attempt"]
    assert fresh > k
    phase, out = _drive_one_phase(session_dir, gitdir, [], head_path)
    assert phase == P_FIXER and out.get("ok"), out
    stale_store = RR.store_path(session_dir, 1, P_FIXER, RR.storage_key(seat, occurrence), k)
    assert not os.path.exists(stale_store)
    assert _state(session_dir)["lastAccepted"]["attempt"] == fresh


def test_edge5_mixed_ruling_file_refuses_whole(tmp_path, keep_severity):
    """axis: a ruling file naming one finding in the emitted batch and one outside it is refused
    whole; nothing is recorded."""
    session_dir, _g, _h, key_f, key_g = _two_important(tmp_path, "c7-e5")
    before = _state_bytes(session_dir)
    out = _rule(session_dir, _write_ruling_file(tmp_path / "mixed.json", [
        {"id": key_g, "ruling": "guidance", "reason": "outside", "guidance": "for G"},
        {"id": key_f, "ruling": "guidance", "reason": "inside", "guidance": "for F"}]))
    assert out.get("ok") is False and out.get("reason") == "ruling-attempt-pending", out
    assert _state_bytes(session_dir) == before


def test_edge6_out_of_scope_and_fixed_findings_are_never_lifted(tmp_path, keep_severity):
    """axis: a real-consequence finding that is effectively out of scope, or already fixed, is not
    lifted; an undisposed one beside them still is."""
    session_dir, _g, _h = _session(
        tmp_path,
        [_finding("blocker B", 1), _finding("minor ruled out", 2, "Minor", "real"),
         _finding("minor fixed", 3, "Minor", "real"), _finding("minor open", 4, "Minor", "real")],
        name="c7-e6")
    state = _state(session_dir)
    keys = {title: _finding_key_by_title(state, title)
            for title in ("blocker B", "minor ruled out", "minor fixed", "minor open")}
    assert set(_batch_keys(state)) == set(keys.values())
    state["pending"] = None
    RD.save_state(session_dir, state)
    assert _rule(session_dir, _write_ruling_file(tmp_path / "oos.json", [
        {"id": keys["minor ruled out"], "ruling": "out-of-scope", "reason": "later",
         "followUp": _follow_up()}]))["ok"]
    state = _state(session_dir)
    RD._record_disposition(state, keys["minor fixed"], "fixed", state["round"])
    blocker = next(row for row in state["findings"] if _key(row) == keys["blocker B"])
    status = RD._queue_fix_batch(state, state["config"], [dict(blocker)])
    assert status == "queued"
    queued = _batch_keys(state) + _queue_keys(state)
    assert queued == [keys["blocker B"], keys["minor open"]]
    assert state["rounds"]["1"]["liftedIntoFixBatch"] == [keys["minor open"]]


def test_edge7_a_round_with_no_offered_rows_lifts_nothing(tmp_path, keep_severity):
    """axis: an autonomous lift never starts a fixer leg. A Minor-only round converges with no fixer
    leg, and an empty offered set lifts nothing (and records no exclusion) though real-consequence
    findings are live."""
    minor_only = tmp_path / "minor-only"
    minor_only.mkdir()
    session_dir, gitdir, head_path = _bootstrap(minor_only, name="c7-e7")
    folded = _TRI._drive_to_terminal(
        session_dir, gitdir, [_finding("only minor", 1, "Minor", "real")], head_path)
    assert P_FIXER not in folded, folded
    final = _state(session_dir)
    assert final.get("terminal") == "converged"
    assert "liftedIntoFixBatch" not in final["rounds"]["1"]

    session_dir, _g, _h = _minors_session(tmp_path, "c7-e7-direct")
    state = _state(session_dir)
    assert any(f.get("consequenceKind") == "real" for f in state["findings"])
    state["pending"] = None
    state["rounds"]["1"].pop("liftedIntoFixBatch", None)
    before = (state.get("_fixBatch"), state.get("_fixQueue"), state.get("step"))
    assert RD._queue_fix_batch(state, state["config"], []) == "empty"
    assert (state.get("_fixBatch"), state.get("_fixQueue"), state.get("step")) == before
    assert "liftedIntoFixBatch" not in state["rounds"]["1"]
    assert "fixBatchExcludedByDischarge" not in state["rounds"]["1"]


# --- review round 1: a lifted product choice, a lifted non-blocking audit, an emitted-time guidance

def _choice(title, line):
    finding = _finding(title, line, "Minor", "real")
    finding["tradeoff"] = True
    return finding


def _judgment_ids(state):
    return [row["id"] for row in state["pending"]["payload"]["findings"]]


def _fold_judgment(tmp_path, session_dir, gitdir, dispositions):
    path = tmp_path / "judgment.json"
    path.write_text(json.dumps({"dispositions": dispositions}), encoding="utf-8")
    return RD.cmd_advance(session_dir, git=_RC._fake_git(gitdir), owner_artifact_path=str(path))


def _gate_blocker(title, line):
    finding = _finding(title, line)
    finding["tradeoff"] = True
    return finding


def test_an_undecided_product_choice_is_not_lifted_beside_a_blocker(tmp_path, keep_severity):
    """axis: I1 — an undecided real-consequence Minor product choice never rides the blocker's batch."""
    session_dir, _g, _h = _session(
        tmp_path, [_finding("blocker B", 1), _choice("minor choice", 2)], name="c7-choice")
    state = _state(session_dir)
    assert [row["title"] for row in state["_fixBatch"]] == ["blocker B"]
    assert not state.get("_fixQueue")
    assert not state.get("_judgmentFindings") and not state.get("_judgmentMechanical")
    assert "liftedIntoFixBatch" not in state["rounds"]["1"]


def test_t_ii_a_guided_choice_rides_the_batch_beside_a_blocker(tmp_path, keep_severity):
    """axis: I1(b) — a product choice a `rule` guidance decision names joins the blocker's batch."""
    session_dir, gitdir, head_path = _session(
        tmp_path, [_finding("blocker B", 1), _choice("minor choice", 2)],
        to_phase=RD.P_VERIFIERS, name="c7-choice-guided")
    key_m = _finding_key_by_title(_state(session_dir), "minor choice")
    assert _rule(session_dir, _guidance_file(tmp_path, "g.json", key_m, "DO-THE-CHOICE"))["ok"]
    _drive_to_phase(session_dir, gitdir, [], head_path, P_FIXER)
    by_title = _rows_by_title(_state(session_dir))
    assert set(by_title) == {"blocker B", "minor choice"}
    assert by_title["minor choice"]["lifted"] == "guidance"
    assert "DO-THE-CHOICE" in _order_text(session_dir)


def test_t_ii_b_a_guided_choice_survives_the_only_blocker_ruled_out_at_the_fixer(
        tmp_path, keep_severity):
    """axis: I1(b) — with the only blocker ruled out at the fixer step, the guided choice still gets
    a fixer leg and the round does not converge past it."""
    session_dir, _g, _h = _session(
        tmp_path, [_finding("blocker B", 1), _choice("minor choice", 2)], name="c7-choice-b-oos")
    state = _state(session_dir)
    assert [row["title"] for row in state["_fixBatch"]] == ["blocker B"]
    key_b = _finding_key_by_title(state, "blocker B")
    key_m = _finding_key_by_title(state, "minor choice")
    _strip_fixer_orders_emitted(session_dir)
    out = _rule(session_dir, _write_ruling_file(tmp_path / "mixed.json", [
        {"id": key_b, "ruling": "out-of-scope", "reason": "not this change",
         "followUp": _follow_up()},
        {"id": key_m, "ruling": "guidance", "reason": "owner call", "guidance": "do the choice"}]))
    assert out.get("ok") is True, out
    after = _state(session_dir)
    assert after.get("terminal") != "converged"
    assert after["step"] == P_FIXER
    assert [row["title"] for row in after["_fixBatch"]] == ["minor choice"]


def _unit_finding(key, line, severity, *, tradeoff=False, kind="real"):
    return dict(findingKey=key, title=key, file="a.py", line=line, severity=severity,
                tradeoff=tradeoff, consequenceKind=kind)


def _unit_round(findings):
    """A state with ``findings`` routed through the driver's own settle entry point."""
    state = RD.new_state()
    RD._set_findings(state, [dict(f) for f in findings])
    RD._after_findings_settled(state, state["config"])
    return state


def _unit_rulings(state, *rows):
    state.update(rulingSeqCounter=len(rows),
                 rulingsLog=[dict(row, seq=i) for i, row in enumerate(rows, 1)])


def _unit_batch(state):
    return [row["findingKey"] for row in state.get("_fixBatch") or []]


def _unit_gate_ids(state):
    return RD._judgment_row_ids(state["_judgmentFindings"])


@pytest.mark.parametrize("blocker_is_tradeoff", [False, True], ids=["mechanical", "gate-blocker"])
def test_t_i_an_undecided_product_choice_is_left_for_the_owner(blocker_is_tradeoff):
    """axis: I1/I2 — an undecided below-blocking product choice never enters the owner gate or a fix
    batch, and the end-of-loop settle leaves it for the owner."""
    state = _unit_round([_unit_finding("B", 1, "Important", tradeoff=blocker_is_tradeoff),
                         _unit_finding("M", 2, "Minor", tradeoff=True)])
    if blocker_is_tradeoff:
        assert state["step"] == RD.P_JUDGMENT
        assert [r["findingKey"] for r in state["_judgmentFindings"]] == ["B"]
        assert state["_judgmentMechanical"] == []
        RD._fold_judgment(state, state["config"], {"dispositions": [
            {"id": _unit_gate_ids(state)[0], "disposition": "fix-as-suggested"}]})
    assert state["step"] == P_FIXER
    assert _unit_batch(state) == ["B"] and not state.get("_fixQueue")
    assert not state.get("_judgmentFindings") and not state.get("_judgmentMechanical")
    RD._set_terminal(state, "converged")
    ledger, fault = RD._disposition_ledger_by_key(state)
    assert fault is None
    assert ledger["M"]["disposition"] == "left-for-owner", ledger["M"]


def test_t_ii_c_a_guided_choice_survives_skipping_the_only_gate_blocker():
    """axis: I1(b)/I3 — with the gate's only blocker skipped, a guided product choice still reaches
    the fixer through the chokepoint."""
    state = _unit_round([_unit_finding("J", 1, "Important", tradeoff=True),
                         _unit_finding("M", 2, "Minor", tradeoff=True)])
    assert [r["findingKey"] for r in state["_judgmentFindings"]] == ["J"]
    _unit_rulings(state, dict(findingKey="M", ruling="guidance", guidance="apply it"))
    RD._fold_judgment(state, state["config"], {"dispositions": [
        {"id": _unit_gate_ids(state)[0], "disposition": "skip", "reason": "keep current"}]})
    assert state["step"] == P_FIXER
    assert _unit_batch(state) == ["M"]
    assert not state.get("terminal")


def test_an_undecided_choice_does_not_survive_skipping_the_only_gate_blocker():
    """axis: I1/E4 — with the gate's only blocker skipped and nothing owner-named, the round settles
    as it always did, with no exclusion counted and no fix batch."""
    state = _unit_round([_unit_finding("J", 1, "Important", tradeoff=True),
                         _unit_finding("M", 2, "Minor", tradeoff=True)])
    RD._fold_judgment(state, state["config"], {"dispositions": [
        {"id": _unit_gate_ids(state)[0], "disposition": "skip", "reason": "keep current"}]})
    assert state.get("terminal") == "converged"
    assert state["step"] != P_FIXER and not state.get("_fixBatch")
    assert "fixBatchExcludedByDischarge" not in state["rounds"]["1"]
    assert "liftedIntoFixBatch" not in state["rounds"]["1"]


@pytest.mark.parametrize("target,other", [("Q", "M"), ("M", "Q")], ids=["quality", "choice"])
def test_t_iii_the_fixer_receives_only_the_owner_named_minor(target, other):
    """axis: I1/I2/I3 — with the mechanical blocker ruled out and the gate's blocker skipped, the
    fixer batch holds the one Minor an owner decision names and never the other."""
    state = _unit_round([
        _unit_finding("B", 1, "Important"),
        _unit_finding("J", 2, "Important", tradeoff=True),
        _unit_finding("M", 3, "Minor", tradeoff=True),
        _unit_finding("Q", 4, "Minor", kind="code-quality")])
    assert [r["findingKey"] for r in state["_judgmentFindings"]] == ["J"]
    assert [r["findingKey"] for r in state["_judgmentMechanical"]] == ["B"]
    _unit_rulings(state, dict(findingKey="B", ruling="out-of-scope"),
                  dict(findingKey=target, ruling="guidance", guidance="apply it"))
    RD._reconcile_fixer_queue_after_rulings(state, state["config"])
    RD._fold_judgment(state, state["config"], {"dispositions": [
        {"id": _unit_gate_ids(state)[0], "disposition": "skip", "reason": "keep current"}]})
    assert state["step"] == P_FIXER
    assert _unit_batch(state) == [target]
    assert other not in _unit_batch(state) + [r["findingKey"] for r in state.get("_fixQueue") or []]


def test_guidance_at_the_judgment_gate_survives_skipping_the_last_blocker(tmp_path, keep_severity):
    """axis: I1(b)/I3 — guidance ruled on a code-quality Minor while the owner gate is open still
    reaches a fixer when the owner then skips the gate's only blocker."""
    blocker = _finding("tradeoff blocker", 1)
    blocker["tradeoff"] = True
    session_dir, gitdir, _h = _session(
        tmp_path, [blocker, _finding("quality minor", 2, "Minor", "code-quality")],
        to_phase=RD.P_JUDGMENT, name="c7-judgment-guidance-skip")
    state = _state(session_dir)
    key_m = _finding_key_by_title(state, "quality minor")
    assert _rule(session_dir, _guidance_file(tmp_path, "g.json", key_m, "TIDY-THE-MINOR"))["ok"]
    [jid] = _judgment_ids(_state(session_dir))
    out = _fold_judgment(tmp_path, session_dir, gitdir,
                         [{"id": jid, "disposition": "skip", "reason": "keep the current shape"}])
    assert out.get("ok") is True, out
    after = _state(session_dir)
    assert after["pending"]["phase"] == P_FIXER
    assert [row["title"] for row in after["_fixBatch"]] == ["quality minor"]
    assert "TIDY-THE-MINOR" in _order_text(session_dir)


def test_a_not_discharged_lifted_minor_never_keeps_the_loop_fixing(tmp_path, keep_severity):
    """axis: the blocker is discharged and the lifted Minor is not — the Minor is held out of
    `notDischarged` and out of the stall breaker's audit round, so it neither restarts the fixer nor
    parks the round."""
    session_dir, gitdir, _h = _session(
        tmp_path, [_finding("blocker B", 1), _finding("real minor", 2, "Minor", "real")],
        to_phase=RD.P_AUDITS, name="c7-audit-minor")
    state = _state(session_dir)
    by_title = {t["title"]: t for t in state["_auditTargets"]}
    tid_b, tid_m = by_title["blocker B"]["id"], by_title["real minor"]["id"]
    pend = state["pending"]
    _TRI._write_dispatch_manifest(session_dir, pend, [(tid_b, 0), (tid_m, 0)],
                                  _TRI._auditor_vendor_for(state))
    _TRI._land(session_dir, state, pend, tid_b,
               {"id": tid_b, "ruling": "discharged", "reason": "re-read the hunk; it is gone"})
    assert _TRI._record(session_dir, tid_b)["ok"] is True
    _TRI._land(session_dir, state, pend, tid_m,
               {"id": tid_m, "ruling": "not-discharged", "reason": "the minor is still there"})
    assert _TRI._record(session_dir, tid_m)["ok"] is True
    out = RD.cmd_advance(session_dir, git=_RC._fake_git(gitdir))
    assert out.get("ok") is True, out
    after = _state(session_dir)
    outcome = after["_auditOutcome"]
    assert outcome["notDischarged"] == [], outcome
    assert outcome["notDischargedNonBlocking"] == [tid_m], outcome
    assert [o["title"] for o in after["auditRounds"][-1]["outcomes"]] == ["blocker B"]
    assert any(d["kind"] == "not-discharged-nonblocking" for d in after["decisions"])
    assert after.get("step") != P_FIXER and after.get("terminal") != "capped-with-open-blocker"


def test_guidance_reopening_a_queued_skip_during_an_emitted_attempt_requeues_it(
        tmp_path, keep_severity):
    """axis: with F emitted and G queued, an out-of-scope ruling drops G from the queue; replacement
    guidance on G puts it back in the queue — the emitted batch and pending step are untouched."""
    session_dir, _g, _h, _key_f, key_g = _two_important(tmp_path, "c7-requeue")
    before = _state(session_dir)
    before_file = _fix_batch_file_bytes(session_dir)
    assert _rule(session_dir, _write_ruling_file(tmp_path / "oos.json", [
        {"id": key_g, "ruling": "out-of-scope", "reason": "later", "followUp": _follow_up()}]))["ok"]
    assert key_g not in _queue_keys(_state(session_dir))
    out = _rule(session_dir, _guidance_file(tmp_path, "g.json", key_g, "fix G now"))
    assert out.get("ok") is True, out
    after = _state(session_dir)
    assert _queue_keys(after) == [key_g]
    assert after["_fixBatch"] == before["_fixBatch"]
    assert after["pending"] == before["pending"]
    assert _fix_batch_file_bytes(session_dir) == before_file


def test_guidance_on_an_unqueued_minor_during_an_emitted_attempt_joins_the_queue(
        tmp_path, keep_severity):
    """axis: guidance naming a code-quality Minor neither slice holds, given while an attempt is
    emitted, queues it for a later slice of the round."""
    session_dir, _g, _h = _session(
        tmp_path, [_finding("bounds F", 1), _finding("quality minor", 3, "Minor", "code-quality")],
        name="c7-emitted-minor", fixBatchCap=1)
    state = _state(session_dir)
    key_m = _finding_key_by_title(state, "quality minor")
    assert key_m not in _batch_keys(state) + _queue_keys(state)
    out = _rule(session_dir, _guidance_file(tmp_path, "g.json", key_m, "TIDY-IT"))
    assert out.get("ok") is True, out
    after = _state(session_dir)
    assert _queue_keys(after) == [key_m]
    assert after["_fixQueue"][0]["lifted"] == "guidance"
    assert after["pending"] == state["pending"]


# --- review round 1: worktree binding, ledger-only guidance targets, merged members, eligible blockers

def test_withdraw_refuses_a_worktree_other_than_the_sessions(tmp_path, keep_severity):
    """axis: the restore check reads the session's own worktree — a clean sibling at the same head
    never stands in for the dirty one."""
    session_dir, _g, _h, _f, _g2 = _two_important(tmp_path, "c7-wrong-wt")
    k = _state(session_dir)["pending"]["attempt"]
    repo, head = _throwaway_repo(tmp_path)
    other, _other_head = _throwaway_repo(tmp_path, "other")
    _bind_anchor_head(session_dir, head, repo)
    before = _state_bytes(session_dir)
    out = RD.cmd_withdraw(session_dir, k, "owner ruled", repo_root=str(other))
    assert out.get("ok") is False and out.get("reason") == "withdraw-wrong-worktree", out
    assert _state_bytes(session_dir) == before
    assert RD.cmd_withdraw(session_dir, k, "owner ruled", repo_root=str(repo))["ok"] is True


def test_a_merged_member_is_never_lifted_by_guidance():
    """axis: a finding synthesis merged into another carries `mergedInto` and never rides a batch."""
    merged = session_contract.MERGED_INTO_FIELD
    guidance = {"ruling": "guidance"}
    assert RD._lift_marker_for({"title": "t"}, {}, guidance) == RD.LIFT_GUIDANCE
    assert RD._lift_marker_for({merged: "rep"}, {}, guidance) is None
    assert RD._lift_marker_for({}, {merged: "rep"}, guidance) is None
    assert RD._lift_marker_for({merged: "rep", "consequenceKind": "real"}, {}, None) is None


def test_guidance_on_an_archived_finding_still_rides_the_next_batch(tmp_path, keep_severity):
    """axis: guidance on an unresolved Minor that scoped synthesis archived to the ledger is
    recovered when the next batch is composed for another blocker."""
    session_dir, _g, _h = _minors_session(tmp_path, "c7-archived")
    state = _state(session_dir)
    quality = _finding_key_by_title(state, "quality minor")
    blocker = next(dict(f) for f in state["findings"] if f.get("title") == "blocker B")
    state["pending"] = None
    RD.save_state(session_dir, state)
    assert _rule(session_dir, _guidance_file(tmp_path, "g.json", quality, "tidy the names"))["ok"]
    state = _state(session_dir)
    RD._set_findings(state, [blocker])
    assert RD._live_finding_by_key(state, quality) is None
    lifted = RD._lifted_fix_rows(state, [blocker])
    assert [(_key(row), row["lifted"]) for row in lifted] == [(quality, RD.LIFT_GUIDANCE)]


def test_stall_recovery_batch_takes_no_lifted_rows_and_merged_members_never_lift(tmp_path, keep_severity):
    """axis: the stall-recovery batch is exactly its composed set; a synthesis-merged member is
    never lifted as an independent fix."""
    session_dir, _g, _h = _minors_session(tmp_path, "c7-stall-nolift")
    state = _state(session_dir)
    assert any(f.get("consequenceKind") == "real" for f in state["findings"])
    state["pending"] = None
    state["rounds"]["1"].pop("liftedIntoFixBatch", None)
    stalled = {"id": "stalled", "severity": "Important", "file": "a.py", "line": 1,
               "title": "stalled target", "body": "b"}
    assert RD._queue_fix_batch(state, state["config"], [dict(stalled)], lift=False) == "queued"
    assert [r.get("id") for r in state["_fixBatch"]] == ["stalled"]
    assert "liftedIntoFixBatch" not in state["rounds"]["1"]
    real = {"consequenceKind": "real"}
    assert RD._lift_marker_for(real, {}, None) == "real-consequence"
    merged = {"consequenceKind": "real", session_contract.MERGED_INTO_FIELD: "rep"}
    assert RD._lift_marker_for(merged, {}, {"ruling": "guidance"}) is None
    assert RD._lift_marker_for(real, {session_contract.MERGED_INTO_FIELD: "rep"},
                               {"ruling": "guidance"}) is None


def test_stall_recovery_batch_keeps_no_lift_through_the_owner_judgment_gate(monkeypatch):
    """axis: a stall batch routed through owner judgment folds into a fix batch without lifting."""
    tradeoff = {"title": "widen the API", "severity": "Important", "file": "j.py", "line": 3,
                "tradeoff": True}
    state = RD.new_state({"leg": "code", "vendors": ["claude", "codex"], "diff": "d",
                          "fixerVendor": "claude"})
    seen = []
    monkeypatch.setattr(RD, "_queue_fix_batch",
                        lambda st, cfg, rows, **kw: seen.append(kw.get("lift", True)))
    RD._route_stall_self_recovery(state, state["config"], [dict(tradeoff)], None, {})
    assert seen == []
    fid = RD._judgment_row_ids(state["_judgmentFindings"])[0]
    RD._fold_judgment(state, state["config"], {"dispositions": [
        {"id": fid, "disposition": "fix"}]})
    assert seen and set(seen) == {False}


def test_ruling_the_gates_blockers_out_clears_the_gate_and_converges(tmp_path, keep_severity):
    """axis: I2/I3 — the gate holds one mechanical and one tradeoff blocker; ruling both out leaves
    nothing to put to the owner, so the gate closes and the loop converges without asking about the
    Minor product choice."""
    session_dir, _g, _h = _session(
        tmp_path, [_finding("blocker B", 1), _gate_blocker("tradeoff J", 2),
                   _choice("minor choice", 3)],
        to_phase=RD.P_JUDGMENT, name="c7-choice-oos")
    state = _state(session_dir)
    assert [row["title"] for row in state["_judgmentFindings"]] == ["tradeoff J"]
    out = _rule(session_dir, _write_ruling_file(tmp_path / "oos.json", [
        {"id": _finding_key_by_title(state, title), "ruling": "out-of-scope",
         "reason": "not this change", "followUp": _follow_up()}
        for title in ("blocker B", "tradeoff J")]))
    assert out.get("ok") is True, out
    after = _state(session_dir)
    assert after.get("terminal") == "converged", after.get("step")
    assert not after.get("_judgmentFindings") and not after.get("_judgmentMechanical")
    assert not after.get("pending")


def test_guidance_on_the_choice_with_the_gate_blockers_out_keeps_it_for_the_fixer(
        tmp_path, keep_severity):
    """axis: I1(b)/I3 — one ruling file rules the gate's blockers out and gives a Minor product choice
    guidance: the gate closes through the chokepoint and the guided choice reaches the fixer."""
    session_dir, _g, _h = _session(
        tmp_path, [_finding("blocker B", 1), _gate_blocker("tradeoff J", 2),
                   _choice("minor choice", 3)],
        to_phase=RD.P_JUDGMENT, name="c7-choice-guided-oos")
    state = _state(session_dir)
    entries = [{"id": _finding_key_by_title(state, title), "ruling": "out-of-scope",
                "reason": "not this change", "followUp": _follow_up()}
               for title in ("blocker B", "tradeoff J")]
    entries.append({"id": _finding_key_by_title(state, "minor choice"), "ruling": "guidance",
                    "reason": "owner call", "guidance": "do the choice"})
    out = _rule(session_dir, _write_ruling_file(tmp_path / "mixed.json", entries))
    assert out.get("ok") is True, out
    after = _state(session_dir)
    assert after.get("terminal") != "converged"
    assert [row["title"] for row in after["_fixBatch"]] == ["minor choice"]


def test_guidance_on_one_choice_keeps_an_undecided_choice_out_of_the_fixer(
        tmp_path, keep_severity):
    """axis: I1 — the gate's blockers are ruled out and only one of two Minor product choices gets
    guidance, so the undecided one never reaches the fixer."""
    session_dir, _g, _h = _session(
        tmp_path, [_finding("blocker B", 1), _gate_blocker("tradeoff J", 2),
                   _choice("choice M", 3), _choice("choice N", 4)],
        to_phase=RD.P_JUDGMENT, name="c7-choice-mn")
    state = _state(session_dir)
    entries = [{"id": _finding_key_by_title(state, title), "ruling": "out-of-scope",
                "reason": "not this change", "followUp": _follow_up()}
               for title in ("blocker B", "tradeoff J")]
    entries.append({"id": _finding_key_by_title(state, "choice M"), "ruling": "guidance",
                    "reason": "owner call", "guidance": "do the choice"})
    out = _rule(session_dir, _write_ruling_file(tmp_path / "mn.json", entries))
    assert out.get("ok") is True, out
    after = _state(session_dir)
    rows = _rows_by_title(after)
    assert "choice M" in rows
    assert "choice N" not in rows
    assert "choice N" in [f.get("title") for f in after.get("findings") or []]
    key_n = _finding_key_by_title(after, "choice N")
    assert key_n not in [r.get("findingKey") for r in after.get("rulingsLog") or []]


def test_ruling_a_withdrawn_batchs_only_blocker_out_drops_its_lifted_minor(tmp_path, keep_severity):
    """axis: a withdrawn fixer batch holds one Important blocker and a lifted real-consequence Minor;
    ruling the blocker out of scope leaves no eligible blocker, so the lifted Minor does not go out
    alone and the loop converges."""
    session_dir, _g, _h = _minors_session(tmp_path, "c7-withdrawn-oos")
    state = _state(session_dir)
    assert [r["title"] for r in state["_fixBatch"]][0] == "blocker B"
    out = RD.cmd_withdraw(session_dir, state["pending"]["attempt"], "rule the blocker out")
    assert out.get("ok") is True, out
    key = _finding_key_by_title(_state(session_dir), "blocker B")
    out = _rule(session_dir, _write_ruling_file(tmp_path / "oos.json", [
        {"id": key, "ruling": "out-of-scope", "reason": "not this change",
         "followUp": _follow_up()}]))
    assert out.get("ok") is True, out
    after = _state(session_dir)
    assert after.get("terminal") == "converged", (after.get("step"), after.get("_fixBatch"))


def _lifted_minor_state(decision_rows=None, gate=None):
    state = RD.new_state()
    state["rulingsLog"] = decision_rows or []
    if gate:
        state["rounds"] = {"1": {"judgmentDispositions": gate}}
    return state, dict(findingKey="m", severity="Minor", lifted="real-consequence")


def test_a_lifted_minor_with_guidance_stays_when_it_is_the_only_row():
    state, row = _lifted_minor_state([dict(findingKey="m", ruling="guidance", guidance="fix it", seq=1)])
    assert RD._queue_fix_batch(state, state["config"], [row]) == "queued"
    assert state.get("terminal") != "converged"


def test_a_lifted_minor_the_owner_approved_to_fix_stays_when_it_is_the_only_row():
    state, row = _lifted_minor_state(gate=[dict(findingKey="m", disposition="fix-as-suggested", rulingSeq=1)])
    assert RD._queue_fix_batch(state, state["config"], [row]) == "queued"
    assert state.get("terminal") != "converged"


def test_an_autonomous_lifted_minor_alone_still_converges():
    state, row = _lifted_minor_state()
    assert RD._queue_fix_batch(state, state["config"], [row]) == "excluded"
    assert state.get("terminal") == "converged"


def test_guidance_survives_skipping_the_gate_when_a_ruled_out_blocker_is_carried(
        tmp_path, keep_severity):
    """axis: I1(b)/I3 — a ruled-out mechanical blocker still carried by the gate does not hide
    accepted guidance on a Minor from the fixer when the owner then skips the gate's tradeoff
    blocker."""
    tradeoff = _finding("tradeoff blocker", 2)
    tradeoff["tradeoff"] = True
    session_dir, gitdir, _h = _session(
        tmp_path, [_finding("blocker B", 1), tradeoff,
                   _finding("quality minor", 3, "Minor", "code-quality")],
        to_phase=RD.P_JUDGMENT, name="c7-carried-oos")
    state = _state(session_dir)
    assert _rule(session_dir, _write_ruling_file(tmp_path / "oos-b.json", [
        {"id": _finding_key_by_title(state, "blocker B"), "ruling": "out-of-scope",
         "reason": "later", "followUp": _follow_up()}]))["ok"]
    key_m = _finding_key_by_title(state, "quality minor")
    assert _rule(session_dir, _guidance_file(tmp_path, "g.json", key_m, "TIDY-THE-MINOR"))["ok"]
    [jid] = _judgment_ids(_state(session_dir))
    out = _fold_judgment(tmp_path, session_dir, gitdir,
                         [{"id": jid, "disposition": "skip", "reason": "keep the current shape"}])
    assert out.get("ok") is True, out
    after = _state(session_dir)
    assert after["pending"]["phase"] == P_FIXER
    assert [row["title"] for row in after["_fixBatch"]] == ["quality minor"]


def test_an_untracked_symlink_outside_the_session_is_dirty_whatever_it_points_at(tmp_path):
    """axis: containment is judged by where the entry sits, not by where a symlink leads."""
    session = tmp_path / "session"
    session.mkdir()
    (session / "scratch.py").write_text("x", encoding="utf-8")
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    os.symlink(str(session / "scratch.py"), str(repo / "src" / "helper.py"))
    assert RD._untracked_outside_session(str(session), str(repo), "?? src/helper.py") is True


def test_an_empty_disposition_fixes_the_gate_blocker_and_never_a_product_choice(
        tmp_path, keep_severity):
    """axis: E5/I1 — a gate blocker with no disposition folds as fix-as-suggested (fail closed) and
    an undecided Minor product choice beside it never rides along."""
    session_dir, gitdir, _h = _session(
        tmp_path, [_gate_blocker("tradeoff J", 1), _choice("minor choice", 2)],
        to_phase=RD.P_JUDGMENT, name="c7-choice-undecided")
    assert [row["title"] for row in _state(session_dir)["_judgmentFindings"]] == ["tradeoff J"]
    out = _fold_judgment(tmp_path, session_dir, gitdir, [])
    assert out.get("ok") is True, out
    after = _state(session_dir)
    assert [row["title"] for row in after["_fixBatch"]] == ["tradeoff J"]
    assert after["_fixBatch"][0].get("judgmentFailClosed") is True
