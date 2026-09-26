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
_FLAGS = ("--no-color", "--no-ext-diff", "--no-textconv", "--src-prefix=a/", "--dst-prefix=b/")


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


def test_an_unsupplied_head_diff_is_derived_from_git_and_reviewed(tmp_path):
    """A fixer that hands back no readable head diff does not make the surface unknown: the driver
    derives `git diff base...head` itself, the delta round reviews that (never round 1's diff), and
    the loop converges. The unknown surface is keyed on the derivation alone. Bite-proof:
    `lib/tests/bite_proofs/l4d_armD_stale_diff.md` (red token: the reviewed diff is not git's)."""
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
        return inner(phase, payload, rnd)
    payload = TRD._drive_cli(d, TRD._cfg(baseRef=base), _discharging(respond))
    with open(os.path.join(RR.round_dir(d, 1), "diff.txt"), encoding="utf-8") as fh:
        round1_diff = fh.read()
    assert captured.get("reviewed") != round1_diff, "the delta round reviewed the pre-fix diff"
    assert captured.get("reviewed") == _expected_diff(checkout, base, captured["head"]), \
        "the reviewed diff is not git's"
    # A known surface: the delta round runs, never a second full panel.
    assert seen.get("panels") == [1], seen
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
        "_fold", "_run_loop_in_process"}
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
    """A supplied diff equal to git's own is simply ignored like any other: the loop converges on
    git's diff."""
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


@pytest.mark.parametrize("agrees", [True, False], ids=["path-agrees-with-git",
                                                        "path-disagrees-with-git"])
def test_a_readable_head_diff_path_carries_no_authority(tmp_path, agrees):
    """A readable `headDiffPath` is read (`headDiffSource: path`) but carries no authority: whether
    its bytes agree with git's or not, the reviewed diff is git's diff at the fold head and the
    loop converges without parking. Bite-proof: `lib/tests/bite_proofs/l4d_armD_stale_diff.md`
    record N (red token: `the reviewed diff equals the path's bytes`)."""
    d = str(tmp_path / "session")
    os.makedirs(d)
    checkout, base = _seed_checkout(d)
    seen = {}
    inner = _respond(checkout, str(tmp_path / "missing.txt"), seen)
    path = str(tmp_path / "head.diff")
    captured = {}

    def respond(phase, payload, rnd):
        if phase == RD.P_VERIFY and "reviewed" not in captured and rnd >= 2:
            captured["reviewed"] = RD.load_state(d)[1].get("reviewedDiff")
            captured["head"] = _git(checkout, "rev-parse", "HEAD").strip()
        art = inner(phase, payload, rnd)
        if phase == RD.P_FIXER:
            head = _git(checkout, "rev-parse", "HEAD").strip()
            text = (_expected_diff(checkout, base, head) if agrees
                    else "diff --git a/f.py b/f.py\n@@ -1 +1 @@\n-x\n+not what git says\n")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
            captured["supplied"] = text
            art = {"fixes": [], "headDiffPath": path}
        return art
    payload = TRD._drive_cli(d, TRD._cfg(baseRef=base), _discharging(respond))
    if not agrees:
        assert captured["reviewed"] != captured["supplied"], "the reviewed diff equals the path's bytes"
    expected = _expected_diff(checkout, base, captured["head"])
    assert captured["reviewed"] == expected, "the reviewed diff is not git's diff at the fold head"
    assert payload["verdict"] == "converged", payload
    rounds = _receipt(d)["rounds"]
    assert any(r.get("headDiffSource") == "path" for r in rounds), rounds
    assert any(r.get("reviewedDiffSource") == "git-derived" for r in rounds), rounds


def test_the_stale_park_names_its_cause():
    """The `reviewed-diff-stale` park says why: an unknown fix-fold head, a head that moved with no
    derivable diff, or a commit landed after the reviewed diff was derived — never one fixed
    reason for all three (red token: two causes share one message)."""
    unknown = {"_headDiffSource": "path"}
    moved = {"fixFolds": 1, "reviewedDiffHead": 0}
    late = {"fixFolds": 1, "reviewedDiffHead": 1, "reviewedDiffSha": "a" * 40,
            "config": {RD.FIX_FOLD_HEAD_KEY: "b" * 40}}
    causes = [RD._reviewed_diff_stale_cause(s) for s in (unknown, moved, late)]
    assert all(causes) and len(set(causes)) == 3, "two causes share one message: %r" % causes
    assert "derivable from git" in causes[1] and "a" * 40 in causes[2] and "b" * 40 in causes[2]
    assert RD._reviewed_diff_stale_cause({"fixFolds": 1, "reviewedDiffHead": 1}) is None


def test_the_contract_literals_are_pinned():
    """The derivation's flags and the named tokens are an external contract: pinned as literals."""
    assert RD._GIT_DIFF_FORMAT_FLAGS == ("--no-color", "--no-ext-diff", "--no-textconv",
                                         "--src-prefix=a/", "--dst-prefix=b/")
    assert RD.REVIEW_DIFF_TOO_LARGE == "review-diff-too-large"
    assert RD.REVIEW_DIFF_UNAVAILABLE == "review-diff-unavailable"
    assert RD.STATE_SCHEMA_VERSION == 6
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


def test_skill_setup_runs_the_drivers_review_diff_verb():
    """One home: SKILL.md's Setup round diff invokes the driver's `review-diff` verb and spells no
    git diff of its own (red token: a raw `git ... diff` Setup line)."""
    skill = os.path.join(os.path.dirname(_LIB), "skills", "review-code", "SKILL.md")
    with open(skill, encoding="utf-8") as fh:
        line = next(ln for ln in fh if "diff.txt.tmp" in ln and ">" in ln and "&&" in ln)
    assert "round_driver.py\" review-diff --base \"$BASE_REF\"" in line, line
    command = line.split(">", 1)[0]
    assert "git " not in command and " diff --no-color" not in command, command


