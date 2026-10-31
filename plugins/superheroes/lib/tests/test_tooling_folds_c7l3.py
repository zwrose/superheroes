"""The loop's tooling folds: a reused run dir never replays another prompt's result, a malformed
live cell is skipped rather than crashing, and the grouping (synthesis) pass can sit on codex.

Edges: p1 same prompt continues · p2 different prompt refuses in dispatch-review · p3 different
prompt refuses in dispatch-write · p4 a journal with no prompt hash is unchanged · p5 an unreadable
prompt is left to the caller's own handling · m1 an unhashable effort is skipped by every caller ·
m2 a well-formed sibling cell is still used · m3 `same_family_degradations` keeps its fail-closed
result · g1 a Claude-built PR's grouping pass seats on codex when the map proves that cell ·
g2 with no proven codex cell it stays unseatable.

The touched-test gate's one-hop selection is tested in
`.github/scripts/tests/test_verify_touched_tests.py`.

Bite-proof record: plugins/superheroes/lib/tests/bite_proofs/c7l3_wo4_tooling.md
"""
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import model_registry as MR  # noqa: E402
import receipt_disclosures as RDISC  # noqa: E402
import seat_map as SM  # noqa: E402
import test_engine_dispatch as TED  # noqa: E402
import test_engine_dispatch_write as TEDW  # noqa: E402

ED = TED.ED
PROMPT_A = "Review this code.\n"
PROMPT_B = "Review some other code entirely.\n"


@pytest.fixture(autouse=True)
def _pin_dispatch_temp_roots(tmp_path, monkeypatch):
    """The imported suites' own autouse pins, for the dispatch modules they load."""
    base = str(tmp_path / "temp-base")
    os.makedirs(base, exist_ok=True)
    journal_root = str(tmp_path / "dispatch-journal-root")
    os.makedirs(journal_root, exist_ok=True)
    # the fixture repos commit with their own identity; a machine-wide signing setup must not apply
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setattr(TED._SV_MOD.tempfile, "gettempdir", lambda: base)
    for module in (TED.ED, TEDW.ED):
        monkeypatch.setattr(module.tempfile, "gettempdir", lambda: base)
        monkeypatch.setenv(module.JOURNAL_ROOT_ENV, journal_root)
    real_which = TEDW.ED.shutil.which
    monkeypatch.setattr(
        TEDW.ED.shutil, "which",
        lambda cmd, *a, **k: None if cmd == "uv" else real_which(cmd, *a, **k),
    )


# --- run-dir replay: p1 / p2 / p3 / p4 / p5 ----------------------------------------------------

def _review(tmp_path, run_dir, prompt, runner=None, max_wait=0):
    return TED.ED.dispatch_review(
        seat=TED._codex_seat(),
        prompt_path=TED._valid_prompt(tmp_path, prompt),
        repo_root=TED._repo(tmp_path),
        run_engine=runner or TED.FakeRunner([]),
        build_view=TED._fake_build_view(tmp_path),
        run_dir=run_dir, max_wait=max_wait, order_id="order-prompt",
    )


def _write(tmp_path, wt, run_dir, prompt, runner=None, max_wait=0):
    return TEDW.ED.dispatch_write(
        seat=TEDW._codex_seat(), cwd=wt, run_dir=run_dir, order_id="order-prompt",
        prompt_path=TEDW._prompt(tmp_path, prompt),
        run_engine=runner or TEDW.FakeRunner([]), max_wait=max_wait,
    )


def test_p2b_review_completed_run_replays_only_for_the_same_prompt(tmp_path):
    run_dir = str(tmp_path / "stored-review")
    runner = TED.FakeRunner([(TED._CODEX_FINDINGS_STDOUT, False, 0, "")])
    first = _review(tmp_path, run_dir, PROMPT_A, runner=runner, max_wait=60)
    assert first["ok"] is True and first["terminal"] is True
    assert len(runner.calls) == 1
    other = _review(tmp_path, run_dir, PROMPT_B, runner=runner, max_wait=60)
    assert other["detail"] == ED.PROMPT_REFUSAL_RUN_DIR_MISMATCH
    assert other["attempts"] == 0
    assert len(runner.calls) == 1
    same = _review(tmp_path, run_dir, PROMPT_A, runner=runner, max_wait=60)
    assert same["ok"] is True and same["terminal"] is True
    assert len(runner.calls) == 1


