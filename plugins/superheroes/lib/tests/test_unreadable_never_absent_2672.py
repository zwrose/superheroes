"""#2672: the review loop's own readers treat an unreadable earlier record or round as unreadable, never absent.

The invariant: a reader that meets an earlier review record or a round record it cannot read stops there and names
it. It never skips it, so no carry or round walk falls back to an older record or round. The healthy case is
unchanged.

S1 the session writer's latest earlier record (`_earlier`, `write_from_session`) · S2 the session writer's raiser walk
(`_other_session_findings`) · M1 the terminal compose over unreadable round records · M2 a round whose fix block is
unreadable · L1 the plan-round walkers (`_previous_dimension_state`, `_carry_forward_dimension`, `_panel_window`) ·
L2 the tally walkers (`_surfaced_blocking_severities`, `_assemble_rounds`).

Bite-proof record: i2672_unreadable_never_absent
"""
import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import review_loop_plan as rlp  # noqa: E402
import review_memory as rm  # noqa: E402
import review_record as rr  # noqa: E402
import review_record_session as rs  # noqa: E402

DIMS = ["code-reviewer", "security-reviewer"]
SID = "session-this"
OTHER = "session-other"
OLDER = "session-older"


# ---- review-record comment fixtures ------------------------------------------------------------------------------


def _finding(title, raiser=None):
    out = {"id": title, "title": title, "file": "src/a.py", "line": 3, "severity": "Important",
           "outcome": "fixed", "reason": "fixed in the change"}
    if raiser:
        out["raisedBy"] = raiser
    return out


def _record_body(record):
    return f"{rr.MARKER}\nsummary\n<details>\n\n```json\n{json.dumps(record)}\n```\n</details>\n"


def _record(session, findings):
    return {"schema": rr.RECORD_SCHEMA, "sessionId": session, "findings": findings}


def _comments(*bodies):
    return [{"id": 100 + i, "url": f"https://example.invalid/pr/7#c{100 + i}", "body": b}
            for i, b in enumerate(bodies)]


UNPARSEABLE = f"{rr.MARKER}\nsummary\n<details>\n\n```json\n{{\"schema\": \"review-record/1\", \n```\n</details>\n"


def _readers(comments):
    return {"list_comments": lambda pr, repo: comments, "repo_name": lambda root: "owner/name"}


def _account(findings=None):
    return {"pr": 7, "sessionId": SID, "findings": findings or [], "checked": []}


# ---- S1: the latest earlier record -------------------------------------------------------------------------------


def test_s1_an_unparseable_latest_record_is_unreadable_never_none():
    # axis: an unreadable latest record is an unreadable entry, never "no earlier record"
    older = _record_body(_record(OLDER, [_finding("old finding")]))
    out = rs._earlier(_account(), {}, "/path/to/repo", _readers(_comments(older, UNPARSEABLE)))
    assert isinstance(out, rs._Unreadable), out
    assert "#c101" in out.detail


def test_s1_a_latest_record_with_a_malformed_findings_list_is_unreadable():
    # axis: a malformed findings list is unreadable, never read as an empty one
    older = _record_body(_record(OLDER, [_finding("old finding")]))
    bad = _record_body(dict(_record(OTHER, []), findings={"not": "a list"}))
    out = rs._earlier(_account(), {}, "/path/to/repo", _readers(_comments(older, bad)))
    assert isinstance(out, rs._Unreadable), out
    assert "findings list is malformed" in out.detail


def test_s1_healthy_latest_record_gives_its_findings_and_no_record_gives_none():
    # axis: the healthy case is unchanged
    latest = _record_body(_record(OTHER, [_finding("kept")]))
    assert [f["title"] for f in rs._earlier(_account(), {}, "/r", _readers(_comments(latest)))] == ["kept"]
    assert rs._earlier(_account(), {}, "/r", _readers([])) == []