def test_the_review_diff_verb_output_is_the_one_review_diff(tmp_path):
    """The verb's output IS the review diff: pinned by behaviour, not a copied flag list — prefixes
    survive `diff.noprefix`, a configured textconv is not applied, and the bytes equal the
    driver's own derivation (red token: `diff --git f.py f.py`, or the textconv marker)."""
    import subprocess
    repo = str(tmp_path / "repo")
    os.makedirs(repo)
    with open(os.path.join(repo, "f.py"), "w", encoding="utf-8") as fh:
        fh.write("a = 1\n")
    base = session_checkout.make_checkout(repo)
    _git(repo, "config", "diff.noprefix", "true")
    _git(repo, "config", "diff.pyconv.textconv", "sed s/a/TEXTCONV/")
    with open(os.path.join(repo, ".gitattributes"), "w", encoding="utf-8") as fh:
        fh.write("*.py diff=pyconv\n")
    with open(os.path.join(repo, "f.py"), "w", encoding="utf-8") as fh:
        fh.write("a = 2\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "change")
    head = _git(repo, "rev-parse", "HEAD").strip()
    out = subprocess.run([sys.executable, "-B", os.path.join(_LIB, "round_driver.py"),
                          "review-diff", "--base", base, "--repo-root", repo],
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    assert "diff --git a/f.py b/f.py\n" in out.stdout, out.stdout
    assert "TEXTCONV" not in out.stdout, out.stdout
    assert out.stdout == RD.derive_review_diff(repo, base)[1]
    assert RD.derive_review_diff(repo, base)[0] == head


@pytest.mark.parametrize("var", ["GIT_DIR", "GIT_WORK_TREE", "GIT_OBJECT_DIRECTORY",
                                 "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_REPLACE_REF_BASE",
                                 "GIT_GRAFT_FILE", "GIT_SHALLOW_FILE", "GIT_CONFIG_PARAMETERS",
                                 "GIT_CONFIG_COUNT", "GIT_CONFIG_KEY_0", "GIT_CONFIG_VALUE_0",
                                 "GIT_DIFF_OPTS", "GIT_ATTR_SOURCE", "GIT_EXTERNAL_DIFF"])
def test_the_git_env_strips_every_ancestry_and_config_shaping_variable(monkeypatch, var):
    """The shared hardening the review diff runs under drops each routing, ancestry and
    config-injection variable (red token: the variable survives into the git env)."""
    import sanitized_view
    monkeypatch.setenv(var, "/hostile")
    assert var not in sanitized_view.git_env()


def test_a_commit_after_the_fold_is_never_certified_unseen(tmp_path):
    """The reviewed diff binds to the SHA it was derived at; a commit landed after the fold moves
    the certified head, so certification withholds `reviewed-diff-stale` (red token: verdict
    `converged` over a head no panel saw)."""
    d = str(tmp_path / "session")
    os.makedirs(d)
    checkout, base = _seed_checkout(d)
    seen = {}
    inner = _respond(checkout, str(tmp_path / "missing.txt"), seen)
    moved = {}

    def respond(phase, payload, rnd):
        if phase == RD.P_VERIFY and rnd >= 2 and not moved:
            with open(os.path.join(checkout, "g.py"), "w", encoding="utf-8") as fh:
                fh.write("late = 1\n")
            _git(checkout, "add", "g.py")
            _git(checkout, "commit", "-qm", "late commit after the fold")
            moved["yes"] = True
        art = inner(phase, payload, rnd)
        if phase == RD.P_FIXER:
            art = {"fixes": [], "headDiff": "supplied, ignored"}
        return art
    payload = TRD._drive_cli(d, TRD._cfg(baseRef=base), _discharging(respond))
    assert moved, "the late commit never landed"
    assert payload["verdict"] == "cannot-certify", payload
    assert "reviewed-diff-stale" in payload["certification"]["reason"], payload


def test_a_user_diff_noprefix_setting_does_not_reshape_the_derived_diff(tmp_path, monkeypatch):
    """The derivation pins the config that reshapes diff bytes: a repository with
    `diff.noprefix=true` still yields `a/`/`b/` prefixes (red token: `diff --git f.py f.py`)."""
    checkout = str(tmp_path / "repo")
    os.makedirs(checkout)
    with open(os.path.join(checkout, "f.py"), "w", encoding="utf-8") as fh:
        fh.write("a = 1\n")
    base = session_checkout.make_checkout(checkout)
    _git(checkout, "config", "diff.noprefix", "true")
    with open(os.path.join(checkout, "f.py"), "w", encoding="utf-8") as fh:
        fh.write("a = 2\n")
    _git(checkout, "commit", "-qam", "change")
    monkeypatch.chdir(checkout)
    session_dir = str(tmp_path / "session")
    os.makedirs(session_dir)
    got = RD._derive_head_diff_from_git(session_dir, {"config": {"baseRef": base}})
    assert got is not None and got.startswith("diff --git a/f.py b/f.py\n"), got


def _certified_session(tmp_path):
    """A converged, git-derived session (fixer supplies nothing; the driver derives the diff)."""
    d = str(tmp_path / "session")
    os.makedirs(d)
    checkout, base = _seed_checkout(d)
    seen = {}
    inner = _respond(checkout, str(tmp_path / "missing.txt"), seen)

    def respond(phase, payload, rnd):
        art = inner(phase, payload, rnd)
        if phase == RD.P_FIXER:
            art = {"fixes": [], "headDiff": "supplied, ignored"}
        return art
    payload = TRD._drive_cli(d, TRD._cfg(baseRef=base), _discharging(respond))
    assert payload["verdict"] == "converged", payload
    return d, checkout, payload


def test_the_certificate_names_the_verified_sha(tmp_path):
    """Certify what was seen: the certification names the explicit SHA the reviewed diff was
    derived at, never "HEAD" (red token: no `certifiedHead`, or one that is not the fold SHA)."""
    d, checkout, payload = _certified_session(tmp_path)
    state = RD.load_state(d)[1]
    assert state["reviewedDiffSha"] == _git(checkout, "rev-parse", "HEAD").strip()
    assert payload["certification"]["certifiedHead"] == state["reviewedDiffSha"], payload


def test_a_commit_after_certification_is_refused_at_handback(tmp_path):
    """Currency is checked where the certificate is consumed: after a late commit the published
    sidecar still names the certified SHA, and the handback gate refuses the moved head with
    `handback-head-mismatch` (red token: the gate allows, or the sidecar names the new head)."""
    d, checkout, payload = _certified_session(tmp_path)
    certified = payload["certification"]["certifiedHead"]
    with open(os.path.join(checkout, "late.py"), "w", encoding="utf-8") as fh:
        fh.write("late = 1\n")
    _git(checkout, "add", "late.py")
    _git(checkout, "commit", "-qm", "late commit after certification")
    _assert_handback_refuses_the_moved_head(d, checkout, certified)


def _assert_handback_refuses_the_moved_head(d, checkout, certified):
    """The published sidecar names `certified`, and the handback gate refuses the live head."""
    import handback_gate as hg
    import json as _json
    state = RD.load_state(d)[1]
    side = RD._publish_sidecar(d, state)
    assert side.get("ok"), side
    with open(side["path"], encoding="utf-8") as fh:
        assert _json.load(fh)["headSha"] == certified
    superheroes_dir = os.path.dirname(side["path"])
    with open(os.path.join(superheroes_dir, hg.BUILD_LANE_FILE), "w", encoding="utf-8") as fh:
        _json.dump({"schema": hg.BUILD_LANE_SCHEMA, "lane": "full", "issue": "#1443",
                    "declaredAt": "2026-09-26T00:00:00Z", "repoRoot": os.path.realpath(checkout),
                    "branch": _git(checkout, "rev-parse", "--abbrev-ref", "HEAD").strip()}, fh)
    result = hg.validate_handback("gh pr ready", checkout)
    assert result["reason"] == "handback-head-mismatch", result


def test_head_resolution_ignores_a_git_dir_decoy(tmp_path, monkeypatch):
    """The head the review diff is derived at resolves under the hardened env: an inherited
    `GIT_DIR` pointing at a decoy repository does not redirect it (red token: the decoy's HEAD)."""
    real = str(tmp_path / "real")
    decoy = str(tmp_path / "decoy")
    for path, text in ((real, "r\n"), (decoy, "d\n")):
        os.makedirs(path)
        with open(os.path.join(path, "f.txt"), "w", encoding="utf-8") as fh:
            fh.write(text)
        session_checkout.make_checkout(path)
    real_head = _git(real, "rev-parse", "HEAD").strip()
    monkeypatch.setenv("GIT_DIR", os.path.join(decoy, ".git"))
    assert RD._hardened_head(real) == real_head


def test_a_no_fix_session_certifies_the_head_its_round_one_diff_was_taken_at(tmp_path):
    """A clean first round through the real CLI `next` certifies the Setup head (meta `headSha`),
    never the live HEAD: a commit landed after certification is refused at handback (red token:
    no `certifiedHead`, so the sidecar and the gate take the late commit)."""
    import test_round_driver_session_mobility as TSM
    repo = TSM._mobility_repo(tmp_path)
    session = TSM._mobility_session(tmp_path, repo)
    d, checkout = session["session_dir"], repo["root_a"]
    TRD.enter_checkout(checkout)
    respond = TRD._responder()
    for _ in range(40):
        n = RD.cmd_next(d)
        assert n["ok"], n
        if n["action"] == RD.P_TERMINAL:
            break
        s = RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"],
                          respond(n["phase"], n["payload"], n["round"]))
        assert s["ok"], s
    payload = n["payload"]
    assert payload["verdict"] == "converged", payload
    assert RD.load_state(d)[1].get("fixFolds") in (None, 0)
    assert payload["certification"]["certifiedHead"] == repo["head"], payload
    with open(os.path.join(checkout, "late.py"), "w", encoding="utf-8") as fh:
        fh.write("late = 1\n")
    _git(checkout, "add", "late.py")
    _git(checkout, "commit", "-qm", "late commit after a no-fix certification")
    _assert_handback_refuses_the_moved_head(d, checkout, repo["head"])


def _prefix_repo(tmp_path):
    repo = str(tmp_path / "repo")
    os.makedirs(repo)
    with open(os.path.join(repo, "f.py"), "w", encoding="utf-8") as fh:
        fh.write("a = 1\n")
    base = session_checkout.make_checkout(repo)
    _git(repo, "config", "diff.srcPrefix", "SRC-")
    _git(repo, "config", "diff.dstPrefix", "DST-")
    with open(os.path.join(repo, "f.py"), "w", encoding="utf-8") as fh:
        fh.write("a = 2\n")
    _git(repo, "commit", "-qam", "change")
    return repo, base, _git(repo, "rev-parse", "HEAD").strip()


def test_configured_diff_prefixes_do_not_reshape_the_review_diff(tmp_path):
    """`diff.srcPrefix`/`diff.dstPrefix` never reach the review diff: the headers stay `a/`/`b/`
    and the round's scope still admits a finding cited on the changed file (red token:
    `+++ DST-f.py`, and the finding dropped as outside the diff scope)."""
    import diff_scope
    repo, base, head = _prefix_repo(tmp_path)
    assert "+++ DST-f.py" in _git(repo, "diff", "%s...%s" % (base, head))
    sha, text, _refusal = RD.derive_review_diff(repo, base)
    assert sha == head
    assert text is not None and text.startswith("diff --git a/f.py b/f.py\n"), text
    assert "\n+++ b/f.py\n" in text, text
    assert 1 in diff_scope.parse_diff_lines(text).get("f.py", ()), text


def test_an_over_cap_review_diff_is_refused_never_truncated(tmp_path, monkeypatch, capsys):
    """Past `REVIEW_DIFF_MAX_BYTES` the review diff is None — never a partial diff — and the verb
    refuses with `review-diff-too-large` (red token: a diff returned, or exit 0)."""
    import json as _json
    import sanitized_view
    repo, base, head = _prefix_repo(tmp_path)
    monkeypatch.setattr(sanitized_view, "REVIEW_DIFF_MAX_BYTES", 16)
    assert RD.derive_review_diff(repo, base) == (head, None, "review-diff-too-large")
    assert RD._review_diff(repo, base, head) == (None, "review-diff-too-large")
    rc = RD.main(["review-diff", "--base", base, "--repo-root", repo])
    err = capsys.readouterr().err.strip().splitlines()[-1]
    assert rc == 1 and _json.loads(err)["reason"] == "review-diff-too-large", err


def test_an_over_cap_post_fix_diff_parks_rather_than_review_a_partial_diff(tmp_path, monkeypatch):
    """The post-fix derivation over the cap derives nothing, so the loop parks
    `reviewed-diff-stale` and never dispatches a panel over a partial diff (red token: a
    `converged` verdict)."""
    import sanitized_view
    monkeypatch.setattr(sanitized_view, "REVIEW_DIFF_MAX_BYTES", 16)
    d = str(tmp_path / "session")
    os.makedirs(d)
    checkout, base = _seed_checkout(d)
    seen = {}
    payload = TRD._drive_cli(d, TRD._cfg(baseRef=base),
                             _discharging(_respond(checkout, str(tmp_path / "missing.txt"), seen)))
    assert payload["verdict"] == "cannot-certify", payload
    assert "reviewed-diff-stale" in payload["certification"]["reason"], payload
    # The park names the size cap, not "no diff derivable".
    assert "review-diff-too-large" in payload["certification"]["reason"], payload


def test_two_real_fix_folds_rebind_the_reviewed_diff_to_each_head(tmp_path):
    """Two fixer folds against real git, no double: after each fold the head diff, its SHA and
    the persisted fix-fold head are that fold's HEAD, and the certificate binds the second head
    (red token: a second fold that reuses the first fold's SHA)."""
    import json as _json
    d = str(tmp_path / "session")
    os.makedirs(d)
    checkout, base = _seed_checkout(d)
    seen = {}
    inner = _respond(checkout, str(tmp_path / "missing.txt"), seen)
    folds = []

    def respond(phase, payload, rnd):
        if phase == RD.P_VERIFY:
            state = RD.load_state(d)[1]
            with open(os.path.join(d, RD.round_records.META_FILE), encoding="utf-8") as fh:
                meta = _json.load(fh)
            head = _git(checkout, "rev-parse", "HEAD").strip()
            folds.append({"head": head, "headDiff": state.get("headDiff"),
                          "headDiffSha": state.get("headDiffSha"),
                          "cfgFold": (state.get("config") or {}).get(RD.FIX_FOLD_HEAD_KEY),
                          "metaFold": meta.get(RD.FIX_FOLD_HEAD_KEY),
                          "expected": _expected_diff(checkout, base, head)})
        if phase == RD.P_AUDITS:
            # The first fix is audited not-discharged, so a second fixer fold follows.
            ruling = "discharged" if seen.get("reopened") else "not-discharged"
            seen["reopened"] = True
            targets = payload.get("targets", [])
            return {"results": [{"id": t["id"], "ruling": ruling, "reason": "r",
                                 "evidence": "e", "auditorVendor": t.get("auditorVendor")}
                                for t in targets],
                    "collectionManifest": {t["id"]: t.get("auditorVendor") for t in targets}}
        art = inner(phase, payload, rnd)
        if phase == RD.P_FIXER:
            art = {"fixes": [], "changedSubjects": ["Code"]}
        return art
    payload = TRD._drive_cli(d, TRD._cfg(baseRef=base), respond)
    assert len(folds) >= 2, folds
    first, second = folds[0], folds[1]
    assert first["head"] != second["head"], folds
    for fold in (first, second):
        assert fold["headDiffSha"] == fold["head"], fold
        assert fold["cfgFold"] == fold["head"] and fold["metaFold"] == fold["head"], fold
        assert fold["headDiff"] == fold["expected"], fold
    assert payload["verdict"] == "converged", payload
    assert payload["certification"]["certifiedHead"] == second["head"], payload


def test_an_older_driver_refuses_a_session_this_driver_minted(tmp_path, monkeypatch):
    """Rollback: state carrying the reviewed-diff binding is minted at the bumped version, so a
    driver that predates it (reads v2–v5) refuses it by version, naming both, before any panel
    is emitted (red token: the older reader loads it)."""
    import json as _json
    d = str(tmp_path / "session")
    os.makedirs(d)
    minted = RD.new_state(TRD._cfg())
    assert minted["schemaVersion"] == 6
    with open(os.path.join(d, RD.STATE_FILE), "w", encoding="utf-8") as fh:
        _json.dump(minted, fh)
    monkeypatch.setattr(RD, "SUPPORTED_STATE_VERSIONS", (2, 3, 4, 5))
    ok, reason = RD.load_state(d)
    assert ok is False and "6" in reason and "5" in reason and "not one of" in reason, reason
    out = RD.cmd_next(d)
    assert not out.get("ok") and out.get("action") != RD.P_PANEL, out


def test_no_operational_reference_spells_a_raw_per_round_diff():
    """One home, every reader: no review-code instruction runs a raw `git diff` over the round
    base — the per-round diff is always the driver's `review-diff` verb (red token: a
    `git diff "$BASE_REF"` or `git diff <pinned baseRef>` directive, with or without git options
    before `diff` or diff flags after it)."""
    import re
    root = os.path.join(os.path.dirname(_LIB), "skills", "review-code")
    raw = re.compile(r'git(?:\s+-[cC]\s+\S+)*\s+diff(?:\s+-{1,2}[\w.-]+(?:=\S+)?)*'
                     r'\s+("?\$\{?BASE_REF|<pinned)')
    for form in ('git diff "$BASE_REF"...HEAD', 'git diff ${BASE_REF}...HEAD',
                 'git diff <pinned baseRef>...HEAD',
                 'git -c core.quotePath=false diff "$BASE_REF"...HEAD',
                 'git -C "$REPO_ROOT" diff "$BASE_REF"...HEAD',
                 'git diff --no-color --src-prefix=a/ "$BASE_REF"...HEAD',
                 'git -c diff.noprefix=false diff -M "$BASE_REF"...HEAD'):
        assert raw.search(form), form
    hits = []
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            if name.endswith(".md"):
                path = os.path.join(dirpath, name)
                with open(path, encoding="utf-8") as fh:
                    for i, line in enumerate(fh, 1):
                        if raw.search(line):
                            hits.append("%s:%d" % (os.path.relpath(path, root), i))
    assert not hits, hits
    with open(os.path.join(root, "reference", "auto-fix-loop.md"), encoding="utf-8") as fh:
        row = next(ln for ln in fh if ln.startswith("| Using `gh pr diff` inside the loop"))
    assert 'round_driver.py review-diff --base "$BASE_REF"' in row, row


# ---- the certified head is recorded by the call that derives the diff (S9 ruling) ------------

def _meta_update(session_dir, **fields):
    import json as _json
    path = os.path.join(session_dir, RR.META_FILE)
    with open(path, encoding="utf-8") as fh:
        meta = _json.load(fh)
    meta.update(fields)
    with open(path, "w", encoding="utf-8") as fh:
        _json.dump(meta, fh)


def test_the_fresh_next_records_the_derived_head_and_digest(tmp_path, capsys):
    """The Setup binding records the pair (the SHA the round-1 diff was derived at, the diff's
    digest) through the one derivation call (red token: no recorded head, or one not HEAD)."""
    import hashlib
    d = str(tmp_path)
    argv = TRD._guard_argv(d)
    rc, out = TRD._cli_next_json(d, argv, capsys)
    assert rc == 0 and out["ok"], out
    state = RD.load_state(d)[1]
    repo = argv[1]
    assert state["reviewedDiffSha"] == _git(repo, "rev-parse", "HEAD").strip()
    with open(os.path.join(d, "round-1", "diff.txt"), "rb") as fh:
        assert state["reviewedDiffDigest"] == hashlib.sha256(fh.read()).hexdigest()


@pytest.mark.parametrize("mode", ["pr", "branch"])
def test_a_behind_checkout_refuses_at_setup(tmp_path, capsys, mode):
    """The session's recorded head (the PR's `headRefOid`) is ahead of the checkout: the round-1
    diff was taken at the checkout's HEAD, so the fresh `next` refuses `round-diff-head-mismatch`
    and seeds no session — never a certificate naming a commit the panel did not review.
    Bite-proof: `lib/tests/bite_proofs/l4d_armD_stale_diff.md` (red token: exit 0 and a pending
    panel)."""
    d = str(tmp_path)
    argv = TRD._guard_argv(d, mode=mode)
    repo = argv[1]
    checkout_head = _git(repo, "rev-parse", "HEAD").strip()
    with open(os.path.join(repo, "g.py"), "w", encoding="utf-8") as fh:
        fh.write("remote only\n")
    _git(repo, "add", "g.py")
    _git(repo, "commit", "-qm", "the PR head the checkout does not have")
    pr_head = _git(repo, "rev-parse", "HEAD").strip()
    _git(repo, "reset", "-q", "--hard", checkout_head)
    _meta_update(d, headSha=pr_head)
    if mode == "pr":
        import json as _json
        _git(repo, "remote", "add", "origin", "https://github.com/o/r.git")
        with open(os.path.join(d, "pr.json"), "w", encoding="utf-8") as fh:
            _json.dump({"url": "https://github.com/o/r/pull/1", "headRefOid": pr_head}, fh)
    rc, out = TRD._cli_next_json(d, argv, capsys)
    assert rc == 1 and out.get("reason") == "round-diff-head-mismatch", out
    assert RD.load_state(d) == (True, None)


def test_a_crlf_round_diff_binds_at_setup(tmp_path, capsys):
    """A diff carrying CRLF lines is read as git's exact bytes, so an unchanged HEAD binds and the
    recorded digest is the digest of the file Setup wrote (red token: `round-diff-head-mismatch`
    from a newline-translated read)."""
    import hashlib
    import json as _json
    d = str(tmp_path)
    argv = TRD._guard_argv(d)
    repo = argv[1]
    with open(os.path.join(repo, "w.txt"), "wb") as fh:
        fh.write(b"one\r\ntwo\r\n")
    _git(repo, "add", "w.txt")
    _git(repo, "commit", "-qm", "a CRLF file")
    with open(os.path.join(d, RR.META_FILE), encoding="utf-8") as fh:
        pin = _json.load(fh)["baseRef"]
    _sha, text, _refusal = RD.derive_review_diff(repo, pin)
    assert text is not None and "+one\r\n" in text, text
    diffpath = os.path.join(d, "round-1", "diff.txt")
    with open(diffpath, "wb") as fh:
        fh.write(text.encode("utf-8"))
    rc, out = TRD._cli_next_json(d, argv, capsys)
    assert rc == 0 and out["ok"], out
    state = RD.load_state(d)[1]
    assert state["reviewedDiffSha"] == _git(repo, "rev-parse", "HEAD").strip()
    with open(diffpath, "rb") as fh:
        assert state["reviewedDiffDigest"] == hashlib.sha256(fh.read()).hexdigest()


def test_a_round_diff_taken_before_head_moved_refuses_at_setup(tmp_path, capsys):
    """HEAD moved between Setup's review diff and the fresh `next`: the supplied diff is not the
    review diff at the resolved SHA, so the binding refuses `round-diff-head-mismatch`."""
    d = str(tmp_path)
    argv = TRD._guard_argv(d)
    repo = argv[1]
    # Same file set and line counts (the stat binding passes); different bytes.
    with open(os.path.join(repo, "f.py"), "w", encoding="utf-8") as fh:
        fh.write("b\n")
    _git(repo, "commit", "-qam", "a commit after Setup's diff")
    rc, out = TRD._cli_next_json(d, argv, capsys)
    assert rc == 1 and out.get("reason") == "round-diff-head-mismatch", out


def _drive_existing(session_dir, respond, max_steps=40):
    for _ in range(max_steps):
        n = RD.cmd_next(session_dir)
        assert n["ok"], n
        if n["action"] == RD.P_TERMINAL:
            return n["payload"]
        s = RD.cmd_submit(session_dir, n["phase"], n["attempt"], n["expectedStateHash"],
                          respond(n["phase"], n["payload"], n["round"]))
        assert s["ok"], s
    raise AssertionError("no terminal")


@pytest.mark.parametrize("recorded", [None, "HEAD", "abc123", "g" * 40],
                         ids=["absent", "symbolic", "short", "not-hex"])
def test_a_no_fix_session_without_a_recorded_head_withholds(tmp_path, recorded):
    """A clean round with no head recorded by the derivation call (or a malformed one) never
    certifies: `cannot-certify` with `reviewed-head-unrecorded`, and no config, meta or live HEAD
    stands in. Bite-proof: same record (red token: `converged`)."""
    import json as _json
    d = str(tmp_path / "session")
    os.makedirs(d)
    checkout, base = _seed_checkout(d)
    TRD.enter_checkout(checkout)
    head = _git(checkout, "rev-parse", "HEAD").strip()
    state = RD.new_state(TRD._cfg(baseRef=base, headSha=head))
    state["reviewedDiffSha"] = recorded
    with open(os.path.join(d, RD.STATE_FILE), "w", encoding="utf-8") as fh:
        _json.dump(state, fh)
    with open(os.path.join(d, RR.META_FILE), "w", encoding="utf-8") as fh:
        _json.dump({"headSha": head, "repoRoot": checkout, "sessionId": "s-unrecorded"}, fh)
    payload = _drive_existing(d, TRD._responder())
    assert payload["verdict"] == "cannot-certify", payload
    assert "reviewed-head-unrecorded" in payload["certification"]["reason"], payload


@pytest.mark.parametrize("version", [2, 3, 4, 5])
def test_a_pre_v6_no_fix_session_withholds(tmp_path, version):
    """An in-flight session an older driver minted (schema 2–5) recorded no head: a clean finish
    withholds `reviewed-head-unrecorded`; a fresh session recovers (red token: `converged`)."""
    import json as _json
    d = str(tmp_path / "session")
    os.makedirs(d)
    checkout, base = _seed_checkout(d)
    TRD.enter_checkout(checkout)
    state = RD.new_state(TRD._cfg(baseRef=base))
    state["schemaVersion"] = version
    for key in ("reviewedDiffSha", "reviewedDiffDigest", "reviewedDiffHead", "fixFolds"):
        state.pop(key, None)
    with open(os.path.join(d, RD.STATE_FILE), "w", encoding="utf-8") as fh:
        _json.dump(state, fh)
    payload = _drive_existing(d, TRD._responder())
    assert payload["verdict"] == "cannot-certify", payload
    assert "reviewed-head-unrecorded" in payload["certification"]["reason"], payload


def test_a_headless_certificate_is_never_published_with_the_live_head(tmp_path):
    """The sidecar of a converged terminal carries the certificate's head or nothing: a
    certificate naming no head refuses `reviewed-head-unrecorded` (red token: a sidecar
    publishing the live HEAD)."""
    repo, base, _head = _prefix_repo(tmp_path)
    d = str(tmp_path / "session")
    os.makedirs(d)
    state = {"terminal": "converged", "certification": {"shape": "audited-chain"},
             "config": {"repoRoot": repo, "baseRef": base, "baseBranch": "main"},
             "reviewedDiff": ""}
    prepared = RD._prepare_sidecar(d, state)
    assert prepared.get("reason") == "reviewed-head-unrecorded", prepared


_CERT = {"shape": "full-panel-confirmed", "fullPanel": True, "independence": "independent",
         "base": "fetched", "shapeDrivers": []}


@pytest.mark.parametrize("source", ["meta-fix-fold", "config-fix-fold", "meta-head",
                                    "config-head"])
def test_the_writer_binds_a_converged_state_to_the_certificate_head_only(tmp_path, source):
    """Run on its own, the certification writer binds a converged state's evidence to the
    certificate's head and nothing else: with no `certifiedHead`, a fix-fold head, a meta head or
    a config head present in the session never stands in, and the writer refuses
    `certified-head-unresolvable` (red token: a receipt, or any other refusal). The same session
    naming its head certifies, so the head is the only thing withheld."""
    import round_certification as RC
    import round_certification_fixtures as F
    head = F.HEAD_SHA
    meta = {"headSha": head} if source == "meta-head" else {"headSha": ""}
    cfg = {"fixerVendor": "claude", "baseGuard": RC.BASE_GUARD_CHECKED,
           "headSha": head if source == "config-head" else ""}
    if source == "meta-fix-fold":
        meta["fixFoldHeadSha"] = head
    if source == "config-fix-fold":
        cfg["fixFoldHeadSha"] = head
    headless = F.write_certifiable_session(
        tmp_path, name="headless", meta=meta,
        state={"config": cfg, "certification": dict(_CERT, certifiedHead=None)})
    receipt, refusal = RC.certify(headless)
    assert receipt is None, receipt
    assert refusal.get("bindingFailure") == "certified-head-unresolvable", refusal
    named = F.write_certifiable_session(
        tmp_path, name="named", meta=meta,
        state={"config": cfg, "certification": dict(_CERT, certifiedHead=head)})
    receipt, refusal = RC.certify(named)
    assert refusal is None and receipt is not None, refusal


def test_only_the_in_process_leg_certifies_without_a_recorded_head():
    """`run_loop` (no repository) still certifies with no recorded head, and the exemption lives
    only inside it: the same clean state outside `run_loop` withholds (red token: `converged`
    outside the loop, or a loop that no longer converges)."""
    receipt = RD.run_loop(TRD._seams(), TRD._cfg_cert(leg="panel"))
    assert receipt["loopTerminal"] == "converged", receipt
    assert RD._IN_PROCESS_LEG.get() is False
    state = RD.new_state(TRD._cfg(leg="panel"))
    assert state["reviewedDiffSha"] is None
    RD._terminal_converged(state, state["config"], full_panel=True)
    assert state["terminal"] == "cannot-certify", state["certification"]
    assert "reviewed-head-unrecorded" in state["certification"]["reason"]


# The live-HEAD reads each module may hold, by innermost enclosing function, and why none of them
# supplies a certified head. A new read, a second read in a listed function, or a read moved
# elsewhere fails the census below.
_LIVE_HEAD_READS = {
    "round_driver.py": {
        "_hardened_head": 1,              # the one hardened lookup (the derivation's, and verify's)
        "_cmd_relocate_locked": 1,        # currency check: refuses a moved checkout
        "_cmd_re_emit_locked": 1,         # currency check: refuses a moved head
        "resolve": 1,                     # sidecar recovery: proves a repository, names no head
        "_prepare_sidecar": 1,            # repository probe; never a certified head
    },
    "round_certification.py": {},
}


def _innermost_live_head_reads(tree):
    """{innermost function name: count} of calls passing the literals "rev-parse", "HEAD"."""
    counts = {}

    def visit(node, owner):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                visit(child, child.name)
                continue
            if isinstance(child, ast.Call):
                consts = []
                for arg in child.args:
                    elts = arg.elts if isinstance(arg, (ast.List, ast.Tuple)) else [arg]
                    consts += [e.value for e in elts if isinstance(e, ast.Constant)]
                if any(a == "rev-parse" and b == "HEAD" for a, b in zip(consts, consts[1:])):
                    counts[owner] = counts.get(owner, 0) + 1
            visit(child, owner)
    visit(tree, "<module>")
    return counts


def test_no_certified_head_is_read_from_live_head():
    """Invariant census: a certificate names exactly the commit whose diff the panel reviewed, and
    nothing else can supply it. (1) Every live-HEAD read in the driver and the certifier is one of
    the pinned, non-certifying reads. (2) The hardened lookup is called only by the derivation
    call and the verify-head resolver, and the derivation call only by its three sanctioned
    callers. (3) `certifiedHead` has one writer, fed only by `_recorded_review_head`, which reads
    only the pair the derivation recorded. (4) Only `_advance_reviewed_diff` moves the recorded
    SHA after setup.

    Rung: a static AST census over `round_driver.py` and `round_certification.py`. It catches a
    new live-HEAD read, an added read inside a listed function, a new caller of the hardened lookup
    or the derivation call, and a second or re-sourced `certifiedHead` writer. It does not see a
    read reached through dynamic dispatch or a helper in another module; the behavioural tests
    above (setup refusal, the unrecorded-head withhold, the headless sidecar) carry those.
    Bite-proof: `lib/tests/bite_proofs/l4d_armD_stale_diff.md` (red token: a live-HEAD fallback
    re-added at certification fails this census)."""
    trees = {}
    for name in _LIVE_HEAD_READS:
        with open(os.path.join(_LIB, name), encoding="utf-8") as fh:
            trees[name] = ast.parse(fh.read())
    for name, tree in trees.items():
        assert _innermost_live_head_reads(tree) == _LIVE_HEAD_READS[name], name
    rd = trees["round_driver.py"]
    assert _calls_in(rd, "_hardened_head") == {"derive_review_diff",
                                               "_resolve_fix_fold_head_sha"}
    # `_dispatch` holds both the `review-diff` verb and the fresh `next`, whose one derivation
    # feeds the preliminary numstat binding and `_bind_round_diff_head` alike.
    assert _calls_in(rd, "derive_review_diff") == {"_derive_head_diff_from_git", "_dispatch"}
    writers = []
    for fn in ast.walk(rd):
        if not isinstance(fn, ast.FunctionDef):
            continue
        for node in ast.walk(fn):
            if (isinstance(node, ast.Assign) and len(node.targets) == 1
                    and isinstance(node.targets[0], ast.Subscript)
                    and isinstance(node.targets[0].slice, ast.Constant)
                    and node.targets[0].slice.value in ("certifiedHead", "reviewedDiffSha")):
                writers.append((node.targets[0].slice.value, fn.name, ast.unparse(node.value)))
    assert sorted(writers) == [
        ("certifiedHead", "_terminal_converged", "certified_head"),
        ("reviewedDiffSha", "_advance_reviewed_diff", "state.get('headDiffSha')"),
    ], writers
    term = next(fn for fn in ast.walk(rd)
                if isinstance(fn, ast.FunctionDef) and fn.name == "_terminal_converged")
    sources = [ast.unparse(n.value) for n in ast.walk(term) if isinstance(n, ast.Assign)
               and any(isinstance(t, ast.Name) and t.id == "certified_head" for t in n.targets)]
    assert sources == ["_recorded_review_head(state)"], sources
    rec = next(fn for fn in ast.walk(rd)
               if isinstance(fn, ast.FunctionDef) and fn.name == "_recorded_review_head")
    reads = sorted({n.args[0].value for n in ast.walk(rec) if isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Attribute) and n.func.attr == "get" and n.args
                    and isinstance(n.args[0], ast.Constant)})
    # `config` is read only to refuse (a config `diffHead` records no head), never to supply one.
    assert reads == ["config", "reviewedDiffSha"], reads


