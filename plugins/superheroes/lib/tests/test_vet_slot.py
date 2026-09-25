"""Fake-runner units for vet_slot.py. No real gh or network — every gh call is faked."""
import json
import os
import subprocess
from types import SimpleNamespace

import pytest

import vet_slot as vs

REPO = "owner/example"
PR = 42
VIEW = ("gh", "pr", "view", "42", "-R", REPO, "--json", "body")
COMMENTS = ("gh", "api", "repos/owner/example/issues/42/comments", "--paginate", "--slurp")
FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "vet_slot")

BODY = """## Advisor vet
<!-- superheroes:advisor-vet -->
old slot text

<!-- superheroes:build-record -->
<details><summary>Build record</summary>

### Follow-ups for the advisor

Follow-ups: 2 (1 owner-call)
- FU1 [owner-call] decide the thing
  - a sub-bullet with detail
- FU2 [defect] fix the other thing
</details>

trailer
"""

RECEIPT = """<!-- superheroes:vet-receipt -->
**Vet 1: READY.**

**Dispositions — completed.** The vet's own items are done.
- FU1: filed #12
- FU2: fixed in PR

<!-- superheroes:pending-proposals -->
**Pending.** `None`.
"""

SLOT = "**Verdict: READY** · abc\n\nNew owner half.\n"


