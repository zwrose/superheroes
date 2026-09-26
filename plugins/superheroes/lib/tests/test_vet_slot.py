"""Fake-runner units for vet_slot.py. No real gh or network — every gh call is faked."""
import inspect
import json
import os
import re
import subprocess
from types import SimpleNamespace

import pytest

import vet_slot as vs

REPO = "owner/example"
PR = 42
VIEW = ("gh", "pr", "view", "42", "-R", REPO, "--json", "body")
COMMENTS = ("gh", "api", "repos/owner/example/issues/42/comments", "--paginate", "--slurp")
FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "vet_slot")

FU_MARKER = "<!-- superheroes:followups FU1 FU2 -->"
DISP_MARKER = "<!-- superheroes:dispositions FU1 FU2 -->"

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
<!-- superheroes:followups FU1 FU2 -->
</details>

trailer
"""

RECEIPT = """<!-- superheroes:vet-receipt -->
**Vet 1: READY.**

**Dispositions — completed.** The vet's own items are done.
- FU1: filed #12
- FU2: fixed in PR
<!-- superheroes:dispositions FU1 FU2 -->

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


# --- refusal fixtures: literal token, a distinguishing detail, zero edit calls -------------

NINE_TOKENS = {
    "bad-argument", "read-failed", "markers-invalid", "receipt-missing",
    "followup-undispositioned", "disposition-unknown", "none-over-list", "write-failed",
    "write-unconfirmed",
}


def test_module_emits_exactly_nine_tokens():
    source = inspect.getsource(vs)
    emitted = set(re.findall(r'_Refusal\(\s*"([a-z-]+)"', source))
    emitted |= set(re.findall(r'_refusal\(\s*"([a-z-]+)"', source))
    emitted |= set(re.findall(r'reason="([a-z-]+)"', source))
    assert emitted == NINE_TOKENS
    for retired in ("followups-malformed", "dispositions-malformed"):
        assert retired not in source, retired


def _body_marker(line):
    """BODY with its live followups marker line replaced by ``line`` (may be several lines)."""
    assert BODY.count(FU_MARKER + "\n") == 1
    return BODY.replace(FU_MARKER + "\n", line)


def _receipt_marker(line):
    assert RECEIPT.count(DISP_MARKER + "\n") == 1
    return RECEIPT.replace(DISP_MARKER + "\n", line)


BODY_CASES = [
    ("read-failed", "empty", "   \n\t\n"),
    ("markers-invalid", "advisor-vet marker appears 0 times",
     BODY.replace("<!-- superheroes:advisor-vet -->\n", "")),
    ("markers-invalid", "advisor-vet marker appears 2 times",
     BODY.replace("trailer", "<!-- superheroes:advisor-vet -->")),
    ("markers-invalid", "advisor-vet marker appears 0 times",
     BODY.replace("<!-- superheroes:advisor-vet -->\n", "```\n<!-- superheroes:advisor-vet -->\n```\n")),
    ("markers-invalid", "build-record marker appears 0 times",
     BODY.replace("<!-- superheroes:build-record -->\n", "")),
    ("markers-invalid", "build-record marker appears 2 times",
     BODY.replace("trailer", "<!-- superheroes:build-record -->")),
    ("markers-invalid", "advisor-vet marker is not above",
     "<!-- superheroes:build-record -->\nx\n<!-- superheroes:advisor-vet -->\n" + FU_MARKER + "\n"),
    # the followups marker: exactly one, below the build-record marker, well formed, unique ids
    ("markers-invalid", "followups marker appears 0 times", _body_marker("")),
    ("markers-invalid", "followups marker appears 2 times",
     BODY.replace("trailer", FU_MARKER)),
    ("markers-invalid", "followups marker appears 0 times",
     _body_marker("```\n" + FU_MARKER + "\n```\n")),
    ("markers-invalid", "followups marker appears 0 times",
     _body_marker("<!-- draft\n" + FU_MARKER + "\n-->\n")),
    ("markers-invalid", "followups marker is not below the build-record marker",
     _body_marker("").replace("old slot text", FU_MARKER)),
    ("markers-invalid", "followups marker is malformed: <!-- superheroes:followups FU01 FU2 -->",
     _body_marker("<!-- superheroes:followups FU01 FU2 -->\n")),
    ("markers-invalid", "followups marker is malformed: <!-- superheroes:followups FU -->",
     _body_marker("<!-- superheroes:followups FU -->\n")),
    ("markers-invalid", "followups marker is malformed: <!-- superheroes:followups fu1 fu2 -->",
     _body_marker("<!-- superheroes:followups fu1 fu2 -->\n")),
    ("markers-invalid", "followups marker is malformed: <!-- superheroes:followups FU1 FU2\n",
     _body_marker("<!-- superheroes:followups FU1 FU2\n")),
    ("markers-invalid", "followups marker is malformed: <!-- superheroes:followups FU1 FU2 done -->",
     _body_marker("<!-- superheroes:followups FU1 FU2 done -->\n")),
    ("markers-invalid", "followups marker is malformed: <!-- superheroes:followups  -->",
     _body_marker("<!-- superheroes:followups  -->\n")),
    ("markers-invalid", "followups marker repeats FU1",
     _body_marker("<!-- superheroes:followups FU1 FU2 FU1 -->\n")),
]


