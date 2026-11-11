"""#2453: no text the plugin prepares for GitHub carries a bare at-sign mention.

`mention_guard` is the one chokepoint: `check` refuses (`bare-mention`), `wrap` neutralizes. The truth table below
is the contract (GitHub's mention grammar is unmeasured here: the session cannot reach GitHub's render endpoint).
The wiring tests post or compose a body carrying a login after an at-sign through each writer and assert the
refusal with no write issued (or, for `pr_comment.upsert` and the review record's summary, that the body sent has
no bare mention), and that a healthy sibling body goes through unchanged.

Bite-proof record: wo_2453_mention_guard
"""
import inspect
import json
import os
import subprocess
import sys
from types import SimpleNamespace

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import cloud_builder as cb  # noqa: E402
import cloud_relay as cr  # noqa: E402
import mention_guard as mg  # noqa: E402
import pr_body_stage as PBS  # noqa: E402
import pr_comment as pc  # noqa: E402
import review_record as rr  # noqa: E402
import test_pr_body_stage as TPB  # noqa: E402
import test_review_record as TRR  # noqa: E402
import test_vet_slot as TVS  # noqa: E402
import vet_slot as vs  # noqa: E402
from test_cloud_relay import world  # noqa: E402,F401  (the relay's fixture)

TICK = "`"
FENCE = TICK * 3

# (text, tokens the guard must report, in order)
FLAGGED = [
    ("ping @zwrose", ["@zwrose"]),
    ("@1 at line start", ["@1"]),
    ("collector @574", ["@574"]),
    ("(@octo)", ["@octo"]),
    ('"@octo"', ["@octo"]),
    ("*@octo*", ["@octo"]),
    ("\\@octo", ["@octo"]),
    ("@octo.", ["@octo"]),
    ("@octo. next", ["@octo"]),
    ("@org/team", ["@org"]),
    (TICK + "x" + TICK + "@893", ["@893"]),
    ("broken " + TICK + " example @893", ["@893"]),
    ("+@octo hi", ["@octo"]),
]

HEALTHY = [
    TICK + "@octo" + TICK,
    TICK * 2 + "a " + TICK + " @octo" + TICK * 2,
    FENCE + "python\n@pytest.fixture\ndef f(): pass\n" + FENCE + "\n",
    "~~~\n@pytest.fixture\n~~~\n",
    FENCE + "\n@octo\n" + FENCE + "\n",
    "~~~\n@octo\n~~~\n",
    "a.b@example.com",
    "ops+@example.com",
    "<ops+@example.com>",
    "x@octo",
    "_@octo",
    "<slot>@<generation>",
    "answers/card@3",
    "@@ -1,2 +1,3 @@",
    "@<pointer>",
    "@-octo",
]

# the body every wiring test sends: a bare mention, and the healthy sibling that must pass untouched
BAD = "Result.\n\nping @zwrose\n"
GOOD = ("Result.\n\nping " + TICK + "@zwrose" + TICK + ", mail a.b@example.com\n\n" + FENCE + "python\n"
        "@pytest.fixture\ndef f(): pass\n" + FENCE + "\n")


def _tokens(text):
    return [m["token"] for m in mg.bare_mentions(text)]


# ---------------------------------------------------------------- the truth table


@pytest.mark.parametrize("text,tokens", FLAGGED, ids=[t for t, _ in FLAGGED])
def test_g1_a_bare_mention_is_reported(text, tokens):
    # axis: G1 — a bare at-sign GitHub reads as a login is reported
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo_2453_mention_guard.md
    assert _tokens(text) == tokens
    verdict = mg.check(text)
    assert verdict == {"ok": False, "reason": "bare-mention", "mentions": mg.bare_mentions(text),
                       "remedy": mg.REMEDY}


@pytest.mark.parametrize("text", HEALTHY)
def test_healthy_rows_pass_untouched(text):
    assert mg.bare_mentions(text) == []
    assert mg.check(text) == {"ok": True}
    assert mg.wrap(text) == text


def test_g2_a_fenced_decorator_is_inert_in_backticks_and_tildes():
    # axis: G2 — lines md_fence marks inert are not scanned
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo_2453_mention_guard.md
    for fence in (FENCE, "~~~"):
        text = "before\n" + fence + "\n@pytest.fixture\n@octo\n" + fence + "\nafter @octo\n"
        assert mg.bare_mentions(text) == [{"line": 6, "token": "@octo"}]
        assert mg.check("x\n" + fence + "\n@pytest.fixture\n@octo\n" + fence + "\n") == {"ok": True}


