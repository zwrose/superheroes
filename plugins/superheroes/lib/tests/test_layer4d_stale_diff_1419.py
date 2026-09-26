"""C13 layer 4d (#1419), part (i): a panel is never dispatched over a diff older than its head.

When a fixer lands with no post-fix head diff, the driver derives `git diff <baseRef>...<head>`
itself and the full panel reviews that; when it cannot, it parks `reviewed-diff-stale` instead of
dispatching a panel over the pre-fix diff."""
import ast
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import round_records as RR  # noqa: E402
import session_checkout  # noqa: E402
import test_round_driver as TRD  # noqa: E402

RD = TRD.RD

# The derivation, the chokepoint and their bite-proofs run with the test-only git double OFF,
# against real temporary git repositories.
pytestmark = pytest.mark.real_git_head_diff


def _git(path, *args):
    return session_checkout._git(path, *args).stdout


# The contract's literals, spelled out — never read back from the driver (a renamed token or a
# dropped flag must fail here, not move the oracle with it).
_FLAGS = ("--no-color", "--no-ext-diff", "--no-textconv")


def _expected_diff(checkout, base, head):
    return _git(checkout, "diff", *_FLAGS, "%s...%s" % (base, head))


def _respond(checkout, missing, seen):
    """Round 1 finds one Important on f.py; the fixer commits a real change and hands back an
    unreadable `headDiffPath`, so the head diff is unknown."""
    def respond(phase, payload, rnd):
        if phase == RD.P_PANEL:
            seen.setdefault("panels", []).append(rnd)
            seats = {dm: {"findings": []} for dm in RD.DIMENSIONS}
            if rnd == 1:
                seats["code-reviewer"] = {"findings": [
                    {"title": "bug", "severity": "Important", "file": "f.py", "line": 1}]}
            return {"seats": seats}
        if phase == RD.P_VERIFIERS:
            return {"verdicts": [{"id": i, "verdict": "CONFIRMED", "evidence": "ran",
                                  "reason": "ran"}
                                 for c in payload.get("clusters", []) for i in c.get("ids", [])]}
        if phase == RD.P_SYNTHESIS:
            return {"grouping": None}
        if phase == RD.P_FIXER:
            # Each fix round commits distinct content, so a loop that wrongly runs on into another
            # fix round fails on the test's own assertion, never on an empty commit here.
            with open(os.path.join(checkout, "f.py"), "w", encoding="utf-8") as fh:
                fh.write("new\nmore\nfixed %d\n" % rnd)
            _git(checkout, "commit", "-qam", "fix %d" % rnd)
            return {"fixes": [], "headDiffPath": missing, "changedSubjects": ["Code"]}
        if phase == RD.P_VERIFY:
            return {"result": "pass"}
        if phase == RD.P_SCOPED:
            seen["scoped"] = True
            return {"findings": []}
        if phase == RD.P_STALL:
            return {"choice": "hold"}
        return {"results": [], "findings": []}
    return respond


def _seed_checkout(session_dir):
    checkout = os.path.join(session_dir, "checkout")
    os.makedirs(checkout)
    with open(os.path.join(checkout, "f.py"), "w", encoding="utf-8") as fh:
        fh.write("new\nmore\n")
    return checkout, session_checkout.make_checkout(checkout)


def _receipt(session_dir):
    import json
    with open(os.path.join(session_dir, RD.RECEIPT_FILE), encoding="utf-8") as fh:
        return json.load(fh)