@pytest.mark.parametrize("token,detail,body", BODY_CASES)
@pytest.mark.parametrize("verb", ["write", "check"])
def test_body_refusals_make_no_edit(token, detail, body, verb, slot_file):
    fake = _ok_fake(body=body)
    result = vs.run_verb(verb, PR, REPO, slot_file=slot_file if verb == "write" else None, run=fake)
    assert result["ok"] is False
    assert result["reason"] == token
    assert detail.rstrip("\n") in result["detail"]
    assert set(result) == {"ok", "reason", "detail"}
    assert fake.edit_calls() == []
    assert fake.calls == [list(VIEW)]  # a bad body never reaches the comments read


def test_empty_read_refuses_read_failed(slot_file):
    fake = FakeGh([""], _pages([_comment(RECEIPT)]))
    result = _write(fake, slot_file)
    assert result["reason"] == "read-failed"
    assert "empty" in result["detail"]
    assert fake.edit_calls() == []


def test_non_string_body_refuses_read_failed():
    result = vs.evaluate("write", None, [_comment(RECEIPT)], SLOT)
    assert result == {"ok": False, "reason": "read-failed", "detail": "PR body is not a string"}


@pytest.mark.parametrize("slot_text,detail", [
    ("", "slot text is empty"), ("  \n", "slot text is empty"),
    ("x\n<!-- superheroes:advisor-vet -->\n", "slot text carries a marker"),
])
def test_evaluate_refuses_bad_slot_text(slot_text, detail):
    result = vs.evaluate("write", BODY, [_comment(RECEIPT)], slot_text)
    assert result["reason"] == "write-failed"
    assert detail in result["detail"]
    assert "newBody" not in result


RECEIPT_CASES = [
    ("markers-invalid", "dispositions marker appears 0 times", _receipt_marker("")),
    ("markers-invalid", "dispositions marker appears 2 times",
     _receipt_marker(DISP_MARKER + "\n" + DISP_MARKER + "\n")),
    ("markers-invalid", "dispositions marker appears 0 times",
     _receipt_marker("```\n" + DISP_MARKER + "\n```\n")),
    ("markers-invalid", "dispositions marker appears 0 times",
     _receipt_marker("<!-- draft\n" + DISP_MARKER + "\n-->\n")),
    ("markers-invalid", "dispositions marker is malformed: <!-- superheroes:dispositions FU1 FU2 -- ",
     _receipt_marker("<!-- superheroes:dispositions FU1 FU2 -- \n")),
    ("markers-invalid", "dispositions marker is malformed: <!-- superheroes:dispositions FU1, FU2 -->",
     _receipt_marker("<!-- superheroes:dispositions FU1, FU2 -->\n")),
    ("markers-invalid", "dispositions marker repeats FU2",
     _receipt_marker("<!-- superheroes:dispositions FU1 FU2 FU2 -->\n")),
    ("none-over-list", "none over FU1 FU2",
     _receipt_marker("<!-- superheroes:dispositions none -->\n")),
    ("followup-undispositioned", "FU2: no disposition",
     _receipt_marker("<!-- superheroes:dispositions FU1 -->\n")),
    ("followup-undispositioned", "FU1: no disposition",
     _receipt_marker("<!-- superheroes:dispositions FU2 -->\n")),
    ("disposition-unknown", "FU3: not in the followups marker",
     _receipt_marker("<!-- superheroes:dispositions FU1 FU2 FU3 -->\n")),
]


