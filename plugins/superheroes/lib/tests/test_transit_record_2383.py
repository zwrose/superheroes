"""#2383: no text the review record, the vet slot writer or the PR-body publisher writes to GitHub reaches a vet
changed and unflagged. Each write is read back and compared through `cloud_builder.transit_compare`; a review
record whose stored JSON differs from what its writer posted is flagged by `review_record.read`.

Bite-proof record: i2383_transit_record
"""
import json
import os
import re

import pytest

import cloud_builder
import pr_body_stage as PBS
import review_record as rr
import test_pr_body_stage as TPB
import test_vet_slot as TVS
import vet_slot as vs
from test_review_record import Fake, account, finding, put, send
from test_review_record_fit_c7l3 import CLOUD_FOOTER, many_findings, parts_of

CDATA = "keep <![CDATA[x]]> as written"


def drop_bangs(body):
    """The observed egress rewrite: a `!` directly before a `[` is deleted when a `]` appears later in the body."""
    return re.sub(r"!(?=\[)", lambda m: "" if "]" in body[m.end():] else m.group(0), body)


class StoreFake(Fake):
    """A fake whose created comments are stored as `store` rewrites them; `sent` keeps what was posted."""

    def __init__(self, store=lambda body: body, **kw):
        super().__init__(**kw)
        self.store, self.sent = store, {}

    def _create(self, pr, repo, body):
        out = super()._create(pr, repo, self.store(body))
        self.sent[out["id"]] = body
        return out


def cdata_findings(count=1, body_chars=0):
    """One finding holding CDATA; with `body_chars`, enough more findings to force a record into parts."""
    if not count > 1:
        return [finding(body=CDATA)]
    rows = many_findings(count, body_chars)
    rows[0] = dict(rows[0], body=CDATA)
    return rows


def parts_findings():
    return cdata_findings(40, 4000)


def read_record(fake):
    out = rr.read(7, readers=fake.readers())
    assert out["ok"], out
    return out


# --- 1: the round trip carries the stamp and no flag ---

def test_1_a_record_written_then_read_carries_sentsha256_and_no_transit_damage(tmp_path):
    # axis: the writer's stamp on the posted record object; a record read back flagged, or carrying no stamp
    fake = Fake()
    send(tmp_path, fake, findings=cdata_findings())
    rec = read_record(fake)
    assert re.fullmatch(r"[0-9a-f]{64}", rec["sentSha256"]) and "transitDamage" not in rec
    assert rec["sentSha256"] == rr._sent_sha(rr._parse_body(fake.marked()[0]["body"]))


def test_1b_a_parts_record_written_then_read_carries_sentsha256_and_no_transit_damage(tmp_path):
    # axis: the writer's stamp on the posted record object on the parts path
    fake = Fake()
    send(tmp_path, fake, findings=parts_findings())
    assert len(parts_of(fake)) >= 2
    rec = read_record(fake)
    assert re.fullmatch(r"[0-9a-f]{64}", rec["sentSha256"]) and "transitDamage" not in rec


def test_1c_a_record_holding_redacted_text_round_trips_with_only_its_redacted_field_flag(tmp_path):
    # axis: the writer's stamp covers the record after the redaction flag, so the flag is not read as damage
    secret = "pass" + "word = " + "x" * 8
    fake = Fake()
    send(tmp_path, fake, findings=[finding(body="see " + secret)])
    rec = read_record(fake)
    assert rec["transitDamage"] == {"redactedFields": ["findings[0].body"]}


# --- 2: a record changed in transit is flagged ---

def test_2_a_record_whose_stored_json_lost_a_bang_reads_flagged_and_is_listed_by_the_next_write(tmp_path):
    # axis: the reader's whole-record check; a record changed in transit read as clean
    fake = StoreFake(drop_bangs)
    send(tmp_path, fake, findings=cdata_findings())
    assert "<![CDATA[" in fake.sent[1] and "<[CDATA[" in fake.comments[0]["body"]
    assert read_record(fake)["transitDamage"]["sentHashMatches"] is False
    fake.store = lambda body: body
    send(tmp_path, fake, findings=cdata_findings())
    rec = read_record(fake)
    assert [(e["id"], e["why"]) for e in rec["earlierRecordsNotChecked"]] == [(1, "changed in transit")]
    assert "transitDamage" not in rec