def _write_through(monkeypatch, tmp_path, comments, findings=None):
    """Run write_from_session with the session read and the record write stubbed out; return the account the record
    writer was handed."""
    extras = tmp_path / "extras.json"
    extras.write_text(json.dumps({"repo": "owner/name"}))
    monkeypatch.setattr(rs, "account_from_session", lambda *a, **k: _account(findings))
    seen = {}

    def write(path, repo_root, readers, **kw):
        with open(path, encoding="utf-8") as fh:
            seen["account"] = json.load(fh)
        return {"ok": True}
    monkeypatch.setattr(rs.review_record, "write", write)
    out = rs.write_from_session(str(tmp_path), str(extras), "/path/to/repo", readers=_readers(comments))
    assert out == {"ok": True}, out
    return seen["account"]


def test_s1_the_writer_carries_nothing_from_an_unreadable_latest_record_and_names_it(monkeypatch, tmp_path):
    # axis: an earlier record that could not be read gives no findings and no raisers, and the record names it
    older = _record_body(_record(OLDER, [_finding("old finding", raiser="code-reviewer")]))
    acct = _write_through(monkeypatch, tmp_path, _comments(older, UNPARSEABLE),
                          findings=[_finding("old finding", raiser="test-role")])
    assert [f["title"] for f in acct["findings"]] == ["old finding"]
    assert acct["findings"][0]["raisedBy"] == "test-role", "the older record behind the unreadable one was read"
    joined = " ".join(acct["checked"])
    assert "No findings were carried from the latest earlier review record" in joined
    assert "No raiser was taken" in joined
    assert "#c101" in joined


def test_s1_healthy_write_carries_and_adds_no_unreadable_line(monkeypatch, tmp_path):
    # axis: the healthy case is unchanged: the earlier finding is carried and its raiser wins
    latest = _record_body(_record(OTHER, [_finding("earlier", raiser="code-reviewer"),
                                          _finding("mine", raiser="code-reviewer")]))
    acct = _write_through(monkeypatch, tmp_path, _comments(latest), findings=[_finding("mine", raiser="test-role")])
    assert sorted(f["title"] for f in acct["findings"]) == ["earlier", "mine"]
    assert next(f for f in acct["findings"] if f["title"] == "mine")["raisedBy"] == "code-reviewer"
    assert acct["checked"] == []


# ---- S2: the raiser walk -----------------------------------------------------------------------------------------


def test_s2_an_unparseable_record_stops_the_raiser_walk():
    # axis: an earlier record that cannot be parsed stops the raiser walk instead of being skipped
    older = _record_body(_record(OLDER, [_finding("x", raiser="code-reviewer")]))
    out = rs._other_session_findings(_account(), {}, "/r", _readers(_comments(older, UNPARSEABLE)))
    assert isinstance(out, rs._Unreadable), out


def test_s2_a_malformed_findings_list_stops_the_walk_whichever_session_posted_it():
    # axis: a record whose findings list is malformed stops the walk, whichever session posted it
    older = _record_body(_record(OLDER, [_finding("x", raiser="code-reviewer")]))
    for session in (OTHER, SID):
        bad = _record_body(dict(_record(session, []), findings="junk"))
        out = rs._other_session_findings(_account(), {}, "/r", _readers(_comments(older, bad)))
        assert isinstance(out, rs._Unreadable), (session, out)


def test_s2_healthy_walk_looks_past_this_sessions_own_record():
    # axis: the healthy case is unchanged: this session's own readable record is looked past to the other one
    older = _record_body(_record(OLDER, [_finding("x", raiser="code-reviewer")]))
    own = _record_body(_record(SID, [_finding("x", raiser="test-role")]))
    out = rs._other_session_findings(_account(), {}, "/r", _readers(_comments(older, own)))
    assert [f["raisedBy"] for f in out] == ["code-reviewer"]
    assert rs._other_session_findings(_account(), {}, "/r", _readers(_comments(own))) == []


