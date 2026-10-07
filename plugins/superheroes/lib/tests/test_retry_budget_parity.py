"""Single-home guard for the reviewer re-dispatch budget (#525).

The reviewer re-dispatch budget is ONE, read from `loop_plan_common.REDISPATCH_BUDGET`. The
code-leg driver (round_driver — #507, which absorbed the retired code_loop_plan) is its one
remaining consumer, so there is no second scheduler left to compare it against: the surviving assertions pin the single module's behaviour and
its read of the single home. Documented intent: #350 ("re-dispatch … once … never asks twice").
The same invariant is stated in skills/review-code/SKILL.md and
skills/review-code/reference/round-scheduler.md ("re-dispatch … once … never asks twice").
"""
import importlib.util
import os

EXPECTED_REDISPATCHES = 1

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RD = _load(os.path.join(_HERE, "..", "round_driver.py"), "round_driver")
LPC = _load(os.path.join(_HERE, "..", "loop_plan_common.py"), "loop_plan_common")


def test_expected_redispatches_matches_budget_home():
    # The pin (EXPECTED_REDISPATCHES) and the single-home constant must not drift: the whole
    # point of REDISPATCH_BUDGET is that ONE value drives every leg.
    assert EXPECTED_REDISPATCHES == LPC.REDISPATCH_BUDGET


# --- round_driver code-leg fixtures (#507: code_loop_plan retired into round_driver) ----------
# The code-leg re-dispatch budget now lives in round_driver.run_loop's reviewer seam loop, which
# reads loop_plan_common.REDISPATCH_BUDGET (the single home). A persistently receipt-missing seat
# is re-dispatched exactly REDISPATCH_BUDGET times, then recorded terminal `missing`.

_RD_DIFF = ("diff --git a/f.py b/f.py\nindex 1..2 100644\n--- a/f.py\n+++ b/f.py\n"
            "@@ -1 +1,2 @@\n-old\n+new\n+more\n")


def _rd_dispatch_count_for_missing_seat(missing_dim, missing_round):
    """Drive round_driver.run_loop with `missing_dim` returning a persistently receipt-missing
    answer at round `missing_round`. Returns (dispatch_count, recorded_seat_status)."""
    calls = {"n": 0}
    seat_status = {"value": None}

    def reviewer(dim, tier, rnd, ctx):
        if dim == missing_dim and rnd == missing_round:
            calls["n"] += 1
            return {"findings": [], "receiptMissing": True}
        return []

    orig_fold = RD._fold_panel

    def spy_fold(state, config, artifact):
        orig_fold(state, config, artifact)
        rec = state["rounds"].get(str(state["round"]), {})
        if rec.get("seatStatus"):
            seat_status["value"] = rec["seatStatus"].get(missing_dim)

    RD._fold_panel = spy_fold
    try:
        RD.run_loop({
            "reviewer": reviewer,
            "verifier": lambda cl, rnd: [{"id": i, "verdict": "PLAUSIBLE"}
                                         for c in (cl or []) for i in c.get("ids", [])],
            "synthesis": lambda f, rnd: None,
            "auditor": lambda t, rnd: [{"id": x["id"], "ruling": "discharged", "reason": "r",
                                        "evidence": "e"} for x in (t or [])],
            "fix_step": lambda b, rnd, p: {"fixes": [], "headDiff": _RD_DIFF, "changedSubjects": []},
            "verify_runner": lambda c, rnd: "pass",
            "io": {},
        }, {"leg": "code", "vendors": ["claude", "codex"], "diff": _RD_DIFF, "fixerVendor": "claude"})
    finally:
        RD._fold_panel = orig_fold
    return calls["n"], seat_status["value"]


# --- round_driver (code-leg) cases ---------------------------------------
# The code leg's re-dispatch bound now rides through round_driver, which reads
# loop_plan_common.REDISPATCH_BUDGET (asserted in test_expected_redispatches_matches_budget_home).
# A persistently receipt-missing seat is dispatched 1 + EXPECTED_REDISPATCHES times, then `missing`.

def test_round_driver_round1_missing_retry_budget():
    dispatches, status = _rd_dispatch_count_for_missing_seat("code-reviewer", 1)
    assert dispatches == 1 + EXPECTED_REDISPATCHES
    assert status == "missing"


def test_round_driver_budget_reads_single_home():
    # the code-leg budget is NOT a local literal — it reads the single home.
    assert RD.REDISPATCH_BUDGET == LPC.REDISPATCH_BUDGET
