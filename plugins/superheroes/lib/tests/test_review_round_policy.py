import importlib.util
import os

LIB = os.path.join(os.path.dirname(__file__), "..")


def load():
    spec = importlib.util.spec_from_file_location("review_round_policy", os.path.join(LIB, "review_round_policy.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RP = load()


def test_malformed_previous_dimension_is_fail_safe():
    out = RP.plan_round({
        "round": 2,
        "dimensions": ["architecture-reviewer"],
        "changedSubjects": ["Test"],
        "previous": {"architecture-reviewer": []},
    })
    assert out["dimensions"]["architecture-reviewer"]["action"] == "run"
    assert out["escalationPolicy"] == "cheap-first"


def test_fractional_round_string_is_malformed():
    out = RP.plan_round({
        "round": "2.5",
        "dimensions": ["test-reviewer"],
        "changedSubjects": ["Test"],
        "previous": {},
    })
    assert out["dimensions"]["test-reviewer"]["reason"] == "malformed round state"
    assert out["escalationPolicy"] == "deep-only"


def test_is_cross_cutting_three_of_five_subjects_is_cross_cutting():
    # #174: "cross-cutting rework" = the fix touched ≥3 of the 5 policy subjects. Pin the rule.
    assert RP.is_cross_cutting(["Code", "Architecture", "Security"]) is True


def test_is_cross_cutting_two_subjects_is_not_cross_cutting():
    assert RP.is_cross_cutting(["Code", "Architecture"]) is False


def test_is_cross_cutting_dedupes_before_counting():
    # Three list entries but only two distinct subjects — not cross-cutting.
    assert RP.is_cross_cutting(["Code", "Code", "Architecture"]) is False


def test_is_cross_cutting_empty_is_not_cross_cutting():
    assert RP.is_cross_cutting([]) is False


def test_is_cross_cutting_unknown_surface_fails_toward_cross_cutting():
    # Unknown rework breadth (malformed / not a list) → conservative: treat as cross-cutting so
    # the loop errs toward one more confirmation, never toward a premature certify.
    assert RP.is_cross_cutting(None) is True


def test_confirmation_followup_non_critical_under_cap_no_rearm():
    # Req 2: a confirmation that surfaces only Importants (not cross-cutting) does NOT trigger
    # another full confirmation — the Importants are fixed + scope-verified by a scoped round.
    out = RP.confirmation_followup(["Important"], 1, False)
    assert out["rearm"] is False
    assert out["park"] is False


def test_confirmation_followup_critical_under_cap_rearms():
    # Req 2: a Critical from a confirmation triggers one additional full confirmation.
    out = RP.confirmation_followup(["Important", "Critical"], 1, False)
    assert out["rearm"] is True
    assert out["park"] is False


def test_confirmation_followup_cross_cutting_under_cap_rearms():
    # Req 2: cross-cutting rework (no Critical) also triggers one additional full confirmation.
    out = RP.confirmation_followup(["Important"], 1, True)
    assert out["rearm"] is True
    assert out["park"] is False


def test_confirmation_followup_critical_at_cap_parks():
    # Req 3: a Critical still owed at the hard cap (2 panels) parks — certification withheld.
    out = RP.confirmation_followup(["Critical"], 2, False)
    assert out["rearm"] is False
    assert out["park"] is True
    assert out["atCap"] is True


def test_confirmation_followup_miscased_critical_at_cap_parks():
    # #291: a mis-cased `critical` at the cap MUST still park (was `"Critical" in sevs`, case-sensitive,
    # so a lowercase Critical was resolved by scoped verify and certified — the fail-open this closes).
    for sev in ("critical", "CRITICAL", "  Critical  "):
        out = RP.confirmation_followup([sev], 2, False)
        assert out["park"] is True, sev
        assert out["rearm"] is False, sev


def test_confirmation_followup_miscased_critical_under_cap_rearms():
    out = RP.confirmation_followup(["critical"], 1, False)
    assert out["rearm"] is True and out["park"] is False


def test_confirmation_followup_non_critical_at_cap_certifies():
    # Req 3: at the cap, remaining non-Critical findings are resolved by scoped verify — no park,
    # no further panel.
    out = RP.confirmation_followup(["Important"], 2, True)
    assert out["rearm"] is False
    assert out["park"] is False
    assert out["atCap"] is True


def test_confirmation_followup_nothing_surfaced_no_rearm():
    out = RP.confirmation_followup([], 1, False)
    assert out["rearm"] is False
    assert out["park"] is False


def test_doc_mode_important_under_cap_rearms():
    out = RP.confirmation_followup(["Important"], 1, False, doc_mode=True)
    assert out == {"rearm": True, "park": False, "atCap": False,
                   "reason": "open blocking finding in doc review — one more full confirmation panel required"}


def test_doc_mode_important_at_cap_parks():
    out = RP.confirmation_followup(["Important"], 2, False, doc_mode=True)
    assert out["rearm"] is False and out["park"] is True and out["atCap"] is True


def test_doc_mode_nothing_open_no_rearm():
    out = RP.confirmation_followup([], 1, False, doc_mode=True)
    assert out == {"rearm": False, "park": False, "atCap": False,
                   "reason": "no open blocking finding — doc review certifies"}


def test_doc_mode_critical_at_cap_parks():
    out = RP.confirmation_followup(["Critical"], 2, False, doc_mode=True)
    assert out["park"] is True and out["atCap"] is True


def test_code_mode_unchanged_important_at_cap_scoped_verify():
    # regression guard: code review's rule is untouched — a non-Critical, non-cross-cutting finding
    # at the cap certifies via scoped verify. `cross_cutting=False` exercises the actual early
    # `not trigger` return; passing True here would instead exercise the cross-cutting-at-cap branch,
    # which happens to produce the same {park, rearm, atCap} values and so would silently pass even
    # if the `not trigger` branch regressed.
    out = RP.confirmation_followup(["Important"], 2, False)
    assert out["park"] is False and out["rearm"] is False and out["atCap"] is True


def test_object_changed_subjects_from_live_doc_fix_still_schedule_skips():
    out = RP.plan_round({
        "round": 2,
        "dimensions": ["architecture-reviewer", "security-reviewer"],
        "changedSubjects": [{"section": "Components > lib/acceptance_launch.py", "reason": "fixed architecture finding"}],
        "previous": {
            "architecture-reviewer": {
                "status": "run",
                "confidence": "high",
                "hasFindings": True,
                "subjects": ["Architecture"],
                "round": 1,
            },
            "security-reviewer": {
                "status": "run",
                "confidence": "high",
                "hasFindings": False,
                "subjects": ["Security"],
                "round": 1,
            },
        },
    })
    assert out["escalationPolicy"] == "cheap-first"
    assert out["dimensions"]["architecture-reviewer"]["tier"] == "reviewer"
    assert out["dimensions"]["security-reviewer"]["action"] == "skip"