def _fixture(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8", newline="") as handle:
        return handle.read()


def _comment(body, created="2026-09-25T10:00:00Z", cid=1):
    return {"id": cid, "html_url": "https://x/c/%d" % cid, "body": body, "created_at": created}


def _pages(*pages):
    return json.dumps([list(p) for p in pages])


class FakeGh:
    """Keyed on argv; body reads are served in order (first read, re-read, readback)."""

    def __init__(self, bodies, comments_out, edit_rc=0, view_rc=0, comments_rc=0, view_raw=None):
        self.bodies = list(bodies)
        self.comments_out = comments_out
        self.edit_rc = edit_rc
        self.view_rc = view_rc
        self.comments_rc = comments_rc
        self.view_raw = view_raw
        self.calls = []
        self.edited = []

    def __call__(self, argv, **kwargs):
        self.calls.append(list(argv))
        assert kwargs.get("timeout") == vs.GH_TIMEOUT
        key = tuple(argv)
        if key == VIEW:
            if self.view_rc:
                return SimpleNamespace(returncode=self.view_rc, stdout="", stderr="boom")
            if self.view_raw is not None:
                return SimpleNamespace(returncode=0, stdout=self.view_raw, stderr="")
            body = self.bodies.pop(0) if len(self.bodies) > 1 else self.bodies[0]
            return SimpleNamespace(returncode=0, stdout=json.dumps({"body": body}), stderr="")
        if key == COMMENTS:
            return SimpleNamespace(returncode=self.comments_rc, stdout=self.comments_out, stderr="")
        if argv[:6] == ["gh", "pr", "edit", "42", "-R", REPO] and argv[6] == "--body-file":
            with open(argv[7], encoding="utf-8") as handle:
                self.edited.append(handle.read())
            if not self.edit_rc and self.bodies:
                self.bodies = [self.edited[-1]]
            return SimpleNamespace(returncode=self.edit_rc, stdout="", stderr="edit boom")
        raise AssertionError("unexpected argv %r" % (argv,))

    def edit_calls(self):
        return [c for c in self.calls if c[:3] == ["gh", "pr", "edit"]]


@pytest.fixture(autouse=True)
def _gh_on_path(monkeypatch):
    monkeypatch.setattr(vs.shutil, "which", lambda name: "/usr/bin/gh" if name == "gh" else None)


@pytest.fixture
def slot_file(tmp_path):
    path = tmp_path / "slot.md"
    path.write_text(SLOT, encoding="utf-8")
    return str(path)


def _write(fake, slot_path, pr=PR, repo=REPO):
    return vs.run_verb("write", pr, repo, slot_file=slot_path, run=fake)


def _ok_fake(body=BODY, receipt=RECEIPT):
    return FakeGh([body], _pages([_comment(receipt)]))


# --- the ok write: exact edit argv and the span invariant -----------------------------------

def test_ok_write_replaces_only_the_slot_span(slot_file):
    fake = _ok_fake()
    result = _write(fake, slot_file)
    assert result == {"ok": True, "verb": "write", "followups": ["FU1", "FU2"],
                      "receipt": "https://x/c/1"}
    edits = fake.edit_calls()
    assert len(edits) == 1
    edit = edits[0]
    assert edit[:7] == ["gh", "pr", "edit", "42", "-R", REPO, "--body-file"]
    assert len(edit) == 8
    assert not os.path.exists(edit[7])  # the temp file is removed afterwards
    new = fake.edited[0]
    a = BODY.index("<!-- superheroes:advisor-vet -->\n") + len("<!-- superheroes:advisor-vet -->\n")
    b = BODY.index("<!-- superheroes:build-record -->")
    b2 = new.index("<!-- superheroes:build-record -->")
    assert new[:a] == BODY[:a]
    assert new[b2:] == BODY[b:]
    assert new[a:b2] == "\n" + SLOT.strip("\n") + "\n\n"
    # every gh pr call carries -R
    for call in fake.calls:
        if call[:2] == ["gh", "pr"]:
            assert call[4:6] == ["-R", REPO]
    assert fake.calls[0] == list(VIEW)
    assert fake.calls[1] == list(COMMENTS)
    assert fake.calls[2] == list(VIEW)  # pre-push re-read
    assert fake.calls[4] == list(VIEW)  # readback


def test_ok_check_reports_receipt_present():
    fake = _ok_fake()
    result = vs.run_verb("check", PR, REPO, run=fake)
    assert result == {"ok": True, "verb": "check", "followups": ["FU1", "FU2"],
                      "receipt": "https://x/c/1", "receiptPresent": True}
    assert fake.edit_calls() == []


# --- refusal fixtures: literal token, zero edit calls ---------------------------------------

def _body_with_followups(section):
    return BODY.replace(
        "Follow-ups: 2 (1 owner-call)\n- FU1 [owner-call] decide the thing\n"
        "  - a sub-bullet with detail\n- FU2 [defect] fix the other thing\n", section)


def _receipt_with(field):
    return RECEIPT.replace(
        "**Dispositions — completed.** The vet's own items are done.\n- FU1: filed #12\n"
        "- FU2: fixed in PR\n", field)


BODY_CASES = [
    ("pr-body-empty", "   \n\t\n"),
    ("advisor-vet-marker-missing", BODY.replace("<!-- superheroes:advisor-vet -->\n", "")),
    ("advisor-vet-marker-duplicated", BODY.replace("trailer", "<!-- superheroes:advisor-vet -->")),
    ("advisor-vet-marker-missing",
     BODY.replace("<!-- superheroes:advisor-vet -->\n", "```\n<!-- superheroes:advisor-vet -->\n```\n")),
    ("build-record-marker-missing", BODY.replace("<!-- superheroes:build-record -->\n", "")),
    ("build-record-marker-duplicated",
     BODY.replace("trailer", "<!-- superheroes:build-record -->")),
    ("slot-order-invalid",
     "<!-- superheroes:build-record -->\nx\n<!-- superheroes:advisor-vet -->\n"
     "### Follow-ups for the advisor\nNone\n"),
    ("followups-section-missing", BODY.replace("### Follow-ups for the advisor", "### Other")),
    ("followups-section-missing",
     BODY.replace("### Follow-ups for the advisor", "```\n### Follow-ups for the advisor\n```")),
    ("followup-unkeyed", _body_with_followups("")),
    ("followup-unkeyed", _body_with_followups("None\n- FU1 [defect] x\n")),
    ("followup-unkeyed", _body_with_followups("- plain bullet\n")),
    ("followup-unkeyed", _body_with_followups("  indented before any item\n- FU1 [defect] x\n")),
    ("followup-unkeyed", _body_with_followups("Follow-ups: 0 (0 owner-call)\n")),
    ("followup-id-nested", _body_with_followups("- FU1 [defect] x\n  - FU2 [craft] hidden\n")),
    ("followup-id-nested", _body_with_followups("- FU1 [defect] x\n    FU2 [craft] hidden\n")),
    ("followup-class-unknown", _body_with_followups("- FU1 [bogus] x\n")),
    ("followup-id-duplicated", _body_with_followups("- FU1 [defect] x\n- FU1 [craft] y\n")),
    ("followup-count-mismatch", _body_with_followups("Follow-ups: 3 (0 owner-call)\n- FU1 [defect] x\n")),
    ("followup-count-mismatch", _body_with_followups("Follow-ups: 1 (1 owner-call)\n- FU1 [defect] x\n")),
]


@pytest.mark.parametrize("token,body", BODY_CASES)
@pytest.mark.parametrize("verb", ["write", "check"])
def test_body_refusals_make_no_edit(token, body, verb, slot_file):
    fake = _ok_fake(body=body)
    result = vs.run_verb(verb, PR, REPO, slot_file=slot_file if verb == "write" else None, run=fake)
    assert result["ok"] is False
    assert result["reason"] == token
    assert set(result) == {"ok", "reason", "detail"}
    assert fake.edit_calls() == []
    assert fake.calls == [list(VIEW)]  # a bad body never reaches the comments read


def test_empty_read_refuses_pr_body_empty(slot_file):
    fake = FakeGh([""], _pages([_comment(RECEIPT)]))
    result = _write(fake, slot_file)
    assert result["reason"] == "pr-body-empty"
    assert fake.edit_calls() == []


RECEIPT_CASES = [
    ("receipt-dispositions-missing", RECEIPT.replace("**Dispositions — completed.**", "**Other.**")),
    ("receipt-dispositions-missing", RECEIPT.replace("<!-- superheroes:pending-proposals -->", "")),
    ("receipt-none-over-followups", _receipt_with("**Dispositions — completed.** `None`\n")),
    ("receipt-none-over-followups", _receipt_with("**Dispositions — completed.**\n\nNone\n")),
    ("disposition-missing", _receipt_with("**Dispositions — completed.**\n- FU1: filed #12\n")),
    ("disposition-missing", _receipt_with("**Dispositions — completed.** FU1 and FU2 filed.\n")),
    ("disposition-id-unknown",
     _receipt_with("**Dispositions — completed.**\n- FU1: filed #1\n- FU2: fixed\n- FU3: info\n")),
    ("disposition-id-duplicated",
     _receipt_with("**Dispositions — completed.**\n- FU1: filed #1\n- FU1: fixed\n- FU2: info\n")),
    ("disposition-unrecognized",
     _receipt_with("**Dispositions — completed.**\n- FU1: ignored it\n- FU2: fixed\n")),
]


@pytest.mark.parametrize("token,receipt", RECEIPT_CASES)
@pytest.mark.parametrize("verb", ["write", "check"])
def test_receipt_refusals_make_no_edit(token, receipt, verb, slot_file):
    fake = _ok_fake(receipt=receipt)
    result = vs.run_verb(verb, PR, REPO, slot_file=slot_file if verb == "write" else None, run=fake)
    assert result["ok"] is False
    assert result["reason"] == token
    assert fake.edit_calls() == []


NONE_BODY = _body_with_followups("`None`\n")


def test_none_build_with_any_receipt_id_is_unknown():
    fake = _ok_fake(body=NONE_BODY)
    result = vs.run_verb("check", PR, REPO, run=fake)
    assert result["reason"] == "disposition-id-unknown"


def test_none_build_with_none_receipt_is_ok(slot_file):
    fake = _ok_fake(body=NONE_BODY, receipt=_receipt_with("**Dispositions — completed.** None\n"))
    result = _write(fake, slot_file)
    assert result["ok"] is True
    assert result["followups"] == []
    assert len(fake.edit_calls()) == 1


def test_check_no_receipt_with_none_followups_is_ok():
    fake = FakeGh([NONE_BODY], _pages([_comment("just a comment")]))
    result = vs.run_verb("check", PR, REPO, run=fake)
    assert result == {"ok": True, "verb": "check", "followups": [], "receipt": None,
                      "receiptPresent": False}


@pytest.mark.parametrize("body", [BODY, NONE_BODY])
def test_write_no_receipt_is_receipt_missing(body, slot_file):
    fake = FakeGh([body], _pages([_comment("just a comment")]))
    result = _write(fake, slot_file)
    assert result["reason"] == "receipt-missing"
    assert fake.edit_calls() == []


def test_check_no_receipt_with_followups_is_receipt_missing():
    fake = FakeGh([BODY], _pages([]))
    assert vs.run_verb("check", PR, REPO, run=fake)["reason"] == "receipt-missing"


@pytest.mark.parametrize("comments_out", [
    "not json",
    json.dumps({"a": 1}),
    json.dumps([{"body": "x", "created_at": "t"}]),  # a page that is not a list
    json.dumps([[{"body": 1, "created_at": "t"}]]),
    json.dumps([[{"body": "x"}]]),
    json.dumps([["a string comment"]]),
])
def test_bad_comments_shape_is_receipt_unreadable(comments_out, slot_file):
    fake = FakeGh([BODY], comments_out)
    result = _write(fake, slot_file)
    assert result["reason"] == "receipt-unreadable"
    assert fake.edit_calls() == []


def test_comments_nonzero_exit_is_receipt_unreadable(slot_file):
    fake = FakeGh([BODY], _pages([_comment(RECEIPT)]), comments_rc=1)
    assert _write(fake, slot_file)["reason"] == "receipt-unreadable"
    assert fake.edit_calls() == []


def test_receipt_on_page_two_is_newest_and_selected():
    stale = _receipt_with("**Dispositions — completed.**\n- FU1: filed #1\n")
    pages = _pages(
        [_comment(stale, "2026-09-25T09:00:00Z", 1), _comment("chatter", "2026-09-25T12:00:00Z", 2)],
        [_comment("﻿  " + RECEIPT, "2026-09-25T11:00:00Z", 3)],
    )
    fake = FakeGh([BODY], pages)
    result = vs.run_verb("check", PR, REPO, run=fake)
    assert result["ok"] is True
    assert result["receipt"] == "https://x/c/3"


# --- read failures -----------------------------------------------------------------------------

@pytest.mark.parametrize("kwargs", [
    {"view_rc": 1},
    {"view_raw": "not json"},
    {"view_raw": json.dumps(["body"])},
    {"view_raw": json.dumps({"body": None})},
])
def test_body_read_failures_are_pr_body_unreadable(kwargs, slot_file):
    fake = FakeGh([BODY], _pages([_comment(RECEIPT)]), **kwargs)
    result = _write(fake, slot_file)
    assert result["reason"] == "pr-body-unreadable"
    assert fake.edit_calls() == []


def test_gh_missing_is_pr_body_unreadable(monkeypatch, slot_file):
    monkeypatch.setattr(vs.shutil, "which", lambda _name: None)
    fake = _ok_fake()
    assert _write(fake, slot_file)["reason"] == "pr-body-unreadable"
    assert fake.calls == []


def test_timeout_is_pr_body_unreadable(slot_file):
    calls = []

    def run(argv, **kwargs):
        calls.append(argv)
        raise subprocess.TimeoutExpired(argv, kwargs.get("timeout"))

    assert _write(run, slot_file)["reason"] == "pr-body-unreadable"
    assert not [c for c in calls if c[:3] == ["gh", "pr", "edit"]]


# --- slot file ---------------------------------------------------------------------------------

@pytest.mark.parametrize("content,token", [
    (None, "slot-file-unreadable"),
    ("\n  \n", "slot-text-empty"),
    ("text\n<!-- superheroes:build-record -->\nmore\n", "slot-text-carries-marker"),
])
def test_slot_file_refusals(tmp_path, content, token):
    path = tmp_path / "slot.md"
    if content is not None:
        path.write_text(content, encoding="utf-8")
    fake = _ok_fake()
    result = _write(fake, str(path))
    assert result["reason"] == token
    assert fake.calls == [list(VIEW)]  # refused before the comments read


# --- write-time refusals -----------------------------------------------------------------------

def test_body_changed_between_read_and_push(slot_file):
    fake = FakeGh([BODY, BODY + "someone else's edit\n"], _pages([_comment(RECEIPT)]))
    result = _write(fake, slot_file)
    assert result["reason"] == "body-changed-under-write"
    assert fake.edit_calls() == []


def test_edit_nonzero_is_write_failed(slot_file):
    fake = FakeGh([BODY], _pages([_comment(RECEIPT)]), edit_rc=1)
    result = _write(fake, slot_file)
    assert result["reason"] == "write-failed"
    assert not os.path.exists(fake.edit_calls()[0][7])


def test_readback_mismatch(slot_file):
    fake = _ok_fake()
    original_call = fake.__call__

    def run(argv, **kwargs):
        out = original_call(argv, **kwargs)
        if argv[:3] == ["gh", "pr", "edit"]:
            fake.bodies = ["rewritten by the far side"]
        return out

    result = _write(run, slot_file)
    assert result["reason"] == "write-readback-mismatch"


def test_readback_tolerates_crlf_and_trailing_whitespace(slot_file):
    fake = _ok_fake()
    original_call = fake.__call__

    def run(argv, **kwargs):
        out = original_call(argv, **kwargs)
        if argv[:3] == ["gh", "pr", "edit"]:
            fake.bodies = [fake.edited[-1].replace("\n", "\r\n") + "  \n"]
        return out

    assert _write(run, slot_file)["ok"] is True


# --- argument validation ----------------------------------------------------------------------

@pytest.mark.parametrize("pr,repo,slot", [
    (0, REPO, "x"), (True, REPO, "x"), (PR, "not-a-repo", "x"), (PR, REPO, None),
])
def test_bad_arguments(pr, repo, slot):
    fake = _ok_fake()
    result = vs.run_verb("write", pr, repo, slot_file=slot, run=fake)
    assert result["reason"] == "bad-argument"
    assert fake.calls == []


# --- the invariant, stated directly over every refusal fixture -------------------------------

def test_property_every_refusal_is_editless_and_ok_preserves_outside_span(slot_file):
    for _token, body in BODY_CASES:
        fake = _ok_fake(body=body)
        assert _write(fake, slot_file)["ok"] is False
        assert fake.edit_calls() == []
    for _token, receipt in RECEIPT_CASES:
        fake = _ok_fake(receipt=receipt)
        assert _write(fake, slot_file)["ok"] is False
        assert fake.edit_calls() == []
    for body in (BODY, NONE_BODY):
        receipt = RECEIPT if body is BODY else _receipt_with("**Dispositions — completed.** None\n")
        result = vs.evaluate("write", body, [_comment(receipt)], SLOT)
        new = result["newBody"]
        a = body.index("-->\n") + 4
        b = body.index("<!-- superheroes:build-record -->")
        b2 = new.index("<!-- superheroes:build-record -->")
        assert new[:a] == body[:a]
        assert new[b2:] == body[b:]


# --- the section bounds ------------------------------------------------------------------------

def test_section_bounded_by_details_with_followups_last():
    body = BODY.replace("</details>\n\ntrailer\n", "</details>\n\n- not a follow-up after details\n")
    fake = _ok_fake(body=body)
    assert vs.run_verb("check", PR, REPO, run=fake)["ok"] is True


def test_section_bounded_by_next_heading():
    body = BODY.replace("</details>\n", "### Next\n- stray bullet\n</details>\n")
    fake = _ok_fake(body=body)
    assert vs.run_verb("check", PR, REPO, run=fake)["ok"] is True


# --- real-shape fixtures -----------------------------------------------------------------------

def _real_fake(body_name="pr1442_body.md", receipt=None):
    body = _fixture(body_name)
    receipt = _fixture("pr1442_receipt.md") if receipt is None else receipt
    return body, FakeGh([body], _pages([_comment(receipt, cid=5838078017)]))


def test_real_1442_pair_passes_check():
    _body, fake = _real_fake()
    result = vs.run_verb("check", PR, REPO, run=fake)
    assert result["ok"] is True
    assert result["followups"] == ["FU%d" % n for n in range(1, 9)]


def test_real_1442_pair_passes_write(slot_file):
    body, fake = _real_fake()
    result = _write(fake, slot_file)
    assert result["ok"] is True
    new = fake.edited[0]
    a = body.index("<!-- superheroes:advisor-vet -->\n") + len("<!-- superheroes:advisor-vet -->\n")
    b = body.index("<!-- superheroes:build-record -->")
    b2 = new.index("<!-- superheroes:build-record -->")
    assert new[:a] == body[:a]
    assert new[b2:] == body[b:]
    assert new[a:b2] == "\n" + SLOT.strip("\n") + "\n\n"


def test_real_1437_legacy_body_refuses_unkeyed():
    _body, fake = _real_fake(body_name="pr1437_body_legacy.md")
    result = vs.run_verb("check", PR, REPO, run=fake)
    assert result["reason"] == "followup-unkeyed"


def test_receipt_missing_fu2_refuses_disposition_missing(slot_file):
    receipt = _fixture("pr1442_receipt.md")
    lines = receipt.split("\n")
    fu2 = [line for line in lines if line.startswith("- FU2:")]
    assert len(fu2) == 1
    receipt = "\n".join(line for line in lines if not line.startswith("- FU2:"))
    _body, fake = _real_fake(receipt=receipt)
    result = _write(fake, slot_file)
    assert result["ok"] is False
    assert result["reason"] == "disposition-missing"
    assert "FU2" in result["detail"]
    assert fake.edit_calls() == []


# --- CLI ---------------------------------------------------------------------------------------

def test_cli_ok_write(capsys, slot_file):
    fake = _ok_fake()
    code = vs.main(["write", "--pr", "42", "--repo", REPO, "--slot-file", slot_file], run=fake)
    out = capsys.readouterr().out
    assert code == 0
    assert out.endswith("\n") and out.count("\n") == 1
    assert json.loads(out)["ok"] is True


def test_cli_refusal(capsys):
    fake = _ok_fake(body="")
    code = vs.main(["check", "--pr", "42", "--repo", REPO], run=fake)
    out = capsys.readouterr().out
    assert code == 1
    assert json.loads(out) == {"ok": False, "reason": "pr-body-empty", "detail": None}


@pytest.mark.parametrize("argv", [
    [], ["frob"], ["check", "--pr", "x", "--repo", REPO], ["check", "--repo", REPO],
    ["check", "--pr", "42", "--repo", REPO, "--slot-file", "s"], ["write", "--pr", "42", "--repo", REPO],
])
def test_cli_bad_argument(capsys, argv):
    code = vs.main(argv, run=_ok_fake())
    assert code == 1
    assert json.loads(capsys.readouterr().out)["reason"] == "bad-argument"
