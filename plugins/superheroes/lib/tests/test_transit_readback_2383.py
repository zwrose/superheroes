"""Tests for the transit comparison and its read-backs (#2383): cloud_builder's `transit_compare`,
`transit_line`, `post_comment`, `edit_comment` and the `readback` verb, and `pr_comment.upsert`.

A cloud session's GitHub egress can change text in transit (it deletes a `!` directly before a `[`
when a `]` appears later in the body, and appends one cloud footer). These tests pin that the write
paths read the comment back and say so when it differs.

No test runs a real `gh` or touches the network: `cloud_builder` is driven through an injected `run`
(or a patched `subprocess.run` for the CLI), `pr_comment` through a patched `_gh`.

bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2383_transit_compare.md
"""
import json
import os
import sys
from types import SimpleNamespace

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.join(_HERE, "..")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import cloud_builder as cb  # noqa: E402
import pr_comment as pc  # noqa: E402

BANG_BODY = "intro\n\n<![CDATA[x]]>\n\ntail"
BANG_LOST = "intro\n\n<[CDATA[x]]>\n\ntail"
ESCAPED_BANG = "\\u0021"  # the six characters backslash, u, 0, 0, 2, 1


class FakeGh:
    """A fake `run`: a write (`-X`) answers `write_out`; a read answers the held body, or fails.

    `held` is a string (the body GitHub holds), None (a JSON null body), or the sentinel FAIL (the read
    exits non-zero); `read_out` overrides the whole read stdout.
    """

    FAIL = object()

    def __init__(self, held="", write_out=None, read_out=None):
        self.held = held
        self.write_out = json.dumps({"id": 55, "html_url": "https://example.test/c/55"}) if write_out is None else write_out
        self.read_out = read_out
        self.calls = []

    def __call__(self, argv, **kwargs):
        self.calls.append(list(argv))
        if "-X" in argv:
            return SimpleNamespace(returncode=0, stdout=self.write_out, stderr="")
        if self.held is self.FAIL:
            return SimpleNamespace(returncode=1, stdout="", stderr="boom")
        out = self.read_out if self.read_out is not None else json.dumps({"body": self.held})
        return SimpleNamespace(returncode=0, stdout=out, stderr="")

    @property
    def reads(self):
        return [argv for argv in self.calls if "-X" not in argv]


def _sent_file(tmp_path, text):
    path = tmp_path / "body.md"
    path.write_text(text, encoding="utf-8")
    return str(path)


# ---------------------------------------------------------------- transit_compare


def test_a_dropped_bang_reads_changed_through_post_comment(tmp_path):
    # axis: E1/E5 — a body GitHub changed in transit is reported changed, through the post write path
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2383_transit_compare.md
    run = FakeGh(held=BANG_LOST)
    result = cb.post_comment("o/r", 3, _sent_file(tmp_path, BANG_BODY), run=run, env={})
    assert result["ok"] is True
    assert result["transit"]["transit"] == "changed"
    change = result["transit"]["changes"][0]
    assert change["sent"] == "!" and change["found"] == ""
    assert change["line"] == 3
    line = result["transitLine"]
    assert line.startswith("Transit damage:")
    assert ESCAPED_BANG in line
    assert "!" not in line
    # the escape decodes, as JSON, to the original excerpt
    assert json.loads('"%s"' % ESCAPED_BANG) == "!"
    assert 'sent "%s"' % ESCAPED_BANG in line


def test_an_identical_read_back_matches_and_has_no_line(tmp_path):
    run = FakeGh(held="plain body\nsecond line")
    result = cb.post_comment("o/r", 3, _sent_file(tmp_path, "plain body\nsecond line"), run=run, env={})
    assert result["ok"] is True
    assert result["transit"] == {"transit": "matched"}
    assert "transitLine" not in result
    assert cb.transit_line(result["transit"]) is None