@pytest.mark.parametrize("token,detail,receipt", RECEIPT_CASES)
@pytest.mark.parametrize("verb", ["write", "check"])
def test_receipt_refusals_make_no_edit(token, detail, receipt, verb, slot_file):
    fake = _ok_fake(receipt=receipt)
    result = vs.run_verb(verb, PR, REPO, slot_file=slot_file if verb == "write" else None, run=fake)
    assert result["ok"] is False
    assert result["reason"] == token
    assert detail in result["detail"]
    assert fake.edit_calls() == []


NONE_BODY = _body_marker("<!-- superheroes:followups none -->\n").replace(
    "Follow-ups: 2 (1 owner-call)\n- FU1 [owner-call] decide the thing\n"
    "  - a sub-bullet with detail\n- FU2 [defect] fix the other thing\n", "None\n")
NONE_RECEIPT = _receipt_marker("<!-- superheroes:dispositions none -->\n")


@pytest.mark.parametrize("verb", ["write", "check"])
def test_list_over_none_build_is_disposition_unknown(verb, slot_file):
    fake = _ok_fake(body=NONE_BODY)
    result = vs.run_verb(verb, PR, REPO, slot_file=slot_file if verb == "write" else None, run=fake)
    assert result["reason"] == "disposition-unknown"
    assert "FU1, FU2: not in the followups marker" in result["detail"]
    assert fake.edit_calls() == []


def test_none_build_with_none_receipt_is_ok(slot_file):
    fake = _ok_fake(body=NONE_BODY, receipt=NONE_RECEIPT)
    result = _write(fake, slot_file)
    assert result["ok"] is True
    assert result["followups"] == []
    assert len(fake.edit_calls()) == 1


def test_fenced_marker_above_the_live_marker_is_ignored(slot_file):
    body = BODY.replace("### Follow-ups for the advisor\n",
                        "```\n<!-- superheroes:followups FU9 -->\n```\n\n### Follow-ups for the advisor\n")
    result = _write(_ok_fake(body=body), slot_file)
    assert result["ok"] is True
    assert result["followups"] == ["FU1", "FU2"]


def test_inline_marker_mention_in_prose_is_ignored():
    body = BODY.replace("trailer\n", "See the <!-- superheroes:followups FU7 --> marker.\n")
    receipt = RECEIPT.replace("**Vet 1: READY.**\n",
                              "**Vet 1: READY.** Wrote <!-- superheroes:dispositions FU7 --> once.\n")
    result = vs.run_verb("check", PR, REPO, run=_ok_fake(body=body, receipt=receipt))
    assert result["ok"] is True
    assert result["followups"] == ["FU1", "FU2"]


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
    assert "vet-receipt marker" in result["detail"]
    assert fake.edit_calls() == []


def test_check_no_receipt_with_followups_is_receipt_missing():
    fake = FakeGh([BODY], _pages([]))
    result = vs.run_verb("check", PR, REPO, run=fake)
    assert result["reason"] == "receipt-missing"
    assert "vet-receipt marker" in result["detail"]