def test_g3_an_inline_code_span_masks_its_mention_and_only_its_own():
    # axis: G3 — a mention inside an inline code span is not reported
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo_2453_mention_guard.md
    assert mg.check(TICK + "@octo" + TICK) == {"ok": True}
    assert mg.check(TICK * 2 + "a " + TICK + " @octo" + TICK * 2) == {"ok": True}
    assert _tokens(TICK + "@a" + TICK + " and @b") == ["@b"]
    assert _tokens("\\" + TICK + "@a" + TICK) == ["@a"]  # a backslash escapes the opening backtick


def test_g4_an_email_shaped_at_sign_is_not_a_login():
    # axis: G4 — the email boundary: a login must end at a non-word character, not run into a dotted domain
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo_2453_mention_guard.md
    for text in ("ops+@example.com", "a.b@example.com", "<ops+@example.com>", "see ops+@example.com now"):
        assert mg.check(text) == {"ok": True}
    assert _tokens("hi @example.com") == []  # a login that runs into a dotted domain is an address, not a mention
    assert _tokens("hi @example. ok") == ["@example"]


def test_line_numbers_are_one_based_and_in_text_order():
    text = "a\n@one\n" + FENCE + "\n@no\n" + FENCE + "\nb @two\n"
    assert mg.bare_mentions(text) == [{"line": 2, "token": "@one"}, {"line": 6, "token": "@two"}]


# ---------------------------------------------------------------- wrap


def test_g5_wrap_puts_a_mention_in_a_code_span():
    # axis: G5 — wrap's delimiter is one backtick longer than any run in the text
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo_2453_mention_guard.md
    wrapped = mg.wrap("ping @zwrose")
    assert wrapped == "ping " + TICK + "@zwrose" + TICK
    assert mg.bare_mentions(wrapped) == []


def test_g5_wrap_never_pairs_with_an_existing_backtick():
    # axis: G5 — the inserted delimiter cannot pair with an existing run
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo_2453_mention_guard.md
    text = "broken " + TICK + " example @893"
    wrapped = mg.wrap(text)
    assert mg.bare_mentions(wrapped) == []
    assert wrapped == "broken " + TICK + " example " + TICK * 2 + "@893" + TICK * 2
    assert wrapped.startswith("broken " + TICK + " ")  # the original backtick is still there, still unmatched
    assert mg.wrap(wrapped) == wrapped


@pytest.mark.parametrize("text", [
    "ping @zwrose", "broken " + TICK + " example @893", "@a @b", "\\@octo", TICK + "@a", "@a" + TICK,
    "x " + TICK * 3 + " @a @b " + TICK * 2 + " @c", "line one @a\r\nline two @b\r\n", "(@a)\n@b.\n",
])
def test_wrap_is_idempotent_and_leaves_no_bare_mention(text):
    wrapped = mg.wrap(text)
    assert mg.bare_mentions(wrapped) == []
    assert mg.wrap(wrapped) == wrapped


def test_wrap_keeps_everything_but_the_wrapped_tokens():
    text = "keep " + TICK + "@kept" + TICK + " and ops+@example.com\n" + FENCE + "\n@pytest.fixture\n" + FENCE + "\n@x\n"
    wrapped = mg.wrap(text)
    assert wrapped == text[:-3] + TICK * 4 + "@x" + TICK * 4 + "\n"  # the fence's run of three makes the delimiter four


# ---------------------------------------------------------------- the edges


@pytest.mark.parametrize("value", [None, 5, b"@octo", ["@octo"], {"a": "@octo"}])
def test_e1_non_string_input_is_no_mention(value):
    # E1: bare_mentions returns [], check is ok, wrap returns the value as it came
    assert mg.bare_mentions(value) == []
    assert mg.check(value) == {"ok": True}
    assert mg.wrap(value) is value


def test_e2_empty_text_is_clean():
    assert mg.bare_mentions("") == [] and mg.check("") == {"ok": True} and mg.wrap("") == ""


def test_e3_an_unterminated_fence_masks_nothing():
    # E3: an unterminated fence masks no line, so a list-contained fence whose indented closer md_fence reads
    # as a new opener cannot hide the prose after it
    text = "top\n" + FENCE + "\n@octo\nmore @octo\n"
    assert _tokens(text) == ["@octo", "@octo"]
    assert _tokens("@before\n" + text) == ["@before", "@octo", "@octo"]