def test_the_state_schema_versions_have_one_home():
    """The driver, the certification writer and the records layer read one list of supported
    state versions, owned by the leaf `receipt_disclosures` (red token: a hand-kept copy)."""
    import receipt_disclosures
    import round_certification as RC
    assert RD.SUPPORTED_STATE_VERSIONS is receipt_disclosures.SUPPORTED_STATE_VERSIONS
    assert RC.SUPPORTED_STATE_VERSIONS is receipt_disclosures.SUPPORTED_STATE_VERSIONS
    assert RD.STATE_SCHEMA_VERSION == RC.STATE_SCHEMA_VERSION == 6
    assert receipt_disclosures.SUPPORTED_STATE_VERSIONS == (2, 3, 4, 5, 6)
    assert tuple(sorted(RR.SEAT_RESULT_SCHEMA_BY_STATE_VERSION)) == (2, 3, 4, 5, 6)
    for name in ("round_driver.py", "round_certification.py", "round_records.py"):
        with open(os.path.join(_LIB, name), encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        literal = [ast.unparse(n) for n in ast.walk(tree)
                   if isinstance(n, ast.Assign) and any(
                       isinstance(t, ast.Name) and t.id == "SUPPORTED_STATE_VERSIONS"
                       for t in n.targets) and isinstance(n.value, ast.Tuple)]
        assert not literal, (name, literal)


def _derived_state(diff, sha):
    """A fresh state minted with the pair the derivation records, carried the way the CLI's fresh
    `next` carries it (`_DERIVED_DIFF_HEAD`)."""
    token = RD._DERIVED_DIFF_HEAD.set({"sha": sha, "digest": RD.review_diff_digest(diff)})
    try:
        return RD.new_state(TRD._cfg(diff=diff))
    finally:
        RD._DERIVED_DIFF_HEAD.reset(token)


def test_reviewed_bytes_that_are_not_the_derived_ones_never_certify():
    """The recorded digest binds the reviewed bytes to the recorded SHA: bytes that are not the
    ones derived there are stale, and the terminal parks `reviewed-diff-stale` (red token:
    `converged` over bytes nobody derived at that head)."""
    sha = "a" * 40
    diff = "diff --git a/f.py b/f.py\n@@ -0,0 +1 @@\n+x\n"
    state = _derived_state(diff, sha)
    assert RD._reviewed_diff_stale_cause(state) is None
    state["reviewedDiff"] = diff + "+tampered\n"
    assert RD._reviewed_diff_stale_cause(state) == (
        "the reviewed diff is not the diff derived at its recorded head")
    RD._terminal_converged(state, state["config"], full_panel=True)
    assert state["terminal"] == "cannot-certify", state["certification"]
    assert "reviewed-diff-stale" in state["certification"]["reason"]


@pytest.mark.parametrize("digest", ["absent", None, "", "0" * 63, "G" * 64, "mismatched"],
                         ids=["absent", "none", "empty", "short", "not-hex", "mismatched"])
def test_a_recorded_head_without_its_bound_digest_never_certifies(digest):
    """The recorded pair, or nothing: a recorded SHA with no digest, a malformed digest, or
    reviewed bytes that do not hash to it binds no bytes, so the reviewed diff is stale and the
    terminal parks `reviewed-diff-stale`. The same state with the digest of its reviewed bytes is
    current, so only the unbound half is refused (red token: `converged` naming the SHA)."""
    sha = "a" * 40
    diff = "diff --git a/f.py b/f.py\n@@ -0,0 +1 @@\n+x\n"
    state = _derived_state(diff, sha)
    assert RD._reviewed_diff_stale_cause(state) is None
    if digest == "absent":
        state.pop("reviewedDiffDigest", None)
    elif digest == "mismatched":
        state["reviewedDiff"] = diff + "+tampered\n"
    else:
        state["reviewedDiffDigest"] = digest
    assert RD._reviewed_diff_stale_cause(state) == (
        "the reviewed diff is not the diff derived at its recorded head")
    RD._terminal_converged(state, state["config"], full_panel=True)
    assert state["terminal"] == "cannot-certify", state["certification"]
    assert "reviewed-diff-stale" in state["certification"]["reason"]
    assert state["certification"].get("certifiedHead") is None


def test_a_seam_backed_fixer_fold_claims_no_git_provenance(monkeypatch):
    """Only the real git derivation earns `git-derived`: a head-diff seam (the eval harness's
    scripted replay) performs no git operation, so the round records no source — while the git
    branch of the same fold still records it (red token: `git-derived` on a seam fold)."""
    monkeypatch.setattr(RD, "_enter_post_fix", lambda state, config, session_dir=None: None)
    subjects = lambda reviewed, head, findings: ["Code"]  # noqa: E731

    def fold(**kw):
        state = {"round": 2, "rounds": {}, "decisions": [], "_fixBatch": [{"id": "a"}],
                 "_fixBatchIndex": 0}
        RD._fold_fixer(state, {"fixerVendor": "claude"}, {"fixes": []}, subjects, **kw)
        return state

    seamed = fold(head_diff_seam=lambda state: "diff --git a/x b/x\n")
    assert seamed["headDiff"] == "diff --git a/x b/x\n"
    assert "reviewedDiffSource" not in seamed["rounds"]["2"], seamed["rounds"]["2"]
    monkeypatch.setattr(RD, "_derive_head_diff_from_git",
                        lambda session_dir, state: "diff --git a/x b/x\n")
    derived = fold()
    assert derived["rounds"]["2"].get("reviewedDiffSource") == "git-derived"


@pytest.mark.parametrize("version", [2, 3, 4, 5, 6])
def test_reviewed_diff_source_rides_only_v6_receipts(version):
    """A state minted before version 6 keeps the receipt shape its schema identifier names: no
    `reviewedDiffSource` key in either receipt builder's round entries; a v6 state carries it
    (red token: the key on a v2–5 round entry)."""
    import round_certification as RC
    state = RD.new_state(TRD._cfg())
    state["schemaVersion"] = version
    state["rounds"] = {"1": {"roundKind": "full", "reviewedDiffSource": "git-derived"}}
    driver_rounds = RD.build_receipt(state)["rounds"]
    writer_rounds = RC._build_receipt_rounds(state, RD.RECEIPT_FORM_CERTIFIED)
    for rounds in (driver_rounds, writer_rounds):
        assert len(rounds) == 1, rounds
        if version >= 6:
            assert rounds[0]["reviewedDiffSource"] == "git-derived", rounds
        else:
            assert "reviewedDiffSource" not in rounds[0], rounds


def test_the_first_round_binding_reads_the_hardened_git_config(tmp_path, capsys, monkeypatch):
    """The fresh `next` preliminary binding recomputes its numstat under the same hardening as
    `derive_review_diff`: an inherited `GIT_CONFIG_*` that turns rename detection off cannot make
    it disagree with a rename-form review diff (red token: `round-diff-base-mismatch`)."""
    import json as _json
    d = str(tmp_path)
    argv = TRD._guard_argv(d)
    repo = argv[1]
    base = _git(repo, "rev-parse", "HEAD").strip()
    meta_path = os.path.join(d, RR.META_FILE)
    with open(meta_path, encoding="utf-8") as fh:
        meta = _json.load(fh)
    meta["baseRef"] = base
    with open(meta_path, "w", encoding="utf-8") as fh:
        _json.dump(meta, fh)
    _git(repo, "mv", "f.py", "g.py")
    _git(repo, "commit", "-qm", "rename")
    _sha, text, refusal = RD.derive_review_diff(repo, base)
    assert refusal is None and "rename from f.py" in text, text
    with open(os.path.join(d, "round-1", "diff.txt"), "w", encoding="utf-8") as fh:
        fh.write(text)
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "diff.renames")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "false")
    rc, out = TRD._cli_next_json(d, argv, capsys)
    assert rc == 0 and out.get("ok"), out