def test_2b_a_parts_record_whose_parts_lost_a_bang_reads_flagged_beside_the_hash_keys(tmp_path):
    # axis: the reader's parts check; a parts record changed in transit flagged only by its length and hash
    fake = StoreFake(drop_bangs)
    send(tmp_path, fake, findings=parts_findings())
    assert any("<[CDATA[" in c["body"] for c in parts_of(fake))
    damage = read_record(fake)["transitDamage"]
    assert damage["sentHashMatches"] is False and damage["hashMatches"] is False
    assert {"recordedChars", "foundChars"} <= set(damage)


# --- 3: the cloud footer alone is not damage ---

@pytest.mark.parametrize("findings", [cdata_findings(), parts_findings()], ids=["one-comment", "parts"])
def test_3_a_record_stored_with_only_the_cloud_footer_appended_reads_unflagged(tmp_path, findings):
    # axis: the host footer read as damage by the stamp check
    fake = StoreFake(lambda body: body + CLOUD_FOOTER)
    send(tmp_path, fake, findings=findings)
    assert "transitDamage" not in read_record(fake)


# --- 4: a record without the key, and a key that is wrong ---

def stored_record(tmp_path):
    fake = Fake()
    send(tmp_path, fake, findings=cdata_findings())
    return json.loads(fake.marked()[0]["body"].split("```json\n")[1].split("\n```\n</details>")[0])


def body_of(obj):
    return f"{rr.MARKER}\nsummary\n\n<details><summary>Full record</summary>\n\n```json\n{json.dumps(obj)}\n```\n</details>"


def test_4_a_record_without_sentsha256_is_read_unflagged(tmp_path):
    # axis: the legacy pass-through; a record written before the key existed read as damaged
    obj = stored_record(tmp_path)
    del obj["sentSha256"]
    rec = rr._parse_body(body_of(obj))
    assert "sentSha256" not in rec and "transitDamage" not in rec


@pytest.mark.parametrize("stamp", [5, "0" * 64, None, ["x"]], ids=["number", "wrong-hash", "null", "list"])
def test_4b_a_sentsha256_that_is_not_the_records_hash_reads_flagged(tmp_path, stamp):
    # axis: a present stamp that is not a string equal to the record's hash is damage
    obj = dict(stored_record(tmp_path), sentSha256=stamp)
    assert rr._parse_body(body_of(obj))["transitDamage"] == {"sentHashMatches": False}


def test_4c_a_flag_is_merged_into_the_transit_damage_the_writer_already_put_there(tmp_path):
    # axis: the stamp check keeps the redacted-field list the writer recorded
    obj = dict(stored_record(tmp_path), transitDamage={"redactedFields": ["findings[0].body"]}, sentSha256="x")
    assert rr._parse_body(body_of(obj))["transitDamage"] == {"redactedFields": ["findings[0].body"],
                                                              "sentHashMatches": False}


# --- 5: _create_comment reads every comment back ---

@pytest.fixture
def patched(monkeypatch):
    seen = {}
    monkeypatch.setattr(rr, "_send", lambda method, path, body: {"id": 41, "url": "http://c/41"})

    def gh_json(*args):
        seen["args"] = args
        return seen["held"]
    monkeypatch.setattr(rr, "_gh_json", gh_json)
    return seen


def test_5_create_comment_matched_changed_and_not_checked(patched):
    # axis: the read-back of a created comment; compared with itself, or a failed read-back read as matched
    body = "see ![a](b) here"
    patched["held"] = {"body": body}
    got = rr._create_comment(7, "o/r", body)
    assert got == {"id": 41, "url": "http://c/41", "transit": {"transit": "matched"}}
    assert patched["args"] == ("api", "repos/o/r/issues/comments/41")
    patched["held"] = {"body": "see [a](b) here"}
    changed = rr._create_comment(7, "o/r", body)["transit"]
    assert changed["transit"] == "changed" and any("!" in c["sent"] for c in changed["changes"])
    for held in (None, {"message": "Not Found"}, ["not", "a", "comment"], {"body": None}):
        patched["held"] = held
        assert rr._create_comment(7, "o/r", body)["transit"]["transit"] == "not-checked"