def test_unknown_head_diff_is_derived_from_git_for_the_full_panel(tmp_path):
    """The full panel after an unknown-head fix reviews `git diff base...head`, not round 1's
    diff. Bite-proof: `lib/tests/bite_proofs/l4d_armD_stale_diff.md` (red token: the round-2
    diff.txt equals the round-1 diff)."""
    d = str(tmp_path / "session")
    os.makedirs(d)
    checkout, base = _seed_checkout(d)
    seen = {}
    payload = TRD._drive_cli(
        d, TRD._cfg(baseRef=base), _respond(checkout, str(tmp_path / "missing.txt"), seen))
    head = _git(checkout, "rev-parse", "HEAD").strip()
    assert seen.get("panels") == [1, 2], seen
    assert not seen.get("scoped")
    with open(os.path.join(RR.round_dir(d, 2), "diff.txt"), encoding="utf-8") as fh:
        panel_diff = fh.read()
    with open(os.path.join(RR.round_dir(d, 1), "diff.txt"), encoding="utf-8") as fh:
        round1_diff = fh.read()
    assert panel_diff != round1_diff, "the round-2 panel reviewed the pre-fix diff"
    assert panel_diff == _expected_diff(checkout, base, head)
    assert payload["verdict"] == "converged", payload
    rounds = _receipt(d)["rounds"]
    assert any(r.get("headDiffSource") == "unknown" for r in rounds), rounds
    assert any(r.get("reviewedDiffSource") == "git-derived" for r in rounds), rounds
    # The certification writer's own round projection carries the provenance too.
    import round_certification as RC
    cert_rounds = RC._build_receipt_rounds(RD.load_state(d)[1], RC.RECEIPT_FORM_CERTIFIED)
    assert any(r.get("reviewedDiffSource") == "git-derived" for r in cert_rounds), cert_rounds


def test_underivable_unknown_head_diff_parks_reviewed_diff_stale(tmp_path):
    """No pinned base, so no derivable diff: the loop parks `reviewed-diff-stale` and never
    dispatches the round-2 panel. Bite-proof: same record (red token: a round-2 panel runs)."""
    d = str(tmp_path / "session")
    os.makedirs(d)
    checkout, _base = _seed_checkout(d)
    seen = {}
    payload = TRD._drive_cli(d, TRD._cfg(), _respond(checkout, str(tmp_path / "missing.txt"), seen))
    assert seen.get("panels") == [1], seen
    assert payload["verdict"] == "cannot-certify", payload
    assert "reviewed-diff-stale" in (payload["certification"] or {}).get("reason", ""), payload


def test_derivation_admits_only_a_non_empty_utf8_git_diff(tmp_path, monkeypatch):
    """Admission: a real change is admitted verbatim; an empty diff and non-UTF-8 output are not."""
    checkout = str(tmp_path / "repo")
    os.makedirs(checkout)
    with open(os.path.join(checkout, "f.py"), "w", encoding="utf-8") as fh:
        fh.write("a = 1\n")
    base = session_checkout.make_checkout(checkout)
    monkeypatch.chdir(checkout)
    session_dir = str(tmp_path / "session")
    os.makedirs(session_dir)
    state = {"config": {"baseRef": base}}
    assert RD._derive_head_diff_from_git(session_dir, dict(state, config={"baseRef": base})) is None
    with open(os.path.join(checkout, "f.py"), "w", encoding="utf-8") as fh:
        fh.write("a = 2\n")
    _git(checkout, "commit", "-qam", "change")
    head = _git(checkout, "rev-parse", "HEAD").strip()
    got = RD._derive_head_diff_from_git(session_dir, {"config": {"baseRef": base}})
    assert got == _expected_diff(checkout, base, head) and got.startswith("diff --git ")
    with open(os.path.join(checkout, "g.py"), "wb") as fh:
        fh.write(b"s = 'caf\xe9'\n")
    _git(checkout, "add", "g.py")
    _git(checkout, "commit", "-qm", "latin1")
    assert RD._derive_head_diff_from_git(session_dir, {"config": {"baseRef": base}}) is None
    assert RD._derive_head_diff_from_git(None, {"config": {"baseRef": base}}) is None
    assert RD._derive_head_diff_from_git(session_dir, {"config": {"baseRef": "main"}}) is None


def _calls_in(tree, name):
    """The function names whose bodies call ``name`` (or raise/catch it)."""
    owners = set()
    for fn in ast.walk(tree):
        if not isinstance(fn, ast.FunctionDef):
            continue
        for node in ast.walk(fn):
            if isinstance(node, ast.Name) and node.id == name:
                owners.add(fn.name)
    return owners