def test_a_supplied_diff_head_never_reaches_the_certificate(tmp_path):
    """Only the derivation call records the reviewed head. The in-process `cmd_next` refuses a
    config `diffHead` with `diff-head-not-derived` and writes no state; `new_state` given one
    records no pair and keeps no config copy, so the clean terminal withholds
    `reviewed-head-unrecorded` and the certificate names no head (red tokens: `ok: True` from
    `cmd_next`, or `converged` naming the supplied SHA)."""
    supplied = {"sha": "a" * 40, "digest": RD.review_diff_digest("diff --git a/f b/f\n")}
    d = str(tmp_path / "session")
    os.makedirs(d)
    out = RD.cmd_next(d, TRD._cfg(diff="diff --git a/f b/f\n", diffHead=supplied))
    assert out.get("ok") is False and out.get("reason") == "diff-head-not-derived", out
    assert not os.path.exists(os.path.join(d, RD.STATE_FILE))
    state = RD.new_state(TRD._cfg(diff="diff --git a/f b/f\n", diffHead=supplied))
    assert state["reviewedDiffSha"] is None and state["reviewedDiffDigest"] is None, state
    assert "diffHead" not in state["config"]
    RD._terminal_converged(state, state["config"], full_panel=True)
    assert state["terminal"] == "cannot-certify", state["certification"]
    assert "reviewed-head-unrecorded" in state["certification"]["reason"]
    assert state["certification"].get("certifiedHead") is None