def test_5b_a_second_footer_on_the_read_back_is_changed(patched):
    # axis: exactly one trailing footer is tolerated
    body = "a record body"
    patched["held"] = {"body": body + CLOUD_FOOTER}
    assert rr._create_comment(7, "o/r", body)["transit"] == {"transit": "matched"}
    patched["held"] = {"body": body + CLOUD_FOOTER + CLOUD_FOOTER}
    assert rr._create_comment(7, "o/r", body)["transit"]["transit"] == "changed"


def test_5c_a_comment_that_could_not_be_created_is_none_and_nothing_is_read_back(monkeypatch):
    # axis: a failed create stays None, with no read-back
    monkeypatch.setattr(rr, "_send", lambda method, path, body: None)
    monkeypatch.setattr(rr, "_gh_json", lambda *a: pytest.fail("read back a comment that was never created"))
    assert rr._create_comment(7, "o/r", "x") is None


# --- 6: write aggregates every comment's read-back ---

CHANGED = {"transit": "changed", "changeCount": 1, "changes": [{"line": 1, "at": 4, "sent": "!", "found": ""}]}
MATCHED = {"transit": "matched"}


def write_with(tmp_path, fake, transit_of, **over):
    """A write whose create_comment returns what `transit_of(kind, n)` says (None: no `transit` key at all)."""
    readers = fake.readers()
    calls = []

    def create(pr, repo, body):
        out = Fake._create(fake, pr, repo, body)
        kind = "raw" if body.startswith(rr.RAW_MARKER) else "part" if body.startswith(rr.PART_MARKER) else "head"
        calls.append(kind)
        transit = transit_of(kind, len(calls))
        return out if transit is None else dict(out, transit=transit)
    readers["create_comment"] = create
    return rr.write(put(tmp_path, account(**over)), str(tmp_path), readers)


def raw_file(tmp_path):
    raw = tmp_path / "raw.txt"
    raw.write_text("a reviewer's raw output\n")
    return str(raw)


def test_6_write_reports_a_changed_head_and_names_it(tmp_path):
    # axis: write's aggregation; a changed comment reported as matched
    out = write_with(tmp_path, Fake(), lambda kind, n: CHANGED if kind == "head" else MATCHED,
                     rawFindingsFiles=[raw_file(tmp_path)])
    assert out["ok"] and out["transit"] == "changed"
    assert [(c["what"], c["transit"]["transit"]) for c in out["transitChecks"]] == [
        ("raw output raw.txt", "matched"), ("record", "changed")]
    head = out["transitChecks"][-1]
    assert out["transitLine"] == f"record (comment {head['comment']}): " + cloud_builder.transit_line(CHANGED)
    assert "Transit damage:" in out["transitLine"] and "raw output" not in out["transitLine"]


def test_6b_write_with_no_transit_on_the_create_result_is_not_checked(tmp_path):
    # axis: a create result with no read-back is not-checked, never matched
    out = write_with(tmp_path, Fake(), lambda kind, n: None)
    assert out["ok"] and out["transit"] == "not-checked"
    assert out["transitChecks"][0]["transit"] == {"transit": "not-checked", "why": "no read-back was made"}
    assert out["transitLine"].startswith("record (comment ") and "Transit check: not checked" in out["transitLine"]


def test_6c_write_where_every_comment_matched_is_matched_with_no_line(tmp_path):
    # axis: a clean write carries no transitLine
    out = write_with(tmp_path, Fake(), lambda kind, n: MATCHED, rawFindingsFiles=[raw_file(tmp_path)])
    assert out["transit"] == "matched" and "transitLine" not in out and len(out["transitChecks"]) == 2


def test_6d_a_changed_comment_outranks_a_not_checked_one_and_parts_are_numbered(tmp_path):
    # axis: changed wins over not-checked; each record part is named by its number
    out = write_with(tmp_path, Fake(), lambda kind, n: CHANGED if (kind, n) == ("part", 2) else
                     (None if (kind, n) == ("part", 1) else MATCHED), findings=parts_findings())
    assert out["transit"] == "changed"
    assert [c["what"] for c in out["transitChecks"]][:2] == ["record part 1", "record part 2"]
    assert out["transitChecks"][-1]["what"] == "record"
    assert out["transitLine"].count("record part") == 2