def test_panel_order_emission_is_the_one_stale_refusal_site():
    """Invariant census: the stale refusal runs in exactly one place, `_emit_orders_manifest` (the
    one renderer of every dispatch order, which `next`, `advance` via `next`, and `re-emit` reach);
    the exception is raised only by the refusal, and parked only where emission is called. The
    retired per-path pieces (marker, `_enter_panel`, loaded-state park) stay retired."""
    with open(os.path.join(_LIB, "round_driver.py"), encoding="utf-8") as fh:
        source = fh.read()
    tree = ast.parse(source)
    assert _calls_in(tree, "_refuse_stale_panel_emission") == {"_emit_orders_manifest"}
    assert _calls_in(tree, "ReviewedDiffStale") == {
        "_refuse_stale_panel_emission", "_cmd_next_locked", "_cmd_re_emit_locked"}
    assert _calls_in(tree, "_emit_orders_manifest") == {"_cmd_next_locked", "_cmd_re_emit_locked"}
    assert _calls_in(tree, "_park_reviewed_diff_stale") == {
        "_cmd_next_locked", "_cmd_re_emit_locked", "_stale_pending_panel_park"}
    # The consumption side: a panel order already pending is checked where it is replayed or folded.
    assert _calls_in(tree, "_stale_pending_panel_park") == {"_cmd_next_locked", "_advance_locked"}
    # One staleness rule: the certification chokepoint (`_terminal_converged`, the one writer of a
    # converged terminal) carries the invariant; emission, consumption, the panel fold and
    # run_loop are early exits reading the same rule.
    assert _calls_in(tree, "_reviewed_diff_is_stale") == {
        "_terminal_converged", "_refuse_stale_panel_emission", "_stale_pending_panel_park",
        "_fold", "run_loop"}
    assert "_reviewedDiffStale" not in source
    defined = {fn.name for fn in ast.walk(tree) if isinstance(fn, ast.FunctionDef)}
    assert not defined & {"_enter_panel", "_reviewed_diff_stale", "_stale_panel_blocks_loaded"}


def test_the_reviewed_diff_is_bound_to_the_head_it_was_taken_at():
    """A session with no fix is never stale; a fold moves the head; only a known head diff (text,
    empty included) re-binds the reviewed diff; a pre-count state that folded a fixer is stale."""
    RD._refuse_stale_panel_emission({"reviewedDiff": "d"}, RD.P_PANEL)
    state = {"reviewedDiff": "old", "reviewedDiffHead": 0, "fixFolds": 1, "headDiff": None}
    RD._advance_reviewed_diff(state)
    assert state["reviewedDiff"] == "old" and state["reviewedDiffHead"] == 0
    try:
        RD._refuse_stale_panel_emission(state, RD.P_PANEL)
        raise AssertionError("a stale panel order was emitted")
    except RD.ReviewedDiffStale as exc:
        assert str(exc) == "reviewed-diff-stale"
    RD._refuse_stale_panel_emission(state, RD.P_FIXER)
    state["headDiff"] = ""
    RD._advance_reviewed_diff(state)
    assert state["reviewedDiff"] == "" and state["reviewedDiffHead"] == 1
    RD._refuse_stale_panel_emission(state, RD.P_PANEL)
    legacy = {"reviewedDiff": "d", "_headDiffSource": "inline", "headDiff": "d"}
    RD._advance_reviewed_diff(legacy)
    try:
        RD._refuse_stale_panel_emission(legacy, RD.P_PANEL)
        raise AssertionError("a pre-count folded state emitted a panel")
    except RD.ReviewedDiffStale:
        pass


def test_inline_head_diff_that_is_not_text_is_unknown(tmp_path):
    """`headDiff: {}` (or any non-text) is an UNKNOWN head, the same as absent; `""` is a known
    empty diff."""
    assert RD._resolve_head_diff({"headDiff": {}}) == (None, "unknown")
    assert RD._resolve_head_diff({"headDiff": 3}) == (None, "unknown")
    assert RD._resolve_head_diff({"headDiff": ""}) == ("", "inline")
    path = tmp_path / "head.diff"
    path.write_text("diff --git a/x b/x\n", encoding="utf-8")
    assert RD._resolve_head_diff({"headDiff": {}, "headDiffPath": str(path)}) == (
        "diff --git a/x b/x\n", "path")