def test_a_fence_inside_a_list_cannot_mask_the_prose_after_it():
    # axis: the list-contained fence of the review's finding; the mention after it is reported and refused
    text = "- " + FENCE + "\n  example\n  " + FENCE + "\n\nping @octo\n"
    assert [m["line"] for m in mg.bare_mentions(text)] == [5]
    assert mg.check(text)["reason"] == "bare-mention"


def test_a_code_span_crossing_a_line_break_pairs_across_it():
    # axis: GFM pairs a code span across a paragraph's lines, so the closer on line two leaves the mention outside
    text = "begin " + TICK + "code\nend" + TICK + " then @octo " + TICK + "literal\n"
    assert [m["line"] for m in mg.bare_mentions(text)] == [2]
    multi = TICK + "first\nsecond" + TICK + " @octo " + TICK + "tail" + TICK + "\n"
    assert _tokens(multi) == ["@octo"]
    # a span that really holds the at-sign across a line break still masks it
    assert mg.bare_mentions(TICK + "a\n@octo b" + TICK + "\n") == []


def test_table_cells_pair_code_spans_on_their_own():
    # axis: a backtick in one cell cannot pair with one in another cell
    table = "| a | b | c |\n| --- | --- | --- |\n| " + TICK + "x | @octo | y" + TICK + " |\n"
    assert [m["line"] for m in mg.bare_mentions(table)] == [3]
    assert mg.wrap(table) == table.replace("@octo", TICK * 2 + "@octo" + TICK * 2)
    inside = "| a | b |\n| --- | --- |\n| x | " + TICK + "@octo" + TICK + " |\n"
    assert mg.bare_mentions(inside) == []


def test_an_at_sign_inside_a_link_or_url_is_left_alone():
    # axis: GitHub renders a link destination, an autolink and a bare URL as an anchor, which it never mentions in
    for text in ("[package](https://www.npmjs.com/package/@playwright/test)\n",
                 "see <https://www.npmjs.com/package/@playwright/test> now\n",
                 "see https://www.npmjs.com/package/@playwright/test now\n",
                 "<div><a href=\"https://www.npmjs.com/package/@playwright/test\">pkg</a></div>\n"):
        assert mg.bare_mentions(text) == []
        assert mg.wrap(text) == text
    # the link text is still prose, and a mention beside a URL is still reported
    assert _tokens("[ask @octo](https://example.com/x) and https://example.com/@ok then @hubot\n") == [
        "@octo", "@hubot"]


def test_a_raw_html_block_is_scanned_and_wrapped_in_a_code_element():
    # axis: a backtick inside a raw HTML block is literal, so it masks nothing and wrap uses a code element
    text = "<div>\n" + TICK + "@octo" + TICK + " and @hubot\n</div>\n\nafter " + TICK + "@kept" + TICK + "\n"
    assert _tokens(text) == ["@octo", "@hubot"]
    wrapped = mg.wrap(text)
    assert "<code>@hubot</code>" in wrapped and "<code>@octo</code>" in wrapped
    assert wrapped.endswith("after " + TICK + "@kept" + TICK + "\n")
    assert mg.bare_mentions(wrapped) == [] and mg.wrap(wrapped) == wrapped


def test_e4_a_mention_on_the_same_line_as_a_closed_span_but_outside_it_is_reported():
    assert _tokens(TICK + "@in" + TICK + " then @out") == ["@out"]
    assert mg.wrap(TICK + "@in" + TICK + " then @out") == TICK + "@in" + TICK + " then " + TICK * 2 + "@out" + TICK * 2


def test_e5_crlf_line_endings_keep_fences_and_lines_working():
    fenced = "a\r\n" + FENCE + "\r\n@octo\r\n" + FENCE + "\r\n@bare\r\n"
    assert mg.bare_mentions(fenced) == [{"line": 5, "token": "@bare"}]
    assert mg.bare_mentions("x\r\n@octo\r\n") == [{"line": 2, "token": "@octo"}]
    assert mg.wrap("x\r\n@octo\r\n") == "x\r\n" + TICK + "@octo" + TICK + "\r\n"


def _cli(*args, stdin=None):
    return subprocess.run([sys.executable, "-B", os.path.join(_LIB, "mention_guard.py"), *args],
                          input=stdin, capture_output=True, text=True)