def test_6e_a_real_write_through_the_read_back_reports_matched_when_the_store_is_faithful(tmp_path, monkeypatch):
    # axis: write wired to _create_comment end to end; a faithful store is matched, a rewriting store is changed
    for store, expected in ((lambda body: body + CLOUD_FOOTER, "matched"), (drop_bangs, "changed")):
        fake = StoreFake(store)
        readers = fake.readers()
        monkeypatch.setattr(rr, "_send", lambda method, path, body, fake=fake: fake._create(7, "o/r", body))
        monkeypatch.setattr(rr, "_gh_json", lambda *a, fake=fake: {"body": fake.comments[int(a[1].rsplit("/", 1)[1]) - 1]["body"]})
        readers["create_comment"] = rr._create_comment
        out = rr.write(put(tmp_path, account(findings=[finding(body="see ![a](b) here")])), str(tmp_path), readers)
        assert out["ok"] and out["transit"] == expected, out


# --- 7: the extra-audit reservation passes its transit through ---

def test_7_reserve_extra_audit_passes_the_create_results_transit_through():
    # axis: the reservation's transit; dropped, or a missing one read as matched
    seen = {"transit": "changed", "changeCount": 1, "changes": []}
    out = rr.reserve_extra_audit(7, "o/r", "s1", "why", {"create_comment": lambda pr, repo, body: {
        "id": 9, "url": "http://c/9", "transit": seen}})
    assert out == {"ok": True, "url": "http://c/9", "id": 9, "transit": seen}
    bare = rr.reserve_extra_audit(7, "o/r", "s1", "why", {"create_comment": lambda pr, repo, body: {
        "id": 9, "url": "http://c/9"}})
    assert bare["transit"] == {"transit": "not-checked", "why": "no read-back was made"}
    assert rr.reserve_extra_audit(7, "o/r", "s1", "why", {"create_comment": lambda *a: None})["ok"] is False


# --- 8: vet_slot compares its read-back through the one comparison ---

BANG_SLOT = "**Verdict: NOT-READY** · abc\n\nNew owner half ![a](u) here.\n"


@pytest.fixture(autouse=True)
def _gh_on_path(monkeypatch):
    monkeypatch.setattr(vs.shutil, "which", lambda name: "/usr/bin/gh" if name == "gh" else None)


def slot_at(tmp_path, text=TVS.SLOT):
    path = tmp_path / "slot.md"
    path.write_text(text, encoding="utf-8")
    return str(path)


def write_slot(tmp_path, readback_of, text=TVS.SLOT, **fake_kw):
    fake = TVS.FakeGh([TVS.BODY], TVS._pages([TVS._comment(TVS.RECEIPT)]), **fake_kw)
    original = fake.__call__

    def run(argv, **kwargs):
        out = original(argv, **kwargs)
        if argv[:3] == ["gh", "pr", "edit"]:
            readback_of(fake)
        return out
    return TVS._write(run, slot_at(tmp_path, text)), fake


def test_8a_a_readback_with_one_cloud_footer_is_confirmed(tmp_path):
    # axis: the vet slot's comparison tolerates the one footer the cloud egress appends
    result, fake = write_slot(tmp_path, lambda f: setattr(f, "bodies", [f.edited[-1] + CLOUD_FOOTER]))
    assert result["ok"] is True and len(fake.edit_calls()) == 1


def test_8b_a_readback_that_lost_a_bang_is_unconfirmed_and_names_the_change(tmp_path):
    # axis: the vet slot's comparison; a changed read-back confirmed
    result, fake = write_slot(tmp_path, lambda f: setattr(f, "bodies", [f.edited[-1].replace("![", "[")]),
                              text=BANG_SLOT)
    assert "![a](u)" in fake.edited[-1]
    assert result["reason"] == "write-unconfirmed"
    assert result["detail"].startswith("slot write already pushed; readback differs from the pushed body: ")
    assert "Transit damage:" in result["detail"]


def test_8b2_two_footers_on_the_readback_are_unconfirmed(tmp_path):
    # axis: exactly one footer is tolerated by the vet slot's comparison
    result, _ = write_slot(tmp_path, lambda f: setattr(f, "bodies", [f.edited[-1] + CLOUD_FOOTER + CLOUD_FOOTER]))
    assert result["reason"] == "write-unconfirmed" and "Transit damage:" in result["detail"]