def test_non_text_inline_head_diff_via_hand_submit_parks_stale(tmp_path):
    """A hand-submitted fixer result with `headDiff: {}` and no derivable diff never reaches a
    round-2 panel (red token: a round-2 panel runs)."""
    d = str(tmp_path / "session")
    os.makedirs(d)
    checkout, _base = _seed_checkout(d)
    seen = {}
    inner = _respond(checkout, str(tmp_path / "missing.txt"), seen)

    def respond(phase, payload, rnd):
        art = inner(phase, payload, rnd)
        if phase == RD.P_FIXER:
            art = {"fixes": [], "headDiff": {}}
        return art
    payload = TRD._drive_cli(d, TRD._cfg(), respond)
    assert seen.get("panels") == [1], seen
    assert payload["verdict"] == "cannot-certify", payload
    assert "reviewed-diff-stale" in payload["certification"]["reason"], payload


def test_a_known_empty_post_fix_diff_parks_rather_than_certify_an_empty_surface(tmp_path):
    """The fixer's commit and revert leave the head's tree equal to the base: git's diff at the fold
    head is empty, and an empty review surface is never certifiable, so derivation admits nothing
    and the loop parks `reviewed-diff-stale` — whatever the fixer supplied (here `""`). Red token:
    a round-2 panel runs."""
    d = str(tmp_path / "session")
    os.makedirs(d)
    checkout, base = _seed_checkout(d)
    seen = {}
    inner = _respond(checkout, str(tmp_path / "missing.txt"), seen)

    def respond(phase, payload, rnd):
        if phase == RD.P_FIXER:
            with open(os.path.join(checkout, "f.py"), "w", encoding="utf-8") as fh:
                fh.write("new\nmore\nfixed\n")
            _git(checkout, "commit", "-qam", "fix")
            _git(checkout, "revert", "--no-edit", "HEAD")
            return {"fixes": [], "headDiff": ""}
        return inner(phase, payload, rnd)
    payload = TRD._drive_cli(d, TRD._cfg(baseRef=base), respond)
    assert seen.get("panels") == [1], seen
    assert payload["verdict"] == "cannot-certify", payload
    assert "reviewed-diff-stale" in payload["certification"]["reason"], payload


def _fold_two_slices(monkeypatch, derived, second_artifact):
    """Fold two fixer slices of one capped round: slice 1 has no diff and `derived` is what git
    yields for it; slice 2 hands back `second_artifact` with derivation now failing."""
    calls = iter([derived, None])
    monkeypatch.setattr(RD, "_derive_head_diff_from_git", lambda session_dir, state: next(calls))
    monkeypatch.setattr(RD, "_enter_post_fix", lambda state, config, session_dir=None: None)
    state = {"round": 2, "rounds": {}, "decisions": [], "_fixBatch": [{"id": "a"}],
             "_fixBatchIndex": 0}
    seam = lambda reviewed, head, findings: ["Code"]  # noqa: E731
    RD._fold_fixer(state, {"fixerVendor": "claude"}, {"fixes": []}, seam)
    assert state["rounds"]["2"].get("reviewedDiffSource") == "git-derived"
    state["_fixBatchIndex"] = 1
    state["_fixBatch"] = [{"id": "b"}]
    RD._fold_fixer(state, {"fixerVendor": "claude"}, second_artifact, seam)
    return state


def test_a_supplied_slice_diff_never_replaces_the_derived_one(monkeypatch):
    """Git is the authority per slice: slice 2 supplies an inline diff but git cannot derive one,
    so the head is unknown — the supplied text is never adopted, and no `git-derived` provenance
    survives from slice 1 (red token: `headDiff` equals the supplied text)."""
    inline = "diff --git a/y b/y\n"
    state = _fold_two_slices(monkeypatch, "diff --git a/x b/x\n", {"fixes": [], "headDiff": inline})
    assert state["headDiff"] is None
    assert "reviewedDiffSource" not in state["rounds"]["2"], state["rounds"]["2"]


