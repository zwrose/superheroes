import json
import os
import subprocess
import sys

import core_md as cm
import file_lock
import guardian_ledger as gled
import guardian_lens as gl
import guardian_store as gs
import mode_registry as mr
import store_core as sc
from guardian_fixtures import ensure_store, init_calibrated_repo

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _rec(rid, disposition, **extra):
    rec = {"id": rid, "disposition": disposition}
    rec.update(extra)
    return rec


# --- 1. round-trip through the REAL reader (CONVENTIONS §12.2 real seam) ------


def test_write_round_trips_through_real_read_ledger(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    records = [
        _rec("dup:jscpd:a.md<->b.md", "accepted",
             date="2026-07-20", issue=None,
             metricAtDisposition={"cloneLines": 177},
             reason="self-contained copies tolerated",
             reraiseWhen="cloneLines grows",
             adjudicatedIn="s1"),
        _rec("hotspot:lizard:plugins/superheroes/lib/repo_doctor.py", "filed",
             date="2026-07-20", issue="#243", adjudicatedIn="s1"),
    ]
    out = gled.write(repo, records, now="2026-07-21")
    assert out["ok"] is True, out

    read = gs.read_ledger(repo)
    assert read["status"] == "ok", read
    assert read["records"] == records
    assert read["byId"]["dup:jscpd:a.md<->b.md"]["metricAtDisposition"] == {"cloneLines": 177}


def test_written_file_shape_matches_conventions(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    gled.write(repo, [_rec("dup:jscpd:a.md", "filed", date="2026-07-20", issue="#1",
                           adjudicatedIn="s1")], now="2026-07-21")
    text = open(gs.ledger_path(repo), encoding="utf-8").read()
    assert text.startswith("<!-- %s: schemaVersion=%d status=confirmed created=2026-07-21 "
                           "updated=2026-07-21 -->"
                           % (gs.LEDGER_FENCE, gs.LEDGER_SCHEMA_VERSION))
    assert "# Guardian dispositions ledger" in text
    assert "## Report card" in text
    assert "```json %s\n" % gs.LEDGER_FENCE in text
    assert text.endswith("```\n")
    assert not text.endswith("```\n\n")


def test_write_is_idempotent_byte_for_byte(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    records = [_rec("dup:jscpd:a.md", "accepted", date="2026-07-20", reason="ok",
                    adjudicatedIn="s1")]
    gled.write(repo, records, now="2026-07-21")
    first = open(gs.ledger_path(repo), "rb").read()
    gled.write(repo, records, now="2026-07-21")
    second = open(gs.ledger_path(repo), "rb").read()
    assert first == second


def test_write_preserves_created_date_across_rewrites(tmp_path):
    """Provenance created= stays put; unchanged card keeps its updated= (Fix 8)."""
    repo = init_calibrated_repo(tmp_path)
    records = [_rec("dup:jscpd:a.md", "filed", issue="#1", adjudicatedIn="s1")]
    gled.write(repo, records, now="2026-07-01")
    gled.write(repo, records, now="2026-07-21")
    text = open(gs.ledger_path(repo), encoding="utf-8").read()
    assert "created=2026-07-01" in text
    # Same effective ledger+card → updated= must not advance across a date boundary.
    assert "guardian-report-card:begin updated=2026-07-01" in text
    assert "## Report card" in text
    assert "filed" in text or "dup" in text


def test_write_never_mutates_the_repo_with_git(tmp_path, monkeypatch):
    """The sweep never commits or pushes: path resolution may read git, nothing may write it."""
    repo = init_calibrated_repo(tmp_path)
    real = sc.run_git
    seen = []

    def _spy(cwd, *args):
        seen.append(args)
        return real(cwd, *args)

    monkeypatch.setattr(sc, "run_git", _spy)
    out = gled.write(repo, [_rec("dup:jscpd:a.md", "filed", issue="#1")], now="2026-07-21")
    assert out["ok"] is True
    mutating = {"commit", "add", "push", "tag", "checkout", "reset", "stash"}
    for args in seen:
        assert not (set(args) & mutating), args


def test_sweeps_roster_round_trips(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    sweep = gled.make_sweep("abc123", "2026-07-21")
    assert set(sweep) == set(gled.SWEEP_FIELDS)
    assert sweep["sweepId"]
    gled.write(repo, [], sweeps=[sweep], now="2026-07-21")
    text = open(gs.ledger_path(repo), encoding="utf-8").read()
    block = json.loads(text.split("```json %s\n" % gs.LEDGER_FENCE)[1].split("\n```")[0])
    assert block["sweeps"] == [sweep]
    assert block["schemaVersion"] == gs.LEDGER_SCHEMA_VERSION


def test_make_sweep_id_is_unique_per_run_and_explicit_id_dedupes():
    """Default ids are unique per run; an explicit sweepId is reused for finalize retry.

    Same-sha same-day must NOT collapse two collects into one id (vitals/roster need
    distinct sweeps). The benching floor still only counts adjudicatedIn stamps, so
    unique ids alone cannot manufacture evidence."""
    a = gled.make_sweep("abc123", "2026-07-21")
    b = gled.make_sweep("abc123", "2026-07-21")
    assert a["sweepId"] != b["sweepId"]
    assert a["sweptSha"] == b["sweptSha"] == "abc123"
    assert a["date"] == b["date"] == "2026-07-21"
    retry = gled.make_sweep("abc123", "2026-07-21", sweep_id=a["sweepId"])
    assert retry["sweepId"] == a["sweepId"]
    roster = gled.append_sweep([], a)
    roster = gled.append_sweep(roster, retry)
    assert roster == [a]
    roster = gled.append_sweep(roster, b)
    assert [s["sweepId"] for s in roster] == [a["sweepId"], b["sweepId"]]


def test_append_sweep_preserves_prior_order_and_is_idempotent_on_sweep_id():
    s1 = {"sweepId": "s1", "sweptSha": "aaa", "date": "2026-07-20"}
    s2 = {"sweepId": "s2", "sweptSha": "bbb", "date": "2026-07-21"}
    s1_retry = {"sweepId": "s1", "sweptSha": "aaa-retry", "date": "2026-07-22"}
    roster = gled.append_sweep([], s1)
    roster = gled.append_sweep(roster, s2)
    roster = gled.append_sweep(roster, s1_retry)
    assert [s["sweepId"] for s in roster] == ["s1", "s2"]
    assert roster[0]["sweptSha"] == "aaa", "first-write wins; retry must not replace"
    assert roster[1] == s2


def test_write_sweeps_none_preserves_on_disk_roster(tmp_path):
    """sweeps=None means preserve, not erase — the half of the finalize wipe defect."""
    repo = init_calibrated_repo(tmp_path)
    s1 = {"sweepId": "s1", "sweptSha": "aaa", "date": "2026-07-20"}
    s2 = {"sweepId": "s2", "sweptSha": "bbb", "date": "2026-07-21"}
    assert gled.write(repo, [], sweeps=[s1, s2], now="2026-07-21")["ok"] is True

    out = gled.write(
        repo, [_rec("dup:jscpd:a.md", "filed", issue="#1")],
        sweeps=None, now="2026-07-22")
    assert out["ok"] is True, out

    text = open(gs.ledger_path(repo), encoding="utf-8").read()
    block = json.loads(text.split("```json %s\n" % gs.LEDGER_FENCE)[1].split("\n```")[0])
    assert block["sweeps"] == [s1, s2]
    assert [s["sweepId"] for s in block["sweeps"]] == ["s1", "s2"]


# --- 2. matcher: identity across line drift ----------------------------------


def test_matcher_exact_id_matches():
    by_id = {"dup:jscpd:a.md": {"id": "dup:jscpd:a.md", "disposition": "accepted"}}
    rec, note = gled.match("dup:jscpd:a.md", by_id)
    assert rec is by_id["dup:jscpd:a.md"]
    assert note is None


def test_matcher_survives_line_drift():
    filed = {"id": "hotspot:lizard:a/b.py:117", "disposition": "filed", "issue": "#1"}
    rec, note = gled.match("hotspot:lizard:a/b.py:243", {filed["id"]: filed})
    assert rec is filed
    assert note is None


def test_matcher_survives_line_range_drift():
    filed = {"id": "dup:jscpd:a/b.py:10-40", "disposition": "accepted", "reason": "r"}
    rec, _ = gled.match("dup:jscpd:a/b.py:88-119", {filed["id"]: filed})
    assert rec is filed


def test_matcher_sorts_multi_location_pairs():
    filed = {"id": "dup:jscpd:a.md<->b.md", "disposition": "accepted", "reason": "r"}
    rec, _ = gled.match("dup:jscpd:b.md<->a.md", {filed["id"]: filed})
    assert rec is filed


def test_matcher_normalizes_separators_and_whitespace():
    filed = {"id": "dup:jscpd:a/b.md", "disposition": "accepted", "reason": "r"}
    rec, _ = gled.match("dup:jscpd: a\\b.md ", {filed["id"]: filed})
    assert rec is filed


def test_matcher_does_not_match_a_different_file():
    filed = {"id": "hotspot:lizard:a/b.py:117", "disposition": "filed", "issue": "#1"}
    rec, note = gled.match("hotspot:lizard:a/c.py:117", {filed["id"]: filed})
    assert rec is None
    assert note is None


def test_matcher_does_not_match_a_different_lens_or_tool():
    filed = {"id": "hotspot:lizard:a/b.py:117", "disposition": "filed", "issue": "#1"}
    assert gled.match("dup:lizard:a/b.py:117", {filed["id"]: filed})[0] is None
    assert gled.match("hotspot:radon:a/b.py:117", {filed["id"]: filed})[0] is None


def test_matcher_never_invents_a_match_from_empty_or_none():
    # A malformed/newer ledger yields an empty byId — nothing may be suppressed.
    assert gled.match("hotspot:lizard:a/b.py:117", {}) == (None, None)
    assert gled.match("hotspot:lizard:a/b.py:117", None) == (None, None)


def test_matcher_ignores_unhashable_and_non_str_ids():
    by_id = {"hotspot:lizard:a/b.py:117": {"id": ["not", "a", "str"], "disposition": "filed"}}
    rec, note = gled.match(None, by_id)
    assert rec is None and note is None


# --- 6b. matcher collision fails OPEN ----------------------------------------


def test_matcher_collision_fails_open_with_breadcrumb():
    a = {"id": "hotspot:lizard:a/b.py:117", "disposition": "accepted", "reason": "r"}
    b = {"id": "hotspot:lizard:a/b.py:243", "disposition": "declined", "reason": "r"}
    rec, note = gled.match("hotspot:lizard:a/b.py:900", {a["id"]: a, b["id"]: b})
    assert rec is None, "an ambiguous normalized form must surface, never suppress"
    assert note is not None
    assert a["id"] in note and b["id"] in note


def test_matcher_exact_id_does_not_bypass_collision():
    """Ambiguity wins over exactness: line-drift collision must surface even on exact id."""
    a = {"id": "hotspot:lizard:a/b.py:117", "disposition": "accepted", "reason": "r"}
    b = {"id": "hotspot:lizard:a/b.py:243", "disposition": "declined", "reason": "r"}
    rec, note = gled.match("hotspot:lizard:a/b.py:117", {a["id"]: a, b["id"]: b})
    assert rec is None
    assert note is not None and "ambiguous" in note
    assert a["id"] in note and b["id"] in note


# --- 3. material worsening (fixes the float(dict) defect) --------------------


def test_materially_worsened_object_metric_reraises_when_metric_grows():
    rec = _rec("dup:jscpd:a.md<->b.md", "accepted", reason="r",
               metricAtDisposition={"cloneLines": 177})
    assert gled.materially_worsened({"id": "x", "cloneLines": 190}, rec) is True


def test_materially_worsened_object_metric_quiet_when_metric_does_not_grow():
    rec = _rec("dup:jscpd:a.md<->b.md", "accepted", reason="r",
               metricAtDisposition={"cloneLines": 177})
    assert gled.materially_worsened({"id": "x", "cloneLines": 177}, rec) is False
    assert gled.materially_worsened({"id": "x", "cloneLines": 12}, rec) is False


def test_regression_object_metric_at_disposition_is_never_float_cast():
    """Regression guard for the live defect: `float(rec["metricAtDisposition"])` on the
    §5 object shape {"cloneLines": 177} raises TypeError, a bare except swallowed it, and
    a worsened trade NEVER re-raised. The object shape must compare, not crash."""
    rec = _rec("dup:jscpd:a.md<->b.md", "accepted", reason="r",
               metricAtDisposition={"cloneLines": 177})
    candidate = {"id": "dup:jscpd:a.md<->b.md", "cloneLines": 400}
    assert gled.materially_worsened(candidate, rec) is True


def test_materially_worsened_reads_metrics_subdict():
    rec = _rec("dup:jscpd:a.md", "accepted", reason="r",
               metricAtDisposition={"cloneLines": 100})
    assert gled.materially_worsened({"id": "x", "metrics": {"cloneLines": 101}}, rec) is True
    assert gled.materially_worsened({"id": "x", "metrics": {"cloneLines": 99}}, rec) is False


def test_materially_worsened_any_key_growing_counts():
    rec = _rec("dup:jscpd:a.md", "accepted", reason="r",
               metricAtDisposition={"cloneLines": 100, "files": 2})
    assert gled.materially_worsened({"cloneLines": 100, "files": 3}, rec) is True


def test_materially_worsened_scalar_back_compat():
    rec = _rec("dup:jscpd:a.md", "accepted", reason="r", metricAtDisposition=177)
    assert gled.materially_worsened({"metric": 178}, rec) is True
    assert gled.materially_worsened({"metric": 177}, rec) is False


def test_materially_worsened_noise_is_false_not_a_raise():
    assert gled.materially_worsened({"cloneLines": 999}, {"id": "x"}) is False
    assert gled.materially_worsened({}, _rec("a:b:c", "accepted", reason="r",
                                             metricAtDisposition={"cloneLines": 1})) is False
    assert gled.materially_worsened(None, None) is False
    assert gled.materially_worsened({"cloneLines": "big"},
                                    _rec("a:b:c", "accepted", reason="r",
                                         metricAtDisposition={"cloneLines": 1})) is False


def test_materially_worsened_never_drops_a_present_comparable_pair():
    rec = _rec("dup:jscpd:a.md", "accepted", reason="r",
               metricAtDisposition={"cloneLines": 100, "unknownMetric": 5})
    # cloneLines is comparable and has grown; the uncomparable sibling must not mask it.
    assert gled.materially_worsened({"cloneLines": 101}, rec) is True


# --- 4. reraiseWhen scoping --------------------------------------------------


def test_reraise_when_scopes_to_the_named_metric():
    rec = _rec("dup:jscpd:a.md", "accepted", reason="r",
               metricAtDisposition={"cloneLines": 177, "files": 2},
               reraiseWhen="cloneLines grows")
    assert gled.materially_worsened({"cloneLines": 177, "files": 9}, rec) is False
    assert gled.materially_worsened({"cloneLines": 178, "files": 2}, rec) is True


def test_reraise_when_unparseable_compares_all_keys():
    rec = _rec("dup:jscpd:a.md", "accepted", reason="r",
               metricAtDisposition={"cloneLines": 177, "files": 2},
               reraiseWhen="when the owner says so")
    assert gled.materially_worsened({"cloneLines": 177, "files": 3}, rec) is True


# --- 5. state machine --------------------------------------------------------


def test_allowed_transitions_cover_every_finding_state():
    assert set(gled.ALLOWED_TRANSITIONS) == set(gl.FINDING_STATES)
    for targets in gled.ALLOWED_TRANSITIONS.values():
        for t in targets:
            assert t in gl.FINDING_STATES


def test_outcome_buckets_are_finding_states():
    for state in gled.OUTCOMES_FOR + gled.OUTCOMES_AGAINST:
        assert state in gl.FINDING_STATES


def test_can_advance_legal_and_illegal():
    assert gled.can_advance("candidate", "surfaced")[0] is True
    assert gled.can_advance("surfaced", "filed")[0] is True
    assert gled.can_advance("filed", "verified-fixed")[0] is True
    assert gled.can_advance("reopened", "filed")[0] is True

    ok, reason = gled.can_advance("verified-fixed", "surfaced")
    assert ok is False and reason
    ok, reason = gled.can_advance("candidate", "filed")
    assert ok is False and reason
    ok, reason = gled.can_advance("accepted", "candidate")
    assert ok is False and reason
    ok, reason = gled.can_advance("filed", "not-a-state")
    assert ok is False and reason


def test_advance_applies_a_legal_transition_without_mutating_input():
    records = [_rec("dup:jscpd:a.md", "surfaced")]
    snapshot = json.dumps(records, sort_keys=True)
    new, result = gled.advance(records, "dup:jscpd:a.md", "filed",
                               issue="#7", date="2026-07-21")
    assert result["ok"] is True
    assert new[0]["disposition"] == "filed"
    assert new[0]["issue"] == "#7"
    assert new[0]["date"] == "2026-07-21"
    assert json.dumps(records, sort_keys=True) == snapshot


def test_advance_refuses_an_illegal_transition_and_keeps_the_record():
    records = [_rec("dup:jscpd:a.md", "verified-fixed", date="2026-07-01")]
    new, result = gled.advance(records, "dup:jscpd:a.md", "surfaced")
    assert result["ok"] is False
    assert result["reason"]
    assert len(new) == 1
    assert new[0]["disposition"] == "verified-fixed", "a terminal state never regresses"


def test_advance_never_removes_records():
    records = [_rec("a:b:c", "surfaced"), _rec("d:e:f", "filed", issue="#1")]
    new, _ = gled.advance(records, "a:b:c", "triaged-out", date="2026-07-21")
    assert len(new) == 2
    assert {r["id"] for r in new} == {"a:b:c", "d:e:f"}


def test_advance_creates_a_record_when_the_target_is_legal_from_candidate():
    new, result = gled.advance([], "dup:jscpd:a.md", "surfaced", date="2026-07-21")
    assert result["ok"] is True
    assert result["created"] is True
    assert new[0]["disposition"] == "surfaced"


def test_advance_refuses_to_create_at_an_advanced_state():
    new, result = gled.advance([], "dup:jscpd:a.md", "verified-fixed")
    assert result["ok"] is False
    assert result["reason"]
    assert new == []


def test_advance_stamps_todays_date_when_none_supplied():
    new, result = gled.advance([], "dup:jscpd:a.md", "surfaced")
    assert result["ok"] is True
    assert len(new[0]["date"]) == 10 and new[0]["date"].count("-") == 2


def test_advance_stamps_trade_fields():
    records = [_rec("dup:jscpd:a.md", "surfaced")]
    new, result = gled.advance(
        records, "dup:jscpd:a.md", "accepted", date="2026-07-21",
        reason="tolerated", metricAtDisposition={"cloneLines": 177},
        reraiseWhen="cloneLines grows", sweptSha="abc123", adjudicatedIn="s1")
    assert result["ok"] is True
    rec = new[0]
    assert rec["reason"] == "tolerated"
    assert rec["metricAtDisposition"] == {"cloneLines": 177}
    assert rec["reraiseWhen"] == "cloneLines grows"
    assert rec["sweptSha"] == "abc123"
    assert rec["adjudicatedIn"] == "s1"


# --- 6c. adjudicatedIn is set once, never overwritten ------------------------


def test_advance_does_not_overwrite_an_existing_adjudicated_in():
    records = [_rec("dup:jscpd:a.md", "filed", issue="#1", adjudicatedIn="sweep-1")]
    new, result = gled.advance(records, "dup:jscpd:a.md", "verified-fixed",
                               date="2026-07-21", adjudicatedIn="sweep-9")
    assert result["ok"] is True
    assert new[0]["adjudicatedIn"] == "sweep-1"


def test_advance_sets_adjudicated_in_only_on_adjudication():
    new, _ = gled.advance([], "dup:jscpd:a.md", "surfaced", adjudicatedIn="sweep-1")
    assert "adjudicatedIn" not in new[0]
    new2, _ = gled.advance(new, "dup:jscpd:a.md", "filed", issue="#1",
                           adjudicatedIn="sweep-1")
    assert new2[0]["adjudicatedIn"] == "sweep-1"


def test_advance_accepts_sweep_id_as_the_adjudication_stamp():
    new, _ = gled.advance([], "dup:jscpd:a.md", "surfaced")
    new, result = gled.advance(new, "dup:jscpd:a.md", "filed", issue="#1", sweepId="s3")
    assert result["ok"] is True
    assert new[0]["adjudicatedIn"] == "s3"


# --- 7. report-card outcome mix ---------------------------------------------


def _adjudicated(lens, n, disposition, sweep_ids, reason="r"):
    out = []
    for i in range(n):
        out.append(_rec("%s:tool:f%d.py" % (lens, i), disposition,
                        reason=reason, adjudicatedIn=sweep_ids[i % len(sweep_ids)]))
    return out


def test_report_card_outcome_mix_buckets():
    records = [
        _rec("dup:t:a", "filed", issue="#1", adjudicatedIn="s1"),
        _rec("dup:t:b", "verified-fixed", adjudicatedIn="s1"),
        _rec("dup:t:c", "accepted", reason="r", adjudicatedIn="s1"),
        _rec("dup:t:d", "reopened", adjudicatedIn="s1"),
        _rec("dup:t:e", "triaged-out", adjudicatedIn="s1"),
        _rec("dup:t:f", "declined", reason="r", adjudicatedIn="s1"),
        _rec("dup:t:g", "candidate"),
        _rec("dup:t:h", "surfaced"),
    ]
    card = gled.report_card(records)["dup"]
    assert card["adjudicated"] == 6
    assert card["for"] == 4
    assert card["against"] == 2
    assert card["actionability"] == 4 / 6


def test_report_card_is_per_lens():
    records = [
        _rec("dup:t:a", "filed", issue="#1", adjudicatedIn="s1"),
        _rec("hotspot:t:a", "triaged-out", adjudicatedIn="s1"),
    ]
    card = gled.report_card(records)
    assert set(card) == {"dup", "hotspot"}
    assert card["dup"]["for"] == 1
    assert card["hotspot"]["against"] == 1


def test_report_card_actionability_none_when_nothing_adjudicated():
    card = gled.report_card([_rec("dup:t:a", "surfaced")])["dup"]
    assert card["adjudicated"] == 0
    assert card["actionability"] is None
    assert card["benched"] is False
    assert card["reason"]


# --- 6. small-N benching guard ----------------------------------------------


def test_bench_needs_ten_adjudicated_nine_is_not_enough():
    records = _adjudicated("dup", 9, "triaged-out", ["s1", "s2", "s3"])
    card = gled.report_card(records)["dup"]
    assert card["adjudicated"] == 9
    assert card["sweeps"] == 3
    assert card["actionability"] == 0.0
    assert card["benched"] is False, "no benching authority below the evidence floor"


def test_bench_at_ten_adjudicated_and_three_sweeps():
    records = (_adjudicated("dup", 5, "triaged-out", ["s1", "s2", "s3"])
               + [_rec("dup:tool:g%d.py" % i, "filed", issue="#1",
                       adjudicatedIn=["s1", "s2", "s3"][i % 3]) for i in range(5)])
    card = gled.report_card(records)["dup"]
    assert card["adjudicated"] == 10
    assert card["sweeps"] == 3
    assert card["actionability"] == 0.5
    assert card["benched"] is True
    assert "bench" in card["reason"].lower()


def test_bench_needs_three_sweeps_two_is_not_enough():
    records = _adjudicated("dup", 10, "triaged-out", ["s1", "s2"])
    card = gled.report_card(records)["dup"]
    assert card["adjudicated"] == 10
    assert card["sweeps"] == 2
    assert card["actionability"] == 0.0
    assert card["benched"] is False, "no benching authority below the sweeps floor"


def test_no_bench_above_the_actionability_bar():
    records = (_adjudicated("dup", 1, "triaged-out", ["s1"])
               + [_rec("dup:tool:g%d.py" % i, "filed", issue="#1",
                       adjudicatedIn=["s1", "s2", "s3"][i % 3]) for i in range(19)])
    card = gled.report_card(records)["dup"]
    assert card["adjudicated"] == 20
    assert card["actionability"] == 0.95
    assert card["benched"] is False


def test_missing_adjudicated_in_forbids_benching_however_bad_the_rate(tmp_path):
    records = _adjudicated("dup", 9, "triaged-out", ["s1", "s2", "s3"])
    records.append(_rec("dup:tool:legacy.py", "triaged-out"))  # hand-written, no sweep id
    card = gled.report_card(records)["dup"]
    assert card["adjudicated"] == 10
    assert card["sweeps"] is None, "an unverifiable sweep history is not a sweep count"
    assert card["actionability"] == 0.0
    assert card["benched"] is False
    assert "adjudicatedIn" in card["reason"] or "history" in card["reason"]


def test_non_adjudicated_records_missing_adjudicated_in_do_not_poison_the_count():
    records = _adjudicated("dup", 10, "triaged-out", ["s1", "s2", "s3"])
    records.append(_rec("dup:tool:fresh.py", "surfaced"))
    card = gled.report_card(records)["dup"]
    assert card["sweeps"] == 3
    assert card["benched"] is True


def test_report_card_overrides_are_honored():
    records = _adjudicated("dup", 2, "triaged-out", ["s1"])
    card = gled.report_card(
        records, {"minAdjudicated": 2, "minSweeps": 1, "actionabilityBar": 0.5})["dup"]
    assert card["benched"] is True


def test_report_card_malformed_overrides_disable_benching():
    """Invalid reportCard overrides must not mute via defaults."""
    records = _adjudicated("dup", 10, "triaged-out", ["s1", "s2", "s3"])
    notes = []
    card = gled.report_card(records, {
        "minAdjudicated": "ten",
        "minSweeps": True,
        "actionabilityBar": "0.5",
    }, notes_out=notes)["dup"]
    assert card["benched"] is False
    assert any("benching disabled" in n for n in notes)
    assert any("minAdjudicated" in n for n in notes)
    assert any("minSweeps" in n for n in notes)
    assert any("actionabilityBar" in n for n in notes)

    notes2 = []
    card2 = gled.report_card(records, {
        "minAdjudicated": 0,
        "minSweeps": -1,
        "actionabilityBar": 1.5,
    }, notes_out=notes2)["dup"]
    assert card2["benched"] is False
    assert len(notes2) == 3


def test_report_card_excludes_ambiguous_normalized_groups_from_bench_evidence():
    """Ten colliding line-number identities must not manufacture a bench."""
    records = []
    for i in range(10):
        records.append(_rec(
            "fixture:tool:a.py:%d" % (i + 1), "triaged-out",
            adjudicatedIn="s%d" % (i % 3)))
    notes = []
    card = gled.report_card(records, notes_out=notes)
    assert "fixture" not in card or card["fixture"]["benched"] is False
    assert any("collision" in n or "ambiguous" in n.lower() for n in notes)


def test_metric_improved_honors_reraise_when_scope():
    record = _rec(
        "dup:t:a", "filed",
        metricAtDisposition={"cloneLines": 177, "files": 2},
        reraiseWhen="cloneLines grows")
    # Primary worsened, secondary improved — not fixed.
    assert gled.metric_improved(
        {"cloneLines": 180, "files": 1}, record) is False
    # Primary improved — fixed.
    assert gled.metric_improved(
        {"cloneLines": 100, "files": 2}, record) is True
    # Primary equal, secondary improved — not fixed (scoped key did not improve).
    assert gled.metric_improved(
        {"cloneLines": 177, "files": 1}, record) is False


def test_write_refuses_invalid_records_without_mutating(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    gled.write(repo, [_rec("dup:t:a", "filed", issue="#1")], now="2026-07-21")
    before = open(gs.ledger_path(repo), encoding="utf-8").read()
    out = gled.write(
        repo, [_rec("dup:t:a", "accepted")], now="2026-07-21")  # no reason
    assert out["ok"] is False
    assert out["reason"] == "invalid-records"
    assert open(gs.ledger_path(repo), encoding="utf-8").read() == before


def test_advance_refuses_accepted_without_a_reason():
    records = [_rec("dup:t:a", "surfaced")]
    new, result = gled.advance(records, "dup:t:a", "accepted")
    assert result["ok"] is False
    assert any("reason" in e for e in result.get("errors") or [])
    assert new[0]["disposition"] == "surfaced"


def test_report_card_defaults_match_the_ratified_bar():
    assert gled.REPORT_CARD_DEFAULTS["actionabilityBar"] == 0.90
    assert gled.REPORT_CARD_DEFAULTS["minAdjudicated"] == 10
    assert gled.REPORT_CARD_DEFAULTS["minSweeps"] == 3


def test_rendered_report_card_states_the_bench_in_one_line(tmp_path):
    records = _adjudicated("dup", 10, "triaged-out", ["s1", "s2", "s3"])
    text = gled.render(records, now="2026-07-21")
    assert "| lens |" in text
    assert "| dup |" in text
    bench_lines = [ln for ln in text.splitlines()
                   if ln.startswith("- ") and "dup" in ln and "benched" in ln]
    assert len(bench_lines) == 1, text


# --- 8. validation: won't-fixes carry their why ------------------------------


def test_validate_record_rejects_wont_fix_without_a_reason():
    for state in ("accepted", "declined"):
        ok, reasons = gled.validate_record(_rec("dup:t:a", state))
        assert ok is False
        assert any("reason" in r for r in reasons), reasons
        ok, _ = gled.validate_record(_rec("dup:t:a", state, reason="because"))
        assert ok is True


def test_validate_record_rejects_unhashable_id():
    ok, reasons = gled.validate_record({"id": ["a"], "disposition": "filed"})
    assert ok is False
    assert any("id" in r for r in reasons)
    assert gled.validate_record({"id": "", "disposition": "filed"})[0] is False
    assert gled.validate_record({"id": {"a": 1}, "disposition": "filed"})[0] is False


def test_validate_record_field_types():
    assert gled.validate_record(_rec("a:b:c", "not-a-state"))[0] is False
    assert gled.validate_record(_rec("a:b:c", "filed", date="07/21/2026"))[0] is False
    assert gled.validate_record(_rec("a:b:c", "filed", date="2026-13-99"))[0] is False
    assert gled.validate_record(_rec("a:b:c", "filed", issue=7))[0] is False
    assert gled.validate_record(_rec("a:b:c", "filed", metricAtDisposition=177))[0] is False
    assert gled.validate_record(_rec("a:b:c", "filed", reraiseWhen=1))[0] is False
    assert gled.validate_record(_rec("a:b:c", "filed", adjudicatedIn=1))[0] is False
    assert gled.validate_record("not a dict")[0] is False
    assert gled.validate_record(_rec("a:b:c", "filed", date="2026-07-21", issue="#1",
                                     metricAtDisposition={"cloneLines": 1},
                                     adjudicatedIn="s1"))[0] is True


def test_validate_records_rejects_duplicate_ids():
    ok, reasons = gled.validate_records([_rec("a:b:c", "filed"), _rec("a:b:c", "surfaced")])
    assert ok is False
    assert any("duplicate" in r for r in reasons), reasons
    assert gled.validate_records([_rec("a:b:c", "filed"), _rec("d:e:f", "surfaced")])[0] is True


def test_validated_records_survive_the_real_reader(tmp_path):
    """Anything validate_records accepts must also survive guardian_store.read_ledger."""
    repo = init_calibrated_repo(tmp_path)
    records = [
        _rec("dup:jscpd:a.md<->b.md", "accepted", reason="r",
             metricAtDisposition={"cloneLines": 177}, adjudicatedIn="s1"),
        _rec("hotspot:lizard:a/b.py", "filed", issue="#1", adjudicatedIn="s1"),
    ]
    assert gled.validate_records(records)[0] is True
    gled.write(repo, records, now="2026-07-21")
    read = gs.read_ledger(repo)
    assert read["status"] == "ok"
    assert len(read["records"]) == len(records)


# --- 9. lock contention ------------------------------------------------------


def test_write_returns_raced_and_leaves_the_file_untouched(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    first = [_rec("dup:jscpd:a.md", "filed", issue="#1")]
    assert gled.write(repo, first, now="2026-07-21")["ok"] is True
    before = open(gs.ledger_path(repo), "rb").read()

    lock = gs.sweep_lock_path(repo)
    file_lock.acquire(lock, ttl=gs.SWEEP_LOCK_TTL)
    try:
        out = gled.write(repo, [_rec("dup:jscpd:z.md", "filed", issue="#9")],
                         now="2026-07-22")
        assert out["ok"] is False
        assert out["reason"] == "raced"
    finally:
        file_lock.release(lock)
    assert open(gs.ledger_path(repo), "rb").read() == before


def test_write_locked_writes_under_a_held_lock(tmp_path):
    """commit_ledger already holds the sweep lock; _write_locked must not deadlock."""
    repo = init_calibrated_repo(tmp_path)
    lock = gs.sweep_lock_path(repo)
    file_lock.acquire(lock, ttl=gs.SWEEP_LOCK_TTL)
    try:
        out = gled._write_locked(repo, [_rec("dup:jscpd:a.md", "filed", issue="#1")],
                                 now="2026-07-21")
        assert out["ok"] is True
    finally:
        file_lock.release(lock)
    assert gs.read_ledger(repo)["status"] == "ok"


# --- 10. unknown fields survive ---------------------------------------------


def test_unknown_fields_survive_a_write_round_trip(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    records = [_rec("dup:jscpd:a.md", "accepted", reason="r",
                    ownerNote="hand-written: revisit after the shared-include decision",
                    someFutureField={"nested": [1, 2]})]
    gled.write(repo, records, now="2026-07-21")
    read = gs.read_ledger(repo)
    rec = read["byId"]["dup:jscpd:a.md"]
    assert rec["ownerNote"].startswith("hand-written")
    assert rec["someFutureField"] == {"nested": [1, 2]}


def test_advance_preserves_unknown_fields():
    records = [_rec("dup:jscpd:a.md", "surfaced", ownerNote="keep me")]
    new, result = gled.advance(records, "dup:jscpd:a.md", "filed", issue="#1")
    assert result["ok"] is True
    assert new[0]["ownerNote"] == "keep me"


# --- 11. both storage modes --------------------------------------------------


def test_ledger_round_trip_in_repo_mode(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    records = [_rec("dup:jscpd:a.md", "filed", issue="#1")]
    out = gled.write(repo, records, now="2026-07-21")
    assert out["path"] == os.path.join(
        repo, ".claude", "superheroes", "guardian", gs.LAYOUT["ledger"])
    assert gs.read_ledger(repo)["records"] == records


def test_ledger_round_trip_in_global_mode(tmp_path):
    repo = init_calibrated_repo(tmp_path, remote="git@github.com:o/r.git")
    root = str(tmp_path / "store")
    store = mr.ensure_project_store(repo, root=root)
    ensure_store(repo, root)
    cfg = os.path.join(store, "config")
    os.makedirs(cfg, exist_ok=True)
    sc.atomic_write(os.path.join(cfg, "core.md"), cm.render_core(
        {"verifyCommand": "true", "stackTags": [], "threatModel": "t", "patterns": ""},
        "confirmed", "2026-01-01", "2026-01-01"))
    mr.write_registry(repo, mr.GLOBAL, "rk", root=root, now="2026-06-21T00:00:00Z")

    records = [_rec("dup:jscpd:a.md", "accepted", reason="r", adjudicatedIn="s1")]
    out = gled.write(repo, records, root=root, now="2026-07-21")
    assert out["ok"] is True
    assert out["path"] == os.path.join(cfg, "guardian", gs.LAYOUT["ledger"])
    assert not os.path.exists(os.path.join(repo, ".claude", "superheroes", "guardian",
                                           gs.LAYOUT["ledger"]))
    assert gs.read_ledger(repo, root=root)["records"] == records


# --- CLI ---------------------------------------------------------------------


def test_cli_report_card_subprocess_smoke(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    records = _adjudicated("dup", 10, "triaged-out", ["s1", "s2", "s3"])
    gled.write(repo, records, now="2026-07-21")
    env = os.environ.copy()
    env["WORKHORSE_STORE_ROOT"] = str(tmp_path / "store")
    r = subprocess.run(
        [sys.executable, os.path.join(_LIB, "guardian_ledger.py"),
         "report-card", "--cwd", repo],
        capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["dup"]["adjudicated"] == 10
    assert out["dup"]["benched"] is True


def test_cli_render_subprocess_smoke(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    gled.write(repo, [_rec("dup:jscpd:a.md", "filed", issue="#1")], now="2026-07-21")
    env = os.environ.copy()
    env["WORKHORSE_STORE_ROOT"] = str(tmp_path / "store")
    r = subprocess.run(
        [sys.executable, os.path.join(_LIB, "guardian_ledger.py"),
         "render", "--cwd", repo],
        capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert "# Guardian dispositions ledger" in out["markdown"]


def test_cli_bad_input_reports_an_error_not_a_traceback(tmp_path):
    r = subprocess.run(
        [sys.executable, os.path.join(_LIB, "guardian_ledger.py"), "report-card",
         "--cwd", str(tmp_path / "nope")],
        capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    json.loads(r.stdout)


# --- WO-13: surgical fence preserve + metric validation ----------------------


def test_write_preserves_bytes_outside_machine_regions_and_unknown_keys(tmp_path):
    """Strong preservation: owner prose outside both machine regions + unknown JSON keys."""
    repo = init_calibrated_repo(tmp_path)
    path = gs.ledger_path(repo)
    owner_outside = (
        "<!-- guardian-ledger: schemaVersion=1 status=confirmed "
        "created=2026-07-01 updated=2026-07-01 -->\n\n"
        "# Owner title — must survive\n\n"
        "Owner hand-written prose before the fence.\n\n"
        "<!-- owner comment outside fence -->\n\n"
        "<!-- guardian-report-card:begin updated=2026-07-01 -->\n\n"
        "## Report card\n\n"
        "_No findings adjudicated yet._\n\n"
        "<!-- guardian-report-card:end -->\n\n"
    )
    block = {
        "schemaVersion": 1,
        "ownerNotes": "keep this top-level unknown",
        "records": [{
            "id": "dup:jscpd:a.md",
            "disposition": "accepted",
            "date": "2026-07-01",
            "issue": None,
            "metricAtDisposition": {"cloneLines": 10},
            "reason": "tolerated",
            "reraiseWhen": None,
            "ownerAnnotation": "per-record unknown must survive",
        }],
        "sweeps": [{"sweepId": "s0", "sweptSha": "abc", "date": "2026-07-01"}],
    }
    text = (
        owner_outside
        + "```json %s\n%s\n```\n\n"
        "Trailing owner prose after the fence.\n" % (
            gs.LEDGER_FENCE, json.dumps(block, indent=2))
    )
    sc.atomic_write(path, text)
    before = open(path, encoding="utf-8").read()
    fence_m = gs._LEDGER_BLOCK.search(before)
    card_m = gled._REPORT_CARD_REGION.search(before)
    assert fence_m is not None and card_m is not None
    owner_before = before[:card_m.start()] + before[card_m.end():fence_m.start()] + before[fence_m.end():]

    new_records = [{
        "id": "dup:jscpd:a.md",
        "disposition": "accepted",
        "date": "2026-07-01",
        "issue": None,
        "metricAtDisposition": {"cloneLines": 12},
        "reason": "tolerated",
        "reraiseWhen": None,
        "adjudicatedIn": "s0",
    }]
    out = gled.write(
        repo, new_records, now="2026-07-21",
        sweeps=[{"sweepId": "s0", "sweptSha": "abc", "date": "2026-07-01"},
                {"sweepId": "s1", "sweptSha": "def", "date": "2026-07-21"}])
    assert out["ok"] is True, out
    after = open(path, encoding="utf-8").read()
    fence_after = gs._LEDGER_BLOCK.search(after)
    card_after = gled._REPORT_CARD_REGION.search(after)
    assert fence_after is not None and card_after is not None
    owner_after = (
        after[:card_after.start()] + after[card_after.end():fence_after.start()]
        + after[fence_after.end():]
    )
    assert owner_after == owner_before
    assert "guardian-report-card:begin updated=2026-07-21" in card_after.group(0)
    assert "_No findings adjudicated yet._" not in card_after.group(0)
    parsed = json.loads(fence_after.group(1))
    assert parsed["ownerNotes"] == "keep this top-level unknown"
    assert parsed["records"][0]["ownerAnnotation"] == "per-record unknown must survive"
    assert parsed["records"][0]["metricAtDisposition"]["cloneLines"] == 12
    assert len(parsed["sweeps"]) == 2


def test_write_skips_when_fence_missing(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    path = gs.ledger_path(repo)
    sc.atomic_write(path, "# no fence here\nowner prose only\n")
    before = open(path, "rb").read()
    out = gled.write(repo, [_rec("a:b:c", "filed", issue="#1")])
    assert out["ok"] is False
    assert "no-fence" in (out.get("skipped") or "")
    assert open(path, "rb").read() == before


def test_write_refuses_ambiguous_duplicate_fences(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    path = gs.ledger_path(repo)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    block = {
        "schemaVersion": 1,
        "records": [_rec("dup:t:a", "accepted", date="2026-07-01", reason="r")],
        "sweeps": [],
    }
    body = json.dumps(block, indent=2)
    text = (
        "# two fences\n\n"
        "```json %s\n%s\n```\n\n"
        "```json %s\n%s\n```\n" % (gs.LEDGER_FENCE, body, gs.LEDGER_FENCE, body)
    )
    open(path, "wb").write(text.encode("utf-8"))
    before = open(path, "rb").read()
    out = gled.write(repo, [_rec("dup:t:a", "accepted", date="2026-07-01", reason="r")])
    assert out["ok"] is False
    assert "ambiguous" in (out.get("skipped") or out.get("reason") or "")
    assert open(path, "rb").read() == before
    read = gs.read_ledger(repo)
    assert read["status"] == "malformed"
    assert "ambiguous" in (read.get("note") or "")


def test_write_never_clobber_merges_concurrent_owner_edit(tmp_path):
    """Concurrent owner edit between read and write is merged, not clobbered."""
    repo = init_calibrated_repo(tmp_path)
    path = gs.ledger_path(repo)
    gled.write(repo, [_rec("dup:t:a", "filed", issue="#1", adjudicatedIn="s1")],
               now="2026-07-01")
    ledger = gs.read_ledger(repo)
    assert ledger["status"] == "ok"

    # Owner adds a new record between finalize's read and write.
    on_disk = open(path, "rb").read().decode("utf-8")
    fence = gs.find_ledger_fences(on_disk)[0]
    block = json.loads(fence.group(1))
    block["records"].append({
        "id": "dup:t:owner-added",
        "disposition": "accepted",
        "date": "2026-07-21",
        "issue": None,
        "metricAtDisposition": None,
        "reason": "owner concurrent edit",
        "reraiseWhen": None,
    })
    mutated = (
        on_disk[:fence.start()]
        + "```json %s\n%s\n```" % (gs.LEDGER_FENCE, json.dumps(block, indent=2))
        + on_disk[fence.end():]
    )
    open(path, "wb").write(mutated.encode("utf-8"))

    out = gled.write(repo, ledger["records"], now="2026-07-21")
    assert out["ok"] is True, out
    ids = {r.get("id") for r in gs.read_ledger(repo)["records"]}
    assert "dup:t:owner-added" in ids
    assert "dup:t:a" in ids


def test_write_preserves_disk_only_record_ids(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    path = gs.ledger_path(repo)
    gled.write(repo, [
        _rec("dup:t:a", "accepted", date="2026-07-01", reason="r", adjudicatedIn="s1"),
        _rec("dup:t:b", "filed", issue="#2", adjudicatedIn="s1"),
    ], now="2026-07-01")
    # Stale roster omits b — writer must retain it.
    out = gled.write(
        repo, [_rec("dup:t:a", "accepted", date="2026-07-01", reason="r",
                    adjudicatedIn="s1")],
        now="2026-07-21")
    assert out["ok"] is True, out
    ids = {r["id"] for r in gs.read_ledger(repo)["records"]}
    assert ids == {"dup:t:a", "dup:t:b"}


def test_write_crlf_byte_preservation_outside_machine_regions(tmp_path):
    """Genuine CRLF bytes outside machine regions must survive a surgical write."""
    repo = init_calibrated_repo(tmp_path)
    path = gs.ledger_path(repo)
    block = {
        "schemaVersion": 1,
        "records": [{
            "id": "dup:t:a",
            "disposition": "accepted",
            "date": "2026-07-01",
            "issue": None,
            "metricAtDisposition": {"cloneLines": 1},
            "reason": "r",
            "reraiseWhen": None,
        }],
        "sweeps": [],
    }
    fence_body = json.dumps(block, indent=2)
    # Outer document uses CRLF; fence JSON body keeps LF (as json.dumps emits).
    text = (
        "<!-- guardian-ledger: schemaVersion=1 status=confirmed "
        "created=2026-07-01 updated=2026-07-01 -->\r\n"
        "\r\n"
        "# Owner CRLF title\r\n"
        "\r\n"
        "Owner prose with CRLF endings.\r\n"
        "\r\n"
        "<!-- guardian-report-card:begin updated=2026-07-01 -->\r\n"
        "\r\n"
        "## Report card\r\n"
        "\r\n"
        "_No findings adjudicated yet._\r\n"
        "\r\n"
        "<!-- guardian-report-card:end -->\r\n"
        "\r\n"
        "```json %s\n%s\n```\r\n"
        "\r\n"
        "Trailing CRLF prose.\r\n"
    ) % (gs.LEDGER_FENCE, fence_body)
    raw = text.encode("utf-8")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "wb").write(raw)
    before = open(path, "rb").read()
    assert b"\r\n# Owner CRLF title\r\n" in before

    card_begin = b"<!-- guardian-report-card:begin"
    card_end_marker = b"<!-- guardian-report-card:end -->"
    fence_open = ("```json %s" % gs.LEDGER_FENCE).encode("utf-8")
    i0 = before.find(card_begin)
    i1 = before.find(card_end_marker) + len(card_end_marker)
    i2 = before.find(fence_open)
    # Closing fence: last ``` before trailing prose
    i3 = before.find(b"```", i2 + len(fence_open))
    assert i3 > i2
    # Include trailing newline sequence after closing fence
    i3_end = i3 + 3
    if before[i3_end:i3_end + 2] == b"\r\n":
        i3_end += 2
    elif before[i3_end:i3_end + 1] == b"\n":
        i3_end += 1
    prefix, mid, suffix = before[:i0], before[i1:i2], before[i3_end:]

    out = gled.write(
        repo, [{
            "id": "dup:t:a",
            "disposition": "accepted",
            "date": "2026-07-01",
            "issue": None,
            "metricAtDisposition": {"cloneLines": 2},
            "reason": "r",
            "reraiseWhen": None,
            "adjudicatedIn": "s1",
        }],
        now="2026-07-21")
    assert out["ok"] is True, out
    after = open(path, "rb").read()
    j0 = after.find(card_begin)
    j1 = after.find(card_end_marker) + len(card_end_marker)
    j2 = after.find(fence_open)
    j3 = after.find(b"```", j2 + len(fence_open))
    j3_end = j3 + 3
    if after[j3_end:j3_end + 2] == b"\r\n":
        j3_end += 2
    elif after[j3_end:j3_end + 1] == b"\n":
        j3_end += 1
    assert after[:j0] == prefix
    assert after[j1:j2] == mid
    assert after[j3_end:] == suffix
    assert b"\r\n# Owner CRLF title\r\n" in after


def test_report_card_updates_across_two_writes(tmp_path):
    """Second face must refresh: empty card → adjudicated table across two writes."""
    repo = init_calibrated_repo(tmp_path)
    path = gs.ledger_path(repo)
    gled.write(repo, [], now="2026-07-01")
    first = open(path, encoding="utf-8").read()
    assert "_No findings adjudicated yet._" in first
    assert "guardian-report-card:begin updated=2026-07-01" in first

    records = [
        _rec("dup:t:a", "accepted", date="2026-07-21", reason="ok", adjudicatedIn="s1"),
        _rec("dup:t:b", "filed", issue="#1", adjudicatedIn="s1"),
    ]
    gled.write(repo, records, now="2026-07-21")
    second = open(path, encoding="utf-8").read()
    card = gled._REPORT_CARD_REGION.search(second)
    assert card is not None
    body = card.group(0)
    assert "guardian-report-card:begin updated=2026-07-21" in body
    assert "_No findings adjudicated yet._" not in body
    assert "| dup |" in body
    assert "created=2026-07-01" in second
    # Owner-facing preamble (outside machine regions) still present.
    assert "# Guardian dispositions ledger" in second


def test_validate_record_rejects_non_numeric_metric_values():
    ok, reasons = gled.validate_record(_rec(
        "dup:t:a", "accepted", reason="r",
        metricAtDisposition={"cloneLines": "many"}))
    assert ok is False
    assert any("cloneLines" in r for r in reasons)
    ok2, _ = gled.validate_record(_rec(
        "dup:t:a", "accepted", reason="r",
        metricAtDisposition={"cloneLines": True}))
    assert ok2 is False
    ok3, _ = gled.validate_record(_rec(
        "dup:t:a", "accepted", reason="r",
        metricAtDisposition={"": 1}))
    assert ok3 is False


def test_report_card_degraded_config_revokes_benching():
    records = [
        _rec("dup:t:%d" % i, "triaged-out", adjudicatedIn="s%d" % (i % 3))
        for i in range(10)
    ]
    notes = []
    card = gled.report_card(records, notes_out=notes, config_status="degraded")
    assert card["dup"]["benched"] is False
    assert any("degraded" in n for n in notes)


# --- WO-1 never-clobber write + unbalanced report-card markers ---------------


def test_write_never_clobber_retries_and_preserves_owner_prose(tmp_path, monkeypatch):
    """Fence identity change at the final re-check triggers retry, not clobber."""
    repo = init_calibrated_repo(tmp_path)
    path = gs.ledger_path(repo)
    owner_note = "OWNER_PROSE_MUST_SURVIVE_NEVER_CLOBBER"
    gled.write(repo, [_rec("dup:t:a", "filed", issue="#1", adjudicatedIn="s1")],
               now="2026-07-01")
    text = open(path, encoding="utf-8").read()
    fence = gs.find_ledger_fences(text)[0]
    seeded = text[:fence.start()] + owner_note + "\n\n" + text[fence.start():]
    open(path, "wb").write(seeded.encode("utf-8"))

    real_prepare = gled._prepare_ledger_write
    calls = {"n": 0}

    def prepare_with_fence_race(path_, *a, **k):
        prepared = real_prepare(path_, *a, **k)
        calls["n"] += 1
        # After first prepare, mutate fence + prose before the final re-check.
        if calls["n"] == 1 and prepared.get("kind") == "splice":
            cur = open(path, encoding="utf-8").read()
            f = gs.find_ledger_fences(cur)[0]
            block = json.loads(f.group(1))
            block["ownerNotes"] = "concurrent"
            new_text = (
                cur[:f.start()] + "CONCURRENT_OWNER_EDIT\n\n"
                + "```json %s\n%s\n```" % (gs.LEDGER_FENCE, json.dumps(block, indent=2))
                + cur[f.end():]
            )
            open(path, "wb").write(new_text.encode("utf-8"))
        return prepared

    monkeypatch.setattr(gled, "_prepare_ledger_write", prepare_with_fence_race)
    out = gled.write(
        repo, [_rec("dup:t:a", "filed", issue="#1", adjudicatedIn="s1")],
        now="2026-07-21")
    assert out["ok"] is True, out
    after = open(path, encoding="utf-8").read()
    assert owner_note in after
    assert "CONCURRENT_OWNER_EDIT" in after
    assert calls["n"] >= 2  # at least one retry cycle


def test_write_never_clobber_retries_on_prose_only_edit(tmp_path, monkeypatch):
    """Prose-only owner edit (fence unchanged) must retry — full-byte guard, not fence id."""
    repo = init_calibrated_repo(tmp_path)
    path = gs.ledger_path(repo)
    owner_note = "OWNER_PROSE_MUST_SURVIVE_NEVER_CLOBBER"
    gled.write(repo, [_rec("dup:t:a", "filed", issue="#1", adjudicatedIn="s1")],
               now="2026-07-01")
    text = open(path, encoding="utf-8").read()
    fence = gs.find_ledger_fences(text)[0]
    seeded = text[:fence.start()] + owner_note + "\n\n" + text[fence.start():]
    open(path, "wb").write(seeded.encode("utf-8"))

    prose_only = "PROSE_ONLY_CONCURRENT_EDIT"
    real_prepare = gled._prepare_ledger_write
    calls = {"n": 0}

    def prepare_with_prose_race(path_, *a, **k):
        prepared = real_prepare(path_, *a, **k)
        calls["n"] += 1
        if calls["n"] == 1 and prepared.get("kind") == "splice":
            cur_text = open(path, encoding="utf-8").read()
            f = gs.find_ledger_fences(cur_text)[0]
            # Insert prose before the fence; leave fence bytes identical.
            new_text = cur_text[:f.start()] + prose_only + "\n\n" + cur_text[f.start():]
            open(path, "wb").write(new_text.encode("utf-8"))
            # Fence identity alone would miss this race — that is the defect.
            assert gs.ledger_fence_identity(new_text) == gs.ledger_fence_identity(cur_text)
        return prepared

    monkeypatch.setattr(gled, "_prepare_ledger_write", prepare_with_prose_race)
    out = gled.write(
        repo, [_rec("dup:t:a", "filed", issue="#1", adjudicatedIn="s1")],
        now="2026-07-21")
    assert out["ok"] is True, out
    after = open(path, encoding="utf-8").read()
    assert owner_note in after
    assert prose_only in after
    assert calls["n"] >= 2  # retried after prose-only race
    # Same effective ledger content → Fix 8 keeps the prior updated= date.
    assert "guardian-report-card:begin updated=2026-07-01" in after


def test_write_raced_out_after_five_attempts(tmp_path, monkeypatch):
    repo = init_calibrated_repo(tmp_path)
    path = gs.ledger_path(repo)
    gled.write(repo, [_rec("dup:t:a", "filed", issue="#1")], now="2026-07-01")
    writes = []
    real_awb = gs.atomic_write_bytes

    def track_awb(p, b):
        writes.append(p)
        return real_awb(p, b)

    monkeypatch.setattr(gs, "atomic_write_bytes", track_awb)

    real_prepare = gled._prepare_ledger_write
    state = {"n": 0}

    def always_race(path_, *a, **k):
        prepared = real_prepare(path_, *a, **k)
        state["n"] += 1
        if prepared.get("kind") == "splice":
            # Mutate after every prepare so the full-byte recheck never matches.
            cur = open(path, encoding="utf-8").read()
            f = gs.find_ledger_fences(cur)[0]
            block = json.loads(f.group(1))
            block["raceToken"] = state["n"]
            new_text = (
                cur[:f.start()]
                + "```json %s\n%s\n```" % (gs.LEDGER_FENCE, json.dumps(block, indent=2))
                + cur[f.end():]
            )
            open(path, "wb").write(new_text.encode("utf-8"))
        return prepared

    monkeypatch.setattr(gled, "_prepare_ledger_write", always_race)
    out = gled.write(repo, [_rec("dup:t:a", "filed", issue="#1")], now="2026-07-21")
    assert out["ok"] is False
    assert out["reason"] == "raced-out"
    assert out["attempts"] == 5
    assert writes == [], "writer must not land a stale splice on raced-out"


def test_splice_unbalanced_report_card_begin_does_not_eat_owner_prose(tmp_path):
    """A stray begin marker must fail closed — never splice across owner prose."""
    repo = init_calibrated_repo(tmp_path)
    path = gs.ledger_path(repo)
    owner_prose = "OWNER_PROSE_BETWEEN_STRAY_AND_REAL"
    card = (
        "<!-- guardian-report-card:begin updated=2026-07-01 -->\n\n"
        "## Report card\n\n_ok_\n\n"
        "<!-- guardian-report-card:end -->\n\n"
    )
    block = {
        "schemaVersion": 1,
        "records": [{
            "id": "dup:t:a",
            "disposition": "accepted",
            "date": "2026-07-01",
            "issue": None,
            "metricAtDisposition": None,
            "reason": "r",
            "reraiseWhen": None,
        }],
        "sweeps": [],
    }
    # Stray begin, then owner prose, then a balanced region — non-greedy match would
    # otherwise span from the stray begin to the real end and eat the prose.
    text = (
        "# Ledger\n\n"
        "<!-- guardian-report-card:begin -->\n\n"
        + owner_prose + "\n\n"
        + card
        + "```json %s\n%s\n```\n" % (gs.LEDGER_FENCE, json.dumps(block, indent=2))
    )
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "wb").write(text.encode("utf-8"))
    before = open(path, "rb").read()

    spliced, err = gled._splice_machine_regions(
        text, block, "<!-- guardian-report-card:begin updated=2026-07-21 -->\n"
                     "## Report card\n\n_new_\n\n"
                     "<!-- guardian-report-card:end -->\n")
    assert spliced is None
    assert err == "ambiguous-report-card"

    out = gled.write(
        repo, [_rec("dup:t:a", "accepted", date="2026-07-01", reason="r")],
        now="2026-07-21")
    assert out["ok"] is False
    assert "ambiguous" in (out.get("skipped") or out.get("reason") or "")
    after = open(path, "rb").read()
    assert after == before
    assert owner_prose.encode("utf-8") in after


def test_read_sweeps_result_distinguishes_read_failed(tmp_path, monkeypatch):
    repo = init_calibrated_repo(tmp_path)
    path = gs.ledger_path(repo)
    gled.write(repo, [], now="2026-07-01")
    status_ok, sweeps_ok = gled._read_sweeps_result(path)
    assert status_ok == "ok"
    assert sweeps_ok == []

    missing = str(tmp_path / "no-such-ledger.md")
    status_abs, sweeps_abs = gled._read_sweeps_result(missing)
    assert status_abs == "absent"
    assert sweeps_abs == []

    real_open = open

    def boom(name, *a, **k):
        if os.path.abspath(str(name)) == os.path.abspath(path):
            raise OSError("simulated")
        return real_open(name, *a, **k)

    monkeypatch.setattr("builtins.open", boom)
    status_fail, sweeps_fail = gled._read_sweeps_result(path)
    assert status_fail == "read-failed"
    assert sweeps_fail == []
    # Legacy helper still collapses to []
    assert gled._read_sweeps(path) == []


# --- WO-1c: atomic commit under lock / append-only merge / never-clobber author ---


def test_prepare_append_only_merge_preserves_concurrent_sweep_entry(tmp_path):
    """A sweep appended between caller's roster read and write is not lost (Fix 2)."""
    repo = init_calibrated_repo(tmp_path)
    path = gs.ledger_path(repo)
    s1 = {"sweepId": "s1", "sweptSha": "aaa", "date": "2026-07-20"}
    s_concurrent = {"sweepId": "s-concurrent", "sweptSha": "bbb", "date": "2026-07-21"}
    s_caller = {"sweepId": "s-caller", "sweptSha": "ccc", "date": "2026-07-22"}
    assert gled.write(repo, [], sweeps=[s1], now="2026-07-20")["ok"] is True

    # Caller read roster as [s1], then concurrent writer appended s_concurrent.
    text = open(path, encoding="utf-8").read()
    fence = gs.find_ledger_fences(text)[0]
    block = json.loads(fence.group(1))
    block["sweeps"] = [s1, s_concurrent]
    open(path, "wb").write((
        text[:fence.start()]
        + "```json %s\n%s\n```" % (gs.LEDGER_FENCE, json.dumps(block, indent=2))
        + text[fence.end()]
    ).encode("utf-8"))

    # Stale caller passes only what it knew + its own append — must keep concurrent.
    out = gled.write(repo, [], sweeps=[s1, s_caller], now="2026-07-22")
    assert out["ok"] is True, out
    after = json.loads(gs.find_ledger_fences(
        open(path, encoding="utf-8").read())[0].group(1))
    ids = [s["sweepId"] for s in after["sweeps"]]
    assert ids == ["s1", "s-concurrent", "s-caller"]


def test_write_author_path_does_not_clobber_concurrently_created_ledger(
        tmp_path, monkeypatch):
    """Exclusive create: a ledger born between absence check and author write survives (Fix 3)."""
    repo = init_calibrated_repo(tmp_path)
    path = gs.ledger_path(repo)
    assert not os.path.isfile(path)

    concurrent_records = [
        _rec("dup:t:concurrent", "accepted", date="2026-07-01", reason="r",
             adjudicatedIn="s0"),
    ]
    concurrent_bytes = gled.render(
        concurrent_records, sweeps=[], now="2026-07-01").encode("utf-8")
    real_prepare = gled._prepare_ledger_write
    calls = {"n": 0}

    def prepare_then_create(path_, *a, **k):
        prepared = real_prepare(path_, *a, **k)
        calls["n"] += 1
        if calls["n"] == 1 and prepared.get("kind") == "author":
            os.makedirs(os.path.dirname(path), exist_ok=True)
            open(path, "wb").write(concurrent_bytes)
        return prepared

    monkeypatch.setattr(gled, "_prepare_ledger_write", prepare_then_create)
    out = gled.write(
        repo, [_rec("dup:t:stale", "filed", issue="#1", adjudicatedIn="s1")],
        now="2026-07-21")
    assert out["ok"] is True, out
    read = gs.read_ledger(repo)
    ids = {r["id"] for r in read["records"]}
    assert "dup:t:concurrent" in ids, "concurrent author must not be clobbered"
    assert "dup:t:stale" in ids  # caller's record merges onto the concurrent ledger


def test_write_persisted_report_card_reflects_disk_only_record(tmp_path):
    """Card is computed from final merged records, not a stale collect-time card (Fix 4)."""
    repo = init_calibrated_repo(tmp_path)
    path = gs.ledger_path(repo)
    gled.write(repo, [
        _rec("dup:t:disk-only", "accepted", date="2026-07-01", reason="kept",
             adjudicatedIn="s1"),
        _rec("dup:t:shared", "filed", issue="#1", adjudicatedIn="s1"),
    ], now="2026-07-01")
    # Stale caller omits disk-only and passes a collect-time card that never saw it.
    stale_card = gled.report_card([
        _rec("dup:t:shared", "filed", issue="#1", adjudicatedIn="s1"),
    ])
    out = gled.write(
        repo,
        [_rec("dup:t:shared", "filed", issue="#1", adjudicatedIn="s1")],
        report_card=stale_card,
        now="2026-07-21")
    assert out["ok"] is True, out
    text = open(path, encoding="utf-8").read()
    card_region = gled._REPORT_CARD_REGION.search(text).group(0)
    assert "| dup |" in card_region
    # Disk-only accepted record must count in the persisted card's for-bucket.
    assert "| 2 |" in card_region or "adjudicated" in card_region.lower()
    # Parse the table row for dup: adjudicated should be 1 (the accepted), for=1.
    rows = [ln for ln in card_region.splitlines() if ln.startswith("| dup |")]
    assert rows, card_region
    cols = [c.strip() for c in rows[0].split("|")[1:-1]]
    # lens | adjudicated | for | against | ...
    # Merged: disk-only accepted + shared filed → adjudicated=2, for=2.
    # Stale collect-time card would only see the filed → adjudicated=1, for=1.
    assert int(cols[1]) == 2, "persisted card must count disk-only record: %s" % rows[0]
    assert int(cols[2]) == 2, "disk-only accepted must appear in for-count: %s" % rows[0]


def test_merge_record_never_clobbers_existing_adjudicated_in():
    """Write-once adjudicatedIn on disk survives a merge that tries to clear/replace it (Fix 5)."""
    old = _rec("dup:t:a", "filed", issue="#1", adjudicatedIn="sweep-original")
    new = _rec("dup:t:a", "verified-fixed", adjudicatedIn="sweep-intruder")
    merged = gled._merge_record_preserving_unknown(old, new)
    assert merged["adjudicatedIn"] == "sweep-original"
    assert merged["disposition"] == "verified-fixed"

    cleared = gled._merge_record_preserving_unknown(
        old, _rec("dup:t:a", "verified-fixed", adjudicatedIn=""))
    assert cleared["adjudicatedIn"] == "sweep-original"

    emptied = gled._merge_record_preserving_unknown(
        old, _rec("dup:t:a", "verified-fixed", adjudicatedIn=None))
    assert emptied["adjudicatedIn"] == "sweep-original"

    # First stamp still lands when disk had none.
    bare = _rec("dup:t:b", "filed", issue="#2")
    stamped = gled._merge_record_preserving_unknown(
        bare, _rec("dup:t:b", "filed", issue="#2", adjudicatedIn="s-new"))
    assert stamped["adjudicatedIn"] == "s-new"
