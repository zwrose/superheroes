"""The review record writer: a record fits by construction (head plus part comments), a lane reason reads
cleanly, and the writer re-checks every cited decision when it writes."""
import json

import pytest
import signal

import canon
import finding_outcomes as FO
import review_findings_schema as rfs
import review_record as rr
import session_contract
from test_review_record import (CANON_ID, CANON_SOURCES, HEAD, Fake, account, build, finding, put, reviewer, send)

KEY = session_contract.FINDING_KEY_FIELD
SEATS = [f"seat-{i:02d}-reviewer" for i in range(11)]
SEC = {"reviewer": "security-reviewer", "kind": "standing-ruling", "canonId": CANON_ID}


def panel_rows(seats, rounds, gap=0):
    """Reviewer rows named `<seat> (round <n>)`: a mix of engine-record, session-reported and did-not-run."""
    rows = []
    for n in range(1, rounds + 1):
        for i, seat in enumerate(seats):
            name = f"{seat} (round {n})"
            kind = (i + n) % 3
            if kind == 0:
                rows.append(reviewer(name, ran=False, runDir=None))
            elif kind == 1:
                rows.append(reviewer(name))
            else:
                rows.append(reviewer(name, runDir=None, commit=HEAD))
    rows += [reviewer(f"seamscheck {seats[n % len(seats)]} (round {n})") for n in range(1, gap + 1)]
    return rows