def test_a_resumed_state_carrying_a_config_diff_head_never_certifies(tmp_path):
    """A session saved by the earlier driver kept a config `diffHead` beside the pair it copied
    from it; the pair cannot be told from a caller-supplied one. Resumed, its clean finish
    withholds `reviewed-head-unrecorded` and names no head, even though the pair is well-formed
    and binds the reviewed bytes (red token: `converged` naming the supplied SHA)."""
    import json as _json
    d = str(tmp_path / "session")
    os.makedirs(d)
    checkout, base = _seed_checkout(d)
    TRD.enter_checkout(checkout)
    head = _git(checkout, "rev-parse", "HEAD").strip()
    state = RD.new_state(TRD._cfg(baseRef=base, headSha=head))
    reviewed = state["reviewedDiff"]
    assert isinstance(reviewed, str), state
    pair = {"sha": head, "digest": RD.review_diff_digest(reviewed)}
    state["config"]["diffHead"] = pair
    state["reviewedDiffSha"], state["reviewedDiffDigest"] = pair["sha"], pair["digest"]
    with open(os.path.join(d, RD.STATE_FILE), "w", encoding="utf-8") as fh:
        _json.dump(state, fh)
    with open(os.path.join(d, RR.META_FILE), "w", encoding="utf-8") as fh:
        _json.dump({"headSha": head, "repoRoot": checkout, "sessionId": "s-config-head"}, fh)
    payload = _drive_existing(d, TRD._responder())
    assert payload["verdict"] == "cannot-certify", payload
    assert "reviewed-head-unrecorded" in payload["certification"]["reason"], payload
    assert payload["certification"].get("certifiedHead") is None