def test_one_trailing_cloud_footer_is_tolerated():
    held = "body text" + "\n\n" + cb.CLOUD_FOOTER
    assert cb.transit_compare("body text", held) == {"transit": "matched"}


def test_line_endings_and_trailing_whitespace_are_tolerated():
    assert cb.transit_compare("a\nb\n", "a\r\nb  \r\n\r\n") == {"transit": "matched"}


def test_a_failed_read_back_is_not_checked_never_matched(tmp_path):
    # axis: E4 — a read-back that could not be made is not-checked, never matched
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2383_transit_compare.md
    run = FakeGh(held=FakeGh.FAIL)
    result = cb.post_comment("o/r", 3, _sent_file(tmp_path, "body"), run=run, env={})
    assert result["ok"] is True
    assert result["transit"]["transit"] == "not-checked"
    assert result["transit"]["transit"] != "matched"
    assert result["transitLine"].startswith("Transit check: not checked")


def test_a_lost_leading_indent_reads_changed():
    # axis: E3 — only trailing whitespace is normalized; a lost four-space indent turns a code block into prose
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2383_transit_compare.md
    result = cb.transit_compare("    code line\nmore", "code line\nmore")
    assert result["transit"] == "changed"
    assert result["changes"][0]["sent"] == "    "


def test_a_second_footer_reads_changed():
    # axis: E2 — exactly one trailing footer is tolerated; a second one is a change
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2383_transit_compare.md
    held = "body text" + "\n\n" + cb.CLOUD_FOOTER + "\n\n" + cb.CLOUD_FOOTER
    result = cb.transit_compare("body text", held)
    assert result["transit"] == "changed"
    assert result["changeCount"] >= 1
    assert cb.CLOUD_FOOTER in result["changes"][0]["found"] or result["changes"][0]["found"].startswith("\n\n---")


def test_a_post_response_without_an_id_is_not_checked(tmp_path):
    run = FakeGh(held="body", write_out=json.dumps({"html_url": "https://example.test/c/1"}))
    result = cb.post_comment("o/r", 3, _sent_file(tmp_path, "body"), run=run, env={})
    assert result["ok"] is True
    assert result["transit"]["transit"] == "not-checked"
    assert run.reads == []
    assert result["transitLine"].startswith("Transit check: not checked")


@pytest.mark.parametrize("write_out", ["not json", "[1, 2]", json.dumps({"id": "55"}), json.dumps({"id": True})])
def test_a_post_response_with_no_integer_id_is_not_checked(tmp_path, write_out):
    run = FakeGh(held="body", write_out=write_out)
    result = cb.post_comment("o/r", 3, _sent_file(tmp_path, "body"), run=run, env={})
    assert result["ok"] is True
    assert result["transit"]["transit"] == "not-checked"
    assert run.reads == []


def test_an_unreadable_sent_file_is_not_checked(tmp_path):
    run = FakeGh(held="body")
    result = cb.post_comment("o/r", 3, str(tmp_path / "missing.md"), run=run, env={})
    assert result["ok"] is True
    assert result["transit"] == {"transit": "not-checked", "why": "the sent text could not be read"}


@pytest.mark.parametrize("held", [None, 5, ["x"]])
def test_a_found_text_that_is_not_a_string_is_not_checked(held):
    assert cb.transit_compare("body", held) == {"transit": "not-checked", "why": "the text could not be read back"}


@pytest.mark.parametrize("sent", [None, 5, b"body"])
def test_a_sent_text_that_is_not_a_string_is_not_checked(sent):
    assert cb.transit_compare(sent, "body") == {"transit": "not-checked", "why": "the sent text could not be read"}