@pytest.mark.parametrize("comments_out,detail", [
    ("not json", "comments: bad JSON"),
    (json.dumps({"a": 1}), "comments: pages are not lists"),
    (json.dumps([{"body": "x", "created_at": "t"}]), "comments: pages are not lists"),
    (json.dumps([[{"body": 1, "created_at": "t"}]]), "comments: a comment lacks"),
    (json.dumps([[{"body": "x"}]]), "comments: a comment lacks"),
    (json.dumps([["a string comment"]]), "comments: a comment lacks"),
])
def test_bad_comments_shape_is_read_failed(comments_out, detail, slot_file):
    fake = FakeGh([BODY], comments_out)
    result = _write(fake, slot_file)
    assert result["reason"] == "read-failed"
    assert detail in result["detail"]
    assert fake.edit_calls() == []


def test_comments_nonzero_exit_is_read_failed(slot_file):
    fake = FakeGh([BODY], _pages([_comment(RECEIPT)]), comments_rc=1)
    result = _write(fake, slot_file)
    assert result["reason"] == "read-failed"
    assert "comments: exit 1" in result["detail"]
    assert fake.edit_calls() == []


def test_receipt_on_page_two_is_newest_and_selected():
    stale = _receipt_marker("<!-- superheroes:dispositions FU1 -->\n")
    pages = _pages(
        [_comment(stale, "2026-09-25T09:00:00Z", 1), _comment("chatter", "2026-09-25T12:00:00Z", 2)],
        [_comment("﻿  " + RECEIPT, "2026-09-25T11:00:00Z", 3)],
    )
    fake = FakeGh([BODY], pages)
    result = vs.run_verb("check", PR, REPO, run=fake)
    assert result["ok"] is True
    assert result["receipt"] == "https://x/c/3"


# --- read failures -----------------------------------------------------------------------------

@pytest.mark.parametrize("kwargs,detail", [
    ({"view_rc": 1}, "PR body: exit 1 boom"),
    ({"view_raw": "not json"}, "PR body: bad JSON"),
    ({"view_raw": json.dumps(["body"])}, "PR body: body is not a string"),
    ({"view_raw": json.dumps({"body": None})}, "PR body: body is not a string"),
])
def test_body_read_failures_are_read_failed(kwargs, detail, slot_file):
    fake = FakeGh([BODY], _pages([_comment(RECEIPT)]), **kwargs)
    result = _write(fake, slot_file)
    assert result["reason"] == "read-failed"
    assert detail in result["detail"]
    assert fake.edit_calls() == []


def test_gh_missing_is_read_failed(monkeypatch, slot_file):
    monkeypatch.setattr(vs.shutil, "which", lambda _name: None)
    fake = _ok_fake()
    result = _write(fake, slot_file)
    assert result["reason"] == "read-failed"
    assert "gh not on PATH" in result["detail"]
    assert fake.calls == []


def test_timeout_is_read_failed(slot_file):
    calls = []

    def run(argv, **kwargs):
        calls.append(argv)
        raise subprocess.TimeoutExpired(argv, kwargs.get("timeout"))

    result = _write(run, slot_file)
    assert result["reason"] == "read-failed"
    assert "PR body: gh call timed out" in result["detail"]
    assert not [c for c in calls if c[:3] == ["gh", "pr", "edit"]]


# --- slot file ---------------------------------------------------------------------------------

@pytest.mark.parametrize("content,detail", [
    (None, "slot file unreadable"),
    ("\n  \n", "slot text is empty"),
    ("text\n<!-- superheroes:build-record -->\nmore\n", "slot text carries a marker"),
])
def test_slot_file_refusals(tmp_path, content, detail):
    path = tmp_path / "slot.md"
    if content is not None:
        path.write_text(content, encoding="utf-8")
    fake = _ok_fake()
    result = _write(fake, str(path))
    assert result["reason"] == "write-failed"
    assert detail in result["detail"]
    assert fake.calls == [list(VIEW)]  # refused before the comments read


# --- write-time refusals -----------------------------------------------------------------------

