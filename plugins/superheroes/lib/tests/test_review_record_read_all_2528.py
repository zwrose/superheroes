"""#2528: `review_record.py read-all --pr <n>` answers with every record comment of the PR accounted for, oldest first:
each one that parses is in `records`, each one that does not (for any reason) is named in `unreadable`."""
import json

import pytest

import review_learning
import review_record as rr
from test_review_record import Fake, account, put, send

NESTED = "[" * 100000 + "]" * 100000
HAND_EDITED = rr.MARKER + "\nhand edited"


def nested_body():
    """A record-marker comment whose JSON block holds an array nested deeply enough that `json.loads` raises RecursionError."""
    return rr.MARKER + "\n<details><summary>x</summary>\n\n```json\n" + NESTED + "\n```\n</details>"


def add(fake, body):
    """Append a comment by hand, the way the fake's own create does; returns it."""
    c = {"id": len(fake.comments) + 1, "author": "a", "body": body, "url": f"http://c/{len(fake.comments) + 1}"}
    fake.comments.append(c)
    return c


def three(tmp_path):
    fake = Fake()
    for sid in ("s1", "s2", "s3"):
        send(tmp_path, fake, sessionId=sid)
    return fake


def around(tmp_path, middle):
    """A readable record, a hand-added record-marker comment with `middle` as its body, a readable record, in that
    comment-id order. The writer reads the earlier records on every write, so the bad comment is added after both
    writes and takes the second id."""
    fake = Fake()
    send(tmp_path, fake, sessionId="s1")
    send(tmp_path, fake, sessionId="s3")
    bad = add(fake, middle)
    last = fake.comments[1]
    last["id"], last["url"] = 3, "http://c/3"
    bad["id"], bad["url"] = 2, "http://c/2"
    fake.comments.sort(key=lambda c: c["id"])
    return fake, bad


def test_read_all_returns_every_record_oldest_first(tmp_path):
    # axis: every record comment of the PR is in records, oldest first by comment id whatever order the listing came in
    fake = three(tmp_path)
    ids = [c["id"] for c in fake.marked()]
    fake.comments.reverse()
    assert [c["id"] for c in fake.comments] == sorted(ids, reverse=True)
    out = rr.read_all(7, readers=fake.readers())
    assert out["ok"] is True and out["pr"] == 7
    assert [r["url"] for r in out["records"]] == [f"http://c/{i}" for i in sorted(ids)]
    assert [r["sessionId"] for r in out["records"]] == ["s1", "s2", "s3"]
    assert out["unreadable"] == []


def test_an_unparseable_record_is_named_never_dropped(tmp_path):
    # axis: a record comment that parses to None is named in unreadable, never dropped, and the readable ones around it stay
    fake, bad = around(tmp_path, HAND_EDITED)
    first, _, last = [c for c in fake.comments if c["body"].startswith(rr.MARKER)]
    out = rr.read_all(7, readers=fake.readers())
    assert out["ok"] is True
    assert len(out["records"]) == 2
    assert [r["url"] for r in out["records"]] == [first["url"], last["url"]]
    assert len(out["unreadable"]) == 1
    entry = out["unreadable"][0]
    assert entry == {"id": bad["id"], "url": bad["url"], "detail": entry["detail"]}
    assert entry["detail"].startswith(bad["url"]) and entry["detail"] == f"{bad['url']}: the comment has no JSON block"


def test_a_record_that_raises_while_parsing_costs_no_other_record(tmp_path):
    # axis: a record comment whose parse raises (RecursionError from a deeply nested JSON body) is named, and the other records are kept
    fake, bad = around(tmp_path, nested_body())
    with pytest.raises(RecursionError):
        rr._parse_body(bad["body"], {})
    out = rr.read_all(7, readers=fake.readers())
    assert out["ok"] is True
    assert [r["sessionId"] for r in out["records"]] == ["s1", "s3"]
    assert [(u["id"], u["url"]) for u in out["unreadable"]] == [(bad["id"], bad["url"])]
    assert out["unreadable"][0]["detail"].startswith(bad["url"])


def test_a_parse_and_a_detail_that_both_raise_fall_back_to_the_named_detail(tmp_path, monkeypatch):
    # axis: a parse that raises and a detail builder that raises still name the comment, with the fallback detail, and keep the rest
    fake, bad = around(tmp_path, HAND_EDITED)
    real = rr._parse_body

    def parse(body, by_id=None):
        if body == bad["body"]:
            raise RecursionError("deep")
        return real(body, by_id)

    def detail(latest, by_id):
        raise ValueError("no detail")
    monkeypatch.setattr(rr, "_parse_body", parse)
    monkeypatch.setattr(rr, "_unreadable_detail", detail)
    out = rr.read_all(7, readers=fake.readers())
    assert out["ok"] is True and [r["sessionId"] for r in out["records"]] == ["s1", "s3"]
    assert out["unreadable"] == [{"id": bad["id"], "url": bad["url"],
                                  "detail": f"{bad['url']}: the record could not be read (RecursionError)"}]


