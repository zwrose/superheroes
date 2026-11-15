"""#2490: GitHub rewrites a control character in a comment (a JSON control escape, or a raw control byte) into caret
notation, which leaves a review record invalid JSON while `write` still reported ok. A record string now carries a
visible stand-in for each such code, and a write that does not read back refuses.

The GitHub-like store below applies the measured rewrite to every body it stores. Control and escape values are built
from pieces at runtime; no raw control byte is typed into this file.

Bite-proof record: wo_2490_controls
"""
import json
import re

import pytest

import cloud_builder
import review_record as rr
from test_review_record import Fake, account, finding, put
from test_review_record_fit_c7l3 import many_findings, parts_of
from test_transit_record_2383 import cdata_findings, drop_bangs

ESC, BEL, NUL, C1_CSI = chr(0x1B), chr(0x07), chr(0x00), chr(0x9B)
BACKSLASH = chr(0x5C)
PICTURE_BEL, PICTURE_NUL, PICTURE_ESC = chr(0x2407), chr(0x2400), chr(0x241B)

# the codes the store rewrites when they appear as a JSON escape (u00XX after backslashes) or as a raw character
ESCAPED_CODES = frozenset([*range(0x00, 0x09), 0x0C, *range(0x0E, 0x20), *range(0x80, 0xA0)])
RAW_CODES = frozenset([*range(0x00, 0x08), *range(0x0E, 0x20), *range(0x80, 0xA0)])
ESCAPE_RUN = re.compile(r"(\\+)u00([0-9a-fA-F]{2})")


def caret(code):
    return "^" + chr((code & 0x1F) + 0x40)


def github_rule(text):
    """The measured storage rule: a control escape keeps its backslashes and becomes caret notation; a raw control
    character becomes caret notation with no backslash."""
    def escaped(m):
        code = int(m.group(2), 16)
        return m.group(1) + caret(code) if code in ESCAPED_CODES else m.group(0)
    text = ESCAPE_RUN.sub(escaped, text)
    return "".join(caret(ord(ch)) if ord(ch) in RAW_CODES else ch for ch in text)


class GitHubLike(Fake):
    """A fake whose created comments are stored as GitHub stores them, listed from the stored bodies, with the
    `transit` a real create returns. The options switch on one further kind of damage or failure."""

    def __init__(self, *, corrupt_json=False, crlf=False, part_tail="", damage_marker=False, drop_head=False,
                 list_fails_after_head=False, break_findings=False, no_transit=False, rewrite=None, **kw):
        super().__init__(**kw)
        self.corrupt_json, self.crlf, self.part_tail = corrupt_json, crlf, part_tail
        self.damage_marker, self.drop_head, self.list_fails = damage_marker, drop_head, list_fails_after_head
        self.break_findings, self.no_transit, self.rewrite = break_findings, no_transit, rewrite
        self.sent, self.hidden, self.listed, self.head_made, self.parts_made = {}, set(), 0, False, 0

    def readers(self):
        return dict(super().readers(), list_comments=self._list)

    def _list(self, pr, repo):
        self.listed += 1
        if self.list_fails and self.head_made:
            return None
        return [c for c in self.comments if c["id"] not in self.hidden]

    def _stored(self, body):
        stored = github_rule(body)
        if self.rewrite:
            stored = self.rewrite(stored)
        if body.startswith(rr.MARKER):
            if self.corrupt_json:
                # the caret rule applied to an escape the stand-in now removes: a backslash and a caret in a string
                stored = stored.replace('"sessionId":"', '"sessionId":"' + BACKSLASH + "^[", 1)
                assert BACKSLASH + "^[" in stored
            if self.break_findings:
                start, end = stored.index("```json\n") + 8, stored.rindex("\n```\n</details>")
                obj = json.loads(stored[start:end])
                obj["findings"] = "oops"
                stored = stored[:start] + json.dumps(obj, sort_keys=True, separators=(",", ":")) + stored[end:]
            if self.damage_marker:
                stored = " " + stored
        if body.startswith(rr.PART_MARKER):
            # the text goes after the closing fence of the second part, which is short: difflib over a full-size part is slow
            self.parts_made += 1
            if self.parts_made == 2:
                stored += self.part_tail
        return stored.replace("\n", "\r\n") if self.crlf else stored

    def _create(self, pr, repo, body):
        stored = self._stored(body)
        out = Fake._create(self, pr, repo, stored)
        self.sent[out["id"]] = body
        if body.startswith(rr.MARKER):
            self.head_made = True
            if self.drop_head:
                self.hidden.add(out["id"])
        return out if self.no_transit else dict(out, transit=cloud_builder.transit_compare(body, stored))


