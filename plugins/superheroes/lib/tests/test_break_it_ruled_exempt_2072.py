"""A break-it test ruled out of scope and discharged by the audit is not required to be kept (#2072).

Exempt only when the finding's effective decision is an attributed `rule`-verb out-of-scope ruling AND a
round's recorded audit cleared it; every other fixed or out-of-scope finding still owes the kept check."""
import os
import sys

import pytest

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import break_it  # noqa: E402
import receipt_disclosures  # noqa: E402
import session_contract  # noqa: E402
import review_record_session as RRS  # noqa: E402
import round_driver as RD  # noqa: E402
import test_break_it_loop as TL  # noqa: E402  (its `World` drives `RD._fold`)
from test_break_it_loop import world  # noqa: E402,F401  (the fixture, reused by name)

PROV = {"ruledBy": "zach", "ruledAt": "2026-10-20T12:00:00Z"}
REASON = "belongs to the billing rewrite"


def _rule(world, key, ruling="out-of-scope", provenance=PROV, reason=REASON):
    """Append a `rule`-verb row to the rulings log the way `_cmd_rule_locked` writes it."""
    row = {"seq": RD._next_ruling_seq(world.state), "round": world.state["round"], "id": key,
           "findingKey": key, "ruling": ruling, "reason": reason, "by": "test"}
    if provenance is not None:
        row["provenance"] = provenance
    RD._writable_rulings_log(world.state).append(row)


def _audit(world, key, ruling="discharged", **extra):
    entry = dict({"id": key, "ruling": ruling}, **extra)
    RD._record_round_append(world.state, "audits", entry)


def _shape(world, disposition="fixed", head_has_test=False):
    """A failing break-it run for the finding, the ledger disposition, and the fix head."""
    world.fold_panel(TL._break_it_finding())
    key = world.key_of_failed_run()
    world.disposition(disposition, **({"outOfScopeReason": REASON} if disposition == "out-of-scope" else {}))
    world.fix(TL._TEST_FAILING if head_has_test else None)
    return key


@pytest.fixture
def spy(monkeypatch):
    """Record every `check_kept` call and run the real one."""
    calls = []
    real = break_it.check_kept

    def recording(*args, **kwargs):
        calls.append(args)
        return real(*args, **kwargs)

    monkeypatch.setattr(break_it, "check_kept", recording)
    return calls


def _owes_the_check(world, spy):
    """The kept step ran `check_kept`, found the test absent from head, and parked."""
    assert RD._break_it_kept_step(world.state, world.state["config"]) is True
    assert len(spy) == 1
    (row,) = world.round_record["breakItKept"]
    assert (row["outcome"], row["reason"]) == ("missing", "not-in-head")


# ---- the exemption: a consuming project's issue shape -----------------------------------------------

def test_a_ruled_out_of_scope_and_discharged_test_is_exempt_from_the_kept_check(world, monkeypatch):
    key = _shape(world)
    _rule(world, key)
    _audit(world, key)

    def never(*args, **kwargs):
        raise AssertionError("check_kept ran for an exempt finding")

    monkeypatch.setattr(break_it, "check_kept", never)
    assert RD._break_it_kept_step(world.state, world.state["config"]) is False
    (row,) = world.round_record["breakItKept"]
    assert row == {"findingKey": key, "path": TL.TEST_PATH, "outcome": "ruled-out-of-scope",
                   "reason": REASON, "ruledBy": "zach", "ruledAt": "2026-10-20T12:00:00Z"}
    detail = [d["detail"] for d in world.state["decisions"] if d["kind"] == "break-it-kept"]
    assert detail == ["0 checked: 0 kept, 0 not kept, 0 not required, 1 ruled out of scope"]