def test_an_exception_inside_the_comparison_is_not_checked(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("diff exploded")

    monkeypatch.setattr(cb.difflib, "SequenceMatcher", boom)
    result = cb.transit_compare("one", "two")
    assert result["transit"] == "not-checked"
    assert isinstance(result["why"], str) and result["why"]


@pytest.mark.parametrize("held", [FakeGh.FAIL, "unparseable"])
def test_unreadable_read_backs_are_not_checked(tmp_path, held):
    if held == "unparseable":
        run = FakeGh(read_out="{not json")
    else:
        run = FakeGh(held=held)
    result = cb.post_comment("o/r", 3, _sent_file(tmp_path, "body"), run=run, env={})
    assert result["transit"]["transit"] == "not-checked"


@pytest.mark.parametrize("read_out", [json.dumps({"body": 7}), json.dumps({"body": None}),
                                      json.dumps({"nobody": "x"}), json.dumps(["body"])])
def test_a_comment_body_that_is_not_a_string_is_not_checked(tmp_path, read_out):
    run = FakeGh(read_out=read_out)
    result = cb.post_comment("o/r", 3, _sent_file(tmp_path, "body"), run=run, env={})
    assert result["transit"]["transit"] == "not-checked"


def test_more_than_the_cap_of_differences_is_capped_with_the_true_count():
    count = cb.TRANSIT_MAX_CHANGES + 5
    sent = "".join("<![A%d]>\n" % i for i in range(count))
    found = sent.replace("![", "[")
    result = cb.transit_compare(sent, found)
    assert result["transit"] == "changed"
    assert result["changeCount"] == count
    assert len(result["changes"]) == cb.TRANSIT_MAX_CHANGES
    line = cb.transit_line(result)
    assert line.startswith("Transit damage:")
    assert "in %d place(s)" % count in line
    assert "(and 5 more)" in line
    assert "!" not in line


def test_a_long_span_is_quoted_to_the_excerpt_length():
    long = "x" * (cb.TRANSIT_EXCERPT_CHARS * 3)
    result = cb.transit_compare("a" + long + "b", "ab")
    assert result["transit"] == "changed"
    assert len(result["changes"][0]["sent"]) == cb.TRANSIT_EXCERPT_CHARS


def test_transit_line_for_results_that_are_not_a_result():
    for result in (None, "matched?", {"transit": "bogus"}, {}, {"transit": "not-checked"}):
        line = cb.transit_line(result)
        assert line == ("Transit check: not checked (no result), so it is not known whether the text "
                        "arrived intact.")
    named = cb.transit_line({"transit": "not-checked", "why": "the text could not be read back"})
    assert named == ("Transit check: not checked (the text could not be read back), so it is not known "
                     "whether the text arrived intact.")


def test_transit_line_for_a_malformed_changed_result_is_not_a_match():
    line = cb.transit_line({"transit": "changed", "changeCount": 1})
    assert line.startswith("Transit check: not checked")


# ---------------------------------------------------------------- edit_comment


def test_edit_comment_reports_a_changed_read_back(tmp_path):
    # axis: E6 — a rewrite is read back by its comment id and compared
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2383_transit_compare.md
    run = FakeGh(held=BANG_LOST)
    result = cb.edit_comment("o/r", 77, _sent_file(tmp_path, BANG_BODY), run=run, env={})
    assert result["ok"] is True
    assert result["transit"]["transit"] == "changed"
    assert result["transitLine"].startswith("Transit damage:")
    assert run.reads == [["gh", "api", "repos/o/r/issues/comments/77"]]


def test_edit_comment_reports_a_matched_read_back(tmp_path):
    run = FakeGh(held=BANG_BODY + "\n\n" + cb.CLOUD_FOOTER)
    result = cb.edit_comment("o/r", 77, _sent_file(tmp_path, BANG_BODY), run=run, env={})
    assert result["ok"] is True
    assert result["transit"] == {"transit": "matched"}
    assert "transitLine" not in result


def test_edit_comment_with_a_failed_read_back_is_not_checked(tmp_path):
    run = FakeGh(held=FakeGh.FAIL)
    result = cb.edit_comment("o/r", 77, _sent_file(tmp_path, "body"), run=run, env={})
    assert result["ok"] is True
    assert result["transit"]["transit"] == "not-checked"


def test_the_existing_write_refusals_are_unchanged():
    run = FakeGh()
    assert cb.post_comment("o/r", 0, "/b", run=run, env={})["reason"] == "github-write-failed"
    assert cb.edit_comment("../x", 5, "/b", run=run, env={})["reason"] == "github-write-failed"
    assert run.calls == []


def test_a_failed_write_has_no_transit(tmp_path):
    def run(argv, **kwargs):
        return SimpleNamespace(returncode=1, stdout="", stderr="no")

    result = cb.post_comment("o/r", 3, _sent_file(tmp_path, "body"), run=run, env={})
    assert result == {"ok": False, "reason": "github-write-failed", "url": None}


# ---------------------------------------------------------------- read helpers


def test_read_pr_body_reads_a_null_body_as_empty_and_failures_as_none():
    assert cb.read_pr_body("o/r", 4, run=FakeGh(read_out=json.dumps({"body": None})), env={}) == ""
    assert cb.read_pr_body("o/r", 4, run=FakeGh(read_out=json.dumps({"body": "text"})), env={}) == "text"
    assert cb.read_pr_body("o/r", 4, run=FakeGh(held=FakeGh.FAIL), env={}) is None
    assert cb.read_pr_body("o/r", 4, run=FakeGh(read_out=json.dumps({"body": 3})), env={}) is None
    assert cb.read_pr_body("o/r", 4, run=FakeGh(read_out=json.dumps({})), env={}) is None
    run = FakeGh()
    assert cb.read_pr_body("bad repo", 4, run=run, env={}) is None
    assert cb.read_pr_body("o/r", True, run=run, env={}) is None
    assert run.calls == []


def test_read_comment_body_refuses_bad_arguments_without_running_gh():
    run = FakeGh()
    assert cb.read_comment_body("bad repo", 4, run=run, env={}) is None
    assert cb.read_comment_body("o/r", 0, run=run, env={}) is None
    assert cb.read_comment_body("o/r", True, run=run, env={}) is None
    assert cb.read_comment_body("o/r", "4", run=run, env={}) is None
    assert run.calls == []


# ---------------------------------------------------------------- the readback verb


def _cli(monkeypatch, capsys, run, *argv):
    monkeypatch.setattr(cb.subprocess, "run", run)
    code = cb.main(list(argv))
    return code, json.loads(capsys.readouterr().out)


def test_readback_by_comment_id_matched(tmp_path, monkeypatch, capsys):
    run = FakeGh(held=BANG_BODY)
    code, out = _cli(monkeypatch, capsys, run, "readback", "--repo", "o/r", "--comment-id", "55",
                     "--sent-file", _sent_file(tmp_path, BANG_BODY))
    assert code == 0
    assert out == {"ok": True, "transit": {"transit": "matched"}}
    assert run.calls == [["gh", "api", "repos/o/r/issues/comments/55"]]


def test_readback_by_comment_id_changed(tmp_path, monkeypatch, capsys):
    # axis: E8 — the verb reads the held text back and compares it with the sent file
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2383_transit_compare.md
    run = FakeGh(held=BANG_LOST)
    code, out = _cli(monkeypatch, capsys, run, "readback", "--repo", "o/r", "--comment-id", "55",
                     "--sent-file", _sent_file(tmp_path, BANG_BODY))
    assert code == 0
    assert out["ok"] is True
    assert out["transit"]["transit"] == "changed"
    assert out["transitLine"].startswith("Transit damage:")
    assert "!" not in out["transitLine"]


def test_readback_by_pr_matched_and_changed(tmp_path, monkeypatch, capsys):
    sent = _sent_file(tmp_path, BANG_BODY)
    run = FakeGh(held=BANG_BODY)
    code, out = _cli(monkeypatch, capsys, run, "readback", "--repo", "o/r", "--pr", "9", "--sent-file", sent)
    assert code == 0 and out["transit"] == {"transit": "matched"}
    assert run.calls == [["gh", "api", "repos/o/r/pulls/9"]]
    run = FakeGh(held=BANG_LOST)
    code, out = _cli(monkeypatch, capsys, run, "readback", "--repo", "o/r", "--pr", "9", "--sent-file", sent)
    assert code == 0 and out["transit"]["transit"] == "changed"


def test_readback_by_pr_reads_a_null_body_as_empty(tmp_path, monkeypatch, capsys):
    run = FakeGh(read_out=json.dumps({"body": None}))
    code, out = _cli(monkeypatch, capsys, run, "readback", "--repo", "o/r", "--pr", "9",
                     "--sent-file", _sent_file(tmp_path, ""))
    assert code == 0 and out["transit"] == {"transit": "matched"}


def test_readback_with_a_failed_read_is_ok_and_not_checked(tmp_path, monkeypatch, capsys):
    run = FakeGh(held=FakeGh.FAIL)
    code, out = _cli(monkeypatch, capsys, run, "readback", "--repo", "o/r", "--comment-id", "55",
                     "--sent-file", _sent_file(tmp_path, "body"))
    assert code == 0
    assert out["ok"] is True and out["transit"]["transit"] == "not-checked"
    assert out["transitLine"].startswith("Transit check: not checked")


def test_readback_with_an_unreadable_sent_file_is_ok_and_not_checked(tmp_path, monkeypatch, capsys):
    run = FakeGh(held="body")
    code, out = _cli(monkeypatch, capsys, run, "readback", "--repo", "o/r", "--comment-id", "55",
                     "--sent-file", str(tmp_path / "missing.md"))
    assert code == 0 and out["transit"]["transit"] == "not-checked"


def test_readback_refuses_a_bad_repo(tmp_path, monkeypatch, capsys):
    run = FakeGh(held="body")
    code, out = _cli(monkeypatch, capsys, run, "readback", "--repo", "not a repo", "--comment-id", "55",
                     "--sent-file", _sent_file(tmp_path, "body"))
    assert code == 1 and out == {"ok": False, "reason": "bad-argument"}
    assert run.calls == []


def test_readback_refuses_both_ids_and_neither_id(tmp_path, monkeypatch, capsys):
    sent = _sent_file(tmp_path, "body")
    run = FakeGh(held="body")
    # the function refuses both ids, and neither, as a bad argument
    assert cb.readback("o/r", sent, comment_id=5, pr=6, run=run, env={}) == {"ok": False, "reason": "bad-argument"}
    assert cb.readback("o/r", sent, run=run, env={}) == {"ok": False, "reason": "bad-argument"}
    assert cb.readback("o/r", sent, comment_id=0, run=run, env={}) == {"ok": False, "reason": "bad-argument"}
    assert cb.readback("o/r", sent, pr=True, run=run, env={}) == {"ok": False, "reason": "bad-argument"}
    assert cb.readback("o/r", "", pr=3, run=run, env={}) == {"ok": False, "reason": "bad-argument"}
    assert run.calls == []
    # the command line refuses them at the parser
    for ids in (["--comment-id", "5", "--pr", "6"], []):
        code, out = _cli(monkeypatch, capsys, run, "readback", "--repo", "o/r", *ids, "--sent-file", sent)
        assert code == 1 and out == {"ok": False, "reason": "usage"}
    assert run.calls == []


# ---------------------------------------------------------------- pr_comment.upsert


def _patch_upsert(monkeypatch, existing, held):
    """Patch pr_comment's gh seams. `held(sent_body)` returns the held body, or raises."""
    monkeypatch.setattr(pc, "gh_user", lambda: "zwrose")
    monkeypatch.setattr(pc, "list_comments", lambda pr: existing)
    seen = {"gets": []}

    def fake_gh(*args, inp=None):
        if "-X" in args:
            seen["sent"] = next(a[len("body="):] for a in args if a.startswith("body="))
            return '{"id": 42}'
        seen["gets"].append(args)
        return json.dumps({"body": held(seen["sent"])})

    monkeypatch.setattr(pc, "_gh", fake_gh)
    return seen


def test_upsert_create_reports_a_changed_read_back(monkeypatch):
    # axis: E7 — the final body sent is read back by comment id and compared
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2383_transit_compare.md
    seen = _patch_upsert(monkeypatch, [], lambda sent: sent.replace("![", "["))
    result = pc.upsert(123, "results", "feat%2Fx", "see ![shot](u.png) done")
    assert result["action"] == "created" and result["id"] == 42
    assert result["transit"]["transit"] == "changed"
    assert result["transit"]["changes"][0]["sent"] == "!"
    assert result["transitLine"].startswith("Transit damage:")
    assert "!" not in result["transitLine"]
    assert seen["gets"] == [("api", "repos/{owner}/{repo}/issues/comments/42")]


def test_upsert_edit_reports_a_matched_read_back(monkeypatch):
    key = "feat%2Fx"
    marker = pc.render_marker("plan", key)
    existing = [{"id": 7, "author": "zwrose", "body": f"{marker}\n- [x] done step\n- [ ] next"}]
    _patch_upsert(monkeypatch, existing, lambda sent: sent + "\n\n" + cb.CLOUD_FOOTER)
    result = pc.upsert(123, "plan", key, f"{marker}\n- [ ] done step\n- [ ] next")
    assert result["action"] == "edited" and result["id"] == 7
    assert result["transit"] == {"transit": "matched"}
    assert "transitLine" not in result


def test_upsert_compares_the_final_body_after_the_checkbox_merge(monkeypatch):
    key = "feat%2Fx"
    marker = pc.render_marker("plan", key)
    existing = [{"id": 7, "author": "zwrose", "body": f"{marker}\n- [x] done step"}]
    seen = _patch_upsert(monkeypatch, existing, lambda sent: sent)
    result = pc.upsert(123, "plan", key, f"{marker}\n- [ ] done step")
    assert "- [x] done step" in seen["sent"]
    assert result["transit"] == {"transit": "matched"}


def test_upsert_with_a_failing_read_back_is_not_checked(monkeypatch):
    monkeypatch.setattr(pc, "gh_user", lambda: "zwrose")
    monkeypatch.setattr(pc, "list_comments", lambda pr: [])

    def fake_gh(*args, inp=None):
        if "-X" in args:
            return '{"id": 42}'
        raise RuntimeError("gh api failed")

    monkeypatch.setattr(pc, "_gh", fake_gh)
    result = pc.upsert(123, "results", "feat%2Fx", "body")
    assert result["action"] == "created" and result["id"] == 42
    assert result["transit"]["transit"] == "not-checked"
    assert result["transitLine"].startswith("Transit check: not checked")


def test_upsert_with_an_unparseable_read_back_is_not_checked(monkeypatch):
    monkeypatch.setattr(pc, "gh_user", lambda: "zwrose")
    monkeypatch.setattr(pc, "list_comments", lambda pr: [])
    monkeypatch.setattr(pc, "_gh", lambda *args, inp=None: '{"id": 42}' if "-X" in args else "<html>")
    result = pc.upsert(123, "results", "feat%2Fx", "body")
    assert result["transit"]["transit"] == "not-checked"


def test_upsert_still_deletes_the_fallback_file(monkeypatch, tmp_path):
    pc.write_fallback(str(tmp_path), "feat%2Fx", "results", "old")
    _patch_upsert(monkeypatch, [], lambda sent: sent)
    pc.upsert(123, "results", "feat%2Fx", "body", plans_dir=str(tmp_path))
    assert not os.path.exists(pc.fallback_path(str(tmp_path), "feat%2Fx", "results"))
