"""The review record flags redacted text: every posted record lists the path of each field whose text reads
`[REDACTED` under `transitDamage.redactedFields`, and its summary says so. A credential-shaped string is built from
pieces at runtime, never written whole."""
import json
from pathlib import Path

import pytest

import review_record as rr
from test_review_record import GOOD_RUN, Fake, account, build, finding, put, send
from test_review_record_fit_c7l3 import SEATS, many_findings, panel_rows, parts_of

SECRET = "pass" + "word = " + "x" * 8
FIXTURE = Path(__file__).parent / "fixtures" / "review_record_redacted" / "pr2113_record_6378109042.json"
PR2113_FIELDS = ["findings[1].body", "findings[2].body", "findings[2].id"]
PR2113_LINE = ("Transit damage: redacted text in 3 recorded fields, so that text is lost: "
               "findings[1].body, findings[2].body, findings[2].id.")


def posted(fake):
    """The record in each record comment the writer posted, oldest first."""
    by_id = {c["id"]: c for c in fake.comments}
    return [rr._parse_body(c["body"], by_id) for c in fake.marked()]


def summary_of(body):
    return body.split("<details>")[0]


# --- T1: PR #2113's recorded record ---

def test_pr2113_record_reads_flagged_and_its_summary_says_text_was_lost():
    # axis: a record already holding [REDACTED FIELD] (PR #2113) posted with no flag and no summary line
    rec = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert "transitDamage" not in rec
    body = rr.render(rec)
    assert rr._parse_body(body)["transitDamage"] == {"redactedFields": PR2113_FIELDS}
    assert PR2113_LINE in summary_of(body)


# --- T2: the writer ---

def test_a_finding_whose_body_the_writer_withholds_is_flagged_in_the_record_it_posts(tmp_path):
    # axis: the writer's own withholding of a credential-shaped body posted without the flag
    fake = Fake()
    send(tmp_path, fake, findings=[finding(body="see " + SECRET)])
    [comment] = fake.marked()
    rec = rr._parse_body(comment["body"])
    assert rec["findings"][0]["body"] == "[REDACTED FIELD]"
    assert rec["transitDamage"] == {"redactedFields": ["findings[0].body"]}
    assert "Transit damage: redacted text in 1 recorded field, so that text is lost: findings[0].body." in summary_of(
        comment["body"])
    assert rr._redacted_paths(rec) == rec["transitDamage"]["redactedFields"]


# --- T3: unchanged when clean ---

def test_a_clean_account_posts_no_flag_and_no_line(tmp_path):
    # axis: a record with no redacted text gaining a transitDamage key or a Transit damage line
    fake = Fake()
    send(tmp_path, fake, findings=[finding(body="plain text")])
    [comment] = fake.marked()
    assert "transitDamage" not in rr._parse_body(comment["body"])
    assert "Transit damage" not in comment["body"]


def test_a_clean_record_renders_identically_with_the_flagging_step_removed(monkeypatch):
    # axis: the flagging step changing a clean record's bytes, in one comment or in parts
    for rec in (build(account(findings=[finding(body="plain text")])),
                build(account(findings=many_findings(40, 4000)))):
        plan = rr.render_plan(rec)
        with monkeypatch.context() as m:
            m.setattr(rr, "_flag_redactions", lambda r: r)
            plain = rr.render_plan(rec)
        assert plan.parts == plain.parts and plan.head([1, 2, 3]) == plain.head([1, 2, 3])
    assert "Transit damage" not in plan.head([1, 2, 3])


# --- T4: parts merge ---

def test_parts_changed_in_transit_keep_the_redacted_fields_beside_the_length_and_hash_keys(tmp_path):
    # axis: the read's length/hash report replacing the writer's redactedFields instead of joining them
    fake = Fake()
    found = many_findings(40, 4000)
    found[0] = finding("f-000", body="see " + SECRET)
    send(tmp_path, fake, findings=found)
    assert len(parts_of(fake)) >= 2
    assert "Transit damage: redacted text in 1 recorded field" in summary_of(fake.marked()[0]["body"])
    part = parts_of(fake)[0]
    assert "reads the saved" in part["body"]
    part["body"] = part["body"].replace("reads the saved", "reads the SAVED", 1)
    out = rr.read(7, readers=fake.readers())
    idx = [f["body"] for f in out["findings"]].index("[REDACTED FIELD]")
    damage = out["transitDamage"]
    assert damage["redactedFields"] == [f"findings[{idx}].body"]
    assert damage["hashMatches"] is False
    assert {"recordedChars", "foundChars"} <= set(damage)