# ---- M1, M2: the terminal compose --------------------------------------------------------------------------------


def _compose(tmp_path, records_text):
    records = tmp_path / "round-records.json"
    if records_text is not None:
        records.write_text(records_text)
    path = tmp_path / "terminal-record.json"
    out = rm.compose_terminal_record(str(path), json.dumps({"terminal": "clean", "round": 2}),
                                     records_path=str(records), run_id="run-1")
    return out, path


def _round(n, fix):
    return {"schemaVersion": 2, "round": n, "kind": "baseline", "dimensions": {}, "findings": [],
            "coverageDecisions": [], "fix": fix}


def test_m1_corrupt_round_records_stop_the_compose_with_a_named_reason(tmp_path):
    # axis: unreadable or corrupt round records stop the terminal compose with a named reason, never read as no rounds
    for text in ("{corrupt", json.dumps({"not": "a list"}), json.dumps([_round(1, {}), "junk"])):
        out, path = _compose(tmp_path, text)
        assert out["ok"] is False and out["reason"] == rm.ROUND_RECORDS_UNREADABLE, out
        assert "corrupt" in out["detail"]
        assert not path.exists(), "a terminal record was written from unreadable rounds"


def test_m2_a_round_whose_fix_block_is_not_an_object_stops_the_compose(tmp_path):
    # axis: a round whose fix block cannot be read stops the compose, so its fixes and deferrals are never dropped
    out, path = _compose(tmp_path, json.dumps([_round(1, {"fixes": [{"id": "a"}]}), _round(2, ["junk"])]))
    assert out["ok"] is False and out["reason"] == rm.ROUND_RECORDS_UNREADABLE, out
    assert "round 2" in out["detail"]
    assert not path.exists()


def test_m_healthy_compose_reads_the_fixes_and_missing_records_read_as_none(tmp_path):
    # axis: the healthy case is unchanged
    out, path = _compose(tmp_path, json.dumps([_round(1, {"fixes": [{"id": "a"}], "deferred": [{"id": "d"}]}),
                                               _round(2, None)]))
    assert out["ok"] is True, out
    written = json.loads(path.read_text())
    assert written["fixes"] == [{"id": "a"}] and written["deferred"] == [{"id": "d"}]
    fresh = tmp_path / "fresh"
    fresh.mkdir()
    out, path = _compose(fresh, None)
    assert out["ok"] is True and json.loads(path.read_text())["fixes"] == []


# ---- L1: the plan-round walkers ----------------------------------------------------------------------------------


def _dim(findings=None):
    return {"status": "run", "confidence": "high", "tier": "reviewer-deep", "findings": findings or []}


def _rec(n, dims, kind="baseline", findings=None):
    return {"round": n, "kind": kind, "dimensions": dims, "findings": findings or []}


GOOD = _rec(1, {"code-reviewer": _dim(), "security-reviewer": _dim()})


@pytest.mark.parametrize("bad", ["junk", None, 7, _rec(2, ["not", "a", "dict"])])
def test_l1_previous_dimension_state_stops_at_an_unreadable_round(bad):
    # axis: a round record that is not an object stops every walk, never skipped
    with pytest.raises(rlp.RoundUnreadable) as exc:
        rlp._previous_dimension_state([GOOD, bad])
    assert exc.value.reason == rlp.ROUND_UNREADABLE and "round record 1" in exc.value.detail


@pytest.mark.parametrize("bad", ["junk", _rec(2, "junk"), _rec(2, {"security-reviewer": "junk"})])
def test_l1_the_carry_never_reaches_past_an_unreadable_round_to_an_older_one(bad):
    # axis: a dimension state that cannot be read stops the carry instead of carrying an older round's state
    with pytest.raises(rlp.RoundUnreadable):
        rlp._carry_forward_dimension([GOOD, bad], "security-reviewer", 1)


