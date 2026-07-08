import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import dispatch_census


# A calibration that routes review→codex, build/fix→cursor, plan authoring→codex, with the doc
# panels + ship fixer native-by-design (as the honest readout renders them, #299).
def _external_rows():
    return [
        {"phase": "plan", "role": "author-plan", "kind": "author-plan", "engine": "codex", "model": "opus"},
        {"phase": "review-plan", "role": "reviewer", "kind": "review-native", "engine": "claude",
         "model": "sonnet", "nativeByDesign": True},
        {"phase": "workhorse", "role": "builder", "kind": "build", "engine": "cursor", "model": "opus"},
        {"phase": "workhorse", "role": "reviewer", "kind": "review", "engine": "codex", "model": "sonnet"},
        {"phase": "workhorse", "role": "fixer", "kind": "fix", "engine": "cursor", "model": "sonnet"},
        {"phase": "workhorse", "role": "reviewer-deep", "kind": "review-deep", "engine": "codex", "model": "opus"},
        {"phase": "ship", "role": None, "kind": "ship-fix-native", "engine": "claude", "model": "opus",
         "nativeByDesign": True},
    ]


_ALLOWED = ["haiku", "sonnet", "opus"]


def _matching_census(**over):
    census = {
        "expected_rows": _external_rows(),
        "external_dispatches": [
            {"engine": "codex", "roleKind": "author-plan", "outcome": "ok"},
            {"engine": "cursor", "roleKind": "build", "outcome": "ok"},
            {"engine": "codex", "roleKind": "review", "outcome": "ok"},
            {"engine": "cursor", "roleKind": "fix", "outcome": "ok"},
        ],
        "by_model": {"workhorse": {"haiku": 5, "sonnet": 2, "opus": 1}, "ship": {"haiku": 1, "opus": 1}},
        "traversed_phases": ["plan", "review-plan", "workhorse", "ship"],
        "allowed_models": _ALLOWED,
        "fable_allowed": False,
    }
    census.update(over)
    return census


def test_matching_run_passes():
    out = dispatch_census.decide(_matching_census())
    assert out["ok"] is True, out["failures"]
    assert out["failures"] == []


def test_missing_engine_evidence_fails_naming_engine_and_role():
    # The calibration routes review→codex and build/fix→cursor but the run journaled NO external
    # dispatches (the silent all-Claude fall-open #299 exists to catch).
    out = dispatch_census.decide(_matching_census(external_dispatches=[]))
    assert out["ok"] is False
    joined = " ".join(out["failures"])
    assert "codex" in joined and "review" in joined            # names the engine + roleKind
    assert "cursor" in joined and "build" in joined
    assert any("silent fall-open" in f for f in out["failures"])


def test_journaled_fall_open_reason_tolerated():
    # A codex review that ran but honestly failed (unreadable) leaves a journaled reason — visible,
    # so it is NOT a silent fall-open. The review roleKind is satisfied by the reasoned dispatch.
    census = _matching_census(external_dispatches=[
        {"engine": "codex", "roleKind": "author-plan", "outcome": "ok"},
        {"engine": "cursor", "roleKind": "build", "outcome": "ok"},
        {"engine": "codex", "roleKind": "review", "outcome": "unreadable"},  # journaled fall-open
        {"engine": "cursor", "roleKind": "fix", "outcome": "ok"},
    ])
    out = dispatch_census.decide(census)
    assert out["ok"] is True, out["failures"]


def test_unexpected_model_fails_naming_phase_and_model():
    census = _matching_census(by_model={"workhorse": {"haiku": 5, "gpt-4o": 1}})
    out = dispatch_census.decide(census)
    assert out["ok"] is False
    assert any("gpt-4o" in f and "workhorse" in f for f in out["failures"])


def test_fable_in_census_fails_when_not_configured():
    census = _matching_census(by_model={"workhorse": {"opus": 1, "fable": 1}}, fable_allowed=False)
    out = dispatch_census.decide(census)
    assert out["ok"] is False
    assert any("Fable" in f and "workhorse" in f for f in out["failures"])


def test_fable_allowed_when_explicitly_configured():
    # A profile that explicitly pins a role to fable makes fable a legitimate census member.
    census = _matching_census(by_model={"workhorse": {"fable": 1}},
                              allowed_models=_ALLOWED + ["fable"], fable_allowed=True)
    out = dispatch_census.decide(census)
    assert out["ok"] is True, out["failures"]