def test_a_later_underivable_slice_clears_git_derived_provenance(monkeypatch):
    """Derived-then-underivable: the final head is unknown (stale), so no `git-derived` claim."""
    state = _fold_two_slices(monkeypatch, "diff --git a/x b/x\n", {"fixes": []})
    assert state["headDiff"] is None and state["fixFolds"] == 2
    assert "reviewedDiffSource" not in state["rounds"]["2"], state["rounds"]["2"]


def _drive_to_post_fix_verify(session_dir, cfg, respond):
    """Drive next/submit until the post-fix verify gate bound for the panel is the next step;
    returns without submitting it."""
    TRD.enter_checkout(os.path.join(session_dir, "checkout"))
    first = True
    for _ in range(80):
        n = RD.cmd_next(session_dir, cfg if first else None)
        first = False
        assert n["ok"], n
        assert n["action"] != RD.P_TERMINAL, n
        if n["phase"] == RD.P_VERIFY and n["round"] >= 2:
            return n
        art = respond(n["phase"], n["payload"], n["round"])
        s = RD.cmd_submit(session_dir, n["phase"], n["attempt"], n["expectedStateHash"], art)
        assert s["ok"], s
    raise AssertionError("never reached the post-fix verify gate")


def _rewrite_state(session_dir, mutate):
    import json
    path = os.path.join(session_dir, RD.STATE_FILE)
    with open(path, encoding="utf-8") as fh:
        state = json.load(fh)
    mutate(state)
    RD.save_state(session_dir, state)


def _legacy(state):
    """The shape the pre-count driver left after a fixer fold: no fold count, no bound head."""
    assert state.get("headDiff") is None and "_headDiffSource" in state, state
    state.pop("fixFolds")
    state.pop("reviewedDiffHead")


def _stale_session(tmp_path):
    d = str(tmp_path / "session")
    os.makedirs(d)
    checkout, _base = _seed_checkout(d)
    seen = {}
    respond = _respond(checkout, str(tmp_path / "missing.txt"), seen)
    _drive_to_post_fix_verify(d, TRD._cfg(), respond)
    return d, respond, seen


def _assert_parked(answer):
    assert answer["ok"] and answer["action"] == RD.P_TERMINAL, answer
    assert answer["payload"]["verdict"] == "cannot-certify", answer
    assert "reviewed-diff-stale" in answer["payload"]["certification"]["reason"], answer


def test_persisted_pre_count_state_at_the_panel_parks_stale_via_next(tmp_path):
    """Entry path `next`: a pre-count state persisted at the panel step over the pre-fix diff parks
    at emission (red token: `next` answers `dispatch-panel` for round 2)."""
    d, _respond_fn, seen = _stale_session(tmp_path)

    def at_panel(state):
        _legacy(state)
        state["step"] = RD.P_PANEL
        state["pending"] = None
        state.pop("_verifyThen", None)
    _rewrite_state(d, at_panel)
    _assert_parked(RD.cmd_next(d))
    assert not os.path.isdir(os.path.join(RR.round_dir(d, 2), "orders", RD.P_PANEL))
    assert seen.get("panels") == [1], seen


def test_persisted_pre_count_state_at_verify_parks_stale(tmp_path):
    """A pre-count state persisted at the verify gate bound for the panel parks when the gate's fold
    reaches panel emission (red token: a round-2 panel runs)."""
    d, respond, seen = _stale_session(tmp_path)
    _rewrite_state(d, _legacy)
    payload = TRD._drive_cli(d, None, respond)
    assert payload["verdict"] == "cannot-certify", payload
    assert "reviewed-diff-stale" in payload["certification"]["reason"], payload
    assert seen.get("panels") == [1], seen