def run(tmp_path, fake, name="account.json", **over):
    return rr.write(put(tmp_path, account(**over), name), str(tmp_path), fake.readers())


def transits(fake):
    return {c["id"]: cloud_builder.transit_compare(fake.sent[c["id"]], c["body"])["transit"] for c in fake.comments}


def dirty():
    """A finding body with real ESC colour codes, a BEL, a NUL and a C1 control."""
    return "pre " + ESC + "[31mFAIL" + ESC + "[0m bell" + BEL + " nul" + NUL + " c1" + C1_CSI + " post"


STOOD = "pre FAIL bell" + PICTURE_BEL + " nul" + PICTURE_NUL + " c1[U+009B] post"


def varied_findings(count, body_chars):
    """`count` findings whose bodies are about `body_chars` long, each line numbered and built from distinct words, so
    the transit comparison of a long, varied body stays fast (a long repetitive one makes difflib crawl)."""
    rows = many_findings(count, 1)
    for i, row in enumerate(rows):
        lines, size, n = [], 0, 0
        while size < body_chars:
            line = f"{i}.{n}: " + " ".join(f"w{(i * 7919 + n * 104729 + k * 1299709) % 1000003:x}" for k in range(6))
            lines.append(line)
            size += len(line) + 1
            n += 1
        row["body"] = "\n".join(lines)[:body_chars]
    return rows


def rewritable(text):
    """The characters of `text` the store would rewrite as a raw byte."""
    return [ch for ch in text if ord(ch) in RAW_CODES]


# --- T1: the round trip (DoD arm A) ---

@pytest.mark.parametrize("many", [False, True], ids=["one-comment", "parts"])
def test_t1_a_finding_with_control_codes_is_written_and_read_back_in_stand_in_form(tmp_path, many):
    # axis: a record string holding a code GitHub rewrites reads back whole; write ok with a read that cannot parse
    fake = GitHubLike()
    if many:
        findings = varied_findings(5, 20000)
        findings[0] = dict(findings[0], body=dirty())
    else:
        findings = [finding(body=dirty())]
    out = run(tmp_path, fake, findings=findings)
    assert out["ok"], out
    assert out["transit"] == "matched" and "transitLine" not in out
    assert (len(parts_of(fake)) >= 2) is many
    rec = rr.read(7, readers=fake.readers())
    assert rec["ok"], rec
    row = next(f for f in rec["findings"] if f["id"] == findings[0]["id"])
    assert row["body"] == STOOD
    assert ESC not in row["body"] and "[31m" not in row["body"] and "[0m" not in row["body"]
    assert "transitDamage" not in rec
    for c in fake.comments:
        assert c["body"] == fake.sent[c["id"]], "the store changed a posted body"
        assert not re.search(r"\^[@-_]", c["body"]) and not rewritable(c["body"])


# --- T2: the stand-in truth table ---

def expected_standin(code):
    if code in (*range(0x00, 0x08), *range(0x0E, 0x20)):
        return chr(0x2400 + code)
    if code == 0x7F:
        return chr(0x2421)
    if 0x80 <= code <= 0x9F:
        return "[U+%04X]" % code
    return chr(code)


def test_t2_every_code_has_its_stand_in_or_is_left_alone():
    # axis: the stand-in rule over all 256 codes, mapped and untouched
    for code in range(256):
        assert rr._visible_controls("a" + chr(code) + " ") == "a" + expected_standin(code) + " ", hex(code)
    for code in (0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D):
        assert rr._visible_controls("a" + chr(code) + "b") == "a" + chr(code) + "b"
    assert rr._visible_controls(chr(0x1B)) == PICTURE_ESC and PICTURE_ESC == chr(0x2400 + 0x1B)
    assert expected_standin(0x9B) == "[U+009B]" and expected_standin(0x8F) == "[U+008F]"


def test_t2_ansi_sequences_are_removed_and_a_lone_esc_is_stood_in():
    # axis: ANSI escape sequences leave nothing behind; an ESC that starts none is shown, never dropped
    visible = rr._visible_controls
    assert visible("x" + ESC + "[31;1mred" + ESC + "[0m") == "xred"
    assert visible("x" + ESC + "[2 qy") == "xy"
    assert visible("x" + ESC + "]0;title" + BEL + "after") == "xafter"
    assert visible("x" + ESC + "]0;title" + ESC + BACKSLASH + "after") == "xafter"
    assert visible("x" + ESC + "]0;title" + chr(0x9C) + "after") == "xafter"
    assert visible("x" + ESC + "Mi") == "xi"
    assert visible("a" + ESC + "b") == "a" + PICTURE_ESC + "b"
    assert visible("a" + ESC) == "a" + PICTURE_ESC
    assert visible(ESC + ESC + "[0m") == PICTURE_ESC
    assert visible("x" + chr(0x9D) + "no end") == "x[U+009D]no end"
    # a C1 code never starts a removed sequence: an 8-bit CSI or OSC is stood in, and the text after it is kept
    assert visible(chr(0x9B) + "31mX") == "[U+009B]31mX"
    assert visible(chr(0x9D) + "0;t" + chr(7)) == "[U+009D]0;t" + chr(0x2407)