def test_the_exempt_finding_lets_the_terminal_converge(world, monkeypatch):
    key = _shape(world)
    _rule(world, key)
    _audit(world, key, "discharged-but-new-issue")
    monkeypatch.setattr(break_it, "check_kept", lambda *a, **k: pytest.fail("check_kept ran"))
    RD._terminal_converged(world.state, world.state["config"], full_panel=True)
    assert world.state["terminal"] == "converged"
    assert world.round_record["breakItKept"][0]["outcome"] == "ruled-out-of-scope"


def test_the_review_record_labels_the_exempt_finding_ruling_never_fixed(world, monkeypatch):
    key = _shape(world)
    _rule(world, key)
    _audit(world, key)
    monkeypatch.setattr(break_it, "check_kept", lambda *a, **k: pytest.fail("check_kept ran"))
    assert RD._break_it_kept_step(world.state, world.state["config"]) is False
    findings, _merged = RRS._findings_and_merges(world.state)
    (got,) = [f for f in findings if f["findingKey"] == key]
    assert got["outcome"] == "ruling"
    assert got["reason"] == "ruled out of scope: %s (ruled by zach, 2026-10-20T12:00:00Z)" % REASON


def test_a_fixed_finding_with_no_exempt_row_is_still_labelled_fixed(world, spy):
    key = _shape(world, head_has_test=True)
    _audit(world, key)
    assert RD._break_it_kept_step(world.state, world.state["config"]) is False
    findings, _merged = RRS._findings_and_merges(world.state)
    (got,) = [f for f in findings if f["findingKey"] == key]
    assert got["outcome"] == "fixed" and got["reason"].startswith("fixed and audited")


def test_the_receipt_disclosure_does_not_list_a_ruled_out_of_scope_row_as_not_kept():
    exempt = {"findingKey": "k", "path": "tests/t.py", "outcome": "ruled-out-of-scope"}
    assert not [line for line in _degraded_for([exempt]) if "break-it-test-not-kept" in line]
    missing = {"findingKey": "j", "path": "tests/u.py", "outcome": "missing"}
    (line,) = [line for line in _degraded_for([exempt, missing]) if "break-it-test-not-kept" in line]
    assert "1 fixed break-it test(s)" in line and "tests/u.py: missing" in line and "tests/t.py" not in line


# ---- the fail-closed edges --------------------------------------------------------------------

@pytest.mark.parametrize("disposition", ["fixed", "out-of-scope"])
def test_edge1_a_rule_with_no_clearing_audit_still_owes_the_check(world, spy, disposition):
    key = _shape(world, disposition)
    _rule(world, key)
    _owes_the_check(world, spy)


def test_edge2_a_cleared_finding_with_no_rule_still_owes_the_check(world, spy):
    key = _shape(world)
    _audit(world, key)
    _owes_the_check(world, spy)


@pytest.mark.parametrize("provenance", [
    None, "zach", {}, {"ruledBy": "zach"}, {"ruledAt": "2026-10-20"}, {"ruledBy": "", "ruledAt": "2026-10-20"},
    {"ruledBy": "zach", "ruledAt": ""}, {"ruledBy": "zach", "ruledAt": "  "}, {"ruledBy": 7, "ruledAt": "2026-10-20"},
    {"ruledBy": "zach", "ruledAt": 20261020},
], ids=["missing", "not-a-dict", "empty", "no-ruledAt", "no-ruledBy", "empty-ruledBy", "empty-ruledAt",
        "blank-ruledAt", "non-string-ruledBy", "non-string-ruledAt"])
def test_edge3_an_unattributed_rule_owes_the_check(world, spy, provenance):
    key = _shape(world)
    _rule(world, key, provenance=provenance)
    _audit(world, key)
    _owes_the_check(world, spy)


@pytest.mark.parametrize("later", ["guidance", "fix"])
def test_edge4_a_later_ruling_that_superseded_the_skip_owes_the_check(world, spy, later):
    key = _shape(world)
    _rule(world, key)
    _rule(world, key, ruling=later)
    _audit(world, key)
    _owes_the_check(world, spy)


