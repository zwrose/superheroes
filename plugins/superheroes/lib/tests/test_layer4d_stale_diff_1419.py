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