def test_p3b_write_completed_run_replays_only_for_the_same_prompt(tmp_path):
    wt, _main = TEDW._linked_worktree(tmp_path)
    run_dir = str(tmp_path / "stored-write")
    runner = TEDW.FakeRunner([(TEDW._build_ok_stdout(), False, 0, "")])
    first = _write(tmp_path, wt, run_dir, "Build this.\n", runner=runner, max_wait=60)
    assert first["ok"] is True and first["terminal"] is True
    assert len(runner.calls) == 1
    other = _write(tmp_path, wt, run_dir, "Build something else.\n", runner=runner, max_wait=60)
    assert other["detail"] == ED.PROMPT_REFUSAL_RUN_DIR_MISMATCH
    assert other["attempts"] == 0
    assert len(runner.calls) == 1
    same = _write(tmp_path, wt, run_dir, "Build this.\n", runner=runner, max_wait=60)
    assert same["ok"] is True and same["terminal"] is True
    assert len(runner.calls) == 1


def test_p1_review_continuation_with_the_same_prompt_is_not_refused(tmp_path):
    run_dir = str(tmp_path / "same-prompt")
    _review(tmp_path, run_dir, PROMPT_A)
    second = _review(tmp_path, run_dir, PROMPT_A)
    assert second.get("detail") != ED.PROMPT_REFUSAL_RUN_DIR_MISMATCH


def test_p2_review_continuation_with_a_different_prompt_refuses_and_never_launches(tmp_path):
    # axis: dispatch-review continuation under a different prompt — see bite-proof record c7l3_wo4_tooling
    run_dir = str(tmp_path / "other-prompt")
    _review(tmp_path, run_dir, PROMPT_A)
    runner = TED.FakeRunner([])
    res = _review(tmp_path, run_dir, PROMPT_B, runner=runner)
    assert res["detail"] == ED.PROMPT_REFUSAL_RUN_DIR_MISMATCH == "run-dir-prompt-mismatch"
    assert res["reason"] == "unrunnable"
    assert res["attempts"] == 0
    assert runner.calls == []


def test_p3_write_continuation_with_a_different_prompt_refuses_and_never_launches(tmp_path):
    # axis: dispatch-write continuation under a different prompt — see bite-proof record c7l3_wo4_tooling
    wt, _main = TEDW._linked_worktree(tmp_path)
    run_dir = str(tmp_path / "write-other-prompt")
    _write(tmp_path, wt, run_dir, "Build this.\n")
    runner = TEDW.FakeRunner([])
    res = _write(tmp_path, wt, run_dir, "Build something else.\n", runner=runner)
    assert res["detail"] == ED.PROMPT_REFUSAL_RUN_DIR_MISMATCH
    assert res["reason"] == "unrunnable"
    assert res["attempts"] == 0
    assert runner.calls == []


def test_p3_write_continuation_with_the_same_prompt_is_not_refused(tmp_path):
    wt, _main = TEDW._linked_worktree(tmp_path)
    run_dir = str(tmp_path / "write-same-prompt")
    _write(tmp_path, wt, run_dir, "Build this.\n")
    second = _write(tmp_path, wt, run_dir, "Build this.\n")
    assert second.get("detail") != ED.PROMPT_REFUSAL_RUN_DIR_MISMATCH


def test_p4_a_journal_with_no_prompt_hash_is_never_refused():
    assert ED._continuation_prompt_mismatch({}, PROMPT_A) is None
    assert ED._continuation_prompt_mismatch({"basePromptSha256": None}, PROMPT_A) is None
    assert ED._continuation_prompt_mismatch({"basePromptSha256": ""}, PROMPT_A) is None


def test_p5_an_unreadable_prompt_is_left_to_the_callers_handling():
    opened = {"basePromptSha256": "0" * 64}
    assert ED._continuation_prompt_mismatch(opened, None) is None
    assert ED._continuation_prompt_mismatch(opened, PROMPT_A) == ED.PROMPT_REFUSAL_RUN_DIR_MISMATCH


# --- a malformed live cell: m1 / m2 / m3 --------------------------------------------------------

_GOOD = ["codex", "gpt-6.1-sol", "xhigh"]
_UNHASHABLE_EFFORTS = [["high"], {"e": 1}]
_CONFIG = {"vendors": ["claude", "codex"]}


def _cell_map(*cells):
    return {"nonPanelLiveCells": [list(c) for c in cells], "nonPanelLiveCellsSource": "probed"}


@pytest.mark.parametrize("effort", _UNHASHABLE_EFFORTS, ids=["list", "dict"])
def test_m1_the_chokepoint_returns_none_for_a_non_string_effort(effort):
    # axis: a malformed effort never reaches a set as an unhashable triple — see bite-proof record c7l3_wo4_tooling
    assert SM._normalize_live_cell(["codex", "gpt-6.1-sol", effort]) is None
    assert SM._normalize_live_cell(_GOOD) == ("codex", "gpt-6.1-sol", "xhigh")
    assert SM._normalize_live_cell(["codex", "gpt-6.1-sol", None]) == ("codex", "gpt-6.1-sol", None)