def test_stale_panel_cannot_be_emitted_via_durable_advance(tmp_path):
    """Entry path `advance`: the durable fold of the verify gate emits the next action through
    `next`, whose panel emission parks (red token: `nextAction` is `dispatch-panel`)."""
    import json
    d, _respond_fn, seen = _stale_session(tmp_path)
    pend = RD.load_state(d)[1]["pending"]
    _rewrite_state(d, lambda state: state.pop("_submitUsed", None))
    landing = RR.bare_payload_path(d, pend["round"], RD.P_VERIFY, RR.storage_key("verify"),
                                   pend["attempt"])
    os.makedirs(os.path.dirname(landing), exist_ok=True)
    with open(landing, "w", encoding="utf-8") as fh:
        json.dump({"result": "pass"}, fh)
    out = RD.cmd_advance(d)
    assert out.get("ok"), out
    _assert_parked(out["nextAction"])
    assert out.get("terminal") == "cannot-certify", out
    assert seen.get("panels") == [1], seen


def test_stale_panel_cannot_be_re_emitted(tmp_path, capsys):
    """Entry path `re-emit`: a pending panel whose reviewed diff is older than the fold head parks
    instead of rendering a new attempt (red token: re-emit answers a `dispatch-panel` attempt 1)."""
    import test_round_driver_re_emit as RE
    _repo, _sess, d = RE._stale_session(tmp_path, capsys)

    def moved(state):
        state["fixFolds"] = 1
    _rewrite_state(d, moved)
    out = RD.cmd_re_emit(d, "tester")
    _assert_parked(out)
    assert RE._anchor_for(d, 1, RD.P_PANEL, 1) is None


def _older_driver_pending_panel(tmp_path):
    """A session an older driver saved after an unknown-head fix, with the round-2 panel order it
    had ALREADY emitted still pending: no fold count, no bound head, pending `dispatch-panel`."""
    d, respond, seen = _stale_session(tmp_path)

    def pending_panel(state):
        _legacy(state)
        state["step"] = RD.P_PANEL
        state.pop("_verifyThen", None)
        state["pending"] = {"action": RD.P_PANEL, "round": state["round"], "phase": RD.P_PANEL,
                            "attempt": 0, "payload": {"dimensions": list(RD.DIMENSIONS)}}
    _rewrite_state(d, pending_panel)
    return d, seen


def test_an_already_pending_stale_panel_is_not_replayed_via_next(tmp_path):
    """Consumption via `next`: the older driver's pending panel order is never replayed over the
    pre-fix diff (red token: `next` answers the pending `dispatch-panel`)."""
    d, seen = _older_driver_pending_panel(tmp_path)
    _assert_parked(RD.cmd_next(d))
    assert seen.get("panels") == [1], seen


def test_an_already_pending_stale_panel_is_not_folded_via_advance(tmp_path):
    """Consumption via durable `advance`: it parks before any roster check (red token: `advance`
    answers `incomplete-roster`, or folds the panel)."""
    d, _seen = _older_driver_pending_panel(tmp_path)
    _rewrite_state(d, lambda state: state.pop("_submitUsed", None))
    out = RD.cmd_advance(d)
    assert out.get("ok") and out.get("folded") is None, out
    _assert_parked(out["nextAction"])
    assert RD.load_state(d)[1]["terminal"] == "cannot-certify"


def test_a_stale_panel_submit_keeps_its_output_then_parks(tmp_path):
    """Consumption via hand `submit`: the panel's artifact is accepted and folded (its output is
    kept in the durable record), then the session parks `reviewed-diff-stale` (red token: the
    submit is refused unrecorded, or the loop moves on to verifiers)."""
    d, _seen = _older_driver_pending_panel(tmp_path)
    state = RD.load_state(d)[1]
    seats = {dm: {"findings": []} for dm in RD.DIMENSIONS}
    seats["code-reviewer"] = {"findings": [
        {"title": "kept", "severity": "Minor", "file": "f.py", "line": 1}]}
    out = RD.cmd_submit(d, RD.P_PANEL, 0, RD.state_hash(state), {"seats": seats})
    assert out.get("ok") and out.get("nextStep") == RD.P_TERMINAL, out
    accepted = [e for e in RD.read_journal(d)
                if e.get("cmd") == "submit" and e.get("outcome") == "accepted"
                and e.get("phase") == RD.P_PANEL and e.get("round") == 2]
    assert accepted, "the stale panel's submit was not recorded"
    after = RD.load_state(d)[1]
    assert after["terminal"] == "cannot-certify"
    assert "reviewed-diff-stale" in after["certification"]["reason"]