# --- T3: dict keys ---

def test_t3_a_key_holding_a_control_is_stood_in():
    # axis: a dict key holding a code GitHub rewrites is posted as its stand-in
    assert rr._scrubbed({"a" + chr(1) + "b": 1, "c" + chr(0x9B): 2}) == {"a" + chr(0x2401) + "b": 1, "c[U+009B]": 2}


@pytest.mark.parametrize("stand_in_first", [True, False], ids=["stand-in-first", "literal-first"])
def test_t3_a_stood_in_key_that_meets_a_literal_picture_key_keeps_both_entries(stand_in_first):
    # axis: the stood-in name lands on a taken name; both entries kept, none overwritten or lost
    pairs = [("a" + NUL, "from-nul"), ("a" + PICTURE_NUL, "literal")]
    out = rr._scrubbed(dict(pairs if stand_in_first else pairs[::-1]))
    assert len(out) == 2 and sorted(out.values()) == ["from-nul", "literal"]
    assert out["a" + PICTURE_NUL] == "literal" and out["a" + PICTURE_NUL + "-1"] == "from-nul"


@pytest.mark.parametrize("decorated_first", [True, False], ids=["decorated-first", "real-first"])
def test_t3_an_ansi_decorated_key_beside_the_real_key_keeps_both(decorated_first):
    # axis: the real key's value is never overwritten by the key that reduces to its name
    pairs = [(ESC + "[1moutcome" + ESC + "[0m", "decorated"), ("outcome", "real")]
    out = rr._scrubbed(dict(pairs if decorated_first else pairs[::-1]))
    assert out == {"outcome": "real", "outcome-1": "decorated"}


def test_t3_a_key_that_is_secret_only_once_its_ansi_is_removed_hides_its_value():
    # axis: the posted key name is checked as well as the original, so a stand-in never exposes a secret key's value
    value = "a-private-value"
    out = rr._scrubbed({"t" + ESC + "[1moken" + ESC + "[0m": value})
    assert value not in json.dumps(out) and list(out.values()) == ["[REDACTED]"]


# --- T4: raw output ---

def test_t4_a_raw_output_with_colour_codes_posts_no_rewritable_code_and_reads_back_matched(tmp_path):
    # axis: the raw comment posts no code GitHub rewrites; a raw ESC stored as caret notation reads back changed
    raw = tmp_path / "raw.txt"
    raw.write_text("run " + ESC + "[31mFAIL" + ESC + "[0m" + BEL + " done\n")
    fake = GitHubLike()
    out = run(tmp_path, fake, rawFindingsFiles=[str(raw)])
    assert out["ok"], out
    (comment,) = fake.raws()
    assert not rewritable(comment["body"]) and not re.search(r"\^[@-_]", comment["body"])
    assert "run FAIL" + PICTURE_BEL + " done" in comment["body"]
    assert {c["what"]: c["transit"]["transit"] for c in out["transitChecks"]}["raw output raw.txt"] == "matched"
    assert transits(fake)[comment["id"]] == "matched"


def test_t4_a_raw_output_that_is_a_credential_only_once_its_ansi_is_removed_is_withheld():
    # axis: the secret check also runs on the text that would be posted, so removing an ESC never builds a posted credential
    text = "pass" + ESC + "[0m" + "word = " + "x" * 8 + "\n"
    assert not rr._has_secret(text)
    body, withheld = rr.render_raw("raw.txt", text)
    assert withheld is True and "x" * 8 not in body


# --- T5: a write that does not read back refuses ---

def refused(out, fake, reason="review-record-unreadable-after-write"):
    assert out["ok"] is False and out["reason"] == reason, out
    assert fake.comments[-1]["url"] in out["detail"], out
    return out["detail"]