def test_8c_a_readback_that_fails_keeps_its_existing_unconfirmed_detail(tmp_path):
    # axis: a failed read-back never reaches the comparison and stays write-unconfirmed
    result, _ = write_slot(tmp_path, lambda f: setattr(f, "view_rc", 1))
    assert result["reason"] == "write-unconfirmed"
    assert "slot write already pushed; readback: PR body: exit 1 boom" in result["detail"]


# --- 9: pr_body_stage compares its read-backs through the one comparison ---

FIXED_BANG = TPB.FIXED.replace("Adds the retry budget", "Adds the retry budget ![chart](c.png)")


def publish_with(tmp_path, after, fixed=TPB.FIXED):
    sd = TPB._staged_fixed(tmp_path, fixed=fixed)
    return sd, PBS.publish(sd, 7, runner=TPB.FakeGh(views=[TPB.BODY, after]))


def test_9_a_readback_that_lost_a_bang_is_refused_with_the_change_in_the_receipt_and_the_line(tmp_path):
    # axis: the publish read-back comparison; a changed read-back published, or the change not named
    sd, out = publish_with(tmp_path, FIXED_BANG.replace("![", "["), fixed=FIXED_BANG)
    assert (out["ok"], out["reason"]) == (False, "pr-body-publish-unverified")
    assert out["transit"]["transit"] == "changed" and "!" in out["transit"]["changes"][0]["sent"]
    line = PBS.record_line(sd)
    assert line == "The review did not copy its PR-body fix onto the PR: " + cloud_builder.transit_line(out["transit"])
    assert "Transit damage:" in line and "\\u0021" in line


def test_9b_a_readback_that_fails_is_not_checked_and_the_line_says_so(tmp_path):
    # axis: a read-back that cannot be made is not-checked, and the line says it was not checked
    sd = TPB._staged_fixed(tmp_path)
    views = iter([TPB._Done(0, json.dumps({"body": TPB.BODY})), TPB._Done(1)])

    def runner(argv):
        return next(views) if argv[2:4] != ["-X", "PATCH"] else TPB._Done(0)
    out = PBS.publish(sd, 7, runner=runner)
    assert (out["ok"], out["reason"]) == (False, "pr-body-publish-unverified")
    assert out["transit"]["transit"] == "not-checked"
    assert "not checked" in PBS.record_line(sd)


def test_9c_a_readback_with_one_footer_is_published(tmp_path):
    # axis: the one cloud footer is not a difference to the publish read-back
    _, out = publish_with(tmp_path, TPB.FIXED + CLOUD_FOOTER)
    assert (out["ok"], out["outcome"]) == (True, "published") and "transit" not in out


def test_9d_a_readback_that_lost_the_leading_indent_is_refused(tmp_path):
    # axis: only trailing whitespace is tolerated; a lost leading indent was hidden by strip_cloud_footer
    sd, out = publish_with(tmp_path, TPB.FIXED, fixed="    " + TPB.FIXED)
    assert (out["ok"], out["reason"]) == (False, "pr-body-publish-unverified")
    assert out["transit"]["transit"] == "changed"
    assert "Transit damage:" in PBS.record_line(sd)


def test_9e_a_receipt_with_no_transit_keeps_the_old_phrase(tmp_path):
    # axis: an older unverified receipt, with no transit key, reads as it did
    sd = TPB._staged_fixed(tmp_path)
    receipt = {"schema": PBS.PUBLISH_SCHEMA, "pr": 7, "ok": False, "outcome": "refused",
               "reason": "pr-body-publish-unverified"}
    TPB._write(PBS.paths(sd)["published"], json.dumps(receipt))
    assert PBS.record_line(sd) == ("The review did not copy its PR-body fix onto the PR: "
                                   "the body read back from GitHub after the edit did not match.")


def test_9f_a_matching_retry_is_recognized_through_the_same_comparison(tmp_path):
    # axis: a retried publish recognizes its own earlier success, footer and trailing whitespace included
    sd = TPB._staged_fixed(tmp_path)
    first = PBS.publish(sd, 7, runner=TPB.FakeGh(views=[TPB.BODY, TPB.FIXED]))
    again = PBS.publish(sd, 7, runner=TPB.FakeGh(views=[TPB.FIXED + CLOUD_FOOTER]))
    assert again["reason"] == PBS.REASON_ALREADY_PUBLISHED and again["at"] == first["at"]