def test_body_changed_between_read_and_push(slot_file):
    fake = FakeGh([BODY, BODY + "someone else's edit\n"], _pages([_comment(RECEIPT)]))
    result = _write(fake, slot_file)
    assert result["reason"] == "write-failed"
    assert "changed between the read and the push" in result["detail"]
    assert fake.edit_calls() == []


def test_edit_nonzero_is_write_unconfirmed(slot_file):
    fake = FakeGh([BODY], _pages([_comment(RECEIPT)]), edit_rc=1)
    result = _write(fake, slot_file)
    assert result["reason"] == "write-unconfirmed"
    assert ("slot edit call failed (edit: exit 1 edit boom); readback differs from the pushed body"
            in result["detail"])
    assert not os.path.exists(fake.edit_calls()[0][7])


@pytest.mark.parametrize("landed", [True, False])
def test_edit_timeout_reads_back(landed, slot_file):
    fake = _ok_fake()
    original_call = fake.__call__

    def run(argv, **kwargs):
        if argv[:3] == ["gh", "pr", "edit"]:
            if landed:
                original_call(argv, **kwargs)
            else:
                fake.calls.append(list(argv))
            raise subprocess.TimeoutExpired(argv, kwargs.get("timeout"))
        return original_call(argv, **kwargs)

    result = _write(run, slot_file)
    if landed:
        assert result["ok"] is True
    else:
        assert result["reason"] == "write-unconfirmed"
        assert ("slot edit call failed (edit: gh call timed out); readback differs from the "
                "pushed body" in result["detail"])
    assert fake.calls[-1] == list(VIEW)  # the readback ran
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
    assert result["reason"] == "write-unconfirmed"
    assert "slot write already pushed; readback differs" in result["detail"]
    assert len(fake.edit_calls()) == 1


def test_readback_read_failure_after_push_is_write_unconfirmed(slot_file):
    fake = _ok_fake()
    original_call = fake.__call__

    def run(argv, **kwargs):
        out = original_call(argv, **kwargs)
        if argv[:3] == ["gh", "pr", "edit"]:
            fake.view_rc = 1
        return out

    result = _write(run, slot_file)
    assert result["reason"] == "write-unconfirmed"
    assert "slot write already pushed; readback: PR body: exit 1 boom" in result["detail"]
    assert len(fake.edit_calls()) == 1


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
    for _token, _detail, body in BODY_CASES:
        fake = _ok_fake(body=body)
        assert _write(fake, slot_file)["ok"] is False
        assert fake.edit_calls() == []
    for _token, _detail, receipt in RECEIPT_CASES:
        fake = _ok_fake(receipt=receipt)
        assert _write(fake, slot_file)["ok"] is False
        assert fake.edit_calls() == []
    for body in (BODY, NONE_BODY):
        receipt = RECEIPT if body is BODY else NONE_RECEIPT
        result = vs.evaluate("write", body, [_comment(receipt)], SLOT)
        new = result["newBody"]
        a = body.index("-->\n") + 4
        b = body.index("<!-- superheroes:build-record -->")
        b2 = new.index("<!-- superheroes:build-record -->")
        assert new[:a] == body[:a]
        assert new[b2:] == body[b:]


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


def test_real_1437_legacy_body_refuses_markers_invalid():
    _body, fake = _real_fake(body_name="pr1437_body_legacy.md")
    result = vs.run_verb("check", PR, REPO, run=fake)
    assert result["reason"] == "markers-invalid"
    assert "followups marker appears 0 times" in result["detail"]
    assert fake.edit_calls() == []