def test_t5_e1_a_listing_that_fails_after_the_write_refuses_gh_failed(tmp_path):
    # axis: a failed re-listing refuses; the write is never ok when the record could not be read back
    fake = GitHubLike(list_fails_after_head=True)
    detail = refused(run(tmp_path, fake, findings=[finding()]), fake, "review-record-gh-failed")
    assert "read the record back after the write" in detail and "posted" in detail


def test_t5_e2_a_head_missing_from_the_new_listing_refuses(tmp_path):
    # axis: the head id absent from the fresh listing is a refusal
    fake = GitHubLike(drop_head=True)
    assert "the comment is missing" in refused(run(tmp_path, fake, findings=[finding()]), fake)


def test_t5_e3_a_head_whose_marker_was_damaged_refuses(tmp_path):
    # axis: the marker predicate `read` uses decides which listed comment is the record
    fake = GitHubLike(damage_marker=True)
    detail = refused(run(tmp_path, fake, findings=[finding()]), fake)
    assert "the comment no longer carries the record marker" in detail and "was posted but does not read back" in detail


def test_t5_e4_a_head_whose_json_no_longer_parses_arrives_changed_and_refuses(tmp_path):
    # axis: a changed read-back is parsed again; the caret rewrite of an escape leaves the record unreadable
    fake = GitHubLike(corrupt_json=True)
    out = run(tmp_path, fake, findings=[finding()])
    assert transits(fake)[fake.comments[-1]["id"]] == "changed"
    detail = refused(out, fake)
    assert "does not parse" in detail and "Transit damage" in detail and detail.startswith(fake.comments[-1]["url"])


def test_t5_e4_crlf_framing_arrives_matched_and_refuses(tmp_path):
    # axis: a matched read-back is parsed again; CRLF framing matches yet the JSON block is not found
    fake = GitHubLike(crlf=True)
    out = run(tmp_path, fake, findings=[finding()])
    assert set(transits(fake).values()) == {"matched"}
    detail = refused(out, fake)
    assert "Transit" not in detail and detail.startswith(fake.comments[-1]["url"])


@pytest.mark.parametrize("tail, leg", [(" ", "matched"), ("\nextra", "changed")], ids=["matched", "changed"])
def test_t5_e5_a_parts_record_whose_part_cannot_be_sliced_refuses(tmp_path, tail, leg):
    # axis: a parts record is joined again; a part with text after its closing fence is not a part
    fake = GitHubLike(part_tail=tail)
    out = run(tmp_path, fake, findings=varied_findings(5, 14000))
    assert len(parts_of(fake)) >= 2
    assert ("changed" in transits(fake).values()) is (leg == "changed")
    assert ("changed" not in transits(fake).values()) is (leg == "matched")
    assert "malformed" in refused(out, fake)


def test_t5_e6_a_head_that_parses_without_a_findings_list_refuses(tmp_path):
    # axis: a record that parses but lists no findings is as unreadable as one that does not parse
    fake = GitHubLike(break_findings=True)
    assert "the record could not be read" in refused(run(tmp_path, fake, findings=[finding()]), fake)


# --- T6: the edges that stay as they were ---

def test_t6_e7_a_changed_record_that_still_parses_stays_ok_with_its_transit_line(tmp_path):
    # axis: a changed read-back that parses is reported changed, never refused
    fake = GitHubLike(rewrite=drop_bangs)
    out = run(tmp_path, fake, findings=cdata_findings())
    assert out["ok"] is True and out["transit"] == "changed"
    assert out["transitLine"].startswith("record (comment ") and "Transit damage" in out["transitLine"]


def test_t6_e8_a_write_with_nothing_read_back_lists_the_comments_no_extra_time(tmp_path):
    # axis: not-checked skips the re-listing; the comments are listed once more only when every comment was read back
    quiet = GitHubLike(no_transit=True)
    out = run(tmp_path, quiet, findings=[finding()])
    assert out["ok"] is True and out["transit"] == "not-checked"
    checked = GitHubLike()
    assert run(tmp_path, checked, name="b.json", findings=[finding()])["ok"] is True
    assert checked.listed == quiet.listed + 1


# --- T7: identity ---

def test_t7_a_second_write_over_a_record_holding_stand_ins_is_not_unaccounted(tmp_path):
    # axis: the finding's stored identity is the account's, so stand-ins in its text never make it unaccounted
    fake = GitHubLike()
    row = finding(title="t" + ESC + "[1mx" + BEL, body=dirty(), reason="fixed in 1a2b3c4" + NUL)
    assert run(tmp_path, fake, findings=[row])["ok"] is True
    again = run(tmp_path, fake, name="b.json", findings=[row])
    assert again["ok"] is True, again
    assert rr.read(7, readers=fake.readers())["ok"] is True