@pytest.mark.parametrize("effort", _UNHASHABLE_EFFORTS, ids=["list", "dict"])
def test_m1_m2_nonpanel_cell_proven_skips_the_malformed_cell_and_uses_the_sibling(effort):
    bad = ["codex", "gpt-6.1-sol", effort]
    assert RDISC.nonpanel_cell_proven(_CONFIG, _cell_map(bad), "codex", "verifier") is False
    assert RDISC.nonpanel_cell_proven(_CONFIG, _cell_map(bad, _GOOD), "codex", "reviewer-deep") is True


@pytest.mark.parametrize("effort", _UNHASHABLE_EFFORTS, ids=["list", "dict"])
def test_m1_m2_nonpanel_candidates_skips_the_malformed_cell_and_uses_the_sibling(effort):
    bad = ["cursor", "cursor-grok-4.6", effort]
    good = ["cursor", "cursor-grok-4.6", "xhigh"]
    assert "cursor" not in RDISC.nonpanel_candidates(_CONFIG, _cell_map(bad), "reviewer-deep")
    assert "cursor" in RDISC.nonpanel_candidates(_CONFIG, _cell_map(bad, good), "reviewer-deep")


@pytest.mark.parametrize("effort", _UNHASHABLE_EFFORTS, ids=["list", "dict"])
def test_m1_m2_build_skips_the_malformed_cell_and_uses_the_sibling(effort):
    seat_map = SM.build(
        SM.PANEL_ROSTER, ["claude", "codex"], "anthropic", 0,
        live_cells=[["claude", "opus-5.5", "xhigh"], ["codex", "gpt-6.1-sol", effort], _GOOD],
        live_cells_source="probed",
    )
    assert ["codex", "gpt-6.1-sol", "xhigh"] in seat_map["liveCells"]
    assert all(isinstance(cell[2], (str, type(None))) for cell in seat_map["liveCells"])


@pytest.mark.parametrize("effort", _UNHASHABLE_EFFORTS, ids=["list", "dict"])
def test_m1_m3_same_family_degradations_keeps_its_fail_closed_result(effort):
    seat_map = SM.build(
        SM.PANEL_ROSTER, ["claude", "codex"], "anthropic", 0,
        live_cells=[["claude", "opus-5.5", "xhigh"], _GOOD], live_cells_source="probed",
    )
    seat_map["liveCells"] = list(seat_map["liveCells"]) + [["codex", "gpt-6.1-sol", effort]]
    seat = next(s for s in SM.PANEL_ROSTER if isinstance(seat_map["seats"].get(s), dict))
    cfg = seat_map["seats"][seat]
    # a map with any malformed live cell is unusable evidence: the existing `None`
    assert SM._resolvable_families_for_seat(seat_map, seat, cfg) is None
    assert isinstance(SM.same_family_degradations(seat_map, "anthropic"), list)


# --- the codex grouping cell: g1 / g2 ----------------------------------------------------------

def test_the_registry_lists_a_codex_synthesis_cell_on_the_panels_model():
    assert MR.matrix_config("synthesis", "codex") == ("gpt-6.1-sol", "high")
    assert MR.matrix_config("synthesis", "cursor") is None


def _claude_built_map(*cells):
    seat_map = _cell_map(["claude", "opus-5.5", "high"], *cells)
    seat_map.update({"hostFamily": "anthropic", "makerFamilies": ["anthropic"]})
    return seat_map


def test_g1_a_claude_built_prs_grouping_pass_seats_on_codex_when_the_map_proves_the_cell():
    seat_map = _claude_built_map(["codex", "gpt-6.1-sol", "high"])
    vendor, family = RDISC.nonpanel_reviewer(
        _CONFIG, seat_map, "synthesis", "codex",
        maker_families=frozenset({"anthropic"}), fixer_vendor="cursor",
    )
    assert (vendor, family) == ("codex", "openai")


def test_g2_with_no_proven_codex_cell_the_grouping_pass_stays_unseatable():
    seat_map = _claude_built_map(["codex", "gpt-6.1-sol", "xhigh"])
    assert RDISC.nonpanel_reviewer(
        _CONFIG, seat_map, "synthesis", "codex",
        maker_families=frozenset({"anthropic"}), fixer_vendor="cursor",
    ) == (None, None)
    assert RDISC.nonpanel_reviewer(
        _CONFIG, _claude_built_map(), "synthesis", "codex",
        maker_families=frozenset({"anthropic"}), fixer_vendor="cursor",
    ) == (None, None)