def many_findings(count, body_chars):
    text = "The handler reads the saved value before the write lands, so a retry can see stale data. "
    return [finding(f"f-{i:03d}", title=f"Finding number {i}", reviewer=SEATS[i % len(SEATS)],
                    body=(text * (body_chars // len(text) + 1))[:body_chars],
                    consequence="A retried request can return data from before the change.",
                    reason=f"fixed in {i:07x}") for i in range(count)]


def pretty_size(fake, **over):
    return len(json.dumps(build(account(**over), fake), indent=2, sort_keys=True))


def parts_of(fake):
    return [c for c in fake.comments if c["body"].startswith(rr.PART_MARKER)]


def keys(rec):
    return [(f[KEY], f["id"]) for f in rec["findings"]], [v["name"] for v in rec["reviewers"]]


# --- record fit ---

def test_the_marker_of_a_part_is_not_the_marker_of_a_record():
    # axis: a part comment never starts with the record marker, so no list of record comments can pick one up
    assert not rr.PART_MARKER.startswith(rr.MARKER) and not rr.MARKER.startswith(rr.PART_MARKER)


def test_116_reviewer_rows_and_78_findings_post_in_comments_under_the_limit_and_read_back_whole(tmp_path):
    # axis: record fit; a long session refused, a comment over the limit, or a record that reads back different
    fake = Fake()
    rows, found = panel_rows(SEATS, 10, gap=6), many_findings(78, 900)
    assert len(rows) == 116
    send(tmp_path, fake, reviewers=rows, findings=found)
    assert all(len(c["body"]) <= rr.MAX_BODY_CHARS for c in fake.comments)
    rec = rr.read(7, readers=fake.readers())
    assert rec["ok"] and keys(rec) == keys(build(account(reviewers=rows, findings=found), fake))
    assert len(rec["findings"]) == 78 and len(rec["reviewers"]) == 116


def test_a_record_of_200k_characters_pretty_printed_posts_whole_in_parts(tmp_path):
    # axis: record fit; a record too big for one comment refused or cut, instead of posted whole in parts
    fake = Fake()
    rows, found = panel_rows(SEATS, 10, gap=6), many_findings(78, 2600)
    assert pretty_size(fake, reviewers=rows, findings=found) >= 198000
    out = send(tmp_path, fake, reviewers=rows, findings=found)
    assert out["parts"] > 1 and len(parts_of(fake)) == out["parts"]
    assert all(len(c["body"]) <= rr.MAX_BODY_CHARS for c in fake.comments)
    assert [c["id"] for c in fake.comments][-1] == fake.marked()[0]["id"]  # the head goes last
    rec = rr.read(7, readers=fake.readers())
    assert keys(rec) == keys(build(account(reviewers=rows, findings=found), fake))
    assert [f["body"] for f in rec["findings"]] == [f["body"] for f in found]


def test_a_record_of_227k_characters_with_98_reviewer_rows_and_79_findings_posts_whole_in_parts(tmp_path):
    # axis: record fit at the largest real session; a record that size refused, cut, or read back different
    fake = Fake()
    rows, found = panel_rows(SEATS, 8, gap=10), many_findings(79, 3000)
    assert len(rows) == 98 and len(found) == 79
    size = pretty_size(fake, reviewers=rows, findings=found)
    assert size >= 227000, size
    out = send(tmp_path, fake, reviewers=rows, findings=found)
    assert out["parts"] > 1 and len(parts_of(fake)) == out["parts"]
    assert all(len(c["body"]) <= rr.MAX_BODY_CHARS for c in fake.comments)
    assert [c["id"] for c in fake.comments][-1] == fake.marked()[0]["id"]  # the head goes last
    rec = rr.read(7, readers=fake.readers())
    assert rec["ok"] and keys(rec) == keys(build(account(reviewers=rows, findings=found), fake))
    assert len(rec["findings"]) == 79 and len(rec["reviewers"]) == 98
    assert [f["body"] for f in rec["findings"]] == [f["body"] for f in found]


def test_66_rows_in_6_seats_over_11_rounds_fit_one_comment(tmp_path):
    # axis: compaction; per-seat bullets and compact JSON failing to keep a mid-size session in one comment
    fake = Fake()
    rows = panel_rows(SEATS[:6], 11)
    assert len(rows) == 66
    out = send(tmp_path, fake, reviewers=rows, findings=many_findings(10, 300))
    assert out["parts"] == 0 and len(fake.marked()) == 1 and not parts_of(fake)
    body = fake.marked()[0]["body"]
    lines = body.split("\n")
    cut = lines.index("Findings:") if "Findings:" in lines else len(lines)
    assert len(body) <= rr.MAX_BODY_CHARS and sum(l.startswith("- ") for l in lines[:cut]) == 6
    assert sum(l.startswith("- ") for l in lines[cut:]) == 10


def test_the_next_write_reads_the_multi_part_prior_record(tmp_path):
    # axis: the prior-record read in write; a parts record read as unreadable or as empty, so a dropped finding goes unseen
    fake = Fake()
    found = many_findings(40, 4000)
    send(tmp_path, fake, findings=found)
    assert parts_of(fake)
    first_head = fake.marked()[0]
    dropped = rr.write(put(tmp_path, account(findings=found[1:])), str(tmp_path), fake.readers())
    assert (dropped["ok"], dropped["reason"]) == (False, "review-record-unaccounted") and "f-000" in dropped["detail"]
    send(tmp_path, fake, findings=found)
    assert rr.read(7, readers=fake.readers())["previousRecord"]["id"] == first_head["id"]


def test_backticks_and_fences_in_a_finding_survive_the_parts(tmp_path):
    # axis: part framing; a fence or json block inside a finding ending a part block early or confusing the reader
    fake = Fake()
    body = "```json\n{\"a\": 1}\n```\n" + "`" * 30 + "\n" + ("y" * 70000) + "```\n</details>"
    send(tmp_path, fake, findings=[finding("f-1", body=body)])
    assert parts_of(fake)
    assert rr.read(7, readers=fake.readers())["findings"][0]["body"] == body


def test_a_body_whose_fence_overhead_exceeds_the_reserve_still_splits(tmp_path):
    # axis: part sizing; a long backtick run growing the fence past the piece so the split never advances
    fake = Fake()
    body = "`" * 40000 + "x" * 70000
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(AssertionError("the split did not terminate")))
    signal.alarm(60)  # bounded: a split that never advances fails instead of hanging
    try:
        send(tmp_path, fake, findings=[finding("f-1", body=body)])
    finally:
        signal.alarm(0)
    assert parts_of(fake) and all(len(c["body"]) <= rr.MAX_BODY_CHARS for c in fake.comments)
    assert rr.read(7, readers=fake.readers())["findings"][0]["body"] == body


def test_78_findings_with_900_character_ids_post_with_a_compact_head(tmp_path):
    # axis: the head bound; a summary that names every finding left for the owner overflowing its own comment
    fake = Fake()
    ids = [f"{i:03d}" + "x" * 897 for i in range(78)]
    found = [finding(i, title=f"t{n}", outcome="left-for-owner", reason="waits") for n, i in enumerate(ids)]
    out = send(tmp_path, fake, findings=found)
    head = fake.marked()[0]["body"]
    assert out["parts"] >= 1 and len(head) <= rr.MAX_BODY_CHARS
    assert "Waiting for the owner: 78 findings left for the owner (listed in the full record) wait for the owner's decision." in head
    assert ids[0] not in head
    assert [f["id"] for f in rr.read(7, readers=fake.readers())["findings"]] == ids


def test_a_head_that_cannot_fit_even_compact_is_refused_before_any_post(tmp_path):
    # axis: the defensive refusal; a head over the limit posted, or parts posted for a head that cannot follow
    fake = Fake()
    out = rr.write(put(tmp_path, account(makers=[{"family": "f" * 40000}, {"family": "g" * 40000}])),
                   str(tmp_path), fake.readers())
    assert (out["ok"], out["reason"]) == (False, "review-record-too-large") and "head comment" in out["detail"]
    assert fake.comments == []


# --- fail-closed edges of reading parts ---

def two_part_record(tmp_path):
    fake = Fake()
    send(tmp_path, fake, findings=many_findings(40, 4000))
    assert len(parts_of(fake)) >= 2
    return fake


def test_edge1_a_deleted_part_makes_the_record_unreadable_and_the_next_write_supersedes_it(tmp_path):
    # axis: a missing part; a record read from the parts that are left, or a later write blocked by it
    fake = two_part_record(tmp_path)
    fake.comments.remove(parts_of(fake)[0])
    assert rr.read(7, readers=fake.readers())["reason"] == "review-record-unreadable"
    assert rr.write(put(tmp_path, account(findings=many_findings(40, 4000))), str(tmp_path), fake.readers())["ok"]
    rec = rr.read(7, readers=fake.readers())
    assert rec["ok"] and [e["why"] for e in rec["earlierRecordsNotChecked"]] == ["unreadable"] and len(rec["findings"]) == 40


def test_edge2_a_part_changed_in_transit_is_read_and_reported(tmp_path):
    # axis: the parts hash; text changed inside a part that still parses, read silently as clean, or refused outright
    fake = two_part_record(tmp_path)
    part = parts_of(fake)[0]
    assert "reads the saved" in part["body"]
    part["body"] = part["body"].replace("reads the saved", "reads the SAVED", 1)
    out = rr.read(7, readers=fake.readers())
    assert out["ok"] and out["transitDamage"]["hashMatches"] is False
    assert out["transitDamage"]["recordedChars"] == out["transitDamage"]["foundChars"]


def test_a_record_written_after_a_damaged_one_lists_it_for_the_vet(tmp_path):
    # axis: a damaged but readable predecessor (a finding could have been lost in transit) hidden by the next write
    fake = two_part_record(tmp_path)
    part = parts_of(fake)[0]
    part["body"] = part["body"].replace("reads the saved", "reads the SAVED", 1)
    damaged = fake.marked()[0]
    assert rr.write(put(tmp_path, account(findings=many_findings(40, 4000))), str(tmp_path), fake.readers())["ok"]
    rec = rr.read(7, readers=fake.readers())
    assert rec["earlierRecordsNotChecked"] == [{"id": damaged["id"], "url": damaged["url"], "why": "changed in transit"}]
    assert "transitDamage" not in rec


@pytest.mark.parametrize("ids", [[{}], [[]], ["1"], [True]])
def test_part_ids_that_are_not_comment_ids_are_unreadable_and_superseded(tmp_path, ids):
    # axis: a part id that cannot be looked up raising instead of reading unreadable, so every later write fails
    fake = two_part_record(tmp_path)
    _set_index(fake.marked()[0], parts=ids)
    assert rr.read(7, readers=fake.readers())["reason"] == "review-record-unreadable"
    assert rr.write(put(tmp_path, account(findings=many_findings(40, 4000))), str(tmp_path), fake.readers())["ok"]


def test_an_undamaged_parts_record_reports_no_transit_damage(tmp_path):
    # axis: a clean record flagged as changed in transit
    fake = two_part_record(tmp_path)
    assert "transitDamage" not in rr.read(7, readers=fake.readers())


def test_backticks_added_in_transit_are_read_and_reported_with_both_lengths(tmp_path):
    # axis: the #1888 shape: stray backticks added inside a part's JSON strings plus the footer, refused outright
    fake = two_part_record(tmp_path)
    part = parts_of(fake)[0]
    part["body"] = part["body"].replace("reads the saved", "reads`` the saved", 1) + CLOUD_FOOTER
    out = rr.read(7, readers=fake.readers())
    assert out["ok"] and out["transitDamage"]["foundChars"] == out["transitDamage"]["recordedChars"] + 2


def test_edge2_a_part_that_is_cut_short_fails_the_length_check(tmp_path):
    # axis: the parts length; a part with text missing read as the record
    fake = two_part_record(tmp_path)
    part = parts_of(fake)[-1]
    fence = part["body"].rindex("\n```")
    part["body"] = part["body"][:fence - 5] + part["body"][fence:]
    assert rr.read(7, readers=fake.readers())["reason"] == "review-record-unreadable"


def _set_index(head, **over):
    good = head["body"]
    start, end = good.rindex("```json\n") + 8, good.rindex("\n```\n</details>")
    index = dict(json.loads(good[start:end]), **over)
    head["body"] = good[:start] + json.dumps(index) + good[end:]


@pytest.mark.parametrize("over", [{"sha256": ""}, {"sha256": "not-a-hash"}, {"sha256": "A" * 64}, {"chars": -1},
                                  {"chars": True}, {"chars": 1.5}])
def test_edge3_an_index_with_a_malformed_hash_or_length_is_unreadable_with_good_parts(tmp_path, over):
    # axis: the forgiving read admitting a malformed index as transit damage when the parts themselves are fine
    fake = two_part_record(tmp_path)
    _set_index(fake.marked()[0], **over)
    assert rr.read(7, readers=fake.readers())["reason"] == "review-record-unreadable"


def test_a_length_that_differs_while_the_hash_matches_reports_the_hash_as_matching(tmp_path):
    # axis: transitDamage reporting a hash mismatch when only the recorded length differs
    fake = two_part_record(tmp_path)
    head = fake.marked()[0]
    good = json.loads(head["body"][head["body"].rindex("```json\n") + 8:head["body"].rindex("\n```\n</details>")])
    _set_index(head, chars=good["chars"] + 3)
    out = rr.read(7, readers=fake.readers())
    assert out["ok"] and out["transitDamage"] == {"recordedChars": good["chars"] + 3, "foundChars": good["chars"],
                                                  "hashMatches": True}


def test_edge3_a_parts_head_with_a_malformed_index_is_unreadable(tmp_path):
    # axis: the parts index; an index that is not valid JSON, or lacks its fields, read as a record
    fake = two_part_record(tmp_path)
    head = fake.marked()[0]
    good = head["body"]
    start = good.rindex("```json\n") + 8
    end = good.rindex("\n```\n</details>")
    for bad in ("{not json", json.dumps({"schema": rr.PARTS_SCHEMA}), json.dumps({"schema": rr.PARTS_SCHEMA, "parts": [],
                "sha256": "0", "chars": 0}), json.dumps({"schema": rr.PARTS_SCHEMA, "parts": "x", "sha256": 1, "chars": "y"}),
                json.dumps({"schema": "review-record-parts/9"})):
        head["body"] = good[:start] + bad + good[end:]
        out = rr.read(7, readers=fake.readers())
        assert (out["ok"], out["reason"]) == (False, "review-record-unreadable"), bad


def test_edge3_a_part_that_does_not_start_with_the_part_marker_is_unreadable(tmp_path):
    # axis: the part marker; any comment the head names read as a part
    fake = two_part_record(tmp_path)
    part = parts_of(fake)[0]
    part["body"] = "x" + part["body"]
    assert rr.read(7, readers=fake.readers())["reason"] == "review-record-unreadable"


def test_edge4_a_part_comment_is_never_the_latest_record(tmp_path):
    # axis: the part marker is not a record marker; a part comment newer than the head becoming the latest record
    fake = two_part_record(tmp_path)
    head = fake.marked()[0]
    fake.comments.append({"id": 10 ** 6, "author": "bot", "body": parts_of(fake)[0]["body"], "url": "http://c/part"})
    out = rr.read(7, readers=fake.readers())
    assert out["ok"] and out["url"] == head["url"] and out["earlierRecords"] == []
    assert rr.write(put(tmp_path, account(findings=many_findings(40, 4000))), str(tmp_path), fake.readers())["ok"]


CLOUD_FOOTER = "\n\n---\n_Generated by [Claude Code](https://claude.ai/code)_"


@pytest.mark.parametrize("footer", [CLOUD_FOOTER, CLOUD_FOOTER + "\n"])
def test_parts_and_head_with_a_host_appended_footer_read_back_whole_and_the_next_write_runs(tmp_path, footer):
    # axis: a cloud session's attribution footer after each part's closing fence making the record unreadable
    fake = two_part_record(tmp_path)
    for c in parts_of(fake) + fake.marked():
        c["body"] += footer
    found = many_findings(40, 4000)
    rec = rr.read(7, readers=fake.readers())
    assert rec["ok"] and [f["body"] for f in rec["findings"]] == [f["body"] for f in found]
    assert rr.write(put(tmp_path, account(findings=found)), str(tmp_path), fake.readers())["ok"]


@pytest.mark.parametrize("trailer", ["\nextra", "\n\n---\nsee ```json", "\n\nnot a footer", "\n\n---\nextra",
                                     CLOUD_FOOTER + "\nEXTRA", "\n\n---\n_Generated by x_\n```json\n{}\n```"])
def test_a_part_with_other_text_after_its_fence_stays_unreadable(tmp_path, trailer):
    # axis: the footer allowance; any trailing text other than a plain footer read as a well-formed part
    fake = two_part_record(tmp_path)
    parts_of(fake)[0]["body"] += trailer
    assert rr.read(7, readers=fake.readers())["reason"] == "review-record-unreadable"


def test_a_footer_does_not_hide_a_changed_part(tmp_path):
    # axis: the hash still checks a footed part; text changed inside it read as clean
    fake = two_part_record(tmp_path)
    part = parts_of(fake)[0]
    part["body"] = part["body"].replace("reads the saved", "reads the SAVED", 1) + CLOUD_FOOTER
    assert rr.read(7, readers=fake.readers())["transitDamage"]["hashMatches"] is False


def test_edge5_a_failing_create_while_posting_parts_posts_no_head(tmp_path):
    # axis: part posting; a head posted after a part failed, naming parts that do not exist
    fake = Fake()
    real = fake._create
    calls = []

    def flaky(pr, repo, body):
        calls.append(body)
        return None if len(calls) == 2 else real(pr, repo, body)
    readers = dict(fake.readers(), create_comment=flaky)
    out = rr.write(put(tmp_path, account(findings=many_findings(40, 4000))), str(tmp_path), readers)
    assert (out["ok"], out["reason"]) == (False, "review-record-gh-failed") and "part 2" in out["detail"]
    assert fake.marked() == [] and len(parts_of(fake)) == 1
    assert rr.read(7, readers=fake.readers())["reason"] == "review-record-missing"


# --- the summary ---

def test_one_bullet_per_seat_and_a_row_without_a_round_keeps_its_own(tmp_path):
    # axis: summary grouping; a bullet per row, or a row with no round suffix folded into a seat
    names = ["code-reviewer (round 1)", "code-reviewer (round 2)", "code-reviewer (round 3)", "code-reviewer (round 4)",
             "code-reviewer (round 5)", "design-reviewer (round 1)", "auditor"]
    rows = [reviewer(n) for n in names]
    rows[2] = reviewer(names[2], runDir=None, commit=HEAD)
    rows[4] = reviewer(names[4], ran=False, runDir=None)
    rec = build(account(reviewers=rows), Fake())
    rec["reviewers"][1].update(notIndependent=True, ownerWord={"words": "ok", "where": "PR comment"})
    lines = [l for l in rr.render(rec).split("\n") if l.startswith("- ")]
    assert lines == [
        "- code-reviewer: ran in rounds 1, 2, 4 (engine record); ran in round 3 (reported by the session); "
        "did not run in round 5; not independent of the makers in round 2 (owner's word: PR comment); "
        "findings: reported by the session",
        "- design-reviewer: ran in round 1 (engine record); findings: reported by the session",
        "- auditor: ran (engine record); findings: reported by the session"]
    assert len(rec["reviewers"]) == 7


def test_a_seat_whose_rounds_report_different_coverage_lists_each_round():
    # axis: summary grouping; differing per-round coverage collapsed into one
    rec = build(account(reviewers=[reviewer("a (round 1)"), reviewer("a (round 2)")]), Fake())
    rec["reviewers"][1]["findingsCoverage"] = "all of them"
    line = [l for l in rr.render(rec).split("\n") if l.startswith("- a:")][0]
    assert line.endswith("findings: round 1: reported by the session; round 2: all of them")


def test_the_reviewers_line_falls_back_to_a_count_when_the_seats_alone_overflow():
    # axis: the last fallback of the head; per-seat bullets that cannot fit the comment posted anyway
    rec = build(account(reviewers=[reviewer(f"{n}{'s' * 300} (round 1)") for n in range(300)]), Fake())
    plan = rr.render_plan(rec)
    head = plan.head([1] * len(plan.parts))
    assert len(head) <= rr.MAX_BODY_CHARS
    assert "Reviewers: 300 rows across 300 seats (listed in the full record)." in head


# --- the lane reason ---

@pytest.mark.parametrize("call, reason", [
    ("**Lane call:** full, inherited from #1814: why", "inherited from #1814: why"),
    ("**Lane call:** full — because it touches money", "because it touches money"),
    ("**Lane call:** full;  : - small", "small"),
    ("**Lane call:** full,", None),
    ("**Lane call:** full — ", None),
    ("**Lane call:** full :;,-–—", None),
])
def test_a_lane_reason_has_no_leading_punctuation(call, reason):
    # axis: the lane reason; punctuation joining the lane word to its reason shown as the reason
    pr = {"head": HEAD, "body": call, "issues": []}
    rec = build(account(laneReason=None), Fake(meta=pr))
    assert rec["lane"]["reason"] == reason
    line = [l for l in rr.render(rec).split("\n") if l.startswith("Lane: ")][0]
    assert ("because" in line) == (reason is not None) and ("because " + reason if reason else "") in line


def test_a_marker_lane_takes_the_cleaned_reason_from_the_issue_call():
    # axis: the lane reason through the build-lane marker branch; the stripped reason read only on the other branch
    marker = {"schema": "build-lane/1", "lane": "full", "branch": "b", "currentBranch": "b", "issue": 9}
    fake = Fake(marker=marker, meta={"head": HEAD, "body": "", "issues": [9]},
                issue_bodies={9: "**Lane call:** full, inherited from #1814: why"})
    lane = build(account(), fake)["lane"]
    assert (lane["source"], lane["reason"], lane["reasonSource"]) == ("build lane marker", "inherited from #1814: why",
                                                                      "issue lane call")
    fake = Fake(marker=marker, meta={"head": HEAD, "body": "", "issues": [9]}, issue_bodies={9: "**Lane call:** full,"})
    assert build(account(laneReason="the session's reason"), fake)["lane"]["reason"] == "the session's reason"


# --- the record-writer half ---

def test_each_finding_carries_the_sheet_part_its_outcome_lands_in():
    # axis: sheetPart; a part restated here, or missing on an undecided finding
    found = [finding(f"o-{n}", title=f"t{n}", outcome=o, reason="r") for n, o in enumerate(rfs.OUTCOMES)]
    found.append(finding("o-none", title="undecided", outcome=None))
    rec = build(account(findings=found), Fake(sources={}))
    assert [f["sheetPart"] for f in rec["findings"][:5]] == [rfs.OUTCOME_SHEET_PART[o] for o in rfs.OUTCOMES]
    assert rec["findings"][5]["sheetPart"] is None and rec["findings"][5]["outcome"] is None
    assert rec["status"] == "not-reviewed"


def canon_with_supersession():
    other = "2026-01-03-abcd1234-2"
    newer = canon.entry_line(other, "2026-01-03", "standing", "a newer ruling",
                             canon.SEP.join(["supersedes: " + CANON_ID, 'owner\'s words: "go"']), "issue thread")
    return {"canonText": CANON_SOURCES["canonText"] + "\n" + newer}


def ruling(fid, ref, **over):
    f = finding(fid, title=fid, outcome="ruling", reason="decided earlier", decidedBy={"kind": "canon", "ref": ref})
    return {**f, **over}


def test_a_ruling_whose_canon_entry_is_on_record_stays_a_ruling():
    # axis: the write-time re-check; a ruling that is on record changed, or noted as changed
    rec = build(account(findings=[ruling("r-1", CANON_ID)]), Fake(sources=CANON_SOURCES))
    f = rec["findings"][0]
    assert (f["outcome"], f["reason"]) == ("ruling", "decided earlier") and rec["decisionRechecks"] == []
    assert rec["status"] == "reviewed" and rec["leftForOwner"] == []


def test_a_ruling_citing_an_entry_that_is_not_on_record_goes_to_the_owner():
    # axis: the write-time re-check; a ruling kept when the Canon entry it cites is absent
    rec = build(account(findings=[ruling("r-1", "2026-09-09-ffffffff-9")]), Fake(sources=CANON_SOURCES))
    f = rec["findings"][0]
    assert f["outcome"] == "left-for-owner" and f["sheetPart"] == rfs.OUTCOME_SHEET_PART["left-for-owner"]
    assert f["reason"] == "the cited decision is not on record (the cited Canon entry is not on record); decided earlier"
    assert rec["decisionRechecks"] == [{"finding": "r-1", "from": "ruling", "to": "left-for-owner",
                                        "why": "the cited decision is not on record (the cited Canon entry is not on record)"}]
    assert rec["leftForOwner"] == ["r-1"] and "finding r-1 waits for the owner's decision" in rec["whatIsMissing"]


def test_a_ruling_citing_a_superseded_entry_goes_to_the_owner():
    # axis: the write-time re-check follows Canon's own supersession rule
    rec = build(account(findings=[ruling("r-1", CANON_ID)]), Fake(sources=canon_with_supersession()))
    assert rec["findings"][0]["outcome"] == "left-for-owner" and len(rec["decisionRechecks"]) == 1


def test_a_ruling_citing_an_id_two_different_canon_entries_share_goes_to_the_owner():
    # axis: the write-time re-check follows canon_decides' distinct-entry count; a ruling kept
    # when two different complete entries share the id it cites
    first = canon.entry_line(CANON_ID, "2026-01-02", "standing", "a ruling", 'owner\'s words: "go"', "issue thread")
    second = canon.entry_line(CANON_ID, "2026-01-02", "standing", "a ruling", 'owner\'s words: "no, stop"', "issue thread")
    assert first != second
    sources = {"canonText": canon.HEADER + first + "\n" + second + "\n"}
    rec = build(account(findings=[ruling("r-1", CANON_ID)]), Fake(sources=sources))
    f = rec["findings"][0]
    assert f["outcome"] == "left-for-owner"
    assert f["reason"] == "the cited decision is not on record (the cited Canon entry is not on record); decided earlier"
    assert rec["decisionRechecks"] == [{"finding": "r-1", "from": "ruling", "to": "left-for-owner",
                                        "why": "the cited decision is not on record (the cited Canon entry is not on record)"}]
    assert rec["leftForOwner"] == ["r-1"]


@pytest.mark.parametrize("sources", [{}, {"canonText": 5}], ids=["canon-unreadable", "canon-malformed"])
def test_edge6_unreadable_canon_leaves_a_cited_ruling_for_the_owner(sources):
    # axis: an unreadable source; a ruling kept because Canon could not be read
    rec = build(account(findings=[ruling("r-1", CANON_ID)]), Fake(sources=sources))
    assert rec["findings"][0]["outcome"] == "left-for-owner"


def test_edge6_a_decision_source_reader_that_raises_leaves_the_ruling_for_the_owner():
    # axis: a failing source reader; the build raising, or a ruling kept
    readers = dict(Fake().readers(), decision_sources=lambda *a: 1 / 0)
    rec = rr.build_record(account(findings=[ruling("r-1", CANON_ID)]), readers)
    assert rec["findings"][0]["outcome"] == "left-for-owner"


def test_the_real_source_reader_reads_nothing_for_a_missing_repository_and_never_raises(tmp_path):
    # axis: the source reader; the ambient project's Canon read for an account that names none
    assert FO.decision_sources(None, None) == {}
    assert FO.decision_sources("", None, {"answers": {}}, 7) == {"sheetAnswers": {"answers": {}}, "pr": 7}
    assert "canonText" not in FO.decision_sources(str(tmp_path), None)


SHEET = {"answers": {"c1": {"answer": "aligned", "optionId": None, "note": ""}}, "cards": {"c1": {"options": []}}}
SHEET_BY = {"kind": "sheet-answer", "ref": {"pr": 7, "card": "c1"}}


def test_a_finding_left_for_the_owner_whose_sheet_answer_is_settled_becomes_a_ruling():
    # axis: the write-time re-check upward; an answered card leaving its finding waiting
    left = finding("l-1", title="l1", outcome="left-for-owner", reason="open", decidedBy=SHEET_BY)
    rec = build(account(findings=[left], sheetAnswers=SHEET), Fake())
    f = rec["findings"][0]
    assert (f["outcome"], f["sheetPart"]) == ("ruling", rfs.OUTCOME_SHEET_PART["ruling"])
    assert f["reason"] == "sheet-answer pr 7 card c1; open"
    assert rec["decisionRechecks"] == [{"finding": "l-1", "from": "left-for-owner", "to": "ruling",
                                        "why": "sheet-answer pr 7 card c1"}]
    assert rec["leftForOwner"] == [] and rec["status"] == "reviewed"


def test_edge8_without_sheet_answers_a_sheet_answer_decision_is_not_on_record():
    # axis: absent sheet answers; a sheet-answer citation accepted with nothing to check it against
    cited = finding("r-1", title="r1", outcome="ruling", reason="answered", decidedBy=SHEET_BY)
    assert build(account(findings=[cited]), Fake())["findings"][0]["outcome"] == "left-for-owner"
    assert build(account(findings=[cited], sheetAnswers=SHEET), Fake())["findings"][0]["outcome"] == "ruling"
    # bites on: a saved aligned answer accepted after the published card gained options
    gained = dict(SHEET, cards={"c1": {"options": ["allow-late-returns"]}})
    assert build(account(findings=[cited], sheetAnswers=gained), Fake())["findings"][0]["outcome"] == "left-for-owner"
    unsettled = {"answers": {"c1": {"answer": None}}}
    assert build(account(findings=[cited], sheetAnswers=unsettled), Fake())["findings"][0]["outcome"] == "left-for-owner"


def test_a_ruling_with_no_cited_decision_and_every_other_outcome_are_unchanged():
    # axis: the re-check's reach; a hand-written ruling or another outcome changed
    found = [finding("a", title="a", outcome="ruling", reason="the owner said so in the issue"),
             finding("b", title="b", outcome="fixed"), finding("c", title="c", outcome="craft", reason="tidy"),
             finding("d", title="d", outcome="left-for-owner", reason="open"),
             finding("e", title="e", outcome="shown-wrong", reason="not a bug", decidedBy={"kind": "canon", "ref": CANON_ID})]
    rec = build(account(findings=found), Fake(sources=CANON_SOURCES))
    assert [f["outcome"] for f in rec["findings"]] == ["ruling", "fixed", "craft", "left-for-owner", "shown-wrong"]
    assert rec["decisionRechecks"] == [] and rec["findings"][0]["reason"] == "the owner said so in the issue"


def test_a_recheck_keeps_a_missing_reason_missing():
    # axis: the re-check never supplies a reason, so a finding with none still counts against the record
    rec = build(account(findings=[ruling("r-1", "nope", reason=None)]), Fake(sources=CANON_SOURCES))
    assert rec["findings"][0]["outcome"] == "left-for-owner" and not rec["findings"][0]["reason"]


@pytest.mark.parametrize("over, key", [
    ({"findings": [finding(decidedBy="canon:x")]}, "findings[0].decidedBy"),
    ({"findings": [finding(decidedBy=["canon"])]}, "findings[0].decidedBy"),
    ({"sheetAnswers": []}, "sheetAnswers"), ({"baseRef": ""}, "baseRef"), ({"baseRef": 5}, "baseRef"),
    ({"refused": {}}, "refused"), ({"refused": [{"title": "t"}]}, "refused[0] (needs title and reason)"),
    ({"rounds": {"count": 1, "cap": 3, "stoppedAtCap": False, "capKind": "weeks"}}, "rounds"),
], ids=["decidedBy-str", "decidedBy-list", "sheetAnswers", "baseRef-empty", "baseRef-int", "refused-dict",
        "refused-no-reason", "capKind"])
def test_edge7_malformed_new_account_keys_are_refused_naming_the_key(tmp_path, over, key):
    # axis: account validation of the new keys; a malformed one accepted
    out = rr.write(put(tmp_path, account(**over)), str(tmp_path), Fake().readers())
    assert (out["ok"], out["reason"], out["detail"]) == (False, "review-account-invalid", key)


def test_the_new_account_keys_are_accepted_when_well_formed(tmp_path):
    # axis: account validation of the new keys; a well-formed value refused
    sent = send(tmp_path, Fake(), findings=[finding(decidedBy=None)], sheetAnswers=None, baseRef="abc123", refused=[])
    assert sent["ok"]


# --- the go-ahead's Canon id ---

def test_a_standing_ruling_go_ahead_counts_only_when_its_canon_entry_is_on_record():
    # axis: the go-ahead's Canon check; a go-ahead naming an entry that is not on record lifting the park
    sec = reviewer("security-reviewer", ran=False, runDir=None)
    off = build(account(reviewers=[sec], goAheads=[SEC]), Fake(sources={}))
    assert (off["status"], off["parked"]) == ("not-reviewed", True)
    assert off["missingReviews"] == [{"name": "security-reviewer", "goAhead": None}]
    assert "the go-ahead for security-reviewer is incomplete (its Canon entry is not on record)" in off["whatIsMissing"]
    on = build(account(reviewers=[sec], goAheads=[SEC]), Fake(sources=CANON_SOURCES))
    assert (on["status"], on["parked"]) == ("not-reviewed", False)
    assert on["missingReviews"] == [{"name": "security-reviewer", "goAhead": SEC}]
    assert f"security-reviewer did not run; go-ahead: standing ruling {CANON_ID}" in on["whatIsMissing"]
    words = {"reviewer": "security-reviewer", "kind": "owner-words", "words": "skip it", "where": "PR comment"}
    assert build(account(reviewers=[sec], goAheads=[words]), Fake(sources={}))["parked"] is False


def test_a_go_ahead_that_is_incomplete_for_another_reason_does_not_blame_canon():
    # axis: the incomplete note; the Canon remark added to a go-ahead that never named an entry
    sec = reviewer("security-reviewer", ran=False, runDir=None)
    rec = build(account(reviewers=[sec], goAheads=[{"reviewer": "security-reviewer", "kind": "standing-ruling"}]), Fake())
    assert "the go-ahead for security-reviewer is incomplete" in rec["whatIsMissing"]


# --- the cap line and the findings not taken ---

@pytest.mark.parametrize("rounds, line", [
    ({"count": 3, "cap": 3, "stoppedAtCap": True}, "Rounds: 3 of 3 (round cap). The loop stopped at its cap."),
    ({"count": 2, "cap": 5, "stoppedAtCap": False, "capKind": "rounds"}, "Rounds: 2 of 5 (round cap)."),
    ({"count": 8, "cap": 8, "stoppedAtCap": True, "capKind": "ceiling"},
     "Rounds: 8 of 8 (round ceiling). The loop stopped at its cap."),
    ({"count": 4, "cap": None, "stoppedAtCap": False}, "Rounds: 4."),
])
def test_the_summary_says_how_many_rounds_ran_against_which_cap(rounds, line):
    # axis: the cap line; the cap kind or the stop left unsaid
    rec = build(account(rounds=rounds), Fake())
    lines = rr.render(rec).split("\n")
    ci = next(i for i, l in enumerate(lines) if l.startswith("CI on the final commit"))
    assert lines[ci + 1] == line
    assert rec["rounds"]["capKind"] == rounds.get("capKind", "rounds")


def test_findings_not_taken_into_the_review_are_listed_by_reason_and_never_counted(tmp_path):
    # axis: refused findings; a refused finding counted as a finding, or left off the summary
    refused = [{"title": "a", "reason": "no file named", "round": 1, "file": "x.py", "line": 2},
               {"title": "b", "reason": "no file named"}, {"title": "c", "reason": "not a finding"}]
    fake = Fake()
    send(tmp_path, fake, findings=[finding()], refused=refused)
    rec = rr.read(7, readers=fake.readers())
    assert rec["refused"] == refused and len(rec["findings"]) == 1
    body = fake.marked()[0]["body"]
    assert "Not taken into the review: 3 findings — no file named: 2; not a finding: 1." in body
    assert "Not taken into the review" not in rr.render(build(account(), Fake()))
    one = rr.render(build(account(refused=refused[2:]), Fake()))
    assert "Not taken into the review: 1 finding — not a finding: 1." in one