# --- T5: propagation to later records ---

def test_a_later_record_lists_an_earlier_one_that_held_redacted_text(tmp_path):
    # axis: an earlier record with redacted text hidden from the vet by the next writes
    fake = Fake()
    send(tmp_path, fake, findings=[finding(body="see " + SECRET)])
    first = fake.marked()[0]
    send(tmp_path, fake, findings=[finding(body="plain text")])
    send(tmp_path, fake, findings=[finding(body="plain text")])
    third = posted(fake)[2]
    listed = [e for e in third["earlierRecordsNotChecked"] if e["id"] == first["id"]]
    assert listed == [{"id": first["id"], "url": first["url"], "why": "redacted text"}]


def test_an_earlier_record_changed_in_transit_still_reads_changed_in_transit(tmp_path):
    # axis: the redacted-text reason taking over a record that also carries the length/hash keys
    fake = Fake()
    found = many_findings(40, 4000)
    found[0] = finding("f-000", body="see " + SECRET)
    send(tmp_path, fake, findings=found)
    part = parts_of(fake)[0]
    part["body"] = part["body"].replace("reads the saved", "reads the SAVED", 1)
    damaged = fake.marked()[0]
    send(tmp_path, fake, findings=found)
    later = posted(fake)[-1]
    assert [e for e in later["earlierRecordsNotChecked"] if e["id"] == damaged["id"]] == [
        {"id": damaged["id"], "url": damaged["url"], "why": "changed in transit"}]


# --- T6: the compact line ---

def test_the_compact_levels_give_the_count_with_the_listed_note_and_no_path():
    # axis: the compact summary levels naming paths instead of counting them
    rec = rr._flag_redactions(rr._scrubbed(build(account(findings=[finding(body="see " + SECRET)]))))
    assert rec["transitDamage"] == {"redactedFields": ["findings[0].body"]}
    line = f"Transit damage: redacted text in 1 recorded field {rr.LISTED}, so that text is lost."
    for level in (1, 2):
        text = rr._summary(rec, level)
        assert line in text and "findings[0].body" not in text
    assert "findings[0].body" in rr._summary(rec, 0)


def test_a_parts_head_that_only_fits_compact_still_carries_the_line(tmp_path):
    # axis: the compact summary level (the parts head's) reading the unflagged record, or naming the path instead of counting
    fake = Fake()
    idx = 40
    ids = [f"{i:03d}" + "x" * 897 for i in range(78)]
    found = [finding(i, title=f"t{n}", outcome="left-for-owner", reason="waits") for n, i in enumerate(ids)]
    found[idx] = dict(found[idx], body="see " + SECRET)
    out = send(tmp_path, fake, findings=found)
    head = fake.marked()[0]["body"]
    assert out["parts"] >= 1
    assert "Waiting for the owner: 78 findings left for the owner (listed in the full record)" in head
    assert ("Transit damage: redacted text in 1 recorded field (listed in the full record), so that text is lost."
            in summary_of(head))
    assert f"findings[{idx}].body" not in head
    assert rr.read(7, readers=fake.readers())["transitDamage"]["redactedFields"] == [f"findings[{idx}].body"]


# --- the path walk and the fail-closed edges ---

def test_paths_come_in_document_order_a_matching_key_before_its_value():
    # axis: the order and the shape of the paths (dict keys joined by '.', list indexes as [i])
    value = {"z": "[REDACTED]", "a": [{"x": "ok"}, {"k[REDACTED": {"inner": "[REDACTED FIELD]"}}], "m": "plain"}
    assert rr._redacted_paths(value) == ["z", "a[1].k[REDACTED", "a[1].k[REDACTED.inner"]


def test_edge_b_scrubbed_keys_report_their_path_once_even_when_the_value_is_redacted_too():
    # axis: a [REDACTED KEY] key (and its numbered twin) listed twice, or not at all
    value = {"a": {"[REDACTED KEY]": "[REDACTED]", "[REDACTED KEY]-1": "v"}}
    assert rr._redacted_paths(value) == ["a.[REDACTED KEY]", "a.[REDACTED KEY]-1"]


