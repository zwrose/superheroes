"""#1957: a cloud session's GitHub egress wraps each bare http(s):// run in backticks; the record's JSON writes every
"/" as "\\/" so it cannot be changed, and an unreadable record names where its JSON is damaged."""
import json
import re
from pathlib import Path

import review_record as rr
from test_review_record import Fake, account, put
from test_review_record_fit_c7l3 import CLOUD_FOOTER, many_findings, parts_of, two_part_record

FIXTURES = Path(__file__).parent / "fixtures" / "review_record_transit"
URL_RUN = re.compile(r"https?://\S*")


def egress(body):
    """The observed rewrite: each bare URL run wrapped in one backtick on each side, then the host footer."""
    return URL_RUN.sub(lambda m: f"`{m.group(0)}`", body) + CLOUD_FOOTER


class EgressFake(Fake):
    """A fake whose created comments are stored as the cloud egress rewrites them; `sent` keeps what was written."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.sent = {}

    def _create(self, pr, repo, body):
        out = super()._create(pr, repo, egress(body))
        self.sent[out["id"]] = body
        return out


def block_of(body):
    return body[body.rindex("```json\n") + 8:body.rindex("\n```\n</details>")]


def url_findings():
    return [{"id": "code-001", "title": "t", "severity": "Minor", "file": "a.py", "line": 3,
             "body": "see https://x/y for the call", "consequence": "c", "outcome": "fixed",
             "reason": "fixed in 1a2b3c4", "reviewer": "code-reviewer"}]


def write_with_urls(tmp_path, fake, **over):
    raw = tmp_path / "raw.txt"
    raw.write_text("a reviewer's raw output\n")
    out = rr.write(put(tmp_path, account(findings=url_findings(), rawFindingsFiles=[str(raw)], **over)),
                   str(tmp_path), fake.readers())
    assert out["ok"], out


def unescaped_text():
    return json.dumps({"url": "https://github.com/o/r/pull/7", "run": "https://github.com/o/r/actions/runs/1",
                       "n": 1}, sort_keys=True, separators=(",", ":"))


def test_record_json_writes_every_slash_escaped(tmp_path):
    # axis: the writer's JSON text; a bare "/" (so a "://") left in it for a host to wrap in transit
    rec = rr.build_record(account(findings=url_findings()), Fake().readers())
    rec["previousRecord"] = {"id": 5, "url": "https://github.com/o/r/pull/7#issuecomment-5"}
    rec["rawOutputs"] = [{"file": "raw.txt", "id": 6, "url": "https://github.com/o/r/pull/7#issuecomment-6",
                          "withheld": False}]
    odd = ["a backslash then slash: \\/ and a lone \\ and /", "", "plain"]
    rec["checked"] = odd
    text = block_of(rr.render_plan(rec).head([]))
    assert "://" not in text and not re.search(r"(?<!\\)/", text)
    assert json.loads(text) == json.loads(json.dumps(rr._scrubbed(rec), sort_keys=True, separators=(",", ":")))
    assert json.loads(text)["checked"] == odd
    assert json.loads(text)["findings"][0]["body"] == "see https://x/y for the call"


def test_one_comment_record_survives_the_url_wrapping_egress(tmp_path):
    # axis: a record in one comment, urls in its links and findings, wrapped by the egress and read back changed
    plain = unescaped_text()
    assert egress(plain) != plain + CLOUD_FOOTER
    fake = EgressFake()
    write_with_urls(tmp_path, fake, sessionId="A")
    write_with_urls(tmp_path, fake, sessionId="B")
    records = fake.marked()
    assert len(records) == 2 and not parts_of(fake)
    assert all(c["body"] == fake.sent[c["id"]] + CLOUD_FOOTER for c in fake.comments)
    out = rr.read(7, readers=fake.readers())
    assert out["ok"] and "transitDamage" not in out
    assert out["previousRecord"]["url"] == records[0]["url"] and out["rawOutputs"][0]["url"] == fake.raws()[-1]["url"]
    assert out["findings"][0]["body"] == "see https://x/y for the call"


def test_parts_record_survives_the_url_wrapping_egress(tmp_path):
    # axis: a record split into parts, urls in its text, wrapped by the egress and read back changed or refused
    plain = unescaped_text()
    assert egress(plain) != plain + CLOUD_FOOTER
    fake = EgressFake()
    found = many_findings(40, 4000)
    found[0]["body"] = "see https://x/y for the call"
    assert rr.write(put(tmp_path, account(findings=found, sessionId="A")), str(tmp_path), fake.readers())["ok"]
    assert len(parts_of(fake)) >= 2
    assert rr.write(put(tmp_path, account(findings=found, sessionId="B")), str(tmp_path), fake.readers())["ok"]
    assert all(c["body"] == fake.sent[c["id"]] + CLOUD_FOOTER for c in fake.comments)
    out = rr.read(7, readers=fake.readers())
    assert out["ok"] and "transitDamage" not in out
    assert [f["body"] for f in out["findings"]] == [f["body"] for f in found]
    assert out["previousRecord"]["url"].startswith("http://c/")


def test_records_readable_today_read_the_same(tmp_path):
    # axis: a record rendered with the old unescaped JSON, or one with stray backticks inside strings, read differently
    fake = Fake()
    write_with_urls(tmp_path, fake, sessionId="A")
    write_with_urls(tmp_path, fake, sessionId="B")
    new = fake.marked()[-1]
    plain = json.dumps(json.loads(block_of(new["body"])), sort_keys=True, separators=(",", ":"))
    old = dict(new, body=new["body"].replace(block_of(new["body"]), plain))
    assert "://" in block_of(old["body"]) and block_of(old["body"]) != block_of(new["body"])
    before = rr.read(7, readers=fake.readers())
    fake.comments[fake.comments.index(new)] = old
    assert rr.read(7, readers=fake.readers()) == before
    fixture = (FIXTURES / "pr1943-record-6244597236.md").read_text()
    damaged = Fake()
    damaged.comments.append({"id": 6244597236, "author": "bot", "body": fixture, "url": "https://x/c"})
    out = rr.read(1943, readers=damaged.readers())
    assert out["ok"] and out["rawOutputs"][0]["url"].startswith("`https://github.com/")
    assert out["reviewers"][0]["findingsCoverage"] == "reported` by the session"


def test_pr1942_record_refusal_names_the_damaged_span(tmp_path):
    # axis: the refusal detail; an unreadable record that names no character offset, comment or excerpt
    body = (FIXTURES / "pr1942-record-6244257429.md").read_text()
    fake = Fake()
    fake.comments.append({"id": 6244257429, "author": "bot", "body": body, "url": "https://x/c"})
    out = rr.read(1942, readers=fake.readers())
    assert (out["ok"], out["reason"]) == (False, "review-record-unreadable") and set(out) == {"ok", "reason", "detail"}
    expected = body.index("}``") + 1
    lead = f"https://x/c: the record's JSON does not parse at character {expected} of comment 6244257429: "
    assert out["detail"].startswith(lead)
    excerpt = json.loads(out["detail"][len(lead):])
    assert excerpt == body[expected - 40:expected + 40] and "``" in excerpt


def test_parts_record_refusal_names_the_part_and_offset(tmp_path):
    # axis: the refusal detail for a parts record; the damage reported against the head or the wrong part
    fake = two_part_record(tmp_path)
    parts = parts_of(fake)
    body = parts[1]["body"]
    at = body.index("\n", len(rr.PART_MARKER) + 1) + 1 + 5
    parts[1]["body"] = body[:at] + "`" + body[at:]
    out = rr.read(7, readers=fake.readers())
    assert out["reason"] == "review-record-unreadable"
    assert out["detail"].startswith(fake.marked()[0]["url"])
    assert f"does not parse at character {at} of comment {parts[1]['id']}: " in out["detail"]


def test_other_unreadable_causes_name_no_offset(tmp_path):
    # axis: an unreadable cause that is not a parse failure; reported with an invented offset
    fake = two_part_record(tmp_path)
    head = fake.marked()[0]
    good = head["body"]
    start, end = good.rindex("```json\n") + 8, good.rindex("\n```\n</details>")
    head["body"] = good[:start - 8] + "no block here"
    out = rr.read(7, readers=fake.readers())
    assert out["detail"] == f"{head['url']}: the comment has no JSON block"
    head["body"] = good[:start] + json.dumps({"schema": rr.PARTS_SCHEMA, "parts": "x"}) + good[end:]
    out = rr.read(7, readers=fake.readers())
    assert out["detail"] == f"{head['url']}: the parts index is malformed"
    head["body"] = good
    gone = parts_of(fake)[0]
    fake.comments.remove(gone)
    out = rr.read(7, readers=fake.readers())
    assert out["detail"] == f"{head['url']}: part comment {gone['id']} is missing or malformed"