def test_cli_check_exits_0_on_ok_and_1_on_a_bare_mention(tmp_path):
    ok, bad = tmp_path / "ok.md", tmp_path / "bad.md"
    ok.write_text(GOOD, encoding="utf-8")
    bad.write_text(BAD, encoding="utf-8")
    out = _cli("check", "--file", str(ok))
    assert (out.returncode, json.loads(out.stdout)) == (0, {"ok": True})
    out = _cli("check", "--file", str(bad))
    assert out.returncode == 1
    assert json.loads(out.stdout) == {"ok": False, "reason": "bare-mention", "remedy": mg.REMEDY,
                                      "mentions": [{"line": 3, "token": "@zwrose"}]}


def test_e7_cli_check_with_a_missing_flag_or_an_unreadable_file_exits_2(tmp_path):
    assert _cli("check").returncode == 2
    assert _cli().returncode == 2
    out = _cli("check", "--file", str(tmp_path / "absent.md"))
    assert out.returncode == 2 and json.loads(out.stdout) == {"ok": False, "reason": "input-unreadable"}
    binary = tmp_path / "bin.md"
    binary.write_bytes(b"\xff\xfe\x00bad")
    out = _cli("check", "--file", str(binary))
    assert out.returncode == 2 and json.loads(out.stdout) == {"ok": False, "reason": "input-unreadable"}


def test_cli_wrap_reads_stdin_and_writes_the_wrapped_text():
    out = _cli("wrap", stdin="ping @zwrose\n")
    assert (out.returncode, out.stdout) == (0, "ping " + TICK + "@zwrose" + TICK + "\n")


# ---------------------------------------------------------------- the wiring: cloud_builder


class _Gh:
    """A recording `run`: every `gh` call is kept; the POST and PATCH answer with a comment URL and no id."""

    def __init__(self):
        self.calls = []

    def __call__(self, argv, **kwargs):
        self.calls.append(list(argv))
        return SimpleNamespace(returncode=0, stdout=json.dumps({"html_url": "https://github.com/o/r/issues/1#c1"}),
                               stderr="")


def _body_file(tmp_path, text):
    path = tmp_path / "body.md"
    path.write_text(text, encoding="utf-8")
    return str(path)


def _assert_refusal(result, token="@zwrose"):
    assert result["ok"] is False and result["reason"] == "bare-mention"
    assert [m["token"] for m in result["mentions"]] == [token]
    assert result["remedy"] == mg.REMEDY


def test_g6_post_comment_refuses_a_bare_mention_before_any_gh_call(tmp_path):
    # axis: G6 — post_comment reads the body file and refuses before the write
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo_2453_mention_guard.md
    run = _Gh()
    result = cb.post_comment("o/r", 1, _body_file(tmp_path, BAD), run=run, env={})
    _assert_refusal(result)
    assert result["url"] is None and run.calls == []
    healthy = cb.post_comment("o/r", 1, _body_file(tmp_path, GOOD), run=run, env={})
    assert healthy["ok"] is True
    assert [c[:4] for c in run.calls] == [["gh", "api", "-X", "POST"]]


def test_g7_edit_comment_refuses_a_bare_mention_before_any_gh_call(tmp_path):
    # axis: G7 — edit_comment reads the body file and refuses before the rewrite
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo_2453_mention_guard.md
    run = _Gh()
    result = cb.edit_comment("o/r", 7, _body_file(tmp_path, BAD), run=run, env={})
    _assert_refusal(result)
    assert result["url"] is None and run.calls == []
    healthy = cb.edit_comment("o/r", 7, _body_file(tmp_path, GOOD), run=run, env={})
    assert healthy["ok"] is True
    assert [c[:4] for c in run.calls][0] == ["gh", "api", "-X", "PATCH"]


def test_e6_an_unreadable_body_file_keeps_todays_behaviour(tmp_path):
    # E6: the guard has nothing to read, so the write goes on exactly as before (the transit check reports it)
    run = _Gh()
    missing = str(tmp_path / "absent.md")
    assert cb.post_comment("o/r", 1, missing, run=run, env={})["ok"] is True
    assert cb.edit_comment("o/r", 7, missing, run=run, env={})["ok"] is True
    assert len(run.calls) >= 2


def _main(capsys, *argv):
    code = cb.main(list(argv))
    return code, json.loads(capsys.readouterr().out)


