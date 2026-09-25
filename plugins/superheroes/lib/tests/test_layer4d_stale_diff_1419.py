"""C13 layer 4d (#1419), part (i): a panel is never dispatched over a diff older than its head.

When a fixer lands with no post-fix head diff, the driver derives `git diff <baseRef>...<head>`
itself and the full panel reviews that; when it cannot, it parks `reviewed-diff-stale` instead of
dispatching a panel over the pre-fix diff."""
import ast
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import round_records as RR  # noqa: E402
import session_checkout  # noqa: E402
import test_round_driver as TRD  # noqa: E402

RD = TRD.RD


def _git(path, *args):
    return session_checkout._git(path, *args).stdout


def _expected_diff(checkout, base, head):
    return _git(checkout, "diff", *RD._GIT_DIFF_FORMAT_FLAGS, "%s...%s" % (base, head))


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
            with open(os.path.join(checkout, "f.py"), "w", encoding="utf-8") as fh:
                fh.write("new\nmore\nfixed\n")
            _git(checkout, "commit", "-qam", "fix")
            return {"fixes": [], "headDiffPath": missing, "changedSubjects": ["Code"]}
        if phase == RD.P_VERIFY:
            return {"result": "pass"}
        if phase == RD.P_SCOPED:
            seen["scoped"] = True
            return {"findings": []}
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
    assert any(r.get("reviewedDiffSource") == RD.REVIEWED_DIFF_SOURCE_GIT for r in rounds), rounds


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
    assert RD.REVIEWED_DIFF_STALE in (payload["certification"] or {}).get("reason", ""), payload


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