def test_edge_c_a_redacted_value_under_a_secret_shaped_key_is_listed(tmp_path):
    # axis: the [REDACTED] a secret-named structured field reads left unflagged
    assert rr._redacted_paths({"cost": {"api_token": "[REDACTED]"}}) == ["cost.api_token"]
    rec = rr._scrubbed(dict(build(account()), extra={"db_password": "hunter2"}))
    assert rr._redacted_paths(rec) == ["extra.db_password"]


def test_edge_d_and_e_scalars_and_empty_sections_give_no_path_and_the_record_itself():
    # axis: a non-string scalar or an empty section flagged, or a clean record copied
    clean = {"a": None, "b": 1, "c": 2.5, "d": True, "e": [], "f": {}, "g": [[], {}], "h": "ok"}
    assert rr._redacted_paths(clean) == []
    assert rr._flag_redactions(clean) is clean


def test_edge_a_a_transit_damage_that_is_not_a_dict_is_replaced_and_a_dict_is_merged():
    # axis: a transitDamage read from a comment as a string or list crashing the flagging, or losing its keys
    flagged = rr._flag_redactions({"transitDamage": "oops", "a": "[REDACTED]"})
    assert flagged["transitDamage"] == {"redactedFields": ["a"]}
    flagged = rr._flag_redactions({"transitDamage": {"hashMatches": False}, "a": "[REDACTED]"})
    assert flagged["transitDamage"] == {"hashMatches": False, "redactedFields": ["a"]}
    assert rr._transit_line("oops", 0) is None and rr._transit_line({"redactedFields": []}, 0) is None


def test_the_records_own_top_level_transit_damage_is_skipped_but_a_nested_one_is_not():
    # axis: the flag listing its own earlier list, or skipping a field that merely shares the name
    assert rr._redacted_paths({"transitDamage": {"redactedFields": ["[REDACTED]"]}, "x": {"transitDamage": "[REDACTED]"}}) \
        == ["x.transitDamage"]


def test_edge_f_the_flag_matches_the_record_a_large_panel_posts(tmp_path):
    # axis: the flag computed before shedding (here a 132-row panel whose first run's telemetry holds redacted text and is shed)
    rows = panel_rows(SEATS, 12)
    telemetry = {"note": "[REDACTED FIELD]", "padding": "x" * 70000}
    big_run = ({**GOOD_RUN, "observation": {**GOOD_RUN["observation"], "telemetry": telemetry}}, None)
    fake = Fake(runs={rows[0]["runDir"]: big_run})
    out = send(tmp_path, fake, findings=[finding(body="see " + SECRET)], reviewers=rows)
    assert out["parts"] == 0
    [comment] = fake.marked()
    rec = rr._parse_body(comment["body"], {c["id"]: c for c in fake.comments})
    assert "observation" in rec["reviewerShed"]
    assert not any("telemetry" in (v.get("observation") or {}) for v in rec["reviewers"])
    assert rec["transitDamage"]["redactedFields"] == rr._redacted_paths(rec) == ["findings[0].body"]


# --- the claim check and the transit line ---

def with_forbidden_redacted_path():
    """A built record whose first reviewer row's observation holds a redacted field under a key that is itself a
    forbidden phrase, so the transit line names that phrase in a path."""
    rec = build(account())
    rec["reviewers"][0]["observation"]["telemetry"] = {"bug-free": "[REDACTED FIELD]"}
    return rec


def test_a_forbidden_phrase_in_a_redacted_fields_path_is_accepted_in_the_transit_line():
    # axis: the transit line's literal record paths being checked for forbidden claims (the exemption removed)
    assert "bug-free" in rr.FORBIDDEN_CLAIMS
    body = rr.render(with_forbidden_redacted_path())
    path = "reviewers[0].observation.telemetry.bug-free"
    assert rr._parse_body(body)["transitDamage"] == {"redactedFields": [path]}
    assert f"Transit damage: redacted text in 1 recorded field, so that text is lost: {path}." in summary_of(body)


def test_a_forbidden_phrase_elsewhere_in_a_summary_with_a_transit_line_is_still_refused():
    # axis: the claim check skipped for the whole summary whenever a transit line exists (the exemption broadened)
    rec = with_forbidden_redacted_path()
    rec["whatIsMissing"] = ["this change is bug-free"]
    with pytest.raises(rr.Refusal) as refused:
        rr.render(rec)
    assert refused.value.reason == "review-record-forbidden-claim"