def test_run_loop_never_runs_a_panel_over_a_stale_reviewed_diff():
    """The in-process `run_loop` path renders no orders; it reads the same rule before a panel
    (red token: the reviewer seam is called for round 2 over the pre-fix diff)."""
    calls = []

    def reviewer(dim, tier, rnd, ctx):
        calls.append(rnd)
        if rnd == 1 and dim == "code-reviewer":
            return [{"title": "bug", "severity": "Important", "file": "f.py", "line": 1}]
        return []
    seams = TRD._seams(reviewer=reviewer,
                       fix_step=lambda batch, rnd, payload: {"fixes": [], "changedSubjects": ["Code"]})
    _refusal, loop_receipt = TRD._run_loop_with_loop_receipt(seams, TRD._cfg())
    assert calls and set(calls) == {1}, calls
    assert loop_receipt["verdict"] == "cannot-certify", loop_receipt.get("verdict")
    assert any("reviewed-diff-stale" in str(dc.get("detail"))
               for dc in loop_receipt.get("decisions") or []), loop_receipt.get("decisions")


def test_the_git_double_is_off_in_this_module():
    """This module's proofs are only proofs if the driver runs its real git derivation."""
    import head_diff_double
    assert not head_diff_double.installed(RD) and not head_diff_double.installed(TRD.RD)


@pytest.mark.parametrize("supplied", ["", "diff --git a/f.py b/f.py\n@@ -1 +1 @@\n-x\n+y\n"])
def test_a_supplied_head_diff_is_ignored_and_git_is_reviewed(tmp_path, supplied):
    """Git is the authority: a supplied diff — including a wrong `""` — carries no authority. The
    reviewed diff after the fix is git's diff at the fold head, never the supplied text (red
    token: the reviewed diff equals the supplied text)."""
    d = str(tmp_path / "session")
    os.makedirs(d)
    checkout, base = _seed_checkout(d)
    seen = {}
    inner = _respond(checkout, str(tmp_path / "missing.txt"), seen)
    captured = {}

    def respond(phase, payload, rnd):
        if phase == RD.P_VERIFY and "reviewed" not in captured and rnd >= 2:
            captured["reviewed"] = RD.load_state(d)[1].get("reviewedDiff")
            captured["head"] = _git(checkout, "rev-parse", "HEAD").strip()
        art = inner(phase, payload, rnd)
        if phase == RD.P_FIXER:
            art = {"fixes": [], "headDiff": supplied}
        return art
    TRD._drive_cli(d, TRD._cfg(baseRef=base), respond)
    assert captured.get("reviewed") == _expected_diff(checkout, base, captured["head"]), captured
    assert captured["reviewed"] != supplied


def test_a_supplied_head_diff_equal_to_git_is_accepted(tmp_path):
    """The cross-check passes when the supplied diff is git's own diff at the fold head."""
    d = str(tmp_path / "session")
    os.makedirs(d)
    checkout, base = _seed_checkout(d)
    seen = {}
    inner = _respond(checkout, str(tmp_path / "missing.txt"), seen)

    def respond(phase, payload, rnd):
        if phase == RD.P_AUDITS:
            targets = payload.get("targets", [])
            return {"results": [{"id": t["id"], "ruling": "discharged", "reason": "r",
                                 "evidence": "e", "auditorVendor": t.get("auditorVendor")}
                                for t in targets],
                    "collectionManifest": {t["id"]: t.get("auditorVendor") for t in targets}}
        art = inner(phase, payload, rnd)
        if phase == RD.P_FIXER:
            head = _git(checkout, "rev-parse", "HEAD").strip()
            art = {"fixes": [], "headDiff": _git(checkout, "diff", "--no-color", "--no-ext-diff",
                                                 "--no-textconv", "%s...%s" % (base, head))}
        return art
    payload = TRD._drive_cli(d, TRD._cfg(baseRef=base), respond)
    assert payload["verdict"] == "converged", payload