def test_a_detail_that_raises_for_an_unparsed_record_falls_back_to_the_named_detail(tmp_path, monkeypatch):
    # axis: a detail builder that raises for a record that parsed to None still names the comment, with the fallback detail
    fake, bad = around(tmp_path, HAND_EDITED)

    def detail(latest, by_id):
        raise ValueError("no detail")
    monkeypatch.setattr(rr, "_unreadable_detail", detail)
    out = rr.read_all(7, readers=fake.readers())
    assert len(out["records"]) == 2
    assert out["unreadable"] == [{"id": bad["id"], "url": bad["url"],
                                  "detail": f"{bad['url']}: the record could not be read (ValueError)"}]


def test_a_comment_with_no_url_falls_back_to_the_stand_in(tmp_path, monkeypatch):
    # axis: a record comment with no url is still named, its fallback detail using the stand-in text
    fake, bad = around(tmp_path, HAND_EDITED)
    del bad["url"]

    def detail(latest, by_id):
        raise ValueError("no detail")
    monkeypatch.setattr(rr, "_unreadable_detail", detail)
    out = rr.read_all(7, readers=fake.readers())
    assert out["unreadable"] == [{"id": bad["id"], "url": None,
                                  "detail": "the existing record: the record could not be read (ValueError)"}]


def test_read_all_with_no_record_is_missing(tmp_path):
    # axis: a PR with no record comment refuses review-record-missing, as read does
    fake = Fake()
    add(fake, "just a comment")
    out = rr.read_all(7, readers=fake.readers())
    assert out["ok"] is False and out["reason"] == "review-record-missing"
    assert out["detail"] == "no review record on PR 7" == rr.read(7, readers=fake.readers())["detail"]


def test_a_part_comment_is_never_a_record(tmp_path):
    # axis: a part comment is not a record comment, so it is neither in records nor in unreadable
    fake = Fake()
    add(fake, rr.PART_MARKER + "\nsome part")
    assert rr.read_all(7, readers=fake.readers())["reason"] == "review-record-missing"
    send(tmp_path, fake, sessionId="s1")
    out = rr.read_all(7, readers=fake.readers())
    assert len(out["records"]) == 1 and out["unreadable"] == []


def test_read_all_with_unlistable_comments_refuses(tmp_path):
    # axis: comments that cannot be listed refuse review-record-gh-failed, never an empty answer
    out = rr.read_all(7, readers={"list_comments": lambda pr, repo: None})
    assert out["ok"] is False and out["reason"] == "review-record-gh-failed"


def test_read_still_answers_the_latest_record_only(tmp_path):
    # axis: read is unchanged: the latest record with the earlier urls, no records or unreadable key, a refusal on an unreadable latest
    fake = three(tmp_path)
    urls = [c["url"] for c in fake.marked()]
    out = rr.read(7, readers=fake.readers())
    assert out["ok"] is True and out["url"] == urls[2] and out["earlierRecords"] == urls[:2]
    assert "records" not in out and "unreadable" not in out
    broken, _ = around(tmp_path, HAND_EDITED)
    add(broken, HAND_EDITED)
    refused = rr.read(7, readers=broken.readers())
    assert refused["ok"] is False and refused["reason"] == "review-record-unreadable"


def test_a_transit_damaged_record_is_read_with_its_damage(tmp_path):
    # axis: a record whose sentSha256 no longer matches but still parses is in records with transitDamage, never in unreadable
    fake = three(tmp_path)
    mid = fake.marked()[1]
    stamp = json.loads(mid["body"][mid["body"].rindex("```json\n") + 8:mid["body"].rindex("\n```\n</details>")])["sentSha256"]
    assert mid["body"].count(stamp) == 1
    mid["body"] = mid["body"].replace(stamp, "0" * len(stamp))
    out = rr.read_all(7, readers=fake.readers())
    assert out["unreadable"] == [] and len(out["records"]) == 3
    assert "transitDamage" in out["records"][1] and out["records"][1]["transitDamage"]["sentHashMatches"] is False
    assert "transitDamage" not in out["records"][0] and "transitDamage" not in out["records"][2]


def test_the_hand_off_to_the_tally_fails_safe(tmp_path):
    # axis: the gardening pass feeds records plus every unreadable entry, so a PR with an unreadable record reads incomplete, never a short list
    fake = Fake()
    send(tmp_path, fake, sessionId="s1")
    add(fake, HAND_EDITED)
    answer = rr.read_all(7, readers=fake.readers())
    assert len(answer["records"]) == 1 and len(answer["unreadable"]) == 1
    since = answer["records"][0]["writtenAt"][:10]
    fed = review_learning.tally(answer["records"] + answer["unreadable"], [], since=since)
    assert fed["measured"] is False and fed["reason"] == "incomplete-evidence" and fed["leftOut"]["undated"] == 1
    short = review_learning.tally(answer["records"], [], since=since)
    assert short["reason"] != "incomplete-evidence"


def test_cli_read_all_prints_json_and_exits(tmp_path, monkeypatch, capsys):
    # axis: the read-all verb prints the answer as JSON and exits 0 on records, 1 on a refusal
    fake = three(tmp_path)
    by_pr = {7: list(fake.comments), 8: []}
    monkeypatch.setattr(rr, "_list_comments", lambda pr, repo: by_pr.get(pr))
    assert rr.main(["read-all", "--pr", "7"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True and len(out["records"]) == 3 and out["unreadable"] == []
    assert rr.main(["read-all", "--pr", "8"]) == 1
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is False and out["reason"] == "review-record-missing"