def test_receipt_missing_fu2_refuses_followup_undispositioned(slot_file):
    receipt = _fixture("pr1442_receipt.md")
    marker = "<!-- superheroes:dispositions FU1 FU2 FU3 FU4 FU5 FU6 FU7 FU8 -->"
    assert receipt.count(marker) == 1
    assert receipt.count("\n- FU2:") == 1  # the prose bullet stays; only the marker loses FU2
    receipt = receipt.replace(marker, marker.replace(" FU2", ""))
    _body, fake = _real_fake(receipt=receipt)
    result = _write(fake, slot_file)
    assert result["ok"] is False
    assert result["reason"] == "followup-undispositioned"
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
    assert json.loads(out) == {"ok": False, "reason": "read-failed", "detail": "PR body is empty"}


@pytest.mark.parametrize("argv", [
    [], ["frob"], ["check", "--pr", "x", "--repo", REPO], ["check", "--repo", REPO],
    ["check", "--pr", "42", "--repo", REPO, "--slot-file", "s"], ["write", "--pr", "42", "--repo", REPO],
])
def test_cli_bad_argument(capsys, argv):
    code = vs.main(argv, run=_ok_fake())
    assert code == 1
    assert json.loads(capsys.readouterr().out)["reason"] == "bad-argument"


@pytest.mark.parametrize("argv", [["-h"], ["--help"], ["check", "-h"], ["write", "--help"]])
def test_cli_help_prints_one_json_line(capsys, argv):
    code = vs.main(argv, run=_ok_fake())
    out = capsys.readouterr().out
    assert code == 1
    assert out.endswith("\n") and out.count("\n") == 1
    assert json.loads(out)["reason"] == "bad-argument"


# --- marker drift: the prose that teaches the markers matches what the writer reads ------------

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))


def _doc(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as handle:
        return handle.read()


def _one_block(blocks, needle, where):
    found = [b for b in blocks if needle in b]
    assert len(found) == 1, "%s: expected one block carrying %r, found %d" % (where, needle, len(found))
    return found[0]


def test_marker_shapes_are_taught_in_the_prose():
    workhorse = _doc(PLUGIN, "skills", "workhorse", "SKILL.md").split("\n\n")
    followups = _one_block(workhorse, "`- FU<n> [<class>] <text>`", "workhorse Follow-ups paragraph")
    receipt = _doc(PLUGIN, "skills", "showrunner", "reference", "vet-receipt.md")
    field7 = re.search(r"^7\. \*\*Dispositions.*?(?=^\d+\. |\Z)", receipt, re.M | re.S)
    assert field7, "vet-receipt.md field 7 not found"
    field7 = field7.group(0)
    taught = [
        (followups, vs.FOLLOWUPS_MARKER_NAME, "<!-- superheroes:followups FU1 FU2 -->", ["FU1", "FU2"]),
        (followups, vs.FOLLOWUPS_MARKER_NAME, "<!-- superheroes:followups none -->", None),
        (field7, vs.DISPOSITIONS_MARKER_NAME, "<!-- superheroes:dispositions FU1 FU2 -->", ["FU1", "FU2"]),
        (field7, vs.DISPOSITIONS_MARKER_NAME, "<!-- superheroes:dispositions none -->", None),
    ]
    for block, name, example, ids in taught:
        assert "`%s`" % example in block, example
        assert vs.read_marker_list(example + "\n", name) == ids, example
    skeleton = re.search(r"^<!-- superheroes:vet-receipt -->$.*?^```$", receipt, re.M | re.S)
    assert skeleton, "vet-receipt.md receipt skeleton not found"
    assert [ln for ln in skeleton.group(0).splitlines()
            if ln.startswith("<!-- superheroes:dispositions ")], "receipt skeleton lacks the marker"


def test_receipt_markers_match_conventions_10_7():
    conventions = _doc(PLUGIN, "..", "..", "CONVENTIONS.md")
    section = re.search(r"^### 10\.7 .*?(?=^### )", conventions, re.M | re.S)
    assert section, "CONVENTIONS section 10.7 not found"
    for marker in (vs.RECEIPT_MARKER, vs.PENDING_MARKER):
        assert "`%s`" % marker in section.group(0), marker
    for prefix in ("<!-- superheroes:followups", "<!-- superheroes:dispositions"):
        assert prefix in section.group(0), prefix