def test_only_the_guarded_entry_schedules_a_panel_after_round_one():
    """Invariant census: after round 1, the one place that sets the step to the panel is
    `_enter_panel` (the stale guard). `_seed_resume` is the fresh-session resume, whose reviewed
    diff is the session's own bound diff and never stale. A new bypassing entry fails here."""
    with open(os.path.join(_LIB, "round_driver.py"), encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    owners = set()
    for fn in ast.walk(tree):
        if not isinstance(fn, ast.FunctionDef):
            continue
        for node in ast.walk(fn):
            if (isinstance(node, ast.Assign) and isinstance(node.value, ast.Name)
                    and node.value.id == "P_PANEL"
                    and any(isinstance(t, ast.Subscript)
                            and isinstance(t.slice, ast.Constant) and t.slice.value == "step"
                            for t in node.targets)):
                owners.add(fn.name)
    assert owners == {"_enter_panel", "_seed_resume"}, owners


def test_a_known_head_diff_clears_the_stale_marker():
    state = {"reviewedDiff": "old", "headDiff": "diff --git a/x b/x\n", "_reviewedDiffStale": True}
    RD._advance_reviewed_diff(state)
    assert state["reviewedDiff"] == "diff --git a/x b/x\n" and "_reviewedDiffStale" not in state
    state = {"reviewedDiff": "old", "headDiff": None, "_reviewedDiffStale": True}
    RD._advance_reviewed_diff(state)
    assert state["reviewedDiff"] == "old" and state["_reviewedDiffStale"] is True
    state = {"reviewedDiff": "old", "headDiff": "", "_reviewedDiffStale": False}
    RD._advance_reviewed_diff(state)
    assert state["reviewedDiff"] == "" and "_reviewedDiffStale" not in state


def test_known_empty_head_diff_rearm_panel_reviews_the_empty_diff(tmp_path, monkeypatch):
    """A fixer that hands back a known-empty head diff (`headDiff: ""`) is not stale; the
    cross-cutting confirmation re-arm's full panel then reviews that empty diff, never the
    pre-fix round-1 diff (red token: the re-armed panel's diff.txt equals the round-1 diff)."""
    d = str(tmp_path / "session")
    os.makedirs(d)
    checkout, base = _seed_checkout(d)
    seen = {}
    base_respond = TRD._responder(round1_findings=[
        {"title": "bug", "severity": "Important", "file": "f.py", "line": 1}])

    def respond(phase, payload, rnd):
        if phase == RD.P_PANEL:
            seen.setdefault("panels", []).append(rnd)
        if phase == RD.P_FIXER:
            # The head moves, but its tree matches the base: the post-fix diff is known-empty.
            with open(os.path.join(checkout, "f.py"), "w", encoding="utf-8") as fh:
                fh.write("new\nmore\nfixed\n")
            _git(checkout, "commit", "-qam", "fix")
            _git(checkout, "revert", "--no-edit", "HEAD")
            return {"fixes": [], "headDiff": ""}
        return base_respond(phase, payload, rnd)

    monkeypatch.setattr(RD, "derive_changed_subjects",
                        lambda reviewed, head, findings: ["Code", "Security", "Test"])
    TRD._drive_cli(d, TRD._cfg(baseRef=base), respond)
    panels = seen.get("panels") or []
    assert len(panels) >= 2 and panels[0] == 1, seen
    with open(os.path.join(RR.round_dir(d, 1), "diff.txt"), encoding="utf-8") as fh:
        assert fh.read() != ""
    with open(os.path.join(RR.round_dir(d, panels[1]), "diff.txt"), encoding="utf-8") as fh:
        assert fh.read() == "", "the re-armed panel reviewed the pre-fix diff"


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
    assert state["rounds"]["2"].get("reviewedDiffSource") == RD.REVIEWED_DIFF_SOURCE_GIT
    state["_fixBatchIndex"] = 1
    state["_fixBatch"] = [{"id": "b"}]
    RD._fold_fixer(state, {"fixerVendor": "claude"}, second_artifact, seam)
    return state


def test_a_later_inline_slice_clears_git_derived_provenance(monkeypatch):
    """Derived-then-inline: the final head diff is the inline one, so the round carries no
    `git-derived` provenance (red token: `reviewedDiffSource == "git-derived"` survives)."""
    inline = "diff --git a/y b/y\n"
    state = _fold_two_slices(monkeypatch, "diff --git a/x b/x\n", {"fixes": [], "headDiff": inline})
    assert state["headDiff"] == inline
    assert "reviewedDiffSource" not in state["rounds"]["2"], state["rounds"]["2"]


def test_a_later_underivable_slice_clears_git_derived_provenance(monkeypatch):
    """Derived-then-underivable: the final head is unknown (stale), so no `git-derived` claim."""
    state = _fold_two_slices(monkeypatch, "diff --git a/x b/x\n", {"fixes": []})
    assert state["headDiff"] is None and state["_reviewedDiffStale"] is True
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


def _rewrite_legacy(session_dir, mutate):
    """Rewrite the persisted state into the shape the pre-marker driver left: no stale marker."""
    import json
    path = os.path.join(session_dir, RD.STATE_FILE)
    with open(path, encoding="utf-8") as fh:
        state = json.load(fh)
    assert state.get("_reviewedDiffStale") is True and state.get("headDiff") is None, state
    state.pop("_reviewedDiffStale")
    mutate(state)
    RD.save_state(session_dir, state)


def _stale_legacy_session(tmp_path):
    d = str(tmp_path / "session")
    os.makedirs(d)
    checkout, _base = _seed_checkout(d)
    seen = {}
    respond = _respond(checkout, str(tmp_path / "missing.txt"), seen)
    _drive_to_post_fix_verify(d, TRD._cfg(), respond)
    return d, respond, seen


def test_persisted_pre_marker_state_at_the_panel_parks_stale(tmp_path):
    """A pre-marker state persisted at the panel step (the old verify fold set it directly) over the
    pre-fix diff parks `reviewed-diff-stale` on load, never emitting the panel (red token: `next`
    answers `dispatch-panel` for round 2)."""
    d, _respond_fn, seen = _stale_legacy_session(tmp_path)

    def at_panel(state):
        state["step"] = RD.P_PANEL
        state["pending"] = None
        state.pop("_verifyThen", None)
    _rewrite_legacy(d, at_panel)
    n = RD.cmd_next(d)
    assert n["ok"] and n["action"] == RD.P_TERMINAL, n
    assert n["payload"]["verdict"] == "cannot-certify", n
    assert RD.REVIEWED_DIFF_STALE in n["payload"]["certification"]["reason"], n
    assert seen.get("panels") == [1], seen


def test_persisted_pre_marker_state_at_verify_parks_stale(tmp_path):
    """A pre-marker state persisted at the verify gate bound for the panel parks at the gate's fold
    (red token: a round-2 panel runs)."""
    d, respond, seen = _stale_legacy_session(tmp_path)
    _rewrite_legacy(d, lambda state: None)
    payload = TRD._drive_cli(d, None, respond)
    assert payload["verdict"] == "cannot-certify", payload
    assert RD.REVIEWED_DIFF_STALE in payload["certification"]["reason"], payload
    assert seen.get("panels") == [1], seen


def test_known_head_state_without_marker_is_not_stale():
    assert not RD._reviewed_diff_stale({"_headDiffSource": "unknown", "headDiff": "diff --git x"})
    assert not RD._reviewed_diff_stale({"headDiff": None})
    assert RD._reviewed_diff_stale({"_headDiffSource": "unknown", "headDiff": None})
    assert not RD._reviewed_diff_stale(
        {"_headDiffSource": "unknown", "headDiff": None, "_reviewedDiffStale": False})