@pytest.mark.parametrize("later", ["guidance", "fix"])
def test_edge4c_a_newer_ruling_on_a_merged_member_supersedes_the_skip(world, spy, later):
    key = _shape(world)
    _rule(world, key)
    world.state["findings"].append({"findingKey": "member", session_contract.MERGED_INTO_FIELD: key})
    _rule(world, "member", ruling=later)
    _audit(world, key)
    assert RD._row_decision(world.state, RD._live_ruling_by_key(world.state), {}, key)["ruling"] == later
    _owes_the_check(world, spy)


def test_edge4b_a_gate_skip_is_not_a_rule_verb_ruling(world, spy):
    key = _shape(world)
    world.round_record["judgmentDispositions"] = [
        {"findingKey": key, "disposition": "skip", "reason": REASON, "rulingSeq": 1, **PROV}]
    _audit(world, key)
    assert RD._live_ruling_by_key(world.state)[key]["source"] == "gate"
    _owes_the_check(world, spy)


@pytest.mark.parametrize("extra", [{}, {"unauthenticated": True}], ids=["plain", "unauthenticated"])
def test_edge5_a_not_discharged_audit_owes_the_check(world, spy, extra):
    key = _shape(world)
    _rule(world, key)
    _audit(world, key, "not-discharged", **extra)
    _owes_the_check(world, spy)


def test_edge6_a_skip_given_on_a_lineage_sibling_owes_the_check(world, spy):
    key = _shape(world)
    world.state["findingLineage"] = {key: "root", "sibling": "root"}
    _rule(world, "sibling")
    _audit(world, key)
    assert key not in RD._live_ruling_by_key(world.state)
    _owes_the_check(world, spy)


@pytest.mark.parametrize("log", ["garbage", {"seq": 1}, [None]], ids=["string", "dict", "bad-row"])
def test_edge7_an_unreadable_rulings_log_owes_the_check(world, spy, log):
    key = _shape(world)
    _rule(world, key)
    _audit(world, key)
    world.state["rulingsLog"] = log
    assert RD._live_ruling_by_key(world.state) == {}
    _owes_the_check(world, spy)


@pytest.mark.parametrize("audits", [None, "discharged", {"id": "k", "ruling": "discharged"}, ["x", 3, None],
                                    [{"id": "other", "ruling": "discharged"}]],
                         ids=["missing", "string", "dict", "non-dict-entries", "other-key"])
def test_edge8_a_round_without_a_usable_audit_list_contributes_no_discharge(world, spy, audits):
    key = _shape(world)
    _rule(world, key)
    if audits is not None:
        world.round_record["audits"] = audits
    _owes_the_check(world, spy)


def test_edge8b_a_malformed_round_beside_a_good_one_does_not_hide_the_discharge(world, monkeypatch):
    key = _shape(world)
    _rule(world, key)
    world.state["rounds"]["0"] = {"audits": "garbage"}
    world.state["rounds"]["2"] = {"audits": [{"id": key, "ruling": "discharged"}]}
    monkeypatch.setattr(break_it, "check_kept", lambda *a, **k: pytest.fail("check_kept ran"))
    assert RD._break_it_kept_step(world.state, world.state["config"]) is False


def test_other_dispositions_keep_not_required(world, spy):
    world.fold_panel(TL._break_it_finding())
    world.disposition("refuted", refutedReason="the verifier refuted it")
    world.fix(None)
    assert RD._break_it_kept_step(world.state, world.state["config"]) is False
    (row,) = world.round_record["breakItKept"]
    assert (row["outcome"], row["reason"]) == ("not-required", "refuted") and spy == []


def _degraded_for(rows):
    """The degraded lines the receipt writes for a round that declared these `breakItKept` rows."""
    degraded, _skipped = receipt_disclosures.build_degraded_prose(
        {"rounds": {"1": {"breakItKept": rows}}}, receipt_disclosures.RECEIPT_FORM_CERTIFIED)
    return degraded