def test_fable_fails_even_if_readout_row_shows_it_without_config():
    # #299 Phase 3a "regardless of readout rows": a buggy expected row showing fable cannot launder a
    # fable dispatch when the config never authorized it.
    rows = _external_rows()
    rows[2]["model"] = "fable"  # a (hypothetical) buggy builder row
    census = _matching_census(expected_rows=rows, by_model={"workhorse": {"fable": 1}},
                              allowed_models=_ALLOWED + ["fable"], fable_allowed=False)
    out = dispatch_census.decide(census)
    assert out["ok"] is False
    assert any("Fable" in f for f in out["failures"])


def test_all_claude_calibration_passes():
    # No external rows at all → nothing to prove on the engine axis; byModel stays within the set.
    rows = [
        {"phase": "plan", "role": "author-plan", "kind": "author-plan", "engine": "claude", "model": "opus"},
        {"phase": "workhorse", "role": "builder", "kind": "build", "engine": "claude", "model": "opus"},
        {"phase": "ship", "role": None, "kind": "ship-fix-native", "engine": "claude", "model": "opus",
         "nativeByDesign": True},
    ]
    census = {"expected_rows": rows, "external_dispatches": [],
              "by_model": {"workhorse": {"haiku": 3, "sonnet": 1, "opus": 1}},
              "traversed_phases": ["plan", "workhorse", "ship"], "allowed_models": _ALLOWED,
              "fable_allowed": False}
    out = dispatch_census.decide(census)
    assert out["ok"] is True, out["failures"]


def test_native_by_design_row_never_demands_external_evidence():
    # A doc-panel / ship row that (via a run-override edge) carries an external engine is still native
    # at dispatch — nativeByDesign means no external evidence is owed, so no false failure.
    rows = _external_rows()
    rows[1]["engine"] = "codex"  # review-native row forced to codex by an override, still nativeByDesign
    census = _matching_census(expected_rows=rows)
    out = dispatch_census.decide(census)
    assert out["ok"] is True, out["failures"]


def test_untraversed_phase_not_asserted():
    # If the run parked before workhorse, its external builder/reviewer rows are not owed evidence.
    census = _matching_census(external_dispatches=[
        {"engine": "codex", "roleKind": "author-plan", "outcome": "ok"}],
        traversed_phases=["plan"])
    out = dispatch_census.decide(census)
    assert out["ok"] is True, out["failures"]


def test_empty_traversed_asserts_nothing():
    # An unknown/empty traversal set must not force every external row to be proven (F2): the shell
    # treats a journal with no dispatch evidence as its own failure, so the decider stays quiet here.
    census = _matching_census(external_dispatches=[], traversed_phases=[])
    out = dispatch_census.decide(census)
    assert out["ok"] is True, out["failures"]


def test_conditional_fix_leg_not_required():
    # A clean run: the builder + reviewers dispatch externally, but the fixer never runs (no blockers
    # found) — so there is NO (cursor, fix) external_dispatch. That must NOT read as a fall-open.
    census = _matching_census(external_dispatches=[
        {"engine": "codex", "roleKind": "author-plan", "outcome": "ok"},
        {"engine": "cursor", "roleKind": "build", "outcome": "ok"},
        {"engine": "codex", "roleKind": "review", "outcome": "ok"},
        # deliberately NO (cursor, fix)
    ])
    out = dispatch_census.decide(census)
    assert out["ok"] is True, out["failures"]


def test_missing_build_not_excused_by_a_review_reason():
    # F3: a journaled reason is keyed on (engine, roleKind) — a reasoned review must NOT excuse a
    # missing unconditional build leg.
    census = _matching_census(external_dispatches=[
        {"engine": "codex", "roleKind": "review", "outcome": "unreadable"}])  # review reasoned only
    out = dispatch_census.decide(census)
    assert out["ok"] is False
    assert any("build" in f for f in out["failures"])


def test_fallback_to_claude_row_skipped():
    # An unauthorized engine row (readout already showed the fall-open) owes no external evidence.
    rows = _external_rows()
    for r in rows:
        if r.get("engine") == "codex":
            r["fallbackToClaude"] = True
    census = _matching_census(expected_rows=rows, external_dispatches=[
        {"engine": "cursor", "roleKind": "build", "outcome": "ok"},
        {"engine": "cursor", "roleKind": "fix", "outcome": "ok"}])
    out = dispatch_census.decide(census)
    assert out["ok"] is True, out["failures"]


def test_non_dict_input_is_safe():
    out = dispatch_census.decide(None)
    assert out["ok"] is True and out["failures"] == []