def test_g8_note_text_refuses_a_bare_mention_and_the_cli_exits_1(tmp_path, capsys):
    # axis: G8 — the composed note is checked before it is returned
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo_2453_mention_guard.md
    _assert_refusal(cb.note_text("ping @zwrose"))
    code, out = _main(capsys, "note", "--question-file", _body_file(tmp_path, "ping @zwrose"))
    assert code == 1 and out["reason"] == "bare-mention"
    healthy = cb.note_text(GOOD)
    assert healthy["comment"].startswith(cb.NOTE_HEADER) and GOOD.strip() in healthy["comment"]
    code, out = _main(capsys, "note", "--question-file", _body_file(tmp_path, GOOD))
    assert code == 0 and "comment" in out


def test_g9_progress_text_refuses_a_bare_mention_and_the_cli_exits_1(capsys):
    # axis: G9 — the composed progress comment is checked before it is returned
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo_2453_mention_guard.md
    started = "2026-01-02T03:04:05Z"
    _assert_refusal(cb.progress_text("building", "ping @zwrose", started, 30))
    code, out = _main(capsys, "progress", "--phase", "building", "--running", "ping @zwrose",
                      "--started", started, "--expected-minutes", "30")
    assert code == 1 and out["reason"] == "bare-mention"
    healthy = cb.progress_text("building", "ping " + TICK + "@zwrose" + TICK + " a.b@example.com", started, 30)
    assert healthy["ok"] is True and "a.b@example.com" in healthy["comment"]


def test_g10_terminal_text_refuses_a_bare_mention_and_the_cli_exits_1(tmp_path, capsys):
    # axis: G10 — the composed handback, stop or park is checked before it is returned
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo_2453_mention_guard.md
    for kind in ("handback", "stop", "park"):
        _assert_refusal(cb.terminal_text(kind, "ping @zwrose"))
    code, out = _main(capsys, "terminal", "--kind", "stop", "--text-file", _body_file(tmp_path, "ping @zwrose"))
    assert code == 1 and out["reason"] == "bare-mention"
    healthy = cb.terminal_text("park", GOOD)
    assert healthy["ok"] is True and healthy["comment"].endswith(GOOD.strip())


# ---------------------------------------------------------------- the wiring: cloud_relay


def _compose(world, text):
    return cr.compose(world.repo, world.config, "builder-1748", text, env=world.env)


def test_g11_cloud_relay_compose_refuses_a_bare_mention_before_any_state_or_file(world):
    # axis: G11 — compose checks the body right after text-empty, before the state opens
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo_2453_mention_guard.md
    result = _compose(world, BAD)
    _assert_refusal(result)
    state_path, why = cr._state_path(world.repo, world.env)
    assert why is None
    assert not os.path.exists(state_path)
    assert not os.path.exists(os.path.join(os.path.dirname(state_path), "relay-messages"))
    healthy = _compose(world, GOOD)
    assert healthy["ok"] is True
    with open(healthy["commentBodyFile"], encoding="utf-8") as fh:
        assert GOOD.rstrip() in fh.read()


# ---------------------------------------------------------------- the wiring: pr_body_stage


def test_g12_publish_refuses_a_staged_body_with_a_bare_mention_and_never_rewrites_it(tmp_path):
    # axis: G12 — publish checks the staged body after the unchanged-return and before the audit and the PATCH
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo_2453_mention_guard.md
    bad = TPB.FIXED + "ping @zwrose\n"
    sd = TPB._staged_fixed(tmp_path, fixed=bad)
    gh = TPB.FakeGh(views=[TPB.BODY, bad])
    out = PBS.publish(sd, 7, runner=gh)
    assert PBS.REASON_BARE_MENTION == "bare-mention"
    assert (out["ok"], out["outcome"], out["reason"]) == (False, "refused", "bare-mention")
    assert out["mentions"] == [{"line": bad.count("\n"), "token": "@zwrose"}]
    assert gh.edits() == []
    assert TPB._read(PBS.paths(sd)["staged"]) == bad
    assert TPB._receipt(sd) == out
    assert "login" in PBS.record_line(sd)


def test_g12_a_healthy_staged_body_is_published(tmp_path):
    good = TPB.FIXED + GOOD
    sd = TPB._staged_fixed(tmp_path, fixed=good)
    gh = TPB.FakeGh(views=[TPB.BODY, good])
    out = PBS.publish(sd, 7, runner=gh)
    assert (out["ok"], out["outcome"], out["reason"]) == (True, "published", None)
    assert len(gh.edits()) == 1 and "mentions" not in out