def test_the_contract_literals_are_pinned():
    """The derivation's flags and the named tokens are an external contract: pinned as literals."""
    assert RD._GIT_DIFF_FORMAT_FLAGS == ("--no-color", "--no-ext-diff", "--no-textconv")
    assert RD.REVIEWED_DIFF_STALE == "reviewed-diff-stale"
    assert RD.REVIEWED_DIFF_SOURCE_GIT == "git-derived"


def test_the_stale_park_via_advance_refuses_a_failed_sidecar_publish(tmp_path, monkeypatch):
    """The stale-pending-panel park on `advance` never answers ok over a failed sidecar publish
    (red token: `ok: True` with the sidecar lost)."""
    d, _seen = _older_driver_pending_panel(tmp_path)
    _rewrite_state(d, lambda state: state.pop("_submitUsed", None))
    monkeypatch.setattr(RD, "_publish_sidecar",
                        lambda session_dir, state, git=None: {"reason": "sidecar-unwritable",
                                                              "detail": "probe"})
    out = RD.cmd_advance(d)
    assert out["ok"] is False and out["reason"] == "sidecar-unwritable", out


def _drive_until(session_dir, cfg, respond, phase, min_round=1):
    TRD.enter_checkout(os.path.join(session_dir, "checkout"))
    first = True
    for _ in range(80):
        n = RD.cmd_next(session_dir, cfg if first else None)
        first = False
        assert n["ok"] and n["action"] != RD.P_TERMINAL, n
        if n["phase"] == phase and n["round"] >= min_round:
            return n
        art = respond(n["phase"], n["payload"], n["round"])
        assert RD.cmd_submit(session_dir, n["phase"], n["attempt"], n["expectedStateHash"],
                             art)["ok"]
    raise AssertionError("never reached %s" % phase)


def _discharging(inner):
    def respond(phase, payload, rnd):
        if phase == RD.P_AUDITS:
            targets = payload.get("targets", [])
            return {"results": [{"id": t["id"], "ruling": "discharged", "reason": "r",
                                 "evidence": "e", "auditorVendor": t.get("auditorVendor")}
                                for t in targets],
                    "collectionManifest": {t["id"]: t.get("auditorVendor") for t in targets}}
        return inner(phase, payload, rnd)
    return respond


def test_a_legacy_resume_past_the_panel_never_certifies(tmp_path):
    """The certification chokepoint: a state an older driver saved after a fix, resumed at the
    fix audits (no panel ahead of it), converges but never certifies — `_terminal_converged`
    parks `reviewed-diff-stale` (red token: verdict `converged`)."""
    d = str(tmp_path / "session")
    os.makedirs(d)
    checkout, base = _seed_checkout(d)
    seen = {}
    inner = _respond(checkout, str(tmp_path / "missing.txt"), seen)

    def with_inline(phase, payload, rnd):
        art = inner(phase, payload, rnd)
        if phase == RD.P_FIXER:
            art = {"fixes": [], "headDiff": "supplied, ignored"}
        return art
    respond = _discharging(with_inline)
    _drive_until(d, TRD._cfg(baseRef=base), respond, RD.P_AUDITS, min_round=2)

    def legacy(state):
        state.pop("fixFolds")
        state.pop("reviewedDiffHead")
    _rewrite_state(d, legacy)
    payload = TRD._drive_cli(d, None, respond)
    assert payload["verdict"] == "cannot-certify", payload
    assert "reviewed-diff-stale" in payload["certification"]["reason"], payload


def test_no_path_certifies_a_head_the_panel_did_not_see(tmp_path):
    """Whatever route a stale session takes, it ends uncertified with the token — asserted on the
    terminal alone, so the certification chokepoint carries it even if every early exit were gone
    (bite-proof: remove emission, consumption and the panel-fold park; this stays green)."""
    d, respond, _seen = _stale_session(tmp_path)
    _rewrite_state(d, _legacy)
    payload = TRD._drive_cli(d, None, _discharging(respond))
    assert payload["verdict"] != "converged", payload
    assert "reviewed-diff-stale" in (payload.get("certification") or {}).get("reason", ""), payload