def test_l1_panel_window_never_drops_an_unreadable_round():
    # axis: the panel window never filters out an unreadable round
    with pytest.raises(rlp.RoundUnreadable):
        rlp._panel_window([GOOD, "junk"])


def test_l1_healthy_walkers_are_unchanged():
    # axis: the healthy case is unchanged, and a round that holds no dimensions or no entry for a name is not unreadable
    newer = _rec(2, {"code-reviewer": dict(_dim(), confidence="low")})
    assert rlp._previous_dimension_state([GOOD, newer])["code-reviewer"]["confidence"] == "low"
    carried = rlp._carry_forward_dimension([GOOD, newer, _rec(3, None)], "security-reviewer", 1)
    assert carried["status"] == "skipped" and carried["confidence"] == "high"
    assert rlp._carry_forward_dimension([], "x", 1)["confidence"] == "low"
    assert rlp._panel_window([GOOD]) == ([], [])


def test_l1_plan_round_runs_all_deep_and_names_the_unreadable_round(monkeypatch, tmp_path):
    # axis: an unreadable round stops the schedule walk and names itself; nothing is skipped or carried from older rounds
    monkeypatch.setattr(rlp, "_load_records", lambda path, dims: {"ok": True, "records": [GOOD, "junk"]})
    ans = rlp.plan_round_decider(str(tmp_path / "r.json"), 3, DIMS, ["Code"], just_marked=False)
    assert ans["memoryUnreadable"] is True and ans["carried"] == {}
    assert ans["unreadableRound"]["reason"] == rlp.ROUND_UNREADABLE
    assert all(d["action"] == "run" and d["tier"] == "reviewer-deep" and rlp.ROUND_UNREADABLE in d["reason"]
               for d in ans["dimensions"].values())


# ---- L2: the tally walkers ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("bad", ["junk", _rec(2, {}, findings=None) | {"findings": "junk"},
                                 _rec(2, {}) | {"findings": ["junk"]}])
def test_l2_surfaced_severities_never_read_an_unreadable_round_as_none(bad):
    # axis: a findings field that is not a list of objects is unreadable, never read as no findings
    with pytest.raises(rlp.RoundUnreadable):
        rlp._surfaced_blocking_severities(bad)


@pytest.mark.parametrize("bad", ["junk", _rec(2, {}) | {"findings": {"a": 1}}])
def test_l2_assemble_rounds_stops_at_an_unreadable_round(bad):
    # axis: an unreadable round stops the breaker's round walk instead of being skipped
    with pytest.raises(rlp.RoundUnreadable):
        rlp._assemble_rounds([GOOD, bad], {})


def test_l2_healthy_tally_walkers_are_unchanged():
    # axis: the healthy case is unchanged
    rec = _rec(1, {}, findings=[{"severity": "Critical", "title": "t"}, {"severity": "Minor", "title": "m"}])
    assert rlp._surfaced_blocking_severities(rec) == ["Critical"]
    assert rlp._surfaced_blocking_severities(_rec(1, {}) | {"findings": None}) == []
    assert [r["round"] for r in rlp._assemble_rounds([_rec(2, {}), GOOD], {})] == [1, 2]


def test_l2_tally_cannot_certify_with_the_named_reason(monkeypatch, tmp_path):
    # axis: an unreadable round stops the tally's round walk with its named reason, never read as an absent round
    monkeypatch.setattr(rlp, "_load_records", lambda path, dims: {"ok": True, "records": [GOOD, "junk", _rec(3, {})]})
    ans = rlp.tally_round_decider(str(tmp_path / "r.json"), 3, DIMS, 7, "clean", "high", [], 0, None,
                                  "completed", None, False)
    assert ans["terminal"] == "cannot-certify" and ans["gate"] == "cannot-certify", ans
    assert ans["reason"].startswith(rlp.ROUND_UNREADABLE + ": round record 1")
    assert ans["unreadableRound"]["reason"] == rlp.ROUND_UNREADABLE