# ---------------------------------------------------------------- the wiring: vet_slot


def _write(slot_text):
    return vs.evaluate("write", TVS.BODY, [TVS._comment(TVS.RECEIPT)], slot_text, advisor_login="advisor")


def test_g13_vet_slot_check_slot_text_refuses_a_bare_mention():
    # axis: G13 — slot text carrying a bare mention refuses write-failed, the detail opening bare-mention: and naming the tokens and the remedy
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo_2453_mention_guard.md
    result = _write(TVS.SLOT + "ping @zwrose\n")
    assert result["ok"] is False and result["reason"] == "write-failed"
    assert result["detail"].startswith("bare-mention:")
    assert "@zwrose" in result["detail"] and "code span" in result["detail"]
    assert "newBody" not in result
    with pytest.raises(vs._Refusal) as raised:
        vs.check_slot_text("ping @zwrose")
    assert raised.value.reason == "write-failed"
    assert raised.value.detail.startswith("bare-mention:")


def test_vet_slot_emits_no_bare_mention_token_of_its_own():
    # the vet_slot refusal census stays at its existing set: the guard's refusal rides write-failed
    assert "_Refusal(\"bare-mention\"" not in inspect.getsource(vs)


def test_g13_a_healthy_slot_text_is_written():
    result = _write(TVS.SLOT + GOOD)
    assert result["ok"] is True and GOOD in result["newBody"]


# ---------------------------------------------------------------- the wiring: pr_comment


def _upsert(monkeypatch, body, family="results"):
    posted = {}

    def fake_gh(*args, inp=None):
        if args[:3] == ("api", "-X", "POST"):
            posted["body"] = next(a[len("body="):] for a in args if a.startswith("body="))
            return '{"id": 42}'
        return ""

    monkeypatch.setattr(pc, "gh_user", lambda: "zwrose")
    monkeypatch.setattr(pc, "list_comments", lambda pr: [])
    monkeypatch.setattr(pc, "_gh", fake_gh)
    pc.upsert(123, family, "main", body)
    return posted["body"]


def test_g14_upsert_wraps_a_bare_mention_in_a_code_span(monkeypatch):
    # axis: G14 — upsert wraps a bare mention after the scrub and before the marker and the write
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo_2453_mention_guard.md
    sent = _upsert(monkeypatch, BAD)
    assert mg.bare_mentions(sent) == []
    assert TICK + "@zwrose" + TICK in sent
    assert sent.startswith(pc.render_marker("results", "main") + "\n")


def test_g14_a_healthy_comment_body_is_sent_unchanged_but_for_the_marker(monkeypatch):
    sent = _upsert(monkeypatch, GOOD)
    assert sent == pc.render_marker("results", "main") + "\n" + GOOD


# ---------------------------------------------------------------- the wiring: review_record


def _record_with(reason):
    return TRR.build(TRR.account(laneReason=reason))


def test_g15_the_record_summary_wraps_a_bare_mention_and_the_json_block_is_untouched():
    # axis: G15 — the record comment's prose summary is wrapped; readers parse only the JSON block
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo_2453_mention_guard.md
    rec = _record_with("ping @zwrose")
    body = rr.render(rec)
    assert mg.bare_mentions(body) == []
    prose = body.split("<details>")[0]
    assert TICK + "@zwrose" + TICK in prose and "ping @zwrose" not in prose
    assert rr._json_block(body)["lane"]["reason"] == "ping @zwrose"


def test_g15_the_head_comment_summary_of_a_record_in_parts_is_wrapped_too():
    rec = _record_with("ping @zwrose")
    rec["whatIsMissing"] = rec["whatIsMissing"] + ["w" * rr.MAX_BODY_CHARS]
    plan = rr.render_plan(rec)
    assert plan.parts
    head = plan.head(list(range(1, len(plan.parts) + 1)))
    assert mg.bare_mentions(head) == []
    assert TICK + "@zwrose" + TICK in head.split("<details>")[0]


def test_g15_a_healthy_record_summary_is_unchanged():
    healthy = _record_with("big change, see " + TICK + "@zwrose" + TICK + " and a.b@example.com")
    body = rr.render(healthy)
    assert "big change, see " + TICK + "@zwrose" + TICK + " and a.b@example.com" in body.split("<details>")[0]
